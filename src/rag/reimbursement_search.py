# src/rag/reimbursement_search.py
# 급여 청크(D, doc_type = reimbursement) 검색. 규칙은 D와 정한 것 (2026-10-20):
#   - 입력은 추천 후보 요법 하나 = 약 목록. 이름은 drug_names.csv로 일반명(소문자)으로 바꾼다 (D 설계 §8.4)
#   - 일치: 후보 약이 모두 청크 drugs에 있으면 맞는 행이다. '완전히 같음'은 쓰지 않는다:
#     D는 계열로 적힌 약을 고를 수 있는 약 전부로 펼치고(LHRH agonist → goserelin, leuprolide)
#     순차 요법(FEC → pertuzumab+trastuzumab+docetaxel)의 약을 모두 넣어서, 청크 drugs가 후보보다 많다
#   - 같은 약 조합이 여러 행에 있다 (예: AC는 선행·보조·고식적 3행). 맞는 행을 모두 돌려주되 setting·line으로 거르고,
#     조건 판정(급여 / 조건 확인 필요 / 허가초과 / 기준 없음)은 B가 한다
#   - 벡터 검색이 아니라 필터로 찾는다 (약 이름과 시행일이 핵심). 순위는 덧붙는 정보
#   - 공고예고(source_type = preview)는 판정에 쓰지 않는다 (PROJECT.md §8 규칙 4). D는 index_status의
#     pending_notices로 따로 알린다
#   - 시행일: reimbursement.effective_from ≤ 기준일이고 superseded_by가 없는 청크만
#   - 결과: L3 행 + 부모(L2 단계, L1 원칙). 부모는 D의 청크 파일에서 찾는다 (chunk_store)
# stage(병기 세부) 조건은 공용 스키마에 아직 칸이 없어 거르지 않는다 (D의 schema_proposal.md)
import csv
from datetime import date

from qdrant_client.models import FieldCondition, Filter, MatchValue

from .chunk_common import DRUG_ALIASES, BASE_DIR
from .chunk_store import get_reimbursement_parents
from .client import COLLECTION_NAME, get_qdrant_client

DRUG_NAMES_CSV = BASE_DIR / "data" / "dictionaries" / "drug_names.csv"
USABLE_SOURCE_TYPES = ("baseline", "overlay")  # preview(공고예고)는 판정에 쓰지 않는다
SCROLL_PAGE = 512

_name_map = None


def normalize_drugs(names) -> list[str]:
    """약 이름 → 일반명(소문자) 목록. 'Zoladex' → goserelin, 'T-DXd' → trastuzumab deruxtecan,
    복합 표기('tamoxiphene+leuporeline')는 여러 일반명으로 나눈다. 사전에 없는 이름은 소문자로 그대로 둔다."""
    global _name_map
    if _name_map is None:
        _name_map = {}
        with open(DRUG_NAMES_CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                generics = [g.strip().lower() for g in row["generic_names"].split("+") if g.strip()]
                _name_map[row["raw_name"].strip().lower()] = generics
                for g in generics:
                    _name_map.setdefault(g, [g])
        for alias, generic in DRUG_ALIASES.items():
            _name_map.setdefault(alias, [generic])
    out = []
    for name in names:
        for generic in _name_map.get(str(name).strip().lower(), [str(name).strip().lower()]):
            if generic and generic not in out:
                out.append(generic)
    return out


def search_reimbursement(
        drugs: list[str],
        setting: str = None,
        line: str = None,
        as_of=None,
        with_parent: bool = True,
        top_k: int = None,
) -> list[dict]:
    """추천 후보 요법(약 목록)에 맞는 급여 행. as_of는 판정 기준일(date 또는 'YYYY-MM-DD', 기본 오늘).
    setting(병기 범주)·line(차수)은 주면 거른다: 청크의 값에 들어 있거나 청크가 any면 통과. unknown이나 None이면 거르지 않는다.
    결과는 청크 dict에 다음 키를 더한 것이다:
      matched_drugs (후보 약 일반명), extra_drugs (청크에만 있는 약: 병용·순차·계열 펼침),
      score (차수가 정확히 맞으면 1.0, any면 0.9, 덜어 낼 약이 하나 늘 때마다 -0.01. 순서를 위한 값),
      parent / parents (with_parent=True일 때. 가까운 부모와 부모 전체 [L2, L1])
    맞는 청크가 없으면 빈 목록 (급여 기준 없음 판정은 B가 한다)."""
    wanted = normalize_drugs(drugs)
    if not wanted:
        return []
    as_of = (date.fromisoformat(as_of) if isinstance(as_of, str) else as_of) or date.today()
    client = get_qdrant_client()
    if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        return []
    # 후보 약이 모두 들어 있는 청크만 (배열 칸에 값별 조건을 모두 걸면 '포함' 검사가 된다)
    flt = Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value="reimbursement"))]
                 + [FieldCondition(key="drugs", match=MatchValue(value=d)) for d in wanted])
    points, offset = [], None
    while True:
        page, offset = client.scroll(collection_name=COLLECTION_NAME, scroll_filter=flt, limit=SCROLL_PAGE,
                                     offset=offset, with_payload=True, with_vectors=False)
        points += page
        if offset is None:
            break

    results = []
    for point in points:
        chunk = point.payload
        if chunk.get("chunk_kind") == "section" or not _usable(chunk, as_of):
            continue
        if not _matches(chunk.get("setting"), setting) or not _matches(chunk.get("line"), line):
            continue
        extra = [d for d in chunk.get("drugs", []) if d not in wanted]
        exact_line = bool(line) and line != "unknown" and line in (chunk.get("line") or [])
        score = (1.0 if exact_line else 0.9) - 0.01 * len(extra)
        results.append({**chunk, "matched_drugs": wanted, "extra_drugs": extra, "score": round(score, 4)})
    results.sort(key=lambda r: (-r["score"], r["reimbursement"].get("effective_from") or "", r["chunk_id"]))
    if top_k:
        results = results[:top_k]
    if with_parent:
        for r in results:
            parents = get_reimbursement_parents(r)
            r["parents"] = parents
            r["parent"] = parents[0] if parents else None
    return results


def _usable(chunk: dict, as_of: date) -> bool:
    rb = chunk.get("reimbursement") or {}
    if rb.get("source_type") not in USABLE_SOURCE_TYPES or chunk.get("superseded_by"):
        return False
    try:
        return date.fromisoformat(str(rb.get("effective_from"))[:10]) <= as_of
    except ValueError:  # 시행일이 없거나 형식이 틀리면 판정에 쓰지 않는다
        return False


def _matches(chunk_values, wanted) -> bool:
    if not wanted or wanted == "unknown":
        return True
    values = chunk_values or []
    if isinstance(values, str):
        values = [values]
    return wanted in values or "any" in values
