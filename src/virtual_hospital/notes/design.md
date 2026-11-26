# 가상 병원 환자 설계

작성: 2026-11-09 (A) · 정리: 2026-11-19 (README의 설계 부분을 옮김. 철회한 계획(옛 §7 L1·L3, 작업 순서, 옛 폴더 구조)은 지움. 바뀐 경위는 [progress.md](progress.md))

실제 슬라이드가 붙은 가상환자로 **모듈 1~3·4-B(슬라이드)에서 처방 모듈(입력 → 판정 → 확정 → 처방·급여)까지**를 한 환자로 이어서 확인한다. 이 문서는 가상환자를 만드는 규칙을 어떻게 세우고, 어디에 두고, 어떻게 검사하는지 정한다. 절 번호는 `rules.csv`의 `출처` 열(`design.md §6.2` 등)이 가리키므로 바꾸지 않는다.

- 규칙 하나하나: [rules.csv](../../../data/virtual_hospital/rules/rules.csv) · 합성한 칸 정리: [synthetic_criteria.md](synthetic_criteria.md) · 코드 안내: [build_guide.md](build_guide.md)

---

## 1. 정한 것 (2026-11-09)

| 항목 | 결정 |
|---|---|
| 환자 갈래 | **BCNB = 수술 전 (생검 직후)**, **TCGA = 수술 후**. 한 사람의 생검·절제 슬라이드 짝은 어느 데이터에도 없어서 섞지 않는다 |
| 뼈대 | 실제 슬라이드 1장 + 그 슬라이드 주인의 실제 라벨. 데이터에 없는 칸만 합성한다 |
| 값의 출처 | 칸마다 `real` (원값) / `derived` (실제 값에서 계산) / `synthetic` (합성). 모델 채점은 `real` 칸으로만 한다. 모듈이 낸 예측·주의 점수는 `model`로 따로 둔다 (§10) |
| 환자 고르기 | **학습·시험 분할은 나누지도 표시하지도 않는다** (2026-11-10). 목적은 가상환자 차트다. 모듈 평가에 쓰게 되면 그때 각 모듈의 분할로 거른다 |
| Synthea | 쓰지 않는다. 배경 기록(방문, 동반 질환)이 필요해지면 그때 검토 |

## 2. 원칙: 처방 모듈을 고치지 않는다

1. **처방 모듈이 기준이다.** 생성기는 처방 모듈이 지금 받는 것(`schemas/patient_state.json`, `field_vocab.csv`, `drug_names.csv`, `report_templates.md`의 틀, 상태값)만 만든다.
2. **못 맞추면 환자를 뺀다.** 실제 값이 처방 모듈 입력 규칙에 들어가지 않으면 그 환자를 빼고 **넘길 목록**(§11.3)에 적는다. 처방 모듈을 바꿀지는 팀이 기존 절차(4명 검토)로 정한다.
3. **바꾸자는 근거는 실제 값이어야 한다.** `synthetic` 칸에서 생긴 문제는 생성기 버그라서 생성기를 고친다.
4. **경계 시험은 기존 가상 차트가 맡는다.** 합성 수치는 판정 경계에서 떨어진 값만 쓴다 (§4.4). 경계 사례는 `tests/fixtures/virtual_charts/`가 맡는다.
5. **처방 모듈이 바뀌면 관문(§11.2)을 다시 돌린다.**

## 3. 만드는 흐름

```
원본 (TCGA 크롭·병합 CSV, 변이, RNA / BCNB 임상 xlsx)  + 슬라이드
   │ S  환자 고르기 (범위, 필수 칸, 제외 목록)
   │ M  실제 값 옮기기 (원본 열 → patient_state 칸, 정규값)
   │ D  계산 (병기, ISH, cT, 날짜, 판정 기준일)
   │ Y  합성 (근거 순위 ①~⑤)
   │ T  치료 이력 (TCGA 재발 갈래만, 실제 투약 기록 그대로, §7)
   │ N  결측 처리
   ▼
CSV (patients · fields · treatments · truth) + slides.csv
   │ G  관문 G1~G7 ── 실패 → 생성기 수정 또는 환자 제외 + 넘길 목록
   │ R  표기 (Chart/F로 chart.txt + 정답 patient_state)
   │ V  검증 V1~V6 → reports/
   ▼
chart.txt · expected/{patient_state, biomarker_record}.json
   │ confirmed.py → expected/confirmed_state.json (처방 흐름 입력)
```

## 4. 규칙 체계

### 4.1 규칙 표

규칙은 **표(CSV)로 두고 코드는 표를 실행만** 한다. 규칙을 코드를 읽지 않고 검토할 수 있게 하려는 것이다. 만든 값마다 거친 규칙(`rule_id`)을 남긴다 (`fields.csv`, 여러 개면 차례로).

- 규칙 목록은 `data/virtual_hospital/rules/rules.csv` 한 표 (`묶음` 열: 고르기 S·옮기기 M·계산 D·합성 Y·결측 N·표기 R·관문 G·이미지 I). 묶음별 개수는 [build_guide.md](build_guide.md) §2
- 숫자·분포는 `references.csv`·`thresholds.csv`, 표기는 `phrases.csv`, 이미지 표 정의는 `image_tables.csv`
- `tests/virtual_hospital/test_virtual_hospital.py`가 코드·산출물의 규칙 id가 모두 표에 있는지 본다

### 4.2 규칙 표의 공통 열

| 열 | 내용 | 예 |
|---|---|---|
| `rule_id` | 묶음 + 번호 | `Y-07` |
| `설명` | 한 줄 | TCGA Ki-67을 MKI67 발현 순위로 만든다 |
| `갈래` | BCNB / TCGA① / TCGA② / 공통 | TCGA① |
| `입력` | 쓰는 원본 열 또는 칸 | `MKI67` 발현 |
| `출력 칸` | `patient_state` 경로 | `proliferation.ki67_percent` |
| `근거` | §4.3의 ①~⑤, 또는 문헌 | ③ |
| `출처` | 파일·열 / 문헌(쪽) / 이 문서의 절 | `references.csv` R-03 |
| `예` | 입력 → 출력 하나 | MKI67 상위 30% → Ki-67 30% |
| `상태` | 제안 / 확정 / 폐기 | 제안 |
| `결정일` | 확정한 날 | |

`근거`나 `출처`가 비어 있는 규칙은 확정할 수 없다.

### 4.3 합성 근거 순위

합성값은 위에서부터 쓸 수 있는 첫 근거로 만든다.

| 순위 | 근거 | 예 |
|---|---|---|
| ① | 같은 환자의 다른 실제 값에서 계산 (`derived`) | TNM → 병기, BCNB HER2 2+ + 양성 → ISH 증폭, 종양 크기 → cT |
| ② | 같은 데이터셋 안의 실제 관계 (조건부 분포) | TCGA 폐경 결측 → TCGA 나이대별 폐경 비율, ER % 결측 → 같은 판정 환자의 실제 구간 분포 |
| ③ | 같은 환자의 다른 실제 데이터 (대리 지표) | TCGA Ki-67 → 같은 환자의 `MKI67` RNA 발현 순위 |
| ④ | 문헌·공개 통계 (`references.csv`에 출처 필수) | ECOG, 초음파 cN 정확도, 판독 없는 환자의 grade |
| ⑤ | 고정값 (근거가 없을 때) | 병원 이름, 문서 사이 날짜 간격 |

- BCNB 값으로 TCGA 칸을 채우지 않는다 (반대로도. 예외: BCNB 폐경·Allred에 TCGA 분포를 씀). 섞으면 TCGA 산출물을 공개할 수 있는지 애매해진다.
- 합성값은 **실제 값과 같은 판정**이 나와야 한다. 예: BCNB ER `Positive`에 붙이는 %는 B 규칙으로도 양성.
- 난수는 `vp_id`와 규칙 id로 정한다. 같은 규칙 표 + 같은 원본 → 같은 결과.

### 4.4 경계 금지 구간 (`thresholds.csv`)

합성 수치에만 적용한다. 실제 값은 경계에 있어도 그대로 쓴다. ER % 1~19, PR % 1~19 (저발현과 B의 판정 경계), Ki-67 % 15~25 (20% 기준).

### 4.5 규칙을 바꾸는 절차

1. 규칙 표의 행을 고친다 (상태 `제안`).
2. 전체를 다시 만든다 → 관문과 검증이 다시 돈다.
3. 바뀐 환자 수와 칸을 [progress.md](progress.md)에 적는다.
4. 확인되면 상태를 `확정`, 결정일을 적는다.

**검증 기준(`thresholds.csv`)은 결과를 본 뒤 바꾸지 않는다.** 바꿔야 하면 이유를 적고 다음 생성부터 적용한다.

## 5. 시점과 정답 분리

차트는 **판정 기준일까지 일어난 일만** 담는다. 그 뒤의 값은 `truth.csv`에만 둔다. 예: BCNB 수술 림프절 결과가 차트에 들어가면 모듈 2가 맞혀야 할 답이 보인다.

| 갈래 | 판정 기준일 | 차트에 보임 | 정답 표에만 | 쓰는 모듈 → 처방 장면 |
|---|---|---|---|---|
| **BCNB** | 초진일 (생검 보고 뒤) | 생검 병리, 임상 크기, 나이, 합성 칸 | 수술 림프절 결과(`ALN status`, 개수), 수술 방법 | 2, 3, 4-B 파트 1 → 수술 전 (선행요법 여부) |
| **TCGA ①** | 실제 첫 보조 투약일과 수술 후 49일 중 빠른 날 (D-10) | 절제 병리, 수용체, 변이, 폐경, 합성 칸 | 이후 투약(참고용), 재발, 생존, PAM50 | 1, 3(ER/PR), 4-B 파트 2 → 수술 후 보조요법 |
| **TCGA ②** | 실제로 다음 고식 치료를 정한 날 (D-R1, 실제 원격 재발 환자만) | ① + 그 전 투약(실제) + 재발 | 그날부터의 투약(참고용), 생존 | → 고식 2차 또는 1차 |

- 날짜: TCGA는 진단일 기준 일수, BCNB는 날짜 없음. 가짜 진단일을 정하고 일수를 더한다 (`D-`).
- TCGA ② 장면: 두 번째 고식 요법이 있으면 그 시작일, 없으면 첫 고식 요법 시작일. 문구는 그 요법의 종류와 차수 (예: 내분비 1차 뒤 capecitabine → "고식 항암 1차 치료 결정"). 기준일에 투약 중인 줄은 반응을 쓰지 않는다. 장면 차수와 B 확정값이 다른 1명(VH-T0213)은 `data/virtual_hospital/reports/confirmed.md`.
- **결정 시점마다 차트:** 차트는 약을 새로 정하는 시점마다 만들고, 그 시점에 시작한 약부터는 차트에 없다. 투약 중간 시점의 차트는 만들지 않는다.
- **실제 처방 기록은 정답이 아니다:** `truth.csv`의 `actual_prescriptions_reference`(①)와 `actual_prescriptions_from_index_reference`(②)는 2000년대 미국 처방이다. 처방 모듈을 여기에 맞추지 않고 추천 옆에 참고로만 둔다. 처방 모듈이 맞는지는 `tests/fixtures/virtual_charts/`(지침·급여 정답)로 본다. 이 폴더의 차트로는 끝까지 실행되는지, 앞 단계(입력·바이오마커·치료 상황·차수) 정답이 맞는지를 본다.
- 투약 기록이 없는 TCGA ① 환자(146명)는 처방 전 환자로 쓴다. 실제 처방과 나란히 보는 데서는 빠진다.

## 6. 칸별 규칙

`차트` = chart.txt에 씀, `정답` = `truth.csv`에만, `거르기` = 환자 고르기에만, `안 씀`. 합성한 칸의 자세한 기준은 [synthetic_criteria.md](synthetic_criteria.md).

### 6.1 BCNB (1,058명, 14열 + 슬라이드)

| 원본 열 | 쓰는 곳 | `patient_state` 칸 | 출처 | 규칙 |
|---|---|---|---|---|
| `Patient ID` | `local/source_map.csv` | — | — | — |
| `Age(years)` | 차트 | `patient.age` | real | M |
| `Tumour Size(cm)` | 차트 | `stage.clinical_size_mm` (×10) | real | M |
| (계산) | 차트 | `stage.ctnm`의 T | derived | D: 크기 → cT |
| `Tumour Type` | 차트 | `diagnosis.histology` | real | M. Other type은 제외 (S-B2) |
| `Histological grading` | 차트 | `diagnosis.grade` | real | M. 결측은 합성하지 않고 줄을 안 씀 |
| `ER`, `PR` | 차트 | `receptors.*.result` | real | M |
| (합성) | 차트 | 같은 칸의 % (Allred) | synthetic | Y: TCGA 같은 판정 분포 (§4.4) |
| `HER2 Expression` | 차트 | `receptors.her2_ihc.score` | real | M |
| `HER2` | 차트 | `receptors.her2_ish` | derived | D: 2+일 때만 |
| `Ki67` | 차트 | `proliferation.ki67_percent` | real | M |
| (합성) | 차트 | `patient.menopausal_status`, `patient.ecog` | synthetic | Y |
| (합성) | 차트 | `stage.ctnm`의 N (초음파) | synthetic | Y: 정답 림프절 + 문헌 초음파 민감도·특이도 |
| `Molecular subtype` | 안 씀 | — | — | 아형은 B가 판정 |
| `ALN status`, `Number of lymph node metastases`, `Surgical` | **정답** | — | real | 모듈 2 정답, 수술 뒤 정보 |
| 슬라이드, 종양 주석 | `slides.csv`, `annotations.csv` | — | real | 모듈 2·3·4-B 입력 |

모듈 3 정제 규칙의 제외 대상 11명은 같은 목록으로 뺀다 (S-B1, `bcnb.py`의 `EXCLUDE_M3`).

### 6.2 TCGA-BRCA (`source/tcga_brca_merged.csv` 1,098명 + 변이 + RNA + 슬라이드)

| 원본 열 | 쓰는 곳 | `patient_state` 칸 | 출처 | 규칙 |
|---|---|---|---|---|
| `gdc_gender` | 거르기 | `patient.gender` | real | S: 남성 제외 |
| `gdc_history_neoadjuvant_treatment` | 거르기 | — | real | S-02: Yes 제외 |
| `gdc_age_at_diagnosis` | 차트 | `patient.age` | real | M |
| `gdc_menopause_status` | 차트 | `patient.menopausal_status` | real | M. 결측은 Y ② (나이대별 실제 비율) |
| `gdc_histological_type` | 차트 | `diagnosis.histology` | real | M |
| Thennavan 2021 판독 점수 | 차트 | `diagnosis.grade` (+ 세 점수) | real | M-05 (650명). 판독 없는 21명만 Y-05 |
| `gdc_ajcc_*` (pT·pN·pM, 병기, 판수) | 차트 | `stage.ptnm`, `stage.group` | real | M. MX + I~III기 → M0 (D-06), pT 하위 글자 정리 (D-11) |
| `gdc_lymph_nodes_examined_*` | 차트 | `stage.positive_ln_count` | real | M |
| `gdc_margin_status`, `gdc_surgical_procedure_first` | 차트 | (병리 글), `recurrence.surgery` | real | M |
| `gdc_er_status_by_ihc`, `gdc_pr_status_by_ihc` + % | 차트 | `receptors.*` (Allred) | real | M, D-07~D-09. % 결측은 Y ② |
| `gdc_her2_*` (IHC 판정·점수, FISH) | 차트 | `receptors.her2_ihc`, `her2_ish` | real | M. 점수·FISH 없는 판정은 Y-07 |
| `MKI67` 발현 (`team_project_final`) | 합성 근거 | `proliferation.ki67_percent` | synthetic | Y ③ |
| 체세포 변이 (7개 유전자) | 차트 | `molecular.mutations.*` | real | M. c. 표기는 `tcga_hgvsc.csv` (M-03) |
| `drug_timeline` | 차트 (TCGA ②만) | `treatment_history` | real | §7 |
| 재발 날짜·부위 | 차트 (TCGA ②만) | `recurrence.*` | real | M |
| `cbio_OS_*`, `PFS_*`, `DFS_*`, `cbio_SUBTYPE` (PAM50) | **정답** | — | real | 차트에 쓰지 않음 |
| 인종·민족, 분할용 TSS, 방사선, 투약 용량 등 | 안 씀 | | | |

## 7. 치료 이력

- BCNB(생검 직후)와 TCGA ①(수술 직후)은 판정 기준일에 투약 이력이 없다.
- TCGA ②는 실제 투약 기록을 **처방된 그대로** 쓰고 차수는 처방 모듈이 센다. 약 계열은 `data/dictionaries/drug_classes.csv`. 병용 약은 같은 구분·시작·종료일이면 한 줄 (D-R4), 중단 사유는 실제 값으로만 (D-R2), 종료일 없는 보조 tamoxifen은 D-R5.
- 허가사항 표(옛 L1)와 비정형 목록(옛 L3)은 만들지 않기로 했다 (2026-11-17, 근거 없이 고른 약 목록이라 철회). 앞뒤가 안 맞는 기록으로 입력 모듈 충돌 검사를 시험하려면 정상 세트와 섞지 않고 따로 만든다.

## 8. 결측 규칙

**처방 모듈이 이미 처리하는 결측만 차트에 남긴다.**

| id | 종류 | 칸 | 처리 |
|---|---|---|---|
| N-1 | 필수 | 성별, 나이, ER, PR, HER2 (IHC 또는 ISH), 병기 (T·N·M) | 실제가 결측이면 환자 제외 (채우면 실제 라벨을 지어내는 셈) |
| N-2 | 보조 | 폐경, grade, Ki-67, ECOG, ER/PR % | 합성. BCNB grade 결측은 실제 결측이라 그대로 둠 |
| N-3 | 선택 | PD-L1, gBRCA, NGS, 영상 | 줄을 쓰지 않는다 (`not_recorded`). 일부는 `not_done` |
| N-4 | 처방 모듈이 처리하는 실제 결측 | 예: HER2 2+인데 FISH 없음 | 그대로 둔다 (B가 `unknown` + ISH 권고) |

## 9. CSV와 chart.txt

### 9.1 CSV

칸 이름은 `patient_state` 경로, 값은 `field_vocab.csv`의 정규값이다. CSV가 처방 모듈과 같은 말을 쓰므로 관문을 CSV 단계에서 바로 돌린다.

| 파일 | 1행 | 주요 열 |
|---|---|---|
| `patients.csv` | 환자 1명 | `vp_id`, `branch`, `dx_date`, `index_day`, `side`, `sex`, `age` |
| `fields.csv` | 칸 1개 | `vp_id`, `field`, `value` (JSON), `status`, `origin` (real / derived / synthetic), `basis` (①~⑤), `rule_id`, `source_column`, `observed_date`, `specimen`, `role` |
| `treatments.csv` | 요법 1개 (TCGA ②) | `vp_id`, 순서, `drugs`, `setting`, 시작·종료, 중단 사유와 근거, 차수 |
| `truth.csv` | 정답 1개 | `vp_id`, 항목, 값. chart.txt에 넣지 않음 |
| `local/source_map.csv` | 환자 1명 | `vp_id`, 원본 ID (git 제외) |

### 9.2 chart.txt

- 처방 모듈 가상 차트 방식(`src/input/script/virtual/virtual_chart.py`의 `Chart`·`F`, 글을 쓰는 순간 칸 값과 위치를 함께 기록)을 그대로 쓴다. 그래서 chart.txt와 정답이 어긋날 수 없다.
- 표기는 이미 있는 표기에서만 고른다 (`phrases.csv`: 가상 차트 사례 스크립트, `report_templates.md`, `field_vocab.csv`, `drug_names.csv`). 머리글은 `report_templates.md` §1.2에서만.
- 문서 순서 (`render.py`): BCNB 초진 기록 → 생검 병리 → 유방 초음파 / TCGA ① 수술 후 외래 → 수술 병리 → 분자병리 / TCGA ② 재발 외래 → 수술 병리 → 분자병리 → 투약 기록.

## 10. 이미지 데이터

### 10.1 보여 줄 것 (착수 발표 v2 21·22쪽)

모듈 3·2 화면 왼쪽의 "생검 H&E · 주의 영역": 썸네일 위에 모델이 크게 본 타일을 노랑·주황으로 덮은 그림 (MIL attention). 모듈 3은 마커마다, 모듈 2는 N+ 하나. 모듈 1(절제 H&E)과 4-B(이웃 환자 썸네일)도 같은 틀.

### 10.2 원칙

1. **원본 슬라이드는 DB에 넣지 않는다.** 파일 경로와 해시만 둔다 (병원 PACS처럼). TCGA 원본 WSI는 GDC file_id로 가리킨다.
2. **위치는 그림이 아니라 좌표로.** 모든 위치는 level 0 픽셀 좌표 + mpp. 히트맵 PNG와 잘라낸 타일은 다시 만들 수 있는 캐시다.
3. **세 구역:** 병원 기록 (슬라이드, 썸네일) / 모듈 결과 (예측값, 타일 점수, 출처 `model`) / 정답 (BCNB 종양 주석, 림프절 결과). 모듈 결과는 chart.txt에 넣지 않는다.
4. **타일 격자는 모듈 실행마다 따로 등록한다** (모듈마다 타일 크기·인코더가 다름).
5. **모듈 코드는 고치지 않는다.** 각 모듈이 정해진 형식(§10.7)으로 낸 결과를 등록만 한다.

### 10.3 표 (열 정의: `rules/image_tables.csv`)

| 파일 | 1행 | 구역 |
|---|---|---|
| `slides.csv` | 슬라이드 1장: 경로, 해시, level 0 크기, mpp, QC, 썸네일·downsample | 병원 기록 |
| `annotations.csv` | 주석 1개: 종류, `origin` (real / pipeline), GeoJSON (level 0) | 정답 / 파이프라인 |
| `tile_grids.csv` | 격자 1개: 모듈, 타일 크기, 타일 수, 격자 파일 | 모듈 결과 |
| `module_runs.csv` | 모듈 실행 1번: 모델·버전·가중치 해시, 인코더, 격자, 입력으로 쓴 칸 | 모듈 결과 |
| `predictions.csv` | 실행별 예측값 (화면용) | 모듈 결과 |
| `attention.csv` | 점수 층 1개: 대상, 점수 파일, 정규화, 상위 k | 모듈 결과 |
| `renders.csv` | 그림 1장 (썸네일 / 히트맵 / 상위 타일) | 캐시 |

빈 표와 폴더는 `data/virtual_hospital/tcga/images/`, `local/bcnb/images/`에 있다. BCNB `annotations.csv`만 채워져 있다. 타일 점수는 CSV에 넣지 않고 실행마다 파일 하나(Parquet 또는 `.h5`)로 두고 경로만 적는다.

### 10.4 좌표 규칙 (`I-`)

| 항목 | 규칙 |
|---|---|
| 기준 좌표 | level 0 픽셀, 타일은 왼쪽 위 `(x, y)` (모듈 1 `.h5` `coords`와 같음) |
| 썸네일 | 썸네일 좌표 = level 0 ÷ `downsample` (썸네일마다 저장) |
| 주석 | GeoJSON, level 0. BCNB 원 주석에서 슬라이드 밖 다각형은 뺌 (I-02) |
| 히트맵 | 타일 점수 → 슬라이드 안 백분위 → 썸네일 격자 → 상위 구간만 노랑·주황 |

### 10.5 시점과 정답 분리 (이미지)

- 수술 전 갈래의 모듈 2 실행 입력에 정답 칸(`ALN status`, 수술 방법)이 없어야 한다.
- 4-B 이웃 환자 썸네일은 검색 DB 쪽 슬라이드라 `slides.csv`가 아니라 4-B 결과에 경로로만 남긴다.

### 10.6 이미지 검증

| id | 확인 | 통과 기준 |
|---|---|---|
| V6 좌표 | 타일·주석 좌표가 슬라이드 안, 썸네일 × downsample = 원본 크기 | 100% |
| V7 다시 그리기 | 그림을 지우고 다시 만든 것이 저장본과 같음 | 100% |
| V8 위치 참고 | 상위 주의 타일 중 종양 주석(BCNB)·CellViT 종양 타일(TCGA) 안 비율 | 보고만 |

### 10.7 모듈에 부탁할 결과 형식 (팀 합의 전)

예측 JSON (실행 정보, 예측값, 입력으로 쓴 칸), 격자 파일 (`coords`, `tile`, `mpp`), 타일 점수 파일 (격자 순서, 대상마다 한 열). 자세히: [module_result_format_proposal.md](module_result_format_proposal.md).

## 11. 검증과 관문

### 11.1 검증: 실제 데이터와 같은지 (V, `verify.py`)

생성할 때마다 돌리고 `data/virtual_hospital/reports/`(BCNB는 `local/reports/`)에 쓴다. 생성기와 다른 코드로 다시 읽는다.

| id | 대상 | 방법 | 통과 기준 |
|---|---|---|---|
| V1 복사 | `real` 칸 | 원본에서 다시 읽어 비교 | 100% |
| V2 계산 | `derived` 칸 | 다른 코드로 다시 계산 | 100% |
| V3 분포 | `synthetic` 칸 | ② 근거는 묶음을 돌려 가며 가리고 다시 만들어 실제와 비교, ③·④는 근거 분포와 비교 | 범주 비율 차이 5%p 이내 |
| V4 관계 | 칸 사이 | 수용체와 치료, 나이와 폐경, 병기와 TNM, 시간 순서, 시점 | 위반 0건 |
| V5 모듈 입력 | 슬라이드 | 가상 번호로 돌린 모듈 결과 = 원래 ID로 돌린 결과 | 100% (모듈 결과가 나오면) |
| V6~V8 | 이미지 | §10.6 | |

### 11.2 관문: 처방 모듈을 지키는지 (G, `gates.py`)

환자 한 명이 세트에 들어가려면 모두 통과해야 한다. 하나라도 실패하면 처방 모듈을 고치지 않는다.

| id | 확인 | 실패하면 |
|---|---|---|
| G1 스키마 | 정답 `patient_state`가 스키마를 통과하고 `fields.csv`와 같다 | 생성기 수정 |
| G2 사전 | 값·약·표기가 모두 사전과 `phrases.csv`에 있음 | 실제 값이 원인이면 환자 제외 + 넘길 목록 |
| G3 범위 | 침윤성, 여성, DCIS·남성·임신 아님 | 환자 제외 |
| G4 일관성 | V4 관계 규칙 통과 | 합성 칸이면 생성기 수정, 실제 칸이면 환자 제외 |
| G5 경계 거리 | 합성 수치가 §4.4 구간 밖 | 생성기 수정 |
| G6 봉투 | 새 (칸, 정규값)·(칸, 표기) 조각이 기존 가상 차트·TCGA 차트에 있었음 | 보고하고 뺀다 |
| G7 시험 실행 | B `assess`와 `lines.annotate`가 오류 없이 돌고 합성 칸 때문에 `unknown`이 없음, 입력 모듈 규칙 단계에 정답 후보를 넣으면 정답이 다시 나옴 | 원인을 생성기 / 실제 값으로 나눠 처리 |

### 11.3 넘길 목록

`data/virtual_hospital/reports/handoff_candidates.csv`: 실제 값 때문에 관문을 못 넘은 환자와 이유 (2026-11-16부터 0명). 처방 모듈을 바꿀지는 팀이 정한다.

## 12. 약관과 공개 범위

- BCNB 약관은 원본과 수정본의 재배포를 금지한다. BCNB 값이 들어간 기록·차트·정답·통계와 BCNB 이미지에서 나온 썸네일·히트맵·타일 점수·주석은 모두 `data/virtual_hospital/local/`(git 제외)에만 둔다. 가상 병원 DB 파일도 BCNB 값을 담으므로 git에 넣지 않는다.
- Thennavan 2021 Data S2(CC BY-NC-ND 4.0) 원본도 `local/`에만.
- 차트 글은 로컬 모델에서만 처리한다 (외부 API 금지). BCNB 차트를 팀 GPU 서버로 보내는 것은 괜찮다 (2026-11-18 사용자 확인).

## 14. 정할 것

| 항목 | 메모 |
|---|---|
| 모듈 1~3 결과가 처방 모듈에 들어갈 자리 | 지금 스키마에 없다 (PROJECT.md는 v0.2). 예: 화면 1의 모듈 3 불일치 배지, 모듈 1 → Oncotype 권고. 공용 스키마라 4명 검토 |
| 모듈 결과 형식 (§10.7) | 모듈 1·2·3·4-B가 같은 형식을 내야 히트맵을 한 방식으로 그린다. 팀 합의 필요 |
| 히트맵 그리는 법 | 정규화, 임계값, 색표, 상위 k |
| 합성 재발 | TCGA 실제 마지막 추적일 이후에만 합성하면 모순이 없다. 하면 `synthetic`으로 표시하고 모듈 1 평가에는 쓰지 않는다 |
| 국소 재발·전이 부위 'other' | 재발 갈래에서 뺀 환자를 되살릴지 ([progress.md](progress.md) "남은 것") |
