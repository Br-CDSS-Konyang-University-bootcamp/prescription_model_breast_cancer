"""경로, 규칙 표 읽기, vp 번호로 정한 난수. 입력·바이오마커·화면 코드는 불러 쓰기만 하고 고치지 않는다."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

MINI = Path(__file__).resolve().parents[3]            # 이 저장소 (team_project)
PROJECT = MINI.parent
FINAL = PROJECT / "team_project_final"                 # 모듈 1 데이터 (MKI67 발현, 슬라이드 목록). 읽기만
CODE = Path(__file__).resolve().parent                 # src/input/virtual_hospital/ (코드·문서)
ROOT = MINI / "data" / "virtual_hospital"              # 가상환자 데이터 (규칙 표, 차트, 보고)
RULES = ROOT / "rules"
OUT = ROOT                                             # OUT / "tcga", OUT / "tcga_recur"
LOCAL = ROOT / "local"                                 # git 제외: BCNB, 원본 ID 대응, 라이선스 원본, LLM 결과
REPORTS = ROOT / "reports"
CREATED_AT = "2026-11-09T00:00:00+09:00"               # 같은 입력 → 같은 출력


def mini_on_path() -> None:
    """저장소 루트를 import 경로에 넣는다 (team_project 폴더에서 python -m으로 돌리면 이미 들어 있다)."""
    if str(MINI) not in sys.path:
        sys.path.insert(0, str(MINI))


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], cols: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = cols or (list(rows[0].keys()) if rows else [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def rules() -> dict[str, dict]:
    return {r["rule_id"]: r for r in read_csv(RULES / "rules.csv")}


def thresholds() -> dict[str, str]:
    return {r["항목"]: r["값"] for r in read_csv(RULES / "thresholds.csv")}


def boundary(name: str) -> tuple[int, int]:
    lo, hi = thresholds()[f"boundary.{name}"].split("-")
    return int(lo), int(hi)


def ref(ref_id: str, target: str) -> str:
    for r in read_csv(RULES / "references.csv"):
        if r["ref_id"] == ref_id and r["대상"] == target:
            return r["값"]
    raise KeyError(f"references.csv에 {ref_id} {target} 없음")


def rng(key: str, rule_id: str) -> random.Random:
    """vp 번호(또는 다른 열쇠)와 규칙 id로 정한 난수. 같은 열쇠 → 같은 값."""
    seed = int(hashlib.sha256(f"{key}|{rule_id}".encode()).hexdigest()[:16], 16)
    return random.Random(seed)


@dataclass
class Rec:
    """fields.csv 한 행 = patient_state 칸 하나."""
    field: str
    status: str                       # present / not_done / not_recorded
    value: object = None
    origin: str = "real"              # real / derived / synthetic
    basis: str = ""                   # ①~⑤ (합성·계산일 때)
    rule_id: str = ""
    source_column: str = ""
    observed_date: str | None = None
    specimen: str | None = None
    note: str = ""

    def row(self, vp_id: str) -> dict:
        return {"vp_id": vp_id, "field": self.field, "status": self.status,
                "value": json.dumps(self.value, ensure_ascii=False) if self.status == "present" else "",
                "origin": self.origin, "basis": self.basis, "rule_id": self.rule_id,
                "source_column": self.source_column, "observed_date": self.observed_date or "",
                "specimen": self.specimen or "", "note": self.note}


@dataclass
class Patient:
    vp_id: str
    source_id: str                    # 원본 ID (local/source_map.csv에만 쓴다)
    branch: str
    split: str
    dx_date: str
    index_day: int
    side: str
    recs: dict[str, Rec] = field(default_factory=dict)
    truth: dict[str, object] = field(default_factory=dict)
    slides: list[dict] = field(default_factory=list)
    cdna: dict[tuple[str, str], str] = field(default_factory=dict)   # (유전자, 단백 변화) → c. 표기 (M-03)
    problems: list[str] = field(default_factory=list)              # 차트로 쓸 수 없는 실제 값 (넘길 목록)
    treatments: list[dict] = field(default_factory=list)           # 재발 갈래: 판정 기준일 전의 실제 투약 (중단 사유 포함)
    grade_scores: tuple[int, int, int] | None = None                # M-05: 관 형성·핵 다형성·유사분열 실제 판독 점수
    scene_kind: str | None = None                                   # 재발 갈래: endocrine / chemo (D-R1 주 차수 종류)
    scene_prev: str | None = None                                   # 재발 갈래: 장면 전 고식 요법 (예: 내분비 1차)
    scene_line: int | None = None                                # 재발 갈래: 이 차트에서 정할 고식 차수 (D-R1)

    def add(self, rec: Rec) -> None:
        self.recs[rec.field] = rec
