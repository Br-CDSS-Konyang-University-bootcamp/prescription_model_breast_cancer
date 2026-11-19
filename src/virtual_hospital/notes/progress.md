# 진행 기록 (2026-11-09 ~ 11-18)

작성: A (Claude와 작업) · 설계: [../README.md](../README.md) · 가상 데이터 기준: [synthetic_criteria.md](synthetic_criteria.md) · 규칙: [../rules/rules.csv](../../../data/virtual_hospital/rules/rules.csv)

11-09, 11-16, 11-17 기록을 합쳤다 (2026-11-18). 나중에 바뀐 결정은 지우지 않고 "→ 바뀜"으로 적었다.

## 지금 상태 (2026-11-18)

| | TCGA ① 수술 후 | TCGA ② 재발 | BCNB 수술 전 |
|---|---|---|---|
| 가상환자 | **671명** (원자료 1,098 → mini 크롭 838 → 후보 741) | **9명** (원격 재발 13명 중) | **971명** (1,058명 중) |
| 장면 (판정 기준일) | 실제 첫 보조 투약일과 49일 중 빠른 날 (D-10) | 실제로 다음 고식 치료를 정한 날 (D-R1): 내분비 2차 결정 3, 항암 1차 결정 6 | 초진일 |
| 차트 | 외래 경과기록 + 수술 병리 + 분자병리 | ① + 재발 경과기록 + 투약 기록 | 초진 기록 + 중심 생검 병리 + 유방 초음파 |
| 확정 상태 초안 | 671 | 9 | 971 |
| 위치 | `data/virtual_hospital/tcga/` (GitHub) | `data/virtual_hospital/tcga_recur/` (GitHub) | `data/virtual_hospital/local/bcnb/` (약관, 공개 안 함) |

- 검증 V1~V4·V6, 관문 G1~G7 (mini 입력 모듈 재현 포함) 통과, 테스트 9개 통과. mini 코드는 고치지 않음
- 입력 모듈 LLM 시험 (qwen3:14b, 59건): 필드 정확도 98.8%
- 실행 순서: `python -m src.virtual_hospital.build` → `python -m src.virtual_hospital.tcga_recur` → `python -m src.virtual_hospital.confirmed` (BCNB는 `python -m src.virtual_hospital.bcnb`). `vh.build`가 TCGA ① 차트 폴더를 새로 만들므로 `vh.confirmed`는 마지막에

## 기록 (날짜순)

### 11-09 설계와 첫 세트

| 한 일 | 결과 |
|---|---|
| 가능성 검토: Synthea 단독은 안 됨 (이미지 없음, 처방 칸 대부분 없음, 한국 형식 아님) → 실제 슬라이드·라벨을 뼈대로 빈칸만 합성 | 방향 결정 |
| 두 갈래: BCNB = 수술 전, TCGA = 수술 후. 독립 폴더 `virtual_hospital/` | README |
| 설계: 실제 값 범위, 합성 근거 순위 ①~⑤, 결측, 검증 V1~V5, CSV 구조, chart.txt 규칙, 관문 G1~G7, 이미지 DB (슬라이드는 경로, 위치는 좌표, 히트맵은 캐시) | README §4~§11 |
| 모듈 1·2·3·4-B 결과 형식 제안 글 | [module_result_format_proposal.md](module_result_format_proposal.md) |
| 규칙 표 29개 + `src/virtual_hospital/` 코드, TCGA 첫 세트 (테스트 분할만) | 132명 |
| 검사로 잡은 문제: V3가 한 번만 가려 흔들림 → 묶음을 돌려 모두 한 번씩 가림 (기준 5%p 그대로). V1이 MX 표기 버그를 잡음. G7(입력 모듈 재현)이 mini가 못 읽는 표기 3종을 잡음 → 변이 c. 표기를 GDC에서 받음 (M-03) | |
| 슬라이드 등록: 공개 표에는 가상 번호만, 원본 대응은 `data/virtual_hospital/local/slide_map.csv` | V6 통과 |

### 11-10 ~ 11-12 TCGA 보강, BCNB 갈래, 문헌 값

| 날짜 | 한 일 | 결과 |
|---|---|---|
| 11-10 | 학습·시험 분할은 거르지 않고 표시만 → 이어서 분할 자체를 없앰 (차트 만들기가 목적) | 432명 |
| 11-10 | 사용자 결정: MX + I~III기 → M0 (D-06), NX 제외 (S-08), HER2 원자료 모순 25명 제외 (S-07). G6은 조합 전체가 아니라 조각별로 | 487명 |
| 11-10 | BCNB 자료 점검 (주석 좌표 밖 5명, Other type 76명) → BCNB 갈래 완성 | 971명, [bcnb_check.md](bcnb_check.md) |
| 11-10 | 점수 없는 HER2 198명 → 같은 판정의 실제 점수·FISH 조합으로 합성 (Y-07) | 675명 |
| 11-10 | ER·PR을 Allred 형식으로 ("ER 강양성 (Allred 8, 5+3)"), TCGA·BCNB 둘 다 | |
| 11-10 | mini 점검 (읽기만): 입력 모듈 H1~H6, 화면 1 초안 C1·C2, 바이오마커 관찰 B1~B5 | [mini_findings.md](mini_findings.md) |
| 11-11 | BCNB 초진 기록에 "수술 가능" (실제로 전원 수술) | 화면 1 확인 권장 971 → 0건 |
| 11-12 | 문헌 값 원문 확인 후 한국 자료로 교체: Ki-67·grade(KBCR, Won 2022), 초음파(Mun 2025). HER2+ Ki-67(일본)·ECOG(미국)는 한국 자료 없음 | [synthetic_criteria.md](synthetic_criteria.md) |
| 11-12 | Allred 강도 점수를 TCGA 실제 열로 (D-08, Y-06), 실제 총점 사용 (D-09, 8점 만점 확인) | 674명 |

### 11-16 변이 표기, 원자료 모순, BCNB 주석

| 한 일 | 결과 |
|---|---|
| 변이 c. 표기 없던 33명: cBioPortal 변이 위치로 Genome Nexus에서 c. 표기 (42건, 못 받음 0) | **707명** |
| ER 원자료 모순 2명은 넘길 목록이 아니라 제외 (S-09, 사용자 결정) | 넘길 목록 0명 |
| BCNB 주석 좌표 5명: 밖 다각형만 빼고 씀 (I-02) | 다각형 8,614개 사용, 9개 뺌 |
| GitHub 개인 저장소에 올림 (README, 인용, git 설정) | |

### 11-17 재발 갈래, 결정 시점 원칙

| 한 일 | 결과 |
|---|---|
| `drug_setting.csv`·약 설명서 지움 (투약 기록·차수 계산 목적에 맞지 않음, 사용자 결정). M-04 삭제 | |
| `src/virtual_hospital/tcga_recur.py`: 실제 원격 재발 환자의 `[투약 기록]`을 처방된 그대로 써서 mini가 차수를 계산. 병용 약은 같은 구분·시작·종료일이면 한 줄 (D-R4), 주기는 실제 기록만, 안트라사이클린은 실제 1회 용량 | |
| 중단 사유는 실제 값으로만 (D-R2): PD → 진행, 보조 요법이 전이 31일 전 이후까지 → 진행, 보조 내분비 ≥1,640일 → 완료, AC 뒤 28일 안 탁산 → 계획된 변경 (처음 35일 → mini와 같은 28일로), 그 밖 비움 | |
| 미래 값 발견: 기준일을 "전이일 + 14일"로 잡았더니 나중에 판정된 PD가 차트에 들어감 → 기준일에 투약 중인 줄은 반응을 쓰지 않음 | |
| **결정 시점 원칙 (사용자 결정):** 처방 모듈은 아직 처방하지 않은 약을 정하는 도구라, 차트는 약을 새로 정하는 날로 만들고 그날 시작한 약부터는 차트에 쓰지 않는다. 투약 중간 시점의 차트는 만들지 않는다 | |
| TCGA ① 기준일을 실제 첫 보조 투약일로 앞당김 (D-10, 81명). 첫 투약이 가짜 병리 보고일(27일) 전인 36명은 뺌 (S-10, TCGA에 원발 수술 날짜가 없어 순서를 알 수 없음). 번호는 그대로 | **671명** |
| 재발 갈래 장면: 전체 차수 기준 고식 1·2차 결정 → 바뀜 (11-18) | 9명 |
| `truth.csv`의 실제 처방 기록은 **참고용, 정답 아님** (2000년대 미국 처방). 처방 모듈을 거기에 맞추지 않는다. 투약 기록이 없는 TCGA ① 146명은 처방 전 환자로 씀 | |
| `rules.csv` 설명 안 쉼표로 칸이 밀린 Y-05·D-R3 줄 고침 | |

### 11-18 확정 상태, 실제 등급, 장면 다시 정함, LLM 시험

| 한 일 | 결과 |
|---|---|
| 확정 상태 초안 `src/virtual_hospital/confirmed.py`: mini `confirmed_fixtures`와 같은 방법 (정답 patient_state + biomarker_record → `build_draft` 기본값 확정) | 1,651건 모두 |
| 못 쓰던 3명 (사용자 결정): pT2a·pT3a → T2·T3 (D-11, 유방암 병기에 없는 하위 글자, TCGA에 크기 칸 없음, VH-T0704는 병기군으로 확인). 종료일 없는 보조 tamoxifen → 전이까지 5년 미만이면 계속 투약 = 내분비 중 전이 (D-R5) | |
| `fields.csv` rule_id에 거친 규칙을 차례로 (예: `D-06, D-11, D-05`) | |
| ESMO 확인: 차수를 세는 정의는 없음. 권고는 내분비·항암 횟수를 따로 씀 ("ET 2회 이상 후" 등). 따로 세는 명시적 규칙은 심평원(공고 p.55)뿐 | |
| grade를 실제 병리 판독으로 (M-05, 사용자 결정): Thennavan 2021 Data S2의 관 형성·핵 다형성·유사분열 합. 650명 실제, 21명만 합성 (Y-05). 원본은 CC BY-NC-ND 4.0 → `data/virtual_hospital/local/`에만, Europe PMC API로 받음 (`src/virtual_hospital/fetch_thennavan.py`), `data/virtual_hospital/tcga/NOTICE.md`에 출처·합성 표시 | 판독 등급 비율이 KBCR과 비슷 (TNBC 3등급 0.83 vs 0.73) |
| 합성 기준 문서의 "HER2+ grade는 SEER" 표기 고침 (실제 값은 KBCR Table 1) | |
| mini 전체 차수 `line` 삭제 (PR #161). 재발 갈래 장면 고르기를 바꿈: 주 차수 기준 (HR+/HER2-는 내분비) → **바뀜:** HR+/HER2-라도 실제로 항암을 고른 시점을 건너뛰어서, "실제로 다음 고식 치료를 정한 날"로 (D-R1, 사용자 결정 A). mini B·C 규칙은 그대로 (차트 날짜만 정함) | 내분비 2차 결정 3, 항암 1차 결정 6 |
| A·B 차수 판단 차이: A는 끝난 이유를 모르면 다음 차수, B는 진행 기록이 있을 때만. 장면 차수와 B 확정값이 다른 사람 VH-T0213 1명 (`data/virtual_hospital/reports/confirmed.md`) | |
| 입력 모듈 LLM 시험 (`src/virtual_hospital/llm_run.py`, qwen3:14b, GPU, 결과 `data/virtual_hospital/local/llm_runs/t1/`): TCGA ① 50 + ② 9, LLM 실패 0, 한 건 평균 11초 | 필드 정확도 98.8%, 정밀도 99.9%, 재현율 98.4%, 인용 100% |
| LLM이 틀린 칸 27개: 유전자 미시행 한 줄 놓침 3명 × 7칸, 병기군 IA 놓침 2, 폐경 "Peri (…)" 놓침 1, "유방 수술 검체"만 보고 수술 가능 2 | |
| 처방 모듈 시험 적용은 mini 쪽 세션에서 (C 검색 → B 추천 → D 급여) | 진행 중 |

## 뺀 환자 (지금 기준)

| 갈래 | 규칙 | 명 |
|---|---|---|
| TCGA ① | S-02~S-08 (선행요법, IV기·병기 불명, 슬라이드 없음, HER2 모순, pN·pT X, 필수 칸 결측) | `data/virtual_hospital/reports/excluded.csv` |
| TCGA ① | S-09 ER 원자료 모순 | 2 |
| TCGA ① | S-10 첫 투약이 가짜 병리 보고일 전 | 36 |
| TCGA ② | 전이 부위가 mini 표기에 없음 ('other: …') | 4 |
| BCNB | S-B1 모듈 3 정제 11, S-B2 조직형 Other type 76 | 87 |

## 남은 것

| 항목 | 상태 |
|---|---|
| 처방 모듈 시험 적용 (일부 환자) | mini 쪽 세션에서 진행 중 |
| 입력 모듈 LLM 전체 실행 (BCNB 포함, 약 4~5시간) | 사용자 결정 대기 (BCNB를 GPU 서버로 보내는 것은 괜찮음, 2026-11-18) |
| 전이 부위 'other' 3명 되살리기 (피부·원격 림프절로 묶기), 국소 재발 10명 장면 | 결정 필요 |
| VH-T0213 A·B 차수 차이를 팀에 알릴지 | 결정 필요 |
| README 설계 부분 정리 (§7 옛 계획 등) | |
| 모듈 결과 등록·히트맵 | 모듈 결과가 나오면 (틀만 있음) |
| 문헌 값 | HER2+ Ki-67(일본)·ECOG(미국). 초음파(R-04)는 한국 단일 기관 |
| 문서 날짜 간격 | 근거 없는 고정값 (D-02) |
| 비어 있는 칸 (원자료에 없음) | TCGA 종양 크기 mm 전원, 양성 림프절 수 67, TNBC PD-L1, BCNB 유전자 변이·gBRCA |
