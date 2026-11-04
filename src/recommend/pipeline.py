"""[4] LLM 추천 진입점: 프롬프트 → LLM → 후처리 → 형식 검사 (PROJECT.md §7, §15.5).

검색과 LLM은 넘겨받기만 한다 (CLAUDE.md: 모듈끼리는 schemas/ 형식으로만 주고받는다).
- guideline_chunks, reimbursement_chunks: schemas/chunk.json 형식 목록 (C의 검색 결과, D의 급여 청크)
- llm: 함수 (프롬프트 글) -> 답 사전 또는 답 글(JSON). 로컬 모델만 쓴다. llm_link.make_llm()이 llm/ 공용 인터페이스로 만든다.
  함수에 prompt_budget(토큰) 속성이 있으면 질문지를 그 안에 맞춘다 (make_llm은 num_ctx - max_tokens로 붙인다)
- index_status: 화면 하단 요약 (D 제공, schemas/recommendation.json)
"""
import json
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
    질문지 길이 때문에 뺀 청크는 후처리에서도 받지 않은 청크로 본다 (모델이 보지 못한 청크를 인용할 수 없으므로).
    confirmed_state(화면 1 의사 확정값)를 주면 참고란에 장기 위기·금기 계열을 의사 확정값으로 넣는다."""
    today = today or date.today()
    base = {"schema_version": SCHEMA_VERSION, "patient_ref": biomarker_record.get("patient_ref"),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "model": model_name,
            "index_status": index_status}
    prompt, guideline_chunks, reimbursement_chunks, log = fit_prompt(
        patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, getattr(llm, "prompt_budget", None))
    try:
        answer = llm(prompt)
        raw = answer if isinstance(answer, dict) else _parse(answer)   # llm_link는 사전, 글로 답하는 함수는 글
    except (ValueError, LLMOutputError) as e:
        raw = {"options": [], "out_of_scope": True, "out_of_scope_reason": f"LLM 답을 읽을 수 없음 ({e})"}
        log.append(raw["out_of_scope_reason"])
    rec = {"options": raw.get("options") or [], "supportive_options": raw.get("supportive_options") or [],
           "tests_needed": raw.get("tests_needed") or [],
           "out_of_scope": bool(raw.get("out_of_scope")), "out_of_scope_reason": raw.get("out_of_scope_reason"),
           "conflicts": raw.get("conflicts") or []}
    phase, bone = _phase_and_bone(patient_state, biomarker_record, confirmed_state)
    rec, post_log = postprocess(rec, biomarker_record, guideline_chunks, reimbursement_chunks, today,
                                conditions_checker, phase=phase, bone_metastasis=bone)
    log += post_log
    rec["tests_needed"] = _merge_tests(rec["tests_needed"], biomarker_record.get("tests_needed"))
    rec["clinical_notes"] = clinical_notes(patient_state, rec["options"], guideline_chunks, confirmed_state)
    result = {**base, **rec}
    return result, log, validate(result)
