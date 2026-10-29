# 제안: 추천 결과에 참고란(`clinical_notes`) 추가

> 작성 B · 2026-10-29 · 받는 사람 A, C, D (4명 검토) · 대상 `schemas/recommendation.json`
> **확정 (2026-10-29):** 팀에 공유한 뒤 "B가 정해 알려 달라"는 답을 받아 이 제안대로 반영했다. 금기 계열 후보는 빼지 않고 `applies_to`로 표시만 한다. `schemas/recommendation.json`의 `clinical_notes`, `src/recommend/clinical_notes.py`

## 1. 배경

- A의 draft7 체크리스트 §1.3: `comorbidities` → `contraindicated_classes`(금기 약 계열)를 추천에서 빼거나 경고로 낼지 정한다.
- C 답 (2026-10-29): 금기 계열은 의사가 화면 1에서 확정한다. C 검색은 금기 계열이 있으면 동반질환 관련 ESMO 권고를 함께 찾고(PR #79), 금기 약 권고를 빼거나 감점하지 않고 그대로 넘긴다.
- A 답 (2026-10-29): 동반질환별로 어떤 약 계열을 못 쓰는지 정한 근거 문서가 없다. 선택지 4개 중 고른다.
- **B 선택: (3) 처방 추천 화면에 참고란을 추가한다.** 근거 없이 "어떤 병이면 어떤 약 금지" 규칙을 만들지 않고, 동반질환 정보와 C가 찾은 ESMO 권고를 함께 보여 준 뒤 판단은 의사에게 맡긴다.
  - (1) 새 근거 문서 찾기: 외부 자료의 라이선스 확인이 필요하고, 쓸 수 없는 지침(NCCN·ASCO 등)이 많다
  - (2) ESMO 청크 3개로 규칙 만들기: ESMO는 "동반질환·PS 때문에 CDK4/6(또는 항HER2)을 못 쓰면 내분비 단독"이라고만 하고 어떤 병이면 못 쓰는지는 정하지 않아, 결국 규칙을 지어내야 한다
  - (4) 넣지 않기: 장기 위기·동반질환 정보가 화면에 보이지 않는다

## 2. 지금 스키마에 담을 곳이 없는 이유

`recommendation.json`의 후보(`options[]`) 칸은 `therapy`, `drugs`, `rationale`, `evidence`, `guideline_source`, `citations`, `reimbursement`, `reimbursement_reason`, `reimbursement_citations`, `copay`, `pending_notices`다. 최상위의 비슷한 칸은 `conflicts`(글 목록, "지침 권고 차수와 급여 기준 차수가 다름" 같은 충돌 메모)뿐이라, 충돌이 아닌 참고 정보를 넣으면 뜻이 섞인다.

## 3. 제안하는 칸

최상위에 선택 칸 `clinical_notes`를 더한다. 없거나 빈 목록이면 참고할 내용이 없다는 뜻이라 기존 출력은 그대로 통과한다.

```json
"clinical_notes": {
  "type": "array",
  "description": "의사가 처방을 고를 때 참고할 환자 상태와 관련 지침 권고. 시스템이 약을 빼거나 바꾸지 않고 보여 주기만 한다 (2026-10-29 제안, 4명 검토 전)",
  "items": {
    "type": "object",
    "required": ["topic", "text", "source_fields"],
    "additionalProperties": false,
    "properties": {
      "topic": {"enum": ["comorbidity", "performance_status", "visceral_crisis", "contraindicated_classes"]},
      "text": {"type": "string", "description": "B 규칙 코드가 정해진 틀로 만드는 문장. LLM이 쓰지 않는다. 지침 원문을 옮기지 않는다"},
      "source_fields": {"type": "array", "items": {"type": "string"},
                        "description": "문장에 쓴 환자 칸 경로. 예: confirmed_state.items.contraindicated_classes"},
      "citations": {"type": "array", "items": {"type": "string"},
                    "description": "관련 지침 청크 ID. recommend()에 넘어온 지침 청크 안의 ID만 (환각 방지 규칙 1과 같음)"},
      "applies_to": {"type": "array", "items": {"type": "string"},
                     "description": "이 참고가 걸리는 후보 요법(options[].therapy). 없으면 환자 전체에 대한 참고"}
    }
  }
}
```

## 4. 채우는 방법 (B, `src/recommend/`)

LLM 답과 상관없이 후처리 단계에서 규칙 코드가 채운다. 약을 빼거나 급여 분류를 바꾸지 않는다.

| topic | 언제 넣나 | 문장 틀 (예) | 근거 칸 |
|---|---|---|---|
| `comorbidity` | 동반질환 기록이 있을 때 | "동반질환: CKD 3a (eGFR 52)" | `patient_state.fields.patient.comorbidities` |
| `performance_status` | ECOG 기록이 있을 때 | "ECOG 1" | `patient_state.fields.patient.ecog` |
| `visceral_crisis` | 의사가 장기 위기 예로 확정했을 때 | "장기 위기: 예 (의사 확정)" | `confirmed_state.items.visceral_crisis` |
| `contraindicated_classes` | 의사가 금기 계열을 확정했을 때 | "의사가 금기로 확정한 계열: CDK4/6_inhibitor" | `confirmed_state.items.contraindicated_classes` |

- 위 문장에 관련 ESMO 청크가 지침 청크 목록 안에 있으면 `citations`에 ID를 붙인다. 예: `esmo-mbc-2026-05-luminal-1l-e03e88`, `esmo-mbc-2026-05-her2-1l-2cded5`, `esmo-mbc-2026-05-her2-1l-58a1c0` (C가 동반질환 질의로 찾는 청크, A 답에 적힌 ID). 화면에는 청크 ID로 원문을 연결하고, 참고란 문장에 ESMO 문장을 옮기지 않는다.
- `contraindicated_classes`가 있으면, 그 계열 약(`data/dictionaries/drug_classes.csv`의 `drug_subclass`·`drug_class`)이 든 후보 요법 이름을 `applies_to`에 적는다. 후보는 지우지 않는다.

## 5. 화면 예시

```
[참고]
· 동반질환: CKD 3a (eGFR 52) / ECOG 1 / 심장 질환 없음
· 의사가 금기로 확정한 계열: CDK4/6_inhibitor → 해당 후보: palbociclib + letrozole
  관련 지침: ESMO MBC 2026-05 [luminal-1l-e03e88]
```

## 6. 영향

| 누구 | 바뀌는 것 |
|---|---|
| B | `postprocess.py`에서 참고란 채우기, `validate.py` 스키마 검사, 테스트 (가상 환자 VC-0108 CKD 3a, 보류 VC-0137 CKD 3b) |
| C | 없음 (지금처럼 동반질환 질의로 청크를 찾아 넘긴다) |
| D | 없음 (급여 판정과 무관) |
| A | `confirmed_state` 항목은 이미 있음. 화면 1·2를 만들 때 참고란 표시 |

## 7. 같이 정할 것

- [ ] 칸 이름과 모양 (`clinical_notes`, 위 4개 topic)
- [ ] 금기 계열에 걸리는 후보를 지우지 않고 `applies_to`로 표시만 하는 방식에 동의하는지 (C의 처음 제안은 "후보에서 빼고 사유와 함께 따로 보여 주기"였다. A 답의 (3)을 따르면 빼지 않는다)
- [ ] "급여만 있는 요법" 별도 칸(C 제안, 지난 회의 안건)과 같은 PR로 검토할지
- [ ] 2단계가 `confirmed_state`만 읽기로 할 때 `comorbidities`·`ecog`도 확정 항목으로 옮길지 (A 체크리스트 §5)
