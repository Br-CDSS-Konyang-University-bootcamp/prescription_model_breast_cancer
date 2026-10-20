# 정답 직접 작성 작업표

> 담당 A · 2026-10-15 (2026-10-20 대상을 9명으로 교체) · 대상 9명 · 기준: 스키마 `0.1-draft6`, 규칙 `src/input/tcga_mapping.md`
>
> draft6(2026-10-16) 계산 칸인 `treatment_history[].line`·`endocrine_line`·`chemo_line`과 `fields.deemed_lines`는 직접 쓰지 않는다. 비교 테스트에서 빼고, 계산은 `tests/input/test_lines.py`에서 검사한다. `recurrence.recurrence_day`(첫 재발일)는 원본 열로 직접 채운다 (tcga_mapping.md §3.7).

## 1. 왜 직접 쓰나

정답 생성기(`src/input/truth/tcga_truth.py`)는 규칙 문서를 코드로 옮긴 것이다. 코드가 문서를 잘못 옮겼거나, 문서 규칙 자체가 모호해도 생성기 테스트만으로는 알 수 없다. 사람이 원본을 보고 직접 쓴 정답과 비교해야 독립적으로 확인할 수 있다.

## 2. 대상 환자

2026-10-20 교체: 규칙 갈래를 모두 덮는 최소 인원으로 골랐다. 변환기가 세는 규칙 갈래(`truth_report.txt`)에 재발 후 수술·원격 재발 전 국소 재발 갈래를 더하고, 같은 규칙을 시험하는 갈래(예: HER2 보정의 여러 점수 조합)는 하나로 묶었다. 묶은 갈래를 이 9명이 모두 덮는다. 2026-10-20 재발 여부 기록 없음 정리 뒤 `recurrence.status = unknown` 갈래는 861명 중 아무에게도 남지 않는다. 이전 대상 4명(TCGA-AO-A03N, A2-A25E, A2-A0SV, A2-A0EW)은 22개만 덮었고, A2-A25E는 크롭본에서 빠진 환자(HER2 2+ / FISH Equivocal, 판정 불가)였다.

| 환자 | 범주 | 병기 | 투약 | 이 환자가 처음 덮는 규칙 갈래 |
|---|---|---|---|---|
| TCGA-A2-A04P | 국소 진행성 (진단 시 III기), 원격 전이 재발 | IIIC | 8건 | anthracycline: positive, positive_ln_count: 양성 있음 / 검사 있음, recurrence.status = distant, stage.metastatic_sites: 전이 여부 기록 없음 + M0 → [Not Applicable], treatment.cycles: estimated/standard, treatment.cycles: null, treatment.cycles: recorded/derived, treatment.setting (유도): 나머지 → adjuvant, treatment.setting (유도): 시작일 ≥ 전이 기준일 → metastatic, 수용체 구간+판정, 원격 재발 전 국소 재발 no, 재발 후 수술 yes, 조직형 표 변환, 주기 기록 + 간격 사전값 |
| TCGA-5T-A9QA | 조기 (진단 시 I~II기) | IIA | 4건 | HER2 IHC를 FISH 음성으로 보정, TNM X → not_assessed, positive_ln_count: 둘 다 없음 → not_recorded, recurrence.status = none, 수용체 판정만, 조직형 ONCOTREE 대체 (Other·Mixed·Medullary), 진단 시 전이 부위 기록 없음 → [Not Available] |
| TCGA-AQ-A0Y5 | 국소 진행성 (진단 시 III기) | IIIA | 3건 | HER2 IHC를 FISH 양성으로 보정, anthracycline: negative, stage.metastatic_sites: 전이 여부 NO → [Not Applicable], treatment.setting (유도): 선행요법 이력 Yes + 첫 요법 → neoadjuvant |
| TCGA-C8-A137 | 조기 (진단 시 I~II기), 국소 재발 | IIB | 0건 | anthracycline: 투약 기록 없음 → No value, recurrence.status = locoregional, 림프절 수 한쪽만 없음, 재발 후 수술 no |
| TCGA-LL-A73Z | 전이성 (진단 시 IV기), 원격 전이 재발 | IV | 4건 | stage.metastatic_sites: Other, specify → 기타 부위 열 내용, 진단 시 전이 부위 목록 |
| TCGA-A1-A0SO | 조기 (진단 시 I~II기) | IIB | 0건 | her2_ihc: 점수 없는 Equivocal → score 2+, treatment: 성분명 unknown 항목 제외 |
| TCGA-AC-A2FO | 조기 (진단 시 I~II기) | IIB | 2건 | her2_ish: 'Indeterminate'는 표준값이 없어 not_recorded |
| TCGA-AR-A24L | 조기 (진단 시 I~II기), 국소 재발 | IIB | 4건 |  |
| TCGA-A8-A07R | 국소 진행성 (진단 시 III기) | IIIC | 1건 | HER2 FISH 없음 → 적힌 판정 유지 |

작업 파일 9개(`tests/input/manual_truth/<환자>.todo.json`)는 빈 틀이 아니라 **값이 채워진 초안**이다. 변환기 코드를 쓰지 않고 `tcga_mapping.md` 규칙과 크롭본 원본 값만으로 만든 별도 스크립트(Claude 작성, 2026-10-20)가 채웠다. `raw` 표기 방식은 규칙 문서에 없는 부분이라 기존 출력 형식을 따랐다. 사람이 원본과 대조해 확인한 뒤 이름을 `.json`으로 바꾼다. 초안과 변환기의 차이는 없다 (2026-10-20, 진단 시 IV기 recurrence_day 수정과 재발 여부 기록 없음 정리 반영 후).

**2026-10-20 삭제**: 초안 9개는 `fields.at_index` 추가(4명 검토 전) 뒤 변환기와 맞지 않아 지웠다 (사용자 결정). 사람이 직접 작성할 때 이 폴더(`tests/input/manual_truth/`)를 다시 만든다. 이 문서의 원본 값과 규칙 표는 그대로 쓸 수 있다. 정답 파일이 없으면 `test_manual_truth.py`는 건너뛴다.

## 3. 작성 순서

1. **초안 열기**: `tests/input/manual_truth/<환자ID>.todo.json`. 2026-10-20부터 값이 채워진 초안이다 (§2). 칸마다 원본과 규칙으로 맞는지 확인하고, 틀리면 고친다. 처음부터 직접 쓰고 싶으면 초안을 가린 채 쓰고 나서 비교한다.
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

작업표를 만들면서 보인, 규칙이 실제 임상 의미와 어긋날 수 있는 곳이다. 직접 쓰면서 규칙대로 둘지 판단해 주세요. 아래 표의 환자 중 일부(AO-A03N, A2-A0EW, A2-A0SV)는 이전 대상(2026-10-15)이지만, 같은 규칙이 다른 환자에도 적용되므로 남겨 둔다.

| 환자 | 칸 | 생성기 결과 | 확인할 점 |
|---|---|---|---|
| TCGA-LL-A73Z | `recurrence.recurrence_day` | (칸 없음) | 2026-10-20 수정: 진단 시 IV기인데 첫 재발일이 0으로 들어가던 것을 규칙(§3.7)대로 뺐다. 다른 진단 시 IV기 6명과 같아짐 |

이전 대상에서 찾은 것:

| 환자 | 칸 | 생성기 결과 | 확인할 점 |
|---|---|---|---|
| TCGA-AO-A03N | `treatment_history` #8~12 setting | 모두 `adjuvant` | 1,645일째 국소 재발(재발 후 수술 NO) 이후 시작한 tesetaxel·paclitaxel·gemcitabine·vinorelbine·denosumab도 `adjuvant`다. setting 규칙은 전이 기준일만 보기 때문이다. 국소 재발 후 수술 없이 한 항암은 보조요법이 아닐 수 있다 |
| TCGA-AO-A03N | `molecular.mutations.PTEN`, 보고서 | PTEN `not_detected`, 보고서에 "PTEN deep deletion"과 "PTEN: 검출되지 않음"이 함께 | `molecular.mutations`는 점 변이만 본다. 깊은 결실(기능 소실)은 보고서 문장에만 있다. PTEN 소실은 capivasertib 대상 판단에 쓰이므로 B가 놓칠 수 있다 |
| TCGA-AO-A03N | `treatment_history` #0~2 | AC와 paclitaxel이 같은 기간(55~153일), 각각 4주기 | 원본 기록 그대로다. 보통 AC 후 paclitaxel 순차 요법이다 |
| TCGA-A2-A0EW | `positive_ln_count.raw` | `"26/[Not Available]"` | 2026-10-19 수정: 검사 림프절 수가 없을 때 raw에 `None`이 들어가던 것을 원본 코드 `[Not Available]`로 바꿨다 |
| TCGA-A2-A0EW | liposomal doxorubicin `cycles` | 치료 이력은 4 (추정), anthracycline 용량은 `No value` | 용량 칸은 기록값만 쓰는 규칙(§3.7a)이라 정상이다 |
| TCGA-A2-A0SV | zoledronic acid | `metastatic`, 7주기 | 골 보호제도 투약 기록이라 치료 이력에 들어간다 |

## 5. 환자별 작업표

각 표의 "생성기가 넣은 값"은 비교용이다. 먼저 직접 채운 뒤 맞춰 본다.

## 국소 진행성 (진단 시 III기), 원격 전이 재발: TCGA-A2-A04P

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N3c<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N3c", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIIC | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIIC"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 18<br>`gdc_lymph_nodes_examined_count` = 20 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": 18, "examined": 20}` |
| stage.disease_extent | `stage_disease_extent` = locally_advanced | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"locally_advanced"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Lumpectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Negative<br>`gdc_er_status_ihc_Percent_Positive` = <1% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [0, 0], "result": "negative"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = <1% | §3.3 ER과 같음. 저발현 없음 | `{"range": [0, 0], "result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = [Not Available]<br>`gdc_her2_status_by_ihc` = [Not Evaluated]<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"status": "not_done"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 36 | 정수 | `36` |
| patient.menopausal_status | `gdc_menopause_status` = Pre (<6 months since LMP AND no prior bilateral ovariectomy AND not on estrogen replacement) | §3.5 사전 (Post → postmenopausal 등) | `"premenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = distant<br>`nte_types` = Locoregional Recurrence; Distant Metastasis | §3.7 recurrence_status 그대로 | `"distant"` |
| recurrence.metastatic_sites | `nte_sites` = Other, specify; Bone; Lung; Liver<br>`nte_sites_other` = Axilla | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | `["other: Axilla", "bone", "lung", "liver"]` |
| recurrence.metastasis_day | `metastasis_dx_days` = 102 | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | `102` |
| recurrence.recurrence_day | `locoregional_dx_days` = 179<br>`metastasis_dx_days` = 102 | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | `102` |
| recurrence.surgery | `nte_surgery` = YES; NO | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | `"yes"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = 179<br>`metastasis_dx_days` = 102 | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | `"no"` |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = R88Q (Missense_Mutation, VAF 0.982) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["R88Q"]}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = Q3206E (Missense_Mutation, VAF 0.089) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["Q3206E"]}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (8건 → 정답 8건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | paclitaxel [Chemotherapy] d69~d180 | 69 / 180 / 12 | | | | | |
| 1 | capecitabine [Chemotherapy] d180~d242 | 180 / 242 / [Not Available] | | | | | |
| 2 | docetaxel [Chemotherapy] d242~d303 | 242 / 303 / [Not Available] | | | | | |
| 3 | gemcitabine [Chemotherapy] d242~d303 | 242 / 303 / [Not Available] | | | | | |
| 4 | doxorubicin [Chemotherapy] d303~d424 | 303 / 424 / [Not Available] | | | | | |
| 5 | exemestane [Hormone Therapy] d424~? | 424 / [Not Available] / [Not Available] | | | | | |
| 6 | vinorelbine [Chemotherapy] d424~d424 | 424 / 424 / 1 | | | | | |
| 7 | cisplatin [Chemotherapy] d424~d424 | 424 / 424 / 1 | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | paclitaxel | adjuvant | 69 / 180 / 111 | 12 (recorded, 간격 10일 derived) | unknown |
| 1 | capecitabine | metastatic | 180 / 242 / 62 | 4 (estimated, 간격 21일 standard) | unknown |
| 2 | docetaxel | metastatic | 242 / 303 / 61 | 4 (estimated, 간격 21일 standard) | unknown |
| 3 | gemcitabine | metastatic | 242 / 303 / 61 | 4 (estimated, 간격 21일 standard) | unknown |
| 4 | doxorubicin | metastatic | 303 / 424 / 121 | 7 (estimated, 간격 21일 standard) | unknown |
| 5 | exemestane | metastatic | 424 / None / None | null | unknown |
| 6 | vinorelbine | metastatic | 424 / 424 / 0 | 1 (recorded, 간격 21일 standard) | unknown |
| 7 | cisplatin | metastatic | 424 / 424 / 0 | 1 (recorded, 간격 21일 standard) | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 102) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 4 | doxorubicin | [Not Available] / [Not Available] / [Not Available] / [Not Available] / [Not Available] | `"No value"` | `"No value"` | No value |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PIK3CA p.R88Q (Missense_Mutation), VAF 98.2%. BRCA2 p.Q3206E (Missense_Mutation), VAF 8.9%. ESR1 amplification. PIK3CA amplification. ERBB2, ESR1, AKT1, PTEN, BRCA1, PALB2: 검출되지 않음.

---

## 조기 (진단 시 I~II기): TCGA-5T-A9QA

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Other, specify<br>`gdc_histologic_diagnosis_other` = infiltrating ductal and mucinous<br>`cbio_sample_ONCOTREE_CODE` = BRCNOS | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"invasive_NOS"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = NX<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_ajcc_staging_edition` = 7th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "not_assessed", "m": "not_assessed", "edition": "7th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIA | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIA"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = [Not Available]<br>`gdc_lymph_nodes_examined_count` = [Not Available] | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"status": "not_recorded"}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Available]"` |
| stage.operable | `gdc_surgical_procedure_first` = [Unknown] | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `{"status": "not_recorded"}` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 70-79% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [70, 79], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = [Not Available] | §3.3 ER과 같음. 저발현 없음 | `{"result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 52 | 정수 | `52` |
| patient.menopausal_status | `gdc_menopause_status` = [Unknown] | §3.5 사전 (Post → postmenopausal 등) | `{"status": "not_recorded"}` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = none<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"none"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (4건 → 정답 4건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | doxorubicin [Chemotherapy] d23~d94 (Complete Response) | 23 / 94 / [Not Available] | | | | | |
| 1 | paclitaxel [Chemotherapy] d115~d198 | 115 / 198 / [Not Available] | | | | | |
| 2 | letrozole [Hormone Therapy] d304~? | 304 / [Not Available] / [Not Available] | | | | | |
| 3 | cyclophosphamide [Chemotherapy] 날짜 없음 (Complete Response) | [Discrepancy] / 94 / [Not Available] | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | doxorubicin | adjuvant | 23 / 94 / 71 | 4 (estimated, 간격 21일 standard) | CR |
| 1 | paclitaxel | adjuvant | 115 / 198 / 83 | 13 (estimated, 간격 7일 standard) | unknown |
| 2 | letrozole | adjuvant | 304 / None / None | null | unknown |
| 3 | cyclophosphamide | adjuvant | None / 94 / None | null | CR |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 0 | doxorubicin | [Not Available] / [Not Available] / [Not Available] / [Not Available] / [Not Available] | `"No value"` | `"No value"` | No value |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 국소 진행성 (진단 시 III기): TCGA-AQ-A0Y5

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N2a<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_ajcc_staging_edition` = 7th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N2a", "m": "not_assessed", "edition": "7th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIIA | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIIA"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 5<br>`gdc_lymph_nodes_examined_count` = 17 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": 5, "examined": 17}` |
| stage.disease_extent | `stage_disease_extent` = locally_advanced | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"locally_advanced"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = NO<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Modified Radical Mastectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 70-79% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [70, 79], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 40-49% | §3.3 ER과 같음. 저발현 없음 | `{"range": [40, 49], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Positive<br>`gdc_her2_fish_status` = Positive | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "positive"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Positive | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 70 | 정수 | `70` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = none<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"none"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = E453K (Missense_Mutation, VAF 0.21) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["E453K"]}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (3건 → 정답 3건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | cyclophosphamide [Chemotherapy] d83~d146 | 83 / 146 / 4 | | | | | |
| 1 | trastuzumab [HER2-targeted Therapy] d83~d146 | 83 / 146 / 4 | | | | | |
| 2 | docetaxel [Chemotherapy] d83~d146 | 83 / 146 / 4 | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | cyclophosphamide | neoadjuvant | 83 / 146 / 63 | 4 (recorded, 간격 21일 derived) | unknown |
| 1 | trastuzumab | adjuvant | 83 / 146 / 63 | 4 (recorded, 간격 21일 derived) | unknown |
| 2 | docetaxel | adjuvant | 83 / 146 / 63 | 4 (recorded, 간격 21일 derived) | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = Yes) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `negative`


### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PIK3CA p.E453K (Missense_Mutation), VAF 21.0%. ERBB2 amplification. ERBB2, ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 조기 (진단 시 I~II기), 국소 재발: TCGA-C8-A137

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N1<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N1", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIB | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIB"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = [Not Available]<br>`gdc_lymph_nodes_examined_count` = 2 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": "[Not Available]", "examined": 2}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = NO<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Modified Radical Mastectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Negative<br>`gdc_er_status_ihc_Percent_Positive` = [Not Available] | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"result": "negative"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = [Not Available] | §3.3 ER과 같음. 저발현 없음 | `{"result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 3+<br>`gdc_her2_status_by_ihc` = Positive<br>`gdc_her2_fish_status` = [Not Evaluated] | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "3+", "result": "positive"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = [Not Evaluated] | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"status": "not_done"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 34 | 정수 | `34` |
| patient.menopausal_status | `gdc_menopause_status` = Pre (<6 months since LMP AND no prior bilateral ovariectomy AND not on estrogen replacement) | §3.5 사전 (Post → postmenopausal 등) | `"premenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = locoregional<br>`nte_types` = Locoregional Recurrence | §3.7 recurrence_status 그대로 | `"locoregional"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = 136<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | `136` |
| recurrence.surgery | `nte_surgery` = NO | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | `"no"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = 136<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | `"no"` |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (0건 → 정답 0건)

투약 기록 없음 → `treatment_history` = `[]`, anthracycline `administered` = `No value`.

### anthracycline 용량: administered = `No value`


### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). ERBB2 amplification. ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 전이성 (진단 시 IV기), 원격 전이 재발: TCGA-LL-A73Z

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T1c<br>`gdc_ajcc_nodes_pathologic_pn` = NX<br>`gdc_ajcc_metastasis_pathologic_pm` = M1<br>`gdc_ajcc_staging_edition` = 7th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T1c", "n": "not_assessed", "m": "M1", "edition": "7th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IV | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IV"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = [Not Available]<br>`gdc_lymph_nodes_examined_count` = [Not Available] | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"status": "not_recorded"}` |
| stage.disease_extent | `stage_disease_extent` = metastatic | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"metastatic"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M1<br>`gdc_metastasis_site` = Other, specify<br>`gdc_metastasis_site_other` = skin | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `["brain"]` |
| stage.operable | `gdc_surgical_procedure_first` = Lumpectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 10-19% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [10, 19], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 1-9% | §3.3 ER과 같음. 저발현 없음 | `{"range": [1, 9], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 55 | 정수 | `55` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = distant<br>`nte_types` = Distant Metastasis | §3.7 recurrence_status 그대로 | `"distant"` |
| recurrence.metastatic_sites | `nte_sites` = Brain<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | `["brain"]` |
| recurrence.metastasis_day | `metastasis_dx_days` = 0 | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | `0` |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = 0 | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = NO | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | `"no"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = 0 | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = V290Sfs*8 (Frame_Shift_Ins, VAF 0.239) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["V290Sfs*8"]}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (4건 → 정답 4건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | doxorubicin [Chemotherapy] d18~d60 (Clinical Progressive Disease) | 18 / 60 / [Not Available] | | | | | |
| 1 | cyclophosphamide [Chemotherapy] d18~d60 (Clinical Progressive Disease) | 18 / 60 / [Not Available] | | | | | |
| 2 | paclitaxel [Chemotherapy] d74~d109 (Clinical Progressive Disease) | 74 / 109 / [Not Available] | | | | | |
| 3 | fulvestrant [Hormone Therapy] d123~d179 (Clinical Progressive Disease) | 123 / 179 / [Not Available] | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | doxorubicin | metastatic | 18 / 60 / 42 | 3 (estimated, 간격 21일 standard) | PD |
| 1 | cyclophosphamide | metastatic | 18 / 60 / 42 | 3 (estimated, 간격 21일 standard) | PD |
| 2 | paclitaxel | metastatic | 74 / 109 / 35 | 6 (estimated, 간격 7일 standard) | PD |
| 3 | fulvestrant | metastatic | 123 / 179 / 56 | 3 (estimated, 간격 28일 standard) | PD |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 0) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 0 | doxorubicin | [Not Available] / [Not Available] / [Not Available] / [Not Available] / [Not Available] | `"No value"` | `"No value"` | No value |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PTEN p.V290Sfs*8 (Frame_Shift_Ins), VAF 23.9%. ERBB2, ESR1, PIK3CA, AKT1, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 조기 (진단 시 I~II기): TCGA-A1-A0SO

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N1<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N1", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIB | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIB"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 1<br>`gdc_lymph_nodes_examined_count` = 9 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": 1, "examined": 9}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Modified Radical Mastectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Negative<br>`gdc_er_status_ihc_Percent_Positive` = [Not Available] | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"result": "negative"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = [Not Available] | §3.3 ER과 같음. 저발현 없음 | `{"result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = [Not Available]<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 67 | 정수 | `67` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = none<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"none"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = X27_splice (Splice_Site, VAF 0.911) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["X27_splice"]}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (1건 → 정답 0건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | unknown [Chemotherapy] d61~d180 | 61 / 180 / [Not Available] | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `negative`


### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). BRCA1 p.X27_splice (Splice_Site), VAF 91.1%. ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA2, PALB2: 검출되지 않음.

---

## 조기 (진단 시 I~II기): TCGA-AC-A2FO

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Lobular Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = ILC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"ILC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N1<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N1", "m": "not_assessed", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIB | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIB"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 2<br>`gdc_lymph_nodes_examined_count` = 10 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": 2, "examined": 10}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = NO<br>`gdc_ajcc_metastasis_pathologic_pm` = MX<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Simple Mastectomy | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 90-99% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [90, 99], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = [Not Available] | §3.3 ER과 같음. 저발현 없음 | `{"result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = [Not Available]<br>`gdc_her2_status_by_ihc` = Negative<br>`gdc_her2_fish_status` = Indeterminate | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Indeterminate | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"status": "not_recorded"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 65 | 정수 | `65` |
| patient.menopausal_status | `gdc_menopause_status` = Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy) | §3.5 사전 (Post → postmenopausal 등) | `"postmenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = none<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"none"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = E545K (Missense_Mutation, VAF 0.269) | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "detected", "variants": ["E545K"]}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (2건 → 정답 2건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | chemotherapy nos [Chemotherapy] d105~? (Complete Response) | 105 / [Not Available] / [Not Available] | | | | | |
| 1 | endocrine therapy nos [Hormone Therapy] d225~? (Complete Response) | 225 / [Not Available] / [Not Available] | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | chemotherapy nos | adjuvant | 105 / None / None | null | CR |
| 1 | endocrine therapy nos | adjuvant | 225 / None / None | null | CR |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `negative`


### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). PIK3CA p.E545K (Missense_Mutation), VAF 26.9%. ERBB2, ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 조기 (진단 시 I~II기), 국소 재발: TCGA-AR-A24L

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N1<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N1", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIB | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIB"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = 2<br>`gdc_lymph_nodes_examined_count` = 12 | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"positive": 2, "examined": 12}` |
| stage.disease_extent | `stage_disease_extent` = early | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"early"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Other | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Positive<br>`gdc_er_status_ihc_Percent_Positive` = 10-19% | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"range": [10, 19], "result": "positive"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Positive<br>`gdc_pr_status_ihc_percent_positive` = 10-19% | §3.3 ER과 같음. 저발현 없음 | `{"range": [10, 19], "result": "positive"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Equivocal<br>`gdc_her2_fish_status` = Negative | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "negative"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = Negative | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"result": "not_amplified", "method": "FISH"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 26 | 정수 | `26` |
| patient.menopausal_status | `gdc_menopause_status` = Pre (<6 months since LMP AND no prior bilateral ovariectomy AND not on estrogen replacement) | §3.5 사전 (Post → postmenopausal 등) | `"premenopausal"` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = locoregional<br>`nte_types` = Locoregional Disease | §3.7 recurrence_status 그대로 | `"locoregional"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = 1414<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | `1414` |
| recurrence.surgery | `nte_surgery` = YES | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | `"yes"` |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | `"unknown"` |
| recurrence.later_distant | `locoregional_dx_days` = 1414<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | `"no"` |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (4건 → 정답 4건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | tamoxifen [Hormone Therapy] d145~d1414 | 145 / 1414 / [Not Available] | | | | | |
| 1 | paclitaxel [Chemotherapy] 날짜 없음 | [Not Available] / [Not Available] / 4 | | | | | |
| 2 | doxorubicin [Chemotherapy] 날짜 없음 | [Not Available] / [Not Available] / 4 | | | | | |
| 3 | cyclophosphamide [Chemotherapy] 날짜 없음 | [Not Available] / [Not Available] / 4 | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | tamoxifen | adjuvant | 145 / 1414 / 1269 | null | unknown |
| 1 | paclitaxel | adjuvant | None / None / None | 4 (recorded, 간격 7일 standard) | unknown |
| 2 | doxorubicin | adjuvant | None / None / None | 4 (recorded, 간격 21일 standard) | unknown |
| 3 | cyclophosphamide | adjuvant | None / None / None | 4 (recorded, 간격 21일 standard) | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `positive`

| 항목 # | 약 | 원본 1회 용량 / 단위 / 총량 / 단위 / 주기 | dose_per_admin | total_dose | cycles |
|---|---|---|---|---|---|
| 2 | doxorubicin | [Not Available] / [Not Available] / [Not Available] / [Not Available] / 4 | `"No value"` | `"No value"` | 4 (recorded) |

### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.

---

## 국소 진행성 (진단 시 III기): TCGA-A8-A07R

| 칸 | 원본 열 = 값 | 적용 규칙 (tcga_mapping.md) | 생성기가 넣은 값 |
|---|---|---|---|
| diagnosis.histology | `gdc_histological_type` = Infiltrating Ductal Carcinoma<br>`gdc_histologic_diagnosis_other` = [Not Applicable]<br>`cbio_sample_ONCOTREE_CODE` = IDC | §3.1 조직형 이름 → 사전. Other·Mixed·Medullary면 ONCOTREE 코드 | `"IDC"` |
| diagnosis.diagnosis_date | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| diagnosis.grade | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| stage.ptnm | `gdc_ajcc_tumor_pathologic_pt` = T2<br>`gdc_ajcc_nodes_pathologic_pn` = N3a<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_ajcc_staging_edition` = 6th | §3.2 공백 제거, TX·NX·MX → not_assessed | `{"t": "T2", "n": "N3a", "m": "M0", "edition": "6th"}` |
| stage.ctnm | — | TCGA에 없음 (병리 병기만 있음) | `{"status": "not_recorded"}` |
| stage.group | `gdc_ajcc_pathologic_tumor_stage` = Stage IIIC | §3.2 'Stage ' 제거, Stage X → not_assessed | `"IIIC"` |
| stage.positive_ln_count | `gdc_lymph_nodes_examined_he_count` = [Not Available]<br>`gdc_lymph_nodes_examined_count` = [Not Available] | §3.2 positive = he_count(양성 수), examined = examined_count. 없는 쪽은 "[Not Available]" (raw도 같음), 둘 다 없으면 not_recorded | `{"status": "not_recorded"}` |
| stage.disease_extent | `stage_disease_extent` = locally_advanced | 크롭 스크립트가 정한 진단 시 범주 그대로 | `"locally_advanced"` |
| stage.metastatic_sites | `gdc_metastatic_tumor_indicator` = [Not Available]<br>`gdc_ajcc_metastasis_pathologic_pm` = M0<br>`gdc_metastasis_site` = [Not Available]<br>`gdc_metastasis_site_other` = [Not Available] | §3.2 NO → [Not Applicable] / 기록 없음 + M0 → [Not Applicable] / 그 밖에는 부위 목록, 진단 시 IV기는 부위 기록 없으면 not_done, 재발 부위와 다르면 재발 기록을 따름 (규칙 8·9). 그 밖에 부위 기록 없으면 [Not Available] | `"[Not Applicable]"` |
| stage.operable | `gdc_surgical_procedure_first` = Other | §3.2 첫 수술 종류 기록이 있으면 yes, 괄호 코드·빈칸이면 not_recorded (2026-10-20) | `"yes"` |
| receptors.er_percent | `gdc_er_status_by_ihc` = Negative<br>`gdc_er_status_ihc_Percent_Positive` = [Not Available] | §3.3 구간 → [최소, 최대], 판정 → 사전. 비율이 없으면 판정만 | `{"result": "negative"}` |
| receptors.pr_percent | `gdc_pr_status_by_ihc` = Negative<br>`gdc_pr_status_ihc_percent_positive` = [Not Available] | §3.3 ER과 같음. 저발현 없음 | `{"result": "negative"}` |
| receptors.her2_ihc | `gdc_her2_ihc_score` = 2+<br>`gdc_her2_status_by_ihc` = Positive<br>`gdc_her2_fish_status` = [Not Available] | §3.3 score + result. 점수 없는 Equivocal → 2+. 2+ 또는 Equivocal이면 FISH로 result 보정 (FISH 없으면 적힌 판정) | `{"score": "2+", "result": "positive"}` |
| receptors.her2_ish | `gdc_her2_fish_status` = [Not Available] | §3.3 Positive → amplified, Negative → not_amplified, Equivocal → equivocal, [Not Evaluated] → not_done | `{"status": "not_recorded"}` |
| receptors.pdl1 | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| proliferation.ki67_percent | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.gender | `gdc_gender` = FEMALE | 그대로 | `"FEMALE"` |
| patient.age | `gdc_age_at_diagnosis` = 80 | 정수 | `80` |
| patient.menopausal_status | `gdc_menopause_status` = [Not Available] | §3.5 사전 (Post → postmenopausal 등) | `{"status": "not_recorded"}` |
| patient.menopausal_basis | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| patient.ecog | — | TCGA에 없음 | `{"status": "not_recorded"}` |
| recurrence.status | `recurrence_status` = none<br>`nte_types` = (빈칸) | §3.7 recurrence_status 그대로 | `"none"` |
| recurrence.metastatic_sites | `nte_sites` = (빈칸)<br>`nte_sites_other` = (빈칸) | §3.7 status = distant일 때만. Other, specify → other: 내용. 내용에 표준 부위 이름이 섞이면 나눔 (규칙 7) | (칸 없음) |
| recurrence.metastasis_day | `metastasis_dx_days` = (빈칸) | §3.7 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 | (칸 없음) |
| recurrence.recurrence_day | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 distant·locoregional일 때만. 국소 재발일과 원격 전이일 중 이른 값. 진단 시 IV기는 넣지 않음 | (칸 없음) |
| recurrence.surgery | `nte_surgery` = (빈칸) | §3.7 status가 none·unknown이 아닐 때만. YES가 하나라도 있으면 yes, NO만 있으면 no, 빈칸이면 unknown | (칸 없음) |
| recurrence.surgery_intent | — | §3.7 surgery를 만들 때 항상 unknown | (칸 없음) |
| recurrence.later_distant | `locoregional_dx_days` = (빈칸)<br>`metastasis_dx_days` = (빈칸) | §3.7 locoregional → no. distant이고 국소 재발일이 있으면 국소 < 전이 → yes | (칸 없음) |
| recurrence.recurrence_date 등 | — | §2.3 날짜는 모두 비움 | `{"status": "not_recorded"}` |
| molecular.mutations.ESR1 | `mut_ESR1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PIK3CA | `mut_PIK3CA` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.AKT1 | `mut_AKT1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PTEN | `mut_PTEN` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA1 | `mut_BRCA1` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.BRCA2 | `mut_BRCA2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |
| molecular.mutations.PALB2 | `mut_PALB2` = 변이 없음 | §3.8 변이 표기 → detected, '변이 없음' → not_detected, 빈칸 → not_done | `{"result": "not_detected", "variants": []}` |

### 치료 이력 (1건 → 정답 1건)

원본 `drug_timeline`의 항목 하나 = 정답 한 줄. 정답은 `start_day` 순으로 정렬한다. 성분명 unknown은 뺀다.

| # | 원본 항목 (`drug_timeline`) | `drug_start_days` / `drug_end_days` / `drug_cycles` | 정답 drugs | setting (유도) | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|---|---|
| 0 | zoledronic acid [Bone-modifying Agent] d181~? | 181 / [Not Available] / [Not Available] | | | | | |

정답 (start_day 순):

| 정답 # | drugs | setting | start_day / end_day / duration_days | cycles | best_response |
|---|---|---|---|---|---|
| 0 | zoledronic acid | adjuvant | 181 / None / None | null | unknown |

setting 규칙: 시작일 ≥ 전이 기준일(`metastasis_dx_days` = 없음) → metastatic, 선행요법 이력(`gdc_history_neoadjuvant_treatment` = No) Yes + 첫 요법 → neoadjuvant, 나머지 → adjuvant.

### anthracycline 용량: administered = `negative`


### 유전자 보고서 원문 (`genomic_reports[0].raw_text`)

> 종양 조직 엑솜 검사 (원발 조직). ERBB2, ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음.
