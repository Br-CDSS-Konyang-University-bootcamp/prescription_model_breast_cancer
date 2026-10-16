"""전이 후 치료 차수 (전달 문서 handoff_to_B.md §6.2·§6.3).

patient_state 한 명의 treatment_history로 전이 후 요법마다 차수를 매긴다. 세 가지를 따로 센다.
- line: 전이 후 전체 차수 (지침용 1L, 2L, >=3L)
- endocrine_line: 고식적 내분비요법 차수 (심평원 투여단계)
- chemo_line: 고식적 항암화학요법 차수 (심평원 투여단계). 심평원은 내분비와 항암을 따로 센다 (공고 p.55)

규칙
1. 전이 기준일(recurrence.metastasis_day) 이후 시작한 투약이 전이 후 요법이다. 시작일이 없는 투약은 순서를 알 수 없어 뺀다.
2. 보조약(Supportive Care)과 골 보호제(Bone-modifying Agent)는 세지 않는다.
3. 시작일이 묶음 첫 투약에서 GROUP_DAYS(28일) 이내인 투약은 한 요법으로 묶는다.
4. 요법 종류: 항암화학·HER2 표적·면역항암제가 하나라도 있으면 항암, 아니면 내분비요법이 있으면 내분비,
   그 밖의 표적치료만 있으면 항암. lapatinib + letrozole 같은 HER2 표적 + 내분비 병용은 공고에서 항암화학요법 표에 있다.
5. 앞 요법이 진행(stop_reason = progression 또는 best_response = PD)으로 끝났으면 다음 요법은 다음 차수다.
   계획된 순차(planned_switch)·유지요법(maintenance)·독성(toxicity)으로 바뀌었으면 같은 차수다.
   끝난 이유를 모르면 다음 차수로 세고 notes에 남긴다.

아직 넣지 않은 것: 선행·보조요법을 고식적 1차로 간주하는 규칙(handoff §6.3)과 국소 재발 후 보조요법(SET-LOCAL-ADJ).
결과를 patient_state·biomarker_record의 어느 칸에 넣을지는 아직 정하지 않았다 (handoff §10.4).
"""
from __future__ import annotations

import csv
from pathlib import Path

DRUG_CLASSES_CSV = Path(__file__).resolve().parents[3] / "data" / "dictionaries" / "drug_classes.csv"
GROUP_DAYS = 28
NOT_COUNTED = {"Supportive Care", "Bone-modifying Agent"}
CHEMO_CLASSES = {"Chemotherapy", "HER2-targeted Therapy", "Immunotherapy"}
SAME_LINE_STOPS = {"planned_switch", "maintenance", "toxicity"}


def load_drug_classes(path: Path = DRUG_CLASSES_CSV) -> dict[str, str]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["generic_name"]: r["drug_class"] for r in csv.DictReader(f)}


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


def palliative_lines(patient_state: dict, drug_classes: dict[str, str] | None = None) -> dict:
    classes = drug_classes if drug_classes is not None else load_drug_classes()
    fields = patient_state.get("fields") or {}
    mday = ((fields.get("recurrence") or {}).get("metastasis_day") or {})
    metastasis_day = mday.get("value") if mday.get("status") == "present" else None
    notes: list[str] = []
    if metastasis_day is None:
        return {"metastasis_day": None, "regimens": [], "counts": None, "notes": ["전이 기준일이 없어 차수를 셀 수 없음"]}

    items = []
    for t in fields.get("treatment_history") or []:
        start = t.get("start_day")
        if start is None:
            if t.get("setting") == "metastatic":
                notes.append(f"시작일이 없는 전이 후 투약은 뺌: {'+'.join(t['drugs'])}")
            continue
        if start < metastasis_day:
            continue
        drugs = [d for d in t["drugs"] if classes.get(d, "Unknown") not in NOT_COUNTED]
        if drugs:
            items.append({**t, "drugs": drugs})
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
        regimens.append({"drugs": drugs, "start_day": g[0]["start_day"], "category": category, **numbers, "_items": g})

    for r in regimens:
        del r["_items"]
    return {"metastasis_day": metastasis_day, "regimens": regimens,
            "counts": {"line": line, "endocrine": endocrine, "chemo": chemo}, "notes": notes}
