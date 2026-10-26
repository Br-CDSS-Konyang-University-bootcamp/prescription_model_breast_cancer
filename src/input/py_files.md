# 입력 모듈 `.py` 파일 정리

> 담당 A · 2026-10-26 · 위치 `src/input/script/` · 실행은 모두 `team_project` 폴더에서 `python -m ...`

입력 모듈은 차트 원문을 `patient_state`(`schemas/patient_state.json`)로 바꾼다. 코드는 `script/` 아래 기능별 폴더 다섯 개에 있다.

```
src/input/script/
├── pipeline/     차트 원문 → patient_state 처리 단계 (IN-0 ~ IN-7)
│   ├── pipeline.py     진입점 run()
│   ├── classify.py     IN-1 문서 나누기
│   ├── deid.py         IN-0 비식별화
│   ├── extract.py      IN-2 구절 찾기 (로컬 LLM)
│   ├── quote.py        인용 확인
│   ├── normalize.py    IN-3 정규화
│   └── assemble.py     IN-4 ~ IN-7 조립
├── evaluation/   정답 후보와 채점
│   ├── candidates.py
│   └── score.py
├── rules/        공용 규칙·사전 (pipeline·virtual·tcga가 같이 쓴다)
│   ├── lines.py
│   └── vocab.py
├── virtual/      가상 차트 (모듈 검증용 정답)
│   ├── virtual_chart.py
│   ├── build_virtual_cases.py
│   └── cases/          vc_0101 ~ vc_0109, vc_0106b, pairs
└── tcga/         TCGA 도구 (지금은 쓰지 않음)
```

폴더 사이의 관계:

```
virtual/ ──만든 정답──▶ evaluation/ ◀──출력── pipeline/
    │                                         │
    └────────────── rules/ ◀──────────────────┘   (tcga/도 rules/를 쓴다)
```

## 1. `pipeline/`: 차트 원문 → `patient_state`

처리 순서: `classify(IN-1) → deid(IN-0) → extract(IN-2, LLM) → quote → normalize(IN-3) → assemble(IN-4~7)`

| 파일 | 역할 | 작업 내용 | 주요 함수 | 테스트 |
|---|---|---|---|---|
| `pipeline.py` | 진입점 | 원문을 문서로 나누고, 식별정보를 가린 문서만 `extract`에 넘기고, 돌아온 후보를 원문 기준으로 조립한다. `extract` 자리에는 LLM 추출기나 정답 후보를 넣는다 | `run(chart_text, extract, patient_ref=, created_at=)` → `(patient_state, issues)` | `test_input_pipeline.py` |
| `classify.py` | IN-1 문서 나누기 | 머리글(`[...]`, `<...>`, `■`)이나 빈 줄 2개로 문서를 나누고, 머리글 단어로 종류(병리·분자병리·투약·영상·경과기록), 머리글·보고일·검사일·작성일로 날짜를 붙인다. 위치는 원문 기준 | `split`, `classify`, `Document` | `test_classify_quote.py` |
| `deid.py` | IN-0 비식별화 | 정규식으로 이름(이름표 뒤 한글)·등록번호·주민번호·연락처·주소를 찾아 `[이름1]` 같은 표시로 가린다. 대응표는 메모리에만 둔다. 날짜·나이·성별·병원 이름은 남긴다 | `identifiers`, `mask` | `test_deid.py` |
| `extract.py` | IN-2 구절 찾기 (로컬 LLM) | 문서마다 그 종류의 칸 목록(출력 스키마 enum)과 시험 세트 밖 예문 1개를 주고, "값이 적힌 구절"을 `{field, quote, specimen, observed_date}`로 받는다. 값은 계산하지 않는다. `"null"` 구절은 버린다. 모델은 `llm/config.toml`의 `[extract]` | `extract_doc`, `make_extract`, `FIELDS`, `EXAMPLES` | `test_extract.py` (가짜 LLM) |
| `quote.py` | 인용 확인 | 구절의 가림 표시를 대응표로 되돌린 뒤 원문 문서에서 찾아 위치를 계산한다. 공백 차이만 허용하고, 없으면 버린다 (지어낸 구절 차단) | `locate` | `test_classify_quote.py` |
| `normalize.py` | IN-3 정규화 | 구절 → 표준값 (사전·정규식). 미시행·결과 대기·예정은 `not_done`. 칸마다 필요한 단어가 없거나 TNM 접두어가 다르면 값을 만들지 않는다 (LLM이 칸을 잘못 고른 경우를 막는다) | `normalize`, `Context`, `parse_date` | `test_normalize.py` |
| `assemble.py` | IN-4 ~ IN-7 조립 | 값 고르기(전이 검체·최신 우선, 나이는 가장 이른 값), 같은 날 다른 값은 충돌, 후보 없는 칸은 `not_recorded`, 다른 칸을 보는 규칙(ypTNM·진단 시 IV기·재발 없음), 투약 setting·progression_day, anthracycline 용량, 유전자 보고서, `rules.lines.annotate`, 스키마 검증. 버린 후보는 `issues`로 돌려준다 | `assemble` | `test_input_pipeline.py` |

## 2. `evaluation/`: 정답 후보와 채점

| 파일 | 역할 | 작업 내용 | 주요 함수 | 테스트 |
|---|---|---|---|---|
| `candidates.py` | IN-2 후보 형식, 정답 후보 | 후보 형식 `{doc_id, field, quote, specimen, observed_date}`을 정한다. 정답 `patient_state`의 근거마다 후보를 만들어 LLM 없이 규칙 쪽(pipeline)을 시험한다 (29건 100%) | `from_expected`, `KEYS` | `test_candidates.py` |
| `score.py` | 채점 | 출력과 가상 차트 정답을 칸 단위로 비교해 필드 정확도(전체·정답 present 칸만), 상태 혼동표, 근거 위치(정확 일치·겹침), 인용 준수율, 틀린 칸 목록을 낸다 | `compare`, `total`, `report` | `test_score.py` |

## 3. `rules/`: 공용 규칙·사전

| 파일 | 역할 | 작업 내용 | 쓰는 곳 | 테스트 |
|---|---|---|---|---|
| `lines.py` | 치료 상황 규칙 | 전이 후 차수(`line`, 고식적 내분비 `endocrine_line`, 고식적 항암 `chemo_line`), 심평원 차수 간주 규칙(`deemed_lines`), 판정 기준일 값(`at_index`: 기준일 나이, 최근 4주 투약)을 계산한다. `annotate()`가 셋을 한 번에 채운다 | `pipeline/assemble.py`, `virtual/`, `tcga/` | `test_lines.py` |
| `vocab.py` | 표준값 사전 | `data/dictionaries/field_vocab.csv`를 읽어 "양성"·"Positive" 같은 표현을 표준값 하나로 바꾼다. 공백·대소문자는 무시하고, 한 표현이 두 값에 대응하면 멈춘다 | `pipeline/normalize.py`, `tcga/` | `test_vocab.py` |

## 4. `virtual/`: 가상 차트

| 파일 | 역할 | 작업 내용 | 테스트 |
|---|---|---|---|
| `virtual_chart.py` | 가상 차트 작성 도구 | `Chart`·`Doc`·`F`로 사례 코드가 글을 쓰는 순간 값과 원문 위치를 함께 기록해 `chart.txt`와 정답 `patient_state.json`이 어긋나지 않게 만든다. 스키마·인용 위치·차수 재계산을 검사한다. 다른 파일이 쓰는 `CASES`, `out_dir`도 여기 있다 | `test_virtual_charts.py` |
| `cases/vc_0101.py` ~ `vc_0109.py`, `vc_0106b.py` | 가상 차트 10건 사례 코드 | 파일마다 `build()`가 차트 하나를 만든다. 일부는 짝 사례용 매개변수가 있다 (예: VC-0103 `adj_gap`, VC-0107 `er`) | `test_virtual_charts.py` |
| `cases/pairs.py` | 짝 사례 19건 | 기본 사례에서 판정을 가르는 값 하나만 바꾸고, A 정답 확인값(`expect_a`)과 B·C·D 기대 판정 초안(`expect`)을 적는다 | `test_virtual_charts.py` |
| `build_virtual_cases.py` | 가상 사례 20건 생성 | `virtual_patient_cases_2026-10-23.md` §3의 값으로 VC-0110 ~ VC-0129의 차트·정답·`scenario.md`·`cases.csv`를 만든다 (`virtual_chart.py`의 `Chart`·`F`를 쓴다) | `test_virtual_cases.py` |

## 5. `tcga/`: TCGA 도구 (지금은 쓰지 않음)

TCGA 데이터로 변환·계산 규칙을 점검하던 도구다. 테스트는 그대로 돌고, B 모듈 테스트(`tests/biomarker/test_bm.py`)가 `tcga_to_patient_state`를 쓴다.
TCGA 원자료 다운로드·병합 스크립트는 `data/script/`에 따로 있다.

| 파일 | 작업 내용 | 테스트 |
|---|---|---|
| `tcga_to_patient_state.py` | TCGA-BRCA 크롭본 CSV → 환자마다 `patient_state` (규칙 명세 `tcga_mapping.md`). 기본은 메모리에서만 변환하고 `--out`이면 저장 | `test_verify_conversion.py`, `test_fixed_chart.py`, `tests/biomarker/test_bm.py` |
| `verify_tcga_conversion.py` | 변환기를 쓰지 않고 크롭본 원본 칸과 규칙만으로 JSON을 한 칸씩 대조한다 | `test_verify_conversion.py` |
| `tcga_truth.py` | 이전 정답 생성기 (같은 변환 + 파일 저장·스키마 검증·규칙별 건수 보고서, `data/truth/`) | `test_tcga_truth.py`, `test_manual_truth.py` |
| `fixed_chart.py` | `patient_state` ↔ 고정 형식 차트 글 (`render`·`parse`). TCGA 838명 모두 왕복이 같아야 한다 | `test_fixed_chart.py` |

## 실행 명령

```bash
python -m src.input.script.pipeline.extract --ids VC-0103 --docs D4         # 문서 하나: LLM 후보와 정답 대조, 시간
python -m src.input.script.pipeline.extract --out data/input/runs/<이름>     # 가상 차트 10건을 끝까지 돌려 저장 (CPU 약 1시간)
python -m src.input.script.pipeline.extract --replay data/input/runs/<이름>  # 저장한 LLM 후보로 규칙만 다시 (몇 초)
python -m src.input.script.evaluation.score --gold                          # 정답 후보로 돌려 채점 (규칙 점검, 100%여야 함)
python -m src.input.script.evaluation.score data/input/runs/<이름>           # 저장한 출력 채점
python -m src.input.script.virtual.virtual_chart [--ids VC-0103] [--check]  # 가상 차트 10건 + 짝 사례 만들기·검사
python -m src.input.script.virtual.build_virtual_cases [--check]            # 가상 사례 20건 만들기·검사
python -m src.input.script.tcga.tcga_to_patient_state [--ids ... --show]    # TCGA 변환 (지금은 쓰지 않음)
```

폴더마다 있는 `__init__.py`는 폴더를 파이썬 패키지로 만드는 파일이고, 폴더 설명 한 줄만 있다.
