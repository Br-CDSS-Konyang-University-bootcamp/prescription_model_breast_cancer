"""화면 2 처방 추천·선택. 화면 1 서버(screen1.py)가 이 모듈의 함수를 불러 /screen2와 /api/rec/* 를 연다.

화면 규격: notes/ui_design_2026-10-21.md §5 (재진 화면을 화면 2로 씀, 2026-11-02).
  왼쪽 ① 확정한 환자 상태 (confirmed_state)  오른쪽 위 ② 처방 추천 5안  오른쪽 아래 ③ 의사 처방 선택 → prescription_decision

흐름: 화면 1이 확정 파일(v<n>.json)을 저장 → 화면 2가 그 파일로
  C retrieve_for_recommend(confirmed_state) → 지침·급여 청크
  B recommend(patient_state, biomarker_record, 청크, 로컬 LLM, index_status, confirmed_state=...) → recommendation
  를 백그라운드로 돌린다 (CPU에서 수 분). 결과는 data/app/recommendations/<patient_ref>/c<확정 버전>.json에 두고 다시 쓴다.
- LLM은 이 PC 주소의 Ollama만 쓴다 (B make_llm이 주소를 확인). 모델: llm/config.toml [recommend] (B 선택 qwen3:14b,
  2026-11-02, src/recommend/README.md "LLM 모델"). [recommend]가 없을 때만 --model을 쓴다.
  --llm-host http://127.0.0.1:11435 = GPU 서버 (SSH 터널). B make_llm이 이 PC 주소인지 확인하므로 터널로만 쓸 수 있다.
- prescription_decision.json은 스키마가 아직 없다 (ui_design §7.2 제안 형식). data/app/decisions/<patient_ref>/v<n>.json.
- 5안 정렬 (ui_design §5.3 제안, B 결정 전): ESMO 근거 수준(LoE I > II …, GoR A > B …) → 급여 분류 → 원래 순서.
"""
from __future__ import annotations

import csv
from dataclasses import replace
import json
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from src.input.script import confirmed as c

ROOT = c.ROOT
DECISION_SCHEMA = ROOT / "src" / "app" / "prescription_decision.json"   # 초안, 4명 검토 뒤 schemas/로 (prescription_decision_proposal.md)
DEFER_REASONS = ("pending_test", "mdt", "patient_discussion", "other")
REC_DIR = ROOT / "data" / "app" / "recommendations"
DECISION_DIR = ROOT / "data" / "app" / "decisions"
INDEX_STATUS = ROOT / "data" / "reimbursement" / "index_status.json"
DRUG_NAMES = ROOT / "data" / "dictionaries" / "drug_names.csv"
DEFAULT_MODEL = "qwen3:14b"   # [recommend]가 없을 때만. 이 PC Ollama에는 모델이 없어 --llm-host(GPU 터널)로 쓴다
SHOWN = 5
REIMB_ORDER = {"covered": 0, "covered_conditions_unverified": 1, "offlabel_approved": 2, "no_criteria": 3}
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def drug_list() -> list[str]:
    """기타 처방에서 고를 약 (drug_names.csv의 일반명)."""
    with open(DRUG_NAMES, encoding="utf-8-sig", newline="") as f:
        names = {g.strip() for r in csv.DictReader(f) for g in (r["generic_names"] or "").split(";") if g.strip()}
    return sorted(names)


def evidence_key(evidence: str | None) -> tuple[int, int]:
    """"LoE I, GoR A" · "I, A" → (1, 1). 읽지 못하면 맨 뒤."""
    m = re.search(r"\b(IV|V|I{1,3})\s*,\s*(?:GoR\s*)?([A-E])\b", evidence or "")
    return (ROMAN[m.group(1)], ord(m.group(2)) - 64) if m else (9, 9)


def ranked(options: list[dict]) -> list[dict]:
    order = sorted(range(len(options)), key=lambda i: (evidence_key(options[i].get("evidence")),
                                                       REIMB_ORDER.get(options[i].get("reimbursement"), 9), i))
    return [{**options[i], "index": i} for i in order]


def chunk_card(ch: dict) -> dict:
    """인용 청크를 화면에 보일 만큼만 (출처, 판, 쪽, 소단원, 본문 앞부분). 원문 파일은 이 PC에만 있다."""
    return {"chunk_id": ch.get("chunk_id"), "doc_type": ch.get("doc_type"), "source": ch.get("source"),
            "version": ch.get("version"), "section": ch.get("section"), "page_start": ch.get("page_start"),
            "page_end": ch.get("page_end"), "text": (ch.get("text") or "")[:600]}


class Recommender:
    """추천 작업 (환자·확정 버전마다 하나). 서버 요청 스레드와 따로 돈다."""

    def __init__(self, bm, model: str = DEFAULT_MODEL, rec_dir: Path = REC_DIR, host: str | None = None):
        self.bm, self.model, self.rec_dir, self.host = bm, model, rec_dir, host
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def path(self, ref: str, version: int) -> Path:
        return self.rec_dir / ref / f"c{version}.json"

    def status(self, ref: str, version: int) -> dict:
        p = self.path(ref, version)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return {"stage": "done", **json.load(f)}
        job = self.jobs.get(f"{ref}/{version}")
        if not job:
            return {"stage": "none"}
        return {k: v for k, v in job.items() if k != "thread"} | {"elapsed": round(time.time() - job["started"])}

    def start(self, ref: str, version: int, confirmed_state: dict, patient_state: dict, force: bool = False) -> dict:
        key = f"{ref}/{version}"
        with self.lock:
            if force:
                self.path(ref, version).unlink(missing_ok=True)
            cur = self.status(ref, version)
            if cur["stage"] in ("done", "검색", "추천 생성"):
                return cur
            job = {"stage": "검색", "started": time.time(), "model": self.model}
            self.jobs[key] = job
        job["thread"] = threading.Thread(target=self._run, args=(job, ref, version, confirmed_state, patient_state),
                                         daemon=True)
        job["thread"].start()
        return self.status(ref, version)

    def _run(self, job, ref, version, confirmed_state, patient_state):
        try:
            from llm import LLMConfig, load_config
            from src.rag import retrieve_for_recommend
            from src.recommend.conditions_eval import make_conditions_checker
            from src.recommend.llm_link import make_llm
            from src.recommend.pipeline import recommend

            guideline, reimb = retrieve_for_recommend(confirmed_state)
            job.update(stage="추천 생성", chunks=len(guideline) + len(reimb))
            try:
                config = load_config("recommend")
            except KeyError:
                config = LLMConfig(provider="ollama", model=self.model, patient_data=True, num_ctx=16384,
                                   timeout=1800, max_tokens=4096)
            if self.host:   # GPU 서버는 SSH 터널로 이 PC 주소(127.0.0.1:11435)에 연다 (src/input/py_files.md)
                config = replace(config, host=self.host)
            br = self.bm.assess(patient_state)
            with open(INDEX_STATUS, encoding="utf-8") as f:
                index = json.load(f)
            rec, log, errors = recommend(patient_state, br, guideline, reimb, make_llm(config=config), index["index_status"],
                                         config.model, conditions_checker=make_conditions_checker(patient_state, br),
                                         confirmed_state=confirmed_state)
            out = {"recommendation": rec, "ranked": ranked(rec["options"]), "shown": SHOWN, "log": log,
                   "schema_errors": errors, "index_summary": index.get("summary"),
                   "chunks": {ch["chunk_id"]: chunk_card(ch) for ch in [*guideline, *reimb]},
                   "seconds": round(time.time() - job["started"])}
            p = self.path(ref, version)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            job.update(stage="done")
        except Exception as e:   # 화면에 이유를 보여 주고 다시 시도할 수 있게 한다
            job.update(stage="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])


def load_confirmed(save_dir: Path, ref: str, version: int) -> dict:
    p = save_dir / ref / f"v{version}.json"
    if not p.exists():
        raise KeyError(f"확정 파일 없음: {ref} v{version}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_decision(body: dict, confirmed_state: dict, rec_status: dict, decision_dir: Path = DECISION_DIR) -> tuple[Path | None, dict, list[str]]:
    """초안 스키마 src/app/prescription_decision.json으로 검사해 저장 (새 버전, 덮어쓰지 않음)."""
    errors = []
    by = (body.get("decided_by") or "").strip()
    if not by:
        errors.append("결정자 ID를 입력하세요 (가명 ID)")
    action = body.get("action")
    rec = rec_status.get("recommendation") or {}
    options = rec.get("options") or []
    doc = {"schema_version": "0.1-draft", "patient_ref": confirmed_state["patient_ref"],
           "confirmed_state_ref": {"version": confirmed_state["version"], "confirmed_at": confirmed_state["confirmed_at"]},
           "recommendation_ref": {"generated_at": rec.get("generated_at"), "model": rec.get("model")} if rec else None,
           "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"), "decided_by": by, "action": action,
           "selected_option_index": None, "selected_rank": None, "shown_option_count": min(SHOWN, len(options)),
           "therapy": None, "drugs": [], "setting": None, "line": None, "reimbursement": None, "reimbursement_reason": None,
           "citations": [], "reimbursement_citations": [], "custom_unlisted_drugs": [], "defer_reason": None, "memo": (body.get("memo") or "").strip() or None}
    if action == "accept_option":
        i = body.get("selected_option_index")
        if not isinstance(i, int) or not 0 <= i < len(options):
            errors.append("추천안을 고르세요")
        else:
            o = options[i]
            shown = [r["index"] for r in rec_status.get("ranked") or ranked(options)]
            doc.update(selected_option_index=i, selected_rank=shown.index(i) + 1, therapy=o["therapy"],
                       drugs=o.get("drugs") or [], reimbursement=o.get("reimbursement"),
                       reimbursement_reason=o.get("reimbursement_reason"), citations=o.get("citations") or [],
                       reimbursement_citations=o.get("reimbursement_citations") or [])
    elif action == "custom":
        drugs = [d for d in body.get("drugs") or [] if d]
        unlisted = [d for d in body.get("custom_unlisted_drugs") or [] if d]
        if not drugs and not unlisted:
            errors.append("기타 처방의 약을 하나 이상 고르세요")
        if not body.get("setting"):
            errors.append("기타 처방의 투여 단계를 고르세요")
        doc.update(therapy=" + ".join(drugs + unlisted), drugs=drugs, custom_unlisted_drugs=unlisted,
                   setting=body.get("setting"), line=body.get("line"))
    elif action == "defer":
        if body.get("defer_reason") not in DEFER_REASONS:
            errors.append("보류 이유를 고르세요")
        doc["defer_reason"] = body.get("defer_reason")
    else:
        errors.append("추천안, 기타, 보류 중 하나를 고르세요")
    if action in ("accept_option", "custom") and not doc["setting"]:
        items = confirmed_state.get("items") or {}
        dis = (items.get("setting.disease") or {}).get("confirmed")
        doc["setting"] = "palliative" if dis == "metastatic" else (items.get("setting.phase") or {}).get("confirmed")
        # 추천안을 고르면 차수는 확정 파일(confirmed_state_ref)의 내분비·항암 차수를 따른다. 기타 처방만 line을 직접 고른다
    if not errors:
        schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
        errors = [f"{'/'.join(map(str, e.absolute_path)) or '(문서)'}: {e.message}"
                  for e in Draft202012Validator(schema).iter_errors(doc)]
    if errors:
        return None, doc, errors
    folder = decision_dir / doc["patient_ref"]
    folder.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(p.stem[1:]) for p in folder.glob("v*.json")] or [0])
    path = folder / f"v{n}.json"
    with open(path, "x", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path, doc, []
