patient_state.json
├── schema_version            "0.1-draft6" (draft7 후보 칸은 4명 검토 뒤 "0.1-draft7"로 올린다)
├── patient_ref               가명 ID (가상 차트는 VC-0101 형식)
├── created_at
├── index_day                 판정 기준일 (진단일 = 0) [draft6]
├── documents[]               {doc_id, doc_type, doc_date}
│                             doc_type: progress_note / pathology / molecular / medication / radiology [draft7 후보]
├── fields                    아래 ◆ 칸은 공통 추출 칸 (맨 아래 설명). [draft7 후보] 칸은 모두 선택 칸이다
│   ├── diagnosis
│   │   ├── diagnosis_date    ◆ 날짜
│   │   ├── histology         ◆ IDC / ILC / mucinous / metaplastic / invasive_NOS / other
│   │   └── grade             ◆ 1 / 2 / 3
│   ├── stage
│   │   ├── ctnm, ptnm        ◆ {t, n, m, edition}  예: T2, N1a, M0, 7th. TX·NX·MX → not_assessed
│   │   │                       ptnm은 수술을 먼저 한 환자만 (선행요법 뒤 병기는 yptnm)
│   │   ├── yptnm             ◆ 선행요법 뒤 수술 병기 [draft7 후보]
│   │   │                       {t, n, m, edition, residual_size_mm, positive_ln, examined_ln}
│   │   │                       t·n은 y를 뺀 범주, m은 선행 전 값. not_done = 아직 수술 전 (raw '예정')
│   │   ├── group             ◆ 0, I, IA … IIIC, IV, not_assessed (Stage X)
│   │   ├── positive_ln_count ◆ {positive, examined}  정수 또는 "[Not Available]"
│   │   ├── disease_extent    ◆ early / locally_advanced / metastatic (진단 시)
│   │   ├── metastatic_sites  ◆ 진단 시 전이 부위 [bone, liver, lung, brain, distant_ln, skin, "other: …"]
│   │   │                       또는 "[Not Applicable]"(M0) / "[Not Available]"
│   │   ├── operable          ◆ yes / no / unknown
│   │   ├── clinical_size_mm  ◆ 치료 전 임상 종양 최대 직경 (mm) [draft7 후보]
│   │   └── pathologic_size_mm ◆ 수술 검체 침윤암 최대 직경 (mm, 관내암 제외) [draft7 후보]
│   ├── receptors
│   │   ├── er_percent        ◆ {percent, range, allred, result}
│   │   │                       result: positive / low_positive / negative / indeterminate
│   │   ├── pr_percent        ◆ {percent, range, allred, result}
│   │   │                       result: positive / negative / indeterminate (저발현 범주 없음)
│   │   │                       range = [최소, 최대] (예: 1-9% → [1, 9], <1% → [0, 0])
│   │   │                       allred = {total, ps, is}
│   │   ├── her2_ihc          ◆ {score, faint, result}
│   │   │                       score: "0" / "1+" / "2+" / "3+", faint: true / false
│   │   │                       result: positive / negative / equivocal / indeterminate / unknown
│   │   ├── her2_ish          ◆ {result, method}
│   │   │                       result: amplified / not_amplified / equivocal
│   │   │                       method: FISH / SISH / DISH / unknown
│   │   └── pdl1              ◆ {assay, score_type, score}
│   │                           assay: 22C3 / SP142 / SP263 / other / unknown
│   │                           score_type: CPS / IC / TPS / unknown
│   ├── proliferation
│   │   └── ki67_percent      ◆ {percent, range, result}  result: low / intermediate / high
│   ├── patient
│   │   ├── gender            ◆ FEMALE / MALE
│   │   ├── age               ◆ 진단 시 나이 (정수)
│   │   ├── menopausal_status ◆ premenopausal / perimenopausal / postmenopausal / indeterminate
│   │   ├── menopausal_basis  ◆ age_amenorrhea / fsh / oophorectomy / ovarian_radiation / hysterectomy / unknown
│   │   │                       (ovarian_radiation·hysterectomy는 [draft7 후보])
│   │   ├── ecog              ◆ 0 / 1 / 2 / 3 / 4
│   │   ├── height_cm, weight_kg   ◆ 키, 몸무게 (체표면적 → mg/m² 환산) [draft7 후보]
│   │   ├── cardiac_history   ◆ yes / no (병명은 raw) [draft7 후보]
│   │   ├── lvef_percent      ◆ 좌심실 박출률 0~100 [draft7 후보]
│   │   ├── mediastinal_radiation  ◆ yes / no [draft7 후보]
│   │   ├── visceral_crisis   ◆ yes / no (의사가 적은 판단만) [draft7 후보]
│   │   └── comorbidities     ◆ 동반질환 원문 표기 목록 [draft7 후보]
│   ├── imaging_findings[]    영상 검사 소견 [draft7 후보]
│   │   ├── modality          CT / MRI / PET / bone_scan / X-ray / ultrasound / other
│   │   ├── day, date         검사일 (진단일 = 0), 날짜
│   │   ├── sites[]           전이로 판독한 부위 (metastatic_sites와 같은 표기, 전이 없음이면 빈 목록)
│   │   ├── certainty         confirmed / suspected
│   │   └── source
│   ├── treatment_history[]   투약 기록 하나 = 원소 하나 (시간순)
│   │   ├── drugs[]           일반명
│   │   ├── setting           neoadjuvant / adjuvant / metastatic / unknown
│   │   ├── start_date, end_date      (날짜)
│   │   ├── start_day, end_day        (진단일 = 0)
│   │   ├── ongoing           기준일에 투약 중: true / false / null(모름) [draft7 후보]
│   │   ├── duration_days
│   │   ├── cycles            {value, basis, interval_days, interval_basis} 또는 null
│   │   │                       basis: recorded / estimated
│   │   │                       interval_basis: recorded / derived / standard / null
│   │   ├── progression_day
│   │   ├── doses[]           약별 용량, drugs의 약마다 하나 [draft7 후보]
│   │   │   ├── drug          일반명 (drugs 안의 약)
│   │   │   ├── per_admin     1회 용량 {value, unit} 또는 "No value"
│   │   │   ├── total         총 투여량 {value, unit} 또는 "No value"
│   │   │   ├── basis         recorded / estimated (1회 × 주기)
│   │   │   └── source
│   │   ├── stop_reason       progression / toxicity / completed / planned_switch / maintenance / other / null
│   │   ├── best_response     CR / PR / SD / PD / unknown / null
│   │   ├── line, endocrine_line, chemo_line   전이 후 차수 (전이 전 null) [draft6]
│   │   └── source
│   ├── deemed_lines[]        차수 간주 규칙 4개 [draft6]
│   │   ├── rule_id           DEEM-ANTHRA-TAXANE / DEEM-SG-1Y / DEEM-HER2ADC-6M / DEEM-ENDO-ADJ-1Y
│   │   ├── category          chemo / endocrine
│   │   ├── status            met / not_met / unknown / not_applicable
│   │   ├── basis             판정 근거 문장
│   │   ├── regimen_refs[]    근거 treatment_history 순번 (0부터)
│   │   ├── gap_days          근거 투약 종료일 ~ 전이 기준일 (없으면 null)
│   │   └── notice_page       공고책자 쪽
│   ├── at_index              판정 기준일 시점 값 [draft7 후보, 2026-10-20]
│   │   ├── age               기준일 나이 = 진단 시 나이 + index_day ÷ 365.25의 몫 (없으면 null)
│   │   └── recent_therapy_28d   최근 4주 이내 항암제·호르몬제 투여
│   │       ├── status        yes / no / unknown
│   │       ├── basis         판정 근거 문장
│   │       ├── regimen_refs[]
│   │       └── gap_days
│   ├── anthracycline_drug_dose
│   │   ├── administered      positive / negative / No value
│   │   └── drugs[]
│   │       ├── drug          doxorubicin / epirubicin / liposomal doxorubicin
│   │       ├── timeline_index, combined_with[]
│   │       ├── dose_per_admin   {value, unit} 또는 "No value"
│   │       ├── cycles           cycles 형식 또는 "No value"
│   │       ├── total_dose       {value, unit} 또는 "No value"
│   │       ├── raw
│   │       └── source
│   ├── neoadjuvant_response
│   │   ├── pcr               ◆ yes / no
│   │   └── rcb               ◆ RCB-0 / RCB-I / RCB-II / RCB-III
│   ├── recurrence
│   │   ├── recurrence_date, adjuvant_endocrine_end_date   ◆ 날짜
│   │   ├── status            ◆ none / distant / locoregional / site_unknown / unknown
│   │   ├── metastatic_sites  ◆ 재발 전이 부위 (stage.metastatic_sites와 같은 형식)
│   │   ├── metastasis_day    ◆ 전이 기준일 (진단일 = 0, 진단 시 IV기 = 0)
│   │   ├── recurrence_day    ◆ 첫 재발일 (국소·원격, 진단일 = 0) [draft6]
│   │   ├── surgery           ◆ yes / no / unknown
│   │   ├── surgery_intent    ◆ curative / palliative / unknown
│   │   └── later_distant     ◆ yes / no / unknown
│   ├── molecular
│   │   ├── mutations         종양 조직·cfDNA 결과
│   │   │   └── ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2
│   │   │       ├── status    present / not_done / not_recorded
│   │   │       ├── raw       not_done일 때 '결과 대기' / '예정' [draft6]
│   │   │       ├── result    detected / not_detected (status가 present일 때)
│   │   │       ├── variants[]  {protein_change, variant_type, vaf, raw}
│   │   │       │               detected면 1개 이상, not_detected면 빈 목록
│   │   │       ├── specimen  primary / metastasis / cfDNA / unknown / null
│   │   │       └── source
│   │   └── germline          생식세포 검사 (혈액·타액) 결과 [draft7 후보]
│   │       └── BRCA1, BRCA2, PALB2   mutations와 같은 형식
│   │                           칸이 없으면 B는 mutations의 BRCA를 gBRCA로 본다
│   └── genomic_reports[]     {doc_id, report_date, specimen, raw_text}
└── conflicts[]               {field, candidates[], note}
                              candidates[] = 공통 추출 칸과 같은 형식

◆ 공통 추출 칸 (extracted)
├── status                    present(값 있음) / not_done(미시행) / not_recorded(기록 없음)
├── value                     표준값 (status가 present일 때만, 형식은 칸마다 위와 같음)
├── raw                       정규화 전 원문 표기. not_done이고 검사 중이면 '결과 대기', 예약만 됐으면 '예정' [draft6]
├── observed_date             날짜
├── specimen                  primary / metastasis / cfDNA / unknown / null
├── confidence                0~1 또는 null
├── source                    {doc_id, quote, char_start, char_end}
└── history[]                 밀려난 이전 값 {status, value, raw, observed_date, specimen, source, superseded_reason}
                              superseded_reason: recurrence / newer_result

2026-10-27 TCGA 정답 세트 폐기, 평가는 가상 차트로.
