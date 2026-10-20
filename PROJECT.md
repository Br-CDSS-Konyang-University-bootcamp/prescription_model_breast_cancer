# 유방암 처방 모델 (prescription_model_breast_cancer) — 프로젝트 개요

> 최종 정리: 2026-10-16 (의료진 검토 대신 원문 기반 정답표로 평가 방식 변경, §12) · 기준 문서: 「유방암 CDSS 설계서 v0.1 — 입력·바이오마커·RAG 모듈」(2026-10-06, @선진)

## 1. 목표와 범위

v0.1은 환자 차트 원문을 받아 바이오마커 상태를 판정하고, ESMO 지침과 국내 급여 기준에서 근거를 검색해,
LLM이 처방 후보와 각 후보의 급여 분류를 함께 제시하는 데까지를 다룬다.

- 대상: 침윤성 유방암의 전신 약물치료 (조기의 선행·보조요법, 전이성의 차수별 치료)
- 범위 외: 용량 계산, DCIS, 엽상종양, 임신 중 유방암, 남성 유방암, 수술·방사선 결정. 범위 외로 표시하고 추천하지 않는다.
- v0.1 모듈: 입력 모듈, 바이오마커 모듈, RAG 지식베이스, LLM 추천 모듈, 급여 기준 자동 업데이트 모듈
- v0.2로 미룬 것: H&E 이미지 모듈(멀티모달 QC), Oncotype 대리 재발점수, 약물유전체(PGx) 경고
- 작업 순서: v0.1을 먼저 진행한다. 첫 작업은 슬라이드가 아닌 TCGA-BRCA 임상·변이 데이터를 탐색하는 코드다 (가상 차트 작성과 BM-2 테스트에 사용)

## 2. 원칙

- 바이오마커 상태값은 결정론적 규칙으로 판정한다. LLM은 이 값을 바꿀 수 없다.
- 급여 판정은 오늘 시행 중인 기준으로만 한다. 시행 전 공고와 공고예고는 판정에 쓰지 않는다.
- 모든 추천 문장과 급여 분류에 근거 청크 id(출처, 버전·공고일, 쪽 또는 섹션)를 인용한다. 인용 없는 문장은 삭제한다.
- 환자 차트에서 나온 텍스트는 비식별화를 거쳤더라도 외부 API로 보내지 않는다. 로컬 모델에서만 처리한다.
- "국내 허가가 있는가", "국내에서 권고되는가"는 판단하지 않는다.
- v0.1은 IRB 없이 쓸 수 있는 공개 자료와 직접 만든 가상 차트로 개발한다. 실제 환자 차트 검증은 IRB 승인 후 진행한다.
- 비영리 프로젝트다. ESMO 지침은 ESMO 웹사이트 약관의 비영리 사용 범위로 쓴다 (2026-10-07 결정). 원문은 원형대로 보관하고, 출처에 "Copyright © European Society for Medical Oncology. All rights reserved"와 원문 링크를 표시한다.
- 사용 승인(수동 심사)이 필요한 모델은 쓰지 않는다. 약관 동의나 공개 배포로 바로 받을 수 있는 모델만 허용한다.
- NCCN 지침은 쓰지 않는다 (EULA가 AI 입력을 금지).

## 3. 전체 구조

```
차트 원문 ──▶ [1] 입력 모듈 ──▶ [2] 바이오마커 모듈 ──┬──▶ [3] RAG 검색 ──▶ [4] LLM 추천 ──▶ 출력
(경과기록,     비식별화·추출·      상태값 판정(규칙)    │    (지침 + 급여)      (처방 후보 +
 병리, NGS,    정규화·정렬         검사 공백 탐지       └────────────────────▶   급여 분류)
 투약 기록)                                                  ▲
                         외부 지식: ESMO 지침 ────────────────┤
                                    심평원 급여 기준 ◀── [5] 급여 기준 자동 업데이트
```

바이오마커 상태값은 RAG 필터와 LLM 프롬프트 양쪽에 직접 들어간다.

## 4. [1] 입력 모듈

사용자가 차트 원문을 붙여넣으면 LLM 추출로 구조화한다. 모든 추출값에 원문 근거 위치를 붙인다.

| ID | 이름 | 하는 일 | 출력 |
|---|---|---|---|
| IN-0 | 비식별화기 | 이름, 등록번호, 주민번호, 연락처, 주소를 가린다. 검사일·투약일은 남긴다 | 마스킹된 원문, 원래 값 대응표(내부 보관, LLM에 넘기지 않음) |
| IN-1 | 문서 분류기 | 경과기록 / 병리 / 분자병리·NGS / 투약 기록으로 나눈다 | 문서 묶음 |
| IN-2 | 필드 추출기 (LLM) | JSON 스키마대로 값을 뽑는다 | 필드별 값, 원문 인용, 확신도 |
| IN-3 | 표기 정규화기 | 국문·영문 혼용 표기를 약어 사전으로 표준화 | 예: ER(+) 90% → ER 90% 양성 |
| IN-4 | 시간 정렬기 | 같은 항목이 여러 번 나오면 최신 값, 전이 병소 재생검 우선 | 정렬된 값 |
| IN-5 | 충돌 검사기 | 같은 시점에 값이 다르면 자동 선택하지 않는다 | 확인 요청 목록 |
| IN-6 | 누락 상태 판정기 | 필드마다 값 있음 / 미시행 / 기록 없음 | 필드 상태 |
| IN-7 | 유전자 보고서 전달기 | 분자병리·NGS 보고서를 해석하지 않고 넘긴다 | 바이오마커 모듈 입력 |

비식별화는 Microsoft Presidio에 한국어 패턴(주민번호, 등록번호, 전화번호)을 추가해 만든다.

추출 스키마:

| 그룹 | 필드 | 원문 예시 | 주 출처 |
|---|---|---|---|
| 진단 | 진단일, 조직형, 등급 | IDC, grade 3 | 병리 |
| 병기 | cTNM, pTNM, 병기군, 병기 범주(조기 / 국소 진행성 / 전이성), 전이 부위 | cT2N1M0 | 경과기록 |
| 수용체 | ER %, PR %, HER2 IHC, HER2 ISH | ER 90%, HER2 2+, SISH neg | 병리 |
| 증식 | Ki-67 % | Ki-67 30% | 병리 |
| 환자 | 나이, 폐경 여부, ECOG | postmenopausal, ECOG 1 | 경과기록 |
| 치료 이력 | 약제, 시작·종료일, 중단 사유, 최선 반응 | AI + palbociclib, PD | 투약 기록 |
| 선행요법 반응 | pCR 여부, RCB | ypT1aN0, RCB-I | 병리 |
| 재발 | 재발일, 보조 내분비요법 종료일 | — | 경과기록 |
| 유전자 검사 | 보고서 원문 전체 | — | 분자병리 |

미시행은 바이오마커 모듈에서 검사 권고로 이어지고, 기록 없음은 "기록 없음"으로만 남긴다.

## 5. [2] 바이오마커 모듈

검사 보고서 문장을 지침·급여 기준이 쓰는 짧은 상태값으로 바꾼다.
예: "HER2 (4B5) 2+, SISH not amplified" → HER2 저발현, "PIK3CA p.H1047R, VAF 31%" → PIK3CA 양성.

| ID | 이름 | 방식 | 예 |
|---|---|---|---|
| BM-1 | 보고서 정규화기 | LLM 파싱 (유일한 LLM 단계) | HER2 · IHC · 2+ / HER2 · ISH · 비증폭 · 1.3 |
| BM-2 | 상태 판정기 | 규칙 | HER2 IHC 2+, ISH 비증폭 → HER2 저발현 |
| BM-3 | 근거 주석기 | 로컬 조회 (허가사항 변이 목록, CIViC, ClinVar, VEP). OncoKB는 쓰지 않음 (2026-10-15 결정) | PIK3CA p.H1047R → 허가 동반진단 변이 (알펠리십 라벨) |
| BM-4 | 검사 공백 탐지기 | 규칙 | 전이성 HR+/HER2-, ESR1 미시행 → ESR1 검사 권고 |

상태값: 양성 / 음성 / 저발현 / 초저발현 / 0 / VUS / 불확정(판정 정보 부족) / 미시행 / 재검 필요(결과가 오래됨). 차트에 언급이 없으면 "기록 없음". 마커별로 쓰는 값은 아래 표를 따른다 (`schemas/biomarker_record.json`의 `status`).

판정 기준표 (BM-2):

| 바이오마커 | 판정 기준 | 상태값 | 주의 |
|---|---|---|---|
| HER2 | IHC 3+, IHC 2+/ISH 증폭, 또는 IHC 점수 없이 ISH 증폭 → 양성 · IHC 1+ 또는 2+/ISH 비증폭 → 저발현 · IHC 0이면서 10% 미만 세포에 미약한 막 염색(`faint: true`) → 초저발현 · IHC 0 → 음성 (아래 세부 규칙, 2026-10-15) | 양성 / 저발현 / 초저발현 / 음성 / unknown | 초저발현은 심평원 기준 최종 음성. IHC 2+인데 ISH가 없으면 unknown + ISH 검사 권고. `zero`는 쓰지 않음 |
| ER | <1% → 음성 · 1–10% → 저발현 · >10% → 양성. Allred 총점을 먼저 본다: 0–2 음성, 3–4 저발현, 5는 비율로 가름, 6–8 양성 (아래 세부 규칙) | 양성 / 저발현 / 음성 / 불확정 | ER 저발현은 `ER-low` 태그 |
| PR | Allred 총점 0~2 음성, 3 이상 양성 → 구간 최대값 ≥9% 양성 → 비율 ≥9% 양성 (아래 세부 규칙, 2026-10-15). 저발현 범주 없음 | 양성 / 음성 / unknown | `PR-low` 태그는 쓰지 않음 (ASCO·ESMO에 없는 범주, 2026-10-15) |
| Ki-67 | percent → range → result 순서. 20% 이상 → 고증식(positive) · 20% 미만 → negative · 구간이 20%에 걸치거나 적힌 판정이 intermediate → intermediate · 쓸 값 없음 → unknown (2026-10-15) | positive / negative / intermediate / unknown | 기준값 20%는 2026-10-15 확정. `Ki-67-high` 태그 |
| gBRCA1/2, PALB2 | ClinVar 병원성·병원성 가능이고 리뷰 등급 2성 이상 → 양성 (ACMG 4·5등급 대응) · 판정 상충 또는 1성 이하 → VUS | 양성 / 음성 / VUS | VUS는 음성 처리하되 표시 유지. TCGA 정답에서는 BRCA1/2 종양 엑솜 결과를 gBRCA 측정으로 가정 (A→B 문서 §4.7) |
| 체세포 BRCA | 종양 검사에서만 확인된 병원성 변이 | 양성 / 음성 | gBRCA와 별도 필드. 가상·실제 차트에서 생식세포 검사 언급이 없으면 gBRCA는 기록 없음 (체세포 결과로 대신하지 않음) |
| PIK3CA / AKT1 | ① FDA·식약처 허가 동반진단 변이 목록 → 양성 · ② 목록에 없고 CIViC 근거 있음 → 양성 + `off-label-variant` 태그 · ③ 그 외 → VUS | 양성 / 음성 / VUS | 패널에 해당 유전자가 없으면 미시행. 변이 목록은 허가사항 원문에서 옮기고 출처·쪽을 저장 |
| PTEN | VEP 절단형(nonsense, frameshift, 필수 스플라이스 부위) → 양성 (기능 소실) · 미스센스이고 ClinVar 병원성 또는 CIViC 근거 → 양성 · 그 외 → VUS | 양성 / 음성 / VUS | |
| ESR1 | 허가 동반진단의 리간드 결합 도메인 변이 (예: Y537S/N/C, D538G) | 양성 / 음성 / 재검 필요 | 마지막 내분비요법 진행 이전 결과면 재검 필요, cfDNA 우선 |
| PD-L1 (TNBC) | 약제별 기준: pembrolizumab은 22C3 CPS ≥ 10 (공고 p.58~59), atezolizumab은 SP142 IC ≥ 1% | 양성 / 음성 | 검사법이 기준과 다르면 해당 약제 판정에 쓰지 않음. 검사법과 점수를 함께 저장 |

BM-3 출처 (2026-10-15 결정, 상세는 `src/input/handoff_to_B.md` §5): OncoKB는 쓰지 않는다. 기관 이메일과 수동 심사가 필요하고, 학술 목적이라도 AI/ML 학습에 쓰는 것을 금지하기 때문이다. 대신 ① FDA 라벨(DailyMed)·동반진단 요약(SSED)·식약처 허가사항의 변이 목록, ② CIViC(CC0), ClinVar(생식세포), Ensembl VEP(PTEN 기능 소실)를 쓴다. 모두 파일로 받아 로컬에서 조회하므로 환자 변이가 외부 서버로 나가지 않는다. cBioPortal 화면의 변이 주석(Oncogenic, Level)은 OncoKB 데이터이므로 옮겨 적거나 정답으로 쓰지 않는다.

수치 기준은 ASCO/CAP 지침 원문(ER·PR 2020, HER2 2023, `data/guidelines/asco/`)과 대조해 확정한다. 팀 결정으로 원문과 다르게 둔 곳(PR 9% 기준 등)은 결정일과 이유를 남긴다. 의료진 검토는 하지 않는다 (2026-10-16 결정, 부트캠프 프로젝트라 의료진 상담이 불가능함).

### ER·PR·HER2 세부 판정 규칙 (2026-10-12 결정)

A가 넘기는 `patient_state`의 수용체 값(`schemas/patient_state.json` 0.1-draft3)을 기준으로 한 규칙이다. A의 정답 데이터와 가상 차트도 이 규칙으로 만든다. 바꿀 때는 A와 B가 함께 바꾼다. 상세 설명과 예시는 `src/input/handoff_to_B.md` §4.

**A가 넘기는 ER·PR 값의 형태:** `percent`(비율 %), `range`(비율 구간 `[최소, 최대]`), `allred`(`{total, ps, is}`. 강도 점수는 `is`, 별도 `score` 키 없음), `result`(적힌 판정) 중 차트에 있는 것을 모두 담은 객체.

**Allred 점수:** total = ps + is (0, 2~8). ps = 비율 점수 (0 없음, 1 <1%, 2 1~10%, 3 11~33%, 4 34~66%, 5 ≥67%), is = 강도 점수 (0~3).

ER (ASCO/CAP 2020: <1% 음성, 1~10% 저발현, >10% 양성). **Allred 총점을 먼저 본다** (2026-10-15 변경). 저발현은 Allred 3~4점, Allred 5점 중 비율이 1~10%, 또는 Allred 없이 비율이 1~10%일 때만 판정한다. 모든 값을 percent → range 순서로 보는 것이 아니다.

| 순서 | 있는 값 | 판정 |
|---|---|---|
| 1 | `allred.total` | 0~2 → 음성 · **3~4 → 저발현** · **5 → 비율로 저발현·양성을 가름** (아래 2). 비율 정보가 없으면 **unknown** + 비율 확인 권고 · 6~8 → 양성 |
| 2 | 비율: `percent`, `range`, `allred.ps` (Allred가 없거나 5점일 때) | <1% (`range` `[0,0]`, ps 0~1) → 음성 · **1~10% (`range` 최대 ≤10, ps 2) → 저발현** · >10% (`range` 최소 ≥10 또는 10%에 걸치는 구간, ps 3~5) → 양성. **0부터 시작하는 구간은 최대값을 percent로 보고 판정** (2026-10-15): `[0,1]` → 음성, `[0,9]`·`[0,10]` → 저발현, `[0,15]` → 양성 |
| 3 | `result`만 | 적힌 판정 (`low_positive` → 저발현) |
| 4 | 위 값이 하나도 없음 (`result`가 indeterminate인 경우 포함) | **unknown** |

0단계: 칸의 `status`만 본다 (`not_done` → 미시행, 칸 없음·`not_recorded` → 기록 없음). Allred 총점은 ps(비율 점수) + is(강도 점수)이고 percent·range·ps는 비율만 잰 값이라, 총점이 있으면 총점을 따른다 (총점과 비율이 달라도 총점). ER·PR에는 `score` 키가 없다 (강도는 `allred.is`, 2026-10-15). 재발 환자는 `value`(가장 최근 재생검 결과)로 판정하고 원발 결과(`history[]`)는 설명에만 쓴다. **ER에는 `indeterminate`를 쓰지 않는다** (2026-10-15 결정).

예: Allred 총점 5점은 비율이 1~10%(ps 2 + is 3)면 **저발현**, 11% 이상(ps 3 + is 2, ps 4 + is 1)이면 **양성**이다. 비율이 적혀 있지 않으면 unknown이다. Allred 3~4점은 비율과 상관없이 저발현으로 판정한다 (3~4점에는 비율상 <1%나 11~33%인 조합도 있지만 팀 결정으로 단순화). Allred 6~8점은 비율 점수가 3 이상일 수밖에 없어 항상 양성이다. TCGA 정답에는 Allred가 없어 `range`와 `result`로 판정한다.

PR (**팀 결정 2026-10-15**. 저발현 범주 없음. 비율 기준을 9%로 둔다: ASCO/CAP 2020의 1% 기준과 다르다. TCGA 정답의 PR `[1,9]` 49명은 최대값 9라 양성).

| 순서 | 있는 값 | 판정 |
|---|---|---|
| 1 | `allred.total` (있을 때만) | 0~2 → 음성 · 3 이상 → 양성 |
| 2 | `range` `[x, y]` | `[0,0]` → 음성 · 최대값 y ≥ 9 → 양성 · 그 밖(y < 9) → 음성 |
| 3 | `percent` | ≥ 9 → 양성 · < 9 → 음성 |
| 4 | `allred.ps` | 0~1 → 음성 · 2~5 → 양성 |
| 5 | `result`만 | `positive`·`negative`는 그대로 · `low_positive` → 양성 |
| 6 | 쓸 값이 없음 (`result`가 indeterminate인 경우 포함) | **unknown** |

처음 맞는 값으로 판정한다. 수치로 정한 판정과 적힌 `result`가 다르면 수치를 따르고 `reason`에 확인 필요를 적는다. **PR에는 `indeterminate`를 쓰지 않는다.**

**PR-low 태그: 쓰지 않는다** (2026-10-15 결정). ASCO·ESMO 지침에 PR-low 범주가 없어 RAG 태그로도 쓸 곳이 없다.

ER·PR 공통: 수치로 정한 판정과 적힌 `result`가 다르면 수치를 따르고, `reason`에 둘 다 적어 확인이 필요하다고 표시한다.

HER2 (**팀 결정 2026-10-15**. A가 `result`를 ISH로 보정해서 넘기므로 **`score`를 먼저 읽는다**):

| 단계 | `her2_ihc.score` | `her2_ish` (FISH·SISH) | 판정 |
|---|---|---|---|
| 1 | 3+ | 상관없음 | `positive` (무조건) |
| 2 | 2+ | 증폭 | `positive` |
| 2 | 2+ | 비증폭 | `low` |
| 2 | 2+ | 미시행·기록 없음 + 적힌 판정 positive | `positive` + ISH 검사 권고 |
| 2 | 2+ | 미시행·기록 없음 + 적힌 판정 negative | `negative` |
| 2 | 2+ | equivocal, 또는 ISH 없이 적힌 판정이 그 외 | `unknown` (판정 불가). TCGA 정답에서는 삭제 |
| 3 | 1+ | 상관없음 | `low` |
| 4 | 0 + 10% 미만 세포의 미약한 막 염색 (`faint: true`) | 증폭 외 | `ultralow` (심평원 기준 최종 음성, 아형은 HER2-) |
| 4 | 0 (`faint` 없음·false) | 증폭 외 | `negative` |
| 4 | 0 | 증폭 | `unknown` + 원자료 확인 (데이터 오류로 봄, TCGA 0명) |
| 5 | 없음 | 증폭 | `positive` |
| 5 | 없음 | `result`만 positive | `positive` |
| 5 | 없음 | `result`만 negative | `negative` (0과 저발현은 구분 못 함) |
| 5 | 없음 | 비증폭 | `negative` (0과 저발현은 구분 못 함) |
| 5 | 없음 | `result`만 equivocal·indeterminate·unknown | `unknown`. TCGA 정답에서는 삭제 |
| 5 | IHC 미시행 | ISH 없음 | `not_done`. TCGA 정답에서는 삭제 |
| 5 | 없음 | 없음 | `not_recorded`. TCGA 정답에서는 삭제 |

`zero`와 `indeterminate`는 쓰지 않는다. `HER2-low`·`HER2-ultralow` 태그도 쓰지 않고 상태값 `low`·`ultralow`로만 표시한다. 재생검(전이 병소) 결과가 있으면 그 점수로 같은 규칙을 적용하고, 없으면 기존 점수를 쓴다. `evidence`에 IHC 점수·ISH 결과를 따로 남기지 않는다.

아형 (ER·PR·HER2 판정 결과로 정한다, 2026-10-15):

| HR | HER2 | 아형 |
|---|---|---|
| HR+ (ER positive·low 또는 PR positive) | HER2- (low·ultralow·negative) | `HR+/HER2-` |
| HR+ | HER2+ (positive) | `HR+/HER2+` |
| HR- (ER negative이고 PR negative) | HER2+ | `HR-/HER2+` |
| HR- | HER2- | `TNBC` |
| 위로 정할 수 없음 (ER·PR·HER2 중 unknown·미시행·기록 없음) | | `unknown` (`indeterminate`는 쓰지 않음) |

ER 음성·PR 양성도 HR+로 본다 (2026-10-15 결정). ER low를 HR+로 볼지는 확인 중이다 (지금은 HR+, `BM1_ER,PR,HER2,Ki_67,subtype.py`의 `ER_LOW_IS_HR_POSITIVE`).

분자 아형 (2026-10-15 결정. 쓸 곳이 정해지지 않아 규칙만 정해 두고 `biomarker_record` 출력에는 아직 넣지 않는다. `BM1_ER,PR,HER2,Ki_67,subtype.py`의 `molecular_subtype_of`):

| 분자 아형 | 아형 | Ki-67 |
|---|---|---|
| `Luminal A` | HR+/HER2- | low (negative) |
| `Luminal B(HER2 negative)` | HR+/HER2- | high (positive). intermediate도 high로 본다 |
| `Luminal B(HER2 positive)` | HR+/HER2+ | 관계없음 |
| `HER2_enriched` | HR-/HER2+ | 관계없음 |
| `Basal_like` | HR-/HER2- (TNBC) | 관계없음 |
| `unknown` | 아형 unknown, 또는 HR+/HER2-인데 Ki-67이 unknown·미시행·기록 없음 | |

TCGA 정답은 Ki-67이 모두 기록 없음이라 HR+/HER2-는 분자 아형이 `unknown`이 된다.

검사 공백 규칙 (BM-4):

- HER2 음성 전이성 → gBRCA1/2, PALB2 미시행이면 권고
- HR+/HER2- 전이성 → PIK3CA·AKT1·PTEN 미시행이면 권고, 내분비요법 진행 시점마다 ESR1 재검 권고
- 전이성 TNBC → PD-L1 미시행이면 권고
- 전이성 전체 → HER2를 0/저발현/초저발현까지 재판정했는지 확인

출력 레코드:

```json
{
  "marker": "ESR1",
  "status": "재검 필요",
  "reason": "2025-11 검사, 이후 2026-06 내분비요법 진행",
  "evidence": {"variant": null, "specimen": "cfDNA"},
  "source_span": "분자병리 보고서, 3행",
  "rag_tags": ["HR+/HER2-", "metastatic"]
}
```

## 6. [3] RAG 지식베이스

지침은 권고문 단위로 청킹하고, 환자의 구조화된 상태로 만든 질의에 메타데이터 필터를 걸어 검색한다. 차트 원문을 질의로 쓰지 않는다.

수집 대상 (원문 PDF와 발행일을 함께 보관):

- ESMO 조기 유방암 지침(2024)과 이후 eUpdate
- ESMO 전이성 유방암 지침(2026-05 개정)
- ~~ASCO 유방암 지침 전체와 Rapid Recommendation Update~~ 재사용 불가로 확인돼 제외 (2026-10-20)
- 심평원 항암화학요법 등 공고내용 전문(공고책자), 이후 개정 공고, 허가초과 항암요법 목록. 약제·요법 하나의 투여 대상 조건을 한 청크로 만들고 시행일을 저장한다.

전처리와 청킹:

- 권고문 청크: 권고 문장 + 근거 수준(LoE/GoR), ESMO-MCBS, ESCAT. 약 300–800 토큰
- 부모-자식 구조: 검색은 권고문 청크로, LLM에는 소단원 전체를 함께 넘긴다
- 치료 알고리즘 그림: 노드-엣지 텍스트("조건 → 권고")로 변환한 별도 청크. 자동 변환 후 사람이 검수한다
- 표: 행 단위로 문장화하고 원 표 제목을 각 청크에 붙인다

메타데이터:

| 필드 | 예시 | 용도 |
|---|---|---|
| source, version, section | ESMO MBC, 2026-05, ER+/HER2- 2차 | 출처 표시, 감사 |
| setting | early / metastatic | 하드 필터 |
| subtype | HR+/HER2-, HER2+, TNBC | 하드 필터 |
| line | neoadjuvant, adjuvant, 1L, 2L, ≥3L | 하드 필터 |
| biomarker_tags | ESR1-mut, gBRCA, HER2-low | 가중치 |
| drugs | elacestrant, capivasertib | 키워드 검색 |
| evidence | LoE I, GoR A, ESCAT I-A | 정렬 |
| superseded_by | 후속 업데이트 청크 id | 구버전 제외 |
| doc_type | guideline / reimbursement | 지침과 급여 기준 분리 검색 |

검색:

- 임베딩 bge-m3 (한국어 질의 ↔ 영문 문서) + BM25 하이브리드 검색 (약제명·유전자명 정확 일치)
- setting, subtype, line으로 거른 뒤 biomarker_tags로 가중치, 교차 인코더(bge-reranker-v2-m3)로 재정렬
- 질의 예: "HR+/HER2- metastatic, 2nd line, prior CDK4/6 inhibitor, ESR1 mutated"
- ESMO와 ASCO가 다르면 출처별로 나란히 제시하고 합치지 않는다 (ASCO는 2026-10-20 제외. 지금은 ESMO만)
- 개정 시 재색인하고, 대체된 청크는 지우지 않고 superseded_by로 표시해 과거 추천을 재현할 수 있게 한다
- 처방 후보가 정해지면 후보 약제명과 환자 상태로 급여 기준 청크(doc_type = reimbursement)를 한 번 더 검색한다

## 7. [4] LLM 추천 모듈

LLM은 검색된 지침·급여 기준 청크 안에서만 처방 후보와 급여 분류를 제시한다. 로컬 모델에서 실행한다.

프롬프트 입력: 구조화된 환자 상태(비식별화), 바이오마커 상태값과 판정 이유, 검사 공백 목록, 지침 청크와 부모 소단원(출처·버전·근거 수준), 후보 약제별 급여 기준 청크와 공고일.

출력 형식:

```json
{
  "options": [{
    "therapy": "...",
    "rationale": "...",
    "evidence": "LoE I, GoR A",
    "citations": ["guideline_chunk_id"],
    "reimbursement": "급여 | 급여(조건 확인 필요) | 허가초과 인정 | 급여 기준 없음",
    "reimbursement_reason": "충족한 조건 또는 빠진 조건",
    "reimbursement_citations": ["reimbursement_chunk_id"]
  }],
  "tests_needed": [{"test": "ESR1 (cfDNA)", "reason": "..."}],
  "out_of_scope": false,
  "conflicts": ["ESMO와 ASCO 권고 차수가 다름"]
}
```

환각 방지:

- 인용 없는 추천 문장은 후처리에서 삭제하고, 인용된 청크에 약제명이 실제로 있는지 문자열로 재확인한다
- 바이오마커가 불확정·미시행이면 그 바이오마커가 필요한 치료는 추천 대신 검사 권고로 낸다
- "급여"는 급여 기준 청크가 인용되고 조건(치료 차수, 이전 약제, ECOG 등)이 모두 확인될 때만 쓴다. 조건이 기록 없음이면 "급여 (조건 확인 필요)"
- 허가초과 인정·급여 기준 없음 후보도 지우지 않고 표시한다
- 검색 결과가 비거나 범위 외 상황이면 추천을 만들지 않고 그대로 알린다

급여 분류:

| 분류 | 근거 | 화면 표시 |
|---|---|---|
| 급여 | 공고책자 + 시행 중인 개정 공고의 조건과 일치 | 급여 (조건 충족) |
| 허가초과 인정 | 허가초과 인정요법 목록의 유방암 항목과 일치 | 허가초과 인정 · 약값 본인부담 100/100 또는 5/100 · 다학제적위원회 협의 필요 |
| 급여 기준 없음 | 위 둘 다 해당 없음 | 급여 기준 없음 (비급여 가능성, 확인 필요) |

"급여 기준 없음"을 "비급여"로 단정하지 않는다. 허가 내 비급여인지, 허가 자체가 없는지 우리 데이터로 구분할 수 없다.

## 8. [5] 급여 기준 자동 업데이트 모듈

공고책자 PDF를 기준선으로 쓰고, 파일명 날짜 이후의 개정 공고를 시행일부터 덧씌운다.

| 출처 | 내용 | 비교 날짜 | 역할 |
|---|---|---|---|
| 항암화학요법 게시판 — 공고내용 전문 | 현재 유효한 전체 공고 책자 PDF | 파일명 날짜 (공고책자_20261001.pdf → 2026-10-01) | 기준선 |
| 같은 게시판 — 허가초과 항암요법 | 승인된 허가초과 요법 목록 | 파일명 날짜·해시 | 허가초과 인정 매칭 |
| 공고 게시판 | 확정된 개정 공고 (월 1회 안팎) | 제·개정일(시행일) | 미반영 개정 덧씌우기 |
| 공고예고 게시판 | 의견조회 중인 개정안 | 공고예고기간 | 개정 예정 안내만 |

2026-10-07 확인: 최신 공고 제2026-210호의 제·개정일이 2026.10.1.로 책자 파일명 날짜와 같다. 책자 날짜 = "반영된 마지막 공고의 시행일" 가정은 몇 달간 대조해 확정한다.

날짜 비교 규칙 (B = 현재 반영된 공고책자의 파일명 날짜):

1. 새 책자: 파일명 날짜 > B → 기준선 재생성, B 갱신, B 이하의 덧씌운 공고 삭제
2. 공고: 작성일이 아니라 제·개정일(시행일)로 비교한다. ≤ B면 건너뛰고, > B면 저장한다
3. 시행일 ≤ 오늘이면 판정에 반영하고, > 오늘이면 "예정"으로 두었다가 시행일에 자동 반영한다
4. 공고예고: 판정에 쓰지 않는다. 예고기간 중이면 "진행중", 기간이 끝났는데 공고가 없으면 "예정". 대응 공고가 올라오면 3번 규칙을 따른다
5. 날짜 표기(2026.10.1. / 2026-06-29)를 비교 전에 통일한다

예정·진행중 안내는 해당 약제 후보 옆에 회색 작은 태그로만 표시한다. 태그를 누르면 공고·예고의 제목, 날짜, 원문 링크만 보여준다.
화면 아래에 "현재 반영: 공고책자 2026-10-01 + 제2026-○○호 / 예정 1건 / 진행중 1건" 한 줄 요약을 둔다.

처리 흐름:

1. 앱 시작 시 백그라운드로 실행한다. 앱은 마지막 정상 색인으로 바로 동작한다
2. 항암화학요법 게시판의 두 첨부 파일명으로 책자 날짜와 허가초과 목록 변경을 확인한다
3. 공고·공고예고 게시판은 1페이지만 읽는다. 전체 수집(백필)은 처음 한 번만 한다
4. 새로 반영할 문서만 내려받는다
5. PDF를 텍스트·표로 변환하고 유방암 관련 약제·요법만 남긴다
6. Claude API로 조건 단위 JSON(약제, 요법, 투여 단계, 조건, 시행일, 공고번호, 출처 쪽수)을 만든다
7. 스키마 검사와 약제명 사전 대조를 통과한 것만 반영하고, 신설·변경·삭제 목록을 만든다
8. 청크마다 source_type(baseline / overlay / preview), effective_from, superseded_by를 붙여 색인한다. 검색은 오늘 기준 유효한 baseline·overlay만 쓴다
9. 실패하면 마지막 정상 버전을 유지하고 현재 버전과 경고를 화면에 보여준다

레지스트리 (SQLite):

| 필드 | 예시 |
|---|---|
| source | booklet / offlabel / notice / preview |
| doc_no | 제2026-210호 |
| board_id | brdBltNo=45661 |
| effective_date | 2026-10-01 |
| posted_date | 2026-09-30 |
| file_name, file_hash | 공고책자_20261001.pdf, sha256 |
| status | downloaded / parsed / indexed / failed / superseded |

구현 주의:

- 게시판 다운로드 버튼이 자바스크립트로 동작한다. 네트워크 탭에서 실제 요청을 재현하고, 안 되면 Playwright로 받는다
- 공고 첨부 형식(PDF·HWP)을 먼저 확인한다. HWP면 변환 도구가 필요하다
- 사이트 이용약관을 확인하고, 요청은 앱 시작당 몇 건으로 제한한다
- 공고 문서에 "무단 복사·복제 금지" 문구가 있으므로 원본과 가공물을 외부에 공개하지 않는다

심평원 유방암 섹션 구성 (이전 검토, 공고 제2025-210호 p.47~61 기준):

1. 선행화학요법: HER2 양성 / HER2 음성
2. 수술후보조요법: 내분비요법(호르몬 수용체, 폐경 여부) / 항암·표적치료(림프절 양성, 종양 크기 >1·>2·≥5cm, HER2, abemaciclib: 양성 림프절 4개 이상 또는 1–3개 + 크기 ≥5cm 또는 등급 3)
3. 고식적 내분비요법: 1차 / 1차 이상 / 2차 이상
4. 고식적 항암화학요법: 1차 / 1차 이상 / 2차 / 2차 이상 / 3차 이상

허가초과 항암요법 파일 (허가초과 항암요법_260827 기준):

| 시트 | 내용 | 우리 모델에서 |
|---|---|---|
| 인정되고 있는 허가초과 항암요법 | 요법코드, 암종, 항암화학요법, 투여대상, 투여단계, 투여요법, 급여상세사항(본인부담률), 용법용량 | 매칭에 사용, 용법용량 열은 쓰지 않음 |
| 변경대비표 | 추가·변경·삭제 이력과 적용일자 | 업데이트 시 바뀐 항목 확인 |
| 불승인 요법 | 불승인 요법과 사유 | 쓰지 않음 (참고용) |
| 검토중인 허가초과 항암요법 | 심의 대기 목록 | "진행중" 안내에만 사용 가능 |

- 인정 요법 726건 중 유방암 21건(남성 유방암 2건 포함), 불승인 681건 중 41건이다. 대부분 허가되지 않은 대상·치료 단계에 쓰는 요법이다
- 예: 체세포 BRCA 변이 HER2 음성 전이성의 올라파립(2차 이상), 선행요법 후 pCR 미달성 TNBC의 펨브롤리주맙 + 카페시타빈(보조), HR+/HER2+ 전이성 1차의 팔보시클립 + 트라스투주맙 ± 퍼투주맙 + 내분비요법, 아로마타제 억제제 5년 후 연장요법
- 결정: v0.1에 포함한다. 21건을 (암종, 약제 조합, 투여대상, 투여단계, 본인부담률)로 저장하고, 추천 후보가 일치하면 "허가초과 인정"으로 분류한다. 파일명 날짜(260827 → 2026-08-27)로 갱신을 판단한다

## 9. 모델·도구 선택

1차 조합: Docling(파싱) + bge-m3(임베딩) + bge-reranker-v2-m3(재정렬) + Qdrant(하이브리드 검색) + LlamaIndex(RAG) + Claude API(공고·지침) + 로컬 모델(환자 차트) + RAGAS(평가). 버전과 라이선스는 도입 시점에 다시 확인한다.

LLM 분리 (결정): 데이터 민감도로 나눈다.

| 작업 | 환자 정보 | 모델 |
|---|---|---|
| 공고책자·개정 공고 구조화, 지침 청크 정리, 평가용 질의 생성 | 없음 | Claude API (claude-sonnet-5-5) |
| IN-2 필드 추출, BM-1 보고서 파싱, LLM 추천 모듈 | 있음 | 로컬 모델 |

- 로컬 모델 후보: Qwen 계열, EXAONE, snuh/hari-q3-8b. 같은 가상 차트 테스트 세트로 추출 정확도와 인용 준수율을 비교해 고른다
- 실행 환경: 개발은 Ollama, 운영은 vLLM. 구조화 출력은 vLLM guided decoding, Outlines, Instructor 중 선택
- 모든 LLM 호출은 공통 인터페이스로 감싸 설정만 바꿔 모델을 교체할 수 있게 한다

임베딩 (결정): BAAI/bge-m3 (MIT, 8,192 토큰, 의미 검색과 키워드 가중치를 한 모델에서 출력).

| 탈락 후보 | 이유 |
|---|---|
| KM-BERT | 검색용 임베딩으로 학습되지 않았고 입력 512 토큰 |
| KURE-v1, BGE-m3-ko | 임상 특화가 아니며 영문 지침 검색 성능 미확인 |
| comsat-embed-ko-8b-preview | 80억 파라미터라 운영 부담이 크고 프리뷰 버전 |
| ClinicalEncoder26AM | 공개·라이선스 미확인 |

recall@5가 부족하면 공고·지침에서 만든 (질의, 정답 청크) 쌍으로 bge-m3를 추가 학습한다 (선택 과제).

다른 후보:

| 계층 | 후보 |
|---|---|
| 문서 파싱 | Marker, Unstructured, PyMuPDF |
| 키워드 검색 | OpenSearch, Elasticsearch, rank_bm25 |
| 벡터 DB | Milvus, Chroma, pgvector |
| RAG 프레임워크 | LangChain·LangGraph, Haystack |
| 평가 | DeepEval |

유전체 도구: GDC Data Portal·gdc-client, cBioPortal API, TCGAbiolinks(R), Ensembl VEP, vcf2maf, CIViC nightly TSV, ClinVar FTP(`variant_summary`, VCF), PharmCAT(PGx, v0.2).

## 10. 필요 데이터셋

v0.1:

| 데이터셋 | 쓰는 모듈 | 접근 | 주의 |
|---|---|---|---|
| ESMO 조기·전이성 유방암 지침 | RAG | 무료 공개 | 상업적 재사용 조건 확인 |
| ~~ASCO 유방암 지침, Rapid Update~~ | 쓰지 않음 | 재사용 불가 (2026-10-20 확인) | 코드·청크 삭제 |
| 심평원 암질환 사용약제 및 요법 공고 | RAG (급여) | 공개 | 수시 개정, 공고일·시행일 관리 |
| 식약처 의약품 허가사항 | LLM 추천 | 공개 | 적응증 추가 시 갱신 |
| 가상 환자 차트 | 입력 모듈, 전체 테스트 | 직접 작성 | 작성자가 아닌 팀원이 TCGA 정답과 대조해 교차 검토 |
| TCGA-BRCA 임상 | 가상 차트 작성, BM-2 테스트 | GDC·cBioPortal | HER2 점수·Ki-67 결측 많음 |
| TCGA-BRCA 체세포 변이·복제수 | BM-1 ~ BM-3 테스트 | GDC·cBioPortal | 원발 종양 위주 |
| FDA 라벨(DailyMed)·SSED, 식약처 허가사항 | BM-3 (허가 동반진단 변이 목록) | 공개 | 원문에서 변이를 옮기고 문서·버전·쪽 저장 |
| CIViC | BM-3 (허가 목록 밖 체세포 변이) | CC0, nightly TSV | 받은 날짜를 파일명에 넣음. 인용: Griffith M et al., Nat Genet 2017 |
| ClinVar | BM-3 (생식세포, PTEN 미스센스) | 공개, FTP 다운로드 | 판정이 엇갈리는 변이 존재. 100MB가 넘어 커밋하지 않고 스크립트만 올림 |

v0.2:

| 데이터셋 | 쓰는 모듈 | 주의 |
|---|---|---|
| TCGA-BRCA H&E 진단 슬라이드 | H&E → IHC 예측 | 기관별 염색 차이, 기관 단위 분할. 바코드 샘플 코드 `01`(원발) + 슬라이드 `DX`(FFPE)만 사용 |
| TCGA-BRCA RNA-seq | 대리 재발점수, RNA-IHC 비교 | RT-PCR 기준과 척도 보정 필요 |
| TCGA-CDR | 재발점수 검증 | 추적 기간이 짧은 환자 많음 |
| METABRIC | 재발점수 외부 검증 | 마이크로어레이 기반 |
| HEROHE, BCI | H&E → HER2 보조 | 라이선스·라벨 형식 확인 |
| 1000 Genomes | PGx 테스트 | 한국인 샘플 없음 |
| gnomAD, KRGDB | PGx 빈도 확인 | KRGDB는 조회 중심 |
| PharmVar, CPIC | PGx 판정·권고 | 지침 개정 추적 |

데이터는 `data/`에 둔다. `data/` 안에서는 csv·txt·py 파일만 git에 올리고 나머지 형식은 제외한다 (§15.2).

## 11. v0.2 미리보기 — H&E 이미지 모듈

H&E에서 ER/PR/HER2를 예측해 차트 값과의 불일치를 표시하는 QC 보조 모듈이다. v0.1을 먼저 진행하고, 이 모듈은 그 뒤에 시작한다.

특징 추출 모델 (2026-10-07 Hugging Face에서 확인):

| 모델 | 라이선스 | 받는 조건 | 크기 | 비고 |
|---|---|---|---|---|
| H-optimus-0 (Bioptimus) | Apache 2.0 (상업 이용 가능) | 로그인 후 연락처 공유 동의, 자동 승인 | 11억 파라미터, 특징 1,536차원 | 유방암 재발 위험(ROR-P) 벤치마크에서 연속 점수와의 상관이 최상위권. GPU 필요 |
| Hibou-B (HistAI) | Apache 2.0 | 로그인 후 연락처 공유 동의, 자동 승인 | 약 8,600만 파라미터 | 가벼워서 GPU가 약해도 돌릴 수 있음 |
| Phikon-v2 (Owkin) | Owkin 비상업 라이선스 | 게이트 없음, 바로 다운로드 | 약 3억 파라미터, 특징 1,024차원 | 학술 프로젝트에 사용 가능 |
| CHIEF (하버드 HMS) | GPLv3, 비상업 학술용 | Docker Hub 이미지는 요청 없이 받음. Google Drive 가중치는 접근 요청 필요 | 경량 | TCGA-BRCA ER 0.877 · PR 0.791 · HER2 0.706 (AUROC, Cancers 2026) |

결정:

- 1순위 H-optimus-0. 라이선스가 가장 자유롭고, 재발점수 QC 방향과 맞는다
- GPU가 약하거나 없으면 Hibou-B로 시작한다. 비교군은 Phikon-v2, CHIEF
- 대규모 벤치마크(19개 모델)의 바이오마커 예측 성능은 CONCH·Virchow2보다 한 단계 아래다. "쓸 수 있는 모델 중 좋은 모델"로 본다
- HER2는 QC 보조로만 쓴다. 공개 모델의 HER2 AUROC가 0.7대이므로 검증 세트로 임계값을 보정하고 불일치 플래그에만 쓴다
- 평가지표: AUROC, AUPRC(유병률 기준선 비교), 보정 임계값의 민감도·특이도·PPV, ECE. 공개 수치는 무작위 분할이라 낙관적일 수 있어 기관 단위 분할로 다시 잰다

슬라이드 준비:

이 모델들은 TCGA 특징 파일이 공개돼 있지 않아 슬라이드를 직접 받아 특징을 뽑는다.

1. GDC API로 TCGA-BRCA 진단 슬라이드 목록을 받고, 파일명의 환자 ID(submitter_id)로 임상 라벨과 매칭한다 (2026-10-07 조회 결과는 `data/metadata/`에 있음. 조회 스크립트는 v0.2 시작 시 다시 작성)
2. 라벨 있는 환자만, 샘플 코드 `01`(원발), 환자당 1장만 고른다. 2026-10-07 조회 결과 1,133장(약 1.16TB), 환자 1,062명, 샘플 코드 `06` 1장 포함
3. 처음에는 100~200장으로 파이프라인을 검증한다
4. 한 장 받기 → 특징 추출 → 원본 삭제를 반복해 디스크 사용량을 줄인다
5. 특징 추출은 Mahmood Lab의 공개 코드 Trident 또는 CLAM을 쓰고, 추출 모델만 H-optimus-0로 바꾼다. 슬라이드 단위 학습은 ABMIL

쓰지 않는 모델 (수동 승인 필요):

| 모델 | 이유 |
|---|---|
| TITAN (Mahmood Lab) | Hugging Face 게이트 저장소, 수동 심사. 기관 이메일 필수이고 개인 이메일은 거절. 미리 추출한 TCGA 특징 파일도 같은 저장소라 승인 없이 받을 수 없음. CC BY-NC-ND 4.0 |
| UNI, UNI2-h, CONCH (Mahmood Lab) | TITAN과 같은 승인 절차 |
| Virchow2 | 승인 필요 |
| H-optimus-1 (Bioptimus) | 수동 승인 게이트, CC BY-NC-ND 4.0 |

기관 이메일을 확보하면 TITAN·UNI2-h를 비교군으로 다시 검토한다.

## 12. 검증

의료진 검토 없이 평가한다 (2026-10-16 결정, 부트캠프 프로젝트라 의료진 상담이 불가능함). 정답은 지침·급여 공고 원문에서 직접 만들고, 정답마다 출처(문서, 버전·공고일, 쪽 또는 그림)를 적는다.

- 입력 모듈: 형식이 다른 차트 원문 30건 이상에서 필드별 추출 정확도와 근거 위치 정확도
- 바이오마커 모듈: HER2 IHC 2+/ISH 미시행, ER 5%, gBRCA VUS, 진행 전 ESR1 결과 같은 경계 사례 판정 테스트. 판정 기준은 ASCO/CAP 원문과 대조한다
- RAG: 아형 × 세팅 × 차수 조합별 질의의 recall@5
- 급여 분류: 가상 환자 × 약제마다 심평원 공고 조건으로 정답 급여 분류(`covered` 등 4종)를 만든다. 분류 정확도와, 인용한 공고 위치가 정답 출처와 같은 비율
- 처방 추천: ESMO 치료 알고리즘(아형 × 병기 범주 × 차수 × 바이오마커 → 권고 요법)을 정답표로 옮겨 허용 선택지로 쓴다. 1순위 추천이 허용 선택지 안에 있는 비율, 허용 선택지 재현율, 인용 출처 일치율. 시스템이 같은 지침을 검색하므로 지침이 옳은지가 아니라 지침을 찾아 적용하는 능력만 평가한다
- 안전 위반 검사 (자동, 0건이 합격 기준): HER2 음성 환자에게 HER2 표적치료 추천, ER·PR 모두 음성 환자에게 내분비요법 단독 추천, 이미 진행된 약제 재추천, 인용 없는 문장, 범위 외 환자(DCIS, 남성 등)에게 추천
- 정답표 신뢰도: 같은 시나리오 30~50건을 두 사람이 따로 정답표로 만들고 일치율(Cohen's kappa)을 잰다. 다르면 원문을 다시 보고 합의하고, 합의 내용을 기록한다
- 보조 지표: TCGA 실제 투약과 큰 방향(HER2 표적치료, 내분비요법 여부)의 일치율. 치료 시기가 오래돼(대부분 2013년 이전) 정답으로 쓰지 않는다
- 한계: 의료진 검증을 하지 않았다. 결과 보고와 발표에 이 한계를 적는다

## 13. 이전 설계(2026-10-06)에서 바뀐 점

| 항목 | 이전 | v0.1 |
|---|---|---|
| 입력 | 원발암 H&E 슬라이드 + 사용자 입력 | 차트 원문. H&E는 v0.2 QC 보조 |
| 처방 근거 | NCI PDQ RAG. ESMO·NCCN·NICE·한국유방암학회 제외 | ESMO 지침 RAG (ASCO는 재사용 불가로 2026-10-20 제외). ESMO는 웹사이트 약관상 비영리 사용에 서면 허가가 필요 없어 사용 확정. NCCN은 여전히 쓰지 않음 |
| 출력 | "조건에 맞는 치료 옵션" (처방 추천 아님) | 처방 후보 + 급여 분류 |
| 병리 모델 | 승인 필요 모델(UNI, CONCH, Virchow2) 제외, Phikon-v2·H-optimus-0 + ABMIL | H-optimus-0 1순위, Hibou-B·Phikon-v2·CHIEF 비교. 승인 필요 모델 제외 원칙은 유지 (TITAN 제거) |
| 급여 판정 | 공고 제2025-210호 고정, 규칙 코드 판정 | 공고책자 + 개정 공고 자동 업데이트, 허가초과 인정 목록 포함 |
| 허가 정보 | 식약처 API로 허가·비급여 약 보완 | 국내 허가 여부는 판단하지 않음 |

## 14. 남은 과제

- [x] TCGA-BRCA 임상·체세포 변이 데이터 다운로드와 구조 파악 (2026-10-07, `data/script/tcga_brca_download.py`, `data/script/tcga_brca_explore.py`)
- [x] TCGA-BRCA 테이블을 환자 ID로 합친 환자 1명 = 1행 파일 (2026-10-07, `data/script/tcga_brca_merge.py`). GDC 결측 코드는 `[Not Available]` = 기록 없음, `[Not Evaluated]` = 미시행으로 해석한다. 변이 검사를 받았는데 변이가 없으면 "변이 없음"으로 쓴다
- [x] TCGA 투약 기록의 약제명·치료 종류 정규화 사전 (`data/dictionaries/drug_names.csv`, `drug_classes.csv`). IN-3 약어 사전의 출발점으로 쓴다
- [x] 병기 범주 (2026-10-13 결정): I~II기 = 조기, III기 = 국소 진행성 (심평원 급여 조건 기준), IV기 = 전이성. `patient_state.stage.disease_extent`(진단 시), `biomarker_record.setting.disease`·`chunk.setting`(현재 치료 상황)에 `locally_advanced`를 추가했다. TCGA 크롭본에 `stage_disease_extent` 열을 만들었다. A의 정답 세트 규칙(병기 `[Discrepancy]` 6명, `[Not Available]` 5명, 전부 빈칸 1명 제외)을 먼저 적용하고, 범주를 정할 수 없는 Stage X 11명과 조직형 NOS·기록 없음 2명을 더 뺐다 (25명, 1,086명 → 1,061명). 이어서 재발 상태(`recurrence_status`)를 정하고, 진단 시 전이성이 아니면서 새 원발암만 있는 18명을 뺐다 (1,061명 → 1,043명). 현재 범주(`current_disease_extent`, `setting.disease` 정답)는 전이가 됐는지만 본다: 진단 시 전이성(Stage IV·M1) 또는 원격 전이 재발 → 전이성, 그 밖(재발 없음, 국소 재발, 재발 부위 모름, 재발 여부 모름)은 진단 시 범주 그대로다. 급여·처방 기준에서 필요한 것은 전이 여부뿐이기 때문이다. 국소 재발(첫 치료 후 유방·흉벽·주변 림프절 재발)은 전이가 아니고, 국소 진행성(진단 시 III기)과도 다른 개념이다. 병합 스크립트가 `follow_up_v2.1`의 재발 종류를 읽지 않아 46명의 재발 종류가 비어 있던 것도 고쳤다. 2026-10-14: 차수는 정답 데이터에 넣지 않고 B 모듈이 투약 이력으로 판단하게 한다. 그 재료로 전이 기준일(`metastasis_dx_days`)을 추가하고, 현재 전이성인데 전이 후 항암 투약 기록이 없는 46명을 뺐다 (1,043명 → 997명, 전이성 32명). TCGA 정답은 진단 시(원발 종양) 병리 병기·수용체만 쓴다. 재발 병소 수용체는 재발 기록과 맞는 환자가 1명뿐이라 정답에 쓰지 않고, 재발 병소 결과 우선 규칙(IN-4)은 가상 차트와 실제 차트에만 적용한다. 크롭본이 곧 정답 세트다
- [x] `patient_state` 0.1-draft5 (2026-10-15 협의): 차수는 정답에 넣지 않고 B가 투약 시작일(`treatment_history[].start_day`, 진단일 = 0)과 전이 기준일(`recurrence.metastasis_day`)로 판단한다. 심평원 투여단계는 고식적 내분비요법과 고식적 항암화학요법을 따로 센다. 국소 재발 후 수술(재발 후 원격 전이 없음)이면 이후 요법은 수술후보조요법(공고 p.48). TCGA 정답에서는 BRCA1/2 종양 엑솜 결과를 gBRCA 측정으로 가정한다. PD-L1은 발현 점수만 넘기고 B가 약제별 기준으로 판정한다. 유전자 변이(ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2)는 유전자별로, anthracycline 투약 용량(liposomal doxorubicin 급여 조건용)은 약별로 넘긴다. 투여 주기에는 주기 길이를 붙인다 (`data/dictionaries/drug_classes.csv`의 `cycle_days`). anthracycline 병용 용량을 나눌 수 없는 4명과 재발했지만 부위를 모르는 7명을 빼 정답 세트는 985명이다. 모델 한계: 장기 위기, 심장 위험 요인, 투약 중 여부, 재발 후 수술 의도는 판단하지 않는다. 전달 문서는 `src/input/handoff_to_B.md` (BM-3 제안과 draft5 내용을 2026-10-15에 한 파일로 합침)
- [x] `patient_state` 0.1-draft6 (2026-10-16 A 제안, 4명 검토 전): 차수는 A가 변환할 때 계산해 `treatment_history[]`의 `line`(전체)·`endocrine_line`(고식적 내분비)·`chemo_line`(고식적 항암)에 넣는다 (`src/input/common/lines.py`). 심평원 차수 간주 규칙 4개(anthracycline·taxane 선행·보조, sacituzumab 1년, T-DM1·T-DXd 6개월, 보조 내분비 1년)는 차수를 바꾸지 않고 `fields.deemed_lines`에 충족 여부만 넣는다. 판정 기준일 `index_day`(TCGA = 마지막 추적일), 첫 재발일 `recurrence.recurrence_day` 추가. TCGA BRCA는 gBRCA 가정 유지
- [x] TCGA 필드를 v0.1 추출 스키마에 대응 (규칙 `src/input/tcga_mapping.md`) + 정답 생성기 (2026-10-15, `src/input/truth/tcga_truth.py`, 874명 전원 스키마 통과 (2026-10-15 HER2 판정 불가 62명, PR Indeterminate 4명, ER·PR·HER2 모두 미시행 43명, ER 또는 PR 미시행 2명 제외 후), 테스트 `tests/input/`)
- [ ] 가상 차트 작성 방법 정하기 (양식 종류, 문장으로 쓸 필드, 합성값, 국내 표현 수집)
- [ ] LLM 공통 인터페이스 `llm/` (0단계 A 담당)
- [ ] ESMO 치료 알고리즘 도식의 텍스트 변환과 검수
- [x] ESMO 사용 조건 확인 (2026-10-07): ESMO 웹사이트 약관은 개인·비영리 사용을 허가 없이 허용하고, AI 관련 조항은 없다. 비영리 프로젝트이므로 ESMO로 진행한다
- [x] ASCO 지침의 재사용 조건 확인 (2026-10-20): 재사용 불가. RAG에서 ASCO 청커·청크·사전 표현을 지웠다
- [ ] ESMO 전이성 유방암 지침(2026) 원문 확보 경로 정하기. Annals of Oncology 논문은 아직 Elsevier 공개 라이선스가 붙지 않았으므로 esmo.org 게시본을 우선 검토한다
- [ ] 심평원 급여 공고 수집, 조건 단위 청킹, 개정 추적 방법 정하기
- [ ] 공고책자 날짜 = 마지막 반영 공고 시행일 가정을 몇 달간 대조해 확정
- [x] ER·PR 판정 규칙 (2026-10-12, §5 세부 판정 규칙): ER만 저발현, PR 1–10%는 양성 + `PR-low` 태그. 2026-10-15 변경: PR은 Allred 총점(0–2 음성, 3 이상 양성) → 구간 최대값 → 비율 순서로 보고 기준을 9%로 둔다 (9% 이상 양성, unknown 사용). `PR-low` 태그는 없앴다 (ASCO·ESMO에 없는 범주). ER: ER은 Allred 총점을 먼저 본다 (0–2 음성, 3–4 저발현, 5는 비율로 가름, 6–8 양성). Allred가 없으면 비율 1–10%를 저발현으로 판정. 같은 날 추가: ER 비율 구간이 0부터 시작하면 최대값으로 판정 (`[0,1]` 음성, `[0,9]`·`[0,10]` 저발현)
- [x] HER2 경계 사례 (2026-10-15, B 결정, §5 HER2 세부 표): IHC 2+ + 적힌 판정 positive + ISH 없음(미시행·기록 없음)은 양성 + ISH 검사 권고 (TCGA 5명). IHC 0 + ISH 증폭은 데이터 오류 가능성이 있어 HER2 값을 판정에서 제외하고 불확정 + 원자료 확인 (TCGA 0명). A에게 알려 정답·가상 차트 기준을 맞춘다
- [x] BM-3 출처 (2026-10-15 결정): OncoKB를 쓰지 않고 허가사항 변이 목록 → CIViC → ClinVar·VEP를 로컬로 조회한다 (`src/input/handoff_to_B.md` §5). `schemas/biomarker_record.json`의 `evidence.oncokb`를 출처 중립 `annotation`으로 바꾸는 스키마 변경은 4명 검토 후 반영
- [ ] BM-2 수치 기준을 ASCO/CAP 원문과 대조해 확정 (HER2 세부 조건 포함). 의료진 검토는 하지 않는다 (2026-10-16)
- [ ] §12 정답표 작성: 급여 분류 정답표, 처방 허용 선택지 표(ESMO·ASCO 치료 알고리즘), 안전 위반 규칙. 담당과 시나리오 수 정하기 (2026-10-16 추가)
- [x] Ki-67 판정 기준 (2026-10-15 확정): 20% 이상 고증식(positive), 미만 negative, 20%에 걸치는 구간·적힌 판정 intermediate는 intermediate, 쓸 값 없으면 unknown (`BM1_ER,PR,HER2,Ki_67,subtype.py`의 `KI67_HIGH_MIN`). TCGA는 Ki-67이 모두 기록 없음이라 정답 영향 없음
- [x] ER low는 아형에서 HR+로 본다 (2026-10-15 확정). TCGA ER low 14명은 원본 `<10%` + Positive를 크롭 단계에서 `1-9%` + Low Positive로 나눈 값
- [x] 기록 없음(`not_recorded`)은 검사 권고를 내지 않고 기록 없음으로만 표기한다 (2026-10-15 확정). 검사 권고(BM-4)는 미시행(`not_done`)일 때만 낸다
- [x] `setting.disease`·`setting.line`과 바이오마커 상태값에서 `indeterminate`를 없애고 `unknown`을 쓴다 (2026-10-15). 차수는 아직 계산하지 않아 `line`은 모두 `unknown`
- [ ] 생식세포/체세포 구분: `patient_state`의 유전자 칸에 출처 구분이 없어 `BM1_ER,PR,HER2,Ki_67,subtype.py`는 patient_ref가 `TCGA-`로 시작하면 gBRCA, 아니면 sBRCA로 본다. 가상·실제 차트를 위해 `molecular.mutations`에 `origin`(germline / somatic) 칸 추가를 검토 (공용 스키마, 4명 합의)
- [ ] ESR1 테스트 범위 확인 (2026-10-15 기록): TCGA 정답 874명 중 ESR1 변이가 있는 환자는 9명뿐이다 (모두 원발 조직 결과). 재검 필요 규칙(원발 결과 + 이후 내분비요법 진행)은 전이성 28명으로 시험할 수 있지만, ESR1 양성 판정(허가 동반진단 변이 목록)은 사례가 적다. MSK-IMPACT는 쓰지 않기로 했으므로(2026-10-15) 부족하면 가상 차트로 사례를 만든다. 지금은 확인만 해 두고 넘어간다
- [ ] 로컬 LLM 선정 (Qwen 계열, EXAONE, snuh/hari-q3-8b 비교)
- [ ] 최종 출력 형식 (CLI, 웹 UI, 리포트 등)
- [ ] 다음 버전: 약물유전체 경고, Oncotype 대리 점수, 멀티모달 QC 연결 (v0.2 문서)
- [ ] v0.2: H-optimus-0 접근 신청 후 바로 열리는지 확인, 슬라이드 100~200장으로 특징 추출 파이프라인 검증
- [x] `data/script/`, `data/dictionaries/`, `data/metadata/`의 공유 방법 (2026-10-12): `.gitignore`를 바꿔 `data/` 안의 csv·txt·py 파일만 git에 올린다 (§15.2)

## 15. 역할 분담 (4명)과 폴더 구조

### 15.1 폴더 구조와 충돌 방지 규칙

모듈마다 폴더를 따로 두고, **각자 자기 모듈 폴더 안에서만 코드를 작성한다.** 다른 사람의 모듈 폴더는 고치지 않는다. 필요한 변경은 담당자에게 요청한다.

```
team_project/
├── src/
│   ├── input/          [1] 입력 모듈          — A
│   ├── biomarker/      [2] 바이오마커 모듈     — B
│   ├── recommend/      [4] LLM 추천 모듈       — B (2단계)
│   ├── rag/            [3] 지침 RAG + 공용 검색 색인 — C
│   └── reimbursement/  [5] 급여 기준 자동 업데이트 — D
├── schemas/            모듈 간 JSON 형식        — 공용 (4명 합의)
├── llm/                LLM 공통 인터페이스      — 공용 (4명 합의)
├── tests/
│   ├── fixtures/       가상 차트, 모듈별 예상 출력 — 공용
│   ├── input/  biomarker/  rag/  reimbursement/  recommend/   — 각 모듈 담당
└── data/               데이터 (csv·txt·py만 git에 올림)
    ├── script/         TCGA-BRCA 데이터 탐색 스크립트
    ├── dictionaries/   약제명·치료 종류 사전
    ├── metadata/       v0.2 슬라이드 목록
    └── tcga_brca/      다운로드한 TCGA 데이터와 합친 파일
```

규칙:

1. 모듈 코드는 `src/<모듈>/`, 모듈 테스트는 `tests/<모듈>/`에만 둔다.
2. 공용 폴더(`schemas/`, `llm/`, `tests/fixtures/`)는 4명이 모두 검토한 뒤에만 바꾼다.
3. 모듈끼리는 `schemas/`에 정한 JSON 형식으로만 데이터를 주고받는다. 다른 모듈의 내부 함수를 직접 가져다 쓰지 않는다. 예외: D는 `src/rag/`가 공개한 색인 함수를 호출해 급여 청크를 넣는다.
4. 공용 검색 색인 코드는 `src/rag/`에만 둔다 (C 관리). D는 색인 코드를 따로 만들지 않는다.
5. 브랜치는 모듈별로 나눈다 (예: `feature/input-deid`, `feature/rag-chunking`). 공용 폴더 변경은 별도 브랜치로 올린다.
6. 앞 모듈이 끝나지 않았으면 `tests/fixtures/`의 예상 출력을 입력으로 써서 개발한다.

### 15.2 폴더별 사용법과 파일 목록

2026-10-12 기준이다. 폴더나 파일을 추가·이동하면 이 표도 함께 고친다.

#### 루트 파일

| 파일 | 용도 | git |
|---|---|---|
| `PROJECT.md` | 설계 문서 (이 파일). 결정 사항과 남은 과제를 여기에 기록한다 | 올림 |
| `CLAUDE.md` | 팀 공용 Claude Code 안내. 4명 모두에게 적용되는 규칙만 쓴다 | 올림 |
| `CLAUDE.local.md` | 개인별 설정 (내 PC 경로, conda 위치, 사용 언어) | 제외 |
| `README.md` | 저장소 제목. UTF-16으로 저장되어 있어 인코딩을 지원하는 도구로 연다 | 올림 |
| `.gitignore` | git 제외 목록. `data/` 안은 csv·txt·py만 올리고 나머지 제외, 스프레드시트 잠금 파일(`.~lock.*#`), `*.h5`·`*.db`·`*.parquet`·`*.npy`, `.env`, `.venv/`, `CLAUDE.local.md`, 캐시 | 올림 |
| `.vscode/settings.json` | VS Code 설정 | 올림 |
| `.env` (만들 때) | API 키 (Claude API 등). 절대 커밋하지 않는다 | 제외 |

#### src/ — 모듈 코드

각 모듈 폴더에는 지금 `README.md`(담당자, 범위, 입력, 출력)와 빈 `__init__.py`만 있다. 코드는 담당자가 이 폴더 안에 추가한다.

| 폴더 | 담당 | 사용법 | 입력 → 출력 |
|---|---|---|---|
| `src/input/` | A | 비식별화(IN-0)부터 유전자 보고서 전달(IN-7)까지. 환자 텍스트는 `llm/`의 로컬 설정으로만 처리 | 차트 원문 → `patient_state` |
| `src/biomarker/` | B | BM-1 파싱(로컬 LLM), BM-2·BM-4는 규칙 코드, BM-3은 허가사항 변이 목록·CIViC·ClinVar·VEP 로컬 조회. 아형과 치료 상황(현재 범주, 차수)도 산출 | `patient_state` → `biomarker_record` |
| `src/rag/` | C | 지침 수집·파싱·청킹, 공용 Qdrant 색인, 검색 API. D가 호출할 색인 함수를 여기서 공개 | 지침 PDF, 급여 청크 → 검색 결과(`chunk` 목록) |
| `src/reimbursement/` | D | 심평원 게시판 수집, 날짜 규칙, SQLite 레지스트리, 급여 청크 생성. 색인 반영은 `src/rag/` 함수 호출 | 심평원 공고 → 급여 `chunk` |
| `src/recommend/` | B (2단계) | 프롬프트 구성, 로컬 LLM 호출, 스키마 검증, 환각 방지 후처리, 급여 분류 | `patient_state` + `biomarker_record` + 검색 결과 → `recommendation` |
| `src/__init__.py` | 공용 | `from src.input import ...` 형태로 가져오기 위한 빈 파일 | — |

#### schemas/ — 모듈 간 JSON 형식 (공용)

| 파일 | 내용 |
|---|---|
| `README.md` | 스키마 설명, 코드값과 한국어 표시 대응표, 가상 환자 예시 4개, 검증 방법, 0단계에서 정할 것 |
| `patient_state.json` | [1] 입력 출력 |
| `biomarker_record.json` | [2] 바이오마커 출력 (레코드 목록 + 아형 + 치료 상황 + 검사 공백) |
| `chunk.json` | 지침·급여 공용 청크 |
| `recommendation.json` | [4] 최종 출력 |

사용법: 모듈 출력을 내보내기 전에 해당 스키마로 검증한다 (`jsonschema` 패키지, 검증 코드는 `schemas/README.md` §7). 지금은 초안(`0.1-draft`)이다.

#### llm/ — LLM 공통 인터페이스 (공용)

| 파일 | 내용 |
|---|---|
| `README.md` | 사용 원칙 (환자 데이터 모듈은 로컬 설정만, Claude API는 공개 문서 모듈만, 키는 `.env`) |
| `__init__.py` | 빈 파일. 0단계에서 A가 공통 인터페이스 초안을 작성한다 |

#### tests/ — 테스트

| 폴더 | 담당 | 사용법 |
|---|---|---|
| `tests/fixtures/` | 공용 (가상 차트는 A) | 가상 차트와 모듈별 예상 출력. 앞 모듈이 없어도 이 파일을 입력으로 써서 개발한다. 실제 환자 데이터는 넣지 않는다. 지금은 `README.md`만 있다 |
| `tests/input/`, `tests/biomarker/`, `tests/rag/`, `tests/reimbursement/`, `tests/recommend/` | 각 모듈 담당 | 모듈 단위 테스트. 지금은 git에 빈 폴더를 올리기 위한 `.gitkeep`만 있다 |

#### data/ — 데이터와 데이터 준비 스크립트

git 규칙: `data/` 안은 기본적으로 제외하고 **csv·txt·py 파일만 올린다.** 다른 텍스트 형식을 올리려면 `.gitignore`에 `!data/**/*.확장자`를 추가한다. GitHub는 50MB가 넘는 파일에 경고하고 100MB가 넘으면 거부하므로, 큰 파일은 올리지 말고 스크립트로 다시 만든다.

| 경로 | 내용 | git |
|---|---|---|
| `data/script/tcga_brca_download.py` | TCGA-BRCA 임상 파일(GDC BCR Biotab)과 cBioPortal 임상·변이·바이오마커 유전자 CNA 데이터를 `data/tcga_brca/`에 내려받는다. 이미 받은 파일은 건너뛴다 | 올림 |
| `data/script/tcga_brca_explore.py` | 구조 요약을 출력하고 `data/tcga_brca/structure_report.md`를 만든다 (`tabulate` 필요) | 올림 |
| `data/script/tcga_brca_merge.py` | 모든 표를 환자 ID로 합쳐 환자 1명 = 1행 파일을 만든다. 약제명은 `data/dictionaries/` 사전으로 바로잡고, 사전에 없는 약제명이 나오면 멈춘다 | 올림 |
| `data/script/tcga_brca_crop.py` | 합친 파일에서 남성 환자와 `DROP` 목록의 열을 빼고, 열 설명과 변경 기록을 만든다 | 올림 |
| `data/dictionaries/drug_names.csv` | 원문 약제명 → 일반명 사전. IN-3 약어 사전의 출발점 | 올림 |
| `data/dictionaries/drug_classes.csv` | 일반명 → 치료 종류 사전 | 올림 |
| `data/metadata/slides_files.csv`, `gdc_manifest_slides_test.txt` | v0.2용 TCGA-BRCA 진단 슬라이드 목록과 GDC 다운로드 매니페스트 | 올림 |
| `data/tcga_brca/gdc_clinical/` | GDC Biotab 임상 파일 9개 (환자, 투약, 방사선, 추적 관찰 v1.5·v2.1·v4.0, 새 종양 사건, 기타 악성종양). 헤더 3줄, 결측은 `[Not Available]` = 기록 없음, `[Not Evaluated]` = 미시행 | 올림 (txt) |
| `data/tcga_brca/cbioportal/` | cBioPortal PanCancer Atlas 파일 6개 (환자·샘플 임상, 임상 속성 설명, 변이, 바이오마커 유전자 CNA, 검사 대상 샘플) | 제외 (tsv). 다운로드 스크립트로 다시 받는다 |
| `data/tcga_brca/structure_report.md` | 탐색 스크립트가 만든 열 단위 구조 보고서 | 제외 (md). 탐색 스크립트로 다시 만든다 |
| `data/tcga_brca/merged/tcga_brca_merged.csv` | 환자 1명 = 1행으로 합친 파일, 열 설명은 `tcga_brca_merged_columns.csv`, 약제명 수정 기록은 `drug_corrections.csv` | 올림 (csv·txt) |
| `data/tcga_brca/merged/tcga_brca_merging_cropped.csv` | 남성 환자와 불필요한 열을 뺀 최종 파일. 열 설명 `_columns.txt`, 변경 기록 `_changes.txt` | 올림 (csv·txt) |

스크립트 실행 순서 (`team_project` 폴더에서, `team_project` conda 환경으로):

```bash
python data/script/tcga_brca_download.py
python data/script/tcga_brca_explore.py
python data/script/tcga_brca_merge.py
python data/script/tcga_brca_crop.py
```

새로 받은 팀원은 git에 없는 파일(cbioportal tsv, structure_report.md)을 위 순서대로 스크립트를 실행해 만든다. 합친 파일(`merged/`)은 git으로 받으므로, 다운로드 없이 바로 쓸 수도 있다. 단, 합친 파일을 다시 만들려면 cbioportal 파일이 필요하므로 다운로드부터 실행한다.

### 15.3 진행 단계

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| 0단계 (1–2일, 4명 함께) | `schemas/` 4개 파일, `llm/` 공통 인터페이스, 가상 차트 5건과 모듈별 예상 출력 | 스키마 합의, fixture 저장 |
| 1단계 (병렬) | A·B·C·D가 각자 모듈 개발 | 각 모듈이 fixture 입력으로 자기 테스트 통과 |
| 2단계 (통합) | [4] LLM 추천 개발, 전체 연결 | 가상 차트 5건이 [1]→[2]→[3]/[5]→[4]를 거쳐 출력까지 나옴 |
| 3단계 (평가) | §12 검증 계획 실행 | 추출 정확도, 경계 사례, recall@5, 급여 정답 대조, 처방 허용 선택지 대조, 안전 위반 0건 |

### 15.4 담당 A — [1] 입력 모듈 + 가상 차트

폴더: `src/input/`, `tests/input/`. 공용 책임: `tests/fixtures/` 가상 차트 작성.

| 작업 | 내용 |
|---|---|
| IN-0 비식별화기 | Presidio + 한국어 패턴(주민번호, 등록번호, 전화번호). 원래 값 대응표는 내부 보관 |
| IN-1 문서 분류기 | 경과기록 / 병리 / 분자병리·NGS / 투약 기록 분류 |
| IN-2 필드 추출기 | 로컬 LLM으로 §4 추출 스키마 추출. 값마다 원문 인용과 확신도 |
| IN-3 표기 정규화기 | 국문·영문 혼용 표기 표준화. `data/dictionaries/`를 출발점으로 확장 |
| IN-4 ~ IN-6 | 시간 정렬(최신 값, 전이 병소 재생검 우선), 충돌 검사, 누락 상태 판정(값 있음 / 미시행 / 기록 없음) |
| IN-7 | 분자병리·NGS 보고서 원문을 해석 없이 B에게 전달 |
| 가상 차트 | TCGA-BRCA 필드를 추출 스키마에 대응시키고, 형식이 다른 가상 차트를 만든다 (0단계 5건 → 검증용 30건 이상). 작성자가 아닌 팀원이 TCGA 정답과 대조해 교차 검토 |
| 로컬 LLM 선정 | Qwen 계열, EXAONE, snuh/hari-q3-8b를 같은 가상 차트로 비교 (추출 정확도, 인용 준수율). 결과를 팀에 공유 |

산출물: `patient_state` (schemas/patient_state.json). 2단계: 가상 차트를 전체 흐름에 넣어 끝까지 돌리고 §12 정답표용 시나리오를 정리한다.

### 15.5 담당 B — [2] 바이오마커 모듈 + [4] LLM 추천 모듈

폴더: `src/biomarker/`, `src/recommend/`, `tests/biomarker/`, `tests/recommend/`.

1단계 — 바이오마커:

| 작업 | 내용 |
|---|---|
| BM-1 보고서 정규화기 | 가상·실제 차트의 유전자 보고서 원문(`genomic_reports[].raw_text`)을 로컬 LLM으로 파싱 (모듈 안의 유일한 LLM 단계). `molecular.mutations`에 같은 정보가 있으면 그쪽을 우선 |
| BM-2 상태 판정기 | §5 판정 기준표를 규칙 코드로 작성. 상태값: 양성 / 음성 / 저발현 / 초저발현 / 0 / VUS / 불확정 / 미시행 / 재검 필요 / 기록 없음. BM-2 ~ BM-4는 한 파일 `src/biomarker/BM1_ER,PR,HER2,Ki_67,subtype.py`에 둔다 (진입점 `assess(patient_state)`, 2026-10-15: ER·PR·HER2·Ki-67 판정, 아형, 현재 범주, 검사 공백. 유전자 7개는 2026-10-16에 1차 규칙(허가 변이 목록·절단 변이, `src/biomarker/README.md`)으로 작성, 유전자 검사 공백도 같은 날 추가, 차수는 아직). 재발 환자는 재생검 결과로 판정하고 원발 대비 변화를 `reason`에 적음 |
| BM-3 근거 주석기 | 허가사항 변이 목록 규칙표(원문에서 작성, 출처 기록), CIViC·ClinVar 다운로드 스크립트(`data/script/`), VEP 로컬 실행. 외부 API 호출 없음. OncoKB는 쓰지 않음 |
| BM-4 검사 공백 탐지기 | §5 검사 공백 규칙 (gBRCA, PIK3CA·AKT1·PTEN, ESR1 재검, PD-L1, HER2 재판정, IHC 2+ ISH 검사) |
| 아형 | ER·PR·HER2 상태로 HR+/HER2-, HR+/HER2+, HR-/HER2+, TNBC. 재발 환자는 재생검 결과 기준 |
| 치료 상황 (2026-10-16 담당 변경) | B: 현재 범주(`setting.disease`), 국소 재발 후 수술이면 수술후보조요법(`SET-LOCAL-ADJ`), PD-L1 약제별 판정. A(변환 단계): 차수, 심평원 투여단계(고식적 내분비요법과 고식적 항암화학요법을 따로 셈), anthracycline 누적 용량. 규칙은 `src/input/handoff_to_B.md` §6·§10.2 |
| 테스트 | 경계 사례(HER2 IHC 2+/ISH 미시행, ER 5%, gBRCA VUS, 진행 전 ESR1 결과 등)는 직접 만든 입력으로 시험한다. 실제 데이터 검증은 TCGA-BRCA 정답 세트(874명, `src/input/script/tcga_to_patient_state.py`의 `convert(load_rows())`)로 한다. MSK-IMPACT는 테스트 범위가 너무 커져 쓰지 않는다 (2026-10-15 결정). TCGA에 ESR1 변이가 9명뿐이라 ESR1 양성 판정은 시험할 사례가 적다 (§14에 확인 항목으로 남김) |
| 기준 확정 | BM-2 수치 기준을 ASCO/CAP 원문과 대조해 확정 (의료진 검토 없음, 2026-10-16) |

2단계 — LLM 추천 (§7):

| 작업 | 내용 |
|---|---|
| 프롬프트 | 환자 상태, 바이오마커 상태값·판정 이유, 검사 공백, 지침 청크(부모 소단원 포함), 급여 청크 |
| 출력 검증 | `schemas/recommendation.json` 스키마 검사 |
| 환각 방지 후처리 | 인용 없는 문장 삭제, 인용 청크의 약제명 문자열 재확인, 불확정·미시행 바이오마커가 필요한 치료는 검사 권고로 전환 |
| 급여 분류 로직 | 급여 / 급여(조건 확인 필요) / 허가초과 인정 / 급여 기준 없음. D와 판정 근거 연결 |

산출물: `biomarker_record` 목록 (schemas/biomarker_record.json), `recommendation` (schemas/recommendation.json).

### 15.6 담당 C — [3] 지침 RAG + 공용 검색 색인

폴더: `src/rag/`, `tests/rag/`.

| 작업 | 내용 |
|---|---|
| 수집 | ESMO 조기(2024)·eUpdate, ESMO 전이성(2026-05). 원문과 발행일 보관. ASCO는 재사용 불가로 제외 (2026-10-20) |
| 사용 조건 | ~~ASCO 재사용 조건 확인~~ 불가로 확인 (2026-10-20), ESMO 전이성 2026 원문 확보 경로 결정 (esmo.org 게시본 우선) |
| 파싱 | Docling. 실패하면 Marker, PyMuPDF 비교 |
| 청킹 | 권고문 단위(약 300–800 토큰), 근거 수준(LoE/GoR, ESMO-MCBS, ESCAT), 부모-자식 구조, 표는 행 단위 문장화 |
| 알고리즘 도식 | 노드-엣지 텍스트("조건 → 권고")로 변환 후 사람 검수 |
| 공용 색인 | Qdrant + bge-m3 + BM25 하이브리드. `schemas/chunk.json` 메타데이터, `superseded_by` 관리. D가 호출할 색인 함수 공개 |
| 검색 API | setting·subtype·line 하드 필터 → biomarker_tags 가중치 → bge-reranker-v2-m3 재정렬. ESMO EBC와 MBC는 출처별로 따로 반환 |
| 평가 | 아형 × 세팅 × 차수 조합별 질의의 recall@5. 평가용 질의는 Claude API로 생성 가능 (환자 정보 없음) |

산출물: 지침 청크, 공용 색인, 검색 API. 2단계: 후보 약제명으로 급여 청크를 다시 검색하는 2차 검색 연결, RAGAS 평가.

### 15.7 담당 D — [5] 급여 기준 자동 업데이트 + 급여 청크

폴더: `src/reimbursement/`, `tests/reimbursement/`.

| 작업 | 내용 |
|---|---|
| 수집 | 항암화학요법 게시판(공고책자, 허가초과 항암요법), 공고 게시판, 공고예고 게시판. 다운로드 요청 재현, 안 되면 Playwright. 첨부 형식(PDF/HWP) 확인 |
| 날짜 규칙 | §8 날짜 비교 규칙 1–5 (책자 날짜 B, 시행일 기준 비교, 예정·진행중 처리, 날짜 표기 통일) |
| 레지스트리 | SQLite (source, doc_no, board_id, effective_date, posted_date, file_name, file_hash, status) |
| 구조화 | 유방암 약제·요법만 남기고 Claude API로 조건 단위 JSON 생성 (약제, 요법, 투여 단계, 조건, 시행일, 공고번호, 출처 쪽수). 스키마 검사와 약제명 사전 대조 |
| 허가초과 | 유방암 인정 요법 21건을 (암종, 약제 조합, 투여대상, 투여단계, 본인부담률)로 저장. 파일명 날짜로 갱신 판단 |
| 색인 반영 | `src/rag/` 색인 함수로 급여 청크 저장. source_type(baseline / overlay / preview), effective_from, superseded_by 부여 |
| 실패 처리 | 마지막 정상 버전 유지, 현재 버전과 경고 표시 |
| 가정 검증 | 공고책자 날짜 = 마지막 반영 공고 시행일 가정을 몇 달간 대조 |

산출물: 급여 청크(doc_type = reimbursement), 레지스트리, 신설·변경·삭제 목록. 2단계: 급여 분류 판정 근거를 B의 추천 모듈에 연결하고, 화면 하단 반영 현황 요약("현재 반영: 공고책자 … / 예정 … / 진행중 …")을 만든다.

### 15.8 0단계 공동 산출물

| 파일 | 초안 작성 | 검토 |
|---|---|---|
| `schemas/patient_state.json` | A | B, C, D |
| `schemas/biomarker_record.json` | B | A, C, D |
| `schemas/chunk.json` | C | D 필수, A, B |
| `schemas/recommendation.json` | B | A, C, D |
| `llm/` 공통 인터페이스 | A | 전원 |
| `tests/fixtures/` 가상 차트 5건 | A | 전원, 모듈별 예상 출력은 각 담당자 |

### 15.9 v0.2 H&E 모듈

1단계에서 여유가 생기는 사람(B 또는 D)이 슬라이드 100–200장으로 특징 추출 파이프라인 검증부터 시작한다. 폴더는 v0.2 시작 시 `src/pathology/`로 만든다.
