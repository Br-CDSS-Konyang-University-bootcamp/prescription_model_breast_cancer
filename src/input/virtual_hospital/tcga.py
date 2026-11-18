"""TCGA ① (수술 후) 갈래: S 고르기 → M 옮기기 → D 계산 → Y·N 합성. 규칙은 rules/rules.csv."""
from __future__ import annotations

import collections
import datetime as dt
import functools
import re
from pathlib import Path

import pandas as pd

from src.input.virtual_hospital.common import FINAL, LOCAL, MINI, ROOT, Patient, Rec, boundary, mini_on_path, read_csv, ref, rng, thresholds

GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
# M-01: 판정 기준일(수술 직후)까지 차트에 보이는 실제 칸
REAL_FIELDS = ["patient.gender", "patient.age", "patient.menopausal_status", "diagnosis.histology", "stage.ptnm",
               "stage.group", "stage.positive_ln_count", "stage.disease_extent", "stage.metastatic_sites",
               "stage.operable", "receptors.er_percent", "receptors.pr_percent", "receptors.her2_ihc",
               "receptors.her2_ish"]
# D-02: 진단일 기준 일수
DAY_SURGERY, DAY_PATH, DAY_NGS, DAY_INDEX = 21, 27, 41, 49
SLIDE_QC = FINAL / "data" / "tcga" / "qc" / "slide_qc.csv"
EXPR = FINAL / "data" / "tcga" / "expr.parquet"
HR_POS = {"positive", "low_positive"}


def load() -> tuple[pd.DataFrame, dict[str, dict]]:
    """mini 크롭본과 mini 변환기 결과 (S-01, M-01)."""
    mini_on_path()
    from src.input.virtual_hospital.tcga_convert import convert, load_rows
    df = load_rows()
    return df, convert(df)


def entry(ps: dict, path: str) -> dict:
    g, *rest = path.split(".")
    e = ps["fields"][g]
    for k in rest:
        e = e[k]
    return e


def dx_slides() -> dict[str, list[dict]]:
    """S-04: H&E 진단 슬라이드(DX) 목록 (환자별)."""
    out = collections.defaultdict(list)
    for r in read_csv(SLIDE_QC):
        if "-DX" in r["slide"] and r["stain"] == "H&E" and not r["error"]:
            out[r["patient_id"]].append(r)
    return out


def subtype(ps: dict) -> str:
    er, pr = entry(ps, "receptors.er_percent"), entry(ps, "receptors.pr_percent")
    ihc, ish = entry(ps, "receptors.her2_ihc"), entry(ps, "receptors.her2_ish")
    hr = any(e.get("status") == "present" and e["value"].get("result") in HR_POS for e in (er, pr))
    her2 = (ihc.get("status") == "present" and (ihc["value"].get("result") == "positive"
                                                or ihc["value"].get("score") == "3+")) or \
           (ish.get("status") == "present" and ish["value"].get("result") == "amplified")
    return "HER2+" if her2 else "HR+/HER2-" if hr else "TNBC"


def her2_conflict(row: pd.Series) -> str:
    """S-07: HER2 IHC 판정·점수·FISH가 서로 맞지 않으면 그 이유 (ASCO/CAP 정의 기준). 맞으면 빈 문자열."""
    call = row["gdc_her2_status_by_ihc"]
    score = row["gdc_her2_ihc_score"] if row["gdc_her2_ihc_score"] in ("0", "1+", "2+", "3+") else None
    fish = row["gdc_her2_fish_status"] if row["gdc_her2_fish_status"] in ("Positive", "Negative", "Equivocal") else None
    if call == "Positive" and score in ("0", "1+"):
        return f"판정 양성인데 점수 {score}"
    if call == "Positive" and score == "2+" and fish != "Positive":
        return f"판정 양성인데 점수 2+이고 FISH {fish or '없음'}"
    if call == "Positive" and score is None and fish == "Negative":
        return "판정 양성인데 점수 없고 FISH 음성"
    if call == "Negative" and score == "3+":
        return "판정 음성인데 점수 3+"
    if call == "Negative" and fish == "Positive":
        return "판정 음성인데 FISH 양성"
    if call == "Equivocal" and score in ("0", "1+", "3+"):
        return f"판정 경계인데 점수 {score}"
    return ""


def first_drug_day(ps: dict) -> int | None:
    """실제 첫 투약 시작일 (시작일 있는 투약만)."""
    days = [t["start_day"] for t in ps["fields"].get("treatment_history") or [] if t.get("start_day") is not None]
    return min(days) if days else None


def postop_index(ps: dict) -> int:
    """D-10: TCGA ① 판정 기준일 = 실제 첫 보조 투약일과 49일 중 빠른 날 (그날 시작한 약부터는 차트에 없음)."""
    first = first_drug_day(ps)
    return DAY_INDEX if first is None else min(DAY_INDEX, first)


def select(df: pd.DataFrame, pss: dict[str, dict]) -> tuple[list[str], list[dict], dict[str, str]]:
    """S-02 ~ S-08. 남는 환자 ID와 뺀 환자·이유. 분할(학습·시험)은 나누지 않는다 (2026-11-10 사용자 결정)."""
    slides = dx_slides()
    rows = df.set_index("patient_id")
    keep, dropped = [], []
    for pid in sorted(pss):
        ps = pss[pid]
        reason = None
        group = entry(ps, "stage.group")
        if rows.loc[pid, "gdc_history_neoadjuvant_treatment"] == "Yes":
            reason = "S-02 선행요법"
        elif group.get("status") != "present" or group["value"] in ("IV", "not_assessed") \
                or entry(ps, "stage.disease_extent").get("value") == "metastatic":
            reason = "S-03 진단 시 IV기 또는 병기 판정 불가"
        elif pid not in slides:
            reason = "S-04 H&E 진단 슬라이드 없음"
        elif her2_conflict(rows.loc[pid]):
            reason = "S-07 HER2 원자료 모순: " + her2_conflict(rows.loc[pid])
        elif rows.loc[pid, "gdc_ajcc_nodes_pathologic_pn"] == "NX" or rows.loc[pid, "gdc_ajcc_tumor_pathologic_pt"] == "TX":
            reason = "S-08 pN 또는 pT가 X (평가 안 됨)"
        elif (first := first_drug_day(ps)) is not None and first < DAY_PATH:
            reason = f"S-10 첫 투약({first}일)이 가짜 병리 보고일({DAY_PATH}일) 전: 수술 후 보조요법 결정 장면을 실제 순서로 못 만듦"
        else:
            need = ["patient.gender", "patient.age", "stage.group"]
            miss = [p for p in need if entry(ps, p).get("status") != "present"]
            for p in ("receptors.er_percent", "receptors.pr_percent"):
                e = entry(ps, p)
                if e.get("status") != "present" or not e["value"].get("result"):
                    miss.append(p)
            if all(entry(ps, p).get("status") != "present" for p in ("receptors.her2_ihc", "receptors.her2_ish")):
                miss.append("receptors.her2")
            if miss:
                reason = "S-06 필수 칸 결측: " + ", ".join(miss)
        if reason:
            dropped.append({"source_id": pid, "rule": reason.split()[0], "reason": reason})
        else:
            keep.append(pid)
    return keep, dropped


# ---------- 합성 근거 표 (②: 같은 데이터 안 실제 관계) ----------
def her2_status(score: str, fish: str | None) -> str:
    """mini PROJECT.md §5 HER2 판정표 (점수가 있을 때). ISH 없는 2+는 판정에 적힌 값이 필요하므로 'need_ish'."""
    if score == "3+":
        return "positive"
    if score == "2+":
        return {"amplified": "positive", "not_amplified": "low"}.get(fish, "need_ish")
    if score == "1+":
        return "low"
    return "unknown" if fish == "amplified" else "negative"


def synth_her2(p: Patient, call: str, ctx: "Context") -> None:
    """Y-07: 점수·ISH 없이 IHC 판정만 있는 환자. 같은 판정 환자들의 실제 (점수, ISH) 조합 분포에서 vp 번호 난수로 뽑는다.
    뽑은 조합은 mini HER2 판정표로 판정해도 원래 판정과 같다 (양성 → 양성, 음성 → 저발현·음성)."""
    pool = ctx.her2.get(call)
    if not pool:
        p.problems.append(f"HER2 IHC 판정 '{call}'만 있고 같은 판정의 실제 점수 조합이 없음")
        return
    score, fish = pick(pool, rng(p.vp_id, "Y-07"))
    note = f"원래 IHC 판정 {call}만 있음 (점수·FISH 없음). 같은 판정 실제 조합 분포에서 뽑음"
    p.add(Rec("receptors.her2_ihc", "present", {"score": score}, "synthetic", "②", "Y-07",
              observed_date=p.recs["receptors.her2_ihc"].observed_date, specimen="primary", note=note))
    if fish:
        p.add(Rec("receptors.her2_ish", "present", {"result": fish, "method": "FISH"}, "synthetic", "②", "Y-07",
                  observed_date=p.recs["receptors.her2_ihc"].observed_date, specimen="primary", note=note))


def allred_ps(rg: list[int]) -> int:
    """D-07: 비율 구간 → Allred 비율 점수 (PS). 구간의 가운데 값으로 정한다 (0% 0, <1% 1, 1~10% 2, 11~33% 3, 34~66% 4, 67~100% 5)."""
    lo, hi = rg
    if lo == hi == 0:
        return 0
    mid = (lo + hi) / 2
    return 1 if mid < 1 else 2 if mid <= 10 else 3 if mid <= 33 else 4 if mid <= 66 else 5


def allred_is_choices(field: str, result: str, ps: int) -> list[int]:
    """Y-06: 강도 점수(IS) 후보. 총점(PS + IS)을 mini B 규칙으로 판정했을 때 원래 판정과 같아야 한다.
    ER: 0~2 음성, 3~4 저발현, 5는 비율(PS 2 저발현, 3~5 양성), 6~8 양성 / PR: 0~2 음성, 3 이상 양성."""
    def er(total):
        return "negative" if total <= 2 else "low_positive" if total <= 4 else \
            ("low_positive" if ps <= 2 else "positive") if total == 5 else "positive"

    def pr(total):
        return "negative" if total <= 2 else "positive"
    judge = er if field == "receptors.er_percent" else pr
    lo = 0 if result == "negative" else 1                    # 양성인데 염색 강도 0은 쓰지 않는다
    return [i for i in range(lo, 4) if judge(ps + i) == result and (result != "negative" or i == 0 or ps > 0)]


ALLRED_TEXT = {"receptors.er_percent": ("gdc_er_positivity_method", "gdc_er_positivity_scale_other"),
               "receptors.pr_percent": ("gdc_pr_positivity_define_method", "gdc_pr_positivity_scale_other")}


def parse_allred(text) -> tuple[int, int | None, int | None] | None:
    """'Allred score 5+3 = 8', 'Allred 8 = 5+3', 'Allred score = 7' → (총점, PS, IS). 총점은 0~8 (PS 0~5 + IS 0~3)."""
    if not isinstance(text, str) or not re.search("allred", text, re.I):
        return None
    m = re.search(r"(\d)\s*\+\s*(\d)\s*[=+]\s*(\d)", text)          # 'a+b=T' ('5+3+8' 오타 포함)
    if m:
        return int(m[3]), int(m[1]), int(m[2])
    m = re.search(r"(\d)\s*=\s*(\d)\s*\+\s*(\d)", text)             # 'T = a+b'
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    m = re.search(r"(\d)", text)
    return (int(m[1]), None, None) if m else None


def load_allred(pids: set[str]) -> dict[tuple[str, str], tuple]:
    """(환자, 칸) → (총점, PS, IS). 두 칸에 다 있으면 PS+IS가 나눠 적힌 쪽을 쓴다. 나눠 적힌 값은 PS+IS = 총점이어야 한다."""
    path = ROOT / "source" / "tcga_brca_merged.csv"
    cols = ["patient_id"] + [c for v in ALLRED_TEXT.values() for c in v]
    m = pd.read_csv(path, dtype=str, usecols=cols).set_index("patient_id")
    out = {}
    for pid in pids & set(m.index):
        for field, cs in ALLRED_TEXT.items():
            found = [x for x in (parse_allred(m.at[pid, c]) for c in cs) if x]
            full = [x for x in found if x[1] is not None and x[1] + x[2] == x[0] and x[1] <= 5 and x[2] <= 3]
            pick_ = (full or [x for x in found if x[1] is None and x[0] <= 8])[:1]
            if pick_:
                out[(pid, field)] = pick_[0]
    return out


def real_allred(p: Patient, path: str, r: Rec, res: str, real: tuple, ctx: "Context") -> None:
    """D-09: 실제 Allred 총점. PS·IS가 나눠 적혀 있으면 그대로, 총점만 있으면 실제 % 구간으로 PS를 정하고 IS = 총점 − PS.
    구간도 없으면 같은 총점이 나눠 적힌 실제 환자들의 (PS, IS) 분포에서 뽑는다. 판정·실제 구간과 맞지 않으면 제외."""
    total, ps, is_ = real
    real_range = r.origin == "real" and "range" in r.value
    if ps is None:
        if real_range:
            ps, is_ = allred_ps(r.value["range"]), total - allred_ps(r.value["range"])
            how = f"총점은 실제, PS는 실제 구간 {r.value['range']}에서, IS = 총점 − PS"
        else:
            pool = collections.Counter({k: n for k, n in ctx.allred_split[(path, total)].items()
                                        if k[1] in allred_is_choices(path, res, k[0])})
            if pool:
                ps, is_ = pick(pool, rng(p.vp_id, "D-09" + path))
                how = "총점은 실제, PS+IS는 같은 총점이 나눠 적힌 실제 환자 분포에서"
            else:                                            # 실제 예가 없으면 판정과 맞는 나눔 중에서 고르게
                splits = [(a, total - a) for a in range(0, 6) if 0 <= total - a <= 3 and not (a == 0 and total > 0)
                          and (total - a) in allred_is_choices(path, res, a)]
                if not splits:
                    p.problems.append(f"{path} 실제 Allred 총점 {total}이 판정 {res}와 맞지 않음 (원자료 모순)")
                    return
                ps, is_ = rng(p.vp_id, "D-09" + path).choice(splits)
                how = "총점은 실제, PS+IS는 실제 예가 없어 판정과 맞는 나눔 중에서 고르게"
    else:
        how = "총점·PS·IS 모두 실제"
        if real_range and allred_ps(r.value["range"]) != ps:
            p.problems.append(f"{path} 실제 Allred PS {ps}와 실제 % 구간 {r.value['range']}가 맞지 않음 (원자료 모순)")
            return
    if not (0 <= is_ <= 3) or is_ not in allred_is_choices(path, res, ps):
        p.problems.append(f"{path} 실제 Allred {ps}+{is_}={total}이 판정 {res}와 맞지 않음 (원자료 모순)")
        return
    p.add(Rec(path, "present", {"allred": {"total": total, "ps": ps, "is": is_}, "result": res}, "real", "", "D-09",
              source_column=" / ".join(ALLRED_TEXT[path]), observed_date=r.observed_date, specimen="primary",
              note=f"판정은 실제, {how}"))


def to_allred(p: Patient, path: str, ctx: "Context") -> None:
    """D-07 + D-08/Y-06: ER·PR을 'ER 강양성 (Allred 8, 5+3)' 형식으로. 비율 점수는 실제 구간에서,
    강도 점수는 그 환자의 실제 값이 있으면 그것(D-08), 없으면 같은 판정 환자의 실제 강도 분포에서(Y-06)."""
    r = p.recs[path]
    res = r.value["result"]
    real = ctx.allred_real.get((p.source_id, path))
    if real:                                                 # D-09: 원자료에 Allred 총점이 적힌 환자
        real_allred(p, path, r, res, real, ctx)
        return
    if "range" in r.value:
        ps = allred_ps(r.value["range"])
    elif res == "negative":
        ps = 0
    elif res == "low_positive":
        ps = 2                                               # ER 저발현의 정의 (1~10%)
    else:
        p.problems.append(f"{path} 양성인데 비율 구간이 없음 (Y-03도 못 만듦)")
        return
    choices = allred_is_choices(path, res, ps)
    if not choices:
        p.problems.append(f"{path} 판정 {res}와 비율 점수 {ps}가 맞지 않음 (원자료 모순)")
        return
    own = ctx.own_is.get((p.source_id, path))
    if own in choices:                                       # D-08: 그 환자의 실제 강도 점수
        is_, origin, basis, rule, how = own, "derived", "①", "D-08", "IS는 실제 (TCGA 강도 점수 열)"
    else:
        is_, basis = pick_is(ctx, path, res, choices, rng(p.vp_id, "Y-06" + path))
        origin, rule = "synthetic", "Y-06"
        how = "IS는 합성 (" + ("실제 값이 판정과 맞지 않아 " if own is not None else "") + \
              ("TCGA 같은 판정 실제 강도 분포)" if basis == "②" else "실제 분포가 없어 고르게)")
    p.add(Rec(path, "present", {"allred": {"total": ps + is_, "ps": ps, "is": is_}, "result": res}, origin, basis,
              rule, observed_date=r.observed_date, specimen="primary",
              note=f"판정은 실제, PS는 구간 {r.value.get('range')}에서 (D-07), {how}"))


def pick_is(ctx: "Context", path: str, res: str, choices: list[int], r) -> tuple[int, str]:
    """Y-06: 같은 판정 환자들의 실제 강도 점수 분포에서, mini 규칙과 맞는 후보(choices)만 남겨 뽑는다. (값, 근거)."""
    pool = collections.Counter({k: n for k, n in ctx.intensity[(path, res)].items() if k in choices})
    if pool:
        return pick(pool, r), "②"
    return r.choice(choices), "⑤"


# 실제 강도 점수 열 (mini 병합본, 크롭본에는 없음). 3점 척도와 척도 미기재의 0~3+만 쓴다 (4점 척도·4+는 Allred로 옮길 수 없음)
INTENSITY = {"receptors.er_percent": ("gdc_er_ihc_score", "gdc_er_positivity_scale_used", "gdc_er_status_by_ihc"),
             "receptors.pr_percent": ("gdc_pr_positivity_ihc_intensity_score", "gdc_pr_positivity_scale_used",
                                      "gdc_pr_status_by_ihc")}

def load_intensity(pids: set[str]) -> dict[tuple[str, str], int]:
    """(환자, 칸) → 실제 강도 점수 0~3."""
    path = ROOT / "source" / "tcga_brca_merged.csv"
    cols = ["patient_id"] + [c for v in INTENSITY.values() for c in v]
    m = pd.read_csv(path, dtype=str, usecols=cols).set_index("patient_id")
    out = {}
    for pid in pids & set(m.index):
        for field, (val, scale, _) in INTENSITY.items():
            v, s = m.at[pid, val], m.at[pid, scale]
            if s == "4 Point Scale" or v not in ("0", "1+", "2+", "3+"):
                continue
            out[(pid, field)] = int(v[0])
    return out


class Context:
    """Y-02·Y-03·Y-04에 쓰는 실제 분포. 838명 전체 실제 값에서 만든다 (가려 놓은 환자는 빼고 만들 수 있게 masked 인자)."""

    def __init__(self, pss: dict[str, dict], masked: set[str] = frozenset()):
        self.meno = collections.defaultdict(collections.Counter)      # 5년 나이대 → 폐경 상태 수
        self.ranges = collections.defaultdict(collections.Counter)    # (칸, 판정) → 구간 수
        for pid, ps in pss.items():
            if pid in masked:
                continue
            age, meno = entry(ps, "patient.age"), entry(ps, "patient.menopausal_status")
            if age.get("status") == "present" and meno.get("status") == "present" \
                    and meno["value"] in ("premenopausal", "postmenopausal", "perimenopausal"):
                self.meno[age["value"] // 5 * 5][meno["value"]] += 1
            for p in ("receptors.er_percent", "receptors.pr_percent"):
                e = entry(ps, p)
                if e.get("status") == "present" and "range" in e["value"]:
                    self.ranges[(p, e["value"]["result"])][tuple(e["value"]["range"])] += 1
        # Y-07: IHC 판정별 실제 (점수, ISH) 조합. mini HER2 판정표와 맞는 조합만 (her2_status)
        self.her2 = collections.defaultdict(collections.Counter)
        for pid, ps in pss.items():
            ihc, ish = entry(ps, "receptors.her2_ihc"), entry(ps, "receptors.her2_ish")
            if pid in masked or ihc.get("status") != "present" or "score" not in ihc["value"]:
                continue
            call = ihc["value"].get("result")
            fish = ish["value"]["result"] if ish.get("status") == "present" else None
            if her2_status(ihc["value"]["score"], fish) == {"positive": "positive"}.get(call, "not_positive") \
                    or (call == "negative" and her2_status(ihc["value"]["score"], fish) in ("low", "negative")):
                self.her2[call][(ihc["value"]["score"], fish)] += 1
        # Y-06: (칸, 판정)별 실제 강도 점수 분포 (TCGA 강도 점수 열)
        # D-09: 원자료 Allred 총점과, 총점별 실제 (PS, IS) 나눔
        self.allred_real = load_allred(set(pss) - set(masked))
        self.allred_split = collections.defaultdict(collections.Counter)
        for (pid, field), (t, a, b) in self.allred_real.items():
            if a is not None:
                self.allred_split[(field, t)][(a, b)] += 1
        self.own_is = load_intensity(set(pss) - set(masked))
        self.intensity = collections.defaultdict(collections.Counter)
        for (pid, field), v in self.own_is.items():
            res = entry(pss[pid], field).get("value", {}).get("result")
            if res:
                self.intensity[(field, res)][v] += 1
        self.mki67 = None
        if EXPR.exists():
            m = pd.read_parquet(EXPR, columns=["MKI67"])["MKI67"]
            self.mki67 = m.rank(pct=True).to_dict()                     # 코호트 안 순위 (0~1]


def pick(counter: collections.Counter, r) -> object:
    items = sorted(counter.items(), key=lambda kv: str(kv[0]))
    total = sum(n for _, n in items)
    x = r.random() * total
    for k, n in items:
        x -= n
        if x < 0:
            return k
    return items[-1][0]


def synth_ecog(vp: str, age: int) -> int:
    """Y-01: 나이대별 ECOG 1 이상 비율(references R-03)에서 vp 번호 난수로 0 또는 1. 출처 표에 2 이상이 따로 없어 1로 쓴다."""
    band = "18-39" if age < 40 else "40-49" if age < 50 else "50-64" if age < 65 else "65-74" if age < 75 else "75+"
    return 1 if rng(vp, "Y-01").random() < float(ref("R-03", band)) else 0


def synth_meno(vp: str, age: int, ctx: Context) -> str:
    """Y-02."""
    if age < 40:
        return "premenopausal"
    if age >= 60:
        return "postmenopausal"
    band = ctx.meno.get(age // 5 * 5)
    if not band or sum(band.values()) < 10:                          # 표본이 적으면 앞뒤 나이대를 합친다
        band = sum((ctx.meno.get(age // 5 * 5 + d, collections.Counter()) for d in (-5, 0, 5)),
                   collections.Counter())
    return pick(band, rng(vp, "Y-02"))


def synth_range(vp: str, path: str, result: str, ctx: Context) -> list[int] | None:
    """Y-03. 경계 금지 구간에 걸치는 구간은 빼고 뽑는다. 음성·약양성은 합성하지 않는다."""
    if result != "positive":
        return None
    lo_b, hi_b = boundary(path.split(".")[1])
    pool = collections.Counter({k: n for k, n in ctx.ranges[(path, result)].items()
                                if k[1] < lo_b or k[0] > hi_b})
    return list(pick(pool, rng(vp, "Y-03" + path))) if pool else None


def synth_ki67(vp: str, pid: str, sub: str, ctx: Context) -> tuple[int, str]:
    """Y-04. (값, 근거)."""
    rate = float(ref("R-01", sub))
    if sub == "HR+/HER2-" and ctx.mki67 and pid in ctx.mki67:
        q = ctx.mki67[pid]
        cut = 1 - rate
        if q <= cut:
            return (5 if q <= cut / 2 else 10), "③"
        step = (q - cut) / rate                                         # 높음 안에서 0~1
        return [30, 40, 50, 60][min(3, int(step * 4))], "③"
    r = rng(vp, "Y-04")
    if r.random() < rate:
        return r.choice([30, 40, 50, 60]), "④"
    return r.choice([5, 10]), "④"


def synth_grade(vp: str, sub: str, ki67: int) -> int:
    """Y-05 (M-05 판독 점수가 없는 환자만). 아형별 grade 비율 (references R-02, 한국 KBCR). Ki-67 높음 여부로 나누지 않는다:
    출처 표가 아형별로만 나와 있다. ki67 인자는 호출 모양을 바꾸지 않으려고 남긴다."""
    p = [float(x) for x in ref("R-02", sub).split("/")]
    x = rng(vp, "Y-05").random()
    return 1 if x < p[0] else 2 if x < p[0] + p[1] else 3


NOTTINGHAM = LOCAL / "thennavan2021" / "mmc3.xlsx"     # CC BY-NC-ND 4.0: 원본은 local/에만 (git 제외)
NOTTINGHAM_COLS = ("Epithelial tubule formation", "Nuclear pleomorphism", "Mitosis")


@functools.cache
def nottingham() -> dict[str, tuple[int, int, int]]:
    """M-05: TCGA 환자 ID → (관 형성, 핵 다형성, 유사분열) 점수 1~3. 세 점수가 다 있는 환자만. 파일이 없으면 빈 표 (전부 Y-05)."""
    if not NOTTINGHAM.exists():
        print(f"경고: {NOTTINGHAM} 없음 → grade는 모두 합성 (Y-05)")
        return {}
    df = pd.read_excel(NOTTINGHAM)
    df.columns = [str(c).strip() for c in df.columns]
    out = {}
    for _, r in df.iterrows():
        s = [re.match(r"\(score = ([123])\)", str(r[c]).strip()) for c in NOTTINGHAM_COLS]
        if all(s):
            out[str(r["Sample CLID"]).strip()] = tuple(int(m.group(1)) for m in s)
    return out


def dx_date(vp: str) -> str:
    """D-01."""
    start = dt.date(2022, 1, 3)
    return (start + dt.timedelta(days=rng(vp, "D-01").randrange(0, 1092))).isoformat()


def variant_type(prot: str, cdna: str) -> str | None:
    """D-05: 차트에는 변이 종류가 적히지 않으므로 표기에서 정한다 (mini 입력 모듈 pipeline._gene과 같은 약속)."""
    frame = "Frame_Shift_Del" if "del" in cdna else "Frame_Shift_Ins" if re.search("dup|ins", cdna) else "Frame_Shift"
    return ("Nonsense_Mutation" if re.fullmatch(r"[A-Z]\d+\*", prot) else
            frame if "fs" in prot else "Missense_Mutation" if re.fullmatch(r"[A-Z]\d+[A-Z]", prot) else None)


def chart_path(p: Patient, ps: dict, hgvsc: dict, ctx: "Context") -> None:
    """D-05·N-05: 실제 값을 차트로 썼을 때 mini 입력 모듈이 읽는 정규값으로 맞춘다. 쓸 수 없으면 problems에 적는다."""
    R = p.recs
    # pTNM: X(not_assessed)는 mini 입력 모듈이 'MX'로 읽어 스키마 설명(→ not_assessed)과 다르다 → 넘길 목록
    t = R["stage.ptnm"].value
    if t["m"] == "not_assessed" and R["stage.group"].value != "IV":
        # D-06: MX인데 병기군이 I~III기면 원격 전이 없음으로 본다 (IV기는 S-03에서 이미 뺐다)
        t = {**t, "m": "M0"}
        p.add(Rec("stage.ptnm", "present", t, "derived", "①", "D-06", observed_date=R["stage.ptnm"].observed_date,
                  note=f"원래 MX, 병기군 {R['stage.group'].value} → M0"))
    bad_t = re.fullmatch(r"T([23])[a-d]", t["t"])
    if bad_t:
        # D-11: 유방암 AJCC 7판 T2·T3에는 하위 글자가 없다 (T2a·T3a는 다른 암 표기). TCGA에 종양 크기 칸이 없어 숫자만 쓴다.
        # N0이면 병기군으로 확인할 수 있다 (T2N0 = IIA, T3N0 = IIB). 맞지 않으면 원자료 모순
        want = {"2": "IIA", "3": "IIB"}[bad_t.group(1)] if t["n"].startswith("N0") else None
        if want and R["stage.group"].value != want:
            p.problems.append(f"원자료 모순: pT {t['t']} N0인데 병기군 {R['stage.group'].value}")
        t = {**t, "t": f"T{bad_t.group(1)}"}
        prev = R["stage.ptnm"]
        p.add(Rec("stage.ptnm", "present", t, "derived", "①", ", ".join(x for x in (prev.rule_id if prev.origin == "derived" else "", "D-11") if x),
                  observed_date=prev.observed_date, note="; ".join(x for x in (prev.note if prev.origin == "derived" else "",
                  f"원래 {bad_t.group(0)} (유방암 병기에 없는 하위 글자), 병기군 {R['stage.group'].value}") if x)))
    if "not_assessed" in (t["t"], t["n"], t["m"]):
        p.problems.append("pTNM에 X(not_assessed): mini 입력 모듈은 TX·NX·MX를 not_assessed로 바꾸지 않음")
    else:
        n = re.match(r"N([0-3][a-c]?(?:mi)?)", t["n"])
        m = re.search(r"M([01])", t["m"])
        new = {**t, "n": f"N{n.group(1)}" if n else t["n"], "m": f"M{m.group(1)}" if m else t["m"]}
        if new != t:
            prev = R["stage.ptnm"]
            p.add(Rec("stage.ptnm", "present", new, "derived", "①", ", ".join(x for x in (prev.rule_id if prev.origin == "derived" else "", "D-05") if x),
                      observed_date=prev.observed_date, note="; ".join(x for x in (prev.note if prev.origin == "derived" else "",
                      f"원래 {t['n']} {t['m']} (mini 입력 모듈은 (i-)·(i+) 꼬리표를 뗀다)") if x)))
        if new["m"] == "M0" and R["stage.metastatic_sites"].value != "[Not Applicable]":
            p.add(Rec("stage.metastatic_sites", "present", "[Not Applicable]", "derived", "①", "D-05",
                      note=f"원래 {R['stage.metastatic_sites'].value} (M0이면 해당 없음)"))
    # HER2 IHC: mini 입력 모듈은 점수만 읽는다
    ihc, ish = R["receptors.her2_ihc"], R["receptors.her2_ish"]
    if ihc.status == "present":
        if "score" in ihc.value:
            if set(ihc.value) != {"score"}:
                p.add(Rec("receptors.her2_ihc", "present", {"score": ihc.value["score"]}, "derived", "①", "D-05",
                          observed_date=ihc.observed_date, specimen="primary",
                          note=f"원래 {ihc.value} (판정은 점수에서 B가 정함)"))
        elif ish.status == "present" and ish.value.get("result") in ("amplified", "not_amplified"):
            # ISH가 판정을 정할 수 있을 때만 (2026-11-10: ISH equivocal 1명이 HER2 unknown이 되어 고침)
            p.add(Rec("receptors.her2_ihc", "not_recorded", None, "derived", "①", "N-05",
                      note=f"원래 {ihc.value}: 점수 없는 IHC 판정은 mini가 읽지 못해 쓰지 않음 (ISH로 판정)"))
        else:
            synth_her2(p, ihc.value.get("result"), ctx)
    # 림프절: 검사 수가 없으면 mini 입력 모듈이 읽지 못한다
    ln = R["stage.positive_ln_count"]
    if ln.status == "present" and not all(isinstance(ln.value.get(k), int) for k in ("positive", "examined")):
        p.add(Rec("stage.positive_ln_count", "not_recorded", None, "derived", "①", "N-05",
                  note=f"원래 {ln.value}: 전이 수·검사 수 중 하나가 없으면 mini가 읽지 못해 쓰지 않음 (pN으로 남음)"))
    # 변이: c. 표기 (M-03) + 차트 경로 변이 종류 (D-05)
    for g in GENES:
        r = R[f"molecular.mutations.{g}"]
        if r.status != "present" or r.value["result"] != "detected":
            continue
        vs = []
        for v in r.value["variants"]:
            cdna = hgvsc.get((p.source_id, g, v["protein_change"]))
            if not cdna:
                p.problems.append(f"{g} p.{v['protein_change']}: c. 표기 없음 (GDC에서도 못 찾음)")
                continue
            p.cdna[(g, v["protein_change"])] = cdna
            vaf = None if v.get("vaf") is None else round(float(f"{v['vaf'] * 100:g}") / 100, 6)
            vs.append({"protein_change": v["protein_change"], "variant_type": variant_type(v["protein_change"], cdna),
                       "vaf": vaf})
        p.add(Rec(f"molecular.mutations.{g}", "present", {"result": "detected", "variants": vs}, "derived", "①",
                  "D-05", specimen="primary", note="M-03 c. 표기 추가, 변이 종류는 표기에서"))


def load_hgvsc() -> dict:
    path = ROOT / "tcga_hgvsc.csv"
    return {(r["case"], r["gene"], r["protein_change"]): r["hgvsc"] for r in read_csv(path)} if path.exists() else {}


def build(vp: str, pid: str, row: pd.Series, ps: dict, ctx: Context, slides: list[dict], hgvsc: dict) -> Patient:
    dxd = dx_date(vp)
    on = lambda d: (dt.date.fromisoformat(dxd) + dt.timedelta(days=d)).isoformat()   # noqa: E731
    p = Patient(vp, pid, "TCGA_postop", "", dxd, postop_index(ps),
                side=rng(vp, "D-04").choice(["좌측", "우측"]), slides=slides)
    for path in REAL_FIELDS:
        e = entry(ps, path)
        obs = on(DAY_SURGERY) if path.startswith(("receptors.", "stage.ptnm")) else None
        spec = "primary" if path.startswith("receptors.") else None
        p.add(Rec(path, e["status"], e.get("value"), "real", rule_id="M-01", source_column="mini convert",
                  observed_date=obs if e["status"] == "present" else None, specimen=spec))
    for g in GENES:
        e = entry(ps, f"molecular.mutations.{g}")
        val = {"result": e.get("result"), "variants": e.get("variants", [])} if e["status"] == "present" else None
        p.add(Rec(f"molecular.mutations.{g}", e["status"], val, "real", rule_id="M-01", source_column="mini convert",
                  specimen="primary" if e["status"] == "present" else None))

    chart_path(p, ps, hgvsc, ctx)

    # D: 계산
    p.add(Rec("diagnosis.diagnosis_date", "present", dxd, "derived", "⑤", "D-01"))
    p.add(Rec("recurrence.status", "present", "none", "derived", "①", "D-03", note="판정 기준일 = 수술 직후"))

    # Y·N: 합성
    age = p.recs["patient.age"].value
    meno = p.recs["patient.menopausal_status"]
    if meno.status != "present" or meno.value not in ("premenopausal", "postmenopausal", "perimenopausal"):
        p.add(Rec("patient.menopausal_status", "present", synth_meno(vp, age, ctx), "synthetic", "②", "Y-02",
                  note=f"원래 {meno.status}:{meno.value}"))
    for path in ("receptors.er_percent", "receptors.pr_percent"):
        r = p.recs[path]
        if "range" not in r.value:
            rg = synth_range(vp, path, r.value["result"], ctx)
            if rg:
                p.add(Rec(path, "present", {"range": rg, "result": r.value["result"]}, "synthetic", "②", "Y-03",
                          observed_date=r.observed_date, specimen="primary", note="result는 실제, range는 합성"))
        to_allred(p, path, ctx)
    sub = subtype(ps)
    k, basis = synth_ki67(vp, pid, sub, ctx)
    p.add(Rec("proliferation.ki67_percent", "present", {"percent": k}, "synthetic", basis, "Y-04",
              observed_date=on(DAY_SURGERY), specimen="primary"))
    scores = nottingham().get(pid)
    if scores:
        # M-05: 병리 전문의 판독 (Heng 2017 채점표, Thennavan 2021 Data S2)의 세 점수 합으로 Nottingham 등급
        total = sum(scores)
        p.grade_scores = scores
        p.add(Rec("diagnosis.grade", "present", 1 if total <= 5 else 2 if total <= 7 else 3, "real", rule_id="M-05",
                  source_column="Thennavan 2021 Data S2: tubule, pleomorphism, mitosis",
                  note=f"관 형성 {scores[0]} + 핵 다형성 {scores[1]} + 유사분열 {scores[2]} = {total}"))
    else:
        p.add(Rec("diagnosis.grade", "present", synth_grade(vp, sub, k), "synthetic", "④", "Y-05",
                  note="Thennavan 2021 판독 점수 없음"))
    p.add(Rec("patient.ecog", "present", synth_ecog(vp, age), "synthetic", "④", "Y-01",
              observed_date=on(p.index_day)))

    # M-02: 수술 뒤 값은 정답 표로
    def val(c):
        v = row.get(c)
        return None if pd.isna(v) else v
    p.truth = {"subtype_rule": sub, "pam50": val("cbio_SUBTYPE"), "recurrence_status": val("recurrence_status"),
               "metastasis_dx_days": val("metastasis_dx_days"), "actual_prescriptions_reference": val("drug_timeline"),
               "os_months": val("cbio_OS_MONTHS"), "os_status": val("cbio_OS_STATUS"),
               "pfs_months": val("cbio_PFS_MONTHS"), "pfs_status": val("cbio_PFS_STATUS"),
               "dfs_months": val("cbio_DFS_MONTHS"), "dfs_status": val("cbio_DFS_STATUS")}
    return p


def build_all() -> tuple[list[Patient], list[dict], dict[str, dict], pd.DataFrame]:
    df, pss = load()
    keep, dropped = select(df, pss)
    ctx, slides, hgvsc = Context(pss), dx_slides(), load_hgvsc()
    rows = df.set_index("patient_id")
    s10 = {d["source_id"] for d in dropped if d["rule"] == "S-10"}
    ids = {pid: f"VH-T{i + 1:04d}" for i, pid in enumerate(sorted(set(keep) | s10))}   # S-10으로 뺀 환자도 번호 자리 유지
    pts = [build(ids[pid], pid, rows.loc[pid], pss[pid], ctx, slides[pid], hgvsc) for pid in keep]
    return pts, dropped, pss, df


def out_dir() -> Path:
    from src.input.virtual_hospital.common import OUT
    return OUT / "tcga"
