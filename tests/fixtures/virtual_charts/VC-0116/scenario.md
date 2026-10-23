# VC-0116 (N07) TNBC 1차 PD-L1 음성, gBRCA 양성

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N07. 차트·A 정답은 `python -m src.input.script.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 생식세포 양성 (지금 0건), MBC 그림 8 gBRCA 갈래, 전이 olaparib 공고 없음 |
| 이야기 핵심 값 | 38세 폐경 전. 2년 전 pT1cN0 TNBC → 보조 TC×4 (anthracycline 없음). 종료 18개월 뒤 간·림프절 전이. PD-L1 22C3 CPS 1. **생식세포 유전 검사 문서**: BRCA1 병원성 변이 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 생식세포 BRCA1 병원성 / VUS (→ gBRCA wt 갈래 `b39e9e`, IN-7 VUS 시험 겸함) |
| B | gBRCA positive (germline), PD-L1 negative, 아형 TNBC, `DEEM-ANTHRA-TAXANE` not_met (anthracycline 없음) |
| C | MBC 그림 8 `6df378` (olaparib, talazoparib, carboplatin 기반). 짝: `b39e9e` |
| D ⚑D | olaparib(전이) → `no_criteria` (40장-30 보조 HR+만). talazoparib → `no_criteria`. carboplatin 포함 4나-10·14 → `covered`. pembrolizumab 4가-6 → CPS 불충족 |
| 추천 | 짝(VUS): PARP 억제제 금지, VUS를 양성으로 쓰지 않음 |
