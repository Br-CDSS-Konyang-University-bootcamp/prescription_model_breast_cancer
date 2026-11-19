"""G 관문: 처방 모듈(mini) 입력 규칙에 맞는지. 실패하면 mini를 고치지 않고 생성기를 고치거나 환자를 뺀다 (notes/design.md §11.2)."""
from __future__ import annotations

import importlib.util
import json
import re
from functools import lru_cache

from src.virtual_hospital.common import MINI, Patient, boundary, mini_on_path, read_csv

CATEGORICAL_INT = {"diagnosis.grade", "patient.ecog"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MARKERS = {"ER": "receptors.er_percent", "PR": "receptors.pr_percent", "Ki-67": "proliferation.ki67_percent"}


def get(ps: dict, path: str):
    e = ps["fields"]
    for k in path.split("."):
        if not isinstance(e, dict) or k not in e:
            return None
        e = e[k]
    return e


# ---------- G1 스키마·같음 ----------
def g1(p: Patient, ps: dict, check_errors: list[str]) -> list[str]:
    errs = [f"mini check: {e}" for e in check_errors]
    for path, r in p.recs.items():
        e = get(ps, path)
        if e is None:
            errs.append(f"{path}: 정답에 칸 없음")
            continue
        if e.get("status") != r.status:
            errs.append(f"{path}: status {e.get('status')} != {r.status}")
        elif r.status == "present":
            if path.startswith("molecular."):
                got = (e.get("result"), [v.get("protein_change") for v in e.get("variants", [])])
                want = (r.value["result"], [v.get("protein_change") for v in r.value["variants"]])
            else:
                got, want = e.get("value"), r.value
            if json.dumps(got, sort_keys=True) != json.dumps(want, sort_keys=True):
                errs.append(f"{path}: 값 {got} != {want}")
    for g, grp in ps["fields"].items():                     # CSV에 없는 칸이 차트에 들어가면 안 된다
        if not isinstance(grp, dict):
            continue
        for k, e in grp.items():
            path = f"{g}.{k}"
            if isinstance(e, dict) and e.get("status") == "present" and path not in p.recs:
                errs.append(f"{path}: CSV에 없는 칸이 차트에 있음")
    return errs


# ---------- G2 사전 ----------
@lru_cache(maxsize=1)
def vocab() -> dict[str, set]:
    out: dict[str, set] = {}
    for r in read_csv(MINI / "data" / "dictionaries" / "field_vocab.csv"):
        out.setdefault(r["field"], set()).add(r["canonical"])
    return out


def g2(p: Patient) -> list[str]:
    errs = []
    for field, allowed in vocab().items():
        if field in p.recs:
            r, key = p.recs[field], None
        else:
            path, _, key = field.rpartition(".")
            r = p.recs.get(path)
        if r is None or r.status != "present":
            continue
        v = r.value.get(key) if key and isinstance(r.value, dict) else (None if key else r.value)
        if v is None or isinstance(v, (dict, list)):
            continue
        if str(v) not in allowed:
            errs.append(f"{field}: '{v}'가 field_vocab에 없음")
    return errs


# ---------- G3 범위 ----------
def g3(p: Patient) -> list[str]:
    errs = []
    if p.recs["patient.gender"].value != "FEMALE":
        errs.append("남성 (범위 외)")
    if p.recs["diagnosis.histology"].value in ("DCIS", "phyllodes"):
        errs.append("비침윤성·엽상종양 (범위 외)")
    return errs


# ---------- G4 일관성 (V4 관계 규칙) ----------
def g4(p: Patient, ps: dict) -> list[tuple[str, str]]:
    """(위반, 원인 origin)."""
    out = []
    age, meno = p.recs["patient.age"].value, p.recs["patient.menopausal_status"]
    if (meno.value == "premenopausal" and age >= 70) or (meno.value == "postmenopausal" and age < 30):
        out.append((f"나이 {age}와 폐경 {meno.value}", meno.origin))
    group, extent = p.recs["stage.group"].value, p.recs["stage.disease_extent"].value
    want = "early" if group.startswith(("I", "II")) and not group.startswith("III") else \
        "locally_advanced" if group.startswith("III") else None
    if want and extent != want:
        out.append((f"병기군 {group}와 병기 범주 {extent}", "real"))
    if p.branch == "TCGA_postop" and ps["fields"].get("treatment_history"):
        out.append(("판정 기준일 뒤 투약이 차트에 있음", "derived"))
    if p.branch == "TCGA_postop" and get(ps, "recurrence.status").get("value") != "none":
        out.append(("수술 직후 차트에 재발이 있음", "derived"))
    if p.branch == "TCGA_recur":
        late = [t for t in ps["fields"].get("treatment_history") or [] if (t.get("start_day") or 0) > ps["index_day"]]
        if late:
            out.append((f"판정 기준일 뒤 시작한 투약 {len(late)}줄이 차트에 있음", "derived"))
    days = [d["doc_date"] for d in ps["documents"] if d["doc_type"] != "medication"]   # 투약 기록은 날짜 없음 (VC 형식)
    if any(x is None for x in days) or days[0] != max(days):
        out.append(("문서 날짜 순서 (경과기록이 가장 늦어야 함)", "derived"))
    return out


# ---------- G5 경계 거리 ----------
def g5(p: Patient) -> list[str]:
    errs = []
    for path in ("receptors.er_percent", "receptors.pr_percent"):
        r = p.recs[path]
        if r.origin == "synthetic" and ("range" in r.value or "percent" in r.value):
            lo, hi = boundary(path.split(".")[1])
            a, b = r.value["range"] if "range" in r.value else (r.value["percent"],) * 2
            if not (b < lo or a > hi):
                errs.append(f"{path} 합성 값 {a}-{b}이 경계 {lo}-{hi}에 걸침")
    r = p.recs["proliferation.ki67_percent"]
    lo, hi = boundary("ki67_percent")
    if r.origin == "synthetic" and lo <= r.value["percent"] <= hi:
        errs.append(f"Ki-67 합성 {r.value['percent']}%가 경계 {lo}-{hi}에 있음")
    return errs


# ---------- G6 봉투 ----------
def sig(path: str, e: dict) -> set:
    """칸 하나의 모양 조각들. 묶음 값(pTNM 등)은 키 목록과 키별 값으로 나눠, 조합 전체가 아니라 조각마다 본다
    (2026-11-10: 조합 전체로 보면 실제 TCGA 값의 새 조합 'pT1c N1 M0 6th'까지 빠졌다)."""
    st = e.get("status")
    if st != "present":
        return {(path, st)}
    if path.startswith("molecular."):
        return {(path, e.get("result"))}
    v = e.get("value")
    if isinstance(v, dict):
        return {(path, "keys", tuple(sorted(v)))} | {(path, k, x) for k, x in v.items() if isinstance(x, str)}
    if isinstance(v, list):
        return {(path, "list")}
    if isinstance(v, int) and not isinstance(v, bool):
        return {(path, v) if path in CATEGORICAL_INT else (path, "int")}
    if isinstance(v, str) and DATE.fullmatch(v):
        return {(path, "date")}
    return {(path, v)}


def walk_sigs(ps: dict) -> set:
    out = set()
    for g, grp in ps["fields"].items():
        if not isinstance(grp, dict):
            continue
        for k, e in grp.items():
            if isinstance(e, dict) and "status" in e:
                out |= sig(f"{g}.{k}", e)
            elif isinstance(e, dict):
                for kk, ee in e.items():
                    if isinstance(ee, dict) and "status" in ee:
                        out |= sig(f"{g}.{k}.{kk}", ee)
    return out


def envelope(tcga_pss: dict[str, dict]) -> set:
    """기존 가상 차트 정답 + mini TCGA 변환 결과에 나온 (칸, 값 모양) 조합."""
    out = set()
    for f in (MINI / "tests" / "fixtures" / "virtual_charts").rglob("expected/patient_state.json"):
        out |= walk_sigs(json.loads(f.read_text(encoding="utf-8")))
    for ps in tcga_pss.values():
        out |= walk_sigs(ps)
    return out


# 기존 차트에는 없었지만 mini 규칙이 이미 정해 둔 값 (근거를 함께 적는다, rules.csv G-06)
ALLOW = {
    ("receptors.her2_ish", "method", "unknown"),           # mini pipeline._her2_ish: 방법 단어가 없으면 unknown
    ("proliferation.ki67_percent", "keys", ("range",)),    # mini PROJECT.md §5 Ki-67: percent → range → result 순서
}


def tnm_shared(atoms: set) -> set:
    """cTNM·pTNM·ypTNM의 T·N·M 범주는 같은 말이다 (예: pT1b가 있었으면 cT1b도 본 적 있는 값)."""
    out = set(atoms)
    for a in atoms:
        if a[0] in ("stage.ctnm", "stage.ptnm", "stage.yptnm") and len(a) == 3 and a[1] in ("t", "n", "m"):
            out |= {(q, a[1], a[2]) for q in ("stage.ctnm", "stage.ptnm", "stage.yptnm")}
    return out


def g6(ps: dict, env: set) -> list[str]:
    return [f"없던 조합 {s}" for s in sorted(walk_sigs(ps) - tnm_shared(env) - ALLOW, key=str)]


# ---------- G7 시험 실행 (빠른) ----------
@lru_cache(maxsize=1)
def biomarker():
    mini_on_path()
    spec = importlib.util.spec_from_file_location("mini_bm", MINI / "src" / "biomarker" / "BM1_ER,PR,HER2,Ki_67,subtype.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def g7(p: Patient, ps: dict) -> tuple[list[str], dict | None]:
    try:
        rec = biomarker().assess(ps)
    except Exception as ex:                                  # noqa: BLE001 — 오류 자체가 관문 결과
        return [f"B assess 오류: {type(ex).__name__}: {ex}"], None
    errs = []
    status = {r["marker"]: r["status"] for r in rec["records"]}
    for m, path in MARKERS.items():
        if p.recs[path].origin == "synthetic" and status.get(m) == "unknown":
            errs.append(f"합성 {path} 때문에 B {m} unknown")
    return errs, rec


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in ("raw", "note")}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in a.keys() | b.keys() for d in _diff(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def g7_input(text: str, ps: dict) -> list[str]:
    """입력 모듈 규칙 단계: LLM 자리에 정답 후보를 넣으면 정답이 다시 나와야 한다 (mini tests/input/test_input_pipeline.py와
    같은 방식). 실패하면 그 표기를 입력 모듈 정규화(IN-3)가 못 읽는다는 뜻이다."""
    mini_on_path()
    from src.input.script.evaluation import from_expected
    from src.input.script.pipeline import run as run_input
    try:
        got, issues = run_input(text, lambda docs: from_expected(ps), patient_ref=ps["patient_ref"],
                                created_at=ps["created_at"])
    except Exception as ex:                                  # noqa: BLE001
        return [f"입력 모듈 오류: {type(ex).__name__}: {ex}"]
    return [f"입력 모듈 issue: {i}" for i in issues] + [f"입력 모듈 재현 차이 {d}" for d in _diff(_strip(got), _strip(ps))]


def run(p: Patient, ps: dict, check_errors: list[str], env: set, text: str = "") -> dict:
    """환자 한 명의 관문 결과. failed가 비어 있어야 세트에 들어간다."""
    res = {"G1": g1(p, ps, check_errors), "G2": g2(p), "G3": g3(p)}
    v4 = g4(p, ps)
    res["G4"] = [f"{m} ({o})" for m, o in v4]
    res["G5"], res["G6"] = g5(p), g6(ps, env)
    res["G7"], rec = g7(p, ps)
    if text:
        res["G7"] += g7_input(text, ps)
    res["failed"] = [k for k in ("G1", "G2", "G3", "G4", "G5", "G6", "G7") if res[k]]
    res["real_cause"] = any(o == "real" for _, o in v4) or bool(res["G2"]) or bool(res["G3"])
    res["biomarker"] = rec
    return res
