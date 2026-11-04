# A(입력·화면) 팀 논의 안건 · 2026-11-04

작성: A

관련: C 안건 1 (`src/rag/team_agenda_C_2026-11-03.md`, PR #125, VC-0108 골 보호제 결정)

> **2026-11-04 상태:** C 안건 문서에 팀 채택으로 기록됨(`fc04ced`, PR #128). 안건 6-1의 'v0.2 결정 종류 칸'은 철회. C는 정답 파일에 `expected_supportive`를 두고 VC-0108·VC-0106을 반영함. 남은 일은 아래 "조원별 할 일".

## 안건 6-1 대안: 골 보호제를 '결정 종류' 칸 대신 '보조 약물' 칸으로 분리

### 제안 요약

골 보호제(denosumab, zoledronic acid, bisphosphonate)를 주 처방 후보 5칸에서 빼고, 화면 2에 **"함께 처방할 보조 약물"** 칸을 따로 둡니다. 의사는 화면 2에서 주 처방 하나와 보조 약물을 **한 번에** 고르고, 결과는 `prescription_decision` 하나에 저장합니다. 이렇게 하면 C가 v0.2에 제안한 "결정 종류" 칸(화면 1에서 먼저 고르는 방식)은 필요 없습니다.

### 이유

1. **골 보호제는 주 처방이 아니라 더해 주는 약입니다.**
   - 전이성 뼈 전이: 뼈 합병증 예방용 지지 약물입니다. 항암·내분비 치료를 대신하지 않습니다.
   - 조기 폐경 후 고위험: 보조 내분비요법에 **더하는** 약입니다(ESMO EBC).
   - 따라서 항암·내분비 후보와 한 줄로 순위를 매길 대상이 아닙니다.

2. **46건 실행(`run_flow`, 2026-11-04, qwen3:14b)에서 실제로 주 후보 자리를 차지했습니다.**

   | 사례 | 상황 | 골 보호제 위치 |
   |---|---|---|
   | VC-0113 | 전이성, 내분비 3차 이상 | **1위** BMA (T-DXd, sacituzumab이 그 뒤로 밀림) |
   | VC-0124 | 조기, **선행요법** 결정 | **1위** adjuvant bisphosphonate (수술 전 결정인데 수술 후 약이 1위) |
   | VC-0143 | 전이성 1차 | 2위 BMA |
   | VC-0109, VC-0132, VC-0133 | 조기 보조요법 | 2위 bisphosphonate |

3. **VC-0108은 반대로 골 보호제가 아예 빠졌습니다.**
   - C의 검색은 정답 청크(`esmo-mbc-2026-05-site-bone-087674`)와 D의 denosumab 급여 청크(`hira-booklet-20261101-supp-denosumab-1`)를 모두 찾아왔습니다.
   - 그런데 B의 추천 5개는 모두 CDK4/6 병용이었습니다. 환자가 이미 먹고 있는 약입니다.
   - 보조 약물 칸이 따로 있으면, 뼈 전이가 있을 때 결정 종류와 상관없이 denosumab이 표시됩니다.

4. **의사가 두 번 결정하지 않아도 됩니다.** 결정 종류 칸 방식은 화면 1에서 "골 보호제"를 고르면 전신 치료 추천이 나오지 않습니다. 둘 다 필요한 환자(전이 1차 시작 + 뼈 전이)는 두 번 돌려야 합니다.

### 화면 2 모습 (예: VC-0108)

```
[주 처방]  (하나 고름)
 ○ 현재 치료 유지 (ribociclib + letrozole)
 ○ 1. ...
 ○ 직접 입력 / 보류

[함께 처방할 보조 약물]  (해당되면 체크)
 ☐ Denosumab: 뼈 전이 [ESMO MBC 뼈 전이 권고 / 급여 기준 있음]
 ☐ Zoledronic acid: 뼈 전이
```

### 바꿀 곳

| 담당 | 바꿀 것 |
|---|---|
| 공동 `schemas/recommendation.json` | `options` 옆에 `supportive_options` 추가. 항목 형식은 `options`와 같게(근거 인용, 급여 분류) **(4명 검토)** |
| B `recommend()` | 골 보호제는 `supportive_options`에만 넣음. 주 후보 5칸에서 제외 |
| C | 검색 코드는 그대로 둠(뼈 전이 추가 검색이 이미 찾음). VC-0108·VC-0113 등 정답 파일에 보조 칸 기준을 표시 |
| D | 바꿀 것 없음(`supp-*` 급여 청크 그대로 사용) |
| A 화면 2, `prescription_decision` | 보조 약물 체크 칸, **"현재 치료 유지"** 선택지(지금은 추천안 선택·직접 입력·보류뿐), 저장 칸 `supportive` 추가 |

### 조원별 할 일 (제안이 받아들여질 때)

순서: ① 공동 스키마 합의 → ② B·C·A 동시 작업 → ③ A가 `run_flow`로 골 보호제 사례를 다시 돌려 확인.

**공동 (A·B·C·D 네 명)**
- [ ] `schemas/recommendation.json`에 `supportive_options` 추가안 검토·승인. 항목 형식은 `options`와 같게 둠(`therapy`, `drugs`, `rationale`, `citations`, `reimbursement`, `reimbursement_reason`, `reimbursement_citations`).
- [ ] v0.1 포함 여부, 보조 약물 범위(골 보호제만) 결정.

**B (`src/recommend/`)**
- [ ] 골 보호제를 고르는 기준을 약 분류로 정함. `data/dictionaries/drug_classes.csv`에 이미 `Bone-modifying Agent`(denosumab, zoledronic acid, pamidronate, ibandronate, clodronate)가 있어 이 분류로 가를 수 있음.
- [ ] 프롬프트: 골 보호제는 `supportive_options`에만 쓰고 주 후보 5칸에는 넣지 않게 함.
- [ ] 후처리: LLM이 주 후보에 골 보호제를 넣으면 `supportive_options`로 옮김. 인용 검사(받지 않은 청크 ID, 인용 없는 문장 삭제)를 보조 칸에도 똑같이 적용.
- [ ] 뼈 전이 청크(`site-bone-*`)나 조기 bisphosphonate 청크가 넘어오면 보조 칸을 채움(VC-0108처럼 주 결정이 내분비 1차여도).
- [ ] `tests/recommend/`에 VC-0108(뼈 전이, 주 후보에 골 보호제 없음)과 VC-0113(주 후보 1위가 BMA였던 사례) 테스트 추가.

**C (`src/rag/`, C 정답 파일)**
- [ ] 검색 코드는 그대로 둠(뼈 전이 추가 검색이 이미 정답 청크를 찾음).
- [x] 정답 파일에 `expected_supportive`(보조 약물 정답) 키를 두고 주 처방 순위·MRR과 따로 채점(`check_case`, `review_guideline`). VC-0108(주 처방 정답은 지금 치료 유지 근거 02649c, 보조는 BMA 087674), VC-0106(비스포스포네이트 fca2a7)을 옮김. VC-0108 note의 'v0.2 결정 종류 칸' 문구도 바꿈 (`fc04ced`).
- [ ] 46건 실행에서 골 보호제가 후보로 나온 나머지 사례(VC-0109, VC-0113, VC-0124, VC-0132, VC-0133, VC-0143)도 보조 약물 정답이 필요한지 확인. VC-0124는 선행요법 결정이라 수술 후 bisphosphonate가 보조 칸에도 맞지 않을 수 있음.

**D (`src/reimbursement/`)**
- [ ] 코드 변경 없음.
- [ ] 골 보호제 급여 청크(`supp-denosumab-1`, `supp-zoledronic-a`, `supp-zoledronic-b`)의 조건이 검수 완료인지, 차수 구분 없이 검색되는지 확인.

**A (`src/app/`, 화면 2)**
- [ ] 화면 2에 "함께 처방할 보조 약물" 체크 칸 추가(여러 개 선택 가능, 근거와 급여 분류 표시).
- [ ] 주 처방 선택지에 **"현재 치료 유지"** 추가(지금은 추천안 선택·직접 입력·보류뿐).
- [ ] `src/app/prescription_decision.json` 초안에 `supportive` 목록과 유지 선택지 추가, `save_decision` 검사와 `tests/app/test_decision.py` 고침.
- [ ] `run_flow`의 `summary.csv`에 보조 약물 열과 C 보조 정답 대조 추가. B·C 작업이 끝나면 위 7건을 다시 돌려 결과 공유.

### 팀이 정할 것

1. v0.1에 넣을지, v0.2로 넘길지.
   - A 의견: 위 표처럼 이미 6건에서 주 후보 순서를 흐리므로 **v0.1에 넣기**를 제안합니다.
2. 보조 약물 범위: v0.1은 지침과 급여 자료에 실제로 있는 **골 보호제만** 넣고, 구토 방지제 같은 다른 지지 요법 약은 v0.2에서 판단.
3. ~~이 제안을 받아들이면 안건 6-1의 "v0.2 결정 종류 칸"은 철회.~~ 철회됨(`fc04ced`). 국소 치료(수술·방사선) 결정이 필요해질 때 다시 논의.
