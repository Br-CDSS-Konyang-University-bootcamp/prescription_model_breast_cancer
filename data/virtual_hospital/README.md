# data/virtual_hospital — 가상 병원 환자 데이터

TCGA-BRCA·BCNB 실제 값을 뼈대로 만든 가상 유방암 환자다. 만든 코드와 규칙 설명은 [../../src/virtual_hospital/](../../src/virtual_hospital/README.md), 파일 안내는 [build_guide.md](../../src/virtual_hospital/notes/build_guide.md).

| 폴더·파일 | 내용 |
|---|---|
| `tcga/` | TCGA ① 수술 후 671명: 차트(`charts/<번호>/chart.txt`), 정답(`expected/patient_state·biomarker_record·confirmed_state.json`), `patients·fields·truth.csv`, `NOTICE.md` |
| `tcga_recur/` | TCGA ② 재발 9명: 위와 같은 구성 + `treatments.csv` |
| `rules/` | 규칙 표 (`rules.csv` 등) |
| `source/` | TCGA 원본 사본 (만들 때의 입력) |
| `reports/` | 생성 보고, 뺀 환자, 관문 결과 |
| `local/` | **git 제외**: BCNB 원자료·결과 (약관), 원본 ID 대응표, 등급 판독 원본, LLM 결과 |

`truth.csv`의 실제 처방 기록은 참고용이고 정답이 아니다. 다시 만들기: `python -m src.virtual_hospital.build` 등 (코드 폴더 README의 "실행").
