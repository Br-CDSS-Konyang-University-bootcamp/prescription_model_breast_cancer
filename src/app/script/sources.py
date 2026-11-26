"""화면 1이 환자 차트를 받는 곳 (사례 이름 = patient_ref).

- FolderSource: 사례 폴더 (<폴더>/<사례>/chart.txt + expected/*.json). 가상 차트, 가상 병원 차트 폴더
- HospitalDbSource: 가상 병원 DB (src/virtual_hospital/scripts/db.py의 공개 함수만 부른다). 실제 병원 DB에
  차트를 요청하는 그림: 식별 정보와 그 외래 날까지의 문서를 받는다. 정답 JSON은 정답 방식에서만 따로 꺼낸다
- Extractor: 입력 모듈 방식. 받은 차트를 입력 모듈(pipeline.run + LLM)에 넣어 patient_state를 만든다.
  화면 요청과 따로 도는 스레드라 화면이 "문서 2/4 읽는 중"을 물어 볼 수 있다. 결과는 <app>/extracted/<사례>/
"""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

IDENT_NO = re.compile(r"등록번호:\s*(\d+)")                 # 차트 식별줄 (찾기용, 첫 줄만 읽음)
IDENT_NAME = re.compile(r"환자명:\s*(\S+)")
KST = timezone(timedelta(hours=9))


def _query(query: str) -> str:
    return re.sub(r"\s+", "", query or "")


class FolderSource:
    kind = "folders"

    def __init__(self, dirs: list[Path]):
        self.dirs = list(dirs)
        self._info: dict[Path, dict] = {}       # 사례 폴더 → patient_ref·등록번호·이름 (한 번 읽고 기억)

    def _index(self) -> dict[str, dict]:
        """사례 이름(patient_ref) → 폴더·등록번호·이름. 여러 사례 폴더를 합친다 (가상 병원은 수술 후·재발 장면이
        같은 폴더 이름이라 patient_ref로 가른다). 폴더는 부를 때마다 다시 찾고, 처음 보는 폴더만 읽는다."""
        out = {}
        for base in self.dirs:
            for p in sorted(base.glob("*/expected/patient_state.json")):
                folder = p.parents[1]
                if folder not in self._info:
                    with open(p, encoding="utf-8") as f:
                        ref = json.load(f)["patient_ref"]
                    chart = folder / "chart.txt"
                    head = chart.read_text(encoding="utf-8")[:400] if chart.exists() else ""
                    reg, name = IDENT_NO.search(head), IDENT_NAME.search(head)
                    self._info[folder] = {"case": ref, "folder": folder,
                                          "set": base.name if base.name != "charts" else base.parent.name,
                                          "registration_no": reg and reg.group(1), "name": name and name.group(1)}
                info = self._info[folder]
                if info["case"] in out:
                    raise ValueError(f"patient_ref가 겹침: {info['case']} ({out[info['case']]['folder']}, {folder})")
                out[info["case"]] = info
        return out

    def folder(self, case: str) -> Path:
        index = self._index()
        if case not in index:
            raise KeyError(f"없는 사례: {case}")
        return index[case]["folder"]

    def cases(self) -> list[str]:
        return sorted(self._index())

    def find(self, query: str) -> list[dict]:
        """환자 번호(등록번호, 가상 번호 VH-…·VC-…) 또는 환자 이름. 번호는 같은 값만, 이름은 같은 이름이 없을 때
        이름 일부로도 찾는다. 같은 환자의 장면이 여럿이면 모두."""
        q = _query(query)
        if not q:
            return []
        rows = list(self._index().values())
        if q.isdigit():
            hits = [r for r in rows if r["registration_no"] == q]
        elif re.fullmatch(r"[A-Za-z]{2}-[A-Za-z0-9-]+", q):
            hits = [r for r in rows if r["case"].upper() == q.upper() or r["case"].upper().startswith(q.upper() + "-")]
        else:
            hits = [r for r in rows if r["name"] == q] or [r for r in rows if r["name"] and q in r["name"]]
        return [{k: r[k] for k in ("case", "set", "registration_no", "name")} for r in sorted(hits, key=lambda r: r["case"])]

    def chart(self, case: str) -> str:
        p = self.folder(case) / "chart.txt"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def answer(self, case: str, kind: str) -> dict | None:
        """정답 JSON (expected/<kind>.json). 없으면 None."""
        p = self.folder(case) / "expected" / f"{kind}.json"
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)


class HospitalDbSource:
    """가상 병원 DB. 서버 요청 스레드마다 연결을 새로 연다 (SQLite 연결은 스레드끼리 나눠 쓰지 않는다)."""
    kind = "hospital_db"

    def __init__(self, path: Path | None = None):
        from src.virtual_hospital.scripts import db
        self.db, self.path = db, path or db.DB_PATH
        with closing(self.db.connect(self.path)):      # 없으면 여기서 알린다 (db build 먼저)
            pass

    def _con(self):
        return closing(self.db.connect(self.path))

    @staticmethod
    def _hit(r: dict) -> dict:
        return {"case": r["patient_ref"], "set": f"외래 {r['visit_date']}", "registration_no": r["registration_no"],
                "name": r["patient_name"]}

    def cases(self) -> list[str]:
        with self._con() as con:
            return [r["patient_ref"] for r in self.db.list_visits(con)]

    def find(self, query: str) -> list[dict]:
        with self._con() as con:
            return [self._hit(r) for r in self.db.find_patients(con, _query(query))]

    def chart(self, case: str) -> str:
        with self._con() as con:
            return self.db.request_visit(con, case)["chart_text"]

    def answer(self, case: str, kind: str) -> dict | None:
        with self._con() as con:
            try:
                return self.db.get_answer(con, case, kind)
            except KeyError:
                return None


class Extractor:
    """입력 모듈 방식: 차트 → 입력 모듈 (비식별화 → 문서마다 LLM 추출 → 정리) → patient_state.
    사례마다 작업 하나. 결과 파일이 있으면 끝난 것으로 본다 (다시 읽기는 force)."""

    def __init__(self, out_dir: Path, host: str | None = None, complete=None):
        """complete: LLM 호출 함수 (기본 llm.complete_json, 시험에서는 가짜)."""
        self.out_dir, self.host, self.complete = out_dir, host, complete
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def path(self, case: str) -> Path:
        return self.out_dir / case / "patient_state.json"

    def result(self, case: str) -> dict:
        if not self.path(case).exists():
            raise KeyError(f"{case}: 입력 모듈 결과 없음 (먼저 차트를 읽을 것)")
        with open(self.path(case), encoding="utf-8") as f:
            return json.load(f)

    def status(self, case: str) -> dict:
        if self.path(case).exists():
            issues = self.out_dir / case / "issues.json"
            log = json.loads(issues.read_text(encoding="utf-8")) if issues.exists() else {}
            return {"stage": "done", "seconds": log.get("seconds"), "issues": len(log.get("issues", [])),
                    "llm_errors": len(log.get("errors", []))}
        job = self.jobs.get(case)
        if not job:
            return {"stage": "none"}
        return {k: v for k, v in job.items() if k != "thread"} | {"elapsed": round(time.time() - job["started"])}

    def start(self, case: str, chart: str, force: bool = False) -> dict:
        with self.lock:
            if force:
                self.path(case).unlink(missing_ok=True)
            cur = self.status(case)
            if cur["stage"] in ("done", "reading"):
                return cur
            job = {"stage": "reading", "started": time.time(), "done": 0, "total": None, "current": None}
            self.jobs[case] = job
        job["thread"] = threading.Thread(target=self._run, args=(job, case, chart), daemon=True)
        job["thread"].start()
        return self.status(case)

    def _run(self, job: dict, case: str, chart: str) -> None:
        try:
            import requests
            from llm import LLMOutputError, complete_json, load_config
            from src.input.script.pipeline import extract_doc, field_list, run, split

            config = load_config("extract", **({"host": self.host} if self.host else {}))
            job.update(model=config.model, total=sum(field_list(d) is not None for d in split(chart)))
            log = {"candidates": 0, "errors": [], "doc_seconds": {}}

            def complete(msgs, sch, cfg):
                t = time.perf_counter()
                try:
                    return (self.complete or complete_json)(msgs, sch, cfg)
                except (LLMOutputError, requests.RequestException) as e:   # 문서 하나가 실패해도 나머지는 읽는다
                    log["errors"].append(str(e)[:300])
                    return {"candidates": []}
                finally:
                    log["doc_seconds"][str(len(log["doc_seconds"]) + 1)] = round(time.perf_counter() - t)

            cands: list[dict] = []

            def extract(docs):                    # 입력 모듈은 비식별화한 문서만 넘긴다 (IN-0)
                for d in docs:
                    if field_list(d) is None:
                        continue
                    job.update(current=d.doc_type)
                    cands.extend(extract_doc(d, config, complete))
                    job["done"] += 1
                log["candidates"] = len(cands)
                return cands

            t0 = time.perf_counter()
            ps, issues = run(chart, extract, patient_ref=case,
                             created_at=datetime.now(KST).replace(microsecond=0).isoformat())
            out = self.out_dir / case
            out.mkdir(parents=True, exist_ok=True)
            (out / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
            (out / "issues.json").write_text(json.dumps({**log, "model": config.model, "issues": issues,
                                                         "seconds": round(time.perf_counter() - t0)},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
            self.path(case).write_text(json.dumps(ps, ensure_ascii=False, indent=1), encoding="utf-8")
            job.update(stage="done")
        except Exception as e:   # 화면에 이유를 보여 주고 다시 읽을 수 있게 한다
            job.update(stage="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
