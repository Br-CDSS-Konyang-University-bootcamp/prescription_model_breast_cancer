# tests/recommend/test_class_terms.py
# 후처리 3번 규칙의 넓은 계열 이름 (C와 합의 2026-11-02). 청크 text는 모두 지어낸 테스트 문장이다.
from src.recommend.postprocess import _drug_in_chunks


def chunk(text, drugs=()):
    return {"chunk_id": "esmo-test", "drugs": list(drugs), "text": text}


def test_broad_class_terms_pass_their_class_only():
    et = chunk("TEST (made up): if CDK4/6 inhibitors cannot be used, ET alone.", ["palbociclib"])
    assert _drug_in_chunks("letrozole", [et])                                    # ET → 내분비 계열 통과
    assert not _drug_in_chunks("capecitabine", [et])                             # 항암제는 통과 못 함
    cht = chunk("TEST (made up): in visceral crisis, ChT is preferred.")
    assert _drug_in_chunks("capecitabine", [cht])
    assert not _drug_in_chunks("letrozole", [cht])
    her2 = chunk("TEST (made up): HER2-directed therapy plus a taxane.")
    assert _drug_in_chunks("trastuzumab", [her2])
    assert _drug_in_chunks("letrozole", [chunk("TEST (made up): endocrine therapy is continued.")])
    assert _drug_in_chunks("paclitaxel", [chunk("TEST (made up): chemotherapy is an option.")])


def test_short_terms_need_exact_word():
    assert not _drug_in_chunks("letrozole", [chunk("TEST (made up): see Smith et al. for details.")])   # et ≠ ET
    assert not _drug_in_chunks("letrozole", [chunk("TEST (made up): METASTATIC setting.")])             # 단어 안의 ET
