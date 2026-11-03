# 정답 confirmed_state 검토용 출력이 검토표의 모든 사례에서 오류 없이 만들어지는지 (색인·모델 없이)
from src.rag.review_confirmed import load_review, render_case, scenario_summary


def test_every_review_case_renders():
    rows = load_review()
    assert rows
    for row in rows:
        text = render_case(row)
        if "(confirmed_state.json 없음)" in text:   # A가 만들지 않은 사례 (VC-0106b, VC-0129)
            continue
        assert "[C 검색 조건]" in text and "필터:" in text, row["case"]


def test_scenario_summary_skips_reimbursement_table():
    text = "# VC-X\n\n## 5. 기대 결과\n\n- **C (지침)**: 그림 2\n- **D (급여)**\n\n| 후보 | 공고 위치 |\n|---|---|\n| a | b |\n"
    out = "\n".join(scenario_summary(text))
    assert "그림 2" in out and "공고 위치" not in out
