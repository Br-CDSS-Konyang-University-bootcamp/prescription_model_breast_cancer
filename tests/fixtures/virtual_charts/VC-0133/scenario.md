# VC-0133 (N24) 폐경 후 보조 bisphosphonate 결정

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N24. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 2 보조 bisphosphonate (지금 0건), zoledronic acid 재발 예방 행 없음 (골전이 조건과 섞지 않기), 투약 중(`ongoing`) 보조 내분비 |
| 이야기 핵심 값 | 63세 폐경 후 (55세 폐경). 골밀도 요추 T-score -1.8. 수술 pT2 pN1a (2/12), IIB, G2, ER 90% / PR 40% / HER2 1+, Ki-67 15%. Oncotype DX RS 12로 항암 생략. 보조 anastrozole 수술 뒤 day 81부터 복용 중 |
| 결정 시점 | 보조 |
| 짝 사례 | 보조 exemestane 처음부터 (2-1~3: tamoxifen 2~3년 뒤 전환만 급여). 아직 만들지 않음 |
| B | HR+/HER2-, 폐경 후, early, 보조 |
| C | EBC 그림 2 `74bcdc` (보조 bisphosphonate), 그림 4 `0196bf` (AI), 본문 E07 |
| D ⚑D | anastrozole 2-1 → `covered`. zoledronic acid → `no_criteria` (고칼슘혈증·골전이만) |
| 추천 | 허용: AI 계속 + bisphosphonate (ESMO, 급여 아님 표시) |
