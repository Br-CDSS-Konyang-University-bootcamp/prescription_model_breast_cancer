"""차트 원문 → patient_state 처리 단계 (IN-0 ~ IN-7). 진입점은 run().

실행: python -m src.input.script.pipeline (LLM 추출 시험, 아래 extract 절의 usage)

이 파일은 아래 순서의 절로 되어 있다 (2026-10-26, 옛 script/pipeline/ 폴더의 파일을 합침).
절마다 맨 위 주석이 옛 파일의 설명이다.
- classify
- deid
- quote
- normalize
- assemble
- pipeline
- extract
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import requests
from jsonschema import Draft202012Validator

from llm import LLMConfig, LLMOutputError, complete_json, load_config
from src.input.script.rules import Vocab, annotate, load_drug_table


# ====================================================================================================
# classify (옛 src/input/script/pipeline/classify.py)
# ====================================================================================================
# IN-1 문서 나누기·분류 [규칙] (notes/input_module_design.md §2 IN-1).
#
# 차트 원문(비식별화 전)을 문서로 나누고 doc_type, doc_date를 붙인다. 위치는 원문 기준이라 인용 위치가 그대로 맞는다.
#
# - 문서 시작: 머리글 줄(`[...]`, `<...>`, `■ ...`) 또는 빈 줄 2개 이상 뒤의 첫 줄 (`BONE SCAN REPORT` 같은 머리글)
# - 종류: 머리글 단어 사전. 사전에 없으면 progress_note
# - 날짜: medication은 null. 그 밖에는 머리글 줄의 날짜, 없으면 보고일·검사일·작성일 같은 이름 붙은 날짜, 없으면 본문 첫 날짜

HEADER = re.compile(r"^(\[[^\]]+\]|<[^>]+>|■)")
# 날짜 표기 (2026-10-28 표현 변형): 2021.3.5 / 2021-03-05 / 2021/03/05 / 2021년 3월 5일 / 21/03/05 (두 자리 연도는 2000년대).
# 연·월·일 세 숫자는 _ymd로 꺼낸다. 일이 없는 날짜(2021년 3월)와 상대 날짜(3년 전)는 받지 않는다 (일수 계산이 필요한 칸이 많다)
DATE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})(?!\d)"
                  r"|(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"
                  r"|(?<![\d./])(\d{2})/(\d{1,2})/(\d{1,2})(?![\d/])")


def _ymd(m: re.Match) -> tuple[int, int, int]:
    y, mo, d = (int(g) for g in [g for g in m.groups() if g is not None][-3:])
    return (2000 + y if y < 100 else y), mo, d
NAMED_DATE = re.compile(r"(보고일|Reported|검사일|수술일|작성일)\s*:\s*" + DATE.pattern)
# 앞에서부터 처음 맞는 종류 (분자병리를 병리보다 먼저 본다)
TYPE_WORDS = [
    ("molecular", ("분자병리", "NGS", "유전자")),
    ("pathology", ("병리", "PATHOLOGY")),
    ("medication", ("투약", "처방")),
    ("radiology", ("영상", "판독", "CT", "MRI", "PET", "BONE SCAN", "초음파")),
]


@dataclass
class Document:
    doc_id: str
    doc_type: str
    doc_date: str | None
    start: int          # 차트 원문에서 문서가 시작하는 위치
    text: str           # 문서 원문 (끝 빈 줄 제외)

    @property
    def end(self) -> int:
        return self.start + len(self.text)

    def entry(self) -> dict:
        """patient_state documents[] 항목."""
        return {"doc_id": self.doc_id, "doc_type": self.doc_type, "doc_date": self.doc_date}


def split(chart: str) -> list[Document]:
    starts, pos, blanks = [], 0, 2
    for line in chart.splitlines(keepends=True):
        s = line.strip()
        if s and (blanks >= 2 or HEADER.match(s)):
            starts.append(pos)
        blanks = 0 if s else blanks + 1
        pos += len(line)
    docs = []
    for i, start in enumerate(starts):
        text = chart[start:starts[i + 1] if i + 1 < len(starts) else len(chart)].rstrip()
        header = text.split("\n", 1)[0]
        doc_type = classify(header)
        docs.append(Document(f"D{i + 1}", doc_type, None if doc_type == "medication" else _date(header, text),
                             start, text))
    return docs


def classify(header: str) -> str:
    h = header.upper()
    for doc_type, words in TYPE_WORDS:
        if any(w.upper() in h for w in words):
            return doc_type
    return "progress_note"


def _date(header: str, text: str) -> str | None:
    m = DATE.search(header) or NAMED_DATE.search(text) or DATE.search(text)
    if not m:
        return None
    y, mo, d = _ymd(m)
    return f"{y:04d}-{mo:02d}-{d:02d}"


# ====================================================================================================
# deid (옛 src/input/script/pipeline/deid.py)
# ====================================================================================================
# IN-0 비식별화 [규칙] (notes/input_module_design.md §2 IN-0, §7 결정 5·6).
#
# 정규식으로 차트 전체에서 식별정보를 찾아 대응표를 만들고, LLM에 보낼 문서마다 같은 대응표로 가린다.
# 대응표는 메모리에만 두고 파일로 저장하지 않으며 LLM에 넘기지 않는다. 인용 확인(quote.locate)이 이 표로 구절을 되돌린다.
#
# - 이름: '환자명·성명·이름' 또는 '담당의·판독의·집도의·Pathologist' 같은 이름표 뒤 한글 2~4자. 찾은 이름은 문서 어디서든 가린다
# - 등록번호: '등록번호·병록번호·MRN' 뒤 숫자
# - 주민번호: 앞 6자리-뒷자리 (뒤를 *로 가린 표기 포함)
# - 연락처: 0으로 시작하는 전화번호
# - 주소: '주소:' 뒤, 또는 시·도 이름으로 시작해 시·군·구가 이어지는 줄
#
# 남기는 것: 날짜, 나이·성별(F/54), 병원·검사기관 이름 (판정과 근거 확인에 필요).

PROVINCES = "서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주"
PATTERNS = [  # (종류, 정규식). 값은 첫 번째 묶음 (없으면 전체)
    ("이름", re.compile(r"(?:환자명|성명|이름|담당의|주치의|판독의|집도의|의뢰의|Name|Pathologist|Radiologist|Physician)"
                       r"\s*[:：]\s*([가-힣]{2,4})(?![가-힣])", re.I)),
    ("등록번호", re.compile(r"(?:등록번호|병록번호|MRN|Patient ID)\s*[:：]?\s*(\d{5,})", re.I)),
    ("주민번호", re.compile(r"(?<!\d)(\d{6}-[1-4][\d*]{6})(?![\d*])")),
    ("연락처", re.compile(r"(?<!\d)(0\d{1,2}-\d{3,4}-\d{4})(?!\d)")),
    ("주소", re.compile(rf"(?:주소\s*[:：]\s*(.+)$|^\s*((?:{PROVINCES})\S*\s+\S+(?:시|군|구)\s.*)$)", re.M)),
]


def identifiers(chart: str) -> dict[str, str]:
    """{가림 표시: 원래 값}. 같은 값은 같은 표시 ([이름1]이 문서마다 같은 사람)."""
    found: dict[str, str] = {}
    counts: dict[str, int] = {}
    for kind, pat in PATTERNS:
        for m in pat.finditer(chart):
            value = next((g for g in m.groups() if g), m.group(0)).strip()
            if value in found:
                continue
            counts[kind] = counts.get(kind, 0) + 1
            found[value] = f"[{kind}{counts[kind]}]"
    return {tag: value for value, tag in found.items()}


def mask(text: str, mapping: dict[str, str]) -> str:
    """대응표의 원래 값을 모두 가림 표시로 바꾼다. 긴 값부터 (주소 안의 이름 등)."""
    for tag, value in sorted(mapping.items(), key=lambda kv: -len(kv[1])):
        text = text.replace(value, tag)
    return text


# ====================================================================================================
# quote (옛 src/input/script/pipeline/quote.py)
# ====================================================================================================
# 인용 확인 [규칙] (notes/input_module_design.md §2 인용 확인, §7 결정 5).
#
# LLM은 가린 문서를 보고 구절을 낸다. 구절의 가림 표시([이름1] 등)를 대응표로 되돌린 뒤 원문 문서에서 찾고,
# 위치는 차트 원문 기준으로 계산한다. 같은 구절이 여러 번 있으면 처음 나오는 곳.
# 그대로 없으면 공백·줄바꿈 차이만 허용해 다시 찾는다. 그래도 없으면 None (후보를 버리고 인용 준수율에 센다).

def locate(quote: str, doc: Document, mapping: dict[str, str] | None = None) -> dict | None:
    """원문 기준 source {doc_id, quote, char_start, char_end}. quote는 원문에서 잘라 온 글자."""
    for masked, original in (mapping or {}).items():
        quote = quote.replace(masked, original)
    i = doc.text.find(quote)
    if i >= 0:
        span = (i, i + len(quote))
    else:
        chars = [re.escape(ch) for ch in quote if not ch.isspace()]
        m = re.search(r"\s*".join(chars), doc.text) if chars else None
        if not m:
            # 원문 'BRCA1/2'를 칸에 맞춰 'BRCA1'·'BRCA2'로 나눠 옮긴 구절은 원문 표기로 되돌려 찾는다 (2026-10-28).
            # 유전자 이름만 바꾼 경우만 받는다. 단어를 빼거나 바꾼 구절은 지어낸 구절과 구별할 수 없어 버린다
            wide = re.sub(r"BRCA[12](?![/\d])", "BRCA1/2", quote)
            return locate(wide, doc) if wide != quote else None
        span = m.span()
    return {"doc_id": doc.doc_id, "quote": doc.text[span[0]:span[1]],
            "char_start": doc.start + span[0], "char_end": doc.start + span[1]}


# ====================================================================================================
# normalize (옛 src/input/script/pipeline/normalize.py)
# ====================================================================================================
# IN-3 정규화 [규칙] (notes/input_module_design.md §2 IN-3).
#
# 후보 하나(칸 + 원문 구절)를 표준값으로 바꾼다. LLM은 값을 계산하지 않으므로 여기가 값을 만드는 유일한 곳이다.
# 표현 사전은 data/dictionaries/field_vocab.csv(결과 단어·조직형·폐경)와 drug_names.csv(약 이름).
#
#     normalize("receptors.er_percent", "ER positive (Allred 8, 5+3)", ctx)
#     -> {"status": "present", "value": {"allred": {"total": 8, "ps": 5, "is": 3}, "result": "positive"}}
#
# 대부분 구절만 본다. 예외 (Context):
# - treatment_history의 setting: 구절이 든 줄의 "보조·선행·고식" (투약 표의 첫 칸). 없으면 None → 4단계가 전이일과 비교해 정한다
# - imaging_findings의 modality·date: 문서 머리글·문서 날짜
# - stage.yptnm의 잔존 크기·림프절 수: 같은 문서의 "잔존 종양 크기", "림프절" 줄
# - *_day: 진단일 기준 일수라 진단일(dx_date)이 있어야 한다
#
# 다른 후보와 맞춰 봐야 하는 값(progression_day, 차수, 간주 규칙)은 4단계(assemble)가 채운다.
# 정규화하지 못하면 None을 돌려준다 (확인 요청 목록으로 보낼 후보).

DRUG_NAMES_CSV = Path(__file__).resolve().parents[3] / "data" / "dictionaries" / "drug_names.csv"
VOCAB = Vocab()

NOT_DONE = re.compile(r"미시행|시행하지 않|검사하지 않|not done", re.I)
PENDING = re.compile(r"결과 대기|pending|검사 중|의뢰함", re.I)
PLANNED = re.compile(r"시행 예정|예정|예약")
TEST_FIELDS = ("receptors.", "proliferation.")     # 미시행·결과 대기·예정을 읽는 검사 칸
NEGATION = re.compile(r"없음|아님|no evidence|negative for", re.I)
SITES = [  # field_vocab.csv metastatic_sites 표준값 순서
    ("bone", r"뼈|(?<!쇄)골|척추|bone|osseous"),     # 쇄골상 림프절은 뼈가 아니다
    ("liver", r"(?<![가-힣])간(?![가-힣])|liver|hepatic"),
    ("lung", r"(?<![가-힣])폐(?!경)|lung|pulmonary"),
    ("brain", r"뇌|brain"),
    ("skin", r"피부|skin"),
    # 원격 림프절만. 같은 쪽 쇄골상·내유 림프절은 국소(N3)라 넣지 않는다. '비대 없음'은 전이가 아니다 (8단계, 2026-10-27)
    ("distant_ln", r"(?:종격동|기관\s*옆|대동맥\s*(?:주위|옆)|후복막|복강\s*내|경부|반대\s*[측편]\s*(?:액와|쇄골\S*)|원격)\s*"
                   r"림프절(?!\s*(?:비대\s*)?없음)|(?:mediastinal|para-?aortic|retroperitoneal|cervical|"
                   r"contralateral\s+(?:axillary|supraclavicular)|distant)\s+(?:lymph\s+nodes?|LNs?)\b"),
]
ROMAN = {"0": "0", "1": "I", "2": "II", "3": "III", "I": "I", "II": "II", "III": "III"}


@dataclass
class Context:
    doc: Document
    line: str = ""                  # 구절이 든 줄 전체
    dx_date: str | None = None      # 진단일 (YYYY-MM-DD)

    @classmethod
    def of(cls, doc: Document, char_start: int, dx_date: str | None = None) -> "Context":
        """char_start는 차트 원문 기준 위치 (quote.locate의 결과)."""
        i = char_start - doc.start
        s = doc.text.rfind("\n", 0, i) + 1
        e = doc.text.find("\n", i)
        return cls(doc, doc.text[s:e if e >= 0 else len(doc.text)], dx_date)


def normalize(field: str, quote: str, ctx: Context) -> dict | None:
    """칸 하나의 값. 목록 칸(treatment_history 등)은 항목 dict, 그 밖에는 {status, value}. 실패하면 None."""
    if field.startswith("molecular."):
        return _gene(field.rsplit(".", 1)[1], quote, ctx)
    if field in ITEMS:
        return ITEMS[field](quote, ctx)
    # 미시행·결과 대기·예정은 검사 칸에만 (유전자 칸은 _gene). '보조 내분비요법 상의 예정' 같은 치료 계획은 검사 상태가 아니다
    if field.startswith(TEST_FIELDS):
        if NOT_DONE.search(quote):
            return {"status": "not_done"}
        if PENDING.search(quote):
            return {"status": "not_done", "raw": "결과 대기"}
        if PLANNED.search(quote):
            return {"status": "not_done", "raw": "예정"}
    parse = PARSERS.get(field)
    value = parse(quote, ctx) if parse else None
    return None if value is None else {"status": "present", "value": value}


# ---------- 공통 ----------
def _num(s: str):
    x = float(s)
    return int(x) if x.is_integer() else x


def parse_date(text: str) -> str | None:
    m = DATE.search(text)
    try:
        return None if not m else dt.date(*_ymd(m)).isoformat()
    except ValueError:            # 13월·32일처럼 날짜가 아닌 숫자
        return None


def _day(date: str | None, dx_date: str | None) -> int | None:
    if date is None or dx_date is None:
        return None
    return (dt.date.fromisoformat(date) - dt.date.fromisoformat(dx_date)).days


def _expr_pattern(expr: str) -> str:
    """사전 표현(소문자) 하나의 정규식. 공백은 여러 칸도 맞고, 영문 끝은 단어 경계를 본다."""
    pat = r"\s+".join(re.escape(w) for w in expr.split(" "))
    if expr[0].isascii() and expr[0].isalnum():
        pat = r"(?<![a-z0-9])" + pat
    if expr[-1].isascii() and expr[-1].isalnum():
        pat += r"(?![a-z0-9])"
    return pat


def _vocab(field: str, text: str) -> str | None:
    """사전 표현 중 text에 들어 있는 가장 긴 것의 표준값. 영문 표현은 단어 경계를 본다."""
    best, low = None, text.casefold()
    for expr, canonical in VOCAB.mapping(field).items():
        if re.search(_expr_pattern(expr), low) and (best is None or len(expr) > best[0]):
            best = (len(expr), canonical)
    return best and best[1]


def _sites(text: str) -> list[str]:
    return [site for site, pat in SITES if re.search(pat, text, re.I)]


def _size_mm(text: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|mm)", text)
    return None if not m else _num(str(round(float(m.group(1)) * (10 if m.group(2) == "cm" else 1), 1)))


def _yes_no(text: str) -> str:
    return "no" if re.search(r"없음|아님|불가|inoperable|\bno\b", text, re.I) else "yes"


# ---------- 칸별 ----------
def _grade(q, ctx):
    m = re.search(r"(?:grade|NG|G)\s*([1-3])", q, re.I) or re.search(r"(?<![A-Za-z])(III|II|I)(?![A-Za-z])", q)
    return None if not m else {"I": 1, "II": 2, "III": 3}.get(m.group(1)) or int(m.group(1))


def _tnm(q, ctx, *, prefix):
    # 'T2, N1(2/14), M0'처럼 쉼표·괄호(림프절 수)가 끼어도 읽는다 (2026-10-28 표현 변형)
    m = re.search(r"(yp|p|c)?T(is|[0-4][a-d]?|X)\s*(?:\([^)]*\))?[\s,]*(?:y?p|c)?N([0-3][a-c]?(?:mi)?|X)\s*(?:\([^)]*\))?"
                  r"[\s,]*(?:[cp]?M([01X]))?", q)
    # 접두어가 칸과 다르면 받지 않는다 (경과기록의 pT2N0M0를 ctnm 칸에 넣은 경우 등). 접두어가 없으면 받는다
    if not m or m.group(1) not in (None, prefix):
        return None
    ed = re.search(r"AJCC\s*(\d+(?:st|nd|rd|th))", q)
    v = {"t": f"T{m.group(2)}", "n": f"N{m.group(3)}", "m": m.group(4) and f"M{m.group(4)}",
         "edition": ed and ed.group(1)}
    if prefix == "yp":
        # ypTNM에 M이 없으면 M0 (수술 병기). 잔존 크기·림프절 수는 같은 문서의 다른 줄에서 읽는다
        v["m"] = v["m"] or "M0"
        size = re.search(r"(?:잔존 (?:종양 )?크기|residual (?:tumor )?size)\s*:\s*(.+)", ctx.doc.text, re.I)
        ln = re.search(r"(?:림프절|lymph node)\s*:\s*(\d+)\s*/\s*(\d+)", ctx.doc.text, re.I)
        # 크기 줄이 없어도 ypT0이면 잔존 침윤암이 없으므로 0 (9단계, 2026-10-27)
        residual = size and _size_mm(size.group(1))
        v.update({"residual_size_mm": 0 if residual is None and v["t"] == "T0" else residual,
                  "positive_ln": ln and int(ln.group(1)), "examined_ln": ln and int(ln.group(2))})
    return v


def _group(q, ctx):
    m = re.search(r"stage\s*(IV|III[A-C]?|II[AB]?|I[AB]?|0)(?![A-Za-z])", q, re.I) \
        or re.search(r"(IV|III[A-C]?|II[AB]?|I[AB]?)\s*기", q) \
        or re.fullmatch(r"\s*(IV|III[A-C]?|II[AB]?|I[AB]?)\s*", q)    # LLM이 'IIIA'만 옮긴 경우 (2026-10-28)
    return m and m.group(1).upper()


def _extent(q, ctx):
    g = _group(q, ctx)
    if g is None:
        return None
    return "metastatic" if g.startswith("IV") else "locally_advanced" if g.startswith("III") else "early"


def _metastatic_sites(q, ctx):
    if re.search(r"M0(?![0-9])", q) or NEGATION.search(q):
        return "[Not Applicable]"
    return _sites(q) or None


def _ln_count(q, ctx):
    m = re.search(r"(\d+)\s*/\s*(\d+)", q) or re.search(r"전이\s*(\d+)\s*개\s*/\s*검사\s*(\d+)\s*개", q)
    return m and {"positive": int(m.group(1)), "examined": int(m.group(2))}


def _receptor(field):
    def parse(q, ctx):
        v = {}
        m = re.search(r"Allred(?:\s*score)?\s*(\d)(?:\s*[,(]?\s*(?:PS\s*)?(\d)\s*\+\s*(?:IS\s*)?(\d))?", q, re.I)
        if m:
            total = int(m.group(1))
            ps, is_ = (int(m.group(2)), int(m.group(3))) if m.group(2) else (0, 0) if total == 0 else (None, None)
            v["allred"] = {"total": total, **({"ps": ps, "is": is_} if ps is not None else {})}
        v.update(_pct_or_range(q))
        result = _vocab(f"receptors.{field}.result", q)
        if result:
            v["result"] = result
        return v or None
    return parse


def _her2_ihc(q, ctx):
    # HER-2/neu, c-erbB2, ERBB2도 HER2 (2026-10-28 표현 변형)
    m = re.search(r"(?:HER-?2(?:/neu)?|c-?erbB-?2|ERBB2)\s*(?:\([^)]*\))?\s*(?:IHC)?\s*:?\s*([0-3])(\+?)", q, re.I)
    if not m:
        return None
    v = {"score": m.group(1) + m.group(2)}
    if v["score"] == "0":
        if re.search(r"희미|faint|ultralow", q, re.I):
            v["faint"] = True
        elif re.search(r"no staining|염색 없음|무염색", q, re.I):
            v["faint"] = False
    return v


def _her2_ish(q, ctx):
    result = _vocab("receptors.her2_ish.result", q)
    method = re.search(r"\b(FISH|SISH|DISH)\b", q)
    return result and {"result": result, "method": method.group(1) if method else "unknown"}


def _pdl1(q, ctx):
    assay = re.search(r"22C3|SP142|SP263", q)
    score = re.search(r"\b(CPS|IC|TPS)\b\s*:?\s*(?:≥|>=)?\s*(\d+(?:\.\d+)?)", q)      # 'CPS ≥10'은 10
    return score and {"assay": assay.group(0) if assay else "unknown", "score_type": score.group(1),
                      "score": _num(score.group(2))}


def _pct_or_range(q: str) -> dict:
    """비율 하나는 percent, 구간은 range (2026-10-28 표현 변형). '<1%'는 [0, 0] (스키마 range 설명), '<10%'는 [0, 9],
    '15~20%'·'15-20%'는 [15, 20]. 구간을 한 숫자로 줄이면 경계(Ki-67 20%, ER 1·10%) 판정이 바뀐다."""
    m = re.search(r"<\s*(\d+(?:\.\d+)?)\s*%", q)
    if m:
        hi = _num(m.group(1))
        return {"range": [0, 0 if hi <= 1 else _num(str(hi - 1))]}
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?\s*[~\-–]\s*(\d+(?:\.\d+)?)\s*%", q)
    if m:
        return {"range": [_num(m.group(1)), _num(m.group(2))]}
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
    return {"percent": _num(m.group(1))} if m else {}


def _percent(q, ctx):
    return _pct_or_range(q) or None


def _age(q, ctx):
    m = re.search(r"(\d+)\s*세", q) or re.search(r"\b[FM]\s*/\s*(\d+)", q)
    return m and int(m.group(1))


def _gender(q, ctx):
    if re.search(r"\bF\s*/|여성|여자|female", q, re.I):
        return "FEMALE"
    if re.search(r"\bM\s*/|남성|남자|\bmale", q, re.I):
        return "MALE"
    return None


def _menopausal_basis(q, ctx):
    """근거 단어가 없으면 None ('폐경 후'만 적힌 구절은 상태이지 근거가 아니다)."""
    for basis, pat in [("fsh", r"FSH"), ("oophorectomy", r"난소\s*절제|oophorectomy|ovariectomy"),
                       ("ovarian_radiation", r"난소\s*방사선"), ("hysterectomy", r"자궁\s*(?:적출|절제)|hysterectomy"),
                       # "58세 폐경 후 여성"의 58세는 나이라 근거가 아니다 (폐경 바로 뒤에 후·전이 붙으면 뺀다)
                       ("age_amenorrhea", r"LMP|\d+\s*세\s*폐경(?!\s*[후전])|폐경\s*\d+\s*세|월경|생리|menses|amenorrhea")]:
        if re.search(pat, q, re.I):
            # LLM이 '58세 폐경'까지만 잘라 옮겨도 원문에서 바로 뒤가 후·전이면 나이다
            if basis == "age_amenorrhea" and re.search(re.escape(q) + r"\s*[후전]", ctx.line):
                return None
            return basis
    return None


def _number(pattern):
    def parse(q, ctx):
        m = re.search(pattern, q, re.I)
        return m and _num(m.group(1))
    return parse


def _day_field(q, ctx):
    """재발·전이 날짜. 재발·전이를 말하지 않는 날짜만의 구절(재발 병소 수술일 등)은 받지 않는다."""
    if not re.search(r"전이|재발|metasta|recur|de novo", q, re.I):
        return None
    date = parse_date(q)
    if date is None:
        return 0 if re.search(r"de novo", q, re.I) else None
    return _day(date, ctx.dx_date)


def _metastasis_day(q, ctx):
    """국소 재발 구절은 원격 전이일이 아니다."""
    if re.search(r"국소|locoregional|local", q, re.I) and not re.search(r"전이|metasta", q, re.I):
        return None
    return _day_field(q, ctx)


SURGERY = re.compile(r"수술|절제|surgery|resection|excision|mastectomy", re.I)


def _need(pattern: str, parse):
    """구절에 그 칸의 단어가 있을 때만 정규화한다. LLM이 '재발·전이 소견 없음' 같은 구절을 여러 칸에 넣는 것을 막는다."""
    def wrapped(q, ctx):
        return parse(q, ctx) if re.search(pattern, q, re.I) else None
    return wrapped


def _need_vocab(field: str):
    """_need와 같고 칸의 단어는 field_vocab.csv에서 (표준값 yes). 값은 구절의 없음·아님으로 가린다 (10단계, 2026-10-27)."""
    return lambda q, ctx: _yes_no(q) if _vocab(field, q) else None


END_WORD = re.compile(r"종료|중단|완료|끝|stop|discontinu|complet", re.I)


def _endocrine_end(q, ctx):
    """보조 내분비요법 종료일. 종료 단어는 구절이나 그 줄에 있으면 된다 (정답 구절은 날짜만, 5단계 2026-10-27).
    줄에 약 이름이 있으면 내분비약이 하나는 있어야 하고 (허셉틴 '18회 완료' 등은 받지 않음),
    날짜만 옮긴 구절은 그 줄의 마지막 날짜여야 한다 (투약 표의 시작일·전이일을 받지 않음)."""
    line = ctx.line or q
    if not (END_WORD.search(q) or END_WORD.search(line)):
        return None
    drugs = [g for g, _ in _drugs(line)]
    if drugs and not any(DRUG_TABLE.get(g, ("",))[0] == "Hormone Therapy" for g in drugs):
        return None
    date = parse_date(q)
    if date and not END_WORD.search(q) and DATE.findall(line)[-1:] != DATE.findall(q)[:1]:
        return None
    return date


def _recurrence_status(q, ctx):
    if NEGATION.search(q):
        return "none"
    if re.search(r"국소|locoregional|local", q, re.I):
        return "locoregional"
    return "distant" if re.search(r"전이|metasta", q, re.I) else None


def _pcr(q, ctx):
    if re.search(r"없음|no residual|\bpCR\b|ypT0", q, re.I):
        return "yes"
    return "no" if re.search(r"있음|residual", q, re.I) else None


def _rcb(q, ctx):
    m = re.search(r"RCB[\s-]*(?:class\s*)?(III|II|I|[0-3])", q, re.I)
    return m and f"RCB-{ROMAN[m.group(1)]}"


def _intent(q, ctx):
    if re.search(r"완치|curative", q, re.I):
        return "curative"
    return "palliative" if re.search(r"고식|palliative", q, re.I) else None


PARSERS = {
    "diagnosis.diagnosis_date": lambda q, ctx: parse_date(q),
    "diagnosis.histology": lambda q, ctx: _vocab("diagnosis.histology", q),
    "diagnosis.grade": _grade,
    "stage.ctnm": lambda q, ctx: _tnm(q, ctx, prefix="c"),
    "stage.ptnm": lambda q, ctx: _tnm(q, ctx, prefix="p"),
    "stage.yptnm": lambda q, ctx: _tnm(q, ctx, prefix="yp"),
    "stage.group": _group,
    "stage.disease_extent": _extent,
    "stage.metastatic_sites": _metastatic_sites,
    "stage.positive_ln_count": _ln_count,
    "stage.operable": lambda q, ctx: _yes_no(q),
    # 유방 종괴 크기만 (흉부 CT의 폐 결절 크기 등은 받지 않는다)
    "stage.clinical_size_mm": lambda q, ctx: _size_mm(q) if re.search(r"유방|breast|종괴|mass", q, re.I) else None,
    "stage.pathologic_size_mm": lambda q, ctx: _size_mm(q),
    "receptors.er_percent": _receptor("er_percent"),
    "receptors.pr_percent": _receptor("pr_percent"),
    "receptors.her2_ihc": _her2_ihc,
    "receptors.her2_ish": _her2_ish,
    "receptors.pdl1": _pdl1,
    "proliferation.ki67_percent": _percent,
    "patient.gender": _gender,
    "patient.age": _age,
    "patient.menopausal_status": lambda q, ctx: _vocab("patient.menopausal_status", q),
    "patient.menopausal_basis": _menopausal_basis,
    # 'PS 1'처럼 ECOG를 빼고 써도 받는다. Allred의 PS(비율 점수)는 받지 않는다 (2026-10-28 표현 변형)
    "patient.ecog": lambda q, ctx: None if re.search(r"Allred|\bIS\b", q, re.I) else
                    _number(r"(?:ECOG\s*(?:PS)?|(?<![A-Za-z])PS)\s*:?\s*([0-4])(?!\d)")(q, ctx),
    "patient.height_cm": _number(r"(\d+(?:\.\d+)?)\s*cm"),
    "patient.weight_kg": _number(r"(\d+(?:\.\d+)?)\s*kg"),
    "patient.lvef_percent": _number(r"(\d+(?:\.\d+)?)\s*%"),
    "patient.cardiac_history": _need_vocab("patient.cardiac_history"),
    "patient.mediastinal_radiation": _need_vocab("patient.mediastinal_radiation"),
    "patient.visceral_crisis": _need_vocab("patient.visceral_crisis"),
    # 재발·전이, '없음' 구절, 심장 병명(cardiac_history 칸), 빈 구절, S) 줄의 증상('기침 3주.')은
    # 동반질환으로 받지 않는다 (2026-10-28 GPU 재실행)
    "patient.comorbidities": lambda q, ctx: None if not q.strip() or re.search(r"재발|전이|metasta", q, re.I)
                                            or NEGATION.search(q) or _vocab("patient.cardiac_history", q)
                                            or ctx.line.lstrip().startswith("S)") else [q],
    "neoadjuvant_response.pcr": _pcr,
    "neoadjuvant_response.rcb": _rcb,
    "recurrence.recurrence_date": _need(r"전이|재발|metasta|recur", lambda q, ctx: parse_date(q)),
    "recurrence.adjuvant_endocrine_end_date": _endocrine_end,
    "recurrence.status": _recurrence_status,
    # TNM의 M0는 진단 시 병기다. 재발 부위 칸에는 받지 않는다 (2026-10-28, 시험 VC-0121 hari)
    "recurrence.metastatic_sites": lambda q, ctx: None if re.fullmatch(r"\s*[cpy]*M[01X]\s*", q) else _metastatic_sites(q, ctx),
    "recurrence.metastasis_day": _metastasis_day,
    "recurrence.recurrence_day": _day_field,
    "recurrence.surgery": _need(SURGERY.pattern, lambda q, ctx: _yes_no(q)),
    # 수술 목적은 그 줄에 수술·절제가 있을 때만 ('고식 항암'의 '고식'을 받지 않는다, 2026-10-28 시험 VC-0114·0127)
    "recurrence.surgery_intent": lambda q, ctx: _intent(q, ctx) if SURGERY.search(q + " " + ctx.line) else None,
    "recurrence.later_distant": _need(r"원격|distant", lambda q, ctx: _yes_no(q)),
}


# ---------- 유전자 ----------
VARIANT = re.compile(r"\b([A-Z][A-Z0-9]+)\s+c\.(\S+)\s*\(p\.([^)]+)\)(?:\s*VAF\s*(\d+(?:\.\d+)?)\s*%)?")


GENE_NEG = re.compile(r"검출되지 않|미검출|not detected|negative|음성|변이 없음|\bno (?:pathogenic )?(?:variant|mutation)|"
                      r"not identified|not found", re.I)
GENE_POS = re.compile(r"병원성|pathogenic|검출됨|검출되었|변이 있음|양성|positive|\bdetected", re.I)
GENE_HEADS = re.compile(r"(검출되지 않|미검출|not detected)|(검출된 변이|detected variants|clinically significant)", re.I)
REVIEW = "_review"     # 정규화 결과에 붙는 확인 요청 표시. 조립(assemble)이 떼어 issues에 needs_review로 남긴다


def _gene(gene: str, q: str, ctx: Context | None = None) -> dict | None:
    """유전자 칸. 구절에 그 유전자 이름이 없으면 None ('BRCA1/2'는 BRCA1·BRCA2 둘 다).

    - 변이 표기(c. / p.)가 있으면 detected. 변이 종류는 MAF Variant_Classification 표기 (fs: c.의 del → Frame_Shift_Del, dup·ins → _Ins)
    - '검출되지 않음'류 단어가 있으면 not_detected
    - 유전자 이름만 나열된 구절은 문서에서 바로 위 머리말이 '검출되지 않음'일 때만 not_detected
    - '병원성 변이'처럼 검출을 말하지만 변이 표기가 없으면 detected + 변이 원문만 + 확인 요청 (2026-10-27 2단계).
      예전에는 not_detected로 봐서 양성 결과가 음성으로 바뀌었다 (시험 세트 VC-0116·0119)
    - 그 밖에 무엇인지 알 수 없는 구절은 None
    """
    named = re.search(rf"(?<![A-Z0-9]){gene}(?![0-9])", q) or (
        gene in ("BRCA1", "BRCA2") and re.search(r"BRCA\s*1\s*/\s*2", q))
    if not named:
        return None
    if NOT_DONE.search(q):
        return {"status": "not_done"}
    variants = []
    for m in VARIANT.finditer(q):
        if m.group(1) != gene:
            continue
        p, cdna = m.group(3), m.group(2)
        frame = "Frame_Shift_Del" if "del" in cdna else "Frame_Shift_Ins" if re.search("dup|ins", cdna) else "Frame_Shift"
        kind = ("Nonsense_Mutation" if re.fullmatch(r"[A-Z]\d+\*", p) else
                frame if "fs" in p else "Missense_Mutation" if re.fullmatch(r"[A-Z]\d+[A-Z]", p) else None)
        variants.append({"protein_change": p, "variant_type": kind,
                         "vaf": m.group(4) and round(float(m.group(4)) / 100, 6),
                         "raw": re.sub(r"\s+", " ", m.group(0))})
    if variants:
        return {"status": "present", "result": "detected", "variants": variants}
    if GENE_NEG.search(q) or (re.fullmatch(r"[A-Z0-9/,\s]+", q) and _under_negative_heading(q, ctx)):
        return {"status": "present", "result": "not_detected", "variants": []}
    if GENE_POS.search(q):
        raw = re.sub(r"\s+", " ", q.strip())
        return {"status": "present", "result": "detected",
                "variants": [{"protein_change": None, "variant_type": None, "vaf": None, "raw": raw}],
                REVIEW: "변이 표기(c. / p.)가 없는 검출 구절: 원문에서 변이를 확인할 것"}
    return None


def _under_negative_heading(q: str, ctx: Context | None) -> bool:
    """유전자 이름만 나열된 구절의 바로 위 머리말이 '검출되지 않음'인지 (검출된 변이 / 검출되지 않음 목록)."""
    if ctx is None:
        return False
    i = ctx.doc.text.find(q)
    heads = list(GENE_HEADS.finditer(ctx.doc.text[:i if i >= 0 else 0]))
    return bool(heads) and heads[-1].group(1) is not None


# ---------- 목록 칸 ----------
def _drug_names(path: Path = DRUG_NAMES_CSV) -> dict[str, list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["raw_name"].strip().casefold(): r["generic_names"].split("+") for r in csv.DictReader(f)}


DRUG_NAMES = _drug_names()
DRUG_TABLE = load_drug_table()


def _drugs(text: str) -> list[tuple[str, list[int]]]:
    """(성분명, 원문에서 그 성분 이름이 끝나는 위치들). 겹치는 이름은 긴 것, 성분 순서는 처음 나온 순서.
    "AC (doxorubicin 60mg/m2 ...)"처럼 약어와 성분명이 함께 있으면 위치가 둘이다 (용량은 성분명 뒤에 있다)."""
    low, hits = text.casefold(), []
    for name, generics in DRUG_NAMES.items():
        pat = re.escape(name)
        if name[0].isascii() and name[0].isalnum():
            pat = r"(?<![a-z0-9])" + pat
        if name[-1].isascii() and name[-1].isalnum():
            pat += r"(?![a-z0-9])"
        hits += [(m.start(), m.end(), generics) for m in re.finditer(pat, low)]
    out: dict[str, list[int]] = {}
    end = -1
    for s, e, generics in sorted(hits, key=lambda h: (h[0], -h[1])):
        if s < end:
            continue
        end = e
        for g in generics:
            out.setdefault(g, []).append(e)
    return list(out.items())


def _cycles(q: str) -> dict | None:
    # 주기 수: '#12', 'x12', '×12', '12회', '12 cycles' (2026-10-28 표현 변형)
    m = re.search(r"(?:q(\d)w|(weekly)|(\d+)\s*일)?\s*(?:[#x×]\s*(\d+)(?!\s*(?:mg|일))|(\d+)\s*(?:회|cycles?\b))", q, re.I)
    if not m:
        return None
    interval = int(m.group(1)) * 7 if m.group(1) else 7 if m.group(2) else int(m.group(3)) if m.group(3) else None
    return {"value": int(m.group(4) or m.group(5)), "basis": "recorded", "interval_days": interval,
            "interval_basis": "recorded" if interval else None}


def _regimen(q: str, ctx: Context) -> dict:
    """투약 한 줄의 공통 부분: 약(첫 날짜 앞), 날짜, 주기, 날짜 뒤 글(반응·중단 사유)."""
    dates = list(DATE.finditer(q))
    head = q[:dates[0].start()] if dates else q
    tail = q[dates[-1].end():] if dates else ""
    return {"drugs": _drugs(head), "head": head, "tail": tail,
            "start": parse_date(dates[0].group(0)) if dates else None,
            "end": parse_date(dates[1].group(0)) if len(dates) > 1 else None,
            "ongoing": len(dates) == 1 and bool(re.search(r"현재|복용 중|투여 중|ongoing", q)),
            "cycles": _cycles(q)}


def _treatment(q: str, ctx: Context) -> dict | None:
    r = _regimen(q, ctx)
    if not r["drugs"]:
        return None
    setting = re.search(r"보조|선행|고식", ctx.line)
    s, e = _day(r["start"], ctx.dx_date), _day(r["end"], ctx.dx_date)
    return {"drugs": [g for g, _ in r["drugs"]],
            "setting": setting and {"보조": "adjuvant", "선행": "neoadjuvant", "고식": "metastatic"}[setting.group(0)],
            "start_date": r["start"], "end_date": r["end"], "start_day": s, "end_day": e,
            "duration_days": e - s if s is not None and e is not None else None,
            **({"ongoing": True} if r["ongoing"] else {}),
            "cycles": r["cycles"], "stop_reason": _stop_reason(r["tail"]),
            "best_response": _vocab("treatment_history.best_response", r["tail"]),
            **({"doses": doses} if (doses := _doses(q, r)) else {})}


# 약별 용량 (treatment_history[].doses, 2026-10-28). 가상 차트 생성기(virtual_chart.row_doses)와 따로 쓴다.
# 용량이 적힌 약만. 1회 용량은 약 이름(상품명이면 뒤의 "(일반명)") 바로 뒤 숫자 + mg/m2·mg/kg·mg, 또는 AUC.
# 총량은 1회 × 주기 수 (d1, d8이면 주기당 2회). 매일 먹는 약, AUC(목표 노출량), 주기 수가 없으면 "No value"
# 약 이름 뒤에 '누적'·'총'이 오면 적힌 총량이다 (doxorubicin 누적 240mg/m2 → total recorded, 2026-10-28 표현 변형)
DOSE_AT = re.compile(r"\s*\)?\s*(누적|총|cumulative|total)?\s*"
                     r"(?:(\d+(?:\.\d+)?)\s*(mg/m2|mg/kg|mg)(?![a-z/])|AUC\s*(\d+(?:\.\d+)?))", re.I)
DAILY_ORAL = {"tamoxifen", "anastrozole", "letrozole", "exemestane", "megestrol", "palbociclib", "ribociclib",
              "abemaciclib", "everolimus", "capecitabine", "lapatinib", "tucatinib", "neratinib", "olaparib",
              "talazoparib", "alpelisib", "capivasertib", "inavolisib", "elacestrant", "imlunestrant"}


def _doses(q: str, r: dict) -> list[dict]:
    out = []
    twice = 2 if re.search(r"d1,\s*d8", q) else 1
    for g, ends in r["drugs"]:
        m = next((m for m in (DOSE_AT.match(r["head"], e) for e in ends) if m), None)
        if not m:
            continue
        per = {"value": _num(m.group(2)), "unit": m.group(3)} if m.group(2) else {"value": _num(m.group(4)), "unit": "AUC"}
        if m.group(1):
            out.append({"drug": g, "per_admin": "No value", "total": per, "basis": "recorded"})
            continue
        daily = g in DAILY_ORAL or re.match(r"\s*(?:qd|bid|tid)\b", r["head"][m.end():], re.I)
        total = "No value" if daily or not r["cycles"] or per["unit"] == "AUC" else \
            {"value": _num(str(round(per["value"] * r["cycles"]["value"] * twice, 3))), "unit": per["unit"]}
        out.append({"drug": g, "per_admin": per, "total": total, "basis": "estimated"})
    return out


# 중단 사유 단어는 field_vocab.csv의 treatment_history.stop_reason. 한 줄에 둘 이상 맞으면 앞 값
# ("관절통 (부작용)으로 중단 후 진행" → toxicity). 유지요법 전환·계획된 변경·독성은 같은 차수 (rules.py SAME_LINE_STOPS)
STOP_REASONS = ("planned_switch", "maintenance", "toxicity", "completed", "progression")


def _stop_reason(tail: str) -> str | None:
    low = tail.casefold()
    for reason in STOP_REASONS:
        if any(re.search(_expr_pattern(e.casefold()), low)
               for e in VOCAB.expressions("treatment_history.stop_reason", reason)):
            return reason
    return None


def _anthracycline(q: str, ctx: Context) -> dict | None:
    r = _regimen(q, ctx)
    drugs = [g for g, _ in r["drugs"]]
    for g, ends in r["drugs"]:
        if DRUG_TABLE.get(g, ("", ""))[1] != "anthracycline":
            continue
        dose = next((m for m in (re.match(r"\s*(\d+(?:\.\d+)?)\s*(mg/m2|mg)", r["head"][e:]) for e in ends) if m), None)
        dose = dose and {"value": _num(dose.group(1)), "unit": dose.group(2)}
        cycles = r["cycles"]
        total = dose and cycles and {"value": _num(str(dose["value"] * cycles["value"])), "unit": dose["unit"]}
        return {"drug": g, "timeline_index": None, "combined_with": [x for x in drugs if x != g],
                "dose_per_admin": dose, "cycles": cycles, "total_dose": total}
    return None


def _imaging(q: str, ctx: Context) -> dict | None:
    # 머리글과 "검사:" 줄에서 검사 종류를 찾는다 ([영상의학 판독]은 머리글에 종류가 없다)
    exam = re.search(r"^\s*(?:검사|Exam)\s*:.*$", ctx.doc.text, re.M)
    header = ctx.doc.text.split("\n", 1)[0] + (" " + exam.group(0) if exam else "")
    modality = next((m for m, pat in [("bone_scan", r"bone scan|골\s*스캔|뼈\s*스캔"), ("PET", r"PET"),
                                      ("MRI", r"MRI"), ("CT", r"CT"), ("ultrasound", r"초음파|ultrasound|US\b"),
                                      ("X-ray", r"X-ray|흉부 사진")]
                     if re.search(pat, header, re.I)), "other")
    if "외" in q:          # "골전이 외 원격 전이 없음": '외' 앞만 전이 부위
        sites = _sites(q.split("외", 1)[0])
    else:
        sites = [] if NEGATION.search(q) else _sites(q)
    return {"modality": modality, "day": _day(ctx.doc.doc_date, ctx.dx_date), "date": ctx.doc.doc_date,
            "sites": sites, "certainty": "suspected" if re.search(r"의증|의심|r/o|suspicious|possible", q, re.I)
            else "confirmed"}


ITEMS = {
    "treatment_history": _treatment,
    "anthracycline_drug_dose.drugs": _anthracycline,
    "imaging_findings": _imaging,
}


# ====================================================================================================
# assemble (옛 src/input/script/pipeline/assemble.py)
# ====================================================================================================
# IN-4~6 조립과 마무리 [규칙] (notes/input_module_design.md §2 IN-4·IN-5·IN-6·마무리).
#
# 후보 목록(IN-2) → 인용 확인 → 정규화(IN-3) → patient_state.
#
# - IN-4 값 고르기: 전이 병소 검체가 있으면 그 값 중 가장 늦은 것이 value, 원발 값은 history (recurrence).
#   없으면 관찰 날짜(없으면 문서 날짜)가 가장 늦은 값이 value, 이전 값은 history (newer_result).
# - IN-5 충돌: 고른 날짜에 값이 둘 이상이면 고르지 않는다. 그 칸은 fields에서 빼고 후보를 모두 conflicts[]에 넣는다.
# - IN-6 누락: 후보가 없는 기본 칸은 not_recorded. 미시행·결과 대기·예정은 정규화(IN-3)가 not_done으로 낸다.
# - 투약: 표 첫 칸에 보조·선행·고식이 없으면 전이일·수술일과 비교해 setting을 정하고,
#   중단 사유가 진행이면 투약 기간 안의 재발·전이일(없으면 종료일)을 progression_day로 둔다.
#   anthracycline 용량은 투약 줄에서 계산한다 (따로 후보를 받지 않는다).
# - 마무리: index_day(가장 늦은 경과기록 날짜), genomic_reports(IN-7), lines.annotate(차수·간주 규칙), 스키마 검증.
#
# 인용을 못 찾은 후보, 정규화하지 못한 후보, 스키마 오류는 버리지 않고 issues로 돌려준다 (확인 요청·채점용).

SCHEMA = Path(__file__).resolve().parents[3] / "schemas" / "patient_state.json"
SCHEMA_VERSION = "0.1-draft6"
# 차트에 없으면 not_recorded로 두는 칸 (draft6 기본 칸). 그 밖의 칸은 후보가 있을 때만 둔다
DEFAULT_FIELDS = {
    "diagnosis": ["diagnosis_date", "histology", "grade"],
    "stage": ["ctnm", "ptnm", "group", "positive_ln_count", "disease_extent", "metastatic_sites", "operable"],
    "receptors": ["er_percent", "pr_percent", "her2_ihc", "her2_ish", "pdl1"],
    "proliferation": ["ki67_percent"],
    "patient": ["gender", "age", "menopausal_status", "menopausal_basis", "ecog"],
    "neoadjuvant_response": ["pcr", "rcb"],
    "recurrence": ["recurrence_date", "adjuvant_endocrine_end_date", "status", "metastatic_sites", "metastasis_day",
                   "recurrence_day", "surgery", "surgery_intent"],
}
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
GROUP_ORDER = ["diagnosis", "stage", "receptors", "proliferation", "patient", "imaging_findings", "treatment_history",
               "anthracycline_drug_dose", "neoadjuvant_response", "recurrence", "molecular", "genomic_reports"]
LIST_FIELDS = {"treatment_history", "imaging_findings"}
DERIVED = {"anthracycline_drug_dose.drugs"}     # 투약 줄에서 계산하므로 후보를 쓰지 않는다
DE_NOVO_EMPTY = {"recurrence.status", "recurrence.metastatic_sites", "recurrence.recurrence_date",
                 "recurrence.recurrence_day"}  # 진단 시 IV기면 비우는 재발 칸


def assemble(docs: list[Document], candidates: list[dict], *, patient_ref: str, created_at: str,
             mapping: dict[str, str] | None = None) -> tuple[dict, list]:
    """patient_state와 issues [{reason, candidate | errors}]. docs는 원문, mapping은 IN-0 대응표 (구절 되돌리기)."""
    by_id = {d.doc_id: d for d in docs}
    order = {d.doc_id: i for i, d in enumerate(docs)}
    issues, found = [], []
    for c in candidates:
        if c["field"] in DERIVED:
            continue
        doc = by_id.get(c["doc_id"])
        src = doc and locate(c["quote"], doc, mapping)
        if src is None:
            issues.append({"reason": "quote_not_found", "candidate": c})
            continue
        found.append((c, doc, src))
    found.sort(key=lambda x: (order[x[0]["doc_id"]], x[2]["char_start"]))

    dx = _diagnosis_date(found)
    items = []                     # (후보, 문서, source, 정규화 결과)
    for c, doc, src in found:
        out = normalize(c["field"], src["quote"], Context.of(doc, src["char_start"], dx))
        if out is None:
            issues.append({"reason": "not_normalized", "candidate": c})
            continue
        if REVIEW in out:                  # 값은 쓰되 확인 요청을 남긴다 (화면 1에서 보여 줄 목록)
            issues.append({"reason": "needs_review", "candidate": c, "note": out[REVIEW]})
            out = {k: v for k, v in out.items() if k != REVIEW}
        items.append((c, doc, src, out))

    # ypTNM이 있는 문서의 크기·림프절은 선행요법 뒤 잔존 값이라 yptnm에만 둔다 (pathologic_size_mm 스키마 설명)
    yp_docs = {c["doc_id"] for c, *_ in items if c["field"] == "stage.yptnm"}
    keep = []
    for it in items:
        if it[0]["field"] in ("stage.pathologic_size_mm", "stage.positive_ln_count") and it[0]["doc_id"] in yp_docs:
            issues.append({"reason": "rule", "candidate": it[0], "note": "ypTNM 문서의 잔존 값"})
        else:
            keep.append(it)
    items = keep

    fields: dict = {g: {k: {"status": "not_recorded"} for k in ks} for g, ks in DEFAULT_FIELDS.items()}
    fields["molecular"] = {"mutations": {g: {"status": "not_recorded"} for g in GENES}}
    conflicts = []
    by_field: dict[str, list] = {}
    for it in items:
        if it[0]["field"] not in LIST_FIELDS:
            by_field.setdefault(it[0]["field"], []).append(it)
    # 다른 칸을 보고 거르는 칸이 있어 병기 범주·재발 상태를 먼저 정한다. 병기 범주는 TNM으로 계산하므로 TNM이 그보다 먼저다
    first = ("stage.ctnm", "stage.ptnm", "stage.yptnm", "stage.disease_extent", "recurrence.status")
    by_field.setdefault("stage.disease_extent", [])     # 범주 후보가 없어도 TNM으로 계산한다
    for field in sorted(by_field, key=lambda f: first.index(f) if f in first else len(first)):
        its = by_field[field]
        if field in ("stage.group", "stage.disease_extent"):
            # 선행요법 뒤 병기(ypStage)는 진단 시 병기군이 아니다. AJCC 8판은 선행 후 병기군을 매기지 않고
            # ypT·ypN만 stage.yptnm에 둔다 (2026-10-27 A 결정)
            yp = [it for it in its if YP_STAGE.search(it[2]["quote"])]
            issues += [{"reason": "rule", "candidate": it[0], "note": "선행요법 뒤 병기 (진단 시 병기군 아님)"} for it in yp]
            its = [it for it in its if it not in yp]
        if field == "stage.disease_extent":
            _set_extent(fields, its, items, conflicts, issues)
            continue
        extent, status = _value(fields, "stage.disease_extent"), _value(fields, "recurrence.status")
        if field == "stage.metastatic_sites" and extent in ("early", "locally_advanced"):
            # 진단 시 IV기가 아니면 진단 시 전이 부위는 없다 (나중 전이를 이 칸에 넣은 후보를 뺀다)
            its = _drop(its, lambda out: isinstance(out.get("value"), list), issues, "진단 시 IV기가 아님")
        if field == "recurrence.metastatic_sites" and status == "none":
            # 재발이 없으면 재발 부위 칸은 비워 둔다 (정답 표기, 2026-10-23 A 결정)
            its = _drop(its, lambda out: True, issues, "재발 없음")
        if field in DE_NOVO_EMPTY and extent == "metastatic":
            # 진단 시 IV기는 재발이 아니라 재발 칸은 비운다 (진행 소견을 재발 부위로 낸 후보, 2026-10-27 A 결정)
            its = _drop(its, lambda out: True, issues, "진단 시 IV기")
        if not its:
            continue
        entries = [_entry(c, doc, src, out) for c, doc, src, out in its]
        chosen = _choose(field, entries)
        if isinstance(chosen, dict) and "conflict" in chosen:
            conflicts.append(chosen["conflict"])
            *groups, key = field.split(".")
            parent = fields
            for g in groups:
                parent = parent.get(g, {})
            parent.pop(key, None)          # 고르지 않은 칸은 not_recorded로도 두지 않는다
            continue
        _set(fields, field, chosen)

    # 진단 시 IV기면 전이 기준일은 0 (스키마 metastasis_day 설명). 투약 setting도 이 값으로 정해진다
    if _value(fields, "stage.disease_extent") == "metastatic" and \
            fields["recurrence"]["metastasis_day"].get("status") == "not_recorded":
        ext = fields["stage"]["disease_extent"]
        fields["recurrence"]["metastasis_day"] = {"status": "present", "value": 0, "raw": ext["raw"],
                                                  "source": ext["source"]}
    # 진단 시 IV기가 아니고 진단 시 전이 부위 후보가 없으면 TNM의 M0로 '해당 없음'을 채운다
    if _value(fields, "stage.disease_extent") in ("early", "locally_advanced") and \
            fields["stage"].get("metastatic_sites", {}).get("status") == "not_recorded":
        tnm = next((fields["stage"][k] for k in ("ptnm", "ctnm", "yptnm")
                    if (_value(fields, f"stage.{k}") or {}).get("m") == "M0"), None)
        if tnm:
            fields["stage"]["metastatic_sites"] = {"status": "present", "value": "[Not Applicable]",
                                                   "raw": tnm["raw"], "source": tnm["source"]}
    # 재발 상태 후보가 없거나 버려졌어도 재발·전이 부위가 있으면 원격 전이다 (LLM이 상태 칸에 'PD'를 내는 경우).
    # 진단 시 IV기면 재발 부위 후보를 위에서 모두 빼서 여기 오지 않는다
    sites = fields["recurrence"].get("metastatic_sites", {})
    if fields["recurrence"].get("status", {}).get("status") == "not_recorded" and isinstance(sites.get("value"), list):
        fields["recurrence"]["status"] = {"status": "present", "value": "distant", "raw": sites["raw"],
                                          "source": sites["source"]}

    rows =[(c, doc, src, out) for c, doc, src, out in items if c["field"] == "treatment_history"]
    rows.sort(key=lambda r: (r[3]["start_day"] is None, r[3]["start_day"] or 0))
    history = [{**out, "source": src} for _, _, src, out in rows]
    images = [{**out, "source": src} for c, _, src, out in items if c["field"] == "imaging_findings"]
    _fill_treatment(history, fields, images)
    anthra = []
    for (c, doc, src, out) in rows:
        a = normalize("anthracycline_drug_dose.drugs", src["quote"], Context.of(doc, src["char_start"], dx))
        if a:
            anthra.append({**a, "raw": src["quote"], "source": src})
    fields["treatment_history"] = history
    _endocrine_end_from_rows(fields, history)
    fields["anthracycline_drug_dose"] = {
        "administered": "positive" if anthra else "negative" if history else "No value", "drugs": anthra}
    if images:
        fields["imaging_findings"] = images
    fields["genomic_reports"] = [_genomic_report(d, fields) for d in docs if d.doc_type == "molecular"]
    fields = {g: fields[g] for g in GROUP_ORDER if g in fields}

    ps = {"schema_version": SCHEMA_VERSION, "patient_ref": patient_ref, "created_at": created_at,
          "index_day": _index_day(docs, dx), "documents": [d.entry() for d in docs], "fields": fields,
          "conflicts": conflicts}
    annotate(ps, load_drug_table())
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(ps)]
    if errors:
        issues.append({"reason": "schema", "errors": errors})
    return ps, issues


YP_STAGE = re.compile(r"y[pc]\s*-?\s*stage|y[pc]T", re.I)


def _anatomic_extent(tnm: dict, m: str | None) -> str | None:
    """AJCC 8판 해부학적 병기표의 범주. M1 → IV기, T4·N2·N3·T3N1(N1mi 포함) → III기, T·N을 모르면 None.
    N1mi가 따로 내려가는 것은 T0~T1 N1mi(IB기)뿐이라 T3N1mi는 IIIA기다."""
    t, n = tnm.get("t") or "", tnm.get("n") or ""
    if (m or "").startswith("M1"):
        return "metastatic"
    if t.startswith("T4") or n.startswith(("N2", "N3")) or (t.startswith("T3") and n.startswith("N1")):
        return "locally_advanced"
    if not t.startswith("T") or not n.startswith("N") or "X" in t + n:
        return None
    return "early"


def _set_extent(fields: dict, its: list, items: list, conflicts: list, issues: list) -> None:
    """stage.disease_extent = 진단 시 범주 (2026-10-27 A 결정).
    진단 시 TNM: 선행요법 환자(yptnm 칸 또는 선행 투약이 있음)는 ctnm, 수술을 먼저 했으면 ptnm, 없으면 ctnm.
    yptnm은 쓰지 않는다. M은 다른 칸에 M1이 있으면 M1. 그 TNM의 해부학적 범주(_anatomic_extent)를 쓰고,
    TNM으로 정할 수 없을 때만 차트의 병기군 구절을 쓴다. 구절과 다르면 확인 요청을 남긴다 (예후 병기일 수 있음)."""
    stage = fields["stage"]
    neo = "yptnm" in stage or any(c["field"] == "treatment_history" and out.get("setting") == "neoadjuvant"
                                  for c, _, _, out in items)
    keys = ("ctnm",) if neo else ("ptnm", "ctnm")
    key = next((k for k in keys if _value(fields, f"stage.{k}")), None)
    m1 = next((k for k in ("ctnm", "ptnm") if ((_value(fields, f"stage.{k}") or {}).get("m") or "").startswith("M1")), None)
    computed = _anatomic_extent(_value(fields, f"stage.{key}") if key else {}, "M1" if m1 else None)
    if m1 and computed == "metastatic":
        key = m1
    chosen = _choose("stage.disease_extent", [_entry(c, doc, src, out) for c, doc, src, out in its]) if its else None
    conflict = isinstance(chosen, dict) and "conflict" in chosen
    if computed is None:
        if conflict:
            conflicts.append(chosen["conflict"])
            stage.pop("disease_extent", None)
        elif chosen:
            _set(fields, "stage.disease_extent", chosen)
        return
    if chosen and not conflict and chosen.get("value") == computed:
        _set(fields, "stage.disease_extent", chosen)
        return
    tnm = stage[key]
    stage["disease_extent"] = {"status": "present", "value": computed, "raw": tnm["raw"], "source": tnm["source"]}
    for c, *_ in its:
        issues.append({"reason": "needs_review", "candidate": c,
                       "note": f"차트 병기군과 {key} 해부학적 병기 범주({computed})가 다름 (예후 병기일 수 있음)"})


def _drop(its: list, test, issues: list, note: str) -> list:
    """test(정규화 결과)가 참인 후보를 빼고 issues에 남긴다."""
    out = []
    for it in its:
        if test(it[3]):
            issues.append({"reason": "rule", "candidate": it[0], "note": note})
        else:
            out.append(it)
    return out


def _diagnosis_date(found) -> str | None:
    for c, doc, src in found:
        if c["field"] == "diagnosis.diagnosis_date":
            out = normalize(c["field"], src["quote"], Context.of(doc, src["char_start"]))
            if out and out["status"] == "present":
                return out["value"]
    return None


def _entry(c: dict, doc: Document, src: dict, out: dict) -> dict:
    """정규화 결과 + 원문 표기·검체·관찰 날짜·근거. 유전자 칸에는 raw가 없다 (변이마다 raw가 있다)."""
    e = dict(out)
    if not c["field"].startswith("molecular."):
        e.setdefault("raw", src["quote"])
    for k in ("specimen",) if c["field"].startswith("molecular.") else ("specimen", "observed_date"):
        if c.get(k) is not None:
            e[k] = c[k]
    e["source"] = src
    e["_date"] = c.get("observed_date") or doc.doc_date or ""
    return e


def _choose(field: str, entries: list[dict]):
    """IN-4·IN-5. 고른 entry(history 포함) 또는 {"conflict": {...}}.

    patient.age는 진단 시 나이라 날짜가 가장 이른 값을 고르고, 나중 문서의 나이는 이력으로 두지 않는다
    (at_index.age가 진단 시 나이 + index_day로 계산한다). 현재 값과 값·검체가 같은 이전 값은 같은 내용을
    다시 적은 것이라 이력에서 뺀다 (성별·나이처럼 문서마다 나오는 칸)."""
    meta = [e for e in entries if e.get("specimen") == "metastasis"]
    if field == "patient.age":
        pool = [e for e in entries if e["_date"]] or entries
        pick = min(e["_date"] for e in pool)
    else:
        pool = meta or entries
        if field.startswith("molecular."):
            # 변이 표기(c. / p.)가 있는 후보를 날짜보다 먼저 고른다. 경과기록 요약('생식세포 BRCA1 병원성 변이')이
            # 보고서보다 늦은 날짜라 골려 변이 상세가 빠지던 것 (2026-10-28 GPU 재실행, 시험 VC-0116·0119)
            pool = [e for e in pool if any(v.get("protein_change") for v in e.get("variants") or [])] or pool
        pick = max(e["_date"] for e in pool)
    top = [e for e in pool if e["_date"] == pick]
    if len({_value_key(e) for e in top}) > 1:
        values = ", ".join(e["source"]["quote"] for e in top)
        return {"conflict": {"field": field, "candidates": [_clean(e) for e in entries],
                             "note": f"같은 날짜({pick or '날짜 없음'})의 값이 다름: {values}"}}
    cur = top[0] if field == "patient.age" else top[-1]
    current = _clean(cur)
    if field == "patient.age" or field.startswith("molecular."):     # 유전자 칸 스키마에는 history가 없다
        return current
    hist = [{**_clean(e), "superseded_reason": "recurrence" if meta and e.get("specimen") != "metastasis"
             else "newer_result"} for e in entries
            if e is not cur and (_value_key(e), e.get("specimen")) != (_value_key(cur), cur.get("specimen"))]
    if hist:
        current["history"] = hist
    return current


def _value_key(e: dict) -> str:
    return json.dumps({k: e.get(k) for k in ("status", "value", "result", "variants")}, sort_keys=True)


def _clean(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "_date"}


def _set(fields: dict, path: str, entry: dict) -> None:
    *groups, key = path.split(".")
    cur = fields
    for g in groups:
        cur = cur.setdefault(g, {})
    cur[key] = entry


def _value(fields: dict, path: str):
    cur = fields
    for k in path.split("."):
        cur = cur.get(k, {}) if isinstance(cur, dict) else {}
    return cur.get("value") if cur.get("status") == "present" else None


def _day_of(fields: dict, path: str) -> int | None:
    """관찰 날짜가 있는 칸의 진단일 기준 일수 (수술일 = 병리 TNM의 관찰 날짜)."""
    cur = fields
    for k in path.split("."):
        cur = cur.get(k, {})
    dx = _value(fields, "diagnosis.diagnosis_date")
    if not cur.get("observed_date") or not dx:
        return None
    return (dt.date.fromisoformat(cur["observed_date"]) - dt.date.fromisoformat(dx)).days


PROGRESSION_IMAGE = re.compile(r"진행|PD|새로|증가|악화|progress|new|increas", re.I)


def _fill_treatment(history: list[dict], fields: dict, images: list[dict] = ()) -> None:
    mday = _value(fields, "recurrence.metastasis_day")
    # 진행을 보인 영상의 날 (정답은 영상으로 진행을 확인한 날, 6단계 2026-10-27)
    scans = [i["day"] for i in images if i.get("day") is not None and PROGRESSION_IMAGE.search(i["source"]["quote"])]
    surgery = _day_of(fields, "stage.yptnm") or _day_of(fields, "stage.ptnm")
    events = [d for d in (_value(fields, "recurrence.recurrence_day"), mday) if d is not None]
    for t in history:
        s, e = t["start_day"], t["end_day"]
        if t["setting"] is None:
            if mday is not None and s is not None and s >= mday:
                t["setting"] = "metastatic"
            elif surgery is not None and s is not None and s < surgery:
                t["setting"] = "neoadjuvant"
            else:
                t["setting"] = "adjuvant"
        prog = None
        if t["stop_reason"] == "progression":
            # 진행 영상: 투약 뒤 ~ 종료 4주 뒤 (종료 뒤 찍은 영상으로 바꾸는 일이 있다) → 투약 기간 안 재발·전이일 → 종료일
            seen = [d for d in scans if s is not None and e is not None and s < d <= e + 28]
            inside = [d for d in events if s is not None and e is not None and s <= d <= e]
            prog = min(seen) if seen else min(inside) if inside else e
        t["progression_day"] = prog
        keys = ["drugs", "setting", "start_date", "end_date", "start_day", "end_day", "duration_days", "ongoing",
                "cycles", "progression_day", "stop_reason", "best_response", "source", "doses"]
        ordered = {k: t[k] for k in keys if k in t}
        t.clear()
        t.update(ordered)


def _endocrine_end_from_rows(fields: dict, history: list[dict]) -> None:
    """보조 내분비 종료일 후보가 없으면 투약 표의 보조 내분비 줄 종료일로 채운다 (근거 = 그 투약 줄, 2026-10-28).
    경과기록의 종료 구절을 LLM이 놓쳐도 같은 날짜가 투약 표에 있다 (시험 VC-0122). 투약 중인 줄은 쓰지 않는다."""
    if fields["recurrence"].get("adjuvant_endocrine_end_date", {}).get("status") != "not_recorded":
        return
    rows = [t for t in history if t["setting"] == "adjuvant" and t.get("end_date") and not t.get("ongoing")
            and any(DRUG_TABLE.get(g, ("",))[0] == "Hormone Therapy" for g in t["drugs"])]
    if rows:
        t = max(rows, key=lambda t: t["end_date"])
        fields["recurrence"]["adjuvant_endocrine_end_date"] = {"status": "present", "value": t["end_date"],
                                                               "raw": t["source"]["quote"], "source": t["source"]}


def _genomic_report(doc: Document, fields: dict) -> dict:
    """IN-7. 문서 원문을 해석하지 않고 넘긴다. 검체는 이 문서에서 나온 유전자 칸의 검체, 없으면 '검체:' 줄."""
    genes = list(fields["molecular"].get("mutations", {}).values()) + list(fields["molecular"].get("germline", {}).values())
    specimen = next((g.get("specimen") for g in genes
                     if g.get("source", {}).get("doc_id") == doc.doc_id and g.get("specimen")), None)
    if specimen is None:
        line = re.search(r"검체\s*:.*", doc.text)
        line = line.group(0) if line else ""
        specimen = ("cfDNA" if re.search(r"cfDNA|plasma|혈장|채혈", line, re.I) else
                    "metastasis" if re.search(r"전이|metasta|간|폐|뼈|골", line, re.I) else "primary")
    return {"doc_id": doc.doc_id, "report_date": doc.doc_date, "specimen": specimen, "raw_text": doc.text}


def _index_day(docs: list[Document], dx: str | None) -> int | None:
    """판정 기준일 = 가장 늦은 경과기록 날짜 (가상 차트의 '오늘 외래'). 경과기록이 없으면 가장 늦은 문서 날짜."""
    dates = [d.doc_date for d in docs if d.doc_type == "progress_note" and d.doc_date] \
        or [d.doc_date for d in docs if d.doc_date]
    if not dates or not dx:
        return None
    return (dt.date.fromisoformat(max(dates)) - dt.date.fromisoformat(dx)).days


# ====================================================================================================
# pipeline (옛 src/input/script/pipeline/pipeline.py)
# ====================================================================================================
# 입력 모듈 진입점: 차트 원문 → patient_state (notes/input_module_design.md §1).
#
#     ps, issues = run(chart_text, extract, patient_ref="VC-0103", created_at="2026-10-23T00:00:00+09:00")
#
# extract는 IN-2 자리다: 문서 목록을 받아 후보 목록(src/input/script/evaluation.py 형식)을 돌려주는 함수.
# LLM 추출기를 넣거나, 시험할 때는 정답에서 만든 후보를 그대로 돌려주는 함수를 넣는다.
# extract는 IN-0으로 가린 문서만 받는다. 문서 나누기와 인용 확인은 원문 기준이다 (설계 §7 결정 5).

def run(chart_text: str, extract: Callable[[list[Document]], list[dict]], *, patient_ref: str,
        created_at: str) -> tuple[dict, list[dict]]:
    """patient_state와 issues (인용 못 찾음, 정규화 실패, 스키마 오류)."""
    docs = split(chart_text)
    mapping = identifiers(chart_text)
    masked = [replace(d, text=mask(d.text, mapping)) for d in docs]
    return assemble(docs, extract(masked), mapping=mapping, patient_ref=patient_ref, created_at=created_at)


# ====================================================================================================
# extract (옛 src/input/script/pipeline/extract.py)
# ====================================================================================================
# IN-2 구절 찾기 [LLM] (notes/input_module_design.md §2 IN-2, notes/input_llm_principles_priorities_2026-10-23.md).
#
# 문서 하나씩, 그 문서 종류에서 찾을 칸 목록과 예시 1개를 주고 "이 칸의 값이 적힌 구절"을 JSON으로 받는다.
# LLM은 값을 계산하지 않는다. 칸 이름은 출력 스키마의 enum으로 강제하고, 구절은 인용 확인(quote.py)이 원문에서 다시 찾는다.
# 문서는 IN-0으로 가린 글만 받는다 (pipeline.run이 넘긴다). 모델은 llm/config.toml의 [extract].
#
# 칸 목록은 문서 종류 5가지(병리·경과기록·영상·투약·분자병리)마다 따로 있다. anthracycline 용량은 투약 줄에서
# 규칙이 계산하므로 칸 목록에 없다.
#
# usage (team_project 폴더에서, Ollama 실행 중):
#     python -m src.input.script.pipeline --ids VC-0103 --docs D4              # 문서 하나: 후보·인용 확인·정답 대조·시간
#     python -m src.input.script.pipeline --ids VC-0103 --model qwen2.5:7b     # 모델 바꾸기
#     python -m src.input.script.pipeline --out data/input/runs/hari           # 10건을 끝까지 돌려 저장 → python -m src.input.script.evaluation <폴더>
#     python -m src.input.script.pipeline --replay data/input/runs/hari        # 저장한 LLM 후보로 규칙만 다시 (LLM 호출 없음, 몇 초)

# 문서 종류별 찾을 칸과 설명 (설명은 프롬프트에 그대로 들어간다)
FIELDS = {
    "pathology": {
        "diagnosis.histology": "조직형 (예: 침윤성 유관암, invasive ductal carcinoma)",
        "diagnosis.grade": "조직학적 등급 (Nottingham, NG, grade)",
        "stage.ptnm": "수술 병리 TNM (pT·pN·pM, 병기와 AJCC 판까지 한 구절)",
        "stage.yptnm": "선행요법 뒤 수술 병리 TNM (ypT·ypN)",
        "stage.group": "병기군 (예: stage IIA)",
        "stage.disease_extent": "병기군 구절 (stage.group과 같은 구절을 한 번 더)",
        "stage.metastatic_sites": "진단 당시 원격 전이 여부가 드러나는 TNM 구절 (예: pT2 N0 M0). "
                                  "재발·전이 병소의 생검 소견(Metastatic carcinoma 등)은 넣지 않는다",
        "stage.positive_ln_count": "전이 림프절 수 / 검사한 림프절 수",
        "stage.operable": "'검체:' 줄의 수술 이름 그대로 (예: 좌측 유방 전절제술 + 액와 림프절 절제). "
                          "수술 검체일 때만 낸다. 중심 생검·침생검은 내지 않는다",
        "stage.pathologic_size_mm": "수술 검체 종양 크기",
        "receptors.er_percent": "ER 결과 (판정 단어, Allred 점수, 비율을 한 구절로)",
        "receptors.pr_percent": "PR 결과 (판정 단어, Allred 점수, 비율을 한 구절로)",
        "receptors.her2_ihc": "HER2 면역염색 점수 (0, 1+, 2+, 3+)",
        "receptors.her2_ish": "HER2 ISH(FISH·SISH) 결과",
        "receptors.pdl1": "PD-L1 검사법과 점수 (22C3 CPS, SP142 IC 등)",
        "proliferation.ki67_percent": "Ki-67 비율",
        "neoadjuvant_response.pcr": "선행요법 뒤 잔존 침윤암 여부",
        "neoadjuvant_response.rcb": "RCB 등급",
        "patient.gender": "성별 (F/나이 표기)",
        "patient.age": "나이 (F/나이 표기)",
    },
    "progress_note": {
        "diagnosis.diagnosis_date": "유방암 진단 날짜가 든 구절 (예: 2021.3.5 core bx로 진단)",
        "diagnosis.histology": "조직형",
        "stage.ctnm": "임상 TNM (cT·cN·cM)",
        "stage.group": "병기군 (예: stage IV, IIIA)",
        "stage.disease_extent": "병기군 구절 (stage.group과 같은 구절을 한 번 더)",
        "stage.metastatic_sites": "진단 당시 원격 전이 부위 구절 (진단 시 IV기의 전이 부위, 또는 M0가 든 TNM). "
                                  "나중에 생긴 재발·전이는 넣지 않는다",
        "patient.gender": "성별 (F/나이, 여성)",
        "patient.age": "나이 (F/나이, 00세)",
        "patient.menopausal_status": "폐경 상태 (폐경 전, 폐경 후)",
        "patient.menopausal_basis": "폐경 판단 근거 (LMP, 폐경 나이, 월경 여부, FSH, 난소절제)",
        "patient.ecog": "ECOG 수행 상태",
        "patient.cardiac_history": "심장 질환 과거력. '과거력' 줄의 심장 병명 구절 (협심증, 심부전, 부정맥 등). "
                                   "심장 질환이 없다고 적혀 있으면 그 구절도 낸다",
        "patient.height_cm": "키",
        "patient.weight_kg": "몸무게",
        "patient.lvef_percent": "좌심실 박출률 (LVEF)",
        "patient.mediastinal_radiation": "종격동 방사선 치료 이력",
        "patient.visceral_crisis": "의사가 visceral crisis(장기 위기)라고 판단해 적은 구절. 검사 수치만 있으면 내지 않는다",
        "patient.comorbidities": "유방암 말고 함께 앓는 질환 이름 (예: 고혈압, 당뇨, CKD 3a). 주로 '과거력' 줄에 있다. "
                                 "질환 하나에 구절 하나. 유방암·재발·전이와 심장 질환(cardiac_history 칸)은 넣지 않는다",
        "recurrence.recurrence_date": "첫 재발·전이 날짜와 부위가 든 구절 (예: 2023.4.4 lung metastasis)",
        "recurrence.recurrence_day": "recurrence_date와 같은 구절",
        "recurrence.metastasis_day": "원격 전이 날짜가 든 구절. 진단 시 IV기면 de novo라고 적힌 구절",
        "recurrence.adjuvant_endocrine_end_date": "보조 내분비요법을 끝낸 날짜가 든 구절 (약 이름, 날짜, 종료·중단·완료). "
                                                  "날짜가 없는 구절은 내지 않는다",
        "recurrence.status": "재발 여부와 종류가 적힌 구절 (예: 간 전이, 흉벽 국소 재발, 재발 소견 없음, "
                             "재발 아님 (진단 시 IV기)). 치료 반응(PD 등)은 넣지 않는다",
        "recurrence.metastatic_sites": "재발·전이 부위 구절 (예: 간 전이, 뼈·간 전이). 국소 재발만 있고 "
                                       "원격 전이가 없다고 적혀 있으면 그 구절 (예: 원격 전이 없음)",
        "recurrence.surgery": "재발 병소 수술 (날짜와 수술 이름)",
        "recurrence.surgery_intent": "재발 병소 수술 목적 (완치, 고식)",
        "recurrence.later_distant": "국소 재발 치료 뒤 원격 전이가 생겼는지 적힌 구절 (예: 수술 후 원격 전이 소견 없음)",
        "molecular.germline.BRCA1": "생식세포 BRCA1 검사 결과 또는 미시행",
        "molecular.germline.BRCA2": "생식세포 BRCA2 검사 결과 또는 미시행",
        "molecular.germline.PALB2": "생식세포 PALB2 검사 결과 또는 미시행",
    },
    "radiology": {
        "imaging_findings": "판독 결론에서 전이를 말하는 구절 하나 (전이 부위와 확실성: 전이, 전이 의심, 전이 없음). "
                            "림프절 전이 의심도 포함. 유방 종괴 크기는 stage.clinical_size_mm으로",
        "stage.clinical_size_mm": "유방 종괴 크기가 든 구절 (예: 우측 유방 1.9 cm 종괴)",
    },
    "medication": {
        "treatment_history": "요법 한 줄: 약 이름부터 날짜·주기·반응·중단 사유까지 그 줄 전체. "
                             "줄 앞의 구분 칸(보조·선행·고식)이나 '- '는 빼고 그 뒤부터",
    },
    "molecular": {
        f"molecular.mutations.{g}": f"{g} 결과: 변이가 있으면 그 변이 줄 (유전자, c., p., VAF), "
                                    f"검출되지 않았으면 {g}가 든 '검출되지 않음' 목록 줄. 패널 포함 유전자 목록은 넣지 않는다"
        for g in ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")
    },
    # 분자병리 문서 중 머리글이 생식세포(유전성) 검사인 보고서 (field_list 참고, 2026-10-27 3단계)
    "germline": {
        f"molecular.germline.{g}": f"생식세포 {g} 결과: 변이가 있으면 그 변이 줄 (유전자, c., p., 판정), "
                                   f"없으면 {g}가 든 '검출되지 않음' 줄"
        for g in ("BRCA1", "BRCA2", "PALB2")
    },
}
# 분자병리 문서 머리글에 이 말이 있으면 생식세포 칸 목록을 준다. 체세포 칸만 주면 LLM이 생식세포 결과를
# 체세포 BRCA 칸에 넣었다 (시험 세트 VC-0115~0119, 2026-10-26)
GERMLINE_HEADER = re.compile(r"유전성|생식세포|germline|hereditary", re.I)


def field_list(doc: Document) -> str | None:
    """이 문서에 줄 칸 목록의 이름 (FIELDS 키). 칸 목록이 없는 문서 종류는 None."""
    if doc.doc_type == "molecular" and GERMLINE_HEADER.search(doc.text.split("\n", 1)[0]):
        return "germline"
    return doc.doc_type if doc.doc_type in FIELDS else None


SYSTEM = """너는 유방암 환자 차트에서 값이 적힌 구절을 찾는 도구다. 값을 계산하거나 해석하지 않는다.

규칙:
1. 칸 목록에 있는 칸마다, 그 값이 적힌 짧은 구절을 문서에서 글자 그대로 복사한다. 띄어쓰기·대소문자·괄호를 바꾸지 않고 요약하지 않는다.
2. 문서에 없는 칸은 내지 않는다. 짐작해서 만들지 않는다.
3. 같은 칸이 문서에 여러 번 나오면 (판독 요약과 본문 표 등) 값이 같든 다르든 모두 낸다.
4. specimen: 원발 유방 조직이면 "primary", 전이·재발 병소이면 "metastasis", 혈액(cfDNA)이면 "cfDNA", 검체와 상관없는 칸이면 null.
5. observed_date: 검체 채취일·수술일·검사 시행일 (YYYY-MM-DD). 보고일이 아니다. 알 수 없으면 null.
6. [이름1]처럼 대괄호로 가린 글자도 문서에 있는 그대로 옮긴다.
JSON만 답한다."""

# 시험 세트(tests/fixtures/virtual_charts) 밖의 예문 (설계 결정: 문서 종류마다 1개, 시험 오염 방지)
EXAMPLES = {
    "pathology": (
        "[병리결과보고서]\n환자명: [이름1]   등록번호: [등록번호1]   F/47\n보고일: 2020.6.10\n"
        "2020.6.3 좌측 유방 중심 생검. Invasive lobular carcinoma.\n"
        "ER positive (Allred 7, 4+3), PR negative (Allred 0), HER2 IHC 2+, Ki-67 20%.\n",
        [{"field": "patient.gender", "quote": "F/47", "specimen": None, "observed_date": None},
         {"field": "patient.age", "quote": "F/47", "specimen": None, "observed_date": None},
         {"field": "diagnosis.histology", "quote": "Invasive lobular carcinoma", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.er_percent", "quote": "ER positive (Allred 7, 4+3)", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.pr_percent", "quote": "PR negative (Allred 0)", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.her2_ihc", "quote": "HER2 IHC 2+", "specimen": "primary", "observed_date": "2020-06-03"},
         {"field": "proliferation.ki67_percent", "quote": "Ki-67 20%", "specimen": "primary",
          "observed_date": "2020-06-03"}],
    ),
    "progress_note": (
        "<외래 경과기록>   2019.3.2   종양내과\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n\n"
        "S) 폐경: 폐경 후 (55세 폐경)\n   과거력: 고혈압 (약 복용 중), 심질환 없음\n"
        "   심초음파 (2019.2.20): LVEF 58%\nO) ECOG PS 1\n"
        "A) Lt. breast IDC, 2017.5.10 core bx로 진단, 수술 후 보조요법\n"
        "   보조 letrozole 2017.6.20~ 복용 중 2019.1.15 간 전이 → letrozole 2019.1.20 중단\n"
        "P) 전이성 1차 치료 상의\n",
        [{"field": "patient.gender", "quote": "F/58", "specimen": None, "observed_date": None},
         {"field": "patient.age", "quote": "F/58", "specimen": None, "observed_date": None},
         {"field": "patient.menopausal_status", "quote": "폐경 후", "specimen": None, "observed_date": None},
         {"field": "patient.menopausal_basis", "quote": "55세 폐경", "specimen": None, "observed_date": None},
         {"field": "patient.comorbidities", "quote": "고혈압 (약 복용 중)", "specimen": None, "observed_date": None},
         {"field": "patient.cardiac_history", "quote": "심질환 없음", "specimen": None, "observed_date": None},
         {"field": "patient.lvef_percent", "quote": "LVEF 58%", "specimen": None, "observed_date": "2019-02-20"},
         {"field": "patient.ecog", "quote": "ECOG PS 1", "specimen": None, "observed_date": "2019-03-02"},
         {"field": "diagnosis.histology", "quote": "IDC", "specimen": None, "observed_date": None},
         {"field": "diagnosis.diagnosis_date", "quote": "2017.5.10 core bx로 진단", "specimen": None,
          "observed_date": None},
         {"field": "recurrence.recurrence_date", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.recurrence_day", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.metastasis_day", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.status", "quote": "간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.metastatic_sites", "quote": "간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.adjuvant_endocrine_end_date", "quote": "letrozole 2019.1.20 중단", "specimen": None,
          "observed_date": None}],
    ),
    "radiology": (
        "[영상의학 판독]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n"
        "검사: Chest-abdomen CT (contrast)   검사일: 2019.1.15\n\nFindings:\n"
        "  우측 유방 상외측에 불규칙한 종괴. 간 S4에 1.0 cm 저음영 결절.\n"
        "Conclusion:\n  1. 우측 유방 1.9 cm 불규칙 종괴, 유방암에 합당\n  2. 간 S4 1.0 cm 결절, 전이 의심\n",
        [{"field": "stage.clinical_size_mm", "quote": "우측 유방 1.9 cm 불규칙 종괴", "specimen": None,
          "observed_date": "2019-01-15"},
         {"field": "imaging_findings", "quote": "간 S4 1.0 cm 결절, 전이 의심", "specimen": None,
          "observed_date": "2019-01-15"}],
    ),
    "medication": (
        "[투약 기록]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n"
        "구분    요법                  시작         종료         주기         반응   중단 사유\n"
        "보조    letrozole 2.5mg qd   2017.6.20   2019.1.20   -   PD     간 전이\n"
        "고식    paclitaxel 80mg/m2   2019.2.1   2019.6.27   weekly #21   PR   완료\n",
        [{"field": "treatment_history", "quote": "letrozole 2.5mg qd   2017.6.20   2019.1.20   -   PD     간 전이",
          "specimen": None, "observed_date": None},
         {"field": "treatment_history", "quote": "paclitaxel 80mg/m2   2019.2.1   2019.6.27   weekly #21   PR   완료",
          "specimen": None, "observed_date": None}],
    ),
    "molecular": (
        "[NGS 보고서]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n보고일: 2019.2.10\n"
        "검체: 간 생검 조직 (2019.1.25)\n\n검출된 변이\n  PIK3CA   c.1633G>A (p.E545K)   VAF 12%\n\n"
        "검출되지 않음 (Not detected)\n  ESR1, AKT1, PTEN\n\n* 패널 포함 유전자: ESR1, PIK3CA, AKT1, PTEN, ERBB2\n",
        [{"field": "molecular.mutations.PIK3CA", "quote": "PIK3CA   c.1633G>A (p.E545K)   VAF 12%",
          "specimen": "metastasis", "observed_date": None}]
        + [{"field": f"molecular.mutations.{g}", "quote": "ESR1, AKT1, PTEN", "specimen": "metastasis",
            "observed_date": None} for g in ("ESR1", "AKT1", "PTEN")],
    ),
    "germline": (
        "[Hereditary cancer panel report]\n환자명: [이름1]   등록번호: [등록번호1]   F/39\n"
        "보고일: 2018.11.2\n검체: 말초혈액\n\nResults\n"
        "  BRCA1: No pathogenic variant identified\n"
        "  BRCA2   c.3847_3848delGT (p.V1283Kfs*2)   Pathogenic\n"
        "  PALB2: No pathogenic variant identified\n",
        [{"field": "molecular.germline.BRCA1", "quote": "BRCA1: No pathogenic variant identified", "specimen": None,
          "observed_date": None},
         {"field": "molecular.germline.BRCA2", "quote": "BRCA2   c.3847_3848delGT (p.V1283Kfs*2)   Pathogenic",
          "specimen": None, "observed_date": None},
         {"field": "molecular.germline.PALB2", "quote": "PALB2: No pathogenic variant identified", "specimen": None,
          "observed_date": None}],
    ),
}


NO_QUOTE = {"null", "none", "n/a", "-"}


def schema(doc_type: str) -> dict:
    """LLM 출력 스키마. 칸 이름은 이 칸 목록(FIELDS 키: 문서 종류 또는 germline) 안에서만."""
    return {"type": "object", "required": ["candidates"], "additionalProperties": False, "properties": {
        "candidates": {"type": "array", "items": {
            "type": "object", "required": ["field", "quote", "specimen", "observed_date"], "additionalProperties": False,
            "properties": {
                "field": {"enum": list(FIELDS[doc_type])},
                "quote": {"type": "string", "minLength": 1},
                "specimen": {"enum": ["primary", "metastasis", "cfDNA", None]},
                "observed_date": {"type": ["string", "null"]}}}}}}


def messages(doc: Document) -> list[dict]:
    kind = field_list(doc)
    fields = "\n".join(f"- {k}: {v}" for k, v in FIELDS[kind].items())
    ex_text, ex_out = EXAMPLES[kind]
    user = "칸 목록:\n{fields}\n\n문서:\n<<<\n{text}\n>>>"
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user.format(fields=fields, text=ex_text)},
            {"role": "assistant", "content": json.dumps({"candidates": ex_out}, ensure_ascii=False)},
            {"role": "user", "content": user.format(fields=fields, text=doc.text)}]


def _iso(date: str | None) -> str | None:
    """LLM이 2023.4.16처럼 써도 YYYY-MM-DD로. 읽을 수 없으면 None."""
    m = date and re.fullmatch(r"\s*(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\.?\s*", date)
    return m and f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def extract_doc(doc: Document, config: LLMConfig, complete: Callable = complete_json) -> list[dict]:
    """문서 하나의 후보 목록 (candidates.py 형식). 칸 목록이 없는 문서 종류는 빈 목록."""
    kind = field_list(doc)
    if kind is None:
        return []
    out = complete(messages(doc), schema(kind), config)
    # 빈 칸에 "null" 같은 글자를 구절로 쓴 것은 후보가 아니다 (인용 준수율에 넣지 않는다)
    return [{"doc_id": doc.doc_id, "field": c["field"], "quote": c["quote"], "specimen": c["specimen"],
             "observed_date": _iso(c["observed_date"])} for c in out["candidates"]
            if c["quote"].strip().lower() not in NO_QUOTE]


def make_extract(config: LLMConfig, complete: Callable = complete_json, doc_ids: set[str] | None = None):
    """pipeline.run에 넣는 extract 함수. doc_ids를 주면 그 문서만 보낸다."""
    def extract(docs: list[Document]) -> list[dict]:
        return [c for d in docs if doc_ids is None or d.doc_id in doc_ids for c in extract_doc(d, config, complete)]
    return extract


def main(argv=None) -> int:
    from src.input.script.evaluation import from_expected
    from src.input.script.virtual.virtual_chart import out_dir


    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="+", help="사례 (기본: 문서 보기는 VC-0103, --out은 --set)")
    ap.add_argument("--set", default="dev", choices=["dev", "pairs", "test", "holdout", "variants"],
                    help="--out의 사례 묶음: dev 10건 (기본), pairs 짝 19건, test 새 20건 (규칙 고정 뒤에만), "
                         "holdout 보류 18건 (성능 보고에만, 틀린 칸을 보고 규칙을 고치지 않는다)")
    ap.add_argument("--docs", nargs="*", help="문서 ID (없으면 칸 목록이 있는 문서 모두)")
    ap.add_argument("--model", help="llm/config.toml [extract]의 모델 대신")
    ap.add_argument("--host", help="Ollama 주소 대신 (예: SSH 터널 http://127.0.0.1:11435). 서버 주소를 바로 쓰지 말 것 (암호화 안 됨)")
    ap.add_argument("--out", type=Path, help="끝까지 돌려 <폴더>/<사례>/patient_state.json, issues.json, candidates.json 저장")
    ap.add_argument("--replay", type=Path, help="<폴더>/<사례>/candidates.json으로 규칙 단계만 다시 돌려 덮어쓴다")
    args = ap.parse_args(argv)
    if args.replay:
        for d in sorted(p for p in args.replay.iterdir() if (p / "candidates.json").exists()):
            ref = d.name
            chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
            want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
            cands = json.loads((d / "candidates.json").read_text(encoding="utf-8"))
            ps, issues = run(chart, lambda docs: cands, patient_ref=ref, created_at=want["created_at"])
            log = json.loads((d / "issues.json").read_text(encoding="utf-8"))
            (d / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "issues.json").write_text(json.dumps({**log, "issues": issues}, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
            print(f"{ref}: 후보 {len(cands)}개, 문제 {len(issues)}개")
        return 0
    override = {k: v for k, v in (("model", args.model), ("host", args.host)) if v}
    cfg = load_config("extract", **override)
    print(f"모델 {cfg.model} ({cfg.host})", flush=True)
    if args.out:
        from src.input.script.evaluation import case_set
        for ref in args.ids or case_set(args.set):
            chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
            want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
            log = {"candidates": 0, "errors": [], "doc_seconds": {}}

            def complete(msgs, sch, config, _log=log):
                t = time.perf_counter()
                try:
                    out = complete_json(msgs, sch, config)
                except (LLMOutputError, requests.RequestException) as e:     # 문서 하나가 실패해도 계속
                    _log["errors"].append(str(e)[:300])
                    out = {"candidates": []}
                _log["candidates"] += sum(c["quote"].strip().lower() not in NO_QUOTE for c in out["candidates"])
                _log["doc_seconds"][str(len(_log["doc_seconds"]) + 1)] = round(time.perf_counter() - t)
                return out

            t0 = time.perf_counter()
            cands: list[dict] = []
            llm_extract = make_extract(cfg, complete)

            def extract(docs, _cands=cands):
                _cands.extend(llm_extract(docs))
                return _cands

            ps, issues = run(chart, extract, patient_ref=ref, created_at=want["created_at"])
            d = args.out / ref
            d.mkdir(parents=True, exist_ok=True)
            (d / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "issues.json").write_text(json.dumps({**log, "model": cfg.model, "issues": issues,
                                                       "seconds": round(time.perf_counter() - t0)},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{ref}: {time.perf_counter() - t0:.0f}초, 후보 {log['candidates']}개, 문제 {len(issues)}개, "
                  f"LLM 실패 {len(log['errors'])}개", flush=True)
        return 0
    for ref in args.ids or ["VC-0103"]:
        chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
        want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        mapping = identifiers(chart)
        for doc in split(chart):
            kind = field_list(doc)
            if kind is None or (args.docs and doc.doc_id not in args.docs):
                continue
            t = time.perf_counter()
            got = extract_doc(replace(doc, text=mask(doc.text, mapping)), cfg)
            sec = time.perf_counter() - t
            gold = {(c["field"], c["quote"]) for c in from_expected(want)
                    if c["doc_id"] == doc.doc_id and c["field"] in FIELDS[kind]}
            print(f"\n== {ref} {doc.doc_id} ({doc.doc_type}) {sec:.0f}초, 후보 {len(got)}개, 정답 {len(gold)}개", flush=True)
            found = set()
            for c in got:
                src = locate(c["quote"], doc, mapping)
                key = (c["field"], src["quote"]) if src else None
                found.add(key)
                mark = "정답과 같음" if key in gold else "원문에 없음" if src is None else "정답과 다름"
                print(f"  [{mark}] {c['field']}: {c['quote']!r} specimen={c['specimen']} date={c['observed_date']}")
            for f, q in sorted(gold - found):
                print(f"  [놓침] {f}: {q!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
