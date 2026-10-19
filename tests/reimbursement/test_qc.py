from collections import Counter

import pytest

from src.reimbursement import qc
from src.reimbursement.chunks import DrugScan
from src.reimbursement.vocab import DICT_CSV, known_drugs, suggest_drug, typo_suspects


# ---------- 파일 ----------

def test_check_file(tmp_path):
    ok = tmp_path / "공고책자_20261001.pdf"
    ok.write_bytes(b"%PDF-1.7\n" + b"0" * 60_000)
    assert qc.check_file(ok).ok

    html = tmp_path / "공고책자_20261101.pdf"
    html.write_bytes(b"<!DOCTYPE html><html>" + b" " * 60_000)
    assert any("HTML" in e for e in qc.check_file(html).errors)

    small = tmp_path / "공고책자_20261201.pdf"
    small.write_bytes(b"%PDF-1.7\n")
    assert any("크기" in e for e in qc.check_file(small).errors)

    wrong = tmp_path / "허가초과_261012.xlsx"
    wrong.write_bytes(b"%PDF-1.7\n" + b"0" * 6_000)
    assert any("서명" in e for e in qc.check_file(wrong).errors)

    assert not qc.check_file(tmp_path / "없음_20261001.pdf").ok
    nodate = tmp_path / "책자.pdf"
    nodate.write_bytes(b"%PDF-1.7\n" + b"0" * 60_000)
    assert any("날짜" in e for e in qc.check_file(nodate).errors)


# ---------- 추출 범위 ----------

def test_breast_scope():
    sections = {"combination": "20 유방암 ... 21 ... 유방암 ... 31 난소암",
                "immunotherapy": "○ 유방암 - adjuvant TAC", "cancer:위암": "위암"}
    r = qc.check_breast_scope(sections, {"combination": "유방암 ... 유방암"})
    assert r.ok and len(r.warnings) == 1                    # immunotherapy는 대상 아님 -> 경고
    r = qc.check_breast_scope(sections, {"combination": "유방암"})
    assert not r.ok                                         # 한 행을 놓침
    # 제외하기로 한 보조 약제 섹션의 언급은 경고가 아니라 정보
    r = qc.check_breast_scope({"other:G-CSF 주사제": "○ 유방암 - adjuvant TAC"}, {})
    assert r.ok and not r.warnings and "제외하기로 한" in r.info[0]


def test_row_numbers():
    assert qc.check_row_numbers({"a": [1, 2, 3], "b": []}).ok
    r = qc.check_row_numbers({"a": [1, 2, 4], "b": [1, 1, 2]})
    assert len(r.errors) == 2 and "빠짐 [3]" in r.errors[0] and "중복 [1]" in r.errors[1]


# ---------- 빠진 부분 / 생성된 단어 ----------

def test_coverage_counts_each_token():
    src = "letrozole 가. 호르몬 수용체 양성 나. 호르몬 수용체 양성"
    assert qc.check_coverage(src, src + " 연번 1", "t").ok
    r = qc.check_coverage(src, "letrozole 가. 호르몬 수용체 양성 나.", "t")
    assert not r.ok and "호르몬×1" in r.errors[0]           # 두 번 나온 낱말이 한 번만 들어감


def test_coverage_ignore():
    assert qc.check_coverage("연번 항암요법 a", "a", "t", ignore=Counter({"연번": 1, "항암요법": 1})).ok


def test_foreign_words():
    src = "paclitaxel 전이성 유방암"
    assert qc.check_foreign(src, "[유방암] 항암요법: paclitaxel 전이성 유방암", "t", {"항암요법"}).ok
    r = qc.check_foreign(src, "paclitaxel 전이성 유방암 nivolumab", "t", set())
    assert not r.ok and "nivolumab" in r.errors[0]


@pytest.mark.parametrize("text, label", [
    ("trastuzumab �", "U+FFFD"),
    ("(cid:12) 유방암", "cid"),
    ("ê³µê³ ì±ì", "latin-1"),
    ("유방암 ㅇ", "자모"),
    ("a\x01b", "제어"),
])
def test_garbled(text, label):
    r = qc.check_garbled({"c": text})
    assert not r.ok and label in r.errors[0]


def test_not_garbled():
    assert qc.check_garbled({"c": "쪽1\f쪽2 ㆍ 가운뎃점 ① ∼ Ⅱ ≥ ㎡ ‘따옴표’"}).ok


# ---------- 약제명 ----------

def test_suggest_drug_typo():
    assert suggest_drug("pembroiizumab") == "pembrolizumab"
    assert suggest_drug("pembrolizumab") is None
    assert suggest_drug("neoadjuvant") is None
    assert typo_suspects("paclitaxel + pembroiizumab → AC") == [("pembroiizumab", "pembrolizumab")]


@pytest.mark.skipif(not DICT_CSV.exists(), reason="공용 약제 사전 없음")
def test_known_drugs_reads_shared_dictionary():
    k = known_drugs()
    assert {"doxorubicin", "cyclophosphamide", "tamoxifen", "nab-paclitaxel"} <= k   # 사전 (BOM 있음)
    assert {"abemaciclib", "capivasertib"} <= k                                       # 모듈 추가분
    assert not any("nos" in x.split() for x in k)


def test_check_drugs():
    chunks = [
        {"chunk_id": "a", "chunk_kind": "reimbursement_condition", "drugs": ["paclitaxel"]},
        {"chunk_id": "b", "chunk_kind": "reimbursement_condition", "drugs": []},
        {"chunk_id": "c", "chunk_kind": "reimbursement_condition", "drugs": ["madeupmab"]},
        {"chunk_id": "d", "chunk_kind": "section", "drugs": []},
    ]
    scans = {"a": DrugScan(["pembrolizumab"], [("pembroiizumab", "pembrolizumab")], ["newdrugib"])}
    r = qc.check_drugs(chunks, scans, "pembroiizumab")
    assert len(r.errors) == 2                     # b: 약제 없음, c: 목록에 없는 이름 (d는 섹션이라 괜찮음)
    assert any("pembroiizumab" in w for w in r.warnings)
    assert any("newdrugib" in w for w in r.warnings)


# ---------- 이전 실행 ----------

def test_counts():
    assert qc.check_counts({"a": 10}, None).ok
    assert qc.check_counts({"a": 10, "b": 5}, {"a": 10, "b": 5}).ok
    r = qc.check_counts({"a": 7, "b": 6}, {"a": 10, "b": 5})
    assert len(r.errors) == 1 and len(r.warnings) == 1     # a는 30% 줄어 오류, b는 늘어 경고
