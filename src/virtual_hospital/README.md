# 가상 병원 환자 (virtual_hospital) — TCGA·BCNB 기반 가상 병원 DB

> A virtual hospital environment built on synthetic breast cancer patients derived from the TCGA-BRCA and BCNB datasets.

작성: 2026-11-09 (A) · 갱신: 2026-11-19. 2026-11-18까지는 별도 저장소(`seonjinj0616-cyber/virtual_patient_database_based_TCGA_and_BCNB`)에서 만들었고, 그 저장소 작업은 끝났다. 이후 작업은 이 폴더에서 한다. 그동안 한 일: [notes/progress.md](notes/progress.md)

TCGA-BRCA와 BCNB의 실제 값을 뼈대로, 데이터에 없는 칸만 근거 있는 규칙으로 채운 가상 유방암 환자다. 처방 모듈(입력 → 바이오마커 → 확정 → 지침 검색·추천·급여)을 실제 슬라이드가 붙은 환자로 끝까지 돌려 보려고 만들었다.

## 지금 상태 (2026-11-19)

| | TCGA ① 수술 후 | TCGA ② 재발 | BCNB 수술 전 |
|---|---|---|---|
| 가상환자 | **671명** | **9명** (원격 재발 13명 중) | **971명** (1,058명 중) |
| 장면 (판정 기준일) | 실제 첫 보조 투약일과 수술 후 49일 중 빠른 날 → 보조 요법 결정 | 실제로 다음 고식 치료를 정한 날 → 내분비 2차 결정 3, 항암 1차 결정 6 | 초진일 → 선행요법 여부 결정 |
| 차트 | 외래 경과기록 + 수술 병리 + 분자병리 | ① + 재발 경과기록 + 투약 기록 | 초진 기록 + 중심 생검 병리 + 유방 초음파 |
| 위치 | `data/virtual_hospital/tcga/` | `data/virtual_hospital/tcga_recur/` | `data/virtual_hospital/local/bcnb/` (**git 제외**, BCNB 약관) |

- 검증 V1~V4·V6, 관문 G1~G7 (입력 모듈 재현 포함) 통과. 모든 차트에 확정 상태 초안 `expected/confirmed_state.json`이 있다
- 처방 흐름 시험 (2026-11-18, 49명): 모두 오류 없이 끝까지 돌았다. 고칠 거리 8가지는 [notes/progress.md](notes/progress.md) §3
- 입력 모듈 LLM 시험 (qwen3:14b, 59명): 필드 정확도 98.8%
- 가상 병원 DB (SQLite 한 파일, 아래 "가상 병원 DB"): 환자·차트·정답 JSON·슬라이드·BCNB 주석·슬라이드 벡터 1,634장을 한곳에서 읽는다

## 원칙

- **실제 값 먼저.** 없는 값만 합성하고 칸마다 `real` / `derived` / `synthetic`과 거친 규칙 id를 남긴다. 합성 근거 순위: ① 같은 환자 계산 → ② 같은 데이터 안 분포 → ③ 같은 환자 대리 지표 → ④ 문헌 → ⑤ 고정값
- **처방 모듈을 고치지 않는다.** 생성기가 처방 모듈 입력 규칙에 맞추고, 실제 값이 못 맞추면 그 환자를 뺀다. 이 폴더는 입력 모듈 규칙, B `assess`, 화면 1 초안 코드를 불러 쓰기만 한다
- **결정 시점마다 차트.** 차트에는 판정 기준일 전에 일어난 일만 쓰고, 그날부터의 값(수술 림프절, 이후 투약, 생존)은 `truth.csv`에만 둔다
- **실제 처방 기록은 참고용이다.** 2000년대 미국 처방이라 정답이 아니다. 처방이 맞는지는 `tests/fixtures/virtual_charts/`로 본다
- **BCNB에서 나온 것은 git에 올리지 않는다.** 약관상 수정본도 재배포할 수 없어서 각자 원자료를 받아 직접 만든다

## 폴더 구조

```
src/virtual_hospital/                 ← git: 코드와 문서
├── README.md                         이 문서
├── common.py                         경로, 규칙 표 읽기, vp 번호로 정한 난수
├── tcga_convert.py · tcga.py         TCGA → patient_state, 고르기·옮기기·계산·합성
├── render.py · gates.py · verify.py  chart.txt, 관문 G, 검증 V
├── build.py · tcga_recur.py · bcnb.py · confirmed.py   만들기 (아래 "만드는 순서")
├── fetch_hgvsc.py · fetch_thennavan.py                 자료 받기
├── bcnb_check.py · mini_probe.py · llm_run.py          점검·시험
├── embed_slides.py                   타일 벡터 .h5 → 슬라이드 벡터 .npz (GPU 서버에서, numpy·h5py만)
├── db_schema.sql                     가상 병원 DB 표 정의
├── db.py                             DB 만들기 + 읽기 함수
└── notes/                            설계·기준·기록 (아래 "문서")

data/virtual_hospital/
├── rules/                            ← git: rules.csv(규칙 원본), references.csv(문헌 값),
│                                        thresholds.csv, phrases.csv, image_tables.csv
├── source/                           ← git: TCGA 크롭본·병합본 CSV (tcga_convert.py 입력)
├── tcga_hgvsc.csv                    ← git: 변이 c. 표기 (fetch_hgvsc가 만듦)
├── tcga/, tcga_recur/                ← git: patients·fields·truth(·treatments).csv, NOTICE.md,
│   │                                    images/(이미지 표 틀), charts/<VH-T…>/
│   └── charts/<VH-T…>/chart.txt, expected/{patient_state, biomarker_record, confirmed_state}.json
├── reports/                          ← git: 생성 보고, 뺀 환자, 관문 결과, confirmed.md
└── local/                            ← git 제외
    ├── bcnb_raw/                     BCNB 원자료 37GB (각자 받음: WSIs/, patient-clinical-data.xlsx)
    ├── bcnb/                         BCNB 차트·정답·이미지 표 (각자 만듦, tcga/와 같은 구성)
    ├── reports/                      BCNB 보고, 처방 흐름 시험 결과 (vh_flow_runs_2026-11-18/)
    ├── source_map.csv · slide_map.csv   가상 번호 ↔ 원본 ID·슬라이드
    ├── mutations.tsv                 cBioPortal 변이 (fetch_hgvsc 입력)
    ├── thennavan2021/                등급 판독 원본 (CC BY-NC-ND, fetch_thennavan이 받음)
    ├── llm_runs/                     입력 모듈 LLM 시험 결과
    ├── features/                     슬라이드 벡터 tcga_hoptimus0.npz · bcnb_hoptimus0.npz
    │   └── <묶음>/<파일>.h5          타일 벡터 (보통 GPU 서버에만, 필요할 때 받음)
    └── virtual_hospital.db           각자 만드는 DB 한 파일 (약 56MB)

tests/virtual_hospital/               ← git
├── test_virtual_hospital.py          규칙 id ↔ 표, 다시 만들면 같은지, BCNB가 local/에만 있는지
└── test_db.py                        DB (BCNB·벡터가 없으면 그 검사만 건너뜀)
```

`.gitignore`: `data/` 안은 원래 csv·txt·py만 올리지만, `data/virtual_hospital/` 아래는 json·md도 올리고 `local/`은 뺀다.

## 만드는 순서

`team_project` 폴더에서 `team_project` 환경으로 실행한다. 같은 상위 폴더에 `team_project_final`(모듈 1: MKI67 발현, 슬라이드 QC·썸네일)이 있어야 한다.

| 단계 | 명령 | 읽는 것 | 만드는 것 | 언제 |
|---|---|---|---|---|
| 0 | `python -m src.virtual_hospital.fetch_thennavan` | Europe PMC | `local/thennavan2021/mmc3.xlsx` | 처음 한 번 (1단계의 grade 판독 점수) |
| 1 | `python -m src.virtual_hospital.build` | `source/`, `tcga_hgvsc.csv`, `local/thennavan2021/`, `team_project_final` | `tcga/`, `reports/`, `local/source_map.csv`·`slide_map.csv` | 규칙·코드를 바꿀 때마다 |
| (1-1) | `python -m src.virtual_hospital.fetch_hgvsc` | `local/source_map.csv`, `local/mutations.tsv`, GDC·Genome Nexus | `tcga_hgvsc.csv` | 변이 표기가 없을 때만 (git에 있음). 받은 뒤 1단계를 다시 |
| 2 | `python -m src.virtual_hospital.tcga_recur` | 1단계와 같은 원본 (TCGA ①을 다시 계산해 씀) | `tcga_recur/` | 1단계 뒤 |
| 3 | `python -m src.virtual_hospital.bcnb` | `local/bcnb_raw/`, `source/`(Allred·폐경 분포) | `local/bcnb/`, `local/reports/` | BCNB 원자료를 받은 사람만 |
| 4 | `python -m src.virtual_hospital.confirmed` | 1~3단계의 `charts/*/expected/` | 차트마다 `expected/confirmed_state.json`, `reports/confirmed.md` | **마지막에** (1·2단계가 차트 폴더를 새로 만들어서) |
| 5 | `python -m pytest tests/virtual_hospital` | 위 결과 | — | 만들 때마다 |
| 6 | `python embed_slides.py <h5 폴더> <출력.npz>` | 타일 벡터 `.h5` (GPU 서버의 `tcga_all/features`, `bcnb-ln-module2/outputs/features_hoptimus0`) | `local/features/<묶음>_hoptimus0.npz` | 타일 벡터가 바뀔 때. 저장소 없이 파일 하나만 서버에 복사해 돌림 |
| 7 | `python -m src.virtual_hospital.db build` | 1~4단계 결과, `local/features/` | `local/virtual_hospital.db` | 1~6단계 뒤. 매번 새로 만듦. 확인: `python -m src.virtual_hospital.db info` |

점검·시험 (필요할 때):

- `python -m src.virtual_hospital.bcnb_check data/virtual_hospital/local/bcnb_raw`: BCNB 원자료 점검 (개수·ID만)
- `python -m src.virtual_hospital.mini_probe`: 정답을 B `assess`와 화면 1 초안에 넣어 `unknown`·빈 칸을 셈
- `python -m src.virtual_hospital.llm_run`: 차트를 입력 모듈 LLM으로 끝까지 돌리고 채점 (GPU 터널 필요)
- 처방 흐름 전체(C 검색 → B 추천 → D 급여)는 `src.app.script.run_flow`로 돈다. 가상 병원 차트로 돌린 방법은 [notes/progress.md](notes/progress.md) §3

## 가상 병원 DB

`local/virtual_hospital.db` (SQLite, git 제외). BCNB 값이 들어 있어 각자 7단계로 만든다.

| 들어 있는 것 (2026-11-19) | 수 |
|---|---|
| 환자 (장면) | 1,651: tcga_postop 671, tcga_recur 9, bcnb_preop 971 |
| 차트, 정답 JSON (patient_state·biomarker_record·confirmed_state) | 1,651, 4,953 |
| fields, truth, treatments | 35,201, 13,324, 28 |
| 슬라이드, BCNB 주석 | 1,691, 971 |
| 슬라이드 벡터 (H-optimus-0, 종양 타일 평균, 없으면 전체 평균) | 1,634: TCGA 663, BCNB 971 |

읽기 함수 (`src.virtual_hospital.db`):

```python
from src.virtual_hospital import db
con = db.connect()
db.list_patients(con, branch="bcnb_preop", subtype=...)   # 환자 목록
db.get_chart(con, vp_id)                                   # chart.txt
db.get_state(con, vp_id, kind="confirmed_state")           # patient_state / biomarker_record / confirmed_state
db.slides(con, vp_id); db.slide_file(con, slide_id)        # 슬라이드 목록, 원본 파일 위치
db.similar(con, slide_id, k=10)                            # 같은 묶음 안 cosine 유사 슬라이드 (같은 환자 제외)
db.tile_features(con, slide_id, feature_set)               # 타일 벡터 (local/features/<묶음>/에 .h5가 있을 때, h5py 필요)
db.truth(con, vp_id, allow_future=True)                    # 판정 기준일 뒤의 값: allow_future를 줘야만 읽힘
```

- 열쇠는 `(vp_id, branch)`. 같은 TCGA 환자가 수술 후·재발 두 장면에 있을 수 있다 (예: VH-T0043). `branch`를 안 주면 하나뿐일 때만 찾는다
- 차트 등록번호는 TCGA와 BCNB에서 겹친다 (VH-T0002와 VH-B0002 모두 00000002). 찾기는 `vp_id`로
- TCGA와 BCNB 벡터는 타일 크기·배율이 달라 섞어 비교하지 않는다

## 문서

| 문서 | 내용 |
|---|---|
| [notes/progress.md](notes/progress.md) | 2026-11-09 ~ 11-19 한 일, 사용자 결정, 처방 흐름 시험 결과, 남은 것 |
| [notes/design.md](notes/design.md) | 설계: 규칙 체계, 시점과 정답 분리, 칸별 규칙, 결측, CSV·chart.txt, 이미지, 검증·관문 |
| [notes/synthetic_criteria.md](notes/synthetic_criteria.md) | 칸별로 어떻게 합성했는지, 실제 값을 바꾼 것, 문헌 값 |
| [notes/build_guide.md](notes/build_guide.md) | 규칙 문서·코드 안내, 처방 모듈에서 쓰는 파일 |
| [notes/bcnb_check.md](notes/bcnb_check.md) | BCNB 원자료 점검 |
| [notes/mini_findings.md](notes/mini_findings.md) | 처방 모듈 점검 결과 (읽기만) |
| [notes/module_result_format_proposal.md](notes/module_result_format_proposal.md) | 이미지 모듈 결과 형식 제안 (팀 합의 전) |

## 데이터 출처와 인용

이 저장소에는 원본 데이터가 들어 있지 않다. 각 데이터는 아래 출처에서 받아야 하며, 쓸 때는 함께 인용한다.

**TCGA-BRCA**

The results shown here are in whole or part based upon data generated by the TCGA Research Network: https://www.cancer.gov/tcga.

- Grossman RL, et al. Toward a shared vision for cancer genomic data. N Engl J Med. 2016;375(12):1109-1112. doi:10.1056/NEJMp1607591 (GDC)
- Liu J, et al. An integrated TCGA pan-cancer clinical data resource to drive high-quality survival outcome analytics. Cell. 2018;173(2):400-416.e11. doi:10.1016/j.cell.2018.02.052 (생존 자료)
- Cerami E, et al. The cBio cancer genomics portal: an open platform for exploring multidimensional cancer genomics data. Cancer Discov. 2012;2(5):401-404. doi:10.1158/2159-8290.CD-12-0095
- Gao J, et al. Integrative analysis of complex cancer genomics and clinical profiles using the cBioPortal. Sci Signal. 2013;6(269):pl1. doi:10.1126/scisignal.2004088

**BCNB**

- Xu F, Zhu C, Tang W, et al. Predicting axillary lymph node metastasis in early breast cancer using deep learning on primary tumor biopsy slides. Front Oncol. 2021;11:759007. doi:10.3389/fonc.2021.759007 · https://bupt-ai-cz.github.io/BCNB/
- BCNB 약관(원본·수정본 재배포 금지)에 따라 이 저장소에는 BCNB 원본과 BCNB로 만든 가상환자 기록·차트·정답·주석을 넣지 않는다 (`data/virtual_hospital/local/`은 git 제외). BCNB를 쓰는 코드는 비상업 연구 목적에 한한다.

**조직학적 등급 (TCGA, 병리 전문의 판독)**

- Thennavan A, Beca F, Xia Y, et al. Molecular analysis of TCGA breast cancer histologic types. Cell Genomics. 2021;1(3):100067. doi:10.1016/j.xgen.2021.100067 · Data S2 (`mmc3.xlsx`, 조직 소견 11가지 점수)
- Heng YJ, et al. The molecular basis of breast cancer pathological phenotypes. J Pathol. 2017;241(3):375-391. PMID 27861902 (판독 채점표)
- Data S2는 CC BY-NC-ND 4.0이라 원본은 `data/virtual_hospital/local/thennavan2021/`에만 둔다. 가상환자 차트에는 그 판독 점수로 정한 등급과 세 점수(관 형성·핵 다형성·유사분열)를 쓴다 (규칙 M-05, 650명). 판독이 없는 21명은 합성(Y-05). 자세한 출처와 표시: [data/virtual_hospital/tcga/NOTICE.md](../../data/virtual_hospital/tcga/NOTICE.md)

**변이 주석**

- de Bruijn I, et al. Genome Nexus: a comprehensive resource for the annotation and interpretation of genomic variants in cancer. JCO Clin Cancer Inform. 2022;6:e2100144. doi:10.1200/CCI.21.00144

**합성 값의 문헌 근거** (Ki-67, 판독 점수 없는 환자의 grade, ECOG, 겨드랑이 초음파): 숫자와 출처, 표 번호는 [rules/references.csv](../../data/virtual_hospital/rules/references.csv)

## 주의

- 연구·교육용 가상 데이터다. 진단·처방에 쓰지 않는다
- 차트의 이름·등록번호·주민번호는 모두 가짜다
- 차트 글은 로컬 모델에서만 처리한다 (외부 API 금지)
