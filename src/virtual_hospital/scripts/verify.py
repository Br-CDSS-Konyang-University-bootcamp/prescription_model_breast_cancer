"""V 검증: 가상 데이터가 실제 TCGA와 같은지 (notes/design.md §11.1). 생성기와 다른 코드로 다시 읽는다."""
from __future__ import annotations

import collections
import datetime as dt
import random
import re
from pathlib import Path

import pandas as pd

from src.virtual_hospital.scripts.common import FINAL, Patient, thresholds
from src.virtual_hospital.scripts.tcga import DAY_INDEX, DAY_PATH, Context, entry, nottingham, synth_meno, synth_range

STAGE = {"Stage I": "I", "Stage IA": "IA", "Stage IB": "IB", "Stage II": "II", "Stage IIA": "IIA",
         "Stage IIB": "IIB", "Stage III": "III", "Stage IIIA": "IIIA", "Stage IIIB": "IIIB", "Stage IIIC": "IIIC"}
RESULT = {"Positive": "positive", "Negative": "negative", "Low Positive": "low_positive"}


def v1(pts: list[Patient], df: pd.DataFrame) -> dict:
    """복사: 크롭본 원래 열을 직접 읽어 real 칸과 비교 (mini 변환기를 거치지 않음)."""
    rows = df.set_index("patient_id")
    checks = collections.Counter()
    bad = []

    def cmp(name, got, want, vp):
        checks[name] += 1
        if got != want:
            bad.append({"vp_id": vp, "칸": name, "가상": got, "원본": want})

    for p in pts:
        r, R = rows.loc[p.source_id], p.recs
        cmp("나이", R["patient.age"].value, int(r["gdc_age_at_diagnosis"]), p.vp_id)
        cmp("ER 판정", R["receptors.er_percent"].value["result"], RESULT.get(r["gdc_er_status_by_ihc"]), p.vp_id)
        cmp("PR 판정", R["receptors.pr_percent"].value["result"], RESULT.get(r["gdc_pr_status_by_ihc"]), p.vp_id)
        if R["receptors.her2_ihc"].status == "present" and "score" in R["receptors.her2_ihc"].value \
                and R["receptors.her2_ihc"].origin != "synthetic":             # Y-07 합성 점수는 V3에서 본다
            # 점수 없이 Equivocal이면 2+ (ASCO/CAP 정의, mini 변환기와 같은 약속)
            raw = str(r["gdc_her2_ihc_score"])
            want = "2+" if raw == "[Not Available]" and r["gdc_her2_status_by_ihc"] == "Equivocal" else raw
            cmp("HER2 IHC 점수", R["receptors.her2_ihc"].value["score"], want, p.vp_id)
        t = R["stage.ptnm"].value
        x = lambda v: "not_assessed" if v in ("TX", "NX", "MX") else v      # noqa: E731 — mini 정규값 (X → not_assessed)
        cmp("pT", t["t"], re.sub(r"^(T[23])[a-d]$", r"\1", x(r["gdc_ajcc_tumor_pathologic_pt"])), p.vp_id)   # D-11
        sc = nottingham().get(p.source_id)                                  # M-05: 판독 세 점수 합 → 등급
        if sc:
            cmp("grade (Nottingham)", R["diagnosis.grade"].value, {3: 1, 4: 1, 5: 1, 6: 2, 7: 2}.get(sum(sc), 3), p.vp_id)
        if R["stage.ptnm"].origin == "real":                                 # D-05로 바꾼 값은 V2가 본다
            cmp("pM", t["m"], x(r["gdc_ajcc_metastasis_pathologic_pm"]), p.vp_id)
        if r["gdc_ajcc_pathologic_tumor_stage"] in STAGE:
            cmp("병기군", R["stage.group"].value, STAGE[r["gdc_ajcc_pathologic_tumor_stage"]], p.vp_id)
    return {"checks": dict(checks), "mismatch": bad, "pass": not bad}


def v2(pts: list[Patient], df: pd.DataFrame) -> dict:
    """계산: 날짜·병기 범주·D-05 pN·pM 정규값을 다른 식으로 다시 계산."""
    rows = df.set_index("patient_id")
    bad = []
    for p in pts:
        t, r = p.recs["stage.ptnm"].value, rows.loc[p.source_id]
        n_raw, m_raw = str(r["gdc_ajcc_nodes_pathologic_pn"]), str(r["gdc_ajcc_metastasis_pathologic_pm"])
        if t["n"] != n_raw.split("(")[0].split(" ")[0].strip():          # 'N0 (i-)', 'N0(i+)' → N0
            bad.append((p.vp_id, f"pN {t['n']} != {n_raw}"))
        if t["m"] != ("M1" if "M1" in m_raw else "M0"):                     # 'cM0 (i+)' → M0
            bad.append((p.vp_id, f"pM {t['m']} != {m_raw}"))
        dxd = dt.date.fromisoformat(p.recs["diagnosis.diagnosis_date"].value)
        if not dt.date(2022, 1, 3) <= dxd <= dt.date(2024, 12, 30):
            bad.append((p.vp_id, "진단일 범위"))
        if not DAY_PATH <= p.index_day <= DAY_INDEX:                     # D-10
            bad.append((p.vp_id, "판정 기준일"))
        g = p.recs["stage.group"].value
        want = "locally_advanced" if g.startswith("III") else "early"
        if p.recs["stage.disease_extent"].value != want:
            bad.append((p.vp_id, f"병기 범주 {g}"))
    return {"n": len(pts), "mismatch": bad, "pass": not bad}


def folds(ids: list[str], frac: float, seed: str) -> list[set[str]]:
    """가리는 묶음: 한 번에 frac만큼 가리고, 묶음을 돌려 모든 환자를 한 번씩 가린다 (교차 맞춤)."""
    ids = sorted(ids)
    random.Random(seed).shuffle(ids)
    k = max(2, round(1 / frac))
    return [set(ids[i::k]) for i in range(k)]


def v3(pss: dict[str, dict]) -> dict:
    """분포: ② 근거 칸은 가려 놓고 다시 만들기 (838명 전체 실제 값으로).

    2026-11-09 첫 실행은 30%를 한 번만 가렸는데, 폐경 이행기를 가린 묶음에서 빼는 버그가 있었고 구간 비교는
    표본(73~95명)이 작아 흔들렸다. 기준(5%p)은 그대로 두고, 묶음을 돌려 모든 환자를 한 번씩 가리는 방식으로 고쳤다.
    """
    frac, lim = float(thresholds()["v3.mask_fraction"]), float(thresholds()["v3.max_diff_pp"])
    cats = ("premenopausal", "postmenopausal", "perimenopausal")
    have = [pid for pid, ps in pss.items() if entry(ps, "patient.menopausal_status").get("value") in cats]
    real, gen = collections.Counter(), collections.Counter()
    for masked in folds(have, frac, "meno"):
        ctx = Context(pss, masked=masked)
        for pid in masked:
            real[entry(pss[pid], "patient.menopausal_status")["value"]] += 1
            gen[synth_meno("mask:" + pid, entry(pss[pid], "patient.age")["value"], ctx)] += 1
    n = len(have)
    meno = {k: (round(real[k] / n * 100, 1), round(gen[k] / n * 100, 1)) for k in cats}
    out = {f"폐경 (실제 %, 다시 만든 %, {n}명)": meno,
           "폐경 최대 차이 %p": max(abs(a - b) for a, b in meno.values())}

    for path in ("receptors.er_percent", "receptors.pr_percent"):
        lo_b, hi_b = map(int, thresholds()[f"boundary.{path.split('.')[1]}"].split("-"))
        have = [pid for pid, ps in pss.items()
                if entry(ps, path).get("value", {}).get("result") == "positive" and "range" in entry(ps, path)["value"]
                and not (entry(ps, path)["value"]["range"][1] >= lo_b and entry(ps, path)["value"]["range"][0] <= hi_b)]
        real, gen = collections.Counter(), collections.Counter()
        for masked in folds(have, frac, path):
            ctx = Context(pss, masked=masked)
            for pid in masked:
                real[tuple(entry(pss[pid], path)["value"]["range"])] += 1
                gen[tuple(synth_range("mask:" + pid, path, "positive", ctx))] += 1
        diff = max(abs(real[k] - gen[k]) / len(have) * 100 for k in set(real) | set(gen))
        out[f"{path} 구간 최대 차이 %p (경계 밖 양성 {len(have)}명)"] = round(diff, 1)
    out["기준 %p"] = lim
    out["pass"] = all(v <= lim for k, v in out.items() if "차이" in k)
    return out


def v4(pts: list[Patient]) -> dict:
    """관계: 합성 Ki-67·grade가 실제 아형(PAM50, 정답 표)과 맞는 방향인지."""
    hi = collections.defaultdict(list)
    g3 = collections.defaultdict(list)
    for p in pts:
        k = p.recs["proliferation.ki67_percent"].value["percent"] >= 20
        hi[p.truth.get("pam50") or "?"].append(k)
        g3[p.truth["subtype_rule"]].append(p.recs["diagnosis.grade"].value == 3)
    rate = {k: round(sum(v) / len(v), 2) for k, v in hi.items() if v}
    grade3 = {k: round(sum(v) / len(v), 2) for k, v in g3.items() if v}
    ok = rate.get("BRCA_LumA", 0) < rate.get("BRCA_LumB", 1) and grade3.get("HR+/HER2-", 0) < grade3.get("TNBC", 1)
    return {"Ki-67 높음 비율 (PAM50별)": rate, "grade 3 비율 (아형별)": grade3,
            "기대": "LumA < LumB, HR+/HER2- < TNBC", "pass": ok}


def v6(slides: list[dict]) -> dict:
    """이미지 좌표: 썸네일이 있고 downsample·크기가 양수."""
    bad = []
    for s in slides:
        if not Path(s["thumb_abs"]).exists():
            bad.append((s["slide_id"], "썸네일 없음"))
        if not (float(s["downsample"]) > 0 and float(s["thumb_w"]) > 0 and float(s["thumb_h"]) > 0):
            bad.append((s["slide_id"], "크기·배율"))
    return {"n": len(slides), "mismatch": bad, "pass": not bad}


THUMBS = FINAL / "data" / "tcga" / "qc" / "thumbs"
