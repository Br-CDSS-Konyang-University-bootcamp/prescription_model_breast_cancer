# tests/rag/test_pages.py
# 쪽 표시(convert_pdf_to_md.page_marker)와 청크 쪽 번호 채우기(chunk_common.fill_pages)를 시험한다.
from src.rag.chunk_common import fill_pages
from src.rag.convert_pdf_to_md import page_marker, printed_page_range


def test_printed_page_range_from_pdf_subject():
    assert printed_page_range({"subject": "J Clin Oncol 2021.39:2959-2961"}) == (2959, 2961)
    assert printed_page_range({"subject": "Annals of Oncology, 37 (2026) 1203-1219. doi:10.1016/x"}) == (1203, 1219)
    assert printed_page_range({"subject": ""}) == (None, None)


def test_page_marker_marks_pages_beyond_printed_range():
    assert "pdf=1 printed=516" in page_marker(1, 516, 519)
    assert "pdf=5 printed=-" in page_marker(5, 516, 519)


def _chunk(cid, text, parent_id=None):
    return {"chunk_id": cid, "text": text, "parent_id": parent_id, "page_start": None, "page_end": None}


def test_fill_pages_finds_start_end_and_parent_range():
    md = (page_marker(1, 100, 102) + "- Alpha drug is recommended for patients [I, A].\n"
          + page_marker(2, 100, 102) + "- Beta drug is recommended for patients with a very long\n"
          + page_marker(3, 100, 102) + "- sentence that continues on the next page [II, B].\n")
    kids = [_chunk("a", "Alpha drug is recommended for patients [I, A].", "p"),
            _chunk("b", "Beta drug is recommended for patients with a very long sentence that continues on the next page [II, B].", "p")]
    parent = _chunk("p", "Section\n\n" + kids[0]["text"] + "\n\n" + kids[1]["text"])
    chunks = [parent] + kids
    fill_pages(chunks, md)
    assert (kids[0]["page_start"], kids[0]["page_end"]) == (100, 100)
    assert (kids[1]["page_start"], kids[1]["page_end"]) == (101, 102)
    assert (parent["page_start"], parent["page_end"]) == (100, 102)
    fill_pages(chunks, md, numbering="pdf")
    assert (kids[1]["page_start"], kids[1]["page_end"]) == (2, 3)
