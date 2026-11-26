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
CODE = Path(__file__).resolve().parents[1]             # src/virtual_hospital/ (문서, db_schema.sql). 코드는 CODE / "scripts"
ROOT = MINI / "data" / "virtual_hospital"              # 가상환자 데이터 (규칙 표, 차트, 보고)
RULES = ROOT / "rules"
OUT = ROOT                                             # OUT / "tcga", OUT / "tcga_recur"
LOCAL = ROOT / "local"                                 # git 제외: BCNB, 원본 ID 대응, 라이선스 원본, LLM 결과
REPORTS = ROOT / "reports"
# BCNB 원자료 (patient-clinical-data.xlsx, WSIs/). 약관상 각자 받아 local/bcnb_raw/에 둔다 (git 제외).
# local/BCNB/는 Windows에서 결과 폴더 local/bcnb/와 같은 폴더라 쓰지 않는다. 없으면 예전 별도 저장소 위치
BCNB_RAW = next((p for p in (LOCAL / "bcnb_raw", PROJECT / "virtual_hospital" / "data" / "BCNB" / "BCNB")
                 if (p / "patient-clinical-data.xlsx").exists()), LOCAL / "bcnb_raw")
FEATURES = LOCAL / "features"                          # 슬라이드 벡터 (<묶음>.npz), 타일 벡터 (<묶음>/<파일>.h5)
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


DATASET_DIGIT = {"T": "1", "B": "2"}                  # R-08: 등록번호 첫 자리 (TCGA 1, BCNB 2)


def registration_no(vp_id: str) -> str:
    """R-08: 등록번호 8자리 (VH-T0043 → 10000043). 같은 환자의 두 장면은 같은 번호."""
    kind, num = vp_id.split("-")[1][0], vp_id.split("-")[1][1:]
    return DATASET_DIGIT[kind] + num.zfill(7)


def phone_no(vp_id: str) -> str:
    """R-08: 연락처 010-등록번호 앞 4자리-뒤 4자리."""
    n = registration_no(vp_id)
    return f"010-{n[:4]}-{n[4:]}"


def scene_ref(vp_id: str, branch: str) -> str:
    """D-12: patient_ref (장면 단위). 재발 장면만 '-R'을 붙인다."""
    return f"{vp_id}-R" if branch == "TCGA_recur" else vp_id


_NAMES: dict[str, str] = {}


def virtual_name(vp_id: str) -> str:
    """Y-08: 가상 이름 (성 + 이름 2자). 성은 rules/names.csv의 성씨 인원 비율, 이름은 정해 둔 글자 조합.
    VH-T0001, VH-B0001, VH-T0002, … VH-B1999 순서로 돌며 vp 번호 난수로 뽑고, 앞 번호가 쓴 이름이면 같은 성의
    다음 이름 (다 찼으면 다음 성)으로 넘긴다. 실제 환자 수와 상관없이 번호마다 이름이 하나로 정해진다."""
    if not _NAMES:
        rows = read_csv(RULES / "names.csv")
        sur = [(r["value"], int(r["weight"])) for r in rows if r["kind"] == "surname"]
        given = [a["value"] + b["value"] for a in rows if a["kind"] == "first"
                 for b in rows if b["kind"] == "second" and a["value"] != b["value"]]
        combos = [s + g for s, _ in sur for g in given]
        used: set[str] = set()
        for i in range(1, 2000):                       # 2 × 1999 < 성 10 × 이름 610 조합
            for kind in ("T", "B"):
                vp = f"VH-{kind}{i:04d}"
                r = rng(vp, "Y-08")
                s = r.choices(range(len(sur)), weights=[w for _, w in sur])[0]
                j = s * len(given) + r.randrange(len(given))
                while combos[j] in used:
                    j = (j + 1) % len(combos)
                used.add(combos[j])
                _NAMES[vp] = combos[j]
    return _NAMES[vp_id]


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
