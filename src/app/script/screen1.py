"""화면 1 처방 조건 확인 로컬 서버. team_project 폴더에서:

    python -m src.app.script.screen1                 # http://127.0.0.1:8501
    python -m src.app.script.screen1 --port 8600 --cases tests/fixtures/virtual_charts

화면 규격 (사용자 결정 2026-11-02, notes/ui_design_2026-10-21.md §4를 바꿈):
- 병리 판정(T·N·병기, ER 판정)은 보고서가 나오기 전에 끝난 일이라 화면 1에서 다시 고르지 않는다.
  화면 1은 "보고서를 처방 규칙의 값으로 옮긴 결과"를 확인하고 빈칸을 채운 뒤 처방 추천(화면 2)으로 넘긴다.
- 초진·재진으로 화면을 나누지 않는다. 모든 환자가 같은 칸 목록을 보고, 이번 결정 단계·아형에 맞지 않는 칸은
  숨기지 않고 "판정 해당 없음"으로 잠가 보여준다 (빠진 칸 없이 훑어볼 수 있게).
- 왼쪽: 검사 결과 원문. 오른쪽 세 묶음:
    A 처리해야 처방 가능  필수인데 빈 칸, 판정 불가(unknown), 값 충돌. 값을 골라야 넘어간다
    B 규칙 판정값          아형·HER2 저발현·병기 범주·치료 단계·재발 고위험군·차수 등 우리 규칙이 만든 값과 의사 판단 칸.
                           칸마다 확인 (전체 확인 가능), 바꾸면 사유
    C 보고서 값            T·N·병기군·림프절 수·등급 등 원문 그대로. 고르지 않고, 추출 오류일 때만 [고치기]

- 표준 라이브러리만 쓴다. 환자 정보가 들어가므로 127.0.0.1에만 연다.
- 서버는 상태를 갖지 않는다. 화면이 초안을 들고 있고, 칸을 바꿀 때마다 /api/set이 새 초안을 돌려준다.
  확정값 계산은 모두 src/input/script/confirmed.py가 한다.
- 각 모듈의 공개 함수만 부른다: A pipeline.split (문서 나누기), A confirmed.*, B assess()·subtype_of().
- 사례 폴더: <cases>/<case>/chart.txt + expected/patient_state.json. biomarker_record.json이 같은 폴더에 있으면 그것을 읽고,
  없으면 B의 assess()를 부른다.
- 확정 저장: data/input/confirmed/<patient_ref>/v<n>.json (git에 올라가지 않음). 해당 없는 선택 칸은 저장하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.app.script import screen2 as s2
from src.input.script import confirmed as c
from src.input.script.pipeline import split

ROOT = c.ROOT
HTML = Path(__file__).resolve().parents[1] / "html" / "screen1.html"
HTML2 = Path(__file__).resolve().parents[1] / "html" / "screen2.html"
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "virtual_charts"
FIELD_VOCAB = ROOT / "data" / "dictionaries" / "field_vocab.csv"

HR_POS = ("HR+/HER2-", "HR+/HER2+")
HER2_NEG = ("HR+/HER2-", "TNBC")
MET = "metastatic"
# 오른쪽 칸 목록 (순서대로 보인다). (칸, 묶음 rule/judge/report, 적용 조건, 해당 없음 이유, 필수 여부)
# 적용 조건은 x = {"sub": 아형, "dis": 병기 범주, "phase": 치료 단계, "prior": 이전 요법 있음, "er": ER 판정}을 받는다. None = 항상
ROWS = [
    ("subtype", "rule", None, "", True),
    ("markers.ER", "rule", None, "", True),
    ("markers.PR", "rule", None, "", True),
    ("markers.HER2", "rule", None, "", True),
    ("markers.Ki-67", "rule", lambda x: x["sub"] == "HR+/HER2-", "HR+/HER2-에서만 판정에 씀", True),
    ("markers.gBRCA", "rule", lambda x: x["sub"] in HER2_NEG, "HER2 음성에서만 판정에 씀", True),
    # ER 저발현은 HR+로 보지만 TNBC에 준할지 논의되고, D가 PD-L1 행(4가-6)을 판정한다 (VC-0142)
    ("markers.PD-L1", "rule", lambda x: x["sub"] == "TNBC" or x["er"] == "low", "TNBC·ER 저발현에서만 판정에 씀", True),
    ("setting.disease", "rule", None, "", True),
    ("setting.phase", "rule", lambda x: x["dis"] != MET, "전이성은 고식적 치료", True),
    ("high_risk_early", "rule", lambda x: x["sub"] == "HR+/HER2-" and x["dis"] != MET and x["phase"] == "adjuvant",
     "HR+/HER2- 보조요법에서만 판정 (보조 abemaciclib)", True),
    ("setting.line_endocrine", "rule", lambda x: x["dis"] == MET, "전이성에서만", True),
    ("setting.line_chemo", "rule", lambda x: x["dis"] == MET, "전이성에서만", True),
    ("recurrence_type", "rule", lambda x: x["dis"] == MET, "전이성에서만", False),
    ("endocrine_relapse_12m", "rule", lambda x: x["dis"] == MET and x["sub"] in HR_POS, "전이성 HR+에서만", True),
    ("dfi_days", "rule", lambda x: x["dis"] == MET and x["sub"] == "TNBC", "전이성 TNBC에서만", True),
    ("deemed_lines", "rule", lambda x: x["dis"] == MET, "전이성에서만", False),
    ("prior_regimens", "rule", lambda x: x["dis"] == MET or x["prior"], "이전 요법 없음", False),
    ("anthracycline_cumulative", "rule", lambda x: x["prior"], "이전 요법 없음", False),
    ("visceral_crisis", "judge", lambda x: x["dis"] == MET, "전이성에서만", False),
    ("contraindicated_classes", "judge", None, "", False),
    ("menopausal_status", "report", lambda x: x["sub"] in HR_POS, "HR+에서만 판정에 씀", True),
    ("stage.t", "report", None, "", True),
    ("stage.n", "report", None, "", True),
    ("stage.group", "report", None, "", True),
    ("stage.positive_ln_count", "report", None, "", True),
    ("stage.size_mm", "report", None, "", False),
    ("grade", "report", None, "", True),
    ("pcr", "report", lambda x: x["prior"] and x["dis"] != MET, "선행요법 뒤에만", False),
    ("metastatic_sites", "report", lambda x: x["dis"] == MET, "전이성에서만", True),
]
# 값 충돌이 난 patient_state 칸 → 확정 칸 (A 묶음으로 올린다)
CONFLICT_ITEM = {"proliferation.ki67_percent": "markers.Ki-67", "receptors.er_percent": "markers.ER",
                 "receptors.pr_percent": "markers.PR", "receptors.her2_ihc": "markers.HER2", "receptors.her2_ish": "markers.HER2",
                 "receptors.pdl1": "markers.PD-L1", "patient.menopausal_status": "menopausal_status", "diagnosis.grade": "grade",
                 "stage.positive_ln_count": "stage.positive_ln_count", "stage.group": "stage.group"}

LABELS = {
    "grade": "등급", "stage.t": "T", "stage.n": "림프절 (N)", "stage.group": "병기군", "stage.positive_ln_count": "양성 림프절 수",
    "setting.disease": "병기 범주", "setting.phase": "치료 단계", "subtype": "아형", "menopausal_status": "폐경",
    "metastatic_sites": "전이 부위", "high_risk_early": "재발 고위험군", "stage.size_mm": "종양 크기 (mm)", "operable": "수술 가능",
    "pcr": "pCR", "setting.line_endocrine": "고식적 내분비 차수", "setting.line_chemo": "고식적 항암 차수",
    "prior_regimens": "이전 요법", "endocrine_relapse_12m": "보조 ET 중·12개월 내 재발", "dfi_days": "무병 기간 (일)",
    "recurrence_type": "재발 유형", "deemed_lines": "심평원 차수 간주", "anthracycline_cumulative": "anthracycline 누적",
    "visceral_crisis": "장기 위기", "contraindicated_classes": "금기 약 계열", "age_at_index": "기준일 나이",
}
# 저장 코드 → 화면 표시. 칸별로 다르면 "칸:코드"
VALUE_LABELS = {
    "positive": "양성", "negative": "음성", "low": "저발현", "ultralow": "초저발현", "intermediate": "중간",
    "not_done": "미시행", "not_recorded": "기록 없음", "vus": "VUS", "unknown": "판정 불가", "retest_needed": "재검 필요",
    "yes": "예", "no": "아니오", "not_applicable": "해당 없음", "not_assessed": "평가 안됨",
    "early": "조기 (I~II)", "locally_advanced": "국소 진행성 (III)", "metastatic": "전이성 (IV)",
    "neoadjuvant": "선행요법", "adjuvant": "보조요법", "premenopausal": "폐경 전", "postmenopausal": "폐경 후",
    "markers.ER:low": "저발현 (1~10%)", "markers.Ki-67:positive": "고증식 (20% 이상)", "markers.Ki-67:negative": "저증식",
    "markers.PD-L1:positive": "양성 (22C3 CPS 10 이상)", "stage.n:positive": "양성 (N1mi 이상)", "stage.n:negative": "음성 (N0)",
    "stage.n:not_assessed": "평가 안됨 (NX)", "stage.t:not_assessed": "TX (평가 안됨)", "grade:1": "1", "grade:2": "2", "grade:3": "3",
    "high_risk_early:unknown": "확인 필요", "met": "충족", "not_met": "불충족",
    "locoregional_curative": "국소 재발 (근치 수술)", "locoregional_other": "국소 재발 (그 밖)", "distant": "원격 전이",
    "none": "재발 없음", ">=3L": "3차 이상", "1L": "1차", "2L": "2차",
    "bone": "뼈", "liver": "간", "lung": "폐", "brain": "뇌", "skin": "피부", "distant_ln": "원격 림프절",
}
DOC_TYPES = {"progress_note": "경과기록", "pathology": "병리결과보고서", "molecular": "분자병리", "medication": "투약 기록",
             "radiology": "영상 판독"}
# ① 원문 칸 이름 (patient_state 경로). 없는 경로는 마지막 이름을 그대로 쓴다
PS_LABELS = {
    "diagnosis.diagnosis_date": "진단일", "diagnosis.histology": "조직형", "diagnosis.grade": "등급",
    "stage.ctnm": "cTNM", "stage.ptnm": "pTNM", "stage.yptnm": "ypTNM", "stage.group": "병기군",
    "stage.positive_ln_count": "림프절", "stage.metastatic_sites": "전이 부위", "stage.operable": "수술",
    "stage.pathologic_size_mm": "크기 (병리)", "stage.clinical_size_mm": "크기 (임상)",
    "receptors.er_percent": "ER", "receptors.pr_percent": "PR", "receptors.her2_ihc": "HER2 IHC",
    "receptors.her2_ish": "HER2 ISH", "receptors.pdl1": "PD-L1", "proliferation.ki67_percent": "Ki-67",
    "patient.gender": "성별", "patient.age": "나이", "patient.menopausal_status": "폐경", "patient.menopausal_basis": "폐경 근거",
    "patient.ecog": "ECOG", "patient.height_cm": "키", "patient.weight_kg": "몸무게",
    "neoadjuvant_response.pcr": "pCR", "neoadjuvant_response.rcb": "RCB", "recurrence.status": "재발",
    "patient.cardiac_history": "심장 병력", "patient.comorbidities": "동반질환", "patient.lvef_percent": "LVEF",
    "patient.visceral_crisis": "장기 위기", "patient.mediastinal_radiation": "종격동 방사선",
    "recurrence.recurrence_date": "재발일", "recurrence.recurrence_day": "재발일 (day)", "recurrence.metastasis_day": "전이일 (day)",
    "recurrence.metastatic_sites": "전이 부위", "recurrence.adjuvant_endocrine_end_date": "보조 ET 종료일",
    "recurrence.surgery": "재발 수술", "recurrence.surgery_intent": "재발 수술 목적",
}
GENE_RESULT = {"detected": "검출", "not_detected": "검출되지 않음"}
IMAGING = {"bone_scan": "뼈 스캔", "CT": "CT", "MRI": "MRI", "PET": "PET", "ultrasound": "초음파", "X-ray": "X선", "other": "기타"}
TREATMENT = {"neoadjuvant": "선행 투약", "adjuvant": "보조 투약", "metastatic": "고식적 투약"}
CERTAINTY = {"confirmed": "확정", "suspected": "의심", "equivocal": "불확실"}
SKIP_PS = {"stage.disease_extent"}   # 코드가 정한 값이라 병기 범주 칸의 근거로 보여준다


def vlabel(key: str, v) -> str:
    if v is None:
        return "없음"
    if isinstance(v, list):
        return ", ".join(vlabel(key, x) for x in v) or "없음"
    if isinstance(v, dict):
        return " · ".join(f"{k} {vlabel(key, x)}" for k, x in v.items())
    return VALUE_LABELS.get(f"{key}:{v}", VALUE_LABELS.get(str(v), str(v)))


def control(rule: dict) -> dict:
    """스키마 규칙 → 화면 입력 방식. enum = 선택, number = 숫자 (+ 고정 값), multi = 여러 개 선택, pair = 고위험 두 칸."""
    if "enum" in rule:
        return {"kind": "enum", "options": rule["enum"]}
    pattern = re.fullmatch(r"\^\((.+)\)\$", rule.get("pattern", ""))
    if rule.get("type") == "string" and pattern:
        return {"kind": "enum", "options": pattern.group(1).split("|")}
    if rule.get("type") in ("integer", "number"):
        return {"kind": "number", "consts": []}
    if "oneOf" in rule:
        nums = [r for r in rule["oneOf"] if r.get("type") in ("integer", "number")]
        consts = [r["const"] for r in rule["oneOf"] if "const" in r]
        if nums:
            return {"kind": "number", "consts": consts}
    if rule.get("type") == "object" and set(rule.get("required", [])) == {"hira", "esmo"}:
        return {"kind": "pair", "parts": {k: rule["properties"][k]["enum"] for k in ("hira", "esmo")}}
    if rule.get("type") == "array" and rule.get("items", {}).get("type") == "string":
        return {"kind": "multi"}
    return {"kind": "json"}


def metastatic_site_codes() -> list[str]:
    with open(FIELD_VOCAB, encoding="utf-8-sig", newline="") as f:
        codes = [r["canonical"] for r in csv.DictReader(f) if r["field"] == "metastatic_sites"]
    return list(dict.fromkeys(codes)) + ["other"]


def load_bm():
    spec = importlib.util.spec_from_file_location("bm", ROOT / "src" / "biomarker" / "BM1_ER,PR,HER2,Ki_67,subtype.py")
    bm = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("bm", bm)
    spec.loader.exec_module(bm)
    return bm


# ----------------------------------------------------------------------------------------------------
# 오른쪽 칸: 적용 여부, 필수, A 묶음 (처리해야 처방 가능), 자동 연결 제안
# ----------------------------------------------------------------------------------------------------

def _confirmed(items: dict, key: str):
    it = c.items_get(items, key)
    return it.get("confirmed") if it else None


def rows(items: dict) -> list[dict]:
    """지금 확정값으로 본 칸 목록. 맞지 않는 칸도 빼지 않고 applies=False와 이유를 단다."""
    x = {"sub": _confirmed(items, "subtype"), "dis": _confirmed(items, "setting.disease"),
         "phase": _confirmed(items, "setting.phase"), "prior": bool(_confirmed(items, "prior_regimens")),
         "er": _confirmed(items, "markers.ER")}
    schema_req = set(c.required_items(items))
    out = []
    for key, group, when, why, req in ROWS:
        if c.items_get(items, key) is None:
            continue
        applies = when is None or bool(when(x))
        out.append({"key": key, "group": group, "applies": applies, "na": "" if applies else why,
                    "required": applies and (req or key in schema_req)})
    return out


def screen_missing(items: dict) -> list[str]:
    return [r["key"] for r in rows(items) if r["required"] and _confirmed(items, r["key"]) is None]


def attention(items: dict, patient_state: dict) -> dict[str, str]:
    """처음 불러올 때 A 묶음에 올릴 칸과 이유 (필수인데 빈 칸, 판정 불가, 값 충돌). 화면은 이 목록을 끝까지 유지한다."""
    out = {}
    for cf in patient_state.get("conflicts") or []:
        key = CONFLICT_ITEM.get(cf["field"])
        if key:
            vals = " / ".join(str(v.get("raw")) for v in cf.get("candidates") or [])
            out[key] = f"값 충돌: {vals}"
    for r in rows(items):
        if not r["applies"] or r["key"] in out:
            continue
        it = c.items_get(items, r["key"])
        if it.get("system") == "unknown":
            out[r["key"]] = "규칙으로 판정 불가"
        elif r["required"] and it.get("confirmed") is None:
            out[r["key"]] = "기록 없음" if it.get("system") in (None, "not_recorded") else "규칙 값이 확정 형식에 없음"
    return out


def drop_not_applicable(draft: dict) -> dict:
    """해당 없는 선택 칸은 확정 파일에 남기지 않는다 (스키마 필수 칸은 그대로)."""
    items, schema_req = draft["items"], set(c.required_items(draft["items"]))
    for r in rows(items):
        if not r["applies"] and r["key"] not in schema_req:
            c.items_get(items, r["key"])["confirmed"] = None
    return draft


def hints(items: dict, subtype_of) -> dict:
    """자동 연결 (설계 §4.4 표): 고른 값과 다르면 화면이 경고만 한다."""
    out = {}
    er, pr, her2 = (_confirmed(items, f"markers.{m}") for m in ("ER", "PR", "HER2"))
    if er and pr and her2:
        sub = subtype_of(er, pr, her2)
        if sub and sub != _confirmed(items, "subtype"):
            out["subtype"] = {"value": sub, "text": f"ER·PR·HER2로 보면 {sub}"}
    group = _confirmed(items, "stage.group")
    if group:
        dis = "metastatic" if group == "IV" else "locally_advanced" if group.startswith("III") else \
            "early" if group.startswith("I") else None
        if dis and dis != _confirmed(items, "setting.disease"):
            out["setting.disease"] = {"value": dis, "text": f"병기군 {group}로 보면 {vlabel('setting.disease', dis)}"}
    return out


# ----------------------------------------------------------------------------------------------------
# 왼쪽 검사 결과 (원문), 칸별 AI 근거, 경고 띠
# ----------------------------------------------------------------------------------------------------

def _cells(node: dict, prefix: str = ""):
    for k, v in node.items():
        path = f"{prefix}{k}"
        if not isinstance(v, dict):
            continue
        if "status" in v and "source" in v:
            yield path, v
            for h in v.get("history") or []:
                yield path, h
        else:
            yield from _cells(v, path + ".")


def _list_cells(fields: dict):
    """칸이 아닌 목록(영상 소견, 투약)도 원문 위치가 있으면 왼쪽에 보인다. (경로, 칸 모양 dict)."""
    for f in fields.get("imaging_findings") or []:
        sites = vlabel("", f.get("sites") or [])
        yield f"imaging:{f.get('modality')}", {**f, "raw": (f.get("source") or {}).get("quote"),
                                                "observed_date": f.get("date"),
                                                "note": f"{sites} · {CERTAINTY.get(f.get('certainty'), f.get('certainty'))}"}
    for t in fields.get("treatment_history") or []:
        yield f"treatment:{t.get('setting')}", {**t, "raw": (t.get("source") or {}).get("quote"), "observed_date": t.get("start_date")}


def _raw_text(path: str, cell: dict) -> str:
    """원문 표기. 유전자 칸은 인용이 "검출되지 않음" 아래의 유전자 이름 나열뿐이라, 미검출이면 판정만 쓰고
    검출이면 판정 뒤에 변이 원문을 붙인다."""
    raw = cell.get("raw") or (cell.get("source") or {}).get("quote") or ""
    if path.startswith("molecular.") and cell.get("result"):
        result = GENE_RESULT.get(cell["result"], cell["result"])
        return result if cell["result"] == "not_detected" else f"{result} · {raw}"
    return raw


def _label(path: str) -> str:
    kind, _, sub = path.partition(":")
    if kind == "imaging":
        return f"영상 {IMAGING.get(sub, sub)}"
    if kind == "treatment":
        return TREATMENT.get(sub, "투약")
    return PS_LABELS.get(path, path.split(".")[-1])


def documents(chart: str, patient_state: dict) -> list[dict]:
    """문서마다 원문과, 그 문서에서 읽은 칸 (원문 표기 그대로)."""
    docs = [{"doc_id": d.doc_id, "doc_type": d.doc_type, "type_label": DOC_TYPES.get(d.doc_type, d.doc_type),
             "doc_date": d.doc_date, "start": d.start, "text": d.text, "values": []} for d in split(chart)]
    by_id = {d["doc_id"]: d for d in docs}
    seen = set()
    fields = patient_state.get("fields") or {}
    conflicted = [(cf["field"], cand) for cf in patient_state.get("conflicts") or [] for cand in cf.get("candidates") or []]
    for path, cell in [*_cells(fields), *_list_cells(fields), *conflicted]:
        src = cell.get("source") or {}
        if path in SKIP_PS or src.get("doc_id") not in by_id or src.get("char_start") is None:
            continue
        if (path, src["char_start"]) in seen:
            continue
        seen.add((path, src["char_start"]))
        by_id[src["doc_id"]]["values"].append({
            "label": _label(path), "raw": _raw_text(path, cell), "note": cell.get("note") if path.startswith("imaging:") else None,
            "status": cell.get("status"), "specimen": cell.get("specimen"), "observed_date": cell.get("observed_date"),
            "start": src["char_start"], "end": src["char_end"]})
    for d in docs:
        d["values"].sort(key=lambda v: v["start"])
    return docs


def _day_date(patient_state: dict, day):
    dx = ((patient_state.get("fields") or {}).get("diagnosis") or {}).get("diagnosis_date") or {}
    if day is None or dx.get("status") != "present" or not isinstance(dx.get("value"), str) or len(dx["value"]) != 10:
        return None
    return (date.fromisoformat(dx["value"]) + timedelta(days=day)).isoformat()


def _raw(cell) -> str | None:
    return cell.get("raw") if isinstance(cell, dict) and cell.get("status") == "present" else None


def reasons(patient_state: dict, br: dict, draft: dict) -> dict[str, str]:
    """칸마다 AI 값의 근거 한 줄 (B 판정 이유·규칙 ID, A 계산식, 원문 표기). 칸 아래 "AI:" 옆에 붙인다."""
    recs = {r["marker"]: r for r in br.get("records") or []}
    items, fields = draft["items"], patient_state.get("fields") or {}
    stage, patient = fields.get("stage") or {}, fields.get("patient") or {}
    setting = br.get("setting") or {}
    out = {}
    for m in ("ER", "PR", "HER2", "Ki-67", "PD-L1"):
        r = recs.get(m)
        if r:
            out[f"markers.{m}"] = f"{r.get('reason', '')} ({r.get('rule_id', '')})"
    gb = (items.get("markers") or {}).get("gBRCA")
    if gb:
        out["markers.gBRCA"] = f"BRCA1·2 합침: {gb.get('note') or ''}"
    st = {m: (recs.get(m) or {}).get("status") for m in ("ER", "PR", "HER2")}
    out["subtype"] = f"ER {vlabel('', st['ER'])} · PR {vlabel('', st['PR'])} · HER2 {vlabel('', st['HER2'])} → 4종 (B, PROJECT.md §5)"
    ext = stage.get("disease_extent") or {}
    out["setting.disease"] = setting.get("reason", "") + (f" · 병기 원문 {ext['raw']}" if _raw(ext) else "")
    phase = c.items_get(items, "setting.phase") or {}
    out["setting.phase"] = f"규칙: {phase.get('note') or ''}. 수술 시점은 시스템이 고를 근거가 없어 수술 기록 유무로 정함"
    tnm = stage.get("ptnm") if _raw(stage.get("ptnm")) else stage.get("ctnm")
    t_it, n_it = c.items_get(items, "stage.t") or {}, c.items_get(items, "stage.n") or {}
    basis = {"p": "병리 병기", "c": "임상 병기"}.get((t_it.get("detail") or {}).get("basis"), "")
    if _raw(tnm):
        out["stage.t"] = f"{basis} 원문 {tnm['raw']}"
        n = ((tnm.get("value") or {}).get("n")) or ""
        out["stage.n"] = f"{basis} {n} → N0 음성 / N1mi 이상 양성 / NX 평가 안됨"
    if _raw(stage.get("group")):
        out["stage.group"] = f"원문 {stage['group']['raw']}"
    if _raw(stage.get("positive_ln_count")):
        out["stage.positive_ln_count"] = f"원문 {stage['positive_ln_count']['raw']} (양성 / 검사)"
    if _raw((fields.get("diagnosis") or {}).get("grade")):
        out["grade"] = f"원문 {fields['diagnosis']['grade']['raw']}"
    meno = patient.get("menopausal_status")
    if _raw(meno):
        b = _raw(patient.get("menopausal_basis"))
        out["menopausal_status"] = f"원문 {meno['raw']}" + (f" · 근거 {b}" if b else "") + \
            (" · 이행기는 폐경 전으로 봄" if (meno.get("value") == "perimenopausal") else "")
    hr = c.items_get(items, "high_risk_early")
    if hr:
        out["high_risk_early"] = (f"재발 고위험군이면 보조 내분비요법에 abemaciclib(CDK4/6 억제제)를 더한다. 급여(공고 9장 2 주2): 양성 림프절 4개↑, "
                                  f"또는 1~3개 + (T3↑ 또는 3등급) · ESMO(E08): 급여 조건 또는 1~3개 + Ki-67 20%↑. {hr.get('note') or ''}")
    sites = c.items_get(items, "metastatic_sites")
    if sites and sites.get("system") is not None:
        out["metastatic_sites"] = "재발·병기 기록의 전이 부위"
    if setting.get("disease") == MET:
        why = setting.get("reason", "").split(" / ")
        out["setting.line_endocrine"] = next((w for w in why if "내분비" in w), "")
        out["setting.line_chemo"] = next((w for w in why if "항암" in w), "")
    return out


def summary(key: str, v) -> str | None:
    """선택창 없이 보여 주는 칸(이전 요법, 차수 간주, 누적 용량)의 한 줄 요약."""
    if v is None:
        return None
    if key == "prior_regimens":
        return " / ".join(f"{'+'.join(r['drugs'])} ({vlabel('', r.get('setting'))}"
                          f"{', 내분비 ' + str(r['line_endocrine']) + '차' if r.get('line_endocrine') else ''}"
                          f"{', 항암 ' + str(r['line_chemo']) + '차' if r.get('line_chemo') else ''}"
                          f"{', ' + str(r['response']) if r.get('response') not in (None, 'unknown') else ''})" for r in v) or "없음"
    if key == "deemed_lines":
        return ", ".join(f"{k} {vlabel('', s)}" for k, s in v.items()) or "없음"
    if key == "anthracycline_cumulative":
        return ", ".join(f"{d} {x['value']} mg/m2" if isinstance(x, dict) else f"{d} {vlabel('', x)}"
                         for d, x in v.items()) or "받지 않음"
    return None


def warnings(patient_state: dict, br: dict) -> list[dict]:
    """경고 띠 (설계 §9.2): 값 충돌, 결과 대기·예정 검사, 검사 권고."""
    out = []
    for cf in patient_state.get("conflicts") or []:
        vals = ", ".join(str(x.get("raw")) for x in cf.get("candidates") or [])
        out.append({"kind": "값 충돌", "text": f"{PS_LABELS.get(cf['field'], cf['field'])}: {vals}. 확인 필요"})
    for path, cell in _cells(patient_state.get("fields") or {}):
        if cell.get("status") == "not_done" and cell.get("raw"):
            out.append({"kind": "결과 대기", "text": f"{PS_LABELS.get(path, path)} {cell['raw']}"})
    for t in br.get("tests_needed") or []:
        out.append({"kind": "검사 권고", "text": f"{t['test']}: {t['reason']}"})
    return out


class App:
    def __init__(self, cases_dir: Path, save_dir: Path, app_dir: Path | None = None, model: str = s2.DEFAULT_MODEL,
                 llm_host: str | None = None):
        self.cases_dir, self.save_dir = cases_dir, save_dir
        self.decision_dir = (app_dir / "decisions") if app_dir else s2.DECISION_DIR
        self.recommender = s2.Recommender(None, model, (app_dir / "recommendations") if app_dir else s2.REC_DIR, llm_host)
        self._bm = None
        self._drugs = None
        self.controls = {k: control(r) for k, r in c.item_rules().items()}
        self.controls["metastatic_sites"]["options"] = metastatic_site_codes()

    @property
    def bm(self):
        self._bm = self._bm or load_bm()
        self.recommender.bm = self._bm
        return self._bm

    def patient_state(self, case: str) -> dict:
        if case not in self.cases():
            raise KeyError(f"없는 사례: {case}")
        with open(self.cases_dir / case / "expected" / "patient_state.json", encoding="utf-8") as f:
            return json.load(f)

    # ---------- 화면 2 ----------
    def screen2(self, case: str, version: int) -> dict:
        """확정 파일 + 추천 진행 상태 + 기타 처방 약 목록."""
        ps = self.patient_state(case)
        doc = s2.load_confirmed(self.save_dir, ps["patient_ref"], version)
        self._drugs = self._drugs or s2.drug_list()
        _ = self.bm
        return {"confirmed": doc, "rec": self.recommender.status(ps["patient_ref"], version), "drugs": self._drugs,
                "decisions": sorted(p.name for p in (self.decision_dir / ps["patient_ref"]).glob("v*.json")),
                "versions": [p.name for p in c._versions(ps["patient_ref"], self.save_dir)]}

    def rec_start(self, case: str, version: int, force: bool = False) -> dict:
        ps = self.patient_state(case)
        doc = s2.load_confirmed(self.save_dir, ps["patient_ref"], version)
        _ = self.bm
        return self.recommender.start(ps["patient_ref"], version, doc, ps, force)

    def cases(self) -> list[str]:
        return sorted(p.parents[1].name for p in self.cases_dir.glob("*/expected/patient_state.json"))

    def draft(self, case: str) -> dict:
        if case not in self.cases():
            raise KeyError(f"없는 사례: {case}")
        folder = self.cases_dir / case
        with open(folder / "expected" / "patient_state.json", encoding="utf-8") as f:
            ps = json.load(f)
        if (folder / "expected" / "biomarker_record.json").exists():
            with open(folder / "expected" / "biomarker_record.json", encoding="utf-8") as f:
                br = json.load(f)
        else:
            br = self.bm.assess(ps)
        chart = (folder / "chart.txt").read_text(encoding="utf-8") if (folder / "chart.txt").exists() else ""
        draft = c.build_draft(ps, br)
        index_day = ps.get("index_day")
        return {**self.state(draft),
                "saved": [p.name for p in c._versions(ps["patient_ref"], self.save_dir)],
                "header": {"index_day": index_day, "index_date": _day_date(ps, index_day)},
                "attention": attention(draft["items"], ps),
                "documents": documents(chart, ps), "reasons": reasons(ps, br, draft), "warnings": warnings(ps, br)}

    def state(self, draft: dict) -> dict:
        """초안이 바뀔 때마다 화면이 다시 받는 것: 초안, 칸 목록, 자동 연결 제안, 빈 필수 칸, 요약 표시."""
        items = draft["items"]
        shown = {k: summary(k, _confirmed(items, k)) for k in ("prior_regimens", "deemed_lines", "anthracycline_cumulative")}
        return {"draft": draft, "rows": rows(items), "hints": hints(items, self.bm.subtype_of),
                "missing": screen_missing(items), "summary": {k: v for k, v in shown.items() if v is not None}}

    def meta(self) -> dict:
        return {"labels": LABELS, "value_labels": VALUE_LABELS, "controls": self.controls, "cases": self.cases()}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):   # 요청 기록에 환자 ID가 남지 않게 끈다
            pass

        def do_GET(self):
            url = urlparse(self.path)
            try:
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                if url.path == "/":
                    self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/screen2":
                    self._send(200, HTML2.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/screen2":
                    self._send(200, app.screen2(q.get("case", ""), int(q.get("version", 0))))
                elif url.path == "/api/rec/status":
                    ps = app.patient_state(q.get("case", ""))
                    self._send(200, app.recommender.status(ps["patient_ref"], int(q.get("version", 0))))
                elif url.path == "/api/meta":
                    self._send(200, app.meta())
                elif url.path == "/api/draft":
                    self._send(200, app.draft(parse_qs(url.query).get("case", [""])[0]))
                else:
                    self._send(404, {"error": "없는 주소"})
            except (KeyError, ValueError) as e:
                self._send(404, {"error": str(e)})

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/set":
                    self._send(200, app.state(c.set_item(body["draft"], body["key"], body.get("value"), body.get("reason"))))
                elif self.path == "/api/finalize":
                    by = (body.get("confirmed_by") or "").strip()
                    draft = body["draft"]
                    errors = [] if by else ["확정자 ID를 입력하세요 (가명 ID)"]
                    errors += [f"{k}: 필수 칸이 비어 있음" for k in screen_missing(draft["items"])]
                    if errors:
                        self._send(200, {"errors": errors})
                        return
                    memo = (body.get("memo") or "").strip()
                    if memo:
                        draft["memo"] = memo
                    path, doc, errors = c.finalize(drop_not_applicable(draft), by, save_dir=app.save_dir)
                    self._send(200, {"errors": errors, "doc": doc, "path": str(path) if path else None})
                elif self.path == "/api/rec/start":
                    self._send(200, app.rec_start(body["case"], int(body["version"]), bool(body.get("force"))))
                elif self.path == "/api/decision":
                    ps = app.patient_state(body["case"])
                    doc = s2.load_confirmed(app.save_dir, ps["patient_ref"], int(body["version"]))
                    rec = app.recommender.status(ps["patient_ref"], int(body["version"]))
                    path, out, errors = s2.save_decision(body, doc, rec, app.decision_dir)
                    self._send(200, {"errors": errors, "doc": out, "path": str(path) if path else None})
                else:
                    self._send(404, {"error": "없는 주소"})
            except (KeyError, ValueError, TypeError) as e:
                self._send(400, {"error": f"{type(e).__name__}: {e}"})

    return Handler


def main():
    ap = argparse.ArgumentParser(description="화면 1 처방 조건 확인 + 화면 2 처방 추천·선택 로컬 서버")
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--save-dir", type=Path, default=c.SAVE_DIR, help="확정 파일 (confirmed_state) 폴더")
    ap.add_argument("--app-dir", type=Path, default=None, help="추천·처방 결정 폴더 (기본 data/app)")
    ap.add_argument("--model", default=s2.DEFAULT_MODEL, help="추천 LLM (llm/config.toml에 [recommend]가 없을 때)")
    ap.add_argument("--llm-host", default=None, help="추천 LLM 주소. GPU 서버는 SSH 터널을 연 뒤 http://127.0.0.1:11435")
    args = ap.parse_args()
    app = App(args.cases.resolve(), args.save_dir.resolve(), args.app_dir.resolve() if args.app_dir else None, args.model,
              args.llm_host)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    print(f"화면 1: http://127.0.0.1:{args.port}  (사례 {len(app.cases())}개, 저장 {app.save_dir})")
    server.serve_forever()


if __name__ == "__main__":
    main()
