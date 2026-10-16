import pytest

from src.input.common.vocab import UnknownExpression, Vocab


@pytest.fixture(scope="module")
def vocab() -> Vocab:
    return Vocab()


def test_lookup_ignores_case_and_spaces(vocab):
    assert vocab.lookup("diagnosis.histology", "infiltrating  ductal carcinoma ") == "IDC"


def test_unknown_expression_raises(vocab):
    with pytest.raises(UnknownExpression):
        vocab.lookup("diagnosis.histology", "Tubular Carcinoma")
    assert vocab.lookup("diagnosis.histology", "Tubular Carcinoma", strict=False) is None


def test_er_has_low_positive_but_pr_does_not(vocab):
    assert "low_positive" in vocab.canonical_values("receptors.er_percent.result")
    assert "low_positive" not in vocab.canonical_values("receptors.pr_percent.result")


def test_expressions_for_canonical(vocab):
    assert vocab.expressions("metastatic_sites", "distant_ln") == ["Lymph Node(s)", "Lymph Node"]


def test_conflicting_rows_rejected(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("field,canonical,expression,lang,source,note\n"
                 "f,a,X,en,manual,\nf,b,x,en,manual,\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Vocab(p)
