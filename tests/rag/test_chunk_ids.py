# tests/rag/test_chunk_ids.py
# chunk_id가 다시 청킹해도 바뀌지 않는지 본다. 평가셋 정답과 추천 결과의 인용이 chunk_id를 가리킨다.
from src.rag.chunk_common import stable_key
from src.rag.chunker_esmo import _section_items


def _ids(lines):
    return [stable_key(head) for head, _ in _section_items(lines)]


SECTION = [
    "- Fulvestrant—capivasertib is recommended for patients with PIK3CA, AKT1 or PTEN alterations [I, A].",
    "- Elacestrant is recommended for patients with ESR1-mutated MBC after at least one line of ET [I, A].",
    "- Steroid mouthwash is recommended for stomatitis prophylaxis in patients receiving everolimus [V, A].",
]


def test_stable_key_ignores_dash_spacing_and_markup():
    a = "Fulvestrant—capivasertib is recommended [I, A]."
    b = "**Fulvestrant-capivasertib**  is  _recommended_ [I, A]."
    assert stable_key(a) == stable_key(b)
    assert stable_key(a) != stable_key("Fulvestrant—alpelisib is recommended [I, A].")


def test_adding_a_recommendation_does_not_shift_other_ids():
    before = _ids(SECTION)
    after = _ids(["- OFS is recommended in addition to all endocrine-based therapies in premenopausal women [I, A]."]
                 + SECTION)
    assert after[1:] == before


def test_id_ignores_options_appended_after_the_recommendation():
    plain = ["- Fulvestrant—CDK4/6 inhibitor can also be recommended for these patients [I, B]."]
    with_options = [plain[0] + " Options include:", "- ■ Fulvestrant—palbociclib (ESMO-MCBS v2.0 score: 4)"]
    assert _ids(plain) == _ids(with_options)


def test_bullet_broken_across_pdf_lines_is_one_recommendation():
    # 변환기가 PDF 줄바꿈에서 한 권고를 불릿 두 개로 낸 경우
    broken = ["- Intrathecal therapy may be considered in type I LMD",
              "- (positive cytology or biopsy) after MDT discussion [III, C]."]
    whole = ["- Intrathecal therapy may be considered in type I LMD (positive cytology or biopsy) after MDT discussion [III, C]."]
    items = _section_items(broken)
    assert len(items) == 1
    assert items[0][1].endswith("after MDT discussion [III, C].")
    assert _ids(broken) == _ids(whole)


def test_lowercase_bullet_after_full_stop_is_a_new_recommendation():
    # "cT2-4 N0 ..."처럼 소문자로 시작하는 권고도, 앞 권고가 마침표로 끝났으면 따로 센다
    lines = ["- For cT1c-4 N0, or any N-positive TNBC, neoadjuvant treatment is preferred [I, A].",
             "- cT2-4 N0 or any N-positive (stage II-III) TNBC should be treated with neoadjuvant ChT plus pembrolizumab [I, A]."]
    assert len(_section_items(lines)) == 2
