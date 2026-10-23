"""IN-3 정규화 [규칙] (notes/input_module_design.md §2 IN-3).

후보 하나(칸 + 원문 구절)를 표준값으로 바꾼다. LLM은 값을 계산하지 않으므로 여기가 값을 만드는 유일한 곳이다.
표현 사전은 TCGA 정답 생성기와 같은 data/dictionaries/field_vocab.csv(결과 단어·조직형·폐경)와 drug_names.csv(약 이름).

    normalize("receptors.er_percent", "ER positive (Allred 8, 5+3)", ctx)
    -> {"status": "present", "value": {"allred": {"total": 8, "ps": 5, "is": 3}, "result": "positive"}}

대부분 구절만 본다. 예외 (Context):
- treatment_history의 setting: 구절이 든 줄의 "보조·선행·고식" (투약 표의 첫 칸). 없으면 None → 4단계가 전이일과 비교해 정한다
- imaging_findings의 modality·date: 문서 머리글·문서 날짜
- stage.yptnm의 잔존 크기·림프절 수: 같은 문서의 "잔존 종양 크기", "림프절" 줄
- *_day: 진단일 기준 일수라 진단일(dx_date)이 있어야 한다

다른 후보와 맞춰 봐야 하는 값(progression_day, 차수, 간주 규칙)은 4단계(assemble)가 채운다.
정규화하지 못하면 None을 돌려준다 (확인 요청 목록으로 보낼 후보).
"""
from __future__ import annotations

import csv
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from src.input.classify import DATE, Document
from src.input.common.lines import load_drug_table
from src.input.common.vocab import Vocab

DRUG_NAMES_CSV = Path(__file__).resolve().parents[2] / "data" / "dictionaries" / "drug_names.csv"
VOCAB = Vocab()

NOT_DONE = re.compile(r"미시행|시행하지 않|검사하지 않|not done", re.I)
PENDING = re.compile(r"결과 대기|pending|검사 중|의뢰함", re.I)
PLANNED = re.compile(r"시행 예정|예정|예약")
NEGATION = re.compile(r"없음|아님|no evidence|negative for", re.I)
SITES = [  # field_vocab.csv metastatic_sites 표준값 순서
    ("bone", r"뼈|골|척추|bone|osseous"),
    ("liver", r"(?<![가-힣])간(?![가-힣])|liver|hepatic"),
    ("lung", r"(?<![가-힣])폐(?!경)|lung|pulmonary"),
    ("brain", r"뇌|brain"),
    ("skin", r"피부|skin"),
]
ROMAN = {"0": "0", "1": "I", "2": "II", "3": "III", "I": "I", "II": "II", "III": "III"}


@dataclass
class Context:
    doc: Document
    line: str = ""                  # 구절이 든 줄 전체
    dx_date: str | None = None      # 진단일 (YYYY-MM-DD)

    @classmethod
    def of(cls, doc: Document, char_start: int, dx_date: str | None = None) -> "Context":
        """char_start는 차트 원문 기준 위치 (quote.locate의 결과)."""
        i = char_start - doc.start
        s = doc.text.rfind("\n", 0, i) + 1
        e = doc.text.find("\n", i)
        return cls(doc, doc.text[s:e if e >= 0 else len(doc.text)], dx_date)


def normalize(field: str, quote: str, ctx: Context) -> dict | None:
    """칸 하나의 값. 목록 칸(treatment_history 등)은 항목 dict, 그 밖에는 {status, value}. 실패하면 None."""
    if field.startswith("molecular."):
        return _gene(field.rsplit(".", 1)[1], quote)
    if field in ITEMS:
        return ITEMS[field](quote, ctx)
    if NOT_DONE.search(quote):
        return {"status": "not_done"}
    if PENDING.search(quote):
        return {"status": "not_done", "raw": "결과 대기"}
    if PLANNED.search(quote):
        return {"status": "not_done", "raw": "예정"}
    parse = PARSERS.get(field)
    value = parse(quote, ctx) if parse else None
    return None if value is None else {"status": "present", "value": value}


# ---------- 공통 ----------
def _num(s: str):
    x = float(s)
    return int(x) if x.is_integer() else x


def parse_date(text: str) -> str | None:
    m = DATE.search(text)
    return None if not m else dt.date(*(int(g) for g in m.groups())).isoformat()


def _day(date: str | None, dx_date: str | None) -> int | None:
    if date is None or dx_date is None:
        return None
    return (dt.date.fromisoformat(date) - dt.date.fromisoformat(dx_date)).days


def _vocab(field: str, text: str) -> str | None:
    """사전 표현 중 text에 들어 있는 가장 긴 것의 표준값. 영문 표현은 단어 경계를 본다."""
    best, low = None, text.casefold()
    for expr, canonical in VOCAB.mapping(field).items():
        pat = r"\s+".join(re.escape(w) for w in expr.split(" "))
        if expr[0].isascii() and expr[0].isalnum():
            pat = r"(?<![a-z0-9])" + pat
        if expr[-1].isascii() and expr[-1].isalnum():
            pat += r"(?![a-z0-9])"
        if re.search(pat, low) and (best is None or len(expr) > best[0]):
            best = (len(expr), canonical)
    return best and best[1]


def _sites(text: str) -> list[str]:
    return [site for site, pat in SITES if re.search(pat, text, re.I)]


def _size_mm(text: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|mm)", text)
    return None if not m else _num(str(round(float(m.group(1)) * (10 if m.group(2) == "cm" else 1), 1)))


def _yes_no(text: str) -> str:
    return "no" if re.search(r"없음|아님|불가|inoperable|\bno\b", text, re.I) else "yes"


# ---------- 칸별 ----------
def _grade(q, ctx):
    m = re.search(r"(?:grade|NG|G)\s*([1-3])", q, re.I) or re.search(r"(?<![A-Za-z])(III|II|I)(?![A-Za-z])", q)
    return None if not m else {"I": 1, "II": 2, "III": 3}.get(m.group(1)) or int(m.group(1))


def _tnm(q, ctx, *, prefix):
    m = re.search(r"(yp|p|c)?T(is|[0-4][a-d]?|X)\s*(?:\(\w+\))?\s*(?:y?p|c)?N([0-3][a-c]?(?:mi)?|X)\s*(?:\(\w+\))?"
                  r"\s*(?:M([01X]))?", q)
    # 접두어가 칸과 다르면 받지 않는다 (경과기록의 pT2N0M0를 ctnm 칸에 넣은 경우 등). 접두어가 없으면 받는다
    if not m or m.group(1) not in (None, prefix):
        return None
    ed = re.search(r"AJCC\s*(\d+(?:st|nd|rd|th))", q)
    v = {"t": f"T{m.group(2)}", "n": f"N{m.group(3)}", "m": m.group(4) and f"M{m.group(4)}",
         "edition": ed and ed.group(1)}
    if prefix == "yp":
        # ypTNM에 M이 없으면 M0 (수술 병기). 잔존 크기·림프절 수는 같은 문서의 다른 줄에서 읽는다
        v["m"] = v["m"] or "M0"
        size = re.search(r"(?:잔존 (?:종양 )?크기|residual (?:tumor )?size)\s*:\s*(.+)", ctx.doc.text, re.I)
        ln = re.search(r"(?:림프절|lymph node)\s*:\s*(\d+)\s*/\s*(\d+)", ctx.doc.text, re.I)
        v.update({"residual_size_mm": size and _size_mm(size.group(1)),
                  "positive_ln": ln and int(ln.group(1)), "examined_ln": ln and int(ln.group(2))})
    return v


def _group(q, ctx):
    m = re.search(r"stage\s*(IV|III[A-C]?|II[AB]?|I[AB]?|0)(?![A-Za-z])", q, re.I) \
        or re.search(r"(IV|III[A-C]?|II[AB]?|I[AB]?)\s*기", q)
    return m and m.group(1).upper()


def _extent(q, ctx):
    g = _group(q, ctx)
    if g is None:
        return None
    return "metastatic" if g.startswith("IV") else "locally_advanced" if g.startswith("III") else "early"


def _metastatic_sites(q, ctx):
    if re.search(r"M0(?![0-9])", q) or NEGATION.search(q):
        return "[Not Applicable]"
    return _sites(q) or None


def _ln_count(q, ctx):
    m = re.search(r"(\d+)\s*/\s*(\d+)", q) or re.search(r"전이\s*(\d+)\s*개\s*/\s*검사\s*(\d+)\s*개", q)
    return m and {"positive": int(m.group(1)), "examined": int(m.group(2))}


def _receptor(field):
    def parse(q, ctx):
        v = {}
        m = re.search(r"Allred(?:\s*score)?\s*(\d)(?:\s*[,(]?\s*(?:PS\s*)?(\d)\s*\+\s*(?:IS\s*)?(\d))?", q, re.I)
        if m:
            total = int(m.group(1))
            ps, is_ = (int(m.group(2)), int(m.group(3))) if m.group(2) else (0, 0) if total == 0 else (None, None)
            v["allred"] = {"total": total, **({"ps": ps, "is": is_} if ps is not None else {})}
        p = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
        if p:
            v["percent"] = _num(p.group(1))
        result = _vocab(f"receptors.{field}.result", q)
        if result:
            v["result"] = result
        return v or None
    return parse


def _her2_ihc(q, ctx):
    m = re.search(r"HER2\s*(?:\([^)]*\))?\s*(?:IHC)?\s*:?\s*([0-3])(\+?)", q)
    if not m:
        return None
    v = {"score": m.group(1) + m.group(2)}
    if v["score"] == "0":
        if re.search(r"희미|faint|ultralow", q, re.I):
            v["faint"] = True
        elif re.search(r"no staining|염색 없음|무염색", q, re.I):
            v["faint"] = False
    return v


def _her2_ish(q, ctx):
    result = _vocab("receptors.her2_ish.result", q)
    method = re.search(r"\b(FISH|SISH|DISH)\b", q)
    return result and {"result": result, "method": method.group(1) if method else "unknown"}


def _pdl1(q, ctx):
    assay = re.search(r"22C3|SP142|SP263", q)
    score = re.search(r"\b(CPS|IC|TPS)\b\s*:?\s*(\d+(?:\.\d+)?)", q)
    return score and {"assay": assay.group(0) if assay else "unknown", "score_type": score.group(1),
                      "score": _num(score.group(2))}


def _percent(q, ctx):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
    return m and {"percent": _num(m.group(1))}


def _age(q, ctx):
    m = re.search(r"(\d+)\s*세", q) or re.search(r"\b[FM]\s*/\s*(\d+)", q)
    return m and int(m.group(1))


def _gender(q, ctx):
    if re.search(r"\bF\s*/|여성|여자|female", q, re.I):
        return "FEMALE"
    if re.search(r"\bM\s*/|남성|남자|\bmale", q, re.I):
        return "MALE"
    return None


def _menopausal_basis(q, ctx):
    """근거 단어가 없으면 None ('폐경 후'만 적힌 구절은 상태이지 근거가 아니다)."""
    for basis, pat in [("fsh", r"FSH"), ("oophorectomy", r"난소\s*절제|oophorectomy|ovariectomy"),
                       ("ovarian_radiation", r"난소\s*방사선"), ("hysterectomy", r"자궁\s*(?:적출|절제)|hysterectomy"),
                       # "58세 폐경 후 여성"의 58세는 나이라 근거가 아니다 (폐경 바로 뒤에 후·전이 붙으면 뺀다)
                       ("age_amenorrhea", r"LMP|\d+\s*세\s*폐경(?!\s*[후전])|폐경\s*\d+\s*세|월경|생리|menses|amenorrhea")]:
        if re.search(pat, q, re.I):
            return basis
    return None


def _number(pattern):
    def parse(q, ctx):
        m = re.search(pattern, q, re.I)
        return m and _num(m.group(1))
    return parse


def _day_field(q, ctx):
    date = parse_date(q)
    if date is None:
        return 0 if re.search(r"de novo", q, re.I) else None
    return _day(date, ctx.dx_date)


def _metastasis_day(q, ctx):
    """국소 재발 구절은 원격 전이일이 아니다."""
    if re.search(r"국소|locoregional|local", q, re.I) and not re.search(r"전이|metasta", q, re.I):
        return None
    return _day_field(q, ctx)


def _need(pattern: str, parse):
    """구절에 그 칸의 단어가 있을 때만 정규화한다. LLM이 '재발·전이 소견 없음' 같은 구절을 여러 칸에 넣는 것을 막는다."""
    def wrapped(q, ctx):
        return parse(q, ctx) if re.search(pattern, q, re.I) else None
    return wrapped


def _recurrence_status(q, ctx):
    if NEGATION.search(q):
        return "none"
    if re.search(r"국소|locoregional|local", q, re.I):
        return "locoregional"
    return "distant" if re.search(r"전이|metasta", q, re.I) else None


def _pcr(q, ctx):
    if re.search(r"없음|no residual|\bpCR\b|ypT0", q, re.I):
        return "yes"
    return "no" if re.search(r"있음|residual", q, re.I) else None


def _rcb(q, ctx):
    m = re.search(r"RCB[\s-]*(?:class\s*)?(III|II|I|[0-3])", q, re.I)
    return m and f"RCB-{ROMAN[m.group(1)]}"


def _intent(q, ctx):
    if re.search(r"완치|curative", q, re.I):
        return "curative"
    return "palliative" if re.search(r"고식|palliative", q, re.I) else None


PARSERS = {
    "diagnosis.diagnosis_date": lambda q, ctx: parse_date(q),
    "diagnosis.histology": lambda q, ctx: _vocab("diagnosis.histology", q),
    "diagnosis.grade": _grade,
    "stage.ctnm": lambda q, ctx: _tnm(q, ctx, prefix="c"),
    "stage.ptnm": lambda q, ctx: _tnm(q, ctx, prefix="p"),
    "stage.yptnm": lambda q, ctx: _tnm(q, ctx, prefix="yp"),
    "stage.group": _group,
    "stage.disease_extent": _extent,
    "stage.metastatic_sites": _metastatic_sites,
    "stage.positive_ln_count": _ln_count,
    "stage.operable": lambda q, ctx: _yes_no(q),
    # 유방 종괴 크기만 (흉부 CT의 폐 결절 크기 등은 받지 않는다)
    "stage.clinical_size_mm": lambda q, ctx: _size_mm(q) if re.search(r"유방|breast|종괴|mass", q, re.I) else None,
    "stage.pathologic_size_mm": lambda q, ctx: _size_mm(q),
    "receptors.er_percent": _receptor("er_percent"),
    "receptors.pr_percent": _receptor("pr_percent"),
    "receptors.her2_ihc": _her2_ihc,
    "receptors.her2_ish": _her2_ish,
    "receptors.pdl1": _pdl1,
    "proliferation.ki67_percent": _percent,
    "patient.gender": _gender,
    "patient.age": _age,
    "patient.menopausal_status": lambda q, ctx: _vocab("patient.menopausal_status", q),
    "patient.menopausal_basis": _menopausal_basis,
    "patient.ecog": _number(r"ECOG\s*(?:PS)?\s*:?\s*([0-4])"),
    "patient.height_cm": _number(r"(\d+(?:\.\d+)?)\s*cm"),
    "patient.weight_kg": _number(r"(\d+(?:\.\d+)?)\s*kg"),
    "patient.lvef_percent": _number(r"(\d+(?:\.\d+)?)\s*%"),
    "patient.cardiac_history": _need(r"심장|심질환|심부전|관상동맥|심근|부정맥|cardiac|heart|CHF|\bMI\b",
                                     lambda q, ctx: _yes_no(q)),
    "patient.mediastinal_radiation": _need(r"종격동|mediastin", lambda q, ctx: _yes_no(q)),
    "patient.comorbidities": lambda q, ctx: None if re.search(r"재발|전이|metasta", q, re.I) else [q],
    "neoadjuvant_response.pcr": _pcr,
    "neoadjuvant_response.rcb": _rcb,
    "recurrence.recurrence_date": lambda q, ctx: parse_date(q),
    "recurrence.adjuvant_endocrine_end_date": _need(r"종료|중단|완료|끝|stop|discontinu|complet",
                                                    lambda q, ctx: parse_date(q)),
    "recurrence.status": _recurrence_status,
    "recurrence.metastatic_sites": _metastatic_sites,
    "recurrence.metastasis_day": _metastasis_day,
    "recurrence.recurrence_day": _day_field,
    "recurrence.surgery": _need(r"수술|절제|surgery|resection|excision|mastectomy", lambda q, ctx: _yes_no(q)),
    "recurrence.surgery_intent": _intent,
    "recurrence.later_distant": _need(r"원격|distant", lambda q, ctx: _yes_no(q)),
}


# ---------- 유전자 ----------
VARIANT = re.compile(r"\b([A-Z][A-Z0-9]+)\s+c\.(\S+)\s*\(p\.([^)]+)\)(?:\s*VAF\s*(\d+(?:\.\d+)?)\s*%)?")


def _gene(gene: str, q: str) -> dict | None:
    """변이 표기(c. / p.)가 있으면 detected, 유전자 이름만 나열돼 있으면 not_detected (검출되지 않음 목록).
    구절에 그 유전자 이름이 없으면 None ('BRCA1/2'는 BRCA1·BRCA2 둘 다). 다른 유전자의 변이 구절을 넣은 경우를 막는다."""
    named = re.search(rf"(?<![A-Z0-9]){gene}(?![0-9])", q) or (
        gene in ("BRCA1", "BRCA2") and re.search(r"BRCA\s*1\s*/\s*2", q))
    if not named:
        return None
    if NOT_DONE.search(q):
        return {"status": "not_done"}
    variants = []
    for m in VARIANT.finditer(q):
        if m.group(1) != gene:
            continue
        p = m.group(3)
        kind = ("Nonsense_Mutation" if re.fullmatch(r"[A-Z]\d+\*", p) else
                "Frame_Shift" if "fs" in p else "Missense_Mutation" if re.fullmatch(r"[A-Z]\d+[A-Z]", p) else None)
        variants.append({"protein_change": p, "variant_type": kind,
                         "vaf": m.group(4) and round(float(m.group(4)) / 100, 6),
                         "raw": re.sub(r"\s+", " ", m.group(0))})
    return {"status": "present", "result": "detected" if variants else "not_detected", "variants": variants}


# ---------- 목록 칸 ----------
def _drug_names(path: Path = DRUG_NAMES_CSV) -> dict[str, list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["raw_name"].strip().casefold(): r["generic_names"].split("+") for r in csv.DictReader(f)}


DRUG_NAMES = _drug_names()
DRUG_TABLE = load_drug_table()


def _drugs(text: str) -> list[tuple[str, list[int]]]:
    """(성분명, 원문에서 그 성분 이름이 끝나는 위치들). 겹치는 이름은 긴 것, 성분 순서는 처음 나온 순서.
    "AC (doxorubicin 60mg/m2 ...)"처럼 약어와 성분명이 함께 있으면 위치가 둘이다 (용량은 성분명 뒤에 있다)."""
    low, hits = text.casefold(), []
    for name, generics in DRUG_NAMES.items():
        pat = re.escape(name)
        if name[0].isascii() and name[0].isalnum():
            pat = r"(?<![a-z0-9])" + pat
        if name[-1].isascii() and name[-1].isalnum():
            pat += r"(?![a-z0-9])"
        hits += [(m.start(), m.end(), generics) for m in re.finditer(pat, low)]
    out: dict[str, list[int]] = {}
    end = -1
    for s, e, generics in sorted(hits, key=lambda h: (h[0], -h[1])):
        if s < end:
            continue
        end = e
        for g in generics:
            out.setdefault(g, []).append(e)
    return list(out.items())


def _cycles(q: str) -> dict | None:
    m = re.search(r"(?:q(\d)w|(weekly)|(\d+)\s*일)?\s*#\s*(\d+)", q)
    if not m:
        return None
    interval = int(m.group(1)) * 7 if m.group(1) else 7 if m.group(2) else int(m.group(3)) if m.group(3) else None
    return {"value": int(m.group(4)), "basis": "recorded", "interval_days": interval,
            "interval_basis": "recorded" if interval else None}


def _regimen(q: str, ctx: Context) -> dict:
    """투약 한 줄의 공통 부분: 약(첫 날짜 앞), 날짜, 주기, 날짜 뒤 글(반응·중단 사유)."""
    dates = list(DATE.finditer(q))
    head = q[:dates[0].start()] if dates else q
    tail = q[dates[-1].end():] if dates else ""
    return {"drugs": _drugs(head), "head": head, "tail": tail,
            "start": parse_date(dates[0].group(0)) if dates else None,
            "end": parse_date(dates[1].group(0)) if len(dates) > 1 else None,
            "ongoing": len(dates) == 1 and bool(re.search(r"현재|복용 중|투여 중|ongoing", q)),
            "cycles": _cycles(q)}


def _treatment(q: str, ctx: Context) -> dict | None:
    r = _regimen(q, ctx)
    if not r["drugs"]:
        return None
    setting = re.search(r"보조|선행|고식", ctx.line)
    s, e = _day(r["start"], ctx.dx_date), _day(r["end"], ctx.dx_date)
    stop = None
    for reason, pat in [("planned_switch", r"계획된 변경|planned"), ("toxicity", r"부작용|독성|toxicity|관절통"),
                        ("completed", r"완료|complete"), ("progression", r"\bPD|진행|progress|전이|재발")]:
        if re.search(pat, r["tail"], re.I):
            stop = reason
            break
    return {"drugs": [g for g, _ in r["drugs"]],
            "setting": setting and {"보조": "adjuvant", "선행": "neoadjuvant", "고식": "metastatic"}[setting.group(0)],
            "start_date": r["start"], "end_date": r["end"], "start_day": s, "end_day": e,
            "duration_days": e - s if s is not None and e is not None else None,
            **({"ongoing": True} if r["ongoing"] else {}),
            "cycles": r["cycles"], "stop_reason": stop,
            "best_response": _vocab("treatment_history.best_response", r["tail"])}


def _anthracycline(q: str, ctx: Context) -> dict | None:
    r = _regimen(q, ctx)
    drugs = [g for g, _ in r["drugs"]]
    for g, ends in r["drugs"]:
        if DRUG_TABLE.get(g, ("", ""))[1] != "anthracycline":
            continue
        dose = next((m for m in (re.match(r"\s*(\d+(?:\.\d+)?)\s*(mg/m2|mg)", r["head"][e:]) for e in ends) if m), None)
        dose = dose and {"value": _num(dose.group(1)), "unit": dose.group(2)}
        cycles = r["cycles"]
        total = dose and cycles and {"value": _num(str(dose["value"] * cycles["value"])), "unit": dose["unit"]}
        return {"drug": g, "timeline_index": None, "combined_with": [x for x in drugs if x != g],
                "dose_per_admin": dose, "cycles": cycles, "total_dose": total}
    return None


def _imaging(q: str, ctx: Context) -> dict | None:
    # 머리글과 "검사:" 줄에서 검사 종류를 찾는다 ([영상의학 판독]은 머리글에 종류가 없다)
    exam = re.search(r"^\s*(?:검사|Exam)\s*:.*$", ctx.doc.text, re.M)
    header = ctx.doc.text.split("\n", 1)[0] + (" " + exam.group(0) if exam else "")
    modality = next((m for m, pat in [("bone_scan", r"bone scan|골\s*스캔|뼈\s*스캔"), ("PET", r"PET"),
                                      ("MRI", r"MRI"), ("CT", r"CT"), ("ultrasound", r"초음파|ultrasound|US\b"),
                                      ("X-ray", r"X-ray|흉부 사진")]
                     if re.search(pat, header, re.I)), "other")
    if "외" in q:          # "골전이 외 원격 전이 없음": '외' 앞만 전이 부위
        sites = _sites(q.split("외", 1)[0])
    else:
        sites = [] if NEGATION.search(q) else _sites(q)
    return {"modality": modality, "day": _day(ctx.doc.doc_date, ctx.dx_date), "date": ctx.doc.doc_date,
            "sites": sites, "certainty": "suspected" if re.search(r"의증|의심|r/o|suspicious|possible", q, re.I)
            else "confirmed"}


ITEMS = {
    "treatment_history": _treatment,
    "anthracycline_drug_dose.drugs": _anthracycline,
    "imaging_findings": _imaging,
}
