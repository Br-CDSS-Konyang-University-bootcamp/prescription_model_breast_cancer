"""허가초과 항암요법 파일(xlsx) 읽기.

게시판 파일명 예: 사전신청요법_(용법용량 포함)및 불승인요법_261012.xlsx (예전 이름: 허가초과 항암요법_260827.xlsx)

시트별 쓰임 (§8):
  인정되고 있는 허가초과 항암요법  유방암 행 저장 -> '허가초과 인정' 매칭. 용법용량 열은 쓰지 않는다
  검토중인 허가초과 항암요법      유방암 행 저장 -> '진행중' 안내에만 쓴다 (판정에 쓰지 않음)
  허가초과 항암요법 변경대비표     저장하지 않고, 레지스트리 diff와 대조하는 검증에만 쓴다
  불승인 요법                     쓰지 않는다

유방암은 '암종' 열이 정확히 '유방암'인 행만 고른다. '유방'으로 찾으면
유방외파젯병(암종 = 기타암)이 섞인다.
"""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .booklet import sha256
from .dates import date_from_filename
from .registry import CriterionItem, Diff
from .validate import Report

BREAST = "유방암"
SHEET_APPROVED = "인정되고"
SHEET_REVIEWING = "검토중"
SHEET_CHANGES = "변경대비표"

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_T = f"{{{_NS['m']}}}t"


# ---------- xlsx 읽기 (openpyxl 없이 zip + xml) ----------

def read_xlsx(path: str | Path) -> dict[str, list[list[str]]]:
    """시트 이름 -> 행 목록. 셀 값은 모두 문자열, 빈 셀은 ''."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(_T)))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {}
        for sh in wb.find("m:sheets", _NS):
            t = target[sh.get(f"{{{_NS['r']}}}id")].lstrip("/")
            part = t if t.startswith("xl/") else "xl/" + t
            sheets[sh.get("name")] = _read_sheet(ET.fromstring(z.read(part)), shared)
    return sheets


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _read_sheet(root: ET.Element, shared: list[str]) -> list[list[str]]:
    rows = []
    for row in root.iter(f"{{{_NS['m']}}}row"):
        vals: dict[int, str] = {}
        for c in row.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if c.get("t") == "inlineStr":
                vals[_col(c.get("r"))] = "".join(t.text or "" for t in c.iter(_T))
            elif v is not None:
                vals[_col(c.get("r"))] = shared[int(v.text)] if c.get("t") == "s" else v.text
        rows.append([vals.get(i, "") for i in range(max(vals) + 1)] if vals else [])
    return rows


# ---------- 결과 형식 ----------

@dataclass
class Regimen:
    """인정 요법 한 줄. 용법용량은 넣지 않는다."""
    code: str          # 요법코드 '2532'
    cancer: str        # 암종
    subtype: str       # 세부암종
    regimen: str       # 항암화학요법
    target: str        # 투여대상
    line: str          # 투여단계 ('1차', '2차 이상', '-')
    setting: str       # 투여요법 (고식적요법, 수술후보조요법 ...)
    copay: str         # 급여상세사항 (본인부담률)

    @property
    def item_key(self) -> str:
        return f"offlabel|{self.code}"

    @property
    def male_only(self) -> bool:
        return "남성" in self.target

    def to_item(self) -> CriterionItem:
        text = " | ".join([self.regimen, self.target, self.line, self.setting, self.copay])
        return CriterionItem(self.item_key, text,
                             meta_json=json.dumps(asdict(self), ensure_ascii=False))


@dataclass
class Reviewing:
    """검토중인 요법 한 줄. '진행중' 태그에만 쓴다."""
    no: str
    cancer: str
    text: str


@dataclass
class ChangeRow:
    """변경대비표 한 줄."""
    no: str
    kind: str                  # 신설 / 변경 / 삭제
    applied_raw: str           # '2025.09.00' 처럼 일이 00인 표기가 있어 원문도 둔다
    applied: date | None
    before: dict[str, str] = field(default_factory=dict)
    after: dict[str, str] = field(default_factory=dict)

    @property
    def codes(self) -> set[str]:
        return {c for c in (self.before.get("요법코드", ""), self.after.get("요법코드", ""))
                if re.fullmatch(r"\d+", c.strip())}


@dataclass
class OffLabel:
    path: Path
    file_date: date            # 파일명 날짜
    base_date: date | None     # 시트 안의 기준일 셀
    file_hash: str
    approved: list[Regimen]    # 유방암만
    reviewing: list[Reviewing]
    changes: list[ChangeRow]   # 유방암만
    approved_total: int        # 전체 인정 요법 수 (구조 확인용)
    sheets: list[str]

    def items(self) -> list[CriterionItem]:
        return [r.to_item() for r in self.approved]


# ---------- 파싱 ----------

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _find_sheet(sheets: dict[str, list[list[str]]], word: str) -> list[list[str]] | None:
    for name, rows in sheets.items():
        if word in _norm(name):
            return rows
    return None


def _header_row(rows: list[list[str]], *names: str) -> int:
    for i, row in enumerate(rows[:10]):
        cells = {_norm(c) for c in row}
        if all(n in cells for n in names):
            return i
    raise ValueError(f"머리글을 찾지 못함: {names}")


def _excel_serial(rows: list[list[str]]) -> date | None:
    """시트 위쪽의 기준일 셀 (엑셀 날짜 숫자, 예: 46308 = 2026-10-13).

    261012 파일은 기준일 셀이 10-13이라 파일명 날짜와 하루 다르다.
    그래서 며칠 차이는 정상으로 보고, 7일 넘게 다를 때만 경고한다.
    """
    for row in rows[:3]:
        for c in row:
            if re.fullmatch(r"4\d{4}", c.strip()):
                return date(1899, 12, 30) + timedelta(days=int(c))
    return None


def _lenient_date(s: str) -> date | None:
    """'2024.8.22' -> 날짜, '2025.09.00' -> 2025-09-01 (일 미상은 1일로)."""
    m = re.search(r"(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})", s)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return date(y, mo, max(d, 1))


def parse_approved(rows: list[list[str]]) -> tuple[list[Regimen], int]:
    h = _header_row(rows, "요법코드", "암종")
    idx = {_norm(c): i for i, c in enumerate(rows[h]) if c}

    def get(row, name):
        i = idx.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    out, total = [], 0
    for row in rows[h + 1:]:
        if not get(row, "요법코드"):
            continue
        total += 1
        if _norm(get(row, "암종")) != BREAST:
            continue
        out.append(Regimen(code=get(row, "요법코드"), cancer=get(row, "암종"),
                           subtype=get(row, "세부암종"), regimen=get(row, "항암화학요법"),
                           target=get(row, "투여대상"), line=get(row, "투여단계"),
                           setting=get(row, "투여요법"), copay=get(row, "급여상세사항")))
    return out, total


def parse_reviewing(rows: list[list[str]]) -> list[Reviewing]:
    h = _header_row(rows, "연번", "암종")
    idx = {_norm(c): i for i, c in enumerate(rows[h]) if c}
    out = []
    for row in rows[h + 1:]:
        cells = row + [""] * (len(rows[h]) - len(row))
        if _norm(cells[idx["암종"]]) == BREAST:
            text = cells[idx.get("항암요법", idx["암종"] + 1)]
            out.append(Reviewing(cells[idx["연번"]].strip(), BREAST, text.strip()))
    return out


_SUB = ("요법코드", "항암화학요법", "투여대상", "투여단계", "용법용량")


def parse_changes(rows: list[list[str]], breast_codes: set[str]) -> list[ChangeRow]:
    """두 줄 머리글: (연번, 구분, 적용일자, 변경 전, 변경 후) / (요법코드, 항암화학요법, ...)."""
    h = _header_row(rows, "연번", "구분", "적용일자")
    top = [_norm(c) for c in rows[h]]
    sub = [_norm(c) for c in rows[h + 1]] if h + 1 < len(rows) else []
    i_no, i_kind, i_date = top.index("연번"), top.index("구분"), top.index("적용일자")
    starts = {"before": top.index("변경전"), "after": top.index("변경후")}
    cols = {}
    for side, s in starts.items():
        j = sub.index("요법코드", s)
        cols[side] = {name: j + k for k, name in enumerate(_SUB)}

    out = []
    for row in rows[h + 2:]:
        cells = row + [""] * (max(len(top), len(sub)) - len(row))
        if not cells[i_kind].strip():
            continue
        sides = {side: {name: cells[i].strip() for name, i in c.items()} for side, c in cols.items()}
        ch = ChangeRow(no=cells[i_no].strip(), kind=cells[i_kind].strip(),
                       applied_raw=cells[i_date].strip(), applied=_lenient_date(cells[i_date]),
                       before=sides["before"], after=sides["after"])
        targets = ch.before.get("투여대상", "") + ch.after.get("투여대상", "")
        if ch.codes & breast_codes or (BREAST in targets and "유방외" not in _norm(targets)):
            out.append(ch)
    return out


def load_offlabel(path: str | Path) -> OffLabel:
    path = Path(path)
    sheets = read_xlsx(path)
    approved_rows = _find_sheet(sheets, SHEET_APPROVED)
    if approved_rows is None:
        raise ValueError(f"'{SHEET_APPROVED}' 시트가 없음: {list(sheets)}")
    approved, total = parse_approved(approved_rows)
    reviewing_rows = _find_sheet(sheets, SHEET_REVIEWING)
    changes_rows = _find_sheet(sheets, SHEET_CHANGES)
    return OffLabel(
        path=path,
        file_date=date_from_filename(path.name),
        base_date=_excel_serial(approved_rows),
        file_hash=sha256(path),
        approved=approved,
        reviewing=parse_reviewing(reviewing_rows) if reviewing_rows else [],
        changes=parse_changes(changes_rows, {r.code for r in approved}) if changes_rows else [],
        approved_total=total,
        sheets=list(sheets),
    )


# ---------- 검증 ----------

# 2026-10-12 파일 기준 유방암 인정 요법 21건 (남성 2건 포함). 크게 줄면 구조가 바뀐 것으로 본다
MIN_BREAST = 15


def validate_offlabel(o: OffLabel, *, diff: Diff | None = None,
                      previous_file_date: date | None = None) -> Report:
    """오류가 있으면 반영하지 않고 이전 목록을 유지한다 (§8 처리 흐름 9).

    diff, previous_file_date를 주면 레지스트리 diff와 변경대비표를 대조한다.
    """
    r = Report()
    for word in (SHEET_APPROVED, SHEET_CHANGES):
        if not any(word in _norm(s) for s in o.sheets):
            r.error(f"'{word}' 시트가 없음 (시트: {', '.join(o.sheets)})")
    if not any(SHEET_REVIEWING in _norm(s) for s in o.sheets):
        r.warn("'검토중' 시트가 없음: 진행중 안내를 만들 수 없다")
    if len(o.approved) < MIN_BREAST:
        r.error(f"유방암 인정 요법이 {len(o.approved)}건뿐 (기대 {MIN_BREAST}건 이상)")
    codes = [x.code for x in o.approved]
    if len(codes) != len(set(codes)):
        r.error("요법코드 중복")
    for x in o.approved:
        if not x.regimen or not x.target:
            r.error(f"요법코드 {x.code}: 항암화학요법 또는 투여대상이 비어 있음")
    if o.base_date is None:
        r.warn("시트 기준일 셀을 찾지 못함")
    elif abs((o.base_date - o.file_date).days) > 7:
        r.warn(f"시트 기준일 {o.base_date}와 파일명 날짜 {o.file_date}가 다름")
    r.info.append(f"인정 요법 전체 {o.approved_total}건 중 유방암 {len(o.approved)}건 "
                  f"(남성 {sum(x.male_only for x in o.approved)}건), 검토중 {len(o.reviewing)}건")
    if diff is not None and previous_file_date is not None:
        _check_changes(o, diff, previous_file_date, r)
    return r


def _check_changes(o: OffLabel, diff: Diff, since: date, r: Report) -> None:
    """레지스트리 diff와 변경대비표의 적용일자 > since 행이 서로 맞는지."""
    recent = [c for c in o.changes if c.applied is None or c.applied > since]
    table_codes = set().union(*(c.codes for c in recent)) if recent else set()
    diff_codes = {k.split("|", 1)[1] for k in diff.added + diff.changed + diff.removed}
    for code in sorted(diff_codes - table_codes):
        r.warn(f"요법코드 {code}: 목록은 바뀌었는데 변경대비표에 {since} 이후 기록이 없음")
    for code in sorted(table_codes - diff_codes):
        r.warn(f"요법코드 {code}: 변경대비표에는 {since} 이후 변경이 있는데 목록 diff에 없음")
