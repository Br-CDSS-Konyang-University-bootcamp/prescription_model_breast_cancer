"""[4] LLM 추천 진입점: 프롬프트 → LLM → 후처리 → 형식 검사 (PROJECT.md §7, §15.5).

검색과 LLM은 넘겨받기만 한다 (CLAUDE.md: 모듈끼리는 schemas/ 형식으로만 주고받는다).
- guideline_chunks, reimbursement_chunks: schemas/chunk.json 형식 목록 (C의 검색 결과, D의 급여 청크)
- llm: 함수 (프롬프트 글) -> 답 사전 또는 답 글(JSON). 로컬 모델만 쓴다. llm_link.make_llm()이 llm/ 공용 인터페이스로 만든다.
  함수에 prompt_budget(토큰) 속성이 있으면 질문지를 그 안에 맞춘다 (make_llm은 num_ctx - max_tokens로 붙인다)
- index_status: 화면 하단 요약 (D 제공, schemas/recommendation.json)
"""
import json
import re
from datetime import date, datetime

from llm import LLMOutputError
from src.recommend.clinical_notes import _confirmed, clinical_notes
from src.recommend.postprocess import postprocess
from src.recommend.prompt import fit_prompt
from src.recommend.validate import validate

SCHEMA_VERSION = "0.1-draft"


def _parse(text):
    """LLM 답에서 JSON만 꺼낸다. 앞뒤 설명이나 ``` 묶음이 있어도 첫 { 부터 마지막 } 까지 읽는다."""
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end < start:
        raise ValueError("JSON 없음")
    return json.loads(text[start:end + 1])


def _merge_tests(llm_tests, bm_tests):
    """바이오마커 모듈의 검사 공백을 먼저 두고, LLM이 낸 검사를 이어 붙인다 (같은 검사는 한 번)."""
    out, seen = [], set()
    for t in list(bm_tests or []) + list(llm_tests or []):
        if t.get("test") in seen:
            continue
        seen.add(t.get("test"))
        out.append({k: t[k] for k in ("test", "reason", "blocks_therapy") if k in t})
    return out


RETRY_NOTE = """[다시 쓰기] 앞의 답에서 남은 후보가 없다. 근거 문장(rationale)의 각 문장 끝에 [지침 청크 ID]가 없었거나,
받지 않은 ID를 인용했거나, 인용한 지침 청크에 그 약이 없었다. 같은 형식으로 다시 답한다.
rationale의 모든 문장 끝에 아래 지침 청크 ID 중 그 문장의 근거인 것을 [ ] 안에 그대로 붙이고, citations에도 같은 ID를 적는다.
급여 청크 ID만으로는 근거가 되지 않는다. 쓸 수 있는 지침 청크 ID: {ids}"""


def _answer_counts(options, guide_ids):
    """LLM이 낸 주 후보를 내용 없이 숫자로만 적는다 (A 공유 2026-11-05 B-2). 실제 환자로 보고 답 원문은 남기지 않는다
    (사용자 결정 2026-11-05). 무엇 때문에 지워졌는지는 이 숫자와 후처리 로그로 본다."""
    cite_re = re.compile(r"\[([A-Za-z0-9_.:\-]+)\]")
    no_field = sum(1 for o in options if not o.get("citations"))
    no_inline = sum(1 for o in options if not cite_re.search(o.get("rationale") or ""))
    no_guide = sum(1 for o in options
                   if not ({*(o.get("citations") or []), *cite_re.findall(o.get("rationale") or "")} & guide_ids))
    return (f"LLM 답: 주 후보 {len(options)}개, citations 칸이 빈 후보 {no_field}개, "
            f"근거 문장에 [ID]가 없는 후보 {no_inline}개, 받은 지침 청크 ID를 하나도 인용하지 않은 후보 {no_guide}개")


def _phase_and_bone(patient_state, biomarker_record, confirmed_state):
    """8번 보조 약물 규칙에 쓸 (치료 단계, 뼈 전이 여부). 의사 확정값을 먼저 보고, 없으면 B 판정·patient_state."""
    setting = biomarker_record.get("setting") or {}
    phase = _confirmed(confirmed_state, "setting.phase")
    if phase not in ("neoadjuvant", "adjuvant"):
        phase = setting.get("line") if setting.get("line") in ("neoadjuvant", "adjuvant") else None
    sites = _confirmed(confirmed_state, "metastatic_sites")
    if sites is None:
        field = (((patient_state or {}).get("fields") or {}).get("recurrence") or {}).get("metastatic_sites") or {}
        sites = field.get("value") if field.get("status") == "present" else None
    bone = setting.get("disease") == "metastatic" and isinstance(sites, list) and "bone" in sites
    return phase, bone


def recommend(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, llm, index_status,
              model_name, today=None, conditions_checker=None, confirmed_state=None):
    """환자 한 명 -> (recommendation, 후처리 로그, 형식 오류 목록). 형식 오류가 비어 있어야 쓸 수 있다.
    질문지 길이 때문에 뺀 지침 청크는 후처리에서도 받지 않은 청크로 본다. 급여 청크는 후처리에 모두 넘긴다.
    confirmed_state(화면 1 의사 확정값)를 주면 참고란에 장기 위기·금기 계열을 의사 확정값으로 넣는다."""
    today = today or date.today()
    base = {"schema_version": SCHEMA_VERSION, "patient_ref": biomarker_record.get("patient_ref"),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "model": model_name,
            "index_status": index_status}
    # 질문지 길이 때문에 뺀 지침 청크는 후처리에서도 받지 않은 청크로 본다 (모델이 보지 못한 근거는 인용할 수 없음).
    # 급여 청크는 빼더라도 후처리에는 모두 넘긴다. 5번 규칙이 약이 맞는 급여 행을 규칙으로 붙이는데, 질문지에서 빠진
    # 행까지 버리면 맞는 행이 있어도 '급여 기준 없음'이 된다 (D 확인 2026-11-04, VC-0101 fulvestrant 단독의 r06)
    all_reimbursement = list(reimbursement_chunks or [])
    prompt, guideline_chunks, _, log = fit_prompt(
        patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, getattr(llm, "prompt_budget", None),
        confirmed_state)
    reimbursement_chunks = all_reimbursement
    phase, bone = _phase_and_bone(patient_state, biomarker_record, confirmed_state)
    guide_ids = [c["chunk_id"] for c in guideline_chunks]

    def ask(text):
        """LLM에 한 번 묻고 후처리까지. (후처리 결과, LLM이 낸 주 후보 수)."""
        try:
            answer = llm(text)
            raw = answer if isinstance(answer, dict) else _parse(answer)   # llm_link는 사전, 글로 답하는 함수는 글
        except (ValueError, LLMOutputError) as e:
            raw = {"options": [], "out_of_scope": True, "out_of_scope_reason": f"LLM 답을 읽을 수 없음 ({e})"}
            log.append(raw["out_of_scope_reason"])
        rec = {"options": raw.get("options") or [], "supportive_options": raw.get("supportive_options") or [],
               "tests_needed": raw.get("tests_needed") or [],
               "out_of_scope": bool(raw.get("out_of_scope")), "out_of_scope_reason": raw.get("out_of_scope_reason"),
               "conflicts": raw.get("conflicts") or []}
        if not rec["options"] and not rec["out_of_scope"]:
            log.append("LLM이 후보를 내지 않음 (out_of_scope도 false)")   # A 전달 §5.3 VC-0126
        log.append(_answer_counts(rec["options"], set(guide_ids)))
        out, post_log = postprocess(rec, biomarker_record, guideline_chunks, reimbursement_chunks, today,
                                    conditions_checker, phase=phase, bone_metastasis=bone,
                                    high_risk_early=_confirmed(confirmed_state, "high_risk_early"))
        log.extend(post_log)
        return out, len(rec["options"])

    rec, asked = ask(prompt)
    # LLM이 낸 주 후보가 후처리에서 모두 지워지면 한 번만 다시 묻는다. 무엇이 빠졌는지와 쓸 수 있는 지침 청크 ID를
    # 콕 집어 알려 준다 (A 공유 2026-11-05 B-1: 근거 문장에 [청크ID]가 없어 6건이 빈 결과). 다시 온 답도 같은 후처리를 거친다
    if asked and not rec["options"]:
        log.append("주 후보가 모두 지워져 LLM에 한 번 다시 물음")
        rec, _ = ask(prompt + "\n\n" + RETRY_NOTE.format(ids=", ".join(guide_ids)))
    rec["tests_needed"] = _merge_tests(rec["tests_needed"], biomarker_record.get("tests_needed"))
    rec["clinical_notes"] = clinical_notes(patient_state, rec["options"], guideline_chunks, confirmed_state)
    result = {**base, **rec}
    return result, log, validate(result)
