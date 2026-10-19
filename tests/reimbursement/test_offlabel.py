import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from src.reimbursement.offlabel import load_offlabel, validate_offlabel
from src.reimbursement.registry import Diff, Registry

RAW = Path(__file__).resolve().parents[2] / "data/reimbursement/raw"


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets: dict[str, list[list]]):
    """테스트용 최소 xlsx (inlineStr 셀만)."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        entries, rels = [], []
        for n, (name, rows) in enumerate(sheets.items(), 1):
            entries.append(f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>')
            rels.append(f'<Relationship Id="rId{n}" Target="worksheets/sheet{n}.xml" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>')
            xml_rows = []
            for r, row in enumerate(rows, 1):
                cells = "".join(
                    f'<c r="{_col(c)}{r}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
                    for c, v in enumerate(row) if v != "")
                xml_rows.append(f'<row r="{r}">{cells}</row>')
            z.writestr(f"xl/worksheets/sheet{n}.xml",
                       f'<worksheet {ns}><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rns}><sheets>{"".join(entries)}</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'{"".join(rels)}</Relationships>')


HEAD = ["", "요법코드", "암종", "세부암종", "항암화학요법", "투여대상", "투여단계", "투여요법",
        "급여상세사항", "참고사항 (용법용량)", "기타사항"]


def _approved(n_breast=16):
    rows = [["", "□ 인정된 요법", "", "", "", "", "", "46308"], HEAD,
            ["", "1004", "난소암", "-", "irinotecan + mitomycin C", "재발성 난소암", "1차 이상",
             "고식적요법", "약값 일부 본인부담(5/100)", "용법"],
            ["", "2095", "기타암", "유방외파젯병", "docetaxel", "전이성 Extramammary paget's disease",
             "1차 이상", "고식적요법", "약값 전액 본인부담(100/100)", "용법"]]
    for i in range(n_breast):
        rows.append(["", str(2500 + i), "유방암", "유방암", f"drug{i}", f"HER2 음성 전이성 유방암 {i}",
                     "2차 이상", "고식적요법", "약값 전액 본인부담(100/100)", "용법 쓰지 않음"])
    rows.append(["", "6020", "유방암", "-", "letrozole + goserelin", "전이성 남성 유방암", "1차 이상",
                 "고식적요법", "약값 전액 본인부담(100/100)", "용법"])
    return rows


def _changes():
    return [["", "46308"], ["", "허가초과 항암화학요법 변경대비표(2024.8~)"],
            ["", "연번", "구분", "적용일자", "변경 전", "", "", "", "", "변경 후"],
            ["", "", "", "", "요법코드", "항암화학요법", "투여대상", "투여단계", "용법용량",
             "요법코드", "항암화학요법", "투여대상", "투여단계", "용법용량"],
            ["", "1", "삭제", "2024.8.22", "4055", "pembrolizumab", "자궁내막암", "1차", "x", "(삭제)"],
            ["", "2", "변경", "2026.10.00", "2501", "drug1", "이전 대상", "2차 이상", "x",
             "2501", "drug1", "HER2 음성 전이성 유방암 1", "2차 이상", "x"],
            ["", "3", "삭제", "2026.10.5", "2999", "olddrug", "전이성 유방암", "1차", "x", "(삭제)"]]


SHEETS = {
    "안내": [[" - 안내입니다."]],
    "검토중인 허가초과 항암요법": [["□ 검토 중"], ["46308"], ["연번", "암종", "항암요법"],
                                 ["1", "비소세포폐암", "폐암 요법"], ["8", "유방암", "non-pCR HER2 양성에 T-DXd"]],
    "인정되고 있는 허가초과 항암요법(용법용량포함)": _approved(),
    "불승인 요법": [["46308"], ["연번", "암 종", "항암화학요법", "불인정 사유"],
                  ["14", "폐경전 호르몬 수용체 양성인 유방암", "toremifene", "의학적 타당성"]],
    "허가초과 항암요법 변경대비표": _changes(),
}


@pytest.fixture
def xlsx(tmp_path):
    p = tmp_path / "사전신청요법_(용법용량 포함)및 불승인요법_261012.xlsx"
    write_xlsx(p, SHEETS)
    return p


def test_load_filters_breast_by_cancer_column(xlsx):
    o = load_offlabel(xlsx)
    assert o.file_date == date(2026, 10, 12)
    assert o.base_date == date(2026, 10, 13)          # 엑셀 날짜 숫자 46308 (실제 파일도 하루 차이)
    assert o.approved_total == 19
    codes = [r.code for r in o.approved]
    assert len(codes) == 17 and "2095" not in codes   # 유방외파젯병(기타암)은 빠진다
    male = [r for r in o.approved if r.male_only]
    assert [r.code for r in male] == ["6020"]


def test_dosage_not_stored(xlsx):
    item = load_offlabel(xlsx).approved[0].to_item()
    assert item.item_key == "offlabel|2500"
    assert "용법" not in item.text and "용법" not in item.meta_json


def test_reviewing_and_changes(xlsx):
    o = load_offlabel(xlsx)
    assert [(r.no, r.text) for r in o.reviewing] == [("8", "non-pCR HER2 양성에 T-DXd")]
    # 자궁내막암 삭제(4055)는 빠지고, 코드가 유방암인 행과 투여대상에 '유방암'이 있는 삭제 행이 남는다
    assert [c.no for c in o.changes] == ["2", "3"]
    assert o.changes[0].applied == date(2026, 10, 1)  # '2026.10.00' -> 1일
    assert o.changes[0].applied_raw == "2026.10.00"


def test_validate_ok(xlsx):
    r = validate_offlabel(load_offlabel(xlsx))
    assert r.ok, r.render()


def test_validate_too_few_breast(tmp_path):
    p = tmp_path / "허가초과 항암요법_261012.xlsx"
    write_xlsx(p, {**SHEETS, "인정되고 있는 허가초과 항암요법(용법용량포함)": _approved(n_breast=3)})
    assert not validate_offlabel(load_offlabel(p)).ok


def test_validate_missing_sheet(tmp_path):
    p = tmp_path / "허가초과 항암요법_261012.xlsx"
    write_xlsx(p, {k: v for k, v in SHEETS.items() if "변경대비표" not in k})
    r = validate_offlabel(load_offlabel(p))
    assert any("변경대비표" in e for e in r.errors)


def test_change_table_cross_check(xlsx):
    o = load_offlabel(xlsx)
    since = date(2026, 9, 1)
    # 대비표의 2501 변경, 2999 삭제와 맞는 diff -> 경고 없음
    ok = validate_offlabel(o, diff=Diff(changed=["offlabel|2501"], removed=["offlabel|2999"]),
                           previous_file_date=since)
    assert ok.warnings == []
    # 대비표에 없는 변경(2503)과 diff에 빠진 삭제(2999) -> 경고 2건
    bad = validate_offlabel(o, diff=Diff(changed=["offlabel|2501", "offlabel|2503"]),
                            previous_file_date=since)
    assert len(bad.warnings) == 2 and bad.ok


def test_registry_offlabel_does_not_remove_booklet_items(xlsx, tmp_path):
    from src.reimbursement.registry import CriterionItem

    reg = Registry(tmp_path / "r.db")
    d = date(2026, 10, 1)
    bk = reg.add_document("booklet", file_hash="b1", effective_date=d)
    reg.apply_booklet(bk, d, [CriterionItem("breast|x", "책자 항목")])
    o = load_offlabel(xlsx)
    ol = reg.add_document("offlabel", file_hash=o.file_hash, effective_date=o.file_date)
    diff = reg.apply_booklet(ol, o.file_date, o.items())
    assert diff.removed == [] and len(diff.added) == 17
    keys = {r["item_key"] for r in reg.active_on(date(2026, 10, 13))}
    assert "breast|x" in keys and "offlabel|6020" in keys
    reg.close()


def _real_files():
    return sorted(RAW.glob("*_[0-9][0-9][0-9][0-9][0-9][0-9].xlsx")) if RAW.exists() else []


@pytest.mark.skipif(not _real_files(), reason="허가초과 xlsx 없음 (data/reimbursement/raw/)")
def test_real_offlabel_file():
    o = load_offlabel(_real_files()[-1])
    r = validate_offlabel(o)
    assert r.ok, r.render()
    assert all(x.cancer == "유방암" for x in o.approved)
