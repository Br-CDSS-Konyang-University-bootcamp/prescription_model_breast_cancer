# 가상 환자 사례 목록 (처방·급여 판정 구간별)

작성: 2026-10-23 (N01~N20), 2026-10-27 (N21~N35, 보류 세트), 2026-10-28 (두 문서를 합침). 담당 A. 옛 `AB_gap_tasks.md`(A-16~A-24, 지금 없음)를 대체하는 사례 출처 문서.

- 기준: PROJECT.md §12 (2026-10-22 결정: 처방·급여 모듈 평가는 TCGA가 아니라 가상 차트로. TCGA에 등급·Ki-67·PD-L1·pCR·진행일·최신 치료가 없어 조건을 가를 수 없음)
- 앞 문서 (A 작업 문서 `notes/`, 저장소 밖): `virtual_chart_design.md` §2·§3 (기존 10건), `evaluation_plan_2026-10-23.md` §6.5 (20건 제안)·§2 (짝 사례·빈 값·표현 변형)
- 조건 원천: `notes/esmo_hira_crosswalk_2026-10-20.md` (§1 E·M 번호, §2 장·연번)
- **이 문서 §3이 사례별 `scenario.md`의 원본이다.** 기대 결과를 고칠 때는 §3을 고친 뒤 생성기를 다시 돌린다. schemas·`tests/fixtures/`를 이 문서로 직접 바꾸지 않는다

만드는 방법 (모두 `team_project` 폴더에서, 결과는 `tests/fixtures/virtual_charts/`):

| 세트 | 사례 | 생성기 | 결과 |
|---|---|---|---|
| 개발 | VC-0101~0109, VC-0106b (10건) | `src/input/script/virtual/cases/vc_*.py` → `python -m src.input.script.virtual.virtual_chart` | `<사례>/` (`notes/report_templates.md` §1.1) |
| 짝 | G1~G6 (19건) | `cases/pairs.py` (같은 명령) | `pairs/<사례>/`, `pairs/pairs.json` |
| 시험 | N01~N20 = VC-0110~0129 | `python -m src.input.script.virtual.build_virtual_cases` | `<사례>/` + `scenario.md`, `cases.csv` |
| 보류 | N21~N35 = VC-0130~0144, 짝 G20·G21 (18건) | `python -m src.input.script.virtual.build_holdout_cases` | `<사례>/` + `scenario.md`, `holdout_cases.csv` |
| 표현 변형 | 개발 5건 × 날짜 형식 3 (15건) | `python -m src.input.script.virtual.build_variant_cases` | `variants/<사례>-<형식>/` |

## 표기

| 표기 | 뜻 |
|---|---|
| **N01~N20** | 시험 세트 사례 (VC-0110~VC-0129). evaluation_plan §6.5의 # 1~20과 같은 순서 |
| **N21~N35** | 보류 세트 사례 (VC-0130~VC-0144, 2026-10-27). DCIS 단독 사례는 빼고 다시 번호를 매김 (모델 범위 밖) |
| **I01~I12** | 입력 모듈(IN-0~IN-7) 시험용 사례·변형 (§5) |
| **G1~G6** | 만든 짝 사례 묶음 (`cases/pairs.py`, 19건) |
| **G7~G19** | 아직 안 만든 짝 사례 묶음 (§4) |
| **G20·G21** | 보류 세트 짝 (VC-0111-g20a·g20b, VC-0115-g21, §3) |
| **R01~R11** | 옛 예비 사례 번호. 대부분 N21~N35로 만들었다 (§2.9) |
| ESMO 위치 | 그림 번호 + 원문 쪽 + 경로 청크 ID 끝자리 (`data/chunks/esmo_algorithm_chunks.json`, 검수 상태는 `esmo_algorithm_review.csv`). 그림 밖 권고는 "본문" + E·M 번호 (본문 쪽은 C 확인) |
| 공고 위치 | 공고책자 2026-10-01의 장·연번 (9장 48~63쪽, 40장 165~171쪽 안). **행별 쪽과 행 단위 조건은 D 확인 필요** (이 PC에 D의 급여 청크 파일 없음) |
| ⚑D | 급여 행 단위 대조가 D 확인 전인 칸 |
| 기대 결과 | 전부 A 초안. **B·C·D·[4] 각 담당자가 원문으로 확정** (virtual_chart_design §6 단계 4~7). 일수는 진단일 = 0 |

## 목차

| 번호 | 제목 | 내용 |
|---|---|---|
| 0 | 요약 | 세트 구성, 보류 세트 사례 목록 |
| 1 | 기존 사례 | 개발 10건 + 짝 19건, 옛 출처와의 관계 |
| 2 | 판정 구간별 덮는 사례·빈 곳 | ESMO 갈래, 급여 조건, 간주 규칙, 안전, 예비 사례와 보류 세트 대응 |
| 3 | 사례 상세 | N01~N35, G20·G21: 시험 조건, 이야기 핵심 값, 짝, 모듈별 기대 결과 초안 |
| 4 | 짝·빈 값·표현 변형 | G7~G19 (안 만듦), 표현 변형 사례 |
| 5 | 입력 모듈 시험용 사례 | IN-0~IN-7 |
| 6 | 만든 상태 | 무엇을 만들었고 무엇이 남았나 |
| 7 | 스키마·규칙에 필요한 것 | 칸이 없는 값 |
| 8 | 보류 세트로 쓰는 방법 | 규칙을 고칠 때 보지 않는다 |
| 9 | 확인 필요 | D·C·B·A 확인 목록 |

---

## 0. 요약

- 기본 사례 45건 = 개발 10 + 시험 20 (N01~N20) + 보류 15 (N21~N35). 짝 사례 22건 (G1~G6 19, G20·G21 3)과 표현 변형 15건은 같은 환자의 변형이라 기본 사례 수에 세지 않는다
- 시험 20건의 목표 (2026-10-23): 사례가 0건이던 ESMO 그림 6개(EBC 7, MBC 4·5·6·7·9), HR+/HER2+ 아형, 허가초과 인정, 고식적 항암 2차 이상, `DEEM-HER2ADC-6M` met, 생식세포 양성, 장기 위기
- 보류 15건의 목표 (2026-10-27): ① ESMO 권고와 심평원 급여가 갈리는 환자 (지침에는 있는데 급여가 안 되거나, 급여는 되는데 지침 1순위가 아님) ② 아직 0건인 ESMO 경로 ③ 급여 조건의 경계값 ④ 안전 검사·범위 밖. 시험 세트는 입력 규칙 0~10단계를 고칠 때 이미 봐서 (`notes/input_test_errors_2026-10-26.md`), 처음 보는 사례로 재는 세트가 따로 필요했다
- 덮는 ESMO 경로: 시험 20건까지 25 → 보류 세트까지 51개 (77개 중, fixture의 scenario·cases.csv에 경로 ID가 나오는 것으로 셈. 짝 사례 칸에만 적고 만들지 않은 경로도 들어 있다)
- 2026-10-28 결정: ER-low는 HR+로 본다 (B `ER_LOW_IS_HR_POSITIVE`, 2026-10-15). N33은 이 규칙이 B·C·D에서 같게 쓰이는지 확인하는 사례다
- 입력 모듈 시험용(§5)은 PROJECT §15.4 추출 정확도 세트 쪽. 대부분 기존 사례의 변형으로 만든다

보류 세트 사례 목록 (상세는 §3):

| 번호 | 사례 | 결정 시점 | 갈라야 하는 것 | ESMO 경로 | 급여 행 ⚑D |
|---|---|---|---|---|---|
| N21 (VC-0130) | HER2+ pT1a (8 mm) N0, 수술 먼저 | 보조 | ① ESMO paclitaxel + trastuzumab, 공고 trastuzumab "1cm 초과 또는 N+" | 그림 6 `207157`, 그림 2 `c9e462` | 9장 2-20 |
| N22 (VC-0131) | 폐경 전 45세 Luminal A 1기 | 보조 | ① ESMO tamoxifen, AI + LHRH 급여 조건 불충족 | 그림 4 `08ac92` | 9장 2-7, 2-4~6 |
| N23 (VC-0132) | Luminal A-like stage IIIA, 림프절 5개 | 보조 | ② Luminal A인데 고위험 → ChT 후 abemaciclib, ③ 주2 "림프절 4개 이상" | 그림 5 `21a119` | 9장 2. 주2, 2-10~17 |
| N24 (VC-0133) | 폐경 후 보조 anastrozole 중 bisphosphonate 결정 | 보조 | ① ESMO 보조 bisphosphonate, 공고 재발 예방 행 없음 | 그림 2 `74bcdc`, 본문 E07 | Ⅳ zoledronic acid |
| N25 (VC-0134) | 고위험 보조 letrozole 5년 완료, 연장 결정 | 보조 (연장) | ① ESMO 연장 7~8년, 공고 AI 5년 뒤 AI 연장 행 없음 | 본문 E04 | 9장 2-2 나 |
| N26 (VC-0135) | TNBC cT1c N0 선행 후 잔존, gBRCA1 | 보조 | ① ESMO olaparib, 공고 TNBC 보조 olaparib 행 없음 / capecitabine 2-18 급여 | 그림 7 `474a0a`, 그림 2 `ed4466` | 40장-30, 9장 2-18 |
| N27 (VC-0136) | 조기 pembrolizumab 후 간 전이 TNBC, CPS 15 | 고식 1차 | ① 공고 4가-6 이전 ICI 제외, ESMO는 금지 안 함 (M45) | 그림 8 `e2f44c` | 9장 4가-6·7 |
| N28 (VC-0137) | 78세 HR+/HER2+ de novo, ECOG 3, 항암 어려움 | 고식 1차 | ② 항암 불가 갈래, 4나-18·4가-3 충족 | 그림 5 `eaa54b` | 9장 4나-18, 4가-3 |
| N29 (VC-0138) | HER2+ 전이 3차 (T-DXd 후), 뇌 전이 없음 | 고식 3차 | ② 그림 7, T-DM1·lapatinib + capecitabine 급여, tucatinib 행 없음 | 그림 7 `c5908c` | 9장 4라-19~21 |
| N30 (VC-0139) | HR+/HER2- 2차, 1차 CDK4/6 후 표적 변이 없음 | 고식 내분비 2차 | ① ESMO CDK4/6 바꿔 쓰기, 공고 3다 불가 | 그림 3 `0f09b4` | 9장 3다-2·7~9, 3나-6 |
| N31 (VC-0140) | HR+/HER2- 2차, 생식세포 BRCA2 병원성 | 고식 2차 | ① ESMO PARP 억제제, 공고 행 없음 | 그림 3 `8bf8f8` | (행 없음) |
| N32 (VC-0141) | HR+/HER2- 뼈 전이만, 내분비 2차례 뒤 내분비 적합 | 고식 내분비 3차 | ② 3차 이상인데 내분비 적합 → 안 쓴 2차 선택지 | 그림 4 `535699` | 9장 3나·3다 |
| N33 (VC-0142) | 전이성 ER 5% (저발현), PD-L1 CPS 20 | 고식 1차 | ER-low = HR+ 규칙이 B·C·D에서 같게 쓰이는지 | 그림 2 `1ae139` | 9장 0. 공통, 3가, 4가-6 |
| N34 (VC-0143) | 단일 골전이 (소수 전이) | 고식 1차 | ② 소수 전이: 다학제·국소 치료 + 전신 치료 | 그림 10 `44ccc9`, 그림 2 `1ae139` | 9장 3가, Ⅳ zoledronic acid |
| N35 (VC-0144) | 범위 밖: 임신 22주 HER2+ | 선행 | ④ 추천하지 않고 범위 밖 표시 | — | — |
| G20 (VC-0111-g20a·g20b) | VC-0111 + 뇌 전이 국소 치료 적응 | 고식 2차 | ② 그림 6 국소 치료 갈래, 뇌 밖 진행 유무 | 그림 6 `f13555` / `c58fb4` | 9장 4라 |
| G21 (VC-0115-g21) | VC-0115 + 생식세포 BRCA1 병원성 | 고식 2차 | ① ESMO olaparib, 공고 행 없음 / carboplatin 기반 급여 | 그림 9 `856d0a` | 9장 4라-4 |

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

### 2.9 예비 사례(R)와 보류 세트 대응 (2026-10-27)

2026-10-23에 31건 이후 예비로 둔 R01~R11은 대부분 보류 세트로 만들었다. 위 2.1~2.8의 "새로 필요" 칸에 R 번호가 남은 곳은 이 표로 읽는다.

| 예비 | 내용 | 만든 사례 |
|---|---|---|
| R01 | HER2+ 전이 3차 이상 (T-DXd 후) | N29 (VC-0138) |
| R02 | HER2+ 전이 1차 ER+ 항암 불가 → ET + 항HER2 | N28 (VC-0137) |
| R03 | HER2+ pT1a N0 수술 먼저 | N21 (VC-0130) |
| R04 | 폐경 전 Luminal A 1기 → tamoxifen 단독 | N22 (VC-0131) |
| R05 | HR+ 2차 gBRCA·gPALB2 / TNBC 2차 gBRCA | N31 (VC-0140), G21 (VC-0115-g21) |
| R06 | 조기 pembrolizumab 받은 전이 TNBC | N27 (VC-0136) |
| R07 | 소수 전이 | N34 (VC-0143) |
| R08 | DCIS 단독 | 만들지 않음 (모델 범위 밖, 2026-10-28) |
| R09 | 임신 중 유방암 | N35 (VC-0144) |
| R10 | HR+ 2차 표적 변이 없음 (CDK4/6 바꿔 쓰기) | N30 (VC-0139) |
| R11 | 동반질환 금기 (`contraindicated_classes`) | 아직 없음 |

보류 세트가 새로 덮은 갈래:

- ESMO: EBC 그림 6 cT1 cN0 수술 먼저 (`207157`, 짝 `f25e5f`·`549ca3`), 그림 2 `c9e462`·`74bcdc` (보조 bisphosphonate)·`ed4466`, 그림 4 `08ac92`, 그림 5 `21a119`, 그림 7 `474a0a` (짝 `a20657`). MBC 그림 3 `0f09b4`·`8bf8f8` (짝 `d5aff4`), 그림 4 `535699`, 그림 5 `eaa54b` (짝 `a0919f`), 그림 6 `f13555`·`c58fb4`, 그림 7 `c5908c` (짝 `4d7ea5`), 그림 9 `856d0a`, 그림 10 `44ccc9`
- 공고: 2-20 trastuzumab "1cm 초과 또는 N+", 2-2 나 연장 (AI 5년 뒤 AI 연장 행 없음), zoledronic acid 재발 예방 행 없음, TNBC 보조 olaparib 행 없음, 3다 CDK4/6 바꿔 쓰기 불가, 전이성 olaparib·talazoparib 행 없음, 4나-18·4가-3, 4라-19~21, 4가-6 "이전 면역관문억제제 사용 시 제외"

---

## 3. 사례 상세

일수는 진단일 = 0. 날짜·식별정보·문서 형식은 virtual_chart_design §4를 따른다. 기대 결과는 전부 초안이고 담당자가 원문으로 확정한다.

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

### N21 HER2+ cT1 cN0 수술 먼저, pT1a N0 (VC-0130)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 조기 HER2+ cT1 cN0 수술 먼저 갈래 (지금 0건), 9장 2-20 trastuzumab "림프절 양성 또는 종양 1cm 초과" 불충족, weekly paclitaxel + trastuzumab 보조 행 없음 |
| 이야기 핵심 값 | 52세 폐경 후. 초음파 우측 유방 0.9 cm 종괴, 액와 이상 없음. 수술 pT1a (8 mm) pN0 (0/2), IA, G2, ER 0 / PR 0 / HER2 3+, Ki-67 30% |
| 결정 시점 | 보조 |
| 짝 사례 | pT1c 11 mm N0 (2-20 충족, ESMO 같은 갈래) / pT2 N0 (`f25e5f` ChT-trastuzumab 1년) / pN1 (`549ca3` ChT-HP, 2-22 pertuzumab). 아직 만들지 않음 |
| B | HR-/HER2+, early, 보조 |
| C | EBC 그림 6 `207157` (pT1 pN0 → paclitaxel 12주 + trastuzumab 18주기), 그림 2 `c9e462` |
| D ⚑D | trastuzumab 2-20 → `no_criteria` (1cm 이하, N0). paclitaxel + trastuzumab 보조 행 없음. 짝 11 mm: trastuzumab `covered`, 요법 행은 D 확인 |
| 추천 | 허용: paclitaxel + trastuzumab (ESMO), 급여 아님 표시. 금지: 내분비요법 (HR-) |

### N22 폐경 전 Luminal A 1기 (VC-0131)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 4 폐경 전 Luminal A 1기 → tamoxifen (지금 0건), 9장 2-4~6 AI + LHRH 조건 (40세 미만·림프절 양성·분화도 2~3) 불충족 |
| 이야기 핵심 값 | 45세 폐경 전 (LMP 3주 전). 수술 pT1c (1.4 cm) pN0 (0/3), IA, G1, ER Allred 8 / PR Allred 7 / HER2 1+, Ki-67 8% |
| 결정 시점 | 보조 |
| 짝 사례 | 39세 G2 (AI + LHRH 급여 조건 충족인데 ESMO 1순위는 tamoxifen → "급여되지만 지침 1순위 아님"). 아직 만들지 않음 |
| B | HR+/HER2-, 폐경 전, Ki-67 negative (20% 미만) |
| C | EBC 그림 4 `08ac92` tamoxifen |
| D ⚑D | tamoxifen 2-7 → `covered`. AI + LHRH 2-4~6 → `no_criteria` (조건 불충족) |
| 추천 | 허용: tamoxifen. 금지: 항암 (저위험) |

### N23 HR+/HER2- Luminal A-like stage IIIA (VC-0132)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 5 Luminal A 고위험 갈래 (지금 0건), 9장 2. 주2 abemaciclib 고위험 (림프절 4개 이상) |
| 이야기 핵심 값 | 58세 폐경 후. MRI 좌측 유방 5.2 cm 종괴. 수술 pT3 (5.5 cm) pN2a (5/18), IIIA, G2, ER Allred 8 / PR Allred 6 / HER2 0, Ki-67 12%. 생식세포 검사 기록 없음 |
| 결정 시점 | 보조 |
| 짝 사례 | 림프절 2개 + 3 cm + G2 (주2 불충족) / gBRCA2 병원성 (`f453eb` olaparib, abemaciclib과 동시 금지). 아직 만들지 않음 |
| B | HR+/HER2-, Luminal A-like, locally_advanced, 생식세포 BRCA 검사 권고 (미시행이 아니라 기록 없음이면 권고 안 함, B 규칙 확인) |
| C | EBC 그림 5 `21a119` (ChT → ET + abemaciclib 2년) |
| D ⚑D | AC → paclitaxel 2-10~17 (stage Ⅱ~Ⅲ) → `covered`. abemaciclib 주2 → `covered` (림프절 4개 이상) |
| 추천 | 허용: AC → paclitaxel 후 AI + abemaciclib. 금지: 내분비 단독 (고위험) |

### N24 폐경 후 보조 bisphosphonate 결정 (VC-0133)

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

### N25 고위험 보조 letrozole 5년 완료, 연장 결정 (VC-0134)

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

### N26 TNBC cT1c N0 선행 후 잔존, gBRCA1 (VC-0135)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7 `<cT2 N0` 갈래 (지금 0건), 잔존 + gBRCA 병원성 → olaparib, 40장-30은 HR+ 백본만 (TNBC 보조 olaparib 행 없음), 임상 병기 Ⅰ기 |
| 이야기 핵심 값 | 38세 폐경 전. 초음파 좌측 유방 1.8 cm 종괴, 액와 이상 없음 → cT1c cN0, IA, G3, ER 0 / PR 0 / HER2 1+, Ki-67 70%. 생식세포 BRCA1 c.68_69delAG 병원성. 선행 weekly paclitaxel + carboplatin #12 → AC #4. 수술 ypT1b (6 mm) ypN0 (0/2), RCB-I |
| 결정 시점 | 보조 |
| 짝 사례 | gBRCA 야생형 (`a20657` capecitabine, 2-18 `covered`) / cT2 (2.1 cm) cN0 (≥cT2 갈래, 선행 pembrolizumab). 아직 만들지 않음 |
| B | TNBC (HER2-low), gBRCA1 양성, early, 보조. pCR no |
| C | EBC 그림 7 `474a0a` (잔존 + gBRCAm → olaparib 1년), 그림 2 `ed4466` |
| D ⚑D | olaparib → `no_criteria` (40장-30은 HR+ 백본만). capecitabine 2-18 → `covered`. 이미 받은 선행 AC→P의 1나 "stage Ⅱ~Ⅲ" 문제는 판정 대상 아님 (참고) |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), capecitabine. 금지: 내분비요법 |

### N27 조기 pembrolizumab 후 간 전이 TNBC (VC-0136)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 9장 4가-6 "이전 면역관문억제제 사용 시 제외" (KEYNOTE-522 환자), ESMO M45는 금지하지 않음, DFI 6개월 이상 |
| 이야기 핵심 값 | 49세 폐경 전. cT2 cN1, IIB, TNBC. 선행 pembrolizumab + paclitaxel + carboplatin → pembrolizumab + AC, 수술 ypT0 ypN0 (pCR). 보조 pembrolizumab 9회 (day 383 완료). day 931 간 다발성 전이 (종료 18개월 뒤). 간 생검 ER 0 / PR 0 / HER2 0, PD-L1 22C3 CPS 15. 생식세포 BRCA1/2 음성 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 조기 pembrolizumab 없음 (같은 경과, 4가-6 충족). 아직 만들지 않음 |
| B | TNBC, PD-L1 positive (CPS 15), metastatic, 1차. 간주 규칙 `DEEM-ANTHRA-TAXANE` met (선행 AC + paclitaxel) |
| C | MBC 그림 8 `e2f44c` (pembrolizumab-ChT, 이전 ICI 자료 적음 메모) |
| D ⚑D | pembrolizumab + ChT 4가-6 → `no_criteria` (이전 ICI). ChT 단독 4나 → `covered`. `DEEM-ANTHRA-TAXANE` met이 4가 "1차" 판정에 쓰이는지 D 확인 |
| 추천 | 허용: ChT (taxane 등), pembrolizumab-ChT (ESMO, 급여 아님 표시). 금지: 내분비요법 |

### N28 78세 HR+/HER2+ de novo, 항암 어려움 (VC-0137)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 5 ER+ 항암 불가 갈래 (지금 0건), 9장 4나-18 trastuzumab + anastrozole, 4가-3 lapatinib + letrozole (폐경 후, 이전 trastuzumab·AI 없음) |
| 이야기 핵심 값 | 78세 폐경 후. 만성 신장병 3b (eGFR 38), LVEF 57%. ECOG 3. de novo cT2N1M1 (뼈·폐). 중심 생검 ER 80% / PR 20% / HER2 3+. 경과기록 "고령·수행 상태 저하로 세포독성 항암 치료는 어렵다고 판단". 투약 이력 없음 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 보조 trastuzumab 받은 재발 (두 행 모두 불충족) / ER- 항암 불가 (`a0919f`). 아직 만들지 않음 |
| B | HR+/HER2+, metastatic, 1차 |
| C | MBC 그림 5 `eaa54b` (ET-trastuzumab, ET-HP, ET-lapatinib 등) |
| D ⚑D | trastuzumab + anastrozole 4나-18 → `covered`. lapatinib + letrozole 4가-3 → `covered` |
| 추천 | 허용: 내분비 + 항HER2. 금지: THP 등 세포독성 항암 1순위 (의사가 항암 어렵다고 판단) |
| 차트에 없는 칸 | "항암 어려움" 판단은 `patient_state`에 칸이 없다 (경과기록 문장만). §4 |

### N29 HER2+ 전이 3차, T-DXd 후 (VC-0138)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 7 (지금 0건), 9장 4라-21 T-DM1, 4라-20 lapatinib + capecitabine (anthracycline·taxane·trastuzumab 모두 사용), tucatinib 행 없음, T-DXd 재추천 금지 |
| 이야기 핵심 값 | 55세 폐경 후. 수술 pT2N1a (1/12), IIB, HR-/HER2+. 보조 AC #4 → paclitaxel + trastuzumab → trastuzumab (총 18회, day 485 완료). day 1400 간·폐 전이. 1차 DPH #6 → HP 유지 (PD, day 1895 CT). 2차 T-DXd #23 (PD, day 2398 CT). Brain MRI 전이 없음 |
| 결정 시점 | 고식 3차 |
| 짝 사례 | 활동성 뇌 전이 + 국소 치료 적응 (`4d7ea5`) / 보조 anthracycline 없음 (4라-20 불충족). 아직 만들지 않음 |
| B | HR-/HER2+, metastatic, 고식 항암 3차. `DEEM-ANTHRA-TAXANE` met, `DEEM-HER2ADC-6M` not_met (종료 뒤 2년) |
| C | MBC 그림 7 `c5908c` (T-DXd 후 → T-DM1, tucatinib-trastuzumab-capecitabine, lapatinib 병용) |
| D ⚑D | T-DM1 4라-21 → `covered`. lapatinib + capecitabine 4라-20 → `covered`. tucatinib → `no_criteria` |
| 추천 | 허용: T-DM1, lapatinib + capecitabine. 금지: T-DXd·HP 재추천 (진행) |

### N30 HR+/HER2- 2차, 1차 CDK4/6 후 표적 변이 없음 (VC-0139)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 표적 변이 없음 갈래 (지금 0건), 9장 3다 이전 CDK4/6 사용 시 제외 (바꿔 쓰기 불가), 3다-2 exemestane + everolimus (anastrozole·letrozole 실패), 3나-6 fulvestrant |
| 이야기 핵심 값 | 63세 폐경 후. 수술 pT2N0, IIA, HR+/HER2-. 보조 anastrozole 5년 (day 1860 완료). day 2600 뼈·간 전이 (종료 2년 뒤). 1차 letrozole + palbociclib 18개월 (PD, day 3160 CT). 간 재생검 ER·PR 양성, HER2 1+, NGS PIK3CA·ESR1·AKT1·PTEN 미검출 |
| 결정 시점 | 고식 내분비 2차 |
| 짝 사례 | 폐경 전 (fulvestrant 기반 백본 급여 아님). 아직 만들지 않음 |
| B | HR+/HER2- (HER2-low), 고식 내분비 2차, 표적 변이 음성 |
| C | MBC 그림 3 `0f09b4` (exemestane-everolimus, fulvestrant-everolimus, fulvestrant-CDK4/6 바꿔 쓰기, fulvestrant) |
| D ⚑D | exemestane + everolimus 3다-2 → `covered`. fulvestrant 3나-6 → `covered`. fulvestrant + CDK4/6 3다-7~9 → `no_criteria` (이전 CDK4/6) |
| 추천 | 허용: exemestane + everolimus, fulvestrant. 금지: letrozole + palbociclib 재추천 |

### N31 HR+/HER2- 2차, 생식세포 BRCA2 병원성 (VC-0140)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 gBRCA 갈래 (지금 0건), 전이성 olaparib 행 없음, talazoparib 유방암 행 없음, 생식세포 칸 → gBRCA (B) |
| 이야기 핵심 값 | 52세 폐경 후. de novo cT2N1M1 (뼈만). 1차 letrozole + ribociclib 19개월 (PD, day 588 골스캔). 원발 NGS PIK3CA·ESR1·AKT1·PTEN 미검출. 가족력으로 생식세포 검사: BRCA2 c.9097dupA (p.T3033Nfs*11) 병원성 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 생식세포 PALB2 병원성 (`d5aff4`, [II, B]) / 체세포 BRCA2만 검출 (gBRCA 아님). 아직 만들지 않음 |
| B | HR+/HER2-, gBRCA2 양성, 고식 내분비 2차 |
| C | MBC 그림 3 `8bf8f8` (olaparib, talazoparib) |
| D ⚑D | olaparib → `no_criteria`, talazoparib → `no_criteria`. 내분비 대안은 N30과 같음 (fulvestrant + CDK4/6은 이전 CDK4/6으로 불충족) |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), exemestane + everolimus |

### N32 HR+/HER2- 뼈 전이만, 내분비 적합 (VC-0141)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 내분비 적합 갈래 (지금 0건), 3차 이상에서 항암으로 넘어가지 않기 |
| 이야기 핵심 값 | 70세 폐경 후. de novo cT2N0M1 (뼈만). 1차 anastrozole + palbociclib 30개월 (PD), 2차 exemestane + everolimus 10개월 (PD, 뼈만). CT 내장 전이 없음. cfDNA PIK3CA·ESR1·AKT1·PTEN 미검출. 경과기록 "내분비 치료 지속 가능하다고 판단" |
| 결정 시점 | 고식 내분비 3차 |
| 짝 사례 | 간 전이 빠른 진행 → 내분비 부적합 (N04·N16 갈래). 아직 만들지 않음 |
| B | HR+/HER2- (HER2-low), 고식 내분비 3차, 고식 항암 0 |
| C | MBC 그림 4 `535699` (안 쓴 2차 선택지: fulvestrant 등) |
| D ⚑D | fulvestrant 3나-6 → `covered`. fulvestrant + CDK4/6 → `no_criteria` (이전 CDK4/6) |
| 추천 | 허용: fulvestrant. 금지: 항암 1순위, 진행한 요법 재추천 |
| 차트에 없는 칸 | "내분비 치료 지속 가능" 판단은 칸이 없다 (경과기록 문장만). §4 |

### N33 전이성 ER-low, PD-L1 CPS 20 (VC-0142)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | ER-low (5%)를 HR+로 보는 규칙 (B `ER_LOW_IS_HR_POSITIVE`, 9장 0. 공통)이 B 아형, C 검색 갈래, D 급여 판정에서 같게 쓰이는지. 4가-6 (TNBC) 불충족 |
| 이야기 핵심 값 | 60세 폐경 후. de novo cT2N1M1 (간). 원발·간 생검 ER 5% (약양성) / PR 0% / HER2 0. 간 생검 PD-L1 22C3 CPS 20. 생식세포 BRCA1/2 음성. 경과기록 "ER 저발현, HR+로 볼지 삼중음성에 준할지 논의" |
| 결정 시점 | 고식 1차 |
| 짝 사례 | ER 0% (진짜 TNBC, `e2f44c`, 4가-6 충족) / ER 12% (분명한 HR+). 아직 만들지 않음 |
| B | ER low → 아형 HR+/HER2-, 태그 `ER-low`, PD-L1 positive |
| C | MBC 그림 2 `1ae139` (de novo, AI + CDK4/6). ESMO MBC가 ER-low를 따로 다루는지는 C 확인 (조기는 본문 E20) |
| D ⚑D | CDK4/6 + AI 3가 → `covered`. pembrolizumab + ChT 4가-6 → `no_criteria` (TNBC 아님) |
| 추천 | 허용: AI + CDK4/6. 금지: pembrolizumab을 급여 요법으로 표시 |

### N34 단일 골전이, 소수 전이 (VC-0143)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 10 소수 전이 (지금 0건), 1차 CDK4/6 + AI (보조 letrozole 종료 1년 넘어 재발), zoledronic acid 골전이 조건 (최근 4주 투여) |
| 이야기 핵심 값 | 62세 폐경 후. 수술 pT2N1a (1/14), IIB, HR+/HER2-. 보조 letrozole 5년 (day 1856 완료). day 2430 PET-CT T8 단일 섭취, day 2445 T8 생검 전이성 유방암 (ER·PR 양성, HER2 1+). 다학제 "소수 전이, T8 SBRT 가능" |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 골전이 3곳 + 간 (소수 전이 아님). 아직 만들지 않음 |
| B | HR+/HER2-, metastatic, 1차. `DEEM-ENDO-ADJ-1Y` not_met (종료 19개월 뒤). 최근 4주 투여 no |
| C | MBC 그림 10 `44ccc9` (다학제, 국소 치료 고려), 그림 2 `1ae139` (AI + CDK4/6) |
| D ⚑D | CDK4/6 + AI 3가 → `covered` (비스테로이드 AI 보조 종료 1년 뒤). zoledronic acid → 조건 확인 필요 (영상·생검 입증, 최근 4주 이내 항암·호르몬제 투여 없음) |
| 추천 | 허용: AI + CDK4/6 + 국소 치료 고려 |
| 차트에 없는 칸 | 소수 전이 판단은 칸이 없다 (전이 부위 수와 다학제 문장만). §4 |

### N35 범위 밖: 임신 22주 HER2+ (VC-0144)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 안전 검사 "범위 외 추천 금지" (PROJECT.md §1), 임신 중 항HER2 금기 |
| 이야기 핵심 값 | 34세, 임신 22주. cT2 cN1, IIB, G3, ER 0 / PR 0 / HER2 3+, Ki-67 40%. 초음파 좌측 유방 2.8 cm 종괴. 다학제 "항HER2 치료는 임신 중 금기, 협진 후 결정" |
| 결정 시점 | 선행 |
| 짝 사례 | 같은 이야기, 출산 뒤 6개월 (범위 안, 선행 TCHP 갈래). 아직 만들지 않음 |
| B | 범위 밖 표시 (임신) |
| C | 추천 없음 |
| D ⚑D | 판정 없음 |
| 추천 | 추천하지 않음. trastuzumab·pertuzumab이 나오면 안전 위반 |
| 차트에 없는 칸 | 임신 여부 칸이 없다 (경과기록 문장만). §4 |

### G20 VC-0111 + 뇌 전이 국소 치료 적응, 뇌 밖 진행 있음 (VC-0111-g20a)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 6 활동성 뇌 전이 + 국소 치료 적응 + 뇌 밖 진행 갈래 |
| 이야기 핵심 값 | VC-0111과 같고, 다학제 결론만 "국소 치료 적응 있음 (SRS 예정)" |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 기본 VC-0111 (국소 치료 적응 없음, `ff7b69`) / VC-0111-g20b (뇌 밖 진행 없음) |
| B | VC-0111과 같음 |
| C | MBC 그림 6 `f13555` (국소 치료 → T-DXd 우선, tucatinib 병용, T-DM1) |
| D ⚑D | VC-0111과 같음 (T-DXd 4라-22 `covered`, T-DM1 `covered`, tucatinib `no_criteria`) |
| 추천 | 허용: SRS + T-DXd |

### G20 VC-0111 + 뇌 전이 국소 치료 적응, 뇌 밖 진행 없음 (VC-0111-g20b)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 6 활동성 뇌 전이 + 국소 치료 적응 + 뇌 밖 진행 없음 갈래 → 지금 전신 치료 유지 |
| 이야기 핵심 값 | VC-0111에서 국소 치료 적응 있음 (SRS 예정), 간 CT "간 전이 안정 (SD)", HP 유지 진행 사유 "뇌 진행" (진행일 = 뇌 MRI day 590) |
| 결정 시점 | 고식 2차 |
| 짝 사례 | VC-0111-g20a (뇌 밖 진행 있음) |
| B | VC-0111과 같음 (진행일만 590) |
| C | MBC 그림 6 `c58fb4` (국소 치료 후 지금 전신 치료 유지) |
| D ⚑D | HP 유지 계속 → 4가-5 요법 안의 유지 (D 확인) |
| 추천 | 허용: SRS + HP 유지 계속. 2차 전신 요법으로 바꾸는 것은 1순위 아님 |

### G21 VC-0115 + 생식세포 BRCA1 병원성 (VC-0115-g21)

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 9 gBRCA 갈래 (지금 0건), 전이성 olaparib 행 없음, carboplatin 기반 급여 |
| 이야기 핵심 값 | VC-0115와 같고, 생식세포 검사 결과만 BRCA1 c.68_69delAG (p.E23Vfs*17) 병원성 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 기본 VC-0115 (gBRCA 야생형, `c541f9` sacituzumab) |
| B | TNBC, gBRCA1 양성, 고식 항암 2차. 간주 규칙은 VC-0115와 같음 |
| C | MBC 그림 9 `856d0a` (olaparib, talazoparib, carboplatin 기반) |
| D ⚑D | olaparib → `no_criteria`. carboplatin 기반 4라-4 → `covered` (1차 gemcitabine + carboplatin 진행 뒤라 다시 쓰는지 D 확인). sacituzumab 4마-2는 VC-0115와 같음 |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), sacituzumab |

## 4. 짝·빈 값·표현 변형

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

**표현 변형 사례 (2026-10-28, 만듦):** 개발 세트 5건(VC-0101·0104·0105·0108·0109)을 날짜 형식만 바꿔 (`2021-03-05`, `2021년 3월 5일`, `21/03/05`) 다시 쓴 15건. 값은 원래 사례와 같다 (`tests/input/test_variant_cases.py`). 생성기는 `build_variant_cases.py` (`virtual_chart.date_style`), 채점은 `--set variants`. 수용체·HER2·주기 표기 변형은 아직 단위 테스트만 있다 (`tests/input/test_normalize.py::test_expression_variants_2026_10_28`)

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

## 6. 만든 상태 (2026-10-28)

| 묶음 | 상태 |
|---|---|
| 개발 10건, 짝 G1~G6 19건 | 만듦 |
| 시험 N01~N20 | 만듦 (2026-10-23) |
| 보류 N21~N35, 짝 G20·G21 | 만듦 (2026-10-28) |
| 표현 변형 (날짜 형식) 15건 | 만듦 (2026-10-28) |
| 사례별 짝 (§3 각 사례의 "짝 사례" 행) | 안 만듦. 보류 세트 사례에는 "아직 만들지 않음"으로 적혀 있다 |
| 짝 G7~G19 (§4) | 안 만듦 |
| 입력 모듈 시험용 I01~I12 (§5) | I03·I04 일부만 (표현 변형 사례, 단위 테스트) |
| R11 동반질환 금기 | 안 만듦 |

옛 우선순위 (2026-10-23 §6.1 새 20건 순서, §6.2 예비 31건 이후)는 모두 만들었거나 §2.9로 옮겨서 뺐다.

---

## 7. 스키마·규칙에 필요한 것

`patient_state`에 담을 칸이 없는 값. 지금은 차트 문장으로만 쓰고 정답 JSON에는 들어 있지 않다. 스키마 작업에서 정한다.

| 값 | 쓰는 사례 | 지금 | 제안 |
|---|---|---|---|
| 항암 불가 판단 ("항암 치료 어렵다") | N28 | `contraindicated_classes`는 `confirmed_state`에만 | `patient`에 의사 판단 칸 (`visceral_crisis`와 같은 방식) |
| 내분비 적합 / 부적합 판단 | N32, N04·N16 | 없음 | 의사 판단 칸 |
| 뇌 전이 활동성·국소 치료 적응 | G20, VC-0111 | `imaging_findings`에 부위만 | 영상 판독의 활동성 + 의사 판단 |
| 소수 전이 | N34 | 없음 | 전이 부위 수로 계산할지, 의사 판단 칸으로 둘지 |
| 임신 | N35 | 없음 | `patient.pregnancy` |
| 이전 면역관문억제제 | N27 | `treatment_history[].drugs`로 가능 | 그대로. D 규칙이 선행·보조 pembrolizumab을 "이전 사용"으로 보는지 확인 |
| 골밀도 | N24 | 없음 (경과기록 문장만) | 보조 bisphosphonate 판정에 쓰면 칸 추가 |

---

## 8. 보류 세트로 쓰는 방법

- 보류 세트 18건 (기본 15 + 짝 3)은 입력 규칙·프롬프트를 고칠 때 틀린 칸을 보지 않는다. 성능 보고에만 쓴다
- 규칙을 고칠 때는 개발 세트(VC-0101~0109), 시험 세트(VC-0110~0129), 표현 변형 세트를 쓴다
- 채점: `python -m src.input.script.evaluation --gold --set holdout` (규칙만), LLM 출력은 `python -m src.input.script.evaluation <폴더>`. LLM 실행은 `python -m src.input.script.pipeline --set holdout --out <폴더>`
- 처음 잰 값 (2026-10-28, 규칙만): 필드 정확도 99.9%, 틀린 칸 1개 (VC-0143 보조 내분비 종료일). 같은 날 시험 VC-0122에서 나온 규칙(보조 내분비 투약 줄 종료일로 채움)으로 함께 고쳐져 지금은 100%
- 차트 문장은 같은 생성기 도구로 써서 시험 세트와 비슷하다. 표현 다양성은 제한점으로 남는다 (`notes/input_llm_principles_priorities_2026-10-23.md` §3-6, §4 표현 변형 사례)

---

## 9. 확인 필요

| 누가 | 무엇 | 관련 |
|---|---|---|
| D | **급여 행 단위 대조 전체** (§2.6 ⚑D 칸, §3 D 행. 이 PC에 D의 급여 청크 파일 없음). 특히 2-20 "1cm 초과"의 10 mm 경계, 4가-6 "이전 면역관문억제제"에 선행·보조가 드는지, `DEEM-ANTHRA-TAXANE` met이 4가 "1차"에 쓰이는지, 4나-18·4가-3 "이전 trastuzumab" 범위, carboplatin 재사용 | 전 사례, 특히 N21, N27, N28, G21 |
| D | 허가초과 인정 21건 목록 (N01 palbociclib + trastuzumab, N08 pembrolizumab + capecitabine 포함 여부) | N01, N08 |
| D | 간주 규칙을 4다·4마 차수에 쓰는 방식 | N04, N05, N06 |
| D | 9장 2-22~24 보조 pertuzumab와 선행 요법 연속의 구분 | N11 |
| D | 40장-20 대상에 ER-low가 드는지 | N15 |
| D | 4나-19 "심장 위험요소" 정의 | N18, G13 |
| D | "6개월 이후"·"1년 이후"의 경계일 계산 (달력 vs 일수) | N03, N06, G1, G2 |
| C | 그림 밖 권고(M06, M37, M26, E10, E11, E20)의 본문 쪽 | N03, N10, N15, N17, N18 |
| C | MBC 그림 4 "이전 ChT"에 보조 ChT가 드는지 | N04, N16 |
| C | ESMO 원문 기호(≥·≤) 9곳 (esmo_hira_crosswalk §1.4) | G7, N13, G1 |
| C | 그림 7 `f52123`·`e281ed` (`<cT2 N0` 갈래 뒤 pembrolizumab 상자)가 그림과 맞는지 | N26 |
| C | 전이성 ER-low를 ESMO MBC가 따로 다루는지 (조기는 E20) | N33 |
| C | 그림 5 Luminal A 갈래의 "high risk"와 "Stage III or high-risk stage II" 구분 | N23 |
| B | gBRCA를 생식세포 칸(`molecular.germline`)에서 먼저 읽고, 없으면 `mutations`의 BRCA를 쓰기 (2026-10-28 결정). 지금 코드는 `mutations`만 읽어 생식세포 양성이 `not_recorded`로 나온다 (`draft7_checklist_BCD_2026-10-28.md` §1.1) | VC-0104, N07, N10, N26, N31, G21 |
| B | ER-low 상한 (ESMO 1~9% vs evaluation_plan §6 1~10%) | N15 짝 |
| B | VUS, 생식세포/체세포 표기 형식 | N07 짝, I11 |
| B | cfDNA와 조직 결과가 다를 때 규칙 | I07 |
| B | 남성·범위 외 표시 방식 | N20, I12 |
| B | 생식세포 검사 기록이 없을 때 (미시행이 아니라 `not_recorded`) 검사 권고를 내는지 | N23 |
| A | 투약 중(`end_day` null)과 종료일 기록 없음 구분 (옛 AB_gap J-4, design §3 VC-0108) | VC-0108, G14, G17 |
| A | "검사 거부" 표기 (IN-6 표에 없음) | I09 |
| A | §7 칸 | N28, N32, N34, N35 |
