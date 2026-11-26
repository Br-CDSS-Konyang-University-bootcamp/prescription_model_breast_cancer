# NOTICE — 조직학적 등급(grade)의 출처

이 폴더의 TCGA 가상환자 차트(`charts/*/chart.txt`의 "조직학적 등급"과 그 아래 세 점수)와 `fields.csv`의 `diagnosis.grade`는 아래 자료를 바탕으로 만들었다.

## 출처

- Thennavan A, Beca F, Xia Y, et al. Molecular analysis of TCGA breast cancer histologic types. *Cell Genomics*. 2021;1(3):100067. doi:[10.1016/j.xgen.2021.100067](https://doi.org/10.1016/j.xgen.2021.100067) — Data S2 (`mmc3.xlsx`, 병리 전문의 패널이 매긴 TCGA BRCA 조직 소견 점수)
- Heng YJ, et al. The molecular basis of breast cancer pathological phenotypes. *J Pathol*. 2017;241(3):375-391. PMID 27861902 — 판독 채점표
- 라이선스: Data S2는 [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/). © 2021 The Authors.

## 이 폴더에서 한 것

| 환자 | 등급 | `fields.csv` 표시 |
|---|---|---|
| 650명 | Data S2의 관 형성·핵 다형성·유사분열 점수(각 1~3)를 더해 Nottingham 기준으로 정함 (합 3~5 = 1, 6~7 = 2, 8~9 = 3). 차트에는 세 점수를 그대로 적음 | `origin = real`, `rule_id = M-05` |
| 21명 | Data S2에 세 점수가 다 없어 **합성**. 아형별 등급 비율(한국유방암등록, Won 2022)에서 뽑음. 차트에 세 점수를 적지 않음 | `origin = synthetic`, `rule_id = Y-05` |

- 원본 표(`mmc3.xlsx`)는 이 저장소에 넣지 않는다. 쓰려면 원 논문의 부록에서 받는다 (`python -m vh.fetch_thennavan`).
- 다른 조직 소견(염증, 괴사, 림프혈관 침범 등)은 쓰지 않았다.
- 비영리 연구 목적이다. 규칙: [rules/rules.csv](../../rules/rules.csv)의 M-05, Y-05.

## 식별줄 (이름·등록번호·주민번호·연락처)

차트의 환자명·등록번호·주민번호·연락처는 모두 가짜 값이다 (규칙 R-08, Y-08). 이름은 통계청 2015 인구주택총조사 상위 10개 성씨의 인원 비율과 정해 둔 글자 조합에서 vp 번호로 뽑은 가상 이름이며 실제 인물이 아니다 (목록과 출처: [rules/names.csv](../rules/names.csv)).
