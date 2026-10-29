"""참고란 (recommendation.json clinical_notes). 제안서 proposal_clinical_notes_2026-10-29.md, 팀 확정 2026-10-29.

동반질환·ECOG·장기 위기·의사가 확정한 금기 계열과 관련 지침 청크 ID를 보여 주기만 한다.
후보를 빼거나 급여 분류를 바꾸지 않고, LLM이 쓰지 않는다. 지침 원문 문장은 옮기지 않는다.
동반질환별로 어떤 약을 못 쓰는지 정한 근거 문서가 없어 판단은 의사에게 맡긴다 (A 선택지 (3), 2026-10-29).
"""
from src.recommend.conditions_eval import _drug_classes, _present

# 동반질환·PS 때문에 CDK4/6·항HER2를 못 쓸 때의 ESMO 권고 청크 (A 답 2026-10-29, C가 동반질환 질의로 찾는 청크)
COMORBIDITY_CHUNKS = ("esmo-mbc-2026-05-luminal-1l-e03e88", "esmo-mbc-2026-05-her2-1l-2cded5",
                      "esmo-mbc-2026-05-her2-1l-58a1c0")


def _confirmed(confirmed_state, key):
    item = ((confirmed_state or {}).get("items") or {}).get(key)
    return item.get("confirmed") if isinstance(item, dict) else None


def _note(topic, text, source_fields, citations=(), applies_to=()):
    out = {"topic": topic, "text": text, "source_fields": list(source_fields)}
    if citations:
        out["citations"] = list(citations)
    if applies_to:
        out["applies_to"] = list(applies_to)
    return out


def clinical_notes(patient_state, options, guideline_chunks, confirmed_state=None):
    """참고란 목록. 참고할 내용이 없으면 빈 목록."""
    patient = ((patient_state or {}).get("fields") or {}).get("patient") or {}
    given = {c.get("chunk_id") for c in guideline_chunks or []}
    cites = [c for c in COMORBIDITY_CHUNKS if c in given]   # 넘어온 지침 청크 안의 ID만 (환각 방지 규칙 1)
    notes = []

    comorbidities = _present(patient.get("comorbidities"))
    if comorbidities:
        notes.append(_note("comorbidity", f"동반질환: {', '.join(comorbidities)}",
                           ["patient_state.fields.patient.comorbidities"], cites))
    ecog = _present(patient.get("ecog"))
    if ecog is not None:
        notes.append(_note("performance_status", f"ECOG {ecog}", ["patient_state.fields.patient.ecog"]))

    crisis = _confirmed(confirmed_state, "visceral_crisis")
    if crisis == "yes":
        notes.append(_note("visceral_crisis", "장기 위기: 예 (의사 확정)", ["confirmed_state.items.visceral_crisis"]))
    elif crisis is None and _present(patient.get("visceral_crisis")) == "yes":
        notes.append(_note("visceral_crisis", "장기 위기: 예 (차트 기록, 의사 확정 전)",
                           ["patient_state.fields.patient.visceral_crisis"]))

    classes = [c for c in _confirmed(confirmed_state, "contraindicated_classes") or [] if c]
    if classes:
        wanted = {c.lower() for c in classes}
        table = _drug_classes()
        hit = [o.get("therapy") for o in options or []
               if any(table.get(d.lower(), {d.lower()}) & wanted for d in o.get("drugs") or [])]
        notes.append(_note("contraindicated_classes", f"의사가 금기로 확정한 계열: {', '.join(classes)}",
                           ["confirmed_state.items.contraindicated_classes"], cites, [h for h in hit if h]))
    return notes
