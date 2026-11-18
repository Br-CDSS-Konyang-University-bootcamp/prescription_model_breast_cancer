# 제안: 이미지 모듈 결과 형식 맞추기 (모듈 1 · 2 · 3 · 4-B)

작성: 2026-11-09 (A) · 상태: **제안** (2026-11-18까지 팀 합의 전) · 관련: [../README.md](../README.md) §10, 받을 표의 틀 [../rules/image_tables.csv](../../../../data/virtual_hospital/rules/image_tables.csv) (2026-11-16)

## 1. 왜 맞추나

착수 발표 v2 20~23쪽의 화면은 네 모듈의 결과를 **한 화면에서 같은 방식으로** 보여 준다. 슬라이드 썸네일 위에 "모델이 크게 본 조직 위치"를 노랑·주황으로 겹쳐 그리고(21·22쪽), 예측값은 처방 모듈에 조건으로 넘긴다(20쪽).

지금은 모듈마다 파이프라인을 따로 만들고 있어서 타일 크기, 좌표, 인코더, 결과 파일이 다르다. 결과 형식을 지금 맞춰 두지 않으면 통합 화면과 가상 병원 DB에서 모듈마다 읽는 코드를 따로 짜야 한다.

**이 제안은 모델이나 학습 방법을 정하지 않는다.** 결과를 내보내는 형식만 맞춘다.

## 2. 부탁하는 것: 실행 1번에 파일 3개

| 파일 | 형식 | 내용 |
|---|---|---|
| ① 예측 JSON | `.json` | 실행 정보, 예측값, 입력으로 쓴 정보 |
| ② 격자 파일 | `.h5` | 타일 좌표와 크기. **모듈 1 `features/*.h5`와 같은 키** |
| ③ 타일 점수 파일 | `.parquet` | 타일마다 모델이 준 점수 (대상마다 한 열) |

②는 이미 특징 `.h5`를 만들고 있다면 그 파일을 그대로 가리켜도 된다 (`coords`·`tile`·`mpp`만 있으면 됨).

### 2.1 ① 예측 JSON

```json
{
  "format_version": "0.1",
  "module": "3",
  "slide_id": "TCGA-A2-A0EW-01Z-00-DX1",
  "specimen": "resection",
  "run": {
    "model": "abmil_marker",
    "model_version": "2026-11-20",
    "weights_sha256": "…",
    "encoder": "h_optimus_0",
    "created_at": "2026-11-20T10:00:00+09:00"
  },
  "split": "test",
  "inputs": ["slide"],
  "predictions": [
    {"target": "ER", "label": "positive", "prob": 0.96},
    {"target": "HER2", "label": "negative", "prob": 0.18}
  ],
  "grid_file": "grid/TCGA-A2-A0EW-01Z-00-DX1.h5",
  "score_file": "scores/TCGA-A2-A0EW-01Z-00-DX1.parquet",
  "score_kind": "attention"
}
```

| 키 | 설명 |
|---|---|
| `module` | `"1"` / `"2"` / `"3"` / `"4B"` |
| `slide_id` | 데이터셋 원래 슬라이드 이름 (TCGA는 `…-DX1`까지, BCNB는 `Patient ID`). 가상환자 번호는 가상 병원 DB가 붙인다 |
| `specimen` | `biopsy` / `resection` |
| `split` | `train` / `val` / `test`. 모델 학습에 쓴 슬라이드인지 표시 (가상 병원은 분할로 거르지 않지만, 학습에 쓴 슬라이드의 예측은 평가에서 따로 본다) |
| `inputs` | 모델에 넣은 것. 슬라이드만이면 `["slide"]`, 임상변수를 같이 넣었으면 그 이름 (예: `"age"`, `"tumour_size"`). **수술 뒤 정보(림프절 결과 등)를 넣지 않았는지 확인하는 데 쓴다** |
| `predictions[]` | 대상마다 한 개. `target`은 모듈 1 `risk`, 모듈 2 `N+`·`N_group`, 모듈 3 `ER`·`PR`·`HER2`·`HER2_IHC`·`Ki67` (제안). 숫자는 `prob` 또는 `value` |
| `score_kind` | 타일 점수의 뜻: `attention` (MIL 가중치) / `tile_prediction` (타일마다의 예측값, 예: 모듈 1 타일별 유전자 예측) |

### 2.2 ② 격자 파일 (`.h5`)

| 키 | 모양 | 설명 |
|---|---|---|
| `coords` | (N, 2) int64 | 타일 왼쪽 위 `[x, y]`, **슬라이드 원본(level 0) 픽셀** |
| 속성 `tile` | int | 타일 한 변의 원본 픽셀 수 |
| 속성 `mpp` | float | 원본 1픽셀의 µm. 파일에 없으면 데이터셋 설명 값을 적고 `mpp_source` 속성에 출처 |
| (선택) `tumor_tile` 등 | (N,) | 조직·종양 표시가 있으면 같이 |

모듈 1 `extract.py`의 `.h5`가 이미 이 모양이다.

### 2.3 ③ 타일 점수 파일 (`.parquet`)

| 열 | 설명 |
|---|---|
| `tile_index` | ② `coords`의 행 번호 (0부터) |
| 대상마다 한 열 (`ER`, `PR`, `N+` …) | `score_kind`가 `attention`이면 **softmax 뒤 가중치 (슬라이드 안 합 1)**. 마커마다 머리가 따로면 열도 따로 |

- 화면용 정규화(슬라이드 안 백분위), 색, 임계값은 **가상 병원 쪽이 한 방식으로** 한다. 모듈은 원값만 내면 된다.
- 히트맵 PNG는 만들지 않아도 된다. 만들었다면 경로를 JSON에 `"heatmap_png"`로 적어 주면 비교용으로 쓴다.

## 3. 가상 병원 쪽이 하는 것

- 위 파일을 등록하고 (`module_runs.csv`, `tile_grids.csv`, `attention.csv`, 틀은 `data/virtual_hospital/rules/image_tables.csv`), 썸네일 위에 히트맵을 그린다. 등록 코드는 모듈 결과가 나오면 만든다.
- 좌표가 슬라이드 크기 안인지(V6), 다시 그린 그림이 같은지(V7) 검사한다.
- BCNB 슬라이드 결과는 약관대로 `data/virtual_hospital/local/`에만 둔다. **BCNB 결과 파일은 GitHub에 올리지 않는다** (각 모듈도 같음).

## 4. 정해야 할 것

| 번호 | 질문 | 제안 |
|---|---|---|
| 1 | 이 형식으로 갈지 | 위 그대로 `format_version` 0.1 |
| 2 | 모듈 3 `target` 이름 | `ER`, `PR`, `HER2`, `HER2_IHC`, `Ki67` |
| 3 | 모듈 2 3구간 이름 | `N0`, `N1-2`, `N3+` |
| 4 | attention이 뚜렷하지 않은 모델 (TransMIL 등) | `score_kind`를 다르게 적고 화면에는 "위치 정보 없음" 표시 |
| 5 | 4-B 이웃 결과 | `predictions` 대신 `neighbors: [{slide_id, distance}]` (따로 정리) |
