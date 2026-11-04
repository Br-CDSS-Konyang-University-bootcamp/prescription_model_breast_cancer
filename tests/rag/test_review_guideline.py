# C 정답 파일 검수용 출력이 모든 사례에서 만들어지고, check_case 결과 순위와 검수 기록이 맞게 붙는지 (색인·모델 없이)
import json

from src.rag.chunk_store import load_guideline_chunks
from src.rag.review_guideline import answer_files, mark_reviewed, parse_results, render_case


def test_every_answer_file_renders():
    chunks = {c["chunk_id"]: c for c in load_guideline_chunks()}
    files = answer_files()
    assert files
    for path in files:
        text = render_case(path, chunks)
        assert "[정답 권고" in text and "청크 파일에 없음" not in text, path


def test_results_ranks_and_mark(tmp_path, monkeypatch):
    from src.rag import review_guideline as rg
    results = tmp_path / "check.txt"
    results.write_text("===== VC-0103 =====\n[지침 청크 2개]\n  1   0.9  권고  esmo-mbc-2026-05-luminal-1l-0fd38a  p1205  x\n"
                       "  2   0.8  그림  esmo-mbc-2026-05-fig2-a9baa4  p1206  x\n", encoding="utf-8")
    parsed = parse_results(results)
    assert [c["chunk_kind"] for c in parsed["VC-0103"]] == ["recommendation", "algorithm"]
    chunks = {c["chunk_id"]: c for c in load_guideline_chunks()}
    text = render_case(answer_files(["VC-0103"])[0], chunks, parsed)
    assert "첫 정답 1위" in text and "이번 1위" in text
    case = tmp_path / "VC-9999" / "expected"
    case.mkdir(parents=True)
    (case / "guideline.json").write_text(json.dumps({"status": "draft"}), encoding="utf-8")
    assert mark_reviewed([case / "guideline.json"], "검수자", today="2026-11-04") == ["VC-9999"]
    assert json.loads((case / "guideline.json").read_text(encoding="utf-8")) == {
        "status": "reviewed", "reviewer": "검수자", "reviewed_on": "2026-11-04"}
