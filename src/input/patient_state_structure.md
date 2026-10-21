patient_state.json
├── schema_version            "0.1-draft6"
├── patient_ref               가명 ID (TCGA는 바코드)
├── created_at
├── index_day                 판정 기준일 (진단일 = 0, TCGA는 마지막 추적일) [draft6]
├── documents[]               {doc_id, doc_type, doc_date}
│                             doc_type: progress_note / pathology / molecular / medication
├── fields                    아래 ◆ 칸은 공통 추출 칸 (맨 아래 설명)
│   ├── diagnosis
│   │   ├── diagnosis_date    ◆ 날짜 (TCGA는 not_recorded)
│   │   ├── histology         ◆ IDC / ILC / mucinous / metaplastic / invasive_NOS / other
│   │   └── grade             ◆ 1 / 2 / 3
│   ├── stage
│   │   ├── ctnm, ptnm        ◆ {t, n, m, edition}  예: T2, N1a, M0, 7th. TX·NX·MX → not_assessed
│   │   ├── group             ◆ 0, I, IA … IIIC, IV, not_assessed (Stage X)
│   │   ├── positive_ln_count ◆ {positive, examined}  정수 또는 "[Not Available]"
│   │   ├── disease_extent    ◆ early / locally_advanced / metastatic (진단 시)
│   │   ├── metastatic_sites  ◆ 진단 시 전이 부위 [bone, liver, lung, brain, distant_ln, skin, "other: …"]
│   │   │                       또는 "[Not Applicable]"(M0) / "[Not Available]"
│   │   └── operable          ◆ yes / no / unknown
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
│   │   ├── menopausal_basis  ◆ age_amenorrhea / fsh / oophorectomy / unknown
│   │   └── ecog              ◆ 0 / 1 / 2 / 3 / 4
│   ├── treatment_history[]   투약 기록 하나 = 원소 하나 (시간순)
│   │   ├── drugs[]           일반명
│   │   ├── setting           neoadjuvant / adjuvant / metastatic / unknown
│   │   ├── start_date, end_date      (날짜, TCGA는 null)
│   │   ├── start_day, end_day        (진단일 = 0)
│   │   ├── duration_days
│   │   ├── cycles            {value, basis, interval_days, interval_basis} 또는 null
│   │   │                       basis: recorded / estimated
│   │   │                       interval_basis: recorded / derived / standard / null
│   │   ├── progression_day
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
│   ├── at_index              판정 기준일 시점 값 [2026-10-20 추가, 4명 검토 전]
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
│   │   └── mutations
│   │       └── ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2
│   │           ├── status    present / not_done / not_recorded
│   │           ├── raw       not_done일 때 '결과 대기' / '예정' [draft6]
│   │           ├── result    detected / not_detected (status가 present일 때)
│   │           ├── variants[]  {protein_change, variant_type, vaf, raw}
│   │           │               detected면 1개 이상, not_detected면 빈 목록
│   │           ├── specimen  primary / metastasis / cfDNA / unknown / null
│   │           └── source
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
├── source                    {doc_id, quote, char_start, char_end} (TCGA 정답은 null)
└── history[]                 밀려난 이전 값 {status, value, raw, observed_date, specimen, source, superseded_reason}
                              superseded_reason: recurrence / newer_result
