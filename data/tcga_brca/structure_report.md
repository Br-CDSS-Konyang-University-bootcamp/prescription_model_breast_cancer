# TCGA-BRCA 임상·변이 데이터 구조

## 1. 파일 목록

| table                           |   rows |   cols | patients   | unit               |
|:--------------------------------|-------:|-------:|:-----------|:-------------------|
| gdc_clinical_drug               |   2406 |     28 | 780        | 환자당 여러 행 (평균 3.1)  |
| gdc_clinical_follow_up_v1.5     |    114 |     63 | 113        | 환자당 여러 행 (평균 1.0)  |
| gdc_clinical_follow_up_v2.1     |    523 |     45 | 516        | 환자당 여러 행 (평균 1.0)  |
| gdc_clinical_follow_up_v4.0     |    716 |     13 | 619        | 환자당 여러 행 (평균 1.2)  |
| gdc_clinical_follow_up_v4.0_nte |     82 |     35 | 58         | 환자당 여러 행 (평균 1.4)  |
| gdc_clinical_nte                |    119 |     34 | 113        | 환자당 여러 행 (평균 1.1)  |
| gdc_clinical_omf_v4.0           |     82 |     30 | 77         | 환자당 여러 행 (평균 1.1)  |
| gdc_clinical_patient            |   1097 |    112 | 1097       | 환자 1명 = 1행         |
| gdc_clinical_radiation          |    618 |     18 | 528        | 환자당 여러 행 (평균 1.2)  |
| cbio_clinical_attributes        |     60 |      5 | -          | 속성 설명              |
| cbio_clinical_patient           |   1084 |     41 | 1084       | 환자 1명 = 1행         |
| cbio_clinical_sample            |   1084 |     20 | 1084       | 환자 1명 = 1행         |
| cbio_cna_biomarker_genes        |   1070 |     10 | 1070       | 환자 1명 = 1행         |
| cbio_mutations                  |  84226 |     19 | 1009       | 환자당 여러 행 (평균 83.5) |
| cbio_profiled_samples           |   1084 |      4 | 1084       | 환자 1명 = 1행         |

## 2. 출처 간 환자 ID 겹침

| 구분 | 환자 수 |
|---|---|
| GDC 임상 환자 | 1,097 |
| cBioPortal 임상 환자 | 1,084 |
| 둘 다 있음 | 1,083 |
| 변이 1개 이상 있는 환자 | 1,009 |
| GDC 임상 ∩ 변이 | 1,009 |
| 투약 기록 있는 환자 | 780 |
| GDC 임상 ∩ 변이 ∩ 투약 | 712 |

## 3. v0.1 핵심 필드 분포

### 수용체 (ER/PR/HER2)

```
  er_status_by_ihc
      Positive: 808
      Negative: 238
      [Not Evaluated]: 49
      Indeterminate: 2
  er_status_ihc_Percent_Positive
      [Not Available]: 627
      90-99%: 245
      <10%: 71
      70-79%: 49
      80-89%: 31
      10-19%: 25
      50-59%: 15
      60-69%: 12
  pr_status_by_ihc
      Positive: 699
      Negative: 344
      [Not Evaluated]: 50
      Indeterminate: 4
  pr_status_ihc_percent_positive
      [Not Available]: 667
      <10%: 138
      90-99%: 105
      70-79%: 41
      10-19%: 31
      80-89%: 30
      40-49%: 21
      60-69%: 18
  her2_status_by_ihc
      Negative: 564
      Equivocal: 179
      [Not Evaluated]: 170
      Positive: 164
      Indeterminate: 12
      [Not Available]: 8
  her2_ihc_percent_positive
      [Not Available]: 889
      <10%: 122
      10-19%: 26
      90-99%: 16
      30-39%: 11
      20-29%: 11
      40-49%: 6
      70-79%: 5
  her2_ihc_score
      [Not Available]: 475
      1+: 272
      2+: 199
      3+: 90
      0: 61
  her2_positivity_scale_other
      [Not Available]: 1083
      0: 5
      CISH: 2
      Hercep Test  TM Dako: 2
      ACIS: 2
      Dako: 1
      FISH: 1
      10-75%: 1
  her2_positivity_method_text
      [Not Available]: 1007
      3+ Positive: 18
      3+ POSITIVE: 18
      dextran coated charcoal: 9
      Hecep Test TM DAKO: 8
      DAKOHercepTest TM: 7
      Venten: 5
      CAP scoring guideline 2010: 5
  her2_fish_status
      [Not Evaluated]: 596
      Negative: 333
      [Not Available]: 81
      Positive: 78
      Equivocal: 5
      Indeterminate: 4
  her2_copy_number
      [Not Available]: 983
      not amplified: 7
      3.2: 6
      2.4: 4
      2.6: 4
      2: 3
      1.8: 3
      2.2: 3
  her2_and_cent17_cells_count
      [Not Available]: 993
      60: 29
      40: 18
      20: 17
      30: 10
      200: 4
      33: 2
      556: 1
  her2_cent17_ratio
      [Not Available]: 864
      1.1: 34
      1.3: 17
      1.0: 17
      1.2: 16
      1.05: 7
      1.5: 7
      1.4: 6
  her2_and_cent17_scale_other
      [Not Available]: 1093
      Vysis AutoVysion System: 1
      >2.2 Positive: 1
      HER2 amplification - negative: 1
      1: 1
  her2_fish_method
      [Not Available]: 1047
      >=2.0 Positive: 8
      PathVysion HER-2 DNA Probe Kit: 6
      RATIO > = 2.0: 3
      CAP scoring guideline 2010: 3
      Enumerate 60 tumor cells; ratio of HER2/Centromere 17 >= 2.1 is amplified: 2
      PathVysion HER-2 DNA probe kit.: 2
      >= 2.0 Positive: 2
  nte_er_status
      [Not Available]: 999
      [Not Evaluated]: 86
      Positive: 9
      Negative: 3
  nte_er_status_ihc__positive
      [Not Available]: 1091
      70-79%: 2
      90-99%: 2
      <10%: 2
  nte_pr_status_by_ihc
      [Not Available]: 999
      [Not Evaluated]: 87
      Negative: 7
      Positive: 4
  nte_pr_status_ihc__positive
      [Not Available]: 1093
      <10%: 4
  nte_her2_status
      [Not Available]: 997
      [Not Evaluated]: 91
      Negative: 8
      Equivocal: 1
  nte_her2_status_ihc__positive
      [Not Available]: 1094
      <10%: 3
  nte_her2_positivity_ihc_score
      [Not Available]: 1092
      1+: 4
      2+: 1
  nte_her2_positivity_other_scale
      [Not Available]: 1097
  nte_her2_positivity_method
      [Not Available]: 1097
  nte_her2_fish_status
      [Not Available]: 999
      [Not Evaluated]: 95
      Negative: 3
  nte_her2_signal_number
      [Not Available]: 1097
  her2_cent17_counted_cells_count
      [Not Available]: 1097
  nte_cent_17_her2_ratio
      [Not Available]: 1095
      1.09: 1
      2.47: 1
  nte_cent17_her2_other_scale
      [Not Available]: 1097
  nte_her2_fish_define_method
      [Not Available]: 1097
```

### 병기 (AJCC)

```
  ajcc_staging_edition
      6th: 445
      7th: 417
      [Not Available]: 141
      5th: 57
      4th: 29
      3rd: 8
  ajcc_tumor_pathologic_pt
      T2: 633
      T1c: 223
      T3: 137
      T1: 41
      T4b: 28
      T1b: 16
      T4: 9
      TX: 3
  ajcc_nodes_pathologic_pn
      N0: 333
      N1a: 167
      N0 (i-): 154
      N1: 126
      N2a: 64
      N2: 56
      N3a: 47
      N1mi: 37
  ajcc_metastasis_pathologic_pm
      M0: 906
      MX: 163
      M1: 22
      cM0 (i+): 6
  ajcc_pathologic_tumor_stage
      Stage IIA: 358
      Stage IIB: 257
      Stage IIIA: 155
      Stage I: 90
      Stage IA: 86
      Stage IIIC: 65
      Stage IIIB: 27
      Stage IV: 20
```

### 환자 (나이, 폐경)

```
  menopause_status
      Post (prior bilateral ovariectomy OR >12 mo since LMP with no prior hysterectomy): 705
      Pre (<6 months since LMP AND no prior bilateral ovariectomy AND not on estrogen replacement): 229
      [Not Available]: 67
      Peri (6-12 months since last menstrual period): 39
      Indeterminate (neither Pre or Postmenopausal): 34
      [Unknown]: 17
      [Not Evaluated]: 6
  age_at_diagnosis
      62: 51
      63: 37
      61: 36
      50: 34
      54: 34
      56: 33
      59: 32
      51: 31
```

### 조직형

```
  histologic_diagnosis_other
      [Not Applicable]: 1021
      Infiltrating ductal and lobular carcinoma: 11
      infiltrating ductal and mucinous: 2
      lobular/ductal: 2
      Ductal & Mucinous: 2
      Mixed invasive ductal and invasive lobular: 2
      Lobular/Ductal: 2
      ductal and lobular: 2
  histological_type
      Infiltrating Ductal Carcinoma: 784
      Infiltrating Lobular Carcinoma: 203
      Other, specify: 46
      Mixed Histology (please specify): 30
      Mucinous Carcinoma: 17
      Metaplastic Carcinoma: 9
      Medullary Carcinoma: 6
      Infiltrating Carcinoma NOS: 1
```

### 치료 이력 (GDC clinical_drug)

```
  pharmaceutical_therapy_drug_name
      Tamoxifen: 222
      Cytoxan: 222
      Cyclophosphamide: 173
      Doxorubicin: 150
      Arimidex: 138
      Adriamycin: 132
      Paclitaxel: 105
      Taxotere: 95
      Docetaxel: 74
      Taxol: 70
  pharmaceutical_therapy_type
      Chemotherapy: 1612
      Hormone Therapy: 670
      Immunotherapy: 37
      Targeted Molecular therapy: 31
      Ancillary: 24
      Other, specify in notes: 22
      [Not Available]: 7
      Chemotherapy|Hormone Therapy: 2
      Vaccine: 1
  treatment_best_response
      [Not Available]: 1455
      Complete Response: 542
      [Not Applicable]: 176
      [Unknown]: 126
      Clinical Progressive Disease: 55
      Stable Disease: 36
      Partial Response: 12
      [Discrepancy]: 4
```

### 재발·새 종양 (GDC clinical_nte)

```
  new_tumor_event_type
      [Not Available]: 103
      Distant Metastasis: 10
      Locoregional Recurrence: 5
      New Primary Tumor: 1
  new_tumor_event_site
      [Not Available]: 104
      Other, specify: 6
      Bone: 5
      Lung: 3
      Liver: 1
  new_tumor_event_site_other
      [Not Available]: 113
      Breast recurrence: 1
      Chest wall: 1
      malignant melanoma: 1
      chestwall: 1
      Adrenal glands: 1
      breast: 1
```

## 4. 체세포 변이·복제수

변이 행 84,226개, 샘플 1,009개, 유전자 16,488개

### 바이오마커 유전자별 변이 환자 수

| gene   |   환자 수 |   비율_% |
|:-------|-------:|-------:|
| ERBB2  |     30 |    3   |
| ESR1   |      9 |    0.9 |
| PIK3CA |    347 |   34.4 |
| AKT1   |     27 |    2.7 |
| PTEN   |     58 |    5.7 |
| BRCA1  |     27 |    2.7 |
| BRCA2  |     29 |    2.9 |
| PALB2  |      7 |    0.7 |

### PIK3CA 상위 변이

| proteinChange   |   count |
|:----------------|--------:|
| H1047R          |     129 |
| E545K           |      65 |
| E542K           |      43 |
| N345K           |      18 |
| H1047L          |      13 |

### 복제수 (GISTIC)

```
  ERBB2   -2:   0  -1: 260   0: 481   1: 206   2: 123
  ESR1    -2:   4  -1: 328   0: 572   1: 146   2:  20
  PIK3CA  -2:   0  -1:  58   0: 680   1: 298   2:  34
  AKT1    -2:   2  -1: 296   0: 601   1: 159   2:  12
  PTEN    -2:  55  -1: 269   0: 659   1:  83   2:   4
  BRCA1   -2:   5  -1: 363   0: 490   1: 199   2:  13
  BRCA2   -2:  14  -1: 429   0: 511   1: 108   2:   8
  PALB2   -2:   0  -1:  90   0: 435   1: 508   2:  37
```

## 5. her2_ihc_score × ERBB2 복제수

| her2_ihc_score   |   -1 |   0 |   1 |   2 |
|:-----------------|-----:|----:|----:|----:|
| 0                |   21 |  26 |  10 |   2 |
| 1+               |   72 | 130 |  55 |   5 |
| 2+               |   27 |  87 |  54 |  24 |
| 3+               |    4 |  10 |  11 |  61 |
| [Not Available]  |  136 | 227 |  76 |  31 |

## 6. 테이블별 열 상세

filled_%는 GDC 결측 코드와 빈칸을 뺀 실제 값 비율이다.

### gdc_clinical_drug (2,406행 × 28열)

| column                              |   filled_% | gdc_codes                                                                  |   n_unique | examples                                                                                                        |
|:------------------------------------|-----------:|:---------------------------------------------------------------------------|-----------:|:----------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                    |      100   |                                                                            |        780 | C07B122E-AC50-4DB2-ADD2-5617A5 (23) | 9435447e-d65f-408b-863b-6576b1 (13) | 8d5fe6e8-d2cc-481f-a6a1-9cb6e7 (12) |
| bcr_patient_barcode                 |      100   |                                                                            |        780 | TCGA-GM-A2DA (23) | TCGA-AO-A03N (13) | TCGA-A2-A0EW (12)                                                       |
| bcr_drug_barcode                    |      100   |                                                                            |       2406 | TCGA-3C-AAAU-D60350 (1) | TCGA-3C-AALI-D62900 (1) | TCGA-3C-AALJ-D62904 (1)                                     |
| bcr_drug_uuid                       |      100   |                                                                            |       2406 | B8C5D175-54E9-4659-A630-DC1EA2 (1) | C09E3F7D-0FC8-4316-AF95-1D9CE3 (1) | D9762142-667A-4123-846B-B3B965 (1)    |
| form_completion_date                |      100   |                                                                            |        345 | 2012-12-6 (188) | 2011-1-10 (73) | 2010-9-19 (55)                                                               |
| pharmaceutical_therapy_drug_name    |       99.3 | [Not Available]:15, [Unknown]:1                                            |        203 | Tamoxifen (222) | Cytoxan (222) | Cyclophosphamide (173)                                                        |
| clinical_trial_drug_classification  |        5   | [Not Available]:2285                                                       |          4 | n/a (118) | Antimetabolite (1) | Biological Therapy/Monoclonal  (1)                                             |
| pharmaceutical_therapy_type         |       99.7 | [Not Available]:7                                                          |          8 | Chemotherapy (1612) | Hormone Therapy (670) | Immunotherapy (37)                                                |
| pharmaceutical_tx_started_days_to   |       95.1 | [Not Available]:116, [Discrepancy]:2                                       |        486 | 61 (42) | 50 (42) | 31 (40)                                                                                     |
| pharmaceutical_tx_ongoing_indicator |       99.4 | [Not Available]:15                                                         |          2 | NO (1902) | YES (489)                                                                                           |
| pharmaceutical_tx_ended_days_to     |       75   | [Not Available]:601                                                        |        504 | 122 (27) | 147 (24) | 140 (22)                                                                                  |
| treatment_best_response             |       26.8 | [Not Available]:1455, [Not Applicable]:176, [Unknown]:126, [Discrepancy]:4 |          4 | Complete Response (542) | Clinical Progressive Disease (55) | Stable Disease (36)                               |
| days_to_stem_cell_transplantation   |        0   | [Not Available]:2406                                                       |          0 |                                                                                                                 |
| pharm_regimen                       |        0   | [Not Available]:2406                                                       |          0 |                                                                                                                 |
| pharm_regimen_other                 |        0   | [Not Available]:2406                                                       |          0 |                                                                                                                 |
| pharma_adjuvant_cycles_count        |       35.9 | [Not Available]:1543                                                       |         31 | 4 (471) | 6 (110) | 3 (67)                                                                                      |
| pharma_type_other                   |        0.9 | [Not Available]:2384                                                       |         11 | Bisphosphonate (5) | Phase III Clinical Trial (4) | Bisphosphonate therapy (3)                                  |
| pharmaceutical_tx_dose_units        |       47.4 | [Not Available]:1265                                                       |         11 | mg (566) | mg/day (317) | mg/m2 (223)                                                                           |
| pharmaceutical_tx_total_dose_units  |       35.4 | [Not Available]:1555                                                       |          8 | mg (769) | mg/day (58) | mg/m2 (14)                                                                             |
| prescribed_dose                     |       46.9 | [Not Available]:1278                                                       |        324 | 1 (142) | 20 (127) | 600 (72)                                                                                   |
| regimen_number                      |       47.4 | [Not Available]:1265, [Unknown]:1                                          |         37 | 1 (678) | 2 (184) | 3 (99)                                                                                      |
| route_of_administration             |       51.7 | [Not Available]:1163                                                       |          6 | IV (842) | PO (379) | IM (12)                                                                                   |
| stem_cell_transplantation           |        0   | [Not Available]:2406                                                       |          0 |                                                                                                                 |
| stem_cell_transplantation_type      |        0   | [Not Available]:2406                                                       |          0 |                                                                                                                 |
| therapy_regimen                     |       54.7 | [Not Available]:1090                                                       |          5 | ADJUVANT (1257) | RECURRENCE (24) | PROGRESSION (17)                                                            |
| therapy_regimen_other               |        0.5 | [Not Applicable]:2393                                                      |         10 | Cancer Vaccine Trial (4) | Patient has oesteoporosis (Pre (1) | Maintenance (for osteopenia) (1)                |
| total_dose                          |       32.3 | [Not Available]:1629                                                       |        467 | 1 (27) | 20 (16) | 3600 (15)                                                                                    |
| tx_on_clinical_trial                |       45.1 | [Not Available]:1321                                                       |          2 | NO (992) | YES (93)                                                                                             |

### gdc_clinical_follow_up_v1.5 (114행 × 63열)

| column                                            |   filled_% | gdc_codes                              |   n_unique | examples                                                                                                     |
|:--------------------------------------------------|-----------:|:---------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                                  |      100   |                                        |        113 | ccd4a24b-d8cc-4686-9dee-c98b0c (2) | 197428f7-bd77-4c5f-8119-87157b (1) | b5fba77b-1f50-4e71-95b2-566afb (1) |
| bcr_patient_barcode                               |      100   |                                        |        113 | TCGA-A2-A04P (2) | TCGA-A2-A04N (1) | TCGA-A2-A04Q (1)                                                       |
| bcr_followup_barcode                              |      100   |                                        |        114 | TCGA-A2-A04N-F9336 (1) | TCGA-A2-A04P-F2652 (1) | TCGA-A2-A04P-F10241 (1)                                    |
| bcr_followup_uuid                                 |      100   |                                        |        114 | B8DC7DC2-B3A7-4D0A-BFD6-936C98 (1) | 0D1BD57A-F783-438D-9F39-8A7519 (1) | 1966A070-7389-434A-BE2F-01ABFB (1) |
| form_completion_date                              |      100   |                                        |         27 | 2010-11-16 (33) | 2010-9-19 (13) | 2010-12-8 (10)                                                            |
| radiation_treatment_adjuvant                      |      100   |                                        |          2 | YES (73) | NO (41)                                                                                           |
| pharmaceutical_tx_adjuvant                        |      100   |                                        |          2 | YES (109) | NO (5)                                                                                           |
| tumor_status                                      |      100   |                                        |          2 | TUMOR FREE (101) | WITH TUMOR (13)                                                                           |
| vital_status                                      |      100   |                                        |          2 | Alive (104) | Dead (10)                                                                                      |
| last_contact_days_to                              |       90.4 | [Not Available]:11                     |        100 | 1948 (2) | 267 (2) | 1519 (2)                                                                                |
| death_days_to                                     |        8.8 | [Not Applicable]:104                   |          9 | 548 (2) | 1920 (1) | 754 (1)                                                                                 |
| new_tumor_event_dx_days_to                        |        9.6 | [Not Available]:103                    |         11 | 179 (1) | 180 (1) | 1470 (1)                                                                                 |
| new_tumor_event_radiation_tx                      |       16.7 | [Not Available]:95                     |          2 | NO (16) | YES (3)                                                                                            |
| new_tumor_event_pharmaceutical_tx                 |       15.8 | [Not Available]:96                     |          2 | YES (9) | NO (9)                                                                                             |
| nte_er_status                                     |        2.6 | [Not Available]:107, [Not Evaluated]:4 |          2 | Positive (2) | Negative (1)                                                                                  |
| nte_er_status_ihc__positive                       |        2.6 | [Not Available]:111                    |          2 | 90-99% (2) | <10% (1)                                                                                        |
| nte_er_ihc_intensity_score                        |        1.8 | [Not Available]:112                    |          1 | 4+ (2)                                                                                                       |
| nte_er_positivity_other_scale                     |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_er_positivity_define_method                   |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_pr_status_by_ihc                              |        2.6 | [Not Available]:107, [Not Evaluated]:4 |          1 | Positive (3)                                                                                                 |
| nte_pr_status_ihc__positive                       |        2.6 | [Not Available]:111                    |          3 | 80-89% (1) | 10-19% (1) | 70-79% (1)                                                                         |
| nte_pr_ihc_intensity_score                        |        2.6 | [Not Available]:111                    |          2 | 2+ (2) | 1+ (1)                                                                                              |
| nte_pr_positivity_other_scale                     |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_pr_positivity_define_method                   |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_her2_status                                   |        2.6 | [Not Available]:107, [Not Evaluated]:4 |          2 | Negative (2) | Equivocal (1)                                                                                 |
| nte_her2_status_ihc__positive                     |        2.6 | [Not Available]:111                    |          2 | <10% (2) | 20-29% (1)                                                                                        |
| nte_her2_positivity_ihc_score                     |        2.6 | [Not Available]:111                    |          2 | 1+ (2) | 2+ (1)                                                                                              |
| nte_her2_positivity_other_scale                   |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_her2_positivity_method                        |        2.6 | [Not Available]:111                    |          1 | 3+ POSITIVE (3)                                                                                              |
| nte_her2_fish_status                              |        0.9 | [Not Available]:107, [Not Evaluated]:6 |          1 | Negative (1)                                                                                                 |
| nte_her2_signal_number                            |        0.9 | [Not Available]:113                    |          1 | 4.0 (1)                                                                                                      |
| nte_cent_17_signal_number                         |        0.9 | [Not Available]:113                    |          1 | 2.4 (1)                                                                                                      |
| her2_cent17_counted_cells_count                   |        0.9 | [Not Available]:113                    |          1 | 40 (1)                                                                                                       |
| nte_cent_17_her2_ratio                            |        0.9 | [Not Available]:113                    |          1 | 1.7 (1)                                                                                                      |
| nte_cent17_her2_other_scale                       |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| nte_her2_fish_define_method                       |        0.9 | [Not Available]:113                    |          1 | RATIO > 2.2 (1)                                                                                              |
| cent17_copy_number                                |        0.9 | [Not Available]:113                    |          1 | 49 (1)                                                                                                       |
| days_to_additional_surgery_locoregional_procedure |        2.6 | [Not Available]:111                    |          3 | 179 (1) | 1239 (1) | 295 (1)                                                                                 |
| days_to_additional_surgery_metastatic_procedure   |        2.6 | [Not Available]:111                    |          3 | 1922 (1) | 1066 (1) | 143 (1)                                                                                |
| days_to_last_known_alive                          |        1.8 | [Not Available]:112                    |          2 | 2576 (1) | 735 (1)                                                                                           |
| er_ihc_score                                      |        0.9 | [Not Available]:113                    |          1 | 2+ (1)                                                                                                       |
| er_positivity_method                              |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| er_positivity_scale_other                         |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| er_status_by_ihc                                  |        2.6 | [Not Available]:111                    |          2 | Negative (2) | Positive (1)                                                                                  |
| er_status_ihc_Percent_Positive                    |        0.9 | [Not Available]:113                    |          1 | 20-29% (1)                                                                                                   |
| her2_and_cent17_cells_count                       |        0.9 | [Not Available]:113                    |          1 | 31 (1)                                                                                                       |
| her2_and_cent17_scale_other                       |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| her2_cent17_ratio                                 |        1.8 | [Not Available]:112                    |          2 | 1.0 (1) | 1.3 (1)                                                                                            |
| her2_copy_number                                  |        0.9 | [Not Available]:113                    |          1 | 62 (1)                                                                                                       |
| her2_fish_method                                  |        0.9 | [Not Available]:113                    |          1 | >=2.0 Positive (1)                                                                                           |
| her2_fish_status                                  |        1.8 | [Not Available]:110, [Not Evaluated]:2 |          1 | Negative (2)                                                                                                 |
| her2_ihc_percent_positive                         |        0.9 | [Not Available]:113                    |          1 | <10% (1)                                                                                                     |
| her2_ihc_score                                    |        1.8 | [Not Available]:112                    |          1 | 0 (2)                                                                                                        |
| her2_positivity_method_text                       |        0.9 | [Not Available]:113                    |          1 | 3+ Positive (1)                                                                                              |
| her2_positivity_scale_other                       |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| her2_status_by_ihc                                |        1.8 | [Not Available]:111, [Not Evaluated]:1 |          1 | Negative (2)                                                                                                 |
| new_tumor_event_surgery                           |       14   | [Not Available]:98                     |          2 | NO (10) | YES (6)                                                                                            |
| new_tumor_event_surgery_met                       |        9.6 | [Not Available]:103                    |          1 | NO (11)                                                                                                      |
| pr_positivity_define_method                       |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| pr_positivity_ihc_intensity_score                 |        0.9 | [Not Available]:113                    |          1 | 2+ (1)                                                                                                       |
| pr_positivity_scale_other                         |        0   | [Not Available]:114                    |          0 |                                                                                                              |
| pr_status_by_ihc                                  |        2.6 | [Not Available]:111                    |          2 | Negative (2) | Positive (1)                                                                                  |
| pr_status_ihc_percent_positive                    |        0.9 | [Not Available]:113                    |          1 | 60-69% (1)                                                                                                   |

### gdc_clinical_follow_up_v2.1 (523행 × 45열)

| column                                          |   filled_% | gdc_codes                                                |   n_unique | examples                                                                                                     |
|:------------------------------------------------|-----------:|:---------------------------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                                |      100   |                                                          |        516 | a1872011-b928-4189-ac02-e87506 (2) | eda6d2d5-4199-4f76-a45b-1d0401 (2) | cc510968-fe52-4109-a79f-74f216 (2) |
| bcr_patient_barcode                             |      100   |                                                          |        516 | TCGA-A2-A0YC (2) | TCGA-AR-A1AR (2) | TCGA-D8-A1XJ (2)                                                       |
| bcr_followup_barcode                            |      100   |                                                          |        523 | TCGA-A1-A0SK-F15926 (1) | TCGA-A2-A0CL-F14457 (1) | TCGA-A2-A0CP-F13741 (1)                                  |
| bcr_followup_uuid                               |      100   |                                                          |        523 | 5F98C53B-5EE8-444C-9089-1E7EF4 (1) | CE691542-B93E-4911-B72C-B246A8 (1) | 7BF10142-06B6-4D5A-BF38-AE1D5E (1) |
| form_completion_date                            |      100   |                                                          |        139 | 2011-12-12 (23) | 2011-7-12 (20) | 2011-8-22 (20)                                                            |
| radiation_treatment_adjuvant                    |       99.4 | [Not Available]:3                                        |          2 | YES (285) | NO (235)                                                                                         |
| pharmaceutical_tx_adjuvant                      |       99   | [Not Available]:5                                        |          2 | YES (474) | NO (44)                                                                                          |
| tumor_status                                    |       86.6 | [Not Available]:70                                       |          2 | TUMOR FREE (404) | WITH TUMOR (49)                                                                           |
| vital_status                                    |       99.8 | [Not Available]:1                                        |          2 | Alive (471) | Dead (51)                                                                                      |
| last_contact_days_to                            |       90.1 | [Not Available]:52                                       |        399 | 385 (6) | 575 (4) | 554 (4)                                                                                  |
| death_days_to                                   |        9.6 | [Not Applicable]:472, [Not Available]:1                  |         47 | 524 (2) | 2965 (2) | 563 (2)                                                                                 |
| new_tumor_event_dx_indicator                    |       99.2 | [Not Available]:4                                        |          2 | NO (455) | YES (64)                                                                                          |
| new_tumor_event_type                            |       11.7 | [Not Available]:462                                      |          3 | Distant Metastasis (40) | New Primary Tumor (11) | Locoregional Disease (10)                                 |
| new_tumor_event_site                            |       10.5 | [Not Available]:468                                      |          5 | Other, specify (21) | Bone (17) | Lung (7)                                                                   |
| new_tumor_event_site_other                      |        4.4 | [Not Available]:500                                      |         19 | Breast (3) | Liver (2) | Chest Wall (2)                                                                      |
| new_tumor_event_dx_days_to                      |       11.7 | [Not Applicable]:455, [Not Available]:6, [Discrepancy]:1 |         60 | 188 (2) | 756 (1) | 798 (1)                                                                                  |
| new_tumor_event_radiation_tx                    |        7.6 | [Not Available]:483                                      |          2 | NO (25) | YES (15)                                                                                           |
| new_tumor_event_pharmaceutical_tx               |        8   | [Not Available]:481                                      |          2 | YES (31) | NO (11)                                                                                           |
| nte_er_status                                   |        3.8 | [Not Available]:485, [Not Evaluated]:18                  |          2 | Positive (10) | Negative (10)                                                                                |
| nte_er_status_ihc__positive                     |        1   | [Not Available]:518                                      |          3 | 90-99% (3) | 10-19% (1) | 20-29% (1)                                                                         |
| nte_er_positivity_scale_used                    |        1.3 | [Not Available]:516                                      |          2 | 4 Point Scale (5) | Other Reporting Scale (2)                                                                |
| nte_er_ihc_intensity_score                      |        0.2 | [Not Available]:522                                      |          1 | 4+ (1)                                                                                                       |
| nte_er_positivity_other_scale                   |        0.8 | [Not Available]:519                                      |          3 | fmol/mg (2) | 133 fmol/mg (1) | Allred score = 0 (1)                                                         |
| nte_er_positivity_define_method                 |        0.8 | [Not Available]:519                                      |          2 | image cytometry (3) | Allred score 0+0 = 0 (1)                                                               |
| nte_pr_status_by_ihc                            |        3.8 | [Not Available]:486, [Not Evaluated]:17                  |          2 | Negative (11) | Positive (9)                                                                                 |
| nte_pr_status_ihc__positive                     |        1   | [Not Available]:518                                      |          5 | 90-99% (1) | 80-89% (1) | 10-19% (1)                                                                         |
| nte_pr_positivity_scale_used                    |        1.3 | [Not Available]:516                                      |          2 | 4 Point Scale (5) | Other Reporting Scale (2)                                                                |
| nte_pr_ihc_intensity_score                      |        0.2 | [Not Available]:522                                      |          1 | 2+ (1)                                                                                                       |
| nte_pr_positivity_other_scale                   |        0.8 | [Not Available]:519                                      |          3 | fmol/mg (2) | 105 fmol/mg (1) | Allred Score = 0 (1)                                                         |
| nte_pr_positivity_define_method                 |        0.8 | [Not Available]:519                                      |          2 | image cytometry (3) | Allred score 0+0 = 0 (1)                                                               |
| nte_her2_status                                 |        2.9 | [Not Available]:486, [Not Evaluated]:22                  |          2 | Negative (11) | Equivocal (4)                                                                                |
| nte_her2_status_ihc__positive                   |        0.8 | [Not Available]:519                                      |          3 | <10% (2) | 20-29% (1) | 30-39% (1)                                                                           |
| nte_her2_positivity_ihc_score                   |        1.7 | [Not Available]:514                                      |          3 | 2+ (4) | 1+ (4) | 0 (1)                                                                                      |
| nte_her2_positivity_other_scale                 |        0.4 | [Not Available]:521                                      |          1 | 3 Point Scale (2)                                                                                            |
| nte_her2_positivity_method                      |        0.2 | [Not Available]:522                                      |          1 | 3 Point Scale (1)                                                                                            |
| nte_her2_fish_status                            |        1   | [Not Available]:493, [Not Evaluated]:25                  |          1 | Negative (5)                                                                                                 |
| nte_her2_signal_number                          |        0.2 | [Not Available]:522                                      |          1 | 4.0 (1)                                                                                                      |
| nte_cent_17_signal_number                       |        0.2 | [Not Available]:522                                      |          1 | 2.4 (1)                                                                                                      |
| her2_cent17_counted_cells_count                 |        0.2 | [Not Available]:522                                      |          1 | 40 (1)                                                                                                       |
| nte_cent_17_her2_ratio                          |        0.6 | [Not Available]:520                                      |          3 | 1.7 (1) | 1.3 (1) | 0.95 (1)                                                                                 |
| nte_cent17_her2_other_scale                     |        0   | [Not Available]:523                                      |          0 |                                                                                                              |
| nte_her2_fish_define_method                     |        0.2 | [Not Available]:522                                      |          1 | RATIO >2.2 (1)                                                                                               |
| days_to_additional_surgery_metastatic_procedure |        3.8 | [Not Available]:503                                      |         20 | 756 (1) | 798 (1) | 559 (1)                                                                                  |
| followup_reason                                 |       99.4 | [Not Available]:3                                        |          2 | Scheduled Follow-up Submission (516) | Additional New Tumor Event (4)                                        |
| new_tumor_event_surgery                         |        9.9 | [Not Available]:471                                      |          2 | NO (32) | YES (20)                                                                                           |

### gdc_clinical_follow_up_v4.0 (716행 × 13열)

| column                       |   filled_% | gdc_codes                                         |   n_unique | examples                                                                                                     |
|:-----------------------------|-----------:|:--------------------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid             |      100   |                                                   |        619 | EBD1512A-4865-4193-97B3-F599D5 (3) | 28e9048a-e540-42de-a1f4-4ef894 (3) | E3FCBF94-D3EF-4A37-AA45-5297F9 (3) |
| bcr_patient_barcode          |      100   |                                                   |        619 | TCGA-AR-A1AM (3) | TCGA-AR-A24Q (3) | TCGA-AR-A2LE (3)                                                       |
| bcr_followup_barcode         |      100   |                                                   |        716 | TCGA-3C-AAAU-F68069 (1) | TCGA-3C-AAAU-F71341 (1) | TCGA-3C-AALI-F68057 (1)                                  |
| bcr_followup_uuid            |      100   |                                                   |        716 | 238F65F8-617D-4508-B006-20A31E (1) | D7B0BC51-D86F-4554-939E-EA9A24 (1) | 4A52CBB9-665B-420E-8AC4-6A1905 (1) |
| form_completion_date         |      100   |                                                   |        210 | 2013-10-2 (42) | 2013-3-2 (35) | 2015-3-30 (32)                                                              |
| followup_lost_to             |       96.4 | [Not Available]:26                                |          2 | NO (626) | YES (64)                                                                                          |
| radiation_treatment_adjuvant |       96.6 | [Unknown]:12, [Not Available]:11, [Discrepancy]:1 |          2 | YES (399) | NO (293)                                                                                         |
| pharmaceutical_tx_adjuvant   |       94.8 | [Unknown]:19, [Not Available]:12, [Discrepancy]:6 |          2 | YES (560) | NO (119)                                                                                         |
| tumor_status                 |       94.6 | [Unknown]:21, [Not Available]:18                  |          2 | TUMOR FREE (616) | WITH TUMOR (61)                                                                           |
| vital_status                 |       98.6 | [Not Available]:10                                |          2 | Alive (654) | Dead (52)                                                                                      |
| last_contact_days_to         |       91.3 | [Not Available]:62                                |        551 | 10 (15) | 396 (5) | 0 (5)                                                                                    |
| death_days_to                |        7.3 | [Not Applicable]:664                              |         52 | 548 (1) | 1468 (1) | 2348 (1)                                                                                |
| new_tumor_event_dx_indicator |       90.4 | [Unknown]:60, [Not Available]:9                   |          2 | NO (587) | YES (60)                                                                                          |

### gdc_clinical_follow_up_v4.0_nte (82행 × 35열)

| column                            |   filled_% | gdc_codes                              |   n_unique | examples                                                                                                     |
|:----------------------------------|-----------:|:---------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                  |      100   |                                        |         58 | ccd4a24b-d8cc-4686-9dee-c98b0c (4) | C07B122E-AC50-4DB2-ADD2-5617A5 (4) | A8E7D8A4-BBF0-496B-B387-8E014C (3) |
| bcr_patient_barcode               |      100   |                                        |         58 | TCGA-A2-A04P (4) | TCGA-GM-A2DA (4) | TCGA-A2-A3XU (3)                                                       |
| bcr_followup_barcode              |      100   |                                        |         61 | TCGA-A2-A04P-F71021 (4) | TCGA-GM-A2DA-F47040 (4) | TCGA-A2-A3XU-F34704 (3)                                  |
| new_tumor_event_type              |       82.9 | [Not Available]:14                     |          3 | Distant Metastasis (44) | Locoregional Recurrence (15) | New Primary Tumor (9)                               |
| new_tumor_event_site              |       79.3 | [Not Available]:17                     |          5 | Bone (23) | Other, specify (22) | Liver (9)                                                                  |
| new_tumor_event_site_other        |       29.3 | [Not Available]:58                     |         23 | Breast (2) | Axilla (1) | LEFT BREAST (1)                                                                    |
| new_tumor_event_dx_days_to        |       98.8 | [Not Available]:1                      |         71 | 596 (2) | 192 (2) | 443 (2)                                                                                  |
| new_tumor_event_surgery           |       69.5 | [Not Available]:24, [Unknown]:1        |          2 | NO (40) | YES (17)                                                                                           |
| new_tumor_event_surgery_days_to   |       20.7 | [Not Available]:65                     |         17 | 179 (1) | 1409 (1) | 3024 (1)                                                                                |
| new_tumor_event_radiation_tx      |       64.6 | [Not Available]:25, [Unknown]:4        |          2 | NO (35) | YES (18)                                                                                           |
| new_tumor_event_pharmaceutical_tx |       64.6 | [Not Available]:26, [Unknown]:3        |          2 | YES (34) | NO (19)                                                                                           |
| nte_er_status                     |       23.2 | [Not Available]:48, [Not Evaluated]:15 |          2 | Positive (14) | Negative (5)                                                                                 |
| nte_er_status_ihc__positive       |        6.1 | [Not Available]:77                     |          3 | 90-99% (3) | 50-59% (1) | <10% (1)                                                                           |
| nte_er_positivity_scale_used      |       11   | [Not Available]:73                     |          1 | 3 Point Scale (9)                                                                                            |
| nte_er_ihc_intensity_score        |        9.8 | [Not Available]:74                     |          2 | 3+ (6) | 2+ (2)                                                                                              |
| nte_er_positivity_other_scale     |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_er_positivity_define_method   |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_pr_status_by_ihc              |       20.7 | [Not Available]:51, [Not Evaluated]:14 |          2 | Negative (9) | Positive (8)                                                                                  |
| nte_pr_status_ihc__positive       |        6.1 | [Not Available]:77                     |          3 | <10% (3) | 10-19% (1) | 70-79% (1)                                                                           |
| nte_pr_positivity_scale_used      |       11   | [Not Available]:73                     |          1 | 3 Point Scale (9)                                                                                            |
| nte_pr_ihc_intensity_score        |        9.8 | [Not Available]:74                     |          3 | 2+ (4) | 1+ (2) | 3+ (2)                                                                                     |
| nte_pr_positivity_other_scale     |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_pr_positivity_define_method   |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_her2_status                   |       13.4 | [Not Available]:52, [Not Evaluated]:19 |          2 | Negative (8) | Positive (3)                                                                                  |
| nte_her2_status_ihc__positive     |        2.4 | [Not Available]:80                     |          2 | <10% (1) | 50-59% (1)                                                                                        |
| nte_her2_positivity_ihc_score     |        9.8 | [Not Available]:74                     |          3 | 1+ (5) | 3+ (2) | 2+ (1)                                                                                     |
| nte_her2_positivity_other_scale   |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_her2_positivity_method        |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_her2_fish_status              |        4.9 | [Not Available]:53, [Not Evaluated]:25 |          1 | Negative (4)                                                                                                 |
| nte_her2_signal_number            |        2.4 | [Not Available]:80                     |          2 | 4.4 (1) | 2.1 (1)                                                                                            |
| nte_cent_17_signal_number         |        2.4 | [Not Available]:80                     |          2 | 3.1 (1) | 2.2 (1)                                                                                            |
| her2_cent17_counted_cells_count   |        1.2 | [Not Available]:81                     |          1 | 200 (1)                                                                                                      |
| nte_cent_17_her2_ratio            |        4.9 | [Not Available]:78                     |          3 | 1.0 (2) | 1.2 (1) | 4.1 (1)                                                                                  |
| nte_cent17_her2_other_scale       |        0   | [Not Available]:82                     |          0 |                                                                                                              |
| nte_her2_fish_define_method       |        0   | [Not Available]:82                     |          0 |                                                                                                              |

### gdc_clinical_nte (119행 × 34열)

| column                            |   filled_% | gdc_codes                               |   n_unique | examples                                                                                                     |
|:----------------------------------|-----------:|:----------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                  |      100   |                                         |        113 | 3AF31FCF-AD0C-4FD9-A8E3-10F917 (5) | A8E7D8A4-BBF0-496B-B387-8E014C (3) | ccd4a24b-d8cc-4686-9dee-c98b0c (1) |
| bcr_patient_barcode               |      100   |                                         |        113 | TCGA-AR-A5QQ (5) | TCGA-A2-A3XU (3) | TCGA-A2-A04P (1)                                                       |
| new_tumor_event_type              |       13.4 | [Not Available]:103                     |          3 | Distant Metastasis (10) | Locoregional Recurrence (5) | New Primary Tumor (1)                                |
| new_tumor_event_site              |       12.6 | [Not Available]:104                     |          4 | Other, specify (6) | Bone (5) | Lung (3)                                                                     |
| new_tumor_event_site_other        |        5   | [Not Available]:113                     |          6 | Breast recurrence (1) | Chest wall (1) | malignant melanoma (1)                                              |
| new_tumor_event_dx_days_to        |       12.6 | [Not Available]:104                     |         11 | 301 (5) | 667 (1) | 574 (1)                                                                                  |
| new_tumor_event_surgery           |        8.4 | [Not Available]:108, [Unknown]:1        |          2 | NO (8) | YES (2)                                                                                             |
| new_tumor_event_surgery_days_to   |        1.7 | [Not Available]:117                     |          2 | 596 (1) | 181 (1)                                                                                            |
| new_tumor_event_radiation_tx      |        7.6 | [Not Available]:109, [Unknown]:1        |          2 | NO (5) | YES (4)                                                                                             |
| new_tumor_event_pharmaceutical_tx |        7.6 | [Not Available]:109, [Unknown]:1        |          2 | YES (8) | NO (1)                                                                                             |
| nte_er_status                     |       13.4 | [Not Evaluated]:90, [Not Available]:13  |          2 | Positive (10) | Negative (6)                                                                                 |
| nte_er_status_ihc__positive       |        6.7 | [Not Available]:111                     |          3 | <10% (4) | 70-79% (2) | 90-99% (2)                                                                           |
| nte_er_positivity_scale_used      |        5   | [Not Available]:113                     |          2 | 4 Point Scale (3) | 3 Point Scale (3)                                                                        |
| nte_er_ihc_intensity_score        |        3.4 | [Not Available]:115                     |          2 | 1+ (2) | 3+ (2)                                                                                              |
| nte_er_positivity_other_scale     |        0.8 | [Not Available]:118                     |          1 | 8 (1)                                                                                                        |
| nte_er_positivity_define_method   |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_pr_status_by_ihc              |       12.6 | [Not Evaluated]:91, [Not Available]:13  |          2 | Negative (10) | Positive (5)                                                                                 |
| nte_pr_status_ihc__positive       |        5   | [Not Available]:113                     |          1 | <10% (6)                                                                                                     |
| nte_pr_positivity_scale_used      |        5   | [Not Available]:113                     |          2 | 4 Point Scale (3) | 3 Point Scale (3)                                                                        |
| nte_pr_ihc_intensity_score        |        3.4 | [Not Available]:115                     |          2 | 1+ (3) | 2+ (1)                                                                                              |
| nte_pr_positivity_other_scale     |        0.8 | [Not Available]:118                     |          1 | Allred score=5 (1)                                                                                           |
| nte_pr_positivity_define_method   |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_her2_status                   |       10.9 | [Not Evaluated]:95, [Not Available]:11  |          2 | Negative (12) | Equivocal (1)                                                                                |
| nte_her2_status_ihc__positive     |        4.2 | [Not Available]:114                     |          1 | <10% (5)                                                                                                     |
| nte_her2_positivity_ihc_score     |        6.7 | [Not Available]:111                     |          2 | 1+ (7) | 2+ (1)                                                                                              |
| nte_her2_positivity_other_scale   |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_her2_positivity_method        |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_her2_fish_status              |        2.5 | [Not Evaluated]:102, [Not Available]:14 |          1 | Negative (3)                                                                                                 |
| nte_her2_signal_number            |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_cent_17_signal_number         |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| her2_cent17_counted_cells_count   |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_cent_17_her2_ratio            |        1.7 | [Not Available]:117                     |          2 | 1.09 (1) | 2.47 (1)                                                                                          |
| nte_cent17_her2_other_scale       |        0   | [Not Available]:119                     |          0 |                                                                                                              |
| nte_her2_fish_define_method       |        0   | [Not Available]:119                     |          0 |                                                                                                              |

### gdc_clinical_omf_v4.0 (82행 × 30열)

| column                                  |   filled_% | gdc_codes                                                                                                                                                                                                        |   n_unique | examples                                                                                                     |
|:----------------------------------------|-----------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                        |      100   |                                                                                                                                                                                                                  |         77 | 6cd9baf5-bbe0-4c1e-a87f-c53b3a (2) | 011b9b2d-ebe5-42bf-9662-d922fa (2) | 8F9AD301-6699-4078-A80D-886E40 (2) |
| bcr_patient_barcode                     |      100   |                                                                                                                                                                                                                  |         77 | TCGA-A7-A13G (2) | TCGA-A7-A26E (2) | TCGA-A7-A3J1 (2)                                                       |
| bcr_omf_barcode                         |      100   |                                                                                                                                                                                                                  |         82 | TCGA-5L-AAT0-O63720 (1) | TCGA-5L-AAT1-O63715 (1) | TCGA-A1-A0SP-O17587 (1)                                  |
| bcr_omf_uuid                            |      100   |                                                                                                                                                                                                                  |         82 | 9B562C8B-E54E-411D-B156-A55CAA (1) | A1B8ADE9-AAC6-4730-AA2E-24B454 (1) | 6B701B59-F79D-49CF-BB3C-0E9725 (1) |
| form_completion_date                    |      100   |                                                                                                                                                                                                                  |         56 | 2011-5-25 (14) | 2011-6-3 (3) | 2014-8-15 (2)                                                                |
| malignancy_type                         |      100   |                                                                                                                                                                                                                  |          2 | Prior Malignancy (46) | Synchronous Malignancy (36)                                                          |
| other_malignancy_dx_days_to             |       24.4 | [Not Available]:62                                                                                                                                                                                               |         16 | 0 (3) | 16 (3) | 39 (1)                                                                                      |
| surgery_indicator                       |       31.7 | [Not Available]:56                                                                                                                                                                                               |          2 | YES (24) | NO (2)                                                                                            |
| other_malignancy_surgery_type           |       28   | [Not Available]:59                                                                                                                                                                                               |         20 | Lumpectomy (2) | total mastectomy (2) | mastectomy (2)                                                       |
| other_malignancy_surgery_days_to        |       76.8 | [Not Available]:19                                                                                                                                                                                               |         55 | 0 (5) | 35 (2) | 34 (2)                                                                                      |
| pharmaceutical_therapy_indicator        |       96.3 | [Not Available]:3                                                                                                                                                                                                |          2 | NO (67) | YES (12)                                                                                           |
| pharmaceutical_therapy_extent           |        8.5 | [Not Available]:74, [Unknown]:1                                                                                                                                                                                  |          1 | Systemic (7)                                                                                                 |
| pharmaceutical_therapy_drug_name        |        8.5 | [Not Available]:73, [Not Available]|Adriamycin|Tamoxifen|Letrozole|Exemestane|[Not Available]:1, [Not Available]|Adriamycin|Taxol|Herceptin|Tamoxifen|Arimidex|Zometa (Bisphosphonate therapy)|[Not Available]:1 |          7 | Paclitaxel|Carboplatin (1) | Tamoxifen (1) | Adriamycin and cytoxan (1)                                      |
| pharmaceutical_tx_started_days_to       |        8.5 | [Not Available]:75                                                                                                                                                                                               |          7 | 57 (1) | -3779 (1) | -1428 (1)                                                                               |
| radiation_therapy_indicator             |       95.1 | [Not Available]:3, [Unknown]:1                                                                                                                                                                                   |          2 | NO (64) | YES (14)                                                                                           |
| radiation_therapy_extent                |        9.8 | [Not Available]:74                                                                                                                                                                                               |          1 | Locoregional (8)                                                                                             |
| history_rt_tx_to_site_of_tcga_tumor     |       11   | [Not Available]:73                                                                                                                                                                                               |          2 | NO (8) | YES (1)                                                                                             |
| radiation_therapy_started_days_to       |        7.3 | [Not Available]:76                                                                                                                                                                                               |          6 | 190 (1) | -3871 (1) | -1347 (1)                                                                              |
| ajcc_staging_edition                    |       39   | [Not Available]:50                                                                                                                                                                                               |          6 | 7th (17) | 6th (10) | 5th (2)                                                                                |
| ajcc_tumor_pathologic_pt                |       35.4 | [Not Available]:53                                                                                                                                                                                               |         10 | T2 (8) | T1c (5) | T1 (3)                                                                                    |
| ajcc_nodes_pathologic_pn                |       34.1 | [Not Available]:54                                                                                                                                                                                               |          6 | N0 (20) | NX (3) | N0 (i-) (2)                                                                               |
| ajcc_metastasis_pathologic_pm           |       34.1 | [Not Available]:54                                                                                                                                                                                               |          3 | M0 (22) | MX (5) | cM0 (i+) (1)                                                                              |
| ajcc_pathologic_tumor_stage             |       34.1 | [Not Available]:54                                                                                                                                                                                               |          8 | Stage IIA (6) | Stage IA (6) | Stage I (6)                                                                   |
| clinical_stage                          |        1.2 | [Not Available]:50, [Not Applicable]:31                                                                                                                                                                          |          1 | Stage IB2 (1)                                                                                                |
| other_malignancy_anatomic_site          |       98.8 | [Not Available]:1                                                                                                                                                                                                |         21 | Breast (48) | Kidney (4) | Colon (4)                                                                         |
| other_malignancy_anatomic_site_text     |        1.2 | [Not Applicable]:81                                                                                                                                                                                              |          1 | Nose (1)                                                                                                     |
| other_malignancy_histological_type      |       81.7 | [Not Available]:15                                                                                                                                                                                               |          4 | Other, specify (59) | Adenocarcinoma, Not Otherwise  (4) | Kidney Clear Cell Renal Carcin (3)                |
| other_malignancy_histological_type_text |       72   | [Not Applicable]:23                                                                                                                                                                                              |         42 | Infiltrating Ductal Carcinoma (5) | DCIS (3) | malignant neoplasm of colon, u (3)                            |
| other_malignancy_laterality             |       62.2 | [Not Available]:27, [Not Applicable]:4                                                                                                                                                                           |          2 | Right (29) | Left (22)                                                                                       |
| stage_other                             |        0   | [Not Available]:82                                                                                                                                                                                               |          0 |                                                                                                              |

### gdc_clinical_patient (1,097행 × 112열)

| column                               |   filled_% | gdc_codes                                             |   n_unique | examples                                                                                                          |
|:-------------------------------------|-----------:|:------------------------------------------------------|-----------:|:------------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                     |      100   |                                                       |       1097 | 6E7D5EC6-A469-467C-B748-237353 (1) | 55262FCB-1B01-4480-B322-365704 (1) | 427D0648-3F77-4FFC-B52C-898554 (1)      |
| bcr_patient_barcode                  |      100   |                                                       |       1097 | TCGA-3C-AAAU (1) | TCGA-3C-AALI (1) | TCGA-3C-AALJ (1)                                                            |
| form_completion_date                 |      100   |                                                       |        315 | 2011-5-27 (91) | 2010-11-2 (28) | 2011-8-2 (18)                                                                   |
| prospective_collection               |       99.6 | [Not Available]:4                                     |          2 | NO (731) | YES (362)                                                                                              |
| retrospective_collection             |       99.6 | [Not Available]:4                                     |          2 | YES (731) | NO (362)                                                                                              |
| birth_days_to                        |       98.6 | [Not Available]:15                                    |       1045 | -32872 (5) | -32873 (3) | -22199 (3)                                                                              |
| gender                               |      100   |                                                       |          2 | FEMALE (1085) | MALE (12)                                                                                         |
| menopause_status                     |       91.8 | [Not Available]:67, [Unknown]:17, [Not Evaluated]:6   |          4 | Post (prior bilateral ovariect (705) | Pre (<6 months since LMP AND n (229) | Peri (6-12 months since last m (39) |
| race                                 |       91.3 | [Not Available]:92, [Not Evaluated]:3                 |          4 | WHITE (757) | BLACK OR AFRICAN AMERICAN (183) | ASIAN (61)                                                        |
| ethnicity                            |       84.1 | [Not Available]:163, [Unknown]:8, [Not Evaluated]:3   |          2 | NOT HISPANIC OR LATINO (884) | HISPANIC OR LATINO (39)                                                            |
| history_other_malignancy             |       99.9 | [Discrepancy]:1                                       |          2 | No (1028) | Yes (68)                                                                                              |
| history_neoadjuvant_treatment        |       99.8 | [Not Available]:1, [Discrepancy]:1                    |          2 | No (1082) | Yes (13)                                                                                              |
| tumor_status                         |       88.6 | [Not Available]:105, [Unknown]:20                     |          2 | TUMOR FREE (878) | WITH TUMOR (94)                                                                                |
| vital_status                         |      100   |                                                       |          2 | Alive (993) | Dead (104)                                                                                          |
| last_contact_days_to                 |       90.5 | [Not Available]:104                                   |        649 | 0 (59) | 10 (17) | 7 (9)                                                                                          |
| death_days_to                        |        9.5 | [Not Applicable]:993                                  |        101 | 2965 (3) | 991 (2) | 967 (1)                                                                                      |
| radiation_treatment_adjuvant         |       15.1 | [Not Available]:891, [Unknown]:40                     |          2 | NO (93) | YES (73)                                                                                                |
| pharmaceutical_tx_adjuvant           |       15   | [Not Available]:891, [Unknown]:41                     |          2 | YES (127) | NO (38)                                                                                               |
| histologic_diagnosis_other           |        6.9 | [Not Applicable]:1021                                 |         60 | Infiltrating ductal and lobula (11) | infiltrating ductal and mucino (2) | lobular/ductal (2)                     |
| initial_pathologic_dx_year           |       99.8 | [Not Available]:2                                     |         26 | 2010 (225) | 2009 (142) | 2011 (125)                                                                              |
| age_at_diagnosis                     |      100   |                                                       |         65 | 62 (51) | 63 (37) | 61 (36)                                                                                       |
| method_initial_path_dx               |       91.1 | [Not Available]:96, [Discrepancy]:2                   |          7 | Core needle biopsy (605) | Tumor resection (164) | Fine needle aspiration biopsy (97)                             |
| method_initial_path_dx_other         |        5.8 | [Not Applicable]:1029, [Unknown]:2, [Not Available]:2 |         14 | Patey's Surgery (22) | Biopsy, NOS (15) | intraoperative examination (12)                                         |
| surgical_procedure_first             |       95   | [Not Available]:53, [Unknown]:1, [Discrepancy]:1      |          4 | Modified Radical Mastectomy (322) | Other (273) | Lumpectomy (247)                                                |
| first_surgical_procedure_other       |       25.1 | [Not Available]:822                                   |         76 | Surgical Resection (77) | Segmental mastectomy (29) | Patey's Surgery (27)                                        |
| margin_status                        |       93.8 | [Not Available]:65, [Unknown]:3                       |          3 | Negative (919) | Positive (79) | Close (31)                                                                       |
| surgery_for_positive_margins         |        5   | [Not Available]:991, [Not Evaluated]:50, [Unknown]:1  |          4 | Mastectomy NOS (18) | Other (14) | Modified radical mastectomy (14)                                               |
| surgery_for_positive_margins_other   |        1.3 | [Not Applicable]:1083                                 |         14 | surgical resection (1) | Margin resection (1) | Skin excision (1)                                                 |
| margin_status_reexcision             |        5.4 | [Not Available]:1038                                  |          3 | Negative (56) | Positive (2) | Close (1)                                                                          |
| axillary_staging_method              |       80.3 | [Not Available]:214, [Unknown]:2                      |          5 | Axillary lymph node dissection (320) | Sentinel node biopsy alone (265) | Sentinel lymph node biopsy plu (239)    |
| axillary_staging_method_other        |        1.8 | [Not Available]:1077                                  |         19 | mastectomy with TLND (2) | Level 1 clearance (1) | Sentinel lymph node biopsy plu (1)                             |
| micromet_detection_by_ihc            |       66.5 | [Not Available]:348, [Unknown]:19                     |          2 | NO (467) | YES (263)                                                                                              |
| lymph_nodes_examined                 |       65.6 | [Not Available]:375, [Unknown]:2                      |          2 | YES (692) | NO (28)                                                                                               |
| lymph_nodes_examined_count           |       88.5 | [Not Available]:126                                   |         42 | 2 (116) | 1 (87) | 3 (70)                                                                                         |
| lymph_nodes_examined_he_count        |       84.7 | [Not Available]:168                                   |         31 | 0 (456) | 1 (155) | 2 (90)                                                                                        |
| lymph_nodes_examined_ihc_count       |       31.4 | [Not Available]:752                                   |          6 | 0 (284) | 1 (45) | 2 (9)                                                                                          |
| ajcc_staging_edition                 |       87.1 | [Not Available]:141                                   |          5 | 6th (445) | 7th (417) | 5th (57)                                                                                  |
| ajcc_tumor_pathologic_pt             |      100   |                                                       |         13 | T2 (633) | T1c (223) | T3 (137)                                                                                   |
| ajcc_nodes_pathologic_pn             |      100   |                                                       |         16 | N0 (333) | N1a (167) | N0 (i-) (154)                                                                              |
| ajcc_metastasis_pathologic_pm        |      100   |                                                       |          4 | M0 (906) | MX (163) | M1 (22)                                                                                     |
| ajcc_pathologic_tumor_stage          |       99   | [Discrepancy]:6, [Not Available]:5                    |         12 | Stage IIA (358) | Stage IIB (257) | Stage IIIA (155)                                                              |
| metastasis_site                      |        2.2 | [Not Available]:1073                                  |          9 | Bone (9) | Other, specify (4) | Bone|Liver (4)                                                                    |
| metastasis_site_other                |        0.6 | [Not Available]:1090                                  |          6 | skin (2) | Ovary (1) | Abdomen (1)                                                                                |
| er_status_by_ihc                     |       95.5 | [Not Evaluated]:49                                    |          3 | Positive (808) | Negative (238) | Indeterminate (2)                                                               |
| er_status_ihc_Percent_Positive       |       42.8 | [Not Available]:627                                   |         10 | 90-99% (245) | <10% (71) | 70-79% (49)                                                                            |
| er_positivity_scale_used             |       13.4 | [Not Available]:950                                   |          2 | 3 Point Scale (130) | 4 Point Scale (17)                                                                          |
| er_ihc_score                         |       19.5 | [Not Available]:883                                   |          5 | 3+ (121) | 2+ (38) | 4+ (22)                                                                                      |
| er_positivity_scale_other            |       22.1 | [Not Available]:855                                   |         65 | >75% (49) | Allred score = 8 (20) | H-SCORE (17)                                                                  |
| er_positivity_method                 |       19.7 | [Not Available]:880, [Unknown]:1                      |         54 | manual counting (42) | Image Analysis (30) | % IHC (17)                                                           |
| pr_status_by_ihc                     |       95.4 | [Not Evaluated]:50                                    |          3 | Positive (699) | Negative (344) | Indeterminate (4)                                                               |
| pr_status_ihc_percent_positive       |       39.2 | [Not Available]:667                                   |         10 | <10% (138) | 90-99% (105) | 70-79% (41)                                                                           |
| pr_positivity_scale_used             |       12.9 | [Not Available]:955                                   |          2 | 3 Point Scale (126) | 4 Point Scale (16)                                                                          |
| pr_positivity_ihc_intensity_score    |       19   | [Not Available]:889                                   |          5 | 3+ (87) | 2+ (44) | 1+ (35)                                                                                       |
| pr_positivity_scale_other            |       20.1 | [Not Available]:876                                   |         66 | >75% (34) | H-SCORE (17) | Allred score = 0 (16)                                                                  |
| pr_positivity_define_method          |       19.1 | [Not Available]:887, [Unknown]:1                      |         60 | manual counting (39) | Image Analysis (30) | Allred score 0+0 = 0 (16)                                            |
| her2_status_by_ihc                   |       83.8 | [Not Evaluated]:170, [Not Available]:8                |          4 | Negative (564) | Equivocal (179) | Positive (164)                                                                 |
| her2_ihc_percent_positive            |       19   | [Not Available]:889                                   |         10 | <10% (122) | 10-19% (26) | 90-99% (16)                                                                            |
| her2_ihc_score                       |       56.7 | [Not Available]:475                                   |          4 | 1+ (272) | 2+ (199) | 3+ (90)                                                                                     |
| her2_positivity_scale_other          |        1.3 | [Not Available]:1083                                  |          7 | 0 (5) | CISH (2) | Hercep Test  TM Dako (2)                                                                       |
| her2_positivity_method_text          |        8.2 | [Not Available]:1007                                  |         20 | 3+ Positive (18) | 3+ POSITIVE (18) | dextran coated charcoal (9)                                                 |
| her2_fish_status                     |       38.3 | [Not Evaluated]:596, [Not Available]:81               |          4 | Negative (333) | Positive (78) | Equivocal (5)                                                                    |
| her2_copy_number                     |       10.4 | [Not Available]:983                                   |         76 | not amplified (7) | 3.2 (6) | 2.4 (4)                                                                             |
| cent17_copy_number                   |        9.7 | [Not Available]:991                                   |         66 | 1.8 (5) | 1.7 (5) | 2.2 (5)                                                                                       |
| her2_and_cent17_cells_count          |        9.5 | [Not Available]:993                                   |         30 | 60 (29) | 40 (18) | 20 (17)                                                                                       |
| her2_cent17_ratio                    |       21.2 | [Not Available]:864                                   |         78 | 1.1 (34) | 1.3 (17) | 1.0 (17)                                                                                    |
| her2_and_cent17_scale_other          |        0.4 | [Not Available]:1093                                  |          4 | Vysis AutoVysion System (1) | >2.2 Positive (1) | HER2 amplification - negative (1)                               |
| her2_fish_method                     |        4.6 | [Not Available]:1047                                  |         30 | >=2.0 Positive (8) | PathVysion HER-2 DNA Probe Kit (6) | RATIO > = 2.0 (3)                                       |
| new_tumor_event_dx_indicator         |       17.8 | [Not Available]:891, [Unknown]:11                     |          2 | NO (185) | YES (10)                                                                                               |
| nte_er_status                        |        1.1 | [Not Available]:999, [Not Evaluated]:86               |          2 | Positive (9) | Negative (3)                                                                                       |
| nte_er_status_ihc__positive          |        0.5 | [Not Available]:1091                                  |          3 | 70-79% (2) | 90-99% (2) | <10% (2)                                                                                |
| nte_er_ihc_intensity_score           |        0.1 | [Not Available]:1096                                  |          1 | 3+ (1)                                                                                                            |
| nte_er_positivity_other_scale        |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_er_positivity_define_method      |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_pr_status_by_ihc                 |        1   | [Not Available]:999, [Not Evaluated]:87               |          2 | Negative (7) | Positive (4)                                                                                       |
| nte_pr_status_ihc__positive          |        0.4 | [Not Available]:1093                                  |          1 | <10% (4)                                                                                                          |
| nte_pr_ihc_intensity_score           |        0.1 | [Not Available]:1096                                  |          1 | 1+ (1)                                                                                                            |
| nte_pr_positivity_other_scale        |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_pr_positivity_define_method      |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_her2_status                      |        0.8 | [Not Available]:997, [Not Evaluated]:91               |          2 | Negative (8) | Equivocal (1)                                                                                      |
| nte_her2_status_ihc__positive        |        0.3 | [Not Available]:1094                                  |          1 | <10% (3)                                                                                                          |
| nte_her2_positivity_ihc_score        |        0.5 | [Not Available]:1092                                  |          2 | 1+ (4) | 2+ (1)                                                                                                   |
| nte_her2_positivity_other_scale      |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_her2_positivity_method           |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_her2_fish_status                 |        0.3 | [Not Available]:999, [Not Evaluated]:95               |          1 | Negative (3)                                                                                                      |
| nte_her2_signal_number               |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_cent_17_signal_number            |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| her2_cent17_counted_cells_count      |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_cent_17_her2_ratio               |        0.2 | [Not Available]:1095                                  |          2 | 1.09 (1) | 2.47 (1)                                                                                               |
| nte_cent17_her2_other_scale          |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| nte_her2_fish_define_method          |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| anatomic_neoplasm_subdivision        |      100   |                                                       |         53 | Left Upper Outer Quadrant (191) | Left (170) | Right Upper Outer Quadrant (158)                                   |
| clinical_M                           |        0   | [Not Applicable]:1097                                 |          0 |                                                                                                                   |
| clinical_N                           |        0   | [Not Applicable]:1097                                 |          0 |                                                                                                                   |
| clinical_T                           |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| clinical_stage                       |        0   | [Not Applicable]:1097                                 |          0 |                                                                                                                   |
| days_to_initial_pathologic_diagnosis |      100   |                                                       |          1 | 0 (1097)                                                                                                          |
| days_to_patient_progression_free     |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| days_to_tumor_progression            |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| disease_code                         |        0.5 | [Not Available]:1092                                  |          1 | FPPP (5)                                                                                                          |
| extranodal_involvement               |        0   | [Not Applicable]:1097                                 |          0 |                                                                                                                   |
| histological_type                    |       99.9 | [Not Available]:1                                     |          8 | Infiltrating Ductal Carcinoma (784) | Infiltrating Lobular Carcinoma (203) | Other, specify (46)                  |
| icd_10                               |      100   |                                                       |          7 | C50.9 (1086) | C50.3 (3) | C50.2 (2)                                                                              |
| icd_o_3_histology                    |      100   |                                                       |         22 | 8500/3 (778) | 8520/3 (201) | 8522/3 (28)                                                                         |
| icd_o_3_site                         |      100   |                                                       |          6 | C50.9 (1087) | C50.3 (3) | C50.2 (2)                                                                              |
| informed_consent_verified            |      100   |                                                       |          1 | YES (1097)                                                                                                        |
| metastatic_tumor_indicator           |       35.8 | [Not Available]:704                                   |          2 | NO (381) | YES (12)                                                                                               |
| patient_id                           |      100   |                                                       |       1097 | AAAU (1) | AALI (1) | AALJ (1)                                                                                    |
| project_code                         |        0.5 | [Not Available]:1092                                  |          1 | TCGA (5)                                                                                                          |
| site_of_primary_tumor_other          |        0   | [Not Applicable]:1097                                 |          0 |                                                                                                                   |
| stage_other                          |        0   | [Not Available]:1097                                  |          0 |                                                                                                                   |
| tissue_source_site                   |      100   |                                                       |         40 | BH (150) | A2 (102) | E2 (90)                                                                                     |
| tumor_tissue_site                    |      100   |                                                       |          1 | Breast (1097)                                                                                                     |

### gdc_clinical_radiation (618행 × 18열)

| column                              |   filled_% | gdc_codes                                             |   n_unique | examples                                                                                                     |
|:------------------------------------|-----------:|:------------------------------------------------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| bcr_patient_uuid                    |      100   |                                                       |        528 | A412B374-4D25-491F-B76F-DDAA98 (5) | 8d5fe6e8-d2cc-481f-a6a1-9cb6e7 (4) | C72CB184-462D-4009-9CDB-848782 (4) |
| bcr_patient_barcode                 |      100   |                                                       |        528 | TCGA-E9-A5UP (5) | TCGA-A2-A0EW (4) | TCGA-A2-A3XT (4)                                                       |
| bcr_radiation_barcode               |      100   |                                                       |        618 | TCGA-3C-AALI-R62901 (1) | TCGA-5L-AAT0-R63722 (1) | TCGA-5T-A9QA-R66894 (1)                                  |
| bcr_radiation_uuid                  |      100   |                                                       |        618 | 2FE462E5-9AEE-417B-BF7C-908AA6 (1) | F11A131E-E0C5-4BCE-A06B-BFEB00 (1) | C8E7F188-6E0A-469B-9BF2-4432E6 (1) |
| form_completion_date                |      100   |                                                       |        250 | 2012-12-11 (45) | 2010-11-17 (17) | 2014-5-1 (15)                                                            |
| radiation_therapy_type              |       96.9 | [Not Available]:15, [Unknown]:4                       |          5 | External (300) | EXTERNAL BEAM (292) | OTHER (5)                                                             |
| radiation_therapy_site              |       96.8 | [Not Available]:17, [Unknown]:3                       |          5 | Primary Tumor Field (453) | Regional site (123) | Distant Recurrence (9)                                     |
| radiation_total_dose                |       86.4 | [Not Available]:84                                    |        127 | 6040 (75) | 5040 (54) | 6000 (53)                                                                            |
| radiation_adjuvant_units            |       90.8 | [Not Available]:57                                    |          2 | cGy (438) | Gy (123)                                                                                         |
| radiation_adjuvant_fractions_total  |       72.3 | [Not Available]:171                                   |         49 | 33 (101) | 25 (63) | 28 (61)                                                                                 |
| radiation_therapy_started_days_to   |       96.1 | [Not Available]:23, [Discrepancy]:1                   |        267 | 153 (9) | 211 (8) | 181 (8)                                                                                  |
| radiation_therapy_ongoing_indicator |       99   | [Not Available]:6                                     |          2 | NO (608) | YES (4)                                                                                           |
| radiation_therapy_ended_days_to     |       96.6 | [Not Available]:21                                    |        275 | 212 (11) | 263 (9) | 246 (9)                                                                                 |
| treatment_best_response             |       42.2 | [Not Available]:329, [Unknown]:27, [Not Applicable]:1 |          4 | Complete Response (235) | Radiographic Progressive Disea (13) | Stable Disease (9)                           |
| course_number                       |       43.2 | [Not Available]:351                                   |          5 | 1 (253) | 2 (7) | 01 (4)                                                                                     |
| radiation_type_other                |        0.8 | [Not Applicable]:613                                  |          5 | Brachytherapy (Iridium 192) (1) | High-dose rate brachytherapy o (1) | Partial Breast irradiation usi (1)    |
| therapy_regimen                     |       50.5 | [Not Available]:306                                   |          4 | ADJUVANT (304) | PALLIATIVE (4) | RECURRENCE (3)                                                             |
| therapy_regimen_other               |        0   | [Not Available]:618                                   |          0 |                                                                                                              |

### cbio_clinical_attributes (60행 × 5열)

| column              |   filled_% | gdc_codes   |   n_unique | examples                                                                                                     |
|:--------------------|-----------:|:------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| clinicalAttributeId |        100 |             |         60 | AGE (1) | AJCC_PATHOLOGIC_TUMOR_STAGE (1) | AJCC_STAGING_EDITION (1)                                         |
| displayName         |        100 |             |         60 | Diagnosis Age (1) | Neoplasm Disease Stage America (1) | American Joint Committee on Ca (1)                  |
| description         |        100 |             |         60 | Age at which a condition or di (1) | The extent of a cancer, especi (1) | The version or edition of the  (1) |
| datatype            |        100 |             |          2 | STRING (41) | NUMBER (19)                                                                                    |
| patientAttribute    |        100 |             |          2 | True (41) | False (19)                                                                                       |

### cbio_clinical_patient (1,084행 × 41열)

| column                                     |   filled_% | gdc_codes   |   n_unique | examples                                                                                                     |
|:-------------------------------------------|-----------:|:------------|-----------:|:-------------------------------------------------------------------------------------------------------------|
| patientId                                  |      100   |             |       1084 | TCGA-3C-AAAU (1) | TCGA-3C-AALI (1) | TCGA-3C-AALJ (1)                                                       |
| AGE                                        |      100   |             |         65 | 62 (51) | 61 (36) | 63 (35)                                                                                  |
| AJCC_PATHOLOGIC_TUMOR_STAGE                |       99.5 |             |         12 | STAGE IIA (355) | STAGE IIB (255) | STAGE IIIA (155)                                                         |
| AJCC_STAGING_EDITION                       |       87.1 |             |          5 | 6TH (438) | 7TH (413) | 5TH (56)                                                                             |
| BUFFA_HYPOXIA_SCORE                        |       99.5 |             |         49 | -29 (45) | -27 (43) | -23 (42)                                                                               |
| CANCER_TYPE_ACRONYM                        |      100   |             |          1 | BRCA (1084)                                                                                                  |
| DAYS_LAST_FOLLOWUP                         |       90.4 |             |        753 | 10 (15) | 0 (12) | 385 (6)                                                                                   |
| DAYS_TO_BIRTH                              |       98.6 |             |       1032 | -32872 (5) | -32873 (3) | -22199 (3)                                                                         |
| DAYS_TO_INITIAL_PATHOLOGIC_DIAGNOSIS       |      100   |             |          1 | 0 (1084)                                                                                                     |
| DFS_MONTHS                                 |       86.8 |             |        736 | 0.32876352 (15) | 0 (11) | 18.21349903 (5)                                                                   |
| DFS_STATUS                                 |       86.9 |             |          2 | 0:DiseaseFree (858) | 1:Recurred/Progressed (84)                                                             |
| DSS_MONTHS                                 |       99.8 |             |        824 | 0.32876352 (15) | 0 (13) | 12.65739554 (7)                                                                   |
| DSS_STATUS                                 |       98.2 |             |          2 | 0:ALIVE OR DEAD TUMOR FREE (981) | 1:DEAD WITH TUMOR (83)                                                    |
| ETHNICITY                                  |       84.4 |             |          2 | Not Hispanic Or Latino (877) | Hispanic Or Latino (38)                                                       |
| FORM_COMPLETION_DATE                       |      100   |             |        314 | 5/27/11 (86) | 11/2/10 (28) | 8/2/11 (18)                                                                    |
| GENETIC_ANCESTRY_LABEL                     |       88.7 |             |         10 | EUR (807) | AFR (83) | AFR_ADMIX (42)                                                                        |
| HISTORY_NEOADJUVANT_TRTYN                  |       99.9 |             |          2 | No (1077) | Yes (6)                                                                                          |
| ICD_10                                     |      100   |             |          7 | C50.9 (1073) | C50.3 (3) | C50.2 (2)                                                                         |
| ICD_O_3_HISTOLOGY                          |      100   |             |         22 | 8500/3 (768) | 8520/3 (199) | 8522/3 (28)                                                                    |
| ICD_O_3_SITE                               |      100   |             |          6 | C50.9 (1074) | C50.3 (3) | C50.2 (2)                                                                         |
| INFORMED_CONSENT_VERIFIED                  |      100   |             |          1 | Yes (1084)                                                                                                   |
| IN_PANCANPATHWAYS_FREEZE                   |      100   |             |          2 | Yes (981) | No (103)                                                                                         |
| NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT    |       81.6 |             |          2 | No (785) | Yes (100)                                                                                         |
| OS_MONTHS                                  |      100   |             |        826 | 0.32876352 (15) | 0 (13) | 12.65739554 (7)                                                                   |
| OS_STATUS                                  |      100   |             |          2 | 0:LIVING (933) | 1:DECEASED (151)                                                                            |
| OTHER_PATIENT_ID                           |      100   |             |       1084 | 6E7D5EC6-A469-467C-B748-237353 (1) | 55262FCB-1B01-4480-B322-365704 (1) | 427D0648-3F77-4FFC-B52C-898554 (1) |
| PATH_M_STAGE                               |      100   |             |          4 | M0 (895) | MX (162) | M1 (21)                                                                                |
| PATH_N_STAGE                               |      100   |             |         16 | N0 (329) | N1A (164) | N0 (I-) (154)                                                                         |
| PATH_T_STAGE                               |      100   |             |         13 | T2 (626) | T1C (219) | T3 (136)                                                                              |
| PERSON_NEOPLASM_CANCER_STATUS              |       88.7 |             |          2 | Tumor Free (870) | With Tumor (91)                                                                           |
| PFS_MONTHS                                 |       99.8 |             |        821 | 0.32876352 (15) | 0 (13) | 13.01903541 (6)                                                                   |
| PFS_STATUS                                 |       99.9 |             |          2 | 0:CENSORED (938) | 1:PROGRESSION (145)                                                                       |
| PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT |       66.4 |             |          2 | Yes (687) | No (33)                                                                                          |
| PRIOR_DX                                   |       99.9 |             |          2 | No (1025) | Yes (58)                                                                                         |
| RACE                                       |       91.7 |             |          4 | White (751) | Black or African American (182) | Asian (60)                                                   |
| RADIATION_THERAPY                          |       90.7 |             |          2 | Yes (549) | No (434)                                                                                         |
| RAGNUM_HYPOXIA_SCORE                       |       99.5 |             |         28 | 14 (81) | 10 (68) | 12 (66)                                                                                  |
| SAMPLE_COUNT                               |      100   |             |          1 | 1 (1084)                                                                                                     |
| SEX                                        |      100   |             |          2 | Female (1072) | Male (12)                                                                                    |
| SUBTYPE                                    |       90.5 |             |          5 | BRCA_LumA (499) | BRCA_LumB (197) | BRCA_Basal (171)                                                         |
| WINTER_HYPOXIA_SCORE                       |       99.5 |             |         60 | -18 (50) | -32 (49) | -8 (46)                                                                                |

### cbio_clinical_sample (1,084행 × 20열)

| column                                    |   filled_% | gdc_codes   |   n_unique | examples                                                                                                          |
|:------------------------------------------|-----------:|:------------|-----------:|:------------------------------------------------------------------------------------------------------------------|
| patientId                                 |      100   |             |       1084 | TCGA-3C-AAAU (1) | TCGA-3C-AALI (1) | TCGA-3C-AALJ (1)                                                            |
| sampleId                                  |      100   |             |       1084 | TCGA-3C-AAAU-01 (1) | TCGA-3C-AALI-01 (1) | TCGA-3C-AALJ-01 (1)                                                   |
| ANEUPLOIDY_SCORE                          |       96   |             |         36 | 4 (74) | 5 (72) | 6 (64)                                                                                          |
| CANCER_TYPE                               |      100   |             |          1 | Breast Cancer (1084)                                                                                              |
| CANCER_TYPE_DETAILED                      |      100   |             |          6 | Breast Invasive Ductal Carcino (780) | Breast Invasive Lobular Carcin (201) | Breast Invasive Carcinoma (NOS (77) |
| FRACTION_GENOME_ALTERED                   |       98.5 |             |        966 | 0.0 (13) | 1.0E-4 (6) | 0.1153 (3)                                                                                |
| MSI_SCORE_MANTIS                          |       95.4 |             |        675 | 0.2894 (6) | 0.2846 (4) | 0.2932 (4)                                                                              |
| MSI_SENSOR_SCORE                          |       99.2 |             |        186 | 0 (131) | 0.01 (78) | 0.02 (38)                                                                                   |
| MUTATION_COUNT                            |       98.3 |             |        202 | 0 (57) | 27 (38) | 28 (29)                                                                                        |
| ONCOTREE_CODE                             |      100   |             |          6 | IDC (780) | ILC (201) | BRCNOS (77)                                                                               |
| SAMPLE_TYPE                               |      100   |             |          1 | Primary (1084)                                                                                                    |
| SOMATIC_STATUS                            |      100   |             |          1 | Matched (1084)                                                                                                    |
| TBL_SCORE                                 |       99.8 |             |        350 | 3 (22) | 2 (21) | 5 (16)                                                                                          |
| TISSUE_PROSPECTIVE_COLLECTION_INDICATOR   |       99.6 |             |          2 | No (719) | Yes (361)                                                                                              |
| TISSUE_RETROSPECTIVE_COLLECTION_INDICATOR |       99.6 |             |          2 | Yes (719) | No (361)                                                                                              |
| TISSUE_SOURCE_SITE                        |      100   |             |         40 | University of Pittsburgh (150) | Walter Reed (101) | Roswell Park (88)                                            |
| TISSUE_SOURCE_SITE_CODE                   |      100   |             |         40 | BH (150) | A2 (101) | E2 (88)                                                                                     |
| TMB_NONSYNONYMOUS                         |       98.3 |             |        208 | 0 (57) | 0.933333333 (31) | 0.8 (27)                                                                              |
| TUMOR_TISSUE_SITE                         |      100   |             |          1 | Breast (1084)                                                                                                     |
| TUMOR_TYPE                                |      100   |             |          9 | Infiltrating Ductal Carcinoma (774) | Infiltrating Lobular Carcinoma (201) | Other (46)                           |

### cbio_cna_biomarker_genes (1,070행 × 10열)

| column    |   filled_% | gdc_codes   |   n_unique | examples                                                        |
|:----------|-----------:|:------------|-----------:|:----------------------------------------------------------------|
| patientId |        100 |             |       1070 | TCGA-3C-AAAU (1) | TCGA-3C-AALI (1) | TCGA-3C-AALJ (1)          |
| sampleId  |        100 |             |       1070 | TCGA-3C-AAAU-01 (1) | TCGA-3C-AALI-01 (1) | TCGA-3C-AALJ-01 (1) |
| AKT1      |        100 |             |          5 | 0 (601) | -1 (296) | 1 (159)                                    |
| BRCA1     |        100 |             |          5 | 0 (490) | -1 (363) | 1 (199)                                    |
| BRCA2     |        100 |             |          5 | 0 (511) | -1 (429) | 1 (108)                                    |
| ERBB2     |        100 |             |          4 | 0 (481) | -1 (260) | 1 (206)                                    |
| ESR1      |        100 |             |          5 | 0 (572) | -1 (328) | 1 (146)                                    |
| PALB2     |        100 |             |          4 | 1 (508) | 0 (435) | -1 (90)                                     |
| PIK3CA    |        100 |             |          4 | 0 (680) | 1 (298) | -1 (58)                                     |
| PTEN      |        100 |             |          5 | 0 (659) | -1 (269) | 1 (83)                                     |

### cbio_mutations (84,226행 × 19열)

| column           |   filled_% | gdc_codes   |   n_unique | examples                                                                      |
|:-----------------|-----------:|:------------|-----------:|:------------------------------------------------------------------------------|
| patientId        |        100 |             |       1009 | TCGA-AN-A046 (5400) | TCGA-AC-A23H (4259) | TCGA-EW-A2FV (3879)               |
| sampleId         |        100 |             |       1009 | TCGA-AN-A046-01 (5400) | TCGA-AC-A23H-01 (4259) | TCGA-EW-A2FV-01 (3879)      |
| gene             |        100 |             |      16488 | PIK3CA (387) | TP53 (353) | TTN (311)                                         |
| entrezGeneId     |        100 |             |      16488 | 5290 (387) | 7157 (353) | 7273 (311)                                          |
| proteinChange    |        100 |             |      59570 | H1047R (129) | M1? (89) | E545K (67)                                          |
| mutationType     |        100 |             |         10 | Missense_Mutation (64473) | Frame_Shift_Del (9171) | Nonsense_Mutation (5417) |
| variantType      |        100 |             |          4 | SNP (73026) | DEL (10176) | INS (1022)                                        |
| ncbiBuild        |        100 |             |          2 | GRCh37 (84222) | GRCh38 (4)                                                   |
| refseqMrnaId     |         87 |             |      15511 | NM_006218.2 (387) | NM_001126112.2 (342) | NM_024690.2 (152)                  |
| chr              |        100 |             |         24 | 1 (9284) | 2 (6222) | 3 (5308)                                                |
| startPosition    |        100 |             |      82909 | 178952085 (142) | 178936091 (65) | 178936082 (43)                             |
| endPosition      |        100 |             |      82889 | 178952085 (142) | 178936091 (65) | 178936082 (43)                             |
| referenceAllele  |        100 |             |       1171 | C (32375) | G (31801) | T (9050)                                              |
| variantAllele    |        100 |             |        180 | T (24777) | A (23647) | G (12997)                                             |
| tumorAltCount    |        100 |             |        374 | 5 (3782) | 6 (3740) | 7 (3511)                                                |
| tumorRefCount    |        100 |             |        951 | 30 (839) | 27 (821) | 29 (817)                                                |
| mutationStatus   |        100 |             |          1 | . (84226)                                                                     |
| validationStatus |        100 |             |          1 | . (84226)                                                                     |
| vaf              |        100 |             |        905 | 0.333 (824) | 0.25 (784) | 0.2 (706)                                          |

### cbio_profiled_samples (1,084행 × 4열)

| column    |   filled_% | gdc_codes   |   n_unique | examples                                                        |
|:----------|-----------:|:------------|-----------:|:----------------------------------------------------------------|
| patientId |        100 |             |       1084 | TCGA-3C-AAAU (1) | TCGA-3C-AALI (1) | TCGA-3C-AALJ (1)          |
| sampleId  |        100 |             |       1084 | TCGA-3C-AAAU-01 (1) | TCGA-3C-AALI-01 (1) | TCGA-3C-AALJ-01 (1) |
| cna       |        100 |             |          2 | True (1070) | False (14)                                        |
| sequenced |        100 |             |          2 | True (1066) | False (18)                                        |
