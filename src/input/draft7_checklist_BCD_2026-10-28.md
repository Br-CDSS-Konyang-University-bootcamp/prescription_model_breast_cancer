# patient_state draft7 후보 칸: B·C·D 확인 체크리스트

> 작성 A · 2026-10-28 · 기준 브랜치 `feat/input-pipeline` (`9d1aa57`) · 받는 사람 B (`src/biomarker/`, `src/recommend/`), C (`src/rag/`), D (`src/reimbursement/`)

가상 차트로 평가하면서 `schemas/patient_state.json`에 선택 칸을 더했다 (draft7 후보, 4명 검토 전). 칸 정의는 [schema_fields.md](schema_fields.md)의 "draft6 → draft7 후보 변경 요약", 스키마 변경 이력은 [schemas/README.md](../../schemas/README.md) §3에 있다. 이 문서는 그 칸들을 **누가 어디서 읽어야 하는지**와 **지금 코드가 읽고 있는지**를 조원별로 나눈 것이다.

- "지금 코드"는 2026-10-28 `feat/input-pipeline`에서 찾아본 결과다. 담당자가 다르게 구현했으면 고쳐 적어 주세요
- 흐름: A의 `patient_state` → 의사가 화면 1에서 `schemas/confirmed_state.json` 항목으로 확정 → 2단계(C 검색, D 급여, B 추천)는 확정값만 읽는다 ([handoff_confirmed_state_to_B.md](handoff_confirmed_state_to_B.md)). 지금 B의 `conditions_eval.py`와 D의 `conditions.py`는 `patient_state` 경로를 직접 읽는다. 둘 중 어느 쪽을 기준으로 할지는 §5에서 정한다
- 시험할 가상 차트: `tests/fixtures/virtual_charts/<사례>/expected/patient_state.json`. VC-0130 이후는 보류 세트라 규칙을 맞출 때 쓰지 않는다 ([virtual_patient_cases.md](virtual_patient_cases.md) §8)

## 0. 한눈에

| 칸 (patient_state) | confirmed_state 항목 | B | C | D | 지금 코드 |
|---|---|---|---|---|---|
| `molecular.germline.{BRCA1, BRCA2, PALB2}` (1순위), 없으면 `mutations`의 같은 유전자 (2순위) | `markers.gBRCA` | ✔ 읽기 | ✔ (B 표지 사용) | ✔ (B 표지 사용) | **B가 안 읽음 (양성이 not_recorded로 나옴)** |
| `stage.clinical_size_mm`, `pathologic_size_mm` | `stage.size_mm` (basis c/p) | ✔ 급여 조건 | | ✔ 급여 조건 | **아무도 안 읽음** |
| `stage.yptnm` | `stage.t`·`stage.n` 설명 | ✔ | ✔ | ✔ | **아무도 안 읽음** |
| `patient.cardiac_history`, `lvef_percent` | `cardiac_risk` | ✔ 급여 조건 | | ✔ 급여 조건 | **B·D 모두 "칸 없음"으로 처리** |
| `patient.mediastinal_radiation` | `mediastinal_radiation` | ✔ | | ✔ | **B·D 모두 "칸 없음"으로 처리** |
| `patient.height_cm`, `weight_kg` | `anthracycline_cumulative`, `prior_regimens.doses` | ✔ (mg → mg/m²) | | ✔ | **안 읽음 (mg/m²만 계산)** |
| `imaging_findings[]` | `bone_metastasis_imaging` | ✔ | | ✔ | **안 읽음 (전이 부위 목록으로 판정)** |
| `treatment_history[].ongoing` | `prior_regimens.ongoing` | | | ✔ | A가 `at_index`에 반영해 간접 사용 |
| `treatment_history[].doses[]` | `prior_regimens.doses` | ✔ | | ✔ | 안 읽음 (`anthracycline_drug_dose` 사용 중). A는 2026-10-28부터 채움 (가상 차트 투약 줄 95개, 규칙 `schema_fields.md` §8) |
| `patient.visceral_crisis` | `visceral_crisis` | | ✔ 검색 질의 | | C 읽음 |
| `patient.comorbidities` | `contraindicated_classes` | ✔ 추천 | ✔ | | **아무도 안 읽음** |
| `at_index.age`, `recent_therapy_28d` | `age_at_index`, `recent_therapy_28d` | ✔ | | ✔ | B·D 읽음 |
| `patient.menopausal_basis` 새 값 | `menopausal_status` 근거 | | ✔ | ✔ | 값만 늘어남 (확인만) |

## 1. B (`src/biomarker/`, `src/recommend/`)

### 1.1 바이오마커 (`BM1_ER,PR,HER2,Ki_67,subtype.py`)

- [ ] **gBRCA는 생식세포 칸을 먼저 쓴다 (2026-10-28 A 결정, PROJECT.md §14).** 유전자마다 (BRCA1, BRCA2, PALB2)
  1. **1순위:** `molecular.germline.<유전자>` (생식세포 검사)에 결과가 있으면 (`status: present`) 그 결과로 `gBRCA1`·`gBRCA2`·`gPALB2` 레코드를 만든다
  2. **2순위:** 생식세포 결과가 없으면 (칸이 없거나 `present`가 아니면) `molecular.mutations.<유전자>` (체세포·종양 조직·cfDNA)의 결과를 쓴다
  - 지금 코드는 `mutations`만 읽어서 (801·921행) 생식세포 결과를 버린다. 2026-10-28 `assess()` 실행 결과: VC-0116 (생식세포 BRCA1 병원성) → `gBRCA1: not_recorded`, VC-0119 (BRCA2 병원성) → `gBRCA2: not_recorded`, 보류 VC-0135 → `gBRCA1: not_recorded`. 양성이 기록 없음으로 바뀌어 PARP 억제제 판정이 빠진다
  - 시험: VC-0116·0119 (생식세포 양성), VC-0115·0117 (생식세포 음성), VC-0102 (생식세포 칸 없음 + 종양 NGS 미검출 → 2순위), 보류 VC-0135·0140, VC-0115-g21
  - B가 정할 것: 생식세포가 `not_done`(미시행)이라 2순위를 쓸 때도 생식세포 검사 권고(BM-4)를 그대로 내는지, 레코드 근거에 어느 칸을 썼는지 적는 방식
- [ ] 생식세포 검사가 `not_recorded`일 때 검사 권고(BM-4)를 내지 않는지 (권고는 `not_done`일 때만, PROJECT.md §14). 보류 VC-0132
- [ ] ER-low → HR+ (`ER_LOW_IS_HR_POSITIVE`) 확인만. 보류 VC-0142

### 1.2 급여 조건 판정 (`src/recommend/conditions_eval.py`)

- [ ] **심장 위험·종격동 방사선.** 지금 `return None   # cardiac_history, mediastinal_radiation 등 환자 JSON에 칸이 없는 조건` (`conditions_eval.py` 끝). `patient.cardiac_history`·`lvef_percent`·`mediastinal_radiation`을 읽는다. 값이 `not_recorded`면 지금처럼 `None` (→ `covered_conditions_unverified`). 시험: VC-0127 (yes·yes), VC-0104
- [ ] **누적 용량 mg → mg/m².** 지금 `cumulative_dose_mg_m2`는 단위가 mg/m²가 아니면 `None`. mg 표기면 `height_cm`·`weight_kg`로 체표면적을 구해 바꾼다 (PROJECT.md §12). 체표면적 공식(Mosteller 등)을 정해 적는다. 시험: VC-0127 (doxorubicin 96mg × 3, 158 cm / 58 kg)
- [ ] **골전이 영상 입증.** 지금 `bone_metastasis`는 전이 부위 목록에 bone이 있는지만 본다. 공고 조건은 "영상으로 골전이 입증"이라 `imaging_findings[]`에 `bone` + `certainty: confirmed`가 있는지로 본다 (confirmed_state `bone_metastasis_imaging`). 시험: VC-0108, 보류 VC-0143 (PET 의심 + 생검 확인)
- [ ] **치료 시기에 맞는 병기·크기.** 선행요법 판정은 cT·`clinical_size_mm`, 수술 먼저 보조는 pT·pN·`pathologic_size_mm`·`positive_ln_count`, 선행 뒤 보조는 `yptnm`·`neoadjuvant_response`. 그 칸이 비면 다른 병기로 대신하지 않고 "알 수 없음". 지금은 pT가 없으면 cT로 대신하고 ypT·ypN은 읽지 않는다. 자세한 내용: §4
- [ ] `treatment_history[].doses[]`를 쓸지 정하기 (`anthracycline_drug_dose`는 당분간 유지)
- [ ] 차수: A가 `treatment_history[].line`·`endocrine_line`·`chemo_line`과 `deemed_lines`를 계산해 넣는다. B가 따로 다시 계산하지 않고 이 값을 읽는지

### 1.3 추천 (`src/recommend/`)

- [ ] `comorbidities` → `contraindicated_classes` (의사가 약 계열로 확정). 금기 계열을 추천에서 빼거나 경고로 내는지. 지금 참조 없음. 시험: VC-0108 (CKD 3a), 보류 VC-0137 (CKD 3b)
- [ ] 스키마에 아직 칸이 없는 의사 판단 (항암 불가, 내분비 적합, 임신)은 `confirmed_state`에서 받을지 정하기 (§5)

## 2. C (`src/rag/`)

- [ ] `visceral_crisis`: 이미 질의에 쓴다 (`retrieve.py`). 확인만. 시험: VC-0126
- [ ] `contraindicated_classes`: 검색 갈래(ESMO M05·M35 "내분비 단독" 등)에 쓸지 정하기. 지금 참조 없음
- [ ] `markers.gBRCA`: B가 생식세포 칸으로 gBRCA를 만들기 시작하면 C의 태그(`gBRCA`, `sBRCA`) 대응이 그대로 맞는지
- [ ] 선행요법 뒤 잔존(`yptnm`, `pcr`)으로 EBC 그림 6·7의 잔존/pCR 갈래를 고르는지. 지금 `pcr`은 읽고 `yptnm`은 안 읽는다
- [ ] 병기 범주: A가 2026-10-28부터 `disease_extent`를 TNM으로 계산한다 (선행요법 환자는 cTNM, 수술 먼저면 pTNM, ypTNM은 쓰지 않음, `e39aa56`). C의 검색 필터가 `stage.group`(차트에 적힌 병기군)과 `disease_extent`(계산값) 중 무엇을 쓰는지

## 3. D (`src/reimbursement/`)

### 3.1 조건 정의 (`conditions.py` `FIELDS`)

- [ ] **`cardiac_history`·`mediastinal_radiation`.** 지금 설명이 `(없음: 이번 모델 제외, PROJECT.md §12) 늘 알 수 없음`이다. 2026-10-22에 칸을 추가해 이 제외 조항을 없앴다 (PROJECT.md §12). 경로를 `patient_state.fields.patient.cardiac_history.value`·`mediastinal_radiation.value`로 바꾼다. 4나-19 "심장 위험요소"의 정의(LVEF 기준 포함?)를 공고 원문으로 적는다
- [ ] **크기 조건.** '직경 > 2㎝', '1cm 이상', '≥ 5 cm'를 T 범주로 바꾸지 말고 cm 그대로 둔다. 정확히 5.0 cm는 T2인데 "≥5cm"를 만족한다. 경로: 선행은 `stage.clinical_size_mm`, 보조는 `stage.pathologic_size_mm` (mm)
- [ ] **조건마다 어느 병기를 보는지** (임상 / 병리 / 선행 뒤). 지금 `t_stage`는 `ctnm`·`ptnm`을 구분하지 않고, `ln_status`는 `ptnm.n`만 읽어 선행요법 환자를 판정하지 못한다. 자세한 내용: §4
- [ ] **골전이 영상 입증.** 지금 `bone_metastasis`는 `metastatic_sites`에 bone이 있는지. "영상으로 입증"은 `imaging_findings[]`의 `bone` + `confirmed`로 본다
- [ ] 누적 용량 조건이 mg/m²만 받는지, mg + 키·몸무게를 받는지 B와 맞추기
- [ ] `doses[]`를 쓰는 조건 (예: cisplatin 1회·총 용량)이 있으면 경로 추가

### 3.2 급여 판정 확인 (가상 차트 기대 결과)

- [ ] 보류 세트 `scenario.md`의 D 행 (⚑D) 확인. 특히 2-20 "1cm 초과"에서 10 mm, 4가-6 "이전 면역관문억제제"에 선행·보조 pembrolizumab이 드는지, `DEEM-ANTHRA-TAXANE` met이 4가 "1차" 판정에 쓰이는지 ([virtual_patient_cases.md](virtual_patient_cases.md) §9)

## 4. 치료 시기별 병기 (B·D 공통)

| 판정 시기 | 보는 값 (`patient_state`) | 조건 예 |
|---|---|---|
| 선행요법, 수술 전 | `stage.ctnm`, `stage.clinical_size_mm`, 임상 병기군 | '직경 > 2㎝', 'stage Ⅱ∼Ⅲ', '염증성' |
| 수술 먼저 → 보조 | `stage.ptnm`, `stage.pathologic_size_mm`, `stage.positive_ln_count` | '1cm 이상', '≥ 5 cm', '림프절 양성', '4개 이상' |
| 선행요법 뒤 보조 | `stage.yptnm` (`residual_size_mm`, `positive_ln`, `examined_ln`), `neoadjuvant_response.pcr`·`rcb` | 'pCR 미도달', '잔존 침윤암' |

- 그 시기의 칸이 비면 다른 병기로 대신하지 않고 "알 수 없음"으로 둔다
- 공고가 "처음 병기"를 보는 조건(선행 뒤 보조에서 진단 시 림프절 양성 등)은 조건마다 적는다
- `stage.group`에는 차트에 적힌 병기군이 그대로 있다 (예후 병기일 수 있음). 임상·병리 구분이 없어 나누려면 스키마 변경이 필요하다 (A 과제, 4명 검토)
- 시험: VC-0103·0105·0119·0120 (A 전달 글 `notes/stage_by_treatment_timing_for_B_D_2026-10-27.md`), 보류 VC-0130 (pT1a 8 mm), VC-0135 (cT1c → ypT1b)

## 5. 같이 정할 것 (4명)

| 정할 것 | 관련 |
|---|---|
| 2단계 모듈이 `confirmed_state`만 읽을지, 지금처럼 `patient_state`를 직접 읽을지 | B `conditions_eval.py`, D `conditions.py` |
| `schema_version`을 `0.1-draft7`로 올리기 (위 칸 확정) | `schemas/patient_state.json` |
| 칸이 없는 의사 판단: 항암 불가, 내분비 적합, 뇌 전이 활동성·국소 치료 적응, 소수 전이, 임신 | 보류 VC-0137, 0141, 0143, 0144, VC-0111-g20a·g20b |
| `stage.group`의 임상·병리 구분 | §4 |
