"""바이오마커 모듈 BM-2 ~ BM-4 (상태 판정, 검사 공백). ER, PR, HER2, Ki-67, 유전자 7개와 아형·치료 상황을 다룬다.

기준 문서
- PROJECT.md 5절 (판정 기준표, ER·PR·HER2 세부 판정 규칙, BM-3 출처, 검사 공백 규칙)
- A -> B 전달 문서(src/input/handoff_to_B.md) 3절(입력 형태), 4절(판정 조건),
  5절(BM-3 출처), 6.1절(현재 범주)
- schemas/biomarker_record.json 0.1-draft (출력 형태), schemas/README.md 4절

입력: patient_state 한 명 (A의 schemas/patient_state.json)
출력: biomarker_record (schema_version, patient_ref, records, subtype, setting, tests_needed)
진입점: assess(patient_state)

이 파일은 규칙만 쓴다. LLM은 쓰지 않는다.
재발 환자는 value(재생검 결과)로 판정하고, history[]의 원발 결과와 비교한 설명을 reason 끝에 붙인다.
유전자 변이(ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2)는 유전자마다 판정 방식이 다르다 (팀 회의 2026-10-20):
PTEN은 변이 유무, PIK3CA·AKT1·ESR1은 허가 변이 목록(actionable_variants.csv), BRCA1·BRCA2는 절단 변이 또는 ClinVar,
PALB2는 ClinVar. CIViC는 판정에 쓰지 않고 근거로만 이유에 적는다. 유전자 검사 공백(BM-4)은
미시행만 권고한다. 차수(setting.line)는 A가 넘긴 treatment_history[].line으로 채운다 (6.2절, draft6, 2026-10-19).
아직 다루지 않는 것: BM-1 보고서 파싱, 국소 재발 후 보조요법(SET-LOCAL-ADJ, 6.4절). VEP는 쓰지 않는다 (팀 회의 2026-10-20).
PD-L1은 약제별 기준(22C3 CPS ≥ 10, SP142 IC ≥ 1%)으로 판정한다 (6.5절, 2026-10-16)
"""

import csv
import re
from pathlib import Path

# ------------------------------------------------------------------ CONFIG
# 수치 기준 (종양내과/병리과 검토로 확정 예정. 바꿀 때는 A와 함께 바꾼다)
ER_NEGATIVE_BELOW = 1          # 이 값(%) 미만이면 음성
ER_LOW_MAX = 10                # NEGATIVE_BELOW 이상 ~ 이 값 이하이면 저발현(low)
# ER은 Allred 총점을 먼저 본다 (2026-10-15 변경): 0~2 음성, 3~4 저발현, 5는 비율로 가름, 6~8 양성
ER_ALLRED_TOTAL_NEG_MAX = 2    # 이하 음성
ER_ALLRED_TOTAL_LOW_MAX = 4    # NEG_MAX 초과 ~ 이 값 이하 저발현 (비율과 상관없음, 팀 결정)
ER_ALLRED_TOTAL_POS_MIN = 6    # 이상 양성 (LOW_MAX와 POS_MIN 사이인 5점은 비율로 가름)

# PR (팀 결정 2026-10-15): Allred 총점 -> range -> percent -> ps -> result 순서. low 상태값 없음
PR_ALLRED_TOTAL_NEG_MAX = 2    # 총점 이하 음성, 초과(3 이상) 양성
PR_POSITIVE_MIN = 9            # range 최대값·percent가 이 값(%) 이상이면 양성, 미만이면 음성 (2026-10-15: 10 -> 9)
# PR-low 태그는 쓰지 않는다 (ESMO에 PR-low 범주가 없음, 2026-10-15 결정)

# Ki-67: 이 값(%) 이상이면 positive(고증식) (팀 결정 2026-10-15)
KI67_HIGH_MIN = 20

# PD-L1 약제별 기준 (전달 문서 6.5절). 검사법과 점수 종류가 기준과 다르면 판정하지 않는다
PDL1_22C3_CPS_MIN = 10         # pembrolizumab + 항암 (TNBC 1차): 22C3 CPS 이 값 이상 양성 (공고책자 2026-11-01판 p.59)
PDL1_SP142_IC_MIN = 1          # atezolizumab + nab-paclitaxel: SP142 IC 이 값(%) 이상 양성 (ESMO MBC)

# 이전 약제 계열에서 뺄 계열 (차수에 들어가지 않는 약)
NON_ANTICANCER_CLASSES = {"Supportive Care", "Bone-modifying Agent", "Unknown", "Other"}
DRUG_CLASSES_CSV = Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "drug_classes.csv"
# -------------------------------------------------------------------------

VALID_MARKERS = {"ER", "PR", "HER2", "Ki-67", "gBRCA1", "gBRCA2", "PALB2", "sBRCA1",
                 "sBRCA2", "PIK3CA", "AKT1", "PTEN", "ESR1", "PD-L1"}
VALID_STATUS = {"positive", "negative", "low", "ultralow", "intermediate", "vus",
                "unknown", "not_done", "retest_needed", "not_recorded"}

_RESULT_TO_STATUS_ER = {"positive": "positive", "low_positive": "low", "negative": "negative"}
# PR에는 저발현 범주가 없어 low_positive가 적혀 있으면 positive로 본다 (팀 결정 2026-10-15)
_RESULT_TO_STATUS_PR = {"positive": "positive", "low_positive": "positive", "negative": "negative"}


# ---------------------------------------------------------------- 공통 도구
def _record(marker, status, reason, rule_id, field=None, evidence=None, tags=None):
    field = field or {}
    src = field.get("source") or {}
    ev = {"specimen": field.get("specimen")}
    # evidence.test_date는 날짜 형식만 받으므로 연·월만 있는 검사일은 넣지 않는다
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(field.get("observed_date") or "")):
        ev["test_date"] = field["observed_date"]
    ev.update(evidence or {})
    return {
        "marker": marker,
        "status": status,
        "reason": reason,
        "rule_id": rule_id,
        "evidence": ev,
        # 원문 근거가 없으면(기록 없음 등) 빈 문자열
        "source_span": {"doc_id": src.get("doc_id", ""), "quote": src.get("quote", "")},
        "rag_tags": list(tags or []),
    }


# 미시행 중 검사를 의뢰·예약한 경우 A가 raw에 넣는 고정 표기 (schema_fields.md 2절, draft6).
# 이때는 검사 권고 대신 "결과 확인"으로 낸다 (전달 문서 0절 5번, B 결정 2026-10-19)
PENDING_RAW = {"결과 대기": "PENDING", "예정": "SCHEDULED"}


def _gate(marker, field, rule_prefix):
    """칸이 없거나 미시행/기록 없음이면 바로 그 상태를 돌려준다. 값이 있으면 None."""
    if not field or field.get("status") in (None, "not_recorded"):
        return _record(marker, "not_recorded", f"{marker} 기록 없음", f"{rule_prefix}-NOTRECORDED", field)
    if field.get("status") == "not_done":
        note = f" ({field['raw']})" if field.get("raw") in PENDING_RAW else ""
        return _record(marker, "not_done", f"{marker} 미시행{note}", f"{rule_prefix}-NOTDONE", field)
    return None


def _mismatch_note(numeric_status, result, mapping):
    """수치로 정한 판정과 차트에 적힌 판정(result)이 다르면 설명 문장을 돌려준다."""
    if result in mapping and mapping[result] != numeric_status:
        return f" / 적힌 판정({result})과 수치 판정({numeric_status})이 달라 확인 필요"
    return ""


def _recurrence_old(field):
    """재발 재생검에 밀려난 원발 결과 칸. 없으면 None (전달 문서 3.5)."""
    for old in (field or {}).get("history") or []:
        if old.get("superseded_reason") == "recurrence":
            return old
    return None


def _change_note(before, now):
    """원발 판정과 재생검 판정을 비교한 설명 (전달 문서 4.5). 판정에는 쓰지 않는다."""
    if before == now:
        return f" / 원발 결과({before})에서 유지"
    return f" / 원발 {before}에서 {now}로 바뀜"


# ----------------------------------------------------------------------- ER
def _er_ratio(value):
    """비율(percent -> range -> allred.ps)로 판정. (status, rule_id, 설명) 또는 None."""
    pct = value.get("percent")
    if pct is not None:
        p = float(pct)
        if p < ER_NEGATIVE_BELOW:
            return "negative", "BM2-ER-PERCENT", f"ER {p:g}% (1% 미만)"
        if p <= ER_LOW_MAX:
            return "low", "BM2-ER-PERCENT", f"ER {p:g}% (1~10%, 저발현)"
        return "positive", "BM2-ER-PERCENT", f"ER {p:g}% (10% 초과)"

    rng = value.get("range")
    if rng:
        lo, hi = rng
        if lo == 0 and hi == 0:
            return "negative", "BM2-ER-RANGE", "ER 구간 [0,0] (1% 미만)"
        # 0부터 시작하는 구간은 최대값을 percent로 보고 판정 (팀 결정 2026-10-15). 단 최대값 1 이하는 음성
        if lo == 0:
            if hi <= ER_NEGATIVE_BELOW:
                return "negative", "BM2-ER-RANGE", f"ER 구간 [0,{hi}] (최대값 {hi}% 이하, 음성)"
            if hi <= ER_LOW_MAX:
                return "low", "BM2-ER-RANGE", f"ER 구간 [0,{hi}] (최대값 {hi}%로 판정, 1~10% 저발현)"
            return "positive", "BM2-ER-RANGE", f"ER 구간 [0,{hi}] (최대값 {hi}%로 판정, 10% 초과 양성)"
        if hi <= ER_LOW_MAX:
            return "low", "BM2-ER-RANGE", f"ER 구간 [{lo},{hi}] (1~10%, 저발현)"
        # 최소 >= 10 이거나 10%에 걸치는 구간 (전달 문서 4.1: 실무상 양성)
        return "positive", "BM2-ER-RANGE", f"ER 구간 [{lo},{hi}] (10%를 넘거나 걸치는 구간은 양성)"

    ps = (value.get("allred") or {}).get("ps")
    if ps is not None:
        if ps <= 1:
            return "negative", "BM2-ER-ALLRED-PS", f"Allred 비율 점수 PS {ps} (1% 미만)"
        if ps == 2:
            return "low", "BM2-ER-ALLRED-PS", "Allred 비율 점수 PS 2 (1~10%, 저발현)"
        return "positive", "BM2-ER-ALLRED-PS", f"Allred 비율 점수 PS {ps} (11% 이상)"
    return None


def _er_numeric(value):
    """(status, rule_id, 설명) 또는 None. Allred 총점 -> 비율 -> result 순서.
    Allred 총점 = ps(비율 점수) + is(강도 점수)라서 비율만 잰 percent·range·ps보다 총점을 먼저 본다.
    총점과 비율이 달라도 총점을 따른다. ER·PR에는 score 키가 없다 (강도는 allred.is, 2026-10-15)."""
    total = (value.get("allred") or {}).get("total")
    if total is not None:
        if total <= ER_ALLRED_TOTAL_NEG_MAX:
            return "negative", "BM2-ER-ALLRED-TOTAL", f"Allred 총점 {total} (0~2, 음성)"
        if total <= ER_ALLRED_TOTAL_LOW_MAX:
            return "low", "BM2-ER-ALLRED-TOTAL", f"Allred 총점 {total} (3~4, 저발현)"
        if total >= ER_ALLRED_TOTAL_POS_MIN:
            return "positive", "BM2-ER-ALLRED-TOTAL", f"Allred 총점 {total} (6~8, 양성)"
        ratio = _er_ratio(value)
        if ratio is None:
            return ("unknown", "BM2-ER-ALLRED-5",
                    f"Allred 총점 {total}이고 비율이 없어 저발현/양성을 가를 수 없음. 비율(PS) 확인 권고")
        status, _, why = ratio
        return status, "BM2-ER-ALLRED-5", f"Allred 총점 {total}, 비율로 판정: {why}"

    ratio = _er_ratio(value)
    if ratio is not None:
        return ratio

    res = value.get("result")
    if res in _RESULT_TO_STATUS_ER:
        return _RESULT_TO_STATUS_ER[res], "BM2-ER-RESULT", f"적힌 판정만 있음({res})"
    return None


def judge_er(field):
    """ER. 0단계: 칸의 status만 본다 (present가 아니면 not_done / not_recorded).
    재발 환자는 value(가장 최근 재생검 결과)로 판정하고, history[]의 원발 결과는 설명에만 쓴다."""
    gate = _gate("ER", field, "BM2-ER")
    if gate:
        return gate
    value = field.get("value") or {}
    numeric = _er_numeric(value)
    if numeric is None:
        what = f"적힌 판정이 {value['result']}" if value.get("result") else "쓸 수 있는 값 없음"
        return _record("ER", "unknown", f"ER 판정 불가 ({what}). percent·range·Allred가 없음",
                       "BM2-ER-UNKNOWN", field)
    status, rule_id, reason = numeric
    if rule_id not in ("BM2-ER-RESULT",):
        reason += _mismatch_note(status, value.get("result"), _RESULT_TO_STATUS_ER)
    old = _recurrence_old(field)
    if old:
        reason = f"재생검({field.get('specimen') or '검체 모름'}) 결과로 판정: {reason}"
        reason += _change_note(judge_er(old)["status"], status)
    tags = ["ER-low"] if status == "low" else []
    ev = {}
    if value.get("percent") is not None:
        ev["percent"] = float(value["percent"])
    return _record("ER", status, reason, rule_id, field, ev, tags)


# ----------------------------------------------------------------------- PR
def _pr_numeric(value):
    """(status, rule_id, 설명) 또는 None. 순서 (팀 결정 2026-10-15):
    1 Allred 총점 -> 2 range -> 3 percent -> 4 allred.ps -> 5 result. 처음 맞는 값으로 판정한다."""
    total = (value.get("allred") or {}).get("total")
    if total is not None:
        if total <= PR_ALLRED_TOTAL_NEG_MAX:
            return "negative", "BM2-PR-ALLRED-TOTAL", f"Allred 총점 {total} (0~2, 음성)"
        return "positive", "BM2-PR-ALLRED-TOTAL", f"Allred 총점 {total} (3 이상, 양성)"

    rng = value.get("range")
    if rng:
        lo, hi = rng
        if lo == 0 and hi == 0:
            return "negative", "BM2-PR-RANGE", "PR 구간 [0,0] (음성)"
        if hi >= PR_POSITIVE_MIN:
            return "positive", "BM2-PR-RANGE", f"PR 구간 [{lo},{hi}] (최대값 {PR_POSITIVE_MIN}% 이상, 양성)"
        return "negative", "BM2-PR-RANGE", f"PR 구간 [{lo},{hi}] (최대값 {PR_POSITIVE_MIN}% 미만, 음성)"

    pct = value.get("percent")
    if pct is not None:
        p = float(pct)
        if p >= PR_POSITIVE_MIN:
            return "positive", "BM2-PR-PERCENT", f"PR {p:g}% ({PR_POSITIVE_MIN}% 이상, 양성)"
        return "negative", "BM2-PR-PERCENT", f"PR {p:g}% ({PR_POSITIVE_MIN}% 미만, 음성)"

    ps = (value.get("allred") or {}).get("ps")
    if ps is not None:
        if ps <= 1:
            return "negative", "BM2-PR-ALLRED-PS", f"Allred 비율 점수 PS {ps} (1% 미만)"
        return "positive", "BM2-PR-ALLRED-PS", f"Allred 비율 점수 PS {ps} (1% 이상)"

    res = value.get("result")
    if res in _RESULT_TO_STATUS_PR:
        return _RESULT_TO_STATUS_PR[res], "BM2-PR-RESULT", f"적힌 판정만 있음({res})"
    return None


def judge_pr(field):
    gate = _gate("PR", field, "BM2-PR")
    if gate:
        return gate
    value = field.get("value") or {}
    numeric = _pr_numeric(value)
    if numeric is None:
        what = f"적힌 판정이 {value['result']}" if value.get("result") else "쓸 수 있는 값 없음"
        return _record("PR", "unknown", f"PR 판정 불가 ({what}). Allred·range·percent가 없음",
                       "BM2-PR-UNKNOWN", field)
    status, rule_id, reason = numeric
    if rule_id not in ("BM2-PR-RESULT",):
        reason += _mismatch_note(status, value.get("result"), _RESULT_TO_STATUS_PR)
    old = _recurrence_old(field)
    if old:
        reason += _change_note(judge_pr(old)["status"], status)
    ev = {}
    if value.get("percent") is not None:
        ev["percent"] = float(value["percent"])
    return _record("PR", status, reason, rule_id, field, ev)


# --------------------------------------------------------------------- HER2
# HER2 판정 규칙 (팀 결정 2026-10-15). 상태값: positive / low / ultralow / negative / unknown / not_done / not_recorded.
# zero는 쓰지 않는다 (IHC 0은 negative). ISH는 FISH 또는 SISH 결과다.


def _rebiopsy_first(field):
    """재생검(전이 병소) 결과가 있으면 그 칸을, 없으면 기존 칸을 쓴다.
    A는 재생검 결과를 value에, 원발 결과를 history[]에 넣지만 (전달 문서 3.5절)
    value가 원발이고 history[]에 재생검 결과가 있으면 재생검 결과를 고른다."""
    field = field or {}
    if field.get("specimen") == "metastasis":
        return field
    for old in field.get("history") or []:
        if old.get("specimen") == "metastasis" and old.get("status") == "present":
            return old
    return field


def judge_her2(ihc_field, ish_field):
    """HER2. 재생검 결과가 있으면 그 점수로, 없으면 기존 점수로 같은 규칙을 적용한다."""
    ihc_field, ish_field = _rebiopsy_first(ihc_field), _rebiopsy_first(ish_field)
    out = _judge_her2_now(ihc_field, ish_field)
    if "metastasis" in ((ihc_field or {}).get("specimen"), (ish_field or {}).get("specimen")):
        out["reason"] = f"재생검 결과로 판정: {out['reason']}"
    return out


def _judge_her2_now(ihc_field, ish_field):
    """IHC 점수(score)를 먼저 읽는다 (result는 A가 ISH로 보정한 값이라 score가 우선).
    1 IHC 3+ -> 2 IHC 2+ (ISH로 가름) -> 3 IHC 1+ -> 4 IHC 0 -> 5 점수 없음."""
    ihc_state = (ihc_field or {}).get("status") or "not_recorded"
    ish_state = (ish_field or {}).get("status") or "not_recorded"
    ihc = (ihc_field or {}).get("value") or {} if ihc_state == "present" else {}
    ish = (ish_field or {}).get("value") or {} if ish_state == "present" else {}

    score, faint, ihc_result = ihc.get("score"), ihc.get("faint"), ihc.get("result")
    ish_result = ish.get("result")
    field = ihc_field if ihc_state == "present" else ish_field

    def rec(status, reason, rule_id):
        return _record("HER2", status, reason, rule_id, field)

    if score is not None and score not in {"0", "1+", "2+", "3+"}:
        return rec("unknown", f"인식할 수 없는 IHC 점수: {score}", "BM2-HER2-BADSCORE")

    # 1단계: IHC 3+는 무조건 양성
    if score == "3+":
        return rec("positive", "IHC 3+ -> 양성", "BM2-HER2-IHC3")

    # 2단계: IHC 2+는 ISH(FISH·SISH)로 가름
    if score == "2+":
        if ish_result == "amplified":
            return rec("positive", "IHC 2+, ISH 증폭 -> 양성", "BM2-HER2-2PLUS-AMP")
        if ish_result == "not_amplified":
            return rec("low", "IHC 2+, ISH 비증폭 -> 저발현", "BM2-HER2-2PLUS-NOTAMP")
        ish_text = {"not_done": "미시행", "not_recorded": "기록 없음"}.get(ish_state, ish_result or "결과 없음")
        # ISH 결과가 없으면(미시행·기록 없음) 적힌 판정을 따른다 (팀 결정 2026-10-15)
        if ish_state != "present":
            if ihc_result == "positive":
                return rec("positive", f"IHC 2+, ISH {ish_text}, 적힌 판정 positive -> 양성. ISH 검사 권고",
                           "BM2-HER2-2PLUS-RESULT-POS")
            if ihc_result == "negative":
                return rec("negative", f"IHC 2+, ISH {ish_text}, 적힌 판정 negative -> 음성",
                           "BM2-HER2-2PLUS-RESULT-NEG")
        # 그 밖(ISH equivocal, 또는 ISH 없이 판정이 positive·negative가 아님): 판정 불가.
        # TCGA 정답에서는 크롭 단계에서 삭제 (2026-10-15)
        return rec("unknown", f"IHC 2+ 인데 ISH {ish_text}, 적힌 판정 {ihc_result or '없음'}. 판정 불가, ISH 검사 권고",
                   "BM2-HER2-2PLUS-NOISH")

    # 3단계: IHC 1+는 ISH와 상관없이 저발현
    if score == "1+":
        return rec("low", "IHC 1+ -> 저발현 (ISH와 무관)", "BM2-HER2-IHC1")

    # 4단계: IHC 0은 음성. 10% 미만 세포의 미약한 막 염색(faint: true)이면 초저발현 (심평원 기준 최종 음성)
    if score == "0":
        if ish_result == "amplified":
            # IHC 0과 ISH 증폭은 함께 나오기 어려워 입력 오류로 본다 (팀 결정 2026-10-15). TCGA에는 없음
            return rec("unknown", "IHC 0 인데 ISH 증폭: 데이터 오류 가능성. 원자료 확인 필요", "BM2-HER2-IHC0-AMP")
        if faint is True:
            return rec("ultralow", "IHC 0, 미약한 막 염색(10% 미만 세포) 있음 -> 초저발현 (심평원 기준 최종 음성)",
                       "BM2-HER2-IHC0-FAINT")
        why = "미약한 막 염색 없음" if faint is False else "미약한 막 염색 기록 없음"
        return rec("negative", f"IHC 0, {why} -> 음성", "BM2-HER2-IHC0")

    # 5단계: IHC 점수가 없음
    if ish_result == "amplified":
        return rec("positive", "IHC 점수 없음, ISH 증폭 -> 양성", "BM2-HER2-ISHAMP")
    if ihc_result == "positive":
        return rec("positive", "IHC 점수 없음, 적힌 판정 positive -> 양성", "BM2-HER2-RESULT-POS")
    if ihc_result == "negative":
        return rec("negative", "IHC 점수 없음, 적힌 판정 negative -> 음성 (0과 저발현은 구분 못 함)", "BM2-HER2-RESULT-NEG")
    if ish_result == "not_amplified":
        return rec("negative", "IHC 점수 없음, ISH 비증폭 -> 음성 (0과 저발현은 구분 못 함)", "BM2-HER2-ISH-NOTAMP")
    # 아래 5~8은 판정할 HER2 값이 없는 경우. TCGA 정답에서는 크롭 단계에서 삭제했다 (2026-10-15)
    if ihc_result in ("equivocal", "indeterminate", "unknown"):
        return rec("unknown", f"IHC 점수 없이 적힌 판정만 {ihc_result}", "BM2-HER2-RESULT-UNKNOWN")
    if ihc_state == "not_done" and ish_state != "present":
        return _record("HER2", "not_done", "HER2 미시행", "BM2-HER2-NOTDONE", field)
    if ihc_state != "present" and ish_state != "present":
        return _record("HER2", "not_recorded", "HER2 기록 없음", "BM2-HER2-NOTRECORDED", field)
    return rec("unknown", "HER2 판정에 쓸 수 있는 값이 없음", "BM2-HER2-UNKNOWN")


# -------------------------------------------------------------------- Ki-67
def judge_ki67(field):
    """Ki-67. percent -> range -> result 순서. KI67_HIGH_MIN 이상이면 positive(고증식), 미만이면 negative,
    구간이 기준에 걸치거나 적힌 판정이 intermediate면 intermediate, 쓸 값이 없으면 unknown (2026-10-15).
    기준값 20%는 2026-10-15 확정."""
    gate = _gate("Ki-67", field, "BM2-KI67")
    if gate:
        return gate
    value = field.get("value") or {}
    cut = KI67_HIGH_MIN

    def rec(status, reason, rule_id, percent=None):
        tags = ["Ki-67-high"] if status == "positive" else []
        ev = {"percent": percent} if percent is not None else {}
        return _record("Ki-67", status, reason, rule_id, field, ev, tags)

    if value.get("percent") is not None:
        p = float(value["percent"])
        if p >= cut:
            return rec("positive", f"Ki-67 {p:g}% ({cut}% 이상, 고증식)", "BM2-KI67-PERCENT", p)
        return rec("negative", f"Ki-67 {p:g}% ({cut}% 미만)", "BM2-KI67-PERCENT", p)
    if value.get("range"):
        lo, hi = value["range"]
        if lo >= cut:
            return rec("positive", f"Ki-67 구간 [{lo},{hi}] ({cut}% 이상, 고증식)", "BM2-KI67-RANGE")
        if hi < cut:
            return rec("negative", f"Ki-67 구간 [{lo},{hi}] ({cut}% 미만)", "BM2-KI67-RANGE")
        return rec("intermediate", f"Ki-67 구간 [{lo},{hi}]가 기준 {cut}%에 걸침 -> 중간", "BM2-KI67-RANGE")
    result = value.get("result")
    if result == "high":
        return rec("positive", "적힌 판정만 있음(high)", "BM2-KI67-RESULT")
    if result == "low":
        return rec("negative", "적힌 판정만 있음(low)", "BM2-KI67-RESULT")
    if result == "intermediate":
        return rec("intermediate", "적힌 판정만 있음(intermediate)", "BM2-KI67-RESULT")
    return rec("unknown", "Ki-67 판정에 쓸 수 있는 값이 없음", "BM2-KI67-UNKNOWN")


# --------------------------------------------------------------------- 아형
# ER 저발현을 HR+로 볼지 팀 결정 전 (전달 문서 10절). 지금은 HR+로 본다
ER_LOW_IS_HR_POSITIVE = True


def subtype_of(er, pr, her2):
    """ER·PR·HER2 상태값 -> 아형. HR+ = ER 또는 PR 양성. 아형에는 HER2 양성/음성만 필요하다."""
    er_pos = er == "positive" or (er == "low" and ER_LOW_IS_HR_POSITIVE)
    hr_pos = er_pos or pr == "positive"
    er_neg = er == "negative" or (er == "low" and not ER_LOW_IS_HR_POSITIVE)
    hr_neg = er_neg and pr == "negative"
    her2_pos = her2 == "positive"
    her2_neg = her2 in ("low", "ultralow", "negative")  # 초저발현은 심평원 기준 최종 음성
    if hr_pos and her2_neg:
        return "HR+/HER2-"
    if hr_pos and her2_pos:
        return "HR+/HER2+"
    if hr_neg and her2_pos:
        return "HR-/HER2+"
    if hr_neg and her2_neg:
        return "TNBC"
    return "unknown"  # ER·PR·HER2 중 판정이 없어 아형을 정할 수 없음 (indeterminate는 쓰지 않음, 2026-10-15)


# 분자 아형 (팀 결정 2026-10-15). 쓸 곳이 정해지지 않아 출력(biomarker_record)에는 아직 넣지 않는다
MOLECULAR_SUBTYPES = ("Luminal A", "Luminal B(HER2 negative)", "Luminal B(HER2 positive)",
                      "HER2_enriched", "Basal_like", "unknown")


def molecular_subtype_of(subtype, ki67):
    """아형(subtype_of 결과)과 Ki-67 상태값 -> 분자 아형.
    HR+/HER2-는 Ki-67로 가른다: low(negative) -> Luminal A, high(positive)·intermediate -> Luminal B(HER2 negative).
    Ki-67이 없으면(unknown·미시행·기록 없음) 정할 수 없다. 나머지 아형은 Ki-67과 관계없다."""
    if subtype == "HR+/HER2+":
        return "Luminal B(HER2 positive)"
    if subtype == "HR-/HER2+":
        return "HER2_enriched"
    if subtype == "TNBC":
        return "Basal_like"
    if subtype == "HR+/HER2-":
        if ki67 == "negative":
            return "Luminal A"
        if ki67 in ("positive", "intermediate"):  # intermediate는 high로 본다
            return "Luminal B(HER2 negative)"
    return "unknown"


# ------------------------------------------------------------------- PD-L1
# (검사법, 점수 종류) -> (양성 최소값, 약, 근거, 태그). 전달 문서 6.5절, PROJECT.md 5절.
# 태그는 C의 표준 태그 PD-L1+ (rag_guideline_chunking_design_update.md 3.5절)
PDL1_RULES = {
    ("22C3", "CPS"): (PDL1_22C3_CPS_MIN, "pembrolizumab", "심평원 공고책자 2026-11-01판 p.59 (hira-booklet-20261101-bc-pal-chemo-1l-r06·r07)",
                       "PD-L1+"),
    ("SP142", "IC"): (PDL1_SP142_IC_MIN, "atezolizumab", "ESMO MBC", "PD-L1+"),
}


def judge_pdl1(field):
    """PD-L1 발현 점수. 검사법·점수 종류에 맞는 약제 기준으로만 판정하고, 맞는 기준이 없으면 unknown."""
    gate = _gate("PD-L1", field, "BM2-PDL1")
    if gate:
        return gate
    value = field.get("value") or {}
    assay, score_type, score = value.get("assay"), value.get("score_type"), value.get("score")
    evidence = {"assay": assay, "score": score}
    rule = PDL1_RULES.get((assay, score_type))
    if rule is None:
        return _record("PD-L1", "unknown",
                       f"PD-L1 {assay} {score_type} {score}: 검사법·점수 종류가 약제 기준(22C3 CPS, SP142 IC)과 "
                       "달라 판정에 쓰지 않음", "BM2-PDL1-ASSAY", field, evidence)
    cutoff, drug, source, tag = rule
    if score is None:
        return _record("PD-L1", "unknown", f"PD-L1 {assay} {score_type} 점수 없음",
                       f"BM2-PDL1-{assay}-NOSCORE", field, evidence)
    if score >= cutoff:
        return _record("PD-L1", "positive", f"PD-L1 {assay} {score_type} {score} ≥ {cutoff} → {drug} 기준 양성 ({source})",
                       f"BM2-PDL1-{assay}", field, evidence, [tag])
    return _record("PD-L1", "negative", f"PD-L1 {assay} {score_type} {score} < {cutoff} → {drug} 기준 음성 ({source})",
                   f"BM2-PDL1-{assay}", field, evidence)


# ------------------------------------------------------------ 유전자 변이
# 전달 문서 3.6절(입력), 4.6절(ESR1 재검), 4.7절(BRCA), 5.4절(판정 순서), 팀 회의 2026-10-20.
# 판정과 근거를 나눈다: 판정은 아래 규칙으로만 하고, 허가 목록·ClinVar·CIViC·급여·지침 근거는 모두 이유에 적는다.
GENES = ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")
# 허가 동반진단 변이 목록이 있는 유전자 (actionable_variants.csv)
LABEL_GENES = {"PIK3CA", "AKT1", "ESR1"}
# 변이 유무로 판정하는 유전자 (팀 회의 2026-10-20: PTEN은 positive/negative로 통일, VEP 안 씀).
# 단백질이 바뀌는 변이가 하나라도 있으면 양성
PRESENCE_GENES = {"PTEN"}
# 단백질 서열이 바뀌지 않는 변이 종류 (MAF 변이 종류 칸). 이것만 있으면 변이 없음으로 본다
NON_PROTEIN_TYPES = {"Silent", "Splice_Region", "Intron", "3'UTR", "5'UTR", "3'Flank", "5'Flank", "IGR", "RNA"}
# 절단 변이(nonsense, frameshift, 필수 스플라이스 부위)를 양성으로 보는 유전자. BRCA1/2는 4.7절
# (TCGA: ClinVar 병원성 또는 절단 변이). PALB2는 5.4절에 ClinVar 기준만 있어 넣지 않는다
TRUNCATING_GENES = {"BRCA1", "BRCA2"}
TRUNCATING_TYPES = {"Nonsense_Mutation", "Frame_Shift_Del", "Frame_Shift_Ins", "Splice_Site"}
ACTIONABLE_CSV = Path(__file__).resolve().parent / "actionable_variants.csv"
# rag_tags는 청크 biomarker_tags와 같은 어휘 (src/rag/rag_guideline_chunking_design_update.md 3.5절 표준 태그)
GENE_TAGS = {"PIK3CA": "PIK3CA-mut", "AKT1": "AKT1-mut", "PTEN": "PTEN-alt", "ESR1": "ESR1-mut",
             "PALB2": "gPALB2", "gBRCA1": "gBRCA", "gBRCA2": "gBRCA", "sBRCA1": "sBRCA", "sBRCA2": "sBRCA"}

# 근거 표시용 출처 (팀 회의 2026-10-20 5번). 판정에는 쓰지 않는다. 문서 문장은 옮기지 않고 문서·쪽만 적는다.
# 급여: D의 공고책자 2026-11-01판(제2026-232호) 인쇄 쪽과 D의 chunk_id (D 확인 2026-10-21, 11-01판 쪽·ID D 확인 2026-10-29). 공고 문구와 공고 내용 해석은
# 옮기지 않는다 (급여 판정은 D의 청크로 한다). 여기 없는 마커는 B가 연결한 행이 없다는 뜻이다
_HIRA = "심평원 공고책자 2026-11-01판"
REIMBURSEMENT_BASIS = {
    "PIK3CA": f"{_HIRA} p.167·170 (병용 연번 22 capivasertib, 23 alpelisib, 30 inavolisib; "
              f"hira-booklet-20261101-combo-r22·r23·r30)",
    "AKT1": f"{_HIRA} p.167 (병용 연번 22 capivasertib; hira-booklet-20261101-combo-r22)",
    "PTEN": f"{_HIRA} p.167 (병용 연번 22 capivasertib; hira-booklet-20261101-combo-r22)",
    "gBRCA1": f"{_HIRA} p.171–173 (병용 연번 31 olaparib; hira-booklet-20261101-combo-r31)",
    "gBRCA2": f"{_HIRA} p.171–173 (병용 연번 31 olaparib; hira-booklet-20261101-combo-r31)",
}
# 지침: data/chunks/esmo_chunks.json의 ESMO 권고 쪽 번호
GUIDELINE_BASIS = {
    "PIK3CA": "ESMO MBC 2026 p.1205 (capivasertib)",
    "AKT1": "ESMO MBC 2026 p.1205 (capivasertib)",
    "PTEN": "ESMO MBC 2026 p.1205 (capivasertib)",
    "ESR1": "ESMO MBC 2026 p.1206 (elacestrant·imlunestrant)",
    "gBRCA1": "ESMO EBC 2024 p.172–173, ESMO MBC 2026 p.1206·1212 (PARP 억제제)",
    "gBRCA2": "ESMO EBC 2024 p.172–173, ESMO MBC 2026 p.1206·1212 (PARP 억제제)",
    "PALB2": "ESMO MBC 2026 p.1206·1212 (PARP 억제제)",
}


def _actionable():
    """{유전자: {단백질 변화: 행}} (actionable_variants.csv)."""
    if not hasattr(_actionable, "cache"):
        table = {}
        with open(ACTIONABLE_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                table.setdefault(r["gene"], {})[r["protein_change"]] = r
        _actionable.cache = table
    return _actionable.cache


# BM-3 ClinVar (전달 문서 5.4절). data/script/clinvar_download.py가 만든 표를 로컬에서만 조회한다
# git에 올리지 않는 파일 (전달 문서 5.6절). 없으면 ClinVar 조회 없이 VUS로 남는다
CLINVAR_CSV = Path(__file__).resolve().parents[2] / "data" / "clinvar" / "clinvar_bm3_genes.tsv"
CLINVAR_GENES = {"BRCA1", "BRCA2", "PALB2", "PTEN"}
# 양성으로 볼 최소 리뷰 등급(별). gBRCA·PALB2는 2성 이상 (PROJECT.md 5절, 전달 문서 5.4절).
# PTEN은 변이 유무로 판정하고 ClinVar는 근거로만 적는다 (팀 회의 2026-10-20). 등급 조건은 문서에 없다
CLINVAR_MIN_STARS = {"BRCA1": 2, "BRCA2": 2, "PALB2": 2, "PTEN": 0}
# ClinVar로 판정하는 유전자
CLINVAR_JUDGE_GENES = {"BRCA1", "BRCA2", "PALB2"}
CLINVAR_PATHOGENIC = {"Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"}


def _clinvar():
    """{(유전자, 단백질 변화): [행, ...]}. 파일이 없으면 빈 표 (ClinVar 조회 없이 VUS로 남는다)."""
    if not hasattr(_clinvar, "cache"):
        table = {}
        if CLINVAR_CSV.exists():
            with open(CLINVAR_CSV, encoding="utf-8") as fh:
                for r in csv.DictReader(fh, delimiter="\t"):
                    r["stars"] = int(r["stars"])
                    table.setdefault((r["gene"], r["protein_change"]), []).append(r)
        _clinvar.cache = table
    return _clinvar.cache


def _clinvar_best(gene, variants):
    """검출 변이 중 ClinVar 근거가 가장 강한 (변이, 행)과 양성 여부. ClinVar에 없으면 (None, None, False)."""
    best = None
    for v in variants:
        for r in _clinvar().get((gene, v.get("protein_change")), []):
            ok = (r["clinical_significance"].split(";")[0] in CLINVAR_PATHOGENIC
                  and r["stars"] >= CLINVAR_MIN_STARS[gene])
            key = (ok, r["stars"])
            if best is None or key > best[0]:
                best = (key, v, r)
    if best is None:
        return None, None, False
    return best[1], best[2], best[0][0]


# BM-3 CIViC (전달 문서 5.4절). data/script/civic_download.py가 만든 표를 로컬에서만 조회한다.
# 표에는 변이 하나를 지목한 발암성·예측(Sensitivity/Response) 근거만 들어 있다
# 파일명에 받은 날짜가 붙는다 (전달 문서 5.6절). 가장 최근 파일을 쓴다.
# 판정에는 쓰지 않고 근거로만 이유에 적는다 (팀 회의 2026-10-20: 약이 듣는지는 판정하지 않는다)
CIVIC_DIR = Path(__file__).resolve().parents[2] / "data" / "civic"
CIVIC_CSV = max(CIVIC_DIR.glob("civic_bm3_evidence_*.csv"), default=CIVIC_DIR / "civic_bm3_evidence_없음.csv")
CIVIC_GENES = {"PIK3CA", "AKT1", "PTEN"}


def _civic():
    """{(유전자, 단백질 변화): [행, ...]}. 파일이 없으면 빈 표."""
    if not hasattr(_civic, "cache"):
        table = {}
        if CIVIC_CSV.exists():
            with open(CIVIC_CSV, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    table.setdefault((r["gene"], r["protein_change"]), []).append(r)
        _civic.cache = table
    return _civic.cache


def _civic_best(gene, variants):
    """검출 변이 중 CIViC 근거 등급이 가장 높은 (변이, 행). 등급이 같으면 유방암 근거를 먼저. 없으면 (None, None)."""
    best = None
    for v in variants:
        for r in _civic().get((gene, v.get("protein_change")), []):
            key = (r["evidence_level"], "breast" not in r["disease"].lower())
            if best is None or key < best[0]:
                best = (key, v, r)
    return (best[1], best[2]) if best else (None, None)


def _civic_text(row):
    therapy = f", {row['therapies']}" if row["therapies"] else ""
    return (f"CIViC 근거 등급 {row['evidence_level']} ({row['evidence_type']} {row['significance']}, "
            f"{row['disease']}{therapy}, EID{row['evidence_id']})")


def _clinvar_text(row):
    return f"{row['clinical_significance']} ({row['stars']}성, VCV{row['variation_id']})"


def _is_truncating(variant):
    """전달 문서 5.4절의 절단형 (nonsense, frameshift, 필수 스플라이스 부위). 변이 종류 칸으로만 판단한다."""
    return variant.get("variant_type") in TRUNCATING_TYPES


def _gene_marker(gene, patient_ref):
    """BRCA1/2 레코드 이름. TCGA·가상·실제 차트 모두 검사 종류와 관계없이 gBRCA로 본다 (전달 문서 4.7절,
    A 결정 2026-10-21). sBRCA1/2 이름은 VALID_MARKERS에 남지만 레코드를 만들지 않는다."""
    if gene in ("BRCA1", "BRCA2"):
        return "g" + gene
    return gene


def _variant_text(variants):
    """변이 이름·종류·VAF. 예: R130* (Nonsense_Mutation, 절단형, VAF 0.056)"""
    parts = []
    for v in variants:
        detail = [v["variant_type"]] if v.get("variant_type") else []
        if _is_truncating(v):
            detail.append("절단형")
        if v.get("vaf") is not None:
            detail.append(f"VAF {v['vaf']:g}")
        name = v.get("protein_change") or v.get("raw") or "?"
        parts.append(f"{name} ({', '.join(detail)})" if detail else name)
    return ", ".join(parts)


def _evidence_notes(gene, marker, variants, cv_row):
    """판정에 쓰지 않은 것까지 모든 근거를 한 줄로 (팀 회의 2026-10-20 5번). 스키마에 칸이 없는 근거는 이유 글에만 적는다."""
    notes = []
    if gene in LABEL_GENES:
        table = _actionable().get(gene, {})
        on = [v["protein_change"] for v in variants if v.get("protein_change") in table]
        notes.append(f"허가 동반진단 목록: {', '.join(on)} 해당" if on else "허가 동반진단 목록: 해당 없음")
    if gene == "ESR1":
        inside = _esr1_fda_missense(variants)
        notes.append(f"FDA 동반진단 범위(codon 310~547 미스센스): {inside['protein_change']} 해당" if inside
                     else "FDA 동반진단 범위(codon 310~547 미스센스): 해당 없음")
    if gene in CLINVAR_GENES:
        if not CLINVAR_CSV.exists():
            notes.append("ClinVar 파일 없음 (data/script/clinvar_download.py 실행 필요)")
        else:
            notes.append(f"ClinVar {_clinvar_text(cv_row)}, 파일 {CLINVAR_CSV.name}" if cv_row else "ClinVar에 없음")
    if gene in CIVIC_GENES:
        if not CIVIC_CSV.exists():
            notes.append("CIViC 파일 없음 (data/script/civic_download.py 실행 필요)")
        else:
            _, civic_row = _civic_best(gene, variants)
            notes.append(f"{_civic_text(civic_row)}, 파일 {CIVIC_CSV.name}, 판정에 쓰지 않음" if civic_row
                         else "CIViC 근거 없음")
    notes.append(f"급여: {REIMBURSEMENT_BASIS.get(marker, 'B가 연결한 심평원 행 없음 (D 확인 전)')}")
    if marker in GUIDELINE_BASIS:
        notes.append(f"지침: {GUIDELINE_BASIS[marker]}")
    return " / 근거: " + "; ".join(notes)


# ESR1: FDA 동반진단 목록의 elacestrant 범위 (codon 310~547 미스센스). 국내 허가·급여 기준이 없어 FDA를 따른다
# (A 확인 2026-10-22: 식약처가 범위를 정하지 않으면 FDA 범위. 범위 안 미스센스는 VUS 여부와 관계없이 대상)
ESR1_FDA_CODONS = (310, 547)
ESR1_FDA_SOURCE = "판단 기준: FDA 동반진단 목록 elacestrant (codon 310~547 미스센스), 국내 미허가, 2026-10-22 확인"
# capivasertib·inavolisib: FDA는 "FDA 승인 검사로 검출된 변이"라고만 쓴다. VUS 포함 여부는 FDA 작성 자료로 확인할 수 없어
# VUS는 음성 처리를 유지하고 이유에 적는다 (A 확인 2026-10-22). alpelisib은 FDA 목록의 PIK3CA 11개
FDA_VUS_NOTE = {
    "PIK3CA": "capivasertib·inavolisib는 FDA 승인 검사로 검출된 PIK3CA 변이가 대상이나 VUS 포함 여부는 FDA 작성 자료로 확인 불가",
    "AKT1": "capivasertib는 FDA 승인 검사로 검출된 AKT1 변화가 대상이나 VUS 포함 여부는 FDA 작성 자료로 확인 불가",
}
_MISSENSE_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")


def _esr1_fda_missense(variants):
    """ESR1 변이 중 codon 310~547 미스센스(아미노산 하나가 다른 아미노산으로)인 첫 변이."""
    lo, hi = ESR1_FDA_CODONS
    for v in variants:
        m = _MISSENSE_RE.match(v.get("protein_change") or "")
        if m and m.group(1) != m.group(3) and lo <= int(m.group(2)) <= hi:
            return v
    return None


def judge_gene(gene, field, patient_ref=""):
    """유전자 한 개 -> biomarker_record 레코드. 위에서부터 처음 맞는 규칙으로 판정한다."""
    marker = _gene_marker(gene, patient_ref)
    gate = _gate(marker, field, f"BM2-{gene}")
    if gate:
        return gate
    if field.get("result") == "not_detected":
        return _record(marker, "negative", f"{gene} 변이 없음", f"BM2-{gene}-NOTDETECTED", field)

    variants = field.get("variants") or []
    if field.get("result") != "detected" or not variants:
        return _record(marker, "unknown", f"{gene} 결과를 읽을 수 없음 (result={field.get('result')})",
                       f"BM2-{gene}-UNKNOWN", field)

    cv_variant, cv_row, cv_ok = None, None, False
    if gene in CLINVAR_GENES:
        cv_variant, cv_row, cv_ok = _clinvar_best(gene, variants)
    notes = _evidence_notes(gene, marker, variants, cv_row)

    hit, rule_id, why = None, None, ""
    if gene in PRESENCE_GENES:
        protein = [v for v in variants if v.get("variant_type") not in NON_PROTEIN_TYPES]
        if not protein:
            return _record(marker, "negative", f"{gene} {_variant_text(variants)} → 단백질이 바뀌는 변이 없음"
                           f"{notes}", f"BM2-{gene}-NONPROTEIN", field)
        hit, rule_id, why = protein[0], f"BM2-{gene}-PRESENT", "단백질이 바뀌는 변이 있음"
    if gene in LABEL_GENES:
        table = _actionable().get(gene, {})
        hit = next((v for v in variants if v.get("protein_change") in table), None)
        if hit:
            row = table[hit["protein_change"]]
            rule_id = f"BM2-{gene}-LABEL"
            why = f"{row['drug']} 허가 동반진단 변이 ({row['source']})"
            if row["verified"] != "yes":
                why += ", 변이 목록 원문 확인 필요"
    if gene == "ESR1" and not hit:
        hit = _esr1_fda_missense(variants)
        if hit:
            rule_id, why = "BM2-ESR1-FDA-RANGE", f"elacestrant 대상 ESR1 미스센스 ({ESR1_FDA_SOURCE})"
    if gene in TRUNCATING_GENES:
        hit = next((v for v in variants if _is_truncating(v)), None)
        if hit:
            rule_id, why = f"BM2-{gene}-TRUNC", "절단 변이 (기능 소실)"
    # BM-3: 절단 변이가 아니면 ClinVar 병원성·병원성 가능 + 리뷰 등급으로 다시 가른다
    if not hit and gene in CLINVAR_JUDGE_GENES and cv_ok:
        hit, rule_id, why = cv_variant, f"BM3-{gene}-CLINVAR", "ClinVar 병원성·병원성 가능"

    picked = hit or cv_variant or variants[0]
    evidence = {"variant": f"p.{picked['protein_change']}" if picked.get("protein_change") else None,
                "vaf": picked.get("vaf")}
    if cv_row:
        evidence["clinvar"] = _clinvar_text(cv_row)
    if hit:
        return _record(marker, "positive", f"{gene} {_variant_text(variants)} → 양성: {why}{notes}",
                       rule_id, field, evidence, [GENE_TAGS[marker]])
    fda = f" ({FDA_VUS_NOTE[gene]})" if gene in FDA_VUS_NOTE else ""
    return _record(marker, "vus", f"{gene} {_variant_text(variants)} → 의미 불명 변이(VUS), 음성으로 처리하되 표시 유지"
                   f"{fda}{notes}", f"BM2-{gene}-VUS", field, evidence)


def _endocrine_progressed(fields):
    """내분비요법 중·후 진행 기록이 있는지 (전달 문서 4.6절)."""
    classes = _drug_class_map()
    for t in fields.get("treatment_history") or []:
        endocrine = any(classes.get(d) == "Hormone Therapy" for d in t.get("drugs") or [])
        progressed = t.get("best_response") == "PD" or t.get("stop_reason") == "progression"
        if endocrine and progressed:
            return True
    return False


def judge_esr1(field, fields):
    """ESR1: 판정 후, 원발 조직 결과인데 이후 내분비요법 진행이 있으면 재검 필요 (전달 문서 4.6절).
    진행 뒤에 새로 생기는 ESR1 변이는 원발 조직 결과로 알 수 없기 때문이다."""
    rec = judge_gene("ESR1", field)
    if rec["status"] in ("not_done", "not_recorded", "unknown"):
        return rec
    if field.get("specimen") == "primary" and _endocrine_progressed(fields):
        rec["reason"] = (f"원발 조직 결과({rec['status']})이고 이후 내분비요법 진행이 있어 재검 필요 "
                         f"(cfDNA·재생검) / 원래 판정: {rec['reason']}")
        rec["status"], rec["rule_id"] = "retest_needed", "BM2-ESR1-RETEST"
    return rec


# 생식세포 검사 칸(molecular.germline)이 있는 유전자. 결과가 있으면 종양 결과(mutations)보다 먼저 쓴다
# (A 결정 2026-10-28, PROJECT.md §14 생식세포/체세포 구분)
GERMLINE_GENES = ("BRCA1", "BRCA2", "PALB2")
FIELD_SOURCE_TEXT = {"germline": "생식세포 검사: ", "tumor": "종양 검사 결과 (생식세포 검사 결과 없음): "}


def gene_field_of(molecular, gene):
    """유전자 칸과 출처 -> (칸, "germline" | "tumor" | None).
    BRCA1·BRCA2·PALB2는 ① 생식세포 칸에 결과(present)가 있으면 그 칸, ② 없으면 mutations의 결과,
    ③ 둘 다 결과가 없으면 생식세포 칸의 상태(미시행·기록 없음)를 쓴다. 생식세포 칸이 없으면(TCGA 등)
    지금처럼 mutations만 보고 출처는 None이다."""
    molecular = molecular or {}
    tumor = (molecular.get("mutations") or {}).get(gene)
    germ = (molecular.get("germline") or {}).get(gene) if gene in GERMLINE_GENES else None
    if germ is None:
        return tumor, None
    if germ.get("status") == "present":
        return germ, "germline"
    if (tumor or {}).get("status") == "present":
        return tumor, "tumor"
    return germ, "germline"


def assess_genes(patient_state):
    """patient_state 한 명 -> 유전자 7개 레코드 목록."""
    fields = (patient_state or {}).get("fields") or {}
    patient_ref = (patient_state or {}).get("patient_ref", "")
    molecular = fields.get("molecular") or {}
    out = []
    for g in GENES:
        field, source = gene_field_of(molecular, g)
        rec = judge_esr1(field, fields) if g == "ESR1" else judge_gene(g, field, patient_ref)
        if source:
            rec["reason"] = FIELD_SOURCE_TEXT[source] + rec["reason"]
        out.append(rec)
    return out


# ---------------------------------------------------------------- 치료 상황
def _drug_class_map():
    if not hasattr(_drug_class_map, "cache"):
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            _drug_class_map.cache = {r["generic_name"]: r["drug_class"] for r in csv.DictReader(fh)}
    return _drug_class_map.cache


def _progressed(t):
    return t.get("best_response") == "PD" or t.get("stop_reason") == "progression"


def _line_label(n):
    return {1: "1L", 2: "2L"}.get(n, ">=3L")


def line_of(fields, disease):
    """setting.line (전달 문서 6.2절, draft6). 이번에 결정할 차수 (handoff_confirmed_state_to_B.md §6 1번, A 제안·B 찬성).
    차수는 A가 treatment_history[].line에 계산해 넘긴다.
    전이성: 마지막 고식적 요법의 차수. 그 요법이 진행(PD, progression)으로 끝났으면 다음 차수를 추천 대상으로 본다
    (전달 문서 8.2절 예시: 1차 letrozole + palbociclib 진행 -> 2L). 전이 후 투약이 없으면 1L (이번이 첫 고식적 치료).
    전이성이 아니면 마지막 선행·보조 투약에 A가 적은 setting (neoadjuvant / adjuvant)을 그대로 쓴다."""
    history = [t for t in fields.get("treatment_history") or [] if t.get("drugs")]
    if disease == "metastatic":
        lined = [t for t in history if t.get("line")]
        if not lined:
            if any(t.get("setting") == "metastatic" for t in history):
                return "unknown", "전이 후 투약은 있지만 차수 정보(line)가 없음"
            return "1L", "전이 후 고식적 투약 없음 -> 이번에 결정할 차수 1차"
        last = max(t["line"] for t in lined)
        regimen = [t for t in lined if t["line"] == last]
        drugs = " + ".join(sorted({d for t in regimen for d in t["drugs"]}))
        sub = regimen[-1]
        kind = (f", 내분비 {sub['endocrine_line']}차" if sub.get("endocrine_line") else "") + \
               (f", 항암 {sub['chemo_line']}차" if sub.get("chemo_line") else "")
        if any(_progressed(t) for t in regimen):
            return _line_label(last + 1), f"마지막 고식적 요법 {last}차({drugs}{kind})에서 진행 -> {last + 1}차 대상"
        return _line_label(last), f"마지막 고식적 요법 {last}차({drugs}{kind}), 진행 기록 없음"
    # 보조약·골 보호제는 차수를 정하지 않는다 (전달 문서 6.2절 규칙 3)
    classes = _drug_class_map()
    timed = [t for t in history if t.get("setting") in ("neoadjuvant", "adjuvant")
             and any(classes.get(d, "Unknown") not in NON_ANTICANCER_CLASSES for d in t["drugs"])]
    if not timed:
        return "unknown", "선행·보조요법 기록 없음"
    timed.sort(key=lambda t: (t.get("start_day") is None, t.get("start_day") or 0))
    last = timed[-1]
    return last["setting"], f"마지막 투약 {' + '.join(last['drugs'])} ({last['setting']})"


LINE_KIND = {"endocrine": ("endocrine_line", "내분비"), "chemo": ("chemo_line", "항암")}
HR_NEGATIVE_SUBTYPES = {"TNBC", "HR-/HER2+"}


def line_kind_of(fields, kind, subtype=None):
    """전이성의 setting.line_endocrine / line_chemo: 이번에 결정할 고식적 내분비·항암 차수 (A 전달 문서
    handoff_confirmed_state_to_B.md §6 2번, 2026-10-21. 화면 1 기본값). 공고 p.55처럼 두 종류를 따로 센다.
    그 종류의 고식적 요법이 없으면 1L, 마지막 차수에서 진행했으면 다음 차수, 진행 기록이 없으면 그 차수.
    전이 후 투약은 있는데 A가 차수를 하나도 넣지 않았으면 unknown. HR 음성은 내분비 not_applicable.
    간주 규칙(deemed_lines)은 넣지 않는다 (급여 판정에서 행마다 +1, 전달 문서 6.3a절)."""
    key, name = LINE_KIND[kind]
    if kind == "endocrine" and subtype in HR_NEGATIVE_SUBTYPES:
        return "not_applicable", f"{subtype}라 내분비요법 대상 아님"
    history = [t for t in fields.get("treatment_history") or [] if t.get("drugs")]
    metastatic = [t for t in history if t.get("setting") == "metastatic"]
    if metastatic and not any(t.get("line") for t in metastatic):
        return "unknown", "전이 후 투약은 있지만 차수 정보(line)가 없음"
    rows = [t for t in history if t.get(key)]
    if not rows:
        return "1L", f"고식적 {name}요법 이력 없음 -> {name} 1차"
    last = max(t[key] for t in rows)
    regimen = [t for t in rows if t[key] == last]
    drugs = " + ".join(sorted({d for t in regimen for d in t["drugs"]}))
    if any(_progressed(t) for t in regimen):
        return _line_label(last + 1), f"고식적 {name} {last}차({drugs})에서 진행 -> {name} {last + 1}차"
    return _line_label(last), f"고식적 {name} {last}차({drugs}), 진행 기록 없음"


def setting_of(fields, subtype=None):
    """현재 범주(전달 문서 6.1절), 차수(6.2절, line_of), 전이성이면 내분비·항암 차수(line_kind_of), 이전 약제 계열."""
    stage = fields.get("stage") or {}
    extent = stage.get("disease_extent") or {}
    recurrence = (fields.get("recurrence") or {}).get("status") or {}
    ext = extent.get("value") if extent.get("status") == "present" else None
    rec = recurrence.get("value") if recurrence.get("status") == "present" else None

    if ext == "metastatic":
        disease, why = "metastatic", "진단 시 전이성"
    elif rec == "distant":
        disease, why = "metastatic", f"진단 시 {ext or '범주 모름'}, 이후 원격 전이 재발"
    elif ext:
        disease, why = ext, f"진단 시 {ext}" + (", 국소 재발 (전이 아님)" if rec == "locoregional" else "")
    else:
        disease, why = "unknown", "진단 시 병기 범주 기록 없음"

    classes = _drug_class_map()
    prior = sorted({classes.get(d, "Unknown") for t in fields.get("treatment_history") or [] for d in t["drugs"]}
                   - NON_ANTICANCER_CLASSES)
    line, line_why = line_of(fields, disease)
    deemed = [d["rule_id"] for d in fields.get("deemed_lines") or [] if d.get("status") == "met"]
    if deemed:
        line_why += f" / 심평원 차수 간주 규칙 충족: {', '.join(deemed)} (급여 판정에서 차수 +1, 전달 문서 6.3a절)"
    out = {"disease": disease, "line": line}
    if disease == "metastatic":
        for kind in LINE_KIND:
            label, kind_why = line_kind_of(fields, kind, subtype)
            out[f"line_{kind}"] = label
            line_why += f" / {kind_why}"
    return {**out, "prior_drug_classes": prior, "reason": f"{why} / {line_why}"}


# ------------------------------------------------------------ BM-4 검사 공백
def tests_needed_of(by, subtype, disease, fields):
    """검사 공백 (PROJECT.md 5절). 미시행(not_done)만 권고하고, 기록 없음은 권고하지 않는다 (PROJECT.md 4절)."""
    out = []
    receptors = fields.get("receptors") or {}
    molecular = fields.get("molecular") or {}
    mutations = molecular.get("mutations") or {}

    def add(test, reason, rule_id, field=None):
        """field가 미시행이면서 raw가 "결과 대기"·"예정"이면 검사 권고 대신 결과 확인으로 바꾼다."""
        raw = (field or {}).get("raw") if (field or {}).get("status") == "not_done" else None
        if raw in PENDING_RAW:
            test, rule_id = f"{test} 결과 확인", f"{rule_id}-{PENDING_RAW[raw]}"
            reason = f"{reason} / 검사 {raw}: 새 검사 대신 결과 확인 필요"
        out.append({"test": test, "reason": reason, "rule_id": rule_id})

    for m, key in (("ER", "er_percent"), ("PR", "pr_percent"), ("HER2", "her2_ihc")):
        if by[m]["status"] == "not_done":
            add(f"{m} IHC", f"{m} 미시행. 아형을 정할 수 없음", f"BM4-{m}", receptors.get(key))
    her2 = by["HER2"]
    if her2["rule_id"] in ("BM2-HER2-2PLUS-NOISH", "BM2-HER2-2PLUS-RESULT-POS"):
        add("HER2 ISH (FISH·SISH)", her2["reason"], "BM4-HER2-ISH", receptors.get("her2_ish"))

    if disease != "metastatic":
        return out
    if her2["status"] == "negative" or (her2["status"] == "unknown" and her2["rule_id"] != "BM2-HER2-2PLUS-NOISH"):
        add("HER2 IHC 재판정", f"전이성인데 HER2 {her2['status']} ({her2['reason']}). "
                            "0/초저발현/저발현까지 재판정했는지 확인", "BM4-HER2-REASSESS")
    if subtype == "TNBC":
        pdl1 = receptors.get("pdl1") or {}
        if pdl1.get("status") == "not_done":
            add("PD-L1 (22C3 CPS, SP142 IC)", "전이성 TNBC인데 PD-L1 미시행", "BM4-PDL1", pdl1)

    # 유전자 (PROJECT.md 5절 검사 공백 규칙). 미시행만 권고한다. 생식세포 BRCA가 기록 없음이면
    # 권고하지 않는다 (전달 문서 4.7절, B 결정 2026-10-16)
    if subtype in ("HR+/HER2-", "TNBC"):
        for m in ("gBRCA1", "gBRCA2", "PALB2"):
            if by.get(m, {}).get("status") == "not_done":
                add(f"{m} (생식세포 검사)", f"전이성 HER2 음성인데 {m} 미시행. PARP 억제제 대상 확인", f"BM4-{m.upper()}",
                    gene_field_of(molecular, m.lstrip("g"))[0])
    if subtype == "HR+/HER2-":
        for m in ("PIK3CA", "AKT1", "PTEN"):
            if by.get(m, {}).get("status") == "not_done":
                add(m, f"전이성 HR+/HER2-인데 {m} 미시행. PI3K·AKT 억제제 대상 확인", f"BM4-{m}", mutations.get(m))
        esr1 = by.get("ESR1", {})
        if esr1.get("status") == "not_done":
            add("ESR1 (cfDNA)", "전이성 HR+/HER2-인데 ESR1 미시행. 경구 SERD 대상 확인", "BM4-ESR1",
                mutations.get("ESR1"))
        elif esr1.get("status") == "retest_needed":
            add("ESR1 (cfDNA)", esr1["reason"], "BM4-ESR1-RETEST")
    return out


# ------------------------------------------------------------------- 진입점
def assess_receptors(patient_state):
    """patient_state 한 명 -> ER, PR, HER2 레코드 목록."""
    rec = ((patient_state or {}).get("fields") or {}).get("receptors") or {}
    return [
        judge_er(rec.get("er_percent")),
        judge_pr(rec.get("pr_percent")),
        judge_her2(rec.get("her2_ihc"), rec.get("her2_ish")),
    ]


def assess(patient_state):
    """patient_state 한 명 -> biomarker_record 전체.
    patient_state 의 필드 이름이 바뀌면 이 함수만 고친다."""
    fields = (patient_state or {}).get("fields") or {}
    patient_ref = (patient_state or {}).get("patient_ref", "")

    records = assess_receptors(patient_state)
    records.append(judge_ki67((fields.get("proliferation") or {}).get("ki67_percent")))
    records.append(judge_pdl1((fields.get("receptors") or {}).get("pdl1")))
    records.extend(assess_genes(patient_state))
    by = {r["marker"]: r for r in records}

    subtype = subtype_of(by["ER"]["status"], by["PR"]["status"], by["HER2"]["status"])
    setting = setting_of(fields, subtype)
    return {
        "schema_version": "0.1-draft",
        "patient_ref": patient_ref,
        "records": records,
        "subtype": subtype,
        "setting": setting,
        "tests_needed": tests_needed_of(by, subtype, setting["disease"], fields),
    }
