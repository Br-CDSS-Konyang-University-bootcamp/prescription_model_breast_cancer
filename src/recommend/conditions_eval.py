"""[4] 급여 조건 판정기 (PROJECT.md §15.5 급여 분류 로직, D README "판정 쪽(B)", D 결정 안건 B2).

D의 급여 청크 `reimbursement.conditions`를 환자와 맞춰 본다. 규칙 코드만 쓰고 LLM·외부 API는 쓰지 않는다.
D 코드는 불러오지 않고 공용 형식(schemas/chunk.json, src/reimbursement/schema_proposal.md "읽는 법")만 읽는다.

결과는 세 값이다: True(충족) / False(불충족) / None(알 수 없음).
- 조건 항목: {id, field, op, value, text[, of][, unless]}. field마다 환자 JSON 위치는 D의 conditions.FIELDS 설명을 따른다
- all_of: 모두 만족. any_of: 묶음마다 항목 하나 이상, 묶음끼리는 "그리고"
- any_of_exceptions: 예외 하나의 all_of를 모두 만족하면 any_of가 실패해도 통과
- unless: 항목이 실패해도 unless를 만족하면 통과
- 바이오마커 status가 판정값(positive·negative·low·ultralow)이 아니면 알 수 없음. vus는 eq positive가 거짓 (음성 처리)
- 환자 JSON에 칸이 없거나 값이 없으면 알 수 없음
행 판정: 하나라도 거짓이면 not_met, 거짓 없이 알 수 없음이 있으면 unknown, 모두 참이면 met.
"""
import csv
from pathlib import Path

DRUG_CLASSES_CSV = Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "drug_classes.csv"
T_ORDER = ["Tis", "T1mi", "T1a", "T1b", "T1c", "T2", "T3", "T4a", "T4b", "T4c", "T4d"]
JUDGED = {"positive", "negative", "low", "ultralow"}
LINE_RULE_MIN = {"1차": (1, 1), "1차 이상": (1, None), "2차": (2, 2), "2차 이상": (2, None), "3차 이상": (3, None)}
LINE_STAGE_COUNT = {"palliative_endocrine": "endocrine_line", "palliative_chemo": "chemo_line"}


def _deem_rule(entry):
    """counts_as_prior_line 한 줄 -> A의 deemed_lines rule_id (D schema_proposal.md "차수 간주 규칙" 표).
    D가 rule_id를 적었으면 그 규칙을 그대로 본다 (D 요청 2026-10-22). 없으면 대응표로 맞춘다:
    anthracycline·taxane 포함 선행·보조 -> DEEM-ANTHRA-TAXANE, 종료 1년 이내 재발 -> DEEM-SG-1Y. 못 맞추면 None."""
    if entry.get("rule_id"):
        return entry["rule_id"]
    drugs = set(entry.get("drugs") or [])
    if {"anthracycline", "taxane"} <= drugs:
        return "DEEM-ANTHRA-TAXANE"
    if entry.get("within_days") == 365:
        return "DEEM-SG-1Y"
    return None


# ------------------------------------------------------------ 세 값 논리
def _and(values):
    values = list(values)
    if any(v is False for v in values):
        return False
    return None if any(v is None for v in values) else True


def _or(values):
    values = list(values)
    if any(v is True for v in values):
        return True
    return None if any(v is None for v in values) else False


# ------------------------------------------------------------ 환자 값 읽기
# 환자 칸 yes/no를 D 조건의 true/false로 읽는 조건 (LVEF 수치는 공고 기준을 D가 적은 뒤 연결한다)
YES_NO_FIELDS = ("cardiac_history", "mediastinal_radiation")
# 값 자체가 true/false인 조건. 그 밖의 조건에서 _value가 bool을 돌려주면 항목을 바로 정한 것이다
BOOL_FIELDS = ("bone_metastasis",) + YES_NO_FIELDS
def _present(field):
    """patient_state 칸 하나의 값. 값이 없으면 None."""
    return field.get("value") if isinstance(field, dict) and field.get("status") == "present" else None


def _drug_classes():
    """{약 일반명: {약 이름, drug_class, drug_subclass}} (공용 사전)."""
    if not hasattr(_drug_classes, "cache"):
        table = {}
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                table[r["generic_name"].lower()] = {r["generic_name"].lower(), r.get("drug_class", "").lower(),
                                                    r.get("drug_subclass", "").lower()} - {""}
        _drug_classes.cache = table
    return _drug_classes.cache


def _has_drug(entry, name):
    """요법 한 줄에 약 이름이나 계열 이름(drug_class·drug_subclass)이 들어 있는지."""
    name = name.lower()
    return any(name in _drug_classes().get(d.lower(), {d.lower()}) for d in entry.get("drugs") or [])


def _entries(fields, of):
    """of.drugs(하나라도 든 요법)·of.setting으로 거른 treatment_history 줄."""
    rows = fields.get("treatment_history") or []
    of = of or {}
    if of.get("setting"):
        rows = [t for t in rows if t.get("setting") in of["setting"]]
    if of.get("drugs"):
        rows = [t for t in rows if any(_has_drug(t, d) for d in of["drugs"])]
    return rows


def _marker(record, name):
    return {r["marker"]: r["status"] for r in record.get("records") or []}.get(name)


def _gene_status(record, markers):
    """여러 레코드 중 하나라도 양성이면 positive, 모두 음성(VUS 포함)이면 negative, 그 밖은 None."""
    sts = [_marker(record, m) for m in markers]
    if "positive" in sts:
        return "positive"
    if sts and all(s in ("negative", "vus") for s in sts):
        return "negative"
    return None


def _bounds(value, order, generic):
    """병기 값 -> order 안의 (가장 낮은, 가장 높은) 위치. 하위 병기 없이 적힌 값(T1, III 등)은 범위가 된다."""
    if value in order:
        i = order.index(value)
        return i, i
    if value in generic:
        lo, hi = generic[value]
        return order.index(lo), order.index(hi)
    return None


def _compare_ranged(op, have, want, order, generic):
    """병기 비교. 환자 값이 범위라 조건과 걸치면 알 수 없음. 'III'는 IIIA~IIIC를 포함한다 (하위 병기는 주 병기로 비교)."""
    wants = want if op == "in" else [want]
    hb = _bounds(have, order, generic)
    if hb is None or any(_bounds(w, order, generic) is None for w in wants):
        return None
    if op in ("eq", "in"):
        results = []
        for w in wants:
            lo, hi = _bounds(w, order, generic)
            results.append(True if lo <= hb[0] and hb[1] <= hi else (False if hb[1] < lo or hb[0] > hi else None))
        return _or(results)
    lo, hi = _bounds(want, order, generic)
    edge = {"gte": lo, "gt": hi, "lte": hi, "lt": lo}.get(op)
    if edge is None:
        return None
    ok = [_compare(op, r, edge) for r in range(hb[0], hb[1] + 1)]
    return True if all(ok) else (False if not any(ok) else None)


T_GENERIC = {"T1": ("T1mi", "T1c"), "T4": ("T4a", "T4d")}
STAGE_ORDER = ["0", "IA", "IB", "IIA", "IIB", "IIIA", "IIIB", "IIIC", "IV"]
STAGE_GENERIC = {"I": ("IA", "IB"), "II": ("IIA", "IIB"), "III": ("IIIA", "IIIC")}


def _days_since(fields, of, end_value):
    """end_value(재발일·진행일 등) - 맞는 요법 중 마지막 종료일."""
    rows = _entries(fields, of)
    if not rows:
        return False
    ends = [t.get("end_day") for t in rows]
    if end_value is None or any(e is None for e in ends):
        return None
    return end_value - max(ends)


def _bone_by_imaging(fields):
    """영상 소견(imaging_findings)에 확정(confirmed)된 뼈 전이가 있으면 True. 뼈가 의심으로만 적혔거나
    전이 부위 목록에만 있으면 영상 입증을 알 수 없어 None. 영상 소견과 전이 부위 어디에도 뼈가 없으면 False."""
    imaging = fields.get("imaging_findings")
    imaging = imaging if isinstance(imaging, list) else []
    bone = [i for i in imaging if "bone" in (i.get("sites") or [])]
    if any(i.get("certainty") == "confirmed" for i in bone):
        return True
    stage, recurrence = fields.get("stage") or {}, fields.get("recurrence") or {}
    lists = [s for s in (_present(stage.get("metastatic_sites")), _present(recurrence.get("metastatic_sites")))
             if isinstance(s, list)]
    if bone or any("bone" in s for s in lists):
        return None
    return False if (imaging or lists) else None


def _value(field, it, patient_state, record):
    """조건 항목의 field에 해당하는 환자 값. 판정할 수 없으면 None. 항목 자체를 바로 정할 수 있으면 bool."""
    fields = (patient_state or {}).get("fields") or {}
    stage, patient = fields.get("stage") or {}, fields.get("patient") or {}
    recurrence = fields.get("recurrence") or {}
    of = it.get("of")
    if field in ("her2", "er", "pr"):
        s = _marker(record, field.upper())
        return s if s in JUDGED else None
    if field == "hr":
        sub = record.get("subtype")
        return {"HR+/HER2-": "positive", "HR+/HER2+": "positive", "HR-/HER2+": "negative",
                "TNBC": "negative"}.get(sub)
    if field == "subtype":
        return record.get("subtype") if record.get("subtype") not in (None, "unknown") else None
    if field in ("pik3ca", "akt1", "pten"):
        s = _marker(record, field.upper())
        return "negative" if s == "vus" else (s if s in ("positive", "negative") else None)
    if field in ("gbrca", "sbrca"):
        prefix = field[0]
        return _gene_status(record, [f"{prefix}BRCA1", f"{prefix}BRCA2"])
    if field == "disease":
        d = (record.get("setting") or {}).get("disease")
        return d if d not in (None, "unknown") else None
    if field == "menopause":   # indeterminate(판단 불가)는 알 수 없음 (D 요청 2026-10-22)
        v = _present(patient.get("menopausal_status"))
        return None if v == "indeterminate" else v
    if field == "recurrence_operable":   # D FIELDS: 재발 후 수술 yes + 의도 curative면 yes, 그 밖은 알 수 없음
        done = _present(recurrence.get("surgery")) == "yes" and _present(recurrence.get("surgery_intent")) == "curative"
        return "yes" if done else None
    if field == "sex":
        return _present(patient.get("gender"))
    if field == "age":
        return _present(patient.get("age"))
    at_index = fields.get("at_index") or {}   # 판정 기준일 시점 값 (A가 계산, D FIELDS)
    if field == "age_at_index":
        return at_index.get("age") if isinstance(at_index.get("age"), int) else None
    if field == "recent_therapy_28d":
        status = (at_index.get("recent_therapy_28d") or {}).get("status")
        return status if status in ("yes", "no") else None
    if field == "recurrence":
        s = _present(recurrence.get("status"))
        return None if s in (None, "unknown") else s
    if field == "operable":
        v = _present(stage.get("operable"))
        return v if v in ("yes", "no") else None
    if field == "t_stage":
        tnm = _present(stage.get("ptnm")) or _present(stage.get("ctnm")) or {}
        return tnm.get("t")
    if field == "stage_group":
        return _present(stage.get("group"))
    if field == "positive_ln_count":
        v = (_present(stage.get("positive_ln_count")) or {}).get("positive")
        return v if isinstance(v, int) else None
    if field == "ln_status":
        n = ((_present(stage.get("ptnm")) or {}).get("n") or "").lstrip("pc")
        if n.startswith(("N1", "N2", "N3")):
            return "positive"
        return "negative" if n.startswith("N0") else None
    if field == "grade":
        return _present((fields.get("diagnosis") or {}).get("grade"))
    if field == "pcr":
        return _present((fields.get("neoadjuvant_response") or {}).get("pcr"))
    if field == "pdl1_22c3_cps":
        v = _present((fields.get("receptors") or {}).get("pdl1")) or {}
        return v.get("score") if v.get("assay") == "22C3" and v.get("score_type") == "CPS" else None
    if field == "bone_metastasis":   # "영상으로 골전이 입증" (draft7 체크리스트 §1.2, 2026-10-29)
        return _bone_by_imaging(fields)
    if field in ("palliative_endocrine_lines", "palliative_chemo_lines"):
        key = "endocrine_line" if "endocrine" in field else "chemo_line"
        rows = fields.get("treatment_history")
        return None if rows is None else max([t.get(key) or 0 for t in rows] or [0])
    if field == "days_end_to_recurrence":
        return _days_since(fields, of, _present(recurrence.get("recurrence_day")))
    if field == "days_end_to_metastasis":   # D FIELDS: 종료일부터 전이 기준일까지 (A의 DEEM-ENDO-ADJ-1Y와 같은 기준)
        return _days_since(fields, of, _present(recurrence.get("metastasis_day")))
    if field == "days_end_to_progression":
        rows = _entries(fields, of)
        if not rows:
            return False
        last = max(rows, key=lambda t: t.get("end_day") if t.get("end_day") is not None else -10**9)
        if last.get("progression_day") is None or last.get("end_day") is None:
            return None
        return last["progression_day"] - last["end_day"]
    if field == "days_since_last_dose":
        return _days_since(fields, of, (patient_state or {}).get("index_day"))
    if field == "treatment_years":
        rows = _entries(fields, of)
        if not rows or any(t.get("duration_days") is None for t in rows):
            return None
        return sum(t["duration_days"] for t in rows) / 365
    if field == "cycles_total":
        rows = _entries(fields, of)
        if not rows or any(not t.get("cycles") for t in rows):
            return None
        return sum(t["cycles"]["value"] for t in rows)
    if field == "cumulative_dose_mg_m2":
        drugs = [d.lower() for d in (of or {}).get("drugs") or []]
        items = [d for d in (fields.get("anthracycline_drug_dose") or {}).get("drugs") or []
                 if not drugs or d.get("drug") in drugs]
        doses = [d.get("total_dose") for d in items]
        if not items or any(not isinstance(x, dict) or x.get("unit") != "mg/m2" for x in doses):
            return None
        return sum(x["value"] for x in doses)
    if field in YES_NO_FIELDS:   # 심장 병력·종격동 방사선 (2026-10-22 칸 추가, draft7 체크리스트 §1.2). 기록 없음은 알 수 없음
        return {"yes": True, "no": False}.get(_present(patient.get(field)))
    return None   # 환자 JSON에 칸이 없는 조건


def _compare(op, have, want):
    if have is None:
        return None
    if op == "eq":
        return have == want
    if op == "in":
        return have in want
    if op == "exists":
        return bool(have) == bool(want)
    if not isinstance(have, (int, float)) or isinstance(have, bool):
        return None
    return {"gt": have > want, "gte": have >= want, "lt": have < want, "lte": have <= want}.get(op)


def evaluate_item(it, patient_state, record):
    """조건 항목 하나 -> True / False / None. unless가 있으면 항목이 실패해도 unless를 만족하면 통과."""
    result = _evaluate_one(it, patient_state, record)
    if result is not True and it.get("unless"):
        u = _evaluate_one(it["unless"], patient_state, record)
        if u is True:
            return True
        if result is False and u is None:
            return None
    return result


def _evaluate_one(it, patient_state, record):
    field, op, want = it.get("field"), it.get("op"), it.get("value")
    fields = (patient_state or {}).get("fields") or {}
    if field in ("prior_drugs", "prior_failed"):
        rows = _entries(fields, {"setting": (it.get("of") or {}).get("setting")})
        if fields.get("treatment_history") is None:
            return None
        wants = want if isinstance(want, list) else [want]
        if field == "prior_failed":
            found = []
            for w in wants:
                hits = [t for t in rows if _has_drug(t, w)]
                failed = [t for t in hits if t.get("stop_reason") == "progression" or t.get("best_response") == "PD"]
                unclear = [t for t in hits if t.get("stop_reason") is None and t.get("best_response") in (None, "unknown")]
                found.append(True if failed else (None if unclear else False))
            return _and(found)
        has = [any(_has_drug(t, w) for t in rows) for w in wants]
        if op == "contains":
            return all(has)
        if op == "not_contains":   # 투약 기록이 빈 목록이면 안 받은 건지 기록이 없는 건지 몰라 알 수 없음 (D 요청 2026-10-22)
            return None if not fields.get("treatment_history") else not any(has)
        return None
    have = _value(field, it, patient_state, record)
    if isinstance(have, bool) and field not in BOOL_FIELDS:
        return have      # 맞는 요법이 없어 항목을 바로 정한 경우 (False)
    if field == "t_stage":
        return None if have is None else _compare_ranged(op, have, want, T_ORDER, T_GENERIC)
    if field == "stage_group":
        return None if have is None else _compare_ranged(op, have, want, STAGE_ORDER, STAGE_GENERIC)
    return _compare(op, have, want)


def _line_rule(cond, patient_state):
    """line_rule {stage, line}: 이번에 줄 치료의 차수(이미 받은 고식적 차수 + 1)가 공고 투여단계에 맞는지.
    공고가 선행·보조요법을 1회로 간주하면(counts_as_prior_line) 그 행의 간주 규칙에 맞는 deemed_lines만 본다
    (handoff_to_B.md §6.3a "행마다 맞는 규칙을 골라"). 규칙을 못 맞추면 알 수 없음.
    DEEM-ENDO-ADJ-1Y(보조 내분비 1년 이내 진행)는 공고 원문에 그 문구가 있는 행에만 D가 rule_id로 넣는다.
    문구 없는 내분비 "2차 이상" 행에는 적용하지 않는다 (D 확인 2026-10-22)."""
    rule = cond.get("line_rule") or {}
    if not rule.get("line") or rule.get("stage") not in LINE_STAGE_COUNT:
        return True
    fields = (patient_state or {}).get("fields") or {}
    rows = fields.get("treatment_history")
    if rows is None:
        return None
    given = max([t.get(LINE_STAGE_COUNT[rule["stage"]]) or 0 for t in rows] or [0])
    lo, hi = LINE_RULE_MIN[rule["line"]]
    fits = lambda n: n >= lo and (hi is None or n <= hi)
    if fits(given + 1):
        return True
    if cond.get("counts_as_prior_line") and fits(given + 2):
        rule_ids = [_deem_rule(e) for e in cond.get("counts_as_prior_line") or []]
        status = {d.get("rule_id"): d.get("status") for d in fields.get("deemed_lines") or []}
        statuses = [status.get(r) if r else None for r in rule_ids]
        if "met" in statuses:
            return True
        if any(st in (None, "unknown") for st in statuses):
            return None
    return False


def evaluate_conditions(cond, patient_state, record):
    """급여 행 하나의 조건 -> {"status": met|not_met|unknown, "failed": [문장], "unknown": [문장]}."""
    failed, unknown = [], []

    def note(it, v):
        if v is False:
            failed.append(it.get("text") or it.get("field"))
        elif v is None:
            unknown.append(it.get("text") or it.get("field"))
        return v

    all_of = _and(note(it, evaluate_item(it, patient_state, record)) for it in cond.get("all_of") or [])
    stage = _and(note(it, evaluate_item(it, patient_state, record)) for it in cond.get("stage_rules") or [])
    groups = []
    for g in cond.get("any_of") or []:
        vals = [evaluate_item(it, patient_state, record) for it in g.get("items") or []]
        v = _or(vals)
        groups.append(note({"text": g.get("text")}, v))
    any_of = _and(groups)
    if any_of is not True and cond.get("any_of_exceptions"):
        exc = _or(_and(evaluate_item(it, patient_state, record) for it in e.get("all_of") or [])
                  for e in cond["any_of_exceptions"])
        if exc is True:
            any_of = True
            failed[:] = [f for f in failed if f not in [g.get("text") for g in cond.get("any_of") or []]]
            unknown[:] = [u for u in unknown if u not in [g.get("text") for g in cond.get("any_of") or []]]
        elif exc is None and any_of is False:
            any_of = None
    line = _line_rule(cond, patient_state)
    if line is not True:
        (failed if line is False else unknown).append(f"투여단계 {(cond.get('line_rule') or {}).get('line')}")
    total = _and([all_of, stage, any_of, line])
    return {"status": {True: "met", False: "not_met", None: "unknown"}[total], "failed": failed, "unknown": unknown}


def make_conditions_checker(patient_state, record, conditions_reviewed=False):
    """recommend()·postprocess()의 conditions_checker. (option, 시행 중인 급여 청크 목록) -> {status, reason}.
    D의 조건은 사람 검수 전이라(D README), conditions_reviewed가 False면 충족이든 불충족이든 확정하지 않고
    unknown(급여(조건 확인 필요))으로 돌려준다. 검수 전 조건이 틀렸을 때 약을 잘못 올리거나 내리지 않게 하려는 것."""
    def check(option, chunks):
        results = []
        for c in chunks:
            cond = (c.get("reimbursement") or {}).get("conditions")
            if cond:
                results.append((c["chunk_id"], evaluate_conditions(cond, patient_state, record)))
        if not results:
            return {"status": "unknown", "reason": "급여 청크에 투여 조건 없음"}
        met = [cid for cid, r in results if r["status"] == "met"]
        if met:
            reason = f"조건 충족 ({', '.join(met)})"
            if not conditions_reviewed:
                return {"status": "unknown", "reason": reason + ", 조건 사람 검수 전"}
            return {"status": "met", "reason": reason}
        unk = [(cid, r) for cid, r in results if r["status"] == "unknown"]
        if unk:
            return {"status": "unknown", "reason": "; ".join(f"{cid} 확인 필요: {', '.join(r['unknown'])}" for cid, r in unk)}
        reason = "; ".join(f"{cid} 불충족: {', '.join(r['failed'])}" for cid, r in results)
        if not conditions_reviewed:
            return {"status": "unknown", "reason": reason + ", 조건 사람 검수 전"}
        return {"status": "not_met", "reason": reason}
    return check
