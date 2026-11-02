# tests/rag/test_biomarker_tags.py
# 청크 biomarker_tags가 B의 rag_tags와 같은 이름을 쓰는지 본다 (src/biomarker/README.md)
from src.rag.chunk_common import find_biomarker_tags


def test_tags_use_biomarker_module_names():
    cases = {
        "HER2-negative tumours with 1%-9% ER and/or PgR expression (ER-/PgR-low)": ["ER-low"],
        "node-positive breast cancer with a Ki67 score of ≥20%": ["Ki-67-high"],
        "somatic pathogenic or likely pathogenic BRCA1/2 mutations": ["sBRCA"],
        "patients with a germline PALB2 mutation": ["gPALB2"],
        "patients with a germline BRCA1/2 mutation": ["gBRCA"],
        "PIK3CA, AKT1 or PTEN alterations": ["PIK3CA-mut", "AKT1-mut", "PTEN-alt"],
        "ESR1-mutated MBC": ["ESR1-mut"],
        "PD-L1-positive (CPS ≥10)": ["PD-L1+"],
    }
    for text, tags in cases.items():
        assert find_biomarker_tags(text) == tags, text


def test_ki67_without_cutoff_is_not_high():
    assert find_biomarker_tags("insufficient evidence to use baseline Ki67 expression") == []


def test_negated_mentions_get_no_positive_tag():
    # B의 태그는 양성일 때만 붙는다. "없다"는 언급에 양성 태그가 붙으면 반대 환자의 권고가 가점을 받는다
    assert find_biomarker_tags("germline BRCA1/2- wild type and PD-L1-negative mTNBC") == []
    assert find_biomarker_tags("germline BRCA1/2-mutated and PD-L1-negative mTNBC") == ["gBRCA"]
    assert find_biomarker_tags("ER-positive, HER2-negative, PIK3CA-wild type MBC") == []
    assert find_biomarker_tags("PIK3CA-mutated MBC") == ["PIK3CA-mut"]
    # 알고리즘 그림의 줄임 표기 (src/rag/algorithm_esmo.py)
    assert find_biomarker_tags("PD-L1- → gBRCA wt → Dato-DXd") == []
    assert find_biomarker_tags("PIK3CA wt → Fulvestrant-palbociclib") == []
    assert find_biomarker_tags("gBRCA1/2-wt or untested") == []
    assert find_biomarker_tags("PD-L1- → gBRCA mutated [ESCAT I-A]") == ["gBRCA"]


def test_class_names_are_expanded_to_drugs():
    # ESMO는 계열 이름으로 쓴다 (A 통합 점검 2026-10-29 §1.2): "AI—CDK4/6 inhibitor"에 letrozole이 없으면
    # B 후처리가 letrozole + palbociclib 후보를 지운다. 좁은 계열만 풀고 ET·ChT 같은 넓은 계열은 풀지 않는다
    from src.rag.chunk_common import find_drugs
    drugs = find_drugs("AI—CDK4/6 inhibitor is recommended for patients with ER-positive, HER2-negative MBC")
    assert {"letrozole", "anastrozole", "exemestane", "palbociclib", "ribociclib", "abemaciclib"} <= set(drugs)
    assert find_drugs("an AI or tamoxifen followed by an AI")[0] == "tamoxifen"  # 적힌 약이 앞, 푼 약이 뒤
    assert {"goserelin", "leuprolide"} <= set(find_drugs("OFS-tamoxifen or OFS-AI"))
    assert "tesetaxel" not in find_drugs("taxane monotherapy") and "paclitaxel" in find_drugs("taxane monotherapy")
    assert find_drugs("ET alone") == [] and find_drugs("Chemotherapy (ChT)") == []  # 넓은 계열은 풀지 않음
    assert find_drugs("MAIN analysis") == []  # 대문자 줄임말은 단어로만


def test_stored_chunk_drugs_are_up_to_date():
    # 청크 JSON의 drugs가 지금 규칙으로 다시 계산한 값과 같아야 한다 (사전·계열 규칙을 바꾸면 python -m src.rag.refresh_drugs)
    import json
    from src.rag.refresh_drugs import ALGORITHM_JSON, ESMO_JSON, chunk_drugs
    for path in (ESMO_JSON, ALGORITHM_JSON):
        stale = [c["chunk_id"] for c in json.loads(path.read_text(encoding="utf-8")) if chunk_drugs(c) != c["drugs"]]
        assert stale == [], f"{path.name}: python -m src.rag.refresh_drugs 필요 {stale[:3]}"
