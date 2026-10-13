# A → B 전달 문서: BM-3 근거 주석에서 OncoKB를 빼고 대체 출처를 쓰는 제안

> 작성: 담당 A · 2026-10-13
> 받는 사람: 담당 B ([2] 바이오마커 모듈)
> 관련 문서: PROJECT.md §5 (BM-3, BM-2 판정 기준표), §10 (데이터셋), `schemas/biomarker_record.json`
> 상태: **제안**. 채택 여부와 스키마 변경은 4명 합의로 정한다.

## 0. 요약

1. **OncoKB는 쓰지 않는 것을 제안한다.** 우리 팀 조건(기관 이메일 없음, 수동 심사 대상 제외, 부트캠프)에 맞지 않고, AI/ML 학습에 쓰는 것을 학술 목적까지 포함해 금지한다 (§1).
2. 대체 조합: **① FDA·식약처 허가사항(동반진단 변이 목록) → ② CIViC → ClinVar(생식세포) → Ensembl VEP(PTEN 기능 소실)** (§2).
3. 네 가지 모두 가입·심사 없이 받을 수 있고, **파일로 받아 로컬에서 조회**한다. 환자에게서 나온 변이 정보가 외부 서버로 나가지 않으므로 "차트 정보는 외부 API로 보내지 않는다" 원칙과도 맞는다.
4. B가 할 일: BM-3 규칙표와 조회 코드를 작성하고 스키마 변경을 제안한다 (§5).

## 1. OncoKB를 빼는 이유

2026-10-13 OncoKB 라이선스 FAQ(https://faq.oncokb.org/licensing)에서 확인했다.

| 조건 | OncoKB | 우리 상황 |
|---|---|---|
| 학술 무료 이용 자격 | "register your account using your institution/university email address" | 기관 이메일 없음 |
| 가입·API 접근 | 계정을 수동으로 심사하고, API는 사용 목적을 적어 따로 신청 | 수동 심사 대상은 후보에서 제외 (팀 원칙) |
| AI/ML 학습 | "OncoKB cannot be used to train AI/ML models whether for academic or commercial purposes" | 나중에 학습·평가 라벨로 쓸 가능성이 있음 |
| 로컬 DB 사본 | 사례별로만, 추가 비용 | 외부 API를 피하려면 로컬 사본이 필요 |
| 부트캠프 | "academic setting"에 해당하는지 불분명 | 판단 근거 없음 |

**함께 지킬 것:** cBioPortal 화면에 보이는 변이 주석(Oncogenic, Level 등)은 OncoKB 데이터다. MSK-IMPACT 등의 변이 원자료는 써도 되지만, **화면의 주석을 옮겨 적거나 정답으로 쓰지 않는다.**

## 2. 대체 출처

| 순서 | 출처 | 쓰는 곳 | 라이선스·접근 (확인 내용) | 받는 방법 |
|---|---|---|---|---|
| ① | **FDA 라벨(DailyMed)과 동반진단 요약(SSED), 식약처 의약품 허가사항** | PIK3CA, AKT1, PTEN, ESR1 중 치료 대상 변이 | 미국 정부 저작물과 국내 공공 문서. 가입 필요 없음 | 원문에서 변이 목록을 옮겨 규칙표로 만든다 (출처 문서·쪽 기록) |
| ② | **CIViC** (civicdb.org) | 허가 목록에 없는 체세포 변이의 근거 | **CC0 1.0 퍼블릭 도메인**. 재배포·상업 이용·학습에 제한 없음. 2026-10-13 로그인 없이 GraphQL API 응답 확인, nightly TSV 다운로드 확인(PIK3CA·AKT1·PTEN·ESR1 관련 108행) | `https://civicdb.org/downloads/nightly/` TSV를 날짜별로 받아 로컬 조회 |
| — | **ClinVar** (NCBI) | gBRCA1/2, PALB2, PTEN 미스센스 | NCBI 정책: "no restrictions on the use or distribution". FTP 다운로드는 가입 필요 없음 | FTP의 VCF 또는 `variant_summary.txt.gz`를 받아 로컬 조회 |
| — | **Ensembl VEP** | PTEN 절단형 변이(기능 소실) 판정, 표기 정규화 | Apache 2.0, 로컬 실행 | 로컬 설치 또는 Docker |

### 제외한 후보

| 후보 | 이유 |
|---|---|
| OncoKB | §1 |
| COSMIC | 학술 무료 이용도 가입과 기관 확인 필요 |
| JAX-CKB | 계정 등록 필요 |
| Cancer Genome Interpreter | 등록 필요. 약관 페이지가 403으로 막혀 라이선스 확인 못 함 |
| Cancer Hotspots | 코드는 AGPL-3.0, 데이터 라이선스가 명시되지 않아 확인 못 함 |
| cBioPortal 화면 주석 | 내용이 OncoKB 데이터 |

## 3. 바이오마커별 판정 제안

PROJECT.md §5 판정 기준표의 "OncoKB 발암성 변이"를 아래로 바꾸는 제안이다. 위에서부터 처음 맞는 줄로 판정한다.

| 바이오마커 | 순서 | 조건 | 상태값 | 비고 |
|---|---|---|---|---|
| PIK3CA | 1 | 허가 동반진단 변이 목록에 있음 | 양성 | 예: C420R, E542K, E545A/D/G/K, Q546E/R, H1047L/R/Y (알펠리십 동반진단 기준. **원문에서 다시 확인**) |
| | 2 | 목록에 없고 CIViC에 발암성·예측 근거가 있음 | 양성 + `off-label-variant` 태그 | 근거 등급(A~E)을 함께 저장 |
| | 3 | 둘 다 아님 | VUS (음성 처리, 표시 유지) | |
| AKT1 | 1 | 허가 근거 변이 (예: E17K, 카피바설팁) | 양성 | 원문 확인 |
| | 2 | CIViC 근거 | 양성 + 태그 | |
| PTEN | 1 | VEP 결과 절단형(nonsense, frameshift, 필수 스플라이스 부위) | 양성 (기능 소실) | |
| | 2 | 미스센스이고 ClinVar 병원성·병원성 가능 또는 CIViC 근거 있음 | 양성 | |
| | 3 | 그 외 | VUS | |
| ESR1 | 1 | 엘라세스트란트 동반진단의 리간드 결합 도메인 변이 (예: Y537S/N/C, D538G 등) | 양성 | 원문 확인. 이후 승인된 SERD 라벨도 확인 |
| | 2 | 기존 "재검 필요" 규칙은 그대로 | | |
| gBRCA1/2, PALB2 | 1 | ClinVar 병원성·병원성 가능이고 리뷰 등급 2성 이상 | 양성 | ACMG 4·5등급 대응 |
| | 2 | 판정 상충 또는 1성 이하 | VUS | |

변이 목록은 A가 기억하는 내용으로 쓴 **예시**다. 규칙표에는 반드시 원문(DailyMed 라벨, FDA SSED, 식약처 허가사항)에서 옮겨 적고, 출처 문서·버전·쪽을 함께 저장한다.

## 4. 스키마 변경 제안 (4명 합의 필요)

현재 `schemas/biomarker_record.json`의 `evidence`에 `oncokb` 필드가 있다. 출처에 묶이지 않는 형식으로 바꾸는 것을 제안한다.

```json
"annotation": {
  "type": ["object", "null"],
  "properties": {
    "source": {"enum": ["label", "civic", "clinvar", "vep"]},
    "source_version": {"type": "string", "description": "예: civic nightly 2026-10-13, clinvar 2026-10-05, 라벨 개정일"},
    "call": {"type": "string", "description": "예: 허가 동반진단 변이, Pathogenic (2성), CIViC 근거 B"},
    "citation": {"type": "string", "description": "예: Piqray 라벨 §14, CIViC EID1234"}
  }
}
```

`clinvar` 필드는 `annotation`으로 합칠지, 따로 둘지 B가 정한다.

## 5. B가 할 일

1. §3 규칙표 확정: 허가사항 원문에서 변이 목록을 옮기고 출처를 기록한다.
2. 다운로드 스크립트: CIViC nightly TSV, ClinVar `variant_summary`를 날짜별로 받는다. 위치는 `data/script/`.
3. BM-3 조회 코드: `src/biomarker/`에 작성한다. **외부 API를 호출하지 않고 로컬 파일만 조회**한다.
4. 스키마 변경 제안(§4)을 4명에게 공유한다.
5. 테스트: `tests/biomarker/`에 허가 목록 변이, CIViC 전용 변이, PTEN 절단형, ClinVar 상충 변이 사례를 하나씩 둔다.

## 6. 파일 관리와 인용

| 항목 | 규칙 |
|---|---|
| ClinVar VCF·`variant_summary` | 100MB가 넘으므로 커밋하지 않는다. 스크립트만 올린다 |
| CIViC TSV | CC0라 올려도 법적 문제는 없지만 크기를 확인한다. 파일명에 받은 날짜를 넣는다 |
| 인용 | CIViC: Griffith M et al., *Nat Genet* 2017;49:170–174. ClinVar: NCBI 고지 문구를 표시한다 |
| 라이선스 재확인 | 도입할 때 각 출처의 약관을 다시 확인하고 날짜를 PROJECT.md에 적는다 |

## 7. 함께 고칠 PROJECT.md 항목 (채택 시)

- §5 BM-3 표: "DB 조회 (OncoKB, ClinVar)" → "로컬 조회 (허가사항 목록, CIViC, ClinVar, VEP)"
- §5 판정 기준표 PIK3CA/AKT1/PTEN 줄: "OncoKB 발암성 변이" → §3 기준
- §9 유전체 도구: "OncoKB annotator" 삭제
- §10 데이터셋 표: OncoKB 행 → CIViC, 허가사항 동반진단 목록
- 결정 날짜와 이유(§1)를 함께 적는다
