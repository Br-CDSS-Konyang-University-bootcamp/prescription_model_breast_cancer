"""화면 1 확정값 (confirmed_state): 기본값 초안, 칸 수정, 확정 저장.

흐름 (src/input/handoff_confirmed_state_to_B.md §1):
    patient_state + biomarker_record ─ build_draft ─▶ 초안 ─ set_item (화면 1) ─▶ finalize ─▶ confirmed_state.json

- 초안은 schemas/confirmed_state.json과 같은 모양이다. 다만 시스템 값이 없거나 판정 불가(unknown)인 칸은
  confirmed가 None이고 needs에 이유가 남는다. 스키마는 confirmed에 unknown을 받지 않으므로 이 칸은 의사가 채운다.
- status는 의사가 고르지 않는다. set_item이 system과 비교해 confirmed / changed를 정하고, changed면 reason이 필요하다.
- finalize는 필수 칸이 비었으면 저장하지 않는다. 선택 칸이 비었으면 빼고 저장한다. 저장한 버전은 지우거나 덮어쓰지 않는다.
- biomarker_record는 JSON(dict)으로만 읽는다 (B 코드를 부르지 않는다).
- 재진(follow_up)의 previous·carried 처리는 아직 없다. 같은 환자의 이전 버전이 있으면 version·supersedes·visit_type만 채운다.

정한 규칙 (2026-10-30, A):
- dfi_days·high_risk_early는 여기서 계산한다 (전달 문서 §6-5 제안).
- gBRCA = gBRCA1·gBRCA2 하나로: 하나라도 positive → positive, vus → vus, 둘 다 negative → negative,
  하나만 negative이고 나머지가 기록 없음 → 의사 확인. sBRCA도 같다.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from src.input.script.rules import NOT_ANTICANCER, load_drug_table

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "schemas" / "confirmed_state.json"
SAVE_DIR = ROOT / "data" / "input" / "confirmed"   # json은 git에 올라가지 않는다 (.gitignore)
SCHEMA_VERSION = "0.1-draft"

MARKER_SCOPE = {"Ki-67": "diagnosis"}   # 나머지 마커는 current
MERGED_GENES = {"gBRCA": ("gBRCA1", "gBRCA2"), "sBRCA": ("sBRCA1", "sBRCA2")}
HR_POSITIVE = {"HR+/HER2-", "HR+/HER2+"}
T3_OR_MORE = ("T3", "T4")


def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------------------------------
# 칸 값 읽기
# ----------------------------------------------------------------------------------------------------

def _present(cell) -> bool:
    return isinstance(cell, dict) and cell.get("status") == "present"


def _value(cell):
    return cell.get("value") if _present(cell) else None


def _ref(source) -> list[dict]:
    """patient_state source → evidence_refs. 인용이 없으면 빈 목록."""
    if not isinstance(source, dict) or not source.get("quote"):
        return []
    return [{"doc_id": source.get("doc_id", ""), "quote": source["quote"],
             "char_start": source.get("char_start"), "char_end": source.get("char_end")}]


def _item(scope: str, system, source: str, *, refs=None, detail=None, note=None, check=None) -> dict:
    """확정 항목 한 칸. check(system)이 False면 (스키마가 받지 않는 값) confirmed는 비운다."""
    ok = system is not None and (check is None or check(system))
    it = {"scope": scope, "system": system, "system_source": source,
          "confirmed": copy.deepcopy(system) if ok else None, "status": "confirmed"}
    if detail:
        it["detail"] = detail
    if note:
        it["note"] = note
    if refs:
        it["evidence_refs"] = refs
    return it


def _bsa(fields: dict) -> float | None:
    """체표면적 (Mosteller). 키·몸무게가 없으면 None."""
    patient = fields.get("patient") or {}
    h, w = _value(patient.get("height_cm")), _value(patient.get("weight_kg"))
    return round((h * w / 3600) ** 0.5, 2) if h and w else None


def _per_m2(dose, bsa: float | None):
    """{value, unit} → mg/m2 용량 또는 not_recorded. mg는 체표면적이 있을 때만 바꾼다."""
    if not isinstance(dose, dict) or dose.get("value") is None:
        return "not_recorded"
    if dose.get("unit") == "mg/m2":
        return {"value": dose["value"], "unit": "mg/m2"}
    if dose.get("unit") == "mg" and bsa:
        return {"value": round(dose["value"] / bsa, 1), "unit": "mg/m2"}
    return "not_recorded"


# ----------------------------------------------------------------------------------------------------
# 항목별 기본값
# ----------------------------------------------------------------------------------------------------

def _neoadjuvant(fields: dict) -> bool:
    return any(t.get("setting") == "neoadjuvant" for t in fields.get("treatment_history") or [])


def _tnm(fields: dict) -> tuple[dict | None, str | None, dict | None]:
    """크기·T·N 판정에 쓸 TNM. 선행요법을 받았으면 선행 전 cTNM, 아니면 pTNM 우선."""
    stage = fields.get("stage") or {}
    order = ("ctnm", "ptnm") if _neoadjuvant(fields) else ("ptnm", "ctnm")
    for key in order:
        if _present(stage.get(key)):
            return stage[key]["value"], key[0], stage[key].get("source")
    return None, None, None


def _n_status(n: str | None) -> str | None:
    if not n:
        return None
    if n.startswith("NX"):
        return "not_assessed"
    if n.startswith("N0"):   # N0(i+)도 음성
        return "negative"
    return "positive"        # N1mi 포함


def _size(fields: dict, basis: str | None) -> tuple[object, str | None, dict | None]:
    stage = fields.get("stage") or {}
    keys = {"c": ("clinical_size_mm", "pathologic_size_mm"), "p": ("pathologic_size_mm", "clinical_size_mm")}
    for key in keys.get(basis or "p"):
        if _present(stage.get(key)):
            return stage[key]["value"], key[0], stage[key].get("source")
    return "not_recorded", None, None


def _high_risk(t: str | None, ln: int | None, grade, ki67: float | None) -> dict | None:
    """공고 9장 2 주2 (hira)와 ESMO E08 (esmo: hira + 1~3개면 Ki-67 20% 이상도 고위험, 원문 기호 확인 필요)."""
    if ln is None:
        return {"hira": "unknown", "esmo": "unknown"}
    if ln >= 4:
        return {"hira": "yes", "esmo": "yes"}
    if ln == 0:
        return {"hira": "no", "esmo": "no"}
    big = t.startswith(T3_OR_MORE) if t else None
    g3 = grade == 3 if grade in (1, 2, 3) else None
    if big or g3:
        return {"hira": "yes", "esmo": "yes"}
    hira = "no" if big is False and g3 is False else "unknown"
    if ki67 is not None and ki67 >= 20:
        return {"hira": hira, "esmo": "yes"}
    esmo = "no" if hira == "no" and ki67 is not None else "unknown"
    return {"hira": hira, "esmo": esmo}


def _dfi(fields: dict, recurrence_day, drug_table) -> tuple[object, str | None]:
    """무병 기간 = 첫 재발일 - 마지막 선행·보조 항암 요법 종료일 (음수 = 투여 중 재발)."""
    if recurrence_day is None:
        return "not_applicable", None
    ends = []
    for t in fields.get("treatment_history") or []:
        if t.get("setting") not in ("neoadjuvant", "adjuvant"):
            continue
        if all(drug_table.get(d, ("Unknown", ""))[0] in NOT_ANTICANCER for d in t["drugs"]):
            continue
        if t.get("end_day") is None:
            return None, f"{'+'.join(t['drugs'])} 종료일이 없어 무병 기간을 셀 수 없음"
        ends.append(t["end_day"])
    if not ends:
        return None, "선행·보조 요법이 없어 무병 기간 기준일이 없음"
    return recurrence_day - max(ends), None


def _regimens(fields: dict, index_day, drug_table, bsa) -> list[dict]:
    """treatment_history → prior_regimens. 판정 기준일 뒤에 시작한 투약은 뺀다."""
    out = []
    for t in fields.get("treatment_history") or []:
        if index_day is not None and t.get("start_day") is not None and t["start_day"] > index_day:
            continue
        subs = []
        for d in t["drugs"]:
            cls, sub = drug_table.get(d, ("Unknown", ""))
            subs.append(sub or cls)
        cycles = t.get("cycles")
        r = {"drugs": t["drugs"], "subclasses": list(dict.fromkeys(subs)),
             "setting": t.get("setting") if t.get("setting") in ("neoadjuvant", "adjuvant", "metastatic") else "unknown",
             "start_day": t.get("start_day"), "end_day": t.get("end_day"),
             "line_endocrine": t.get("endocrine_line"), "line_chemo": t.get("chemo_line"),
             "response": t.get("best_response") or "unknown", "stop_reason": t.get("stop_reason"),
             "progression_day": t.get("progression_day"),
             "cycles": {"value": cycles["value"], "interval_days": cycles.get("interval_days")} if cycles else None,
             "ongoing": t.get("ongoing")}
        if t.get("doses"):
            r["doses"] = [{"drug": d["drug"], "per_admin": _per_m2(d.get("per_admin"), bsa),
                           "total": _per_m2(d.get("total"), bsa), "basis": d.get("basis", "recorded")}
                          for d in t["doses"] if d.get("drug") in t["drugs"]]
        out.append(r)
    return out


def _anthracycline(fields: dict, bsa) -> dict | None:
    dose = fields.get("anthracycline_drug_dose") or {}
    if dose.get("administered") == "negative":
        return {}
    if dose.get("administered") != "positive":
        return None
    out: dict = {}
    for d in dose.get("drugs") or []:
        if d.get("drug") not in ("doxorubicin", "epirubicin", "liposomal doxorubicin"):
            continue
        total = _per_m2(d.get("total_dose"), bsa)
        prev = out.get(d["drug"])
        if prev is None:
            out[d["drug"]] = total
        elif isinstance(prev, dict) and isinstance(total, dict):
            out[d["drug"]] = {"value": prev["value"] + total["value"], "unit": "mg/m2"}
        else:
            out[d["drug"]] = "not_recorded"
    return out


def _merge_genes(statuses: list[str | None]) -> str | None:
    """gBRCA1·gBRCA2 → gBRCA (모듈 설명의 규칙). 정할 수 없으면 None."""
    s = [x for x in statuses if x is not None]
    if not s:
        return None
    if "positive" in s:
        return "positive"
    if "vus" in s:
        return "vus"
    if all(x == "negative" for x in s) and len(s) == len(statuses):
        return "negative"
    if "unknown" in s or "negative" in s:
        return None
    if "not_done" in s:
        return "not_done"
    return "not_recorded"


def _marker_detail(marker: str, rec: dict, fields: dict) -> dict:
    ev = {k: v for k, v in (rec.get("evidence") or {}).items() if v is not None}
    receptors = fields.get("receptors") or {}
    cell = {"ER": receptors.get("er_percent"), "PR": receptors.get("pr_percent"),
            "HER2": receptors.get("her2_ihc"), "PD-L1": receptors.get("pdl1")}.get(marker)
    v = _value(cell)
    if isinstance(v, dict):
        if marker in ("ER", "PR"):
            ev.update({k: v[k] for k in ("allred", "percent") if v.get(k) is not None})
        elif marker == "HER2" and v.get("score") is not None:
            ev["ihc_score"] = v["score"]
        elif marker == "PD-L1":
            ev.update({k: v[k] for k in ("assay", "score_type", "score") if k in v})
    return ev


def _markers(br: dict, fields: dict, checks: dict) -> dict:
    recs = {r["marker"]: r for r in br.get("records") or []}
    out = {}
    for marker, rec in recs.items():
        if any(marker in parts for parts in MERGED_GENES.values()):
            continue
        check = checks.get(f"markers.{marker}")
        if check is None:
            continue
        span = rec.get("source_span") or {}
        out[marker] = _item(MARKER_SCOPE.get(marker, "current"), rec["status"], "biomarker_record",
                            refs=_ref(span), detail=_marker_detail(marker, rec, fields), check=check)
    for merged, parts in MERGED_GENES.items():
        found = [recs[p] for p in parts if p in recs]
        if not found:
            continue
        system = _merge_genes([recs[p]["status"] if p in recs else None for p in parts])
        refs = [r for rec in found for r in _ref(rec.get("source_span"))]
        note = ", ".join(f"{p} {recs[p]['status']}" for p in parts if p in recs)
        it = _item("current", system, "derived", refs=refs, note=note, check=checks.get(f"markers.{merged}"))
        if system is None:
            it["system"] = note   # 화면에 원래 두 값을 보여준다
        out[merged] = it
    return out


# ----------------------------------------------------------------------------------------------------
# 스키마에서 칸별 허용 값 읽기 (화면 선택지와 초안 검사가 같은 값을 쓴다)
# ----------------------------------------------------------------------------------------------------

def _confirmed_rule(prop: dict) -> dict:
    for part in prop.get("allOf", []):
        rule = part.get("properties", {}).get("confirmed")
        if rule:
            return rule
    return {}


def item_rules(schema: dict | None = None) -> dict[str, dict]:
    """항목 키 → confirmed 규칙 (JSON Schema 조각). 마커는 'markers.ER'처럼 쓴다."""
    schema = schema or load_schema()
    props = schema["$defs"]["items"]["properties"]
    out = {k: _confirmed_rule(v) for k, v in props.items() if k != "markers"}
    for m, v in props["markers"]["properties"].items():
        out[f"markers.{m}"] = _confirmed_rule(v)
    for k, rule in out.items():   # $ref (gene_status 등)는 풀어 둔다
        if "$ref" in rule:
            out[k] = schema["$defs"][rule["$ref"].split("/")[-1]]
    return out


def value_checks(schema: dict | None = None) -> dict:
    """항목 키 → 값이 스키마에 맞는지 보는 함수."""
    schema = schema or load_schema()
    out = {}
    for key, rule in item_rules(schema).items():
        v = Draft202012Validator({**rule, "$defs": schema["$defs"]})
        out[key] = v.is_valid
    return out


def _checks() -> dict:
    if not hasattr(_checks, "cache"):
        _checks.cache = value_checks()
    return _checks.cache


# ----------------------------------------------------------------------------------------------------
# 초안
# ----------------------------------------------------------------------------------------------------

def build_draft(patient_state: dict, biomarker_record: dict, drug_table=None) -> dict:
    """patient_state + biomarker_record → 초안 confirmed_state (confirmed는 시스템 값, 없으면 None).

    반환값의 needs: 의사가 채우거나 확인할 칸 목록 (required_items·missing_items가 다시 계산한다).
    """
    drug_table = drug_table if drug_table is not None else load_drug_table()
    checks = _checks()
    fields = patient_state.get("fields") or {}
    setting = biomarker_record.get("setting") or {}
    stage, patient = fields.get("stage") or {}, fields.get("patient") or {}
    recurrence = fields.get("recurrence") or {}
    at_index = fields.get("at_index") or {}
    index_day = patient_state.get("index_day")
    bsa = _bsa(fields)
    notes: dict[str, str] = {}
    items: dict = {}

    def put(key, scope, system, source, **kw):
        items[key] = _item(scope, system, source, check=checks.get(key), **kw)

    # 치료 상황
    put("setting.disease", "current", setting.get("disease"), "biomarker_record")
    put("subtype", "current", biomarker_record.get("subtype"), "biomarker_record")
    line = setting.get("line")
    put("setting.phase", "current", line if line in ("neoadjuvant", "adjuvant", "unknown") else None, "biomarker_record")
    put("setting.line_endocrine", "current", setting.get("line_endocrine"), "biomarker_record")
    put("setting.line_chemo", "current", setting.get("line_chemo"), "biomarker_record")

    # 환자
    meno = _value(patient.get("menopausal_status"))
    meno_note = "peri → premenopausal (급여 2026-10-15 규칙, ESMO M01)" if meno == "perimenopausal" else None
    put("menopausal_status", "current", "premenopausal" if meno == "perimenopausal" else meno, "patient_state",
        refs=_ref((patient.get("menopausal_status") or {}).get("source")),
        detail={"basis": _value(patient.get("menopausal_basis")) or "not_recorded"}, note=meno_note)
    put("age_at_index", "current", at_index.get("age"), "patient_state")

    # 병기
    tnm, basis, tnm_src = _tnm(fields)
    t = (tnm or {}).get("t")
    put("stage.t", "diagnosis", t, "patient_state", refs=_ref(tnm_src), detail={"basis": basis} if basis else None)
    if t and items["stage.t"]["confirmed"] is None:
        notes["stage.t"] = f"T 값 '{t}'은 확정 칸 형식에 없음"
    size, size_basis, size_src = _size(fields, basis)
    put("stage.size_mm", "diagnosis", size, "patient_state", refs=_ref(size_src),
        detail={"basis": size_basis} if size_basis else None)
    put("stage.n", "diagnosis", _n_status((tnm or {}).get("n")), "patient_state", refs=_ref(tnm_src),
        detail={"basis": basis} if basis else None)
    ln_cell = stage.get("positive_ln_count")
    ln = (_value(ln_cell) or {}).get("positive") if _present(ln_cell) else None
    put("stage.positive_ln_count", "diagnosis", ln if ln is not None else "not_recorded", "patient_state",
        refs=_ref((ln_cell or {}).get("source")))
    put("stage.group", "diagnosis", _value(stage.get("group")), "patient_state",
        refs=_ref((stage.get("group") or {}).get("source")))
    put("operable", "diagnosis", _value(stage.get("operable")), "patient_state")
    grade = _value((fields.get("diagnosis") or {}).get("grade"))
    put("grade", "diagnosis", grade if grade in (1, 2, 3) else "not_recorded", "patient_state")
    pcr = _value((fields.get("neoadjuvant_response") or {}).get("pcr")) if _neoadjuvant(fields) else "not_applicable"
    put("pcr", "diagnosis", pcr, "patient_state")
    ki67 = (_value((fields.get("proliferation") or {}).get("ki67_percent")) or {}).get("percent")
    put("high_risk_early", "diagnosis", _high_risk(t, ln, grade, ki67), "derived",
        note=f"림프절 {ln if ln is not None else '?'}개, {t or 'T?'}, {grade or '?'}등급, Ki-67 {ki67 if ki67 is not None else '?'}%")

    # 재발·전이
    deemed = {d["rule_id"]: d["status"] for d in fields.get("deemed_lines") or []}
    deemed_ok = deemed and all(s in ("met", "not_met", "not_applicable") for s in deemed.values())
    put("deemed_lines", "current", deemed if deemed else None, "patient_state")
    if deemed and not deemed_ok:
        items["deemed_lines"]["confirmed"] = None
        notes["deemed_lines"] = "판정할 수 없는 규칙이 있음: " + ", ".join(k for k, s in deemed.items() if s == "unknown")
    endo = deemed.get("DEEM-ENDO-ADJ-1Y")
    endo_basis = next((d for d in fields.get("deemed_lines") or [] if d["rule_id"] == "DEEM-ENDO-ADJ-1Y"), {})
    adjuvant_et = any(t.get("setting") == "adjuvant" and
                      any(drug_table.get(d, ("Unknown", ""))[0] == "Hormone Therapy" for d in t["drugs"])
                      for t in fields.get("treatment_history") or [])
    if not adjuvant_et and endo in ("not_met", "not_applicable"):
        endo = "not_applicable"   # 보조 내분비요법이 없으면 해당 없음 (스키마 설명)
    put("endocrine_relapse_12m", "current",
        {"met": "yes", "not_met": "no", "not_applicable": "not_applicable"}.get(endo), "patient_state",
        note=endo_basis.get("basis"))
    rday = _value(recurrence.get("recurrence_day"))
    rstatus = _value(recurrence.get("status"))
    mday = _value(recurrence.get("metastasis_day"))
    if rday is None and rstatus in (None, "none"):
        put("recurrence_day", "current", "not_applicable", "patient_state")
    else:
        put("recurrence_day", "current", rday, "patient_state", refs=_ref((recurrence.get("recurrence_day") or {}).get("source")))
    put("metastasis_day", "current", mday if mday is not None else
        ("not_applicable" if setting.get("disease") != "metastatic" else None), "patient_state")
    dfi, dfi_note = _dfi(fields, rday if isinstance(rday, int) else None, drug_table)
    put("dfi_days", "current", dfi, "derived", note=dfi_note)
    if rstatus == "locoregional":
        rtype = "locoregional_curative" if _value(recurrence.get("surgery_intent")) == "curative" else "locoregional_other"
    elif rstatus in ("none", "distant"):
        rtype = rstatus
    elif mday == 0:
        rtype = "none"   # 진단 시 전이성 (재발 아님)
    else:
        rtype = None
    put("recurrence_type", "current", rtype, "patient_state",
        refs=_ref((recurrence.get("status") or {}).get("source")))

    sites = _value(recurrence.get("metastatic_sites"))
    if not isinstance(sites, list):
        sites = _value(stage.get("metastatic_sites"))
    put("metastatic_sites", "current", sites if isinstance(sites, list) else
        ([] if setting.get("disease") != "metastatic" else None), "patient_state")
    imaging = fields.get("imaging_findings") or []
    bone = [f for f in imaging if "bone" in (f.get("sites") or []) and f.get("certainty") == "confirmed"]
    bone_site = isinstance(sites, list) and "bone" in sites
    put("bone_metastasis_imaging", "current", "yes" if bone else (None if bone_site else "no"), "derived",
        refs=[r for f in bone for r in _ref(f.get("source"))],
        note="골전이 부위가 있지만 영상 확인 기록이 없음" if bone_site and not bone else None)

    # 약제·안전
    put("prior_regimens", "current", _regimens(fields, index_day, drug_table, bsa), "patient_state")
    put("anthracycline_cumulative", "current", _anthracycline(fields, bsa), "patient_state",
        note=f"체표면적 {bsa} m2로 환산" if bsa else None)
    recent = (at_index.get("recent_therapy_28d") or {})
    put("recent_therapy_28d", "current", recent.get("status"), "patient_state", note=recent.get("basis"))
    put("cardiac_risk", "current", _value(patient.get("cardiac_history")), "patient_state",
        detail={"lvef_percent": _value(patient.get("lvef_percent"))} if _value(patient.get("lvef_percent")) else None)
    put("mediastinal_radiation", "current", _value(patient.get("mediastinal_radiation")), "patient_state")
    put("visceral_crisis", "current", _value(patient.get("visceral_crisis")), "patient_state")
    comorb = _value(patient.get("comorbidities"))
    put("contraindicated_classes", "current", [], "derived",
        note=("동반질환: " + ", ".join(comorb)) if comorb else None)

    items["markers"] = _markers(biomarker_record, fields, checks)

    for key, text in notes.items():
        items_get(items, key)["note"] = text

    draft = {
        "schema_version": SCHEMA_VERSION,
        "patient_ref": patient_state.get("patient_ref"),
        "version": 1,
        "visit_type": "initial",
        "decision_context": None,
        "index_day": index_day,
        "confirmed_at": None,
        "confirmed_by": None,
        "based_on": {"patient_state_created_at": patient_state.get("created_at"),
                     "biomarker_record_version": biomarker_record.get("schema_version", "")},
        "supersedes": None,
        "items": items,
    }
    _refresh(draft)
    return draft


# ----------------------------------------------------------------------------------------------------
# 필수 칸과 빈 칸
# ----------------------------------------------------------------------------------------------------

def items_get(items: dict, key: str) -> dict | None:
    if key.startswith("markers."):
        return (items.get("markers") or {}).get(key.split(".", 1)[1])
    return items.get(key)


def item_keys(items: dict) -> list[str]:
    keys = [k for k in items if k != "markers"]
    return keys + [f"markers.{m}" for m in items.get("markers") or {}]


def _confirmed(items: dict, key: str):
    it = items_get(items, key)
    return it.get("confirmed") if it else None


def decision_context(items: dict) -> str | None:
    disease = _confirmed(items, "setting.disease")
    return {"metastatic": "metastatic", "early": "early", "locally_advanced": "early"}.get(disease)


def required_items(items: dict) -> list[str]:
    """지금 확정값으로 필수인 칸 (schemas/confirmed_state.json의 required·allOf를 옮김. 스키마를 고치면 같이 고칠 것)."""
    req = ["setting.disease", "subtype", "markers.ER", "markers.PR", "markers.HER2"]
    ctx, subtype = decision_context(items), _confirmed(items, "subtype")
    if ctx == "metastatic":
        req += ["setting.line_endocrine", "setting.line_chemo", "prior_regimens", "metastatic_sites"]
    elif ctx == "early":
        req += ["setting.phase", "stage.t", "stage.positive_ln_count", "stage.group"]
    if subtype in HR_POSITIVE:
        req.append("menopausal_status")
        if ctx == "metastatic":
            req.append("endocrine_relapse_12m")
    if ctx == "metastatic" and subtype == "TNBC":
        req += ["dfi_days", "markers.PD-L1"]
    return req


# 스키마 필수는 아니지만 이 결정에서 급여·지침 판정에 쓰는 칸 (비어 있으면 화면에서 확인을 권한다)
RECOMMENDED = {
    "metastatic": ["visceral_crisis", "recurrence_type", "metastasis_day", "recent_therapy_28d", "deemed_lines"],
    "early": ["stage.n", "stage.size_mm", "grade", "pcr", "high_risk_early", "operable"],
}


def missing_items(items: dict) -> dict[str, list[str]]:
    """{'required': 필수인데 빈 칸, 'recommended': 확인을 권하는 빈 칸}."""
    ctx = decision_context(items)
    req = required_items(items)
    empty = lambda k: items_get(items, k) is None or _confirmed(items, k) is None   # noqa: E731
    return {"required": [k for k in req if empty(k)],
            "recommended": [k for k in RECOMMENDED.get(ctx, []) if k not in req and items_get(items, k) and empty(k)]}


def _refresh(draft: dict) -> None:
    draft["decision_context"] = decision_context(draft["items"])
    draft["needs"] = missing_items(draft["items"])


# ----------------------------------------------------------------------------------------------------
# 수정과 확정
# ----------------------------------------------------------------------------------------------------

def set_item(draft: dict, key: str, value, reason: str | None = None) -> dict:
    """한 칸의 confirmed를 바꾼다. system과 같으면 status confirmed, 다르면 changed (reason 필요).

    value가 None이면 칸을 비운다. 스키마가 받지 않는 값이면 ValueError. 새 초안을 돌려준다 (원본은 바꾸지 않는다).
    """
    draft = copy.deepcopy(draft)
    it = items_get(draft["items"], key)
    if it is None:
        raise KeyError(f"없는 항목: {key}")
    if value is not None and not _checks()[key](value):
        raise ValueError(f"{key}: 허용하지 않는 값 {json.dumps(value, ensure_ascii=False)}")
    it["confirmed"] = value
    if value is None or value == it.get("system"):
        it["status"] = "confirmed"
        it.pop("reason", None)
    else:
        it["status"] = "changed"
        if reason:
            it["reason"] = reason
        else:
            it.pop("reason", None)
    _refresh(draft)
    return draft


def to_confirmed_state(draft: dict, confirmed_by: str, confirmed_at: str | None = None) -> tuple[dict, list[str]]:
    """초안 → confirmed_state 문서와 오류 목록. 빈 선택 칸은 뺀다. 오류가 있으면 저장하지 말 것."""
    doc = copy.deepcopy(draft)
    doc.pop("needs", None)
    errors = [f"{k}: 필수 칸이 비어 있음" for k in missing_items(doc["items"])["required"]]
    for key in item_keys(doc["items"]):
        it = items_get(doc["items"], key)
        if it["status"] == "changed" and not it.get("reason"):
            errors.append(f"{key}: 시스템 값과 다르게 확정하면 이유(reason)가 필요함")
    for key in list(doc["items"]):
        if key != "markers" and doc["items"][key].get("confirmed") is None:
            del doc["items"][key]
    for m in list(doc["items"].get("markers", {})):
        if doc["items"]["markers"][m].get("confirmed") is None:
            del doc["items"]["markers"][m]
    doc["decision_context"] = decision_context(doc["items"])
    doc["confirmed_by"] = confirmed_by
    doc["confirmed_at"] = confirmed_at or datetime.now().astimezone().isoformat(timespec="seconds")
    if not errors:
        errors = [f"{'/'.join(map(str, e.absolute_path)) or '(문서)'}: {e.message}"
                  for e in Draft202012Validator(load_schema()).iter_errors(doc)]
    return doc, errors


def _versions(patient_ref: str, save_dir: Path) -> list[Path]:
    folder = save_dir / patient_ref
    return sorted(folder.glob("v*.json"), key=lambda p: int(p.stem[1:])) if folder.exists() else []


def finalize(draft: dict, confirmed_by: str, confirmed_at: str | None = None,
             save_dir: Path = SAVE_DIR) -> tuple[Path | None, dict, list[str]]:
    """확정 저장. 오류가 없으면 save_dir/<patient_ref>/v<n>.json에 새 버전으로 쓴다 (이전 버전은 그대로)."""
    previous = _versions(draft["patient_ref"], save_dir)
    draft = copy.deepcopy(draft)
    if previous:
        with open(previous[-1], encoding="utf-8") as f:
            last = json.load(f)
        draft.update(version=last["version"] + 1, visit_type="follow_up",
                     supersedes={"version": last["version"], "confirmed_at": last["confirmed_at"]})
    doc, errors = to_confirmed_state(draft, confirmed_by, confirmed_at)
    if errors:
        return None, doc, errors
    path = save_dir / draft["patient_ref"] / f"v{doc['version']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:   # 같은 버전 파일이 있으면 덮어쓰지 않고 멈춘다
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path, doc, []
