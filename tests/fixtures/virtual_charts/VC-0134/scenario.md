# VC-0134 (N25) 고위험 보조 letrozole 5년 완료, 연장 결정

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases_2026-10-27.md` §3 N25. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 연장 내분비요법 (본문 E04), 9장 2-2 나는 tamoxifen 5년 뒤 letrozole만, AI 5년 뒤 AI 연장 행 없음 |
| 이야기 핵심 값 | 61세 폐경 후. 수술 pT2 pN2a (6/15), IIIA, HR+/HER2-. 보조 AC #4 → weekly paclitaxel #12 → letrozole 5년 (day 215~2041) 완료, 재발 없음. 결정 day 2070 |
| 결정 시점 | 보조 (연장) |
| 짝 사례 | tamoxifen 5년 완료 뒤 (2-2 나 letrozole `covered`). 아직 만들지 않음 |
| B | HR+/HER2-, early (재발 없음), 보조 |
| C | 본문 E04 (고위험 연장 내분비 7~8년) |
| D ⚑D | AI 연장 → `no_criteria`. tamoxifen 전환 → D 확인 (2-2 나는 tamoxifen 먼저인 순서만) |
| 추천 | 허용: 연장 내분비 (급여 아님 표시) |
