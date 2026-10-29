# 입력 모듈 `.py` 파일 정리

> 담당 A · 2026-10-26 · 위치 `src/input/script/` · 실행은 모두 `team_project` 폴더에서 `python -m ...`

입력 모듈은 차트 원문을 `patient_state`(`schemas/patient_state.json`)로 바꾼다. 코드는 `script/` 아래 기능별로 나뉜다.

- `pipeline.py`, `evaluation.py`, `rules.py`: 기능마다 **파일 하나**. 옛 폴더(`pipeline/`, `evaluation/`, `rules/`)의 파일을 합쳤고 (2026-10-26),
  파일 안은 옛 파일 이름의 **절**로 나뉜다
- `virtual/`: **폴더**. 같은 이름의 함수가 여러 파일에 있어 합치지 않았다 (6절)
- `tcga/`: B 테스트가 쓰는 변환기 하나만 남은 폴더 (5절)

## 구조

```
src/input/script/
├── __init__.py
├── pipeline.py     1,306줄  차트 원문 → patient_state 처리 단계 (IN-0 ~ IN-7). 실행 명령 있음
├── evaluation.py     284줄  정답 후보와 채점. 실행 명령 있음
├── rules.py          389줄  공용 규칙·사전 (pipeline·virtual이 같이 쓴다)
├── virtual/                 가상 차트 (모듈 검증용 정답)
│   ├── virtual_chart.py
│   ├── build_virtual_cases.py
│   └── cases/               vc_0101 ~ vc_0109, vc_0106b, pairs
└── tcga/                    B 테스트용 변환기만 남김
    └── tcga_to_patient_state.py
```

파일 사이의 관계:

```
virtual/ ──만든 정답──▶ evaluation.py ◀──출력── pipeline.py
    │                                              │
    └──────────────── rules.py ◀───────────────────┘
```

### 합친 파일 읽는 법

- 절마다 맨 위에 `# 절이름 (옛 src/input/script/<폴더>/<파일>.py)` 머리 주석과 옛 파일의 설명이 주석으로 있다. 아래 표의 "시작 줄"로 바로 찾아간다
- 절 순서는 의존 순서다 (앞 절의 이름을 뒤 절이 쓴다). 실행 명령(`main()`)은 파일 맨 끝 절에 있다
- import 이름은 합치기 전과 같다. 모듈 경로만 짧아졌다

```python
from src.input.script.pipeline import run, split, normalize, Context, assemble, make_extract
from src.input.script.evaluation import from_expected, compare, total, case_set
from src.input.script.rules import Vocab, annotate, load_drug_table
```

## 1. `pipeline.py`: 차트 원문 → `patient_state`

처리 순서: `classify(IN-1) → deid(IN-0) → extract(IN-2, LLM) → quote → normalize(IN-3) → assemble(IN-4~7)`.
진입점은 `run()`, 실행 명령은 extract 절의 `main()` (`python -m src.input.script.pipeline`).

| 절 | 시작 줄 | 역할 | 작업 내용 | 주요 이름 | 테스트 |
|---|---|---|---|---|---|
| `classify` | 36 | IN-1 문서 나누기 | 머리글(`[...]`, `<...>`, `■`)이나 빈 줄 2개로 문서를 나누고, 머리글 단어로 종류(병리·분자병리·투약·영상·경과기록), 머리글·보고일·검사일·작성일로 날짜를 붙인다. 위치는 원문 기준 | `split`, `classify`, `Document`, `DATE` | `test_classify_quote.py` |
| `deid` | 110 | IN-0 비식별화 | 정규식으로 이름(이름표 뒤 한글)·등록번호·주민번호·연락처·주소를 찾아 `[이름1]` 같은 표시로 가린다. 대응표는 메모리에만 둔다. 날짜·나이·성별·병원 이름은 남긴다 | `identifiers`, `mask` | `test_deid.py` |
| `quote` | 158 | 인용 확인 | 구절의 가림 표시를 대응표로 되돌린 뒤 원문 문서에서 찾아 위치를 계산한다. 공백 차이만 허용하고, 없으면 버린다 (지어낸 구절 차단) | `locate` | `test_classify_quote.py` |
| `normalize` | 184 | IN-3 정규화 | 구절 → 표준값 (`field_vocab.csv`·`drug_names.csv`·정규식). 미시행·결과 대기·예정은 검사 칸(수용체·Ki-67)에서만 `not_done`. LLM이 칸을 잘못 고른 구절은 값을 만들지 않는다: 칸마다 필요한 단어, TNM 접두어, 유전자 이름, 재발·전이 단어, 종료·중단 단어 등 | `normalize`, `Context`, `parse_date`, `TEST_FIELDS` | `test_normalize.py` |
| `assemble` | 668 | IN-4 ~ IN-7 조립 | 값 고르기(전이 검체·최신 우선, 나이는 가장 이른 값, 같은 값 반복은 이력에서 뺌), 같은 날 다른 값은 충돌, 후보 없는 칸은 `not_recorded`. 다른 칸을 보는 규칙: ypTNM 문서의 크기·림프절, 진단 시 IV기(전이일 0·투약 setting), 진단 시 IV기 아님(진단 시 전이 부위 제외, M0면 "해당 없음"), 재발 없음(재발 부위 비움), 재발 부위가 있으면 재발 상태 "원격 전이". 그 밖에 투약 setting·progression_day, anthracycline 용량, 유전자 보고서, `annotate`, 스키마 검증. 버린 후보는 `issues`로 | `assemble` | `test_input_pipeline.py` |
| `pipeline` | 967 | 진입점 | 원문을 문서로 나누고, 식별정보를 가린 문서만 `extract`에 넘기고, 돌아온 후보를 원문 기준으로 조립한다. `extract` 자리에는 LLM 추출기나 정답 후보를 넣는다 | `run(chart_text, extract, patient_ref=, created_at=)` → `(patient_state, issues)` | `test_input_pipeline.py` |
| `extract` | 987 | IN-2 구절 찾기 (로컬 LLM) | 문서마다 그 종류의 칸 목록(출력 스키마 enum)과 시험 세트 밖 예문 1개를 주고 "값이 적힌 구절"을 `{field, quote, specimen, observed_date}`로 받는다. 값은 계산하지 않는다. `"null"` 구절은 버린다. 모델은 `llm/config.toml`의 `[extract]`. `main()`: 문서 보기, 사례 묶음 실행·저장, 저장 후보로 다시 조립 | `extract_doc`, `make_extract`, `FIELDS`, `EXAMPLES`, `main` | `test_extract.py` (가짜 LLM) |

## 2. `evaluation.py`: 정답 후보와 채점

실행 명령은 score 절의 `main()` (`python -m src.input.script.evaluation`).

| 절 | 시작 줄 | 역할 | 작업 내용 | 주요 이름 | 테스트 |
|---|---|---|---|---|---|
| `candidates` | 24 | IN-2 후보 형식, 정답 후보 | 후보 형식 `{doc_id, field, quote, specimen, observed_date}`을 정한다. 정답 `patient_state`의 근거마다 후보를 만들어 LLM 없이 규칙 쪽(pipeline)을 시험한다 | `from_expected`, `KEYS` | `test_candidates.py` |
| `score` | 73 | 채점 | 출력과 가상 차트 정답을 칸 단위로 비교해 필드 정확도(전체·정답 present 칸만), 정밀도·재현율(칸별로도), 상태 혼동표, 근거 위치(정확 일치·겹침), 인용 준수율, 틀린 칸 목록을 낸다. 사례 묶음: `dev` 10건, `pairs` 짝 19건, `test` 새 20건 | `compare`, `total`, `report`, `case_set`, `expected`, `main` | `test_score.py` |

## 3. `rules.py`: 공용 규칙·사전

| 절 | 시작 줄 | 역할 | 작업 내용 | 쓰는 곳 | 테스트 |
|---|---|---|---|---|---|
| `vocab` | 19 | 표준값 사전 | `data/dictionaries/field_vocab.csv`를 읽어 "양성"·"Positive" 같은 표현을 표준값 하나로 바꾼다. 공백·대소문자는 무시하고, 한 표현이 두 값에 대응하면 멈춘다 | `pipeline.py` (normalize) | `test_vocab.py` |
| `lines` | 73 | 치료 상황 규칙 | 전이 후 차수(`line`, 고식적 내분비 `endocrine_line`, 고식적 항암 `chemo_line`), 심평원 차수 간주 규칙(`deemed_lines`), 판정 기준일 값(`at_index`: 기준일 나이, 최근 4주 투약)을 계산한다. `annotate()`가 셋을 한 번에 채운다 | `pipeline.py` (assemble), `virtual/` | `test_lines.py` |

## 4. `virtual/`: 가상 차트

| 파일 | 역할 | 작업 내용 | 테스트 |
|---|---|---|---|
| `virtual_chart.py` | 가상 차트 작성 도구 | `Chart`·`Doc`·`F`로 사례 코드가 글을 쓰는 순간 값과 원문 위치를 함께 기록해 `chart.txt`와 정답 `patient_state.json`이 어긋나지 않게 만든다. 스키마·인용 위치·차수 재계산을 검사한다. 다른 파일이 쓰는 `CASES`, `out_dir`도 여기 있다 | `test_virtual_charts.py` |
| `cases/vc_0101.py` ~ `vc_0109.py`, `vc_0106b.py` | 가상 차트 10건 사례 코드 (개발 세트) | 파일마다 `build()`가 차트 하나를 만든다. 일부는 짝 사례용 매개변수가 있다 (예: VC-0103 `adj_gap`, VC-0107 `er`) | `test_virtual_charts.py` |
| `cases/pairs.py` | 짝 사례 19건 | 기본 사례에서 판정을 가르는 값 하나만 바꾸고, A 정답 확인값(`expect_a`)과 B·C·D 기대 판정 초안(`expect`)을 적는다 | `test_virtual_charts.py` |
| `build_virtual_cases.py` | 가상 사례 20건 생성 (시험 세트) | `virtual_patient_cases.md` §3의 값으로 VC-0110 ~ VC-0129의 차트·정답·`scenario.md`·`cases.csv`를 만든다 (`virtual_chart.py`의 `Chart`·`F`를 쓴다) | `test_virtual_cases.py` |

## 5. `tcga/`

2026-10-27 TCGA 정답 세트 폐기, 평가는 가상 차트로. B 모듈 테스트(`tests/biomarker/test_bm.py`)가 쓰는 `tcga_to_patient_state.py`만 남겼다.

## 6. `virtual/`를 파일 하나로 합치지 않은 이유 (2026-10-26 확인)

| 폴더 | 같은 이름의 정의 | 실행 명령 | 그 밖 |
|---|---|---|---|
| `virtual/` | `build` 10개(사례 파일마다), `main` 2개, `ROOT`, `CYC` | 2개 (`virtual_chart`, `build_virtual_cases`) | `virtual_chart.py`가 사례 파일을 이름으로 불러온다 (`cases.vc_0103`) |

그대로 합치면 같은 이름이 서로 덮어쓰고 실행 명령이 하나만 남는다. 합치려면 이름을 바꾸고 실행 명령을 하위 명령으로 나눠야 한다.

## 실행 명령

```bash
# LLM 추출 (pipeline.py)
python -m src.input.script.pipeline --ids VC-0103 --docs D4                      # 문서 하나: LLM 후보와 정답 대조, 시간
python -m src.input.script.pipeline --out data/input/runs/<이름>                  # 개발 세트 10건을 끝까지 돌려 저장 (CPU 약 1시간)
python -m src.input.script.pipeline --set test --out data/input/runs/<이름>       # 시험 세트 20건 (규칙을 고정한 뒤에만, 약 2시간)
python -m src.input.script.pipeline --replay data/input/runs/<이름>               # 저장한 LLM 후보로 규칙만 다시 (몇 초)
python -m src.input.script.pipeline --host http://127.0.0.1:11435 --out ...      # GPU 서버 (SSH 터널을 연 뒤, 아래 참고)

# 채점 (evaluation.py)
python -m src.input.script.evaluation --gold                                      # 정답 후보로 돌려 채점 (기본 dev + pairs, 규칙 점검)
python -m src.input.script.evaluation --gold --set test                           # 시험 세트를 정답 후보로 (규칙만의 일반화 확인)
python -m src.input.script.evaluation data/input/runs/<이름>                       # 저장한 출력 채점 (폴더 안의 사례 전부)

# 가상 차트 (virtual/)
python -m src.input.script.virtual.virtual_chart [--ids VC-0103] [--check]       # 가상 차트 10건 + 짝 사례 만들기·검사
python -m src.input.script.virtual.build_virtual_cases [--ids VC-0112] [--check] # 가상 사례 20건 만들기·검사

```

개발 세트(dev)는 규칙·프롬프트를 고칠 때 보는 사례, 시험 세트(test)는 규칙을 고정한 뒤에만 재는 사례다 (과적합 방지, `llm_extraction_runs.md`).

## GPU 서버로 돌리기 (SSH 터널)

서버의 Ollama는 서버 자신(`127.0.0.1`)에서만 받게 띄우고, 이 PC와는 SSH 터널(암호화)로만 잇는다. 서버 주소를 `--host`에 바로 쓰지 않는다 (Ollama는 인증·암호화가 없다).
비식별화·인용 확인·정규화·조립은 이 PC에서 하고, 서버에는 가린 문서만 간다.

```bash
# 이 PC에서 (창을 열어 둔다): 이 PC 11435 → 서버 Ollama 11500
ssh -p <포트> -N -L 11435:127.0.0.1:11500 <계정>@<서버>
```

서버 쪽 설치·실행(관리자 권한 없이 계정 폴더에)은 `~/ollama`에 공식 `ollama-linux-amd64.tar.zst`를 풀고
`OLLAMA_HOST=127.0.0.1:11500 OLLAMA_MODELS=$HOME/ollama/models ~/ollama/bin/ollama serve`로 띄운다 (tmux 안에서). 가상 차트 시험만 이 방식으로 한다. 실제 환자 차트를 공용 서버로 보낼지는 팀·기관이 따로 정한다.

## 참고

- 폴더마다 있는 `__init__.py`는 폴더를 파이썬 패키지로 만드는 파일이고, 폴더 설명 한 줄만 있다
- 합친 뒤 git은 `score.py → evaluation.py`, `lines.py → rules.py`만 이름 바꾸기로 보고 나머지는 삭제와 새 파일로 본다. 옛 파일의 이력은 옛 경로로 본다 (`git log -- src/input/script/pipeline/normalize.py`)
- 시작 줄은 2026-10-26 기준이다. 코드를 고치면 줄이 바뀌므로, 절 머리 주석(`# normalize (옛 ...)`)으로 찾는 편이 정확하다
