"""급여 청크 만들기 (schemas/chunk.json, doc_type = reimbursement).

청크 계층은 B의 설계 문서 reimbursement_chunking_design.md (2026-10-16) §0.2, chunk_id는 §2.5:
  L1 원칙       일반원칙(-general-*), 유방암 투여 원칙(-bc-principle), Ⅳ 기타 약제(-supp)    chunk_kind = section
  L2 단계·소단원  -bc-neo, -bc-neo-her2pos, -bc-pal-endo-1l, -combo, -supp-zoledronic …  chunk_kind = section
  L3 요법 행     표의 연번 하나(-bc-…-r01, -combo-r22), Ⅳ 약제의 조건 묶음(-supp-zoledronic-b)
                                                                    chunk_kind = reimbursement_condition
  L4 조건 항목   L3의 reimbursement.conditions (conditions.py, §3.5)
  행에는 그 행에 표시된 주N 각주와 연번 범위 규칙을 붙이고(§2.3), 공고 이력 전체(§2.4)와 요법 구조화(§8.4)를 넣는다.
  허가초과 목록 (설계 범위 밖, 파이프라인 --with-offlabel일 때만)
    - 인정 요법 한 줄                             chunk_kind = offlabel_regimen, source_type = baseline
    - 검토중 요법 한 줄                           chunk_kind = offlabel_regimen, source_type = preview

책자 표를 텍스트로 읽을 때 생기는 문제와 처리:
  - 병합 셀: 투여대상이 비어 있는 행은 바로 위 행의 투여대상을 물려받는다 (본문에 표시)
  - 쪽이 바뀌면 표 머리글('연번 항암요법 투여대상')이 반복되고, 앞 행의 남은 글이 그 뒤에 온다
    -> 다음 행 번호를 보고 이어지는 표의 마지막 행에 붙인다
  - 소단원 제목이 연달아 나오고 표가 뒤에 몰려 올 수 있다 ('나. 1차 이상', '다. 2차 이상' 다음에 표 2개)
    -> 새 표(연번 1)마다 아직 표가 없는 소단원을 차례로 배정한다
  - 어디에 붙일지 모르는 조각은 버리지 않고 parse_warnings에 남긴다

setting, subtype, line, drugs는 검색 하드 필터용 추정값이다. 넓게 잡는다 (애매하면 후보를 더 넣는다).
조건 판정은 하지 않는다. 조건 단위 구조화(reimbursement.conditions)는 §8 처리 흐름 6 (Claude API)에서 한다.

사용 (team_project 폴더에서):
    python -m src.reimbursement.chunks --booklet data/reimbursement/raw/공고책자_20261001.pdf \\
        --offlabel "data/reimbursement/raw/사전신청요법_(용법용량 포함)및 불승인요법_261012.xlsx"
결과: data/reimbursement/chunks/reimbursement_chunks_<책자날짜>.jsonl (git에 올리지 않음)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .booklet import Booklet, item_tags, load_booklet
from .offlabel import OffLabel, load_offlabel
from .registry import CriterionItem
from .vocab import COMMON_WORDS, known_drugs, suggest_drug

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"
SCHEMA_PATH = ROOT / "schemas" / "chunk.json"
SCHEMA_VERSION = "0.1-draft"
BOARD_URL = "https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA030023030000"   # 항암화학요법 게시판
BREAST_TITLE = "9. 유방암"

MAIN_NAMES = {"1": "선행화학요법", "2": "수술후보조요법", "3": "고식적 내분비요법", "4": "고식적 항암화학요법"}
_MAIN = re.compile(r"^([1-4])\.\s*(선행화학요법|수술후보조요법|고식적\s*내분비요법|고식적\s*항암화학요법)")
_SUB = re.compile(r"^([가-하])\.\s*(투여단계\s*:\s*.+|HER2\s*(?:양성|음성)\s*유방암의\s*선행화학요법.*)$")
_ROW_NO = re.compile(r"^(\d{1,2})$")
_NOTE = re.compile(r"^주\s*\d+\s*\.")
_TAG_LINE = re.compile(r"^\(?\s*(?:개정\s*)?제\s*\d{4}\s*-\s*\d+\s*호")
_ENDS_WITH_TAG = re.compile(r"\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.*\s*\)\s*$")
_HANGUL_WORD = re.compile(r"[가-힣]{2,}")
_SUB_ASCII = {c: a for c, a in zip("가나다라마바사아자차카타파하", "abcdefghijklmn")}
# 치료 단계 (설계 §2.1 L2 stage)와 chunk_id 조각 (§2.5)
STAGE_OF_MAIN = {"1": "neoadjuvant", "2": "adjuvant", "3": "palliative_endocrine", "4": "palliative_chemo"}
MAIN_SLUG = {"1": "neo", "2": "adj", "3": "pal-endo", "4": "pal-chemo"}
# 투여단계: (패턴, chunk_id 조각, 공고 표기). '이상'을 먼저 본다
_LINE_RULES = [(re.compile(r"1\s*차\s*이상"), "1lplus", "1차 이상"),
               (re.compile(r"2\s*차\s*이상"), "2lplus", "2차 이상"),
               (re.compile(r"3\s*차\s*이상"), "3lplus", "3차 이상"),
               (re.compile(r"1\s*차"), "1l", "1차"),
               (re.compile(r"2\s*차"), "2l", "2차")]


# ---------- 책자 표 읽기 ----------

@dataclass
class Row:
    no: int
    lines: list[str] = field(default_factory=list)
    pages: set[int] = field(default_factory=set)      # PDF 쪽

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


@dataclass
class Subsection:
    main: str                    # '1'..'4'
    sub: str | None              # '가'.. 또는 None (소단원이 없는 대단원)
    title: str                   # 'HER2 양성 유방암의 선행화학요법', '투여단계: 1차 이상'
    main_title: str = ""         # 원문 대단원 제목 '선행화학요법(neoadjuvant)'
    notes: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    pages: set[int] = field(default_factory=set)
    has_table: bool = False

    @property
    def key(self) -> str:
        """chunk_id 조각 (설계 §2.5): bc-neo-her2pos, bc-adj, bc-pal-endo-1l, bc-pal-chemo-2lplus."""
        base = f"bc-{MAIN_SLUG[self.main]}"
        if self.sub is None:
            return base
        if self.main == "1":
            return f"{base}-{'her2pos' if self.her2_section == 'positive' else 'her2neg'}"
        slug = next((s for rx, s, _ in _LINE_RULES if rx.search(self.title)), None)
        return f"{base}-{slug or _SUB_ASCII.get(self.sub, 'x')}"

    @property
    def stage(self) -> str:
        return STAGE_OF_MAIN[self.main]

    @property
    def line_rule(self) -> str | None:
        """공고 투여단계 ('1차', '1차 이상', '2차', '2차 이상', '3차 이상'). 고식적 요법 소단원만."""
        if self.main not in ("3", "4") or self.sub is None:
            return None
        return next((r for rx, _, r in _LINE_RULES if rx.search(self.title)), None)

    @property
    def her2_section(self) -> str | None:
        """선행화학요법 소단원의 HER2 구분."""
        if self.main != "1" or self.sub is None:
            return None
        return "positive" if re.search(r"HER2\s*양성", self.title) else "negative"

    @property
    def path(self) -> str:
        head = f"{self.main}. {self.main_title or MAIN_NAMES[self.main]}"
        return f"{head} > {self.sub}. {self.title}" if self.sub else head


@dataclass
class BreastTable:
    principles: list[str]
    principles_pages: set[int]
    subsections: list[Subsection]
    warnings: list[str]


def _table_header_at(lines: list[str], i: int) -> bool:
    return (lines[i].strip() == "연번" and i + 2 < len(lines)
            and lines[i + 1].strip() == "항암요법" and lines[i + 2].strip() == "투여대상")


def _is_complete(row: Row) -> bool:
    """행이 공고 표시 '(... 2021.6.1.)'로 끝났는가. 아니면 다음 쪽에 이어지는 글이 있다."""
    return bool(_ENDS_WITH_TAG.search(row.text))


def parse_breast_table(b: Booklet) -> BreastTable:
    s = b.section("유방암")
    text = b.section_text("유방암")
    lines: list[tuple[str, int]] = []
    for k, page_text in enumerate(text.split("\f")):
        for ln in page_text.splitlines():
            if ln.strip():
                lines.append((ln.rstrip(), s.start + k))
    only = [ln for ln, _ in lines]

    principles, principles_pages = [], set()
    subs: list[Subsection] = []
    queue: list[Subsection] = []          # 표를 아직 못 받은 소단원
    current: Subsection | None = None     # 지금 행을 받는 소단원
    note_target: Subsection | None = None
    buffer: list[tuple[str, int]] = []    # 반복 머리글 뒤, 행 번호 전의 글
    mode = "principles"                   # principles / pre / note / header / row
    warnings: list[str] = []

    def last_row_of(sub: Subsection | None) -> Row | None:
        return sub.rows[-1] if sub and sub.rows else None

    def flush_buffer_to(row: Row | None, why: str) -> None:
        if not buffer:
            return
        if row is None:
            warnings.append(f"붙일 행을 찾지 못한 조각 ({why}): " + " / ".join(t for t, _ in buffer))
        else:
            row.lines += [t for t, _ in buffer]
            row.pages |= {p for _, p in buffer}
        buffer.clear()

    i = 0
    while i < len(lines):
        ln, page = lines[i]
        t = ln.strip()
        m_main, m_sub = _MAIN.match(t), _SUB.match(t)
        if m_main:
            main_title = t[m_main.end(1) + 1:].strip()
            node = Subsection(m_main.group(1), None, MAIN_NAMES[m_main.group(1)], main_title, pages={page})
            subs.append(node)
            queue.append(node)
            note_target, mode = node, "pre"
        elif m_sub and subs:
            node = Subsection(subs[-1].main, m_sub.group(1), m_sub.group(2).strip(), subs[-1].main_title,
                              pages={page})
            subs.append(node)
            queue.append(node)
            note_target, mode = node, "pre"
        elif _table_header_at(only, i):
            i += 3
            mode = "header"
            continue
        elif mode in ("header", "row") and _ROW_NO.match(t):
            n = int(t)
            if n == 1:
                # 새 표: 앞의 남은 조각은 이어지지 못한 마지막 행에 붙인다
                target = next((r for r in (last_row_of(x) for x in reversed(subs) if x.has_table)
                               if r and not _is_complete(r)), None)
                flush_buffer_to(target, "새 표 앞")
                # 대단원 바로 뒤에 소단원이 오면 대단원은 표를 받지 않는다
                while queue and len(queue) > 1 and queue[0].sub is None and queue[1].main == queue[0].main \
                        and queue[1].sub is not None:
                    queue.pop(0)
                if queue:
                    current = queue.pop(0)
                elif current is None:
                    warnings.append(f"소단원 없이 시작한 표 (PDF {page}쪽)")
                    current = Subsection("4", None, MAIN_NAMES["4"], MAIN_NAMES["4"])
                    subs.append(current)
                current.has_table = True
                current.rows.append(Row(n, pages={page}))
            else:
                owner = current if last_row_of(current) and last_row_of(current).no == n - 1 else \
                    next((x for x in reversed(subs) if last_row_of(x) and last_row_of(x).no == n - 1), None)
                if owner is None:
                    warnings.append(f"연번 {n}을 이어 받을 표가 없음 (PDF {page}쪽)")
                    owner = current
                flush_buffer_to(last_row_of(owner), f"연번 {n} 앞")
                owner.rows.append(Row(n, pages={page}))
                current = owner
            note_target = current
            mode = "row"
        elif _NOTE.match(t):
            mode = "note"
            target = note_target or current
            if target:
                target.notes.append(t)
                target.pages.add(page)
        elif mode == "principles":
            principles.append(t)
            principles_pages.add(page)
        elif mode in ("pre", "note"):
            target = note_target or current
            if target:
                target.notes.append(t)
                target.pages.add(page)
        elif mode == "header":
            buffer.append((t, page))
        else:   # row
            row = last_row_of(current)
            row.lines.append(t)
            row.pages.add(page)
        i += 1
    flush_buffer_to(None, "섹션 끝")
    for sub in subs:
        for r in sub.rows:
            sub.pages |= r.pages
    return BreastTable(principles, principles_pages, subs, warnings)


# ---------- 40. 기타 항암제 병용요법 표의 유방암 행 ----------

COMBO_HEADER = ("연번", "주요", "암종", "항암제 병용요법", "허가사항", "급여 요법", "급여기준", "비고")
COMBO_TITLE = "40. 기타 항암제 병용요법"
# 주요 암종 칸 (줄바꿈으로 '비소', '세포', '폐암'처럼 쪼개져 나온다)
_CANCER_END = re.compile(r"(암|육종|림프종|골수종|백혈병|종양)$")


@dataclass
class ComboRow:
    no: int
    cancer: str                 # 이 행이 속한 암종 (칸이 병합돼 있어 첫 행에만 적혀 있다)
    lines: list[str] = field(default_factory=list)
    pages: set[int] = field(default_factory=set)
    starts_group: bool = False  # 이 행에 암종 칸 글이 적혀 있음

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


@dataclass
class ComboTable:
    intro: list[str]            # 표 앞 안내 (본인부담 조건 가)·나)·다), 주의사항)
    rows: list[ComboRow]        # 모든 암종의 행
    warnings: list[str]

    @property
    def breast(self) -> list[ComboRow]:
        return [r for r in self.rows if r.cancer == "유방암"]


def _combo_header_at(lines: list[str], i: int) -> bool:
    return tuple(x.strip() for x in lines[i:i + len(COMBO_HEADER)]) == COMBO_HEADER


def parse_combination(b: Booklet) -> ComboTable:
    """'40 기타 항암제 병용요법' 표를 행으로 나눈다. 행 번호는 1부터 하나씩 늘어나는 숫자만 쓴다."""
    s = b.section("combination")
    lines: list[tuple[str, int]] = []
    for k, page_text in enumerate(b.section_text("combination").split("\f")):
        for ln in page_text.splitlines():
            if ln.strip():
                lines.append((ln.strip(), s.start + k))
    only = [ln for ln, _ in lines]
    intro, rows, warnings = [], [], []
    cancer = ""
    i = 0
    while i < len(lines):
        t, page = lines[i]
        if _combo_header_at(only, i):
            i += len(COMBO_HEADER)
            continue
        expected = rows[-1].no + 1 if rows else 1
        if t == str(expected):
            # 행 첫머리의 한글 줄이 암종 칸이면 새 암종 묶음이 시작된다
            j, name = i + 1, ""
            while j < len(lines) and re.fullmatch(r"[가-힣 ]+", only[j]) and len(name) < 12:
                name += only[j].replace(" ", "")
                j += 1
                if _CANCER_END.search(name):
                    break
            starts = bool(name and _CANCER_END.search(name))
            if starts:
                cancer, i = name, j
            else:
                i += 1
            rows.append(ComboRow(expected, cancer, pages={page}, starts_group=starts))
            continue
        if rows:
            rows[-1].lines.append(t)
            rows[-1].pages.add(page)
        elif t != "40" and not t.startswith("기타 항암제 병용요법"):
            intro.append(t)
        i += 1
    if not any(r.cancer == "유방암" for r in rows):
        warnings.append("병용요법 표에서 유방암 행을 찾지 못함")
    # 행 번호 줄이 빠지면 다음 행이 앞 행에 묻힌다: 숫자만 있는 줄이 행 안에 남아 있으면 의심
    for r in rows:
        stray = [ln for ln in r.lines if re.fullmatch(r"\d{1,3}", ln) and int(ln) > r.no]
        if stray and r.cancer == "유방암":
            warnings.append(f"병용요법 연번 {r.no} 안에 행 번호로 보이는 줄 {stray} (행 경계를 놓쳤을 수 있음)")
    return ComboTable(intro, rows, warnings)


_SETTING_MARK = re.compile(r"[\[(]\s*(선행화학요법|수술\s*후\s*보조요법|수술후보조요법)\s*[\])]")
_PALLIATIVE_MARK = re.compile(r"\(\s*(\d\s*차[^()]*?),\s*고식적[^()]*\)")


def combo_filters(text: str) -> tuple[list[str], list[str]]:
    """(setting, line). 칸 끝의 '(1차 이상, 고식적 내분비요법)', '(선행화학요법)' 표시로 정한다."""
    flat = re.sub(r"\s+", " ", text)
    lines = []
    for m in _SETTING_MARK.finditer(flat):
        lines.append("neoadjuvant" if "선행" in m.group(1) else "adjuvant")
    if lines:
        return ["early", "locally_advanced"], list(dict.fromkeys(lines))
    m = _PALLIATIVE_MARK.search(flat)
    return settings_for("4", flat), (lines_from(m.group(1)) if m else None) or ["any"]


# ---------- 행 나누기와 추정 ----------

def _is_tag_piece(line: str) -> bool:
    return bool(_TAG_LINE.match(line) or re.match(r"^[\d.,)\s]", line))


def split_row(text: str) -> tuple[str, str, str]:
    """(항암요법, 투여대상, 공고 표시).

    공고 표시는 칸 맨 끝에 오므로 첫 표시 줄부터 끝까지를 표시로 본다
    (줄바꿈된 '2021.6.1., 개정 제2024-188호' 같은 조각이 투여대상에 섞이지 않게).
    그 앞에서는 한글 낱말(2자 이상)이 처음 나오는 줄부터 투여대상이다.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    cut = next((k for k, ln in enumerate(lines) if _TAG_LINE.match(ln)), len(lines))
    # 표시 뒤에 온 글 중 표시가 줄바꿈된 조각('0., 개정 ...')이 아닌 것은 다음 쪽에서 넘어온 투여대상이다
    body = lines[:cut] + [ln for ln in lines[cut:] if not _is_tag_piece(ln)]
    tags = "\n".join(ln for ln in lines[cut:] if _is_tag_piece(ln))
    for k, ln in enumerate(body):
        if _HANGUL_WORD.search(re.sub(r"주\s*\d+", "", ln)):
            return " ".join(body[:k]).strip(), "\n".join(body[k:]).strip(), tags
    return " ".join(body).strip(), "", tags


# 변경 표시는 책자 검사와 같은 규칙(booklet.ITEM_TAG, 쌍점·쉼표 표기 모두)으로 읽는다
row_tags = item_tags


_STOP = {"iv", "sc", "po", "lhrh", "agonist", "weekly", "and", "or", "dose", "dense", "intra",
         "peritoneal", "mg", "chemotherapy", "therapy", "endocrine", "aromatase", "inhibitor",
         "inhibitors", "fixed", "combination", "followed", "by", "neoadjuvant", "adjuvant", "with",
         "platinum", "taxane", "anthracycline", "cdk", "non", "pcr", "her", "plus", "q", "w", "d",
         "dose-dense", "non-pcr", "regimen", "therapy"}
_MULTI = [(re.compile(r"trastuzumab\s+deruxtecan|t-?dxd", re.I), "trastuzumab deruxtecan"),
          (re.compile(r"trastuzumab\s+emtansine|t-?dm1", re.I), "trastuzumab emtansine"),
          (re.compile(r"sacituzumab\s+govitecan", re.I), "sacituzumab govitecan"),
          # 공용 사전(data/dictionaries) 표기에 맞춘다: nab-paclitaxel, megestrol
          (re.compile(r"albumin[-\s]*bound\s+paclitaxel|nab-?paclitaxel", re.I), "nab-paclitaxel"),
          (re.compile(r"megestrol\s+acetate", re.I), "megestrol"),
          # 공용 사전(drug_classes.csv) 표기. 설계 §8.4는 'pegylated liposomal doxorubicin'을 제안했지만
          # 환자 이력·지침 추천 약제가 모두 공용 사전으로 정규화되므로 사전 이름에 맞춘다 (2026-10-17)
          (re.compile(r"(?:pegylated\s+)?liposomal\s+doxorubicin", re.I), "liposomal doxorubicin"),
          (re.compile(r"zoledronic\s+acid", re.I), "zoledronic acid"),
          (re.compile(r"sodium\s+thiosulfate", re.I), "sodium thiosulfate")]
_ABBR = {"AC": ["doxorubicin", "cyclophosphamide"], "EC": ["epirubicin", "cyclophosphamide"],
         "TC": ["docetaxel", "cyclophosphamide"], "TAC": ["docetaxel", "doxorubicin", "cyclophosphamide"],
         "DA": ["docetaxel", "doxorubicin"], "ED": ["docetaxel", "epirubicin"],
         "FEC": ["fluorouracil", "epirubicin", "cyclophosphamide"],
         "CMF": ["cyclophosphamide", "methotrexate", "fluorouracil"],
         "TCHP": ["docetaxel", "carboplatin", "trastuzumab", "pertuzumab"],
         "LHRH": ["goserelin", "leuprolide"]}
_KO = {"토레미펜": "toremifene", "레트로졸": "letrozole", "타목시펜": "tamoxifen",
       "아나스트로졸": "anastrozole", "엑스메스탄": "exemestane",
       "팔보시클립": "palbociclib", "풀베스트란트": "fulvestrant"}


@dataclass
class DrugScan:
    drugs: list[str]                              # 알려진 약제명 (나온 순서, 중복 없음)
    corrected: list[tuple[str, str]]              # 오타로 보고 바로잡은 것 [(원문 낱말, 약제명)]
    unknown: list[str]                            # 약제명 목록에 없고 가까운 것도 없는 낱말


def scan_drugs(regimen: str) -> DrugScan:
    """요법 문자열에서 약제명을 찾는다. 알려진 약제명(vocab)만 drugs에 넣는다."""
    known = known_drugs()
    found: list[str] = []
    corrected, unknown = [], []
    rest = regimen
    for rx, name in _MULTI:
        if rx.search(rest):
            found.append(name)
            rest = rx.sub(" ", rest)
    for abbr, names in _ABBR.items():
        if re.search(rf"(?<![A-Za-z]){abbr}(?![A-Za-z])", rest):     # 'TCHP' 안의 'TC'는 아니다
            found += names
    for ko, name in _KO.items():
        if ko in rest:
            found.append(name)
    for tok in re.findall(r"[a-z][a-z\-]{3,}", rest.lower()):
        tok = tok.strip("-")
        if tok in _STOP or tok.upper() in _ABBR or tok in COMMON_WORDS:
            continue
        if tok in known:
            found.append(tok)
        elif (s := suggest_drug(tok)) is not None:
            found.append(s)
            corrected.append((tok, s))
        else:
            unknown.append(tok)
    return DrugScan(list(dict.fromkeys(found)), list(dict.fromkeys(corrected)),
                    list(dict.fromkeys(unknown)))


def extract_drugs(regimen: str) -> list[str]:
    """요법 문자열 -> 일반명 소문자 목록 (나온 순서, 중복 없음)."""
    return scan_drugs(regimen).drugs


_LINE_MAP = [(re.compile(r"1\s*차\s*이상"), ["1L", "2L", ">=3L"]),
             (re.compile(r"2\s*차\s*이상"), ["2L", ">=3L"]),
             (re.compile(r"3\s*차\s*이상"), [">=3L"]),
             (re.compile(r"1\s*차"), ["1L"]),
             (re.compile(r"2\s*차"), ["2L"])]


def lines_from(text: str) -> list[str] | None:
    for rx, out in _LINE_MAP:
        if rx.search(text):
            return out
    return None


def subtypes_from(text: str, hr_implied: bool = False) -> list[str]:
    """본문의 HER2·호르몬 수용체 표기로 아형 후보를 넓게 잡는다. 근거가 없으면 ['any']."""
    t = re.sub(r"\s+", " ", text)
    if re.search(r"(?m)^\s*가\.", text) and re.search(r"(?m)^\s*나\.", text):
        return ["any"]          # '가. ... 나. ...' 선택 조건이면 하나로 좁히지 않는다
    if re.search(r"삼중\s*음성", t):
        return ["TNBC"]
    her2_pos = bool(re.search(r"HER2\s*(양성|과발현)|HER2\+", t))
    her2_neg = bool(re.search(r"HER2\s*음성|HER2-(?!/)", t))
    hr_pos = hr_implied or bool(re.search(r"호르몬\s*(수용체\s*)?(-\s*)?양성|에스트로겐\s*수용체\s*(\(ER\)\s*)?양성|HR\s*\+|HR\(Hormone Receptor\)\s*양성", t))
    her2 = "pos" if her2_pos and not her2_neg else "neg" if her2_neg and not her2_pos else None
    if her2 == "pos":
        return ["HR+/HER2+"] if hr_pos else ["HR+/HER2+", "HR-/HER2+"]
    if her2 == "neg":
        return ["HR+/HER2-"] if hr_pos else ["HR+/HER2-", "TNBC"]
    return ["HR+/HER2-", "HR+/HER2+"] if hr_pos else ["any"]


def settings_for(main: str | None, text: str) -> list[str]:
    if main in ("1", "2"):
        return ["early", "locally_advanced"]
    if main in ("3", "4"):
        # field_values.csv L2: 고식적 요법은 전이성 + '국소진행성이면서 수술 불가'도 포함한다.
        # 검색 필터는 넓게 잡고, 행마다 국소진행성 허용 여부는 conditions(disease, operable)로 가른다
        return ["locally_advanced", "metastatic"]
    return ["early", "locally_advanced", "metastatic"]


def _latest_tag(text: str, fallback_no: str, fallback_date: date) -> tuple[str, date]:
    tags = row_tags(text)
    if not tags:
        return fallback_no, fallback_date
    no, d = max(tags, key=lambda x: x[1])
    return no, d


def _pages(b: Booklet, pdf_pages: set[int]) -> tuple[int | None, int | None]:
    printed = [p for p in (b.printed_page(x) for x in sorted(pdf_pages)) if p is not None]
    return (min(printed), max(printed)) if printed else (None, None)


def _norm_key(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣+]", "", s.lower())


# ---------- 청크 만들기 ----------

# 검색 가중치 태그. 어휘는 src/rag/rag_guideline_chunking_design_update.md §3.5 제안 (biomarker_record.rag_tags와
# 같은 단어). 본문에 그 마커가 적혀 있을 때만 붙인다 (원문에 없는 태그를 만들지 않음).
# ER-low, Ki-67-high는 B 코드(BM1)가 rag_tags에 실제로 쓰는 철자를 따른다 (설계 문서의 Ki67-high가 아님).
_TAG_RULES = [
    ("HER2-low", re.compile(r"HER2\s*[-‐]?\s*(?:저발현|low)", re.I)),
    ("HER2-ultralow", re.compile(r"HER2\s*[-‐]?\s*(?:초저발현|ultra-?low)", re.I)),
    ("ER-low", re.compile(r"(?<![A-Za-z])ER\s*[-‐]?\s*(?:저발현|low)")),
    ("Ki-67-high", re.compile(r"Ki\s*-?\s*67", re.I)),
    ("sBRCA", re.compile(r"somatic\s*BRCA|체세포\S{0,6}\s*BRCA|sBRCA", re.I)),
    ("gBRCA", re.compile(r"BRCA")),           # 체세포라고 적힌 경우는 아래에서 뺀다
    # 유전자 태그는 B 코드(BM1 GENE_TAGS, 2026-10-17)의 철자: PALB2-mut, PTEN-loss
    ("PALB2-mut", re.compile(r"PALB2")),
    ("PIK3CA-mut", re.compile(r"PIK3CA")),
    ("AKT1-mut", re.compile(r"AKT1")),
    ("PTEN-loss", re.compile(r"PTEN")),
    ("ESR1-mut", re.compile(r"ESR1")),
    # PD-L1은 B의 PDL1_RULES 태그: 22C3 CPS ≥ 10 -> PD-L1-CPS10, SP142 IC -> PD-L1-SP142.
    # 'PD-L1 inhibitor'(약 계열)는 검사 결과가 아니므로 뺀다
    ("PD-L1-CPS10", re.compile(r"PD-L1\s*(?:발현\s*양성)?\s*\(?\s*CPS|CPS\s*≥\s*10", re.I)),
    ("PD-L1-SP142", re.compile(r"SP142")),
]

# 요법 이름 뒤에 붙은 각주 표시 (예: 'anastrozole주2', 'trastuzumab(IV, SC) 주1+ docetaxel').
# 본문(text)에는 원문대로 두고 reimbursement.regimen 값에서만 뗀다.
_FOOTNOTE = re.compile(r"(?<!\d)\s*주\s?\d+(?!\s*[기일간])")


def clean_regimen(s: str) -> str:
    s = _FOOTNOTE.sub(" ", s)
    s = re.sub(r"\s+([+→±])", r" \1", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def biomarker_tags_from(text: str) -> list[str]:
    tags = [t for t, rx in _TAG_RULES if rx.search(text)]
    if "sBRCA" in tags and not re.search(r"gBRCA|germline|생식세포", text, re.I):
        tags.remove("gBRCA")            # 'Somatic BRCA1/2'만 있으면 gBRCA가 아니다
    return tags


def _base(chunk_id: str, source: str, version: str, section: str, text: str, kind: str,
          setting: list[str], subtype: list[str], line: list[str], drugs: list[str],
          reimbursement: dict, parent_id: str | None = None,
          page_start: int | None = None, page_end: int | None = None) -> dict:
    # 판정용 정규화 본문은 지침 청크와 같이 쓰도록 청크 최상위 칸에 둔다 (2026-10-20 결정, C 제안)
    normalized = reimbursement.pop("text_normalized", None)
    chunk = {
        "schema_version": SCHEMA_VERSION, "chunk_id": chunk_id, "doc_type": "reimbursement",
        "source": source, "version": version, "section": section,
        "page_start": page_start, "page_end": page_end, "url": BOARD_URL,
        "chunk_kind": kind, "parent_id": parent_id, "text": text,
        "setting": setting, "subtype": subtype, "line": line,
        "biomarker_tags": biomarker_tags_from(text), "drugs": drugs, "evidence": None,
        "superseded_by": None, "copyright_notice": None,
        "reimbursement": reimbursement,
    }
    if normalized is not None:
        chunk["text_normalized"] = normalized
    return chunk


GENERAL_TITLE = "항암요법의 요양급여 적용 일반원칙"
# 일반원칙 중 처방 판단에 쓰는 앞부분만 청크로 만든다. '[별표] 허가초과 승인 기준 및 절차'와
# '첨부' 서식(신청서·사용 내역)은 요양기관 행정 절차라서 뺀다.
# 쪽 경계 '\f' 뒤도 줄 시작으로 본다
_GENERAL_END = re.compile(r"(?m)(?:^|(?<=\f))\s*\[별표\]")
_GENERAL_HEAD = re.compile(r"(?m)(?:^|(?<=\f))[ \t]*(?:[1-9]\.\s+\S.*|※\s*참고사항.*)$")


def general_source(b: Booklet) -> str:
    """일반원칙 중 청크로 만드는 부분의 원문 ([별표] 앞까지). 섹션이 없으면 빈 문자열."""
    if "general" not in b.sections:
        return ""
    full = b.section_text("general")
    end = _GENERAL_END.search(full)
    return full[:end.start()] if end else full


def general_chunks(b: Booklet) -> list[dict]:
    """일반원칙 (모든 암종 공통: 급여 범위·본인부담, 투여기준, 반응평가, 용어 정의).
    유방암 행에 '주단위 요법은 일반원칙에 따름'처럼 이 부분을 가리키는 경우가 있어 함께 넣는다."""
    body = general_source(b)
    if not body:
        return []
    s = b.sections["general"]
    heads = list(_GENERAL_HEAD.finditer(body))
    if not heads:
        return []
    prelude = body[:heads[0].start()].strip()           # 제목과 개정 이력 줄
    no, d = _latest_tag(prelude, b.doc_no, b.file_date)
    prefix = f"hira-booklet-{b.file_date:%Y%m%d}-general"
    out = []
    for i, h in enumerate(heads):
        stop = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        piece = body[h.start():stop].strip()
        if i == 0:
            piece = prelude + "\n" + piece
        heading = h.group(0).strip()
        first = s.start + body[:h.start()].count("\f")
        last = s.start + body[:stop].rstrip().count("\f")
        ps, pe = _pages(b, set(range(first, last + 1)))
        slug = "terms" if heading.startswith("※") else heading.split(".", 1)[0]
        out.append(_base(
            f"{prefix}-{slug}", "HIRA-booklet", b.file_date.isoformat(), f"{GENERAL_TITLE} > {heading}",
            f"[{GENERAL_TITLE} > {heading}]\n" + piece.replace("\f", "\n"), "section",
            ["early", "locally_advanced", "metastatic"], ["any"], ["any"], [],
            {"source_type": "baseline", "notice_no": f"제{no}호", "effective_from": d.isoformat()},
            page_start=ps, page_end=pe))
    return out


@dataclass
class BookletChunks:
    chunks: list[dict]
    items: list[CriterionItem]      # 레지스트리용 (행 단위)
    warnings: list[str]
    table: BreastTable | None = None
    combo: ComboTable | None = None
    drug_scans: dict[str, DrugScan] = field(default_factory=dict)   # chunk_id -> 약제명 찾기 결과
    contexts: dict[str, str] = field(default_factory=dict)          # L3 chunk_id -> 조건 구조화 때 함께 넘길 소단원 글
    supp_sources: dict[str, str] = field(default_factory=dict)      # 'other:…' 섹션 -> 그 섹션에서 청크에 넣은 글


def _item(key: str, seen: dict[str, int], text: str, eff: date | None, page: int | None,
          chunk_id: str) -> CriterionItem:
    seen[key] = seen.get(key, 0) + 1
    if seen[key] > 1:
        key += f"#{seen[key]}"
    return CriterionItem(key, text, effective_from=eff, source_page=page,
                         meta_json=json.dumps({"chunk_id": chunk_id}, ensure_ascii=False))


# ---------- 행에 붙이는 것: 주N 각주, 연번 범위 규칙, 공고 이력 (설계 §2.3, §2.4) ----------

_NOTE_HEAD = re.compile(r"^주\s*(\d+)\s*\.")
_RANGE_HEAD = re.compile(r"^연번\s*(\d+)\s*[∼~\-]\s*(\d+)")
# 행 안의 각주 표시 ('letrozole주1', '(CPS≥10)주3', 'trastuzumab(IV, SC) 주1+'). '4주 간격'·'주기'는 아니다
_MARK = re.compile(r"(?<![\d가-힣])주\s?(\d+)(?!\s*[기일간주])")


@dataclass
class SubNotes:
    head: list[str]                              # 표 앞 머리 규칙
    footnotes: dict[str, list[str]]              # '1' -> ['주1. …', '▪ …']
    ranges: list[tuple[int, int, list[str]]]     # (연번 시작, 끝, 줄)


def split_notes(notes: list[str]) -> SubNotes:
    head: list[str] = []
    foot: dict[str, list[str]] = {}
    ranges: list[tuple[int, int, list[str]]] = []
    cur = head
    for ln in notes:
        if m := _NOTE_HEAD.match(ln):
            cur = foot.setdefault(m.group(1), [])
        elif m := _RANGE_HEAD.match(ln):
            cur = []
            ranges.append((int(m.group(1)), int(m.group(2)), cur))
        cur.append(ln)
    return SubNotes(head, foot, ranges)


def footnote_marks(*texts: str) -> list[str]:
    return list(dict.fromkeys(m.group(1) for t in texts for m in _MARK.finditer(t)))


def history_of(text: str) -> list[dict]:
    """행의 공고 이력 전체 (시행일 순). notice_no·effective_from은 이 중 가장 늦은 것."""
    seen = {}
    for no, d in row_tags(text):
        seen[(d, no)] = {"notice_no": f"제{no}호", "effective_from": d.isoformat()}
    return [seen[k] for k in sorted(seen)]


# ---------- 요법 구조화 (설계 §8.4) ----------

_COPAY_AFTER = re.compile(r"([A-Za-z][A-Za-z\-\s]*?)\s*\(\s*(\d+)\s*/\s*100\s*\)")
_ROUTE_AFTER = re.compile(r"([A-Za-z][A-Za-z\-\s]*?)\s*\(\s*((?:IV|SC|PO)(?:\s*,\s*(?:IV|SC|PO))*)\s*\)")
_FDC = re.compile(r"\[([^\]]+)\]\s*(SC|IV)\s*\(\s*(\d+)\s*/\s*100\s*\)")


def _last_drug(s: str) -> str | None:
    d = scan_drugs(s).drugs
    return d[-1] if d else None


def parse_regimen(regimen: str, attached: str = "") -> dict:
    """요법 문자열 -> {sequence, optional_drugs, routes, copay_by_drug, fixed_dose_combination}.

    sequence: 'A → B'면 [[A 약제], [B 약제]], 순차가 아니면 []
    optional_drugs: '± pertuzumab'의 약제
    routes: 'trastuzumab(IV, SC)' -> {trastuzumab: [IV, SC]}
    copay_by_drug: 'pertuzumab(30/100)' -> {pertuzumab: 30/100}
    fixed_dose_combination: 붙은 주석의 '[pertuzumab + trastuzumab] SC (30/100)'
    """
    s = clean_regimen(regimen)
    copay = {d: f"{m.group(2)}/100" for m in _COPAY_AFTER.finditer(s) if (d := _last_drug(m.group(1)))}
    routes = {d: [x.strip() for x in m.group(2).split(",")]
              for m in _ROUTE_AFTER.finditer(s) if (d := _last_drug(m.group(1)))}
    plain = re.sub(r"\(\s*\d+\s*/\s*100\s*\)|\(\s*(?:IV|SC|PO)(?:\s*,\s*(?:IV|SC|PO))*\s*\)", "", s)
    parts = [p for p in re.split(r"→", plain) if p.strip()]
    sequence = [scan_drugs(p).drugs for p in parts] if len(parts) > 1 else []
    optional = [d for m in re.finditer(r"±\s*([A-Za-z][A-Za-z\-]*(?:\s+[a-z][a-z\-]+)?)", plain)
                for d in scan_drugs(m.group(1)).drugs]
    fdc = [{"drugs": scan_drugs(m.group(1)).drugs, "route": m.group(2), "copay": f"{m.group(3)}/100"}
           for m in _FDC.finditer(attached)]
    return {"sequence": sequence, "optional_drugs": list(dict.fromkeys(optional)), "routes": routes,
            "copay_by_drug": copay, "fixed_dose_combination": fdc}


_FOOT_COMBO = re.compile(r"‘([A-Za-z][A-Za-z\-]+)(?:\s*\(품명[^)]*\))?’\s*과\s*병용\s*투여하는\s*경우")


def footnote_combination(attached: str) -> dict | None:
    """붙은 각주의 '동 요법을 … ‘X(품명: …)’과 병용 투여하는 경우, … ‘X’ 약값전액본인부담(100/100)'
    -> {added_drug: [X], added_drug_coverage: '100/100'}. 없으면 None."""
    m = _FOOT_COMBO.search(attached)
    if not m:
        return None
    drug = m.group(1)
    flat = re.sub(r"\s+", "", attached)
    full = re.search(rf"‘{re.escape(drug)}’약값전액본인부담\(100/100\)", flat)
    return {"added_drug": scan_drugs(drug).drugs or [drug.lower()],
            "added_drug_coverage": "100/100" if full else None}


def copay_text(parsed: dict, drugs: list[str]) -> str | None:
    """reimbursement.copay: 요법 전체에 하나로 정해질 때만 그 값('50/100' 등), 아니면 None.
    기준값은 regimen_parsed.copay_by_drug (약제별). 'trastuzumab + pertuzumab(30/100)'처럼 일부 약제에만
    붙은 값은 요법 전체 값이 아니므로 None (schema_proposal.md 'copay', B 동의 2026-10-20)."""
    c = parsed.get("copay_by_drug") or {}
    if len(set(c.values())) == 1 and drugs and set(drugs) <= set(c):
        return next(iter(c.values()))
    return None


def _normalized(text: str) -> str:
    """판정용 정규화 텍스트 (설계 §5: ①→1, ㎝→cm). 원문 text는 그대로 둔다."""
    return unicodedata.normalize("NFKC", text)


def _line_rule(stage: str, line: str | None) -> dict:
    return {"line_rule": {"stage": stage, "line": line}}


# ---------- 40. 기타 항암제 병용요법 행의 칸 나누기 (설계 §1.4) ----------

_BRACKET_ONLY = re.compile(r"^→?\s*\[[^\]]+\]$")


def _is_regimen_line(ln: str) -> bool:
    t = re.sub(r"\[[^\]]*\]|\(\s*비급여\s*\)", "", ln).strip()
    return bool(t) and not _HANGUL_WORD.search(t) and not re.search(r"[가-힣]", t) \
        and not t.lower().startswith("stage") and not t.startswith(("(", "※", "‘", "'", "’"))


def _continues(prev: str, cur: str) -> bool:
    return prev.rstrip().endswith(("+", "→", "±")) or cur.lstrip().startswith(("+", "→", "±", "(")) \
        or bool(_BRACKET_ONLY.match(prev.strip())) or cur.strip() == "agonist"


def _regimen_drugs(s: str) -> list[str]:
    # 'LHRH)'처럼 agonist 없는 LHRH는 허가사항 설명 속 낱말이다 (호르몬 이름)
    return scan_drugs(re.sub(r"LHRH(?!\s*agonist)", " ", s)).drugs


def combo_columns(r: ComboRow, learned_added: set[str]) -> dict:
    """병용요법 한 행 -> {combined, added_drug, added_drug_coverage, base_regimen}.

    열: 항암제 병용요법 / 허가사항(추가 약제 + 허가 문구) / 급여 요법(기존 급여 요법) / 급여기준 / 비고.
    허가사항 칸이 위 행과 병합된 행(ribociclib 보조요법 26~28)은 위 행에서 찾은 추가 약제를 쓴다.
    """
    lines = [ln.strip() for ln in r.lines if ln.strip()]
    i = 1
    while i < len(lines) and _continues(lines[i - 1], lines[i]):
        i += 1
    combined = " ".join(lines[:i])
    combined_drugs = scan_drugs(combined).drugs
    added: list[str] = []
    start = i
    if i < len(lines) and _is_regimen_line(lines[i]):
        cand = _regimen_drugs(lines[i])
        desc = []
        for ln in lines[i + 1:i + 14]:
            if _is_regimen_line(ln) and _regimen_drugs(ln):
                break
            desc.append(ln)
        is_label = re.search(r"\(\s*비급여\s*\)", lines[i]) or re.search(r"환자|이 약|병용|(?<![가-힣])성인", " ".join(desc))
        if cand and set(cand) <= set(combined_drugs) and is_label:
            added, start = cand, i + 1
    merged = not added
    if merged:
        added = [d for d in combined_drugs if d in learned_added]
    groups: list[list[str]] = []
    first_base = None
    prev = ""
    for k, ln in enumerate(lines[start:], start):
        if _is_regimen_line(ln) or ln.strip() == "agonist":
            if groups and prev and _continues(prev, ln):
                groups[-1].append(ln)
            else:
                groups.append([ln])
                if first_base is None and _regimen_drugs(ln):
                    first_base = k
            prev = ln
        else:
            prev = ""
    base = [clean_regimen(" ".join(g)) for g in groups if _regimen_drugs(" ".join(g))]
    coverage = "비급여" if re.search(r"\(\s*비급여\s*\)", combined + " ".join(lines[i:start])) else None
    # 급여기준 칸 이후의 글 (치료 단계를 정할 때 허가사항 문구에 속지 않게)
    criteria = "\n".join(lines[first_base:]) if first_base is not None else "\n".join(lines)
    return {"combined": clean_regimen(combined), "added_drug": added, "added_drug_coverage": coverage,
            "base_regimen": base, "merged": merged, "criteria": criteria}


def _combo_stage(text: str) -> tuple[str, str | None]:
    """급여기준 칸의 '(1차 이상, 고식적 내분비요법)', '(선행화학요법)' -> (기존 요법의 치료 단계, 투여단계)."""
    flat = re.sub(r"\s+", " ", text)
    m = _PALLIATIVE_MARK.search(flat)
    if m:
        stage = "palliative_endocrine" if "내분비" in flat[m.start():m.end()] else "palliative_chemo"
        return stage, next((r for rx, _, r in _LINE_RULES if rx.search(m.group(1))), None)
    if (m := _SETTING_MARK.search(flat)):
        return ("neoadjuvant" if "선행" in m.group(1) else "adjuvant"), None
    # 표시가 없는 행: 급여기준 칸의 낱말로 (inavolisib 29는 전이성, ribociclib 25~26은 수술후보조요법).
    # 전이성 행의 '수술후보조요법 투여 중 … 진행된 경우도 인정'에 속지 않게 전이성을 먼저 본다
    if re.search(r"전이성|재발성", flat):
        endocrine = re.search(r"fulvestrant|letrozole|anastrozole|exemestane|tamoxifen", flat)
        return ("palliative_endocrine" if endocrine else "palliative_chemo"), None
    if re.search(r"수술\s*후\s*보조요법|수술후보조요법", flat):
        return "adjuvant", None
    return "combination", None


# ---------- Ⅳ 기타 약제 (설계 §10.2) ----------

SUPP_TITLE = "Ⅳ. 기타 약제"
# (섹션 키, chunk_id 조각, 묶음을 나누는 줄 패턴 또는 None)
SUPP_DRUGS = [("other:G-CSF 주사제", "gcsf", re.compile(r"^(가|나)\.\s")),
              ("other:zoledronic acid 주사제", "zoledronic", re.compile(r"^(가|나)\.\s")),
              ("other:denosumab 주사제", "denosumab", None),
              # 유방암 문구는 없지만 모든 암종 공통 기준이라 넣는다 (설계 §10.1·§10.2, field_values.csv Ⅳ 1~5)
              ("other:sodium thiosulfate 주사제", "thiosulfate", None),
              ("other:dexrazoxane 주사제", "dexrazoxane", re.compile(r"^\((\d)\)\s"))]
# 쪽 옆 세로 글자 ('Ⅳ 기 타 약', '별 첨')가 본문에 섞여 나온다 (설계 §5)
_SIDEBAR = re.compile(r"[ⅠⅡⅢⅣ]\n(?:[가-힣](?:\n|$)){2,6}|\n별\n첨\s*$")
# 묶음 안의 항목 시작 줄. '-' 줄은 앞 항목에 딸린다 ('- adjuvant TAC…'), '- 아 래 -'만 따로
_ITEM_START = re.compile(r"^(○|\d\)\s|\*|※|\(\d\)|\(제\s*\d|-\s*(아|다)\s+(래|음)\s*-$|(가|나)\.\s)")
_COMMON = re.compile(r"^※\s*(허가사항 범위이지만|상기)")


def supp_lines(b: Booklet, key: str) -> list[str]:
    text = _SIDEBAR.sub("\n", b.section_text(key).replace("\f", "\n"))
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _items(lines: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    for ln in lines:
        if not out or _ITEM_START.match(ln):
            out.append([ln])
        else:
            out[-1].append(ln)
    return out


def _keep_item(item: list[str]) -> bool:
    """암종별 줄은 유방암(G-CSF 치료 목적은 고형암)만 남기고, 소아암 조항은 뺀다."""
    head = item[0]
    text = " ".join(item)
    if head.startswith("○"):
        return "유방" in text or "고형암" in text
    if "소아암" in text and "유방" not in text:
        return False
    return True


def _regimen_list(lines: list[str]) -> list[dict]:
    """G-CSF 요법 목록의 '- adjuvant TAC(…)' 줄 -> [{regimen, setting, drugs}]. 줄바꿈된 요법은 잇는다."""
    out: list[dict] = []
    for ln in lines:
        if ln.startswith("- "):
            out.append({"regimen": ln[2:].strip()})
        elif out and not ln.startswith(("주", "○", "※")):
            out[-1]["regimen"] += " " + ln
    for r in out:
        r["regimen"] = clean_regimen(r["regimen"])
        head = r["regimen"].split("(", 1)[0].lower()
        r["setting"] = [s for s in ("neoadjuvant", "adjuvant") if re.search(rf"(?<!neo){s}", head)] or ["any"]
        r["drugs"] = scan_drugs(r["regimen"]).drugs
        # 약제 구성이 같아도 순차 요법과 동시 투여는 다른 요법이다 (예: TAC와 AC → docetaxel)
        r["sequence"] = parse_regimen(r["regimen"].split(" ", 1)[1] if " " in r["regimen"] else r["regimen"])["sequence"]
    return out


def supportive_chunks(b: Booklet, prefix: str, ver: str) -> tuple[list[dict], list[CriterionItem], dict, dict]:
    """Ⅳ 기타 약제 중 유방암에 쓰는 약제: L1 'Ⅳ 기타 약제' / L2 약제 / L3 조건 묶음 (가·나, (1)~(3)).
    암종별 적용기준은 유방암 줄만, G-CSF 예방 요법 목록은 유방암 줄만 쓴다.
    sodium thiosulfate는 유방암 문구가 없지만 모든 암종 공통 기준이라 넣는다 (설계 §10.2)."""
    chunks, items, contexts, sources = [], [], {}, {}
    seen: dict[str, int] = {}
    l1_id = f"{prefix}-supp"
    common: list[str] = []
    headings: list[str] = []
    for key, slug, marker in SUPP_DRUGS:
        if key not in b.sections:
            continue
        s = b.sections[key]
        ps, pe = _pages(b, set(range(s.start, s.end + 1)))
        lines = supp_lines(b, key)
        no_line, heading = lines[0], lines[1]
        headings.append(f"{no_line}. {heading}")
        body = lines[2:]
        # 묶음 나누기. G-CSF 앞머리의 '가. filgrastim…/나. pegfilgrastim…' 약제 목록('인정'이 없는 묶음)은 L2로
        pre, bundles, head_list = [], [], []
        for ln in body:
            if marker and marker.match(ln):
                bundles.append([ln])
            elif bundles:
                bundles[-1].append(ln)
            else:
                pre.append(ln)
        if slug == "gcsf":
            head_list = [ln for x in bundles if "인정" not in " ".join(x) for ln in x]
            bundles = [x for x in bundles if "인정" in " ".join(x)]
        if not marker:
            bundles = [[]]          # denosumab: 앞머리 문장이 곧 조건이다
        l2_id = f"{l1_id}-{slug}"
        l2_title = f"{SUPP_TITLE} > {no_line}. {heading}"
        drug_common = []
        made = []
        for bundle in bundles:
            its = _items(bundle) if bundle else []
            drug_common += ["\n".join(it) for it in its if _COMMON.match(it[0])]
            kept = [it for it in its if not _COMMON.match(it[0]) and _keep_item(it)]
            # G-CSF 나.(예방)는 1)·2) 요법 목록마다 따로 (위험 > 20% / 10~20%)
            groups = [kept]
            if slug == "gcsf" and bundle and bundle[0].startswith("나."):
                firsts = [k for k, it in enumerate(kept) if re.match(r"^\d\)\s", it[0])]
                if firsts:
                    intro = kept[:firsts[0]]
                    groups = [intro + kept[a:b_] for a, b_ in zip(firsts, firsts[1:] + [len(kept)])]
            for g_no, group in enumerate(groups, 1):
                if bundle:
                    m = marker.match(bundle[0])
                    label = m.group(1) + (f"-{g_no}" if len(groups) > 1 else "")
                    lab_ascii = _SUB_ASCII.get(m.group(1), m.group(1)) + (str(g_no) if len(groups) > 1 else "")
                else:
                    label, lab_ascii = "", ""
                glines = [ln for it in group for ln in it]
                pre_cond = [ln for it in _items(pre) if not _COMMON.match(it[0]) for ln in it]
                text_lines = [f"[{l2_title}" + (f" > {label}" if label else "") + "]", *pre_cond, *glines]
                text = "\n".join(text_lines)
                cid = f"{l2_id}-{lab_ascii}" if lab_ascii else f"{l2_id}-1"
                no, d = _latest_tag("\n".join(pre + glines), b.doc_no, b.file_date)
                # 약제: G-CSF는 묶음 머리('가. filgrastim…, lenograstim…')의 제제, 나머지는 약제 제목
                drug_head = " ".join(its[0]).split("만 19세")[0] if slug == "gcsf" and its else heading
                drugs = scan_drugs(drug_head).drugs
                rlist = _regimen_list([ln for it in group if it[0].startswith("○") for ln in it])
                metastatic = bool(re.search(r"골전이|전이성\s*유방암", text))
                setting = ["metastatic"] if metastatic else \
                    (["early", "locally_advanced"] if rlist else ["early", "locally_advanced", "metastatic"])
                line = list(dict.fromkeys(x for r in rlist for x in r["setting"] if x != "any")) or ["any"]
                reimb = {"source_type": "baseline", "notice_no": f"제{no}호", "effective_from": d.isoformat(),
                         "regimen": [heading.split("(")[0].strip()], "stage": "supportive",
                         "her2_section": None, "line_rule": None,
                         "history": history_of("\n".join(pre + glines)),
                         "conditions": _line_rule("supportive", None), "text_normalized": _normalized(text)}
                if rlist:
                    reimb["regimen_list"] = rlist
                chunks.append(_base(cid, "HIRA-booklet", ver, l2_title + (f" > {label}" if label else ""), text,
                                    "reimbursement_condition", setting, ["any"], line, drugs, reimb,
                                    parent_id=l2_id, page_start=ps, page_end=pe))
                contexts[cid] = "\n".join([f"[{l2_title}]", *pre])
                items.append(_item(f"supp|{slug}|{lab_ascii or '1'}", seen, text, d, ps, cid))
                made.append(text)
        drug_common = list(dict.fromkeys(drug_common + ["\n".join(it) for it in _items(pre) if _COMMON.match(it[0])]))
        pre_body = [ln for it in _items(pre) if not _COMMON.match(it[0]) for ln in it]
        l2_text = "\n".join([f"[{l2_title}]", *head_list, *pre_body, *drug_common])
        common += drug_common
        chunks.append(_base(l2_id, "HIRA-booklet", ver, l2_title, l2_text, "section",
                            ["early", "locally_advanced", "metastatic"], ["any"], ["any"],
                            scan_drugs(heading).drugs,
                            {"source_type": "baseline", "notice_no": f"제{b.doc_no}호", "effective_from": ver,
                             "stage": "supportive", "her2_section": None, "line_rule": None},
                            parent_id=l1_id, page_start=ps, page_end=pe))
        sources[key] = "\n".join([l2_text, *made])
    if chunks:
        l1_text = "\n".join([f"[{SUPP_TITLE}]", *headings])
        # 목록 청크라 쪽이 따로 없다: 자식 청크의 첫 쪽~끝 쪽 (C의 지침 부모 청크와 같은 방식, 인용에 쪽이 빠지지 않게)
        pages = [c[k] for c in chunks for k in ("page_start", "page_end") if c.get(k) is not None]
        chunks.insert(0, _base(l1_id, "HIRA-booklet", ver, SUPP_TITLE, l1_text, "section",
                               ["early", "locally_advanced", "metastatic"], ["any"], ["any"], [],
                               {"source_type": "baseline", "notice_no": f"제{b.doc_no}호", "effective_from": ver,
                                "stage": "supportive", "her2_section": None, "line_rule": None},
                               page_start=min(pages) if pages else None, page_end=max(pages) if pages else None))
    return chunks, items, contexts, sources


# ---------- 책자 청크 (L1 원칙 / L2 단계·소단원 / L3 요법 행) ----------

def booklet_chunks(b: Booklet) -> BookletChunks:
    table = parse_breast_table(b)
    ver = b.file_date.isoformat()
    prefix = f"hira-booklet-{b.file_date:%Y%m%d}"
    notice_no = f"제{b.doc_no}호"
    chunks, items = general_chunks(b), []
    scans: dict[str, DrugScan] = {}
    contexts: dict[str, str] = {}

    if table.principles:
        text = "\n".join(table.principles)
        ps, pe = _pages(b, table.principles_pages)
        chunks.append(_base(f"{prefix}-bc-principle", "HIRA-booklet", ver,
                            f"{BREAST_TITLE} > 유방암 항암요법 투여 원칙", text, "section",
                            settings_for(None, text), ["any"], ["any"], [],
                            {"source_type": "baseline", "notice_no": notice_no, "effective_from": ver},
                            page_start=ps, page_end=pe))

    seen_keys: dict[str, int] = {}
    for sub in table.subsections:
        heading = f"{BREAST_TITLE} > {sub.path}"
        main_parent = next((x for x in table.subsections if x.main == sub.main and x.sub is None), None)
        sub_id = f"{prefix}-{sub.key}"
        hr_implied = sub.main == "3"
        line = lines_from(sub.title) or {"1": ["neoadjuvant"], "2": ["adjuvant"]}.get(sub.main, ["any"])
        notes = split_notes(sub.notes)
        main_notes = split_notes(main_parent.notes) if main_parent and main_parent is not sub else SubNotes([], {}, [])
        ctx = "\n".join([f"[{heading}]", *(main_notes.head if main_parent is not sub else []), *sub.notes])

        row_texts, prev_target, prev_no = [], "", None
        for r in sub.rows:
            regimen, target, tags = split_row(r.text)
            inherited = not target
            if inherited:
                target = prev_target
            else:
                prev_target, prev_no = target, r.no
            body = f"연번 {r.no}\n항암요법: {regimen}\n투여대상: " + \
                   ("(위 연번과 같음) " if inherited else "") + target
            row_texts.append(f"{body}\n{tags}".strip())
            # 이 행에만 붙는 주N 각주 (같은 소단원, 없으면 대단원의 주N), 연번 범위 규칙
            attached = []
            for n in footnote_marks(regimen, "" if inherited else target):
                attached += notes.footnotes.get(n) or main_notes.footnotes.get(n) or []
            for lo, hi, ln in notes.ranges + main_notes.ranges:
                if lo <= r.no <= hi:
                    attached += ln
            attached_text = "\n".join(attached)
            text = "\n".join(x for x in [f"[{heading}]", body, tags, attached_text] if x).strip()
            ps, pe = _pages(b, r.pages)
            no, d = _latest_tag(r.text, b.doc_no, b.file_date)
            filt = f"{sub.title}\n{target}"
            chunk_id = f"{sub_id}-r{r.no:02d}"
            scans[chunk_id] = scan = scan_drugs(regimen)
            parsed = parse_regimen(regimen, attached_text)
            reimb = {"source_type": "baseline", "notice_no": f"제{no}호", "effective_from": d.isoformat(),
                     "regimen": [clean_regimen(regimen)], "copay": copay_text(parsed, scan.drugs),
                     "stage": sub.stage, "her2_section": sub.her2_section, "line_rule": sub.line_rule,
                     "history": history_of(r.text), "regimen_parsed": parsed,
                     "conditions_inherited_from": f"r{prev_no:02d}" if inherited and prev_no else None,
                     "conditions": _line_rule(sub.stage, sub.line_rule), "text_normalized": _normalized(text)}
            drugs = scan.drugs
            # 각주가 정한 병용 약제 (설계 §1.5: 보조요법 주2 'abemaciclib과 병용 시 abemaciclib 100/100').
            # 40장 병용요법과 같은 뜻이라 combination 칸에 넣고, 약제로 행을 찾을 수 있게 drugs에도 더한다
            added = footnote_combination(attached_text)
            if added:
                reimb["combination"] = {**added, "base_regimen": [clean_regimen(regimen)]}
                drugs = list(dict.fromkeys(drugs + added["added_drug"]))
            chunks.append(_base(
                chunk_id, "HIRA-booklet", ver, f"{heading} > 연번 {r.no}", text, "reimbursement_condition",
                settings_for(sub.main, target), subtypes_from(filt, hr_implied), line, drugs, reimb,
                parent_id=sub_id, page_start=ps, page_end=pe))
            contexts[chunk_id] = ctx
            items.append(_item(f"breast|{sub.key}|{_norm_key(regimen)}", seen_keys,
                               f"{regimen}\n{target}\n{tags}", d if row_tags(r.text) else None,
                               ps, chunk_id))

        text = "\n".join([f"[{heading}]", *sub.notes, *row_texts]).strip()
        ps, pe = _pages(b, sub.pages)
        chunks.append(_base(
            sub_id, "HIRA-booklet", ver, heading, text, "section",
            settings_for(sub.main, text), subtypes_from(sub.title, hr_implied), line,
            list(dict.fromkeys(d for c in chunks if c["parent_id"] == sub_id for d in c["drugs"])),
            {"source_type": "baseline", "notice_no": notice_no, "effective_from": ver,
             "stage": sub.stage, "her2_section": sub.her2_section, "line_rule": sub.line_rule},
            parent_id=f"{prefix}-{main_parent.key}" if sub.sub and main_parent else f"{prefix}-bc-principle",
            page_start=ps, page_end=pe))

    # 병용요법 섹션이 없으면 validate_booklet이 오류로 잡는다 (REQUIRED_SECTIONS)
    combo = parse_combination(b) if "combination" in getattr(b, "sections", {}) else None
    if combo is not None and combo.breast:
        combo_id = f"{prefix}-combo"
        row_texts = []
        learned: set[str] = set()
        prev_stage = None
        for r in combo.breast:
            no, d = _latest_tag(r.text, b.doc_no, b.file_date)
            ps, pe = _pages(b, r.pages)
            heading = f"{COMBO_TITLE} > 유방암 > 연번 {r.no}"
            body = f"연번 {r.no}\n{r.text}"
            row_texts.append(body)
            setting, line = combo_filters(r.text)
            chunk_id = f"{combo_id}-r{r.no:02d}"
            cols = combo_columns(r, learned)
            learned |= set(cols["added_drug"])
            scans[chunk_id] = scan = scan_drugs(r.text)
            stage, line_rule = _combo_stage(cols["criteria"])
            if stage == "combination" and cols["merged"] and prev_stage:
                stage = prev_stage           # 허가사항 칸이 위 행과 병합된 행은 위 행과 같은 단계 (ribociclib 27~28)
            prev_stage = stage
            text = f"[{heading}]\n(열: 항암제 병용요법 / 허가사항 / 급여 요법 / 급여기준 / 비고)\n{body}"
            parsed = parse_regimen(cols["combined"])
            reimb = {"source_type": "baseline", "notice_no": f"제{no}호", "effective_from": d.isoformat(),
                     "regimen": [cols["combined"]], "copay": copay_text(parsed, scan_drugs(cols["combined"]).drugs),
                     "stage": "combination", "her2_section": None, "line_rule": line_rule,
                     "history": history_of(r.text), "regimen_parsed": parsed,
                     "combination": {k: cols[k] for k in ("added_drug", "added_drug_coverage", "base_regimen")},
                     "conditions": _line_rule(stage, line_rule), "text_normalized": _normalized(text)}
            chunks.append(_base(chunk_id, "HIRA-booklet", ver, heading, text, "reimbursement_condition",
                                setting, subtypes_from(r.text), line, scan.drugs, reimb,
                                parent_id=combo_id, page_start=ps, page_end=pe))
            ctx = [f"[{COMBO_TITLE} > 유방암]", *combo.intro]
            if cols["merged"] and "유방암" not in r.text and row_texts[:-1]:
                # 급여기준 칸까지 위 행과 병합된 행(ribociclib 28): 조건 근거가 위 행에만 있다
                ctx += ["(급여기준 칸이 위 행과 병합됨. 위 행:)", row_texts[-2]]
            contexts[chunk_id] = "\n".join(ctx)
            items.append(_item(f"breast|combo|{_norm_key(cols['combined'])}", seen_keys, r.text,
                               d if row_tags(r.text) else None, ps, chunk_id))
        pages = set().union(*(r.pages for r in combo.breast))
        ps, pe = _pages(b, pages)
        text = "\n".join([f"[{COMBO_TITLE} > 유방암]", *combo.intro, *row_texts])
        chunks.append(_base(
            combo_id, "HIRA-booklet", ver, f"{COMBO_TITLE} > 유방암", text, "section",
            ["early", "locally_advanced", "metastatic"], ["any"], ["any"],
            list(dict.fromkeys(x for c in chunks if c["parent_id"] == combo_id for x in c["drugs"])),
            {"source_type": "baseline", "notice_no": notice_no, "effective_from": ver,
             "stage": "combination", "her2_section": None, "line_rule": None},
            page_start=ps, page_end=pe))

    supp, supp_items, supp_ctx, supp_src = supportive_chunks(b, prefix, ver)
    chunks += supp
    items += supp_items
    contexts.update(supp_ctx)
    warnings = table.warnings + (combo.warnings if combo else [])
    return BookletChunks(chunks, items, warnings, table, combo, scans, contexts, supp_src)


_OL_SETTING = [(re.compile(r"선행|neoadjuvant", re.I), "neoadjuvant"),
               (re.compile(r"수술\s*후\s*보조|(?<!neo)adjuvant", re.I), "adjuvant")]


def _offlabel_filters(setting_text: str, target: str, line_text: str) -> tuple[list, list]:
    """(setting, line). 선행·수술후보조면 조기·국소진행, 아니면 고식적으로 본다."""
    lines = [v for rx, v in _OL_SETTING if rx.search(setting_text)]
    if lines:
        return ["early", "locally_advanced"], lines
    return settings_for("4", target), lines_from(line_text) or ["any"]


def _copay(s: str) -> str | None:
    m = re.search(r"(\d+)\s*/\s*100", s)
    return f"{m.group(1)}/100" if m else None


def offlabel_chunks(o: OffLabel) -> list[dict]:
    """허가초과 항암요법 목록 (설계 문서는 이번 범위에서 제외. 파이프라인 --with-offlabel일 때만 쓴다)."""
    ver = o.file_date.isoformat()
    label = f"허가초과 항암요법 {o.path.stem.rsplit('_', 1)[-1]}"   # notice_no 자리. 공고번호가 없는 목록이다
    prefix = f"hira-offlabel-{o.file_date:%Y%m%d}"
    out = []
    for r in o.approved:
        setting, line = _offlabel_filters(r.setting, r.target, r.line)
        text = (f"[허가초과 인정 요법 > 유방암 > 요법코드 {r.code}]\n항암요법: {r.regimen}\n"
                f"투여대상: {r.target}\n투여단계: {r.line}\n투여요법: {r.setting}\n급여: {r.copay}")
        reimb = {"source_type": "baseline", "notice_no": label, "effective_from": ver,
                 "regimen": [clean_regimen(r.regimen)], "copay": _copay(r.copay),
                 "text_normalized": _normalized(text)}
        if r.male_only:
            # patient_state.patient.gender 값. 근거 구절은 투여대상 원문 그대로
            reimb["conditions"] = {"all_of": [{"id": "m1", "field": "sex", "op": "eq", "value": "MALE",
                                               "text": r.target}]}
        out.append(_base(f"{prefix}-{r.code}", "HIRA-offlabel", ver,
                         f"허가초과 항암요법 > 유방암 > 요법코드 {r.code}", text, "offlabel_regimen",
                         setting, subtypes_from(r.target), line, extract_drugs(r.regimen), reimb))
    for v in o.reviewing:
        setting, line = _offlabel_filters(v.text, v.text, v.text)
        text = f"[검토중인 허가초과 항암요법 (판정에 쓰지 않음)]\n연번 {v.no}\n{v.text}"
        out.append(_base(f"{prefix}-review-{v.no}", "HIRA-offlabel", ver,
                         f"검토중인 허가초과 항암요법 > 유방암 > 연번 {v.no}", text, "offlabel_regimen",
                         setting, subtypes_from(v.text), line, extract_drugs(v.text),
                         {"source_type": "preview", "notice_no": label, "effective_from": ver,
                          "text_normalized": _normalized(text)}))
    return out


# ---------- 스키마 검사와 저장 ----------

# 설계 문서(reimbursement_chunking_design.md, 2026-10-16)가 제안한 reimbursement 칸. 공용 스키마(schemas/chunk.json)에는
# 아직 없다 (4명 검토 대상, 개정안: src/reimbursement/schema_proposal.md). 반영 전까지 D는 공용 스키마 + 이 칸으로 검사한다.
REIMBURSEMENT_EXTENSION = {
    "stage": {"enum": list(STAGE_OF_MAIN.values()) + ["combination", "supportive"]},
    "her2_section": {"enum": ["positive", "negative", None]},
    "line_rule": {"enum": [r for _, _, r in _LINE_RULES] + [None]},
    "history": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["notice_no", "effective_from"],
        "properties": {"notice_no": {"type": "string"}, "effective_from": {"type": "string", "format": "date"}}}},
    "regimen_parsed": {"type": "object", "additionalProperties": False,
                       "properties": {"sequence": {"type": "array"}, "optional_drugs": {"type": "array"},
                                      "routes": {"type": "object"}, "copay_by_drug": {"type": "object"},
                                      "fixed_dose_combination": {"type": "array"}}},
    "regimen_list": {"type": "array", "items": {"type": "object"}},
    "combination": {"type": "object", "additionalProperties": False,
                    "required": ["added_drug", "added_drug_coverage", "base_regimen"],
                    "properties": {"added_drug": {"type": "array", "items": {"type": "string"}},
                                   "added_drug_coverage": {"enum": ["비급여", "100/100", None]},
                                   "base_regimen": {"type": "array", "items": {"type": "string"}}}},
    "conditions_inherited_from": {"type": ["string", "null"]},
}
# 청크 최상위에 더하는 칸 (지침 청크와 같이 쓰는 판정용 정규화 본문, 2026-10-20 결정)
TOP_LEVEL_EXTENSION = {"text_normalized": {"type": "string"}}


def load_schema(schema_path: Path = SCHEMA_PATH, extended: bool = True) -> dict:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if extended:
        props = schema["properties"]["reimbursement"]["properties"]
        props.update({k: v for k, v in REIMBURSEMENT_EXTENSION.items() if k not in props})
        top = schema["properties"]
        top.update({k: v for k, v in TOP_LEVEL_EXTENSION.items() if k not in top})
    return schema


def check_chunks(chunks: list[dict], schema_path: Path = SCHEMA_PATH, extended: bool = True) -> list[str]:
    """schemas/chunk.json(+ 설계 제안 칸) 위반 목록. jsonschema가 있으면 그것으로, 없으면 필수·허용값·추가 필드만 본다."""
    schema = load_schema(schema_path, extended)
    errors = []
    ids = [c["chunk_id"] for c in chunks]
    for dup in sorted({x for x in ids if ids.count(x) > 1}):
        errors.append(f"chunk_id 중복: {dup}")
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    except ImportError:
        validator = None
    for c in chunks:
        if validator is not None:
            errors += [f"{c['chunk_id']}: {e.message}" for e in validator.iter_errors(c)]
        else:
            errors += [f"{c['chunk_id']}: {m}" for m in _light_check(c, schema)]
    return errors


def _light_check(obj: dict, schema: dict) -> list[str]:
    errs = [f"필수 필드 없음: {k}" for k in schema.get("required", []) if k not in obj]
    props = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        errs += [f"정의되지 않은 필드: {k}" for k in obj if k not in props]
    for k, v in obj.items():
        p = props.get(k, {})
        if "const" in p and v != p["const"]:
            errs.append(f"{k} = {v!r} (기대 {p['const']!r})")
        if "enum" in p and v not in p["enum"]:
            errs.append(f"{k} = {v!r} 허용값 아님")
        if p.get("type") == "array" and isinstance(v, list):
            if len(v) < p.get("minItems", 0):
                errs.append(f"{k}: 비어 있음")
            enum = p.get("items", {}).get("enum")
            errs += [f"{k}: {x!r} 허용값 아님" for x in v if enum and x not in enum]
        if p.get("type") == "object" and isinstance(v, dict):
            errs += [f"{k}.{m}" for m in _light_check(v, p)]
    return errs


def write_jsonl(chunks: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with open(tmp, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--booklet", type=Path, required=True)
    ap.add_argument("--offlabel", type=Path)
    ap.add_argument("--out", type=Path, help="기본: data/reimbursement/chunks/reimbursement_chunks_<책자날짜>.jsonl")
    args = ap.parse_args(argv)

    b = load_booklet(args.booklet, DATA / "cache")
    bc = booklet_chunks(b)
    chunks = list(bc.chunks)
    if args.offlabel:
        chunks += offlabel_chunks(load_offlabel(args.offlabel))
    errors = check_chunks(chunks)

    kinds = {}
    for c in chunks:
        kinds[(c["source"], c["chunk_kind"])] = kinds.get((c["source"], c["chunk_kind"]), 0) + 1
    for (src, kind), n in sorted(kinds.items()):
        print(f"{src:<14} {kind:<24} {n}")
    for w in bc.warnings:
        print(f"[경고] {w}")
    no_drug = [c["chunk_id"] for c in chunks
               if c["chunk_kind"] != "section" and not c["drugs"]]
    if no_drug:
        print(f"[경고] 약제명을 못 뽑은 청크 {len(no_drug)}개: {', '.join(no_drug[:10])}")
    if errors:
        print(f"[오류] 스키마 위반 {len(errors)}건")
        for e in errors[:20]:
            print("  " + e)
        return 1
    out = args.out or DATA / "chunks" / f"reimbursement_chunks_{b.file_date:%Y%m%d}.jsonl"
    print(f"저장: {write_jsonl(chunks, out)} ({len(chunks)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
