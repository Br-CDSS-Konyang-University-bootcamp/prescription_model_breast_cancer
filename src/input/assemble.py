"""IN-4~6 조립과 마무리 [규칙] (notes/input_module_design.md §2 IN-4·IN-5·IN-6·마무리).

후보 목록(IN-2) → 인용 확인 → 정규화(IN-3) → patient_state.

- IN-4 값 고르기: 전이 병소 검체가 있으면 그 값 중 가장 늦은 것이 value, 원발 값은 history (recurrence).
  없으면 관찰 날짜(없으면 문서 날짜)가 가장 늦은 값이 value, 이전 값은 history (newer_result).
- IN-5 충돌: 고른 날짜에 값이 둘 이상이면 고르지 않는다. 그 칸은 fields에서 빼고 후보를 모두 conflicts[]에 넣는다.
- IN-6 누락: 후보가 없는 기본 칸은 not_recorded. 미시행·결과 대기·예정은 정규화(IN-3)가 not_done으로 낸다.
- 투약: 표 첫 칸에 보조·선행·고식이 없으면 전이일·수술일과 비교해 setting을 정하고,
  중단 사유가 진행이면 투약 기간 안의 재발·전이일(없으면 종료일)을 progression_day로 둔다.
  anthracycline 용량은 투약 줄에서 계산한다 (따로 후보를 받지 않는다).
- 마무리: index_day(가장 늦은 경과기록 날짜), genomic_reports(IN-7), lines.annotate(차수·간주 규칙), 스키마 검증.

인용을 못 찾은 후보, 정규화하지 못한 후보, 스키마 오류는 버리지 않고 issues로 돌려준다 (확인 요청·채점용).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from src.input.classify import Document
from src.input.common.lines import annotate, load_drug_table
from src.input.normalize import Context, normalize
from src.input.quote import locate

SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "patient_state.json"
SCHEMA_VERSION = "0.1-draft6"
# 차트에 없으면 not_recorded로 두는 칸 (draft6 기본 칸). 그 밖의 칸은 후보가 있을 때만 둔다
DEFAULT_FIELDS = {
    "diagnosis": ["diagnosis_date", "histology", "grade"],
    "stage": ["ctnm", "ptnm", "group", "positive_ln_count", "disease_extent", "metastatic_sites", "operable"],
    "receptors": ["er_percent", "pr_percent", "her2_ihc", "her2_ish", "pdl1"],
    "proliferation": ["ki67_percent"],
    "patient": ["gender", "age", "menopausal_status", "menopausal_basis", "ecog"],
    "neoadjuvant_response": ["pcr", "rcb"],
    "recurrence": ["recurrence_date", "adjuvant_endocrine_end_date", "status", "metastatic_sites", "metastasis_day",
                   "recurrence_day", "surgery", "surgery_intent"],
}
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
GROUP_ORDER = ["diagnosis", "stage", "receptors", "proliferation", "patient", "imaging_findings", "treatment_history",
               "anthracycline_drug_dose", "neoadjuvant_response", "recurrence", "molecular", "genomic_reports"]
LIST_FIELDS = {"treatment_history", "imaging_findings"}
DERIVED = {"anthracycline_drug_dose.drugs"}     # 투약 줄에서 계산하므로 후보를 쓰지 않는다


def assemble(docs: list[Document], candidates: list[dict], *, patient_ref: str, created_at: str,
             mapping: dict[str, str] | None = None) -> tuple[dict, list]:
    """patient_state와 issues [{reason, candidate | errors}]. docs는 원문, mapping은 IN-0 대응표 (구절 되돌리기)."""
    by_id = {d.doc_id: d for d in docs}
    order = {d.doc_id: i for i, d in enumerate(docs)}
    issues, found = [], []
    for c in candidates:
        if c["field"] in DERIVED:
            continue
        doc = by_id.get(c["doc_id"])
        src = doc and locate(c["quote"], doc, mapping)
        if src is None:
            issues.append({"reason": "quote_not_found", "candidate": c})
            continue
        found.append((c, doc, src))
    found.sort(key=lambda x: (order[x[0]["doc_id"]], x[2]["char_start"]))

    dx = _diagnosis_date(found)
    items = []                     # (후보, 문서, source, 정규화 결과)
    for c, doc, src in found:
        out = normalize(c["field"], src["quote"], Context.of(doc, src["char_start"], dx))
        if out is None:
            issues.append({"reason": "not_normalized", "candidate": c})
            continue
        items.append((c, doc, src, out))

    fields: dict = {g: {k: {"status": "not_recorded"} for k in ks} for g, ks in DEFAULT_FIELDS.items()}
    fields["molecular"] = {"mutations": {g: {"status": "not_recorded"} for g in GENES}}
    conflicts = []
    by_field: dict[str, list] = {}
    for it in items:
        if it[0]["field"] not in LIST_FIELDS:
            by_field.setdefault(it[0]["field"], []).append(it)
    for field, its in by_field.items():
        entries = [_entry(c, doc, src, out) for c, doc, src, out in its]
        chosen = _choose(field, entries)
        if isinstance(chosen, dict) and "conflict" in chosen:
            conflicts.append(chosen["conflict"])
            *groups, key = field.split(".")
            parent = fields
            for g in groups:
                parent = parent.get(g, {})
            parent.pop(key, None)          # 고르지 않은 칸은 not_recorded로도 두지 않는다
            continue
        _set(fields, field, chosen)

    rows = [(c, doc, src, out) for c, doc, src, out in items if c["field"] == "treatment_history"]
    rows.sort(key=lambda r: (r[3]["start_day"] is None, r[3]["start_day"] or 0))
    history = [{**out, "source": src} for _, _, src, out in rows]
    _fill_treatment(history, fields)
    anthra = []
    for (c, doc, src, out) in rows:
        a = normalize("anthracycline_drug_dose.drugs", src["quote"], Context.of(doc, src["char_start"], dx))
        if a:
            anthra.append({**a, "raw": src["quote"], "source": src})
    fields["treatment_history"] = history
    fields["anthracycline_drug_dose"] = {
        "administered": "positive" if anthra else "negative" if history else "No value", "drugs": anthra}
    images = [{**out, "source": src} for c, _, src, out in items if c["field"] == "imaging_findings"]
    if images:
        fields["imaging_findings"] = images
    fields["genomic_reports"] = [_genomic_report(d, fields) for d in docs if d.doc_type == "molecular"]
    fields = {g: fields[g] for g in GROUP_ORDER if g in fields}

    ps = {"schema_version": SCHEMA_VERSION, "patient_ref": patient_ref, "created_at": created_at,
          "index_day": _index_day(docs, dx), "documents": [d.entry() for d in docs], "fields": fields,
          "conflicts": conflicts}
    annotate(ps, load_drug_table())
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(ps)]
    if errors:
        issues.append({"reason": "schema", "errors": errors})
    return ps, issues


def _diagnosis_date(found) -> str | None:
    for c, doc, src in found:
        if c["field"] == "diagnosis.diagnosis_date":
            out = normalize(c["field"], src["quote"], Context.of(doc, src["char_start"]))
            if out and out["status"] == "present":
                return out["value"]
    return None


def _entry(c: dict, doc: Document, src: dict, out: dict) -> dict:
    """정규화 결과 + 원문 표기·검체·관찰 날짜·근거. 유전자 칸에는 raw가 없다 (변이마다 raw가 있다)."""
    e = dict(out)
    if not c["field"].startswith("molecular."):
        e.setdefault("raw", src["quote"])
    for k in ("specimen", "observed_date"):
        if c.get(k) is not None:
            e[k] = c[k]
    e["source"] = src
    e["_date"] = c.get("observed_date") or doc.doc_date or ""
    return e


def _choose(field: str, entries: list[dict]):
    """IN-4·IN-5. 고른 entry(history 포함) 또는 {"conflict": {...}}."""
    meta = [e for e in entries if e.get("specimen") == "metastasis"]
    pool = meta or entries
    latest = max(e["_date"] for e in pool)
    top = [e for e in pool if e["_date"] == latest]
    if len({_value_key(e) for e in top}) > 1:
        values = ", ".join(e["source"]["quote"] for e in top)
        return {"conflict": {"field": field, "candidates": [_clean(e) for e in entries],
                             "note": f"같은 날짜({latest or '날짜 없음'})의 값이 다름: {values}"}}
    current = _clean(top[-1])
    hist = [{**_clean(e), "superseded_reason": "recurrence" if meta and e.get("specimen") != "metastasis"
             else "newer_result"} for e in entries if e is not top[-1]]
    if hist:
        current["history"] = hist
    return current


def _value_key(e: dict) -> str:
    return json.dumps({k: e.get(k) for k in ("status", "value", "result", "variants")}, sort_keys=True)


def _clean(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "_date"}


def _set(fields: dict, path: str, entry: dict) -> None:
    *groups, key = path.split(".")
    cur = fields
    for g in groups:
        cur = cur.setdefault(g, {})
    cur[key] = entry


def _value(fields: dict, path: str):
    cur = fields
    for k in path.split("."):
        cur = cur.get(k, {}) if isinstance(cur, dict) else {}
    return cur.get("value") if cur.get("status") == "present" else None


def _day_of(fields: dict, path: str) -> int | None:
    """관찰 날짜가 있는 칸의 진단일 기준 일수 (수술일 = 병리 TNM의 관찰 날짜)."""
    cur = fields
    for k in path.split("."):
        cur = cur.get(k, {})
    dx = _value(fields, "diagnosis.diagnosis_date")
    if not cur.get("observed_date") or not dx:
        return None
    return (dt.date.fromisoformat(cur["observed_date"]) - dt.date.fromisoformat(dx)).days


def _fill_treatment(history: list[dict], fields: dict) -> None:
    mday = _value(fields, "recurrence.metastasis_day")
    surgery = _day_of(fields, "stage.yptnm") or _day_of(fields, "stage.ptnm")
    events = [d for d in (_value(fields, "recurrence.recurrence_day"), mday) if d is not None]
    for t in history:
        s, e = t["start_day"], t["end_day"]
        if t["setting"] is None:
            if mday is not None and s is not None and s >= mday:
                t["setting"] = "metastatic"
            elif surgery is not None and s is not None and s < surgery:
                t["setting"] = "neoadjuvant"
            else:
                t["setting"] = "adjuvant"
        prog = None
        if t["stop_reason"] == "progression":
            inside = [d for d in events if s is not None and e is not None and s <= d <= e]
            prog = min(inside) if inside else e
        t["progression_day"] = prog
        keys = ["drugs", "setting", "start_date", "end_date", "start_day", "end_day", "duration_days", "ongoing",
                "cycles", "progression_day", "stop_reason", "best_response", "source"]
        ordered = {k: t[k] for k in keys if k in t}
        t.clear()
        t.update(ordered)


def _genomic_report(doc: Document, fields: dict) -> dict:
    """IN-7. 문서 원문을 해석하지 않고 넘긴다. 검체는 이 문서에서 나온 유전자 칸의 검체, 없으면 '검체:' 줄."""
    genes = list(fields["molecular"].get("mutations", {}).values()) + list(fields["molecular"].get("germline", {}).values())
    specimen = next((g.get("specimen") for g in genes
                     if g.get("source", {}).get("doc_id") == doc.doc_id and g.get("specimen")), None)
    if specimen is None:
        line = re.search(r"검체\s*:.*", doc.text)
        line = line.group(0) if line else ""
        specimen = ("cfDNA" if re.search(r"cfDNA|plasma|혈장|채혈", line, re.I) else
                    "metastasis" if re.search(r"전이|metasta|간|폐|뼈|골", line, re.I) else "primary")
    return {"doc_id": doc.doc_id, "report_date": doc.doc_date, "specimen": specimen, "raw_text": doc.text}


def _index_day(docs: list[Document], dx: str | None) -> int | None:
    """판정 기준일 = 가장 늦은 경과기록 날짜 (가상 차트의 '오늘 외래'). 경과기록이 없으면 가장 늦은 문서 날짜."""
    dates = [d.doc_date for d in docs if d.doc_type == "progress_note" and d.doc_date] \
        or [d.doc_date for d in docs if d.doc_date]
    if not dates or not dx:
        return None
    return (dt.date.fromisoformat(max(dates)) - dt.date.fromisoformat(dx)).days
