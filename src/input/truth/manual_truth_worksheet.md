# 정답 직접 작성 작업표

> 담당 A · 2026-10-15 · 대상 4명 · 기준: 스키마 `0.1-draft6`, 규칙 `src/input/tcga_mapping.md`
>
> draft6(2026-10-16) 계산 칸인 `treatment_history[].line`·`endocrine_line`·`chemo_line`과 `fields.deemed_lines`는 직접 쓰지 않는다. 비교 테스트에서 빼고, 계산은 `tests/input/test_lines.py`에서 검사한다. `recurrence.recurrence_day`(첫 재발일)는 원본 열로 직접 채운다 (tcga_mapping.md §3.7).

## 1. 왜 직접 쓰나

정답 생성기(`src/input/truth/tcga_truth.py`)는 규칙 문서를 코드로 옮긴 것이다. 코드가 문서를 잘못 옮겼거나, 문서 규칙 자체가 모호해도 생성기 테스트만으로는 알 수 없다. 사람이 원본을 보고 직접 쓴 정답과 비교해야 독립적으로 확인할 수 있다.

## 2. 대상 환자

범주마다 정답 규칙이 쓰는 원본 열이 가장 많이 채워진 환자다. 같으면 투약 항목 수, 검출된 변이 수가 많은 환자를 골랐다.

| 범주 | 환자 | 병기 | 확인할 규칙 |
|---|---|---|---|
| 조기 | TCGA-AO-A03N | IIB | 투약 13건, 국소 재발(수술 없음), PIK3CA 변이, PTEN 결실·PALB2 증폭 |
| 국소 진행성 | TCGA-A2-A25E | IIIA | HER2 2+ / FISH Equivocal → unknown, trastuzumab 47주기, 국소 재발 후 수술 |
| 전이성 (진단 시 IV기) | TCGA-A2-A0SV | IV | 전이 기준일 0 → 모든 투약 metastatic, 진단 시 뼈 전이 |
| 전이성 (원격 전이 재발) | TCGA-A2-A0EW | IIIC | 1,353일째 뼈 전이, 전이 전후 setting, anthracycline 용량 범위값 |

## 3. 작성 순서

1. **빈 틀 열기**: `tests/input/manual_truth/<환자ID>.todo.json`. 키 구조만 있고 값은 모두 `"TODO"`다. 생길 수 있는 칸을 모두 넣어 두었으므로, 이 환자에게 해당 없는 칸은 지운다 (예: 재발이 없으면 `recurrence.surgery`).
2. **원본 보기**: `data/tcga_brca/merged/tcga_brca_merging_cropped.csv`에서 환자 행을 연다 (엑셀이나 VS Code). 열 뜻은 `tcga_brca_merging_cropped_columns.txt`. 아래 표의 "원본 열 = 값"에도 같은 값을 옮겨 두었다.
3. **규칙대로 채우기**: 칸마다 `tcga_mapping.md`의 해당 절, 표준값은 `data/dictionaries/field_vocab.csv`, 값 모양은 `schema_fields.md`와 `patient_state_structure.md`를 본다.
   - 아래 표의 **"생성기가 넣은 값" 열은 가린 채** 먼저 채우는 것을 권한다. 미리 보면 같은 실수를 따라 하게 된다.
   - `"TODO"`를 남기면 스키마 검사에서 실패하므로 빠뜨린 칸을 찾을 수 있다.
4. **이름 바꾸기**: 다 쓰면 `<환자ID>.todo.json` → `<환자ID>.json`.
5. **비교 실행** (team_project 폴더에서):

```bash
python -m pytest tests/input/test_manual_truth.py
```

   스키마 오류가 있으면 먼저 알려주고, 통과하면 생성기 결과와 칸별로 비교해 다른 칸을 모두 보여준다.

6. **다른 칸 처리**: 셋 중 하나다.

| 원인 | 처리 |
|---|---|
| 내가 규칙을 잘못 적용함 | 직접 쓴 정답을 고친다 |
| 생성기가 규칙과 다르게 동작함 | `tcga_truth.py`를 고친다 (버그) |
| 규칙이 모호하거나 빠짐 | `tcga_mapping.md`에 규칙을 정하고, 코드와 테스트 건수를 함께 고친다 |

7. 4명이 모두 일치하면, 이 4개 파일이 **사람이 확인한 정답**이 된다. 이후 생성기를 고칠 때마다 이 테스트가 같이 돈다.

## 4. 작성 중 특히 확인할 곳

작업표를 만들면서 보인, 규칙이 실제 임상 의미와 어긋날 수 있는 곳이다. 직접 쓰면서 규칙대로 둘지 판단해 주세요.

| 환자 | 칸 | 생성기 결과 | 확인할 점 |
|---|---|---|---|
| TCGA-AO-A03N | `treatment_history` #8~12 setting | 모두 `adjuvant` | 1,645일째 국소 재발(재발 후 수술 NO) 이후 시작한 tesetaxel·paclitaxel·gemcitabine·vinorelbine·denosumab도 `adjuvant`다. setting 규칙은 전이 기준일만 보기 때문이다. 국소 재발 후 수술 없이 한 항암은 보조요법이 아닐 수 있다 |
| TCGA-AO-A03N | `molecular.mutations.PTEN`, 보고서 | PTEN `not_detected`, 보고서에 "PTEN deep deletion"과 "PTEN: 검출되지 않음"이 함께 | `molecular.mutations`는 점 변이만 본다. 깊은 결실(기능 소실)은 보고서 문장에만 있다. PTEN 소실은 capivasertib 대상 판단에 쓰이므로 B가 놓칠 수 있다 |
| TCGA-AO-A03N | `treatment_history` #0~2 | AC와 paclitaxel이 같은 기간(55~153일), 각각 4주기 | 원본 기록 그대로다. 보통 AC 후 paclitaxel 순차 요법이다 |
| TCGA-A2-A0EW | `positive_ln_count.raw` | `"26/None"` | 검사 림프절 수가 없을 때 raw에 `None`이 들어간다. `"26/[Not Available]"`이 자연스럽다 |
| TCGA-A2-A0EW | liposomal doxorubicin `cycles` | 치료 이력은 4 (추정), anthracycline 용량은 `No value` | 용량 칸은 기록값만 쓰는 규칙(§3.7a)이라 정상이다 |
| TCGA-A2-A0SV | zoledronic acid | `metastatic`, 7주기 | 골 보호제도 투약 기록이라 치료 이력에 들어간다 |

## 5. 환자별 작업표

각 표의 "생성기가 넣은 값"은 비교용이다. 먼저 직접 채운 뒤 맞춰 본다.

## 조기 (진단 시 I~II기): TCGA-AO-A03N

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전 (`field_vocab.csv`) | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N1a<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N1a", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIB | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIB"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 2<br>`gdc_lymph_nodes_examined_count` = 19 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" | `{"positive": 2, "examined": 19}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록 | `"[Not Applicable]"` |
| stage.operable | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 70-79% | §3.3 구간 → [최소, 최대], 판정 → 사전. 점수 열은 쓰지 않음 | `{"range": [70, 79], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 1-9% | §3.3 ER과 같음. 저발현 없음 | `{"range": [1, 9], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 0<br>`gdc_her2_status_by_ihc` = Negative<br>`gdc_her2_fish_status` = [Not Evaluated] | §3.3 score + result. 보정 대상 아님 (score와 판정 그대로) | `{"score": "0", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = [Not Evaluated] | §3.3 Positive → amplified, Negative → not_amplified, [Not Evaluated] → not_done | `{"status": "not_done"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 59 | 정수 | `59` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = locoregional<br>`nte_types` = Locoregional Disease | §3.7 recurrence_status 그대로 | `"locoregional"` |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = NO | §3.7 재발이 있을 때만. YES가 하나라도 있으면 yes | `"no"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = 1645<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | `"no"` |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = E542K (Missense_Mutation, VAF 0.239) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["E542K"]}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (13건 → 정답 13건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | cyclophosphamide [Chemotherapy] d55~d153 | 55 / 153 / 4 | cyclophosphamide | adjuvant | 55 / 153 / 98 | 4 (recorded, 간격 33일 derived) | unknown |
| 1 | doxorubicin [Chemotherapy] d55~d153 | 55 / 153 / 4 | doxorubicin | adjuvant | 55 / 153 / 98 | 4 (recorded, 간격 33일 derived) | unknown |
| 2 | paclitaxel [Chemotherapy] d55~d153 | 55 / 153 / 4 | paclitaxel | adjuvant | 55 / 153 / 98 | 4 (recorded, 간격 33일 derived) | unknown |
| 3 | anastrozole [Hormone Therapy] d207~d449 | 207 / 449 / [Not Available] | anastrozole | adjuvant | 207 / 449 / 242 | null | unknown |
| 4 | letrozole [Hormone Therapy] d450~d820 | 450 / 820 / [Not Available] | letrozole | adjuvant | 450 / 820 / 370 | null | unknown |
| 5 | exemestane [Hormone Therapy] d821~d1007 | 821 / 1007 / [Not Available] | exemestane | adjuvant | 821 / 1007 / 186 | null | unknown |
| 6 | tamoxifen [Hormone Therapy] d1007~? | 1007 / [Not Available] / [Not Available] | tamoxifen | adjuvant | 1007 / None / None | null | unknown |
| 7 | fulvestrant [Hormone Therapy] d1639~d1667 | 1639 / 1667 / 3 | fulvestrant | adjuvant | 1639 / 1667 / 28 | 3 (recorded, 간격 14일 derived) | unknown |
| 8 | tesetaxel [Chemotherapy] d1699~d1762 | 1699 / 1762 / 4 | tesetaxel | adjuvant | 1699 / 1762 / 63 | 4 (recorded, 간격 21일 derived) | unknown |
| 9 | paclitaxel [Chemotherapy] d1814~d1828 | 1814 / 1828 / 2 | paclitaxel | adjuvant | 1814 / 1828 / 14 | 2 (recorded, 간격 14일 derived) | unknown |
| 10 | gemcitabine [Chemotherapy] d1835~d1842 | 1835 / 1842 / 2 | gemcitabine | adjuvant | 1835 / 1842 / 7 | 2 (recorded, 간격 7일 derived) | unknown |
| 11 | vinorelbine [Chemotherapy] d1857~? | 1857 / [Not Available] / 16 | vinorelbine | adjuvant | 1857 / None / None | 16 (recorded, 간격 21일 standard) | unknown |
| 12 | denosumab [Bone-modifying Agent] d1989~? | 1989 / [Not Available] / 2 | denosumab | adjuvant | 1989 / None / None | 2 (recorded, 간격 None일 None) | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.
cycles 규칙: 기록 있음 + 2주기 이상 + 기간 있음 → 간격 = 기간 ÷ (주기 − 1) (derived) / 기록 없음 → 기간 ÷ 사전 기본 간격 + 1 (estimated) / 매일 먹는 약 → null.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 1 | doxorubicin | 60 / mg/m2 / [Not Available] / [Not Available] / 4 | `{"value": 60.0, "unit": "mg/m2"}` | `"No value"` | 4 (recorded) |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PIK3CA p.E542K (Missense_Mutation), VAF 23.9%. PTEN deep deletion. PALB2 amplification. ERBB2, ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 국소 진행성 (진단 시 III기): TCGA-A2-A25E

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전 (`field_vocab.csv`) | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N2a<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N2a", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIIA | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIIA"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 6<br>`gdc_lymph_nodes_examined_count` = 10 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" | `{"positive": 6, "examined": 10}` |
| stage.disease_extent | `stage_disease_extent` = locally_advanced | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"locally_advanced"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = NO<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록 | `"[Not Applicable]"` |
| stage.operable | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 80-89% | §3.3 구간 → [최소, 최대], 판정 → 사전. 점수 열은 쓰지 않음 | `{"range": [80, 89], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 60-69% | §3.3 ER과 같음. 저발현 없음 | `{"range": [60, 69], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Equivocal | §3.3 score + result. 2+ 또는 Equivocal이라 FISH로 result 보정 | `{"score": "2+", "result": "unknown"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Equivocal | §3.3 Positive → amplified, Negative → not_amplified, [Not Evaluated] → not_done | `{"result": "equivocal", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 34 | 정수 | `34` |
| patient.menopausal_status | `gdc_menopause_status` = Pre (<6 months since LMP AND no prior bilateral ovariectomy AND not on estrogen replacement) | §3.5 사전 (Post → postmenopausal 등) | `"premenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = locoregional<br>`nte_types` = Locoregional Recurrence | §3.7 recurrence_status 그대로 | `"locoregional"` |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = YES | §3.7 재발이 있을 때만. YES가 하나라도 있으면 yes | `"yes"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = 2989<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | `"no"` |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (7건 → 정답 7건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | cyclophosphamide [Chemotherapy] d67~d136 | 67 / 136 / 4 | cyclophosphamide | adjuvant | 67 / 136 / 69 | 4 (recorded, 간격 23일 derived) | unknown |
| 1 | doxorubicin [Chemotherapy] d67~d136 | 67 / 136 / 4 | doxorubicin | adjuvant | 67 / 136 / 69 | 4 (recorded, 간격 23일 derived) | unknown |
| 2 | paclitaxel [Chemotherapy] d158~d242 | 158 / 242 / 12 | paclitaxel | adjuvant | 158 / 242 / 84 | 12 (recorded, 간격 8일 derived) | unknown |
| 3 | trastuzumab [HER2-targeted Therapy] d250~d601 | 250 / 601 / 47 | trastuzumab | adjuvant | 250 / 601 / 351 | 47 (recorded, 간격 8일 derived) | unknown |
| 4 | tamoxifen [Hormone Therapy] d334~d2155 | 334 / 2155 / [Not Available] | tamoxifen | adjuvant | 334 / 2155 / 1821 | null | unknown |
| 5 | goserelin [Hormone Therapy] d2380~? | 2380 / [Not Available] / [Not Available] | goserelin | adjuvant | 2380 / None / None | null | unknown |
| 6 | anastrozole [Hormone Therapy] d3055~? | 3055 / [Not Available] / [Not Available] | anastrozole | adjuvant | 3055 / None / None | null | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.
cycles 규칙: 기록 있음 + 2주기 이상 + 기간 있음 → 간격 = 기간 ÷ (주기 − 1) (derived) / 기록 없음 → 기간 ÷ 사전 기본 간격 + 1 (estimated) / 매일 먹는 약 → null.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 1 | doxorubicin | 90 / mg / 360 / mg / 4 | `{"value": 90.0, "unit": "mg"}` | `{"value": 360.0, "unit": "mg"}` | 4 (recorded) |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 전이성 (진단 시 IV기): TCGA-A2-A0SV

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전 (`field_vocab.csv`) | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N2a<br>`gdc_ajcc_metastasis_pathologic_pm` = M1<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N2a", "m": "M1", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IV | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IV"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 8<br>`gdc_lymph_nodes_examined_count` = 9 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" | `{"positive": 8, "examined": 9}` |
| stage.disease_extent | `stage_disease_extent` = metastatic | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"metastatic"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M1<br>`gdc_metastasis_site` = Bone<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록 | `["bone"]` |
| stage.operable | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 90-99% | §3.3 구간 → [최소, 최대], 판정 → 사전. 점수 열은 쓰지 않음 | `{"range": [90, 99], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 10-19% | §3.3 ER과 같음. 저발현 없음 | `{"range": [10, 19], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 2+ 또는 Equivocal이라 FISH로 result 보정 | `{"score": "2+", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 63 | 정수 | `63` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = unknown<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"unknown"` |
| recurrence.metastasis_day | `metastasis_dx_days` = 0 | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | `0` |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 재발이 있을 때만. YES가 하나라도 있으면 yes | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = 0 | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = H64_Y65del (In_Frame_Del, VAF 0.444) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["H64_Y65del"]}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (4건 → 정답 4건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | zoledronic acid [Bone-modifying Agent] d65~d253 | 65 / 253 / 7 | zoledronic acid | metastatic | 65 / 253 / 188 | 7 (recorded, 간격 31일 derived) | unknown |
| 1 | anastrozole [Hormone Therapy] d79~d168 | 79 / 168 / [Not Available] | anastrozole | metastatic | 79 / 168 / 89 | null | unknown |
| 2 | fulvestrant [Hormone Therapy] d170~d223 | 170 / 223 / 5 | fulvestrant | metastatic | 170 / 223 / 53 | 5 (recorded, 간격 13일 derived) | unknown |
| 3 | capecitabine [Chemotherapy] d304~? | 304 / [Not Available] / [Not Available] | capecitabine | metastatic | 304 / None / None | null | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 0) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.
cycles 규칙: 기록 있음 + 2주기 이상 + 기간 있음 → 간격 = 기간 ÷ (주기 − 1) (derived) / 기록 없음 → 기간 ÷ 사전 기본 간격 + 1 (estimated) / 매일 먹는 약 → null.

### anthracycline 용량: administered = `negative`

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PTEN p.H64_Y65del (In_Frame_Del), VAF 44.4%. ERBB2, ESR1, PIK3CA, AKT1, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 전이성 (원격 전이 재발): TCGA-A2-A0EW

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Lobular Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = ILC | §3.1 조직형 이름 → 사전 (`field_vocab.csv`) | `"ILC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T1b<br>`gdc_ajcc_nodes_pathologic_pn` = N3a<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T1b", "n": "N3a", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIIC | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIIC"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 26<br>`gdc_lymph_nodes_examined_count` = [Not Available] | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" | `{"positive": 26, "examined": "[Not Available]"}` |
| stage.disease_extent | `stage_disease_extent` = locally_advanced | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"locally_advanced"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록 | `"[Not Applicable]"` |
| stage.operable | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 90-99% | §3.3 구간 → [최소, 최대], 판정 → 사전. 점수 열은 쓰지 않음 | `{"range": [90, 99], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 10-19% | §3.3 ER과 같음. 저발현 없음 | `{"range": [10, 19], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 0<br>`gdc_her2_status_by_ihc` = Negative<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 보정 대상 아님 (score와 판정 그대로) | `{"score": "0", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 53 | 정수 | `53` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = distant<br>`nte_types` = Distant Metastasis | §3.7 recurrence_status 그대로 | `"distant"` |
| recurrence.metastatic_sites | `nte_sites` = Bone<br>`nte_sites_other` = (빈칸) | §3.7 distant일 때만. 부위 사전, Other → other: 기타 내용 | `["bone"]` |
| recurrence.metastasis_day | `metastasis_dx_days` = 1353 | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | `1353` |
| recurrence.surgery | `nte_surgery` = NO | §3.7 재발이 있을 때만. YES가 하나라도 있으면 yes | `"no"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = 1353 | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = Q546R (Missense_Mutation, VAF 0.226) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["Q546R"]}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (12건 → 정답 12건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | doxorubicin [Chemotherapy] d85~d127 | 85 / 127 / 4 | doxorubicin | adjuvant | 85 / 127 / 42 | 4 (recorded, 간격 14일 derived) | unknown |
| 1 | cyclophosphamide [Chemotherapy] d85~d127 | 85 / 127 / 4 | cyclophosphamide | adjuvant | 85 / 127 / 42 | 4 (recorded, 간격 14일 derived) | unknown |
| 2 | paclitaxel [Chemotherapy] d141~d184 | 141 / 184 / 4 | paclitaxel | adjuvant | 141 / 184 / 43 | 4 (recorded, 간격 14일 derived) | unknown |
| 3 | anastrozole [Hormone Therapy] d221~d812 | 221 / 812 / [Not Available] | anastrozole | adjuvant | 221 / 812 / 591 | null | unknown |
| 4 | letrozole [Hormone Therapy] d813~d903 (Complete Response) | 813 / 903 / [Not Available] | letrozole | adjuvant | 813 / 903 / 90 | null | CR |
| 5 | anastrozole [Hormone Therapy] d904~d1001 (Complete Response) | 904 / 1001 / [Not Available] | anastrozole | adjuvant | 904 / 1001 / 97 | null | CR |
| 6 | exemestane [Hormone Therapy] d1002~d1365 (Clinical Progressive Disease) | 1002 / 1365 / [Not Available] | exemestane | adjuvant | 1002 / 1365 / 363 | null | PD |
| 7 | zoledronic acid [Bone-modifying Agent] d1158~d1422 (Clinical Progressive Disease) | 1158 / 1422 / [Not Available] | zoledronic acid | adjuvant | 1158 / 1422 / 264 | null | PD |
| 8 | fulvestrant [Hormone Therapy] d1366~d1562 (Clinical Progressive Disease) | 1366 / 1562 / [Not Available] | fulvestrant | metastatic | 1366 / 1562 / 196 | 8 (estimated, 간격 28일 standard) | PD |
| 9 | denosumab [Bone-modifying Agent] d1425~d1718 (Clinical Progressive Disease) | 1425 / 1718 / [Not Available] | denosumab | metastatic | 1425 / 1718 / 293 | null | PD |
| 10 | tamoxifen [Hormone Therapy] d1618~d1722 (Clinical Progressive Disease) | 1618 / 1722 / [Not Available] | tamoxifen | metastatic | 1618 / 1722 / 104 | null | PD |
| 11 | liposomal doxorubicin [Chemotherapy] d1696~d1787 (Clinical Progressive Disease) | 1696 / 1787 / [Not Available] | liposomal doxorubicin | metastatic | 1696 / 1787 / 91 | 4 (estimated, 간격 28일 standard) | PD |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 1353) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.
cycles 규칙: 기록 있음 + 2주기 이상 + 기간 있음 → 간격 = 기간 ÷ (주기 − 1) (derived) / 기록 없음 → 기간 ÷ 사전 기본 간격 + 1 (estimated) / 매일 먹는 약 → null.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 0 | doxorubicin | 115-116 / mg / 463 / mg / 4 | `{"value": 116.0, "unit": "mg"}` | `{"value": 463.0, "unit": "mg"}` | 4 (recorded) |
| 11 | liposomal doxorubicin | [Not Available] / [Not Available] / [Not Available] / [Not Available] / [Not Available] | `"No value"` | `"No value"` | No value |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PIK3CA p.Q546R (Missense_Mutation), VAF 22.6%. ERBB2, ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

