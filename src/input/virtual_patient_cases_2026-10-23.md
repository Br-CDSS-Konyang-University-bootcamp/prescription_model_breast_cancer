# 가상 환자 사례 목록 (처방·급여 판정 구간별)

작성: 2026-10-23. 담당 A. 옛 `AB_gap_tasks.md`(A-16~A-24, 지금 없음)를 대체하는 사례 출처 문서.

- 기준: PROJECT.md §12 (2026-10-22 결정: 처방·급여 모듈 평가는 TCGA가 아니라 가상 차트로. TCGA에 등급·Ki-67·PD-L1·pCR·진행일·최신 치료가 없어 조건을 가를 수 없음)
- 앞 문서 (A 작업 문서 `notes/`, 저장소 밖): `virtual_chart_design.md` §2·§3 (기존 10건), `evaluation_plan_2026-10-23.md` §6.5 (20건 제안, 옛 virtual_chart_coverage)·§2 (짝 사례·빈 값·표현 변형)
- 조건 원천: `notes/esmo_hira_crosswalk_2026-10-20.md` (§1 E·M 번호, §2 장·연번)
- 기존 10건 만드는 방법: `src/input/chart/cases/vc_*.py` → `python -m src.input.chart.virtual_chart` → `tests/fixtures/virtual_charts/<사례>/` (`notes/report_templates.md` §1.1)
- **새 사례 N01~N20 만드는 방법 (2026-10-23):** `src/input/script/build_virtual_cases.py` → `python -m src.input.script.build_virtual_cases` → `tests/fixtures/virtual_charts/<VC-01xx>/chart.txt` + `expected/patient_state.json` + `scenario.md` (이 문서 §3의 해당 표를 옮김), 목록 `tests/fixtures/virtual_charts/cases.csv`. 기존 10건과 같은 폴더. 이 문서가 평가 데이터의 기준이고, 기대 결과를 고칠 때는 이 문서 §3을 고친 뒤 스크립트를 다시 돌린다
- 이 문서는 목록만. schemas·`tests/fixtures/`는 이 문서로 바꾸지 않음

## 표기

| 표기 | 뜻 |
|---|---|
| **N01~N20** | 새 사례 제안 번호. evaluation_plan §6.5의 # 1~20과 같은 순서. 가번호 VC-0110~VC-0129 (만들 때 확정) |
| **I01~I12** | 입력 모듈(IN-0~IN-7) 시험용 사례·변형 (§5) |
| **G1~G6** | 이미 만든 짝 사례 묶음 (`cases/pairs.py`, 19건) |
| **G7~** | 아직 안 만든 짝 사례 묶음 (§4) |
| ESMO 위치 | 그림 번호 + 원문 쪽 + 경로 청크 ID 끝자리 (`data/chunks/esmo_algorithm_chunks.json`). 그림 밖 권고는 "본문" + E·M 번호 (본문 쪽은 C 확인) |
| 공고 위치 | 공고책자 2026-10-01의 장·연번 (9장 48~63쪽, 40장 165~171쪽 안). **행별 쪽과 행 단위 조건은 D 확인 필요** (이 PC에 D의 급여 청크 파일 없음) |
| ⚑D | 급여 행 단위 대조가 D 확인 전인 칸 |
| 기대 결과 | 전부 A 초안. **B·C·D·[4] 각 담당자가 원문으로 확정** (virtual_chart_design §6 단계 4~7) |

## 목차

| 번호 | 제목 | 내용 |
|---|---|---|
| 0 | 요약 | 30건 구성, 우선순위 요지 |
| 1 | 기존 사례 | 10건 + 짝 19건, 옛 출처와의 관계 |
| 2 | 판정 구간별 덮는 사례·빈 곳 | ESMO 갈래, 급여 조건, 간주 규칙, 안전 |
| 3 | 새 사례 20건 상세 | 시험 조건, 이야기 핵심 값, 짝, 모듈별 기대 결과 초안 |
| 4 | 기존 사례에 더할 짝·빈 값 변형 | G7~G16 |
| 5 | 입력 모듈 시험용 사례 | IN-0~IN-7 |
| 6 | 우선순위 (30건 기준) | 순위, 예비 사례 |
| 7 | 확인 필요 | D·C·B 확인 목록 |

---

## 0. 요약

- 30건 = 기존 기본 사례 10건 + 새 기본 사례 20건 (N01~N20). 짝 사례·변형은 30건에 세지 않음 (같은 환자의 경계값 변형이라 독립 사례 아님)
- 새 20건의 목표: 사례가 0건인 ESMO 그림 6개(EBC 7, MBC 4·5·6·7·9), HR+/HER2+ 아형, 허가초과 인정, 고식적 항암 2차 이상, `DEEM-HER2ADC-6M` met, 생식세포 양성, 장기 위기
- 30건이 되면 덮는 ESMO 경로 약 10 → 31개 (77개 중), 아형 HR+/HER2- 12 · HER2+ 8 · TNBC 8 · 국소 재발 1 · 범위 외 1
- 입력 모듈 시험용(§5)은 PROJECT §15.4 추출 정확도 세트 쪽. 대부분 기존 사례의 변형으로 만듦

---

## 1. 기존 사례

### 1.1 기본 10건 (virtual_chart_design §2)

| 사례 | 아형 | 결정 시점 | 핵심 판정 | ESMO 경로 |
|---|---|---|---|---|
| VC-0101 | HR+/HER2- (HER2-low) | 전이 2차 | ESR1 cfDNA, 이전 CDK4/6 불충족, elacestrant 공고 없음 | MBC 그림 3 (1207쪽) `14326f` |
| VC-0102 | HR+/HER2- | 전이 2차 | PIK3CA, 40장 병용 비급여 | MBC 그림 3 `1c118e` |
| VC-0103 | HR+/HER2- | 전이 1차 | `DEEM-ENDO-ADJ-1Y` met, CDK4/6 + AI 불충족 | MBC 그림 2 (1206쪽) `a9baa4` |
| VC-0104 | TNBC (HER2-low) | 전이 1차 | PD-L1 CPS 12, DFI 6개월, gBRCA 미시행 | MBC 그림 8 (1213쪽) `e2f44c` |
| VC-0105 | HR-/HER2+ | 선행 후 보조 | 잔존 → T-DM1, trastuzumab 18주기 | EBC 그림 2 (162쪽) `9d09dd`, 그림 6 (168쪽) `83c27d` |
| VC-0106 / 0106b | HR+/HER2- | 보조 | abemaciclib 고위험(크기), Ki-67 시점 차이 / 같은 날 충돌 | EBC 그림 5 (166쪽) `d83cba`, 그림 4 (165쪽) `0196bf` |
| VC-0107 | HR+/HER2- | 보조 | 40세 미만 AI + LHRH, 회송서 | EBC 그림 4 `a14908` |
| VC-0108 | HR+/HER2- | 전이 1차 진행 중 | 골 보호제, 최근 4주 투여 | MBC 그림 2 `1ae139` |
| VC-0109 | HR+/HER2- | 국소 재발 후 보조 | `SET-LOCAL-ADJ`, 간주 규칙 not_applicable | 그림 없음 (본문) |

### 1.2 짝 사례 19건 (`cases/pairs.py`, `tests/fixtures/virtual_charts/pairs/`)

| 묶음 | 경계 | 기본 | 짝 사례 |
|---|---|---|---|
| G1 | 보조 내분비 종료 후 재발 기간 | VC-0103 | g365, g366 |
| G2 | DFI 6개월 | VC-0104 | dfi180, dfi182 |
| G3 | PD-L1 점수·검사법 | VC-0104 | cps9, cps10, sp142 |
| G4 | ER Allred | VC-0107 | er2, er3, er5ps2, er5ps3, er6 |
| G5 | PR Allred | VC-0109 | pr2, pr3 |
| G6 | HER2 IHC·ISH | VC-0101 | her2-0, her2-0f, her2-2n, her2-2a, her2-3p |

evaluation_plan §2.1에는 "6묶음 20건"으로 적혀 있음. `pairs.py` 목록 기준 19건.

### 1.3 옛 출처 `AB_gap_tasks.md`와의 관계

| 항목 | 내용 |
|---|---|
| 옛 출처 | A-16~A-24 → 기본 9건 (VC-0101~0109). VC-0106b는 2026-10-16 결정 4로 추가 |
| A 번호 ↔ VC 번호 대응 | 확인 불가 (파일 없음). 이 문서는 VC 번호만 씀 |
| virtual_chart_design §3의 "AB_gap N-3"(B의 sBRCA 이름 붙임), "AB_gap J-4"(투약 중 vs 기록 없음) | 내용은 design §3 본문에 남아 있음. 이 문서 §7 확인 목록에 옮김 |

---

## 2. 판정 구간별 덮는 사례·빈 곳

"새로 필요" 칸의 번호는 §3의 새 사례, §4의 짝 묶음.

### 2.1 ESMO 조기 유방암 (EBC 2024-02)

| 구간 | ESMO 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| HR+/HER2- 선행 치료 | 그림 2 (162쪽) `5abbd1` | 없음 | N12 |
| HER2+ cT1 N0 수술 먼저 | 그림 2 `c9e462`, 그림 6 (168쪽) `207157`·`f25e5f`·`549ca3` | 없음 | 예비 R03 (§6.2) |
| HER2+ ≥cT2 또는 cN+ 선행 | 그림 2 `9d09dd` | VC-0105 | |
| HER2+ 선행 후 pCR, 진단 시 cN0 / cN+ | 그림 6 `bcc9bd` / `163f7d` | 없음 | N11 (+ cN0 짝) |
| HER2+ 선행 후 잔존 → T-DM1 | 그림 6 `83c27d` | VC-0105 | N11 짝 |
| 폐경 전 Luminal A 1기 → tamoxifen | 그림 4 (165쪽) `08ac92` | 없음 | 예비 R04 |
| 폐경 전 고위험 → OFS + tamoxifen/AI | 그림 4 `a14908` | VC-0107 | |
| 폐경 후 AI | 그림 4 `0196bf` | VC-0106, 0109 | |
| Luminal B 고위험 → abemaciclib | 그림 5 (166쪽) `d83cba` | VC-0106 | G8 (§4) |
| gBRCA 변이 고위험 → olaparib + ET | 그림 5 `6ffe04` 등, 본문 E10·E11 | 없음 | N10 |
| Luminal A 저위험 → ET만 | 그림 5 `1094f4`의 앞 갈래 | 없음 | 예비 R04 |
| TNBC cT1a/b N0 수술 먼저 (pT1a 없음 / pT1b ChT) | 그림 7 (170쪽) `5ab655` / `8ccb0b` / `304a0f` | 없음 | N09 |
| TNBC ≥cT2 또는 N+ 선행 ChT + pembrolizumab → 잔존 / pCR | 그림 7 `796507`·`6c7aa4`·`9ac5a5` / `dbe131` | 없음 | N08 |
| TNBC <cT2 N0 선행 | 그림 7 `a20657` 등 | 없음 | 예비 |
| ER-low (1~9%) TNBC처럼 | 본문 E20 | 없음 (G4 er3·er5ps2는 B 판정만) | N15 |
| 고령·남성·DCIS | 본문 E26 (범위 밖) | 없음 | N20, 예비 R08·R09 |

### 2.2 ESMO 전이성 HR+/HER2- (MBC 2026-05 그림 2~4)

| 구간 | ESMO 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| 1차 de novo / 보조 ET 종료 12개월 넘어 재발 | 그림 2 (1206쪽) `1ae139` | VC-0108, G1 g366 | |
| 1차 보조 ET 중·12개월 이내, PIK3CA wt | 그림 2 `a9baa4` | VC-0103, G1 g365 | |
| 1차 보조 ET 중·12개월 이내, PIK3CA 변이 → inavolisib 3제 | 그림 2 `0a0c7b` | 없음 | N13 |
| 1차 장기 위기 → ChT | 본문 M06 | 없음 | N17 |
| 폐경 전·이행기 OFS 추가 | 본문 M01 | 없음 (전이성 폐경 전 0건) | N19 |
| 2차 ESR1 | 그림 3 (1207쪽) `14326f` | VC-0101 | G15 (ESR1 시점) |
| 2차 PIK3CA | 그림 3 `1c118e` | VC-0102 | |
| 2차 AKT1·PTEN | 그림 3 `416e66` | 없음 | N14 |
| 2차 gBRCA / gPALB2 | 그림 3 `8bf8f8` / `d5aff4` | 없음 | 예비 R05 |
| 2차 표적 변이 없음 (everolimus, CDK4/6 바꿔 쓰기 등) | 그림 3 `0f09b4` | 없음 (VC-0101은 ESR1 갈래) | 예비 |
| 3차 이상, 내분비 적합 → 안 쓴 2차 선택지 | 그림 4 (1208쪽) `535699` | 없음 | 예비 |
| 3차 이상, 이전 ChT 없음, HER2-low·ultralow → T-DXd | 그림 4 `4e3ecd`·`76de27`·`ddbc18` | 없음 | N04, N16 |
| 3차 이상, 이전 ChT 없음, HER2 0 → ChT | 그림 4 `2f74bb`·`c401eb`·`930a6b` | 없음 | N04 짝 |
| 3차 이상, 이전 ChT 있음 → sacituzumab·Dato-DXd / HER2-low T-DXd | 그림 4 `b93339`·`1ab440`·`88ce0e` / `9af0ad`·`12dec2`·`b89463` | 없음 | N05 |

### 2.3 ESMO 전이성 HER2+ (MBC 그림 5~7)

| 구간 | ESMO 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| 1차 ER+ 항암 가능 (THP → 유지 HP-ET-palbociclib / T-DXd-pertuzumab) | 그림 5 (1209쪽) `33f1be`·`6c697d` | 없음 (G6 her2-2a·3p는 B 판정만) | N01 |
| 1차 ER+ 항암 불가 → ET + 항HER2 | 그림 5 `eaa54b` | 없음 | 예비 |
| 1차 ER- 항암 가능 / 불가 | 그림 5 `ce139d`·`44dbb0` / `a0919f` | 없음 | N01 짝 (ER-) |
| 보조 항HER2 종료 6~12개월 안 재발 → 2차 선택지 | 본문 M37 | 없음 | N03 |
| 2차 활동성 뇌 전이, 국소 치료 없음 / 있음 | 그림 6 (1210쪽) `ff7b69` / `f13555`·`c58fb4` | 없음 | N02 |
| 2차 뇌 전이 없음·안정 | 그림 6 `158c93` | 없음 | N02 짝, N03 |
| 3차 이상 (뇌 전이 갈래 포함) | 그림 7 (1211쪽) `b11a0c`·`4d7ea5`·`6b280f`·`c5908c` | 없음 | 예비 R01 |

### 2.4 ESMO 전이성 TNBC (MBC 그림 8·9)

| 구간 | ESMO 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| 1차 PD-L1+ | 그림 8 (1213쪽) `e2f44c` | VC-0104, G2, G3 cps10 | |
| 1차 PD-L1-, gBRCA wt | 그림 8 `b39e9e` | G3 cps9 (C 기대만) | N07 짝 |
| 1차 PD-L1-, gBRCA 변이 | 그림 8 `6df378` | 없음 | N07 |
| 1차 SP142 IC (atezolizumab) | 그림 8 `e2f44c`, 본문 M46 | G3 sp142 | |
| 장기 위기 → capecitabine·taxane ± bevacizumab | 본문 M50 | 없음 | 예비 (N17은 HR+) |
| 2차 이상 gBRCA·gPALB2 | 그림 9 (1214쪽) `856d0a`·`0f049d` | 없음 | 예비 R05 |
| 2차 이상 gBRCA wt → sacituzumab / HER2-low T-DXd | 그림 9 `dde930` / `c541f9` | 없음 | N06 |
| 조기에 pembrolizumab 받은 전이 TNBC | 본문 M45 메모 | 없음 | 예비 R06 |

### 2.5 소수 전이·부위별

| 구간 | ESMO 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| 소수 전이 (OMD) | 그림 10 (1215쪽) `44ccc9` | 없음 | 예비 R07 |
| 골 전이 골 보호제 | 본문 M56 | VC-0108 | G14 (4주 이내) |
| HER2+ 뇌 전이 | 본문 M57 | 없음 | N02 |

### 2.6 급여 조건 (공고책자 2026-10-01) ⚑D

| 구간 | 공고 위치 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| 9장 0. 공통: ER-low도 HR+ | 9장 공통 원칙 | 없음 | N15 |
| 9장 0. 공통: 폐경 정의 (FSH 등) | 9장 공통 원칙 | 없음 (`menopausal_basis` fsh 0건) | N19, G11 |
| 1. 선행 HER2 양성 (총 trastuzumab 18주기) | 9장 1가-1~6 | VC-0105 | N11 |
| 1. 선행 HER2 음성 (AC → paclitaxel, stage Ⅱ~Ⅲ) | 9장 1나 | 없음 | N12 |
| 2. 보조 내분비 폐경 후 AI | 9장 2-1·2·3 | VC-0106, 0109 | |
| 2. 보조 AI + LHRH (40세 미만·림프절 양성·분화도 2~3 중 하나) | 9장 2-4·5·6 | VC-0107 | G10 (나이) |
| 2. 보조 abemaciclib 고위험 (주2) | 9장 2. 주2 | VC-0106 | G8 (크기·림프절·등급) |
| 2. 보조 ChT (TC 1cm 이상 또는 N+, AC → taxane stage Ⅱ~Ⅲ) | 9장 2-10~17·19 | 없음 (판정 대상으로는) | N09 |
| 2. 보조 capecitabine (pCR 미도달 HER2-) | 9장 2-18 | 없음 | N08 |
| 2. 보조 trastuzumab (N+ 또는 1cm 초과) | 9장 2-20 | 없음 | 예비 R03 |
| 2. 보조 pertuzumab (100/100) | 9장 2-22·23·24 | 없음 | N11 |
| 2. 보조 T-DM1 (선행에 taxane + trastuzumab) | 9장 2-25 | VC-0105 | N11 짝 |
| 3가. CDK4/6 + AI 1차 (비스테로이드 AI 이력, 고식 ChT 이력, 폐경 전 ribociclib 예외) | 9장 3가-1~6, 3가 주1 | VC-0103 (불충족), 0108 (확인용), G1 | N19 |
| 3나. 내분비 단독 (fulvestrant 폐경 후) | 9장 3나-1~6 | VC-0101 | N14 짝 |
| 3다. everolimus + exemestane | 9장 3다-2 | VC-0101 | |
| 3다. fulvestrant + CDK4/6 (2차 이상, 바꿔 쓰기 불가) | 9장 3다-7·8·9 | VC-0101 (불충족), 0103 | N13, N19 |
| 4가. trastuzumab + paclitaxel / docetaxel + HP | 9장 4가-1 / 4가-5 | 없음 | N01 |
| 4가. lapatinib + letrozole | 9장 4가-3 | 없음 | 예비 |
| 4가. bevacizumab + paclitaxel (paclitaxel 미사용) | 9장 4가-4 | 없음 | N04, N17 |
| 4가. pembrolizumab + ChT (22C3 CPS, 이전 ICI 없음) | 9장 4가-6·7 | VC-0104, G2, G3 | N07 (불충족), 예비 R06 |
| 4나. 1차 이상 ChT (taxane, anthracycline, carboplatin, capecitabine) | 9장 4나-7~17 | 없음 (판정 대상으로는) | N04, N07, N17 |
| 4나. trastuzumab + anastrozole | 9장 4나-18 | 없음 | 예비 |
| 4나. liposomal doxorubicin (누적 240mg/m² 또는 심장 위험) | 9장 4나-19 | 없음 (데이터만 VC-0101·0102·0104) | N18, G12·G13 |
| 4다. eribulin 2차 (anthracycline·taxane 모두 경험) | 9장 4다-1 | 없음 | N04, N05 짝 |
| 4라. 2차 이상 (nab-paclitaxel, trastuzumab 단독, lapatinib + capecitabine) | 9장 4라-1·19·20 | 없음 | N02 |
| 4라. T-DM1 (6개월 간주) | 9장 4라-21 | 없음 | N02, N03 |
| 4라. T-DXd (HER2 양성만, trastuzumab·taxane 실패) | 9장 4라-22 | 없음 | N02, N03, N04 (불충족) |
| 4마. eribulin 3차 이상 | 9장 4마-1 | 없음 | N05 |
| 4마. sacituzumab (TNBC 3차 이상, 1년 간주, 이전 taxane) | 9장 4마-2 | 없음 | N06, N05 (불충족) |
| 40장 pembrolizumab 선행·보조 | 40장-20 | 없음 | N08 |
| 40장 capivasertib / alpelisib + fulvestrant | 40장-21 / 22 | VC-0102 | N14 |
| 40장 ribociclib 보조 | 40장-25~28 | VC-0106 | |
| 40장 inavolisib 3제 (보조 CDK4/6 종료 12개월 초과) | 40장-29 | 없음 | N13 |
| 40장 olaparib + 내분비 (보조) | 40장-30 | 없음 | N10 |
| Ⅳ zoledronic acid·denosumab (영상 입증, 최근 4주 투여) | Ⅳ 기타 약제 | VC-0108 | G14 |
| 허가초과 인정 (21건, 목록 파일 없음) | 허가초과 항암요법 목록 | 없음 | N08, N01 (⚑D 목록 확인 전) |
| 공고 없음 (`no_criteria`) | crosswalk §2.8 | VC-0101 (elacestrant) | N02 (tucatinib), N04·N16 (HER2-low T-DXd), N05 (ER+ sacituzumab), N07 (전이 olaparib) |

### 2.7 간주 규칙·분류 상태

| 구간 | 근거 | 덮는 사례 | 새로 필요 |
|---|---|---|---|
| `DEEM-ANTHRA-TAXANE` met | 9장 0. 차수 간주 | VC-0101, 0102, 0104 | N04, N05 |
| `DEEM-SG-1Y` met / 경계 | 9장 4마-2 | VC-0103, 0104 | N06 (365/366일 짝) |
| `DEEM-HER2ADC-6M` met | 9장 4라-21·22 | **없음** | N03 |
| `DEEM-ENDO-ADJ-1Y` met / 경계 | 9장 3가, 3다-7~9 | VC-0103, G1 | N19 |
| 간주 규칙 상태 `unknown` | 종료일 없음 | **없음** | G16 (§4) |
| 분류 `covered` | | 다수 | |
| 분류 `covered_conditions_unverified` | | VC-0104, 0108 | N18 짝, G16 |
| 분류 `no_criteria` (공고 없음·조건 불충족) | | VC-0101, 0103 | §2.6 마지막 줄 |
| 분류 허가초과 인정 | | **없음** | N08, N01 |

### 2.8 안전 검사·범위 외 (PROJECT.md §12, evaluation_plan §2.4)

| 구간 | 덮는 사례 | 새로 필요 |
|---|---|---|
| HER2 음성에 HER2 표적 금지 | 9건 | |
| ER·PR 음성에 내분비 단독 금지 | VC-0104, 0105 | N01 짝 (ER-) |
| 진행한 약 재추천 금지 | VC-0101, 0102, 0103, 0109 | N02 (trastuzumab·pertuzumab 진행), N05 |
| 장기 위기에 내분비 + CDK4/6 1순위 금지 | 없음 | N17 |
| 필요한 마커 미시행 → 그 약 대신 검사 권고 | VC-0104 (gBRCA) | N10 짝 (gBRCA 미시행) |
| olaparib과 abemaciclib 동시 금지 | 없음 | N10 (본문 E11) |
| 동반질환 금기 약 계열 | 없음 | N17 (ECOG 2·간 기능), N18 (심장) |
| 범위 외 추천 금지 (남성, DCIS, 임신) | 없음 | N20, 예비 R08·R09 |

---

## 3. 새 사례 20건 상세

일수는 진단일 = 0. 날짜·식별정보·문서 형식은 virtual_chart_design §4를 따름. 기대 결과는 전부 초안이고 담당자가 원문으로 확정.

### N01 HR+/HER2+ 전이 1차, 항암 가능 (VC-0110 가번호)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | HR+/HER2+ 아형 (지금 0건), HER2+ 전이 1차 요법, 유지 요법, 허가초과 후보 |
| 이야기 핵심 값 | 57세 폐경 후. 6년 전 pT2N0 HR+/HER2+ → 보조 AC → TH(trastuzumab 18주기) + letrozole 5년 완료. 완료 14개월 뒤 간·뼈 전이, 간 생검 ER 70%, PR 10%, HER2 IHC 3+. ECOG 0 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 간 생검 ER 70% / ER 0% (→ ER- 갈래, 유지 HP만) |
| B | HER2 positive, ER positive, 아형 HR+/HER2+, `setting.line` 1. 간주 규칙: `DEEM-ANTHRA-TAXANE` met (보조 AC → paclitaxel), 나머지 3개 not_met (보조 종료 후 6개월·1년 넘음) |
| C | MBC 그림 5 (1209쪽) ER+ 항암 가능 `33f1be` (THP → 유지 HP-ET-palbociclib), `6c697d` (T-DXd-pertuzumab). 짝: `ce139d` |
| D ⚑D | docetaxel + HP 9장 4가-5 → `covered`. T-DXd-pertuzumab → `no_criteria` (1차 행 없음, crosswalk §2.8). HP + 내분비 유지 → 확인 필요 (crosswalk §2.4.1 4가-5 메모). palbociclib + trastuzumab → 허가초과 인정 후보 (evaluation_plan §6.3 예시, 목록 확인 전) |
| 추천 | 허용: THP. 금지: 내분비 단독, HER2 표적 없는 요법. 짝(ER-): 내분비 포함 유지 금지 |

### N02 HER2+ 전이 2차, 활동성 뇌 전이 (VC-0111)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 뇌 전이 갈래, 2차 이상 HER2 행, tucatinib 공고 없음, lapatinib + capecitabine의 anthracycline 조건 |
| 이야기 핵심 값 | 51세 폐경 전. 진단 시 cT3N2M1(간), HR-/HER2+ IHC 3+, de novo. 1차 docetaxel + HP 6주기 → HP 유지 15개월 → 새 뇌 전이 3개 (MRI, 최대 1.8cm, 증상 있음) + 간 진행. 경과기록에 "국소 치료 적응 없음" 의사 문장. anthracycline 사용 없음 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 뇌 전이 활동성 / 안정 (MRI 변화 없음, `158c93` 갈래). 추가 짝: 이전 anthracycline 없음 / 있음 (lapatinib + capecitabine 갈림) |
| B | 아형 HR-/HER2+, `setting.line` 2, `metastatic_sites`에 brain |
| C | MBC 그림 6 (1210쪽) `ff7b69` (T-DXd 우선, tucatinib-trastuzumab-capecitabine, T-DM1). 본문 M57. 짝: `158c93` |
| D ⚑D | T-DXd 9장 4라-22 → `covered` (HER2+, trastuzumab·taxane 실패, 2차 이상). T-DM1 4라-21 → `covered`. tucatinib → `no_criteria` (공고 없음). lapatinib + capecitabine 4라-20 → 조건 불충족 (anthracycline 사용 없음). 짝(활동성 → 안정): D 결과 같음 (C만 바뀌어야 함) |
| 추천 | 금지: docetaxel + HP 재추천 (진행), 내분비 단독 |

### N03 HER2+ 보조 trastuzumab 종료 6개월 안 재발 (VC-0112)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | `DEEM-HER2ADC-6M` met (지금 0건), ESMO는 6~12개월까지 2차로 보는데 공고는 6개월 → 두 기준 차이 |
| 이야기 핵심 값 | 46세 폐경 전. pT2N1a(2/14) HR-/HER2+ IHC 3+, 등급 3. 수술 먼저 → 보조 AC×4 → TH, trastuzumab 18주기 종료. 종료 4개월(약 120일) 뒤 폐·간 전이, 뇌 MRI 음성 |
| 결정 시점 | 고식 1차 (실제 차수 0) |
| 짝 사례 | trastuzumab 종료 → 전이 183일 / 184일 (6개월 경계, 달력 계산은 G2처럼 확인) / 270일 (ESMO 2차 갈래, 공고 1차) |
| B | `DEEM-HER2ADC-6M` met (gap 약 120), `DEEM-ANTHRA-TAXANE` met. 아형 HR-/HER2+ |
| C | 본문 M37 → 2차 선택지. MBC 그림 6 `158c93`. 짝 270일: C는 그대로 2차, 짝 184일 초과는 6개월 문구 확인 |
| D ⚑D | T-DXd 4라-22 / T-DM1 4라-21 → `covered` (간주 1차 + 2차 이상). 짝 184일: 간주 not_met → 2차 이상 불충족, 1차 docetaxel + HP 4가-5가 후보 |
| 추천 | 금지: trastuzumab 보조 직후 같은 THP를 1순위로 (짝 184·270일에서는 허용 여부 B 확인) |

### N04 HR+/HER2- 3차, 이전 고식 항암 없음, HER2-low (VC-0113)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 T-DXd 갈래, HER2-low T-DXd 공고 없음, 보조 AC → T로 인한 `DEEM-ANTHRA-TAXANE` met → 고식 항암 "2차" (eribulin) |
| 이야기 핵심 값 | 60세 폐경 후. 보조 AC×4 → paclitaxel×12 → letrozole 5년. 재발 후 1차 letrozole + palbociclib PD(20개월), 2차 exemestane + everolimus PD(6개월). 간 생검 HER2 IHC 1+. 의사 문장 "내분비 치료 더 이상 부적합" |
| 결정 시점 | 고식 3차 (내분비 2차례 후, 고식 항암 실제 0) |
| 짝 사례 | 간 생검 HER2 1+ / 0 (막 염색 없음, `2f74bb` 갈래). N16은 0 faint |
| B | HER2 low, `endocrine_line` 2, `chemo_line` 0, `DEEM-ANTHRA-TAXANE` met |
| C | MBC 그림 4 (1208쪽) `4e3ecd` (이전 ChT 없음 → T-DXd). ESMO "이전 ChT"에 보조 ChT가 드는지 C 확인. 짝: `2f74bb` |
| D ⚑D | T-DXd → `no_criteria` (공고는 HER2 양성만). eribulin 4다-1 → `covered` 기대 (간주 1차 + anthracycline·taxane 모두 경험 → 2차, 간주를 4다 차수에 쓰는지 D 확인). capecitabine 4나-17 → `covered`. bevacizumab + paclitaxel 4가-4 → paclitaxel 이미 사용 → 불충족 |
| 추천 | 허용: T-DXd(공고 없음 표시와 함께) 또는 ChT. 금지: palbociclib·everolimus 재추천 |

### N05 HR+/HER2- 3차 이상, 이전 고식 항암 있음, HER2 0 (VC-0114)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 이전 ChT 갈래, ER+ sacituzumab 공고 없음, 고식 항암 2차 / 3차 이상 경계 |
| 이야기 핵심 값 | 66세 폐경 후. de novo 뼈·폐 전이. 1차 anastrozole + ribociclib PD(26개월), 2차 fulvestrant 단독 PD, 고식 항암 capecitabine PD → paclitaxel PD. 이전 doxorubicin 없음. 폐 생검 HER2 0 |
| 결정 시점 | 고식 항암 3차 |
| 짝 사례 | 고식 항암 1회(capecitabine만) / 2회(capecitabine → paclitaxel). 1회면 eribulin 4다-1 대상인데 anthracycline 미사용으로 불충족 |
| B | HER2 negative(0), `chemo_line` 2 (실제), 간주 규칙 4개 not_met (선행·보조요법 없음) |
| C | MBC 그림 4 `b93339` (sacituzumab·Dato-DXd → T-DXd). HER2 0이라 T-DXd 갈래 아님 |
| D ⚑D | sacituzumab 4마-2 → `no_criteria` (삼중음성만). eribulin 4마-1 → `covered` (3차 이상). 짝(1회): 4다-1 조건 불충족 (anthracycline 없음) |
| 추천 | 금지: capecitabine·paclitaxel 재추천, HER2 표적 |

### N06 TNBC 2차, gBRCA 야생형 → sacituzumab (VC-0115)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 9, sacituzumab 3차 이상 + `DEEM-SG-1Y` 경계 |
| 이야기 핵심 값 | 42세 폐경 전. pT2N1 TNBC (ER 0%, PR 0%, HER2 0) → 보조 AC → paclitaxel. 보조 종료 300일 뒤 폐 전이. PD-L1 22C3 CPS 2. 생식세포 BRCA1·2 검사 음성(문서 있음). 1차 고식 gemcitabine + carboplatin PD(7개월) |
| 결정 시점 | 고식 2차 (실제 1) |
| 짝 사례 | 보조 종료 → 전이 365일 / 366일 (`DEEM-SG-1Y` met / not_met) |
| B | 아형 TNBC, gBRCA negative (germline), `DEEM-SG-1Y` met, `chemo_line` 1 |
| C | MBC 그림 9 (1214쪽) `dde930` (sacituzumab 우선, ChT). 본문 M51 |
| D ⚑D | sacituzumab 4마-2 → `covered` (간주 1차 + 실제 1 = 3차, 이전 taxane 있음). 짝 366일: 실제 2차 → 3차 이상 불충족. eribulin 4다-1 → `covered` (2차) |
| 추천 | 금지: gemcitabine + carboplatin 재추천, PARP 억제제 (gBRCA 음성) |

### N07 TNBC 1차 PD-L1 음성, gBRCA 양성 (VC-0116)

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

### N08 조기 TNBC 선행 pembrolizumab 후 잔존 → capecitabine (VC-0117)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7, 허가초과 인정 (pCR 미달성 pembrolizumab + capecitabine), 40장 pembrolizumab, 보조 capecitabine |
| 이야기 핵심 값 | 44세 폐경 전. cT2N1M0 TNBC, 등급 3, Ki-67 70%. 선행 paclitaxel + carboplatin → AC + pembrolizumab (KEYNOTE-522 요법) → 수술 ypT1bN1a (RCB-II). 생식세포 BRCA 음성 |
| 결정 시점 | 수술 후 보조 |
| 짝 사례 | 잔존 / pCR (ypT0N0 → `dbe131`, capecitabine 대상 아님) |
| B | `neoadjuvant_response.pcr` no, `rcb` RCB-II, gBRCA negative, `setting` adjuvant |
| C | EBC 그림 7 (170쪽) 잔존 갈래 `796507`·`9ac5a5` (보조 pembrolizumab 9주기, gBRCA wt → capecitabine). 짝: `dbe131` |
| D ⚑D | 보조 pembrolizumab 40장-20 → 추가 약제 비급여. capecitabine 9장 2-18 → `covered` (pCR 미도달 HER2-). pembrolizumab + capecitabine 병용 → 허가초과 인정 후보 (목록 확인 전). 짝(pCR): capecitabine 2-18 불충족 |
| 추천 | 금지: 짝(pCR)에서 capecitabine 추천, olaparib (gBRCA 음성) |

### N09 조기 TNBC cT1b N0 수술 먼저 (VC-0118)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7 작은 종양 갈래, TC 급여 "1cm 이상 또는 N+" |
| 이야기 핵심 값 | 63세 폐경 후. 검진 발견 8mm TNBC → 부분절제 + 감시림프절 → pT1b(8mm) N0(0/2), 등급 2 |
| 결정 시점 | 보조 |
| 짝 사례 | ESMO 경계 pT1a 5mm / pT1b 6mm (`5ab655` 보조 없음 고려 / `8ccb0b` ChT). 공고 경계 9mm / 10mm (TC "1cm 이상") |
| B | 아형 TNBC, `ptnm` T1b N0, `disease_extent` early |
| C | EBC 그림 7 `8ccb0b`. 짝 5mm: `5ab655` |
| D ⚑D | TC 9장 2-16 계열 → 조건 불충족 (1cm 미만, N0). AC 계열 행의 크기 조건 D 확인. 짝 10mm: TC `covered` |
| 추천 | 짝 5mm: 전신 요법 필수 표현 금지 (ESMO "고려") |

### N10 HR+/HER2- 고위험 조기, gBRCA 양성 → 보조 olaparib (VC-0119)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 5 olaparib, 40장-30, olaparib과 abemaciclib 동시 금지 (본문 E11) |
| 이야기 핵심 값 | 41세 폐경 전. cT3N1 HR+/HER2- (ER 80%, PR 30%, HER2 0), 등급 3. 선행 AC → paclitaxel → ypT2N1a(2개) 잔존. 생식세포 BRCA2 병원성 변이. CPS+EG 점수 계산 재료(cT·ypN·ER·등급) 모두 있음 |
| 결정 시점 | 보조 |
| 짝 사례 | gBRCA 병원성 / 미시행 (→ olaparib 대신 검사 권고, evaluation_plan §2.2) |
| B | gBRCA positive, `pcr` no, 아형 HR+/HER2-, Ki-67 기록 |
| C | EBC 그림 5 `6ffe04` (Luminal B, gBRCA 변이 → olaparib + ET). 본문 E10·E11 |
| D ⚑D | olaparib + 내분비 40장-30 → olaparib 비급여 + 내분비 급여. abemaciclib 주2 → 고위험 충족(림프절 1~3 + 등급 3) → 100/100. AI + LHRH 2-4~6 → `covered` (림프절 양성·분화도 3) |
| 추천 | 금지: olaparib + abemaciclib 동시. 짝(미시행): olaparib 추천 금지, gBRCA 검사 권고 필수 |

### N11 HER2+ 선행 후 pCR (VC-0120)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 6 pCR 갈래, T-DM1 조건 불충족, 보조 pertuzumab 계속 |
| 이야기 핵심 값 | 50세 폐경 후. cT2N1 HR+/HER2+ (ER 60%, HER2 3+). 선행 TCHP 6주기 → ypT0N0 (pCR). 선행 trastuzumab 6주기 |
| 결정 시점 | 보조 |
| 짝 사례 | pCR / 잔존 ypT1a N0 (→ T-DM1). 추가 짝: 진단 시 cN1 / cN0 (`163f7d` HP 1년 / `bcc9bd` trastuzumab 1년) |
| B | `pcr` yes, 아형 HR+/HER2+ |
| C | EBC 그림 6 `163f7d` (HP 1년 완료, HR+ ET) |
| D ⚑D | 보조 HP 계속 → 선행 요법(1가-5 TCHP)의 연속으로 보는지 2-22~24 보조 pertuzumab 100/100인지 D 확인. T-DM1 2-25 → 불충족 (pCR). 폐경 후 AI 2-1~3 → `covered`. 총 trastuzumab 18주기 이하 |
| 추천 | 금지: pCR인데 T-DM1. 짝(잔존): T-DM1 허용 |

### N12 HR+/HER2- 선행화학요법 결정 (VC-0121)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 공고 1. 선행 HER2 음성 (지금 0건), EBC 그림 2 HR+/HER2- 선행 |
| 이야기 핵심 값 | 47세 폐경 전. cT3N1M0 IIIA, ER 90%, PR 5%, HER2 1+, 등급 3, Ki-67 45% (중심부 생검). 다학제 회의에서 선행 항암 결정 |
| 결정 시점 | 선행 (치료 전, `treatment_history` 비어 있음) |
| 짝 사례 | cT3N1 (stage Ⅲ) / cT1cN0 (IA, 선행 급여 stage Ⅱ~Ⅲ 밖) |
| B | 아형 HR+/HER2- (HER2-low), `setting` neoadjuvant, `ctnm`만 있고 `ptnm` 없음 |
| C | EBC 그림 2 `5abbd1` |
| D ⚑D | AC → paclitaxel 9장 1나 → `covered` (stage Ⅱ~Ⅲ). carboplatin 추가 → 행 없음. 짝 IA: 선행 행 조건 불충족 |
| 추천 | 금지: pembrolizumab 선행 (TNBC 아님) |

### N13 보조 ET 중 재발 + PIK3CA 변이 → inavolisib 3제 (VC-0122)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 2 남은 갈래, 40장-29 |
| 이야기 핵심 값 | VC-0103과 같은 경과(다른 환자, 55세 폐경 후): 보조 letrozole 3년째 폐 전이. 원발 조직 NGS PIK3CA E545K 검출. 보조 CDK4/6 사용 없음 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | PIK3CA 검출 / 미검출 (= VC-0103 갈래). 추가 짝: 보조 abemaciclib 사용, 종료 → 전이 365일 / 366일 (40장-29 "12개월 초과") |
| B | PIK3CA positive, `DEEM-ENDO-ADJ-1Y` met |
| C | MBC 그림 2 `0a0c7b` (fulvestrant-palbociclib-inavolisib) |
| D ⚑D | inavolisib + palbociclib + fulvestrant 40장-29 → inavolisib 비급여 + palbociclib + fulvestrant 3다-7 `covered`. palbociclib + letrozole 3가 → 불충족 (보조 AI 중 재발) |
| 추천 | 금지: AI + CDK4/6 1순위 |

### N14 HR+/HER2- 2차, AKT1 변이 (VC-0123)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 AKT1·PTEN, 40장-21의 폐경 후 백본 |
| 이야기 핵심 값 | 64세 폐경 후. de novo 뼈 전이. 1차 letrozole + abemaciclib PD(22개월). 뼈 생검 실패 → 원발 조직 NGS AKT1 E17K 검출, PIK3CA·ESR1 미검출 |
| 결정 시점 | 고식 내분비 2차 |
| 짝 사례 | 폐경 후 / 폐경 전 (같은 이야기, 46세 월경 있음 → fulvestrant 백본도 급여 아님) |
| B | AKT1 positive, PIK3CA·ESR1 negative, `endocrine_line` 1 |
| C | MBC 그림 3 `416e66` (fulvestrant-capivasertib) |
| D ⚑D | capivasertib + fulvestrant 40장-21 → capivasertib 비급여 + fulvestrant 급여. fulvestrant + CDK4/6 3다-7~9 → 불충족 (이전 CDK4/6). everolimus + exemestane 3다-2 → `covered`. 짝(폐경 전): fulvestrant 3나-6·40장-21 백본 불충족, everolimus 폐경 후 조건 불충족 |
| 추천 | 금지: abemaciclib 재추천 |

### N15 HER2 IHC 2+/ISH 비증폭 + ER low 5% (VC-0124)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | ER-low (ESMO는 TNBC처럼, 공고는 HR+), HER2 ISH 칸, 선행 단계의 ESMO·공고 차이 |
| 이야기 핵심 값 | 39세 폐경 전. cT2N1M0, ER 5% (약양성), PR 0%, HER2 IHC 2+ → SISH 비증폭(비율 1.4), 등급 3, Ki-67 60% |
| 결정 시점 | 선행 |
| 짝 사례 | ER 9% / 10% / 11% (ESMO 1~9% vs B·evaluation_plan §6의 1~10% 정의 차이 확인용) |
| B | ER low, HER2 low (2+/ISH-), 아형 HR+/HER2- (ER-low 태그) |
| C | 본문 E20 → EBC 그림 7 ≥cT2·N+ 갈래 (`796507` 계열 선행 ChT + pembrolizumab) |
| D ⚑D | 9장 1나 HER2- 선행 AC → paclitaxel → `covered`. 40장-20 pembrolizumab(TNBC) → 대상 여부 D 확인 (공고는 ER-low를 HR+로 봄 → TNBC 아님 가능성). 이 차이를 결과에 남기는지 |
| 추천 | 허용 범위 B 결정 필요 (ESMO TNBC형 vs 공고 HR+). 금지: HER2 표적 |

### N16 HER2 IHC 0 faint (초저발현), 전이성 3차 (VC-0125)

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

### N17 장기 위기 + ECOG 2 (VC-0126)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | `visceral_crisis` (지금 0건), ESMO 본문 M06, 안전 검사 |
| 이야기 핵심 값 | 59세 폐경 후. de novo HR+/HER2- (ER 95%, HER2 0), 다발성 간 전이, 총빌리루빈 3.1 mg/dL, AST·ALT 상승, ECOG 2. 경과기록에 "visceral crisis로 판단" 의사 문장 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 장기 위기 있음 / 없음 (같은 간 전이, 간 기능 정상, ECOG 1 → `1ae139` AI-CDK4/6) |
| B | `visceral_crisis` yes, ECOG 2, `setting.line` 1 |
| C | 본문 M06 (장기 부전 임박 → ChT). 짝: MBC 그림 2 `1ae139` |
| D ⚑D | paclitaxel 단독 4나-7~9 → `covered`. bevacizumab + paclitaxel 4가-4 → `covered` (bevacizumab 100/100). ribociclib + letrozole 3가 → `covered` (급여는 되지만 ESMO 1순위 아님) |
| 추천 | 금지: 내분비 + CDK4/6 1순위. 간 기능 때문에 용량 주의 표시 여부는 B 결정 |

### N18 anthracycline 누적 미달 + 심장 위험 → liposomal doxorubicin (VC-0127)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 9장 4나-19 조건 (누적 용량 또는 심장 위험), 심장 칸 yes·종격동 방사선 yes (지금 0건) |
| 이야기 핵심 값 | 61세 폐경 후. TNBC. 보조 AC 3주기 후 심부전 의심으로 중단 (doxorubicin 누적 180 mg/m², mg 표기 + 키·몸무게), 좌측 흉벽·내유림프절 방사선. 협심증 병력, LVEF 48%. 무병 3년 뒤 폐 전이, 1차 paclitaxel PD |
| 결정 시점 | 고식 항암 2차 |
| 짝 사례 | 심장 위험 있음 / 없음 (→ 누적 미달이라 불충족) / 기록 없음 (→ `covered_conditions_unverified`) |
| B | 누적 용량 계산 값 180, 심장 병력 yes, 종격동 방사선 yes, LVEF 48 |
| C | 본문 M26 (liposomal anthracycline 재투여, DFI 12개월 이상) |
| D ⚑D | liposomal doxorubicin 4나-19 → `covered` (심장 위험요소), 50/100. 짝: 위 셋. 심장 위험요소의 공고 정의 D 확인 |
| 추천 | 금지: doxorubicin(일반) 재투여 |

### N19 폐경 전 전이성 HR+, ribociclib 예외, FSH 판정 (VC-0128)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 폐경 전 전이성 (지금 0건), 3가 주1 (tamoxifen 보조 중 재발 폐경 전), `menopausal_basis` fsh, ESMO·공고 차이 |
| 이야기 핵심 값 | 43세. pT2N1 HR+/HER2- → 보조 tamoxifen 2년째 뼈·림프절 전이. 월경 불규칙, FSH 6.2 mIU/mL·E2 폐경 전 범위 (검사 기록). PIK3CA 미검출 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 폐경 전 (FSH 폐경 전 범위) / 폐경 후 (같은 나이, 양측 난소절제 기록) / 기록 없음 (→ confirmed_state_items §7.1 폐경 규칙, 급여 "확인 필요") |
| B | `menopausal_status` premenopausal, basis fsh, `DEEM-ENDO-ADJ-1Y` met (tamoxifen은 비스테로이드 AI 아님) |
| C | MBC 그림 2 `a9baa4` (보조 ET 중 재발 → fulvestrant-CDK4/6) + 본문 M01 (OFS 추가) |
| D ⚑D | ribociclib + AI + LHRH 3가-5·6 → `covered` (폐경 전 ribociclib, tamoxifen 보조 중 재발 인정). palbociclib·abemaciclib + AI → 불충족 (폐경 후만). fulvestrant + CDK4/6 3다-7~9 → 폐경 조건 행별 D 확인 |
| 추천 | 금지: OFS 없는 AI. 짝(기록 없음): 폐경 추정 금지 |

### N20 범위 외: 남성 유방암 (VC-0129)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 안전 검사 "범위 외 추천 금지" (PROJECT.md §1 범위 밖, ESMO 본문 E26) |
| 이야기 핵심 값 | 66세 남성. pT2N1 HR+/HER2- (ER 95%, PR 80%, HER2 1+). 보조 결정 |
| 결정 시점 | 보조 |
| 짝 사례 | 같은 이야기 여성 66세 폐경 후 (일반 보조 AI 갈래) |
| B | 범위 외 표시 (성별 칸 처리 방식 B 확인). 폐경 상태 칸은 해당 없음 |
| C | 검색은 해도 추천에 쓰지 않음 |
| D ⚑D | 판정하지 않음 또는 범위 외 표시 (D와 형식 합의) |
| 추천 | 허용: 없음 ("범위 외, 의사 판단"). 금지: 어떤 약제든 추천 |

---

## 4. 기존 사례에 더할 짝·빈 값 변형

evaluation_plan §2.1 표의 아직 안 만든 줄 + §2.2 빈 값 변형. 모두 `cases/vc_*.py` 매개변수로 만들고, 30건에 세지 않음.

| 묶음 | 경계 | 기본 | 바꿀 값 | 갈리는 판정 | 근거 위치 |
|---|---|---|---|---|---|
| G7 | Ki-67 | VC-0106 | 19% / 20% | 분자 아형 Luminal A/B, ESMO 고위험 | EBC 그림 5 `d83cba`, 본문 E08 (기호?) |
| G8 | 크기·림프절·등급 | VC-0106 | 50 / 51 mm, 림프절 3 / 4개, 등급 2 / 3 | abemaciclib 고위험 | 9장 2. 주2 ⚑D, EBC 그림 5 |
| G10 | 나이 (폐경 전 보조) | VC-0107 | 39 / 40세 | AI + LHRH ① 40세 미만 | 9장 2-4·5·6 ⚑D |
| G11 | 폐경 상태 | VC-0103 | 폐경 후 / 폐경 전 / 이행기 | 내분비 선택, 3가 폐경 조건 | 9장 0. 공통, 3가 ⚑D, 본문 M01 |
| G12 | anthracycline 누적 | VC-0101 | 239 / 240 mg/m², mg 표기 + 키·몸무게 | liposomal doxorubicin | 9장 4나-19 ⚑D |
| G13 | 심장 위험·종격동 방사선 | VC-0104 | 없음 / 있음 / 기록 없음 | liposomal doxorubicin, `covered_conditions_unverified` | 9장 4나-19 ⚑D |
| G14 | 최근 4주 이내 투여 | VC-0108 | 투약 중 / 종료 28일 / 29일 / 종료일 없음 | zoledronic acid | Ⅳ 기타 약제 ⚑D |
| G15 | ESR1 결과 시점 | VC-0101 | 마지막 내분비 진행 뒤 / 앞 | ESR1 양성 vs 재검 필요 | MBC 그림 3 `14326f` |
| G16 | 재발 후 수술 | VC-0109 | 완치 목적 절제 / 고식 / 수술 안 함 | `SET-LOCAL-ADJ`, "절제 불가능한 국소 재발" | 9장 투여 원칙 ⚑D |
| G17 | 간주 규칙 `unknown` (빈 값) | VC-0103 | anastrozole 종료일 "기록 없음" (시작일만) | `DEEM-ENDO-ADJ-1Y` unknown → 3다 `covered_conditions_unverified` | 9장 3다-7~9 ⚑D |
| G18 | 판정 값 기록 없음 (빈 값) | VC-0104 | PD-L1 `not_recorded` / `not_done` | 급여 `covered_conditions_unverified` / B 검사 권고 | 9장 4가-6 ⚑D, evaluation_plan §2.2 |
| G19 | as_of 날짜 | VC-0103 | 개정 공고 시행 전날 / 당일, 공고예고만 있는 약 | 예고는 판정에 안 씀, "진행중" 태그 | evaluation_plan §2.5 (개정 공고 자료 D 확인) |

G9는 비워 둠 (크기·림프절·등급을 G8 하나로 합침).

---

## 5. 입력 모듈 시험용 사례 (IN-0~IN-7)

처방·급여 판정이 아니라 추출을 시험. 정답은 `patient_state`만 (B·C·D 정답 불필요). 대부분 기존 사례의 표현 변형으로 만들고, 정답이 기본 사례와 같거나 정해진 규칙으로 바뀜 (evaluation_plan §5 3).

| ID | 단계 | 시험 | 덮는 사례 | 만드는 방법 | 기대 A 정답 |
|---|---|---|---|---|---|
| I01 | IN-0 비식별화 | 본문 중간 이름(보호자·외부 의사), 주소, 외부 병원 이름, 주민번호 뒷자리 일부 노출 | 머리글 식별정보만 (전 사례) | VC-0107 변형 | 마스킹 뒤 원문 위치(`char_start`·`end`) 유지, 식별정보가 `patient_state`에 없음 |
| I02 | IN-1 문서 분류 | 머리글 없는 문서 경계, 같은 종류 문서 2개 (병리 2건 날짜 다름), 영상 판독, 다학제 회의록 | VC-0107 (회송서), VC-0101 (병리 2건) | VC-0106 변형 | `doc_type`·`doc_date` 정답 |
| I03 | IN-2 표현 변형 | Allred ↔ 비율 + 판정, 한글 ↔ 영문, 상품명 ↔ 일반명, 약어(TCHP), 오타 1~2개, 문서 순서 바꿈 | 일부 (회송서 영문) | VC-0103·0105 변형 (evaluation_plan §2.3) | 기본 사례와 **같은 정답** (판정 변경률 기준선) |
| I04 | IN-3 날짜 | `2021.3.5`, `21/03/05`, `2021년 3월`(일 없음), `2021-03`, 상대 표현("3년 전") | 일부 | VC-0109 변형 | 부분 날짜 허용, 일수 계산, 상대 표현은 후보 + 확인 요청 |
| I05 | IN-3 단위·점수 | doxorubicin mg 총량 + 키·몸무게 ↔ mg/m², PD-L1 CPS ↔ TPS 표기, Ki-67 "15~20%" 구간 | VC-0101·0102·0104 (mg 표기) | VC-0104 변형 | 구간은 `range`, TPS를 CPS로 바꾸지 않음 |
| I06 | IN-4 재생검 우선 | 전이 재생검(오래됨) vs 원발 재판독 보고서(더 최근 날짜) | VC-0101 (재생검이 더 최근) | VC-0101 변형 | 규칙 1(전이 검체 우선)이 날짜보다 앞섬: 재생검 `value`, 원발 재판독 `history[]` |
| I07 | IN-4 cfDNA vs 조직 | 같은 유전자 cfDNA 검출 + 이후 조직 미검출 | VC-0101·0102 (서로 다른 유전자) | VC-0101 변형 | `specimen`별 처리 규칙 B와 확인 (확인 필요 표시) |
| I08 | IN-5 충돌 | 같은 날 다른 문서(병리 보고서 vs 경과기록 요약)의 ER 값 차이, 적힌 판정과 수치 불일치 | VC-0106b (같은 보고서), VC-0101 (PR 5% "약양성") | VC-0107 변형 | `conflicts[]`, `value` 비움 |
| I09 | IN-6 누락 상태 | "미시행" / "결과 대기" / "시행 예정" / "검사 거부" / 언급 없음 | VC-0104 (미시행) | VC-0104 변형 4개 | `not_done` + `raw` ("결과 대기"·"예정"), 거부는 `not_done` + 원문, 언급 없음 `not_recorded`. "거부" 표기는 확인 필요 |
| I10 | IN-6 부정 표현 | "HER2 음성", "변이 없음" vs "검사 안 함" 구분 | 일부 | VC-0102 변형 | 음성은 `present` + negative, 검사 안 함은 `not_done` |
| I11 | IN-7 유전자 보고서 | 다유전자 패널(변이 여러 줄 + 미검출 목록), VUS, 생식세포 보고서, 같은 날 조직·cfDNA 두 보고서 | VC-0101·0102 (변이 1개) | N07 짝(VUS) + VC-0102 변형 | `genomic_reports[]` 원문 보존, VUS는 `detected`가 아닌 별도 표시 (B와 형식 확인), germline/somatic 구분 |
| I12 | 범위 밖 입력 | 남성, DCIS 단독 병리, 임신 중 기록 | 없음 | N20, 예비 R08·R09 | 범위 외 표시 칸 처리 (스키마 칸 여부 확인) |

---

## 6. 우선순위 (30건 기준)

### 6.1 새 20건 순서

기준: (1) 지금 0건인 구간을 몇 개 채우나 (2) 급여 분류 공백(허가초과, 고식 항암 2차 이상, 간주 met) (3) 안전 검사 (4) 만들기 쉬움(기존 사례 재사용).

| 순위 | 사례 | 묶음 | 채우는 0건 구간 | 이유 |
|---|---|---|---|---|
| 1 | N01 HR+/HER2+ 전이 1차 | 1차 묶음 (먼저) | HR+/HER2+ 아형, MBC 그림 5, 허가초과 후보 | 아형 공백이 가장 큼 |
| 2 | N03 HER2+ 6개월 안 재발 | 1차 묶음 | `DEEM-HER2ADC-6M` met, M37 | 간주 규칙 4개 중 하나가 0건 |
| 3 | N02 HER2+ 2차 뇌 전이 | 1차 묶음 | MBC 그림 6, 4라 행, 뇌 전이 | HER2+ 전이 3그림 0건 |
| 4 | N08 조기 TNBC 잔존 | 1차 묶음 | EBC 그림 7, 허가초과 인정, 2-18, 40장-20 | 허가초과 인정 0건 |
| 5 | N06 TNBC 2차 | 1차 묶음 | MBC 그림 9, 4마-2, SG-1Y 경계 | TNBC 2차 0건 |
| 6 | N04 HR+ 3차 HER2-low | 1차 묶음 | MBC 그림 4, 4다-1 | 고식 항암 2차 0건 |
| 7 | N05 HR+ 3차 이전 ChT | 1차 묶음 | 4마-1, ER+ sacituzumab 공고 없음 | 고식 항암 3차 이상 0건 |
| 8 | N07 TNBC gBRCA 양성 | 1차 묶음 | 생식세포 양성, MBC 그림 8 gBRCA | 생식세포 칸 미사용 |
| 9 | N17 장기 위기 | 2차 묶음 | `visceral_crisis`, 안전 검사 | 안전 0건 |
| 10 | N20 남성 (범위 외) | 2차 묶음 | 범위 외 안전 검사 | 안전 0건, 만들기 쉬움 |
| 11 | N10 보조 olaparib | 2차 묶음 | EBC 그림 5 olaparib, 40장-30, E11 | 안전(동시 금지) |
| 12 | N11 HER2+ pCR | 2차 묶음 | EBC 그림 6 pCR | VC-0105 재사용 |
| 13 | N12 HR+ 선행 | 2차 묶음 | 9장 1나 | 공고 1. 음성 0건 |
| 14 | N19 폐경 전 전이 | 2차 묶음 | 폐경 전 전이, FSH, 3가 주1 | 폐경 칸 공백 |
| 15 | N13 inavolisib | 3차 묶음 | MBC 그림 2 남은 갈래, 40장-29 | VC-0103 재사용 |
| 16 | N14 AKT1 | 3차 묶음 | MBC 그림 3 AKT1·PTEN, 40장-21 | VC-0102 재사용 |
| 17 | N18 liposomal doxorubicin | 3차 묶음 | 4나-19, 심장 칸 yes | G12·G13과 같이 |
| 18 | N15 ER-low + HER2 2+/ISH- | 3차 묶음 | ER-low, ISH 칸 | B 정의 확인이 먼저 |
| 19 | N09 TNBC cT1b | 3차 묶음 | EBC 그림 7 작은 종양 | |
| 20 | N16 HER2 ultralow | 3차 묶음 | ultralow T-DXd | N04와 묶음, G6 her2-0f가 B 쪽은 덮음 |

- 1차 묶음 8건이 끝나면 아형 HER2+ 4건, TNBC 4건이 됨. 이 시점에 VC-0103 정답 형식(B·C·D·[4])으로 정답을 같이 씀
- 짝 사례 G7~G19는 기본 사례를 만들 때 같이 (1차 묶음 중 G17·G18 먼저: `unknown`·빈 값 0건)

### 6.2 예비 (31건 이후)

| ID | 사례 | 채우는 구간 | 근거 위치 |
|---|---|---|---|
| R01 | HER2+ 전이 3차 이상 (T-DXd 후) | MBC 그림 7 | 1211쪽 `c5908c` 등, 9장 4라-19·20 ⚑D |
| R02 | HER2+ 전이 1차 ER+ 항암 불가 → ET + 항HER2 | MBC 그림 5 `eaa54b`, 9장 4가-3·4나-18 | 1209쪽 ⚑D |
| R03 | HER2+ pT1a N0 수술 먼저 | EBC 그림 6 `207157`, trastuzumab 1cm 초과 조건 불충족 | 168쪽, 9장 2-20 ⚑D |
| R04 | 폐경 전 Luminal A 1기 → tamoxifen 단독 | EBC 그림 4 `08ac92`, 그림 5 저위험 | 165·166쪽, 9장 2-7 ⚑D |
| R05 | HR+ 2차 gPALB2 / TNBC 2차 gBRCA | MBC 그림 3 `d5aff4`, 그림 9 `856d0a` | 1207·1214쪽 |
| R06 | 조기 pembrolizumab 받은 전이 TNBC | 9장 4가-6 이전 ICI 제외 | ⚑D |
| R07 | 소수 전이 | MBC 그림 10 `44ccc9` | 1215쪽 |
| R08 | DCIS 단독 | 범위 외 | 본문 E26 |
| R09 | 임신 중 유방암 | 범위 외 | PROJECT.md §1 |
| R10 | HR+ 2차 표적 변이 없음 (CDK4/6 바꿔 쓰기 요청) | MBC 그림 3 `0f09b4`, 3다 바꿔 쓰기 불가 | 1207쪽 ⚑D |
| R11 | 동반질환 금기 (`contraindicated_classes`) | 안전 검사 | evaluation_plan §2.4 |

---

## 7. 확인 필요

| 누가 | 무엇 | 관련 |
|---|---|---|
| D | **급여 행 단위 대조 전체** (§2.6 ⚑D 칸, §3 D 행). 이 PC에 D의 급여 청크 파일 없음 | 전 사례 |
| D | 허가초과 인정 21건 목록 (N01 palbociclib + trastuzumab, N08 pembrolizumab + capecitabine 포함 여부) | N01, N08 |
| D | 간주 규칙을 4다·4마 차수에 쓰는 방식 | N04, N05, N06 |
| D | 9장 2-22~24 보조 pertuzumab와 선행 요법 연속의 구분 | N11 |
| D | 40장-20 대상에 ER-low가 드는지 | N15 |
| D | 4나-19 "심장 위험요소" 정의 | N18, G13 |
| D | "6개월 이후"·"1년 이후"의 경계일 계산 (달력 vs 일수) | N03, N06, G1, G2 |
| C | 그림 밖 권고(M06, M37, M26, E10, E11, E20)의 본문 쪽 | N03, N10, N15, N17, N18 |
| C | MBC 그림 4 "이전 ChT"에 보조 ChT가 드는지 | N04, N16 |
| C | ESMO 원문 기호(≥·≤) 9곳 (esmo_hira_crosswalk §1.4) | G7, N13, G1 |
| B | ER-low 상한 (ESMO 1~9% vs evaluation_plan §6 1~10%) | N15 짝 |
| B | VUS, 생식세포/체세포 표기 형식 | N07 짝, I11 |
| B | cfDNA와 조직 결과가 다를 때 규칙 | I07 |
| B | 남성·범위 외 표시 방식 | N20, I12 |
| B | 지금 코드가 차트 BRCA를 sBRCA로 이름 붙여 gBRCA 권고가 안 나옴 (옛 AB_gap N-3, virtual_chart_design §3 VC-0104) | VC-0104, N07, N10 |
| A | 투약 중(`end_day` null)과 종료일 기록 없음 구분 (옛 AB_gap J-4, design §3 VC-0108) | VC-0108, G14, G17 |
| A | "검사 거부" 표기 (IN-6 표에 없음) | I09 |
