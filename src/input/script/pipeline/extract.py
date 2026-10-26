"""IN-2 구절 찾기 [LLM] (notes/input_module_design.md §2 IN-2, notes/input_llm_principles_priorities_2026-10-23.md).

문서 하나씩, 그 문서 종류에서 찾을 칸 목록과 예시 1개를 주고 "이 칸의 값이 적힌 구절"을 JSON으로 받는다.
LLM은 값을 계산하지 않는다. 칸 이름은 출력 스키마의 enum으로 강제하고, 구절은 인용 확인(quote.py)이 원문에서 다시 찾는다.
문서는 IN-0으로 가린 글만 받는다 (pipeline.run이 넘긴다). 모델은 llm/config.toml의 [extract].

칸 목록은 문서 종류 5가지(병리·경과기록·영상·투약·분자병리)마다 따로 있다. anthracycline 용량은 투약 줄에서
규칙이 계산하므로 칸 목록에 없다.

usage (team_project 폴더에서, Ollama 실행 중):
    python -m src.input.script.pipeline.extract --ids VC-0103 --docs D4              # 문서 하나: 후보·인용 확인·정답 대조·시간
    python -m src.input.script.pipeline.extract --ids VC-0103 --model qwen2.5:7b     # 모델 바꾸기
    python -m src.input.script.pipeline.extract --out data/input/runs/hari           # 10건을 끝까지 돌려 저장 → python -m src.input.script.evaluation.score <폴더>
    python -m src.input.script.pipeline.extract --replay data/input/runs/hari        # 저장한 LLM 후보로 규칙만 다시 (LLM 호출 없음, 몇 초)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

import requests

from llm import LLMConfig, LLMOutputError, complete_json, load_config
from src.input.script.pipeline.classify import Document

# 문서 종류별 찾을 칸과 설명 (설명은 프롬프트에 그대로 들어간다)
FIELDS = {
    "pathology": {
        "diagnosis.histology": "조직형 (예: 침윤성 유관암, invasive ductal carcinoma)",
        "diagnosis.grade": "조직학적 등급 (Nottingham, NG, grade)",
        "stage.ptnm": "수술 병리 TNM (pT·pN·pM, 병기와 AJCC 판까지 한 구절)",
        "stage.yptnm": "선행요법 뒤 수술 병리 TNM (ypT·ypN)",
        "stage.group": "병기군 (예: stage IIA)",
        "stage.disease_extent": "병기군 구절 (stage.group과 같은 구절을 한 번 더)",
        "stage.metastatic_sites": "진단 당시 원격 전이 여부가 드러나는 TNM 구절 (예: pT2 N0 M0). "
                                  "재발·전이 병소의 생검 소견(Metastatic carcinoma 등)은 넣지 않는다",
        "stage.positive_ln_count": "전이 림프절 수 / 검사한 림프절 수",
        "stage.operable": "'검체:' 줄의 수술 이름 그대로 (예: 좌측 유방 전절제술 + 액와 림프절 절제). "
                          "수술 검체일 때만 낸다. 중심 생검·침생검은 내지 않는다",
        "stage.pathologic_size_mm": "수술 검체 종양 크기",
        "receptors.er_percent": "ER 결과 (판정 단어, Allred 점수, 비율을 한 구절로)",
        "receptors.pr_percent": "PR 결과 (판정 단어, Allred 점수, 비율을 한 구절로)",
        "receptors.her2_ihc": "HER2 면역염색 점수 (0, 1+, 2+, 3+)",
        "receptors.her2_ish": "HER2 ISH(FISH·SISH) 결과",
        "receptors.pdl1": "PD-L1 검사법과 점수 (22C3 CPS, SP142 IC 등)",
        "proliferation.ki67_percent": "Ki-67 비율",
        "neoadjuvant_response.pcr": "선행요법 뒤 잔존 침윤암 여부",
        "neoadjuvant_response.rcb": "RCB 등급",
        "patient.gender": "성별 (F/나이 표기)",
        "patient.age": "나이 (F/나이 표기)",
    },
    "progress_note": {
        "diagnosis.diagnosis_date": "유방암 진단 날짜가 든 구절 (예: 2021.3.5 core bx로 진단)",
        "diagnosis.histology": "조직형",
        "stage.ctnm": "임상 TNM (cT·cN·cM)",
        "stage.group": "병기군 (예: stage IV, IIIA)",
        "stage.disease_extent": "병기군 구절 (stage.group과 같은 구절을 한 번 더)",
        "stage.metastatic_sites": "진단 당시 원격 전이 부위 구절 (진단 시 IV기의 전이 부위, 또는 M0가 든 TNM). "
                                  "나중에 생긴 재발·전이는 넣지 않는다",
        "patient.gender": "성별 (F/나이, 여성)",
        "patient.age": "나이 (F/나이, 00세)",
        "patient.menopausal_status": "폐경 상태 (폐경 전, 폐경 후)",
        "patient.menopausal_basis": "폐경 판단 근거 (LMP, 폐경 나이, 월경 여부, FSH, 난소절제)",
        "patient.ecog": "ECOG 수행 상태",
        "patient.cardiac_history": "심장 질환 과거력",
        "patient.height_cm": "키",
        "patient.weight_kg": "몸무게",
        "patient.lvef_percent": "좌심실 박출률 (LVEF)",
        "patient.mediastinal_radiation": "종격동 방사선 치료 이력",
        "patient.comorbidities": "유방암 말고 함께 앓는 질환 이름 (예: 고혈압, 당뇨, CKD 3a). 질환 하나에 구절 하나. "
                                 "유방암·재발·전이는 넣지 않는다",
        "recurrence.recurrence_date": "첫 재발·전이 날짜와 부위가 든 구절 (예: 2023.4.4 lung metastasis)",
        "recurrence.recurrence_day": "recurrence_date와 같은 구절",
        "recurrence.metastasis_day": "원격 전이 날짜가 든 구절. 진단 시 IV기면 de novo라고 적힌 구절",
        "recurrence.adjuvant_endocrine_end_date": "보조 내분비요법을 끝낸 날짜가 든 구절 (약 이름, 날짜, 종료·중단·완료). "
                                                  "날짜가 없는 구절은 내지 않는다",
        "recurrence.status": "재발 여부와 종류가 적힌 구절 (예: 간 전이, 흉벽 국소 재발, 재발 소견 없음, "
                             "재발 아님 (진단 시 IV기)). 치료 반응(PD 등)은 넣지 않는다",
        "recurrence.metastatic_sites": "재발·전이 부위 구절 (예: 간 전이, 뼈·간 전이). 국소 재발만 있고 "
                                       "원격 전이가 없다고 적혀 있으면 그 구절 (예: 원격 전이 없음)",
        "recurrence.surgery": "재발 병소 수술 (날짜와 수술 이름)",
        "recurrence.surgery_intent": "재발 병소 수술 목적 (완치, 고식)",
        "recurrence.later_distant": "국소 재발 치료 뒤 원격 전이가 생겼는지 적힌 구절 (예: 수술 후 원격 전이 소견 없음)",
        "molecular.germline.BRCA1": "생식세포 BRCA1 검사 결과 또는 미시행",
        "molecular.germline.BRCA2": "생식세포 BRCA2 검사 결과 또는 미시행",
        "molecular.germline.PALB2": "생식세포 PALB2 검사 결과 또는 미시행",
    },
    "radiology": {
        "imaging_findings": "판독 결론에서 전이를 말하는 구절 하나 (전이 부위와 확실성: 전이, 전이 의심, 전이 없음). "
                            "림프절 전이 의심도 포함. 유방 종괴 크기는 stage.clinical_size_mm으로",
        "stage.clinical_size_mm": "유방 종괴 크기가 든 구절 (예: 우측 유방 1.9 cm 종괴)",
    },
    "medication": {
        "treatment_history": "요법 한 줄: 약 이름부터 날짜·주기·반응·중단 사유까지 그 줄 전체. "
                             "줄 앞의 구분 칸(보조·선행·고식)이나 '- '는 빼고 그 뒤부터",
    },
    "molecular": {
        f"molecular.mutations.{g}": f"{g} 결과: 변이가 있으면 그 변이 줄 (유전자, c., p., VAF), "
                                    f"검출되지 않았으면 {g}가 든 '검출되지 않음' 목록 줄. 패널 포함 유전자 목록은 넣지 않는다"
        for g in ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")
    },
}

SYSTEM = """너는 유방암 환자 차트에서 값이 적힌 구절을 찾는 도구다. 값을 계산하거나 해석하지 않는다.

규칙:
1. 칸 목록에 있는 칸마다, 그 값이 적힌 짧은 구절을 문서에서 글자 그대로 복사한다. 띄어쓰기·대소문자·괄호를 바꾸지 않고 요약하지 않는다.
2. 문서에 없는 칸은 내지 않는다. 짐작해서 만들지 않는다.
3. 같은 칸이 문서에 여러 번 나오면 (판독 요약과 본문 표 등) 값이 같든 다르든 모두 낸다.
4. specimen: 원발 유방 조직이면 "primary", 전이·재발 병소이면 "metastasis", 혈액(cfDNA)이면 "cfDNA", 검체와 상관없는 칸이면 null.
5. observed_date: 검체 채취일·수술일·검사 시행일 (YYYY-MM-DD). 보고일이 아니다. 알 수 없으면 null.
6. [이름1]처럼 대괄호로 가린 글자도 문서에 있는 그대로 옮긴다.
JSON만 답한다."""

# 시험 세트(tests/fixtures/virtual_charts) 밖의 예문 (설계 결정: 문서 종류마다 1개, 시험 오염 방지)
EXAMPLES = {
    "pathology": (
        "[병리결과보고서]\n환자명: [이름1]   등록번호: [등록번호1]   F/47\n보고일: 2020.6.10\n"
        "2020.6.3 좌측 유방 중심 생검. Invasive lobular carcinoma.\n"
        "ER positive (Allred 7, 4+3), PR negative (Allred 0), HER2 IHC 2+, Ki-67 20%.\n",
        [{"field": "patient.gender", "quote": "F/47", "specimen": None, "observed_date": None},
         {"field": "patient.age", "quote": "F/47", "specimen": None, "observed_date": None},
         {"field": "diagnosis.histology", "quote": "Invasive lobular carcinoma", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.er_percent", "quote": "ER positive (Allred 7, 4+3)", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.pr_percent", "quote": "PR negative (Allred 0)", "specimen": "primary",
          "observed_date": "2020-06-03"},
         {"field": "receptors.her2_ihc", "quote": "HER2 IHC 2+", "specimen": "primary", "observed_date": "2020-06-03"},
         {"field": "proliferation.ki67_percent", "quote": "Ki-67 20%", "specimen": "primary",
          "observed_date": "2020-06-03"}],
    ),
    "progress_note": (
        "<외래 경과기록>   2019.3.2   종양내과\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n\n"
        "S) 폐경: 폐경 후 (55세 폐경)\nO) ECOG PS 1\n"
        "A) Lt. breast IDC, 2017.5.10 core bx로 진단, 수술 후 보조요법\n"
        "   보조 letrozole 2017.6.20~ 복용 중 2019.1.15 간 전이 → letrozole 2019.1.20 중단\n"
        "P) 전이성 1차 치료 상의\n",
        [{"field": "patient.gender", "quote": "F/58", "specimen": None, "observed_date": None},
         {"field": "patient.age", "quote": "F/58", "specimen": None, "observed_date": None},
         {"field": "patient.menopausal_status", "quote": "폐경 후", "specimen": None, "observed_date": None},
         {"field": "patient.menopausal_basis", "quote": "55세 폐경", "specimen": None, "observed_date": None},
         {"field": "patient.ecog", "quote": "ECOG PS 1", "specimen": None, "observed_date": "2019-03-02"},
         {"field": "diagnosis.histology", "quote": "IDC", "specimen": None, "observed_date": None},
         {"field": "diagnosis.diagnosis_date", "quote": "2017.5.10 core bx로 진단", "specimen": None,
          "observed_date": None},
         {"field": "recurrence.recurrence_date", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.recurrence_day", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.metastasis_day", "quote": "2019.1.15 간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.status", "quote": "간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.metastatic_sites", "quote": "간 전이", "specimen": None, "observed_date": None},
         {"field": "recurrence.adjuvant_endocrine_end_date", "quote": "letrozole 2019.1.20 중단", "specimen": None,
          "observed_date": None}],
    ),
    "radiology": (
        "[영상의학 판독]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n"
        "검사: Chest-abdomen CT (contrast)   검사일: 2019.1.15\n\nFindings:\n"
        "  우측 유방 상외측에 불규칙한 종괴. 간 S4에 1.0 cm 저음영 결절.\n"
        "Conclusion:\n  1. 우측 유방 1.9 cm 불규칙 종괴, 유방암에 합당\n  2. 간 S4 1.0 cm 결절, 전이 의심\n",
        [{"field": "stage.clinical_size_mm", "quote": "우측 유방 1.9 cm 불규칙 종괴", "specimen": None,
          "observed_date": "2019-01-15"},
         {"field": "imaging_findings", "quote": "간 S4 1.0 cm 결절, 전이 의심", "specimen": None,
          "observed_date": "2019-01-15"}],
    ),
    "medication": (
        "[투약 기록]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n"
        "구분    요법                  시작         종료         주기         반응   중단 사유\n"
        "보조    letrozole 2.5mg qd   2017.6.20   2019.1.20   -   PD     간 전이\n"
        "고식    paclitaxel 80mg/m2   2019.2.1   2019.6.27   weekly #21   PR   완료\n",
        [{"field": "treatment_history", "quote": "letrozole 2.5mg qd   2017.6.20   2019.1.20   -   PD     간 전이",
          "specimen": None, "observed_date": None},
         {"field": "treatment_history", "quote": "paclitaxel 80mg/m2   2019.2.1   2019.6.27   weekly #21   PR   완료",
          "specimen": None, "observed_date": None}],
    ),
    "molecular": (
        "[NGS 보고서]\n환자명: [이름1]   등록번호: [등록번호1]   F/58\n보고일: 2019.2.10\n"
        "검체: 간 생검 조직 (2019.1.25)\n\n검출된 변이\n  PIK3CA   c.1633G>A (p.E545K)   VAF 12%\n\n"
        "검출되지 않음 (Not detected)\n  ESR1, AKT1, PTEN\n\n* 패널 포함 유전자: ESR1, PIK3CA, AKT1, PTEN, ERBB2\n",
        [{"field": "molecular.mutations.PIK3CA", "quote": "PIK3CA   c.1633G>A (p.E545K)   VAF 12%",
          "specimen": "metastasis", "observed_date": None}]
        + [{"field": f"molecular.mutations.{g}", "quote": "ESR1, AKT1, PTEN", "specimen": "metastasis",
            "observed_date": None} for g in ("ESR1", "AKT1", "PTEN")],
    ),
}


NO_QUOTE = {"null", "none", "n/a", "-"}


def schema(doc_type: str) -> dict:
    """LLM 출력 스키마. 칸 이름은 이 문서 종류의 칸 목록 안에서만."""
    return {"type": "object", "required": ["candidates"], "additionalProperties": False, "properties": {
        "candidates": {"type": "array", "items": {
            "type": "object", "required": ["field", "quote", "specimen", "observed_date"], "additionalProperties": False,
            "properties": {
                "field": {"enum": list(FIELDS[doc_type])},
                "quote": {"type": "string", "minLength": 1},
                "specimen": {"enum": ["primary", "metastasis", "cfDNA", None]},
                "observed_date": {"type": ["string", "null"]}}}}}}


def messages(doc: Document) -> list[dict]:
    fields = "\n".join(f"- {k}: {v}" for k, v in FIELDS[doc.doc_type].items())
    ex_text, ex_out = EXAMPLES[doc.doc_type]
    user = "칸 목록:\n{fields}\n\n문서:\n<<<\n{text}\n>>>"
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user.format(fields=fields, text=ex_text)},
            {"role": "assistant", "content": json.dumps({"candidates": ex_out}, ensure_ascii=False)},
            {"role": "user", "content": user.format(fields=fields, text=doc.text)}]


def _iso(date: str | None) -> str | None:
    """LLM이 2023.4.16처럼 써도 YYYY-MM-DD로. 읽을 수 없으면 None."""
    m = date and re.fullmatch(r"\s*(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\.?\s*", date)
    return m and f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def extract_doc(doc: Document, config: LLMConfig, complete: Callable = complete_json) -> list[dict]:
    """문서 하나의 후보 목록 (candidates.py 형식). 칸 목록이 없는 문서 종류는 빈 목록."""
    if doc.doc_type not in FIELDS:
        return []
    out = complete(messages(doc), schema(doc.doc_type), config)
    # 빈 칸에 "null" 같은 글자를 구절로 쓴 것은 후보가 아니다 (인용 준수율에 넣지 않는다)
    return [{"doc_id": doc.doc_id, "field": c["field"], "quote": c["quote"], "specimen": c["specimen"],
             "observed_date": _iso(c["observed_date"])} for c in out["candidates"]
            if c["quote"].strip().lower() not in NO_QUOTE]


def make_extract(config: LLMConfig, complete: Callable = complete_json, doc_ids: set[str] | None = None):
    """pipeline.run에 넣는 extract 함수. doc_ids를 주면 그 문서만 보낸다."""
    def extract(docs: list[Document]) -> list[dict]:
        return [c for d in docs if doc_ids is None or d.doc_id in doc_ids for c in extract_doc(d, config, complete)]
    return extract


def main(argv=None) -> int:
    from src.input.script.evaluation.candidates import from_expected
    from src.input.script.virtual.virtual_chart import out_dir
    from src.input.script.pipeline.classify import split
    from src.input.script.pipeline.deid import identifiers, mask
    from src.input.script.pipeline.quote import locate

    from src.input.script.virtual.virtual_chart import CASES
    from src.input.script.pipeline.pipeline import run

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="+", help="사례 (기본: 문서 보기는 VC-0103, --out은 10건)")
    ap.add_argument("--docs", nargs="*", help="문서 ID (없으면 칸 목록이 있는 문서 모두)")
    ap.add_argument("--model", help="llm/config.toml [extract]의 모델 대신")
    ap.add_argument("--out", type=Path, help="끝까지 돌려 <폴더>/<사례>/patient_state.json, issues.json, candidates.json 저장")
    ap.add_argument("--replay", type=Path, help="<폴더>/<사례>/candidates.json으로 규칙 단계만 다시 돌려 덮어쓴다")
    args = ap.parse_args(argv)
    if args.replay:
        for d in sorted(p for p in args.replay.iterdir() if (p / "candidates.json").exists()):
            ref = d.name
            chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
            want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
            cands = json.loads((d / "candidates.json").read_text(encoding="utf-8"))
            ps, issues = run(chart, lambda docs: cands, patient_ref=ref, created_at=want["created_at"])
            log = json.loads((d / "issues.json").read_text(encoding="utf-8"))
            (d / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "issues.json").write_text(json.dumps({**log, "issues": issues}, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
            print(f"{ref}: 후보 {len(cands)}개, 문제 {len(issues)}개")
        return 0
    cfg = load_config("extract", **({"model": args.model} if args.model else {}))
    print(f"모델 {cfg.model}", flush=True)
    if args.out:
        for ref in args.ids or CASES:
            chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
            want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
            log = {"candidates": 0, "errors": [], "doc_seconds": {}}

            def complete(msgs, sch, config, _log=log):
                t = time.perf_counter()
                try:
                    out = complete_json(msgs, sch, config)
                except (LLMOutputError, requests.RequestException) as e:     # 문서 하나가 실패해도 계속
                    _log["errors"].append(str(e)[:300])
                    out = {"candidates": []}
                _log["candidates"] += sum(c["quote"].strip().lower() not in NO_QUOTE for c in out["candidates"])
                _log["doc_seconds"][str(len(_log["doc_seconds"]) + 1)] = round(time.perf_counter() - t)
                return out

            t0 = time.perf_counter()
            cands: list[dict] = []
            llm_extract = make_extract(cfg, complete)

            def extract(docs, _cands=cands):
                _cands.extend(llm_extract(docs))
                return _cands

            ps, issues = run(chart, extract, patient_ref=ref, created_at=want["created_at"])
            d = args.out / ref
            d.mkdir(parents=True, exist_ok=True)
            (d / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")
            (d / "issues.json").write_text(json.dumps({**log, "model": cfg.model, "issues": issues,
                                                       "seconds": round(time.perf_counter() - t0)},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{ref}: {time.perf_counter() - t0:.0f}초, 후보 {log['candidates']}개, 문제 {len(issues)}개, "
                  f"LLM 실패 {len(log['errors'])}개", flush=True)
        return 0
    for ref in args.ids or ["VC-0103"]:
        chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
        want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        mapping = identifiers(chart)
        for doc in split(chart):
            if doc.doc_type not in FIELDS or (args.docs and doc.doc_id not in args.docs):
                continue
            t = time.perf_counter()
            got = extract_doc(replace(doc, text=mask(doc.text, mapping)), cfg)
            sec = time.perf_counter() - t
            gold = {(c["field"], c["quote"]) for c in from_expected(want)
                    if c["doc_id"] == doc.doc_id and c["field"] in FIELDS[doc.doc_type]}
            print(f"\n== {ref} {doc.doc_id} ({doc.doc_type}) {sec:.0f}초, 후보 {len(got)}개, 정답 {len(gold)}개", flush=True)
            found = set()
            for c in got:
                src = locate(c["quote"], doc, mapping)
                key = (c["field"], src["quote"]) if src else None
                found.add(key)
                mark = "정답과 같음" if key in gold else "원문에 없음" if src is None else "정답과 다름"
                print(f"  [{mark}] {c['field']}: {c['quote']!r} specimen={c['specimen']} date={c['observed_date']}")
            for f, q in sorted(gold - found):
                print(f"  [놓침] {f}: {q!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
