# src/rag/convert_pdf_to_md.py
# 실행: team_project 폴더에서 python -m src.rag.convert_pdf_to_md
# 입력: data/guidelines/esmo_*.pdf
# 출력: data/parsed_md/esmo/*.md
#
# 지침 전문은 저작권 문서라 PDF와 변환한 md는 저장소에 올리지 않는다 (.gitignore가 data/ 안의 .pdf, .md를 막는다).
# 각자 PDF를 받아 이 스크립트로 md를 만든 뒤 chunker_esmo.py를 돌린다.
# 필요 패키지: pymupdf, pymupdf4llm (conda install -n team_project -c conda-forge pymupdf pymupdf4llm)
# 만든 뒤 python -m src.rag.check_md_quality로 깨짐이 남았는지 확인한다.
#
# 왜 기호 폰트 대응표가 필요한가:
# ESMO EBC PDF는 ≥, =, +, – 같은 기호를 기호 전용 폰트의 다른 글자 칸에 넣어 둔다.
# 예: AdvP4C4E74 폰트에서 "\x04"는 화면에 ≥로 그려진다. 그래서 어떤 변환기로 뽑아도 깨진 글자로 나온다.
# 글자마다 폰트 이름을 알 수 있는 PyMuPDF로 읽으면서, 아래 표의 폰트에 속한 글자만 원래 기호로 바꾼다.
# 본문 폰트의 숫자·기호는 건드리지 않는다. 표는 ESMO PDF에서 글자 앞뒤 문맥을 보고 만들었다 (2026-10-19).
import argparse
import csv
import hashlib
import re
from pathlib import Path

from .chunk_common import BASE_DIR, PARSED_MD_DIR

GUIDELINES_DIR = BASE_DIR / "data" / "guidelines"
# 받은 곳·라이선스·파일 지문 기록 (PDF는 저작권 때문에 git에 없어서, 팀원이 같은 판을 받았는지 지문으로 확인한다)
SOURCES_CSV = GUIDELINES_DIR / "sources.csv"


def check_source(pdf: Path, sources_csv: Path = SOURCES_CSV) -> str:
    """PDF가 sources.csv에 적힌 판과 같은지. 쪽 번호와 chunk_id가 판에 따라 달라질 수 있어 다르면 경고한다.
    → "ok" / "unlisted" (목록에 없음) / "mismatch" (지문이 다름)"""
    if not sources_csv.exists():
        return "unlisted"
    with open(sources_csv, encoding="utf-8-sig", newline="") as f:
        expected = {r["file"]: r["sha256"] for r in csv.DictReader(f)}
    if pdf.name not in expected:
        return "unlisted"
    return "ok" if hashlib.sha256(pdf.read_bytes()).hexdigest() == expected[pdf.name] else "mismatch"

# 폰트 이름: {PDF에 저장된 글자: 실제 기호}
SYMBOL_FONTS = {
    # ESMO EBC (Annals of Oncology 2024)
    "AdvPS44A44B": {"d": "—", "e": "–"},
    "AdvP4C4E74": {"\x01": "*", "\x03": "•", "\x04": "≥", "\x05": "≤", "¼": "=", "þ": "+"},
    "AdvPS3FDD77": {"w": "~"},
    "AdvPS40C6FB": {"/": "→"},
}


def _remap_dict(d: dict, raw: bool) -> dict:
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                table = SYMBOL_FONTS.get(span.get("font"))
                if not table:
                    continue
                if raw:
                    for ch in span.get("chars", []):
                        ch["c"] = table.get(ch["c"], ch["c"])
                if "text" in span:
                    span["text"] = "".join(table.get(c, c) for c in span["text"])
    return d


def _install_symbol_fix(pymupdf):
    """pymupdf4llm은 본문은 extractDICT, 표는 extractRAWDICT로 읽는다. 둘 다 기호 대응표를 거치게 한다."""
    textpage = pymupdf.TextPage
    if getattr(textpage, "_symbol_fix_installed", False):
        return
    orig_dict, orig_raw = textpage.extractDICT, textpage.extractRAWDICT
    textpage.extractDICT = lambda self, *a, **k: _remap_dict(orig_dict(self, *a, **k), raw=False)
    textpage.extractRAWDICT = lambda self, *a, **k: _remap_dict(orig_raw(self, *a, **k), raw=True)
    textpage._symbol_fix_installed = True


def postprocess(markdown: str) -> str:
    # 그림 안의 글자(알고리즘 도표)는 본문 사이에 끼어 들어가므로 뺀다
    markdown = re.sub(r"<!-- Start of picture text -->.*?<!-- End of picture text -->", "", markdown, flags=re.DOTALL)
    # 줄 끝에서 끊긴 복합어는 하이픈이 빠진 채 붙는다 (HER2-↵negative → HER2negative). 자주 쓰는 의학 복합어만 되돌린다
    markdown = re.sub(r"\b(HER2|HR|ER|PgR|PD-L1|PIK3CA|ESR1)(negative|positive|low|ultralow|targeted|directed|mutated)\b",
                      r"\1-\2", markdown)
    markdown = re.sub(r"\btriplenegative\b", "triple-negative", markdown)
    return markdown


def printed_page_range(metadata: dict):
    """PDF 정보 칸(subject)의 실린 쪽 범위. 'Annals of Oncology, 37 (2026) 1203-1219. doi:...' → (1203, 1219).
    없으면 (None, None)."""
    m = re.search(r"[:)]\s*(\d+)\s*[-–]\s*(\d+)", metadata.get("subject") or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def page_marker(pdf_page: int, first_printed, last_printed) -> str:
    """쪽마다 맨 앞에 넣는 표시. 청커가 이 표시로 청크의 page_start·page_end를 채운다.
    printed는 학술지에 인쇄된 쪽 (PDF 1쪽 = 실린 첫 쪽). 실린 범위를 넘는 뒤쪽(부록 등)은 '-'."""
    printed = "-"
    if first_printed is not None and first_printed + pdf_page - 1 <= last_printed:
        printed = str(first_printed + pdf_page - 1)
    return f"\n<!-- page pdf={pdf_page} printed={printed} -->\n\n"


def convert_all(pdf_dir: Path, out_dir: Path, overwrite: bool = False):
    import pymupdf
    import pymupdf4llm

    _install_symbol_fix(pymupdf)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"{pdf_dir}에 PDF가 없습니다.")

    for pdf in pdfs:
        source = pdf.stem.split("_")[0]
        if source != "esmo":
            # ASCO 지침은 재사용 불가로 확인돼 쓰지 않는다 (2026-10-20)
            print(f"[건너뜀] {pdf.name}: 파일 이름이 esmo_로 시작하지 않습니다.")
            continue
        status = check_source(pdf)
        if status == "mismatch":
            print(f"[경고] {pdf.name}: data/guidelines/sources.csv에 적힌 판과 파일 지문이 다릅니다. "
                  "쪽 번호와 chunk_id가 달라질 수 있으니 esmo.org에서 같은 판을 받았는지 확인하세요.")
        elif status == "unlisted":
            print(f"[알림] {pdf.name}: data/guidelines/sources.csv에 없는 파일입니다. 받은 곳과 지문을 적어 주세요.")
        out_path = out_dir / source / f"{pdf.stem}.md"
        if out_path.exists() and not overwrite:
            print(f"[있음] {out_path.name}")
            continue
        first_printed, last_printed = printed_page_range(pymupdf.open(str(pdf)).metadata)
        pages = pymupdf4llm.to_markdown(str(pdf), page_chunks=True, show_progress=False)
        markdown = "".join(page_marker(i, first_printed, last_printed) + page["text"]
                           for i, page in enumerate(pages, 1))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(postprocess(markdown), encoding="utf-8")
        print(f"[변환] {pdf.name} -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description="지침 PDF를 마크다운으로 변환한다.")
    parser.add_argument("--pdf-dir", type=Path, default=GUIDELINES_DIR)
    parser.add_argument("--out-dir", type=Path, default=PARSED_MD_DIR)
    parser.add_argument("--overwrite", action="store_true", help="이미 있는 md도 다시 만든다")
    args = parser.parse_args()
    convert_all(args.pdf_dir, args.out_dir, args.overwrite)


if __name__ == "__main__":
    main()
