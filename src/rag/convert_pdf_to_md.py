# src/rag/convert_pdf_to_md.py
# 실행: team_project 폴더에서 python -m src.rag.convert_pdf_to_md
# 입력: data/guidelines/*.pdf (asco_*.pdf, esmo_*.pdf)
# 출력: data/parsed_md/asco/*.md, data/parsed_md/esmo/*.md
#
# 지침 전문은 저작권 문서라 PDF와 변환한 md는 저장소에 올리지 않는다 (.gitignore가 data/ 안의 .pdf, .md를 막는다).
# 각자 PDF를 받아 이 스크립트로 md를 만든 뒤 chunker_asco_all.py, chunker_esmo.py를 돌린다.
# 필요 패키지: docling (conda install -n team_project -c conda-forge docling)
import argparse
import re
from pathlib import Path

from .chunk_common import BASE_DIR, PARSED_MD_DIR

GUIDELINES_DIR = BASE_DIR / "data" / "guidelines"


def strip_personal_lines(markdown: str) -> str:
    """ASCO PDF 머리말에 찍힌 내려받은 사람 정보("Downloaded from ascopubs.org by ...")를 지운다."""
    return re.sub(r"^.*Downloaded from ascopubs\.org.*\n?", "", markdown, flags=re.MULTILINE | re.IGNORECASE)


def convert_all(pdf_dir: Path, out_dir: Path, overwrite: bool = False):
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"{pdf_dir}에 PDF가 없습니다.")

    for pdf in pdfs:
        source = pdf.stem.split("_")[0]  # asco 또는 esmo
        if source not in ("asco", "esmo"):
            print(f"[건너뜀] {pdf.name}: 파일 이름이 asco_ 또는 esmo_로 시작하지 않습니다.")
            continue
        out_path = out_dir / source / f"{pdf.stem}.md"
        if out_path.exists() and not overwrite:
            print(f"[있음] {out_path.name}")
            continue
        markdown = converter.convert(str(pdf)).document.export_to_markdown()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(strip_personal_lines(markdown), encoding="utf-8")
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
