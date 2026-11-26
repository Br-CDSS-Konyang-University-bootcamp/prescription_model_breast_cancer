"""TCGA ① (수술 후) 가상환자 세트를 만든다: 고르기 → 옮기기 → 계산 → 합성 → 관문 → chart.txt → 검증.

실행 (virtual_hospital 폴더에서, mini의 team_project 환경으로):
    python -m src.virtual_hospital.scripts.build              # out/tcga/, reports/, local/source_map.csv
결과:
    out/tcga/patients.csv · fields.csv · truth.csv · images/slides.csv · charts/<vp>/chart.txt, expected/
    reports/tcga_postop.md (요약) · excluded.csv · handoff_candidates.csv · gates.csv
    local/source_map.csv (가상환자 번호 ↔ TCGA ID, 공개하지 않음)
"""
from __future__ import annotations

import collections
import json
import shutil
import subprocess

from src.virtual_hospital.scripts import gates, render, verify
from src.virtual_hospital.scripts.common import FINAL, LOCAL, MINI, OUT, REPORTS, write_csv
from src.virtual_hospital.scripts.tcga import build_all


def mini_version() -> str:
    try:
        return subprocess.run(["git", "-C", str(MINI), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return "unknown"


def slide_rows(p) -> list[dict]:
    """I-01. 공개 표(slides.csv)에는 가상 슬라이드 번호만, 원본 슬라이드 이름·GDC file_id·썸네일 경로는 local/slide_map.csv."""
    out = []
    for i, s in enumerate(sorted(p.slides, key=lambda x: x["slide"])):
        thumb = verify.THUMBS / f"{s['slide']}.png"
        out.append({"slide_id": f"{p.vp_id}-S{i + 1}", "vp_id": p.vp_id, "dataset": "TCGA-BRCA",
                    "specimen": "resection", "source_slide": s["slide"], "gdc_file_id": s["file_id"],
                    "wsi_note": "원본 svs는 로컬에 없음 (GDC file_id)",
                    "thumb_path": str(thumb.relative_to(FINAL.parent)).replace("\\", "/"), "thumb_abs": str(thumb),
                    "thumb_w": s["thumb_w"], "thumb_h": s["thumb_h"], "downsample": s["downsample"],
                    "approx_w0": round(float(s["thumb_w"]) * float(s["downsample"])),
                    "approx_h0": round(float(s["thumb_h"]) * float(s["downsample"])),
                    "mpp": "", "mpp_source": "원본 svs 속성에서 읽어야 함", "stain_qc": s["stain"],
                    "pen_qc": s["pen"], "rule_id": "I-01"})
    return out


def main() -> int:
    pts, dropped, pss, df = build_all()
    env = gates.envelope(pss)
    out = OUT / "tcga"
    if (out / "charts").exists():
        shutil.rmtree(out / "charts")
    kept, gate_rows, handoff = [], [], []
    for p in pts:
        if p.problems:
            reason = "; ".join(p.problems)
            if all("원자료 모순" in x for x in p.problems):      # S-09: 원자료끼리 맞지 않음 → 제외만 (mini 문제 아님)
                dropped.append({"source_id": p.source_id, "rule": "S-09", "reason": f"S-09 원자료 모순: {reason}"})
                continue
            dropped.append({"source_id": p.source_id, "rule": "G2", "reason": f"G2 차트로 쓸 수 없음: {reason}"})
            handoff.append({"vp_id": p.vp_id, "관문": "G2", "이유": reason, "원인": "real"})   # 차트로 쓸 수 없음 → 넘길 목록
            continue
        try:
            text, ps, errs = render.chart(p)
        except render.RenderError as ex:
            dropped.append({"source_id": p.source_id, "rule": "G2", "reason": f"G2 표기 없음: {ex}", })
            handoff.append({"vp_id": p.vp_id, "관문": "G2", "이유": str(ex), "원인": "real"})
            continue
        res = gates.run(p, ps, errs, env, text)
        gate_rows.append({"vp_id": p.vp_id, **{k: " | ".join(res[k]) for k in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")}})
        if res["failed"]:
            reason = "; ".join(f"{k}: {res[k][0]}" for k in res["failed"])
            dropped.append({"source_id": p.source_id, "rule": res["failed"][0], "reason": reason, })
            if res["real_cause"]:
                handoff.append({"vp_id": p.vp_id, "관문": ",".join(res["failed"]), "이유": reason, "원인": "real"})
            continue
        d = out / "charts" / p.vp_id
        (d / "expected").mkdir(parents=True, exist_ok=True)
        (d / "chart.txt").write_text(text, encoding="utf-8", newline="\n")
        (d / "expected" / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2) + "\n",
                                                           encoding="utf-8", newline="\n")
        (d / "expected" / "biomarker_record.json").write_text(
            json.dumps(res["biomarker"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        kept.append(p)

    # CSV
    write_csv(out / "patients.csv", [{"vp_id": p.vp_id, "branch": p.branch,
                                      "dx_date": p.dx_date, "index_day": p.index_day, "side": p.side,
                                      "sex": "F", "age": p.recs["patient.age"].value} for p in kept])
    write_csv(out / "fields.csv", [r.row(p.vp_id) for p in kept for r in p.recs.values()])
    write_csv(out / "truth.csv", [{"vp_id": p.vp_id, "항목": k, "값": "" if v is None else v}
                                  for p in kept for k, v in p.truth.items()])
    slides = [s for p in kept for s in slide_rows(p)]
    private = ("source_slide", "gdc_file_id", "thumb_path", "thumb_abs", "wsi_note")
    write_csv(out / "images" / "slides.csv", slides, [k for k in slides[0] if k not in private])
    write_csv(LOCAL / "slide_map.csv", slides, ["slide_id", "vp_id", *private[:-2], "wsi_note"])
    write_csv(LOCAL / "source_map.csv", [{"vp_id": p.vp_id, "dataset": "TCGA-BRCA", "source_id": p.source_id}
                                        for p in pts])
    write_csv(REPORTS / "excluded.csv", dropped, ["source_id", "rule", "reason"])
    write_csv(REPORTS / "handoff_candidates.csv", handoff, ["vp_id", "관문", "이유", "원인"])
    write_csv(REPORTS / "gates.csv", gate_rows, ["vp_id", "G1", "G2", "G3", "G4", "G5", "G6", "G7"])

    # 검증
    v = {"V1 복사": verify.v1(kept, df), "V2 계산": verify.v2(kept, df), "V3 분포": verify.v3(pss),
         "V4 관계": verify.v4(kept), "V6 이미지 좌표": verify.v6(slides)}
    report(kept, dropped, handoff, v)
    print(f"세트 {len(kept)}명, 뺀 환자 {len(dropped)}명 넘길 목록 {len(handoff)}건")
    for k, x in v.items():
        print(k, "통과" if x["pass"] else "실패")
    return 0 if all(x["pass"] for x in v.values()) else 1


def report(kept, dropped, handoff, v) -> None:
    by = collections.Counter(d["rule"] for d in dropped)
    origin = collections.Counter((r.origin, r.rule_id) for p in kept for r in p.recs.values() if r.status == "present")
    sub = collections.Counter(p.truth["subtype_rule"] for p in kept)
    lines = ["# TCGA ① (수술 후) 가상환자 세트 — 생성 보고", "",
             f"mini 커밋: `{mini_version()}` · 실행: `python -m src.virtual_hospital.scripts.build`", "",
             "## 인원", "", "| 항목 | 수 |", "|---|---|", f"| 세트 (관문 통과) | {len(kept)} |"]
    lines += [f"| 뺀 환자: {k} | {n} |" for k, n in sorted(by.items())]
    lines += [f"| 넘길 목록 (실제 값 원인) | {len(handoff)} |", "",
              "아형 (규칙 판정): " + ", ".join(f"{k} {n}" for k, n in sub.most_common()), "",
              "## 칸 출처 (present 칸 수)", "", "| origin | 규칙 | 칸 수 |", "|---|---|---|"]
    lines += [f"| {o} | {r} | {n} |" for (o, r), n in sorted(origin.items())]
    lines += ["", "## 검증", ""]
    for k, x in v.items():
        lines.append(f"### {k} — {'통과' if x['pass'] else '실패'}")
        lines.append("")
        lines.append("```")
        lines.append(json.dumps({kk: vv for kk, vv in x.items() if kk != "pass"}, ensure_ascii=False, indent=1,
                                default=str)[:3000])
        lines.append("```")
        lines.append("")
    (REPORTS / "tcga_postop.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
