"""TCGA ② 재발 갈래: 실제 원격 재발이 있는 환자를 고식 차수를 정하는 외래 시점 차트로 만든다 (투약 기록 포함).

- 진단 시 값(병리·수용체·변이·합성 칸)은 TCGA ① 생성(tcga.build_all)을 그대로 쓴다
- 장면 (D-R1): 실제로 다음 치료를 정한 시점. 두 번째 고식 요법이 있으면 그 시작일, 없으면 첫 고식 요법 시작일.
  판정 기준일 = 그 차수 약의 실제 시작일. 그 전에 시작한 투약만 차트에 쓰고, 그날부터의 투약은
  truth.csv의 실제 처방 기록(참고용, 정답 아님)으로
- 기준일에 아직 투약 중인 줄은 "현재 투약 중"으로 쓰고 반응은 쓰지 않는다 (반응 판정이 기준일 뒤일 수 있음)
- 투약은 처방된 그대로 (mini 변환기의 treatment_history: 약, 구분, 시작·종료일, 주기, 반응)
- 중단 사유는 실제 값으로만 정한다 (D-R2). 근거가 없으면 비운다 → 차수는 mini lines.annotate가 계산

실행 (team_project 폴더, team_project 환경): python -m src.virtual_hospital.scripts.tcga_recur
결과: out/tcga_recur/ (patients·fields·treatments·truth CSV, charts/), reports/tcga_recur*.csv·md
"""
from __future__ import annotations

import collections
import json
import shutil

from src.virtual_hospital.scripts import gates, render
from src.virtual_hospital.scripts.common import MINI, OUT, REPORTS, Rec, read_csv, write_csv
from src.virtual_hospital.scripts.tcga import build_all, entry

ADJ_ENDOCRINE_DONE = 1640                      # D-R2: 보조 내분비를 약 4.5년(1,640일) 이상 쓰면 완료
ADJ_ENDOCRINE_FULL = 1825                      # D-R5: 보조 내분비 5년
SWITCH_GAP = 28                                # D-R2: AC 끝나고 28일 안에 탁산 → 계획된 변경 (mini rules.py 차수 규칙 5와 같음)
RECUR_GAP = 31                                 # D-R2: 전이일 31일 전 이후에 끝났거나 계속 중이면 재발로 중단 (진행)
STANDARD_INTERVALS = (7, 14, 21, 28)           # 차트 주기 표기 (weekly·q2w·q3w·q4w)
OUT_DIR = OUT / "tcga_recur"
SCENE_KEY = {"endocrine": "endocrine_line", "chemo": "chemo_line"}   # D-R1: mini treatment_history 칸
KIND_KO = {"endocrine": "내분비", "chemo": "항암"}


def classes() -> dict[str, tuple[str, str]]:
    """성분명 → (drug_class, drug_subclass), mini drug_classes.csv."""
    return {r["generic_name"]: (r["drug_class"], r["drug_subclass"])
            for r in read_csv(MINI / "data" / "dictionaries" / "drug_classes.csv")}


def merge(items: list[dict]) -> list[dict]:
    """D-R4: TCGA는 병용 약을 약마다 한 줄로 적는다. 구분·시작일·종료일이 같은 줄은 한 요법(예: AC)으로 묶는다.
    주기·반응은 모든 약이 같을 때만 남긴다 (다르면 비움)."""
    groups: dict[tuple, list[dict]] = {}
    for t in items:
        groups.setdefault((t["setting"], t.get("start_day"), t.get("end_day")), []).append(t)
    out = []
    for g in groups.values():
        same = lambda k: g[0].get(k) if all(x.get(k) == g[0].get(k) for x in g) else None  # noqa: E731
        out.append({**g[0], "drugs": [d for x in g for d in x["drugs"]], "cycles": same("cycles"),
                    "best_response": same("best_response")})
    return sorted(out, key=lambda t: (t.get("start_day") is None, t.get("start_day") or 0))


def stop_reason(i: int, items: list[dict], mday: int, cls: dict) -> tuple[str | None, str]:
    """D-R2: (중단 사유, 근거). 실제 값으로만 정하고, 근거가 없으면 (None, '근거 없음')."""
    t = items[i]
    sub = lambda u: {cls.get(d, ("", ""))[1] for d in u["drugs"]}  # noqa: E731
    kinds = {cls.get(d, ("", ""))[0] for d in t["drugs"]}
    s, e = t.get("start_day"), t.get("end_day")
    if t.get("best_response") == "PD":
        return "progression", "실제 반응 PD"
    if t["setting"] != "palliative" and s is not None and s < mday and e is not None and e >= mday - RECUR_GAP:
        return "progression", (f"전이 {mday - e}일 전까지 투약 (재발로 중단)" if e < mday
                               else f"전이 {e - mday}일 뒤까지 투약 (재발로 중단)")
    if t["setting"] == "adjuvant" and kinds == {"Hormone Therapy"} and s is not None and e is not None \
            and e - s >= ADJ_ENDOCRINE_DONE:
        return "completed", f"보조 내분비 {e - s}일 복용"
    if t["setting"] in ("adjuvant", "neoadjuvant") and "anthracycline" in sub(t) and e is not None:
        nxt = [u for u in items[i + 1:] if u["setting"] == t["setting"] and u.get("start_day") is not None
               and u["start_day"] > s and 0 <= u["start_day"] - e <= SWITCH_GAP and "taxane" in sub(u)]
        if nxt:
            return "planned_switch", f"안트라사이클린 끝나고 {nxt[0]['start_day'] - e}일 뒤 탁산 시작 (순차 요법)"
    return None, "근거 없음 (비움)"


def treatments(ps: dict, index_day: int, mday: int, cls: dict) -> tuple[list[dict], list[dict], list[str]]:
    """(차트에 쓸 요법, 정답 표로 가는 뒤 요법, 문제)."""
    items = merge(ps["fields"].get("treatment_history") or [])
    for t in items:
        # D-R5: 종료일 없는 보조 내분비약은 끊었다는 기록이 없으므로 계속 투약으로 본다. 시작부터 전이까지 5년(1,825일)
        # 미만이면 전이일까지 투약 (내분비 중 전이, 2026-11-18 사용자 결정). 5년 이상이면 정하지 않는다
        if t["setting"] == "adjuvant" and t.get("end_day") is None and t.get("start_day") is not None \
                and {cls.get(d, ("", ""))[0] for d in t["drugs"]} == {"Hormone Therapy"} \
                and 0 <= mday - t["start_day"] < ADJ_ENDOCRINE_FULL:
            t["end_day"], t["end_basis"] = mday, f"종료일 없음 → 전이일까지 계속 투약으로 봄 ({mday - t['start_day']}일 < 5년)"
    anthra = ps["fields"]["anthracycline_drug_dose"]["drugs"]
    shown, later, problems = [], [], []
    for i, t in enumerate(items):
        if t.get("start_day") is None:
            problems.append(f"투약 시작일 없음: {'+'.join(t['drugs'])}")
            continue
        if t["start_day"] >= index_day:
            later.append(t)
            continue
        cyc = t.get("cycles")
        if cyc and cyc.get("basis") != "recorded":
            cyc = None                                           # 추정 주기 수는 차트에 쓰지 않는다
        elif cyc and (cyc.get("interval_basis") != "derived" or cyc.get("interval_days") not in STANDARD_INTERVALS):
            cyc = {**cyc, "interval_days": None, "interval_basis": None}   # 약 표준 간격(standard)은 쓰지 않는다
        elif cyc:
            cyc = {**cyc, "interval_basis": "recorded"}          # 실제 날짜로 계산한 간격을 차트에 적었으므로 차트 기준 recorded
        doses = {}
        for g in t["drugs"]:
            if cls.get(g, ("", ""))[1] != "anthracycline":
                continue
            a = [x for x in anthra if x["drug"] == g]
            if len(a) != 1 or not isinstance(a[0]["dose_per_admin"], dict):
                problems.append(f"{g} 1회 용량 없음 또는 여러 줄: mini가 용량 없는 안트라사이클린 줄을 schema 위반으로 냄")
                continue
            doses[g] = a[0]["dose_per_admin"]
        reason, why = stop_reason(i, items, mday, cls)
        ongoing = t.get("end_day") is not None and t["end_day"] > index_day
        resp = t.get("best_response") if t.get("best_response") in ("CR", "PR", "SD", "PD") and not ongoing else None
        shown.append({"drugs": t["drugs"], "setting": t["setting"], "start_day": t["start_day"],
                      "end_day": None if ongoing else t.get("end_day"), "ongoing": ongoing, "cycles": cyc,
                      "best_response": resp, "stop_reason": None if ongoing else reason, "doses": doses,
                      # D-R3: mini 읽기 규칙과 같게 — 진행이면 투약 기간 안 전이일, 없으면 종료일
                      "progression_day": None if ongoing or reason != "progression" else
                      mday if t["start_day"] <= mday <= (t.get("end_day") if t.get("end_day") is not None else mday) else t.get("end_day"),
                      "adjuvant_endocrine": t["setting"] == "adjuvant"
                      and any(cls.get(g, ("", ""))[0] == "Hormone Therapy" for g in t["drugs"]),
                      "stop_basis": "판정 기준일에 투약 중" if ongoing else
                      why + (f"; D-R5 {t['end_basis']}" if t.get("end_basis") else "")})
    return shown, later, problems


def main() -> int:
    pts, _, pss, _ = build_all()
    cls, env = classes(), gates.envelope(pss)
    if (OUT_DIR / "charts").exists():
        shutil.rmtree(OUT_DIR / "charts")
    kept, dropped, rows_t = [], [], []
    for p in pts:
        ps0 = pss[p.source_id]
        rec = entry(ps0, "recurrence.status")
        if rec.get("value") != "distant":
            continue
        mday = entry(ps0, "recurrence.metastasis_day").get("value")
        rday = entry(ps0, "recurrence.recurrence_day").get("value")
        sites = entry(ps0, "recurrence.metastatic_sites").get("value") or []
        problems = list(p.problems)
        if mday is None:
            problems.append("원격 전이일 없음")
        elif rday not in (None, mday):
            problems.append(f"국소 재발({rday}일)이 원격 전이({mday}일)보다 먼저: 이 갈래에서 다루지 않음")
        if not sites or any(s not in render.SITE_KO for s in sites):
            problems.append(f"전이 부위를 차트로 쓸 수 없음: {sites}")
        if problems:
            dropped.append({"vp_id": p.vp_id, "reason": "; ".join(problems)})
            continue
        # D-R1: 실제로 다음 치료를 정한 시점 (2026-11-18 사용자 결정 A). mini A가 붙인 (내분비 차수, 항암 차수) 번호 조합이
        # 바뀌는 곳이 요법 경계다. 두 번째 고식 요법이 있으면 그 시작일, 없으면 첫 고식 요법 시작일이 기준일.
        # 장면 종류·차수 = 그 요법에서 새로 올라간 종류와 그 차수 (예: 내분비 1차 뒤 capecitabine → 고식 항암 1차 결정)
        hist = sorted((t for t in ps0["fields"]["treatment_history"] if t.get("start_day") is not None
                       and (t.get("endocrine_line") or t.get("chemo_line"))), key=lambda t: t["start_day"])
        groups: list[tuple] = []
        for t in hist:
            tag = (t.get("endocrine_line"), t.get("chemo_line"))
            if tag not in [g[0] for g in groups]:
                groups.append((tag, t["start_day"]))
        if not groups:
            dropped.append({"vp_id": p.vp_id, "reason": "D-R1 고식 투약 기록 없음: 결정 장면을 만들 수 없음"})
            continue
        # 두 번째 요법 장면을 만들 수 없으면 (그 전 투약에 차트로 쓸 수 없는 줄) 첫 요법 장면으로 물러난다
        options = ([(groups[1], groups[0][0])] if len(groups) > 1 else []) + [(groups[0], (None, None))]
        for (tag, start), prev in options:
            tried = treatments(ps0, start, mday, cls)
            if not tried[2]:
                break
        kind = "endocrine" if tag[0] and tag[0] != prev[0] else "chemo"
        key = SCENE_KEY[kind]
        k = tag[0] if kind == "endocrine" else tag[1]
        p.branch, p.scene_line, p.scene_kind = "TCGA_recur", k, kind
        p.scene_prev = "·".join(f"{KIND_KO[x]} {n}차" for x, n in zip(SCENE_KEY, prev) if n) or None
        p.index_day = start
        p.recs.pop("recurrence.status", None)
        p.add(Rec("recurrence.status", "present", "distant", "real", rule_id="M-01", source_column="recurrence_status"))
        p.add(Rec("recurrence.metastatic_sites", "present", sites, "real", rule_id="M-01", source_column="nte_sites"))
        p.add(Rec("recurrence.metastasis_day", "present", mday, "real", rule_id="M-01", source_column="metastasis_dx_days"))
        p.add(Rec("recurrence.recurrence_day", "present", mday, "real", rule_id="M-01", source_column="metastasis_dx_days"))
        p.add(Rec("recurrence.recurrence_date", "present", render.Chart(p.vp_id, p.dx_date, 0).on(mday), "derived", "①",
                  "D-01", note="가짜 진단일 + 실제 전이 일수"))
        p.treatments, later, tproblems = tried
        ends = [t for t in p.treatments if t["adjuvant_endocrine"] and t["end_day"] is not None and not t["ongoing"]]
        if ends:
            e = max(t["end_day"] for t in ends)
            p.add(Rec("recurrence.adjuvant_endocrine_end_date", "present", render.Chart(p.vp_id, p.dx_date, 0).on(e),
                      "derived", "①", "D-R2", source_column="drug_end_days", note="보조 내분비 투약 줄의 실제 종료일"))
        if tproblems:
            dropped.append({"vp_id": p.vp_id, "reason": "; ".join(tproblems)})
            continue
        try:
            text, ps, errs = render.chart(p)
        except render.RenderError as ex:
            dropped.append({"vp_id": p.vp_id, "reason": f"G2 표기 없음: {ex}"})
            continue
        res = gates.run(p, ps, errs, env, text)
        seen = [t.get(key) for t in ps["fields"]["treatment_history"] if t.get(key)]
        if (max(seen) if seen else 0) + 1 != k:                       # 차트만 읽은 mini 그 종류 차수 + 1 = 장면 차수
            res["failed"] = res["failed"] + ["D-R1"]
            res["D-R1"] = [f"차트로 센 마지막 고식 {KIND_KO[kind]} 차수 {max(seen) if seen else 0} + 1 != 장면 {k}차"]
        if res["failed"]:
            dropped.append({"vp_id": p.vp_id, "reason": "; ".join(f"{k}: {res[k][0]}" for k in res["failed"])})
            continue
        d = OUT_DIR / "charts" / p.vp_id
        (d / "expected").mkdir(parents=True, exist_ok=True)
        (d / "chart.txt").write_text(text, encoding="utf-8", newline="\n")
        (d / "expected" / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2) + "\n",
                                                           encoding="utf-8", newline="\n")
        (d / "expected" / "biomarker_record.json").write_text(
            json.dumps(res["biomarker"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        lines = {(t.get("start_day"), tuple(t["drugs"])): t for t in ps["fields"]["treatment_history"]}
        for t in p.treatments:
            g = lines.get((t["start_day"], tuple(t["drugs"])), {})
            rows_t.append({"vp_id": p.vp_id, "drugs": "+".join(t["drugs"]), "setting": t["setting"],
                           "start_day": t["start_day"], "end_day": t["end_day"], "stop_reason": t["stop_reason"] or "",
                           "stop_basis": t["stop_basis"], "best_response": t["best_response"] or "",
                           "endocrine_line (mini)": g.get("endocrine_line"), "chemo_line (mini)": g.get("chemo_line"),
                           "rule_id": "M-01, D-R2"})
        p.truth["scene"] = f"고식 {KIND_KO[kind]} {k}차 결정"
        p.truth["actual_prescriptions_from_index_reference"] = " | ".join(
            f"{'+'.join(t['drugs'])} d{t['start_day']}" + "".join(
                f" (mini {KIND_KO[x]} {t[SCENE_KEY[x]]}차)" for x in SCENE_KEY if t.get(SCENE_KEY[x])) for t in later)
        kept.append((p, ps))

    write_csv(OUT_DIR / "patients.csv", [{"vp_id": p.vp_id, "branch": p.branch, "dx_date": p.dx_date,
                                          "index_day": p.index_day, "scene_kind": p.scene_kind, "scene_line": p.scene_line,
                                          "metastasis_day": p.recs["recurrence.metastasis_day"].value,
                                          "sex": "F", "age": p.recs["patient.age"].value} for p, _ in kept])
    write_csv(OUT_DIR / "fields.csv", [r.row(p.vp_id) for p, _ in kept for r in p.recs.values()])
    write_csv(OUT_DIR / "treatments.csv", rows_t)
    write_csv(OUT_DIR / "truth.csv", [{"vp_id": p.vp_id, "항목": k, "값": "" if v is None else v}
                                      for p, _ in kept for k, v in p.truth.items()])
    write_csv(REPORTS / "tcga_recur_excluded.csv", dropped, ["vp_id", "reason"])
    lines = collections.Counter((ps["fields"].get("at_index") or {}).get("line") for _, ps in kept)
    summary = {"세트": len(kept), "장면": dict(collections.Counter(f"고식 {KIND_KO[p.scene_kind]} {p.scene_line}차 결정" for p, _ in kept)),
               "뺀 환자": len(dropped), "요법 줄": len(rows_t),
               "중단 사유": dict(collections.Counter(r["stop_reason"] or "(비움)" for r in rows_t)),
               "중단 사유 근거": dict(collections.Counter(r["stop_basis"].split(" (")[0].split(" ")[0] for r in rows_t)),
               "뺀 이유": dict(collections.Counter(r["reason"].split(":")[0][:20] for r in dropped))}
    (REPORTS / "tcga_recur.md").write_text("# TCGA ② 재발 갈래 — 생성 보고\n\n```\n" +
                                           json.dumps(summary, ensure_ascii=False, indent=1) + "\n```\n",
                                           encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))
    for r in dropped:
        print("뺌", r["vp_id"], r["reason"][:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
