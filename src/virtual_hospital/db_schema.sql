-- 가상 병원 DB (SQLite). python -m src.virtual_hospital.scripts.db build가 매번 새로 만든다.
-- DB 파일(data/virtual_hospital/local/virtual_hospital.db)은 BCNB에서 만든 값을 담으므로 git에 넣지 않는다 (BCNB 약관).
-- 표 이름·칸은 rules/image_tables.csv(모듈 결과 틀)와 맞춘다.

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

-- 환자 (판정 기준일의 장면 하나 = 한 행)
-- 같은 환자가 두 장면에 있을 수 있다 (VH-T0043: 수술 후 + 재발). 열쇠는 (vp_id, branch)
CREATE TABLE patients (
  vp_id TEXT NOT NULL,               -- VH-T0001, VH-B0002
  branch TEXT NOT NULL,              -- tcga_postop / tcga_recur / bcnb_preop
  dataset TEXT NOT NULL,             -- TCGA-BRCA / BCNB
  dx_date TEXT, index_day INTEGER,   -- 가짜 진단일, 판정 기준일 (진단일 = 0)
  age INTEGER, sex TEXT,
  subtype TEXT,                      -- B 판정 아형 (biomarker_record)
  stage_group TEXT, disease TEXT,    -- 병기군, early / locally_advanced / metastatic
  phase TEXT,                        -- 확정 상태 setting.phase (adjuvant / neoadjuvant), 전이성이면 NULL
  scene TEXT,                        -- 재발 갈래 장면 (예: 고식 항암 1차 결정)
  registration_no TEXT,              -- R-08 차트의 등록번호 (환자 단위, TCGA 1·BCNB 2로 시작, 두 장면은 같은 번호)
  patient_name TEXT,                 -- Y-08 가상 이름 (실제 인물 아님, 환자마다 다름)
  patient_ref TEXT NOT NULL UNIQUE,  -- D-12 장면 단위 (재발 장면은 vp_id + '-R'), 확정·추천 저장 폴더 이름
  PRIMARY KEY (vp_id, branch)
);

CREATE TABLE charts (vp_id TEXT, branch TEXT, chart_text TEXT NOT NULL, PRIMARY KEY (vp_id, branch));

-- 병원 쪽 문서 (EMR 흉내): 장면 차트를 입력 모듈 split()으로 나눈 문서. 본문을 이어 붙이면 chart_text와 같다
-- doc_date가 비어 있는 문서(투약 기록 표)는 장면 판정 기준일 기준 목록
CREATE TABLE documents (
  vp_id TEXT, branch TEXT, doc_id TEXT, doc_type TEXT NOT NULL, doc_date TEXT, start INTEGER NOT NULL, text TEXT NOT NULL,
  PRIMARY KEY (vp_id, branch, doc_id)
);

-- 정답 JSON: patient_state / biomarker_record / confirmed_state
CREATE TABLE states (
  vp_id TEXT, branch TEXT, kind TEXT NOT NULL, json TEXT NOT NULL,
  PRIMARY KEY (vp_id, branch, kind)
);

-- 칸마다 출처 (fields.csv): real / derived / synthetic
CREATE TABLE fields (
  vp_id TEXT, branch TEXT, field TEXT, status TEXT, value TEXT,
  origin TEXT, basis TEXT, rule_id TEXT, source_column TEXT, observed_date TEXT, specimen TEXT, note TEXT,
  PRIMARY KEY (vp_id, branch, field)
);

-- 차트에 없는 값 (판정 기준일 뒤 = 미래 값). 모델 정답(BCNB 수술 림프절 등)과 참고용 실제 처방 기록
CREATE TABLE truth (vp_id TEXT, branch TEXT, item TEXT, value TEXT, PRIMARY KEY (vp_id, branch, item));

-- 재발 갈래 요법 줄 (treatments.csv)
CREATE TABLE treatments (
  vp_id TEXT, branch TEXT, drugs TEXT, setting TEXT, start_day INTEGER, end_day INTEGER,
  stop_reason TEXT, stop_basis TEXT, best_response TEXT, endocrine_line INTEGER, chemo_line INTEGER
);

-- H&E 슬라이드. 원본 파일은 DB에 넣지 않고 기준 폴더(root) + 상대 경로로 가리킨다
--   root: bcnb_raw (data/virtual_hospital/local/bcnb_raw, 없으면 예전 위치) / final (team_project_final) / gdc (원본 없음)
CREATE TABLE slides (
  slide_id TEXT PRIMARY KEY,         -- VH-T0001-S1
  vp_id TEXT, dataset TEXT, specimen TEXT,   -- biopsy / resection (슬라이드는 환자에 붙음, 갈래와 무관)
  root TEXT, path TEXT,              -- 원본 (BCNB jpg) 또는 썸네일 (TCGA)
  source_slide TEXT,                 -- 원본 슬라이드 이름 (local 전용 정보라 DB도 local)
  width INTEGER, height INTEGER, mpp REAL, stain_qc TEXT, pen_qc TEXT
);

CREATE TABLE annotations (
  ann_id TEXT PRIMARY KEY, slide_id TEXT REFERENCES slides, vp_id TEXT, kind TEXT, origin TEXT,
  file TEXT, n_polygons INTEGER, dropped_outside INTEGER, rule_id TEXT
);

-- 타일 특징 벡터 묶음 (슬라이드 하나 = 한 행). 파일은 크기가 커서 DB 밖 (서버 또는 local/features/)
CREATE TABLE feature_sets (
  slide_id TEXT REFERENCES slides, feature_set TEXT,   -- 예: tcga_hoptimus0, bcnb_hoptimus0
  encoder TEXT, tile_px INTEGER, input_px INTEGER, mpp REAL,
  n_tiles INTEGER, n_tumor_tiles INTEGER, dim INTEGER,
  file TEXT,                         -- 묶음 폴더 안 파일 이름 (예: TCGA-…-DX1.h5, 2.h5)
  PRIMARY KEY (slide_id, feature_set)
);

-- 슬라이드 벡터 하나 (타일 벡터를 모은 것). 병리 유사 환자 검색 (4-B)
CREATE TABLE slide_embeddings (
  slide_id TEXT REFERENCES slides, feature_set TEXT, pooling TEXT,   -- mean_tumor / mean_all
  dim INTEGER, vector BLOB NOT NULL,                                  -- float32 little-endian
  PRIMARY KEY (slide_id, feature_set, pooling)
);

-- 모듈 결과 (모듈 결과 형식 제안, rules/image_tables.csv). 모듈 결과가 나오면 채운다
CREATE TABLE module_runs (
  run_id TEXT PRIMARY KEY, vp_id TEXT, slide_id TEXT, module TEXT, model TEXT, model_version TEXT,
  weights_sha256 TEXT, encoder TEXT, grid_id TEXT, inputs TEXT, score_kind TEXT, prediction_file TEXT,
  format_version TEXT, created_at TEXT
);
CREATE TABLE predictions (run_id TEXT REFERENCES module_runs, vp_id TEXT, target TEXT, label TEXT, prob REAL, value REAL);
CREATE TABLE tile_grids (
  grid_id TEXT PRIMARY KEY, slide_id TEXT, vp_id TEXT, module TEXT, tile_px INTEGER, tile_um REAL, mpp REAL,
  overlap_px INTEGER, n_tiles INTEGER, grid_file TEXT
);
CREATE TABLE attention (
  layer_id TEXT PRIMARY KEY, run_id TEXT, target TEXT, score_file TEXT, score_column TEXT, n_tiles INTEGER,
  normalization TEXT, top_k_tiles TEXT
);
CREATE TABLE renders (
  render_id TEXT PRIMARY KEY, layer_id TEXT, slide_id TEXT, kind TEXT, file TEXT, downsample REAL,
  colormap TEXT, threshold REAL, code_version TEXT
);

CREATE INDEX idx_patients_branch ON patients (branch, subtype);
CREATE INDEX idx_slides_vp ON slides (vp_id);
