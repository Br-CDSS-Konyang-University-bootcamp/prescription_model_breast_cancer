"""로컬 모델 초안의 확인 (조건을 맞는 칸·값으로 옮겼는지). 걸리면 사람 검토로 돌린다.

원문 구절이 원문에 있는지(conditions.check_grounding)만으로는 '구절은 맞는데 칸·값을 잘못 고른' 오류를 못 막는다.
그래서 초안에 아래를 더 본다. 1~3은 사람이 쓴 저장본 131행에는 하나도 걸리지 않게 맞췄다 (테스트).

  1. 팀 사전 대조: 항목 구절에 data/dictionaries/reimbursement_terms.csv의 표현(병기·수용체·폐경 등 칸이 분명한 것)이
     있으면 그 항목 칸이 사전의 칸과 같은지, 값이 정해진 표현이면 값도 같은지
  2. 숫자 대조: 숫자 칸 항목의 구절에 숫자가 있으면 값이 그 숫자(단위를 바꾼 값 포함)와 같은지
  3. 빠진 조건: 투여대상 문장 중 어느 구절에도 들어가지 않은 부분에 사전 표현이나 숫자가 남았는지
  4. 두 답 비교: 다른 질문(다른 예시, 이전 판 없이)으로 한 번 더 만든 답과 판정에 쓰는 항목이 같은지.
     1~3은 칸·숫자 실수만 잡고, 조건 빠뜨림·더 넣음·묶음 위치 차이는 4가 잡는다 (2026-11-02 131행 평가)

걸린 것은 그 원문 구절을 human_review에 넣는다. human_review가 있는 행은 판정에서 '알 수 없음'이다 (설계 §9.4).
통과해도 정답이 보장되지는 않으므로 초안은 검수 전으로 남는다 (검수표).
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from .conditions import FIELDS, _norm, iter_items, _NUM

TERMS_CSV = Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "reimbursement_terms.csv"

# 팀 사전 json_field -> 이 표현이 들어갈 수 있는 조건 칸. 칸이 분명한 분류만 쓴다
# (history·line·drug·regimen·reimbursement 표현은 '진행'·'투여 종료'처럼 여러 칸에 걸쳐 대조하지 않는다)
_FIELD_MAP = {
    "stage.disease_extent": {"disease"},
    "recurrence.status": {"recurrence"},
    "stage.operable": {"operable", "recurrence_operable"},
    "stage.group": {"stage_group"},
    "stage.ptnm.n": {"cn_status", "pn_status", "positive_ln_count"},
    "stage.positive_ln_count.positive": {"positive_ln_count"},
    "diagnosis.grade": {"grade"},
    "records[marker=HER2].status": {"her2", "subtype"},
    "subtype": {"hr", "subtype", "er", "pr"},
    "records[marker=ER].status": {"er", "hr"},
    "records[marker=PR].status": {"pr", "hr"},
    "records[marker=ER/PR].status": {"hr", "er", "pr", "subtype"},
    "records[marker=PD-L1].status": {"pdl1_22c3_cps"},
    "receptors.pdl1.value.score_type": {"pdl1_22c3_cps"},
    "receptors.pdl1.value.assay": {"pdl1_22c3_cps"},
    "neoadjuvant_response.pcr": {"pcr"},
    "patient.menopausal_status": {"menopause"},
}
# 크기·염증성은 사전에 T 칸(stage.ptnm.t)으로 적혀 있지만, 조건 칸은 치료 시기별 병기·크기 칸이다 (conditions.FIELDS)
_T_FIELDS = {"ct_stage", "pt_stage", "clinical_size_mm", "pathologic_size_mm"}
# 사전 값 -> 조건 값 (값을 대조하는 칸만). 사전 값이 조건 값과 다르게 적힌 칸은 대조하지 않는다
_VALUE_FIELDS = {"disease", "recurrence", "operable", "her2", "menopause", "pcr"}


def _key(s: str) -> str:
    """대조용: 괄호 안 글과 공백을 뺀다 ('호르몬 수용체(ER and PR) 음성' -> '호르몬수용체음성')."""
    return re.sub(r"\s+", "", re.sub(r"\([^)]*\)", "", s or ""))


@lru_cache(maxsize=1)
def terms() -> tuple[tuple[str, frozenset[str], frozenset | None], ...]:
    """(대조 글, 들어갈 수 있는 칸, 값 또는 None). 값은 값을 대조하는 칸이고 사전에 값이 있을 때만."""
    out = []
    with open(TERMS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            jf = r["json_field"]
            fields = _FIELD_MAP.get(jf) or (_T_FIELDS if jf == "stage.ptnm.t" else None)
            if not fields:
                continue
            vals = [v.strip() for v in r["json_value"].split("|") if v.strip()]
            if r["notice_term"] == "병리학적 완전관해 (pCR)":
                vals = []                        # '도달하지 않은' -> no 처럼 앞뒤 말로 값이 바뀐다
            # 값은 사전이 정한 표현(match exact·multi)만 대조한다. partial('진행성' 등)은 앞뒤 말로 값이 정해진다
            value = (frozenset(vals) if vals and fields & _VALUE_FIELDS and jf != "stage.ptnm.n"
                     and r["match"] in ("exact", "multi") else None)
            for variant in r["notice_term"].split(" / "):
                k = _key(variant)
                if jf == "stage.group" and len(k) == 1:
                    k = "stage" + k              # 'stage Ⅰ / Ⅱ / …'의 Ⅱ 등은 stage가 붙은 것만
                if len(k) >= 2:
                    out.append((k, frozenset(fields), value))
    return tuple(out)


_DICT_FIELDS = frozenset().union(*_FIELD_MAP.values(), _T_FIELDS)
# 사전에 없는 칸의 낱말. 여기 없는 칸(이전 치료·기간 등)은 사전 대조를 하지 않는다
_OWN_WORDS = {"age": r"\d\s*세", "age_at_index": r"\d\s*세", "sex": r"여성|남성|여자|남자"}


def _found(text: str) -> list[tuple[str, frozenset[str], frozenset | None]]:
    """구절에 있는 사전 표현. 괄호 안 글을 뺀 것과 그대로인 것 모두에서 찾고,
    다른 표현 안에 든 짧은 표현은 뺀다 ('국소진행성' 안의 '진행성')."""
    keys = (_key(text), re.sub(r"\s+", "", text or ""))
    hits = [t for t in terms() if any(t[0] in k for k in keys)]
    if re.search(r"\d\s*기(?!간)", text or ""):           # '2기 및 3기'처럼 숫자로 적은 병기 (사전에는 로마숫자만)
        hits.append(("n기", frozenset({"stage_group"}), None))
    return [t for t in hits if not any(t[0] != o[0] and t[0] in o[0] for o in hits)]


_UNIT = r"(cm|㎝|mm|㎜|개월|달|년|주|일|세|개|주기|차|㎎|mg)?"


def _numbers(text: str, field: str) -> set[float]:
    """구절의 숫자로 나올 수 있는 값 (단위를 칸 단위로 바꾼 값 포함)."""
    out = set()
    # 이름 안의 숫자(HER2, CDK4/6, 22C3의 3)는 뺀다
    for n, unit in re.findall(r"(?<![A-Za-z0-9/.])(\d+(?:\.\d+)?)\s*" + _UNIT, text or ""):
        n = float(n)
        out.add(n)
        if unit in ("cm", "㎝"):
            out.add(n * 10)
        elif unit == "년":
            out.add(n * 365)
        elif unit in ("개월", "달"):
            out |= {n * 30, float(int(n * 365 / 12 + 0.5))}
        elif unit == "주":
            out.add(n * 7)
        if field.endswith("_lines"):              # 'n차 이상' = 이미 n-1차를 받음
            out.add(n - 1)
    return out


def _item_issues(where: str, it: dict) -> list[str]:
    f, op, val, text = it.get("field"), it.get("op"), it.get("value"), it.get("text") or ""
    out = []
    # 사전에 칸이 없는 조건(sex, age 등)은 구절에 그 칸의 낱말이 있으면 다른 표현이 같이 있어도 된다
    # ('폐경기 이후 여성 및 남성' -> sex). 낱말도 없으면 사전 표현의 칸과 다른 것으로 본다
    found = _found(text)
    if f not in _DICT_FIELDS and (f not in _OWN_WORDS or re.search(_OWN_WORDS[f], text)):
        found = []
    if found and not any(f in fields for _, fields, _ in found):
        out.append(f"{where}: 구절의 사전 표현({', '.join(t for t, _, _ in found)})과 칸 {f}이 다름")
    same = [t for t in found if f in t[1] and t[2] is not None]
    if len(same) == 1 and op in ("eq", "in"):
        got = frozenset(val if isinstance(val, list) else [val])
        if got != same[0][2]:
            out.append(f"{where}: 사전 값 {sorted(same[0][2])}과 다름 ({sorted(got, key=str)})")
    if f in FIELDS and FIELDS[f][2] == _NUM and op != "exists":
        nums = _numbers(text, f)
        vals = val if isinstance(val, list) else [val]
        if nums and not all(isinstance(v, (int, float)) and float(v) in nums for v in vals):
            out.append(f"{where}: 값 {val}이 구절의 숫자와 다름")
    return out


def _target_part(text: str) -> str:
    """유방암 표 행의 투여대상 칸: '투여대상:' 뒤부터 각주(주1. …)·묶음 안내(▪, 연번 20∼24 …) 앞까지, 공고 번호는 뺀다."""
    body = re.sub(r"^\[[^\]]*\]\n", "", text)
    m = re.search(r"투여\s*대상\s*:?", body)
    if not m:
        return ""
    body = body[m.end():]
    end = re.search(r"\n\s*(?:주\s*\d+\s*\.|▪|•|연번\s*\d+\s*[∼~-])", body)
    if end:
        body = body[:end.start()]
    return re.sub(r"\((?:제|개정)[^)]*\)", " ", body)


# 빠진 조건으로 볼 숫자: 단위가 붙은 것만 ('(2)'·'①' 같은 번호는 빼고)
_UNIT_NUM = re.compile(r"(?<![A-Za-z0-9/.])\d+(?:\.\d+)?\s*(?:cm|㎝|mm|㎜|개월|달|년|세|개|주기|%)")


def _quotes(cond: dict) -> list[str]:
    out = []
    for _, it in iter_items(cond):
        out.append(it.get("text") or "")
        if it.get("unless"):
            out.append(it["unless"].get("text") or "")
    for key in ("any_of", "any_of_exceptions", "counts_as_prior_line"):
        out += [g.get("text") or "" for g in cond.get(key, [])]
    for key in ("notes", "human_review", "unmapped"):
        out += list(cond.get(key, []))
    return [q for q in map(_norm, out) if q]


def uncovered(cond: dict, text: str) -> list[str]:
    """투여대상 칸 중 어느 구절에도 들어가지 않은 부분 (공백 뺀 글). 사전 표현이나 단위가 붙은 숫자가 있는 것만.
    병용요법·Ⅳ 기타 약제는 칸 구조가 달라(허가사항과 급여기준이 겹침) 투여대상 칸이 없으면 보지 않는다."""
    part = _norm(_target_part(text))
    covered = [False] * len(part)
    for q in _quotes(cond):
        for m in re.finditer(re.escape(q), part):
            covered[m.start():m.end()] = [True] * len(q)
    runs = re.findall(r"[^\x00]+", "".join("\x00" if c else ch for ch, c in zip(part, covered)))
    return [r for r in runs if _UNIT_NUM.search(r) or _found(r)]


def verify_conditions(cond: dict, text: str) -> list[tuple[str, str]]:
    """(문제, 사람 검토로 넣을 원문 구절) 목록. 구절은 원문에 있는 글이라 원문 구절 검사를 통과한다.
    text는 행 본문 (투여대상 칸을 찾는다). 소단원 안내에서 인용한 항목도 칸·숫자 대조는 한다."""
    out = []
    for where, it in iter_items(cond):
        for msg in _item_issues(where, it):
            out.append((msg, it.get("text") or ""))
        if it.get("unless"):
            for msg in _item_issues(f"{where}.unless", it["unless"]):
                out.append((msg, it["unless"].get("text") or ""))
    for run in uncovered(cond, text):
        out.append((f"투여대상 중 조건으로 옮기지 않은 부분 '{run}'", run))
    return out


# ---------- 두 답 비교 ----------

def item_key(where: str, it: dict) -> str:
    """항목을 비교할 열쇠: 묶음 위치(번호 없이) + field·op·value·of. 글과 id는 달라도 된다."""
    place = re.sub(r"\[\d+\]", "", where)
    value = sorted(it["value"], key=str) if isinstance(it.get("value"), list) else it.get("value")
    of = {k: sorted(v) for k, v in (it.get("of") or {}).items()}
    return json.dumps([place, it.get("field"), it.get("op"), value, of], ensure_ascii=False, sort_keys=True)


def keyed_items(cond: dict) -> list[tuple[str, str]]:
    """(열쇠, 원문 구절). 판정에 쓰는 것 전부: 조건 항목, unless, 간주 규칙."""
    out = []
    for where, it in iter_items(cond):
        out.append((item_key(where, it), it.get("text") or ""))
        if it.get("unless"):
            out.append((item_key(where + ".unless", it["unless"]), it["unless"].get("text") or ""))
    for g in cond.get("counts_as_prior_line") or []:
        out.append((json.dumps(["counts_as_prior_line", sorted(g.get("setting") or []), sorted(g.get("drugs") or []),
                                g.get("within_days"), g.get("rule_id")], ensure_ascii=False), g.get("text") or ""))
    return out


def disagreements(first: dict, second: dict, source: str) -> list[tuple[str, str | None]]:
    """두 답이 다른 곳: 한쪽에만 있는 항목과, human_review·unmapped가 한쪽에만 있는 것. 구절은 원문에 있는 것만."""
    src = _norm(source)
    a, b = keyed_items(first), keyed_items(second)
    ka, kb = [k for k, _ in a], [k for k, _ in b]
    out = []
    for keys, other, items, label in ((ka, kb, a, "첫 답에만"), (kb, ka, b, "두 번째 답에만")):
        for k, quote in items:
            if keys.count(k) > other.count(k):
                f = json.loads(k)[1] if not k.startswith('["counts_as_prior_line"') else "간주 규칙"
                out.append((f"두 답이 다름: {label} 있는 {f}", quote if _norm(quote) and _norm(quote) in src else None))
    for key in ("human_review", "unmapped"):
        if bool(first.get(key)) != bool(second.get(key)):
            q = next((t for t in (first.get(key) or second.get(key)) if _norm(t) in src), None)
            out.append((f"두 답이 다름: {key}", q))
    return out


def flag_for_review(cond: dict, text: str, extra: list[tuple[str, str | None]] = ()) -> tuple[dict, list[str]]:
    """확인에 걸린 구절을 human_review에 더한다 (이미 있으면 그대로). (조건, 문제 목록)을 돌려준다.
    extra: 그 밖의 문제 (두 답 비교). 구절이 없으면 첫 조건 항목의 구절을 넣어 행이 '알 수 없음'이 되게 한다."""
    issues = verify_conditions(cond, text) + list(extra)
    if not issues:
        return cond, []
    hr = list(cond.get("human_review", []))
    fallback = next((q for _, q in keyed_items(cond) if q), None) or _target_part(text).strip()[:40] or None
    for _, quote in issues:
        quote = quote or fallback
        if quote and quote not in hr:
            hr.append(quote)
    return {**cond, "human_review": hr}, [m for m, _ in issues]
