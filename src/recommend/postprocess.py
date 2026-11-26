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
import itertools
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


def _class_words():
    """약 계열을 가리키는 말 (B-14에서 약 후보인지 가릴 때만 쓴다. 약 이름을 비우는 데는 쓰지 않는다).
    drug_classes.csv의 계열·세부 계열 이름(영문, 한글)과 흔한 계열 표현."""
    words = {"inhibitor", "inhibitors", "억제제", "parp", "pi3k", "akt", "mtor", "adc", "antibody-drug conjugate",
             "checkpoint", "immunotherapy", "면역", "표적", "bisphosphonate", "비스포스포네이트"}
    with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            for k in ("drug_class", "drug_class_ko", "drug_subclass"):
                v = (r.get(k) or "").strip().lower().replace("_", " ")
                if v and v not in ("other", "unknown", "기타", "알 수 없음"):
                    words.add(v)
    return words


CLASS_WORD_RE = re.compile("|".join(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])"
                                    for w in sorted(_class_words(), key=len, reverse=True)), re.IGNORECASE)


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


def _base_match(option, chunk):
    """병용 행(40장)이 아닌 급여 행에서, 각주로 붙은 추가 약제를 뺀 요법(base_regimen)과 후보 약이 똑같은가.
    보조 내분비 행(공고 인쇄 p.51~52)은 요법이 'anastrozole' 단독인데, 각주(주2) 'abemaciclib과 병용 시 본인부담'
    때문에 D 청크 drugs에 abemaciclib이 함께 들어 있다. 그래도 그 행은 단독 요법의 급여 행이다 (2026-11-18 원문 확인)."""
    if (chunk.get("reimbursement") or {}).get("stage") == "combination":
        return False
    added = set(_added_drugs(chunk)[0])
    base = {d.lower() for d in chunk.get("drugs") or []} - added
    if not added or not base:
        return False
    groups = _groups(option)
    union = {d for g in groups for d in g}
    return bool(groups) and all(base & set(g) for g in groups) and base <= union


def _has_condition_field(chunk, field):
    """급여 행의 투여 조건에 그 칸(field) 항목이 있는지 (all_of, stage_rules, any_of 묶음, any_of_exceptions, unless)."""
    cond = (chunk.get("reimbursement") or {}).get("conditions") or {}
    items = list(cond.get("all_of") or []) + list(cond.get("stage_rules") or [])
    for g in cond.get("any_of") or []:
        items += g.get("items") or []
    for e in cond.get("any_of_exceptions") or []:
        items += e.get("all_of") or []
    items += [it["unless"] for it in items if isinstance(it.get("unless"), dict)]
    return any(it.get("field") == field for it in items)


def _drugs_match(option, chunk, exact=False):
    """후보 약 묶음마다 급여 행의 drugs에 하나 이상 있는지 (소문자로 비교). exact면 행의 약이 후보 약 밖에 없어야 한다
    (C 검색 결과의 extra_drugs가 빈 행). 40장 병용 행의 추가 약제가 후보에 없으면 맞지 않는다 (그 행 조건은 추가 약제의
    허가 조건이다, D 요청 2026-11-04 VC-0108). 후보 약이 없으면 맞출 수 없어 False."""
    groups = _groups(option)
    have = {d.lower() for d in chunk.get("drugs") or []}
    union = {d for g in groups for d in g}
    if not groups or not all(have & set(g) for g in groups):
        return False
    # 추가 약제 검사는 40장 병용요법 행(stage combination)에만. 9장 보조요법 행의 각주("abemaciclib과 병용하면
    # abemaciclib 100/100")도 added_drug로 들어 있지만, 그 행의 요법(AI 단독, tamoxifen 단독 등) 자체가 급여 대상이다
    # (D 확인 2026-11-05, VC-0133 tamoxifen 단독이 r09를 잃고 '기준 없음'이 되던 문제)
    is_combo = (chunk.get("reimbursement") or {}).get("stage") == "combination"
    if is_combo and not set(_added_drugs(chunk)[0]) <= union:
        return False
    return have <= union if exact else True


# 좁은 계열 펼치기 (2026-11-17): 요법 이름의 좁은 계열(AI, CDK4/6 inhibitor, taxane, anthracycline, SERD)을
# drug_classes.csv 세부 계열의 약으로 펼쳐 약 조합마다 급여를 판정한다. 넓은 계열(ET, ChT, 항HER2)은 아직 펼치지 않는다
# (ET는 폐경별 청크, ChT는 단계·범주 사전으로 따로 한다). 후보 drugs는 비운 채 두고 candidates에 조합별 판정을 단다
NARROW_CLASS = [
    (re.compile(r"\bAIs?\b|[Aa]romatase inhibitors?"), ("AI_nonsteroidal", "AI_steroidal")),
    (re.compile(r"CDK4/6(?:\s*inhibitors?|i\b)?"), ("CDK4/6_inhibitor",)),
    (re.compile(r"\b[Tt]axanes?\b"), ("taxane",)),
    (re.compile(r"\b[Aa]nthracyclines?\b"), ("anthracycline",)),
    (re.compile(r"\bSERDs?\b"), ("SERD",)),
]
BROAD_CLASS_RE = re.compile(r"\bET\b|[Ee]ndocrine|\bChT\b|[Cc]hemotherapy|[Aa]nti-HER2")
# 화면 2에 보이는 줄 수 상한. LHRH 작용제만 다른 조합(goserelin + X, leuprolide + X)은 화면 2에서 한 줄(약 고르기)이라
# 한 줄로 센다 (2026-11-26)
MAX_CANDIDATES = 12
# 계열에 들어 있지만 ESMO 권고의 뜻으로 넣지 않는 약 (허가되지 않은 시험약, C chunk_common.CLASS_EXCLUDE와 같음)
CANDIDATE_EXCLUDE = {"tesetaxel"}
# 계열 사이의 "or"·"또는"은 둘 중 하나다 (예: "Rechallenge with anthracyclines or taxanes"). 병용 조합으로 곱하지 않는다
ALTERNATIVE_RE = re.compile(r"\bor\b|또는|혹은")
PAREN_ALT_RE = re.compile(r"\([^()]*(?:\bor\b|또는|혹은)[^()]*\)")
REIMB_RANK = {"covered": 0, "covered_conditions_unverified": 1, "offlabel_approved": 2, "no_criteria": 3}


def _subclass_members(keys):
    """세부 계열(drug_subclass) → 약 일반명 (사전 순서, 'nos'는 뺀다)."""
    if not hasattr(_subclass_members, "cache"):
        table = {}
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                name, sub = (r.get("generic_name") or "").strip().lower(), (r.get("drug_subclass") or "").strip()
                if name and sub and "nos" not in name.split():
                    table.setdefault(sub, []).append(name)
        _subclass_members.cache = table
    return [n for k in keys for n in _subclass_members.cache.get(k, [])]


def _fixed_groups(text):
    """요법 이름 한 부분에서 계열이 아닌 약 묶음: LHRH·OFS(goserelin·leuprolide 그중 하나)와 사전에 있는 약 이름.
    (찾은 묶음 목록, 찾은 자리를 지운 글)."""
    blank = lambda m: " " * len(m.group())   # noqa: E731  자리를 지켜 순서를 남긴다
    fixed = []
    for rx, names in EXPAND_CLASS:
        if rx.search(text):
            fixed.append(names())
            text = rx.sub(blank, text)
    low = text.lower()
    for rx, g in _name_patterns():
        if rx.search(low):
            if [g] not in fixed:
                fixed.append([g])
            low = rx.sub(blank, low)
    return fixed, low


def _part_slots(part, in_chunks):
    """요법 이름 한 조각('or'로 나눈 것)의 약 자리 [(글자 위치, [그중 하나인 약])]와 좁은 계열이 있었는지.
    펼치지 못하는 계열 이름이 남으면 None. LHRH·OFS는 goserelin·leuprolide 중 하나인 자리 하나다 (2026-11-26, VC-0121:
    두 약을 한 조합에 넣으면 화면 2에 'goserelin + leuprolide + …'로 보였다). 계열 이름 뒤에 그 계열 약을 적으면
    (예: "AI (anastrozole, letrozole, exemestane)") 그 약들은 고정 약이 아니라 그 계열 자리의 '그중 하나'로 좁힌다"""
    blank = lambda m: " " * len(m.group())   # noqa: E731  자리를 지켜 순서를 남긴다
    text, slots, narrow = part, [], False   # slots: [위치, 고를 약, 계열의 약 전체, 이름이 적힌 약]
    for rx, names in EXPAND_CLASS:
        m = rx.search(text)
        if m:
            slots.append([m.start(), names(), names(), []])
            text = rx.sub(blank, text)
    for rx, keys in NARROW_CLASS:
        m = rx.search(text)
        if m:
            members = [d for d in _subclass_members(keys) if d not in CANDIDATE_EXCLUDE]
            slots.append([m.start(), [d for d in members if d in in_chunks] or members, members, []])
            text = rx.sub(blank, text)
            narrow = True
    if CLASS_NAME_RE.search(text):
        return None
    low = text.lower()
    for rx, g in _name_patterns():
        m = rx.search(low)
        if m:
            low = rx.sub(blank, low)
            owner = next((s for s in slots if g in s[2]), None)
            if owner:
                owner[3].append(g)
            else:
                slots.append([m.start(), [g], [g], []])
    return [(s[0], [d for d in s[2] if d in s[3]] if s[3] else s[1]) for s in slots], narrow


def _narrow_candidates(option, cited, reimb_by_id, today, conditions_checker):
    """계열 이름 후보를 약 조합으로 펼쳐 조합마다 급여를 판정한다. 펼칠 수 없으면 None.
    계열의 약은 인용한 지침 청크의 drugs에 있는 것만 쓴다 (C가 좁은 계열을 청크 drugs로 풀어 둔다). 없으면 사전의 약 전체.
    요법 이름은 'or'·'또는'으로 먼저 나눈다. 나눈 조각은 서로 '둘 중 하나'라 곱하지 않고, 조각마다 약 자리를 곱한다
    (예: "OFS-tamoxifen or OFS-AI" → goserelin+tamoxifen, leuprolide+tamoxifen, goserelin+anastrozole, …, 2026-11-26 VC-0121)"""
    therapy = option.get("therapy") or ""
    if option.get("drugs") or BROAD_CLASS_RE.search(therapy):
        return None
    in_chunks = {d.lower() for c in cited for d in c.get("drugs") or []}
    # 'or'가 든 괄호는 앞말의 예시다 ("taxanes (liposomal anthracyclines or protein-bound paclitaxel, if available)").
    # 괄호 밖만으로 약이 정해지면 그 괄호는 빼고 나눈다. 괄호를 빼면 펼칠 계열이 없을 때만 괄호까지 본다
    for text in dict.fromkeys([PAREN_ALT_RE.sub(lambda m: " " * len(m.group()), therapy), therapy]):
        combos, any_narrow = [], False
        for part in ALTERNATIVE_RE.split(text):
            found = _part_slots(part, in_chunks)
            if found is None:
                return None
            slots, narrow = found
            any_narrow = any_narrow or narrow
            if slots:   # 약이 없는 조각(앞말만 남은 것)은 건너뛴다
                combos += itertools.product(*[s for _, s in sorted(slots, key=lambda x: x[0])])
        if any_narrow:
            break
    if not any_narrow:
        return None
    return _classify_combos(therapy, combos, reimb_by_id, today, conditions_checker)


def _one_of_candidates(option, reimb_by_id, today, conditions_checker):
    """약 이름으로 정한 후보(7번)에 LHRH 작용제 '그중 하나' 묶음이 있으면 약마다 한 조합으로 판정한다
    (예: "OFS-tamoxifen" → goserelin + tamoxifen, leuprolide + tamoxifen). 화면 2에서 LHRH 약을 골라 처방한다 (2026-11-26).
    후보 drugs는 그대로 둔다 (같은 요법 합치기·OFS 중 bisphosphonate 판단에 쓰인다). 묶음이 없으면 None"""
    groups = option.get("_groups") or []
    multi = [g for g in groups if len(g) > 1]
    if not multi or not all(set(g) <= LHRH_DRUGS for g in multi):
        return None
    return _classify_combos(option.get("therapy") or "", itertools.product(*groups), reimb_by_id, today, conditions_checker)


def _row_count(combos):
    """화면 2의 줄 수. LHRH 작용제만 다른 조합은 한 줄이다 (약 목록 또는 후보 dict)."""
    return len({tuple("*" if d in LHRH_DRUGS else d for d in (c["drugs"] if isinstance(c, dict) else c)) for c in combos})


def _classify_combos(therapy, combos, reimb_by_id, today, conditions_checker):
    """약 조합마다 급여를 판정해 급여가 나은 순서로 돌려준다. 화면 줄 수(LHRH 약만 다른 조합은 한 줄)가 상한을 넘으면 None."""
    combos = list(dict.fromkeys(tuple(dict.fromkeys(c)) for c in combos))
    if _row_count(combos) > MAX_CANDIDATES:
        return None
    out = []
    for combo in combos:
        temp = {"therapy": therapy, "drugs": list(combo),
                "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "", "reimbursement_citations": []}
        _classify(temp, reimb_by_id, today, conditions_checker)
        out.append({k: temp.get(k) for k in ("drugs", "reimbursement", "reimbursement_basis", "reimbursement_reason",
                                               "reimbursement_citations")} | {"copay": temp.get("copay")})
    return sorted(out, key=lambda c: REIMB_RANK.get(c["reimbursement"], 9))


def _apply_candidates(option, candidates):
    """후보에 조합별 판정을 달고, 후보 자체의 급여는 가장 나은 조합으로 둔다 (순위에 쓰인다). 약은 건드리지 않는다."""
    option["candidates"] = candidates
    best = candidates[0]["reimbursement"]
    rows = [i for c in candidates if c["reimbursement"] == best for i in c["reimbursement_citations"]]
    counts = {}
    for c in candidates:
        counts[c["reimbursement"]] = counts.get(c["reimbursement"], 0) + 1
    names = {"covered": "급여", "covered_conditions_unverified": "조건 확인 필요", "offlabel_approved": "허가초과",
             "no_criteria": "급여 기준 없음"}
    summary = ", ".join(f"{names[k]} {v}" for k, v in sorted(counts.items(), key=lambda x: REIMB_RANK[x[0]]))
    option.update(reimbursement=best, reimbursement_citations=list(dict.fromkeys(rows)), reimbursement_basis="drug_undetermined",
                  reimbursement_reason=f"약 조합 {_row_count(candidates)}개"
                                       + (f"(LHRH 약까지 {len(candidates)}가지)" if _row_count(candidates) < len(candidates) else "")
                                       + f"로 펼쳐 판정 ({summary}). 조합을 골라 처방",
                  copay=None)


# 넓은 계열 펼치기 (2026-11-18): 조기 유방암의 ET·ChT 계열 이름 후보를 B 사전 dictionaries/class_candidates.csv로
# 펼친다. ET는 폐경 상태·고위험으로 고른 요법(ESMO EBC 폐경별 권고 청크), ChT는 이번 결정 단계의 급여 행 중 약이 모두
# 허용 범주(ESMO EBC 본문)인 요법. "ChT followed by ET"는 선행 항암을 이미 받은 보조 결정이면 ET, 그 밖은 ChT를 펼친다
CLASS_CANDIDATES_CSV = Path(__file__).resolve().parent / "dictionaries" / "class_candidates.csv"
ET_RE = re.compile(r"\bET\b|[Ee]ndocrine|내분비|호르몬")
CHT_RE = re.compile(r"\bChT\b|[Cc]hemotherapy|항암|화학요법")
OTHER_CLASS_RE = re.compile(r"[Aa]nti-HER2|HER2-(?:directed|targeted)|\bICI\b|PARP")


def _class_rows():
    if not hasattr(_class_rows, "cache"):
        with open(CLASS_CANDIDATES_CSV, encoding="utf-8-sig") as fh:
            _class_rows.cache = list(csv.DictReader(fh))
    return _class_rows.cache


def _member_choices(token):
    """사전의 약 자리 하나 → 고를 수 있는 약 목록. LHRH, AI 등 세부 계열은 약마다."""
    if token == "LHRH":   # 약마다 한 조합 (화면 2에서 LHRH 약만 다른 조합은 한 줄로 묶어 고른다, 2026-11-26)
        return [["goserelin"], ["leuprolide"]]
    if token == "AI":
        return [[m] for m in _subclass_members(("AI_nonsteroidal", "AI_steroidal"))]
    members = _subclass_members((token,))
    return [[m] for m in members] if members else [[token]]


def _allowed_drugs(tokens):
    """ChT 허용 범주(세부 계열 이름 또는 약 이름) → 약 일반명 집합."""
    out = set()
    for t in tokens:
        members = _subclass_members((t,))
        out |= set(members) if members else {t}
    return out


def _broad_candidates(option, reimb_by_id, today, conditions_checker, ctx):
    """ET·ChT 계열 이름 후보를 펼쳐 조합마다 급여를 판정한다. 펼칠 수 없으면 (None, 메모). ctx: disease, subtype,
    menopausal, high_risk(ESMO yes/no/None), phase, prior_chemo(bool)."""
    therapy = option.get("therapy") or ""
    if option.get("drugs") or ctx["disease"] in (None, "metastatic") or OTHER_CLASS_RE.search(therapy):
        return None, None
    has_et, has_cht = bool(ET_RE.search(therapy)), bool(CHT_RE.search(therapy))
    if not (has_et or has_cht):
        return None, None
    note = None
    if has_et and has_cht:   # "ChT followed by ET"
        if ctx["phase"] == "adjuvant" and ctx["prior_chemo"]:
            has_cht, note = False, "선행 항암을 이미 받아 내분비요법을 펼침"
        else:
            has_et, note = False, "항암을 먼저 펼침 (내분비요법은 항암·수술 뒤 다음 단계)"
    rows = [r for r in _class_rows() if r["class"] == ("ET" if has_et else "ChT") and r["disease"] == "early"
            and ctx["subtype"] in r["subtypes"].split(";")]
    # 요법 이름에 함께 적힌 약 (예: "olaparib + ET", "ET + LHRH agonist"). 내분비 약은 사전 규칙이 고르므로 빼고,
    # LHRH가 적혀 있으면 OFS가 든 요법만 쓴다. 그 밖의 약(olaparib, abemaciclib 등)은 조합마다 더한다 (2026-11-18 VC-0107·0119)
    fixed, _ = _fixed_groups(CHT_RE.sub(" ", ET_RE.sub(" ", therapy)))
    is_endo = lambda g: all("hormone therapy" in _drug_classes().get(d, set()) for d in g)   # noqa: E731
    want_lhrh = any(set(g) == {"goserelin", "leuprolide"} for g in fixed)
    extra = [g for g in fixed if not is_endo(g)]
    combos = []
    if has_et:
        if ctx["menopausal"] not in ("premenopausal", "postmenopausal"):
            return None, None   # 폐경 상태를 모르면 펼치지 않는다 (확정값에서 필수)
        for r in rows:
            if r["menopausal"] != ctx["menopausal"] or (r["risk"] == "high" and ctx["high_risk"] == "no"):
                continue
            if want_lhrh and "LHRH" not in r["members"].split("+"):
                continue
            for pick in itertools.product(*[_member_choices(t) for t in r["members"].split("+")]):
                groups = [list(g) for g in pick] + extra
                combos.append((groups, r["source"]))
    else:
        if extra and any(not all("chemotherapy" in _drug_classes().get(d, set()) for d in g) for g in extra):
            return None, None   # 항암에 표적·면역 약이 함께 적힌 후보는 이번 범위 밖 (급여 행이 병용 행이라 따로 봐야 함)
        allowed = _allowed_drugs([t for r in rows for t in r["members"].split(";")])
        if not allowed:
            return None, None
        source = "; ".join(dict.fromkeys(r["source"] for r in rows))
        for c in reimb_by_id.values():
            drugs = [d.lower() for d in c.get("drugs") or []]
            if (drugs and _valid_reimb(c, today) and c.get("source") != "HIRA-offlabel" and set(drugs) <= allowed
                    and (c.get("subtype") in (None, []) or "any" in c["subtype"] or ctx["subtype"] in c["subtype"])):
                combos.append(([[d] for d in dict.fromkeys(drugs)], source))
    if not combos or _row_count([[d for g in groups for d in g] for groups, _ in combos]) > MAX_CANDIDATES:
        return None, None
    out, seen = [], set()
    for groups, source in combos:
        key = tuple(sorted(d for g in groups for d in g))
        if key in seen:
            continue
        seen.add(key)
        temp = {"therapy": therapy, "drugs": list(dict.fromkeys(d for g in groups for d in g)),
                "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "", "reimbursement_citations": []}
        if any(len(g) > 1 for g in groups):
            temp["_groups"] = groups
        _classify(temp, reimb_by_id, today, conditions_checker, exact_only=True)
        out.append({k: temp.get(k) for k in ("drugs", "reimbursement", "reimbursement_basis", "reimbursement_reason",
                                               "reimbursement_citations")} | {"copay": temp.get("copay")})
    return sorted(out, key=lambda c: REIMB_RANK.get(c["reimbursement"], 9)), note


# 맞는 급여 행이 없을 때의 규칙 문구. 이번 결정 단계(선행·보조·고식 차수)의 급여 범위 밖이라는 뜻이다. 허가 범위 안이면
# 약값 전액 본인부담(100분의 100, 공고책자 일반원칙)이라 덧붙이는 말 없이 둔다 (사용자 결정 2026-11-26. 전에는 D #157
# 요청으로 '비급여로 확정한 것은 아님'을 붙였는데 급여가 될 수도 있는 것처럼 읽혔다). 약을 정하지 못한 경우는 NO_CLASS_ROW_REASON
NO_ROW_REASON = "후보 약과 맞는 시행 중인 급여 행 없음"
NO_CLASS_ROW_REASON = ("약 확인 필요: 요법 이름이 계열이라 약을 정하지 못했고, 이번 결정 단계의 급여 행 검색에 "
                       "이 계열 행이 없음. 비급여로 확정한 것은 아님 (요법을 정한 뒤 확인)")


def _classify(option, reimb_by_id, today, conditions_checker, exact_only=False):
    """5번. 급여 분류·이유·근거(reimbursement_basis)를 고친다. 바꾼 내용을 문장 목록으로 돌려준다 (없으면 빈 목록).
    exact_only면 약이 정확히 같은 급여 행만 쓴다 (넓은 계열 후보: 약이 더 든 병용 행의 조건으로 판정하지 않게)."""
    changes = _classify_class(option, reimb_by_id, today, conditions_checker, exact_only)
    option["reimbursement_basis"] = _basis(option)
    return changes


def _basis(option):
    """최종 급여 분류에서 근거 값 (schemas/recommendation.json $defs/reimbursement_basis, 2026-11-17).
    no_criteria를 '맞는 행 없음'과 '조건 불충족'으로 나눠 보인다."""
    cls = option.get("reimbursement")
    if not option.get("drugs") and cls != "offlabel_approved":
        return "drug_undetermined"
    if cls == "offlabel_approved":
        return "offlabel"
    if cls == "covered":
        return "conditions_met"
    if cls == "covered_conditions_unverified":
        return "conditions_unverified"
    reason = option.get("reimbursement_reason") or ""
    return "conditions_not_met" if reason.startswith("급여 조건 불충족") else "no_matching_row"


def _classify_class(option, reimb_by_id, today, conditions_checker, exact_only=False):
    """_classify의 분류 본체."""
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
        # 계열 이름(ChT·ET·항HER2) 후보는 그 계열 약으로만 된 시행 중인 급여 행을 붙이고 '급여(약 확인 필요)'로 둔다.
        # 계열 안의 요법(AC, TC, AC→T 등)마다 급여 조건이 달라 '급여 기준 없음'은 틀린 말이다 (D 의견 2026-11-05 B-12, VC-0118)
        therapy = option.get("therapy") or ""
        named = [k for k, rx in CLASS_TERMS.items() if rx.search(therapy)]
        cited_ids = {c["chunk_id"] for c in valid}
        class_rows = [c for c in reimb_by_id.values()
                      if c["chunk_id"] not in cited_ids and _valid_reimb(c, today) and c.get("source") != "HIRA-offlabel"
                      and c.get("drugs") and any(all(k in _drug_classes().get(d.lower(), set()) for d in c["drugs"])
                                                 for k in named)]
        if class_rows:
            valid = valid + class_rows
            option["reimbursement_citations"] = [c["chunk_id"] for c in valid]
            option.update(reimbursement="covered_conditions_unverified",
                          reimbursement_reason=f"약 확인 필요 (관련 급여 요법 {len(class_rows)}개): "
                                               "계열 안의 요법마다 급여 조건이 다름, 요법을 정한 뒤 확인")
            return changes + [f"계열 이름 후보라 그 계열 급여 행 {len(class_rows)}개를 붙이고 급여(약 확인 필요)로 둠"]
        if valid:   # 인용한 시행 중 급여 행이 있으면 LLM이 no_criteria라고 했어도 조건 확인 필요로 둔다
            option.update(reimbursement="covered_conditions_unverified",
                          reimbursement_reason="후보 약을 정하지 못해 급여 조건을 판정하지 않음, 의사 확인")
            return changes + ([] if cls == "covered_conditions_unverified" else [f"{cls} → 급여(조건 확인 필요) (후보 약 미정)"])
        # 이 계열 급여 행이 검색에 없으면 LLM 분류·문장과 상관없이 규칙 문구로 둔다. '급여 기준 없음'만 보이면 급여가 안 되는
        # 약으로 읽히므로 검색 범위의 문제임을 적는다 (D #157 2026-11-17, VC-0121 'Adjuvant Endocrine Therapy')
        option.update(reimbursement="no_criteria", reimbursement_citations=[], copay=None,
                      reimbursement_reason=NO_CLASS_ROW_REASON)
        return changes + ([] if cls == "no_criteria" else [f"{cls} → 급여 기준 없음 (이 계열 급여 행 검색 안 됨)"])
    # 후보 약과 행 약이 똑같은 행을 먼저 쓰고, 그런 행이 없을 때만 약이 더 든 행을 쓴다 (D 요청 2026-11-04.
    # 예: paclitaxel 후보가 paclitaxel + pembrolizumab 행의 조건으로 급여가 되지 않게)
    current = [c for c in reimb_by_id.values() if _valid_reimb(c, today)]
    if _is_supportive(option):
        # 골 보호제(보조 약물)는 뼈 전이 골 보호 목적의 행만 쓴다. 그런 행은 조건에 bone_metastasis 항목이 있다
        # (supp-zoledronic-b, supp-denosumab-1). 고칼슘혈증 행(supp-zoledronic-a)에는 없다 (D 확인 2026-11-05, B-7)
        current = [c for c in current if _has_condition_field(c, "bone_metastasis")]
    exact = [c for c in current if _drugs_match(option, c, exact=True) or _base_match(option, c)]
    pool = exact if exact_only else (exact or [c for c in current if _drugs_match(option, c)])
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
        # 맞는 행이 없으면 LLM이 처음에 no_criteria라고 썼어도 규칙 문구로 통일한다 (D #157, VC-0121 'Tamoxifen alone'은
        # LLM 문장, VC-0105는 규칙 문구였다)
        option.update(reimbursement="no_criteria", reimbursement_citations=[], reimbursement_reason=NO_ROW_REASON)
        if cls in COVERED_CLASSES:
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
    """골 보호제만으로 된 후보인지. 약이 있으면 모두 골 보호제, 약이 없으면 요법 이름에 골 보호제 말이 있을 때.
    요법 이름에 골 보호제가 아닌 계열 이름(ET 등)이나 약 이름이 섞이면 골 보호제만으로 된 후보가 아니다
    (A 공유 2026-11-05 B-10, 보조 칸에 "ET + bisphosphonate"가 섞임)."""
    drugs = [d.lower() for d in option.get("drugs") or []]
    if drugs and not all(d in _bma_drugs() for d in drugs):
        return False
    therapy = option.get("therapy") or ""
    rest = BMA_TERM_RE.sub(" ", therapy)
    if CLASS_NAME_RE.search(rest) or any(rx.search(rest.lower()) and g not in _bma_drugs() for rx, g in _name_patterns()):
        return False
    return bool(drugs) or bool(BMA_TERM_RE.search(therapy))


# 8번 뒤: 조기 유방암에서 수술 뒤에만 쓰는 약 (보조요법 근거만 있음: abemaciclib monarchE, ribociclib NATALEE, olaparib OlympiA)
# 선행(수술 전) 결정에는 내지 않는다 (A 공유 2026-11-05 B-11, VC-0121)
POST_SURGERY_ONLY = {"abemaciclib", "ribociclib", "olaparib"}
EXTENDED_ET_RE = re.compile(r"[Ee]xtended|연장")


def _near_id(cited: str, known: set) -> str | None:
    """받지 않은 청크 ID가 받은 ID 하나의 오타면 그 ID (2026-11-17, 20261116 VC-0124 'hrpos-05ca0c8d' → 'hrpos-ca0c8d').
    정확히 하나가 맞을 때만 바꾼다. 맞는 경우는 둘이다.
    - 앞부분(마지막 '-' 앞)이 같고, 끝 해시가 서로를 포함하거나 같은 길이에서 한 글자만 다름
    - 앞부분을 두 번 적음: 받은 ID의 앞부분으로 시작하고 끝 해시가 같음 ('hrpos-02-hrpos-49918b', 20261117_fix VC-0121)"""
    if "-" not in cited:
        return None
    head, tail = cited.rsplit("-", 1)
    hits = []
    for k in known:
        if "-" not in k:
            continue
        kh, kt = k.rsplit("-", 1)
        if not kt:
            continue
        if kh == head and (kt in tail or tail in kt or (len(kt) == len(tail) and sum(a != b for a, b in zip(kt, tail)) == 1)):
            hits.append(k)
        elif kh != head and kt == tail and cited.startswith(kh + "-"):
            hits.append(k)
    return hits[0] if len(hits) == 1 else None


def _repair_ids(o: dict, known: set, log: list) -> None:
    """후보의 citations·reimbursement_citations·근거 문장의 [ID]에서 오타 ID를 받은 ID로 고친다."""
    fixed = {}
    for key in ("citations", "reimbursement_citations"):
        for i in o.get(key) or []:
            if i not in known and i not in fixed:
                near = _near_id(i, known)
                if near:
                    fixed[i] = near
    for i in _CITE_RE.findall(o.get("rationale") or ""):
        if i not in known and i not in fixed:
            near = _near_id(i, known)
            if near:
                fixed[i] = near
    if not fixed:
        return
    for key in ("citations", "reimbursement_citations"):
        if o.get(key):
            o[key] = list(dict.fromkeys(fixed.get(i, i) for i in o[key]))
    o["rationale"] = _CITE_RE.sub(lambda m: f"[{fixed.get(m.group(1), m.group(1))}]", o.get("rationale") or "")
    log.append(f"{o.get('therapy')}: 청크 ID 오타를 받은 ID로 고침 {fixed}")


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


LHRH_DRUGS = {"goserelin", "leuprolide", "triptorelin"}


def _early_bma_supportive(guideline_chunks, done):
    """8번: 수술 후 보조요법 bisphosphonate 권고 청크(뼈 전이 청크가 아닌, 골 보호제가 든 조기 청크)의 골 보호제를
    보조 후보로 만든다 (LLM이 빠뜨렸을 때, A 공유 2026-11-05 B-6, B·C 합의). 근거 문장은 정해진 틀이고 원문을 옮기지 않는다.
    약 묶는 법은 _bone_supportive와 같다 (본문에 이름이 나오는 약은 따로, 나머지는 bisphosphonates 계열 한 줄)."""
    out = []
    for c in guideline_chunks:
        cid = c["chunk_id"]
        if "site-bone" in cid or "early" not in (c.get("setting") or []):
            continue
        bma = [d for d in (x.lower() for x in c.get("drugs") or []) if d in _bma_drugs()]
        if not bma:
            continue
        ev = c.get("evidence") or {}
        base = {"rationale": f"폐경 후 또는 난소 기능 억제 중인 여성의 수술 후 보조요법으로 bisphosphonate가 권고된다 [{cid}].",
                "citations": [cid],
                "evidence": (f"LoE {ev['loe']}" + (f", GoR {ev['gor']}" if ev.get("gor") else "")) if ev.get("loe") else None,
                "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "", "reimbursement_citations": []}
        text = (c.get("text") or "").lower()
        named = [d for d in bma if d in text and d not in done]
        for d in named:
            done.add(d)
            out.append({**base, "therapy": d, "drugs": [d]})
        group = [d for d in bma if d not in named and d not in done]
        if group:
            done.update(group)
            out.append({**base, "therapy": f"bisphosphonates 계열 ({', '.join(group)} 중 하나)", "drugs": group,
                        "_groups": [group]})
    return out


def postprocess(recommendation, biomarker_record, guideline_chunks, reimbursement_chunks, today=None,
                conditions_checker=None, phase=None, bone_metastasis=False, high_risk_early=None, menopausal=None,
                ofs=False):
    """추천 결과를 고쳐서 돌려준다. (고친 결과, 로그 목록). 받은 값은 바꾸지 않는다.
    conditions_checker(option, 급여 청크 목록) -> {status, reason}: 급여 조건 판정 (conditions_eval.make_conditions_checker).
    phase(neoadjuvant / adjuvant / None)·bone_metastasis(bool)는 8번 보조 약물 규칙에, phase·high_risk_early
    (confirmed_state의 {hira, esmo})는 조기 결정 단계 규칙에, menopausal·ofs(난소 기능 억제를 받는 중)는 수술 후
    bisphosphonate 보조 칸 채우기에 쓴다."""
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
    setting = biomarker_record.get("setting") or {}
    risk = (high_risk_early or {}).get("esmo") if isinstance(high_risk_early, dict) else None
    class_ctx = {"disease": setting.get("disease"), "subtype": biomarker_record.get("subtype"), "menopausal": menopausal,
                 "high_risk": risk if risk in ("yes", "no") else None, "phase": phase,
                 "prior_chemo": "Chemotherapy" in (setting.get("prior_drug_classes") or [])}
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
        _repair_ids(o, set(guide_by_id) | set(reimb_by_id), log)
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
            # 2번 뒤: 지침 인용이 남지 않았어도, 후보 약이 모두 넘겨받은 지침 청크에 있으면 지우지 않는다. LLM의 근거 없는 문장은
            # 보여 주지 않고, 약이 든 청크(관련도 순서로 첫 것)를 붙인 정해진 문장으로 대신한다. 근거 없는 내용을 보여 주지
            # 않는 원칙은 지키면서 맞는 약을 살린다 (A 공유 2026-11-05 §7 B-13: LLM이 [ID]를 빠뜨리거나 급여 행 ID만 인용해
            # 맞는 약이 지워짐). 약을 정하지 못한 후보는 살리지 않는다
            _fill_drugs_evidence(o, [])
            found = [next((c["chunk_id"] for c in guideline_chunks if _drug_in_chunks(d, [c])), None)
                     for d in o.get("drugs") or []]
            if not found or None in found:
                log.append(f"후보 삭제: {name} (지침 인용이 있는 근거 문장 없음)")
                return False
            cites = list(dict.fromkeys(found))
            o["rationale"] = " ".join(f"이 요법의 약이 지침 권고에 있다 [{cid}]." for cid in cites) + \
                (" " + o["rationale"] if o["rationale"] else "")
            log.append(f"{name}: 지침 인용이 없어 약이 든 받은 지침 청크를 근거로 붙이고 정해진 문장으로 씀 {cites}")
        o["citations"] = cites
        filled, unresolved = _fill_drugs_evidence(o, [guide_by_id[i] for i in cites])
        if filled:
            log.append(f"{name}: 빈 칸을 인용한 지침 청크에서 채움 ({', '.join(filled)})")
        if unresolved:
            rec["conflicts"].append(f"{name}: {unresolved}")
            log.append(f"{name}: {unresolved}")
        elif not o.get("drugs") and not _is_supportive(o):
            if CLASS_WORD_RE.search(name or ""):
                # 7번 계열 이름 목록(CLASS_NAME_RE)에 없는 계열 이름(예: "PARP 억제제", "ADC")도 약 후보로 보고 남긴다.
                # 약은 정하지 않고 의사 확인으로 둔다 (D 확인 2026-11-12, VC-0113·0125)
                note = "요법 이름에 계열 이름이 있어 약을 정하지 못함, 의사 확인 필요"
                rec["conflicts"].append(f"{name}: {note}")
                log.append(f"{name}: {note}")
            else:
                # 약도 약 계열 이름도 없는 후보(예: 다학제 회의 토론, 국소 치료)는 처방 후보가 아니라 참고로 옮긴다 (A 공유 §7 B-14)
                rec["conflicts"].append(f"참고 (약 후보 아님): {name}")
                log.append(f"후보 삭제: {name} (약이 아닌 후보라 참고로 옮김)")
                return False
        # 3번 앞: 인용한 지침 청크에 후보 약이 없지만 넘겨받은 다른 지침 청크에 그 약이 있으면, 그 청크(관련도 순서로 첫 것)를
        # 근거에 더한다 (A 공유 2026-11-05 B-5, VC-0127 sacituzumab). 지어낸 근거가 아니라 받은 청크에 약이 있음을 확인하는 것
        added_for_drug = []
        for d in [d for d in o.get("drugs") or [] if not _drug_in_chunks(d, [guide_by_id[i] for i in cites])]:
            other = next((c["chunk_id"] for c in guideline_chunks if c["chunk_id"] not in cites and _drug_in_chunks(d, [c])), None)
            if other:
                cites.append(other)
                added_for_drug.append(other)
                log.append(f"{name}: 인용한 청크에 {d}가 없어 그 약이 든 받은 청크를 근거에 더함 ({other})")
        # 3번 앞: 후보 약과 상관없는 인용은 뺀다 (A 공유 2026-11-05 B-10, B-5의 반대 방향). 약이 든 다른 인용이 남을 때만.
        # 약이 있는 후보: 청크 drugs가 있는데 후보 약이 하나도 안 나오는 청크. 골 보호제가 아닌 후보: 골 보호제만 다루는 청크
        def unrelated(cid):
            c = guide_by_id[cid]
            chunk_drugs = [x.lower() for x in c.get("drugs") or []]
            if not chunk_drugs:
                return False
            if not _is_supportive(o) and all(x in _bma_drugs() for x in chunk_drugs):
                return True
            return bool(o.get("drugs")) and not any(_drug_in_chunks(d, [c]) for d in o["drugs"])
        keep = [i for i in cites if not unrelated(i)]
        if keep and len(keep) < len(cites):
            dropped_ids = [i for i in cites if i not in keep]
            log.append(f"{name}: 후보 약과 상관없는 인용 뺌 {dropped_ids}")
            cites = keep
            if added_for_drug:   # 바로 위에서 약이 든 청크를 더했으면, 뺀 인용을 문장 안에서 그 청크로 바꾼다
                o["rationale"] = _CITE_RE.sub(lambda m: f"[{added_for_drug[0]}]" if m.group(1) in dropped_ids
                                              else m.group(0), o["rationale"])
            o["rationale"], _, gone = _keep_cited_sentences(o["rationale"], set(keep) | set(reimb_by_id))
            if gone:
                log.append(f"{name}: 뺀 인용만 있던 문장 {gone}개 삭제")
            if not o["rationale"]:
                log.append(f"후보 삭제: {name} (상관없는 인용을 빼자 근거 문장이 남지 않음)")
                return False
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
        cands = _narrow_candidates(o, [guide_by_id[i] for i in cites], reimb_by_id, today, conditions_checker)
        kind, note = "좁은 계열", None
        if not cands:
            cands, note = _broad_candidates(o, reimb_by_id, today, conditions_checker, class_ctx)
            kind = "넓은 계열(ET·ChT)"
        if not cands and not _is_supportive(o):
            cands, kind = _one_of_candidates(o, reimb_by_id, today, conditions_checker), "LHRH 작용제 묶음"
        if cands:
            _apply_candidates(o, cands)
            if note:
                o["reimbursement_reason"] += f" ({note})"
            log.append(f"{name}: {kind}을 약 조합 {_row_count(cands)}개로 펼쳐 급여 판정 ({o['reimbursement_reason']})")
            # 확인 띠의 "약을 정하지 못함" 문구는 조합을 고르라는 안내로 바꾼다 (화면 2에서 조합을 고른다)
            old = f"{name}: {unresolved}" if unresolved else None
            if old in rec["conflicts"]:
                rec["conflicts"][rec["conflicts"].index(old)] = f"{name}: 계열 이름이라 약 조합 {_row_count(cands)}개 중 하나를 고를 것"
        return True

    main, support = [], []
    for o in rec["options"]:
        if check(o):
            if _is_supportive(o):
                log.append(f"{o.get('therapy')}: 골 보호제라 보조 약물 칸으로 옮김")
                support.append(o)
            else:
                main.append(o)
    # 조기 결정 단계 (A 공유 2026-11-05 B-11): 선행(수술 전) 결정에는 수술 뒤에만 쓰는 약·연장 내분비요법을 내지 않고,
    # ESMO 기준 고위험이 아니면(high_risk_early.esmo = no) abemaciclib 보조요법을 내지 않는다
    if disease != "metastatic":
        kept_main = []
        esmo_risk = (high_risk_early or {}).get("esmo") if isinstance(high_risk_early, dict) else None
        for o in main:
            drugs = {d.lower() for d in o.get("drugs") or []}
            # 계열 이름 후보(#151)는 약 목록이 비어 있어 요법 이름의 약 이름도 본다 (2026-11-17, 20261116 VC-0121·0124)
            therapy = o.get("therapy") or ""
            named = {d for d in POST_SURGERY_ONLY if d in therapy.lower()}
            why = None
            # 이름의 'Adjuvant'는 보지 않는다: 'Adjuvant ChT followed by ET'처럼 선행 항암 후 ET를 잘못 이름 붙인
            # 정답 후보가 지워졌다 (20261117_fix VC-0121). 수술 뒤에만 쓰는 약 이름만 본다
            if phase == "neoadjuvant" and (drugs & POST_SURGERY_ONLY or named or EXTENDED_ET_RE.search(therapy)):
                why = "선행요법 결정이라 수술 뒤에 쓰는 약은 해당 없음"
            elif esmo_risk == "no" and "abemaciclib" in drugs | named:
                why = "고위험 조기 유방암이 아니라 abemaciclib 보조요법 해당 없음"
            if why:
                log.append(f"후보 삭제: {o.get('therapy')} ({why})")
            else:
                kept_main.append(o)
        main = kept_main
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
    # 8번: 수술 후 보조요법 결정(HR+/HER2-)에서 폐경 후이거나 난소 기능 억제(OFS) 중이면, bisphosphonate 권고 청크가 왔는데
    # LLM이 빠뜨렸을 때 규칙으로 채운다. ESMO "난소 기능이 없는 여성(폐경 후 또는 OFS)에게 권고, 특히 재발 고위험"이라
    # 고위험은 필수 조건이 아니다. 선행 결정은 위에서 이미 뺐다 (A 공유 2026-11-05 B-6, B·C 합의, v0.1은 HR+/HER2-만)
    ofs_now = ofs or any({d.lower() for d in o.get("drugs") or []} & LHRH_DRUGS for o in main)
    if (disease in ("early", "locally_advanced") and phase == "adjuvant" and biomarker_record.get("subtype") == "HR+/HER2-"
            and (menopausal == "postmenopausal" or ofs_now)):
        done = {d.lower() for o in support for d in o.get("drugs") or []}
        if not done & set(_bma_drugs()):
            for o in _early_bma_supportive(guideline_chunks, done):
                log.append(f"{o['therapy']}: 수술 후 bisphosphonate 권고 청크가 있어 보조 약물 칸에 채움 ({o['citations'][0]})")
                log.extend(f"{o['therapy']}: {c}" for c in _classify(o, reimb_by_id, today, conditions_checker))
                support.append(o)
    for o in main + support:
        o.pop("_groups", None)   # 내부용 (스키마에 없는 칸)
    rec["options"], rec["supportive_options"] = main, support
    return rec, log
