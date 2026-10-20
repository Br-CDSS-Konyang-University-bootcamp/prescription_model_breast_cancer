"""투여 조건 구조화 (설계 §3.5 형식). Claude API는 부르지 않는다 (가짜 구조화기)."""
import copy
import csv
import json

import pytest

from src.reimbursement import conditions as cm
from src.reimbursement.conditions import (
    Cache, attach_conditions, check_grounding, check_schema, export_review, output_schema,
)

TEXT = ("[9. 유방암 > 2. 수술후보조요법]\n연번 4\n항암요법: anastrozole + LHRH agonist주2\n"
        "투여대상: 호르몬 수용체 양성인 폐경 전 유방암으로 아래의\n하나에 해당하는 경우 (투여기간: 5년)\n"
        "① 40세 미만\n② 림프절 양성\n③ 종양분화도 2∼3\n※ ‘LHRH agonist‘는 4주 간격의 goserelin과\n"
        "leuprolide만 인정함\n(제2020-155호: 2020.6.1., 개정 제2024-264호, 2024.12.1.)")


def _empty(**kw):
    out = {"all_of": [], "any_of": [], "any_of_exceptions": [], "stage_rules": [], "counts_as_prior_line": [],
           "notes": [], "human_review": [], "unmapped": []}
    out.update(kw)
    return out


GOOD = _empty(
    all_of=[{"id": "c1", "field": "hr", "op": "eq", "value": "positive", "text": "호르몬 수용체 양성인"},
            {"id": "c2", "field": "menopause", "op": "in", "value": ["premenopausal", "perimenopausal"],
             "text": "폐경 전"},
            {"id": "c3", "field": "treatment_years", "op": "lte", "value": 5, "text": "(투여기간: 5년)"}],
    any_of=[{"text": "아래의 하나에 해당하는 경우", "items": [
        {"id": "a1", "field": "age", "op": "lt", "value": 40, "text": "40세 미만"},
        {"id": "a2", "field": "positive_ln_count", "op": "gte", "value": 1, "text": "림프절 양성"},
        {"id": "a3", "field": "grade", "op": "gte", "value": 2, "text": "종양분화도 2∼3"}]}],
    notes=["‘LHRH agonist‘는 4주 간격의 goserelin과 leuprolide만 인정함"],
)


def test_output_schema_is_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(output_schema())
    jsonschema.Draft202012Validator.check_schema(cm.stored_schema())
    assert check_schema(GOOD) == [] and cm.check_values(GOOD) == []


def test_grounded_conditions_pass():
    # 줄바꿈 위치가 달라도 원문 구절로 인정한다 (notes는 두 줄에 걸쳐 있음)
    assert check_grounding(GOOD, TEXT) == []


def test_invented_text_is_rejected():
    bad = copy.deepcopy(GOOD)
    bad["all_of"].append({"id": "c4", "field": "her2", "op": "eq", "value": "negative", "text": "HER2 음성"})
    errs = check_grounding(bad, TEXT)
    assert len(errs) == 1 and "all_of[3]" in errs[0] and "원문에 없는" in errs[0]


def test_empty_text_is_rejected():
    bad = copy.deepcopy(GOOD)
    bad["any_of"][0]["items"][0]["text"] = ""
    assert any("any_of[0].items[0]" in e for e in check_grounding(bad, TEXT))


def test_paraphrased_note_is_rejected():
    bad = copy.deepcopy(GOOD)
    bad["notes"] = ["LHRH agonist는 4주마다 투여"]                       # 바꿔 쓴 문장
    assert any("notes" in e for e in check_grounding(bad, TEXT))


def test_schema_rejects_unknown_field_and_op():
    pytest.importorskip("jsonschema")
    bad = copy.deepcopy(GOOD)
    bad["all_of"][0]["field"] = "hormone"
    assert check_schema(bad)
    bad = copy.deepcopy(GOOD)
    bad["all_of"][0]["op"] = "approx"
    assert check_schema(bad)


@pytest.mark.parametrize("item, msg", [
    ({"field": "menopause", "op": "eq", "value": "perimenopause"}, "허용값이 아님"),
    ({"field": "age", "op": "lt", "value": "40"}, "숫자여야"),
    ({"field": "her2", "op": "gte", "value": "positive"}, "쓸 수 없는 op"),
    ({"field": "prior_drugs", "op": "not_contains", "value": ["nonsteroidal aromatase inhibitor"]}, "사전에 없는 이름"),
    ({"field": "her2", "op": "in", "value": "negative"}, "값 목록"),
])
def test_values_follow_vocabulary(item, msg):
    cond = _empty(all_of=[{"id": "c1", "text": "x", **item}])
    errs = cm.check_values(cond)
    assert errs and msg in errs[0]


def test_prior_drugs_and_unless():
    """설계 §3.5 예: 이전 비스테로이드성 AI 없음, 단 보조요법 종료 1년 이후 재발은 인정."""
    cond = _empty(all_of=[{
        "id": "c3", "field": "prior_drugs", "op": "not_contains", "value": ["AI_nonsteroidal"],
        "text": "이전에 비스테로이드성 aromatase inhibitor를 투여받은 적이 없는 경우",
        "unless": {"field": "days_end_to_recurrence", "op": "gt", "value": 365,
                   "of": {"drugs": ["AI_nonsteroidal"], "setting": ["neoadjuvant", "adjuvant"]},
                   "text": "투여 종료 후 1년 이후 재발한 경우도 인정"}}],
        counts_as_prior_line=[{"text": "1차 투여가 실시된 것으로 간주", "setting": ["adjuvant"],
                               "drugs": ["anthracycline", "taxane"]}])
    assert check_schema(cond) == [] and cm.check_values(cond) == []
    cond["all_of"][0]["unless"]["of"]["drugs"] = ["aromatase"]
    assert any("unless.of" in e for e in cm.check_values(cond))


class Fake:
    def __init__(self, result=GOOD, fail=False):
        self.result, self.fail, self.calls = result, fail, 0

    def __call__(self, text, context):
        self.calls += 1
        if self.fail:
            raise RuntimeError("timeout")
        return copy.deepcopy(self.result), {"input_tokens": 100, "output_tokens": 50}


def _chunks():
    return [
        {"chunk_id": "row", "chunk_kind": "reimbursement_condition", "text": TEXT, "section": "9. 유방암 > 2 > 연번 4",
         "reimbursement": {"source_type": "baseline", "notice_no": "제2024-264호", "effective_from": "2024-12-01",
                           "regimen": ["anastrozole + LHRH agonist"],
                           "conditions": {"line_rule": {"stage": "adjuvant", "line": None}}}},
        {"chunk_id": "sec", "chunk_kind": "section", "text": TEXT, "section": "9. 유방암 > 2", "reimbursement": {}},
    ]


def test_attach_uses_cache_and_keeps_line_rule(tmp_path):
    fake = Fake()
    cache_path = tmp_path / "c.jsonl"
    ch = _chunks()
    rep = attach_conditions(ch, {}, structurer=fake, cache=Cache(cache_path))
    assert (rep.requested, rep.from_cache, fake.calls) == (1, 0, 1)    # 섹션 청크는 대상 아님
    cond = ch[0]["reimbursement"]["conditions"]
    assert cond["line_rule"] == {"stage": "adjuvant", "line": None}   # 코드가 넣은 투여단계는 남는다
    assert [x["id"] for x in cond["all_of"]] == ["c1", "c2", "c3"]
    assert "conditions" not in ch[1]["reimbursement"]
    assert check_schema(cond, cm.stored_schema()) == []

    ch2 = _chunks()
    rep = attach_conditions(ch2, {}, structurer=fake, cache=Cache(cache_path))   # 새로 연 저장본
    assert (rep.requested, rep.from_cache, fake.calls) == (0, 1, 1)
    assert ch2[0]["reimbursement"]["conditions"] == cond

    ch3 = _chunks()
    ch3[0]["text"] += "\n변경된 문장"                                     # 본문이 바뀌면 다시 요청
    attach_conditions(ch3, {}, structurer=fake, cache=Cache(cache_path))
    assert fake.calls == 2


def test_rejected_result_is_not_attached(tmp_path):
    bad = copy.deepcopy(GOOD)
    bad["all_of"][0]["text"] = "HR 양성"
    ch = _chunks()
    rep = attach_conditions(ch, {}, structurer=Fake(bad), cache=Cache(tmp_path / "c.jsonl"))
    assert "row" in rep.rejected and "all_of" not in ch[0]["reimbursement"]["conditions"]


def test_context_can_be_quoted(tmp_path):
    ctx = ("[9. 유방암 > 3. 고식적 내분비요법]\n- 투여단계는 고식적 항암화학요법(chemotherapy)과 별도로 적용함. "
           "단 ‘CDK4/6 inhibitor +letrozole or anastrozole’ 병용요법의 경우 고식적 항암화학요법을 투여하지 않은 사람을 대상으로 함")
    res = _empty(stage_rules=[{"id": "s1", "field": "palliative_chemo_lines", "op": "eq", "value": 0,
                               "text": "고식적 항암화학요법을 투여하지 않은 사람을 대상으로 함"}])
    ch = _chunks()
    ch[0]["text"] = "연번 1\n항암요법: palbociclib + letrozole"
    rep = attach_conditions(ch, {"row": ctx}, structurer=Fake(res), cache=Cache(tmp_path / "c.jsonl"))
    assert not rep.rejected and ch[0]["reimbursement"]["conditions"]["stage_rules"][0]["value"] == 0


def test_failure_and_no_api_do_not_stop(tmp_path):
    ch = _chunks()
    rep = attach_conditions(ch, {}, structurer=Fake(fail=True), cache=Cache(tmp_path / "c.jsonl"))
    assert "row" in rep.failed and "all_of" not in ch[0]["reimbursement"]["conditions"]
    rep = attach_conditions(_chunks(), {}, structurer=None, cache=Cache(tmp_path / "c.jsonl"), use_api=False)
    assert rep.skipped_no_api == ["row"]


def test_existing_male_condition_is_kept(tmp_path):
    ch = _chunks()
    male = {"id": "m1", "field": "sex", "op": "eq", "value": "MALE", "text": "남성 유방암"}
    ch[0]["reimbursement"]["conditions"] = {"all_of": [male]}
    attach_conditions(ch, {}, structurer=Fake(), cache=Cache(tmp_path / "c.jsonl"))
    cond = ch[0]["reimbursement"]["conditions"]
    assert male in cond["all_of"] and len(cond["all_of"]) == 4


def test_review_sheet(tmp_path):
    ch = _chunks()
    attach_conditions(ch, {}, structurer=Fake(), cache=Cache(tmp_path / "c.jsonl"))
    p = export_review(ch, tmp_path / "review.tsv")
    with open(p, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    assert rows[0] == cm.REVIEW_COLUMNS
    groups = [r[3] for r in rows[1:]]
    assert groups.count("all_of") == 3 and groups.count("any_of") == 3 and "line_rule" in groups
    assert "notes" in groups and all(r[10] == "" for r in rows[1:])     # 검수 칸은 비어 있다
    assert export_review(_chunks(), tmp_path / "none.tsv").exists()   # line_rule만 있어도 검수 대상


def test_unavailable_without_package_or_key(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_anthropic(name, *a, **k):
        if name == "anthropic":
            raise ImportError
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_anthropic)
    with pytest.raises(cm.StructurerUnavailable):
        cm.ClaudeStructurer()


class _Run:
    """subprocess.run 가짜: Claude Code 출력(--output-format json)을 돌려주고 받은 명령을 남긴다."""
    def __init__(self, out):
        self.out, self.cmd, self.input = out, None, None

    def __call__(self, cmd, input=None, **kw):
        import types
        self.cmd, self.input, self.env = cmd, input, kw.get("env")
        return types.SimpleNamespace(stdout=json.dumps(self.out, ensure_ascii=False), stderr="", returncode=0)


def test_claude_code_structurer(monkeypatch):
    import subprocess
    run = _Run({"is_error": False, "result": "", "structured_output": GOOD, "session_id": "s",
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 7}})
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    s = cm.ClaudeCodeStructurer(exe="claude")
    cond, usage = s("본문", "안내")
    assert cond == GOOD and usage["input_tokens"] == 15 and usage["output_tokens"] == 7
    assert "[급여 기준 본문]\n본문" in run.input                       # 공고 글은 표준 입력으로
    assert run.cmd[run.cmd.index("--tools") + 1] == ""                    # 도구를 모두 끈다
    assert "--json-schema" in run.cmd and s.label == f"claude-code:{cm.MODEL}"
    assert "ANTHROPIC_API_KEY" not in run.env                             # 구독으로 돌게 API 키는 넘기지 않는다


def test_claude_code_text_result_and_errors(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", _Run({"is_error": False, "result": "```json\n" + json.dumps(GOOD) + "\n```"}))
    assert cm.ClaudeCodeStructurer(exe="claude")("본문", "")[0] == GOOD
    for msg in ("Not logged in · Please run /login", "Claude usage limit reached", "Credit balance is too low"):
        monkeypatch.setattr(subprocess, "run", _Run({"is_error": True, "result": msg}))
        with pytest.raises(cm.StructurerUnavailable):
            cm.ClaudeCodeStructurer(exe="claude")("본문", "")
    monkeypatch.setattr(subprocess, "run", _Run({"is_error": True, "result": "overloaded"}))
    with pytest.raises(RuntimeError):
        cm.ClaudeCodeStructurer(exe="claude")("본문", "")


def test_find_claude_code_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_EXE", "/x/claude")
    assert cm.find_claude_code() == "/x/claude"


def test_find_claude_code_store_app(tmp_path, monkeypatch):
    """스토어판 데스크톱 앱: 실제 파일은 LOCALAPPDATA/Packages/Claude_*/LocalCache/Roaming 아래. 최신판을 고른다."""
    import shutil
    monkeypatch.delenv("CLAUDE_CODE_EXE", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))         # 앱 밖에서는 비어 있음
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    base = tmp_path / "local/Packages/Claude_abc/LocalCache/Roaming/Claude/claude-code"
    for ver in ("2.1.295", "2.1.299"):
        exe = base / ver / "h" / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("")
    assert cm.find_claude_code() == str(base / "2.1.299" / "h" / "claude.exe")


def test_falls_back_to_next_structurer(tmp_path, monkeypatch):
    class NoCredit:
        def __call__(self, text, context):
            raise cm.StructurerUnavailable("API 크레딧 잔액 부족")

    class Sub(Fake):
        label = "claude-code:test"

    sub = Sub()
    monkeypatch.setattr(cm, "STRUCTURERS", (NoCredit, lambda: sub))
    ch = _chunks()
    cache_path = tmp_path / "c.jsonl"
    rep = attach_conditions(ch, {}, cache=Cache(cache_path))
    assert rep.requested == 1 and sub.calls == 1 and "크레딧" in rep.unavailable_reason
    assert [x["id"] for x in ch[0]["reimbursement"]["conditions"]["all_of"]] == ["c1", "c2", "c3"]
    assert json.loads(cache_path.read_text(encoding="utf-8"))["model"] == "claude-code:test"

    def none():
        raise cm.StructurerUnavailable("Claude Code 실행 파일 없음")
    monkeypatch.setattr(cm, "STRUCTURERS", (NoCredit, none))
    rep = attach_conditions(_chunks(), {}, cache=Cache(tmp_path / "d.jsonl"))
    assert rep.skipped_no_api == ["row"] and "실행 파일 없음" in rep.unavailable_reason


def test_fields_follow_team_terms_dictionary():
    """공고 표현 -> 칸·값은 팀 사전 data/dictionaries/reimbursement_terms.csv를 따른다."""
    path = cm.ROOT / "data" / "dictionaries" / "reimbursement_terms.csv"
    if not path.exists():
        pytest.skip("reimbursement_terms.csv 없음")
    with open(path, encoding="utf-8") as f:
        terms = {r["notice_term"]: r for r in csv.DictReader(f)}
    split = lambda s: [x.strip().split(" ")[0] for x in s.split("|")]          # noqa: E731
    assert set(split(terms["HER2 음성"]["json_value"])) <= set(cm.FIELDS["her2"][2])
    assert "stage.ptnm" in cm.FIELDS["ln_status"][0]                          # 림프절 양성·음성은 N 병기
    assert terms["림프절 양성"]["json_field"] == "stage.ptnm.n"
    assert "stage.disease_extent" in cm.FIELDS["disease"][0]
    assert terms["전이성"]["json_field"] == "stage.disease_extent"
    assert "duration_days" in cm.FIELDS["treatment_years"][0]
    assert terms["투여기간"]["json_field"] == "treatment_history[].duration_days"
    # 고식적 = treatment_history.setting metastatic (JSON에 palliative 값 없음)
    assert terms["고식적 (palliative)"]["json_value"] == "metastatic"
    assert cm._OF["properties"]["setting"]["items"]["enum"] == ["neoadjuvant", "adjuvant", "metastatic"]


def test_prompt_lists_every_field():
    for k in cm.FIELDS:
        assert f"- {k}:" in cm.SYSTEM
