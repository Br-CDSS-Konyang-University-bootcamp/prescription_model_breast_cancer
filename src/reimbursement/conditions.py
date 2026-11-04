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
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .dates import KST

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"
CACHE_PATH = DATA / "conditions_cache.jsonl"
MODEL ="claude-sonnet-5-5"          # PROJECT.md §9: 공고·지침 구조화
PROMPT_VERSION = "2026-10-22.1"       # 프롬프트·어휘를 바꾸면 올린다 (예전 저장 결과를 안 쓰게)

OPS = ["eq", "in", "not_contains", "contains", "gt", "gte", "lt", "lte", "exists"]
STAGES = ["0", "I", "IA", "IB", "II", "IIA", "IIB", "III", "IIIA", "IIIB", "IIIC", "IV"]
T_STAGES = ["Tis", "T1mi", "T1a", "T1b", "T1c", "T1", "T2", "T3", "T4", "T4a", "T4b", "T4c", "T4d"]
# 이전 치료 계열 이름: 공용 사전 drug_classes.csv의 drug_subclass·drug_class 값 (2026-10-17판:
# CDK4/6_inhibitor, immune_checkpoint_inhibitor 추가). 사전에 계열이 없는 묶음은 약 일반명을 모두 적는다
DRUG_SUBCLASSES = ["anthracycline", "taxane", "AI_nonsteroidal", "AI_steroidal", "LHRH_agonist",
                   "SERM", "SERD", "progestin", "CDK4/6_inhibitor", "immune_checkpoint_inhibitor"]
DRUG_CLASSES = ["Chemotherapy", "Hormone Therapy", "HER2-targeted Therapy", "Immunotherapy", "Other Targeted Therapy"]
LINE_STAGES = ["neoadjuvant", "adjuvant", "palliative_endocrine", "palliative_chemo", "combination", "supportive"]
# 심평원 차수 간주 규칙 (A의 patient_state fields.deemed_lines[].rule_id, schemas/patient_state.json)
DEEM_RULES = ["DEEM-ANTHRA-TAXANE", "DEEM-SG-1Y", "DEEM-HER2ADC-6M", "DEEM-ENDO-ADJ-1Y"]
LINE_RULES = ["1차", "1차 이상", "2차", "2차 이상", "3차 이상"]

_POSNEG = ["positive", "negative"]
_NUM = "number"
_DRUGS = "drugs"           # 값이 약 이름·계열 이름 목록 (사전 검사)

# field -> (환자 JSON 경로, 허용 op, 값 종류 또는 허용값 목록, 설명). 설명은 프롬프트에도 들어간다.
# patient_state 경로는 0.1-draft6 기준 (A의 patient_state_structure.md, 2026-10-20)에 draft7 후보 칸
# (A의 draft7_checklist_BCD_2026-10-28 §3: 크기, 치료 시기별 병기, 심장, 영상 골전이, 용량)을 더했다. 공통 추출 칸(◆)은 값이 .value에 있어
# 경로에 .value까지 적는다. treatment_history[], deemed_lines[], at_index, anthracycline_drug_dose,
# molecular.mutations.*는 틀 없이 키를 그대로 쓴다.
# 날짜는 모두 진단일 = 0인 정수 일수(*_day)다.
# 공고 표현 -> 칸·값은 팀 사전 data/dictionaries/reimbursement_terms.csv를 따른다 (2026-10-20 대조).
FIELDS: dict[str, tuple[str, list[str], object, str]] = {
    # 값은 B의 biomarker_record 값을 따른다 (팀 사전과 같이 canonical = B). B는 zero를 쓰지 않는다 (IHC 0은 negative)
    "her2": ("biomarker_record.records[HER2].status", ["eq", "in"], ["positive", "negative", "low", "ultralow"],
             "'HER2 양성(과발현)' -> eq positive, 'HER2 음성' -> in [negative, low, ultralow] (공고에 저발현 구분 없음)"),
    "hr": ("biomarker_record.subtype in [HR+/HER2-, HR+/HER2+] (positive) / ER·PR 모두 negative (negative)", ["eq"], _POSNEG,
           "'호르몬 수용체 양성' -> eq positive (ER 또는 PR 양성), '호르몬 수용체(ER and PR) 음성' -> eq negative"),
    "er": ("biomarker_record.records[ER].status", ["eq", "in"], ["positive", "low", "negative"],
           "에스트로겐 수용체만 따로 적힌 경우. 'ER 양성' -> in [positive, low]"),
    "pr": ("biomarker_record.records[PR].status", ["eq"], _POSNEG, "프로게스테론 수용체만 따로 적힌 경우"),
    "subtype": ("biomarker_record.subtype", ["eq", "in"], ["HR+/HER2-", "HR+/HER2+", "HR-/HER2+", "TNBC"],
                "'삼중음성' -> eq TNBC"),
    "menopause": ("patient_state.fields.patient.menopausal_status.value", ["eq", "in"],
                  ["premenopausal", "perimenopausal", "postmenopausal"],
                  "'폐경 후' -> eq postmenopausal, '폐경 전' -> in [premenopausal, perimenopausal]"),
    "sex": ("patient_state.fields.patient.gender.value", ["eq", "in"], ["FEMALE", "MALE"],
            "'여성 및 남성' -> in [FEMALE, MALE], '남성' -> eq MALE"),
    # 나이 기준은 A의 data_needs_by_module §6-2: patient.age는 진단 시 나이, 처방 시점 조건은 at_index.age
    "age": ("patient_state.fields.patient.age.value (진단 시 나이)", ["gt", "gte", "lt", "lte"], _NUM,
            "선행·수술후보조 대상의 나이 조건. '40세 미만' -> lt 40, '35세 미만' -> lt 35"),
    "age_at_index": ("patient_state.fields.at_index.age (판정 기준일 나이, 없으면 알 수 없음)", ["gt", "gte", "lt", "lte"], _NUM,
                     "투여 시점 나이 조건 (보조 약제 등). '만 19세 이상' -> gte 19, '70세 이상' -> gte 70"),
    # 값은 팀 사전(stage.disease_extent의 값)과 같다. 칸은 지금 범위인 setting.disease를 쓴다:
    # 스키마 설명 "재발 후 상태는 biomarker_record.setting.disease", handoff_to_B.md §6.1
    # (진단 시 전이 또는 원격 재발 -> metastatic, 국소 재발 등은 진단 시 범주 그대로)
    "disease": ("biomarker_record.setting.disease (진단 시 stage.disease_extent + 원격 재발)", ["eq", "in"],
                ["early", "locally_advanced", "metastatic"],
                "'국소진행성' -> locally_advanced, '전이성' -> metastatic (원격 재발 포함), '조기'·'초기' -> early, "
                "'진행성' -> in [locally_advanced, metastatic]. 국소 재발은 disease에 들어가지 않으므로 "
                "'전이성, 재발성'은 any_of 묶음에 disease eq metastatic과 recurrence in [...] 항목을 함께 넣는다"),
    "recurrence": ("patient_state.fields.recurrence.status.value", ["eq", "in", "exists"],
                   ["distant", "locoregional", "site_unknown"],
                   "'재발성'(국소·구역·원격 재발 모두) -> in [distant, locoregional, site_unknown], '국소 재발' -> eq locoregional"),
    "operable": ("patient_state.fields.stage.operable.value", ["eq"], ["yes", "no"],
                 "'절제 불가능한'·'수술이 불가능한' -> eq no (진단 시 기준)"),
    # 재발 병소를 절제할 수 있는지는 데이터에 없어 칸을 두지 않고, 재발 후 실제 수술 여부로 대신한다 (A 답변 2026-10-21).
    # 수술하지 않은 것(surgery = no)은 절제할 수 없는 것과 같지 않으므로 no로 읽지 않는다
    "recurrence_operable": ("patient_state.fields.recurrence.surgery.value = yes 이고 surgery_intent.value = curative -> yes "
                            "(절제함). 그 밖(no, unknown, palliative)은 알 수 없음 (사유: 재발 병소 절제 가능 여부 확인 필요)",
                            ["eq"], ["yes", "no"], "'절제 불가능한 국소 재발성' -> eq no"),
    # 병기·크기는 치료 시기에 맞는 칸을 고른다 (A draft7 체크리스트 §4, 2026-10-28): 선행요법 행은 임상(c),
    # 수술후보조요법 행은 수술 병리 병기: 수술을 먼저 했으면 ptnm, 선행요법 뒤 수술이면 yptnm (§4 표 '선행요법 뒤 보조').
    # 그 칸이 비면 다른 병기로 대신하지 않고 알 수 없음 (선행요법 중이라 yptnm이 not_done이면 알 수 없음).
    # §4의 예외('처음 병기'를 보는 조건은 조건마다 적음)에 해당하는 원문은 지금 D 행에 없다 (2026-11-02 확인)
    "ct_stage": ("patient_state.fields.stage.ctnm.value.t (임상 T)", ["eq", "in", "gt", "gte"], T_STAGES,
                 "선행요법 행의 T 조건. '염증성' -> eq T4d"),
    "pt_stage": ("patient_state.fields.stage.ptnm.value.t (수술을 먼저 한 환자) / stage.yptnm.value.t (선행요법 뒤 수술)",
                 ["eq", "in", "gt", "gte"], T_STAGES,
                 "수술후보조요법 행의 T 조건. 크기(cm)로 적힌 조건은 T 범주로 바꾸지 않고 pathologic_size_mm를 쓴다"),
    # 크기는 cm 경계를 T 범주로 바꾸지 않는다 (정확히 5.0 cm는 T2인데 '≥ 5 cm'를 만족함). 값은 mm
    "clinical_size_mm": ("patient_state.fields.stage.clinical_size_mm.value (치료 전 임상 종양 크기, mm)",
                         ["gt", "gte", "lt", "lte"], _NUM, "선행요법 행의 크기 조건. '직경 > 2㎝' -> gt 20"),
    "pathologic_size_mm": ("patient_state.fields.stage.pathologic_size_mm.value (수술을 먼저 한 환자의 침윤암 최대 직경, mm) / "
                           "stage.yptnm.value.residual_size_mm (선행요법 뒤 수술의 잔존 침윤암 최대 직경, mm)",
                           ["gt", "gte", "lt", "lte"], _NUM,
                           "수술후보조요법 행의 크기 조건. '1cm 이상' -> gte 10, '1cm를 초과' -> gt 10, "
                           "'종양 크기 > 2 cm' -> gt 20, '≥ 5 cm' -> gte 50"),
    "stage_group": ("patient_state.fields.stage.group.value", ["eq", "in", "gte", "lte"], STAGES,
                    "'stage Ⅱ∼Ⅲ' -> 항목 둘 (gte II, lte III), 'stage ⅢA 이상' -> gte IIIA. "
                    "로마숫자 Ⅰ~Ⅳ는 I~IV로 옮기고 하위 병기(A·B·C)는 붙이지 않는다 (III는 IIIA~IIIC 포함)"),
    # 림프절 양성: N1*·N2*·N3* (N1mi 포함) / 음성: N0, N0(i-), N0(i+), N0(mol+). 앞의 c·p 글자는 떼고 본다
    "cn_status": ("patient_state.fields.stage.ctnm.value.n (임상 N)", ["eq"], _POSNEG,
                  "선행요법 행의 '림프절 양성' -> eq positive"),
    "pn_status": ("patient_state.fields.stage.ptnm.value.n (수술을 먼저 한 환자) / stage.yptnm.value.n (선행요법 뒤 수술)",
                  ["eq"], _POSNEG,
                  "수술후보조요법 행의 '림프절 양성' -> eq positive, '림프절 음성' -> eq negative"),
    "positive_ln_count": ("patient_state.fields.stage.positive_ln_count.value.positive", ["eq", "gt", "gte", "lt", "lte"], _NUM,
                          "전이된 림프절 갯수가 적힌 경우만. '4개 이상' -> gte 4, '1-3개' -> 항목 둘 (gte 1, lte 3)"),
    "grade": ("patient_state.fields.diagnosis.grade.value", ["eq", "in", "gte"], _NUM,
              "'종양분화도 2∼3' -> gte 2, '조직학적 3등급' -> eq 3"),
    "pcr": ("patient_state.fields.neoadjuvant_response.pcr.value", ["eq"], ["yes", "no"],
            "'병리학적 완전관해(pCR)에 도달하지 않은'·'침습적 잔존 병변' -> eq no"),
    "pdl1_22c3_cps": ("patient_state.fields.receptors.pdl1.value.score (assay=22C3, score_type=CPS)", ["gte", "gt"], _NUM,
                      "'PD-L1 발현 양성(CPS≥10)' + 'IHC 22C3' -> gte 10"),
    "pik3ca": ("biomarker_record.records[PIK3CA].status", ["eq"], _POSNEG, "'PIK3CA 변이' -> eq positive"),
    "akt1": ("biomarker_record.records[AKT1].status", ["eq"], _POSNEG, "AKT1 변이"),
    "pten": ("biomarker_record.records[PTEN].status", ["eq"], _POSNEG, "PTEN 변이"),
    "gbrca": ("biomarker_record.records[gBRCA1|gBRCA2].status", ["eq"], _POSNEG, "'gBRCA 변이' -> eq positive"),
    "sbrca": ("biomarker_record.records[sBRCA1|sBRCA2].status", ["eq"], _POSNEG, "체세포 BRCA 변이"),
    # 공고는 '영상으로 입증'이라 전이 부위 목록이 아니라 영상 소견을 본다 (A draft7 체크리스트 §3.1)
    "bone_metastasis": ("patient_state.fields.imaging_findings[]에 sites bone + certainty confirmed가 있으면 true. "
                        "뼈가 의심(suspected)으로만 있거나 stage·recurrence.metastatic_sites에만 있으면 알 수 없음, "
                        "영상 소견과 전이 부위 어디에도 뼈가 없으면 false", ["eq"], [True, False],
                        "'골전이(영상의학적으로 입증)' -> eq true"),
    "prior_drugs": ("patient_state.fields.treatment_history[].drugs", ["contains", "not_contains"], _DRUGS,
                    "이전에 받은(contains) / 받은 적이 없는(not_contains) 약·계열. 값 목록은 contains면 모두 받았어야 하고 "
                    "(예: 'taxane 및 trastuzumab'), not_contains면 하나도 받지 않았어야 한다 (예: 'CDK4/6 inhibitor 또는 "
                    "fulvestrant를 투여 받은 적이 없는'). 'A 또는 B를 받은'처럼 하나만 받으면 되는 조건은 any_of 묶음에 "
                    "항목을 나눠 넣는다. of.setting으로 시기를 좁힐 수 있음 "
                    "(예: 'paclitaxel을 포함한 보조요법' -> contains [paclitaxel], of.setting [adjuvant]). "
                    "'고식적요법'은 of.setting [metastatic]"),
    "prior_failed": ("patient_state.fields.treatment_history[].stop_reason = progression 또는 best_response = PD "
                     "(A의 data_needs_by_module §4)",
                     ["contains"], _DRUGS, "'~에 실패한'·'~ 투여 후 진행된' 약·계열. 목록은 모두 실패했어야 한다 "
                     "(예: 'trastuzumab과 taxane계 항암제 모두에 실패'). 'A 또는 B에 실패'는 any_of 묶음으로 나눈다"),
    "palliative_endocrine_lines": ("patient_state.fields.treatment_history[].endocrine_line의 최댓값 (전이 전 null = 0)",
                                   ["eq", "gte", "lte"], _NUM, "이미 받은 고식적 내분비요법 차수"),
    "palliative_chemo_lines": ("patient_state.fields.treatment_history[].chemo_line의 최댓값 (전이 전 null = 0)",
                               ["eq", "gte", "lte"], _NUM,
                               "이미 받은 고식적 항암화학요법 차수. '고식적 항암화학요법을 투여하지 않은' -> eq 0"),
    "days_end_to_recurrence": ("patient_state.fields.recurrence.recurrence_day.value - treatment_history[].end_day", ["gt", "lte"], _NUM,
                               "'투여 종료 후 1년 이후 재발' -> gt 365, '투여 중 또는 종료 1년 이내 재발' -> lte 365, "
                               "'6개월 이내' -> lte 183. of에 대상 약·시기. 첫 재발일(국소 재발 포함)까지. "
                               "단 고식적 내분비 1차(3가)는 days_end_to_metastasis (A 답변 2026-10-21)"),
    "days_end_to_metastasis": ("patient_state.fields.recurrence.metastasis_day.value - treatment_history[].end_day "
                               "(A의 deemed_lines DEEM-ENDO-ADJ-1Y와 같은 기준: 종료일부터 전이 기준일까지)", ["gt", "lte"], _NUM,
                               "고식적 단계에서 '수술후보조요법 투여 중 또는 종료 후 1년 이내에 진행' -> lte 365 (진행 = 전이, B 확인). "
                               "고식적 내분비 1차(3가)의 '종료 후 1년 이후 재발'·'1년 이내 재발'도 이 칸 (A 답변 2026-10-21: "
                               "DEEM-ENDO-ADJ-1Y로 판정). 병용 연번 30(2026-11-01판)의 'CDK4/6 종료 후 12개월 초과'는 of CDK4/6로 gt 365. "
                               "그 밖의 '재발'로 적힌 기간은 days_end_to_recurrence. 국소 재발만 있어 전이 기준일이 없으면 알 수 없음"),
    "days_end_to_progression": ("patient_state.fields.treatment_history[].progression_day - end_day", ["lte", "gt"], _NUM,
                                "'고식적요법 투여 중 또는 종료 후 1달 이내에 진행' -> lte 30"),
    "recent_therapy_28d": ("patient_state.fields.at_index.recent_therapy_28d.status (A가 계산, unknown이면 알 수 없음)",
                           ["eq"], ["yes", "no"],
                           "'최근 4주 이내에 항암제 또는 호르몬제가 투여된' -> eq yes (A의 data_needs_by_module §6-1)"),
    "treatment_years": ("patient_state.fields.treatment_history[].duration_days ÷ 365 (년)", ["lte"], _NUM, "'투여기간: 5년' -> lte 5"),
    "cycles_total": ("patient_state.fields.treatment_history[].cycles.value 합 (basis가 estimated인 값이 들어가면 추정값으로 표시)",
                     ["lte", "eq"], _NUM,
                     "'총 trastuzumab 투여 주기 18주기 이하' -> lte 18, of.drugs [trastuzumab]"),
    # 용량은 A가 2026-10-28부터 treatment_history[].doses[]에 채운다 (draft7 체크리스트 §0). 단위는 원문 그대로라
    # mg이면 판정 쪽이 키·몸무게로 mg/m2로 바꾼다. 체표면적은 Mosteller 공식 (B 제안, D 동의 2026-10-29)
    "cumulative_dose_mg_m2": ("patient_state.fields.treatment_history[].doses[] 중 of.drugs 약의 total을 모두 더한 값 (mg/m2). "
                              "단위가 mg면 patient.height_cm·weight_kg의 체표면적(Mosteller: √(키cm × 몸무게kg ÷ 3600))으로 "
                              "나눈다. 키·몸무게가 없거나 'No value'면 "
                              "알 수 없음. doses가 없는 기록은 anthracycline_drug_dose.drugs[].total_dose.value (mg/m2만)",
                              ["gt", "gte"], _NUM,
                              "'doxorubicin 누적 240mg/m2 이상' -> gte 240, of.drugs [doxorubicin]. "
                              "'cisplatin 총 투여용량 300mg/㎡ 이상' -> gte 300, of.drugs [cisplatin]"),
    "per_admin_dose_mg_m2": ("patient_state.fields.treatment_history[].doses[] 중 of.drugs 약의 per_admin (1회 용량, mg/m2) 중 "
                             "가장 큰 값. 단위 바꾸기와 알 수 없음은 cumulative_dose_mg_m2와 같다. 공고의 '1 cycle당'은 "
                             "한 주기에 한 번 주는 요법이면 1회 용량과 같고, 나눠 주는 요법은 주기 용량을 알 수 없으므로 "
                             "1회 용량이 기준 이상이면 참, 기준보다 작으면 알 수 없음 (거짓으로 두지 않음)", ["gt", "gte"], _NUM,
                             "'시스플라틴 고용량 투여(1 cycle당 100㎎/㎡ 이상)' -> gte 100, of.drugs [cisplatin]"),
    # 2026-10-22에 칸이 생겨 이번 모델 제외 조항을 없앴다 (PROJECT.md §12). 값은 yes -> true, no -> false,
    # 기록 없음은 알 수 없음. liposomal doxorubicin은 누적용량 기준을 만족하면 이 조건 없이 판정한다
    "cardiac_history": ("patient_state.fields.patient.cardiac_history.value (yes -> true, no -> false)", ["eq"], [True, False],
                        "4나-19 '심장위험요소'는 공고 원문의 '관상동맥질환, 부정맥, 울혈성 심부전 등의 심장질환 병력'이다 "
                        "(LVEF 기준은 원문에 없음. 종격동 방사선요법 치료력은 mediastinal_radiation). "
                        "Ⅳ dexrazoxane의 '울혈 심부전증 병력 등 병발 심장질환' -> eq true"),
    "mediastinal_radiation": ("patient_state.fields.patient.mediastinal_radiation.value (yes -> true, no -> false)",
                              ["eq"], [True, False], "'종격동 방사선 치료' 경험 -> eq true"),
    # 의사 판단으로 대상이 넓어지는 예외 (2026-11-04 D 결정). 환자 JSON에 칸이 없어 판정은 늘 알 수 없음이다.
    # 본 조건 항목의 unless에만 둔다: 본 조건을 만족하면 그대로 충족, 만족하지 못하면 거짓 대신 알 수 없음 (의사 확인)
    "physician_opinion": ("환자 JSON에 칸 없음 (의사 판단, 늘 알 수 없음)", ["eq"], [True],
                          "'이러한 치료가 부적절한 환자는 예외로 함', '사용할 수 없는 타당한 의사 소견이 있는 경우'처럼 "
                          "의사 판단으로 대상이 넓어지는 예외 -> 그 예외가 덮는 본 조건 항목의 unless에 eq true. "
                          "unless 밖에는 쓰지 않는다"),
}
UNLESS_ONLY_FIELDS = frozenset({"physician_opinion"})

_VALUE = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"},
                    {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "number"}]}}]}
_OF = {"type": "object", "additionalProperties": False,
       "properties": {"drugs": {"type": "array", "items": {"type": "string"}},
                      "setting": {"type": "array", "items": {"enum": ["neoadjuvant", "adjuvant", "metastatic"]}}}}
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
                               "setting": {"type": "array", "items": {"enum": ["neoadjuvant", "adjuvant", "metastatic"]}},
                               "drugs": {"type": "array", "items": {"type": "string"}},
                               "within_days": {"type": "number"},
                               # A의 deemed_lines 규칙 이름. 적혀 있으면 판정 쪽이 이 규칙을 그대로 본다 (VC-0103, 2026-10-22)
                               "rule_id": {"enum": DEEM_RULES}}}},
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
   고식적 내분비 2차 이상의 '수술후보조요법 투여 중 또는 종료 후 1년 이내에 진행된 경우도 인정함'도 간주 규칙이다:
   counts_as_prior_line에 rule_id DEEM-ENDO-ADJ-1Y, setting [adjuvant], drugs [Hormone Therapy]로 넣는다 (within_days 없이).
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
        if it.get("field") in UNLESS_ONLY_FIELDS:
            errs.append(f"{where}: {it['field']}은 본 조건 항목의 unless에만 쓸 수 있음")
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

    def entry(self, key: str) -> dict | None:
        return self.rows.get(key)

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
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise StructurerUnavailable("API 키 없음 (.env의 ANTHROPIC_API_KEY)")
        self.anthropic = anthropic
        ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        self.client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)
        self.model = model

    label = MODEL

    def __call__(self, text: str, context: str) -> tuple[dict, dict]:
        user = _user_message(text, context)
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


def _user_message(text: str, context: str) -> str:
    return (f"[소단원 안내 - 참고용, 이 행 조건의 근거로도 인용할 수 있음]\n{context}\n\n" if context else "") \
        + f"[급여 기준 본문]\n{text}"


def _version_key(name: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in name.split("."))


def find_claude_code() -> str | None:
    """Claude Code 실행 파일. CLAUDE_CODE_EXE 환경 변수 > PATH의 claude > Claude 데스크톱 앱에 든 최신판."""
    import shutil
    exe = os.environ.get("CLAUDE_CODE_EXE") or shutil.which("claude")
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA")
    # Windows 스토어판 앱은 AppData를 앱 전용 폴더로 돌려 두므로, 앱 밖 터미널에서는 이 실제 위치에 있다
    packaged = [p / "LocalCache" / "Roaming" / "Claude" / "claude-code"
                for p in (Path(local) / "Packages").glob("Claude_*")] if local else []
    bases = [Path(os.environ.get("APPDATA", "")) / "Claude" / "claude-code",                 # Windows (앱 안에서 본 경로)
             *packaged,
             Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"]    # macOS
    found = [p for b in bases if b.is_dir() for p in b.glob("*/*/claude*") if p.is_file()]
    found = [p for p in found if p.name in ("claude", "claude.exe")]
    if not found:
        return None
    return str(max(found, key=lambda p: _version_key(p.parent.parent.name)))


class ClaudeCodeStructurer:
    """Claude Code(claude -p)로 조건 JSON을 받는다. API 크레딧 대신 Claude 구독 사용량을 쓴다.
    프롬프트·출력 형식은 ClaudeStructurer와 같다. 처음 한 번 터미널에서 claude를 실행해 /login 해 둔다.
    도구·MCP·세션 저장은 끄고, 저장소 밖(임시 폴더)에서 실행해 프로젝트 설정을 읽지 않게 한다."""

    def __init__(self, model: str = MODEL, exe: str | None = None, timeout: int = 900):
        self.exe = exe or find_claude_code()
        if not self.exe:
            raise StructurerUnavailable("Claude Code 실행 파일 없음 (CLAUDE_CODE_EXE 환경 변수로 경로 지정)")
        self.model = model
        self.timeout = timeout

    def _cmd(self) -> list[str]:
        return [self.exe, "-p", "--output-format", "json", "--model", self.model,
                "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                "--system-prompt", SYSTEM, "--json-schema", json.dumps(output_schema())]

    def __call__(self, text: str, context: str) -> tuple[dict, dict]:
        import subprocess
        import tempfile
        # API 키가 환경에 있으면 Claude Code가 구독 대신 그 키(API 크레딧)를 쓰므로 넘기지 않는다
        env = {k: v for k, v in os.environ.items() if k not in (*DOTENV_KEYS, "ANTHROPIC_AUTH_TOKEN")}
        try:
            r = subprocess.run(self._cmd(), input=_user_message(text, context), capture_output=True, text=True,
                               encoding="utf-8", cwd=tempfile.gettempdir(), timeout=self.timeout, env=env)
        except OSError as e:
            raise StructurerUnavailable(f"Claude Code 실행 실패: {e}") from e
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Claude Code 출력이 JSON이 아님: {(r.stderr or r.stdout)[:300]}") from e
        msg = str(out.get("result") or "")
        if out.get("is_error"):
            low = msg.lower()
            # 계정 문제·사용 한도는 행마다 다시 시도해도 같아서 전체를 멈춘다 (받은 결과는 저장본에 남는다)
            if "not logged in" in low or "/login" in low:
                raise StructurerUnavailable(f"Claude Code 로그인 필요: 터미널에서 {self.exe} 실행 후 /login")
            if "credit balance" in low:
                raise StructurerUnavailable(f"Claude Code가 크레딧 없는 API 키로 접속함: {msg[:200]} (/login으로 구독 계정 로그인)")
            if "limit" in low or "quota" in low:
                raise StructurerUnavailable(f"Claude 구독 사용 한도: {msg[:200]} (한도가 풀린 뒤 다시 실행하면 이어서 함)")
            raise RuntimeError(f"Claude Code 오류: {msg[:300]}")
        cond = out.get("structured_output")
        if cond is None:
            body = re.sub(r"^```(?:json)?\s*|\s*```$", "", msg.strip())
            cond = json.loads(body)
        u = out.get("usage") or {}
        usage = {"input_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                 + u.get("cache_creation_input_tokens", 0),
                 "output_tokens": u.get("output_tokens", 0), "session_id": out.get("session_id"),
                 "via": "claude-code"}
        return cond, usage

    @property
    def label(self) -> str:
        return f"claude-code:{self.model}"


OLLAMA_HOST = "http://127.0.0.1:11500"    # GPU 서버의 Ollama를 SSH 터널로 이 포트에 연다 (README "로컬 LLM")


UPDATE_TASK = ("[할 일] 위 이전 판(사람이 검수한 조건)에서 바뀐 부분만 조건에 반영하고, 바뀌지 않은 조건은 이전 판 그대로 둔다. "
               "원문 구절(text)은 새 본문(또는 소단원 안내)에서 그대로 복사한다.")
REVISE_TASK = ("코드 검사에서 아래 문제가 나왔다. 문제가 있는 칸만 고치고 나머지는 그대로 두어 JSON 전체를 다시 답하라. "
               "원문에 없는 구절은 원문에서 한 글자도 바꾸지 않고 복사하고, 옮길 수 없는 조건은 unmapped에 원문 그대로 넣는다.\n")


def _update_message(prev: dict, text: str, context: str) -> str:
    return (f"[이전 판 급여 기준 본문]\n{prev['text']}\n\n[이전 판 조건 (사람이 검수함)]\n"
            f"{json.dumps(prev['conditions'], ensure_ascii=False)}\n\n{_user_message(text, context)}\n\n{UPDATE_TASK}")


class OllamaStructurer:
    """로컬 모델(Ollama)로 조건 JSON을 받는다 (PROJECT.md §9, 2026-10-23 Claude API에서 로컬 모델로 바꿈).
    공용 llm/의 complete_json을 쓴다. llm/config.toml에 칸을 두지 않고 환경 변수로 받는다:
    REIMB_OLLAMA_MODEL (없으면 이 방식을 건너뜀), REIMB_OLLAMA_HOST (기본 OLLAMA_HOST).
    프롬프트·출력 형식·검사는 Claude 방식과 같다.

    예시 없이는 우리 조건 형식의 관례(칸 고르기·단위·묶음 위치)를 몰라 쓸 수 없어서 (131행 평가: 항목 정확도 25%),
    행마다 prepare로 원문이 가장 비슷한 검수된 행 similar개를 예시로 넣고 (80%), 이전 책자에 같은 행이 있으면
    이전 판 원문·조건을 주고 바뀐 부분만 고치게 한다. 받은 초안은 draft()가 규칙으로 고치고, 검사에 걸리면 한 번 더 묻는다."""

    assisted = True         # draft()에서 규칙 고치기·다시 묻기를 쓴다

    def __init__(self, model: str | None = None, host: str | None = None, timeout: int = 900, think: bool = False,
                 examples: list[tuple[str, str, dict]] | None = None, similar: int = 3):
        import requests
        model = model or os.environ.get("REIMB_OLLAMA_MODEL")
        if not model:
            raise StructurerUnavailable("로컬 모델 미지정 (REIMB_OLLAMA_MODEL)")
        host = (host or os.environ.get("REIMB_OLLAMA_HOST") or OLLAMA_HOST).rstrip("/")
        try:
            tags = requests.get(f"{host}/api/tags", timeout=60).json()     # 터널 첫 연결이 10초를 넘긴 적이 있음
        except (requests.RequestException, ValueError) as e:
            raise StructurerUnavailable(f"Ollama 서버에 연결 안 됨: {host} (SSH 터널 확인)") from e
        if model not in {m.get("name") for m in tags.get("models", [])}:
            raise StructurerUnavailable(f"Ollama에 모델 없음: {model} (서버에서 ollama pull)")
        from llm import LLMConfig
        # 시스템 프롬프트(어휘 목록)가 길어 문맥을 넉넉히 둔다. 예시(검수된 행)를 넣으면 더 늘린다.
        # 생각 모드는 기본으로 끈다 (llm/ 기본값과 같음). 켜면 생각한 글도 출력 길이에 들어가 상한을 올린다
        self.fixed_examples = list(examples or [])     # 늘 넣는 예시 (평가용 --shots)
        self.examples = list(self.fixed_examples)
        self.similar = similar
        self.previous_row: dict | None = None
        self.hint: dict = {}
        self.config = LLMConfig(provider="ollama", model=model, patient_data=False, host=host,
                                num_ctx=32768 if self.examples or similar else 16384,
                                max_tokens=16384 if think else 8192, timeout=timeout, retries=1, think=think)

    def prepare(self, target: dict, pool: list[dict], previous: list[dict] = ()) -> None:
        """target 행에 넣을 예시를 고른다. pool·previous는 검수된 행 {chunk_id, text, context, conditions, drugs}."""
        ranked = similar_rows(target, pool, 2 * self.similar) if self.similar else []
        picked = ranked[:self.similar]
        self.examples = self.fixed_examples + [(p["text"], p.get("context", ""), p["conditions"]) for p in picked]
        self.previous_row = find_previous(target, previous)
        # 두 번째 답(second_opinion)용: 이전 판이 있으면 이전 판 없이 같은 예시로, 없으면 그다음으로 비슷한 예시로
        alt = picked if self.previous_row else ranked[self.similar:] or picked
        self._alt_examples = self.fixed_examples + [(p["text"], p.get("context", ""), p["conditions"]) for p in alt]
        best = max((similarity(target["text"], p["text"]) for p in pool if p["chunk_id"] != target["chunk_id"]),
                   default=None)
        self.hint = {"examples": [p["chunk_id"] for p in picked],
                     "previous": self.previous_row["chunk_id"] if self.previous_row else None,
                     "similarity": round(best, 2) if best is not None else None}

    def messages(self, text: str, context: str) -> list[dict]:
        msgs = [{"role": "system", "content": SYSTEM}]
        for t, c, cond in self.examples:       # 검수된 행을 앞선 문답으로 보여 준다 (few-shot)
            msgs += [{"role": "user", "content": _user_message(t, c)},
                     {"role": "assistant", "content": json.dumps(cond, ensure_ascii=False)}]
        last = _update_message(self.previous_row, text, context) if self.previous_row else _user_message(text, context)
        return msgs + [{"role": "user", "content": last}]

    def __call__(self, text: str, context: str) -> tuple[dict, dict]:
        from llm import complete_json
        cond = complete_json(self.messages(text, context), output_schema(), self.config)
        return cond, {"via": "ollama", "model": self.config.model}

    def second_opinion(self, text: str, context: str) -> dict:
        """다른 질문으로 한 번 더 만든 답 (prepare에서 고른 다른 예시, 이전 판 없이). 첫 답과 다르면 불확실로 본다."""
        saved = self.examples, self.previous_row
        self.examples, self.previous_row = getattr(self, "_alt_examples", self.examples), None
        try:
            return self(text, context)[0]
        finally:
            self.examples, self.previous_row = saved

    def revise(self, text: str, context: str, cond: dict, problems: list[str]) -> dict:
        """검사에 걸린 초안을 문제 목록과 함께 돌려주고 고친 것을 받는다."""
        from llm import complete_json
        msgs = self.messages(text, context) + [
            {"role": "assistant", "content": json.dumps(cond, ensure_ascii=False)},
            {"role": "user", "content": REVISE_TASK + "\n".join(problems[:20])}]
        return complete_json(msgs, output_schema(), self.config)

    @property
    def label(self) -> str:
        extra = ((["think"] if self.config.think else []) + ([f"{len(self.fixed_examples)}shot"] if self.fixed_examples else [])
                 + ([f"sim{self.similar}"] if self.similar else []))
        return f"ollama:{self.config.model}" + (f" ({', '.join(extra)})" if extra else "")


# 기본 구조화 순서: 로컬 모델(REIMB_OLLAMA_MODEL이 있을 때) -> Claude API(.env 키, 크레딧) -> Claude Code(구독)
STRUCTURERS = (OllamaStructurer, ClaudeStructurer, ClaudeCodeStructurer)


def _next_structurer(factories: list, reasons: list[str]):
    while factories:
        try:
            return factories.pop(0)()
        except StructurerUnavailable as e:
            reasons.append(str(e))
    return None


# ---------- 로컬 모델 돕기: 예시 고르기, 규칙으로 고치기, 다시 묻기 ----------

_DRAFT_LABELS = ("ollama:", "claude-code:")


def is_reviewed(model: str | None) -> bool:
    """저장본 한 줄이 사람이 넣은(--import) 조건인지. 구조화 방식(로컬 모델·Claude)이 만든 초안이면 False."""
    return bool(model) and not model.startswith(_DRAFT_LABELS) and model != MODEL


def _words(text: str) -> set[str]:
    """비슷한 행 찾기용 낱말 (첫 줄 머리 제목과 공고 번호·날짜는 뺌)."""
    body = re.sub(r"^\[[^\]]*\]\n", "", text)
    body = re.sub(r"\(제\s*\d{4}-\d+호[^)]*\)|\d{4}\.\d{1,2}\.\d{1,2}\.?", " ", body)
    return set(re.findall(r"[0-9A-Za-z가-힣/+.]+", body.lower()))


def similarity(a: str, b: str) -> float:
    """두 원문의 낱말 겹침 (Jaccard)."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / (len(wa | wb) or 1)


def similar_rows(target: dict, pool: list[dict], k: int, skip_self: bool = True) -> list[dict]:
    """pool 중 원문 낱말이 가장 많이 겹치는 k개. skip_self면 같은 chunk_id는 뺀다."""
    scored = [(similarity(target["text"], c["text"]), c["chunk_id"], c)
              for c in pool if not (skip_self and c["chunk_id"] == target["chunk_id"])]
    return [c for _, _, c in sorted(scored, key=lambda x: (-x[0], x[1]))[:k]]


def row_group(chunk_id: str) -> str:
    """책자 날짜와 연번을 뺀 소단원 이름 (hira-booklet-20261101-bc-adj-r19 -> bc-adj, ...-supp-gcsf-b1 -> supp-gcsf)."""
    return re.sub(r"-(?:r\d+|[a-z]\d*|\d+)$", "", re.sub(r"^hira-booklet-\d{8}-", "", chunk_id))


def find_previous(target: dict, previous: list[dict]) -> dict | None:
    """새 책자 행의 이전 판: 이전 책자 행 중 같은 소단원·같은 약 목록이고 원문이 가장 비슷한 것. 없으면 새 행."""
    g, drugs = row_group(target["chunk_id"]), sorted(target.get("drugs") or [])
    cands = [p for p in previous if row_group(p["chunk_id"]) == g and sorted(p.get("drugs") or []) == drugs]
    return (similar_rows(target, cands, 1, skip_self=False) or [None])[0]


def _stored(c: dict) -> dict:
    return {k: v for k, v in (c["reimbursement"].get("conditions") or {}).items() if k != "line_rule"}


def reviewed_rows(chunks: list[dict], cache: Cache, contexts: dict[str, str] | None = None) -> list[dict]:
    """이전 책자 청크(reimbursement_chunks_current.jsonl) 중 조건이 사람이 넣은 저장본과 같은 행.
    바뀐 행의 이전 판으로 쓴다. 검수 전 초안이 붙은 행은 넣지 않는다.
    contexts: 그 책자의 소단원 안내 (reimbursement_contexts_current.json). 없으면 context는 None이고
    내용이 같아도 옮기지 않는다 (carry_over)."""
    by_id: dict[str, list[tuple[dict, str]]] = {}
    for r in cache.rows.values():
        if is_reviewed(r.get("model")):
            by_id.setdefault(r["chunk_id"], []).append((r["conditions"], r["model"]))
    out = []
    for c in chunks:
        if c.get("chunk_kind") not in TARGET_KINDS or not _stored(c):
            continue
        # 저장본은 원문 해시가 열쇠라, 원문이 그대로인 행은 처음 넣을 때의 (옛 책자) 행 이름으로 남아 있다.
        # 안내를 알면 해시로 찾고, 모르면 행 이름으로 찾는다
        e = cache.entry(cache_key(c["text"], contexts.get(c["chunk_id"], ""))) if contexts is not None else None
        found = [(e["conditions"], e["model"])] if e and is_reviewed(e.get("model")) else []
        author = next((m for cond, m in found + by_id.get(c["chunk_id"], []) if cond == _stored(c)), None)
        if author is not None:
            out.append({"chunk_id": c["chunk_id"], "text": c["text"], "drugs": c.get("drugs") or [],
                        "context": contexts.get(c["chunk_id"]) if contexts is not None else None,
                        "conditions": _stored(c), "author": author})
    return out


# ---------- 원문 내용이 같은 행: 모델 없이 이전 판 조건을 옮긴다 (2026-11-03) ----------
# 원문이 같은데 모델에 다시 물으면 맞는 조건을 고쳐 쓴다 (131행 평가: 이전 판이 맞는데 17행을 바꿈).
# 그래서 공백·문장부호만 다른 행은 검수된 조건을 그대로 옮기고, 원문 구절만 새 책자 표기로 맞춘다.

CARRIED_MARK = " (이전 판에서 옮김)"       # 저장본 model 칸: 검수한 사람 뒤에 붙인다 (is_reviewed는 True)
_PUNCT = re.compile(r"[\s.,·:;'\"“”‘’`()\[\]{}「」『』]|※|▪|•")


def _content(s: str) -> str:
    """내용 비교용: NFKC(①→1, ㎝→cm) 뒤 공백·문장부호를 뺀다. 숫자·글자·비교 기호(> < ≥ ≤)·∼는 남는다."""
    return _PUNCT.sub("", unicodedata.normalize("NFKC", s or ""))


def same_content(a: str, b: str) -> bool:
    return _content(a) == _content(b)


# 행 자신의 연번 (머리 제목 '> 연번 21]'과 '연번 21' 한 줄). 앞에 행이 생기면 숫자만 밀린다 (11-01 책자 병용요법)
_OWN_NO = re.compile(r"(?m)(?<=> )연번 \d+(?=\])|^연번\s*\d+\s*$")


def _without_own_no(text: str) -> str:
    return _OWN_NO.sub("", text)


def _align_quote(t: str, source: str) -> str | None:
    """이전 판 구절을 새 원문에서 같은 내용의 구절로 바꾼다. 원문에 그대로 있으면 그대로, 못 찾으면 None."""
    if not isinstance(t, str) or not _content(t):
        return None
    if _norm(t) in _norm(source):
        return t
    chars, idx = [], []
    for i, ch in enumerate(source):
        for o in unicodedata.normalize("NFKC", ch):
            if not _PUNCT.fullmatch(o):
                chars.append(o)
                idx.append(i)
    want = _content(t)
    pos = "".join(chars).find(want)
    if pos < 0:
        return None
    start, end = idx[pos], idx[pos + len(want) - 1] + 1
    # 이전 구절 앞뒤의 문장부호('(투여기간: 5년)'의 괄호 등)는 새 원문에도 있으면 같이 붙인다
    lead = len(t) - len(t.lstrip("([「『“‘'\""))
    trail = len(t) - len(t.rstrip(").]」』”’'\"。"))
    for _ in range(lead):
        if start > 0 and source[start - 1] in "([「『“‘'\"":
            start -= 1
    for _ in range(trail):
        if end < len(source) and source[end] in ").]」』”’'\"。":
            end += 1
    return re.sub(r"\s+", " ", source[start:end]).strip()


def _realign(cond: dict, source: str) -> dict | None:
    """조건의 원문 구절을 모두 새 원문에 맞춘다. 하나라도 못 찾으면 None."""
    cond = json.loads(json.dumps(cond))
    holders = []
    for _, it in iter_items(cond):
        holders.append(it)
        if it.get("unless"):
            holders.append(it["unless"])
    for key in ("any_of", "any_of_exceptions", "counts_as_prior_line"):
        holders += cond.get(key, [])
    for h in holders:
        if "text" in h:
            if (q := _align_quote(h["text"], source)) is None:
                return None
            h["text"] = q
    for key in ("notes", "human_review", "unmapped"):
        new = [_align_quote(t, source) for t in cond.get(key, [])]
        if None in new:
            return None
        if key in cond:
            cond[key] = new
    return cond


def carry_over(target: dict, context: str, previous: list[dict]) -> tuple[dict, dict] | None:
    """이전 판(find_previous)과 본문·소단원 안내의 내용이 같으면 (검수된 조건, 이전 판 행). 아니면 None.
    본문의 자기 연번 숫자는 비교에서 뺀다 (안내에 '연번 N' 한 줄로 든 위 행 번호도). 문장 순서만 바뀐 행은
    같다고 보지 않는다 (모델로 넘김). 이전 판 안내를 모르면(context None) 옮기지 않는다.
    구절을 맞춘 뒤 검사에 걸려도 옮기지 않는다 (모델로 넘김)."""
    p = find_previous(target, previous)
    if p is None or p.get("context") is None:
        return None
    if not (same_content(_without_own_no(p["text"]), _without_own_no(target["text"]))
            and same_content(_without_own_no(p["context"]), _without_own_no(context))):    # 병합 행 안내의 '위 행: 연번 N'
        return None
    source = f"{context}\n{target['text']}"
    cond = _realign(p["conditions"], source)
    if cond is None or problems_of(cond, source):
        return None
    return cond, p


# 비교 낱말 -> op. 한 구절에 한 종류만 있을 때만 쓴다 ('1cm 이상' -> gte, '직경 > 2cm' -> gt)
_CMP_WORDS = [("초과", "gt"), ("이상", "gte"), ("미만", "lt"), ("이하", "lte"),
              ("≥", "gte"), ("≤", "lte"), (">", "gt"), ("<", "lt")]
# 병기·크기 칸은 치료 시기로 정해진다 (FIELDS의 ct_stage 위 주석, A draft7 체크리스트 §4)
_TIMING_FIELDS = {"neoadjuvant": {"pt_stage": "ct_stage", "pn_status": "cn_status",
                                  "pathologic_size_mm": "clinical_size_mm"},
                  "adjuvant": {"ct_stage": "pt_stage", "cn_status": "pn_status",
                               "clinical_size_mm": "pathologic_size_mm"}}
_QUOTE_MARKS = "\"'“”‘’「」『』 "


def _fix_drug(name, vocab: frozenset[str]):
    if not isinstance(name, str) or name in vocab:
        return name
    for cand in (name.lower(), name.replace(" ", "_"), name.lower().replace(" ", "_")):
        if cand in vocab:
            return cand
    return name


def _fix_quote(t: str, src: str) -> str:
    """원문에 없는 구절이 앞뒤 따옴표·마침표만 다르면 떼어 낸다."""
    if not isinstance(t, str) or _norm(t) in src:
        return t
    for s in (t.rstrip(" .。"), t.strip(_QUOTE_MARKS), t.strip(_QUOTE_MARKS).rstrip(".。")):     # 덜 바꾼 것부터
        if s and _norm(s) in src:
            return s
    return t


def _fix_item(it: dict, stage: str | None, src: str, vocab: frozenset[str], where: str, log: list[str]) -> None:
    f = it.get("field")
    if f in _TIMING_FIELDS.get(stage, {}):
        it["field"] = _TIMING_FIELDS[stage][f]
        log.append(f"{where}: {f} -> {it['field']} ({stage} 행)")
        f = it["field"]
    if f not in FIELDS:
        return
    _, ops, allowed, _ = FIELDS[f]
    text, op, val = it.get("text") or "", it.get("op"), it.get("value")
    if op == "in" and not isinstance(val, list):
        it["value"] = val = [val]
        log.append(f"{where}: in 값을 목록으로")
    if op == "eq" and isinstance(val, list) and "in" in ops:
        it["op"], op = ("in", "in") if len(val) > 1 else ("eq", "eq")
        if len(val) == 1:
            it["value"] = val = val[0]
        log.append(f"{where}: eq 목록 -> {op}")
    if allowed == _NUM and op in ("gt", "gte", "lt", "lte"):
        kinds = {o for w, o in _CMP_WORDS if w in text}
        if len(kinds) == 1 and (new := kinds.pop()) != op and new in ops:
            it["op"] = new
            log.append(f"{where}: op {op} -> {new} (원문 비교 낱말)")
    if f.endswith("_size_mm") and isinstance(val, (int, float)) and not isinstance(val, bool) \
            and not re.search(r"mm|㎜", text, re.I) \
            and val in [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:cm|㎝)", text, re.I)]:
        it["value"] = int(val * 10) if float(val * 10).is_integer() else val * 10
        log.append(f"{where}: {val}cm -> {it['value']}mm")
    if allowed == _DRUGS:
        new = [_fix_drug(v, vocab) for v in val] if isinstance(val, list) else _fix_drug(val, vocab)
        if new != val:
            it["value"] = new
            log.append(f"{where}: 약 이름 사전 표기로")
    if (it.get("of") or {}).get("drugs"):
        it["of"]["drugs"] = [_fix_drug(d, vocab) for d in it["of"]["drugs"]]
    q = _fix_quote(text, src)
    if q != text:
        it["text"] = q
        log.append(f"{where}.text: 앞뒤 따옴표·마침표 뗌")
    if it.get("unless"):
        _fix_item(it["unless"], stage, src, vocab, f"{where}.unless", log)


def fix_conditions(cond: dict, stage: str | None, source: str) -> tuple[dict, list[str]]:
    """규칙으로 정해지는 것은 모델에 맡기지 않고 코드가 고친다 (로컬 모델 초안에만 쓴다). 고친 내용 목록도 돌려준다.
      - 병기·크기 칸: 선행요법 행은 임상(c), 수술후보조요법 행은 병리(p) 칸 (치료 시기로 정해짐)
      - 구절에 비교 낱말이 한 종류만 있으면 op를 그것으로 (초과 gt, 이상 gte, 미만 lt, 이하 lte)
      - 크기 칸 값이 구절의 cm 숫자 그대로면 mm로 (×10)
      - in인데 값이 하나면 목록으로, eq인데 목록이면 in으로
      - 약 이름의 대소문자·띄어쓰기를 사전 표기로
      - 원문 구절이 앞뒤 따옴표·마침표만 다르면 떼어 냄
    사람이 쓴 저장본 131행에 쓰면 하나도 바뀌지 않는다 (tests/reimbursement/test_conditions.py)."""
    cond = json.loads(json.dumps(cond))
    src, vocab, log = _norm(source), prior_vocab(), []
    for where, it in iter_items(cond):
        _fix_item(it, stage, src, vocab, where, log)
    for g in cond.get("counts_as_prior_line", []):
        g["drugs"] = [_fix_drug(d, vocab) for d in g.get("drugs", [])]
    for key in ("any_of", "any_of_exceptions", "counts_as_prior_line"):
        for i, g in enumerate(cond.get(key, [])):
            if (q := _fix_quote(g.get("text", ""), src)) != g.get("text", ""):
                g["text"] = q
                log.append(f"{key}[{i}].text: 앞뒤 따옴표·마침표 뗌")
    for key in ("notes", "human_review", "unmapped"):
        cond[key] = [_fix_quote(t, src) for t in cond.get(key, [])]
    return cond, log


def problems_of(cond: dict, source: str) -> list[str]:
    return check_schema(cond) + check_values(cond) + check_grounding(cond, source)


def draft(structurer, chunk: dict, context: str, verify: bool = True) -> tuple[dict, dict]:
    """구조화 방식 하나로 초안을 받는다. 로컬 모델(assisted)이면 규칙으로 고치고, 검사에 걸리면 문제를 알려 한 번 더 묻고,
    마지막으로 확인한다(verify.py): 칸·값·숫자·빠진 조건을 보고, 다른 질문으로 한 번 더 만든 답과 비교한다.
    걸린 구절은 human_review에 넣는다 (그 행은 판정에서 '알 수 없음').
    사용량 칸에 예시·이전 판·겹침·고친 내용·확인 결과를 남긴다 (검수표의 검수 우선순위에 쓴다).
    verify=False는 평가용 (확인 전 답을 채점하고 확인은 따로 본다)."""
    text = chunk["text"]
    cond, usage = structurer(text, context)
    if not getattr(structurer, "assisted", False):
        return cond, usage
    source, stage = f"{context}\n{text}", chunk["reimbursement"].get("stage")
    cond, fixed = fix_conditions(cond, stage, source)
    usage = {**usage, **getattr(structurer, "hint", {}), "fixed": fixed, "revised": False}
    problems = problems_of(cond, source)
    if problems:
        try:
            again = structurer.revise(text, context, cond, problems)
        except Exception as e:          # 다시 묻기가 실패하면 첫 초안을 그대로 둔다 (검사에서 버려진다)
            usage["revise_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        else:
            cond, fixed2 = fix_conditions(again, stage, source)
            usage.update(fixed=fixed + fixed2, revised=True, first_problems=[p.split(":")[0] for p in problems])
    if verify:
        from .verify import disagreements, flag_for_review
        extra = []
        if hasattr(structurer, "second_opinion"):
            try:
                second, _ = fix_conditions(structurer.second_opinion(text, context), stage, source)
            except Exception as e:      # 두 번째 답을 못 받으면 비교할 수 없으니 불확실로 둔다
                extra = [(f"두 번째 답을 받지 못함 ({type(e).__name__})", None)]
            else:
                extra = disagreements(cond, second, source)
                usage["second_same"] = not extra
        usage["draft"] = cond                   # 확인 전 초안 (평가에서 채점)
        cond, usage["verify"] = flag_for_review(cond, text, extra)
    return cond, usage


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
    sources: dict[str, dict] = field(default_factory=dict)          # chunk_id -> 만든 이·검수 여부·초안 정보 (검수표)
    carried: list[str] = field(default_factory=list)                # 원문 내용이 같아 이전 판 조건을 옮긴 행


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
                      cache: Cache | None = None, use_api: bool = True,
                      previous: list[dict] | None = None) -> ConditionReport:
    """대상 청크마다 저장된 결과를 쓰거나 API로 받아, 검사를 통과한 조건만 reimbursement.conditions에 넣는다.

    contexts: chunk_id -> 소단원 제목·머리 규칙·주석 (근거 구절로 쓸 수 있는 글)
    structurer: (본문, 안내) -> (조건, 사용량). None이고 use_api면 STRUCTURERS 순서대로 쓸 수 있는 것을 쓴다
    (Claude API가 키·크레딧 문제로 안 되면 Claude Code로 넘어간다).
    previous: 이전 책자의 검수된 행 (reviewed_rows). 본문·안내가 공백·문장부호만 다르면 모델 없이 그 조건을 옮기고
    (carry_over), 실제로 바뀐 행은 로컬 모델이 이전 판 기준으로 고치게 한다.
    로컬 모델의 예시는 이번 책자에서 저장본의 검수된 조건을 그대로 쓰는 행 중에서 고른다.
    """
    rep = ConditionReport()
    cache = cache or Cache()
    factories = list(STRUCTURERS) if structurer is None and use_api else []
    reasons: list[str] = []
    if structurer is None:
        structurer = _next_structurer(factories, reasons)
    pool = []
    for c in chunks:
        if c["chunk_kind"] in TARGET_KINDS:
            ctx = contexts.get(c["chunk_id"], "")
            e = cache.entry(cache_key(c["text"], ctx))
            if e and is_reviewed(e.get("model")) and not is_empty(e["conditions"]):
                pool.append({"chunk_id": c["chunk_id"], "text": c["text"], "context": ctx,
                             "drugs": c.get("drugs") or [], "conditions": e["conditions"]})
    for c in chunks:
        if c["chunk_kind"] not in TARGET_KINDS:
            continue
        cid, text, ctx = c["chunk_id"], c["text"], contexts.get(c["chunk_id"], "")
        key = cache_key(text, ctx)
        cond = cache.get(key)
        if cond is not None:
            rep.from_cache += 1
        elif previous and (moved := carry_over(c, ctx, previous)):
            cond, p = moved
            author = p["author"].removesuffix(CARRIED_MARK)       # 여러 번 옮겨도 표시는 하나
            cache.put(key, cid, cond, {"carried_from": p["chunk_id"]}, model=author + CARRIED_MARK)
            rep.carried.append(cid)
        else:
            while structurer is not None:
                try:
                    if hasattr(structurer, "prepare"):
                        structurer.prepare(c, pool, previous or [])
                    cond, usage = draft(structurer, c, ctx)
                    break
                except StructurerUnavailable as e:     # 다음 방법으로 같은 청크를 다시 시도
                    reasons.append(str(e))
                    structurer = _next_structurer(factories, reasons)
                except Exception as e:      # 한 청크 실패로 전체를 멈추지 않는다 (보고서에 남김)
                    rep.failed[cid] = f"{type(e).__name__}: {e}"
                    break
            if structurer is None:
                rep.skipped_no_api.append(cid)
                continue
            if cid in rep.failed:
                continue
            rep.requested += 1
            rep.input_tokens += usage.get("input_tokens", 0)
            rep.output_tokens += usage.get("output_tokens", 0)
            cache.put(key, cid, cond, usage, model=getattr(structurer, "label", MODEL))
        e = cache.entry(key) or {}
        rep.sources[cid] = {"model": e.get("model"), "reviewed": is_reviewed(e.get("model")),
                            **{k: v for k, v in (e.get("usage") or {}).items()
                               if k in ("examples", "previous", "similarity", "fixed", "revised", "verify",
                                        "carried_from")}}
        problems = problems_of(cond, f"{ctx}\n{text}")
        if problems:
            rep.rejected[cid] = problems
            continue
        if is_empty(cond):
            rep.empty.append(cid)
        c["reimbursement"]["conditions"] = merge_conditions(c["reimbursement"].get("conditions", {}), cond)
    if reasons:
        rep.unavailable_reason = " / ".join(reasons)
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
                  "검수(O/X)", "고칠 내용", "검수 우선", "만든 이", "코드가 고친 것"]


def review_priority(src: dict | None) -> tuple[int, str]:
    """검수 순서 (작을수록 먼저, 꼼꼼히). 확인(verify.py)에 걸린 초안이 맨 앞.
    겹침 기준은 2026-11-02 131행 평가 (겹침 0.7 이상 정확도 95%, 0.5 미만 47%)."""
    if not src:
        return 5, ""
    if src.get("reviewed"):
        return 4, f"검수됨 (원문 내용이 같아 이전 판 {src['carried_from']}에서 옮김)" if src.get("carried_from") else "검수됨"
    if src.get("verify"):
        return 0, f"확인에 걸림 (사람 검토로 돌림, 판정은 알 수 없음): {'; '.join(src['verify'][:3])}"
    if src.get("previous"):
        return 3, f"바뀐 행: 이전 판 {src['previous']}에서 바뀐 부분 위주로"
    s = src.get("similarity")
    if s is None or s < 0.5:
        return 1, f"새 행, 비슷한 검수 행 없음 (겹침 {s}): 꼼꼼히"
    if s < 0.7:
        return 2, f"새 행, 조금 비슷한 검수 행 (겹침 {s}): 꼼꼼히"
    return 3, f"새 행, 비슷한 검수 행 있음 (겹침 {s})"


def review_rows(chunks: list[dict], sources: dict[str, dict] | None = None) -> list[list[str]]:
    """검수표 줄. sources(ConditionReport.sources)가 있으면 검수 우선 순서로 행을 늘어놓는다."""
    sources = sources or {}
    order = sorted((c for c in chunks if c["chunk_kind"] in TARGET_KINDS and c["reimbursement"].get("conditions")),
                   key=lambda c: review_priority(sources.get(c["chunk_id"]))[0])
    rows = []
    for c in order:
        cond = c["reimbursement"].get("conditions") or {}
        src = sources.get(c["chunk_id"]) or {}
        tail = [review_priority(src)[1], src.get("model") or "", "; ".join(src.get("fixed") or [])]
        n0 = len(rows)
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
                extra = json.dumps({k: v for k, v in g.items() if k in ("setting", "drugs", "within_days", "rule_id")},
                                   ensure_ascii=False) if key == "counts_as_prior_line" else ""
                rows.append(head + [f"{key} (묶음 머리)", "", "", "", extra, "", g.get("text", ""), "", ""])
        for key in ("notes", "human_review", "unmapped"):
            for t in cond.get(key, []):
                rows.append(head + [key, "", "", "", "", "", t, "", ""])
        for r in rows[n0:]:
            r += tail
    return rows


def export_review(chunks: list[dict], path: Path, sources: dict[str, dict] | None = None) -> Path | None:
    """검수표를 탭 구분 파일로 쓴다. 엑셀에서 열 수 있게 UTF-8 BOM을 붙인다.
    공고 원문이 들어 있어 .csv가 아닌 .tsv로 둔다 (data/ 안의 csv는 git에 올라가므로)."""
    rows = review_rows(chunks, sources)
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
