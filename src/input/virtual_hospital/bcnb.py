"""BCNB (수술 전, 생검 직후) 갈래: 고르기 → 옮기기 → 계산 → 합성 → 관문 → chart.txt → 검증.

BCNB 약관(원본·수정본 재배포 금지) 때문에 산출물은 모두 local/bcnb/, 보고는 local/reports/에 쓴다.
실행 (virtual_hospital 폴더에서, mini의 team_project 환경으로): python -m src.input.virtual_hospital.bcnb
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import shutil

import pandas as pd

from src.input.virtual_hospital import gates
from src.input.virtual_hospital.common import CREATED_AT, LOCAL, PROJECT, ROOT, Patient, Rec, mini_on_path, ref, rng, write_csv
from src.input.virtual_hospital.render import allred_word
from src.input.virtual_hospital.tcga import Context, allred_is_choices, allred_ps, dx_date, load as load_tcga, pick, pick_is, synth_ecog, synth_meno

# BCNB 원자료 (37GB, 약관상 git 제외): data/virtual_hospital/local/BCNB/BCNB/. 없으면 예전 위치 ../virtual_hospital/data/BCNB/BCNB
BCNB = next((p for p in (LOCAL / "BCNB" / "BCNB", PROJECT / "virtual_hospital" / "data" / "BCNB" / "BCNB") if p.exists()),
            LOCAL / "BCNB" / "BCNB")
OUT = LOCAL / "bcnb"
REPORT = LOCAL / "reports"
# 모듈 3 정제 규칙(연구 계획 6-2-1)에서 ER·PR 예측과 아형 평가에서 뺀 환자: ER−/PR+ 등 모순 10명 + Ki-67 80% Luminal A 1명
EXCLUDE_M3 = {49, 162, 420, 449, 623, 953, 199, 619, 842, 844, 174}
HISTOLOGY = {"Invasive ductal carcinoma": ("IDC", "Invasive ductal carcinoma, NST"),          # VC core_path 표기
             "Invasive lobular carcinoma": ("ILC", "Infiltrating Lobular Carcinoma")}         # field_vocab tcga 표기
DAY_PATH, DAY_US, DAY_INDEX = 4, 5, 14                     # D-B5: 생검 0일, 보고 4일, 초음파 5일, 초진 14일
STAGE = {("T1", "N0"): "IA", ("T1", "N1"): "IIA", ("T2", "N0"): "IIA", ("T2", "N1"): "IIB",
         ("T3", "N0"): "IIB", ("T3", "N1"): "IIIA"}         # AJCC 8판 해부학 병기 (M0)


def ct(size_cm: float) -> str:
    """D-B1: 종양 크기 → cT (AJCC 8판)."""
    mm = size_cm * 10
    return "T1a" if mm <= 5 else "T1b" if mm <= 10 else "T1c" if mm <= 20 else "T2" if mm <= 50 else "T3"


def ki67(raw) -> tuple[dict, str]:
    """D-B4: (값, 차트 표기). 숫자 0.3 → 30%, '＞60%' → 61-100% (mini가 '>'를 읽지 못함), '＜5%' → <5%."""
    try:
        x = round(float(raw) * 100, 1)
        x = int(x) if x == int(x) else x
        return {"percent": x}, f"{x}%"
    except (TypeError, ValueError):
        s = str(raw).replace("＞", ">").replace("＜", "<").strip()
    m = re.fullmatch(r"<(\d+)%", s)
    if m:
        hi = int(m.group(1))
        return {"range": [0, 0 if hi <= 1 else hi - 1]}, f"<{hi}%"
    m = re.fullmatch(r">(\d+)%", s)
    if m:
        lo = int(m.group(1)) + 1
        return {"range": [lo, 100]}, f"{lo}-100%"
    m = re.fullmatch(r"(\d+)-(\d+)%", s)
    if m:
        return {"range": [int(m.group(1)), int(m.group(2))]}, f"{m.group(1)}-{m.group(2)}%"
    raise ValueError(f"Ki67 표기를 읽을 수 없음: {raw}")


def synth_cn(vp: str, aln: str) -> str:
    """Y-B2: 수술 전 초음파 cN. 실제 림프절 결과(정답)와 초음파 민감도·특이도(references R-04)로 정한다."""
    sens, spec = (float(x) for x in ref("R-04", "겨드랑이 초음파").split("/"))
    x = rng(vp, "Y-B2").random()
    if aln == "N0":
        return "N0" if x < spec else "N1"
    return "N1" if x < sens else "N0"


def build(vp: str, row: pd.Series, ctx: Context) -> Patient:
    pid = int(row["Patient ID"])
    dxd = dx_date(vp)
    on = lambda d: (dt.date.fromisoformat(dxd) + dt.timedelta(days=d)).isoformat()   # noqa: E731
    p = Patient(vp, str(pid), "BCNB_preop", "", dxd, DAY_INDEX, side=rng(vp, "D-04").choice(["좌측", "우측"]))
    age = int(row["Age(years)"])
    hist = HISTOLOGY[row["Tumour Type"]][0]
    p.add(Rec("patient.gender", "present", "FEMALE", "synthetic", "⑤", "Y-B3", note="BCNB에 성별 열 없음"))
    p.add(Rec("patient.age", "present", age, "real", rule_id="M-B1", source_column="Age(years)"))
    p.add(Rec("diagnosis.histology", "present", hist, "real", rule_id="M-B1", source_column="Tumour Type"))
    g = row["Histological grading"]
    p.add(Rec("diagnosis.grade", "present", int(g), "real", rule_id="M-B1", source_column="Histological grading")
          if pd.notna(g) else Rec("diagnosis.grade", "not_recorded", origin="real", rule_id="M-B1",
                                  source_column="Histological grading", note="BCNB 결측 (합성하지 않음)"))
    obs = dxd
    for path, col in (("receptors.er_percent", "ER"), ("receptors.pr_percent", "PR")):
        # Y-B1: 판정만 실제. 양성의 비율 점수(PS)는 TCGA 같은 판정 환자의 실제 구간 → PS 분포에서, 강도 점수는 Y-06
        res = "positive" if row[col] == "Positive" else "negative"
        if res == "positive":
            ps = allred_ps(list(pick(ctx.ranges[(path, "positive")], rng(vp, "Y-B1" + col))))
        else:
            ps = 0
        is_, _ = pick_is(ctx, path, res, allred_is_choices(path, res, ps), rng(vp, "Y-06" + path))
        p.add(Rec(path, "present", {"allred": {"total": ps + is_, "ps": ps, "is": is_}, "result": res}, "synthetic",
                  "②", "Y-B1", source_column=col, observed_date=obs, specimen="primary",
                  note="판정은 실제, PS는 TCGA 같은 판정 실제 구간 분포에서, IS는 Y-06"))
    score = str(row["HER2 Expression"])
    p.add(Rec("receptors.her2_ihc", "present", {"score": score}, "real", rule_id="M-B1",
              source_column="HER2 Expression", observed_date=obs, specimen="primary"))
    if score == "2+":
        amp = "amplified" if row["HER2"] == "Positive" else "not_amplified"
        p.add(Rec("receptors.her2_ish", "present", {"result": amp, "method": "unknown"}, "derived", "①", "D-B2",
                  source_column="HER2", observed_date=obs, specimen="primary"))
    else:
        p.add(Rec("receptors.her2_ish", "not_recorded", origin="derived", rule_id="D-B2"))
    k, _ = ki67(row["Ki67"])
    p.add(Rec("proliferation.ki67_percent", "present", k, "real" if "percent" in k else "derived",
              "" if "percent" in k else "①", "D-B4", source_column="Ki67", observed_date=obs, specimen="primary"))
    size_mm = round(float(row["Tumour Size(cm)"]) * 10, 1)
    size_mm = int(size_mm) if size_mm == int(size_mm) else size_mm
    p.add(Rec("stage.clinical_size_mm", "present", size_mm, "real", rule_id="M-B1", source_column="Tumour Size(cm)",
              observed_date=on(DAY_US)))
    t = ct(float(row["Tumour Size(cm)"]))
    n = synth_cn(vp, row["ALN status"])
    group = STAGE[(t[:2], n)]
    p.add(Rec("stage.ctnm", "present", {"t": t, "n": n, "m": "M0", "edition": None}, "derived", "①",
              "D-B3", observed_date=dxd, note="T는 크기(D-B1), N은 초음파 합성(Y-B2), M0는 조기 유방암 코호트"))
    p.add(Rec("stage.group", "present", group, "derived", "①", "D-B3"))
    p.add(Rec("stage.disease_extent", "present", "locally_advanced" if group.startswith("III") else "early",
              "derived", "①", "D-B3"))
    p.add(Rec("stage.metastatic_sites", "present", "[Not Applicable]", "derived", "①", "D-B3"))
    p.add(Rec("stage.operable", "present", "yes", "derived", "①", "D-B6", source_column="Surgical",
              note=f"실제로 수술받음 ({row['Surgical']}) → 수술 전 차트에 수술 가능"))
    p.add(Rec("patient.menopausal_status", "present", synth_meno(vp, age, ctx), "synthetic", "②", "Y-02",
              note="TCGA 나이대별 실제 비율"))
    p.add(Rec("patient.ecog", "present", synth_ecog(vp, age), "synthetic", "④", "Y-01", observed_date=on(DAY_INDEX)))
    p.add(Rec("diagnosis.diagnosis_date", "present", dxd, "derived", "⑤", "D-01"))
    p.truth = {"aln_status": row["ALN status"], "ln_metastases": int(row["Number of lymph node metastases"]),
               "surgical": row["Surgical"], "molecular_subtype": row["Molecular subtype"], "cN_synthetic": n,
               "her2_label": row["HER2"]}
    p.slides = [{"jpg": BCNB / "WSIs" / f"{pid}.jpg", "json": BCNB / "WSIs" / f"{pid}.json"}]
    return p


# ---------- R 표기 ----------
def chart(p: Patient):
    mini_on_path()
    from src.input.script.virtual.virtual_chart import Chart, F, check, kdate
    R = p.recs
    age = R["patient.age"].value
    c = Chart(p.vp_id, p.dx_date, DAY_INDEX, created_at=CREATED_AT)
    D = c.on
    side_en = {"좌측": "Lt.", "우측": "Rt."}[p.side]
    meno = R["patient.menopausal_status"].value
    ctnm, group, extent = R["stage.ctnm"].value, R["stage.group"].value, R["stage.disease_extent"].value

    # R-B1 초진 경과기록 (VC-0118·0121 형식)
    d = c.doc("progress_note", c.index_date)
    d.t(f"<외래 경과기록>   {kdate(c.index_date)}   유방외과\n").ident(age)
    d.t("병원: 가상대학교병원 유방외과   담당의: 이가상\n\n")
    d.t("S) 검진에서 발견된 유방 종괴로 의뢰됨.\n   폐경: ")
    d.put({"postmenopausal": "폐경 후", "premenopausal": "폐경 전",
           "perimenopausal": "Peri (6-12 months since last menstrual period)"}[meno],
          F("patient.menopausal_status", meno)).t("\n")
    ecog = R["patient.ecog"].value
    d.t("O) ").put(f"ECOG PS {ecog}", F("patient.ecog", ecog, observed_date=c.index_date)).t("\n\n")
    d.t(f"A) {side_en} breast cancer, ")
    d.put(f"{kdate(D(0))} core bx로 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0)))).t(", ")
    tn = f"c{ctnm['t']}{ctnm['n']}M0"
    d.put(f"{tn}, stage {group}", F("stage.ctnm", ctnm, observed_date=D(0), within=tn),
          F("stage.group", group, within=f"stage {group}"), F("stage.disease_extent", extent, within=f"stage {group}"),
          F("stage.metastatic_sites", "[Not Applicable]", within=tn)).t("\n   ")
    d.put("수술 가능 (operable)", F("stage.operable", "yes")).t("\n\n")          # D-B6
    d.t("P) 다학제 회의에서 수술 범위와 선행요법 여부 결정\n")

    # R-B2 중심 생검 병리 (core_path 형식)
    d = c.doc("pathology", D(DAY_PATH))
    d.t("SURGICAL PATHOLOGY REPORT\n").ident(age, F("patient.gender", "FEMALE"), F("patient.age", age), full=False)
    d.t(f"Received: {kdate(D(0))}   Reported: {kdate(D(DAY_PATH))}\nSpecimen: {p.side} 유방, 초음파 유도 중심 생검\n\n")
    hist = R["diagnosis.histology"].value
    d.t("DIAGNOSIS\n  ").put({"IDC": "Invasive ductal carcinoma, NST", "ILC": "Infiltrating Lobular Carcinoma"}[hist],
                             F("diagnosis.histology", hist))
    if R["diagnosis.grade"].status == "present":
        g = R["diagnosis.grade"].value
        d.t("\n  Histologic grade: ").put(f"Nottingham grade {g}", F("diagnosis.grade", g))
    d.t("\n\nIMMUNOHISTOCHEMISTRY\n  ")
    obs = D(0)
    for path, label in (("receptors.er_percent", "ER"), ("receptors.pr_percent", "PR")):
        v = R[path].value
        a = v["allred"]                                         # R-04 (TCGA와 같은 표기)
        d.put(f"{label} {allred_word(label, v['result'], a)} (Allred {a['total']}, {a['ps']}+{a['is']})",
              F(path, v, specimen="primary", observed_date=obs)).t("\n  ")
    d.put(f"HER2 (4B5): {R['receptors.her2_ihc'].value['score']}",
          F("receptors.her2_ihc", R["receptors.her2_ihc"].value, specimen="primary", observed_date=obs)).t("\n  ")
    _, ktext = ki67_text(p)
    d.put(f"Ki-67: {ktext}", F("proliferation.ki67_percent", R["proliferation.ki67_percent"].value,
                                specimen="primary", observed_date=obs))
    if R["receptors.her2_ish"].status == "present":
        v = R["receptors.her2_ish"].value
        d.t("\n  ").put(f"HER2 ISH: {'amplified' if v['result'] == 'amplified' else 'not amplified'}",
                        F("receptors.her2_ish", v, specimen="primary", observed_date=obs))
    d.t("\n\nPathologist: 박가상\n")

    # R-B3 유방 초음파 (image 형식)
    d = c.doc("radiology", D(DAY_US))
    d.t("[영상의학 판독]\n").ident(age, full=False)
    d.t(f"검사: Breast ultrasound   검사일: {kdate(D(DAY_US))}\n\nFindings:\n  ")
    mm = R["stage.clinical_size_mm"].value
    d.put(f"{p.side} 유방 {mm / 10:g} cm 종괴", F("stage.clinical_size_mm", mm, observed_date=D(DAY_US)))
    if ctnm["n"] == "N1":
        d.t(f", {p.side} 액와 림프절 피질 비후.\nConclusion:\n  ")
        d.image(f"{p.side} 액와 림프절 전이 의심", modality="ultrasound", date=D(DAY_US), sites=[], certainty="suspected")
    else:
        d.t(", 액와 림프절 특이 소견 없음.\nConclusion:\n  ")
        d.image("액와 림프절 전이 소견 없음", modality="ultrasound", date=D(DAY_US), sites=[], certainty="confirmed")
    d.t("\n")
    text, ps = c.build()
    return text, ps, check(text, ps)


def ki67_text(p: Patient) -> tuple[dict, str]:
    raw = p.truth["_ki67_raw"]
    return ki67(raw)


def slide_row(p: Patient) -> dict:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    s = p.slides[0]
    with Image.open(s["jpg"]) as im:
        w, h = im.size
    # I-02: 이미지 밖 다각형(잘려 나간 조직 조각의 주석)은 빼고 안쪽 다각형만 local 주석 파일에 남긴다
    polys = json.loads(s["json"].read_text(encoding="utf-8"))["positive"]
    keep = [q for q in polys if all(0 <= x <= w and 0 <= y <= h for x, y in q["vertices"])]
    ann = OUT / "images" / "annotations" / f"{p.vp_id}.json"
    ann.parent.mkdir(parents=True, exist_ok=True)
    ann.write_text(json.dumps({"positive": keep, "coordinate": "level 0 픽셀 (jpg 원본 크기)",
                               "dropped_outside": len(polys) - len(keep)}, ensure_ascii=False), encoding="utf-8")
    return {"slide_id": f"{p.vp_id}-S1", "vp_id": p.vp_id, "dataset": "BCNB", "specimen": "biopsy",
            "jpg": str(s["jpg"]), "annotation": str(ann), "width": w, "height": h,
            "mpp": "", "mpp_source": "BCNB jpg에 배율 정보 없음 (원 논문 확인 필요)",
            "annotation_polygons": len(keep), "annotation_dropped_outside": len(polys) - len(keep),
            "rule_id": "I-01, I-02"}


def main() -> int:
    df = pd.read_excel(BCNB / "patient-clinical-data.xlsx")
    _, tcga_pss = load_tcga()
    ctx, env = Context(tcga_pss), gates.envelope(tcga_pss)
    if (OUT / "charts").exists():
        shutil.rmtree(OUT / "charts")
    kept, dropped, gate_rows, handoff = [], [], [], []
    for i, (_, row) in enumerate(df.sort_values("Patient ID").iterrows()):
        pid = int(row["Patient ID"])
        vp = f"VH-B{i + 1:04d}"
        if pid in EXCLUDE_M3:
            dropped.append({"vp_id": vp, "rule": "S-B1", "reason": "S-B1 모듈 3 정제 제외 (ER·PR·아형 모순)"})
            continue
        if row["Tumour Type"] not in HISTOLOGY:
            dropped.append({"vp_id": vp, "rule": "S-B2", "reason": f"S-B2 조직형 '{row['Tumour Type']}' (알 수 없음)"})
            continue
        p = build(vp, row, ctx)
        p.truth["_ki67_raw"] = row["Ki67"]
        text, ps, errs = chart(p)
        p.truth.pop("_ki67_raw")
        res = gates.run(p, ps, errs, env, text)
        gate_rows.append({"vp_id": vp, **{k: " | ".join(res[k]) for k in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")}})
        if res["failed"]:
            reason = "; ".join(f"{k}: {res[k][0]}" for k in res["failed"])
            dropped.append({"vp_id": vp, "rule": res["failed"][0], "reason": reason})
            if res["real_cause"]:
                handoff.append({"vp_id": vp, "관문": ",".join(res["failed"]), "이유": reason, "원인": "real"})
            continue
        d = OUT / "charts" / vp
        (d / "expected").mkdir(parents=True, exist_ok=True)
        (d / "chart.txt").write_text(text, encoding="utf-8", newline="\n")
        (d / "expected" / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2) + "\n",
                                                           encoding="utf-8", newline="\n")
        (d / "expected" / "biomarker_record.json").write_text(
            json.dumps(res["biomarker"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        kept.append((p, row))

    pts = [p for p, _ in kept]
    write_csv(OUT / "patients.csv", [{"vp_id": p.vp_id, "branch": p.branch, "dx_date": p.dx_date,
                                      "index_day": p.index_day, "side": p.side, "sex": "F",
                                      "age": p.recs["patient.age"].value} for p in pts])
    write_csv(OUT / "fields.csv", [r.row(p.vp_id) for p in pts for r in p.recs.values()])
    write_csv(OUT / "truth.csv", [{"vp_id": p.vp_id, "항목": k, "값": v} for p in pts for k, v in p.truth.items()])
    slides = [slide_row(p) for p in pts]
    write_csv(OUT / "images" / "slides.csv", slides)
    # 주석 목록 (rules/image_tables.csv의 annotations 열 순서)
    write_csv(OUT / "images" / "annotations.csv",
              [{"ann_id": f"{s['vp_id']}-A1", "slide_id": s["slide_id"], "vp_id": s["vp_id"], "kind": "tumor_region",
                "origin": "real", "file": s["annotation"], "n_polygons": s["annotation_polygons"],
                "dropped_outside": s["annotation_dropped_outside"], "rule_id": "I-02"} for s in slides],
              ["ann_id", "slide_id", "vp_id", "kind", "origin", "file", "n_polygons", "dropped_outside", "rule_id"])
    write_csv(OUT / "source_map.csv", [{"vp_id": p.vp_id, "dataset": "BCNB", "source_id": p.source_id} for p in pts])
    write_csv(REPORT / "bcnb_excluded.csv", dropped, ["vp_id", "rule", "reason"])
    write_csv(REPORT / "bcnb_handoff_candidates.csv", handoff, ["vp_id", "관문", "이유", "원인"])
    write_csv(REPORT / "bcnb_gates.csv", gate_rows, ["vp_id", "G1", "G2", "G3", "G4", "G5", "G6", "G7"])
    v = verify(kept)
    report(pts, dropped, handoff, v)
    print(f"BCNB 세트 {len(pts)}명, 뺀 환자 {len(dropped)}명, 넘길 목록 {len(handoff)}건")
    for k, x in v.items():
        print(k, "통과" if x["pass"] else "실패")
    return 0 if all(x["pass"] for x in v.values()) else 1


# ---------- V 검증 ----------
def verify(kept) -> dict:
    bad1, bad2 = [], []
    checks = collections.Counter()
    for p, row in kept:
        R = p.recs

        def cmp(name, got, want):
            checks[name] += 1
            if got != want:
                bad1.append({"vp_id": p.vp_id, "칸": name, "가상": got, "원본": want})
        cmp("나이", R["patient.age"].value, int(row["Age(years)"]))
        cmp("ER 판정", R["receptors.er_percent"].value["result"], str(row["ER"]).lower())
        cmp("PR 판정", R["receptors.pr_percent"].value["result"], str(row["PR"]).lower())
        cmp("HER2 점수", R["receptors.her2_ihc"].value["score"], str(row["HER2 Expression"]))
        cmp("크기 mm", float(R["stage.clinical_size_mm"].value), round(float(row["Tumour Size(cm)"]) * 10, 1))
        if pd.notna(row["Histological grading"]):
            cmp("grade", R["diagnosis.grade"].value, int(row["Histological grading"]))
        # V2: 다른 식으로 다시 계산
        mm = float(row["Tumour Size(cm)"]) * 10
        want_t = next(t for lim, t in ((5, "T1a"), (10, "T1b"), (20, "T1c"), (50, "T2"), (1e9, "T3")) if mm <= lim)
        if R["stage.ctnm"].value["t"] != want_t:
            bad2.append((p.vp_id, "cT"))
        ish = R["receptors.her2_ish"]
        if (str(row["HER2 Expression"]) == "2+") != (ish.status == "present"):
            bad2.append((p.vp_id, "ISH 유무"))
        if ish.status == "present" and (ish.value["result"] == "amplified") != (row["HER2"] == "Positive"):
            bad2.append((p.vp_id, "ISH 판정"))
    pts = [p for p, _ in kept]
    # 초음파 cN 합성이 근거 민감도·특이도에 맞는지 (참고)
    pos = [p for p in pts if p.truth["aln_status"] != "N0"]
    neg = [p for p in pts if p.truth["aln_status"] == "N0"]
    sens = sum(p.truth["cN_synthetic"] == "N1" for p in pos) / max(1, len(pos))
    spec = sum(p.truth["cN_synthetic"] == "N0" for p in neg) / max(1, len(neg))
    want = [float(x) for x in ref("R-04", "겨드랑이 초음파").split("/")]
    v6 = [p.vp_id for p in pts if not p.slides[0]["jpg"].exists() or not p.slides[0]["json"].exists()]
    return {"V1 복사": {"checks": dict(checks), "mismatch": bad1, "pass": not bad1},
            "V2 계산": {"n": len(pts), "mismatch": bad2, "pass": not bad2},
            "V3 초음파 cN": {"민감도 (만든 / 근거)": (round(sens, 3), want[0]),
                           "특이도 (만든 / 근거)": (round(spec, 3), want[1]),
                           "pass": abs(sens - want[0]) <= 0.05 and abs(spec - want[1]) <= 0.05},
            "V6 이미지": {"n": len(pts), "파일 없음": v6,
                        "pass": not v6}}


def report(pts, dropped, handoff, v) -> None:
    by = collections.Counter(d["rule"] for d in dropped)
    origin = collections.Counter((r.origin, r.rule_id) for p in pts for r in p.recs.values() if r.status == "present")
    lines = ["# BCNB (수술 전) 가상환자 세트 — 생성 보고 (공개하지 않음)", "",
             "| 항목 | 수 |", "|---|---|", f"| 세트 (관문 통과) | {len(pts)} |"]
    lines += [f"| 뺀 환자: {k} | {n} |" for k, n in sorted(by.items())]
    lines += [f"| 넘길 목록 | {len(handoff)} |", "",
              "| origin | 규칙 | 칸 수 |", "|---|---|---|"]
    lines += [f"| {o} | {r} | {n} |" for (o, r), n in sorted(origin.items())]
    lines.append("")
    for k, x in v.items():
        lines += [f"## {k} — {'통과' if x['pass'] else '실패'}", "", "```",
                  json.dumps({kk: vv for kk, vv in x.items() if kk != "pass"}, ensure_ascii=False, indent=1,
                             default=str)[:3000], "```", ""]
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "bcnb_preop.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
