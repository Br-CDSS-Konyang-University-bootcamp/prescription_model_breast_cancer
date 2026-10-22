# tests/rag/test_algorithm.py
# 알고리즘 그림 → 경로 청크 (src/rag/algorithm_esmo.py). ESMO PDF는 저장소에 없으므로 작은 가짜 그림 PDF를 만들어 본다
import csv
import json
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

from src.rag import algorithm_esmo as alg  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
GREEN = (0.03, 0.32, 0.16)


def _box(page, rect, text, fill=(1, 1, 1), dashes=None):
    page.draw_rect(rect, color=GREEN, fill=fill, width=1, dashes=dashes)
    page.insert_textbox(rect + (2, 2, -2, -2), text, fontsize=7, align=1)


def _arrow(page, x, y_from, y_to, dashes=None):
    """아래로 향하는 연결선 + 삼각형 화살촉 (끝점이 y_to)."""
    page.draw_line((x, y_from), (x, y_to - 3), color=GREEN, width=1, dashes=dashes)
    page.draw_polyline([(x - 3, y_to - 3.5), (x + 3, y_to - 3.5), (x, y_to)], color=None, fill=GREEN, closePath=True)


@pytest.fixture
def figure_page():
    """제목 상자 → 두 갈래(조건) → 각 치료 상자 → 'PD' 이름표가 붙은 합류선 → 다음 차수 상자."""
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    _box(page, pymupdf.Rect(130, 20, 270, 40), "Previously untreated MBC", fill=(0.5, 0.1, 0.3))
    page.draw_line((200, 40), (200, 50), color=GREEN, width=1)
    page.draw_polyline([(100, 50), (300, 50)], color=GREEN, width=1)
    _arrow(page, 100, 50, 70)
    _arrow(page, 300, 50, 70)
    _box(page, pymupdf.Rect(50, 70, 150, 90), "PIK3CA wt")
    _box(page, pymupdf.Rect(250, 70, 350, 90), "PIK3CA mutated")
    _arrow(page, 100, 90, 120)
    _arrow(page, 300, 90, 120)
    _box(page, pymupdf.Rect(40, 120, 160, 150), "Fulvestrant-palbociclib [I, A]", fill=(0.3, 0.5, 0.7))
    _box(page, pymupdf.Rect(240, 120, 360, 150), "Fulvestrant-alpelisib [I, B]", fill=(0.3, 0.5, 0.7))
    page.draw_polyline([(100, 150), (100, 180), (300, 180), (300, 150)], color=GREEN, width=1)
    _arrow(page, 200, 180, 220)
    page.insert_text((205, 202), "PD", fontsize=7)
    _box(page, pymupdf.Rect(150, 220, 250, 240), "Second-line treatment")
    _box(page, pymupdf.Rect(20, 20, 90, 40), "ctDNA testing", dashes="[2 1] 0")
    page.draw_line((90, 30), (127, 30), color=GREEN, width=1, dashes="[2 1] 0")
    page.draw_polyline([(126.5, 27), (126.5, 33), (130, 30)], color=None, fill=GREEN, closePath=True)
    return page


def _texts(nodes, trail):
    return [nodes[i]["text"] for i, _, _ in trail]


def test_boxes_arrows_and_labels_become_paths(figure_page):
    nodes, edges, leftover, warnings = alg.build_graph(figure_page, pymupdf.Rect(10, 10, 390, 250))
    assert not warnings and leftover == []
    trails = alg.paths(nodes, edges)
    assert sorted(_texts(nodes, t) for t in trails) == [
        ["Previously untreated MBC", "PIK3CA mutated", "Fulvestrant-alpelisib [I, B]", "Second-line treatment"],
        ["Previously untreated MBC", "PIK3CA wt", "Fulvestrant-palbociclib [I, A]", "Second-line treatment"],
    ]
    text = alg.path_text(nodes, trails[0])
    assert "→ [PD] → Second-line treatment" in text  # 상자 밖 글자는 합류선의 이름표
    # 점선 상자는 경로의 첫 단계가 아니라 가리키는 상자에 붙는 참고다
    assert text.startswith("Previously untreated MBC (optional: ctDNA testing) →")


def test_box_text_marks_superscripts_and_splits_items():
    R = pymupdf.Rect
    spans = [(R(0, 0, 50, 8), "AI-ribociclib [I, A]", 7.0, 7.0), (R(51, 0, 54, 4), "c", 4.5, 4.0),
             (R(0, 9, 50, 17), "AI-abemaciclib [I, A]", 7.0, 16.0)]
    assert alg._box_text(spans) == "AI-ribociclib [I, A]^c; AI-abemaciclib [I, A]"


def test_ebc_line_follows_surgery_position():
    nodes = [{"text": t} for t in ["HER2+ EBC", "≥cT2 or cN+", "6-8 cycles ChT-HP [I, A]", "Surgery and locoregional RT",
                                   "Residual invasive disease", "T-DM1 up to 14 cycles [I, A]"]]
    trail = [(i, None, False) for i in range(len(nodes))]
    assert alg._path_line(nodes, trail, None) == ["neoadjuvant", "adjuvant"]
    assert alg._path_line(nodes, [trail[0], trail[3], trail[5]], None) == ["adjuvant"]


def test_her2_figure_branches_set_hr_status():
    nodes = [{"text": "Previously untreated HER2+ MBC"}, {"text": "ER+^b"}, {"text": "ER-"}]
    assert alg._path_subtype(nodes, [(0, None, False), (1, None, False)], alg.HER2_POS) == ["HR+/HER2+"]
    assert alg._path_subtype(nodes, [(0, None, False), (2, None, False)], alg.HER2_POS) == ["HR-/HER2+"]


ALG_JSON = BASE_DIR / "data" / "chunks" / "esmo_algorithm_chunks.json"


@pytest.mark.skipif(not ALG_JSON.exists(), reason="알고리즘 청크 파일 없음")
def test_algorithm_chunks_and_review_sheet_agree():
    chunks = json.loads(ALG_JSON.read_text(encoding="utf-8"))
    paths = [c for c in chunks if c["parent_id"]]
    assert paths and all(c["chunk_kind"] == "algorithm" and " → " in c["text"] for c in paths)
    with open(alg.REVIEW_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["chunk_id"] for r in rows] == [c["chunk_id"] for c in paths]
    # path 칸은 청크 본문의 경로 글과 같다 (검수자는 이 칸을 그림과 대조한다)
    assert [r["path"] for r in rows] == [alg.review_path_text(c) for c in paths]
    assert all(" → " in r["path"] and "Footnotes" not in r["path"] for r in rows)
    assert {r["status"] for r in rows} <= {"draft", "reviewed", "rejected"}


def test_figure_text_table_has_no_duplicate_boxes():
    table = alg.load_figure_text()
    for key, rows in table.items():
        points = [(round(x), round(y)) for x, y, _ in rows]
        assert len(points) == len(set(points)), key
