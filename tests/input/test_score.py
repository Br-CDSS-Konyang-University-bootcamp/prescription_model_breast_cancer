"""입력 모듈 채점 (src/input/script/evaluation/score.py): 정답 그대로면 만점, 일부러 틀린 출력은 그만큼 깎인다."""
import copy

from src.input.script.evaluation.score import compare, expected, main, total


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
