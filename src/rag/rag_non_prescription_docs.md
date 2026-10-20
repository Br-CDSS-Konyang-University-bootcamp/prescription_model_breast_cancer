# 처방 RAG에서 제외하는 지침 문서

> **2026-10-20 변경**: ASCO 지침은 재사용 불가로 확인돼 RAG에서 뺐다 (청커·청크·사전 표현 삭제). 아래의 ASCO 관련 내용은 기록으로만 남긴다. 지금 청킹·검색 대상은 ESMO EBC·MBC 2개다.


작성: 2026-10-16. 대상: `team_project/data/guidelines/`
설계 본문은 `rag_guideline_chunking_design_update.md`이다. 아래 문서는 처방 추천 색인에 넣지 않는다.

## 1. 제외 문서 8개

| 파일 | 내용 | 분류 | 제외 이유 |
|---|---|---|---|
| `asco_cap_2020-01_er_pr_testing` | ER/PR 검사법, ER low 판정 (ASCO/CAP) | 검사 | 병리 검사법 지침. 약제 권고가 없다 |
| `asco_cap_2023-06_her2_testing` | HER2 검사·판독, HER2-low/ultralow 보고 (ASCO/CAP) | 검사 | 검사법 지침. 처방 근거는 trastuzumab deruxtecan 지침에 따로 있다 |
| `asco_gen_2024-01_germline_testing` | 어떤 환자에게 생식세포 유전자 검사를 할지 (ASCO/SSO) | 검사 | 검사 대상 선정 지침. PARP 억제제 처방 근거는 olaparib 지침에 있다 |
| `asco_mbc_2022-06_biomarkers` | 전이성에서 어떤 바이오마커를 검사할지 (PIK3CA, gBRCA, PD-L1, MSI, NTRK 등) | 검사 | 권고 문장이 모두 "~하려면 검사해야 한다" 형식이다 |
| `asco_mbc_2023-05_esr1_testing` | 재발·진행 시 ESR1 변이 검사 | 검사 | 권고가 검사 시점에 관한 것이다 |
| `asco_prev_2019-09_risk_reduction_endocrine` | 유방암이 없는 고위험 여성의 예방 내분비요법 | 예방 | 유방암 환자가 대상이 아니다 |
| `asco_mbc_2024-01_resource_stratified` | 자원 제한 국가용 전이성 치료 (basic/limited/enhanced) | 범위 외 | 한국은 자원 최대 수준이라 해당하지 않는다. 다른 지침의 권고를 각색한 것이라 중복된다 |
| `asco_ebc_2019-05_biomarkers_tailorx` | Oncotype DX로 보조 항암 결정 (TAILORx) | 대체됨 | `asco_ebc_2022-04_biomarkers_adjuvant`로 대체됐다 |

## 2. 처방 문서 안에서 제외하는 소단원

처방 문서에 들어 있지만 약제 처방과 무관한 부분이다.

| 문서 | 제외 소단원 |
|---|---|
| ESMO EBC | Screening, diagnosis, pathology · Staging · Locoregional treatment(수술·방사선) · Adjuvant therapy for DCIS · Follow-up, survivorship |
| ESMO MBC | Diagnosis, pathology and molecular biology(바이오마커 검사 표) · Staging and risk assessment(영상 추적) · Follow-up |
| ASCO 처방 문서 | 검사만 권하는 권고: endocrine_targeted Rec 2.1(PIK3CA 검사), Rec 2.2(ESR1 검사 비권고) |
| 공통 | METHODS, Disclaimer, Conflicts of Interest, RESULTS(문헌 수), Open comment, Implementation, Patient communication, Health disparities, Cost, References, Appendix, Acknowledgements, Funding, Disclosure, 머리말·꼬리말 |

## 3. 제외해서 생기는 공백

- **ESR1 변이에 대한 ASCO 처방 권고가 없어진다.** elacestrant 처방은 ESMO MBC 2L 권고로만 검색된다. ASCO capivasertib 지침에는 근거 설명에서만 elacestrant가 나온다.
- **PIK3CA, gBRCA 검사 권고는 RAG가 찾지 않는다.** 검사 공백(`tests_needed`)은 B의 BM-4 규칙이 만든다.

## 4. 나중에 다른 용도로 쓸 수 있는 문서

처방 색인과 섞지 않고 따로 쓰는 경우다.

| 용도 | 문서 |
|---|---|
| B의 판정 규칙(BM-2) 근거 인용 | er_pr_testing (ER low 1~10%), her2_testing (HER2-low/ultralow 정의) |
| `tests_needed` 문장의 출처 인용 | germline_testing, mbc_biomarkers, esr1_testing |

이렇게 쓰려면 `role: testing`으로 따로 색인하고 처방 검색에서는 거른다. 팀 결정 사항이다.
