# TCGA ① (수술 후) 가상환자 세트 — 생성 보고

mini 커밋: `a8f9363` · 실행: `python -m src.virtual_hospital.build`

## 인원

| 항목 | 수 |
|---|---|
| 세트 (관문 통과) | 671 |
| 뺀 환자: S-02 | 8 |
| 뺀 환자: S-03 | 9 |
| 뺀 환자: S-04 | 80 |
| 뺀 환자: S-07 | 25 |
| 뺀 환자: S-08 | 7 |
| 뺀 환자: S-09 | 2 |
| 뺀 환자: S-10 | 36 |
| 넘길 목록 (실제 값 원인) | 0 |

아형 (규칙 판정): HR+/HER2- 445, HER2+ 116, TNBC 110

## 칸 출처 (present 칸 수)

| origin | 규칙 | 칸 수 |
|---|---|---|
| derived | D-01 | 671 |
| derived | D-03 | 671 |
| derived | D-05 | 925 |
| derived | D-06 | 96 |
| derived | D-06, D-05 | 13 |
| derived | D-06, D-11, D-05 | 1 |
| derived | D-08 | 280 |
| derived | D-11 | 1 |
| real | D-09 | 124 |
| real | M-01 | 10812 |
| real | M-05 | 650 |
| synthetic | Y-01 | 671 |
| synthetic | Y-02 | 44 |
| synthetic | Y-04 | 671 |
| synthetic | Y-05 | 21 |
| synthetic | Y-06 | 938 |
| synthetic | Y-07 | 268 |

## 검증

### V1 복사 — 통과

```
{
 "checks": {
  "나이": 671,
  "ER 판정": 671,
  "PR 판정": 671,
  "pT": 671,
  "grade (Nottingham)": 650,
  "pM": 442,
  "병기군": 671,
  "HER2 IHC 점수": 420
 },
 "mismatch": []
}
```

### V2 계산 — 통과

```
{
 "n": 671,
 "mismatch": []
}
```

### V3 분포 — 통과

```
{
 "폐경 (실제 %, 다시 만든 %, 779명)": {
  "premenopausal": [
   23.5,
   23.0
  ],
  "postmenopausal": [
   72.7,
   72.9
  ],
  "perimenopausal": [
   3.9,
   4.1
  ]
 },
 "폐경 최대 차이 %p": 0.5,
 "receptors.er_percent 구간 최대 차이 %p (경계 밖 양성 331명)": 2.1,
 "receptors.pr_percent 구간 최대 차이 %p (경계 밖 양성 233명)": 2.1,
 "기준 %p": 5.0
}
```

### V4 관계 — 통과

```
{
 "Ki-67 높음 비율 (PAM50별)": {
  "BRCA_Her2": 0.79,
  "BRCA_LumA": 0.28,
  "BRCA_Normal": 0.32,
  "BRCA_LumB": 0.7,
  "BRCA_Basal": 0.76,
  "?": 0.36
 },
 "grade 3 비율 (아형별)": {
  "HER2+": 0.41,
  "HR+/HER2-": 0.24,
  "TNBC": 0.83
 },
 "기대": "LumA < LumB, HR+/HER2- < TNBC"
}
```

### V6 이미지 좌표 — 통과

```
{
 "n": 720,
 "mismatch": []
}
```
