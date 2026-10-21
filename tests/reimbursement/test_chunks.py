"""급여 청크. 책자 표를 텍스트로 읽을 때 생기는 문제(쪽 경계, 병합 셀, 몰려 나온 소단원)를 짧은 가짜 본문으로 시험한다."""
import re
from datetime import date
from pathlib import Path

import pytest

from src.reimbursement.booklet import Section
from src.reimbursement.chunks import (
    biomarker_tags_from, booklet_chunks, check_chunks, clean_regimen, combo_filters, copay_text,
    footnote_marks, parse_regimen, split_notes, extract_drugs, lines_from,
    offlabel_chunks, parse_breast_table, parse_combination, split_row, subtypes_from,
)
from src.reimbursement.offlabel import load_offlabel
from test_offlabel import SHEETS, write_xlsx     # 같은 폴더의 테스트용 xlsx 도우미

HEADER = "연번\n항암요법\n투여대상"

# 쪽 1: 원칙, 1.가 표 (연번 2는 병합 셀), 연번 3은 다음 쪽으로 이어짐
P1 = f"""9
유방암(Breast Cancer)
[유방암 항암요법 투여 원칙]
- 'HER2 양성(과발현)'은 IHC 3+ 또는 ISH 양성인 경우를 의미함
1. 선행화학요법(neoadjuvant)
가. HER2 양성 유방암의 선행화학요법
{HEADER}
1
docetaxel + trastuzumab
국소진행성 HER2 양성 유방암
(제2021-150호: 2021.6.1.)
2
AC(doxorubicin + cyclophosphamide) →
trastuzumab
(제2013-187호: 2013.12.1, 개정 제2024-188호, 2024.8.1)
3
pertuzumab + trastuzumab + docetaxel
(제2017-132호: 2017.6.1, 개정 제2019-158호: 2019.5.20,,"""

# 쪽 2: 주석, 1.나 표, 반복 머리글 뒤에 1.가 연번 3의 남은 글과 연번 4
P2 = f"""주1. 피하투여 제형도 인정함
나. HER2 음성 유방암의 선행화학요법
{HEADER}
1
paclitaxel + epirubicin
국소진행성 유방암
(제2006-3호: 2006.1.9.)
{HEADER}
개정 제2024-264호, 2024.12.1.)
4
trastuzumab emtansine
선행요법 후 잔존암이 있는 HER2 양성 유방암
(제2024-85호: 2024.4.1.)"""

# 쪽 3: 소단원 제목 두 개가 몰려 나오고 표 두 개가 뒤따름. 두 번째 표 앞에 앞 행의 남은 글
P3 = f"""3. 고식적 내분비요법(palliative endocrine therapy)
- 호르몬 수용체 양성인 유방암을 대상으로 함
나. 투여단계: 1차 이상
다. 투여단계: 2차 이상
{HEADER}
1
anastrozole
호르몬 수용체 양성인 폐경 후 전이성 유방암
(제2007-7호: 2007.11.20.)
2
letrozole
다음 조건을 만족하는
{HEADER}
(제2009-3호: 2009.7.1.)
경우
{HEADER}
1
exemestane
호르몬 수용체 양성인 폐경 후 전이성 유방암
(제2009-6호: 2009.10.1.)"""


class FakeBooklet:
    """유방암 섹션(필수)과 병용요법 섹션(선택)만 있는 가짜 책자."""
    file_date = date(2026, 10, 1)
    doc_no = "2026-210"

    def __init__(self, pages, combo_pages=None):
        self.pages = list(pages) + list(combo_pages or [])
        self._text = {"cancer:유방암": "\f".join(pages)}
        self.sections = {"cancer:유방암": Section("cancer:유방암", "9 유방암", 1, len(pages))}
        if combo_pages:
            n = len(pages)
            self._text["combination"] = "\f".join(combo_pages)
            self.sections["combination"] = Section("combination", "combination", n + 1, n + len(combo_pages))

    def section(self, key):
        return self.sections[key if key in self.sections else f"cancer:{key}"]

    def section_text(self, key):
        return self._text[self.section(key).key]

    def printed_page(self, pdf_page):
        return pdf_page + 47


@pytest.fixture
def table():
    return parse_breast_table(FakeBooklet([P1, P2, P3]))


def _rows(table, path_end):
    sub = next(s for s in table.subsections if s.path.endswith(path_end))
    return {r.no: r.text for r in sub.rows}


def test_principles(table):
    assert table.principles[0].startswith("9")
    assert any("HER2 양성(과발현)" in ln for ln in table.principles)


def test_page_break_continuation_goes_to_right_table(table):
    a = _rows(table, "HER2 양성 유방암의 선행화학요법")
    assert sorted(a) == [1, 2, 3, 4]
    assert "제2024-264호" in a[3]                  # 반복 머리글 뒤 조각은 1.가 연번 3에
    assert sorted(_rows(table, "HER2 음성 유방암의 선행화학요법")) == [1]
    assert table.warnings == []


def test_bunched_headings_get_tables_in_order(table):
    b = _rows(table, "1차 이상")
    c = _rows(table, "2차 이상")
    assert [b[1].split("\n")[0], c[1].split("\n")[0]] == ["anastrozole", "exemestane"]
    assert "경우" in b[2]                          # 새 표 앞 조각은 끝나지 않은 앞 행에


def test_footnote_goes_to_subsection_notes(table):
    a = next(s for s in table.subsections if s.path.endswith("HER2 양성 유방암의 선행화학요법"))
    assert any(n.startswith("주1.") for n in a.notes)


def test_split_row_and_inherited_target():
    reg, target, tags = split_row("letrozole\n다음 조건을 만족하는\n(제2009-3호: 2009.7.1.)\n경우")
    assert reg == "letrozole"
    assert target == "다음 조건을 만족하는\n경우"     # 표시 뒤로 넘어온 투여대상 조각
    assert tags == "(제2009-3호: 2009.7.1.)"
    reg, target, _ = split_row("AC(doxorubicin + cyclophosphamide) →\ntrastuzumab\n(제2013-187호: 2013.12.1)")
    assert target == ""


def test_booklet_chunks():
    bc = booklet_chunks(FakeBooklet([P1, P2, P3]))
    by_id = {c["chunk_id"]: c for c in bc.chunks}
    # chunk_id는 설계 §2.5 형식: bc-{단계}-{소단원}-r{연번}
    r2 = by_id["hira-booklet-20261001-bc-neo-her2pos-r02"]
    assert "(위 연번과 같음) 국소진행성 HER2 양성 유방암" in r2["text"]
    assert r2["parent_id"] == "hira-booklet-20261001-bc-neo-her2pos"
    assert by_id[r2["parent_id"]]["parent_id"] == "hira-booklet-20261001-bc-neo"
    re_ = r2["reimbursement"]
    # 쉼표 표기 '개정 제2024-188호, 2024.8.1'도 최신 공고로 읽는다
    assert (re_["notice_no"], re_["effective_from"]) == ("제2024-188호", "2024-08-01")
    assert re_["history"][-1] == {"notice_no": "제2024-188호", "effective_from": "2024-08-01"}
    assert (re_["stage"], re_["her2_section"], re_["line_rule"]) == ("neoadjuvant", "positive", None)
    assert re_["conditions_inherited_from"] == "r01"                    # 병합 셀 물려받기 (§2.2)
    assert re_["conditions"] == {"line_rule": {"stage": "neoadjuvant", "line": None}}
    # 판정용 정규화 본문은 청크 최상위 칸 (지침 청크와 같이 씀), reimbursement 안에는 없다
    assert "국소진행성" in r2["text_normalized"] and "text_normalized" not in re_
    assert r2["line"] == ["neoadjuvant"] and r2["subtype"] == ["HR+/HER2+", "HR-/HER2+"]
    r = by_id["hira-booklet-20261001-bc-pal-endo-2lplus-r01"]
    assert r["line"] == ["2L", ">=3L"] and r["reimbursement"]["line_rule"] == "2차 이상"
    assert r["subtype"] == ["HR+/HER2-", "HR+/HER2+"]
    assert by_id["hira-booklet-20261001-bc-neo-her2pos-r04"]["drugs"] == ["trastuzumab emtansine"]
    assert by_id["hira-booklet-20261001-bc-neo-her2pos-r01"]["page_start"] == 48
    assert bc.contexts["hira-booklet-20261001-bc-neo-her2pos-r01"].startswith("[9. 유방암 > 1.")
    assert check_chunks(bc.chunks) == []
    assert len({i.item_key for i in bc.items}) == len(bc.items)


def test_extract_drugs():
    assert extract_drugs("Dose dense AC(+ filgrastim) → paclitaxel(+ filgrastim)") == \
        ["doxorubicin", "cyclophosphamide", "filgrastim", "paclitaxel"]
    assert extract_drugs("anastrozole + LHRH agonist주2") == ["goserelin", "leuprolide", "anastrozole"]
    assert extract_drugs("토레미펜 후 레트로졸 연장요법") == ["toremifene", "letrozole"]
    assert extract_drugs("liposomal doxorubicin(50/100)") == ["liposomal doxorubicin"]   # 공용 사전 표기
    assert extract_drugs("albumin-bound paclitaxel") == ["nab-paclitaxel"]     # 공용 사전 표기
    assert extract_drugs("megestrol acetate") == ["megestrol"]
    assert extract_drugs("pertuzumab + trastuzumab + docetaxel + carboplatin (TCHP)") == \
        ["docetaxel", "carboplatin", "trastuzumab", "pertuzumab"]


@pytest.mark.parametrize("text, expected", [
    ("HER2 양성 유방암", ["HR+/HER2+", "HR-/HER2+"]),
    ("호르몬 수용체 양성 및 HER2 음성인 전이성 유방암", ["HR+/HER2-"]),
    ("삼중음성 유방암", ["TNBC"]),
    ("가. 림프절 양성 유방암\n나. HER2 음성이며 림프절 음성", ["any"]),
    ("전이성 유방암", ["any"]),
])
def test_subtypes(text, expected):
    assert subtypes_from(text) == expected


def test_lines_from():
    assert lines_from("투여단계: 1차(first line)") == ["1L"]
    assert lines_from("투여단계: 2차 이상") == ["2L", ">=3L"]


def test_offlabel_chunks(tmp_path):
    p = tmp_path / "사전신청요법_(용법용량 포함)및 불승인요법_261012.xlsx"
    write_xlsx(p, SHEETS)
    chunks = offlabel_chunks(load_offlabel(p))
    assert check_chunks(chunks) == []
    base = [c for c in chunks if c["reimbursement"]["source_type"] == "baseline"]
    prev = [c for c in chunks if c["reimbursement"]["source_type"] == "preview"]
    assert len(base) == 17 and len(prev) == 1
    male = next(c for c in base if c["chunk_id"].endswith("-6020"))
    item = male["reimbursement"]["conditions"]["all_of"][0]
    assert (item["field"], item["op"], item["value"]) == ("sex", "eq", "MALE") and "남성" in item["text"]
    assert male["reimbursement"]["copay"] == "100/100"
    assert "용법" not in base[0]["text"]


def test_check_chunks_reports_schema_errors():
    bad = booklet_chunks(FakeBooklet([P1])).chunks[:1]
    bad[0]["line"] = ["5L"]
    bad[0]["extra"] = 1
    errs = check_chunks(bad + bad)
    assert any("중복" in e for e in errs)
    assert any("5L" in e for e in errs)
    assert any("extra" in e for e in errs)


COMBO_HEAD = "연번\n주요\n암종\n항암제 병용요법\n허가사항\n급여 요법\n급여기준\n비고"
COMBO_P1 = f"""40
기타 항암제 병용요법 (기존 항암요법 본인일부부담)
∙ 기존 항암요법에 타 항암제를 병용 시 기존 본인부담률을 적용함
{COMBO_HEAD}
1
비소
세포
폐암
lazertinib +
amivantamab
(1차,
고식적요법)
2
유방암
[선행화학요법]
paclitaxel +
pembroiizumab
→[수술후보조요법]
pembrolizumab
삼중음성 유방암
(선행화학요법)
(제2025-133호:
2025.6.5.)
3
fulvestrant +
capivasertib
(비급여)
호르몬 수용체 양성 및 HER2
음성인 전이성 유방암
(1차 이상,
고식적
내분비요법)"""
COMBO_P2 = f"""{COMBO_HEAD}
(제2025-133호:
2025.6.5.)
또는 이후 진행된 경우
4
난소암
olaparib
유지요법"""


def test_parse_combination_keeps_only_breast_group():
    b = FakeBooklet([P1], [COMBO_P1, COMBO_P2])
    combo = parse_combination(b)
    assert [(r.no, r.cancer) for r in combo.rows] == [(1, "비소세포폐암"), (2, "유방암"), (3, "유방암"), (4, "난소암")]
    assert [r.no for r in combo.breast] == [2, 3]
    assert combo.breast[0].starts_group and not combo.breast[1].starts_group
    assert "또는 이후 진행된 경우" in combo.breast[1].text      # 다음 쪽으로 이어진 글
    assert any("본인부담률" in ln for ln in combo.intro)
    assert combo.warnings == []


def test_combination_chunks():
    bc = booklet_chunks(FakeBooklet([P1], [COMBO_P1, COMBO_P2]))
    by_id = {c["chunk_id"]: c for c in bc.chunks}
    r2, r3 = by_id["hira-booklet-20261001-combo-r02"], by_id["hira-booklet-20261001-combo-r03"]
    assert r2["line"] == ["neoadjuvant", "adjuvant"] and r2["subtype"] == ["TNBC"]
    assert "pembrolizumab" in r2["drugs"]                       # 원문 오타 pembroiizumab도 읽는다
    assert bc.drug_scans[r2["chunk_id"]].corrected == [("pembroiizumab", "pembrolizumab")]
    # 고식적 요법은 전이성 + 국소진행성(수술 불가)을 함께 잡는다 (field_values.csv L2)
    assert r3["line"] == ["1L", "2L", ">=3L"] and r3["setting"] == ["locally_advanced", "metastatic"]
    assert r3["subtype"] == ["HR+/HER2-"] and r3["drugs"] == ["fulvestrant", "capivasertib"]
    assert r3["parent_id"] == "hira-booklet-20261001-combo"
    assert "hira-booklet-20261001-combo-r04" not in by_id      # 난소암 행은 넣지 않는다
    assert check_chunks(bc.chunks) == []


def test_combo_filters():
    assert combo_filters("(2차 이상,\n고식적\n항암화학요법)") == (["locally_advanced", "metastatic"], ["2L", ">=3L"])
    # 비고의 '선행화학요법 또는 수술후보조요법이 사용된 경우'는 표시가 아니다
    assert combo_filters("※ 선행화학요법 또는 수술후보조요법이 사용된 경우\n(2차 이상, 고식적 항암화학요법)")[1] \
        == ["2L", ">=3L"]


@pytest.mark.parametrize("text, tags", [
    ("PIK3CA/AKT1/PTEN 변이가 있는 국소 진행성 또는 전이성 유방암", ["PIK3CA-mut", "AKT1-mut", "PTEN-loss"]),
    ("치료경험이 있는 gBRCA 변이 HER2-음성 고위험 조기 유방암", ["gBRCA"]),
    ("Somatic BRCA1/2 pathogenic/likely pathogenic variant 확인된 HER2 음성 전이성", ["sBRCA"]),
    ("Stage Ⅱ~Ⅲ BRCA 변이 또는 삼중음성 유방암", ["gBRCA"]),
    ("PD-L1 발현 양성(CPS≥10)이며 삼중음성 유방암", ["PD-L1-CPS10"]),   # B의 태그
    ("HER2 양성 유방암", []),
    # 약 계열 이름은 검사 결과가 아니다 (허가초과 4060: 'PD-L1 inhibitor 치료를 받은 환자 제외')
    ("이전에 eribulin 또는 PD-L1 inhibitor 치료를 받은 환자 제외", []),
    ("HER2 초저발현 또는 저발현 전이성 유방암", ["HER2-ultralow"]),
    ("HER2-low 전이성 유방암", ["HER2-low"]),
    ("ER 저발현 유방암", ["ER-low"]),
    ("Ki-67 ≥20%인 고위험 조기 유방암", ["Ki-67-high"]),         # B의 rag_tags 철자
])
def test_biomarker_tags(text, tags):
    """§3.5 어휘. 본문에 마커가 적혀 있을 때만 붙인다."""
    assert biomarker_tags_from(text) == tags


@pytest.mark.parametrize("raw, clean", [
    ("anastrozole + LHRH agonist주2", "anastrozole + LHRH agonist"),
    ("pertuzumab + trastuzumab(IV, SC) 주1+ docetaxel", "pertuzumab + trastuzumab(IV, SC) + docetaxel"),
    ("pembrolizumab주2 + paclitaxel", "pembrolizumab + paclitaxel"),
    ("liposomal doxorubicin(50/100)", "liposomal doxorubicin(50/100)"),
    ("paclitaxel 3주 간격", "paclitaxel 3주 간격"),               # 투여 간격은 각주가 아님
])
def test_clean_regimen(raw, clean):
    assert clean_regimen(raw) == clean


def test_parse_regimen():
    """설계 §8.4: 순차(→), 선택(±), 제형 괄호, 본인부담 괄호."""
    p = parse_regimen("AC (doxorubicin + cyclophosphamide) → trastuzumab(IV, SC) + paclitaxel ± pertuzumab(100/100)주1")
    assert p["sequence"] == [["doxorubicin", "cyclophosphamide"], ["trastuzumab", "paclitaxel", "pertuzumab"]]
    assert p["optional_drugs"] == ["pertuzumab"]
    assert p["routes"] == {"trastuzumab": ["IV", "SC"]}
    assert p["copay_by_drug"] == {"pertuzumab": "100/100"}
    # copay는 요법 전체에 하나일 때만 (pertuzumab에만 붙은 값은 None, 약제별 값은 copay_by_drug)
    assert copay_text(p, ["doxorubicin", "cyclophosphamide", "trastuzumab", "paclitaxel", "pertuzumab"]) is None
    p = parse_regimen("liposomal doxorubicin(50/100)")
    assert p["copay_by_drug"] == {"liposomal doxorubicin": "50/100"} and p["sequence"] == []
    assert copay_text(p, ["liposomal doxorubicin"]) == "50/100"


def test_split_notes_and_marks():
    n = split_notes(["- 머리 규칙", "연번 20∼24 trastuzumab 관련:", "(1) 3주 요법", "주1. 고정용량 복합제",
                     "• [pertuzumab + trastuzumab] SC (100/100)", "주2. abemaciclib 병용"])
    assert n.head == ["- 머리 규칙"]
    assert n.ranges == [(20, 24, ["연번 20∼24 trastuzumab 관련:", "(1) 3주 요법"])]
    assert list(n.footnotes) == ["1", "2"] and len(n.footnotes["1"]) == 2
    assert footnote_marks("anastrozole주2", "PD-L1 발현 양성(CPS≥10)주3인", "4주 간격의 goserelin") == ["2", "3"]


def test_real_booklet_chunks(booklet):
    bc = booklet_chunks(booklet)
    assert check_chunks(bc.chunks) == []
    rows = [c for c in bc.chunks if c["chunk_kind"] == "reimbursement_condition"]
    assert len(rows) >= 110
    assert all(c["drugs"] for c in rows)
    assert bc.warnings == []
    assert [r.no for r in bc.combo.breast] == list(range(20, 31))
    by_id = {c["chunk_id"]: c for c in bc.chunks}
    assert by_id["hira-booklet-20261001-combo-r21"]["biomarker_tags"] == ["PIK3CA-mut", "AKT1-mut", "PTEN-loss"]
    assert "gBRCA" in by_id["hira-booklet-20261001-combo-r30"]["biomarker_tags"]       # olaparib 보조요법
    general = [c for c in bc.chunks if "-general-" in c["chunk_id"]]
    assert [c["section"].split(" > ")[1] for c in general] == \
        ["1. 급여 범위 및 비용 부담", "2. 항암요법 적용기준", "※ 참고사항(용어 정의)"]
    # 행정 절차([별표] 제1조~)와 첨부 서식은 뺀다. 본문의 '([별표] 참조)'는 남는다
    assert all("제1조(목적)" not in c["text"] and "신청서식" not in c["text"] for c in general)
    assert general[0]["reimbursement"]["notice_no"] == "제2026-50호"
    # 주N 각주는 표시가 붙은 행에만 (§2.3): 연번 22 pertuzumab주1, 연번 20 trastuzumab 단독은 주1 없음
    adj22, adj20 = by_id["hira-booklet-20261001-bc-adj-r22"], by_id["hira-booklet-20261001-bc-adj-r20"]
    assert "주1. ‘pertuzumab + trastuzumab’" in adj22["text"] and "주1." not in adj20["text"]
    assert "연번 20∼24 trastuzumab 수술후보조요법 관련" in adj20["text"]          # 연번 범위 규칙
    fdc = adj22["reimbursement"]["regimen_parsed"]["fixed_dose_combination"]
    assert fdc == [{"drugs": ["pertuzumab", "trastuzumab"], "route": "SC", "copay": "100/100"}]
    # 40장 병용요법: 추가 약제(비급여) + 기존 급여 요법 (§1.4, §1.5)
    combo = {int(c["chunk_id"][-2:]): c["reimbursement"]["combination"] for c in bc.chunks
             if "-combo-r" in c["chunk_id"]}
    assert {n: c["added_drug"] for n, c in combo.items()} == {
        20: ["pembrolizumab"], 21: ["capivasertib"], 22: ["alpelisib"], 23: ["pembrolizumab"],
        24: ["pembrolizumab"], 25: ["ribociclib"], 26: ["ribociclib"], 27: ["ribociclib"], 28: ["ribociclib"],
        29: ["inavolisib"], 30: ["olaparib"]}
    assert combo[21]["added_drug_coverage"] == "비급여" and combo[21]["base_regimen"] == ["fulvestrant"]
    assert combo[29]["base_regimen"] == ["palbociclib + fulvestrant"]
    stages = {int(c["chunk_id"][-2:]): c["reimbursement"]["conditions"]["line_rule"]["stage"]
              for c in bc.chunks if "-combo-r" in c["chunk_id"]}
    assert stages[29] == "palliative_endocrine" and stages[27] == "adjuvant" and stages[20] == "neoadjuvant"
    # Ⅳ 기타 약제 (§10.2): 유방암 줄만, 다른 암종 줄은 없음
    supp = {c["chunk_id"].split("-supp-")[1]: c for c in bc.chunks if "-supp-" in c["chunk_id"]}
    assert set(supp) >= {"gcsf-a", "gcsf-b1", "gcsf-b2", "zoledronic-a", "zoledronic-b", "denosumab-1",
                         "dexrazoxane-1", "dexrazoxane-2", "dexrazoxane-3"}
    assert "thiosulfate-1" in supp and supp["thiosulfate-1"]["drugs"] == ["sodium thiosulfate"]   # 설계 §10.2 Ⅳ 1~5
    b1 = supp["gcsf-b1"]
    assert "○ 유방암" in b1["text"] and "요로상피암" not in b1["text"] and "골암" not in b1["text"]
    assert [r["regimen"].split("(")[0] for r in b1["reimbursement"]["regimen_list"]][:2] == \
        ["adjuvant TAC", "neoadjuvant DA"]
    # G-CSF 요법 목록은 순차 여부로 TAC와 AC → docetaxel(약제 구성 같음)을 구분한다
    b2_seq = [bool(r["sequence"]) for r in supp["gcsf-b2"]["reimbursement"]["regimen_list"]]
    assert b1["reimbursement"]["regimen_list"][0]["sequence"] == [] and b2_seq[1] is True
    # 수술후보조 주2: abemaciclib 병용 시 abemaciclib 100/100 (설계 §1.5) -> 연번 1~9에 병용 정보
    for n in range(1, 10):
        row = by_id[f"hira-booklet-20261001-bc-adj-r{n:02d}"]
        assert row["reimbursement"]["combination"]["added_drug"] == ["abemaciclib"]
        assert row["reimbursement"]["combination"]["added_drug_coverage"] == "100/100" and "abemaciclib" in row["drugs"]
    assert "combination" not in by_id["hira-booklet-20261001-bc-adj-r10"]["reimbursement"]
    zb = supp["zoledronic-b"]["text"]
    assert "○ 유방암" in zb and "○ 전립선암" not in zb and "○ 다발골수종" not in zb   # 암종별 적용기준은 유방암만
    assert "Ⅳ\n기" not in zb                                                       # 세로 사이드바 제거
    assert supp["denosumab-1"]["setting"] == ["metastatic"] and supp["denosumab-1"]["drugs"] == ["denosumab"]
    assert all(c["reimbursement"]["stage"] == "supportive" for c in supp.values())
    regimens = [r for c in bc.chunks for r in c["reimbursement"].get("regimen", [])]
    assert not [r for r in regimens if re.search(r"주\d", r)]                       # 각주 표시가 남지 않음
