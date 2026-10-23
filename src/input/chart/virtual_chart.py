"""가상 차트 작성 도구: 차트 글과 정답 patient_state를 한곳에서 함께 쓴다 (notes/report_templates.md).

사례마다 글을 앞에서부터 이어 쓰고, 값이 들어가는 구절을 쓰는 순간 그 칸의 값과 원문 위치(source)를 함께 기록한다.
그래서 chart.txt와 expected/patient_state.json의 위치가 어긋날 수 없다. 사례는 src/input/chart/cases/에 있다.
차수·간주 규칙·판정 기준일 값은 변환기와 같은 lines.annotate로 계산하고, 결과는 schemas/patient_state.json으로 검증한다.

usage (team_project 폴더에서):
    python -m src.input.chart.virtual_chart                 # 10건 + 짝 사례(pairs/) 모두 만들어 tests/fixtures/virtual_charts/에 쓴다
    python -m src.input.chart.virtual_chart --ids VC-0103   # 한 건만
    python -m src.input.chart.virtual_chart --check         # 쓰지 않고, 저장된 파일과 같은지만 본다
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

from src.input.common.lines import annotate, load_drug_table

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "virtual_charts"
SCHEMA = ROOT / "schemas" / "patient_state.json"
SCHEMA_VERSION = "0.1-draft6"
CASES = ["VC-0101", "VC-0102", "VC-0103", "VC-0104", "VC-0105", "VC-0106", "VC-0106b", "VC-0107", "VC-0108",
         "VC-0109"]
DOC_GAP = "\n\n\n"
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]

# 차트에 없으면 not_recorded로 두는 칸 (draft6 기본 칸). 2026-10-22 선택 칸은 차트에 있을 때만 둔다
DEFAULT_FIELDS = {
    "diagnosis": ["diagnosis_date", "histology", "grade"],
    "stage": ["ctnm", "ptnm", "group", "positive_ln_count", "disease_extent", "metastatic_sites", "operable"],
    "receptors": ["er_percent", "pr_percent", "her2_ihc", "her2_ish", "pdl1"],
    "proliferation": ["ki67_percent"],
    "patient": ["gender", "age", "menopausal_status", "menopausal_basis", "ecog"],
    "neoadjuvant_response": ["pcr", "rcb"],
    "recurrence": ["recurrence_date", "adjuvant_endocrine_end_date", "status", "metastatic_sites", "metastasis_day",
                   "recurrence_day", "surgery", "surgery_intent"],
}
GROUP_ORDER = ["diagnosis", "stage", "receptors", "proliferation", "patient", "imaging_findings", "treatment_history",
               "anthracycline_drug_dose", "neoadjuvant_response", "recurrence", "molecular", "genomic_reports"]
NOTHING = object()


@dataclass
class F:
    """구절 하나에 들어가는 칸 하나.

    path: 'receptors.er_percent' 같은 칸 경로. 'molecular.mutations.ESR1'·'molecular.germline.BRCA1'은 유전자 칸.
    role: current (지금 값) / history:recurrence / history:newer_result (이전 값) / conflict (같은 시점의 다른 값)
    raw: 정규화 전 표기. 없으면 구절 전체.
    """
    path: str
    value: object = NOTHING
    raw: str | None = None
    status: str = "present"
    role: str = "current"
    specimen: str | None = NOTHING
    observed_date: str | None = NOTHING
    result: str | None = None          # 유전자 칸: detected / not_detected
    variants: list = field(default_factory=list)
    note: str | None = None            # conflict 설명
    within: str | None = None          # 구절 안의 더 짧은 부분만 quote로 쓸 때 (처음 나오는 곳)


@dataclass
class _Span:
    start: int
    end: int
    text: str


class Doc:
    def __init__(self, chart: "Chart", doc_id: str, doc_type: str, date: str | None):
        self.chart, self.doc_id, self.doc_type, self.date = chart, doc_id, doc_type, date
        self.buf = ""
        self.puts: list[tuple[_Span, F]] = []
        self.rows: list[tuple[_Span, dict]] = []
        self.images: list[tuple[_Span, dict]] = []
        self.report: dict | None = None

    def t(self, s: str) -> "Doc":
        """값이 없는 글."""
        self.buf += s
        return self

    def put(self, text: str, *fs: F) -> "Doc":
        """값이 든 구절. 구절 전체가 각 칸의 quote가 된다."""
        sp = _Span(len(self.buf), len(self.buf) + len(text), text)
        self.buf += text
        for f in fs:
            if f.within is None:
                self.puts.append((sp, f))
                continue
            i = text.find(f.within)
            if i < 0:
                raise ValueError(f"'{f.within}'가 구절 '{text}'에 없음")
            self.puts.append((_Span(sp.start + i, sp.start + i + len(f.within), f.within), f))
        return self

    def ident(self, age: int, *fs: F, full: bool = True) -> "Doc":
        """환자 식별줄 (IN-0 시험용 가짜 값). 사례 번호를 등록번호·연락처 끝자리로 쓴다. fs는 'F/나이' 구절의 칸."""
        digits, sex = self.chart.ident_no, self.chart.sex
        self.t(f"환자명: 김가상   등록번호: 0000{digits}   ").put(f"{sex}/{age}", *fs)
        if full:
            code = 1 if sex == "M" else 2
            self.t(f"   주민번호: {(self.chart.dx.year - age) % 100:02d}0101-{code}******   연락처: 010-0000-{digits}")
        return self.t("\n")

    def row(self, text: str, *, drugs: list[str], setting: str, start: str | None, end: str | None = None,
            cycles: dict | None = None, stop_reason: str | None = None, best_response: str | None = None,
            progression: str | None = None, ongoing: bool | None = NOTHING, anthra: list[dict] = ()) -> "Doc":
        """투약 기록 한 줄 = treatment_history 항목 하나. 줄 전체가 source."""
        sp = _Span(len(self.buf), len(self.buf) + len(text), text)
        self.buf += text
        item = {"drugs": drugs, "setting": setting, "start_date": start, "end_date": end,
                "cycles": cycles, "stop_reason": stop_reason, "best_response": best_response,
                "_progression": progression, "_anthra": list(anthra)}
        if ongoing is not NOTHING:
            item["ongoing"] = ongoing
        self.rows.append((sp, item))
        return self

    def image(self, text: str, *, modality: str, date: str, sites: list[str], certainty: str) -> "Doc":
        """영상 판독 결론 구절 = imaging_findings 항목 하나."""
        sp = _Span(len(self.buf), len(self.buf) + len(text), text)
        self.buf += text
        self.images.append((sp, {"modality": modality, "date": date, "sites": sites, "certainty": certainty}))
        return self

    def genomic_report(self, specimen: str, report_date: str) -> "Doc":
        """이 문서 전체를 genomic_reports[] 원문으로 넘긴다 (IN-7)."""
        self.report = {"specimen": specimen, "report_date": report_date}
        return self


class Chart:
    def __init__(self, ref: str, dx_date: str, index_date: str | int, created_at: str = "2026-10-23T00:00:00+09:00",
                 ident_no: str | None = None):
        self.ref, self.dx = ref, dt.date.fromisoformat(dx_date)
        self.index_date, self.created_at = index_date, created_at
        self.ident_no = ident_no or "".join(ch for ch in ref if ch.isdigit())
        self.sex = "F"                          # 식별줄 성별 표기 (남성 사례는 "M")
        if isinstance(index_date, int):          # 진단일 기준 일수로 줘도 된다
            self.index_date = self.on(index_date)
        self.docs: list[Doc] = []
        self.omit: set[str] = set()

    def day(self, date: str | None) -> int | None:
        return None if date is None else (dt.date.fromisoformat(date) - self.dx).days

    def on(self, day: int) -> str:
        """진단일 기준 일수 -> 날짜 (YYYY-MM-DD)."""
        return (self.dx + dt.timedelta(days=day)).isoformat()

    def doc(self, doc_type: str, date: str | None) -> Doc:
        d = Doc(self, f"D{len(self.docs) + 1}", doc_type, date)
        self.docs.append(d)
        return d

    # ---------- 만들기 ----------
    def build(self) -> tuple[str, dict]:
        texts, offsets, pos = [], {}, 0
        for d in self.docs:
            text = d.buf.rstrip("\n")
            offsets[d.doc_id] = pos
            texts.append(text)
            pos += len(text) + len(DOC_GAP)
        chart = DOC_GAP.join(texts) + "\n"

        def src(d: Doc, sp: _Span) -> dict:
            s = offsets[d.doc_id] + sp.start
            return {"doc_id": d.doc_id, "quote": sp.text, "char_start": s, "char_end": s + len(sp.text)}

        fields: dict = {g: {k: {"status": "not_recorded"} for k in ks} for g, ks in DEFAULT_FIELDS.items()}
        fields["molecular"] = {"mutations": {g: {"status": "not_recorded"} for g in GENES}}
        entries: dict[str, list[tuple[F, dict]]] = {}
        for d in self.docs:
            for sp, f in d.puts:
                entries.setdefault(f.path, []).append((f, self._entry(f, src(d, sp))))

        conflicts = []
        for path, es in entries.items():
            cur = [e for f, e in es if f.role == "current"]
            hist = [(f, e) for f, e in es if f.role.startswith("history:")]
            conf = [(f, e) for f, e in es if f.role == "conflict"]
            if conf:
                conflicts.append({"field": path, "candidates": [e for _, e in conf],
                                  "note": next(f.note for f, _ in conf if f.note)})
                continue
            if len(cur) != 1:
                raise ValueError(f"{self.ref} {path}: 지금 값이 {len(cur)}개")
            entry = cur[0]
            if hist:
                entry["history"] = [{**{k: v for k, v in e.items() if k != "history"},
                                     "superseded_reason": f.role.split(":", 1)[1]} for f, e in hist]
            _set(fields, path, entry)
        for path in self.omit:
            _delete(fields, path)

        rows = [(d, sp, r) for d in self.docs for sp, r in d.rows]
        rows.sort(key=lambda x: (self.day(x[2]["start_date"]) is None, self.day(x[2]["start_date"]) or 0))
        history, anthra = [], []
        for d, sp, r in rows:
            item = {k: v for k, v in r.items() if not k.startswith("_")}
            s, e = self.day(r["start_date"]), self.day(r["end_date"])
            item = {"drugs": item["drugs"], "setting": item["setting"], "start_date": item["start_date"],
                    "end_date": item["end_date"], "start_day": s, "end_day": e,
                    "duration_days": e - s if s is not None and e is not None else None,
                    **({"ongoing": item["ongoing"]} if "ongoing" in item else {}),
                    "cycles": item["cycles"], "progression_day": self.day(r["_progression"]),
                    "stop_reason": item["stop_reason"], "best_response": item["best_response"], "source": src(d, sp)}
            history.append(item)
            for a in r["_anthra"]:
                anthra.append({"drug": a["drug"], "timeline_index": None,
                               "combined_with": [x for x in r["drugs"] if x != a["drug"]],
                               "dose_per_admin": a["dose_per_admin"], "cycles": a["cycles"],
                               "total_dose": a["total_dose"], "raw": sp.text, "source": src(d, sp)})
        fields["treatment_history"] = history
        fields["anthracycline_drug_dose"] = {
            "administered": "positive" if anthra else "negative" if history else "No value", "drugs": anthra}

        images = [{**i, "day": self.day(i["date"]), "source": src(d, sp)} for d in self.docs for sp, i in d.images]
        if images:
            fields["imaging_findings"] = [{k: i[k] for k in ("modality", "day", "date", "sites", "certainty", "source")}
                                          for i in images]
        fields["genomic_reports"] = [{"doc_id": d.doc_id, "report_date": d.report["report_date"],
                                      "specimen": d.report["specimen"], "raw_text": d.buf.rstrip("\n")}
                                     for d in self.docs if d.report]
        fields = {g: fields[g] for g in GROUP_ORDER if g in fields}

        ps = {"schema_version": SCHEMA_VERSION, "patient_ref": self.ref, "created_at": self.created_at,
              "index_day": self.day(self.index_date),
              "documents": [{"doc_id": d.doc_id, "doc_type": d.doc_type, "doc_date": d.date} for d in self.docs],
              "fields": fields, "conflicts": conflicts}
        annotate(ps, load_drug_table())
        return chart, ps

    def _entry(self, f: F, source: dict) -> dict:
        if f.path.startswith("molecular."):
            e = {"status": f.status}
            if f.status == "present":
                e.update({"result": f.result, "variants": f.variants})
                if f.specimen is not NOTHING:
                    e["specimen"] = f.specimen
            elif f.raw is not None:
                e["raw"] = f.raw
            e["source"] = source
            return e
        e = {"status": f.status}
        if f.value is not NOTHING:
            e["value"] = f.value
        e["raw"] = f.raw if f.raw is not None else source["quote"]
        if f.specimen is not NOTHING:
            e["specimen"] = f.specimen
        if f.observed_date is not NOTHING:
            e["observed_date"] = f.observed_date
        e["source"] = source
        return e


def _set(fields: dict, path: str, entry: dict) -> None:
    *groups, key = path.split(".")
    cur = fields
    for g in groups:
        cur = cur.setdefault(g, {})
    cur[key] = entry


def _delete(fields: dict, path: str) -> None:
    *groups, key = path.split(".")
    cur = fields
    for g in groups:
        cur = cur[g]
    cur.pop(key, None)


# ---------- 공통 글 ----------
def allred(ps: int, is_: int, result: str | None = None) -> dict:
    """ER·PR 값 (Allred 점수). 국내 IHC 결과지는 보통 Allred 총점(PS + IS, 8점 만점)으로 적는다 (2026-10-23 사용자).
    B는 Allred 총점을 먼저 본다 (PROJECT.md §5 ER·PR 세부 판정 규칙)."""
    v = {"allred": {"total": ps + is_, "ps": ps, "is": is_}}
    return {**v, "result": result} if result else v


def allred_text(ps: int, is_: int) -> str:
    return f"Allred score {ps + is_} (PS {ps} + IS {is_})"


def kdate(date: str) -> str:
    """2021-03-05 -> 2021.3.5"""
    y, m, d = date.split("-")
    return f"{y}.{int(m)}.{int(d)}"


# ---------- 검사 ----------
def check(chart: str, ps: dict) -> list[str]:
    """스키마, 인용 위치, 문서 범위, 빠진 근거, annotate 재계산."""
    errs = [f"스키마 {list(e.path)}: {e.message}"
            for e in Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).iter_errors(ps)]
    spans, pos = {}, 0
    for d, text in zip(ps["documents"], chart.rstrip("\n").split(DOC_GAP)):
        spans[d["doc_id"]] = (pos, pos + len(text))
        pos += len(text) + len(DOC_GAP)

    def walk(x, path):
        if isinstance(x, dict):
            s = x.get("source")
            if isinstance(s, dict):
                if chart[s["char_start"]:s["char_end"]] != s["quote"]:
                    errs.append(f"인용 위치 {path}")
                lo, hi = spans.get(s["doc_id"], (0, -1))
                if not lo <= s["char_start"] <= s["char_end"] <= hi:
                    errs.append(f"문서 범위 밖 {path} ({s['doc_id']})")
            if x.get("status") in ("present", "not_done") and not isinstance(x.get("source"), dict):
                errs.append(f"근거 없음 {path}")
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(ps["fields"], "fields")
    again = annotate(copy.deepcopy(ps), load_drug_table())
    if again != ps:
        errs.append("annotate 재계산이 다름")
    return errs


def load_case(ref: str) -> Chart:
    """기본 사례(VC-0103) 또는 짝 사례(VC-0103-g365, src/input/chart/cases/pairs.py)."""
    from src.input.chart.cases.pairs import BY_ID
    pair = BY_ID.get(ref)
    base = pair.base if pair else ref
    mod = importlib.import_module(f"src.input.chart.cases.{base.lower().replace('-', '_')}")
    c = mod.build(**(pair.params if pair else {}))
    c.ref = ref
    return c


def out_dir(ref: str) -> Path:
    from src.input.chart.cases.pairs import BY_ID
    return FIXTURES / "pairs" / ref if ref in BY_ID else FIXTURES / ref


def dumps(ps: dict) -> str:
    return json.dumps(ps, ensure_ascii=False, indent=2) + "\n"


def pairs_index() -> tuple[str, str]:
    """pairs/pairs.json (B·C·D가 읽는 기대 판정 목록)과 pairs/README.md."""
    from src.input.chart.cases.pairs import GROUPS, PAIRS
    data = {"groups": {g: {"title": t, "base": b, "base_note": n} for g, (t, b, n) in GROUPS.items()},
            "pairs": [{"id": p.id, "base": p.base, "group": p.group, "change": p.change, "params": p.params,
                       "expect_a": p.expect_a, "expect": p.expect} for p in PAIRS]}
    lines = ["# 짝 사례 (최소 대조쌍)", "",
             "> 담당 A · 2026-10-23 · 만드는 곳 `src/input/chart/cases/pairs.py` · 계획 `notes/evaluation_plan_2026-10-23.md` §2.1", "",
             "기본 사례에서 판정을 가르는 값 하나만 경계 양쪽으로 바꾼 사례다. **같은 묶음의 기본 사례와 짝 사례를 모두 맞혀야 통과**로 센다. "
             "폴더마다 `chart.txt`와 A 정답 `expected/patient_state.json`이 있고, B·C·D 기대 판정 초안은 `pairs.json`의 `expect`에 있다 "
             "(각 담당자가 원문으로 확정). 손으로 고치지 말고 `python -m src.input.chart.virtual_chart`로 다시 만든다.", ""]
    for g, (title, base, note) in GROUPS.items():
        lines += [f"## {g} {title} (기본 {base})", "", note, "", "| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |", "|---|---|---|"]
        for p in (p for p in PAIRS if p.group == g):
            exp = "<br>".join(f"{k}: {v}" for k, v in p.expect.items()) or "—"
            lines.append(f"| `{p.id}` | {p.change} | {exp} |")
        lines.append("")
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n", "\n".join(lines)


def main(argv=None) -> int:
    from src.input.chart.cases.pairs import PAIRS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", default=CASES + [p.id for p in PAIRS])
    ap.add_argument("--check", action="store_true", help="쓰지 않고 저장된 파일과 비교")
    args = ap.parse_args(argv)
    bad = 0
    pj, readme = pairs_index()
    idx = FIXTURES / "pairs"
    if args.check:
        if (idx / "pairs.json").read_text(encoding="utf-8") != pj or (idx / "README.md").read_text(encoding="utf-8") != readme:
            print("pairs/pairs.json·README.md가 pairs.py와 다름")
            bad += 1
    else:
        idx.mkdir(parents=True, exist_ok=True)
        (idx / "pairs.json").write_text(pj, encoding="utf-8", newline="\n")
        (idx / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    for ref in args.ids:
        chart, ps = load_case(ref).build()
        errs = check(chart, ps)
        out = out_dir(ref)
        if args.check:
            if (out / "chart.txt").read_text(encoding="utf-8") != chart:
                errs.append("저장된 chart.txt와 다름")
            if (out / "expected" / "patient_state.json").read_text(encoding="utf-8") != dumps(ps):
                errs.append("저장된 patient_state.json과 다름")
        elif not errs:
            (out / "expected").mkdir(parents=True, exist_ok=True)
            (out / "chart.txt").write_text(chart, encoding="utf-8", newline="\n")
            (out / "expected" / "patient_state.json").write_text(dumps(ps), encoding="utf-8", newline="\n")
        print(f"{ref}: {'OK' if not errs else '; '.join(errs[:8])}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
