"""[4] 환각 방지 후처리 (PROJECT.md §7 환각 방지·급여 분류, §15.5).

LLM이 낸 추천을 받은 청크와 B의 판정에 비추어 고친다. 규칙만 쓰고 LLM은 쓰지 않는다.
1. 받은 청크에 없는 청크 ID 인용은 지운다.
2. 근거 문장(rationale)에서 [청크ID]가 없는 문장은 지운다. 남은 문장이 없거나 지침 인용이 없으면 후보를 지운다.
3. 약 이름이 인용한 지침 청크에 실제로 있는지 확인한다 (청크의 drugs 목록 또는 본문 글자). 없으면 후보를 지운다.
4. 약에 필요한 바이오마커(drug_biomarker.csv)가 미시행·기록 없음·불확정·재검 필요면 후보 대신 검사 권고로 바꾼다.
   양성이 아니면(음성·VUS 등) 후보를 지우고 conflicts에 적는다.
5. 급여 분류는 시행 중인 급여 청크(baseline·overlay, 시행일이 오늘 이전) 중 후보 약이 모두 행의 drugs에 든 행으로만 한다
   (C search_reimbursement의 "후보 약이 모두 행에 있어야"와 같음, A 전달 handoff_recommend_options_to_B_2026-11-03.md §3).
   약이 다른 행 인용은 지우고, 넘겨받은 급여 청크 중 약이 맞는데 인용하지 않은 행은 붙인다. 맞는 행이 없으면 급여 기준 없음.
   행의 약이 후보 약과 똑같은 행이 있으면 그 행만 쓰고, 없을 때만 약이 더 든 행을 쓴다. 후보 drugs가 비면(7번)
   인용 행을 그대로 두고 급여(조건 확인 필요)로 둔다 (D 요청 2026-11-04).
   허가초과 인정은 허가초과 청크(HIRA-offlabel)를 인용할 때만. 급여 조건은 conditions_checker(conditions_eval.py)로 판정한다:
   충족이면 "급여", 불충족이면 "급여 기준 없음", 알 수 없으면(판정기 없음 포함) "급여(조건 확인 필요)".
6. 지침 청크가 하나도 없으면 추천을 만들지 않고 범위 외로 알린다.
7. drugs가 비면 인용한 지침 청크의 drugs 중 요법 이름(therapy)에 적힌 약으로, evidence가 비면 인용한 지침 청크의
   LoE·GoR로 채운다 (A 전달 handoff_recommend_prompt_to_B_2026-11-02.md §6 4번, LLM이 두 칸을 비워 냄).
   요법 이름에 계열 이름(AI, ET, CDK4/6 등)이 있으면 어느 약인지 정할 수 없어 drugs를 비워 두고 conflicts에 적는다
   (A 전달 2026-11-03 §2 3번. 예: "AI—palbociclib"을 palbociclib 하나로 채우지 않는다).
   다만 LHRH 작용제(LHRH·GnRH agonist, OFS, ovarian suppression)는 goserelin·leuprolide 중 하나로 펼친다 (D 요청 2026-11-04).
8. 골 보호제(drug_classes.csv의 Bone-modifying Agent)는 주 후보가 아니라 supportive_options(함께 처방할 보조 약물)에 둔다
   (팀 안건 A, 2026-11-04). 1~5·7번 검사는 보조 칸에도 똑같이 한다. 선행요법 결정이면 골 보호제를 내지 않고,
   뼈 전이 환자에게 뼈 전이 청크(site-bone)가 왔는데 LLM이 빠뜨리면 그 청크의 골 보호제를 약마다 규칙으로 채운다.
지운 것과 바꾼 것은 모두 로그로 돌려준다.
"""
import csv
import re
from datetime import date
from pathlib import Path

from src.recommend.conditions_eval import DRUG_CLASSES_CSV, _drug_classes

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


# 넓은 계열 이름 (C가 청크 drugs로 풀지 않은 ET·ChT·항HER2, C와 합의 2026-11-02). 인용한 청크 본문에 이 말이 있으면
# 그 계열(drug_classes.csv의 drug_class) 약은 3번 규칙을 통과한다. 짧은 약어(ET, ChT)는 대소문자까지 맞을 때만 본다
CLASS_TERMS = {
    "hormone therapy": re.compile(r"\bET\b|\b[Ee]ndocrine\b"),
    "chemotherapy": re.compile(r"\bChT\b|\b[Cc]hemotherapy\b"),
    "her2-targeted therapy": re.compile(r"\b[Aa]nti-HER2\b|\bHER2-(directed|targeted)\b"),
}


def _drug_in_chunks(drug, chunks):
    """3번 규칙: 약 이름이 인용한 청크의 drugs나 본문에 있거나, 그 약의 계열을 가리키는 넓은 계열 이름이 본문에 있다."""
    d = drug.lower()
    if any(d in [x.lower() for x in (c.get("drugs") or [])] or d in (c.get("text") or "").lower() for c in chunks):
        return True
    terms = [CLASS_TERMS[k] for k in _drug_classes().get(d, set()) if k in CLASS_TERMS]
    return any(rx.search(c.get("text") or "") for rx in terms for c in chunks)


# 7번: 요법 이름에 있으면 약을 하나로 정할 수 없는 계열 이름
CLASS_NAME_RE = re.compile(r"\bAIs?\b|[Aa]romatase inhibitor|\bET\b|[Ee]ndocrine|CDK4/6|\b[Tt]axanes?\b|"
                           r"\b[Aa]nthracyclines?\b|\bChT\b|[Cc]hemotherapy|[Aa]nti-HER2|\bSERDs?\b|\bLHRH\b|\bOFS\b")


# 7번: 약으로 펼치는 계열 이름. LHRH 작용제는 급여 행이 goserelin·leuprolide로 적혀 있어 두 약의 "그중 하나" 묶음(_groups)으로
# 펼친다 (D 요청 2026-11-04, 급여 행 r04~r06). 급여 행은 묶음마다 하나 이상 맞으면 맞는 행으로 본다.
# AI·CDK4/6 등 다른 계열은 펼치지 않고 약을 비워 둔다 (A 전달 2026-11-03 규칙 7, D가 펼치기 요청을 취소 2026-11-04)
EXPAND_CLASS = [
    (re.compile(r"\b(?:LHRH|GnRH)(?:[- ]?(?:agonist|analog(?:ue)?)s?)?\b|\bOFS\b|[Oo]varian (?:function )?suppression"),
     lambda: ["goserelin", "leuprolide"]),
]


DRUG_NAMES_CSV = DRUG_CLASSES_CSV.parent / "drug_names.csv"


def _name_patterns():
    """[(정규식, 일반명)]. 공용 약 사전의 일반명과 별칭(약 하나로 바뀌는 것만). 긴 이름부터 찾는다."""
    if not hasattr(_name_patterns, "cache"):
        names = {g: g for g in _drug_classes()}
        with open(DRUG_NAMES_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                g = (r.get("generic_names") or "").strip().lower()
                if g and "+" not in g and g in names:
                    names.setdefault(r["raw_name"].strip().lower(), g)
        _name_patterns.cache = [(re.compile(rf"(?<![a-z]){re.escape(n)}(?![a-z])"), g)
                                for n, g in sorted(names.items(), key=lambda x: -len(x[0])) if len(n) > 3]
    return _name_patterns.cache


def _groups(option):
    """후보 약 묶음 목록. 계열 이름을 펼친 후보는 _groups, 아니면 약마다 하나씩."""
    return option.get("_groups") or [[d.lower()] for d in option.get("drugs") or []]


def _fill_drugs_evidence(option, chunks):
    """7번. 빈 drugs·evidence를 인용한 지침 청크에서 채운다. (채운 칸 이름 목록, 약을 정하지 못한 이유 또는 None)."""
    filled, unresolved = [], None
    if not option.get("drugs"):
        therapy = option.get("therapy") or ""
        expanded = []   # [(자리, [약 묶음])]
        for rx, names in EXPAND_CLASS:
            m = rx.search(therapy)
            if m:
                expanded.append((m.start(), names()))
                therapy = rx.sub(lambda x: " " * len(x.group()), therapy)
        classes = sorted(set(CLASS_NAME_RE.findall(therapy)))
        if classes:
            unresolved = f"요법 이름에 계열 이름({', '.join(classes)})이 있어 약을 정하지 못함, 의사 확인 필요"
        else:
            # 요법 이름에 적힌 약: 공용 약 사전(일반명·별칭)으로 찾는다. 인용 청크의 drugs에만 기대면 청크에 없는 약이
            # 빠진다 (D 확인 2026-11-04: "anastrozole + LHRH agonist"가 goserelin·leuprolide만 남음).
            # 청크에 없는 약은 다음 3번 규칙이 거른다
            found, text = [], therapy.lower()
            for rx, g in _name_patterns():
                m = rx.search(text)
                if m:
                    text = rx.sub(lambda x: " " * len(x.group()), text)   # 자리를 지켜 순서를 남긴다
                    found.append((m.start(), g))
            groups = []
            for _, g in sorted(found + expanded, key=lambda x: x[0]):
                g = [g] if isinstance(g, str) else g
                if g and g not in groups:
                    groups.append(g)
            if groups:
                option["drugs"] = list(dict.fromkeys(d for g in groups for d in g))
                if any(len(g) > 1 for g in groups):
                    option["_groups"] = groups
                filled.append("drugs")
    if not (option.get("evidence") or "").strip():
        ev = next((c.get("evidence") for c in chunks if (c.get("evidence") or {}).get("loe")), None)
        if ev:
            option["evidence"] = f"LoE {ev['loe']}" + (f", GoR {ev['gor']}" if ev.get("gor") else "")
            filled.append("evidence")
    return filled, unresolved


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


def _added_drugs(chunk):
    """병용 행(40장)의 추가 약제와 그 급여 (D chunk.json reimbursement.combination)."""
    combo = (chunk.get("reimbursement") or {}).get("combination") or {}
    return [d.lower() for d in combo.get("added_drug") or []], combo.get("added_drug_coverage")


def _drugs_match(option, chunk, exact=False):
    """후보 약 묶음마다 급여 행의 drugs에 하나 이상 있는지 (소문자로 비교). exact면 행의 약이 후보 약 밖에 없어야 한다
    (C 검색 결과의 extra_drugs가 빈 행). 병용 행의 추가 약제가 후보에 없으면 맞지 않는다 (그 행 조건은 추가 약제의
    허가 조건이다, D 요청 2026-11-04 VC-0108). 후보 약이 없으면 맞출 수 없어 False."""
    groups = _groups(option)
    have = {d.lower() for d in chunk.get("drugs") or []}
    union = {d for g in groups for d in g}
    if not groups or not all(have & set(g) for g in groups):
        return False
    if not set(_added_drugs(chunk)[0]) <= union:
        return False
    return have <= union if exact else True


def _classify(option, reimb_by_id, today, conditions_checker):
    """5번. 급여 분류와 이유를 고친다. 바꾼 내용을 문장 목록으로 돌려준다 (없으면 빈 목록)."""
    cls = option.get("reimbursement")
    changes = []
    cited = [reimb_by_id[i] for i in option.get("reimbursement_citations") or [] if i in reimb_by_id]
    valid = [c for c in cited if _valid_reimb(c, today)]
    if not option.get("drugs"):
        # 약을 정하지 못한 후보 (7번, 계열 이름). 행의 약과 맞춰 볼 수 없으니 인용 행을 지우거나 붙이지 않고,
        # 급여 조건도 판정하지 않는다 (D 요청 2026-11-04, VC-0119)
        option["reimbursement_citations"] = [c["chunk_id"] for c in valid]
        if cls == "offlabel_approved" and any(c.get("source") == "HIRA-offlabel" for c in valid):
            option["copay"] = next(c for c in valid if c.get("source") == "HIRA-offlabel")["reimbursement"].get("copay")
            return changes
        if cls in COVERED_CLASSES and valid:
            option.update(reimbursement="covered_conditions_unverified",
                          reimbursement_reason="후보 약을 정하지 못해 급여 조건을 판정하지 않음, 의사 확인")
            return changes + ([] if cls == "covered_conditions_unverified" else [f"{cls} → 급여(조건 확인 필요) (후보 약 미정)"])
        if cls in COVERED_CLASSES:
            option.update(reimbursement="no_criteria", reimbursement_citations=[], copay=None)
            return changes + [f"{cls} → 급여 기준 없음 (시행 중인 급여 청크 인용 없음)"]
        return changes
    # 후보 약과 행 약이 똑같은 행을 먼저 쓰고, 그런 행이 없을 때만 약이 더 든 행을 쓴다 (D 요청 2026-11-04.
    # 예: paclitaxel 후보가 paclitaxel + pembrolizumab 행의 조건으로 급여가 되지 않게)
    current = [c for c in reimb_by_id.values() if _valid_reimb(c, today)]
    exact = [c for c in current if _drugs_match(option, c, exact=True)]
    pool = exact or [c for c in current if _drugs_match(option, c)]
    matched = [c for c in valid if c in pool]
    if len(matched) < len(valid):
        changes.append(f"약이 다른 급여 행 인용 삭제 {[c['chunk_id'] for c in valid if c not in matched]}")
    added = [c for c in pool if c not in matched]
    if added:
        changes.append(f"약이 맞는 급여 행 붙임 {[c['chunk_id'] for c in added]}")
    valid = matched + added
    option["reimbursement_citations"] = [c["chunk_id"] for c in valid]
    if cls == "offlabel_approved":
        off = [c for c in valid if c.get("source") == "HIRA-offlabel"]
        if off:
            option["copay"] = (off[0].get("reimbursement") or {}).get("copay")
            return changes
        # 허가초과 청크가 없으면 바로 급여 기준 없음으로 두지 않고, 약이 맞는 일반 급여 행으로 판정한다
        # (허가초과 목록은 v0.1에서 쓰지 않음. LLM이 허가초과로 분류해 맞는 급여 행이 붙지 않을 수 있었다, D 확인 VC-0101)
        option["copay"] = None
        changes.append("허가초과 인정 → 일반 급여 행으로 판정 (허가초과 청크 없음)")
        cls = "covered_conditions_unverified"
    valid = [c for c in valid if c.get("source") != "HIRA-offlabel"]
    option["reimbursement_citations"] = [c["chunk_id"] for c in valid]
    if not valid:
        if cls in COVERED_CLASSES:
            option.update(reimbursement="no_criteria", reimbursement_citations=[],
                          reimbursement_reason="후보 약과 맞는 시행 중인 급여 행 없음")
            changes.append(f"{cls} → 급여 기준 없음 (후보 약과 맞는 시행 중인 급여 행 없음)")
        return changes
    if cls not in COVERED_CLASSES:
        changes.append(f"{cls} → 급여 행 판정 (후보 약과 맞는 급여 행 있음)")
    # 급여 조건 판정 (conditions_eval.make_conditions_checker). 옛 형식(True/False)도 받는다
    res = conditions_checker(option, valid) if conditions_checker else None
    if isinstance(res, bool):
        res = {"status": "met" if res else "unknown", "reason": ""}
    status, why = (res or {}).get("status", "unknown"), (res or {}).get("reason", "")
    # 병용 행의 추가 약제가 비급여면 이유 앞에 적는다 (D 요청 2026-11-04, VC-0122 inavolisib·VC-0123 capivasertib)
    nonpaid = sorted({d for c in valid for d in _added_drugs(c)[0] if _added_drugs(c)[1] == "비급여"})
    if nonpaid:
        rest = [d for d in option.get("drugs") or [] if d.lower() not in nonpaid]
        why = f"{'·'.join(nonpaid)} 비급여 + {'·'.join(rest)} 급여" + (f"; {why}" if why else "")
    # 이유 문장은 판정기가 쓴 것만 둔다. LLM의 reimbursement_reason을 앞에 붙이면 "조건 확인 불가 (조건 충족 …)"처럼
    # 앞뒤가 어긋난다 (D 확인 2026-11-04)
    if status == "met":
        option.update(reimbursement="covered", reimbursement_reason=why or "급여 조건 충족")
        return changes + ([] if cls == "covered" else [f"{cls} → 급여 ({why})"])
    if status == "not_met":
        option.update(reimbursement="no_criteria", reimbursement_reason=f"급여 조건 불충족: {why}" if why else "급여 조건 불충족")
        return changes + ([] if cls == "no_criteria" else [f"{cls} → 급여 기준 없음 (급여 조건 불충족)"])
    option["reimbursement"] = "covered_conditions_unverified"
    option["reimbursement_reason"] = why or "급여 조건을 자동으로 모두 확인하지 못함"
    return changes + (["급여 → 급여(조건 확인 필요) (조건 확인 안 됨)"] if cls == "covered" else [])


# 8번: 골 보호제 (drug_classes.csv의 Bone-modifying Agent). 주 후보 options가 아니라 보조 약물 supportive_options에 둔다
# (팀 안건 A src/input/team_agenda_A_2026-11-04.md, schemas/recommendation.json supportive_options)
BMA_CLASS = "Bone-modifying Agent"
BMA_TERM_RE = re.compile(r"[Bb]isphosphonates?|\bBMAs?\b|[Bb]one[- ]modifying|[Dd]enosumab|[Zz]oledron|"
                         r"[Pp]amidronate|[Ii]bandronate|[Cc]lodronate")


def _bma_drugs():
    """골 보호제 일반명 목록 (소문자, 사전 순서)."""
    if not hasattr(_bma_drugs, "cache"):
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            _bma_drugs.cache = [r["generic_name"].lower() for r in csv.DictReader(fh) if r["drug_class"] == BMA_CLASS]
    return _bma_drugs.cache


def _is_supportive(option):
    """골 보호제만으로 된 후보인지. 약이 있으면 모두 골 보호제, 약이 없으면 요법 이름에 골 보호제 말이 있을 때."""
    drugs = [d.lower() for d in option.get("drugs") or []]
    if drugs:
        return all(d in _bma_drugs() for d in drugs)
    return bool(BMA_TERM_RE.search(option.get("therapy") or ""))


def _bone_supportive(guide_by_id, done):
    """8번: 뼈 전이 청크(chunk_id에 site-bone)의 골 보호제를 보조 후보로 만든다 (LLM이 빠뜨렸을 때, VC-0108).
    급여 여부가 아니라 지침 근거로 정한다 (A 의견, C 확인 2026-11-04): 청크 본문에 이름이 직접 나오는 약
    (ESMO MBC는 zoledronic acid, denosumab)은 약마다 한 줄, 청크 drugs에만 있는 약(C가 "bisphosphonates"를
    계열 사전으로 푼 것)은 "bisphosphonates 계열" 한 줄로 묶는다 (그중 하나라는 뜻). 급여는 5번 규칙이 판정한다.
    근거 문장은 정해진 틀이고 지침 원문을 옮기지 않는다. done은 이미 보조 칸에 있는 약."""
    out = []
    for cid, c in guide_by_id.items():
        if "site-bone" not in cid:
            continue
        ev = c.get("evidence") or {}
        base = {"rationale": f"뼈 전이 환자에게 골 보호제가 권고된다 [{cid}].", "citations": [cid],
                "evidence": (f"LoE {ev['loe']}" + (f", GoR {ev['gor']}" if ev.get("gor") else "")) if ev.get("loe") else None,
                "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "", "reimbursement_citations": []}
        text = (c.get("text") or "").lower()
        bma = [d for d in (x.lower() for x in c.get("drugs") or []) if d in _bma_drugs()]
        named = [d for d in bma if d in text]
        for d in named:
            if d not in done:
                done.add(d)
                out.append({**base, "therapy": d, "drugs": [d]})
        group = [d for d in bma if d not in named and d not in done]
        if group:
            done.update(group)
            out.append({**base, "therapy": f"bisphosphonates 계열 ({', '.join(group)} 중 하나)", "drugs": group,
                        "_groups": [group]})
    return out


def postprocess(recommendation, biomarker_record, guideline_chunks, reimbursement_chunks, today=None,
                conditions_checker=None, phase=None, bone_metastasis=False):
    """추천 결과를 고쳐서 돌려준다. (고친 결과, 로그 목록). 받은 값은 바꾸지 않는다.
    conditions_checker(option, 급여 청크 목록) -> {status, reason}: 급여 조건 판정 (conditions_eval.make_conditions_checker).
    phase(neoadjuvant / adjuvant / None)·bone_metastasis(bool)는 8번 보조 약물 규칙에 쓴다."""
    today = today or date.today()
    rec = {**recommendation, "options": [dict(o) for o in recommendation.get("options") or []],
           "supportive_options": [dict(o) for o in recommendation.get("supportive_options") or []],
           "tests_needed": list(recommendation.get("tests_needed") or []),
           "conflicts": list(recommendation.get("conflicts") or [])}
    log = []
    if not guideline_chunks:
        log += [f"후보 삭제: {o.get('therapy')} (지침 검색 결과 없음)" for o in rec["options"] + rec["supportive_options"]]
        rec.update(options=[], supportive_options=[], out_of_scope=True, out_of_scope_reason="지침 검색 결과 없음")
        return rec, log

    guide_by_id = {c["chunk_id"]: c for c in guideline_chunks}
    reimb_by_id = {c["chunk_id"]: c for c in reimbursement_chunks or []}
    records = {r["marker"]: r["status"] for r in biomarker_record.get("records") or []}
    disease = (biomarker_record.get("setting") or {}).get("disease")

    # 1번 앞: 소단원(부모) ID를 인용하면 넘겨받은 그 자식 청크 ID로 바꾼다 (A 전달 §5.3, VC-0134가 부모 ID를 인용해 지워짐).
    # 자식이 여럿이면 후보 약이 든 자식, 없으면 첫 자식
    children = {}
    for c in guideline_chunks:
        for p in (c.get("parents") or []) + [c.get("parent")]:
            pid = (p or {}).get("chunk_id") if isinstance(p, dict) else p
            if pid and pid not in guide_by_id:
                children.setdefault(pid, [])
                if c["chunk_id"] not in children[pid]:
                    children[pid].append(c["chunk_id"])

    def resolve_parents(o):
        drugs = {d.lower() for d in o.get("drugs") or []}

        def child(pid):
            kids = children[pid]
            return next((k for k in kids if drugs & {d.lower() for d in guide_by_id[k].get("drugs") or []}), kids[0])
        hit = [i for i in o.get("citations") or [] if i in children]
        hit += [i for i in _CITE_RE.findall(o.get("rationale") or "") if i in children and i not in hit]
        if not hit:
            return
        o["citations"] = list(dict.fromkeys(child(i) if i in children else i for i in o.get("citations") or []))
        o["rationale"] = _CITE_RE.sub(lambda m: f"[{child(m.group(1))}]" if m.group(1) in children else m.group(0),
                                      o.get("rationale") or "")
        log.append(f"{o.get('therapy')}: 소단원 ID 인용을 자식 청크로 바꿈 {hit}")

    def check(o):
        """1~5·7번을 후보 하나에 적용한다. 남기면 True."""
        resolve_parents(o)
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
            return False
        o["citations"] = cites
        filled, unresolved = _fill_drugs_evidence(o, [guide_by_id[i] for i in cites])
        if filled:
            log.append(f"{name}: 빈 칸을 인용한 지침 청크에서 채움 ({', '.join(filled)})")
        if unresolved:
            rec["conflicts"].append(f"{name}: {unresolved}")
            log.append(f"{name}: {unresolved}")
        # 3번 앞: 인용한 지침 청크에 후보 약이 없지만 넘겨받은 다른 지침 청크에 그 약이 있으면, 그 청크(관련도 순서로 첫 것)를
        # 근거에 더한다 (A 공유 2026-11-05 B-5, VC-0127 sacituzumab). 지어낸 근거가 아니라 받은 청크에 약이 있음을 확인하는 것
        for d in [d for d in o.get("drugs") or [] if not _drug_in_chunks(d, [guide_by_id[i] for i in cites])]:
            other = next((c["chunk_id"] for c in guideline_chunks if c["chunk_id"] not in cites and _drug_in_chunks(d, [c])), None)
            if other:
                cites.append(other)
                log.append(f"{name}: 인용한 청크에 {d}가 없어 그 약이 든 받은 청크를 근거에 더함 ({other})")
        o["citations"] = cites
        cited = [guide_by_id[i] for i in cites]
        if o.get("_groups"):   # 펼친 묶음은 인용 청크에 있는 약만 남기고, 묶음마다 하나 이상 있어야 한다
            o["_groups"] = [[d for d in g if _drug_in_chunks(d, cited)] for g in o["_groups"]]
            missing = [] if all(o["_groups"]) else [d for g in o["_groups"] if not g for d in ["(계열 묶음)"]]
            o["drugs"] = list(dict.fromkeys(d for g in o["_groups"] for d in g))
        else:
            missing = [d for d in o.get("drugs") or [] if not _drug_in_chunks(d, cited)]
        if missing:
            log.append(f"후보 삭제: {name} (인용한 지침 청크에 약 이름 없음: {missing})")
            return False
        tests, conflicts = _gate(o, records, disease)
        if tests or conflicts:
            rec["tests_needed"] += [t for t in tests if t not in rec["tests_needed"]]
            rec["conflicts"] += conflicts
            log.append(f"후보 삭제: {name} ({'검사 권고로 바꿈' if tests else '바이오마커 조건 불일치'})")
            return False
        if any(guide_by_id[i].get("source", "").startswith("ESMO") for i in cites):
            o["guideline_source"] = "ESMO"
        log.extend(f"{name}: {c}" for c in _classify(o, reimb_by_id, today, conditions_checker))
        return True

    main, support = [], []
    for o in rec["options"]:
        if check(o):
            if _is_supportive(o):
                log.append(f"{o.get('therapy')}: 골 보호제라 보조 약물 칸으로 옮김")
                support.append(o)
            else:
                main.append(o)
    # 같은 요법(약이 같거나, 약이 없으면 이름이 같은 후보)은 하나로 합치고 근거는 모은다 (A 공유 2026-11-05 B-4)
    merged = []
    for o in main:
        key = frozenset(d.lower() for d in o.get("drugs") or []) or (o.get("therapy") or "").strip().lower()
        same = next((m for m in merged if m[0] == key), None)
        if same:
            same[1]["citations"] = list(dict.fromkeys(same[1]["citations"] + o["citations"]))
            log.append(f"{o.get('therapy')}: 같은 요법이라 앞 후보와 합침")
        else:
            merged.append((key, o))
    main = [o for _, o in merged]
    for o in rec["supportive_options"]:
        if check(o):
            if _is_supportive(o):
                support.append(o)
            else:
                log.append(f"후보 삭제: {o.get('therapy')} (보조 약물 칸에는 골 보호제만)")
    # 8번: 수술 전(선행요법) 결정에서는 수술 뒤 비스포스포네이트 같은 골 보호제가 지금 맞지 않는다 (C 정답 VC-0121·0124)
    if phase == "neoadjuvant" and disease != "metastatic" and support:
        log += [f"후보 삭제: {o.get('therapy')} (선행요법 결정이라 골 보호제는 지금 해당 없음)" for o in support]
        support = []
    # 같은 약 조합은 한 번만
    seen, unique = set(), []
    for o in support:
        key = frozenset(d.lower() for d in o.get("drugs") or []) or o.get("therapy")
        if key not in seen:
            seen.add(key)
            unique.append(o)
    support = unique
    # 8번: 뼈 전이 환자에게 뼈 전이 청크가 왔는데 LLM이 골 보호제를 빠뜨리면 규칙으로 채운다 (VC-0108)
    if bone_metastasis:
        done = {d.lower() for o in support for d in o.get("drugs") or []}
        for o in _bone_supportive(guide_by_id, done):
            log.append(f"{o['therapy']}: 뼈 전이 청크가 있어 보조 약물 칸에 채움 ({o['citations'][0]})")
            log.extend(f"{o['therapy']}: {c}" for c in _classify(o, reimb_by_id, today, conditions_checker))
            support.append(o)
    for o in main + support:
        o.pop("_groups", None)   # 내부용 (스키마에 없는 칸)
    rec["options"], rec["supportive_options"] = main, support
    return rec, log
