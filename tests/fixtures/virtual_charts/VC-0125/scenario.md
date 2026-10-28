# VC-0125 (N16) HER2 IHC 0 faint (초저발현), 전이성 3차

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N16. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | HER2-ultralow → T-DXd 갈래, 원발과 전이 HER2 차이 (IN-4 겸함) |
| 이야기 핵심 값 | N04와 같은 경과(다른 환자, 58세). 원발 HER2 0 (2018 보고서), 간 재생검 HER2 0 + 희미한 불완전 막 염색 <10% |
| 결정 시점 | 고식 3차, 이전 고식 항암 없음 |
| 짝 사례 | N04 (HER2 1+), N04 짝 (HER2 0 막 염색 없음) — 세 사례가 0 / 0 faint / 1+ 묶음 |
| B | HER2 ultralow (공고 기준 음성), 재생검 값이 `value`, 원발 0은 `history[]`. N04와 달리 보조 AI 종료 159일 뒤 재발이라 `DEEM-ENDO-ADJ-1Y` met, 1차는 fulvestrant + palbociclib |
| C | MBC 그림 4 `4e3ecd` (low or ultralow → T-DXd), `76de27` (PD 후 HER2 low만) |
| D ⚑D | T-DXd → `no_criteria`. 나머지 N04와 같음 |
| 추천 | ultralow를 "HER2 양성"으로 쓰지 않음 |
