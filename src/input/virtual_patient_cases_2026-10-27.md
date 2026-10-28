# 가상 환자 사례 추가 (N21~N35 + 짝 G20·G21, 보류 세트)

작성: 2026-10-27, 차트 생성 2026-10-28. 담당 A. [virtual_patient_cases_2026-10-23.md](virtual_patient_cases_2026-10-23.md)(N01~N20)의 뒤를 잇는 사례 목록. 이 문서 §3이 `scenario.md`와 `tests/fixtures/virtual_charts/holdout_cases.csv`의 원본이다.

- 만드는 방법: `src/input/script/virtual/build_holdout_cases.py` → `python -m src.input.script.virtual.build_holdout_cases` (`--ids`, `--check`) → `tests/fixtures/virtual_charts/<VC-01xx>/` (`chart.txt`, `expected/patient_state.json`, `scenario.md`). 기대 결과를 고칠 때는 이 문서 §3을 고친 뒤 스크립트를 다시 돌린다
- 왜 새로 만드나
  - 기존 30건은 ESMO 알고리즘 경로 77개 중 25개만 덮는다 (fixture의 scenario·cases.csv에 경로 ID가 나오는 것 기준, 2026-10-27 집계)
  - 시험 세트(VC-0110~0129)는 입력 규칙 0~10단계를 고칠 때 이미 봤다 (`notes/input_test_errors_2026-10-26.md`). 처음 보는 사례로 재는 세트가 따로 필요하다
- 고른 기준
  - ① ESMO 권고와 심평원 급여가 갈리는 환자 (지침에는 있는데 급여가 안 되거나, 급여는 되는데 지침 1순위가 아님)
  - ② 아직 0건인 ESMO 경로
  - ③ 급여 조건의 경계값
  - ④ 안전 검사·범위 밖
- 근거
  - ESMO 경로: `data/chunks/esmo_algorithm_chunks.json` (ID 끝 6자리, 검수 상태는 `esmo_algorithm_review.csv`)
  - 급여 행: `notes/esmo_hira_crosswalk_2026-10-20.md` §2 (공고책자 2026-10-01). **이 PC에 D의 급여 청크가 없어 행 단위 조건은 ⚑D(D 확인 필요)**
- 2026-10-28 결정
  - DCIS 단독 사례는 뺐다 (모델 범위에 DCIS 없음). 번호는 N21~N35로 다시 매겼다
  - ER-low는 HR+로 본다 (B `ER_LOW_IS_HR_POSITIVE`, 2026-10-15). N33은 이 규칙이 B·C·D에서 같게 쓰이는지 확인하는 사례로 둔다
- 일수는 진단일 = 0. 기대 결과는 모두 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다

## 1. 지금 비어 있는 갈래

| 구분 | 덮지 않은 ESMO 경로 | 덮지 않은 급여 행·조건 |
|---|---|---|
| 조기 HER2+ | 그림 6 cT1 cN0 수술 먼저 3갈래 (`207157`·`f25e5f`·`549ca3`), 그림 2 `c9e462` | 2-20 trastuzumab "1cm 초과 또는 N+", weekly paclitaxel + H 행 없음 |
| 조기 HR+ | 그림 4 `08ac92` (폐경 전 Luminal A 1기), 그림 5 Luminal A 고위험 `21a119`, 그림 2 `74bcdc` (보조 bisphosphonate) | 2-7 tamoxifen, 2-2 나 연장 (AI 5년 뒤 AI 연장 행 없음), zoledronic acid 재발 예방 행 없음 |
| 조기 TNBC | 그림 7 `<cT2 N0` 갈래 `474a0a`·`a20657`, 그림 2 `ed4466` | TNBC 보조 olaparib 행 없음, 1나 AC→P "stage Ⅱ~Ⅲ" |
| 전이 HR+/HER2- | 그림 3 `0f09b4`·`8bf8f8`·`d5aff4`, 그림 4 `535699` | 3다 CDK4/6 바꿔 쓰기 불가, 전이성 olaparib·talazoparib 행 없음 |
| 전이 HER2+ | 그림 5 `eaa54b`·`a0919f`, 그림 6 `f13555`·`c58fb4`, 그림 7 4개 | 4나-18 trastuzumab + anastrozole, 4가-3 lapatinib + letrozole, 4라-19~21 |
| 전이 TNBC | 그림 9 `856d0a`·`0f049d` | 4가-6 "이전 면역관문억제제 사용 시 제외" |
| 그 밖 | 그림 10 `44ccc9` (소수 전이) | — |
| 범위 밖 | — | 임신 중 |

## 2. 사례 목록

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

fixture의 scenario·cases.csv에 경로 ID가 나오는 것으로 세면 25개에서 51개가 된다 (77개 중, 2026-10-28). 짝 사례 칸에만 적고 아직 만들지 않은 경로도 들어 있어, 실제 차트로 덮는 경로는 이보다 적다.

## 3. 사례 상세

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

## 4. 스키마·규칙에 필요한 것

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

## 5. 보류 세트로 쓰는 방법

- 이 18건 (기본 15 + 짝 3)은 입력 규칙·프롬프트를 고칠 때 틀린 칸을 보지 않는다. 성능 보고에만 쓴다
- 규칙을 고칠 때는 지금처럼 개발 세트(VC-0101~0109)와 시험 세트(VC-0110~0129)를 쓴다
- 채점: `python -m src.input.script.evaluation --gold --set holdout` (규칙만), LLM 출력은 `python -m src.input.script.evaluation <폴더>`
- 처음 잰 값 (2026-10-28, 규칙만 = 정답 구절을 넣은 경우): 필드 정확도 99.9%, 틀린 칸 1개. VC-0143 `recurrence.adjuvant_endocrine_end_date`: 정답 구절이 날짜만이고 그 줄에 뒤 날짜(전이일)가 더 있어, 5단계 규칙("날짜만 옮긴 구절은 그 줄의 마지막 날짜")이 받지 않는다. 보류 세트에서 나온 오류라 이 사례를 보고 규칙을 고치지 않고, 고칠 때는 개발·시험 세트에 같은 형태의 사례를 먼저 만든다
- 차트 문장은 같은 생성기 도구를 써서 기존 30건과 비슷하다. 표현 다양성은 제한점으로 남는다 (`notes/input_llm_principles_priorities_2026-10-23.md` §3-6)

## 6. 확인 필요

| 누가 | 무엇 | 관련 |
|---|---|---|
| D | ⚑D 행 전체. 특히 2-20 "1cm 초과"의 10 mm 경계, 4가-6 "이전 면역관문억제제"에 선행·보조가 드는지, `DEEM-ANTHRA-TAXANE` met이 4가 "1차"에 쓰이는지, 4나-18·4가-3 "이전 trastuzumab" 범위, carboplatin 재사용 | N21, N27, N28, G21 |
| C | 그림 7 `f52123`·`e281ed` (`<cT2 N0` 갈래 뒤 pembrolizumab 상자)가 그림과 맞는지 | N26 |
| C | 전이성 ER-low를 ESMO MBC가 따로 다루는지 (조기는 E20) | N33 |
| C | 그림 5 Luminal A 갈래의 "high risk"와 "Stage III or high-risk stage II" 구분 | N23 |
| B | 생식세포 검사 기록이 없을 때 (미시행이 아니라 `not_recorded`) 검사 권고를 내는지 | N23 |
| A | §4 칸 | N28, N32, N34, N35 |
