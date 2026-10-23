"""IN-2 추출기 (src/input/extract.py)를 가짜 LLM으로 본다: 가린 문서만 보내고, 칸 이름을 enum으로 강제하고,
날짜 표기를 고치고, LLM이 바꿔 쓴 구절은 인용 확인에서 걸러진다. 실제 모델 시험은 `python -m src.input.extract`.
"""
import json

from jsonschema import Draft202012Validator

from llm import LLMConfig
from src.input.chart.virtual_chart import out_dir
from src.input.extract import FIELDS, EXAMPLES, make_extract, schema
from src.input.pipeline import run

CFG = LLMConfig(provider="ollama", model="fake", patient_data=True)


def test_example_matches_schema():
    for doc_type, (_, out) in EXAMPLES.items():
        assert list(Draft202012Validator(schema(doc_type)).iter_errors({"candidates": out})) == []
    assert "receptors.er_percent" in schema("pathology")["properties"]["candidates"]["items"]["properties"]["field"]["enum"]


def test_pipeline_with_fake_llm():
    ref = "VC-0103"
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    sent = []

    def fake(messages, schema_, config):
        doc = messages[-1]["content"]
        sent.append(doc)
        if "ER positive (Allred 8, 5+3)" not in doc:
            return {"candidates": []}
        return {"candidates": [
            {"field": "receptors.er_percent", "quote": "ER positive  (Allred 8, 5+3)", "specimen": "metastasis",
             "observed_date": "2023.4.16"},
            {"field": "receptors.her2_ihc", "quote": "HER2 IHC 1+", "specimen": "metastasis",
             "observed_date": "2023-04-16"},            # 원문에 없는 구절 (지어낸 값)
            {"field": "receptors.pdl1", "quote": "null", "specimen": None, "observed_date": None}]}  # 빈 칸

    got, issues = run(chart, make_extract(CFG, fake), patient_ref=ref, created_at=want["created_at"])
    assert len(sent) == sum(d["doc_type"] in FIELDS for d in want["documents"])     # 병리 문서만 보냄
    assert not any("김가상" in s for s in sent)
    er = got["fields"]["receptors"]["er_percent"]
    assert er["value"] == want["fields"]["receptors"]["er_percent"]["value"]
    assert er["observed_date"] == "2023-04-16"
    assert er["source"] == want["fields"]["receptors"]["er_percent"]["source"]       # 공백 차이는 원문 위치로
    assert got["fields"]["receptors"]["her2_ihc"] == {"status": "not_recorded"}
    assert [i["reason"] for i in issues] == ["quote_not_found"]
