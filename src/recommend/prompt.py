"""[4] LLM 프롬프트 만들기 (PROJECT.md §7 프롬프트 입력).

넣는 것: 구조화된 환자 상태(차트 원문·인용은 넣지 않음), 바이오마커 상태값과 판정 이유, 검사 공백,
지침 청크(부모 소단원 포함, 출처·버전·쪽·근거 수준), 급여 청크(공고 번호·시행일).
로컬 모델에만 넘긴다 (CLAUDE.md: 환자 차트는 외부 API로 보내지 않는다).
"""
import json

INSTRUCTIONS = """너는 유방암 처방 후보를 정리하는 도우미다. 아래 규칙을 지킨다.
1. 아래 [지침 청크]와 [급여 청크]에 있는 내용만 쓴다. 청크에 없는 약, 수치, 근거는 쓰지 않는다.
2. rationale의 모든 문장 끝에 근거 청크 ID를 [청크ID] 형식으로 붙인다. 예: "PIK3CA 변이 환자에게 권고된다 [esmo-mbc-2026-05-luminal-2l-49918b]."
3. 바이오마커 판정은 [바이오마커]의 상태값을 그대로 따른다. 바꾸거나 새로 판정하지 않는다.
4. 바이오마커가 not_done·not_recorded·unknown·retest_needed이면 그 바이오마커가 필요한 치료는 추천하지 말고 tests_needed에 적는다.
5. reimbursement: 급여 청크의 조건이 모두 확인되면 covered, 급여 청크는 있지만 조건을 다 확인할 수 없으면 covered_conditions_unverified,
   허가초과 인정 청크와 맞으면 offlabel_approved, 둘 다 없으면 no_criteria. no_criteria를 "비급여"로 단정하지 않는다.
6. 지침 청크로 답할 수 없으면 options를 비우고 out_of_scope를 true로, out_of_scope_reason에 이유를 적는다.
7. 아래 JSON 형식으로만 답한다. 다른 글은 쓰지 않는다."""

OUTPUT_FORMAT = """{"options": [{"therapy": "", "drugs": [""], "rationale": "", "evidence": "LoE I, GoR A",
  "citations": ["지침 청크 ID"], "reimbursement": "covered | covered_conditions_unverified | offlabel_approved | no_criteria",
  "reimbursement_reason": "충족한 조건 또는 빠진 조건", "reimbursement_citations": ["급여 청크 ID"]}],
 "tests_needed": [{"test": "", "reason": ""}], "out_of_scope": false, "out_of_scope_reason": null, "conflicts": []}"""


def _value(field):
    """patient_state 칸에서 값만. 기록 없음·미시행은 상태 그대로."""
    if not isinstance(field, dict):
        return field
    return field.get("value") if field.get("status") == "present" else field.get("status")


def patient_summary(patient_state, biomarker_record):
    """프롬프트에 넣을 환자 요약 (구조화 값만, 원문 인용 없음)."""
    f = (patient_state or {}).get("fields") or {}
    setting = biomarker_record.get("setting") or {}
    return {
        "subtype": biomarker_record.get("subtype"),
        "disease": setting.get("disease"),
        "line": setting.get("line"),
        "line_reason": setting.get("reason"),
        "prior_drug_classes": setting.get("prior_drug_classes") or [],
        "menopausal_status": _value((f.get("patient") or {}).get("menopausal_status")),
        "histology": _value((f.get("diagnosis") or {}).get("histology")),
        "metastatic_sites": _value((f.get("recurrence") or {}).get("metastatic_sites")),
        "treatment_history": [{"drugs": t.get("drugs"), "setting": t.get("setting"), "line": t.get("line"),
                               "best_response": t.get("best_response"), "stop_reason": t.get("stop_reason")}
                              for t in f.get("treatment_history") or []],
    }


def _chunk_block(c):
    head = (f"[{c['chunk_id']}] {c.get('source')} {c.get('version')} · {c.get('section')} · "
            f"p.{c.get('page_start')}")
    ev = c.get("evidence") or {}
    if ev.get("loe") or ev.get("gor"):
        head += f" · LoE {ev.get('loe')}, GoR {ev.get('gor')}"
    r = c.get("reimbursement") or {}
    if r:
        head += f" · 공고 {r.get('notice_no')} 시행 {r.get('effective_from')} ({r.get('source_type')})"
    lines = [head, c.get("text") or ""]
    if c.get("parent"):
        lines.append(f"(소단원 [{c['parent']['chunk_id']}]) {c['parent'].get('text') or ''}")
    return "\n".join(lines)


def build_prompt(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks):
    """LLM에 넘길 글 한 덩어리."""
    records = [{"marker": r["marker"], "status": r["status"], "reason": r["reason"]}
               for r in biomarker_record.get("records") or []]
    parts = [
        INSTRUCTIONS,
        "[환자]\n" + json.dumps(patient_summary(patient_state, biomarker_record), ensure_ascii=False),
        "[바이오마커]\n" + json.dumps(records, ensure_ascii=False),
        "[검사 공백]\n" + json.dumps(biomarker_record.get("tests_needed") or [], ensure_ascii=False),
        "[지침 청크]\n" + ("\n\n".join(_chunk_block(c) for c in guideline_chunks) or "(없음)"),
        "[급여 청크]\n" + ("\n\n".join(_chunk_block(c) for c in reimbursement_chunks or []) or "(없음)"),
        "[출력 형식]\n" + OUTPUT_FORMAT,
    ]
    return "\n\n".join(parts)
