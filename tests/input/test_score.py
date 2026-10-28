"""입력 모듈 채점 (src/input/script/evaluation.py): 정답 그대로면 만점, 일부러 틀린 출력은 그만큼 깎인다."""
import copy

from src.input.script.evaluation import case_set, compare, expected, main, total


def _scores(want, got):
    return total({"x": compare(want, got)})


def test_expected_against_itself_is_perfect():
    want = expected("VC-0103")
    t = _scores(want, want)
    assert (t["field_accuracy"], t["present_accuracy"], t["source_exact"], t["source_overlap"]) == (1, 1, 1, 1)


def test_wrong_value_counts_one_slot():
    want = expected("VC-0103")
    got = copy.deepcopy(want)
    got["fields"]["receptors"]["er_percent"]["value"]["result"] = "negative"
    r = compare(want, got)
    assert [w[0] for w in r["wrong"]] == ["receptors.er_percent"]
    assert r["correct"] == r["slots"] - 1


def test_missing_value_is_status_error():
    want = expected("VC-0103")
    got = copy.deepcopy(want)
    got["fields"]["patient"]["ecog"] = {"status": "not_recorded"}
    r = compare(want, got)
    assert r["confusion"][("present", "not_recorded")] == 1
    assert r["source_exact"] == r["source"] - 1


def test_treatment_row_and_extra_field():
    want = expected("VC-0103")
    got = copy.deepcopy(want)
    got["fields"]["treatment_history"][0]["stop_reason"] = "completed"
    got["fields"]["patient"]["height_cm"] = {"status": "present", "value": 160, "source": None}
    names = [w[0] for w in compare(want, got)["wrong"]]
    assert names == ["patient.height_cm", "treatment_history[anastrozole 2021-04-14]"]


def test_precision_and_recall():
    """없는 값을 만들면 정밀도만, 있는 값을 놓치면 재현율만, 값이 틀리면 둘 다 내려간다."""
    want = expected("VC-0103")
    base = total({"x": compare(want, want)})
    assert (base["precision"], base["recall"]) == (1, 1)
    n = base["counts"]["gold"]

    made = copy.deepcopy(want)
    made["fields"]["patient"]["height_cm"] = {"status": "present", "value": 160}
    t = total({"x": compare(want, made)})
    assert t["counts"] == {"hit": n, "pred": n + 1, "gold": n} and t["recall"] == 1

    missed = copy.deepcopy(want)
    missed["fields"]["patient"]["ecog"] = {"status": "not_recorded"}
    t = total({"x": compare(want, missed)})
    assert t["counts"] == {"hit": n - 1, "pred": n - 1, "gold": n} and t["precision"] == 1

    wrong = copy.deepcopy(want)
    wrong["fields"]["patient"]["ecog"]["value"] = 2
    assert total({"x": compare(want, wrong)})["counts"] == {"hit": n - 1, "pred": n, "gold": n}


def test_case_sets():
    assert len(case_set("dev")) == 10 and len(case_set("pairs")) == 19
    test = case_set("test")
    assert len(test) == 20 and test[0] == "VC-0110" and not set(test) & set(case_set("all"))


def test_site_order_and_variant_raw_ignored():
    """0단계 (2026-10-26): 전이 부위 순서와 변이 원문(raw)의 공백 차이는 틀린 칸이 아니다. 값이 다르면 여전히 틀린다."""
    want = expected("VC-0101")
    got = copy.deepcopy(want)
    rec = got["fields"]["recurrence"]["metastatic_sites"]
    rec["value"] = list(reversed(rec["value"]))
    got["fields"]["imaging_findings"][0]["sites"] = list(reversed(got["fields"]["imaging_findings"][0]["sites"]))
    for v in got["fields"]["molecular"]["mutations"]["ESR1"]["variants"]:
        v["raw"] = v["raw"].replace(" ", "   ")
    assert compare(want, got)["wrong"] == []
    got["fields"]["molecular"]["mutations"]["ESR1"]["variants"][0]["protein_change"] = "D538G"
    assert [w[0] for w in compare(want, got)["wrong"]] == ["molecular.mutations.ESR1"]


def test_partial_overlap():
    want = expected("VC-0103")
    got = copy.deepcopy(want)
    s = got["fields"]["receptors"]["er_percent"]["source"]          # 27자 구절의 앞 3자를 뺀다
    got["fields"]["receptors"]["er_percent"]["source"] = {**s, "char_start": s["char_start"] + 3}
    r = compare(want, got)
    assert r["source_exact"] == r["source"] - 1
    assert round(r["source"] - r["source_overlap"], 3) == round(3 / 27, 3)


def test_quote_rate_and_cli(capsys):
    want = expected("VC-0103")
    t = total({"x": compare(want, want)}, {"x": {"candidates": 4, "issues": [{"reason": "quote_not_found"}]}})
    assert t["quote_rate"] == 0.75
    assert main(["--gold", "--ids", "VC-0103", "VC-0106b"]) == 0
    assert "필드 정확도 100.0%" in capsys.readouterr().out
