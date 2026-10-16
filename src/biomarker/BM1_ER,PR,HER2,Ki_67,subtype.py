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
유전자 변이(ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2)는 허가 변이 목록(actionable_variants.csv)과
절단 변이만으로 판정하는 1차 규칙이다 (2026-10-16). 유전자 검사 공백(BM-4)은 미시행만 권고한다 (2026-10-16). 아직 다루지 않는 것:
차수(setting.line, 6.2절), BM-1 보고서 파싱, BM-3 근거 주석, PD-L1 약제별 판정(6.5절), 심평원 투여단계(6.3절)
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
# PR-low 태그는 쓰지 않는다 (ASCO·ESMO에 PR-low 범주가 없음, 2026-10-15 결정)

# Ki-67: 이 값(%) 이상이면 positive(고증식) (팀 결정 2026-10-15)
KI67_HIGH_MIN = 20

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


def _gate(marker, field, rule_prefix):
    """칸이 없거나 미시행/기록 없음이면 바로 그 상태를 돌려준다. 값이 있으면 None."""
    if not field or field.get("status") in (None, "not_recorded"):
        return _record(marker, "not_recorded", f"{marker} 기록 없음", f"{rule_prefix}-NOTRECORDED", field)
    if field.get("status") == "not_done":
        return _record(marker, "not_done", f"{marker} 미시행", f"{rule_prefix}-NOTDONE", field)
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


# ------------------------------------------------------------ 유전자 변이
# 전달 문서 3.6절(입력), 4.6절(ESR1 재검), 4.7절(BRCA), 5.4절(판정 순서). BM-3 로컬 조회(ClinVar, CIViC)가
# 생기기 전 1차 규칙이다: 허가 변이 목록 또는 절단 변이만 양성으로 보고, 나머지 검출 변이는 VUS로 남긴다.
GENES = ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")
# 허가 동반진단 변이 목록이 있는 유전자 (actionable_variants.csv)
LABEL_GENES = {"PIK3CA", "AKT1", "ESR1"}
# 절단 변이(nonsense, frameshift, 필수 스플라이스 부위)를 기능 소실 양성으로 보는 유전자
TRUNCATING_GENES = {"PTEN", "BRCA1", "BRCA2", "PALB2"}
TRUNCATING_TYPES = {"Nonsense_Mutation", "Frame_Shift_Del", "Frame_Shift_Ins", "Splice_Site"}
ACTIONABLE_CSV = Path(__file__).resolve().parent / "actionable_variants.csv"
GENE_TAGS = {"PIK3CA": "PIK3CA-mut", "AKT1": "AKT1-mut", "PTEN": "PTEN-loss", "ESR1": "ESR1-mut",
             "PALB2": "PALB2-mut", "gBRCA1": "gBRCA", "gBRCA2": "gBRCA", "sBRCA1": "sBRCA", "sBRCA2": "sBRCA"}


def _actionable():
    """{유전자: {단백질 변화: 행}} (actionable_variants.csv)."""
    if not hasattr(_actionable, "cache"):
        table = {}
        with open(ACTIONABLE_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                table.setdefault(r["gene"], {})[r["protein_change"]] = r
        _actionable.cache = table
    return _actionable.cache


def _is_truncating(variant):
    change = variant.get("protein_change") or ""
    return (variant.get("variant_type") in TRUNCATING_TYPES
            or change.endswith("*") or "fs" in change or change.endswith("_splice"))


def _gene_marker(gene, patient_ref):
    """BRCA1/2 레코드 이름. patient_state에 생식세포/체세포 구분 칸이 없어, TCGA는 gBRCA로 가정하고
    (전달 문서 4.7절) 그 밖은 종양 검사로 보고 sBRCA로 둔다 (PROJECT.md 남은 과제의 origin 칸 검토)."""
    if gene in ("BRCA1", "BRCA2"):
        return ("g" if patient_ref.startswith("TCGA-") else "s") + gene
    return gene


def _variant_text(variants):
    return ", ".join(v.get("protein_change") or v.get("raw") or "?" for v in variants)


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

    hit, rule_id, why = None, None, ""
    if gene in LABEL_GENES:
        table = _actionable().get(gene, {})
        hit = next((v for v in variants if v.get("protein_change") in table), None)
        if hit:
            row = table[hit["protein_change"]]
            rule_id = f"BM2-{gene}-LABEL"
            why = f"{row['drug']} 허가 동반진단 변이 ({row['source']})"
            if row["verified"] != "yes":
                why += ", 변이 목록 원문 확인 필요"
    if gene in TRUNCATING_GENES:
        hit = next((v for v in variants if _is_truncating(v)), None)
        if hit:
            rule_id, why = f"BM2-{gene}-TRUNC", "절단 변이 (기능 소실)"

    picked = hit or variants[0]
    evidence = {"variant": f"p.{picked['protein_change']}" if picked.get("protein_change") else None,
                "vaf": picked.get("vaf")}
    if hit:
        return _record(marker, "positive", f"{gene} {_variant_text(variants)} → 양성: {why}",
                       rule_id, field, evidence, [GENE_TAGS[marker]])
    return _record(marker, "vus",
                   f"{gene} {_variant_text(variants)} → 의미 불명 변이(VUS). 음성으로 처리하되 표시 유지. "
                   "BM-3(ClinVar·CIViC) 조회로 다시 판정 예정", f"BM2-{gene}-VUS", field, evidence)


def _endocrine_progressed(fields):
    """내분비요법 중·후 진행 기록이 있는지 (전달 문서 4.6절)."""
    classes = _drug_class_map()
    for t in fields.get("treatment_history") or []:
        endocrine = any(classes.get(d) == "Hormone Therapy" for d in t.get("drugs") or [])
        progressed = (t.get("best_response") == "PD" or t.get("stop_reason") == "progression"
                      or t.get("progression_day") is not None)
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


def assess_genes(patient_state):
    """patient_state 한 명 -> 유전자 7개 레코드 목록."""
    fields = (patient_state or {}).get("fields") or {}
    patient_ref = (patient_state or {}).get("patient_ref", "")
    mutations = (fields.get("molecular") or {}).get("mutations") or {}
    return [judge_esr1(mutations.get("ESR1"), fields) if g == "ESR1"
            else judge_gene(g, mutations.get(g), patient_ref) for g in GENES]


# ---------------------------------------------------------------- 치료 상황
def _drug_class_map():
    if not hasattr(_drug_class_map, "cache"):
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            _drug_class_map.cache = {r["generic_name"]: r["drug_class"] for r in csv.DictReader(fh)}
    return _drug_class_map.cache


def setting_of(fields):
    """현재 범주(전달 문서 6.1절)와 이전 약제 계열. 차수는 아직 계산하지 않는다 (6.2절)."""
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
    return {"disease": disease, "line": "unknown", "prior_drug_classes": prior,
            "reason": f"{why} / 차수는 아직 계산하지 않음 (전달 문서 6.2절)"}


# ------------------------------------------------------------ BM-4 검사 공백
def tests_needed_of(by, subtype, disease, fields):
    """검사 공백 (PROJECT.md 5절). 미시행(not_done)만 권고하고, 기록 없음은 권고하지 않는다 (PROJECT.md 4절)."""
    out = []

    def add(test, reason, rule_id):
        out.append({"test": test, "reason": reason, "rule_id": rule_id})

    for m in ("ER", "PR", "HER2"):
        if by[m]["status"] == "not_done":
            add(f"{m} IHC", f"{m} 미시행. 아형을 정할 수 없음", f"BM4-{m}")
    her2 = by["HER2"]
    if her2["rule_id"] in ("BM2-HER2-2PLUS-NOISH", "BM2-HER2-2PLUS-RESULT-POS"):
        add("HER2 ISH (FISH·SISH)", her2["reason"], "BM4-HER2-ISH")

    if disease != "metastatic":
        return out
    if her2["status"] == "negative" or (her2["status"] == "unknown" and her2["rule_id"] != "BM2-HER2-2PLUS-NOISH"):
        add("HER2 IHC 재판정", f"전이성인데 HER2 {her2['status']} ({her2['reason']}). "
                            "0/초저발현/저발현까지 재판정했는지 확인", "BM4-HER2-REASSESS")
    if subtype == "TNBC":
        pdl1 = (fields.get("receptors") or {}).get("pdl1") or {}
        if pdl1.get("status") == "not_done":
            add("PD-L1 (22C3 CPS, SP142 IC)", "전이성 TNBC인데 PD-L1 미시행", "BM4-PDL1")

    # 유전자 (PROJECT.md 5절 검사 공백 규칙). 미시행만 권고한다. 생식세포 BRCA가 기록 없음이거나
    # 레코드가 sBRCA뿐이면(TCGA가 아닌 차트) 권고하지 않는다 (전달 문서 4.7절, B 결정 2026-10-16)
    if subtype in ("HR+/HER2-", "TNBC"):
        for m in ("gBRCA1", "gBRCA2", "PALB2"):
            if by.get(m, {}).get("status") == "not_done":
                add(f"{m} (생식세포 검사)", f"전이성 HER2 음성인데 {m} 미시행. PARP 억제제 대상 확인", f"BM4-{m.upper()}")
    if subtype == "HR+/HER2-":
        for m in ("PIK3CA", "AKT1", "PTEN"):
            if by.get(m, {}).get("status") == "not_done":
                add(m, f"전이성 HR+/HER2-인데 {m} 미시행. PI3K·AKT 억제제 대상 확인", f"BM4-{m}")
        esr1 = by.get("ESR1", {})
        if esr1.get("status") == "not_done":
            add("ESR1 (cfDNA)", "전이성 HR+/HER2-인데 ESR1 미시행. 경구 SERD 대상 확인", "BM4-ESR1")
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
    records.extend(assess_genes(patient_state))
    by = {r["marker"]: r for r in records}

    subtype = subtype_of(by["ER"]["status"], by["PR"]["status"], by["HER2"]["status"])
    setting = setting_of(fields)
    return {
        "schema_version": "0.1-draft",
        "patient_ref": patient_ref,
        "records": records,
        "subtype": subtype,
        "setting": setting,
        "tests_needed": tests_needed_of(by, subtype, setting["disease"], fields),
    }
