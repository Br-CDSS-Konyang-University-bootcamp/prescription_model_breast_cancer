"""[4] LLM 프롬프트 만들기 (PROJECT.md §7 프롬프트 입력).

넣는 것: 구조화된 환자 상태(차트 원문·인용은 넣지 않음), 바이오마커 상태값과 판정 이유, 검사 공백,
지침 청크(출처·버전·쪽·근거 수준), 지침 소단원(같은 소단원은 한 번만), 급여 청크(공고 번호·시행일).
급여 청크의 소단원 본문은 넣지 않는다 (ID만). 급여 조건은 LLM이 아니라 conditions_eval.py가 판정하고,
같은 소단원이 행마다 반복되어 질문지가 문맥을 넘었기 때문이다 (A 전달 handoff_recommend_prompt_to_B_2026-11-02.md,
VC-0103 질문지 81,998자 중 급여 소단원 56,917자).
질문지가 모델 문맥(num_ctx - max_tokens)을 넘으면 Ollama가 앞부분(지시문·환자)을 버리므로, fit_prompt()가
뒤쪽 청크부터 빼서 맞춘다. 로컬 모델에만 넘긴다 (CLAUDE.md: 환자 차트는 외부 API로 보내지 않는다).
"""
import json
import re

INSTRUCTIONS = """너는 유방암 처방 후보를 정리하는 도우미다. 아래 규칙을 지킨다.
1. 아래 [지침 청크]와 [급여 청크]에 있는 내용만 쓴다. 청크에 없는 약, 수치, 근거는 쓰지 않는다.
2. rationale의 모든 문장 끝에 근거 청크 ID를 [청크ID] 형식으로 붙인다. 예: "PIK3CA 변이 환자에게 권고된다 [esmo-mbc-2026-05-luminal-2l-49918b]."
   [ID]가 없는 문장은 지워지고, 남은 문장이 없는 후보는 통째로 지워진다. citations 칸에만 적는 것으로는 부족하다.
   근거는 [지침 청크]의 ID로 단다. [급여 청크]의 ID만으로는 근거가 되지 않는다.
   청크 ID는 [지침 청크]·[급여 청크]의 대괄호 안 ID를 그대로 쓴다. [지침 소단원]의 ID는 인용하지 않는다.
   [지침 청크]는 이 환자와 관련이 높은 순서로 놓여 있으니 앞의 청크부터 확인한다.
3. 바이오마커 판정은 [바이오마커]의 상태값을 그대로 따른다. 바꾸거나 새로 판정하지 않는다.
4. 바이오마커가 not_done·not_recorded·unknown·retest_needed이면 그 바이오마커가 필요한 치료는 추천하지 말고 tests_needed에 적는다.
5. reimbursement: 급여 청크의 조건이 모두 확인되면 covered, 급여 청크는 있지만 조건을 다 확인할 수 없으면 covered_conditions_unverified,
   허가초과 인정 청크와 맞으면 offlabel_approved, 둘 다 없으면 no_criteria. no_criteria를 "비급여"로 단정하지 않는다.
6. [지침 청크]에 이 환자에게 맞는 요법이 여러 개 있으면 요법마다 후보를 하나씩 쓴다 (최대 5개). 같은 요법을 두 번 쓰지 않는다.
   drugs에는 그 요법의 약 일반명을 모두 쓰고, evidence에는 인용한 지침 청크의 LoE·GoR를 그대로 쓴다.
7. [환자]의 disease·line에 맞는 치료만 쓴다. 예: metastatic 환자에게 수술전·수술후보조요법을 쓰지 않는다.
8. 골 보호제(denosumab, zoledronic acid, pamidronate, ibandronate, clodronate, bisphosphonate)는 options에 넣지 않고
   supportive_options(함께 처방할 보조 약물)에만 쓴다. 뼈 전이 환자의 골 보호제 권고나 수술 후 보조요법 단계의 bisphosphonate 권고가
   [지침 청크]에 있으면 주 처방과 상관없이 supportive_options에 쓴다. 수술 전(선행요법) 결정에는 쓰지 않는다.
9. 지침 청크로 답할 수 없으면 options를 비우고 out_of_scope를 true로, out_of_scope_reason에 이유를 적는다.
10. 아래 JSON 형식으로만 답한다. 다른 글은 쓰지 않는다."""

OUTPUT_FORMAT = """{"options": [{"therapy": "", "drugs": [""], "rationale": "", "evidence": "LoE I, GoR A",
  "citations": ["지침 청크 ID"], "reimbursement": "covered | covered_conditions_unverified | offlabel_approved | no_criteria",
  "reimbursement_reason": "충족한 조건 또는 빠진 조건", "reimbursement_citations": ["급여 청크 ID"]}],
 "supportive_options": [{"therapy": "골 보호제 이름", "drugs": [""], "rationale": "", "evidence": "", "citations": ["지침 청크 ID"],
  "reimbursement": "", "reimbursement_reason": "", "reimbursement_citations": []}],
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
    if c.get("parent"):
        head += f" · 소단원 [{c['parent']['chunk_id']}]"
    return "\n".join([head, c.get("text") or ""])


def _parent_blocks(chunks):
    """지침 청크의 소단원 본문. 같은 소단원은 한 번만 (A 전달 §6 1번)."""
    out, seen = [], set()
    for c in chunks:
        p = c.get("parent") or {}
        if p.get("chunk_id") and p["chunk_id"] not in seen:
            seen.add(p["chunk_id"])
            out.append(f"[{p['chunk_id']}]\n{p.get('text') or ''}")
    return out


def build_prompt(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks):
    """LLM에 넘길 글 한 덩어리."""
    records = [{"marker": r["marker"], "status": r["status"], "reason": r["reason"]}
               for r in biomarker_record.get("records") or []]
    parents = _parent_blocks(guideline_chunks)
    parts = [
        INSTRUCTIONS,
        "[환자]\n" + json.dumps(patient_summary(patient_state, biomarker_record), ensure_ascii=False),
        "[바이오마커]\n" + json.dumps(records, ensure_ascii=False),
        "[검사 공백]\n" + json.dumps(biomarker_record.get("tests_needed") or [], ensure_ascii=False),
        "[지침 청크]\n" + ("\n\n".join(_chunk_block(c) for c in guideline_chunks) or "(없음)"),
    ]
    if parents:
        parts.append("[지침 소단원] (지침 청크의 앞뒤 문맥. 인용은 지침 청크 ID로 한다)\n" + "\n\n".join(parents))
    parts += [
        "[급여 청크]\n" + ("\n\n".join(_chunk_block(c) for c in reimbursement_chunks or []) or "(없음)"),
        "[출력 형식]\n" + OUTPUT_FORMAT,
    ]
    return "\n\n".join(parts)


# 토큰 수 어림: 한글·한자는 글자당 1토큰, 그 밖(영문·숫자·기호·공백)은 3글자당 1토큰.
# 모델 토크나이저 없이 넉넉하게 잡는다. 실제로는 이보다 적게 나오는 편이다
_WIDE_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3\u4e00-\u9fff]")
SAFETY_TOKENS = 256   # 어림 오차 여유 (어림 자체가 실제보다 10% 안팎 많게 나와 작게 둠)


def estimate_tokens(text):
    wide = len(_WIDE_RE.findall(text or ""))
    return wide + (len(text or "") - wide + 2) // 3


def fit_prompt(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, budget=None):
    """질문지가 budget(토큰) 안에 들도록 뒤쪽 청크부터 뺀다 (A 전달 §6 2번, 잘린 채로 조용히 돌지 않게).
    급여 청크를 뒤에서부터 먼저 빼고, 그래도 넘으면 지침 청크를 뒤에서부터 뺀다 (지침 청크는 1개는 남긴다).
    돌려주는 것: (질문지, 넣은 지침 청크, 넣은 급여 청크, 로그). budget이 없으면 자르지 않는다."""
    guide, reimb = list(guideline_chunks or []), list(reimbursement_chunks or [])
    prompt = build_prompt(patient_state, biomarker_record, guide, reimb)
    log = []
    if not budget:
        return prompt, guide, reimb, log
    limit = budget - SAFETY_TOKENS
    dropped = []
    while estimate_tokens(prompt) > limit and (reimb or len(guide) > 1):
        dropped.append((reimb or guide).pop()["chunk_id"])
        prompt = build_prompt(patient_state, biomarker_record, guide, reimb)
    if dropped:
        log.append(f"질문지 길이 제한({budget}토큰)으로 청크 {len(dropped)}개 뺌: {', '.join(reversed(dropped))}")
    if estimate_tokens(prompt) > limit:
        log.append(f"경고: 청크를 빼도 질문지가 길이 제한을 넘음 (어림 {estimate_tokens(prompt)}토큰 > {limit})")
    return prompt, guide, reimb, log
