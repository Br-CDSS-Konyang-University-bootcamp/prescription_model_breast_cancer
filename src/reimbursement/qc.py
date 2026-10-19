"""단계별 품질 검사. 결과는 validate.Report (오류가 있으면 반영하지 않는다, §8 처리 흐름 9).

  1. 내려받은 파일     check_file          크기, 파일 형식(PDF·xlsx 서명), 오류 페이지(HTML)가 아닌지, 파일명 날짜
  2. 유방암 부분 추출  check_breast_scope  책자 전체에서 '유방' 언급이 추출한 곳(유방암 섹션, 병용요법 유방암 행) 밖에 있는지
                       check_row_numbers   표마다 연번이 1부터 빠짐·중복 없이 이어지는지
  3. 빠진 부분        check_coverage      원문 낱말이 청크에 모두 들어갔는지 (개수까지 비교)
  4. 생성된 단어       check_foreign       청크에 원문에 없는 낱말이 들어갔는지 (청크 머리표 낱말은 뺀다)
                       check_garbled       깨진 글자: U+FFFD, (cid:n), 제어 문자, 사용자 정의 영역, latin-1로 깨진 한글
                       check_drugs         약제명이 목록에 있는지, 원문 오타(예: pembroiizumab)
  5. 이전 실행과 비교  check_counts        섹션별 행 수가 이전 정상 실행보다 크게 줄었는지
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .dates import date_from_filename
from .validate import Report
from .vocab import known_drugs, typo_suspects

MIN_SIZE = {".pdf": 50_000, ".xlsx": 5_000}
MAGIC = {".pdf": b"%PDF-", ".xlsx": b"PK\x03\x04"}

_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")
_GARBLED = [
    (re.compile("�"), "대체 문자(U+FFFD)"),
    (re.compile(r"\(cid:\d+\)"), "(cid:n) 글꼴 오류"),
    (re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]"), "제어 문자"),     # \x0c(\f)는 쪽 구분으로 쓴다
    (re.compile(r"[-]"), "사용자 정의 영역 글자"),
    (re.compile(r"[ÃÂ][\x80-\xbf]|[ê-í][\x80-\xbf]"), "latin-1로 깨진 한글"),
    (re.compile(r"[ㄱ-ㆌㆎ]"), "낱자 자모"),      # U+318D 'ㆍ'(가운뎃점)는 정상
]


def tokens(text: str) -> Counter:
    return Counter(t.lower() for t in _TOKEN.findall(text))


# ---------- 1. 내려받은 파일 ----------

def check_file(path: Path, expected_name: str | None = None) -> Report:
    r = Report()
    path = Path(path)
    if not path.exists():
        r.error(f"파일 없음: {path}")
        return r
    ext = path.suffix.lower()
    size = path.stat().st_size
    head = path.read_bytes()[:512]
    if size < MIN_SIZE.get(ext, 1):
        r.error(f"{path.name}: 크기 {size:,}바이트 (기대 {MIN_SIZE.get(ext, 1):,} 이상)")
    if head.lstrip()[:1] == b"<" or b"<html" in head.lower():
        r.error(f"{path.name}: 파일이 아니라 웹 페이지(HTML)가 내려옴")
    elif ext in MAGIC and not head.startswith(MAGIC[ext]):
        r.error(f"{path.name}: {ext} 파일 서명이 아님 (앞 8바이트 {head[:8]!r})")
    if expected_name and path.name != expected_name:
        r.warn(f"파일명이 게시판 이름과 다름: {path.name} != {expected_name}")
    try:
        r.info.append(f"{path.name}: {size:,}바이트, 파일명 날짜 {date_from_filename(path.name)}")
    except ValueError:
        r.error(f"{path.name}: 파일명에 날짜가 없음")
    return r


# ---------- 2. 유방암 부분 추출 ----------

# 일부러 넣지 않는 목차 섹션 (팀 결정). 여기의 '유방' 언급은 정보로만 남긴다.
#   other:*     Ⅳ. 기타 약제 (G-CSF, zoledronic acid, denosumab, dexrazoxane 등 보조 약제)
#   appendix:*  별첨 삭제사항 정리 (이미 급여에서 빠진 요법 이력)
#   general     일반원칙 중 [별표]·첨부 서식의 예시 문구 (앞부분 규칙은 청크로 넣음)
EXCLUDED_SECTIONS = ("other:", "appendix:", "general")


def check_breast_scope(sections: dict[str, str], covered: dict[str, str],
                       excluded: tuple[str, ...] = EXCLUDED_SECTIONS) -> Report:
    """책자 섹션별 '유방' 언급 수와, 그중 추출한 글에 들어간 수를 비교한다.

    sections: {섹션 키: 섹션 본문}, covered: {섹션 키: 그 섹션에서 추출한 글}
    추출 대상 섹션에서 언급이 남으면 오류, 제외하기로 한 섹션의 언급은 정보,
    그 밖의 섹션(새로 생긴 암종 등)의 언급은 경고로 알린다.
    """
    r = Report()
    for key, text in sections.items():
        n = len(re.findall(r"유방", text))
        if not n:
            continue
        got = len(re.findall(r"유방", covered.get(key, "")))
        if key in covered:
            if got < n:
                r.error(f"{key}: '유방' 언급 {n}회 중 {got}회만 추출함 (빠진 행이 있을 수 있음)")
            else:
                r.info.append(f"{key}: '유방' 언급 {n}회 모두 추출")
        elif key.startswith(excluded):
            r.info.append(f"{key}: '유방' 언급 {n}회 - 제외하기로 한 부분")
        else:
            r.warn(f"{key}: '유방' 언급 {n}회 - 추출 범위 밖 (내용 확인 후 필요하면 범위에 추가)")
    return r


def check_row_numbers(tables: dict[str, list[int]], start: dict[str, int] | None = None) -> Report:
    """{표 이름: [연번...]}. 연번이 시작 번호부터 1씩 늘어나는지."""
    r = Report()
    start = start or {}
    for name, nums in tables.items():
        if not nums:
            continue
        s = start.get(name, 1)
        expected = list(range(s, s + len(nums)))
        if nums != expected:
            dup = sorted(n for n, c in Counter(nums).items() if c > 1)
            gap = sorted(set(range(min(nums), max(nums) + 1)) - set(nums))
            r.error(f"{name}: 연번 {nums} (중복 {dup}, 빠짐 {gap})")
    return r


# ---------- 3·4. 빠진 부분, 생성된 단어 ----------

def check_coverage(source: str, produced: str, name: str, ignore: Counter | None = None,
                   max_report: int = 15) -> Report:
    """원문의 낱말이 결과에 같은 개수 이상 들어 있는지 (결과에는 부모 청크·물려받은 투여대상으로 중복이 있다)."""
    r = Report()
    src = tokens(source) - (ignore or Counter())
    missing = src - tokens(produced)
    total = sum(src.values())
    lost = sum(missing.values())
    if lost:
        sample = ", ".join(f"{t}×{c}" for t, c in missing.most_common(max_report))
        r.error(f"{name}: 원문 낱말 {total}개 중 {lost}개가 청크에 없음 ({sample})")
    else:
        r.info.append(f"{name}: 원문 낱말 {total}개 모두 청크에 들어감")
    return r


def check_foreign(source: str, produced: str, name: str, allowed: set[str]) -> Report:
    """결과에만 있고 원문에 없는 낱말. 청크 머리표(섹션 경로, '항암요법:' 등) 낱말은 allowed로 뺀다."""
    r = Report()
    extra = set(tokens(produced)) - set(tokens(source)) - {a.lower() for a in allowed}
    if extra:
        r.error(f"{name}: 원문에 없는 낱말 {len(extra)}개가 청크에 있음 ({', '.join(sorted(extra)[:20])})")
    return r


def check_garbled(texts: dict[str, str]) -> Report:
    r = Report()
    for name, text in texts.items():
        for rx, label in _GARBLED:
            hits = rx.findall(text)
            if hits:
                r.error(f"{name}: {label} {len(hits)}개 ({''.join(hits[:5])!r})")
    return r


def check_drugs(chunks: list[dict], scans: dict, source_text: str) -> Report:
    """약제명 검사.

    - 청크의 drugs가 모두 알려진 약제명인지 (오류)
    - 약제가 하나도 없는 행 청크 (오류)
    - 원문 오타로 보고 바로잡은 낱말 (경고: 원문 오타일 수 있음)
    - 약제명 목록에 없고 가까운 것도 없는 낱말 (경고: 새 약제면 vocab.BREAST_EXTRA에 추가)
    """
    r = Report()
    known = known_drugs()
    for c in chunks:
        bad = [d for d in c["drugs"] if d not in known]
        if bad:
            r.error(f"{c['chunk_id']}: 목록에 없는 약제명 {bad}")
        if c["chunk_kind"] != "section" and not c["drugs"]:
            r.error(f"{c['chunk_id']}: 약제명을 하나도 찾지 못함")
    corrected = sorted({x for s in scans.values() for x in s.corrected})
    for tok, fix in corrected:
        r.warn(f"원문 오타로 보이는 약제명: '{tok}' -> '{fix}'로 읽음")
    unknown = sorted({x for s in scans.values() for x in s.unknown})
    if unknown:
        r.warn(f"약제명 목록에 없는 영문 낱말 (새 약제인지 확인): {', '.join(unknown)}")
    for tok, fix in typo_suspects(source_text):
        if (tok, fix) not in corrected:
            r.warn(f"원문에 약제명 오타로 보이는 낱말: '{tok}' (≈ {fix})")
    return r


# ---------- 5. 이전 실행과 비교 ----------

def check_counts(now: dict[str, int], before: dict[str, int] | None, max_drop: float = 0.2,
                 out_of_scope: set[str] = frozenset()) -> Report:
    """이전 정상 실행보다 행 수가 많이 줄면 오류. out_of_scope는 이번 실행에서 일부러 뺀 항목 (예: 허가초과 끔)."""
    r = Report()
    if not before:
        r.info.append("이전 정상 실행 기록 없음: 행 수 비교 생략")
        return r
    for key in sorted(set(now) | set(before)):
        if key in out_of_scope and key not in now:
            r.info.append(f"{key}: 이번 실행 범위에서 뺌 (이전 {before.get(key, 0)}건)")
            continue
        a, b = before.get(key, 0), now.get(key, 0)
        if a and b < a * (1 - max_drop):
            r.error(f"{key}: 행 수 {a} -> {b} (이전보다 {1 - b / a:.0%} 줄어듦, 잘렸을 수 있음)")
        elif a != b:
            r.warn(f"{key}: 행 수 {a} -> {b}")
    return r
