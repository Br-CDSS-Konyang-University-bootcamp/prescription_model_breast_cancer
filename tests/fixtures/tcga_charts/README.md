# TCGA 기반 차트 원문 (12명)

> 담당 A · 2026-10-19 · 기준 스키마: `schemas/patient_state.json` 0.1-draft6 · 틀: `notes/report_templates.md` (팀 공유 전 초안, A 개인 notes 폴더)

TCGA-BRCA 정답 세트(크롭본 874명)에서 범주마다 3명을 골라, 정답 값을 문서 2~4개짜리 차트 원문으로 옮겼다. 입력 모듈(IN-0~IN-7)이 문장을 정확히 읽는지 재는 추출 세트의 첫 묶음이다 (PROJECT.md §15.4, 30건 이상 목표).

## 1. 사례 목록

| 번호 | 환자 | 범주 | 병기 | 아형 (적힌 값) | 고른 이유 |
|---|---|---|---|---|---|
| T01 | [TCGA-AO-A03N](TCGA-AO-A03N/chart.txt) | 조기 | IIB | ER+ / PR+ / HER2 0 | 직접 작성 정답 대상. 투약 13건, 국소 재발(수술 없음), PIK3CA, PTEN 결실 |
| T02 | [TCGA-5L-AAT0](TCGA-5L-AAT0/chart.txt) | 조기 | IIA | ER+ / PR+ / HER2 1+ | 예시 정답(`src/input/examples/`). ILC, 투약 1건, `index_day` 없음 |
| T03 | [TCGA-AO-A126](TCGA-AO-A126/chart.txt) | 조기 | IIA | ER+ / PR+ / HER2 1+, FISH 음성 | 39세 폐경 전, CMF, goserelin, 국소 재발 후 수술 |
| T04 | [TCGA-A2-A0YG](TCGA-A2-A0YG/chart.txt) | 국소 진행성 | IIIC | ER+ / PR+ / HER2 3+ | 예시 정답. AC → paclitaxel + trastuzumab, doxorubicin 용량 |
| T05 | [TCGA-E2-A107](TCGA-E2-A107/chart.txt) | 국소 진행성 | IIIA | ER+ / PR- / HER2 2+, FISH 음성 | ILC, 비율 없는 ER·PR, 같은 약 중복 기록, AKT1 |
| T06 | [TCGA-AR-A0TQ](TCGA-AR-A0TQ/chart.txt) | 국소 진행성 | IIIA | ER+ / PR- / HER2 2+, FISH 양성 | 27세, triptorelin, trastuzumab 3개 기록 |
| T07 | [TCGA-A2-A0SV](TCGA-A2-A0SV/chart.txt) | 전이성 (진단 시 IV기) | IV | ER+ / PR+ / HER2 2+, FISH 음성 | 직접 작성 정답 대상. 뼈 전이, 차수 1~3, PTEN |
| T08 | [TCGA-LL-A73Z](TCGA-LL-A73Z/chart.txt) | 전이성 (진단 시 IV기) | IV | ER+ / PR+ / HER2 2+, FISH 음성 | NX, 피부·뇌 전이, 모든 투약 PD |
| T09 | [TCGA-B6-A3ZX](TCGA-B6-A3ZX/chart.txt) | 전이성 (진단 시 IV기) | IV | ER- / PR- / HER2 1+ | 혼합형 조직, 폐경 기록 없음, 변이 없음 |
| T10 | [TCGA-A2-A0EW](TCGA-A2-A0EW/chart.txt) | 전이성 (원격 재발) | IIIC | ER+ / PR+ / HER2 0 | 직접 작성 정답 대상. 1,353일 뼈 전이, 검사 림프절 수 없음 |
| T11 | [TCGA-GM-A2DA](TCGA-GM-A2DA/chart.txt) | 전이성 (원격 재발) | IIB | ER+ / PR+ / HER2 2+, FISH 양성 | 투약 23건, 차수 14, 4개 부위 전이 |
| T12 | [TCGA-A2-A04P](TCGA-A2-A04P/chart.txt) | 전이성 (원격 재발) | IIIC | ER- / PR- / HER2 IHC 미시행, FISH 음성 | 36세, 102일 국소·원격 재발, BRCA2 VUS 후보, 유전자 증폭 |

범주는 정답의 `stage.disease_extent`와 `recurrence.status`로 나눴다. 같은 범주에서는 값이 있는 칸이 많은 환자, 그다음 투약 기록이 많은 환자를 골랐다. 직접 작성 정답 대상이던 TCGA-A2-A25E는 크롭본에서 빠져(HER2 2+ / FISH equivocal, 판정 불가) TCGA-AR-A0TQ로 바꿨다.

## 2. 정답

정답은 따로 두지 않는다. 변환기로 만든다 (`team_project` 폴더에서).

```bash
python -m src.input.script.tcga.tcga_to_patient_state --out <출력 폴더> --ids TCGA-AO-A03N TCGA-5L-AAT0 TCGA-AO-A126 TCGA-A2-A0YG TCGA-E2-A107 TCGA-AR-A0TQ TCGA-A2-A0SV TCGA-LL-A73Z TCGA-B6-A3ZX TCGA-A2-A0EW TCGA-GM-A2DA TCGA-A2-A04P
```

정답의 `source`(원문 인용·위치)와 `documents`는 아직 비어 있다. 이 원문을 기준으로 채우는 것은 다음 작업이다 (tcga_mapping.md §1의 (2)).

## 3. 원문 작성 규칙

`notes/report_templates.md` §1의 공통 규칙에 아래를 더했다.

- **날짜를 쓰지 않는다** (tcga_mapping.md §2.3). 모든 시점은 진단일 기준 일수로 쓴다: `진단 후 55일`, `D+55`. 정답의 `start_day`·`end_day`·`metastasis_day`·`recurrence_day`·`index_day`와 같은 숫자다.
- **경과기록 작성일 = `index_day`**(마지막 추적일). 값이 없는 T02는 작성일 없이 쓴다.
- **정답에 없는 값은 쓰지 않는다.** 등급, Ki-67, ECOG, 폐경 근거, 수술 가능 여부, 투약 중단 사유, 차수는 TCGA에 없으므로 원문에도 없다. 합성값을 넣으면 정답과 어긋난다.
- **ER·PR 구간은 대표값으로 쓴다** (tcga_mapping.md §2.4): `90-99%` → 95%, `70-79%` → 75%, `50-59%` → 55%, `10-19%` → 15%, `1-9%` → 5%, `<1%` → `<1%`. 비율이 없으면 판정만 쓴다.
- **주기 수는 기록값(`basis: recorded`)만 쓴다.** 생성기가 투여 일수로 추정한 값(`estimated`)은 원문에 없다.
- **최선 반응은 `unknown`이 아닐 때만 쓴다.**
- **투약 기록은 정답 한 원소 = 한 줄**이다. 같은 약이 두 번 기록된 경우도 두 줄로 둔다.
- **NGS 보고서의 "결과 요약" 줄은 정답 `genomic_reports[].raw_text`를 그대로 옮겼다.** 원문 인용을 맞추기 위해서다.
- 식별정보: 이름 `TCGA가상`, 등록번호 `0000T` + 번호, 병원 `가상대학교병원`.

## 4. 작성하면서 본 생성기 결과의 문제

원문은 정답대로 썼다. 아래는 정답 쪽에서 확인할 곳이다.

| 환자 | 칸 | 생성기 값 | 문제 |
|---|---|---|---|
| T08 TCGA-LL-A73Z, T09 TCGA-B6-A3ZX | `recurrence.recurrence_day` | `0` | 진단 시 IV기인데 첫 재발일이 들어감. draft6 규칙은 "진단 시 IV기는 넣지 않음". `recurrence_status`가 `distant`이고 전이 진단일이 0이라 생긴다 |
| T08 TCGA-LL-A73Z | `stage.metastatic_sites` vs `recurrence.metastatic_sites` | 진단 시 `other: skin`, 재발 `brain` (둘 다 0일) | 같은 날 부위가 다르게 기록됨. 원문에는 "진단 시 피부 전이, 같은 시기 뇌 전이"로 썼다 |
| T12 TCGA-A2-A04P | NGS `raw_text` | `ESR1 amplification`과 `ESR1: 검출되지 않음`이 함께 | 점 변이와 증폭을 한 문장에 섞음 (manual_truth_worksheet.md §4의 PTEN 결실과 같은 문제) |
| T12 TCGA-A2-A04P | `recurrence.later_distant` | `no` | 국소 재발과 원격 전이가 같은 날(102일)이라 "나중에 원격 전이"가 아님. 값은 맞지만 원문에서는 "동시"로 썼다 |
