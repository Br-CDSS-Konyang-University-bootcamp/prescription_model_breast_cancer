"""[4] 환각 방지 후처리 (PROJECT.md §7 환각 방지·급여 분류, §15.5).

LLM이 낸 추천을 받은 청크와 B의 판정에 비추어 고친다. 규칙만 쓰고 LLM은 쓰지 않는다.
1. 받은 청크에 없는 청크 ID 인용은 지운다.
2. 근거 문장(rationale)에서 [청크ID]가 없는 문장은 지운다. 남은 문장이 없거나 지침 인용이 없으면 후보를 지운다.
3. 약 이름이 인용한 지침 청크에 실제로 있는지 확인한다 (청크의 drugs 목록 또는 본문 글자). 없으면 후보를 지운다.
4. 약에 필요한 바이오마커(drug_biomarker.csv)가 미시행·기록 없음·불확정·재검 필요면 후보 대신 검사 권고로 바꾼다.
   양성이 아니면(음성·VUS 등) 후보를 지우고 conflicts에 적는다.
5. 급여 분류는 시행 중인 급여 청크(baseline·overlay, 시행일이 오늘 이전)를 인용할 때만 인정한다.
   허가초과 인정은 허가초과 청크(HIRA-offlabel)를 인용할 때만. 급여 조건은 conditions_checker(conditions_eval.py)로 판정한다:
   충족이면 "급여", 불충족이면 "급여 기준 없음", 알 수 없으면(판정기 없음 포함) "급여(조건 확인 필요)".
6. 지침 청크가 하나도 없으면 추천을 만들지 않고 범위 외로 알린다.
지운 것과 바꾼 것은 모두 로그로 돌려준다.
"""
import csv
import re
from datetime import date
from pathlib import Path

DRUG_BIOMARKER_CSV = Path(__file__).resolve().parent / "drug_biomarker.csv"
# 4번: 이 상태면 치료 대신 검사 권고 (PROJECT.md §7 "불확정·미시행이면 검사 권고")
GATE_STATUSES = {"not_done", "not_recorded", "unknown", "retest_needed"}
VALID_REIMB_SOURCE_TYPES = {"baseline", "overlay"}   # preview(예고)는 아직 시행 전이라 판정에 쓰지 않는다
COVERED_CLASSES = {"covered", "covered_conditions_unverified", "offlabel_approved"}
_CITE_RE = re.compile(r"\[([A-Za-z0-9_.:\-]+)\]")
_SENTENCE_RE = re.compile(r"[^.\n]*?(?:\.(?=\s|$)|\n|$)")


def _drug_table():
    """{약 이름(소문자): 행}. markers·statuses는 | 로 나눈 목록."""
    if not hasattr(_drug_table, "cache"):
        with open(DRUG_BIOMARKER_CSV, encoding="utf-8-sig") as fh:
            _drug_table.cache = {r["drug"].lower(): {**r, "markers": r["markers"].split("|"),
                                                       "statuses": r["statuses"].split("|")}
                                 for r in csv.DictReader(fh)}
    return _drug_table.cache


def _sentences(text):
    return [s.strip() for s in _SENTENCE_RE.findall(text or "") if s.strip()]


def _keep_cited_sentences(text, valid_ids):
    """[청크ID]가 붙은 문장만 남긴다. (남은 글, 문장에서 찾은 유효 ID, 지운 문장 수)"""
    kept, found, dropped = [], [], 0
    for s in _sentences(text):
        ids = [i for i in _CITE_RE.findall(s) if i in valid_ids]
        if ids:
            kept.append(s)
            found += [i for i in ids if i not in found]
        else:
            dropped += 1
    return " ".join(kept), found, dropped


def _drug_in_chunks(drug, chunks):
    d = drug.lower()
    return any(d in [x.lower() for x in (c.get("drugs") or [])] or d in (c.get("text") or "").lower() for c in chunks)


def _valid_reimb(chunk, today):
    r = chunk.get("reimbursement") or {}
    return (chunk.get("doc_type") == "reimbursement" and r.get("source_type") in VALID_REIMB_SOURCE_TYPES
            and (r.get("effective_from") or "9999") <= today.isoformat())


def _gate(option, records, disease):
    """4번. (검사 권고 목록, 충돌 문장). 둘 다 비면 통과."""
    tests, conflicts = [], []
    for drug in option.get("drugs") or []:
        row = _drug_table().get(drug.lower())
        if not row or (row["disease"] and row["disease"] != disease):
            continue
        found = {m: records.get(m) for m in row["markers"]}
        if any(s in row["statuses"] for s in found.values()):
            continue
        gated = [m for m, s in found.items() if s in GATE_STATUSES or s is None]
        if gated:
            tests += [{"test": f"{m} 검사 결과 확인", "reason": f"{drug}에 필요한 {m}이(가) {found[m] or '판정 없음'}",
                       "blocks_therapy": option.get("therapy")} for m in gated]
        else:
            conflicts.append(f"{option.get('therapy')}: {drug}에 필요한 {'·'.join(row['markers'])}이(가) "
                             f"{'·'.join(str(found[m]) for m in row['markers'])} (필요: {'·'.join(row['statuses'])}, "
                             f"출처: {row['source']})")
    return tests, conflicts


def _classify(option, reimb_by_id, today, conditions_checker):
    """5번. 급여 분류와 이유를 고친다. 바꾼 내용을 문장으로 돌려준다 (없으면 None)."""
    cls = option.get("reimbursement")
    cited = [reimb_by_id[i] for i in option.get("reimbursement_citations") or [] if i in reimb_by_id]
    valid = [c for c in cited if _valid_reimb(c, today)]
    option["reimbursement_citations"] = [c["chunk_id"] for c in valid]
    if cls not in COVERED_CLASSES:
        return None
    if cls == "offlabel_approved":
        off = [c for c in valid if c.get("source") == "HIRA-offlabel"]
        if not off:
            option.update(reimbursement="no_criteria", reimbursement_citations=[], copay=None)
            return "허가초과 인정 → 급여 기준 없음 (시행 중인 허가초과 청크 인용 없음)"
        option["copay"] = (off[0].get("reimbursement") or {}).get("copay")
        return None
    if not valid:
        option.update(reimbursement="no_criteria", reimbursement_citations=[])
        return f"{cls} → 급여 기준 없음 (시행 중인 급여 청크 인용 없음)"
    # 급여 조건 판정 (conditions_eval.make_conditions_checker). 옛 형식(True/False)도 받는다
    res = conditions_checker(option, valid) if conditions_checker else None
    if isinstance(res, bool):
        res = {"status": "met" if res else "unknown", "reason": ""}
    status, why = (res or {}).get("status", "unknown"), (res or {}).get("reason", "")
    reason = option.get("reimbursement_reason") or ""
    if status == "met":
        option.update(reimbursement="covered", reimbursement_reason=f"{reason} ({why})".strip())
        return None if cls == "covered" else f"{cls} → 급여 ({why})"
    if status == "not_met":
        option.update(reimbursement="no_criteria", reimbursement_reason=f"{reason} (급여 조건 불충족: {why})".strip())
        return f"{cls} → 급여 기준 없음 (급여 조건 불충족)"
    option["reimbursement"] = "covered_conditions_unverified"
    option["reimbursement_reason"] = f"{reason} ({why or '급여 조건을 자동으로 모두 확인하지 못함'})".strip()
    return "급여 → 급여(조건 확인 필요) (조건 확인 안 됨)" if cls == "covered" else None


def postprocess(recommendation, biomarker_record, guideline_chunks, reimbursement_chunks, today=None,
                conditions_checker=None):
    """추천 결과를 고쳐서 돌려준다. (고친 결과, 로그 목록). 받은 값은 바꾸지 않는다.
    conditions_checker(option, 급여 청크 목록) -> bool: 급여 조건을 모두 확인했으면 True (D 판정 연결용, 없으면 확인 안 됨)."""
    today = today or date.today()
    rec = {**recommendation, "options": [dict(o) for o in recommendation.get("options") or []],
           "tests_needed": list(recommendation.get("tests_needed") or []),
           "conflicts": list(recommendation.get("conflicts") or [])}
    log = []
    if not guideline_chunks:
        log += [f"후보 삭제: {o.get('therapy')} (지침 검색 결과 없음)" for o in rec["options"]]
        rec.update(options=[], out_of_scope=True, out_of_scope_reason="지침 검색 결과 없음")
        return rec, log

    guide_by_id = {c["chunk_id"]: c for c in guideline_chunks}
    reimb_by_id = {c["chunk_id"]: c for c in reimbursement_chunks or []}
    records = {r["marker"]: r["status"] for r in biomarker_record.get("records") or []}
    disease = (biomarker_record.get("setting") or {}).get("disease")
    kept = []
    for o in rec["options"]:
        name = o.get("therapy")
        bad = [i for i in o.get("citations") or [] if i not in guide_by_id]
        bad += [i for i in o.get("reimbursement_citations") or [] if i not in reimb_by_id]
        if bad:
            log.append(f"{name}: 받지 않은 청크 ID 인용 삭제 {bad}")
        o["rationale"], in_text, dropped = _keep_cited_sentences(o.get("rationale"), set(guide_by_id) | set(reimb_by_id))
        if dropped:
            log.append(f"{name}: 인용 없는 문장 {dropped}개 삭제")
        cites = [i for i in o.get("citations") or [] if i in guide_by_id]
        cites += [i for i in in_text if i in guide_by_id and i not in cites]
        if not cites or not o["rationale"]:
            log.append(f"후보 삭제: {name} (지침 인용이 있는 근거 문장 없음)")
            continue
        o["citations"] = cites
        missing = [d for d in o.get("drugs") or [] if not _drug_in_chunks(d, [guide_by_id[i] for i in cites])]
        if missing:
            log.append(f"후보 삭제: {name} (인용한 지침 청크에 약 이름 없음: {missing})")
            continue
        tests, conflicts = _gate(o, records, disease)
        if tests or conflicts:
            rec["tests_needed"] += [t for t in tests if t not in rec["tests_needed"]]
            rec["conflicts"] += conflicts
            log.append(f"후보 삭제: {name} ({'검사 권고로 바꿈' if tests else '바이오마커 조건 불일치'})")
            continue
        if any(guide_by_id[i].get("source", "").startswith("ESMO") for i in cites):
            o["guideline_source"] = "ESMO"
        change = _classify(o, reimb_by_id, today, conditions_checker)
        if change:
            log.append(f"{name}: {change}")
        kept.append(o)
    rec["options"] = kept
    return rec, log
