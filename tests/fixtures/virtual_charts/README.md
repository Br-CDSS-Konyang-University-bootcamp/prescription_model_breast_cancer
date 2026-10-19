# 가상 차트 시나리오 세트 (10건)

> 담당 A · 2026-10-19 · 기준 스키마: `schemas/patient_state.json` 0.1-draft6 (PR #6) · 공고책자 2026-10-01 · ESMO EBC 2024-02 / MBC 2026-05

TCGA로는 만들 수 없는 최신 치료(CDK4/6 억제제 이후 2차, 면역항암제, 보조 CDK4/6 등)의 지침·급여 경계 사례를 입력 모듈부터 추천까지(A → B → C/D → [4]) 끝까지 돌려 보기 위한 가상 환자다. 모두 가상 환자이고 실제 환자 정보는 없다.

**지금 상태: 차트 원문 초안까지 있다 (2026-10-19).** 사례마다 `scenario.md`(이야기, 시험 목적, 기대 결과 초안)와 `chart.txt`(`notes/report_templates.md` 틀로 작성한 초안)가 있고, 정답은 VC-0103의 `expected/patient_state.json`(A)만 있다 (2026-10-19). 나머지 정답은 이 형식을 따라 만든다.

## 1. 다른 데이터와의 관계

| | TCGA 정답 (874명) | 추출 세트 (30건 이상, 예정) | **이 폴더 (10건)** |
|---|---|---|---|
| 원천 | TCGA 표 + 규칙 (`src/input/truth/`) | TCGA 환자 + 그 환자로 쓴 차트 문장 | 완전 가상 |
| 정답을 정하는 것 | 원자료와 규칙 | 원자료와 규칙 | 각 담당자가 원문(지침·공고)을 보고 작성 |
| 시험하는 것 | B 판정 규칙, 차수 계산을 대량으로 | 입력 모듈이 문장을 정확히 읽는지 | 최신 치료의 지침·급여 경계 사례 |

## 2. 사례 목록

| ID | 상황 | 아형 | 범주·단계 | 핵심 시험 |
|---|---|---|---|---|
| [VC-0101](VC-0101/scenario.md) | 보조 AI 완료 3년 뒤 재발, 1차 CDK4/6 + AI 진행, cfDNA ESR1 변이 | HR+/HER2- (HER2-low) | 전이성, 내분비 2차 | ESR1 cfDNA, 재생검(IN-4), "이전 CDK4/6" 불충족, elacestrant 급여 없음 |
| [VC-0102](VC-0102/scenario.md) | VC-0101과 같은 경과, PIK3CA H1047R, ESR1 음성 | HR+/HER2- | 전이성, 내분비 2차 | 40장 병용(capivasertib·alpelisib 비급여) |
| [VC-0103](VC-0103/scenario.md) | 보조 anastrozole 복용 중 폐 전이 | HR+/HER2- | 전이성, 내분비 1차 | `DEEM-ENDO-ADJ-1Y` met → CDK4/6 + fulvestrant 급여, CDK4/6 + AI 불충족 |
| [VC-0104](VC-0104/scenario.md) | 보조 AC → paclitaxel 종료 8개월 뒤 간 전이, PD-L1 22C3 CPS 12 | TNBC | 전이성, 항암 1차 | PD-L1, pembrolizumab "6개월 이후 재발", 생식세포 BRCA 미시행 |
| [VC-0105](VC-0105/scenario.md) | 선행 TCHP 후 잔존 병변 | HR-/HER2+ | 조기 → 보조 | pCR no, RCB, ypTNM, 보조 T-DM1 |
| [VC-0106](VC-0106/scenario.md) | pT3(5.5cm) N1a(2개), 등급 2, 시점이 다른 Ki-67 두 값 | HR+/HER2- | 국소진행(IIIA), 보조 | abemaciclib 고위험(크기), 보조 CDK4/6 추가 약제 비급여, `history[]` |
| [VC-0106b](VC-0106b/scenario.md) | VC-0106과 같은 환자, 같은 보고서 안에 Ki-67 두 값 | HR+/HER2- | 국소진행(IIIA), 보조 | 같은 날 값 충돌 → `conflicts[]` (IN-5) |
| [VC-0107](VC-0107/scenario.md) | 38세 폐경 전, pT1c N0, 등급 3, 외부 병원 회송서 | HR+/HER2- | 조기, 보조 | AI + LHRH(40세 미만), 영문 회송서 |
| [VC-0108](VC-0108/scenario.md) | 70세, 진단 시 뼈 전이만, 1차 ribociclib + letrozole 복용 중 | HR+/HER2- | 전이성(de novo), 골 보호제 | `index_day`, "최근 4주 이내 투여", 투약 중 여부 한계 |
| [VC-0109](VC-0109/scenario.md) | 보조 tamoxifen 3년째 흉벽 국소 재발 → 완치 목적 절제 | HR+/HER2- | 조기, 재발 후 보조 | `recurrence_day`만 있음, `SET-LOCAL-ADJ` |

## 3. 폴더 구성

```
virtual_charts/
├── README.md                    이 파일
└── VC-0101/
    ├── scenario.md              이야기, 시험 목적, 기대 결과 초안, 정답 근거 출처   [A, 있음]
    ├── chart.txt                차트 원문 (문서 2~4개를 이어 붙인 텍스트 한 파일)     [A, 초안 있음]
    └── expected/                                                                   [작성 예정]
        ├── patient_state.json   A
        ├── biomarker_record.json B
        ├── guideline.json       C: 허용 권고 청크 ID·문장
        ├── reimbursement.json   D: 후보 약제별 급여 분류·공고 위치
        └── recommendation.json  B([4]): 허용 선택지, 안전 위반 목록
```

`guideline.json`, `reimbursement.json`, `recommendation.json`은 아직 스키마가 없다. 형식은 각 담당자가 정한다.

## 4. 차트 원문 작성 규칙

- **한 사례 = 텍스트 파일 하나.** EMR에서 복사한 것처럼 문서 2~4개를 이어 붙이고, 문서 경계는 머리글로만 표시한다 (`[병리결과보고서]`, `<외래 경과기록>`). 입력 모듈의 문서 분류(IN-1)를 시험하기 위해서다.
- **문서 종류**: 경과기록(SOAP, 문단형 요약, 다학제 회의록, 외부 병원 회송서) / 병리 / 분자병리·NGS / 투약 기록
- **표기는 섞어 쓴다**: `ER(+) 95%`, `ER positive (Allred 8)`, `에스트로겐 수용체 양성 90%` / 일반명·상품명·약어·오타 / 한글 문장 + 영문 의학 용어
- **날짜**: 사례마다 가짜 진단일을 하나 정하고 차트에는 실제 날짜 형식으로 쓴다 (`2021.3.5`, `21/03/05`, `2021년 3월`). 정답에는 날짜와 진단일 기준 일수(`*_day`, `index_day`)를 함께 넣는다. TCGA 기반 차트의 "날짜 없음" 규칙(`src/input/tcga_mapping.md` §2.3)은 이 폴더에 적용하지 않는다 (2026-10-16 A 결정)
- **식별정보**: 누가 봐도 가짜인 값만 쓴다. 이름 `김가상`, 등록번호 `0000` + 사례 번호, 전화 `010-0000-` + 사례 번호, 병원 `가상대학교병원`, 외부 병원 `가상의원`
- **합성 표시**: 전부 합성이므로 `scenario.md`에 사례 단위로 적는다. `patient_state`의 추출값 틀은 추가 키를 허용하지 않아 `"synthetic": true`를 넣을 수 없다

## 5. 정답 작성과 검수 (PROJECT.md §12)

| 단계 | 누가 | 할 일 |
|---|---|---|
| 1 | A | `scenario.md`, `chart.txt` |
| 2 | A | `expected/patient_state.json`. 스키마 검증, 차수·간주 규칙은 `src/input/common/lines.py` 재계산과 일치 |
| 3 | A가 아닌 1명 | 차트 원문만 보고 `patient_state`를 따로 작성 → 칸별 비교, 다르면 원문을 보고 합의·기록 |
| 4 | B | `biomarker_record.json` |
| 5 | C | `guideline.json` |
| 6 | D | `reimbursement.json` |
| 7 | B | `recommendation.json` (5·6을 합쳐) |

정답마다 출처(문서, 버전·공고일, 쪽·연번)를 적는다.

## 6. 만드는 순서

1. PR #6(draft6) 병합 뒤 시작한다.
2. **VC-0103을 먼저** A·B·C·D 정답까지 끝까지 만든다. 간주 규칙, 급여 조건 불충족, `covered`가 한 사례에 모두 있어 정답 형식을 한 번에 확정할 수 있다.
3. 형식이 정해지면 나머지 9건을 만든다.

## 7. 시험 범위

| 시험 대상 | 0101 | 0102 | 0103 | 0104 | 0105 | 0106 | 0106b | 0107 | 0108 | 0109 |
|---|---|---|---|---|---|---|---|---|---|---|
| 재발 병소 재생검 → `history[]` (IN-4) | ✓ | | | | | | | | | |
| 시점이 다른 값 → `history[]` | | | | | | ✓ | | | | |
| 같은 날 값 충돌 → `conflicts[]` (IN-5) | | | | | | | ✓ | | | |
| 외부 병원 회송서·영문 (IN-1·IN-2) | | | | | | | | ✓ | | |
| 등급, Ki-67, pCR·RCB, ypTNM | | | | | ✓ | ✓ | ✓ | ✓ | | |
| PD-L1 22C3 CPS | | | | ✓ | | | | | | |
| ESR1 cfDNA | ✓ | ✓ | | | | | | | | |
| PIK3CA 변이 | | ✓ | | | | | | | | |
| HER2-low (IHC 1+) | ✓ | | | ✓ | | | | ✓ | | |
| 미시행 → BM-4 검사 권고 | | | | ✓ | | | | | | |
| `recurrence_day` | 있음 | 있음 | 있음 | 있음 | 없음 | 없음 | 없음 | 없음 | 없음 (de novo) | 있음 (국소) |
| 차수 1 이상 | ✓ | ✓ | | | | | | | ✓ | |
| `DEEM-ANTHRA-TAXANE` met | ✓ | ✓ | | ✓ | | | | | | |
| `DEEM-SG-1Y` met | | | ✓ | ✓ | | | | | | |
| `DEEM-ENDO-ADJ-1Y` met | | | ✓ | | | | | | | |
| 간주 규칙 not_applicable | | | | | ✓ | ✓ | ✓ | ✓ | | ✓ |
| `SET-LOCAL-ADJ` | | | | | | | | | | ✓ |
| 급여 `covered` | ✓ | | ✓ | | ✓ | | | ✓ | ✓ | ✓ |
| 급여 `covered_conditions_unverified` | | | | ✓ | | | | | ✓ | |
| 급여 `no_criteria` (공고에 없음) | ✓ | | | | | | | | | |
| 급여 조건 불충족 | ✓ | | ✓ | | | | | | | |
| 추가 약제 비급여 (40장·보조요법 주2) | | ✓ | | | | ✓ | ✓ | | | |
| 보조 약제 (Ⅳ 기타 약제) | | | | | | | | | ✓ | |
| 안전: HER2 음성에 HER2 표적 금지 | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| 안전: ER·PR 음성에 내분비 단독 금지 | | | | ✓ | ✓ | | | | | |
| 안전: 진행한 약 재추천 금지 | ✓ | ✓ | ✓ | | | | | | | ✓ |

다음 묶음 후보: 남성 유방암·DCIS(범위 외), HER2-ultralow, ER low(1~9%), gBRCA VUS·PALB2, HER2+ 전이성 2차 이후(T-DXd·tucatinib), 뇌 전이, 폐경 전 전이성(ribociclib 예외).
