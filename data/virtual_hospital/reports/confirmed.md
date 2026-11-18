# 확정 상태(confirmed_state) 초안 — 생성 보고

mini `confirmed_fixtures`와 같은 방법 (정답 patient_state + biomarker_record → build_draft 기본값 확정)

- TCGA ①: 씀 671, 못 씀 0
- TCGA ②: 씀 9, 못 씀 0
- BCNB: 결과는 `local/`에만 (약관). 씀 971, 못 씀 0

TCGA ② 장면 차수와 B 확정값이 다른 환자 1명 (A: 이유 모르면 다음 차수, B: 진행 기록 있을 때만)
  - VH-T0213: 장면 endocrine 2차, B 확정값 setting.line_endocrine = 1L
