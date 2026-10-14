"""합친 TCGA-BRCA 파일에서 v0.1에 필요 없는 열과 남성 환자 행을 뺀 정리본을 만든다.

입력: data/tcga_brca/merged/tcga_brca_merged.csv (tcga_brca_merge.py 결과, 수정하지 않음)
      data/tcga_brca/gdc_clinical/ 환자·추적 관찰 파일 (재발 여부 new_tumor_event_dx_indicator만 읽음)
출력 (data/tcga_brca/merged/):
- tcga_brca_merging_cropped.csv           정리본 (Excel용 UTF-8 BOM)
- tcga_brca_merging_cropped_columns.txt   남은 열별 의미
- tcga_brca_merging_cropped_changes.txt   변경 내역: 행 삭제, 바꾼 값, 삭제한 열(한 줄 사유), 용어 통일

실행: conda team_project 환경에서 tcga_brca_merge.py 다음에
    python data/script/tcga_brca_crop.py
"""
from datetime import date
from pathlib import Path

import pandas as pd

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
MERGED_DIR = DATA_ROOT / "tcga_brca" / "merged"
SRC = MERGED_DIR / "tcga_brca_merged.csv"
OUT_CSV = MERGED_DIR / "tcga_brca_merging_cropped.csv"
OUT_COLS = MERGED_DIR / "tcga_brca_merging_cropped_columns.txt"
OUT_CHANGES = MERGED_DIR / "tcga_brca_merging_cropped_changes.txt"
CORRECTIONS = MERGED_DIR / "drug_corrections.csv"
GDC_DIR = DATA_ROOT / "tcga_brca" / "gdc_clinical"
RECURRENCE_FILES = ["patient", "follow_up_v1.5", "follow_up_v2.1", "follow_up_v4.0"]

# ---------------------------------------------------------------------------
# 삭제할 열: {묶음: {열: 한 줄 사유}}
# ---------------------------------------------------------------------------
DROP = {
    "모든 환자가 빈칸": {
        "gdc_nte_er_positivity_other_scale": "재발 시 ER 기타 척도, 입력 없음",
        "gdc_nte_er_positivity_define_method": "재발 시 ER 판정 방법, 입력 없음",
        "gdc_nte_pr_positivity_other_scale": "재발 시 PR 기타 척도, 입력 없음",
        "gdc_nte_pr_positivity_define_method": "재발 시 PR 판정 방법, 입력 없음",
        "gdc_nte_her2_positivity_other_scale": "재발 시 HER2 기타 척도, 입력 없음",
        "gdc_nte_her2_positivity_method": "재발 시 HER2 판정 방법, 입력 없음",
        "gdc_nte_her2_signal_number": "재발 시 HER2 신호 수, 입력 없음",
        "gdc_nte_cent_17_signal_number": "재발 시 CEP17 신호 수, 입력 없음",
        "gdc_her2_cent17_counted_cells_count": "재발 시 FISH 계수 세포 수, 입력 없음",
        "gdc_nte_cent17_her2_other_scale": "재발 시 FISH 기타 척도, 입력 없음",
        "gdc_nte_her2_fish_define_method": "재발 시 FISH 판정 방법, 입력 없음",
        "gdc_clinical_T": "임상 T 병기, 입력 없음",
        "gdc_clinical_N": "임상 N 병기, 입력 없음",
        "gdc_clinical_M": "임상 M 병기, 입력 없음",
        "gdc_clinical_stage": "임상 병기, 입력 없음",
        "gdc_days_to_patient_progression_free": "무진행 일수, 입력 없음",
        "gdc_days_to_tumor_progression": "진행까지 일수, 입력 없음",
        "gdc_extranodal_involvement": "림프절 외 침범, 입력 없음",
        "gdc_site_of_primary_tumor_other": "원발 부위 기타, 입력 없음",
        "gdc_stage_other": "기타 병기, 입력 없음",
    },
    "모든 환자가 같은 값": {
        "gdc_tumor_tissue_site": "모두 Breast",
        "cbio_sample_TUMOR_TISSUE_SITE": "모두 Breast",
        "gdc_days_to_initial_pathologic_diagnosis": "모두 0 (진단일이 기준일)",
        "cbio_DAYS_TO_INITIAL_PATHOLOGIC_DIAGNOSIS": "모두 0 (진단일이 기준일)",
        "gdc_informed_consent_verified": "모두 YES",
        "cbio_INFORMED_CONSENT_VERIFIED": "모두 Yes",
        "cbio_CANCER_TYPE_ACRONYM": "모두 BRCA",
        "cbio_sample_CANCER_TYPE": "모두 Breast Cancer",
        "cbio_sample_SAMPLE_TYPE": "모두 Primary",
        "cbio_sample_SOMATIC_STATUS": "모두 Matched",
        "cbio_SAMPLE_COUNT": "모두 1",
        "gdc_disease_code": "0.5%만 입력, 값 FPPP 하나",
        "gdc_project_code": "0.5%만 입력, 값 TCGA 하나",
    },
    "다른 열과 내용이 같음 (GDC 쪽을 남김)": {
        "cbio_AGE": "gdc_age_at_diagnosis와 같음",
        "cbio_DAYS_TO_BIRTH": "gdc_birth_days_to와 같음",
        "cbio_SEX": "gdc_gender와 같음",
        "cbio_RACE": "gdc_race와 같음",
        "cbio_ETHNICITY": "gdc_ethnicity와 같음",
        "cbio_AJCC_PATHOLOGIC_TUMOR_STAGE": "gdc_ajcc_pathologic_tumor_stage와 같음",
        "cbio_AJCC_STAGING_EDITION": "gdc_ajcc_staging_edition과 같음",
        "cbio_PATH_T_STAGE": "gdc_ajcc_tumor_pathologic_pt와 같음",
        "cbio_PATH_N_STAGE": "gdc_ajcc_nodes_pathologic_pn과 같음",
        "cbio_PATH_M_STAGE": "gdc_ajcc_metastasis_pathologic_pm과 같음",
        "cbio_ICD_10": "gdc_icd_10과 같음",
        "cbio_ICD_O_3_HISTOLOGY": "gdc_icd_o_3_histology와 같음",
        "cbio_ICD_O_3_SITE": "gdc_icd_o_3_site와 같음",
        "cbio_sample_TUMOR_TYPE": "gdc_histological_type과 같음",
        "cbio_HISTORY_NEOADJUVANT_TRTYN": "gdc_history_neoadjuvant_treatment와 같음",
        "cbio_PRIOR_DX": "gdc_history_other_malignancy와 같음",
        "cbio_PERSON_NEOPLASM_CANCER_STATUS": "gdc_tumor_status와 같음",
        "cbio_PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT": "gdc_lymph_nodes_examined와 같음",
        "cbio_FORM_COMPLETION_DATE": "gdc_form_completion_date와 같음",
        "cbio_OTHER_PATIENT_ID": "환자 UUID, patient_id로 충분",
        "gdc_patient_id": "바코드 끝 4자리, patient_id로 충분",
        "cbio_sample_MUTATION_COUNT": "mut_n_total과 같음 (전원 일치 확인)",
        "cbio_sample_TISSUE_SOURCE_SITE_CODE": "gdc_tissue_source_site와 같음",
        "cbio_sample_TISSUE_PROSPECTIVE_COLLECTION_INDICATOR": "gdc_prospective_collection과 같음",
        "cbio_sample_TISSUE_RETROSPECTIVE_COLLECTION_INDICATOR": "gdc_retrospective_collection과 같음",
        "has_mutation_data": "mut_sequenced와 같음",
    },
    "생존 정보 중복 (fu_ 요약과 cBioPortal 생존 지표를 남김)": {
        "gdc_vital_status": "등록 시점 생존 여부, fu_last_vital_status가 더 최신",
        "gdc_last_contact_days_to": "등록 시점 마지막 연락일, fu_last_days가 더 최신",
        "gdc_death_days_to": "등록 시점 사망일, fu_death_days와 겹침",
        "gdc_tumor_status": "등록 시점 종양 상태, fu_last_tumor_status가 더 최신",
        "cbio_DAYS_LAST_FOLLOWUP": "마지막 추적일, fu_last_days와 겹침",
    },
    "행정·수집 정보": {
        "gdc_bcr_patient_uuid": "환자 UUID",
        "gdc_form_completion_date": "양식 작성일",
        "gdc_prospective_collection": "전향적 수집 여부",
        "gdc_retrospective_collection": "후향적 수집 여부",
        "cbio_IN_PANCANPATHWAYS_FREEZE": "PanCancer 분석 포함 여부",
        "cbio_sample_TISSUE_SOURCE_SITE": "수집 기관 이름 (기관 코드 gdc_tissue_source_site는 남김)",
    },
    "설계서 범위 밖 (수술·방사선)": {
        "gdc_method_initial_path_dx": "첫 병리 진단 방법 (생검 종류)",
        "gdc_method_initial_path_dx_other": "첫 병리 진단 방법 기타",
        "gdc_surgical_procedure_first": "첫 수술 종류",
        "gdc_first_surgical_procedure_other": "첫 수술 종류 기타",
        "gdc_surgery_for_positive_margins": "절제면 양성 시 추가 수술",
        "gdc_surgery_for_positive_margins_other": "절제면 양성 시 추가 수술 기타",
        "gdc_margin_status": "절제면 상태",
        "gdc_margin_status_reexcision": "재절제 후 절제면 상태",
        "gdc_axillary_staging_method": "액와 림프절 병기 결정 방법",
        "gdc_axillary_staging_method_other": "액와 림프절 병기 결정 방법 기타",
        "gdc_micromet_detection_by_ihc": "미세전이 IHC 검출 여부",
        "gdc_lymph_nodes_examined": "림프절 평가 시행 여부 (개수 열은 남김)",
        "gdc_anatomic_neoplasm_subdivision": "종양 위치 (좌우, 사분면)",
        "rad_n_records": "방사선 치료 기록 수",
        "rad_types": "방사선 치료 종류",
        "rad_sites": "방사선 치료 부위",
        "rad_first_start_days": "첫 방사선 치료 시작일",
    },
    "수용체 검사 방법 세부 (자유 기재, 판정 결과 열에 정리돼 있음)": {
        "gdc_er_positivity_scale_used": "ER 강도 척도 종류",
        "gdc_er_positivity_scale_other": "ER 기타 척도 (Allred, H-score 등 자유 기재)",
        "gdc_er_positivity_method": "ER 판정 방법 자유 기재",
        "gdc_pr_positivity_scale_used": "PR 강도 척도 종류",
        "gdc_pr_positivity_scale_other": "PR 기타 척도 자유 기재",
        "gdc_pr_positivity_define_method": "PR 판정 방법 자유 기재",
        "gdc_her2_positivity_scale_other": "HER2 기타 척도 자유 기재",
        "gdc_her2_positivity_method_text": "HER2 판정 방법 자유 기재",
        "gdc_her2_and_cent17_scale_other": "FISH 기타 척도 자유 기재",
        "gdc_her2_fish_method": "FISH 키트·기준 자유 기재",
        "gdc_her2_and_cent17_cells_count": "FISH 계수 세포 수",
    },
    "사용자 요청으로 삭제": {
        "gdc_birth_days_to": "진단일 기준 출생일 일수, 진단 시 나이(gdc_age_at_diagnosis)로 충분",
    },
    "처방에 쓰지 않는 연구용 점수": {
        "cbio_BUFFA_HYPOXIA_SCORE": "저산소 유전자 점수 (Buffa)",
        "cbio_RAGNUM_HYPOXIA_SCORE": "저산소 유전자 점수 (Ragnum)",
        "cbio_WINTER_HYPOXIA_SCORE": "저산소 유전자 점수 (Winter)",
        "cbio_GENETIC_ANCESTRY_LABEL": "유전적 조상 추정",
        "cbio_sample_ANEUPLOIDY_SCORE": "이수성 점수",
        "cbio_sample_FRACTION_GENOME_ALTERED": "복제수 변화 유전체 비율",
        "cbio_sample_TBL_SCORE": "총 결실 부담 점수",
    },
}

# ---------------------------------------------------------------------------
# 남는 열의 의미: {묶음: {열: 설명}}
# ---------------------------------------------------------------------------
DESCRIPTIONS = {
    "식별·출처 표시": {
        "patient_id": "TCGA 환자 바코드 (예: TCGA-A7-A0DC). 모든 테이블의 연결 키",
        "has_gdc_clinical": "GDC 환자 임상 기록이 있으면 True",
        "has_cbio_clinical": "cBioPortal 임상 기록이 있으면 True",
        "has_drug": "GDC 투약 기록이 1건 이상 있으면 True",
        "gdc_tissue_source_site": "검체 수집 기관 코드 (2글자). v0.2 기관 단위 분할에 사용",
        "cbio_sample_sampleId": "종양 샘플 ID (환자 ID + -01). 01은 원발 종양",
    },
    "환자 정보": {
        "gdc_age_at_diagnosis": "진단 시 나이 (세)",
        "gdc_gender": "성별. 정리본에는 FEMALE만 남음",
        "gdc_menopause_status": "폐경 상태. Pre(폐경 전) / Peri(폐경 이행기) / Post(폐경 후) / Indeterminate(판단 불가)",
        "gdc_race": "인종",
        "gdc_ethnicity": "히스패닉 여부",
        "gdc_initial_pathologic_dx_year": "첫 병리 진단 연도",
        "gdc_history_other_malignancy": "다른 암 병력 여부 (Yes/No)",
    },
    "진단·조직형": {
        "gdc_histological_type": "주 조직형 (Infiltrating Ductal Carcinoma = 침윤성 관암, Lobular = 소엽암 등)",
        "gdc_histologic_diagnosis_other": "주 조직형이 Other 또는 Mixed일 때만 적는 구체적 조직형. 그 외는 [Not Applicable]",
        "gdc_icd_10": "ICD-10 진단 코드 (C50.x = 유방암, 소수점 아래는 부위)",
        "gdc_icd_o_3_histology": "ICD-O-3 조직형 코드 (8500/3 = 침윤성 관암, 8520/3 = 소엽암)",
        "gdc_icd_o_3_site": "ICD-O-3 부위 코드",
        "cbio_sample_CANCER_TYPE_DETAILED": "cBioPortal 세부 암종 이름",
        "cbio_sample_ONCOTREE_CODE": "OncoTree 암종 코드 (IDC, ILC 등). OncoKB 조회에 사용",
        "cbio_SUBTYPE": "PAM50 유전자 발현 아형 (LumA, LumB, Her2, Basal, Normal). IHC 아형과 다를 수 있음",
    },
    "병기 (AJCC 병리 병기)": {
        "gdc_ajcc_staging_edition": "AJCC 병기 판 (3rd~7th). 판마다 기준이 다름",
        "gdc_ajcc_tumor_pathologic_pt": "병리 T 병기 (원발 종양 크기·침범)",
        "gdc_ajcc_nodes_pathologic_pn": "병리 N 병기 (림프절 전이)",
        "gdc_ajcc_metastasis_pathologic_pm": "병리 M 병기 (원격 전이). MX = 평가 안 됨",
        "gdc_ajcc_pathologic_tumor_stage": "종합 병기 (Stage I~IV). M1인데 [Discrepancy]였던 2명은 Stage IV로 바꿈",
        "stage_disease_extent": "진단 시 병기 기준 범주. early(조기, I~II) / locally_advanced(국소 진행성, III) / metastatic(전이성, IV). "
                                "III 기준은 심평원 급여 조건. 병기가 없으면 AJCC 규칙(M0·MX이면서 T4 또는 N2~3 → III)으로 정함",
        "gdc_lymph_nodes_examined_count": "검사한 림프절 개수",
        "gdc_lymph_nodes_examined_he_count": "H&E 염색으로 확인한 양성 림프절 개수 (이름과 달리 양성 개수). 심평원 abemaciclib 기준(4개)에 사용",
        "gdc_lymph_nodes_examined_ihc_count": "면역염색으로 확인한 양성 림프절 개수",
        "gdc_metastatic_tumor_indicator": "진단 시 원격 전이 여부",
        "gdc_metastasis_site": "원격 전이 부위 (Bone, Liver 등, 여러 곳이면 | 로 구분)",
        "gdc_metastasis_site_other": "원격 전이 부위 기타 자유 기재",
    },
    "수용체 (진단 시 원발 종양)": {
        "gdc_er_status_by_ihc": "ER 면역염색 판정 (Positive/Low Positive/Negative/Indeterminate). 비율이 <10%인데 Positive였던 값은 Low Positive(저발현)로 바꿈",
        "gdc_er_status_ihc_Percent_Positive": "ER 양성 세포 비율 구간 (<1%, 1-9%, 10-19% … 90-99%). 원본 <10%는 판정에 따라 1-9%(Low Positive) 또는 <1%(Negative)로 나눔",
        "gdc_er_ihc_score": "ER 염색 강도 점수 (1+~4+)",
        "gdc_pr_status_by_ihc": "PR 면역염색 판정 (Positive/Negative/Indeterminate). PR에는 저발현 범주가 없다 (ASCO/CAP Low Positive는 ER만 해당)",
        "gdc_pr_status_ihc_percent_positive": "PR 양성 세포 비율 구간 (<1%, 1-9%, 10-19% … 90-99%). 원본 <10%는 판정에 따라 1-9%(Positive) 또는 <1%(Negative)로 나눔",
        "gdc_pr_positivity_ihc_intensity_score": "PR 염색 강도 점수",
        "gdc_her2_status_by_ihc": "HER2 면역염색 판정 (Positive/Equivocal/Negative). Equivocal = IHC 2+",
        "gdc_her2_ihc_score": "HER2 IHC 점수 (0, 1+, 2+, 3+). HER2 저발현(1+, 2+/ISH 음성) 판정에 사용",
        "gdc_her2_ihc_percent_positive": "HER2 막 염색 세포 비율 구간",
        "gdc_her2_fish_status": "HER2 FISH 판정 (Positive = 증폭)",
        "gdc_her2_copy_number": "세포당 평균 HER2 신호 수 (FISH)",
        "gdc_cent17_copy_number": "세포당 평균 17번 염색체 중심체(CEP17) 신호 수",
        "gdc_her2_cent17_ratio": "HER2/CEP17 비율. 2.0 이상이면 증폭",
    },
    "재발 시 정보": {
        "gdc_new_tumor_event_dx_indicator": "재발 또는 새 종양 발생 여부 (등록 양식 기준)",
        "gdc_nte_er_status": "재발 병소 ER 판정. 비율이 <10%인데 Positive였던 값은 Low Positive로 바꿈",
        "gdc_nte_er_status_ihc__positive": "재발 병소 ER 양성 세포 비율 구간. 원본 <10%는 1-9% 또는 <1%로 나눔",
        "gdc_nte_er_ihc_intensity_score": "재발 병소 ER 염색 강도",
        "gdc_nte_pr_status_by_ihc": "재발 병소 PR 판정 (저발현 범주 없음)",
        "gdc_nte_pr_status_ihc__positive": "재발 병소 PR 양성 세포 비율 구간. 원본 <10%는 1-9% 또는 <1%로 나눔",
        "gdc_nte_pr_ihc_intensity_score": "재발 병소 PR 염색 강도",
        "gdc_nte_her2_status": "재발 병소 HER2 판정",
        "gdc_nte_her2_status_ihc__positive": "재발 병소 HER2 양성 세포 비율 구간",
        "gdc_nte_her2_positivity_ihc_score": "재발 병소 HER2 IHC 점수",
        "gdc_nte_her2_fish_status": "재발 병소 HER2 FISH 판정",
        "gdc_nte_cent_17_her2_ratio": "재발 병소 HER2/CEP17 비율",
        "cbio_NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT": "첫 치료 후 재발·새 종양 여부 (cBioPortal 정리값)",
        "nte_n_records": "재발·새 종양 기록 수",
        "nte_types": "사건 종류 (Distant Metastasis = 원격 전이, Locoregional Recurrence = 국소 재발, New Primary Tumor = 새 원발암)",
        "nte_sites": "재발 부위",
        "nte_sites_other": "재발 부위 기타 자유 기재",
        "nte_first_dx_days": "첫 재발 진단일 (진단 후 일수)",
        "nte_event_types": "재발·새 종양 사건별 종류. nte_dx_days와 같은 순서 (진단일 순). 재발 기록 파일 3개(nte, follow_up_v4.0_nte, follow_up_v2.1)에서 모음",
        "nte_dx_days": "재발·새 종양 사건별 진단일 (new_tumor_event_dx_days_to, 진단 후 일수). nte_event_types와 같은 순서. metastasis_dx_days는 이 중 Distant Metastasis의 가장 이른 값",
        "nte_surgery": "재발 후 수술 여부 (new_tumor_event_surgery: YES / NO). 재발 기록 파일과 추적 관찰 v1.5·v2.1에서 모음. 값이 여럿이면 '; '로 이음",
        "nte_surgery_days": "재발 후 수술일 (진단 후 일수, 가장 이른 값). 기록이 적음",
        "recurrence_status": "재발 상태. none(재발 없음) / distant(원격 전이 재발, 국소 재발이 함께 있어도 distant) / "
                             "locoregional(국소 재발만) / site_unknown(재발했으나 부위 기록 없음) / unknown(재발 여부 기록 없음) / "
                             "new_primary(새 원발암만, 진단 시 전이성인 경우만 남음). 환자·추적 관찰 파일의 재발 여부와 nte_types로 정함",
        "current_disease_extent": "현재 치료 상황의 병기 범주 (biomarker_record.setting.disease 정답). 진단 시 전이성 또는 "
                                  "원격 전이 재발 → metastatic, 그 밖은 진단 시 범주 그대로",
        "metastasis_dx_days": "전이 기준일 (진단 후 일수). 진단 시 전이성 = 0, 원격 전이 재발 = 가장 이른 원격 전이 진단일. "
                              "전이성이 아니면 빈칸. drug_timeline의 시작일과 비교해 전이 전·후 처방을 나누고 차수를 판단하는 재료",
        "locoregional_dx_days": "첫 국소 재발 진단일 (진단 후 일수). 국소 재발 기록이 없으면 빈칸. metastasis_dx_days와 비교해 "
                                "국소 재발 이후 원격 전이가 있었는지 판단 (국소 재발 후 수술후보조요법 인정, 공고 p.48)",
    },
    "치료 이력": {
        "gdc_history_neoadjuvant_treatment": "수술 전 선행요법 여부",
        "gdc_pharmaceutical_tx_adjuvant": "보조 약물치료 여부 (등록 양식 기준, 입력 적음)",
        "gdc_radiation_treatment_adjuvant": "보조 방사선치료 여부 (등록 양식 기준, 입력 적음)",
        "cbio_RADIATION_THERAPY": "방사선치료 여부 (cBioPortal 정리값)",
        "drug_n_records": "투약 기록 수",
        "drug_names": "투약한 약제 성분명 목록 (시작일 순). 상품명·오타는 성분명으로 통일",
        "drug_therapy_types": "치료 종류 목록 (Chemotherapy, Hormone Therapy, HER2-targeted Therapy 등). 약제 성분 기준으로 다시 분류",
        "drug_best_responses": "약물치료 최선 반응 (Complete Response, Stable Disease, Clinical Progressive Disease 등)",
        "drug_first_start_days": "첫 약물치료 시작일 (진단 후 일수)",
        "drug_timeline": "투약 타임라인. '성분명 [치료 종류] d시작~d종료 (최선 반응)', 종료일 모르면 ?",
        "drug_total_dose": "투약별 총 투여량. drug_timeline과 같은 순서로 ' | '로 이음. 값이 없으면 -",
        "drug_total_dose_units": "투약별 총 투여량 단위 (mg, mg/m2 등). drug_timeline과 같은 순서",
        "drug_prescribed_dose": "투약별 1회 처방 용량. '60+600'처럼 병용 약 용량이 합쳐진 값이 있음. drug_timeline과 같은 순서",
        "drug_dose_units": "투약별 1회 용량 단위 (mg, mg/m2 등). drug_timeline과 같은 순서",
        "drug_cycles": "투약별 주기 수 (pharma_adjuvant_cycles_count). drug_timeline과 같은 순서",
        "drug_start_days": "투약별 시작일 (pharmaceutical_tx_started_days_to, 진단 후 일수). drug_timeline과 같은 순서. patient_state의 treatment_history[].start_day",
        "drug_end_days": "투약별 종료일 (pharmaceutical_tx_ended_days_to, 진단 후 일수). drug_timeline과 같은 순서. patient_state의 treatment_history[].end_day",
        "drug_names_raw": "원본 약제명 (정규화 전, 대조용)",
        "drug_therapy_types_raw": "원본 치료 종류 (정규화 전, 대조용)",
    },
    "추적 관찰·생존": {
        "fu_n_records": "추적 관찰 기록 수",
        "fu_last_days": "마지막 추적일 (진단 후 일수, 연락일과 사망일 중 늦은 값)",
        "fu_last_vital_status": "마지막 추적 시 생존 여부 (Alive/Dead)",
        "fu_last_tumor_status": "마지막 추적 시 종양 상태 (TUMOR FREE / WITH TUMOR)",
        "fu_death_days": "사망일 (진단 후 일수)",
        "cbio_OS_MONTHS": "전체 생존 기간 (개월)",
        "cbio_OS_STATUS": "전체 생존 사건 (0:LIVING, 1:DECEASED)",
        "cbio_DSS_MONTHS": "질병 특이 생존 기간 (개월)",
        "cbio_DSS_STATUS": "질병 특이 생존 사건 (1 = 암으로 사망)",
        "cbio_DFS_MONTHS": "무병 생존 기간 (개월)",
        "cbio_DFS_STATUS": "무병 생존 사건 (1 = 재발·진행)",
        "cbio_PFS_MONTHS": "무진행 생존 기간 (개월)",
        "cbio_PFS_STATUS": "무진행 생존 사건 (1 = 진행)",
    },
    "다른 암 병력": {
        "omf_n_records": "다른 암 기록 수",
        "omf_malignancy_types": "다른 암 시기 (Prior = 이전, Synchronous = 동시)",
        "omf_sites": "다른 암 부위",
    },
    "유전체 검사 여부·종양 비특이 바이오마커": {
        "mut_sequenced": "체세포 변이 검사(엑솜) 대상이면 True",
        "cna_profiled": "복제수 검사 대상이면 True",
        "mut_n_total": "체세포 변이 총개수. 검사 안 했으면 빈칸",
        "cbio_sample_TMB_NONSYNONYMOUS": "종양 변이 부담 (100만 염기당 비동의 변이 수). 10 이상이면 TMB-high",
        "cbio_sample_MSI_SCORE_MANTIS": "MSI 점수 (MANTIS). 0.4 이상이면 MSI-H로 봄",
        "cbio_sample_MSI_SENSOR_SCORE": "MSI 점수 (MSIsensor). 10 이상이면 MSI-H로 봄",
    },
    "바이오마커 유전자 체세포 변이 (단백질 변화 (변이 종류, VAF))": {
        f"mut_{g}": f"{g} 체세포 변이. 검사했는데 없으면 '변이 없음', 검사 안 했으면 빈칸"
        for g in ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
    },
    "바이오마커 유전자 복제수 (GISTIC: -2 깊은 결실, -1 얕은 결실, 0 정상, 1 증가, 2 증폭)": {
        f"cna_{g}": f"{g} 복제수" + (". 2(증폭)는 HER2 ISH 증폭과 대응" if g == "ERBB2" else
                                    ". -2(깊은 결실)는 기능 소실 근거" if g == "PTEN" else "")
        for g in ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
    },
}

# 양성 세포 비율 구간 <10%를 판정에 따라 둘로 나눈다 (사용자 결정, 2026-10-12).
#   <10% + Positive → 구간 1-9%. ER만 판정을 Low Positive로 바꾼다
#                     (ASCO/CAP 2020의 Low Positive는 ER에만 정의됨. PR은 Positive 유지)
#   <10% + Negative → 구간 <1%  (가정: 1% 기준 음성. 2010년 이전 진단은 10% 기준이었을 수 있음)
# 이력: 2026-10-07에는 <10% + Positive를 Negative로 바꿨다. 2026-10-12 오전에는 PR도 Low Positive로 바꿨다.
# (마커, 비율 열, 판정 열, Low Positive로 바꿀지)
RECODE = [
    ("ER", "gdc_er_status_ihc_Percent_Positive", "gdc_er_status_by_ihc", True),
    ("PR", "gdc_pr_status_ihc_percent_positive", "gdc_pr_status_by_ihc", False),
    ("재발 ER", "gdc_nte_er_status_ihc__positive", "gdc_nte_er_status", True),
    ("재발 PR", "gdc_nte_pr_status_ihc__positive", "gdc_nte_pr_status_by_ihc", False),
]


def recode_low_percent(df):
    changed = {}
    year = pd.to_numeric(df["gdc_initial_pathologic_dx_year"], errors="coerce")
    for marker, pct_col, status_col, relabel in RECODE:
        low = (df[pct_col] == "<10%") & (df[status_col] == "Positive")
        neg = (df[pct_col] == "<10%") & (df[status_col] == "Negative")
        changed[marker] = {
            "low": sorted(df.loc[low, "patient_id"]),
            "neg": sorted(df.loc[neg, "patient_id"]),
            "neg_before_2010": int((neg & (year < 2010)).sum()),
        }
        if relabel:
            df.loc[low, status_col] = "Low Positive"
        df.loc[low, pct_col] = "1-9%"
        df.loc[neg, pct_col] = "<1%"
    return changed


# 진단 시 병기 범주와 삭제할 행 (사용자 결정, 2026-10-13)
#   I~II → early, III → locally_advanced (심평원 급여 조건의 "3기"), IV → metastatic
#   먼저 A의 정답 세트 규칙으로 종합 병기가 [Discrepancy]·[Not Available]·빈칸인 환자를 삭제한다 (우선 적용)
#   M1인데 종합 병기가 Stage IV가 아닌 환자는 Stage IV로 바꾼다
#   Stage X는 AJCC 규칙으로 III만 정한다: M0·MX이면서 T4 또는 N2~N3 → III.
#     그 밖은 범주를 정할 수 없어 행을 삭제한다
#   GDC 임상 기록이 없는 환자(재발 상태 기록 없음)와 조직형이 NOS·기록 없음·빈칸인 환자도 삭제한다
#   진단 시 전이성이 아니면서 새 원발암만 있는 환자도 삭제한다
#   현재 범주(current_disease_extent): 진단 시 전이성 또는 원격 전이 재발 → metastatic,
#     그 밖(재발 없음, 국소 재발, 재발 부위 모름, 재발 여부 모름)은 진단 시 범주 그대로
EXTENT_BY_STAGE = [("Stage IV", "metastatic"), ("Stage III", "locally_advanced"),
                   ("Stage II", "early"), ("Stage I", "early")]
STAGE_EXCLUDED = {"[Discrepancy]", "[Not Available]", ""}
HISTOLOGY_UNKNOWN = {"Infiltrating Carcinoma NOS", "[Not Available]", ""}


def stage_extent(df):
    stage = df["gdc_ajcc_pathologic_tumor_stage"].fillna("")
    m1 = df["gdc_ajcc_metastasis_pathologic_pm"].fillna("") == "M1"
    to_iv = sorted(df.loc[m1 & (stage != "Stage IV"), "patient_id"])
    df.loc[m1 & (stage != "Stage IV"), "gdc_ajcc_pathologic_tumor_stage"] = "Stage IV"
    stage = df["gdc_ajcc_pathologic_tumor_stage"].fillna("")

    extent = pd.Series(pd.NA, index=df.index, dtype="object")
    for prefix, value in EXTENT_BY_STAGE:  # IV, III을 먼저 확인해야 II, I과 섞이지 않음
        extent[extent.isna() & stage.str.startswith(prefix)] = value
    t = df["gdc_ajcc_tumor_pathologic_pt"].fillna("")
    n = df["gdc_ajcc_nodes_pathologic_pn"].fillna("")
    by_tnm = extent.isna() & (t.str.startswith("T4") | n.str.match(r"N[23]"))
    extent[by_tnm] = "locally_advanced"
    df["stage_disease_extent"] = extent
    return to_iv, sorted(df.loc[by_tnm, "patient_id"])


def stage_excluded(df):
    """A의 정답 세트 규칙: 종합 병기가 [Discrepancy]·[Not Available]·빈칸인 환자."""
    stage = df["gdc_ajcc_pathologic_tumor_stage"].fillna("")
    return df.loc[stage.isin(STAGE_EXCLUDED), ["patient_id", "gdc_ajcc_pathologic_tumor_stage"]]


def recurrence_status(df):
    """환자·추적 관찰 파일의 재발 여부와 nte_types로 재발 상태를 정한다."""
    frames = []
    for name in RECURRENCE_FILES:
        f = pd.read_csv(GDC_DIR / f"nationwidechildrens.org_clinical_{name}_brca.txt", sep="	", skiprows=[1, 2], dtype=str)
        if "new_tumor_event_dx_indicator" in f:
            frames.append(f[["bcr_patient_barcode", "new_tumor_event_dx_indicator"]])
    ind = pd.concat(frames).groupby("bcr_patient_barcode")["new_tumor_event_dx_indicator"].agg(set)
    flags = df["patient_id"].map(ind)
    types = df["nte_types"].fillna("")

    def status(flag, t):
        if isinstance(flag, set) and "YES" in flag:
            if "Distant" in t:
                return "distant"
            if "Locoregional" in t:
                return "locoregional"
            return "new_primary" if "New Primary" in t else "site_unknown"
        return "none" if isinstance(flag, set) and "NO" in flag else "unknown"
    df["recurrence_status"] = [status(f, t) for f, t in zip(flags, types)]


NEW_COLS = ["stage_disease_extent", "recurrence_status", "current_disease_extent", "metastasis_dx_days",
            "locoregional_dx_days"]
# 정리 기준을 바꿀 때마다 한 줄씩 추가한다 (변경 내역 txt의 0번 항목)
HISTORY = [
    ("2026-10-07", "남성 환자와 불필요한 열 삭제, ER·PR <10% + Positive를 Negative로 바꿈"),
    ("2026-10-12", "ER·PR <10%를 판정에 따라 1-9% / <1%로 나눔. ER만 Low Positive (PR은 Positive 유지)"),
    ("2026-10-13", "진단 시 병기 범주(stage_disease_extent) 추가: I~II 조기, III 국소 진행성(심평원 급여 조건), IV 전이성"),
    ("2026-10-13", "A 정답 세트 규칙(병기 [Discrepancy]·[Not Available]·빈칸) 우선 적용, 범주를 정할 수 없는 Stage X와 "
                   "조직형 NOS·기록 없음 삭제 (여성 1,086명 → 1,061명)"),
    ("2026-10-13", "재발 상태(recurrence_status)와 현재 범주(current_disease_extent) 추가. 새 원발암만 있거나 재발 정보가 "
                   "불명확한 환자 삭제, 진단 시 전이성과 재생검 기록 환자는 unclear로 남김. 국소 재발은 현재 범주 "
                   "indeterminate (1,061명 → 842명)"),
    ("2026-10-13", "위 규칙을 바꿈. 현재 범주는 전이가 됐는지만 본다: 진단 시 전이성 또는 원격 전이 재발 → metastatic, "
                   "그 밖은 진단 시 범주. 재발 정보가 불명확한 환자를 다시 남기고 indeterminate를 없앰. 병합 스크립트가 "
                   "follow_up_v2.1의 재발 종류를 읽지 않아 46명의 재발 종류가 비어 있던 것도 고침 (842명 → 1,043명)"),
    ("2026-10-14", "현재 전이성 환자 중 전이 후 항암 투약 기록이 없는 환자 삭제. 차수는 정답에 넣지 않고 B 모듈이 판단하도록 "
                   "차수 판단 재료인 전이 기준일(metastasis_dx_days)을 추가 (1,043명 → 997명)"),
    ("2026-10-14", "TCGA 정답은 진단 시(원발 종양) 병리 병기·수용체만 쓴다. 재발 병소 수용체(gdc_nte_*)는 정답에 쓰지 않고 "
                   "참고용으로만 남긴다 (재발 기록과 맞는 환자 1명뿐). 재발 병소 결과 우선 규칙(IN-4)은 가상 차트 등 다른 입력에만 적용"),    ("2026-10-14", "투약별 용량·주기 열 5개(drug_total_dose, drug_total_dose_units, drug_prescribed_dose, drug_dose_units, "
                   "drug_cycles) 추가. anthracycline 누적 용량(심평원 기준 mg/m2) 확인용. 행 수는 그대로"),
    ("2026-10-14", "재발 후 수술 여부(nte_surgery)와 수술일(nte_surgery_days) 열 추가. 행 수는 그대로"),
    ("2026-10-14", "재발 기록과 맞지 않는 수술 기록 정리: 재발 없음인데 수술 YES인 환자 삭제, 재발 여부를 모르는데 "
                   "수술 기록이 있는 환자는 nte_surgery·nte_surgery_days를 빈칸(기록 없음)으로 바꿈"),
    ("2026-10-15", "anthracycline 병용 기록의 용량을 약별로 나눌 수 없는 4명 삭제 (약·용량 개수 다름, 용량에 약 이름, "
                   "순서 불일치). 첫 국소 재발 진단일(locoregional_dx_days) 열 추가"),
    ("2026-10-15", "투약별 시작일·종료일(drug_start_days, drug_end_days)과 재발 사건별 종류·진단일(nte_event_types, nte_dx_days) 열 추가. "
                   "재발했지만 부위를 알 수 없는 환자(site_unknown) 삭제 (992명 → 985명)"),
]

# anthracycline 병용 기록('+')의 용량을 약 순서대로 나눌 수 없는 환자 (사용자 결정, 2026-10-15)
ANTHRACYCLINE_DOSE_UNSPLITTABLE = {
    "TCGA-D8-A27N": "약 4개(paclitaxel+doxorubicin+cyclophosphamide+trastuzumab), 용량 2개(60+600)",
    "TCGA-D8-A1XL": "약 3개(doxorubicin+cyclophosphamide+tamoxifen), 용량 2개",
    "TCGA-D8-A140": "용량에 약 이름이 적힘 (60 doxorubicin+ 600 CPH)",
    "TCGA-D8-A1JM": "약과 용량 순서가 다름 (doxorubicin+cyclophosphamide+tamoxifen, 1200+120+20)",
}


ANTICANCER = {"Chemotherapy", "Hormone Therapy", "HER2-targeted Therapy", "Other Targeted Therapy", "Immunotherapy"}
TIMELINE_ITEM = r"\[(.*?)\] d(\d+)~"


def first_event_day(kind):
    """재발 기록 3개 파일에서 사건 종류(kind 포함)별 가장 이른 진단일 (환자별)."""
    frames = []
    for name, need_yes in [("nte", False), ("follow_up_v4.0_nte", False), ("follow_up_v2.1", True)]:
        f = pd.read_csv(GDC_DIR / f"nationwidechildrens.org_clinical_{name}_brca.txt", sep="\t", skiprows=[1, 2],
                        dtype=str).fillna("")
        if need_yes:
            f = f[f["new_tumor_event_dx_indicator"] == "YES"]
        frames.append(f.loc[f["new_tumor_event_type"].str.contains(kind),
                            ["bcr_patient_barcode", "new_tumor_event_dx_days_to"]])
    d = pd.concat(frames)
    return pd.to_numeric(d["new_tumor_event_dx_days_to"], errors="coerce").groupby(d["bcr_patient_barcode"]).min()


def metastasis_day(df):
    """전이 기준일: 진단 시 전이성 = 0, 원격 전이 재발 = 원격 전이 기록 중 가장 이른 진단일."""
    day = df["patient_id"].map(first_event_day("Distant")).where(df["recurrence_status"] == "distant")
    day[df["stage_disease_extent"] == "metastatic"] = 0
    df["metastasis_dx_days"] = day.astype("Int64")


def locoregional_day(df):
    """첫 국소 재발 진단일. 국소 재발 기록이 없으면 빈칸."""
    df["locoregional_dx_days"] = df["patient_id"].map(first_event_day("Locoregional")).astype("Int64")


def anthracycline_dose_drops(df):
    """anthracycline 병용 기록의 용량을 나눌 수 없는 환자 (사용자 결정, 2026-10-15)."""
    hit = df["patient_id"].isin(ANTHRACYCLINE_DOSE_UNSPLITTABLE)
    return {"anthracycline 병용 용량을 약별로 나눌 수 없음": df.loc[hit, ["patient_id", "drug_prescribed_dose"]]}


def post_metastasis_drops(df):
    """현재 전이성인데 전이 후 항암 투약(골 보호제·보조요법 제외) 기록이 없는 환자 (사용자 결정, 2026-10-14)."""
    def has_post(timeline, day):
        if pd.isna(day) or pd.isna(timeline):
            return False
        items = pd.Series(timeline).str.extractall(TIMELINE_ITEM)
        return any(set(cls.split("|")) & ANTICANCER and int(start) >= day for cls, start in items.itertuples(index=False))

    met = df["current_disease_extent"] == "metastatic"
    no_day = met & df["metastasis_dx_days"].isna()
    no_drug = met & ~no_day & df["drug_timeline"].isna()
    post = pd.Series([has_post(t, d) for t, d in zip(df["drug_timeline"], df["metastasis_dx_days"])], index=df.index)
    no_post = met & ~no_day & ~no_drug & ~post
    cols = ["patient_id", "current_disease_extent"]
    return {"전이성: 원격 전이 진단일 기록 없음": df.loc[no_day, cols],
            "전이성: 투약 기록 없음": df.loc[no_drug, cols],
            "전이성: 전이 후 항암 투약 없음": df.loc[no_post, cols]}


def surgery_cleanup(df):
    """재발 기록과 맞지 않는 재발 후 수술 기록 (사용자 결정, 2026-10-14).

    재발 없음인데 수술 YES → 삭제 대상으로 돌려준다.
    재발 여부를 모르는데 수술 기록이 있음 → 수술 열을 빈칸(기록 없음)으로 바꾸고 환자 목록을 돌려준다.
    """
    surgery = df["nte_surgery"].fillna("")
    contradict = (df["recurrence_status"] == "none") & surgery.str.contains("YES")
    blank = (df["recurrence_status"] == "unknown") & (surgery != "")
    blanked = sorted(df.loc[blank, "patient_id"])
    df.loc[blank, ["nte_surgery", "nte_surgery_days"]] = pd.NA
    drops = {"재발 없음인데 재발 후 수술 YES": df.loc[contradict, ["patient_id", "nte_surgery"]]}
    return drops, blanked


def recurrence_drops(df):
    """진단 시 전이성이 아니면서 새 원발암만 있는 환자 (사용자 결정, 2026-10-13),
    재발했지만 부위(원격·국소)를 알 수 없는 환자 (사용자 결정, 2026-10-15)."""
    new_primary = (df["recurrence_status"] == "new_primary") & (df["stage_disease_extent"] != "metastatic")
    site_unknown = df["recurrence_status"] == "site_unknown"
    return {"새 원발암만 있음 (진단 시 전이성 아님)": df.loc[new_primary, ["patient_id", "recurrence_status"]],
            "재발했지만 부위 모름 (site_unknown)": df.loc[site_unknown, ["patient_id", "recurrence_status"]]}


def current_extent(df):
    """현재 치료 상황의 병기 범주 (biomarker_record.setting.disease의 정답, 사용자 결정 2026-10-13).

    급여·처방 기준에서 필요한 것은 전이가 됐는지뿐이다.
    진단 시 전이성(Stage IV·M1) 또는 원격 전이 재발 → metastatic.
    그 밖(재발 없음, 국소 재발, 재발 부위 모름, 재발 여부 모름)은 진단 시 병기 범주를 그대로 쓴다.
    """
    metastatic = (df["stage_disease_extent"] == "metastatic") | (df["recurrence_status"] == "distant")
    df["current_disease_extent"] = df["stage_disease_extent"].where(~metastatic, "metastatic")


def drop_rows(df):
    """stage_excluded 다음에 삭제할 환자를 사유별로 돌려준다. 한 환자가 여러 사유에 걸릴 수 있다."""
    return {
        "병기 범주를 정할 수 없음": df.loc[df["stage_disease_extent"].isna(), ["patient_id", "gdc_ajcc_pathologic_tumor_stage"]],
        "GDC 임상 기록 없음 (재발 상태 기록 없음)": df.loc[df["has_gdc_clinical"] != "True", ["patient_id", "has_gdc_clinical"]],
        "조직형 NOS·기록 없음·빈칸": df.loc[df["gdc_histological_type"].fillna("").isin(HISTOLOGY_UNKNOWN),
                                       ["patient_id", "gdc_histological_type"]],
    }


CODES = """GDC 결측 코드 (지우지 않고 그대로 둠)
  [Not Available]   값이 기록되지 않음 → 입력 모듈 '기록 없음'
  [Not Evaluated]   검사·평가를 하지 않음 → '미시행'
  [Unknown]         모든 노력을 해도 알 수 없음 → '기록 없음'
  [Not Applicable]  해당 없음 (예: 주 조직형이 Other가 아니면 기타 조직형 칸)
  [Discrepancy]     원본 자료끼리 값이 어긋남
  빈칸              그 출처에 이 환자 기록이 아예 없음
날짜는 진단일을 0으로 한 일수다 (d77 = 진단 후 77일). 여러 값은 '; '로 구분한다."""


def write_columns_txt(df):
    n = len(df)
    lines = [f"TCGA-BRCA 정리본 열 설명 ({OUT_CSV.name})",
             f"작성일 {date.today()} · 환자 {n:,}명 × {df.shape[1]}열", "",
             CODES, "",
             "열 접두어: gdc_ = GDC 환자 임상, cbio_ = cBioPortal, drug_ = 투약 요약, nte_ = 재발 요약,",
             "          fu_ = 추적 관찰 요약, omf_ = 다른 암 병력, mut_ = 체세포 변이, cna_ = 복제수", ""]
    for group, cols in DESCRIPTIONS.items():
        lines += ["=" * 78, f"[{group}]", "=" * 78]
        for c, desc in cols.items():
            s = df[c].astype("string")
            filled = s.dropna()
            filled = filled[~filled.str.match(r"^\[.*\]$")]
            ex = "; ".join(str(v)[:30] for v in filled.value_counts().head(3).index)
            lines += [c, f"    의미: {desc}",
                      f"    실제 값 비율: {100 * len(filled) / n:.1f}%   예시: {ex}", ""]
    OUT_COLS.write_text("\n".join(lines), encoding="utf-8-sig")


def write_changes_txt(before, after, males, recoded, to_iv, by_tnm, dropped, df, surgery_blanked):
    lines = [f"TCGA-BRCA 정리본 변경 내역 ({OUT_CSV.name})", f"작성일 {date.today()}", "",
             f"원본: {SRC.name} (수정하지 않음)",
             f"결과: 환자 {before[0]:,}명 × {before[1]}열  →  {after[0]:,}명 × {after[1]}열",
             f"  열: 원본 {before[1]}열 − 삭제 {sum(len(v) for v in DROP.values())}열 + 새로 만든 {len(NEW_COLS)}열 ({', '.join(NEW_COLS)})", ""]

    lines += ["=" * 78, "0. 정리 기준 변경 이력", "=" * 78]
    lines += [f"  {d}  {what}" for d, what in HISTORY]
    lines.append("")

    drop_ids = set().union(*(set(d["patient_id"]) for d in dropped.values()))
    lines += ["=" * 78, "1. 삭제한 행", "=" * 78,
              f"남성 환자 {len(males)}명 (gdc_gender = MALE). 설계서 범위에서 남성 유방암은 제외",
              "  " + ", ".join(males), "",
              f"병기·기록·조직형·재발 정보 사유 {len(drop_ids)}명 (사용자 결정, 2026-10-13). 첫 사유(A 정답 세트 규칙)로 뺀 환자는 뒤 사유에 다시 적지 않음.",
              "뒤 사유끼리는 한 환자가 여러 사유에 걸리면 사유마다 적음"]
    for reason, rows in dropped.items():
        lines.append(f"[{reason}] {len(rows)}명")
        lines += [f"  {r.iloc[0]}  ({'빈칸' if pd.isna(r.iloc[1]) or r.iloc[1] == '' else r.iloc[1]})" for _, r in rows.iterrows()]
    lines.append("")

    counts = df["stage_disease_extent"].value_counts()
    lines += ["=" * 78, "1-0. 바꾼 값과 새 열: 진단 시 병기 범주 (stage_disease_extent)", "=" * 78,
              "사용자 결정 (2026-10-13). I~II → early(조기), III → locally_advanced(국소 진행성, 심평원 급여 조건의 3기),",
              "IV → metastatic(전이성)",
              f"M1인데 종합 병기가 Stage IV가 아니던 {len(to_iv)}명 → gdc_ajcc_pathologic_tumor_stage를 Stage IV로 바꿈",
              "  " + (", ".join(to_iv) or "없음"),
              f"종합 병기가 없어 AJCC 규칙(M0·MX이면서 T4 또는 N2~3 → III)으로 국소 진행성으로 정한 {len(by_tnm)}명 (병기 값은 그대로 둠)",
              "  " + (", ".join(by_tnm) or "없음"),
              "결과: " + ", ".join(f"{k} {v}명" for k, v in counts.items()), ""]

    rec = df["recurrence_status"].value_counts()
    lines += ["=" * 78, "1-0-1. 새 열: 재발 상태 (recurrence_status)", "=" * 78,
              "사용자 결정 (2026-10-13). 환자·추적 관찰 파일의 재발 여부(new_tumor_event_dx_indicator)와 nte_types로 정함",
              "  none = 재발 없음 (마지막 추적 시점까지) / distant = 원격 전이 재발 (국소 재발이 함께 있어도 distant)",
              "  locoregional = 국소 재발만 / site_unknown = 재발했으나 부위 기록 없음 / unknown = 재발 여부 기록 없음",
              "  new_primary = 새 원발암만. 진단 시 전이성이 아니면 삭제했다 (1. 삭제한 행)",
              "결과: " + ", ".join(f"{k} {v}명" for k, v in rec.items()), ""]

    cur = df["current_disease_extent"].value_counts()
    lines += ["=" * 78, "1-0-2. 새 열: 현재 병기 범주 (current_disease_extent)", "=" * 78,
              "사용자 결정 (2026-10-13). biomarker_record.setting.disease의 정답으로 쓴다",
              "  진단 시 전이성(Stage IV·M1) 또는 원격 전이 재발 → metastatic",
              "  그 밖(재발 없음, 국소 재발, 재발 부위 모름, 재발 여부 모름) → 진단 시 범주 그대로",
              "  급여·처방 기준에서 필요한 것은 전이가 됐는지뿐이다. 국소 재발은 전이가 아니다",
              "현재 전이성 환자 중 전이 후 항암 투약 기록이 없는 환자는 삭제했다 (2026-10-14, 1. 삭제한 행).",
              "차수는 정답에 넣지 않는다. B 모듈이 drug_timeline과 metastasis_dx_days(전이 기준일)로 판단한다",
              "결과: " + ", ".join(f"{k} {v}명" for k, v in cur.items()), ""]

    lines += ["=" * 78, "1-0-3. 바꾼 값: 재발 후 수술 기록 (nte_surgery)", "=" * 78,
              "사용자 결정 (2026-10-14). 재발 기록과 맞지 않는 수술 기록을 정리했다",
              "  재발 없음인데 수술 YES → 행 삭제 (1. 삭제한 행)",
              f"  재발 여부를 모르는데 수술 기록(NO)이 있음 → nte_surgery·nte_surgery_days를 빈칸(기록 없음)으로 바꿈 {len(surgery_blanked)}명",
              "  " + (", ".join(surgery_blanked) or "없음"), ""]

    lines += ["=" * 78, "1-1. 바꾼 값: ER·PR 양성 세포 비율 <10%를 판정에 따라 둘로 나눔", "=" * 78,
              "사용자 결정 (2026-10-12). 원래 값은 tcga_brca_merged.csv에 그대로 있음",
              "  <10% + Positive → 구간 1-9%. ER만 판정을 Low Positive로 바꿈 (ASCO/CAP 2020의 Low Positive는 ER에만 정의됨)",
              "                    PR은 판정 Positive를 그대로 둠 (PR에는 저발현 범주가 없음)",
              "  <10% + Negative → 구간 <1% (가정: 1% 기준 음성)",
              "주의: 1% 기준은 2010년 ASCO/CAP 지침부터다. 2010년 이전 진단 환자의 음성 판정은 10% 기준이었을 수 있어,",
              "      <1%로 바꾼 값 중 일부는 실제로 1-9%였을 수 있다",
              "이력: 2026-10-07에는 <10% + Positive를 Negative로 바꿨고, 2026-10-12 오전에는 PR도 Low Positive로 바꿨다", ""]
    final = set(df["patient_id"])
    lines += ["아래 인원은 여성 전체(행 삭제 전) 기준이다. 정리본에 남은 인원은 [정리본 n명]으로 함께 적는다"]
    for (marker, pct_col, status_col, relabel) in RECODE:
        r = recoded[marker]
        low_kept = [p for p in r["low"] if p in final]
        neg_kept = [p for p in r["neg"] if p in final]
        change = f"{status_col}: Positive → Low Positive, " if relabel else f"{status_col}: Positive 유지, "
        lines += [f"[{marker}] {change}{pct_col}: <10% → 1-9%  {len(r['low'])}명 [정리본 {len(low_kept)}명]",
                  "  " + (", ".join(r["low"]) or "없음"),
                  f"[{marker}] {pct_col}: <10% → <1% (판정 Negative)  {len(r['neg'])}명 [정리본 {len(neg_kept)}명], "
                  f"이 중 2010년 이전 진단 {r['neg_before_2010']}명",
                  "  " + (", ".join(r["neg"]) or "없음")]
    lines.append("")

    n_drop = sum(len(v) for v in DROP.values())
    lines += ["=" * 78, f"2. 삭제한 열 ({n_drop}개)", "=" * 78]
    for group, cols in DROP.items():
        lines += [f"[{group}] {len(cols)}개"]
        lines += [f"  {c:<55} {why}" for c, why in cols.items()]
        lines.append("")

    lines += ["=" * 78, "3. 유지하기로 정한 열 (삭제 후보였음)", "=" * 78,
              "  MSI·TMB 점수 3개: 종양 비특이 면역항암제 적응증(MSI-H, TMB-high)에 쓸 수 있음",
              "  재발 시 수용체 결과 11개: 참고용. TCGA 정답에는 쓰지 않는다 (2026-10-14). 재발 병소 우선 규칙(IN-4)은 가상 차트로 테스트",
              "  원본 약제 열 2개 (drug_names_raw, drug_therapy_types_raw): 정규화 전 값과 대조용", ""]

    lines += ["=" * 78, "4. 용어 통일 (tcga_brca_merge.py 단계에서 적용, 사전: data/dictionaries/)", "=" * 78]
    if CORRECTIONS.exists():
        log = pd.read_csv(CORRECTIONS, dtype=str, keep_default_na=False)
        log["n_records"] = log["n_records"].astype(int)
        total = log["n_records"].sum()
        name_n = log.loc[log["name_changed"] == "True", "n_records"].sum()
        type_n = log.loc[log["type_changed"] == "True", "n_records"].sum()
        lines += [f"투약 기록 {total:,}건 중 약제명 {name_n:,}건, 치료 종류 {type_n:,}건을 고침 (남성 환자 기록 포함 전체 기준)",
                  "원본 값은 drug_names_raw, drug_therapy_types_raw 열과 drug_corrections.csv에 남아 있음", "",
                  "4-1. 약제명 → 성분명 (상품명, 오타, 라틴어 표기, 요법 약어 통일)"]
        names = (log.groupby("generic_names")["raw_name"]
                 .agg(lambda s: sorted(set(s), key=lambda r: (r.lower(), r))))
        for generic, raws in names.items():
            raws = [r for r in raws if r.strip().lower() != generic]
            if raws:
                lines.append(f"  {generic:<40} ← " + ", ".join(raws))
        lines += ["", "4-2. 치료 종류 (약제 성분 기준으로 다시 분류)",
                  "  분류: Chemotherapy, Hormone Therapy, HER2-targeted Therapy, Other Targeted Therapy,",
                  "        Bone-modifying Agent(골 보호제), Supportive Care(보조요법), Vaccine, Other, Unknown",
                  "  약제를 알 수 없는 기록은 원본 분류를 그대로 둠", ""]
        t = log[log["type_changed"] == "True"]
        t = (t.groupby(["raw_type", "corrected_type"])
             .agg(n=("n_records", "sum"), drugs=("generic_names", lambda s: ", ".join(sorted(set(s)))))
             .reset_index().sort_values("n", ascending=False))
        for _, r in t.iterrows():
            lines.append(f"  {r.raw_type:<28} → {r.corrected_type:<36} {r.n:>4}건  ({r.drugs})")
    lines += ["", "4-3. 기타 표기",
              "  투약 타임라인 종료일 [Not Available] → ?",
              "  개수·일수 열 소수점(77.0) → 정수(77)",
              "  변이 검사를 받았는데 변이가 없으면 '변이 없음', 검사를 안 받았으면 빈칸", ""]
    OUT_CHANGES.write_text("\n".join(lines), encoding="utf-8-sig")


def main():
    df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_values=[""])
    before = df.shape

    drop_cols = [c for cols in DROP.values() for c in cols]
    keep_cols = [c for cols in DESCRIPTIONS.values() for c in cols]
    unknown = set(drop_cols) - set(df.columns)
    assert not unknown, f"원본에 없는 삭제 열: {unknown}"
    leftover = set(df.columns) - set(drop_cols) - set(keep_cols)
    assert not leftover, f"설명도 삭제 사유도 없는 열: {leftover}"
    assert not set(drop_cols) & set(keep_cols), "삭제와 유지에 동시에 있는 열"

    males = sorted(df.loc[df["gdc_gender"] == "MALE", "patient_id"])
    df = df[df["gdc_gender"] != "MALE"].copy()
    recoded = recode_low_percent(df)
    excluded = stage_excluded(df)
    df = df[~df["patient_id"].isin(excluded["patient_id"])].copy()
    to_iv, by_tnm = stage_extent(df)
    recurrence_status(df)
    dropped = {"종합 병기 [Discrepancy]·[Not Available]·빈칸 (A 정답 세트 규칙, 우선 적용)": excluded, **drop_rows(df)}
    dropped.update(recurrence_drops(df))
    surgery_drops, surgery_blanked = surgery_cleanup(df)
    dropped.update(surgery_drops)
    current_extent(df)
    metastasis_day(df)
    locoregional_day(df)
    dropped.update(post_metastasis_drops(df))
    dropped.update(anthracycline_dose_drops(df))
    drop_ids = set().union(*(set(d["patient_id"]) for d in dropped.values()))
    df = df[~df["patient_id"].isin(drop_ids)]
    df = df[[c for c in df.columns if c in keep_cols]]  # 원래 열 순서 유지, 새 열은 끝에

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    write_columns_txt(df)
    write_changes_txt(before, df.shape, males, recoded, to_iv, by_tnm, dropped, df, surgery_blanked)

    print(f"환자 {before[0]:,}명 × {before[1]}열 → {df.shape[0]:,}명 × {df.shape[1]}열")
    print(f"  남성 {len(males)}명 행 삭제, 열 {len(drop_cols)}개 삭제")
    print(f"  병기·기록·조직형·재발 정보 사유로 {len(drop_ids)}명 행 삭제: " + ", ".join(f"{k} {len(v)}명" for k, v in dropped.items()))
    print(f"  Stage IV로 바꿈 {len(to_iv)}명, 병기 없이 TNM으로 국소 진행성 {len(by_tnm)}명")
    print("  병기 범주: " + ", ".join(f"{k} {v}" for k, v in df["stage_disease_extent"].value_counts().items()))
    print("  재발 상태: " + ", ".join(f"{k} {v}" for k, v in df["recurrence_status"].value_counts().items())
          )
    print("  현재 범주: " + ", ".join(f"{k} {v}" for k, v in df["current_disease_extent"].value_counts().items()))
    print("  <10% → 1-9%(Positive, ER은 Low Positive) / <1%(Negative): " + ", ".join(f"{k} {len(v['low'])}/{len(v['neg'])}명" for k, v in recoded.items()))
    for p in (OUT_CSV, OUT_COLS, OUT_CHANGES):
        print(f"  {p}")


if __name__ == "__main__":
    main()
