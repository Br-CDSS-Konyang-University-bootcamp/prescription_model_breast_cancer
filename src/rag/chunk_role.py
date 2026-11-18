# src/rag/chunk_role.py
# 실행: team_project 폴더에서 python -m src.rag.chunk_role   (--check: 파일을 바꾸지 않고 바뀔 청크 수만)
# 지침 청크의 역할(role)을 정한다. B 요청(#158, 2026-11-17): 판단 청크("Luminal A 대부분 항암 불필요")나 주의 청크
# ("olaparib·abemaciclib 병용 금지")만 인용한 후보가 처방 후보로 남지 않게, B 후처리가 "후보는 처방 청크를 하나 이상
# 인용해야 남는다"를 적용한다. 약 목록이 빈지로는 가를 수 없다 ("ChT followed by ET"처럼 계열 이름만 적힌 처방 권고도 약 목록이 빔).
#
# 역할 (schemas/chunk.json role)
#   prescribe        처방: 약 이름을 적어 권고한다 (예: "AI—CDK4/6 inhibitor"가 아니라 "Fulvestrant—capivasertib")
#   prescribe_class  계열 처방: 계열 이름으로만 권고한다 (ET, ChT, AI, CDK4/6 inhibitor, bisphosphonates, OFS 등)
#   judgment         판단: 약을 고르지 않는 권고 (항암 필요 여부, 검사, 치료 순서·기간, 국소 치료, MDT)
#   caution          주의: 금기·병용 금지·감시·예방 (처방 후보의 근거로는 쓰지 않는다)
#
# 정하는 순서: 1) data/chunks/esmo_chunk_roles.csv의 role 칸(사람이 검토해 고친 값)이 있으면 그 값
#              2) 없으면 본문 규칙(auto_role): 주의 표현 → caution, 적힌 약 → prescribe, 계열 이름 → prescribe_class, 그 밖 judgment
# 청크 JSON의 role 칸과 검토표를 함께 갱신한다. 검토표의 role·reviewer·note는 다시 써도 남는다.
# 권고(recommendation)와 그림 경로(algorithm, parent_id가 있는 것)에만 붙인다. 소단원·그림 부모 청크는 비운다.
import argparse
import csv
import json
import re

from .chunk_common import CHUNKS_DIR, explicit_drugs, find_class_drugs

ROLES = ("prescribe", "prescribe_class", "judgment", "caution")
ROLES_CSV = CHUNKS_DIR / "esmo_chunk_roles.csv"
CSV_FIELDS = ("chunk_id", "chunk_kind", "auto_role", "role", "reviewer", "note", "text")
CAUTION = re.compile(r"should not be (combined|given|used|administered)|(is|are) not recommended|should be monitored|"
                     r"monitored (very )?closely|contraindicated|should be avoided", re.IGNORECASE)
# 계열 이름: chunk_common.CLASS_TERMS로 약을 푸는 좁은 계열 + 약으로 풀지 않는 넓은 계열
BROAD_CLASS = re.compile(r"(?<![A-Za-z])(ChT|ET|ICIs?|ADCs?|BMAs?|OFS)(?![A-Za-z])|chemotherapy|endocrine(-based)? therap|"
                         r"HER2-(targeted|directed)|anti-HER2|bisphosphonates?|bone-modifying", re.IGNORECASE)


def _esmo_json():
    return CHUNKS_DIR / "esmo_chunks.json"


def _algorithm_json():
    return CHUNKS_DIR / "esmo_algorithm_chunks.json"


def needs_role(chunk: dict) -> bool:
    """역할을 붙이는 청크: 권고와 그림 경로 (소단원·그림 부모는 아님)."""
    kind = chunk.get("chunk_kind")
    return kind == "recommendation" or (kind == "algorithm" and bool(chunk.get("parent_id")))


def role_text(chunk: dict) -> str:
    """판정에 쓰는 글: 각주를 빼고, 그림 경로는 경로 부분만."""
    text = (chunk.get("text") or "").split(" Footnotes: ", 1)[0]
    return text.split("(algorithm path):", 1)[-1] if chunk.get("chunk_kind") == "algorithm" else text


def auto_role(chunk: dict) -> str:
    text = role_text(chunk)
    if CAUTION.search(text):
        return "caution"
    if explicit_drugs(text):
        return "prescribe"
    if find_class_drugs(text) or BROAD_CLASS.search(text):
        return "prescribe_class"
    return "judgment"


def load_review(path=None) -> dict:
    path = path or ROLES_CSV
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["chunk_id"]: r for r in csv.DictReader(f)}


def final_role(chunk: dict, review: dict) -> str:
    row = review.get(chunk["chunk_id"]) or {}
    role = (row.get("role") or "").strip()
    if role and role not in ROLES:
        raise ValueError(f"{ROLES_CSV.name}: {chunk['chunk_id']}의 role '{role}'은 {ROLES} 중 하나가 아님")
    return role or auto_role(chunk)


def apply_roles(chunks: list[dict], review: dict = None) -> int:
    """청크마다 role을 채운다 (역할이 없는 청크는 role을 지운다). 바꾼 청크 수."""
    review = load_review() if review is None else review
    changed = 0
    for c in chunks:
        new = final_role(c, review) if needs_role(c) else None
        if c.get("role") != new:
            if new is None:
                c.pop("role", None)
            else:
                c["role"] = new
            changed += 1
    return changed


def review_rows(chunks: list[dict], review: dict) -> list[dict]:
    rows = []
    for c in chunks:
        if not needs_role(c):
            continue
        old = review.get(c["chunk_id"]) or {}
        rows.append({"chunk_id": c["chunk_id"], "chunk_kind": c["chunk_kind"], "auto_role": auto_role(c),
                     "role": old.get("role", ""), "reviewer": old.get("reviewer", ""), "note": old.get("note", ""),
                     "text": re.sub(r"\s+", " ", role_text(c)).strip()[:300]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="지침 청크의 역할(role) 칸과 검토표 갱신")
    ap.add_argument("--check", action="store_true", help="파일을 바꾸지 않고 바뀔 청크 수만 출력")
    args = ap.parse_args(argv)
    review = load_review()
    rows = []
    for path in (_esmo_json(), _algorithm_json()):
        chunks = json.loads(path.read_text(encoding="utf-8"))
        changed = apply_roles(chunks, review)
        rows += review_rows(chunks, review)
        if changed and not args.check:
            path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: 청크 {len(chunks)}개 중 role이 바뀌는 청크 {changed}개" + (" (저장 안 함)" if args.check else ""))
    if not args.check:
        with open(ROLES_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    counts = {r: sum(1 for x in rows if (x["role"] or x["auto_role"]) == r) for r in ROLES}
    print(f"역할 {len(rows)}개: {counts}, 사람이 고친 값 {sum(1 for x in rows if x['role'])}개")


if __name__ == "__main__":
    main()
