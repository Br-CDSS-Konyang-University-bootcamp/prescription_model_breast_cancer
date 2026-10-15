patient_state.json
├── schema_version            "0.1-draft5"
├── patient_ref               가명 ID (TCGA는 바코드)
├── created_at
├── documents[]               {doc_id, doc_type, doc_date}
├── fields
│   ├── diagnosis
│   │   ├── diagnosis_date
│   │   ├── histology         IDC / ILC / mucinous / metaplastic / invasive_NOS / other
│   │   └── grade             1 / 2 / 3
│   ├── stage
│   │   ├── ctnm, ptnm        {t, n, m, edition}
│   │   ├── group             IIA, IIIC, IV …
│   │   ├── positive_ln_count {positive, examined}
│   │   ├── disease_extent    early / locally_advanced / metastatic (진단 시)
│   │   ├── metastatic_sites  진단 시 전이 부위 (M0이면 [Not Applicable])
│   │   └── operable          yes / no / unknown
│   ├── receptors
│   │   ├── er_percent        {percent, range, allred, result}
│   │   ├── pr_percent        {percent, range, allred, result}
│   │   ├── her2_ihc          {score, faint, result}
│   │   ├── her2_ish          {result, method}
│   │   └── pdl1              {assay, score_type, score}
│   ├── proliferation
│   │   └── ki67_percent      {percent, range, result}
│   ├── patient
│   │   ├── gender, age
│   │   ├── menopausal_status, menopausal_basis
│   │   └── ecog
│   ├── treatment_history[]   투약 기록 하나 = 원소 하나
│   │   ├── drugs[], setting
│   │   ├── start_date, end_date      (날짜, TCGA는 null)
│   │   ├── start_day, end_day        (진단일 = 0)
│   │   ├── duration_days
│   │   ├── cycles            {value, basis, interval_days, interval_basis}
│   │   ├── progression_day
│   │   ├── stop_reason, best_response
│   │   └── source
│   ├── anthracycline_drug_dose
│   │   ├── administered      positive / negative / No value
│   │   └── drugs[]
│   │       ├── drug, timeline_index, combined_with[]
│   │       ├── dose_per_admin   {value, unit} 또는 "No value"
│   │       ├── cycles           cycles 형식 또는 "No value"
│   │       ├── total_dose       {value, unit} 또는 "No value"
│   │       └── raw
│   ├── neoadjuvant_response
│   │   ├── pcr               yes / no
│   │   └── rcb               RCB-0 ~ RCB-III
│   ├── recurrence
│   │   ├── recurrence_date, adjuvant_endocrine_end_date
│   │   ├── status            none / distant / locoregional / site_unknown / unknown
│   │   ├── metastatic_sites  재발 전이 부위
│   │   ├── metastasis_day    전이 기준일 (진단일 = 0)
│   │   ├── surgery           yes / no / unknown
│   │   ├── surgery_intent    curative / palliative / unknown
│   │   └── later_distant     yes / no / unknown
│   ├── molecular
│   │   └── mutations
│   │       └── ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2
│   │           ├── status    present / not_done
│   │           ├── result    detected / not_detected
│   │           ├── variants[]  {protein_change, variant_type, vaf, raw}
│   │           └── specimen
│   └── genomic_reports[]     {doc_id, report_date, specimen, raw_text}
└── conflicts[]               {field, candidates[], note}

