"""patient_state <-> 고정 형식 차트 원문 (chart.txt).

render(patient_state)는 환자 한 명을 보고서 4종(병리, 분자병리, 외래 경과기록, 투약 기록)을 이어 붙인 텍스트로 쓰고,
parse(text)는 같은 형식의 텍스트를 다시 patient_state로 읽는다. 형식은 하나로 고정한다 (표현을 바꿔 쓰지 않음).
parse는 칸마다 원문 위치(source: doc_id, quote, char_start, char_end)를 채우고, 차수·간주 규칙·판정 기준일 값은
변환기와 같은 함수(lines.annotate)로 다시 계산한다.

왕복 검사: parse(render(x))는 아래만 빼고 x와 같아야 한다 (same_content).
- raw, source, created_at, documents: 원문에서 새로 만드는 값
- anthracycline_drug_dose.drugs[].timeline_index: TCGA drug_timeline 순번이라 차트에는 없음 (스키마: 차트에서는 null)
- genomic_reports[].doc_id: 차트의 분자병리 보고서 번호를 쓴다

담지 못하는 값(날짜가 있는 투약, observed_date, history, 같은 보고서 안에 검체가 다른 값 등)이 오면 render가 멈춘다.

usage (team_project 폴더에서):
    python -m src.input.script.tcga.fixed_chart                              # TCGA 크롭본 전원 왕복 검사
    python -m src.input.script.tcga.fixed_chart --ids TCGA-A2-A0EW --show    # 한 명의 차트 원문 출력
    python -m src.input.script.tcga.fixed_chart --out <폴더>                 # <폴더>/<환자>/chart.txt, patient_state.json
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

from src.input.script.rules import annotate, load_drug_table
from src.input.script.tcga.tcga_to_patient_state import ANTHRA, CREATED_AT, GENES, ITEM, SCHEMA_VERSION, cycles_of

DRUG_TABLE = load_drug_table()
NOT_DONE, NOT_RECORDED = "미시행", "기록 없음"
NO_VALUE = "-"


class Unsupported(ValueError):
    """고정 형식에 담을 수 없는 값."""


# ---------- 값 <-> 글 ----------
def _num(x) -> str:
    return str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)


def _parse_num(s: str):
    return int(s) if re.fullmatch(r"-?\d+", s) else float(s)


def _day(n) -> str:
    return NO_VALUE if n is None else f"D{'+' if n >= 0 else '-'}{abs(n)}"


def _parse_day(s: str):
    if s == NO_VALUE:
        return None
    m = re.fullmatch(r"D([+-])(\d+)", s)
    if not m:
        raise ValueError(f"일수 형식이 아님: '{s}'")
    return int(m[2]) * (1 if m[1] == "+" else -1)


class Words:
    """표준값 <-> 보고서 낱말."""

    def __init__(self, table: dict):
        self.table, self.back = table, {v: k for k, v in table.items()}

    def enc(self, v) -> str:
        if v not in self.table:
            raise Unsupported(f"고정 형식에 없는 값: {v!r}")
        return self.table[v]

    def dec(self, s: str):
        return self.back[s]


HISTOLOGY = Words({"IDC": "Invasive ductal carcinoma", "ILC": "Invasive lobular carcinoma",
                   "mucinous": "Mucinous carcinoma", "metaplastic": "Metaplastic carcinoma",
                   "invasive_NOS": "Invasive carcinoma, NOS", "other": "Other carcinoma"})
EXTENT = Words({"early": "조기", "locally_advanced": "국소 진행성", "metastatic": "전이성"})
OPERABLE = Words({"yes": "가능", "no": "불가", "unknown": "미상"})
YES_NO = Words({"yes": "예", "no": "아니오", "unknown": "미상"})
HR_RESULT = Words({"positive": "양성", "low_positive": "저발현 양성", "negative": "음성", "indeterminate": "불확정"})
HER2_RESULT = Words({"positive": "양성", "negative": "음성", "equivocal": "경계", "indeterminate": "불확정",
                     "unknown": "미상"})
ISH_RESULT = Words({"amplified": "증폭", "not_amplified": "비증폭", "equivocal": "경계"})
ISH_METHOD = Words({"FISH": "FISH", "SISH": "SISH", "DISH": "DISH", "unknown": "방법미상"})
KI67_RESULT = Words({"low": "낮음", "intermediate": "중간", "high": "높음"})
GENDER = Words({"FEMALE": "여", "MALE": "남"})
MENOPAUSE = Words({"premenopausal": "폐경 전", "perimenopausal": "폐경 주변기", "postmenopausal": "폐경 후",
                   "indeterminate": "판정 불가"})
MENO_BASIS = Words({"age_amenorrhea": "나이와 무월경 기간", "fsh": "혈중 FSH", "oophorectomy": "양측 난소절제",
                    "unknown": "미상"})
PCR = Words({"yes": "pCR", "no": "잔존 침윤암"})
RECURRENCE = Words({"none": "없음", "distant": "원격 전이", "locoregional": "국소 재발",
                    "site_unknown": "재발 부위 미상", "unknown": "미상"})
INTENT = Words({"curative": "완치 목적", "palliative": "고식 목적", "unknown": "미상"})
SPECIMEN = Words({"primary": "원발 종양", "metastasis": "전이 병소", "cfDNA": "혈액 cfDNA", "unknown": "미상"})
SETTING = Words({"neoadjuvant": "선행", "adjuvant": "보조", "metastatic": "고식", "unknown": "미상"})
STOP = Words({"progression": "진행", "toxicity": "독성", "completed": "완료", "planned_switch": "계획된 변경",
              "maintenance": "유지요법 전환", "other": "기타"})
RESPONSE = Words({"CR": "CR", "PR": "PR", "SD": "SD", "PD": "PD", "unknown": NO_VALUE})
SITE_CODES = {"[Not Applicable]": "해당 없음", "[Not Available]": "부위 기록 없음"}
LN_MISSING = "[Not Available]"
TNM_NA = {"t": "TX", "n": "NX", "m": "MX"}


class Codec:
    def __init__(self, enc, dec):
        self.enc, self.dec = enc, dec


def _words(w: Words) -> Codec:
    return Codec(w.enc, w.dec)


INT = Codec(str, int)
TEXT = Codec(str, str)
DAY = Codec(_day, _parse_day)
AGE = Codec(lambda v: f"{v}세", lambda s: int(s.removesuffix("세")))
GROUP = Codec(lambda v: "평가 불가" if v == "not_assessed" else v, lambda s: "not_assessed" if s == "평가 불가" else s)


def _enc_tnm(v: dict) -> str:
    parts = [TNM_NA[k] if v[k] == "not_assessed" else v[k] for k in ("t", "n", "m")]
    ed = v.get("edition")
    return " ".join(parts) + (f" (AJCC {ed})" if ed else " (AJCC 판 기록 없음)")


def _dec_tnm(s: str) -> dict:
    m = re.fullmatch(r"(\S+) (\S+) (\S+) \(AJCC (.+)\)", s)
    t, n, mm = (("not_assessed" if x == TNM_NA[k] else x) for k, x in zip("tnm", m.groups()[:3]))
    return {"t": t, "n": n, "m": mm, "edition": None if m[4] == "판 기록 없음" else m[4]}


def _enc_ln(v: dict) -> str:
    p, e = (NOT_RECORDED if v[k] == LN_MISSING else str(v[k]) for k in ("positive", "examined"))
    return f"전이 {p} / 검사 {e}"


def _dec_ln(s: str) -> dict:
    m = re.fullmatch(r"전이 (.+) / 검사 (.+)", s)
    return {k: LN_MISSING if x == NOT_RECORDED else int(x) for k, x in zip(("positive", "examined"), m.groups())}


def _enc_sites(v) -> str:
    return SITE_CODES[v] if isinstance(v, str) else "; ".join(v)


def _dec_sites(s: str):
    back = {w: c for c, w in SITE_CODES.items()}
    return back[s] if s in back else s.split("; ")


def _percent_parts(v: dict, result: Words) -> list[str]:
    """ER·PR·Ki-67 공통: 판정, 비율, 구간, Allred."""
    parts = []
    if "result" in v:
        parts.append(result.enc(v["result"]))
    if "percent" in v:
        parts.append(f"{_num(v['percent'])}%")
    if "range" in v:
        parts.append(f"구간 {_num(v['range'][0])}-{_num(v['range'][1])}%")
    if "allred" in v:
        a = v["allred"]
        parts.append("Allred " + " ".join(f"{k} {a[k]}" for k in ("total", "ps", "is") if k in a))
    return parts


def _percent_value(s: str, result: Words) -> dict:
    out = {}
    for p in s.split(", "):
        if p.startswith("구간 "):
            lo, hi = p.removeprefix("구간 ").removesuffix("%").split("-")
            out["range"] = [_parse_num(lo), _parse_num(hi)]
        elif p.startswith("Allred "):
            toks = p.removeprefix("Allred ").split()
            out["allred"] = {k: int(x) for k, x in zip(toks[::2], toks[1::2])}
        elif p.endswith("%"):
            out["percent"] = _parse_num(p.removesuffix("%"))
        else:
            out["result"] = result.dec(p)
    return out


def _percent(result: Words) -> Codec:
    return Codec(lambda v: ", ".join(_percent_parts(v, result)), lambda s: _percent_value(s, result))


def _enc_her2_ihc(v: dict) -> str:
    parts = []
    if "score" in v:
        parts.append(f"점수 {v['score']}")
    if "faint" in v:
        parts.append(f"미약한 막 염색 {'있음' if v['faint'] else '없음'}")
    if "result" in v:
        parts.append(f"판정 {HER2_RESULT.enc(v['result'])}")
    return ", ".join(parts)


def _dec_her2_ihc(s: str) -> dict:
    out = {}
    for p in s.split(", "):
        k, x = p.rsplit(" ", 1)
        if k == "점수":
            out["score"] = x
        elif k == "미약한 막 염색":
            out["faint"] = x == "있음"
        else:
            out["result"] = HER2_RESULT.dec(x)
    return out


def _enc_ish(v: dict) -> str:
    return " ".join(([ISH_METHOD.enc(v["method"])] if "method" in v else []) + [ISH_RESULT.enc(v["result"])])


def _dec_ish(s: str) -> dict:
    toks = s.split(" ")
    return {"result": ISH_RESULT.dec(toks[-1]), **({"method": ISH_METHOD.dec(toks[0])} if len(toks) == 2 else {})}


def _enc_pdl1(v: dict) -> str:
    parts = [f"검사법 {v['assay']}"] if "assay" in v else []
    if "score_type" in v:
        parts.append(f"점수 종류 {v['score_type']}")
    if "score" in v:
        parts.append(f"점수 {_num(v['score'])}")
    return ", ".join(parts)


def _dec_pdl1(s: str) -> dict:
    keys = {"검사법": "assay", "점수 종류": "score_type", "점수": "score"}
    out = {}
    for p in s.split(", "):
        k, x = p.rsplit(" ", 1)
        out[keys[k]] = _parse_num(x) if k == "점수" else x
    return out


TNM = Codec(_enc_tnm, _dec_tnm)
LN = Codec(_enc_ln, _dec_ln)
SITES = Codec(_enc_sites, _dec_sites)
HER2_IHC = Codec(_enc_her2_ihc, _dec_her2_ihc)
HER2_ISH = Codec(_enc_ish, _dec_ish)
PDL1 = Codec(_enc_pdl1, _dec_pdl1)

# (보고서, 그룹, 칸, 이름, 값 형식, present일 때 함께 두는 키). 칸이 JSON에 없으면 줄을 쓰지 않는다.
# 함께 두는 키: specimen = 그 보고서의 검체, observed_date = null (날짜가 있는 값은 담지 않음)
FIELDS = [
    ("pathology", "diagnosis", "histology", "조직형", _words(HISTOLOGY), ()),
    ("pathology", "diagnosis", "grade", "조직학적 등급", INT, ()),
    ("pathology", "stage", "ptnm", "pTNM", TNM, ()),
    ("pathology", "stage", "ctnm", "cTNM", TNM, ()),
    ("pathology", "stage", "group", "병기", GROUP, ()),
    ("pathology", "stage", "positive_ln_count", "림프절", LN, ()),
    ("pathology", "receptors", "er_percent", "ER", _percent(HR_RESULT), ("specimen", "observed_date")),
    ("pathology", "receptors", "pr_percent", "PR", _percent(HR_RESULT), ("specimen", "observed_date")),
    ("pathology", "receptors", "her2_ihc", "HER2 IHC", HER2_IHC, ("specimen",)),
    ("pathology", "receptors", "her2_ish", "HER2 ISH", HER2_ISH, ("specimen",)),
    ("pathology", "proliferation", "ki67_percent", "Ki-67", _percent(KI67_RESULT), ("specimen", "observed_date")),
    ("pathology", "receptors", "pdl1", "PD-L1", PDL1, ()),
    ("progress_note", "diagnosis", "diagnosis_date", "진단일", TEXT, ()),
    ("progress_note", "patient", "gender", "성별", _words(GENDER), ()),
    ("progress_note", "patient", "age", "진단 시 나이", AGE, ("observed_date",)),
    ("progress_note", "patient", "menopausal_status", "폐경 상태", _words(MENOPAUSE), ()),
    ("progress_note", "patient", "menopausal_basis", "폐경 판정 근거", _words(MENO_BASIS), ()),
    ("progress_note", "patient", "ecog", "ECOG", INT, ()),
    ("progress_note", "stage", "disease_extent", "병기 범주", _words(EXTENT), ()),
    ("progress_note", "stage", "operable", "수술 가능 여부", _words(OPERABLE), ()),
    ("progress_note", "stage", "metastatic_sites", "진단 시 원격 전이 부위", SITES, ()),
    ("progress_note", "neoadjuvant_response", "pcr", "선행요법 반응", _words(PCR), ()),
    ("progress_note", "neoadjuvant_response", "rcb", "RCB", TEXT, ()),
    ("progress_note", "recurrence", "status", "재발", _words(RECURRENCE), ()),
    ("progress_note", "recurrence", "metastatic_sites", "재발 전이 부위", SITES, ()),
    ("progress_note", "recurrence", "metastasis_day", "전이 진단", DAY, ()),
    ("progress_note", "recurrence", "recurrence_day", "첫 재발", DAY, ()),
    ("progress_note", "recurrence", "surgery", "재발 후 수술", _words(YES_NO), ()),
    ("progress_note", "recurrence", "surgery_intent", "재발 후 수술 의도", _words(INTENT), ()),
    ("progress_note", "recurrence", "later_distant", "이후 원격 전이", _words(YES_NO), ()),
    ("progress_note", "recurrence", "recurrence_date", "재발 날짜", TEXT, ()),
    ("progress_note", "recurrence", "adjuvant_endocrine_end_date", "보조 내분비요법 종료 날짜", TEXT, ()),
]
GROUPS = ["diagnosis", "stage", "receptors", "proliferation", "patient", "neoadjuvant_response", "recurrence"]

# 보고서: doc_type -> (doc_id, 머리글). 문서 번호는 보고서 종류마다 고정한다
DOCS = {"pathology": ("D1", "[병리결과보고서]"), "molecular": ("D2", "[분자병리 보고서]"),
        "progress_note": ("D3", "<외래 경과기록>"), "medication": ("D4", "[투약 기록]")}
HEADER_TO_TYPE = {h: t for t, (_, h) in DOCS.items()}
TABLE_HEADER = "구분 | 약제 | 시작 | 종료 | 주기 | 반응 | 진행일 | 중단 사유 | anthracycline 용량"
NO_DRUGS = "투약 기록 없음"
UNKNOWN_DRUGS_ONLY = "약제명을 알 수 없는 투약만 있음"  # TCGA 'unknown' 약제: 행은 없지만 anthracycline 투약은 negative


# ---------- render ----------
class _Writer:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, line: str = "") -> None:
        self.lines.append(line)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _field_text(f: dict, codec: Codec, extras: tuple, specimen: str | None) -> str:
    st = f["status"]
    if st == "not_done":
        if f.get("raw"):
            raise Unsupported(f"미시행 상태 표기 '{f['raw']}'")
        return NOT_DONE
    if st == "not_recorded":
        return NOT_RECORDED
    if f.get("history") or f.get("confidence") is not None:
        raise Unsupported("history·confidence")
    for k in extras:
        if k == "observed_date" and f.get("observed_date") is not None:
            raise Unsupported("observed_date")
        if k == "specimen" and f.get("specimen") != specimen:
            raise Unsupported(f"보고서 검체({specimen})와 다른 검체({f.get('specimen')})")
    if set(f) - {"status", "value", "raw", "source", *extras}:
        raise Unsupported(f"담지 못하는 키 {sorted(set(f) - {'status', 'value', 'raw', 'source', *extras})}")
    return codec.enc(f["value"])


def _doc_specimen(fields_: list[dict]) -> str:
    specs = {f.get("specimen") for f in fields_ if f.get("status") == "present"}
    if len(specs) > 1:
        raise Unsupported(f"한 보고서에 검체가 여러 개: {specs}")
    return next(iter(specs), None) or "primary"


def _variant_text(v: dict) -> str:
    if set(v) == {"protein_change", "variant_type", "vaf", "raw"}:
        return f"p.{v['protein_change']} ({v['variant_type']}), VAF {_num(v['vaf'])}"
    if set(v) == {"raw"}:
        return f"원문 {v['raw']}"
    raise Unsupported(f"변이 형식 {sorted(v)}")


def _gene_text(g: dict) -> str:
    if g["status"] == "not_done":
        if g.get("raw"):
            raise Unsupported(f"미시행 상태 표기 '{g['raw']}'")
        return NOT_DONE
    if g["status"] == "not_recorded":
        return NOT_RECORDED
    if g["result"] == "not_detected":
        return "검출되지 않음"
    return "검출: " + "; ".join(_variant_text(v) for v in g["variants"])


def _dose_text(d) -> str:
    return NOT_RECORDED if d == "No value" else f"{_num(d['value'])} {d['unit']}"


def _anthra_by_row(fields: dict) -> dict[int, list[dict]]:
    """anthracycline 용량 기록을 투약 행에 붙인다. 같은 약 조합인 행 중 원문(raw)의 시작·종료일이 같은 행을 먼저,
    없으면 첫 행을 고른다 (TCGA는 원문이 '날짜 없음'이어도 행에는 다른 열의 날짜가 들어갈 수 있다)."""
    rows = fields["treatment_history"]
    used: dict[int, list[dict]] = {}
    for a in fields["anthracycline_drug_dose"]["drugs"]:
        m = ITEM.match(a["raw"].strip()) if a.get("raw") else None
        combo = sorted([a["drug"]] + a["combined_with"])
        cands = [i for i, t in enumerate(rows)
                 if sorted(t["drugs"]) == combo and a["drug"] not in {x["drug"] for x in used.get(i, [])}]
        dated = [i for i in cands if m is not None and rows[i]["start_day"] == (int(m["s"]) if m["s"] else None)
                 and rows[i]["end_day"] == (int(m["e"]) if m["e"] else None)]
        if not cands:
            raise Unsupported(f"anthracycline 용량 기록을 붙일 투약 행이 없음: {a.get('raw')}")
        used.setdefault((dated or cands)[0], []).append(a)
    for i, t in enumerate(rows):
        if {d for d in t["drugs"] if d in ANTHRA} != {a["drug"] for a in used.get(i, [])}:
            raise Unsupported(f"투약 행의 anthracycline과 용량 기록이 맞지 않음: {t['drugs']}")
    return used


def render(patient_state: dict) -> str:
    """patient_state -> 고정 형식 차트 원문."""
    fields = patient_state["fields"]
    ref = patient_state["patient_ref"]
    w = _Writer()

    def head(doc_type: str, *extra: str) -> None:
        if w.lines:
            w.add()
            w.add()
        w.add(DOCS[doc_type][1])
        w.add(f"등록번호: {ref}")
        for x in extra:
            w.add(x)

    def write_fields(doc_type: str, specimen: str | None) -> None:
        for doc, grp, key, label, codec, extras in FIELDS:
            if doc == doc_type and key in fields.get(grp, {}):
                w.add(f"{label}: {_field_text(fields[grp][key], codec, extras, specimen)}")

    # 병리
    path_fields = [fields[g][k] for d, g, k, *_ in FIELDS if d == "pathology" and k in fields.get(g, {})]
    spec = _doc_specimen([f for f in path_fields if "specimen" in f])
    head("pathology", f"검체: {SPECIMEN.enc(spec)}")
    write_fields("pathology", spec)

    # 분자병리 (검사를 하나도 안 했고 보고서도 없으면 쓰지 않는다)
    genes, reports = fields["molecular"]["mutations"], fields["genomic_reports"]
    if any(genes[g]["status"] != "not_done" for g in GENES) or reports:
        if set(genes) != set(GENES):
            raise Unsupported(f"유전자 목록이 다름: {sorted(genes)}")
        spec = _doc_specimen([genes[g] for g in GENES] + [{"status": "present", **r} for r in reports])
        head("molecular", f"검체: {SPECIMEN.enc(spec)}")
        for g in GENES:
            w.add(f"{g}: {_gene_text(genes[g])}")
        for r in reports:
            if r.get("report_date") is not None:
                raise Unsupported("report_date")
            w.add(f"결과 요약: {r['raw_text']}")

    # 외래 경과기록 (작성일 = 판정 기준일)
    idx = patient_state.get("index_day")
    head("progress_note", f"작성일: {NOT_RECORDED if idx is None else _day(idx)}")
    write_fields("progress_note", None)

    # 투약 기록
    head("medication")
    rows = fields["treatment_history"]
    anthra = _anthra_by_row(fields)
    if not rows:
        w.add(UNKNOWN_DRUGS_ONLY if fields["anthracycline_drug_dose"]["administered"] == "negative" else NO_DRUGS)
    else:
        w.add(TABLE_HEADER)
    for i, t in enumerate(rows):
        if t.get("start_date") or t.get("end_date"):
            raise Unsupported("투약 날짜")
        c = t.get("cycles")
        dose = "; ".join(f"{a['drug']} 1회 {_dose_text(a['dose_per_admin'])}, 총 {_dose_text(a['total_dose'])}"
                         for a in anthra.get(i, [])) or NO_VALUE
        cells = [SETTING.enc(t["setting"]), " + ".join(t["drugs"]), _day(t["start_day"]), _day(t["end_day"]),
                 str(c["value"]) if c and c["basis"] == "recorded" else NO_VALUE,
                 RESPONSE.enc(t["best_response"]), _day(t.get("progression_day")),
                 STOP.enc(t["stop_reason"]) if t.get("stop_reason") else NO_VALUE, dose]
        w.add(" | ".join(cells))
    return w.text()


# ---------- parse ----------
def _lines(text: str):
    """(줄, 시작 위치) 목록."""
    pos = 0
    for line in text.split("\n"):
        yield line, pos
        pos += len(line) + 1


def _split_docs(text: str) -> dict[str, list[tuple[str, int]]]:
    docs: dict[str, list[tuple[str, int]]] = {}
    cur = None
    for line, pos in _lines(text):
        if line in HEADER_TO_TYPE:
            cur = HEADER_TO_TYPE[line]
            docs[cur] = []
        elif cur and line.strip():
            docs[cur].append((line, pos))
    return docs


def _labels(lines: list[tuple[str, int]]) -> dict[str, list[tuple[str, int, int]]]:
    """'이름: 값' 줄 -> {이름: [(값, 시작, 끝)]}. 위치는 값 부분만."""
    out: dict[str, list[tuple[str, int, int]]] = {}
    for line, pos in lines:
        if ": " in line and " | " not in line:
            label, value = line.split(": ", 1)
            start = pos + len(label) + 2
            out.setdefault(label, []).append((value, start, start + len(value)))
    return out


def _src(doc_id: str, value: str, start: int, end: int) -> dict:
    return {"doc_id": doc_id, "quote": value, "char_start": start, "char_end": end}


def _extracted(value: str, start: int, end: int, doc_id: str, codec: Codec, extras: tuple, specimen) -> dict:
    src = _src(doc_id, value, start, end)
    if value == NOT_DONE:
        return {"status": "not_done", "source": src}
    if value == NOT_RECORDED:
        return {"status": "not_recorded", "source": src}
    out = {"status": "present", "value": codec.dec(value), "raw": value}
    for k in extras:
        out[k] = specimen if k == "specimen" else None
    out["source"] = src
    return out


def _variant(s: str) -> dict:
    if s.startswith("원문 "):
        return {"raw": s.removeprefix("원문 ")}
    m = re.fullmatch(r"p\.(\S+) \((\S+)\), VAF (\S+)", s)
    vaf = _parse_num(m[3])
    return {"protein_change": m[1], "variant_type": m[2], "vaf": vaf, "raw": f"{m[1]} ({m[2]}, VAF {m[3]})"}


def _dose(s: str):
    if s == NOT_RECORDED:
        return "No value"
    v, unit = s.split(" ", 1)
    return {"value": _parse_num(v), "unit": unit}


def parse(text: str) -> dict:
    """고정 형식 차트 원문 -> patient_state (원문 위치 포함, 차수·간주 규칙 다시 계산)."""
    docs = _split_docs(text)
    fields: dict = {g: {} for g in GROUPS}
    labels = {t: _labels(lines) for t, lines in docs.items()}
    ref = next(v[0][0] for lab in labels.values() for k, v in lab.items() if k == "등록번호")

    def spec_of(doc_type: str):
        v = labels.get(doc_type, {}).get("검체")
        return SPECIMEN.dec(v[0][0]) if v else None

    for doc, grp, key, label, codec, extras in FIELDS:
        found = labels.get(doc, {}).get(label)
        if found:
            fields[grp][key] = _extracted(*found[0], DOCS[doc][0], codec, extras, spec_of(doc))

    # 분자병리
    mol = labels.get("molecular")
    genes, reports = {}, []
    for g in GENES:
        if not mol:
            genes[g] = {"status": "not_done"}
            continue
        value, s, e = mol[g][0]
        src = _src(DOCS["molecular"][0], value, s, e)
        if value in (NOT_DONE, NOT_RECORDED):
            genes[g] = {"status": "not_done" if value == NOT_DONE else "not_recorded", "source": src}
            continue
        variants = [] if value == "검출되지 않음" else [_variant(x) for x in value.removeprefix("검출: ").split("; ")]
        genes[g] = {"status": "present", "result": "detected" if variants else "not_detected",
                    "variants": variants, "specimen": spec_of("molecular"), "source": src}
    for value, _, _ in (mol or {}).get("결과 요약", []):
        reports.append({"doc_id": DOCS["molecular"][0], "report_date": None, "specimen": spec_of("molecular"),
                        "raw_text": value})
    fields["molecular"] = {"mutations": genes}
    fields["genomic_reports"] = reports

    # 투약 기록
    rows, anthra = [], []
    for line, pos in docs.get("medication", []):
        if " | " not in line or line == TABLE_HEADER:
            continue
        cells = line.split(" | ")
        drugs = cells[1].split(" + ")
        s, e = _parse_day(cells[2]), _parse_day(cells[3])
        dur = e - s if s is not None and e is not None else None
        recorded = None if cells[4] == NO_VALUE else cells[4]
        src = _src(DOCS["medication"][0], line, pos, pos + len(line))
        rows.append({"drugs": drugs, "setting": SETTING.dec(cells[0]), "start_date": None, "end_date": None,
                     "start_day": s, "end_day": e, "duration_days": dur, "cycles": cycles_of(drugs, recorded, dur),
                     "progression_day": _parse_day(cells[6]),
                     "stop_reason": None if cells[7] == NO_VALUE else STOP.dec(cells[7]),
                     "best_response": RESPONSE.dec(cells[5]), "source": src})
        for part in ([] if cells[8] == NO_VALUE else cells[8].split("; ")):
            m = re.fullmatch(r"(.+?) 1회 (.+), 총 (.+)", part)
            c = cycles_of([m[1]], recorded, dur)
            anthra.append({"drug": m[1], "timeline_index": None, "combined_with": [x for x in drugs if x != m[1]],
                           "dose_per_admin": _dose(m[2]), "cycles": c if c and c["basis"] == "recorded" else "No value",
                           "total_dose": _dose(m[3]), "raw": line, "source": src})
    fields["treatment_history"] = rows
    unknown_only = any(line == UNKNOWN_DRUGS_ONLY for line, _ in docs.get("medication", []))
    fields["anthracycline_drug_dose"] = {
        "administered": "positive" if anthra else "negative" if rows or unknown_only else "No value", "drugs": anthra}

    note = labels.get("progress_note", {}).get("작성일")
    doc = {"schema_version": SCHEMA_VERSION, "patient_ref": ref, "created_at": CREATED_AT,
           "index_day": None if not note or note[0][0] == NOT_RECORDED else _parse_day(note[0][0]),
           "documents": [{"doc_id": DOCS[t][0], "doc_type": t, "doc_date": None} for t in DOCS if t in docs],
           "fields": fields, "conflicts": []}
    return annotate(doc, DRUG_TABLE)


# ---------- 왕복 검사 ----------
DROP_KEYS = {"raw", "source", "created_at", "documents", "timeline_index"}


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in DROP_KEYS}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def comparable(patient_state: dict) -> dict:
    """왕복 비교용: 원문에서 새로 만드는 값을 빼고, 순서가 차트 순서로 바뀌는 목록을 정렬한다."""
    d = _strip(copy.deepcopy(patient_state))
    f = d["fields"]
    for r in f["genomic_reports"]:
        r.pop("doc_id", None)
    f["anthracycline_drug_dose"]["drugs"].sort(key=lambda a: json.dumps(a, sort_keys=True))
    return d


def differences(a, b, path: str = "") -> list[str]:
    """두 값이 다른 곳의 경로 목록."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [x for k in sorted(set(a) | set(b)) for x in
                ([f"{path}.{k}: 한쪽에만 있음"] if (k in a) != (k in b) else differences(a[k], b[k], f"{path}.{k}"))]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: 길이 {len(a)} != {len(b)}"]
        return [x for i, (p, q) in enumerate(zip(a, b)) for x in differences(p, q, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def round_trip(patient_state: dict) -> tuple[str, dict, list[str]]:
    """(차트 원문, 다시 읽은 patient_state, 다른 곳 목록)."""
    text = render(patient_state)
    back = parse(text)
    return text, back, differences(comparable(patient_state), comparable(back))


def quote_errors(text: str, patient_state: dict) -> list[str]:
    """source.quote가 원문 char_start~char_end와 같은지."""
    bad = []

    def walk(x, path):
        if isinstance(x, dict):
            s = x.get("source")
            if isinstance(s, dict) and text[s["char_start"]:s["char_end"]] != s["quote"]:
                bad.append(path)
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(patient_state, "")
    return bad


def main(argv=None) -> int:
    from src.input.script.tcga.tcga_to_patient_state import convert, load_rows

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", help="환자 ID (없으면 전체)")
    ap.add_argument("--out", type=Path, help="저장할 폴더. <폴더>/<환자>/chart.txt, patient_state.json")
    ap.add_argument("--show", action="store_true", help="차트 원문을 화면에 출력")
    args = ap.parse_args(argv)

    df = load_rows()
    if args.ids:
        df = df[df.patient_id.isin(args.ids)]
    failed = 0
    for pid, ps in convert(df).items():
        text, back, diffs = round_trip(ps)
        diffs += [f"인용 위치 불일치 {p}" for p in quote_errors(text, back)]
        if diffs:
            failed += 1
            print(f"{pid}: 왕복 불일치 {len(diffs)}곳 {diffs[:5]}")
        if args.show:
            print(text)
        if args.out:
            (args.out / pid).mkdir(parents=True, exist_ok=True)
            (args.out / pid / "chart.txt").write_text(text, encoding="utf-8")
            (args.out / pid / "patient_state.json").write_text(
                json.dumps(back, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(df):,}명 중 왕복 불일치 {failed}명")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
