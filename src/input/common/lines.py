"""전이 후 치료 차수와 심평원 차수 간주 규칙 (전달 문서 handoff_to_B.md §6.2·§6.3).

patient_state 한 명의 treatment_history로 전이 후 요법마다 차수를 매긴다. 세 가지를 따로 센다.
- line: 전이 후 전체 차수 (지침용 1L, 2L, >=3L)
- endocrine_line: 고식적 내분비요법 차수 (심평원 투여단계)
- chemo_line: 고식적 항암화학요법 차수 (심평원 투여단계). 심평원은 내분비와 항암을 따로 센다 (공고 p.55)

차수 규칙
1. 전이 기준일(recurrence.metastasis_day) 이후 시작한 투약이 전이 후 요법이다. 시작일이 없는 투약은 순서를 알 수 없어 뺀다.
2. 보조약(Supportive Care)과 골 보호제(Bone-modifying Agent)는 세지 않는다.
3. 시작일이 묶음 첫 투약에서 GROUP_DAYS(28일) 이내인 투약은 한 요법으로 묶는다.
4. 요법 종류: 항암화학·HER2 표적·면역항암제가 하나라도 있으면 항암, 아니면 내분비요법이 있으면 내분비,
   그 밖의 표적치료만 있으면 항암. lapatinib + letrozole 같은 HER2 표적 + 내분비 병용은 공고에서 항암화학요법 표에 있다.
5. 앞 요법이 진행(stop_reason = progression 또는 best_response = PD)으로 끝났으면 다음 요법은 다음 차수다.
   계획된 순차(planned_switch)·유지요법(maintenance)·독성(toxicity)으로 바뀌었으면 같은 차수다.
   끝난 이유를 모르면 다음 차수로 세고 notes에 남긴다.

간주 규칙 (deemed_lines). 차수 자체는 바꾸지 않고 규칙마다 충족 여부만 낸다. 급여 판정이 행마다 맞는 규칙을 골라 더한다.
- 선행·보조요법 = setting이 neoadjuvant·adjuvant이고 전이 기준일 전에 시작한 투약 (보조약·골 보호제 제외)
- 기간은 근거 투약 종료일부터 전이 기준일까지 센다. 종료일이 없으면 시작일로 하한을 잡아, 그래도 기간 안이면 met,
  아니면 unknown이다 (종료일이 시작일보다 앞설 수 없으므로).
"""
from __future__ import annotations

import csv
from pathlib import Path

DRUG_CLASSES_CSV = Path(__file__).resolve().parents[3] / "data" / "dictionaries" / "drug_classes.csv"
GROUP_DAYS = 28
NOT_COUNTED = {"Supportive Care", "Bone-modifying Agent"}
NOT_ANTICANCER = NOT_COUNTED | {"Unknown", "Other"}
CHEMO_CLASSES = {"Chemotherapy", "HER2-targeted Therapy", "Immunotherapy"}
SAME_LINE_STOPS = {"planned_switch", "maintenance", "toxicity"}

# rule_id: (category, 공고 쪽, 대상 setting, 기간(일) 또는 None)
DEEM_RULES = {
    "DEEM-ANTHRA-TAXANE": ("chemo", "61-62", ("neoadjuvant", "adjuvant"), None),
    "DEEM-SG-1Y": ("chemo", "63", ("neoadjuvant", "adjuvant"), 365),
    "DEEM-HER2ADC-6M": ("chemo", "62-63", ("adjuvant",), 183),
    "DEEM-ENDO-ADJ-1Y": ("endocrine", "57", ("adjuvant",), 365),
}


def load_drug_table(path: Path = DRUG_CLASSES_CSV) -> dict[str, tuple[str, str]]:
    """성분명 -> (drug_class, drug_subclass)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["generic_name"]: (r["drug_class"], r["drug_subclass"]) for r in csv.DictReader(f)}


def load_drug_classes(path: Path = DRUG_CLASSES_CSV) -> dict[str, str]:
    return {g: c for g, (c, _) in load_drug_table(path).items()}


def _category(classes: set[str]) -> str:
    if classes & CHEMO_CLASSES:
        return "chemo"
    if "Hormone Therapy" in classes:
        return "endocrine"
    if "Other Targeted Therapy" in classes:
        return "chemo"
    return "unknown"


def _progressed(items: list[dict]) -> bool | None:
    """요법이 진행으로 끝났으면 True, 같은 차수로 이어지는 이유면 False, 모르면 None."""
    if any(t.get("stop_reason") == "progression" or t.get("best_response") == "PD" for t in items):
        return True
    if any(t.get("stop_reason") in SAME_LINE_STOPS for t in items):
        return False
    return None


def _metastasis_day(fields: dict) -> int | None:
    mday = (fields.get("recurrence") or {}).get("metastasis_day") or {}
    return mday.get("value") if mday.get("status") == "present" else None


def palliative_lines(patient_state: dict, drug_classes: dict[str, str] | None = None) -> dict:
    classes = drug_classes if drug_classes is not None else load_drug_classes()
    fields = patient_state.get("fields") or {}
    metastasis_day = _metastasis_day(fields)
    notes: list[str] = []
    if metastasis_day is None:
        return {"metastasis_day": None, "regimens": [], "counts": None, "notes": ["전이 기준일이 없어 차수를 셀 수 없음"]}

    items = []
    for i, t in enumerate(fields.get("treatment_history") or []):
        start = t.get("start_day")
        if start is None:
            if t.get("setting") == "metastatic":
                notes.append(f"시작일이 없는 전이 후 투약은 뺌: {'+'.join(t['drugs'])}")
            continue
        if start < metastasis_day:
            continue
        drugs = [d for d in t["drugs"] if classes.get(d, "Unknown") not in NOT_COUNTED]
        if drugs:
            items.append({**t, "drugs": drugs, "_index": i})
    items.sort(key=lambda t: t["start_day"])

    groups: list[list[dict]] = []
    for t in items:
        if groups and t["start_day"] - groups[-1][0]["start_day"] <= GROUP_DAYS:
            groups[-1].append(t)
        else:
            groups.append([t])

    regimens = []
    line = endocrine = chemo = 0
    for g in groups:
        drugs = list(dict.fromkeys(d for t in g for d in t["drugs"]))
        category = _category({classes.get(d, "Unknown") for d in drugs})
        prev = regimens[-1] if regimens else None
        progressed = _progressed(prev["_items"]) if prev else True
        if prev and progressed is False:
            numbers = {k: prev[k] for k in ("line", "endocrine_line", "chemo_line")}
        else:
            if prev and progressed is None:
                notes.append(f"{'+'.join(prev['drugs'])} 이후 진행 여부를 몰라 {'+'.join(drugs)}를 다음 차수로 셈")
            line += 1
            endocrine += category == "endocrine"
            chemo += category == "chemo"
            numbers = {"line": line,
                       "endocrine_line": endocrine if category == "endocrine" else None,
                       "chemo_line": chemo if category == "chemo" else None}
        regimens.append({"drugs": drugs, "start_day": g[0]["start_day"], "category": category, **numbers,
                         "refs": [t["_index"] for t in g], "_items": g})

    for r in regimens:
        del r["_items"]
    return {"metastasis_day": metastasis_day, "regimens": regimens,
            "counts": {"line": line, "endocrine": endocrine, "chemo": chemo}, "notes": notes}


def _deem(rule_id: str, status: str, basis: str, refs: list[int], gap: int | None) -> dict:
    category, page, _, _ = DEEM_RULES[rule_id]
    return {"rule_id": rule_id, "category": category, "status": status, "basis": basis,
            "regimen_refs": refs, "gap_days": gap, "notice_page": page}


def _within(rule_id: str, cands: list[tuple[int, dict]], mday: int, limit: int, what: str) -> dict:
    """후보 투약 중 종료일(없으면 시작일 하한)이 전이 기준일 limit일 이내인 것이 있으면 met."""
    if not cands:
        return _deem(rule_id, "not_met", f"{what} 없음", [], None)

    def bound(t):
        return t["end_day"] if t.get("end_day") is not None else t.get("start_day")

    inside = [c for c in cands if bound(c[1]) is not None and mday - bound(c[1]) <= limit]
    if inside:
        i, t = max(inside, key=lambda c: bound(c[1]))
        gap = mday - bound(t)
        if t.get("end_day") is None:
            how = f"종료일 없음, 시작 후 {gap}일 뒤 전이"
        elif gap < 0:
            how = f"투여 중 전이 (종료 {-gap}일 전)"
        else:
            how = f"종료 후 {gap}일 뒤 전이"
        return _deem(rule_id, "met", f"{what} {'+'.join(t['drugs'])} {how} (기준 {limit}일 이내)", [i], gap)
    if any(c[1].get("end_day") is None for c in cands):
        return _deem(rule_id, "unknown", f"{what} 중 종료일 없는 투약이 있어 기간을 알 수 없음",
                     [c[0] for c in cands if c[1].get("end_day") is None], None)
    i, t = max(cands, key=lambda c: c[1]["end_day"])
    gap = mday - t["end_day"]
    return _deem(rule_id, "not_met", f"{what} {'+'.join(t['drugs'])} 종료 후 {gap}일 뒤 전이 (기준 {limit}일 초과)", [i], gap)


def deemed_lines(patient_state: dict, drug_table: dict[str, tuple[str, str]] | None = None) -> list[dict]:
    table = drug_table if drug_table is not None else load_drug_table()
    fields = patient_state.get("fields") or {}
    mday = _metastasis_day(fields)
    if mday is None:
        return [_deem(r, "not_applicable", "전이 기준일 없음 (전이성 아님)", [], None) for r in DEEM_RULES]
    history = fields.get("treatment_history") or []

    def cls(d):
        return table.get(d, ("Unknown", ""))[0]

    def sub(d):
        return table.get(d, ("Unknown", ""))[1]

    def before(settings, need=lambda drugs: True):
        return [(i, t) for i, t in enumerate(history)
                if t.get("setting") in settings and (t.get("start_day") is None or t["start_day"] < mday)
                and any(cls(d) not in NOT_ANTICANCER for d in t["drugs"]) and need(t["drugs"])]

    out = []
    pre = before(("neoadjuvant", "adjuvant"))
    anthra = [i for i, t in pre if any(sub(d) == "anthracycline" for d in t["drugs"])]
    taxane = [i for i, t in pre if any(sub(d) == "taxane" for d in t["drugs"])]
    if anthra and taxane:
        out.append(_deem("DEEM-ANTHRA-TAXANE", "met", "선행·보조요법에 anthracycline과 taxane이 모두 있음",
                         sorted(set(anthra + taxane)), None))
    else:
        lacking = " · ".join(x for x, ok in (("anthracycline", anthra), ("taxane", taxane)) if not ok)
        out.append(_deem("DEEM-ANTHRA-TAXANE", "not_met", f"선행·보조요법에 {lacking} 없음", sorted(set(anthra + taxane)), None))
    out.append(_within("DEEM-SG-1Y", pre, mday, 365, "선행·보조요법"))
    out.append(_within("DEEM-HER2ADC-6M", before(("adjuvant",), lambda ds: "trastuzumab" in ds), mday, 183,
                       "trastuzumab 포함 보조요법"))
    out.append(_within("DEEM-ENDO-ADJ-1Y", before(("adjuvant",), lambda ds: any(cls(d) == "Hormone Therapy" for d in ds)),
                       mday, 365, "보조 내분비요법"))
    return out


def annotate(patient_state: dict, drug_table: dict[str, tuple[str, str]] | None = None) -> dict:
    """patient_state에 차수 3칸(treatment_history[])과 deemed_lines를 채워 그대로 돌려준다."""
    table = drug_table if drug_table is not None else load_drug_table()
    fields = patient_state["fields"]
    numbers: dict[int, dict] = {}
    for r in palliative_lines(patient_state, {g: c for g, (c, _) in table.items()})["regimens"]:
        for i in r["refs"]:
            numbers[i] = {k: r[k] for k in ("line", "endocrine_line", "chemo_line")}
    for i, t in enumerate(fields["treatment_history"]):
        t.update(numbers.get(i, {"line": None, "endocrine_line": None, "chemo_line": None}))
    fields["deemed_lines"] = deemed_lines(patient_state, table)
    return patient_state
