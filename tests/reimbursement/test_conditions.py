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


def test_physician_opinion_only_in_unless():
    """의사 판단 예외(2026-11-04 D 결정)는 본 조건의 unless에만 둔다. 본 조건 자리에 오면 버린다."""
    exc = {"field": "physician_opinion", "op": "eq", "value": True, "text": "이러한 치료가 부적절한 환자는 예외로 함"}
    cond = _empty(all_of=[{"id": "c2", "field": "prior_drugs", "op": "contains", "value": ["anthracycline", "taxane"],
                           "text": "anthracycline계와 taxane계 항암제 모두 사용 경험이 있어야 하며", "unless": exc}])
    assert check_schema(cond) == [] and cm.check_values(cond) == []
    alone = _empty(all_of=[{"id": "c3", **exc}])
    assert any("unless에만" in e for e in cm.check_values(alone))
    assert any("unless" in e for e in cm.check_values(
        _empty(all_of=[{**cond["all_of"][0], "unless": {**exc, "value": False}}])))


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


def test_review_sheet_puts_unlike_drafts_first():
    ch = _chunks() + [{**copy.deepcopy(_chunks()[0]), "chunk_id": c} for c in ("new", "changed")]
    for c in ch:
        if c["chunk_kind"] != "section":
            c["reimbursement"]["conditions"] = {**GOOD}
    sources = {"row": {"model": "담당 D", "reviewed": True},
               "changed": {"model": "ollama:x", "reviewed": False, "previous": "old-r01", "fixed": ["a: b"]},
               "new": {"model": "ollama:x", "reviewed": False, "previous": None, "similarity": 0.31}}
    rows = cm.review_rows(ch, sources)
    order = list(dict.fromkeys(r[0] for r in rows))
    assert order == ["new", "changed", "row"]
    first = next(r for r in rows if r[0] == "new")
    assert len(first) == len(cm.REVIEW_COLUMNS) and "비슷한 검수 행 없음" in first[12] and first[13] == "ollama:x"
    assert next(r for r in rows if r[0] == "changed")[14] == "a: b"


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


def test_ollama_structurer(monkeypatch):
    """로컬 모델: REIMB_OLLAMA_MODEL이 없거나 서버·모델이 없으면 건너뛰고, 있으면 공용 llm.complete_json으로 부른다."""
    import types
    import requests
    import llm
    monkeypatch.delenv("REIMB_OLLAMA_MODEL", raising=False)
    with pytest.raises(cm.StructurerUnavailable):
        cm.OllamaStructurer()
    tags = {"models": [{"name": "qwen3:32b"}]}
    monkeypatch.setattr(requests, "get", lambda url, timeout: types.SimpleNamespace(json=lambda: tags))
    with pytest.raises(cm.StructurerUnavailable):
        cm.OllamaStructurer(model="exaone3.5:32b")                        # 서버에 없는 모델
    seen = {}

    def fake(messages, schema, config):
        seen.update(messages=messages, schema=schema, config=config)
        return GOOD
    monkeypatch.setattr(llm, "complete_json", fake)
    monkeypatch.setenv("REIMB_OLLAMA_MODEL", "qwen3:32b")
    s = cm.OllamaStructurer(similar=0)
    assert s("본문", "안내")[0] == GOOD and s.label == "ollama:qwen3:32b"
    assert seen["messages"][0] == {"role": "system", "content": cm.SYSTEM}
    assert "[급여 기준 본문]\n본문" in seen["messages"][1]["content"] and seen["schema"] == cm.output_schema()
    assert seen["config"].host == cm.OLLAMA_HOST and not seen["config"].think
    # 예시(검수된 행)는 앞선 문답으로, 생각 모드는 설정으로 넘긴다
    s = cm.OllamaStructurer(think=True, examples=[("예시 본문", "예시 안내", GOOD)], similar=0)
    msgs = s.messages("본문", "")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert json.loads(msgs[2]["content"]) == GOOD and s.config.think and s.label == "ollama:qwen3:32b (think, 1shot)"
    # 기본: 행마다 비슷한 검수 행 3개, 이전 판이 있으면 마지막 질문에 이전 판 원문·조건
    s = cm.OllamaStructurer()
    assert s.label == "ollama:qwen3:32b (sim3)" and s.config.num_ctx == 32768
    pool = [{"chunk_id": f"hira-booklet-20261101-bc-adj-r{i:02d}", "text": f"연번 {i}\n{t}", "context": "",
             "drugs": [], "conditions": GOOD} for i, t in enumerate(["letrozole 폐경 후", "letrozole 폐경 전", "기타", "x"])]
    target = {"chunk_id": "hira-booklet-20261101-bc-adj-r00", "text": "letrozole 폐경 후 5년", "drugs": ["letrozole"]}
    prev = {"chunk_id": "hira-booklet-20261001-bc-adj-r07", "text": "letrozole 폐경 후", "drugs": ["letrozole"],
            "conditions": GOOD}
    s.prepare(target, pool, [prev])
    msgs = s.messages(target["text"], "")
    assert len(msgs) == 2 + 2 * 3 and target["chunk_id"] not in s.hint["examples"]      # 시스템 + 예시 3문답 + 질문
    assert s.hint["previous"] == prev["chunk_id"] and "[이전 판 조건 (사람이 검수함)]" in msgs[-1]["content"]
    assert cm.UPDATE_TASK in msgs[-1]["content"]
    s.prepare({**target, "drugs": ["anastrozole"]}, pool, [prev])           # 약이 다르면 새 행
    assert s.previous_row is None and "[이전 판" not in s.messages("본문", "")[-1]["content"]


def test_fix_conditions_rules():
    """규칙으로 정해지는 것은 코드가 고친다: 시기별 병기 칸, 비교 낱말, cm -> mm, in 목록, 약 이름, 원문 구절 따옴표."""
    src = "투여대상: 림프절 양성 또는 종양 크기 1cm를 초과하는 경우\n‘CDK4/6 inhibitor’를 받은 적이 없는 경우"
    cond = _empty(any_of=[{"text": "하나", "items": [
        {"id": "a1", "field": "cn_status", "op": "eq", "value": "positive", "text": "림프절 양성"},
        {"id": "a2", "field": "clinical_size_mm", "op": "gte", "value": 1, "text": "종양 크기 1cm를 초과"}]}],
        all_of=[{"id": "c1", "field": "prior_drugs", "op": "not_contains", "value": ["CDK4/6 inhibitor"],
                 "text": "‘CDK4/6 inhibitor’를 받은 적이 없는 경우."},
                {"id": "c2", "field": "her2", "op": "in", "value": "positive", "text": "림프절 양성"}])
    new, log = cm.fix_conditions(cond, "adjuvant", src)
    a1, a2 = new["any_of"][0]["items"]
    assert (a1["field"], a2["field"], a2["op"], a2["value"]) == ("pn_status", "pathologic_size_mm", "gt", 10)
    c1, c2 = new["all_of"]
    assert c1["value"] == ["CDK4/6_inhibitor"] and c1["text"] == "‘CDK4/6 inhibitor’를 받은 적이 없는 경우"
    assert c2["value"] == ["positive"] and len(log) == 7 and cond["any_of"][0]["items"][0]["field"] == "cn_status"
    assert cm.fix_conditions(new, "adjuvant", src) == (new, [])                       # 두 번 고쳐도 같다
    assert cm.fix_conditions(cond, "neoadjuvant", src)[0]["any_of"][0]["items"][0]["field"] == "cn_status"
    # 비교 낱말이 두 종류면 건드리지 않는다
    two = _empty(all_of=[{"id": "c1", "field": "age", "op": "lt", "value": 19, "text": "19세 이상 70세 미만"}])
    assert cm.fix_conditions(two, None, "19세 이상 70세 미만")[1] == []


def test_fix_conditions_keep_reviewed_rows():
    """사람이 쓴 저장본 조건에 쓰면 하나도 바뀌지 않는다 (규칙이 저장본 관례와 맞는지)."""
    cur = cm.DATA / "chunks" / "reimbursement_chunks_current.jsonl"
    if not cur.exists():
        pytest.skip("청크 파일 없음")
    from src.reimbursement.booklet import load_booklet
    from src.reimbursement.chunks import booklet_chunks
    from src.reimbursement.pipeline import _latest_local
    booklet = _latest_local(cm.DATA / "raw", "공고책자_*.pdf")
    if booklet is None:
        pytest.skip("공고책자 PDF 없음")
    bc = booklet_chunks(load_booklet(booklet, cm.DATA / "cache"))
    stored = {c["chunk_id"]: cm._stored(c) for c in map(json.loads, open(cur, encoding="utf-8"))}
    n = 0
    for c in bc.chunks:
        cond = stored.get(c["chunk_id"])
        if cond:
            n += 1
            src = f"{bc.contexts.get(c['chunk_id'], '')}\n{c['text']}"
            assert cm.fix_conditions(cond, c["reimbursement"].get("stage"), src) == (cond, []), c["chunk_id"]
    assert n > 100


class Assisted(Fake):
    """로컬 모델 흉내: prepare·revise가 있고, 처음 답은 검사에 걸리고 다시 물으면 고쳐 답한다."""
    assisted = True
    label = "ollama:test (sim3)"

    def __init__(self, first, second=GOOD):
        super().__init__(first)
        self.second, self.prepared, self.problems = second, [], None
        self.hint = {}

    def prepare(self, target, pool, previous=()):
        self.prepared.append((target["chunk_id"], [p["chunk_id"] for p in pool], [p["chunk_id"] for p in previous]))
        self.hint = {"examples": [p["chunk_id"] for p in pool], "previous": None, "similarity": 0.3}

    def revise(self, text, context, cond, problems):
        self.problems = problems
        return copy.deepcopy(self.second)


def test_draft_fixes_then_asks_again(tmp_path):
    bad = copy.deepcopy(GOOD)
    bad["all_of"][0]["text"] = "HR 양성"                                 # 원문에 없는 구절
    bad["all_of"][2]["value"] = "5"                                       # 숫자가 아님
    s = Assisted(bad)
    ch = _chunks()
    rep = attach_conditions(ch, {}, structurer=s, cache=Cache(tmp_path / "c.jsonl"))
    assert not rep.rejected and s.problems and any("원문에 없는" in p for p in s.problems)
    assert ch[0]["reimbursement"]["conditions"]["all_of"] == GOOD["all_of"]
    src = rep.sources["row"]
    assert not src["reviewed"] and src["revised"] and src["similarity"] == 0.3 and src["verify"] == []
    # 확인에 걸리면 그 구절이 human_review로 들어간다 (판정은 알 수 없음)
    wrong = copy.deepcopy(GOOD)
    wrong["all_of"][1]["value"] = ["postmenopausal"]                     # '폐경 전'을 폐경 후로
    ch = _chunks()
    rep = attach_conditions(ch, {}, structurer=Assisted(wrong), cache=Cache(tmp_path / "v.jsonl"))
    cond = ch[0]["reimbursement"]["conditions"]
    assert "폐경 전" in cond["human_review"] and rep.sources["row"]["verify"]
    assert cm.review_priority(rep.sources["row"])[0] == 0
    # 다시 물어도 틀리면 버린다 (검사는 그대로)
    rep = attach_conditions(_chunks(), {}, structurer=Assisted(bad, bad), cache=Cache(tmp_path / "d.jsonl"))
    assert "row" in rep.rejected


def test_examples_come_from_reviewed_rows_only(tmp_path):
    """예시 후보는 저장본에서 사람이 넣은(--import) 조건을 쓰는 이번 책자 행. 모델 초안은 넣지 않는다."""
    cache = Cache(tmp_path / "c.jsonl")
    ch = _chunks() + [{**copy.deepcopy(_chunks()[0]), "chunk_id": "row2", "text": TEXT + "\n추가"},
                      {**copy.deepcopy(_chunks()[0]), "chunk_id": "row3", "text": TEXT + "\n초안"}]
    rep = cm.import_conditions({"row": GOOD}, ch, {}, cache, author="담당 D")
    assert rep.saved == ["row"]
    cache.put(cm.cache_key(ch[3]["text"], ""), "row3", GOOD, {}, model="ollama:qwen3:32b (sim3)")
    s = Assisted(GOOD)
    attach_conditions(ch, {}, structurer=s, cache=cache, previous=[{"chunk_id": "old", "text": TEXT}])
    assert s.prepared == [("row2", ["row"], ["old"])]
    assert cm.is_reviewed("담당 D") and not cm.is_reviewed("ollama:qwen3:32b") and not cm.is_reviewed(cm.MODEL)


def test_reviewed_rows_and_find_previous(tmp_path):
    cache = Cache(tmp_path / "c.jsonl")
    old = {"chunk_id": "hira-booklet-20261001-bc-adj-r04", "chunk_kind": "reimbursement_condition", "text": TEXT,
           "drugs": ["anastrozole"], "reimbursement": {"conditions": {**GOOD, "line_rule": {"stage": "adjuvant", "line": None}}}}
    draft_row = {**copy.deepcopy(old), "chunk_id": "hira-booklet-20261001-bc-adj-r05"}
    cache.put("k1", old["chunk_id"], GOOD, {}, model="담당 D")
    cache.put("k2", draft_row["chunk_id"], GOOD, {}, model="ollama:qwen3:32b")
    prev = cm.reviewed_rows([old, draft_row], cache)
    assert [p["chunk_id"] for p in prev] == [old["chunk_id"]] and "line_rule" not in prev[0]["conditions"]
    new = {"chunk_id": "hira-booklet-20261101-bc-adj-r05", "text": TEXT + "\n개정", "drugs": ["anastrozole"]}
    assert cm.find_previous(new, prev)["chunk_id"] == old["chunk_id"]
    assert cm.find_previous({**new, "chunk_id": "hira-booklet-20261101-bc-neo-her2pos-r01"}, prev) is None
    # 원문이 그대로라 저장본에 옛 책자 행 이름으로 남은 조건도 안내를 알면 해시로 찾는다
    cache.put(cm.cache_key(TEXT, "[안내]"), "hira-booklet-20260901-bc-adj-r04", GOOD, {}, model="담당 C")
    assert cm.reviewed_rows([{**old, "chunk_id": "hira-booklet-20261001-bc-adj-r09"}], cache,
                            {"hira-booklet-20261001-bc-adj-r09": "[안내]"})[0]["author"] == "담당 C"
    assert cm.reviewed_rows([{**old, "chunk_id": "hira-booklet-20261001-bc-adj-r09"}], cache) == []
    assert cm.row_group("hira-booklet-20261101-supp-gcsf-b1") == "supp-gcsf"
    assert cm.row_group("hira-booklet-20261101-bc-pal-endo-1l-r01") == "bc-pal-endo-1l"


def _carry_case(tmp_path, new_text, old_ctx="[안내]", new_ctx="[안내]"):
    """이전 책자 행(검수됨)과 새 책자 행 하나로 attach_conditions를 돌린다."""
    cache = Cache(tmp_path / "c.jsonl")
    old = {"chunk_id": "hira-booklet-20261001-bc-adj-r04", "chunk_kind": "reimbursement_condition", "text": TEXT,
           "drugs": ["anastrozole"], "reimbursement": {"conditions": copy.deepcopy(GOOD)}}
    cache.put("k1", old["chunk_id"], GOOD, {}, model="담당 D")
    prev = cm.reviewed_rows([old], cache, None if old_ctx is None else {old["chunk_id"]: old_ctx})
    ch = _chunks()
    ch[0].update(chunk_id="hira-booklet-20261101-bc-adj-r04", text=new_text, drugs=["anastrozole"])
    fake = Fake()
    rep = attach_conditions(ch, {ch[0]["chunk_id"]: new_ctx}, structurer=fake, cache=cache, previous=prev)
    return rep, fake, ch[0], cache


def test_same_content_row_is_carried_without_model(tmp_path):
    """원문이 문장부호만 다르면 모델에 묻지 않고 검수된 조건을 옮긴다. 구절은 새 원문 표기로 맞춘다."""
    new_text = TEXT.replace("‘LHRH agonist‘", "'LHRH agonist'").replace("① 40세 미만", "1. 40세 미만.")
    rep, fake, c, cache = _carry_case(tmp_path, new_text)
    assert fake.calls == 0 and rep.carried == [c["chunk_id"]] and not rep.rejected
    cond = c["reimbursement"]["conditions"]
    assert cond["notes"] == ["'LHRH agonist'는 4주 간격의 goserelin과 leuprolide만 인정함"]
    assert cond["all_of"] == GOOD["all_of"] and cond["line_rule"] == {"stage": "adjuvant", "line": None}
    assert check_grounding(cond, new_text) == []
    src = rep.sources[c["chunk_id"]]
    assert src["reviewed"] and src["carried_from"] == "hira-booklet-20261001-bc-adj-r04"
    assert src["model"] == "담당 D (이전 판에서 옮김)" and cm.review_priority(src)[0] == 4
    # 다음 책자에서 또 옮겨도 표시는 하나
    nxt = {**c, "chunk_kind": "reimbursement_condition"}
    assert cm.reviewed_rows([nxt], cache, {c["chunk_id"]: "[안내]"})[0]["author"] == "담당 D (이전 판에서 옮김)"


def test_renumbered_row_is_carried(tmp_path):
    """앞에 행이 생겨 자기 연번만 밀린 행 (11-01 책자 병용요법 21~31)."""
    rep, fake, c, _ = _carry_case(tmp_path, TEXT.replace("연번 4", "연번 5"))
    assert fake.calls == 0 and rep.carried == [c["chunk_id"]]
    assert cm._without_own_no("[40. 병용요법 > 유방암 > 연번 21]\n연번 21\n연번 20∼24 관련") == \
        "[40. 병용요법 > 유방암 > ]\n\n연번 20∼24 관련"


@pytest.mark.parametrize("new_text, old_ctx, new_ctx", [
    (TEXT.replace("40세 미만", "35세 미만"), "[안내]", "[안내]"),       # 본문 내용이 바뀜
    (TEXT.replace("2∼3", "3"), "[안내]", "[안내]"),
    (TEXT, "[안내]", "[안내] 새 머리 규칙"),                             # 소단원 안내가 바뀜
    (TEXT, None, "[안내]"),                                              # 이전 판 안내를 모름
])
def test_changed_row_goes_to_model(tmp_path, new_text, old_ctx, new_ctx):
    rep, fake, c, _ = _carry_case(tmp_path, new_text, old_ctx, new_ctx)
    assert fake.calls == 1 and rep.carried == []


def test_same_content_ignores_only_spacing_and_punctuation():
    assert cm.same_content("① 40세 미만 (5년).", "1 40세미만 5년")
    assert not cm.same_content("직경 > 2㎝", "직경 2cm")
    assert not cm.same_content("2∼3년", "23년")


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


def _enums(node, key, out=None):
    """스키마 안에서 key 속성에 붙은 enum 값 목록들 ($ref 정의 안까지)."""
    out = [] if out is None else out
    if isinstance(node, dict):
        prop = node.get("properties", {}).get(key)
        if isinstance(prop, dict) and "enum" in prop:
            out.append({v for v in prop["enum"] if v is not None})
        for v in node.values():
            _enums(v, key, out)
    elif isinstance(node, list):
        for v in node:
            _enums(v, key, out)
    return out


def test_fields_follow_team_terms_dictionary():
    """공고 표현 -> 칸·값은 팀 사전 data/dictionaries/reimbursement_terms.csv를 따른다."""
    path = cm.ROOT / "data" / "dictionaries" / "reimbursement_terms.csv"
    if not path.exists():
        pytest.skip("reimbursement_terms.csv 없음")
    with open(path, encoding="utf-8") as f:
        terms = {r["notice_term"]: r for r in csv.DictReader(f)}
    split = lambda s: [x.strip().split(" ")[0] for x in s.split("|")]          # noqa: E731
    # HER2 값은 B의 biomarker_record 값 (canonical = B). 사전의 zero는 B가 쓰지 않아 뺀다
    schema = json.loads((cm.ROOT / "schemas" / "biomarker_record.json").read_text(encoding="utf-8"))
    b_status = next(s for s in _enums(schema, "status") if "ultralow" in s)     # records[].status (마커 판정값)
    assert set(cm.FIELDS["her2"][2]) <= b_status and "zero" not in b_status | set(cm.FIELDS["her2"][2])
    assert set(split(terms["HER2 음성"]["json_value"])) - {"zero"} <= set(cm.FIELDS["her2"][2])
    # 림프절 양성·음성은 N 병기. 사전은 병리 N이고, 선행요법 행은 임상 N을 따로 둔다 (A draft7 체크리스트 §4)
    assert "stage.ptnm.value.n" in cm.FIELDS["pn_status"][0] and "stage.ctnm.value.n" in cm.FIELDS["cn_status"][0]
    assert terms["림프절 양성"]["json_field"] == "stage.ptnm.n"
    # 국소진행성·전이성: 값은 사전(stage.disease_extent)과 같고, 칸은 재발 후 상태까지 담은 setting.disease
    # (스키마 설명 "재발 후 상태는 biomarker_record.setting.disease")
    assert terms["전이성"]["json_field"] == "stage.disease_extent"
    assert terms["전이성"]["json_value"] in cm.FIELDS["disease"][2]
    assert cm.FIELDS["disease"][0].startswith("biomarker_record.setting.disease")
    assert "duration_days" in cm.FIELDS["treatment_years"][0]
    assert terms["투여기간"]["json_field"] == "treatment_history[].duration_days"
    # 고식적 = treatment_history.setting metastatic (JSON에 palliative 값 없음)
    assert terms["고식적 (palliative)"]["json_value"] == "metastatic"
    assert cm._OF["properties"]["setting"]["items"]["enum"] == ["neoadjuvant", "adjuvant", "metastatic"]


def test_fields_follow_input_paths():
    """A의 data_needs_by_module (2026-10-20) §4·§6: 나이 기준, 최근 4주 투약, 실패 근거."""
    assert cm.FIELDS["age"][0].startswith("patient_state.fields.patient.age")
    assert cm.FIELDS["age_at_index"][0].startswith("patient_state.fields.at_index.age")
    assert "at_index.recent_therapy_28d" in cm.FIELDS["recent_therapy_28d"][0]
    assert cm.FIELDS["recent_therapy_28d"][2] == ["yes", "no"]
    assert "days_since_last_dose" not in cm.FIELDS
    assert "best_response = PD" in cm.FIELDS["prior_failed"][0]
    # A 답변 2026-10-21: 재발 병소 절제 가능 여부는 재발 후 수술 여부로 대신
    assert "recurrence.surgery" in cm.FIELDS["recurrence_operable"][0] and "curative" in cm.FIELDS["recurrence_operable"][0]
    # 2026-10-22 칸 추가로 심장·종격동 제외 조항을 없앴다 (draft7 체크리스트 §3.1)
    assert cm.FIELDS["cardiac_history"][0].startswith("patient_state.fields.patient.cardiac_history.value")
    assert cm.FIELDS["mediastinal_radiation"][0].startswith("patient_state.fields.patient.mediastinal_radiation.value")
    assert "imaging_findings" in cm.FIELDS["bone_metastasis"][0] and "confirmed" in cm.FIELDS["bone_metastasis"][0]
    assert "doses[]" in cm.FIELDS["cumulative_dose_mg_m2"][0] and "height_cm" in cm.FIELDS["cumulative_dose_mg_m2"][0]
    assert "Mosteller" in cm.FIELDS["cumulative_dose_mg_m2"][0]                  # B 제안, D 동의 2026-10-29
    assert "per_admin" in cm.FIELDS["per_admin_dose_mg_m2"][0]                  # sodium thiosulfate '1 cycle당 100㎎/㎡ 이상'
    # patient_state_structure.md: 공통 추출 칸(◆)은 값이 .value 아래
    for f in ("menopause", "sex", "age", "recurrence", "operable", "stage_group", "positive_ln_count", "grade", "pcr",
              "days_end_to_recurrence", "days_end_to_metastasis"):
        assert ".value" in cm.FIELDS[f][0], f


def test_stage_fields_by_treatment_timing():
    """치료 시기별 병기 (draft7 체크리스트 §4): 선행은 임상, 보조는 병리. 크기는 T 범주가 아니라 mm. 칸은 patient_state에 있다."""
    assert "t_stage" not in cm.FIELDS and "ln_status" not in cm.FIELDS
    schema = json.loads((cm.ROOT / "schemas" / "patient_state.json").read_text(encoding="utf-8"))
    stage = schema["properties"]["fields"]["properties"]["stage"]["properties"]
    patient = schema["properties"]["fields"]["properties"]["patient"]["properties"]
    for f, where in [("ct_stage", "ctnm"), ("cn_status", "ctnm"), ("pt_stage", "ptnm"), ("pn_status", "ptnm"),
                     ("clinical_size_mm", "clinical_size_mm"), ("pathologic_size_mm", "pathologic_size_mm")]:
        assert f"stage.{where}.value" in cm.FIELDS[f][0] and where in stage, f
    for f in ("cardiac_history", "mediastinal_radiation", "height_cm", "weight_kg"):
        assert f in patient, f
    assert cm.FIELDS["clinical_size_mm"][2] == cm._NUM and "gt 20" in cm.FIELDS["clinical_size_mm"][3]
    # 보조 행은 수술 병리 병기: 선행요법 뒤 수술이면 yptnm (§4 표 '선행요법 뒤 보조')
    yp = schema["$defs"]["yptnm_value"]["properties"]
    assert "yptnm" in stage and {"t", "n", "residual_size_mm"} <= set(yp)
    assert "stage.yptnm.value.t" in cm.FIELDS["pt_stage"][0] and "stage.yptnm.value.n" in cm.FIELDS["pn_status"][0]
    assert "yptnm.value.residual_size_mm" in cm.FIELDS["pathologic_size_mm"][0]


def test_prompt_lists_every_field():
    for k in cm.FIELDS:
        assert f"- {k}:" in cm.SYSTEM
