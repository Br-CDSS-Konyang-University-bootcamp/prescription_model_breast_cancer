# patient_state 필드 정리와 정규화 예시

> 담당 A · 2026-10-12 (2026-10-13 `stage.disease_extent` 추가, 2026-10-15 draft5 필드 추가, 2026-10-16 draft6 필드 추가, 2026-10-20~23 draft7 후보 필드 추가, 2026-10-27 draft7 변경 요약 추가, TCGA 정답 규칙 삭제) · 기준 스키마: `schemas/patient_state.json` (0.1-draft6 + draft7 후보. `schema_version`은 4명 검토 뒤 `0.1-draft7`로 올린다)

입력 모듈(A)이 만드는 `patient_state`의 필드, 표준값 형태, 정규화 방식, 예시를 정리한다. 2026-10-27 TCGA 정답 세트 폐기, 평가는 가상 차트로.

표기:

- 정규화 방식: **사전** = `data/dictionaries/field_vocab.csv` 조회 · **해석** = 정규식·파싱 함수 · **그대로** = 원문 보존
- **[제안]**: 현재 스키마 초안에 없거나 형태가 다른 항목. B와 합의 후 스키마에 반영한다
- **[A 결정]**: 담당 A가 정한 규칙
- **[합의 예정]**: A가 받아들인 제안. 스키마 반영 전에 B와 확인한다
- **[draft7 후보]**: 가상 차트 평가용으로 2026-10-20~23에 스키마에 넣은 선택 칸. 4명 검토 전이다

A는 원칙적으로 표기만 정리한다. 예외: HER2 IHC의 `result`는 ISH 결과로 보정한다 (§5, A 결정). 양성·음성·저발현 같은 최종 판정은 B가 한다. B에게 전달하는 내용은 [handoff_to_B.md](handoff_to_B.md)에 있다.

## draft6 → draft7 후보 변경 요약 (2026-10-20~23)

가상 차트(VC-0101~VC-0129)로 평가하면서 추가한 칸이다. 모두 선택 칸이라 없어도 검증을 통과한다 (`at_index`는 A가 계산해 늘 채움). A의 `patient_state` 값은 의사가 화면 1에서 `schemas/confirmed_state.json` 항목으로 확정하고, 2단계(C 검색, D 급여, B 추천)는 그 확정값만 읽는다. "가상 차트"는 `tests/fixtures/virtual_charts/*/expected/patient_state.json`에 값이 있는 사례다 (2026-10-27 기준).

| 추가된 칸 | 위치 (자세히) | 형태 | 담는 내용 | 쓰는 곳 (근거) | confirmed_state 항목 → 읽는 모듈 | 가상 차트 |
|---|---|---|---|---|---|---|
| `doc_type` 값 `radiology` | `documents[]` (§1) | enum 값 추가 | 영상 판독 문서 (CT, 뼈 스캔, PET 등) | A 문서 분류(IN-1), `imaging_findings` 근거 문서 | — (A 내부) | 23건 |
| `yptnm` | `stage` (§4) | `{t, n, m, edition, residual_size_mm, positive_ln, examined_ln}` | 선행요법 뒤 수술 병리 병기, 잔존 침윤암 크기, 림프절 수. 선행요법 전 병기는 `ctnm`, 수술 먼저면 `ptnm` | 선행요법 뒤 잔존암 판단. 크기 조건은 선행 전 cT로 본다 | `stage.t` 설명에서 참조 → C·D | VC-0105, 0117, 0119, 0120 |
| `clinical_size_mm` | `stage` (§4) | 숫자 (mm) | 치료 전 임상 종양 최대 직경 | 선행요법 급여 '2cm 초과' (공고 9장 1가). T 범주로는 1·2·5cm 경계를 못 가름 | `stage.size_mm` (basis c) → D | 5건 |
| `pathologic_size_mm` | `stage` (§4) | 숫자 (mm) | 수술 검체 침윤암 최대 직경 (관내암 제외) | 보조요법 급여 '1cm 이상·초과', '5cm 이상' (공고 9장 2-10~20) | `stage.size_mm` (basis p) → D | 19건 |
| `menopausal_basis` 값 `ovarian_radiation`, `hysterectomy` | `patient` (§7) | enum 값 추가 | 난소 방사선요법, 자궁적출로 무월경 판정 불가 (FSH는 `raw`) | 폐경 정의 (공고 p.48, 원문 대조 전) | `menopausal_status` 판단 근거 → C·D | 없음 |
| `height_cm`, `weight_kg` | `patient` (§7) | 숫자 | 키, 몸무게 (측정일은 `observed_date`) | 용량이 mg로만 적힌 차트에서 체표면적 → mg/m² 환산 (공고 9장 4나-19) | `prior_regimens.doses`, `anthracycline_cumulative` (mg/m²로 확정) → D | VC-0101, 0102, 0127 |
| `cardiac_history` | `patient` (§7) | `yes` / `no` (병명은 `raw`) | 심장 위험요소·병력 | liposomal doxorubicin 급여 (공고 9장 4나-19) | `cardiac_risk` → D | 25건 |
| `lvef_percent` | `patient` (§7) | 숫자 0~100 | 좌심실 박출률 (심초음파·MUGA) | 공고 p.51 (용어 사전 58행) | `cardiac_risk.detail.lvef_percent` → D | 23건 |
| `mediastinal_radiation` | `patient` (§7) | `yes` / `no` | 종격동 방사선 치료 이력 | liposomal doxorubicin 급여 (공고 9장 4나-19) | `mediastinal_radiation` → D | VC-0104, 0127 |
| `visceral_crisis` | `patient` (§7) | `yes` / `no` | 장기 위기. 의사가 적은 판단만 (A가 수치로 추정하지 않음) | 내분비 + CDK4/6 대신 항암 (ESMO M06·M50) | `visceral_crisis` → C 지침 검색 질의 (`src/rag/retrieve.py`, 전이성일 때) | VC-0126 |
| `comorbidities` | `patient` (§7) | 원문 표기 목록 | 치료 선택에 영향을 주는 동반질환 | 못 쓰는 약 계열 판단 (ESMO M05·M35) | `contraindicated_classes` (의사가 약 계열로 확정) → B·C | VC-0108 |
| `imaging_findings[]` | `fields` (§9) | `{modality, day, date, sites[], certainty, source}` | 영상 검사별 전이 부위와 확정·의심 | 골 보호제 급여 '영상으로 골전이 입증', M 병기 근거 | `bone_metastasis_imaging` (bone + confirmed) → D | 23건 |
| `ongoing` | `treatment_history[]` (§8) | `true` / `false` / `null` | 기준일에 투약 중인지. `end_day` null만으로는 "투약 중"과 "종료 기록 없음"을 못 가름 | 최근 4주 이내 투여 계산(`at_index`), 투여 기간 | `prior_regimens.ongoing`, `recent_therapy_28d` → D | VC-0108 (`true`) |
| `doses[]` (`$defs/dose_entry`) | `treatment_history[]` (§8) | `{drug, per_admin, total, basis, source}` | 모든 약의 1회·총 용량. `basis` `recorded` / `estimated`(1회 × 주기) | 약을 골라 보는 용량 조건 (예: sodium thiosulfate의 cisplatin 1회 100mg/m²·총 300mg/m², liposomal doxorubicin 누적). `anthracycline_drug_dose`는 당분간 유지 | `prior_regimens.doses` (mg/m²로 확정) → D | 아직 없음 (2026-10-23 추가) |
| `molecular.germline.{BRCA1, BRCA2, PALB2}` | `molecular` (§9) | `mutations`와 같은 유전자 칸 | 생식세포 검사(혈액·타액) 결과. `mutations`는 종양 조직·cfDNA | 한 유전자에 생식세포 음성 + 종양 양성처럼 두 결과가 있을 때 gBRCA 조건(PARP 억제제 등)을 바로 판단 | `markers.gBRCA` → B·C·D. 칸이 없으면 B는 지금처럼 `mutations`의 BRCA를 gBRCA로 본다 | VC-0104, 0115, 0116, 0117, 0119 |
| `at_index` {`age`, `recent_therapy_28d`} (2026-10-20) | `fields` (§9) | 객체 (A가 `rules.py at_index`로 계산) | 판정 기준일(`index_day`) 시점 나이와 최근 4주 이내 항암제·호르몬제 투여 | 급여 조건을 일수 계산 없이 읽음 ('만 19세 이상', '65세 이상', zoledronic acid 4주 조건, 공고 Ⅳ) | `age_at_index`, `recent_therapy_28d` → D (`src/recommend/conditions_eval.py`도 읽음) | 모든 출력 (계산) |

함께 바뀐 설명 (값은 그대로): `ptnm`은 수술을 먼저 한 환자만 담는다 (선행요법 뒤 병기는 `yptnm`). `treatment_history[].line` 계산 위치가 `src/input/script/rules.py`로 바뀌었다.

## 1. 최상위 구조

| 항목 | 의미 | 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `schema_version` | 스키마 버전 | 문자열 | 고정 | → `"0.1-draft6"` |
| `patient_ref` | 가명 ID | 문자열 | 비식별화(IN-0). 실제 값은 내부 대응표에만 | `홍길동 (등록번호 12345678)` → `"VC-0001"` |
| `created_at` | 생성 시각 | ISO 8601 | 자동 | → `"2026-10-12T09:00:00+09:00"` |
| `index_day` [draft6] | 판정 기준일 (진단일 = 0). 추천·급여 판정을 하는 '지금' 시점 | 정수 또는 `null` | 해석 (차트 작성일 → 진단일 기준 일수) | 진단 2024-03-05, 진료일 2026-10-16 → `955` |
| `documents[]` | 문서 목록 (IN-1). `doc_type`은 `progress_note` / `pathology` / `molecular` / `medication` / `radiology` (영상 판독, [draft7 후보]) | `{doc_id, doc_type, doc_date}` | 해석 + 사전 | `[병리결과보고서] 2024.03.05` → `{"doc_id":"D1","doc_type":"pathology","doc_date":"2024-03-05"}`, `[영상 판독] 뼈 스캔` → `"radiology"` |
| `conflicts[]` | 같은 시점에 값이 다른 경우 (IN-5) | `{field, candidates[], note}` | 규칙 | `암 3기` vs `cT2N1M0` → `{"field":"stage.group","candidates":[…III…, …IIB…],"note":"적힌 병기와 TNM 계산 병기가 다름"}` |

## 2. 추출값 공통 틀

아래 3~9의 칸은 대부분 이 틀에 담긴다. 예외: `treatment_history[]`, `anthracycline_drug_dose`, `molecular.mutations.*`, `genomic_reports[]`는 각자의 키를 그대로 쓴다.

| 항목 | 의미 | 예시 (원문 "ER(+) 95%") |
|---|---|---|
| `status` | `present`(값 있음) / `not_done`(미시행) / `not_recorded`(기록 없음) | `"present"` |
| `value` | 표준값 | `{"percent": 95}` |
| `raw` | 원문 표기 그대로 | `"ER(+) 95%"` |
| `observed_date` | 검사일·기록일 | `"2024-03-05"` |
| `specimen` [합의 예정] | `primary` / `metastasis` / `cfDNA` / `unknown` | `"primary"` |
| `confidence` | LLM 추출 확신도 0–1 | `0.97` |
| `source` | 원문 근거 (문서 ID, 인용, 문자 위치) | `{"doc_id":"D1","quote":"ER(+) 95%","char_start":120,"char_end":129}` |
| `history[]` [합의 예정, A 결정] | 새 결과에 밀려난 이전 값 (참고용). 항목마다 밀려난 이유 `superseded_reason`을 적는다: `recurrence`(재발 병소 재생검 결과로 대체), `newer_result`(같은 검체의 더 최근 결과로 대체) | `[{"specimen":"primary", "value":{"result":"positive"}, "superseded_reason":"recurrence", …}]` |

### 특수 표기값 [A 결정]

아래 표기는 `value` 안에 그대로 쓴다. 칸 전체가 비어 있으면 `status`로 표시한다.

| 표기 | 의미 | 쓰는 곳 |
|---|---|---|
| `not_assessed` (평가 안됨) | 평가하지 않았거나 평가할 수 없음 | TNM의 TX·NX·MX, 병기군 `Stage X` |
| `[Not Available]` | 그 항목만 기록 없음 | 림프절 수의 한쪽 값 |
| `[Not Applicable]` (해당 없음) | 해당 사항 없음 | 진단 시 전이 없음(M0)일 때 전이 부위 |
| `No value` | 값 없음 | `anthracycline_drug_dose`의 투여 여부·용량·주기 |

평가 안됨·평가 불가는 `not_assessed` 하나로 통합한다 [A 결정].

### 미시행의 세부 표기: "결과 대기"·"예정" [A 결정, 2026-10-19, draft6]

검사를 의뢰했거나 예약했지만 결과가 아직 없으면 `status`는 `not_done`이다 (값이 없으므로). 이때 `raw`에 아래 고정 표기를 넣어 단순 미시행과 구분한다. 원문 문장은 `source.quote`에 남긴다.

| 차트 원문 예 | `status` | `raw` | 뜻 |
|---|---|---|---|
| `gBRCA 검사 의뢰함 (결과 대기)`, `PD-L1 검사 중`, `NGS sent, pending` | `not_done` | `"결과 대기"` | 검사는 했고(검체를 보냄) 결과를 기다림 |
| `PD-L1 22C3 시행 예정`, `다음 외래에 gBRCA 검사 예약` | `not_done` | `"예정"` | 예약됐지만 아직 시행 전 |
| `gBRCA 검사 시행하지 않음`, 언급은 있으나 계획 없음 | `not_done` | 원문 그대로 또는 `null` | 단순 미시행 |
| 언급 없음 | `not_recorded` | — | 기록 없음 |

- 유전자 칸(`molecular.mutations.{유전자}`)도 같은 규칙이다. draft6에서 `raw` 키를 추가했다.
- B는 `raw`가 `"결과 대기"`·`"예정"`이면 검사 권고 대신 "결과 확인 필요"로 낼 수 있다 (B와 확인할 것).

## 3. 진단 (`fields.diagnosis`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `diagnosis_date` | 진단일 | `YYYY-MM-DD` | 해석 | `2024.3.5 조직검사로 진단` → `"2024-03-05"` |
| `histology` | 조직형 | `IDC` / `ILC` / `mucinous` / `metaplastic` / `invasive_NOS` / `other` | 사전 | `침윤성 유관암` → `"IDC"` |
| `grade` | 조직학적 등급 | `1` / `2` / `3` | 사전 + 해석 | `Nottingham grade III (3+3+2=8)` → `3` |

## 4. 병기 (`fields.stage`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `ctnm` | 임상 TNM | `{t, n, m}` | 해석 | `cT2N1M0` → `{"t":"T2","n":"N1","m":"M0"}` |
| `ptnm` | 병리 TNM (수술을 먼저 한 환자) | `{t, n, m, edition}` | 해석 | `pT2 pNX M0, AJCC 7th` → `{"t":"T2","n":"not_assessed","m":"M0","edition":"7th"}` |
| `yptnm` [draft7 후보] | 선행요법 뒤 수술 병리 병기. status `present` = 결과 있음, `not_done` = 선행요법 뒤 아직 수술 전 (`raw` "예정"), `not_recorded` = 수술했지만 병기 기록 없음. 선행요법을 안 받았으면 칸 없음 | `{t, n, m, edition, residual_size_mm, positive_ln, examined_ln}` (y는 빼고 범주만, M은 선행 전 값) | 해석 | `ypT1c ypN1a (2/12), 잔존 침윤암 1.4cm` → `{"t":"T1c","n":"N1a","m":"M0","residual_size_mm":14,"positive_ln":2,"examined_ln":12}` |
| `group` [합의 예정] | 병기군 | `I`, `IA`, `IIA` … `IV` / `not_assessed` | 해석 | `Stage IIA` → `"IIA"` / `Stage X` → `"not_assessed"` |
| `positive_ln_count` [합의 예정] | 양성 림프절 수 / 검사한 수 | `{positive, examined}` | 해석 | `LN 2/15 (+)` → `{"positive":2,"examined":15}` |
| `disease_extent` | 진단 시 병기 범주 | `early` / `locally_advanced` / `metastatic` | 규칙 | `Stage IIB` → `"early"`, `Stage IIIA` → `"locally_advanced"`, `pT2N1M1` → `"metastatic"` |
| `metastatic_sites` | 진단 시 원격 전이 부위 | `bone` / `liver` / `lung` / `brain` / `distant_ln` / `skin` / `other` 목록, 또는 `[Not Applicable]` / `[Not Available]` | 사전 | `간과 뼈에 다발성 전이` → `["liver","bone"]` |
| `operable` [draft5] | 수술 가능 여부 | `yes` / `no` / `unknown` | 사전 | `inoperable, locally advanced` → `"no"` |
| `clinical_size_mm` [draft7 후보] | 치료 전 임상 종양 크기 (영상·촉진 최대 직경) | 숫자 (mm) | 해석 (cm → mm) | `유방 초음파상 3.2cm 종괴` → `32` |
| `pathologic_size_mm` [draft7 후보] | 수술 검체 침윤암 최대 직경 (관내암 제외). 선행요법 뒤 잔존 크기는 여기가 아니라 `yptnm.value.residual_size_mm` | 숫자 (mm) | 해석 (cm → mm) | `invasive tumor size 5.5 x 4.0 cm` → `55` |

TNM·병기군 표기 규칙 [A 결정]:

- 값이 X(TX, NX, MX)이면 `not_assessed` (평가 안됨)
- 차트의 병리 병기는 `ptnm`에 넣는다 (`pT2N1M0`처럼 p가 붙음). 선행요법 뒤 병기는 `yptnm`
- 세부 표기는 공백만 지우고 그대로 둔다 [합의 예정]: `N0 (i-)` → `N0(i-)`, `N0 (i+)` → `N0(i+)`, `N1mi`, `N0 (mol+)` → `N0(mol+)`, `cM0 (i+)` → `cM0(i+)`
- 병기군: `Stage X` → `not_assessed`. `Stage` 뒤의 로마숫자와 A~C를 그대로 쓴다 (`Stage IIA` → `IIA`, `Stage IV` → `IV`)

`disease_extent` 규칙 (사용자 결정 2026-10-13, 2026-10-27 TNM 우선으로 변경. 코드: `src/input/script/pipeline.py`의 `_set_extent`):

- 진단 시 범주다. 재발 후 현재 상태는 B의 `biomarker_record.setting.disease`가 정한다
- 진단 시 TNM으로 계산한다 (AJCC 8판 해부학적 병기표). 진단 시 TNM은 선행요법 환자(`yptnm` 칸이 있거나 선행 투약이 있음)는 `ctnm`, 수술을 먼저 했으면 `ptnm`, 둘 다 아니면 `ctnm`이다. `yptnm`은 쓰지 않는다. M은 `ctnm`·`ptnm` 중 하나라도 M1이면 M1
- M1 → `metastatic`. T4, N2, N3, T3N1 (N1mi 포함) → `locally_advanced` (III기). 그 밖은 `early`. N1mi가 따로 내려가는 것은 T0~T1 N1mi(IB기)뿐이다
- T나 N을 모르면(없음, X) TNM으로 정할 수 없으므로 병기군 구절(I~II → `early`, III → `locally_advanced`, IV → `metastatic`)을 쓴다
- 병기군 구절이 계산값과 다르면 계산값을 쓰고 issues에 확인 요청(`needs_review`)을 남긴다. 차트의 병기군은 AJCC 8판 예후 병기(등급·ER·PR·HER2 반영)일 수 있어 해부학적 병기와 다를 수 있다. `stage.group`에는 차트에 적힌 병기군을 그대로 둔다
- 선행요법 뒤 병기 구절(`ypStage IIA`, `ypT1c ypN1a, stage IIA`)은 `group`·`disease_extent` 후보에서 뺀다. AJCC 8판은 선행요법 뒤 병기군을 매기지 않는다 (post-neoadjuvant prognostic stage는 준비 중). ypT·ypN·잔존 크기·림프절 수는 `yptnm`, pCR·RCB는 `neoadjuvant_response`에 둔다
- 스키마 `disease_extent` 설명("병기군이 없으면 TNM", T3N1 빠짐)은 이 규칙에 맞춰 고칠 제안이다 (4명 검토 전)
- 림프절 세침흡인(FNA)이나 중심부 바늘 생검 양성은 임상 N이다 (AJCC 8판 `cN1(f)`). `ctnm`의 `n`에 넣고 (f)는 지금 버린다

## 5. 수용체 (`fields.receptors`)

| 필드 | 의미 | 표준값 형태 [A 결정] | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `er_percent` | ER 결과 | `percent`, `range`, `allred`, `result` 중 **있는 것을 모두** 한 객체에 | 해석 + 사전 | `ER 강양성 (90-99%)` → `{"range":[90,99],"result":"positive"}` / `ER Allred 6/8 (PS 4, IS 2)` → `{"allred":{"total":6,"ps":4,"is":2}}` |
| `pr_percent` | PR 결과 | ER과 같음. 단 `result`에 `low_positive` 없음 | 해석 + 사전 | `PR 0%` → `{"percent":0}` / `PR 5%, positive` → `{"percent":5,"result":"positive"}` |
| `her2_ihc` | HER2 면역염색 | `score`(+`faint`: IHC 0이면서 10% 이하 세포에 희미한 불완전 막 염색 → `true`, 초저발현)와 `result`를 **있는 것 모두** | 해석 + 사전 | `c-erbB2 2+, SISH 음성` → `{"score":"2+","result":"negative"}` |
| `her2_ish` | HER2 ISH (FISH/SISH/DISH) | `{result, method}` | 해석 + 사전 | `SISH: not amplified` → `{"result":"not_amplified","method":"SISH"}` |
| `pdl1` [draft5] | PD-L1 발현 (면역염색) | `{assay, score_type, score}` | 해석 + 사전 | `PD-L1 (22C3) CPS 12` → `{"assay":"22C3","score_type":"CPS","score":12}` |

`result` 표준값: `positive` / `low_positive` (저발현, **ER만**, 1–10%) / `negative` / `indeterminate` / `unknown` (HER2만)

`allred` 형태: `{total, ps, is}` 중 적힌 것만. total = ps + is (0, 2~8), ps = 비율 점수 0~5, is = 강도 점수 0~3. 차트에 총점만 있으면 `{"total": 6}`.

### ER·PR 규칙 [A 결정]

- ER·PR에는 `score` 키를 두지 않는다 (2026-10-15 결정). 점수는 Allred(`allred.total`, `ps`, `is`)로만 받는다.
- 비율·구간·Allred·판정 중 **있는 것을 모두** 한 객체에 담아 B(BM-2)에 넘긴다. 어느 하나를 고르지 않는다.
- ER과 PR 모두 같은 규칙을 쓴다. 단 `low_positive`는 ER에만 쓴다 (ASCO/CAP 2020의 Low Positive는 ER에만 정의됨) [A 결정].
- 점수는 Allred(`Allred 6/8`, `TS 6`, `PS 4`, `IS 2`)만 `allred`에 담는다. 강도만 적힌 표기(`ER 3+`, `strong`)는 `raw`에만 남긴다. 척도가 적혀 있지 않은 숫자(예: `ER score 6`)는 `raw`에만 남기고 `value`에 넣지 않는다.
- 양성·음성 판정 조건(비율, 구간, Allred)은 B의 BM-2 규칙이다. A의 제안은 [handoff_to_B.md](handoff_to_B.md) §4.

### HER2 IHC 규칙 [A 결정]

1. `score`(0, 1+, 2+, 3+)와 `result`(판정)가 둘 다 있으면 둘 다 넣는다.
2. 판정이 `Equivocal`인데 점수가 없으면 `score: "2+"`를 채운다 (Equivocal의 정의가 IHC 2+).
3. `score`가 `2+`이거나 `result`가 `Equivocal`이면 ISH 결과로 `result`를 보정한다: ISH 음성(not amplified) → `negative`, 양성(amplified) → `positive`, ISH가 없거나 equivocal이고 판정이 `Equivocal`이면 → `unknown`.
4. HER2 복제수·CEP17 복제수·비율은 넣지 않는다.

참고: `score 2+`와 `result negative`가 함께 있으면 B는 HER2 저발현으로 판정할 수 있다. 그래서 B는 `result`보다 `score`를 먼저 읽어야 한다.

### 재발 병소 재생검 수용체 → `value`, 원발 값 → `history[]` [A 결정]

재생검(재발 병소) 결과로 평가하고 처방하므로, 재생검 결과를 `value`로 쓴다. PROJECT.md IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.

- 재발 병소 값을 `value`로 쓴다. `specimen`은 `metastasis`. 변환 규칙은 원발 값과 같다 (ER·PR score 제외, HER2 ISH 보정).
- 원발 조직 값은 `history[]`로 옮기고 `"superseded_reason": "recurrence"`로 재발 때문에 대체되었음을 적는다. `specimen`은 `primary`.
- 재발 병소 값이 없는 마커는 원발 값을 그대로 `value`로 둔다. 예: 재발 병소에서 ER만 검사했으면 PR·HER2는 원발 값.

예 (ER):

```json
"er_percent": {
  "status": "present",
  "value": {"result": "negative"},
  "specimen": "metastasis",
  "raw": "재발 병소 ER Negative",
  "history": [
    {"status": "present", "value": {"range": [90, 99], "result": "positive"}, "specimen": "primary",
     "raw": "ER Positive (90-99%)", "superseded_reason": "recurrence"}
  ]
}
```

## 6. 증식 (`fields.proliferation`)

| 필드 | 의미 | 표준값 형태 [제안] | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `ki67_percent` | Ki-67 지수 | `{percent}` / `{range}` / `{result}` | 해석 + 사전 | `Ki-67 labeling index: 30%` → `{"percent":30}` |

## 7. 환자 (`fields.patient`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `gender` [제안, A 결정] | 성별 | `FEMALE` / `MALE` | 사전 | `F/62` → `"FEMALE"` |
| `age` | 진단 시 나이 | 정수 | 해석 | `F/62` → `62` |
| `menopausal_status` | 폐경 여부 | `premenopausal` / `perimenopausal` / `postmenopausal` / `indeterminate` | 사전 | `폐경 후 상태` → `"postmenopausal"` |
| `ecog` | 전신 수행 상태 | `0`~`4` | 해석 | `ECOG PS 1` → `1` |
| `menopausal_basis` [draft5] | 폐경 판정 근거 | `age_amenorrhea` / `fsh` / `oophorectomy` / `ovarian_radiation` / `hysterectomy` / `unknown` (`ovarian_radiation`·`hysterectomy`는 2026-10-22 추가, 공고 p.48 원문 대조 전) | 사전 | `양측 난소절제술 후` → `"oophorectomy"`, `자궁적출술 후, FSH 68` → `"hysterectomy"` (FSH 값은 `raw`) |
| `cardiac_history` [draft7 후보] | 심장 위험요소·병력 (병명은 `raw`) | `yes` / `no` | 사전 | `HTN, 협심증으로 스텐트 시술` → `"yes"` |
| `lvef_percent` [draft7 후보] | 좌심실 박출률 | 숫자 (%) | 해석 | `Echo: LVEF 62%` → `62` |
| `mediastinal_radiation` [draft7 후보] | 종격동 방사선 치료 이력 | `yes` / `no` | 사전 | `호지킨 림프종으로 종격동 RT (2001)` → `"yes"` |
| `visceral_crisis` [draft7 후보] | 장기 위기. 의사가 적은 판단만 옮김 | `yes` / `no` | 사전 | `visceral crisis 소견` → `"yes"` |
| `comorbidities` [draft7 후보] | 치료 선택에 영향을 주는 동반질환 | 원문 표기 목록 | 그대로 | `간경화 Child B, CKD 4기` → `["간경화 Child B","CKD 4기"]` |
| `height_cm`, `weight_kg` [draft7 후보] | 키, 몸무게 (체표면적 → anthracycline 누적 용량 mg/m²) | 숫자 | 해석 | `Ht 158cm / Wt 55.5kg` → `158`, `55.5` |

- 성별은 범위 외 판정(남성 유방암)에 쓰인다
- 폐경 여부는 적힌 것만 옮긴다. 마지막 생리일(LMP)만 있으면 계산하지 않고 `raw`에 남긴다
- `KPS 90`처럼 다른 척도는 ECOG로 바꾸지 않는다

## 8. 치료 이력 (`fields.treatment_history[]`)

항목 하나가 투약 기록 하나다. 원본 한 기록에 약이 여러 개면(AC 등) 한 항목에 여러 약이 들어간다. 여러 기록을 한 요법으로 묶고 차수를 매기는 일은 A가 변환할 때 한다 (`src/input/script/rules.py`, handoff_to_B.md §6.2) [2026-10-16 변경, draft6].

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `drugs` | 약제 목록 | 일반명 소문자 목록 | 사전 (`drug_names.csv` + 요법 약어 사전) | `AC #4` → `["doxorubicin","cyclophosphamide"]` |
| `setting` | 치료 단계 | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | 사전 | `수술 전 항암` → `"neoadjuvant"` |
| `start_date` | 시작일 | `YYYY-MM-DD` | 해석 | `'25.1.10부터` → `"2025-01-10"` |
| `end_date` | 종료일 | `YYYY-MM-DD` 또는 `null` | 해석 | `2026.6.20 중단` → `"2026-06-20"` |
| `start_day`, `end_day` [draft5] | 시작일·종료일 (진단일 = 0) | 정수 또는 `null` | 해석 (날짜 → 진단일 기준 일수) | 진단 2024-03-05, 시작 2024-04-04 → `30` |
| `duration_days` [제안, A 결정] | 투여일 (일) | 정수 또는 `null` | 해석 | `2025.1.10 ~ 2025.3.10` → `59` |
| `cycles` [draft5] | 주기 수와 주기 길이 | `{value, basis, interval_days, interval_basis}` 또는 `null` | 해석 | `AC q3w #4` → `{"value":4,"basis":"recorded","interval_days":21,"interval_basis":"recorded"}` |
| `progression_day` [draft5] | 진행일 (진단일 = 0) | 정수 또는 `null` | 해석 | `2026.3 CT상 PD` → 진단일 기준 일수 |
| `doses[]` [draft7 후보] | 약별 용량. `drugs`의 약마다 하나. 급여 조건이 약을 골라 1회·누적 용량을 볼 때 (cisplatin, anthracycline 등) | `{drug, per_admin, total, basis, source}`. 용량은 `{value, unit}` 또는 `"No value"`, `basis`는 `recorded` / `estimated`(1회 × 주기) | 해석 | `DP: docetaxel 75mg/m2 + cisplatin 75mg/m2 q3w #4` → `[{"drug":"cisplatin","per_admin":{"value":75,"unit":"mg/m2"},"total":{"value":300,"unit":"mg/m2"},"basis":"estimated"}, …]` |
| `ongoing` [draft7 후보] | 기준일에 투약 중인지. `end_day` null만으로는 "투약 중"과 "종료 기록 없음"을 가를 수 없어 둔다 | `true` / `false` / `null`(모름) | 사전 | `현재 키스칼리·페마라 복용 중` → `true` (`end_day`는 `null`) |
| `stop_reason` | 중단 사유 | `progression` / `toxicity` / `completed` / `planned_switch` / `maintenance` / `other` | 사전 | `PD로 중단` → `"progression"` |
| `best_response` | 최선 반응 | `CR` / `PR` / `SD` / `PD` / `unknown` | 사전 | `완전관해` → `"CR"` |
| `line`, `endocrine_line`, `chemo_line` [draft6] | 전이 후 전체 차수, 고식적 내분비 차수, 고식적 항암 차수 (간주 규칙 없음) | 정수 또는 `null` | 계산 (`rules.py`) | 전이 후 letrozole → paclitaxel → `1/1/null`, `2/null/1` |
| `source` | 원문 근거 | 공통 틀과 같음 | — | `{"doc_id":"D3","quote":"AI + palbociclib, PD"}` |

## 9. 선행요법 반응, 재발, 기준일 값, 영상 소견, 유전자 보고서

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `neoadjuvant_response.pcr` | 병리적 완전관해 | `yes` / `no` | 사전 | `pCR 달성` → `"yes"` |
| `neoadjuvant_response.rcb` | 잔존암 부담 등급 | `RCB-0` / `RCB-I` / `RCB-II` / `RCB-III` | 사전 + 해석 | `RCB class II (index 2.1)` → `"RCB-II"` |
| `recurrence.recurrence_date` | 재발일 | 날짜 | 해석 | `2026년 6월 간 전이로 재발` → `"2026-06"` [제안: 부분 날짜] |
| `recurrence.adjuvant_endocrine_end_date` | 보조 내분비요법 종료일 | 날짜 | 해석 | `타목시펜 5년 복용 후 2023.3 종료` → `"2023-03"` |
| `recurrence.status`, `metastatic_sites`, `metastasis_day`, `surgery`, `surgery_intent`, `later_distant` [draft5] | 재발 상태, 재발 전이 부위, 전이 기준일, 재발 후 수술 | handoff_to_B.md §3.1 | 사전 + 해석 | `2026.6 간 전이 재발` → `status: distant`, `metastatic_sites: ["liver"]` |
| `recurrence.recurrence_day` [draft6] | 첫 재발일 (국소·원격, 진단일 = 0). 진단 시 IV기는 넣지 않음 | 정수 | 해석 | `2026.6 흉벽 재발` → 진단일 기준 일수 |
| `deemed_lines[]` [draft6] | 심평원 차수 간주 규칙 4개의 충족 여부 | `{rule_id, category, status, basis, regimen_refs, gap_days, notice_page}` | 계산 (`rules.py`) | 보조 AC → paclitaxel 후 전이 → `DEEM-ANTHRA-TAXANE: met` |
| `at_index` [draft7 후보, 2026-10-20] | 기준일 시점 값. `age`(기준일 나이 = 진단 시 나이 + `index_day` ÷ 365.25의 몫), `recent_therapy_28d`(최근 4주 이내 항암제·호르몬제 투여 `{status, basis, regimen_refs, gap_days}`, 보조약·골 보호제 제외) | 객체 | 계산 (`rules.py at_index`: `index_day`, 진단 시 나이, `treatment_history[]`) | `index_day` 1000, letrozole `end_day` 980 → `{"status":"yes","gap_days":20,…}` |
| `anthracycline_drug_dose` [draft5] | anthracycline 투여 여부와 약별 용량 | `{administered, drugs[]}` | 해석 | `doxorubicin 60 mg/m2 #4` → `{"drug":"doxorubicin","dose_per_admin":{"value":60,"unit":"mg/m2"}, …}` |
| `molecular.mutations.{유전자}` [draft5] | 유전자별 변이 (ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2) | `{status, result, variants[], specimen}` | 해석 | `PIK3CA H1047R, VAF 31%` → `{"status":"present","result":"detected","variants":[…]}` |
| `imaging_findings[]` [draft7 후보] | 영상 소견 (골전이 영상 입증, M 병기 근거) | `{modality, day, date, sites[], certainty, source}` | 해석 + 사전 | `Bone scan: 척추·골반 다발성 골전이` → `{"modality":"bone_scan","sites":["bone"],"certainty":"confirmed"}` |
| `molecular.germline.{BRCA1, BRCA2, PALB2}` [draft7 후보] | 생식세포 검사 (혈액·타액) 결과. `mutations`는 종양 조직·cfDNA. 한 유전자에 두 결과가 있을 수 있어 칸을 나눈다 | `mutations`와 같은 `{status, result, variants[]}` | 해석 | `혈액 BRCA1/2 유전자 검사: 병원성 변이 없음` → `BRCA1`·`BRCA2` `{"status":"present","result":"not_detected","variants":[]}` |
| `genomic_reports[].specimen` | 검체 | `primary` / `metastasis` / `cfDNA` / `unknown` | 사전 | `혈장 cfDNA NGS` → `"cfDNA"` |
| `genomic_reports[].report_date` | 보고일 | `YYYY-MM-DD` | 해석 | `보고일 2026-07-01` → `"2026-07-01"` |
| `genomic_reports[].raw_text` | 보고서 원문 | 문자열 | **그대로** | `ESR1 p.Y537S detected, VAF 4.2%` → 그대로 |

- 유전자 보고서(`genomic_reports`)는 검체와 날짜만 정리하고 원문은 손대지 않는다. 변이의 의미 판정은 B의 BM-2·BM-3
- pCR은 명시된 경우만 옮긴다. `ypT0 ypN0`처럼 병기만 있으면 병기만 저장한다

## 10. B와 합의할 항목

A가 받아들인 제안과 A 결정이다. 2026-10-12에 `schemas/patient_state.json` 0.1-draft3로 모두 반영했다. B 검토 후 `0.1`로 확정한다.

| 항목 | 상태 |
|---|---|
| 수용체 `value`: `percent`/`range`/`allred`/`result` 중 있는 것을 모두 한 객체에 (ER·PR `score`는 2026-10-15 삭제). `result`에 `low_positive` 추가 (ER만) | A 결정, 스키마 반영 (0.1-draft3) |
| `allred`를 `{total, ps, is}` 객체로 | A 결정, 스키마 반영 (0.1-draft3) |
| ER·PR·HER2 판정 조건 (BM-2) | A 제안 → B 결정. handoff_to_B.md §4 |
| ER·PR `score` 키 삭제 (Allred 총점·강도와 중복) | 2026-10-15 결정, 스키마 반영 |
| HER2 IHC `{score, faint}` + `{result}` 동시 표기, ISH로 `result` 보정 | A 결정. B는 score를 먼저 읽는다 |
| `her2_ish`는 `{result, method}`만 (복제수·비율 제외) | A 결정 |
| `specimen`, `history[]`(`superseded_reason`: `recurrence` / `newer_result`) 추가 | 스키마 반영 (0.1-draft3) |
| 재발 병소 재생검 결과를 `value`로, 원발 값을 `history[]`로 (IN-4와 같음) | A 결정 |
| `stage.group`, `stage.positive_ln_count` 추가 | 스키마 반영 (0.1-draft3) |
| `patient.gender` 추가 | 스키마 반영 (0.1-draft3) |
| `treatment_history[].duration_days` 추가 | 스키마 반영 (0.1-draft3) |
| 특수 표기값 `not_assessed`, `[Not Available]`, `[Not Applicable]`을 `value`에 허용 | A 결정 (평가 안됨·불가 통합) |
| `stop_reason` 표준값 목록 | 스키마 반영 (0.1-draft3) |
| 부분 날짜(`YYYY-MM`, `YYYY`) 허용 | 스키마 반영 (0.1-draft3) |
| `stage.disease_extent` 추가 (I~II 조기, III 국소 진행성, IV 전이성) | 사용자 결정 (2026-10-13), 스키마 반영 (0.1-draft4) |
| 상대 일수(진단일 = 0) `start_day`·`end_day`·`metastasis_day` | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `treatment_history[].cycles` (`value`, `basis`, `interval_days`, `interval_basis`), `progression_day`, `stop_reason`에 `planned_switch`·`maintenance` | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `anthracycline_drug_dose` (투여 여부, 약별 1회 용량·주기·총 투여량. 범위 용량은 최대값, 값이 없으면 `No value`) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `recurrence.status`, `metastatic_sites`, `metastasis_day`, `surgery`, `surgery_intent`, `later_distant` | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `receptors.pdl1` (발현: 검사법, 점수 종류, 점수. 판정은 B) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `molecular.mutations` 유전자별 (ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2): 변이 있음 / 변이 없음 / 미시행 | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `stage.operable`, `patient.menopausal_basis` (가상 차트용) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| 차수(line)는 정답에 넣지 않고 B가 `start_day`·`metastasis_day`로 판단 | 협의 완료 (2026-10-15). handoff_to_B.md §6.2 |
| `treatment_history`는 투약 기록 하나 = 항목 하나. 같은 날 시작한 별도 기록·중복 기록을 묶지 않음 (요법 묶음은 B) | 사용자 결정 (2026-10-15) |
| ER 판정: Allred 총점 우선 (0~2 음성, 3~4 저발현, 5는 비율로 가름, 6~8 양성). HER2 `faint` = IHC 0 + 10% 이하 세포의 희미한 불완전 막 염색 | 사용자 결정 (2026-10-15). handoff_to_B.md §4.1·§4.4 |
| `at_index` (`age`, `recent_therapy_28d`) | draft7 후보 (2026-10-20), 4명 검토 전 |
| `doc_type` `radiology`, `stage.yptnm`·`clinical_size_mm`·`pathologic_size_mm`, `patient.height_cm`·`weight_kg`, `menopausal_basis`의 `ovarian_radiation`·`hysterectomy`, `treatment_history[].ongoing`, `molecular.germline` | draft7 후보 (2026-10-22, 가상 차트용), 4명 검토 전. `ptnm`은 수술을 먼저 한 환자만 |
| 한계 조항을 없애는 칸: `patient.cardiac_history`·`lvef_percent`·`mediastinal_radiation`·`visceral_crisis`·`comorbidities`, `fields.imaging_findings[]` | draft7 후보 (2026-10-22), 4명 검토 전 |
| `treatment_history[].doses[]` (모든 약의 1회·총 용량). `anthracycline_drug_dose`는 당분간 유지 | draft7 후보 (2026-10-23), 4명 검토 전 |

2026-10-27 TCGA 정답 세트 폐기, 평가는 가상 차트로. TCGA 정답 규칙과 건수는 git 이력에 있다.
