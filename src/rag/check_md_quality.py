# src/rag/check_md_quality.py
# 실행: team_project 폴더에서 python -m src.rag.check_md_quality [md 폴더 ...]
# 변환한 지침 md에서 PDF 추출 때 생기는 깨짐을 세어 표로 보여 준다. 0에 가까울수록 좋다.
# 폴더를 두 개 주면 (예: 옛 변환, 새 변환) 나란히 비교한다. 기본값은 data/parsed_md.
import argparse
import re
from pathlib import Path

from .chunk_common import PARSED_MD_DIR
from .chunker_esmo import DOCS as ESMO_DOCS

# 이름: (설명, 정규식)
CHECKS = {
    "제어문자": ("눈에 안 보이는 제어문자", r"[\x00-\x08\x0b-\x1f]"),
    "대시e": ("en dash가 e로 깨짐 (ESMO EBC)", r"OFSe(tamoxifen|AI)|taxanee|anthracyclinee|tumoure"),
    "단어붙음": ("하이픈이 빠져 붙은 단어", r"\b(HER2|HR|ER)(negative|positive)\b|triplenegative|withmetastatic"),
    "그림글자": ("그림 각주 줄이 본문에 섞임", r"(?m)^[a-m] [A-Z][a-z]"),
}

WANTED = list(ESMO_DOCS)  # 처방 지침 (ESMO 2개)


def count(md_dir: Path) -> dict:
    result = {}
    for stem in WANTED:
        path = md_dir / stem.split("_")[0] / f"{stem}.md"
        if not path.exists():
            result[stem] = None
            continue
        text = path.read_text(encoding="utf-8")
        result[stem] = {name: len(re.findall(pattern, text)) for name, (_, pattern) in CHECKS.items()}
    return result


def main():
    parser = argparse.ArgumentParser(description="변환한 지침 md의 깨짐을 센다.")
    parser.add_argument("md_dirs", nargs="*", type=Path, default=[PARSED_MD_DIR])
    args = parser.parse_args()

    for name, (desc, _) in CHECKS.items():
        print(f"  {name}: {desc}")
    print()
    results = [(d, count(d)) for d in args.md_dirs]
    header = f"{'항목':<8}" + "".join(f"{str(d)[-28:]:>30}" for d, _ in results)
    print(header)
    for name in CHECKS:
        row = f"{name:<8}"
        for _, res in results:
            total = sum(v[name] for v in res.values() if v)
            row += f"{total:>30}"
        print(row)
    for d, res in results:
        missing = [s for s, v in res.items() if v is None]
        if missing:
            print(f"\n[{d}] 없는 파일: {missing}")


if __name__ == "__main__":
    main()
