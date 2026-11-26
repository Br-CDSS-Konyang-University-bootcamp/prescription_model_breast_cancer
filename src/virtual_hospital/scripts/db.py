"""가상 병원 DB (SQLite): 각자 컴퓨터에서 만들어, 처방 흐름·입력 모듈·이미지 모듈이 같은 함수로 환자를 꺼낸다.

DB 파일 data/virtual_hospital/local/virtual_hospital.db는 BCNB에서 만든 값을 담아 git에 넣지 않는다 (BCNB 약관:
원본·수정본 재배포 금지). git pull 뒤 각자 만든다:

    python -m src.virtual_hospital.scripts.db build      # 매번 처음부터 새로 만든다 (수십 초)
    python -m src.virtual_hospital.scripts.db info       # 들어 있는 개수

넣는 것 (있는 것만, 없으면 건너뛰고 알린다)
- TCGA ① 수술 후·② 재발: git의 data/virtual_hospital/tcga/, tcga_recur/
- BCNB 수술 전: data/virtual_hospital/local/bcnb/ (BCNB를 받아 python -m src.virtual_hospital.scripts.bcnb로 만든 것)
- 슬라이드: BCNB jpg (local/bcnb_raw/), TCGA 썸네일 (team_project_final). 원본 파일은 DB에 넣지 않고 경로만
- 슬라이드 벡터: local/features/<묶음>.npz (embed_slides.py로 GPU 서버에서 만든 것). 타일 벡터 .h5는 서버에 두고,
  필요하면 local/features/<묶음>/에 받아 tile_features()로 읽는다

읽기 (모든 모듈 공통)
    from src.virtual_hospital.scripts import db
    con = db.connect()
    db.find_patients(con, "10000043")                      # 병원 쪽: 등록번호·이름으로 찾기 (외래 날마다 한 줄)
    db.request_chart(con, "10000043", as_of="2028-08-28")   # 병원 쪽: 그날까지의 문서 (입력 모듈에 넣을 것)
    db.list_patients(con, branch="bcnb_preop", subtype="TNBC")
    db.get_state(con, "VH-B0002", "confirmed_state", allow_answer=True)   # 정답 (채점용)
    db.similar(con, "VH-B0002-S1", k=10)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path

import numpy as np

from src.virtual_hospital.scripts.common import BCNB_RAW, CODE, FEATURES, LOCAL, MINI, OUT, PROJECT, mini_on_path, read_csv

DB_PATH = LOCAL / "virtual_hospital.db"
SCHEMA = CODE / "db_schema.sql"
BRANCHES = {"tcga_postop": OUT / "tcga", "tcga_recur": OUT / "tcga_recur", "bcnb_preop": LOCAL / "bcnb"}
STATE_KINDS = ("patient_state", "biomarker_record", "confirmed_state")
# 슬라이드 벡터 묶음 이름 → (데이터셋, 파일 이름 → slide_id 찾는 방법)
FEATURE_SETS = {"tcga_hoptimus0": "TCGA-BRCA", "bcnb_hoptimus0": "BCNB"}


# ---------------------------------------------------------------- 만들기
def _confirmed(items: dict, key: str):
    return (items.get(key) or {}).get("confirmed")


def _patient_rows(branch: str, base: Path) -> list[dict]:
    """patients.csv + 정답 JSON에서 찾기용 요약 칸."""
    rows = []
    scene = {r["vp_id"]: r for r in read_csv(base / "patients.csv")} if (base / "patients.csv").exists() else {}
    for vp, r in scene.items():
        d = base / "charts" / vp
        if not (d / "chart.txt").exists():
            continue
        text = (d / "chart.txt").read_text(encoding="utf-8")
        states = {k: json.loads((d / "expected" / f"{k}.json").read_text(encoding="utf-8"))
                  for k in STATE_KINDS if (d / "expected" / f"{k}.json").exists()}
        ps, br = states.get("patient_state", {}), states.get("biomarker_record", {})
        items = states.get("confirmed_state", {}).get("items", {})
        stage = (ps.get("fields", {}).get("stage", {}).get("group") or {}).get("value")
        kind = {"endocrine": "내분비", "chemo": "항암"}.get(r.get("scene_kind"))
        rows.append({
            "vp_id": vp, "branch": branch, "dataset": "BCNB" if branch == "bcnb_preop" else "TCGA-BRCA",
            "dx_date": r.get("dx_date"), "index_day": int(r["index_day"]) if r.get("index_day") else None,
            "age": int(r["age"]) if r.get("age") else None, "sex": r.get("sex"),
            "subtype": (br.get("subtype") or {}).get("value") if isinstance(br.get("subtype"), dict) else br.get("subtype"),
            "stage_group": stage, "disease": _confirmed(items, "setting.disease"), "phase": _confirmed(items, "setting.phase"),
            "scene": f"고식 {kind} {r['scene_line']}차 결정" if kind else None,
            "registration_no": (m.group(1) if (m := re.search(r"등록번호:\s*(\d+)", text)) else None),
            "patient_name": (m.group(1) if (m := re.search(r"환자명:\s*(\S+)", text)) else None),
            "patient_ref": states["patient_state"]["patient_ref"],             # D-12: 장면 단위 (재발 장면은 -R)
            "_text": text, "_states": states, "_dir": base})
    return rows


def _documents(text: str) -> list[tuple]:
    """차트 → 문서 (doc_id, doc_type, doc_date, start, 본문). 나누기는 입력 모듈 IN-1 split을 불러 쓰기만 하고,
    본문은 다음 문서 시작 전까지의 원문 그대로라 이어 붙이면 차트와 같다."""
    mini_on_path()
    from src.input.script.pipeline import split
    docs = split(text)
    ends = [d.start for d in docs[1:]] + [len(text)]
    return [(d.doc_id, d.doc_type, d.doc_date, d.start, text[d.start:e]) for d, e in zip(docs, ends)]


def _rel(path: str, root: Path) -> str:
    """절대 경로 → 기준 폴더 상대 경로 (조원마다 폴더가 달라도 같은 값)."""
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def build(path: Path = DB_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    notes, count = [], {}
    for branch, base in BRANCHES.items():
        rows = _patient_rows(branch, base)
        if not rows:
            notes.append(f"{branch}: 없음 ({base})" + (" — BCNB를 받아 python -m src.virtual_hospital.scripts.bcnb를 먼저"
                                                       if branch == "bcnb_preop" else ""))
            continue
        cols = ["vp_id", "branch", "dataset", "dx_date", "index_day", "age", "sex", "subtype", "stage_group", "disease",
                "phase", "scene", "registration_no", "patient_name", "patient_ref"]
        con.executemany(f"INSERT INTO patients ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                        [[r[c] for c in cols] for r in rows])
        con.executemany("INSERT INTO charts VALUES (?,?,?)", [(r["vp_id"], branch, r["_text"]) for r in rows])
        con.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                        [(r["vp_id"], branch, *d) for r in rows for d in _documents(r["_text"])])
        con.executemany("INSERT INTO states VALUES (?,?,?,?)",
                        [(r["vp_id"], branch, k, json.dumps(v, ensure_ascii=False)) for r in rows for k, v in r["_states"].items()])
        keep = {r["vp_id"] for r in rows}
        fc = ["field", "status", "value", "origin", "basis", "rule_id", "source_column", "observed_date", "specimen", "note"]
        con.executemany(f"INSERT INTO fields VALUES (?,?,{','.join('?' * len(fc))})",
                        [[f["vp_id"], branch, *[f[c] for c in fc]] for f in read_csv(base / "fields.csv") if f["vp_id"] in keep])
        con.executemany("INSERT INTO truth VALUES (?,?,?,?)",
                        [(t["vp_id"], branch, t["항목"], t["값"]) for t in read_csv(base / "truth.csv") if t["vp_id"] in keep])
        if (base / "treatments.csv").exists():
            con.executemany("INSERT INTO treatments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            [(t["vp_id"], branch, t["drugs"], t["setting"], t["start_day"] or None, t["end_day"] or None,
                              t["stop_reason"] or None, t["stop_basis"], t["best_response"] or None,
                              t["endocrine_line (mini)"] or None, t["chemo_line (mini)"] or None)
                             for t in read_csv(base / "treatments.csv")])
        count[branch] = len(rows)
    _slides(con, notes)
    _features(con, notes)
    con.executemany("INSERT INTO meta VALUES (?,?)", [
        ("commit", subprocess.run(["git", "-C", str(MINI), "rev-parse", "--short", "HEAD"], capture_output=True,
                                  text=True).stdout.strip()),
        ("counts", json.dumps(count)), ("notes", json.dumps(notes, ensure_ascii=False))])
    con.commit()
    con.close()
    tmp.replace(path)
    return {"counts": count, "notes": notes}


def _slides(con, notes: list[str]) -> None:
    """TCGA: 공개 표 + local 원본 대응표(썸네일 경로). BCNB: local 표 (jpg는 bcnb_raw 상대 경로)."""
    pub = OUT / "tcga" / "images" / "slides.csv"
    priv = {r["slide_id"]: r for r in read_csv(LOCAL / "slide_map.csv")} if (LOCAL / "slide_map.csv").exists() else {}
    if pub.exists():
        if not priv:
            notes.append("TCGA 원본 슬라이드 대응표(local/slide_map.csv) 없음 → 썸네일·벡터 연결 안 함 (python -m src.virtual_hospital.scripts.build)")
        con.executemany("INSERT INTO slides VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            (r["slide_id"], r["vp_id"], r["dataset"], r["specimen"], "project" if r["slide_id"] in priv else None,
             priv.get(r["slide_id"], {}).get("thumb_path"), priv.get(r["slide_id"], {}).get("source_slide"),
             int(float(r["approx_w0"])) if r["approx_w0"] else None, int(float(r["approx_h0"])) if r["approx_h0"] else None,
             float(r["mpp"]) if r["mpp"] else None, r["stain_qc"], r["pen_qc"]) for r in read_csv(pub)])
    bimg = LOCAL / "bcnb" / "images"
    if (bimg / "slides.csv").exists():
        src = {r["vp_id"]: r["source_id"] for r in read_csv(LOCAL / "bcnb" / "source_map.csv")}
        con.executemany("INSERT INTO slides VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            (r["slide_id"], r["vp_id"], r["dataset"], r["specimen"], "bcnb_raw", f"WSIs/{Path(r['jpg']).name}",
             src.get(r["vp_id"]), int(r["width"]) if r["width"] else None, int(r["height"]) if r["height"] else None,
             float(r["mpp"]) if r["mpp"] else None, None, None) for r in read_csv(bimg / "slides.csv")])
        con.executemany("INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?,?)", [
            (a["ann_id"], a["slide_id"], a["vp_id"], a["kind"], a["origin"], _rel(a["file"], LOCAL),
             int(a["n_polygons"]), int(a["dropped_outside"]), a["rule_id"]) for a in read_csv(bimg / "annotations.csv")])


def _features(con, notes: list[str]) -> None:
    """local/features/<묶음>.npz → feature_sets + slide_embeddings. 파일 이름(원본 슬라이드 이름) → slide_id."""
    by_source = {}
    for sid, ds, source in con.execute("SELECT slide_id, dataset, source_slide FROM slides WHERE source_slide IS NOT NULL"):
        by_source[(ds, str(source))] = sid
    for name, ds in FEATURE_SETS.items():
        f = FEATURES / f"{name}.npz"
        if not f.exists():
            notes.append(f"슬라이드 벡터 {name}.npz 없음 (local/features/, embed_slides.py로 만들어 받을 것)")
            continue
        z = np.load(f, allow_pickle=False)
        hit = 0
        for i, nm in enumerate(z["names"]):
            sid = by_source.get((ds, str(nm)))
            if sid is None:
                continue                                            # 가상환자에 없는 슬라이드 (제외된 환자 등)
            mpp = float(z["mpp"][i])
            con.execute("INSERT INTO feature_sets VALUES (?,?,?,?,?,?,?,?,?,?)", (
                sid, name, str(z["encoder"][i]), int(z["tile_px"][i]) or None, int(z["input_px"][i]) or None,
                None if np.isnan(mpp) else mpp, int(z["n_tiles"][i]),
                int(z["n_tumor"][i]) if int(z["n_tumor"][i]) >= 0 else None, int(z["vectors"].shape[1]), f"{nm}.h5"))
            con.execute("INSERT INTO slide_embeddings VALUES (?,?,?,?,?)", (
                sid, name, str(z["pooling"][i]), int(z["vectors"].shape[1]), z["vectors"][i].astype("<f4").tobytes()))
            hit += 1
        notes.append(f"슬라이드 벡터 {name}: 파일 {len(z['names'])}장 중 가상환자 슬라이드 {hit}장")


# ---------------------------------------------------------------- 읽기
def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음 → python -m src.virtual_hospital.scripts.db build")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def list_patients(con, branch: str | None = None, **where) -> list[dict]:
    """예: list_patients(con, branch="bcnb_preop", subtype="TNBC"). 칸은 patients 표."""
    cond = {**({"branch": branch} if branch else {}), **where}
    sql = "SELECT * FROM patients" + (" WHERE " + " AND ".join(f"{k} = ?" for k in cond) if cond else "") + \
          " ORDER BY vp_id, branch"
    return [dict(r) for r in con.execute(sql, list(cond.values()))]


def _branch(con, vp_id: str, branch: str | None) -> str:
    rows = [r[0] for r in con.execute("SELECT branch FROM patients WHERE vp_id = ?", (vp_id,))]
    if not rows:
        raise KeyError(f"{vp_id} 없음")
    if branch is None:
        if len(rows) > 1:
            raise ValueError(f"{vp_id}는 장면이 {rows}에 있음 → branch를 줄 것")
        return rows[0]
    return branch


def get_chart(con, vp_id: str, branch: str | None = None) -> str:
    b = _branch(con, vp_id, branch)
    return con.execute("SELECT chart_text FROM charts WHERE vp_id = ? AND branch = ?", (vp_id, b)).fetchone()[0]


def get_state(con, vp_id: str, kind: str, branch: str | None = None, *, allow_answer: bool = False) -> dict:
    """kind: patient_state / biomarker_record / confirmed_state (정답, 판정 기준일 시점).
    병원 DB에는 없는 정답이라 allow_answer=True일 때만 꺼낸다 (채점, 정답 방식으로 B·C·D만 시험할 때)."""
    if not allow_answer:
        raise PermissionError("정답 JSON이다. 병원 쪽 입력은 request_chart()로 받고, 정답은 allow_answer=True로 꺼낼 것")
    b = _branch(con, vp_id, branch)
    r = con.execute("SELECT json FROM states WHERE vp_id = ? AND branch = ? AND kind = ?", (vp_id, b, kind)).fetchone()
    if r is None:
        raise KeyError(f"{vp_id} {b} {kind} 없음")
    return json.loads(r[0])


# ---------------------------------------------------------------- 병원 쪽 요청 (EMR 흉내)
# 실제 병원 DB에 있는 것만 내준다: 환자 식별 정보와 문서(종류·날짜·본문). 정답 JSON·fields·truth는 내주지 않는다.
HOSPITAL_PATIENT = ("registration_no", "patient_name", "sex", "age", "patient_ref")


def _visit_date(row) -> str:
    """장면 판정 기준일 (진단일 + index_day). 외래에서 차트를 요청한 날."""
    import datetime as dt
    return (dt.date.fromisoformat(row["dx_date"]) + dt.timedelta(days=row["index_day"] or 0)).isoformat()


def find_patients(con, query: str) -> list[dict]:
    """환자 찾기: 등록번호(숫자), 가상 번호(VH-…), 이름. 같은 환자의 장면(외래 날)이 여럿이면 모두."""
    q = re.sub(r"\s+", "", query or "")
    if not q:
        return []
    if q.isdigit():
        rows = con.execute("SELECT * FROM patients WHERE registration_no = ?", (q,))
    elif q.upper().startswith("VH-"):
        rows = con.execute("SELECT * FROM patients WHERE vp_id = ? OR patient_ref = ?", (q.upper(), q.upper()))
    else:
        rows = con.execute("SELECT * FROM patients WHERE patient_name = ?", (q,))
    return sorted(({**{k: r[k] for k in HOSPITAL_PATIENT}, "visit_date": _visit_date(r)} for r in rows),
                  key=lambda r: (r["registration_no"], r["visit_date"]))


def request_chart(con, registration_no: str, as_of: str | None = None) -> dict:
    """병원 DB에 차트 요청: 그 환자의 as_of(YYYY-MM-DD) 날까지 마지막 외래 장면의 문서. as_of가 없으면 마지막 외래.
    돌려주는 것: patient (식별 정보, visit_date), documents ([{doc_id, doc_type, doc_date, text}]), chart_text.
    문서 날짜가 as_of 뒤인 문서는 뺀다 (날짜 없는 투약 기록 표는 그 외래 날 기준이라 남긴다)."""
    scenes = [r for r in con.execute("SELECT * FROM patients WHERE registration_no = ?", (str(registration_no),))]
    if not scenes:
        raise KeyError(f"등록번호 {registration_no} 없음")
    scenes = sorted(scenes, key=_visit_date)
    if as_of:
        scenes = [r for r in scenes if _visit_date(r) <= as_of]
        if not scenes:
            raise KeyError(f"등록번호 {registration_no}: {as_of}까지 외래 기록 없음")
    s = scenes[-1]
    docs = [dict(d) for d in con.execute("SELECT doc_id, doc_type, doc_date, text FROM documents "
                                         "WHERE vp_id = ? AND branch = ? ORDER BY start", (s["vp_id"], s["branch"]))]
    if as_of:
        docs = [d for d in docs if d["doc_date"] is None or d["doc_date"] <= as_of]
    return {"patient": {**{k: s[k] for k in HOSPITAL_PATIENT}, "visit_date": _visit_date(s)},
            "documents": docs, "chart_text": "".join(d["text"] for d in docs)}


def truth(con, vp_id: str, branch: str | None = None, *, allow_future: bool = False) -> dict:
    """판정 기준일 뒤의 값 (수술 림프절 결과, 생존, 실제 처방 기록 등). 모델 입력에 섞이지 않게 allow_future=True일 때만."""
    if not allow_future:
        raise PermissionError("truth는 미래 값이다. 정답·평가에만 쓰고 allow_future=True로 꺼낼 것")
    b = _branch(con, vp_id, branch)
    return {r[0]: r[1] for r in con.execute("SELECT item, value FROM truth WHERE vp_id = ? AND branch = ?", (vp_id, b))}


def slides(con, vp_id: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM slides WHERE vp_id = ? ORDER BY slide_id", (vp_id,))]


def slide_file(con, slide_id: str) -> Path | None:
    """원본(BCNB jpg) 또는 썸네일(TCGA) 파일 위치. 이 컴퓨터에 없으면 None."""
    r = con.execute("SELECT root, path FROM slides WHERE slide_id = ?", (slide_id,)).fetchone()
    if r is None or r["path"] is None:
        return None
    p = {"bcnb_raw": BCNB_RAW, "project": PROJECT}.get(r["root"], PROJECT) / r["path"]
    return p if p.exists() else None


def tile_features(con, slide_id: str, feature_set: str):
    """(좌표, 타일 벡터). 파일은 local/features/<묶음>/<파일>.h5 (서버에서 받아 둘 것). h5py 필요."""
    r = con.execute("SELECT file FROM feature_sets WHERE slide_id = ? AND feature_set = ?", (slide_id, feature_set)).fetchone()
    if r is None:
        raise KeyError(f"{slide_id} {feature_set} 벡터 없음")
    f = FEATURES / feature_set / r[0]
    if not f.exists():
        raise FileNotFoundError(f"{f} 없음 → 서버의 타일 벡터 파일을 이 위치에 받을 것")
    import h5py
    with h5py.File(f, "r") as h:
        return h["coords"][:], h["features"][:]


def similar(con, slide_id: str, k: int = 10, feature_set: str | None = None, *,
            same_branch: bool = False, exclude_same_patient: bool = True) -> list[dict]:
    """병리 유사 환자 (4-B): 같은 묶음 안 슬라이드 벡터의 cosine 유사도 상위 k개.
    묶음마다 타일 크기·배율이 달라(TCGA 512px 0.25µm, BCNB 256px) 묶음을 섞어 비교하지 않는다."""
    q = con.execute("SELECT feature_set, vector, s.vp_id FROM slide_embeddings e JOIN slides s USING (slide_id) "
                    "WHERE slide_id = ?" + (" AND feature_set = ?" if feature_set else ""),
                    (slide_id, *([feature_set] if feature_set else []))).fetchone()
    if q is None:
        raise KeyError(f"{slide_id} 슬라이드 벡터 없음")
    fs, qv, qvp = q[0], np.frombuffer(q[1], "<f4"), q[2]
    rows = con.execute("SELECT e.slide_id, s.vp_id, e.vector FROM slide_embeddings e JOIN slides s USING (slide_id) "
                       "WHERE e.feature_set = ? AND e.slide_id != ?", (fs, slide_id)).fetchall()
    if exclude_same_patient:
        rows = [r for r in rows if r[1] != qvp]
    if same_branch:
        mine = {r[0] for r in con.execute("SELECT branch FROM patients WHERE vp_id = ?", (qvp,))}
        ok = {r[0] for r in con.execute("SELECT vp_id FROM patients WHERE branch IN (%s)" % ",".join("?" * len(mine)), list(mine))}
        rows = [r for r in rows if r[1] in ok]
    if not rows:
        return []
    m = np.stack([np.frombuffer(r[2], "<f4") for r in rows])
    sim = m @ qv / (np.linalg.norm(m, axis=1) * np.linalg.norm(qv) + 1e-12)
    top = np.argsort(-sim)[:k]
    return [{"slide_id": rows[i][0], "vp_id": rows[i][1], "similarity": float(sim[i])} for i in top]


def info(con) -> dict:
    out = {"patients": {r[0]: r[1] for r in con.execute("SELECT branch, count(*) FROM patients GROUP BY branch")}}
    for t in ("charts", "documents", "states", "fields", "truth", "treatments", "slides", "annotations", "feature_sets", "slide_embeddings"):
        out[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    out["meta"] = {r[0]: r[1] for r in con.execute("SELECT key, value FROM meta")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["build", "info"])
    args = ap.parse_args(argv)
    if args.command == "build":
        res = build()
        print(f"만듦: {DB_PATH}")
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(info(connect()), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
