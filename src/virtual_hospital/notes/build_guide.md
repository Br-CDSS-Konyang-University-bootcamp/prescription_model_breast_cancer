# 가상환자 데이터를 만든 규칙과 코드 (안내)

작성: 2026-11-18 (A) · 코드: `src/virtual_hospital/` · 데이터: `data/virtual_hospital/` (2026-11-18 별도 저장소 `virtual_hospital`에서 옮김)

TCGA-BRCA와 BCNB의 실제 값을 뼈대로, 빈칸만 근거 있는 규칙으로 채운 가상 병원 환자다. 이 문서는 **어떤 규칙 문서와 어떤 코드로 만들었는지**를 한곳에 모은 안내다. 규칙 하나하나의 내용은 아래 규칙 문서에 있다.

## 1. 만든 것

| 갈래 | 인원 | 장면 (판정 기준일) | 차트 문서 | 위치 |
|---|---|---|---|---|
| TCGA ① 수술 후 | 671 | 실제 첫 보조 투약일과 49일 중 빠른 날 → "보조 전신 요법 결정" | 외래 경과기록, 수술 병리, 분자병리 | `data/virtual_hospital/tcga/` |
| TCGA ② 재발 | 9 | 실제로 다음 고식 치료를 정한 날 → "고식 내분비 2차 결정" 3, "고식 항암 1차 결정" 6 | ① + 재발 경과기록, 투약 기록 | `data/virtual_hospital/tcga_recur/` |
| BCNB 수술 전 | 971 | 초진일 → 선행요법 여부 결정 | 초진 기록, 중심 생검 병리, 유방 초음파 | `data/virtual_hospital/local/bcnb/` (약관상 공개 안 함) |

원칙
- **실제 값 먼저.** 없는 값만 합성하고, 합성 근거 순위는 ① 같은 환자 계산 → ② 같은 데이터 안 분포 → ③ 같은 환자 대리 지표 → ④ 문헌 → ⑤ 고정값
- **처방 모듈 규칙을 지킨다.** 합성값을 mini 규칙으로 판정해도 원래 실제 판정과 같아야 하고, mini 입력 모듈이 차트를 읽어 정답을 다시 만들 수 있어야 한다 (관문 G7). mini 코드는 고치지 않는다
- **결정 시점마다 차트.** 차트에는 판정 기준일 전에 일어난 일만 쓰고, 그날 시작한 약부터는 정답 표에만 둔다
- **실제 처방 기록은 참고용이다.** 2000년대 미국 처방이라 정답이 아니다

## 2. 규칙 문서

| 파일 | 내용 |
|---|---|
| [../rules/rules.csv](../../../data/virtual_hospital/rules/rules.csv) | **규칙 원본 69개.** 규칙마다 id, 묶음, 설명, 갈래, 입력 열, 출력 칸, 근거, 출처, 예, 상태(확정 15·제안 53·폐기 1), 결정일. 코드와 출력의 `rule_id`가 모두 이 표에 있어야 한다 (테스트) |
| [../rules/references.csv](../../../data/virtual_hospital/rules/references.csv) | 합성에 쓴 문헌 값 12행 (Ki-67, grade, ECOG, 겨드랑이 초음파). 값, 출처, 표 번호, 확인일 |
| [../rules/thresholds.csv](../../../data/virtual_hospital/rules/thresholds.csv) | 판정 경계 금지 구간 6개 (예: ER 1~10%, Ki-67 15~25%). 합성값이 경계에 걸려 판정이 흔들리지 않게 |
| [../rules/phrases.csv](../../../data/virtual_hospital/rules/phrases.csv) | 차트 표기 22개 (mini 가상 차트·field_vocab 표기) |
| [../rules/image_tables.csv](../../../data/virtual_hospital/rules/image_tables.csv) | 이미지·모듈 결과를 받을 표의 틀 (주석, 실행, 예측, 타일 격자, 점수, 그림) |
| [synthetic_criteria.md](synthetic_criteria.md) | **칸별로 어떻게 채웠는지** 사람이 읽는 정리 (실제 값을 바꾼 것, 합성한 것, 뺀 것, 재발 갈래, 문헌 값) |
| [progress.md](progress.md) | 날짜순 진행 기록과 사용자 결정 |
| [bcnb_check.md](bcnb_check.md) | BCNB 원자료 점검 |
| [mini_findings.md](mini_findings.md) | mini 처방 모듈 점검 (읽기만) |
| [module_result_format_proposal.md](module_result_format_proposal.md) | 이미지 모듈 결과 형식 제안 (팀 합의 전) |
| [design.md](design.md) | 설계 전체 (§4 규칙 체계, §5 시점, §6 칸별 규칙, §9 CSV·chart.txt, §10 이미지, §11 검증·관문) |
| [../README.md](../README.md) | 지금 상태, 폴더 구조, 만드는 순서, 가상 병원 DB, 데이터 출처와 인용 |
| `data/virtual_hospital/tcga/NOTICE.md` | 조직학적 등급 판독 자료(Thennavan 2021)의 출처·라이선스·합성 표시 |

### 규칙 묶음

| 묶음 | id | 개수 | 하는 일 |
|---|---|---|---|
| 고르기 | S-, S-B, S-R | 13 | 환자 고르기와 제외 (선행요법, IV기, 원자료 모순, 첫 투약이 병리 보고 전 등) |
| 옮기기 | M- | 5 | 실제 값을 칸으로 (mini TCGA 변환기, 변이 c. 표기, 실제 병리 판독 등급) |
| 계산 | D-, D-B, D-R | 22 | 같은 환자 실제 값에서 계산 (MX → M0, Allred 점수, 판정 기준일, 중단 사유, 진행일 등) |
| 합성 | Y-, Y-B | 10 | 없는 값 만들기 (HER2 점수·FISH, Allred 강도, ER·PR 구간, Ki-67, 판독 없는 grade, ECOG, 폐경, 초음파 cN) |
| 결측 | N- | 5 | 쓸 수 없는 값의 처리 (줄을 쓰지 않음, 미시행 표기) |
| 표기 | R- | 10 | chart.txt 문장 형식 |
| 관문 | G- | 2 | mini 규칙 검사 |
| 이미지 | I- | 2 | 슬라이드·주석 좌표 |

## 3. 코드 (`src/virtual_hospital/scripts/`, 모두 `team_project` 폴더에서 `python -m src.virtual_hospital.scripts.<이름>`)

### 3.1 만들기

| 파일 | 하는 일 | 쓰는 규칙 | 결과 |
|---|---|---|---|
| `common.py` | 경로, 규칙 표 읽기, vp 번호로 정한 난수, `Rec`(칸 하나)·`Patient` | — | — |
| `tcga_convert.py` | TCGA 크롭본 → patient_state. 입력 모듈의 옛 TCGA 변환기(`src/input/script/tcga/tcga_to_patient_state.py`) 사본, 입력은 `data/virtual_hospital/source/` (그 변환기와 `data/tcga_brca/`가 정리돼도 가상 병원은 다시 만들 수 있게) | M-01 | patient_state 목록 |
| `tcga.py` | TCGA ① 고르기 → 옮기기 → 계산 → 합성. mini TCGA 변환기(`convert`)를 불러 씀 | S-02~S-10, M-01~M-05, D-01~D-11, Y-01~Y-07, N- | `Patient` 목록 |
| `render.py` | 칸 → chart.txt + 정답 `patient_state` (mini `Chart`·`F`를 그대로 씀). 투약 기록 표 포함 | R-01~R-07 | 차트 글, 정답 |
| `gates.py` | 관문 G1~G7: 칸 일치, 표기, 범위, 서로 맞는지, 경계, 실제 값 범위, B 판정 + mini 입력 모듈 재현 | G- | 통과 여부 |
| `verify.py` | 검증 V1~V6: 실제 값 복사, 계산, 분포, 관계, 이미지 좌표 (생성기와 다른 코드로 다시 읽음) | — | `data/virtual_hospital/reports/` |
| `build.py` | **TCGA ① 실행.** 위를 묶어 세트를 만들고 저장 | — | `data/virtual_hospital/tcga/`, `data/virtual_hospital/reports/`, `data/virtual_hospital/local/source_map.csv` |
| `tcga_recur.py` | **TCGA ② 실행.** 원격 재발 환자의 결정 시점 차트 (실제 투약 기록, 중단 사유) | S-R1, D-R1~D-R5, R-05~R-07 | `data/virtual_hospital/tcga_recur/` |
| `bcnb.py` | **BCNB 실행.** 고르기부터 검증까지 (Allred는 TCGA 분포 사용) | S-B, D-B, Y-B, I-02 | `data/virtual_hospital/local/bcnb/` |
| `confirmed.py` | **확정 상태 초안.** 정답 patient_state + biomarker_record → mini `build_draft` 기본값 (화면 1에서 그대로 확정한 것과 같음) | — | `<차트>/expected/confirmed_state.json`, `data/virtual_hospital/reports/confirmed.md` |
| `embed_slides.py` | 타일 벡터 `.h5` → 슬라이드 벡터 (종양 타일 평균, 없으면 전체 평균). GPU 서버에서 파일 하나만 복사해 돌림 | — | `data/virtual_hospital/local/features/<묶음>_hoptimus0.npz` |
| `db.py`, `db_schema.sql` | **가상 병원 DB.** 위 결과와 슬라이드 벡터를 SQLite 한 파일로 (`build`, `info`) + 읽기 함수 (README "가상 병원 DB") | — | `data/virtual_hospital/local/virtual_hospital.db` |

### 3.2 자료 받기

| 파일 | 하는 일 | 결과 |
|---|---|---|
| `fetch_hgvsc.py` | 변이 c. 표기를 GDC 공개 API, 없으면 Genome Nexus에서 (M-03) | `data/virtual_hospital/tcga_hgvsc.csv` |
| `fetch_thennavan.py` | 조직학적 등급 판독 점수 (Thennavan 2021 Data S2)를 Europe PMC에서 (M-05) | `data/virtual_hospital/local/thennavan2021/mmc3.xlsx` (CC BY-NC-ND, git 제외) |

### 3.3 점검·시험

| 파일 | 하는 일 | 결과 |
|---|---|---|
| `bcnb_check.py` | BCNB 원자료 점검 (개수·ID만, 라벨은 안 찍음) | 화면 출력 |
| `mini_probe.py` | 만든 정답을 mini B `assess`와 화면 1 초안에 넣어 봄 (읽기만) | `data/virtual_hospital/reports/mini_probe.md` |
| `llm_run.py` | 차트를 mini 입력 모듈 LLM으로 끝까지 돌리고 mini 채점기로 채점 (GPU 터널 필요) | `data/virtual_hospital/local/llm_runs/<이름>/` |
| `tests/virtual_hospital/test_virtual_hospital.py` | 규칙 id가 표에 있는지, 다시 만들면 같은지, BCNB가 `data/virtual_hospital/local/`에만 있는지 등 9개, `test_db.py` DB 6개 | `python -m pytest tests/virtual_hospital` |

### 3.4 실행 순서

```bash
python -m src.virtual_hospital.scripts.fetch_hgvsc        # 처음 한 번 (build를 먼저 한 번 돌려 data/virtual_hospital/local/source_map.csv가 있어야 함)
python -m src.virtual_hospital.scripts.fetch_thennavan    # 처음 한 번
python -m src.virtual_hospital.scripts.build              # TCGA ①
python -m src.virtual_hospital.scripts.tcga_recur         # TCGA ②
python -m src.virtual_hospital.scripts.bcnb               # BCNB (data/virtual_hospital/local/bcnb_raw/ 필요)
python -m src.virtual_hospital.scripts.confirmed          # 확정 상태 초안 (build가 차트 폴더를 새로 만드므로 마지막에)
python -m src.virtual_hospital.scripts.db build           # 가상 병원 DB (위 결과 + local/features/)
python -m pytest tests/virtual_hospital
```

실행은 team_project 폴더에서. 필요한 것: 같은 상위 폴더의 `team_project_final`(모듈 1 MKI67 발현, 슬라이드 목록), `team_project` conda 환경. BCNB는 원자료를 `data/virtual_hospital/local/bcnb_raw/`에.

## 4. 원자료

| 자료 | 쓰는 것 | 인용·약관 |
|---|---|---|
| TCGA-BRCA (mini 크롭본, GDC, cBioPortal) | 병리, 병기, 수용체, 변이, 투약, 재발, 생존 | README "데이터 출처와 인용" |
| Thennavan 2021 Data S2 | 조직학적 등급 판독 점수 | CC BY-NC-ND 4.0, `data/virtual_hospital/tcga/NOTICE.md` |
| GDC·Genome Nexus | 변이 c. 표기 | `data/virtual_hospital/tcga_hgvsc.csv` |
| BCNB | 수술 전 갈래 전체 | 원본·수정본 재배포 금지 → `data/virtual_hospital/local/`에만 |
| 문헌 (KBCR 등) | 합성 비율 | `data/virtual_hospital/rules/references.csv` |

## 5. 처방 모듈에서 쓰는 파일

처방 흐름은 차트마다 `expected/confirmed_state.json`을 입력으로 쓰고(C 검색 → B 추천 → D 급여), 처음부터 돌릴 때는 `chart.txt`를 입력 모듈에 넣는다.

```
data/virtual_hospital/
├── tcga/                        TCGA ① 671명
│   ├── NOTICE.md
│   ├── patients.csv  truth.csv  fields.csv  images/
│   └── charts/<VH-T…>/chart.txt, expected/{patient_state, biomarker_record, confirmed_state}.json
├── tcga_recur/                  TCGA ② 9명
│   ├── patients.csv  truth.csv  fields.csv  treatments.csv
│   └── charts/<VH-T…>/…  (위와 같음)
└── local/bcnb/                  BCNB 971명 (git 제외, 같은 구성)
```

| 파일 | 처방 모듈에서 |
|---|---|
| `chart.txt` | 입력 모듈 입력 (처음부터 시험할 때) |
| `expected/confirmed_state.json` | C 지침 검색·B 추천·D 급여 입력 |
| `expected/patient_state.json` | 입력 모듈 채점 정답, 화면 1 |
| `expected/biomarker_record.json` | B 판정 채점 정답 |
| `patients.csv` | 판정 기준일, 재발 갈래 장면 |
| `truth.csv` | 실제 처방 기록(참고용, 정답 아님), 생존, PAM50 |
| `fields.csv` | 칸마다 실제·계산·합성 출처 (합성 값 때문인지 가려낼 때) |
| `treatments.csv` | 재발 갈래 요법별 중단 사유와 근거, 차수 |

주의
- **BCNB는 git에 올리지 않는다.** 약관상 수정본도 재배포할 수 없다. `data/virtual_hospital/local/`은 `.gitignore`로 빠진다. BCNB가 필요한 조원은 원자료를 받아 직접 만든다
- `guideline.json`(C 지침 검색 정답)은 없다. mini 가상 차트(`tests/fixtures/virtual_charts/`)와 달리 C 검색 결과를 정답으로 채점할 수 없다
- 조직학적 등급은 Thennavan 2021 판독(CC BY-NC-ND 4.0)에서 왔다. 출처와 합성 표시는 `tcga/NOTICE.md`
