"""급여 청크의 투여 조건 구조화 (§8 처리 흐름 6, chunk.reimbursement.conditions).

형식은 B의 설계 문서 reimbursement_chunking_design.md §3.5 (2026-10-16)를 따른다:
  all_of             모두 만족해야 하는 조건 항목
  any_of             '아래의 하나에 해당하는 경우'처럼 묶음 안에서 하나 이상 만족 (§3.5에 없는 칸, 묶음 조건용으로 추가)
  any_of_exceptions  '※ 단, … 경우도 급여 인정함' 같은 예외 분기
  line_rule          공고의 치료 단계·투여단계 (코드가 소단원에서 채운다. LLM이 쓰지 않음)
  stage_rules        소단원 머리 규칙 중 이 행 판정에 쓰는 것 (예: CDK4/6 + AI는 고식적 항암 미투여자만)
  counts_as_prior_line  이전 치료를 차수로 간주하는 규칙 (§3.1)
  notes              처방 조건 (판정 대상 아님. 예: LHRH agonist 병용 필요)
  human_review       사람 판단이 필요한 조건 (§9.4. 판정 결과는 covered_conditions_unverified)
  unmapped           어느 칸에도 옮기지 못한 원문 구절
조건 항목 = {id, field, op, value, text[, of][, unless]}. field 어휘와 환자 JSON 경로는 FIELDS
(reimbursement_field_values.csv의 input 행과 맞춤). 환자 JSON에서 field 값을 만드는 함수는 B가 맡는다.

LLM이 지어낸 조건을 막는 장치
  - 항목마다 원문 구절(text)을 그대로 복사하게 하고, 그 구절이 청크 본문(또는 소단원 안내)에 있는지 코드로 확인한다
  - field·op·value가 어휘에 없으면 버린다. 문제가 하나라도 있으면 그 청크의 조건 전체를 버리고 보고서에 남긴다
  - 결과는 사람이 전수 검수한다 (§3.5). export_review가 검수표(.tsv)를 만든다

비용과 재현성
  결과는 data/reimbursement/conditions_cache.jsonl에 (프롬프트 버전, 모델, 청크 본문) 해시로 저장한다.
  본문이 바뀐 청크만 다시 요청한다. API 키가 없으면 저장된 결과만 쓴다.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .dates import KST

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"
CACHE_PATH = DATA / "conditions_cache.jsonl"
MODEL = "claude-sonnet-5-5"          # PROJECT.md §9: 공고·지침 구조화
PROMPT_VERSION = "2026-10-19.1"       # 프롬프트·어휘를 바꾸면 올린다 (예전 저장 결과를 안 쓰게)

OPS = ["eq", "in", "not_contains", "contains", "gt", "gte", "lt", "lte", "exists"]
STAGES = ["0", "I", "IA", "IB", "II", "IIA", "IIB", "III", "IIIA", "IIIB", "IIIC", "IV"]
T_STAGES = ["Tis", "T1mi", "T1a", "T1b", "T1c", "T1", "T2", "T3", "T4", "T4a", "T4b", "T4c", "T4d"]
# 이전 치료 계열 이름: 공용 사전 drug_classes.csv의 drug_subclass·drug_class 값 (2026-10-17판:
# CDK4/6_inhibitor, immune_checkpoint_inhibitor 추가). 사전에 계열이 없는 묶음은 약 일반명을 모두 적는다
DRUG_SUBCLASSES = ["anthracycline", "taxane", "AI_nonsteroidal", "AI_steroidal", "LHRH_agonist",
                   "SERM", "SERD", "progestin", "CDK4/6_inhibitor", "immune_checkpoint_inhibitor"]
DRUG_CLASSES = ["Chemotherapy", "Hormone Therapy", "HER2-targeted Therapy", "Immunotherapy", "Other Targeted Therapy"]
LINE_STAGES = ["neoadjuvant", "adjuvant", "palliative_endocrine", "palliative_chemo", "combination", "supportive"]
LINE_RULES = ["1차", "1차 이상", "2차", "2차 이상", "3차 이상"]

_POSNEG = ["positive", "negative"]
_NUM = "number"
_DRUGS = "drugs"           # 값이 약 이름·계열 이름 목록 (사전 검사)

# field -> (환자 JSON 경로, 허용 op, 값 종류 또는 허용값 목록, 설명). 설명은 프롬프트에도 들어간다.
FIELDS: dict[str, tuple[str, list[str], object, str]] = {
    "her2": ("biomarker_record.records[HER2].status", ["eq", "in"], ["positive", "negative", "low", "ultralow"],
             "'HER2 양성(과발현)' -> eq positive, 'HER2 음성' -> in [negative, low, ultralow] (공고에 저발현 구분 없음)"),
    "hr": ("biomarker_record.subtype의 HR", ["eq"], _POSNEG,
           "'호르몬 수용체 양성' -> eq positive (ER 또는 PR 양성), '호르몬 수용체(ER and PR) 음성' -> eq negative"),
    "er": ("biomarker_record.records[ER].status", ["eq", "in"], ["positive", "low", "negative"],
           "에스트로겐 수용체만 따로 적힌 경우. 'ER 양성' -> in [positive, low]"),
    "pr": ("biomarker_record.records[PR].status", ["eq"], _POSNEG, "프로게스테론 수용체만 따로 적힌 경우"),
    "subtype": ("biomarker_record.subtype", ["eq", "in"], ["HR+/HER2-", "HR+/HER2+", "HR-/HER2+", "TNBC"],
                "'삼중음성' -> eq TNBC"),
    "menopause": ("patient_state.fields.patient.menopausal_status", ["eq", "in"],
                  ["premenopausal", "perimenopausal", "postmenopausal"],
                  "'폐경 후' -> eq postmenopausal, '폐경 전' -> in [premenopausal, perimenopausal]"),
    "sex": ("patient_state.fields.patient.gender", ["eq", "in"], ["FEMALE", "MALE"],
            "'여성 및 남성' -> in [FEMALE, MALE], '남성' -> eq MALE"),
    "age": ("patient_state.fields.patient.age", ["gt", "gte", "lt", "lte"], _NUM,
            "'40세 미만' -> lt 40, '만 19세 이상' -> gte 19, '70세 이상' -> gte 70"),
    "disease": ("biomarker_record.setting.disease", ["eq", "in"], ["early", "locally_advanced", "metastatic"],
                "'국소진행성' -> locally_advanced, '전이성' -> metastatic, '조기'·'초기' -> early"),
    "recurrence": ("patient_state.fields.recurrence.status", ["eq", "in", "exists"],
                   ["distant", "locoregional", "site_unknown"],
                   "'재발성'(국소·구역·원격 재발 모두) -> in [distant, locoregional, site_unknown], '국소 재발' -> eq locoregional"),
    "operable": ("patient_state.fields.stage.operable", ["eq"], ["yes", "no"],
                 "'절제 불가능한'·'수술이 불가능한' -> eq no (진단 시 기준)"),
    "recurrence_operable": ("(없음: recurrence.operable 제안)", ["eq"], ["yes", "no"],
                            "'절제 불가능한 국소 재발성' -> eq no"),
    "t_stage": ("patient_state.fields.stage.ctnm/ptnm T", ["eq", "in", "gt", "gte"], T_STAGES,
                "'염증성' -> eq T4d, '직경 > 2㎝' -> gte T2, '1cm 이상'·'1cm 초과' -> gte T1c, '≥ 5 cm' -> gte T3"),
    "stage_group": ("patient_state.fields.stage.group", ["eq", "in", "gte", "lte"], STAGES,
                    "'stage Ⅱ∼Ⅲ' -> 항목 둘 (gte II, lte III), 'stage ⅢA 이상' -> gte IIIA"),
    "positive_ln_count": ("patient_state.fields.stage.positive_ln_count.positive", ["eq", "gt", "gte", "lt", "lte"], _NUM,
                          "'림프절 양성' -> gte 1, '림프절 음성' -> eq 0, '4개 이상' -> gte 4"),
    "grade": ("patient_state.fields.diagnosis.grade", ["eq", "in", "gte"], _NUM,
              "'종양분화도 2∼3' -> gte 2, '조직학적 3등급' -> eq 3"),
    "pcr": ("patient_state.fields.neoadjuvant_response.pcr", ["eq"], ["yes", "no"],
            "'병리학적 완전관해(pCR)에 도달하지 않은'·'침습적 잔존 병변' -> eq no"),
    "pdl1_22c3_cps": ("patient_state.fields.receptors.pdl1 (assay=22C3, score_type=CPS)", ["gte", "gt"], _NUM,
                      "'PD-L1 발현 양성(CPS≥10)' + 'IHC 22C3' -> gte 10"),
    "pik3ca": ("biomarker_record.records[PIK3CA].status", ["eq"], _POSNEG, "'PIK3CA 변이' -> eq positive"),
    "akt1": ("biomarker_record.records[AKT1].status", ["eq"], _POSNEG, "AKT1 변이"),
    "pten": ("biomarker_record.records[PTEN].status", ["eq"], _POSNEG, "PTEN 변이"),
    "gbrca": ("biomarker_record.records[gBRCA1|gBRCA2].status", ["eq"], _POSNEG, "'gBRCA 변이' -> eq positive"),
    "sbrca": ("biomarker_record.records[sBRCA1|sBRCA2].status", ["eq"], _POSNEG, "체세포 BRCA 변이"),
    "bone_metastasis": ("patient_state.fields.stage/recurrence.metastatic_sites에 bone", ["eq"], [True, False],
                        "'골전이(영상의학적으로 입증)' -> eq true"),
    "prior_drugs": ("patient_state.fields.treatment_history[].drugs", ["contains", "not_contains"], _DRUGS,
                    "이전에 받은(contains) / 받은 적이 없는(not_contains) 약·계열. 값 목록은 contains면 모두 받았어야 하고 "
                    "(예: 'taxane 및 trastuzumab'), not_contains면 하나도 받지 않았어야 한다 (예: 'CDK4/6 inhibitor 또는 "
                    "fulvestrant를 투여 받은 적이 없는'). 'A 또는 B를 받은'처럼 하나만 받으면 되는 조건은 any_of 묶음에 "
                    "항목을 나눠 넣는다. of.setting으로 시기를 좁힐 수 있음 "
                    "(예: 'paclitaxel을 포함한 보조요법' -> contains [paclitaxel], of.setting [adjuvant])"),
    "prior_failed": ("patient_state.fields.treatment_history[] stop_reason=progression 또는 best_response=PD",
                     ["contains"], _DRUGS, "'~에 실패한'·'~ 투여 후 진행된' 약·계열. 목록은 모두 실패했어야 한다 "
                     "(예: 'trastuzumab과 taxane계 항암제 모두에 실패'). 'A 또는 B에 실패'는 any_of 묶음으로 나눈다"),
    "palliative_endocrine_lines": ("src/input/common/lines.py palliative_lines() counts.endocrine (저장 칸은 미정)",
                                   ["eq", "gte", "lte"], _NUM, "이미 받은 고식적 내분비요법 차수"),
    "palliative_chemo_lines": ("src/input/common/lines.py palliative_lines() counts.chemo (저장 칸은 미정)",
                               ["eq", "gte", "lte"], _NUM,
                               "이미 받은 고식적 항암화학요법 차수. '고식적 항암화학요법을 투여하지 않은' -> eq 0"),
    "days_end_to_recurrence": ("treatment_history[].end_day ~ recurrence 일수", ["gt", "lte"], _NUM,
                               "'투여 종료 후 1년 이후 재발' -> gt 365, '투여 중 또는 종료 1년 이내 재발' -> lte 365, "
                               "'6개월 이내' -> lte 183. of에 대상 약·시기"),
    "days_end_to_progression": ("treatment_history[].end_day ~ progression_day 일수", ["lte", "gt"], _NUM,
                                "'고식적요법 투여 중 또는 종료 후 1달 이내에 진행' -> lte 30"),
    "days_since_last_dose": ("판정 기준일 - 마지막 투여일", ["lte"], _NUM,
                             "'최근 4주 이내 항암제 또는 호르몬제 투여' -> lte 28"),
    "treatment_years": ("treatment_history[].start_day ~ end_day", ["lte"], _NUM, "'투여기간: 5년' -> lte 5"),
    "cycles_total": ("treatment_history[].cycles 합", ["lte", "eq"], _NUM,
                     "'총 trastuzumab 투여 주기 18주기 이하' -> lte 18, of.drugs [trastuzumab]"),
    "cumulative_dose_mg_m2": ("patient_state.fields.anthracycline_drug_dose.drugs[].total_dose", ["gt", "gte"], _NUM,
                              "'doxorubicin 누적 240mg/m2 이상' -> gte 240, of.drugs [doxorubicin]"),
    "cardiac_history": ("(없음: patient.comorbidities)", ["eq"], [True, False],
                        "'심장위험요소'·'울혈 심부전증 병력 등 병발 심장질환' -> eq true"),
    "mediastinal_radiation": ("(없음: radiotherapy_history)", ["eq"], [True, False],
                              "'종격동 방사선 치료' 경험 -> eq true"),
}

_VALUE = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"},
                    {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "number"}]}}]}
_OF = {"type": "object", "additionalProperties": False,
       "properties": {"drugs": {"type": "array", "items": {"type": "string"}},
                      "setting": {"type": "array", "items": {"enum": ["neoadjuvant", "adjuvant", "palliative"]}}}}
_BASE_ITEM = {"id": {"type": "string"}, "field": {"enum": list(FIELDS)}, "op": {"enum": OPS},
              "value": _VALUE, "text": {"type": "string"}, "of": _OF}
_UNLESS = {"type": "object", "additionalProperties": False, "required": ["field", "op", "value", "text"],
           "properties": {k: v for k, v in _BASE_ITEM.items() if k != "id"}}
ITEM = {"type": "object", "additionalProperties": False, "required": ["id", "field", "op", "value", "text"],
        "properties": {**_BASE_ITEM, "unless": _UNLESS}}
_TEXTS = {"type": "array", "items": {"type": "string"}}


def output_schema() -> dict:
    """structured outputs용 스키마 (재귀 없음). line_rule은 코드가 채우므로 LLM 출력에 없다."""
    return {
        "type": "object", "additionalProperties": False,
        "required": ["all_of", "any_of", "any_of_exceptions", "stage_rules", "counts_as_prior_line",
                     "notes", "human_review", "unmapped"],
        "properties": {
            "all_of": {"type": "array", "items": ITEM},
            "any_of": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "items"],
                "properties": {"text": {"type": "string"}, "items": {"type": "array", "items": ITEM}}}},
            "any_of_exceptions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "all_of"],
                "properties": {"text": {"type": "string"}, "all_of": {"type": "array", "items": ITEM}}}},
            "stage_rules": {"type": "array", "items": ITEM},
            "counts_as_prior_line": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "setting", "drugs"],
                "properties": {"text": {"type": "string"},
                               "setting": {"type": "array", "items": {"enum": ["neoadjuvant", "adjuvant", "palliative"]}},
                               "drugs": {"type": "array", "items": {"type": "string"}},
                               "within_days": {"type": "number"}}}},
            "notes": _TEXTS, "human_review": _TEXTS, "unmapped": _TEXTS,
        },
    }


def stored_schema() -> dict:
    """청크에 붙인 뒤의 형식 (line_rule 포함, 허가초과 남성 조건처럼 코드가 만든 항목도 같은 형식)."""
    s = output_schema()
    s["properties"] = {**s["properties"], "line_rule": {
        "type": ["object", "null"], "additionalProperties": False, "required": ["stage", "line"],
        "properties": {"stage": {"enum": LINE_STAGES}, "line": {"enum": LINE_RULES + [None]}}}}
    s["required"] = []
    return s


SYSTEM = """당신은 건강보험심사평가원 항암요법 급여 기준 문장을 판정용 조건 JSON으로 옮기는 일을 한다.

규칙:
1. 입력 본문에 적힌 조건만 옮긴다. 일반 의학 지식으로 조건을 보태거나 추측하지 않는다.
2. 조건 항목마다 text에 근거가 되는 원문 구절을 한 글자도 바꾸지 않고 복사한다 (줄바꿈 위치는 달라도 된다).
   원문에 없는 구절을 쓰면 결과 전체가 버려진다. any_of·any_of_exceptions의 text, notes, human_review,
   unmapped, counts_as_prior_line의 text도 원문 그대로여야 한다.
3. 모두 만족해야 하는 조건은 all_of에 둔다. '아래의 하나에 해당하는 경우'처럼 여러 항목 중 하나만 만족하면
   되는 묶음은 any_of에 묶음 하나로 넣는다. '※ 단, … 경우도 급여 인정함' 같은 예외 분기는 any_of_exceptions에 넣는다.
4. '투여 종료 후 1년 이후 재발한 경우도 인정' 처럼 한 조건의 예외는 그 항목의 unless에 넣는다.
5. 소단원 안내의 머리 규칙 중 이 행 판정에 쓰이는 것(예: 'CDK4/6 inhibitor + letrozole or anastrozole 병용요법의
   경우 고식적 항암화학요법을 투여하지 않은 사람')은 stage_rules에 넣는다. 이 행과 관계없는 규칙은 넣지 않는다.
6. '선행·보조요법 중 또는 종료 후 1년 이내 재발이면 1차 투여가 실시된 것으로 간주', 'Anthracycline계 및 Taxane을
   포함한 선행화학요법 또는 수술후보조요법이 사용된 경우에는 1차 투여가 실시된 것으로 간주' 같은 간주 규칙은
   counts_as_prior_line에 넣는다 (within_days는 기간이 있을 때만).
7. 판정 대상이 아닌 처방 조건(예: '4주 간격의 goserelin 혹은 leuprolide를 함께 투여해야 함', 투여 주기 간격)은 notes,
   의사 소견·기관 요건·'이러한 치료가 부적절한 환자는 예외'·'허가사항 범위 내에서 필요ㆍ적절하게'처럼 데이터로 판정할 수
   없는 조건은 human_review에 원문 그대로 넣는다.
8. field·op·value는 아래 어휘만 쓴다. 옮길 수 없는 조건은 unmapped에 원문 그대로 넣는다.
9. '(위 연번과 같음)' 뒤의 투여대상은 이 행에 적용되는 조건이다. 공고 번호·시행일 표시는 조건이 아니다.
10. id는 all_of에서 c1, c2, …, any_of 묶음 안에서 a1, a2, …, 예외 안에서 e1, e2, …, stage_rules에서 s1, s2, … 로 붙인다.
11. 약·계열 이름(value, of.drugs, counts_as_prior_line.drugs)은 일반명 소문자 또는 계열 이름 """ + ", ".join(
    DRUG_SUBCLASSES + DRUG_CLASSES) + """ 만 쓴다 (예: 'CDK4/6 inhibitor' -> CDK4/6_inhibitor,
    'PD-1 inhibitor 등 면역관문억제제' -> immune_checkpoint_inhibitor, '비스테로이드성 aromatase inhibitor' -> AI_nonsteroidal).
    사전에 계열이 없는 묶음은 약 일반명을 모두 적는다 (예: 'aromatase inhibitor' -> anastrozole, letrozole, exemestane).

op: """ + ", ".join(OPS) + """ (not_contains·contains는 이전 치료 목록에 쓴다)

field 어휘 (환자 JSON 경로 / 허용 op / 허용값 / 예):
""" + "\n".join(f"- {k}: [{p}] op {'|'.join(ops)} / 값 {v if isinstance(v, list) else v} / {d}"
                 for k, (p, ops, v, d) in FIELDS.items())


# ---------- 결과 검사 (LLM 출력이 원문에 근거하는지) ----------

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def iter_items(cond: dict):
    """(위치, 항목) 전부. unless는 따로 돌려준다."""
    for i, it in enumerate(cond.get("all_of", [])):
        yield f"all_of[{i}]", it
    for g, grp in enumerate(cond.get("any_of", [])):
        for i, it in enumerate(grp.get("items", [])):
            yield f"any_of[{g}].items[{i}]", it
    for g, grp in enumerate(cond.get("any_of_exceptions", [])):
        for i, it in enumerate(grp.get("all_of", [])):
            yield f"any_of_exceptions[{g}].all_of[{i}]", it
    for i, it in enumerate(cond.get("stage_rules", [])):
        yield f"stage_rules[{i}]", it


def _texts(cond: dict):
    for where, it in iter_items(cond):
        yield f"{where}.text", it.get("text", "")
        if it.get("unless"):
            yield f"{where}.unless.text", it["unless"].get("text", "")
    for key in ("any_of", "any_of_exceptions", "counts_as_prior_line"):
        for i, g in enumerate(cond.get(key, [])):
            yield f"{key}[{i}].text", g.get("text", "")
    for key in ("notes", "human_review", "unmapped"):
        for i, t in enumerate(cond.get(key, [])):
            yield f"{key}[{i}]", t


def check_grounding(cond: dict, source: str) -> list[str]:
    """원문 구절 칸이 모두 원문에 있는지. 문제 목록을 돌려준다."""
    src = _norm(source)
    return [f"{where}: 원문에 없는 구절 {t!r}" for where, t in _texts(cond)
            if not _norm(t) or _norm(t) not in src]


def check_schema(cond: dict, schema: dict | None = None) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    v = jsonschema.Draft202012Validator(schema or output_schema())
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in v.iter_errors(cond)]


def prior_vocab() -> frozenset[str]:
    """약·계열 이름으로 쓸 수 있는 것: 계열 이름 + 알려진 약 일반명."""
    from .vocab import known_drugs
    return frozenset(DRUG_SUBCLASSES) | frozenset(DRUG_CLASSES) | known_drugs()


def _check_item(it: dict, where: str, vocab: frozenset[str]) -> list[str]:
    errs = []
    f, op, val = it.get("field"), it.get("op"), it.get("value")
    if f not in FIELDS:
        return [f"{where}: 어휘에 없는 field {f!r}"]
    _, ops, allowed, _ = FIELDS[f]
    if op not in ops:
        errs.append(f"{where}: {f}에 쓸 수 없는 op {op!r} (허용 {ops})")
    vals = val if isinstance(val, list) else [val]
    if op == "in" and not isinstance(val, list):
        errs.append(f"{where}: op in에는 값 목록이 필요함")
    if allowed == _NUM:
        if op != "exists" and not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            errs.append(f"{where}: {f} 값은 숫자여야 함 ({val!r})")
    elif allowed == _DRUGS:
        errs += [f"{where}: 사전에 없는 이름 {v!r}" for v in vals if v not in vocab]
    elif op != "exists":
        errs += [f"{where}: {f}의 허용값이 아님 {v!r}" for v in vals if v not in allowed]
    for d in (it.get("of") or {}).get("drugs", []):
        if d not in vocab:
            errs.append(f"{where}.of: 사전에 없는 이름 {d!r}")
    if it.get("unless"):
        errs += _check_item({**it["unless"], "id": "unless"}, f"{where}.unless", vocab)
    return errs


def check_values(cond: dict) -> list[str]:
    """스키마로 막지 못하는 값 검사: field마다 허용 op·값, 약·계열 이름이 사전에 있는지."""
    vocab = prior_vocab()
    errs = []
    for where, it in iter_items(cond):
        errs += _check_item(it, where, vocab)
    for i, g in enumerate(cond.get("counts_as_prior_line", [])):
        errs += [f"counts_as_prior_line[{i}]: 사전에 없는 이름 {d!r}" for d in g.get("drugs", []) if d not in vocab]
    return errs


def is_empty(cond: dict) -> bool:
    return not any(cond.get(k) for k in ("all_of", "any_of", "any_of_exceptions", "stage_rules",
                                          "counts_as_prior_line", "notes", "human_review", "unmapped"))


# ---------- 저장된 결과 ----------

def cache_key(text: str, context: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{MODEL}\n{context}\n---\n{text}".encode()).hexdigest()


class Cache:
    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        self.rows: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.rows[r["key"]] = r

    def get(self, key: str) -> dict | None:
        r = self.rows.get(key)
        return r["conditions"] if r else None

    def put(self, key: str, chunk_id: str, cond: dict, usage: dict, model: str = MODEL) -> None:
        r = {"key": key, "chunk_id": chunk_id, "model": model, "prompt_version": PROMPT_VERSION,
             "conditions": cond, "usage": usage,
             "created_at": datetime.now(KST).isoformat(timespec="seconds")}
        self.rows[key] = r
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:     # 한 줄씩 덧붙여 중간에 끊겨도 받은 것은 남는다
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------- Claude API ----------

class StructurerUnavailable(RuntimeError):
    pass


DOTENV_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID")


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """.env의 ANTHROPIC_API_KEY와 ANTHROPIC_WORKSPACE_ID만 읽는다 (이미 환경 변수에 있으면 그대로).
    워크스페이스에 묶이지 않은 키는 요청마다 anthropic-workspace-id 헤더가 필요하다 (없으면 400)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        for name in DOTENV_KEYS:
            m = re.match(rf"\s*{name}\s*=\s*['\"]?([^'\"\s]+)", line)
            if m and not os.environ.get(name):
                os.environ[name] = m.group(1)


class ClaudeStructurer:
    """Claude API로 조건 JSON을 받는다. 공용 llm/ 인터페이스가 생기면 그쪽으로 옮긴다 (llm/README: [5] 공고 구조화)."""

    def __init__(self, model: str = MODEL):
        try:
            import anthropic
        except ImportError as e:
            raise StructurerUnavailable("anthropic 패키지 없음 (conda install -c conda-forge anthropic)") from e
        _load_dotenv()
        self.anthropic = anthropic
        ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        self.client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)
        self.model = model

    def __call__(self, text: str, context: str) -> tuple[dict, dict]:
        user = (f"[소단원 안내 - 참고용, 이 행 조건의 근거로도 인용할 수 있음]\n{context}\n\n" if context else "") \
            + f"[급여 기준 본문]\n{text}"
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM,
                output_config={"effort": "medium",
                               "format": {"type": "json_schema", "schema": output_schema()}},
                messages=[{"role": "user", "content": user}],
            )
        except self.anthropic.AuthenticationError as e:
            raise StructurerUnavailable("Claude API 인증 실패 (.env의 ANTHROPIC_API_KEY 확인)") from e
        except self.anthropic.BadRequestError as e:
            # 계정 설정 문제는 행마다 다시 시도해도 같은 오류라 전체를 멈춘다
            if "workspace" in str(e):
                raise StructurerUnavailable(
                    "API 키가 워크스페이스에 묶여 있지 않음: .env에 ANTHROPIC_WORKSPACE_ID=wrkspc_... 를 넣거나 "
                    "워크스페이스 키를 새로 만든다") from e
            if "credit balance" in str(e):
                raise StructurerUnavailable(
                    "API 크레딧 잔액 부족: console.anthropic.com > Plans & Billing에서 크레딧을 충전한다") from e
            raise
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"모델이 응답을 거부함: {getattr(resp, 'stop_details', None)}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("응답이 max_tokens에서 잘림")
        text_out = next(b.text for b in resp.content if b.type == "text")
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                 "request_id": getattr(resp, "_request_id", None)}
        return json.loads(text_out), usage


# ---------- 청크에 붙이기 ----------

TARGET_KINDS = ("reimbursement_condition", "offlabel_regimen")


@dataclass
class ConditionReport:
    from_cache: int = 0
    requested: int = 0
    skipped_no_api: list[str] = field(default_factory=list)
    rejected: dict[str, list[str]] = field(default_factory=dict)    # chunk_id -> 문제
    failed: dict[str, str] = field(default_factory=dict)            # chunk_id -> 예외
    empty: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    unavailable_reason: str | None = None


def merge_conditions(base: dict, extra: dict) -> dict:
    """코드가 미리 넣은 조건(line_rule, 허가초과 남성 항목)과 LLM 결과를 합친다. 목록은 이어 붙인다."""
    out = dict(extra)
    for k, v in base.items():
        if isinstance(v, list):
            out[k] = list(out.get(k, [])) + [x for x in v if x not in out.get(k, [])]
        else:
            out[k] = v
    return out


def attach_conditions(chunks: list[dict], contexts: dict[str, str], *, structurer=None,
                      cache: Cache | None = None, use_api: bool = True) -> ConditionReport:
    """대상 청크마다 저장된 결과를 쓰거나 API로 받아, 검사를 통과한 조건만 reimbursement.conditions에 넣는다.

    contexts: chunk_id -> 소단원 제목·머리 규칙·주석 (근거 구절로 쓸 수 있는 글)
    structurer: (본문, 안내) -> (조건, 사용량). None이고 use_api면 ClaudeStructurer를 만든다.
    """
    rep = ConditionReport()
    cache = cache or Cache()
    if structurer is None and use_api:
        try:
            structurer = ClaudeStructurer()
        except StructurerUnavailable as e:
            rep.unavailable_reason = str(e)
    for c in chunks:
        if c["chunk_kind"] not in TARGET_KINDS:
            continue
        cid, text, ctx = c["chunk_id"], c["text"], contexts.get(c["chunk_id"], "")
        key = cache_key(text, ctx)
        cond = cache.get(key)
        if cond is not None:
            rep.from_cache += 1
        elif structurer is None:
            rep.skipped_no_api.append(cid)
            continue
        else:
            try:
                cond, usage = structurer(text, ctx)
            except StructurerUnavailable as e:
                rep.unavailable_reason = str(e)
                structurer = None
                rep.skipped_no_api.append(cid)
                continue
            except Exception as e:      # 한 청크 실패로 전체를 멈추지 않는다 (보고서에 남김)
                rep.failed[cid] = f"{type(e).__name__}: {e}"
                continue
            rep.requested += 1
            rep.input_tokens += usage.get("input_tokens", 0)
            rep.output_tokens += usage.get("output_tokens", 0)
            cache.put(key, cid, cond, usage)
        problems = check_schema(cond) + check_values(cond) + check_grounding(cond, f"{ctx}\n{text}")
        if problems:
            rep.rejected[cid] = problems
            continue
        if is_empty(cond):
            rep.empty.append(cid)
        c["reimbursement"]["conditions"] = merge_conditions(c["reimbursement"].get("conditions", {}), cond)
    return rep


# ---------- API 없이 넣기 (대화에서 직접 작성, 사람이 고친 조건) ----------

@dataclass
class ImportReport:
    saved: list[str] = field(default_factory=list)
    rejected: dict[str, list[str]] = field(default_factory=dict)
    unknown: list[str] = field(default_factory=list)          # 청크 파일에 없는 chunk_id


def import_conditions(items: dict[str, dict], chunks: list[dict], contexts: dict[str, str], cache: Cache,
                      author: str) -> ImportReport:
    """{chunk_id: 조건} -> API 결과와 같은 검사(형식·어휘·원문 구절)를 통과한 것만 저장본에 넣는다.
    저장본 키는 API 결과와 같아서, 파이프라인을 다시 돌리면 이 조건을 그대로 쓴다. author는 model 칸에 남긴다."""
    rep = ImportReport()
    by_id = {c["chunk_id"]: c for c in chunks}
    for cid, cond in items.items():
        c = by_id.get(cid)
        if c is None:
            rep.unknown.append(cid)
            continue
        ctx = contexts.get(cid, "")
        problems = check_schema(cond) + check_values(cond) + check_grounding(cond, f"{ctx}\n{c['text']}")
        if problems:
            rep.rejected[cid] = problems
            continue
        cache.put(cache_key(c["text"], ctx), cid, cond, {}, model=author)
        rep.saved.append(cid)
    return rep


# ---------- 사람 검수표 (§3.5: 사람이 전수 검수) ----------

REVIEW_COLUMNS = ["chunk_id", "section", "regimen", "묶음", "id", "field", "op", "value", "of", "원문 구절",
                  "검수(O/X)", "고칠 내용"]


def review_rows(chunks: list[dict]) -> list[list[str]]:
    rows = []
    for c in chunks:
        cond = c["reimbursement"].get("conditions") or {}
        if c["chunk_kind"] not in TARGET_KINDS or not cond:
            continue
        head = [c["chunk_id"], c["section"], " / ".join(c["reimbursement"].get("regimen", []))]
        lr = cond.get("line_rule")
        if lr:
            rows.append(head + ["line_rule", "", "", "", json.dumps(lr, ensure_ascii=False), "", "(소단원)", "", ""])
        for where, it in iter_items(cond):
            rows.append(head + [where.split("[")[0], it.get("id", ""), it.get("field", ""), it.get("op", ""),
                                json.dumps(it.get("value"), ensure_ascii=False),
                                json.dumps(it.get("of"), ensure_ascii=False) if it.get("of") else "",
                                it.get("text", ""), "", ""])
            if it.get("unless"):
                u = it["unless"]
                rows.append(head + [f"{where.split('[')[0]}.unless", it.get("id", ""), u.get("field", ""),
                                    u.get("op", ""), json.dumps(u.get("value"), ensure_ascii=False), "",
                                    u.get("text", ""), "", ""])
        for key in ("any_of", "any_of_exceptions", "counts_as_prior_line"):
            for g in cond.get(key, []):
                extra = json.dumps({k: v for k, v in g.items() if k in ("setting", "drugs", "within_days")},
                                   ensure_ascii=False) if key == "counts_as_prior_line" else ""
                rows.append(head + [f"{key} (묶음 머리)", "", "", "", extra, "", g.get("text", ""), "", ""])
        for key in ("notes", "human_review", "unmapped"):
            for t in cond.get(key, []):
                rows.append(head + [key, "", "", "", "", "", t, "", ""])
    return rows


def export_review(chunks: list[dict], path: Path) -> Path | None:
    """검수표를 탭 구분 파일로 쓴다. 엑셀에서 열 수 있게 UTF-8 BOM을 붙인다.
    공고 원문이 들어 있어 .csv가 아닌 .tsv로 둔다 (data/ 안의 csv는 git에 올라가므로)."""
    rows = review_rows(chunks)
    if not rows:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(REVIEW_COLUMNS)
        w.writerows(rows)
    return path


# ---------- 실행 ----------

def main(argv: list[str] | None = None) -> int:
    """python -m src.reimbursement.conditions --import 파일.json [--author 이름]
    파일 형식: {chunk_id: 조건(설계 §3.5)}. 통과한 것만 저장본에 넣고, 버린 것과 이유를 보여 준다."""
    import argparse
    import sys
    from .booklet import load_booklet
    from .chunks import booklet_chunks
    from .pipeline import _latest_local

    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="직접 작성하거나 검수에서 고친 투여 조건을 저장본에 넣는다")
    ap.add_argument("--import", dest="path", type=Path, required=True)
    ap.add_argument("--author", default="manual", help="저장본 model 칸에 남길 작성자")
    ap.add_argument("--raw", type=Path, default=DATA / "raw")
    ap.add_argument("--cache", type=Path, default=CACHE_PATH)
    args = ap.parse_args(argv)

    booklet = _latest_local(args.raw, "공고책자_*.pdf")
    if booklet is None:
        print(f"[넣지 않음] 공고책자가 {args.raw}에 없음", file=sys.stderr)
        return 1
    bc = booklet_chunks(load_booklet(booklet, DATA / "cache"))
    items = json.loads(args.path.read_text(encoding="utf-8"))
    rep = import_conditions(items, bc.chunks, bc.contexts, Cache(args.cache), args.author)
    print(f"저장 {len(rep.saved)}개, 버림 {len(rep.rejected)}개, 없는 chunk_id {len(rep.unknown)}개")
    for cid, probs in rep.rejected.items():
        print(f"  [버림] {cid}")
        for p in probs:
            print(f"     - {p}")
    for cid in rep.unknown:
        print(f"  [없음] {cid}")
    return 0 if not rep.rejected and not rep.unknown else 1


if __name__ == "__main__":
    raise SystemExit(main())
