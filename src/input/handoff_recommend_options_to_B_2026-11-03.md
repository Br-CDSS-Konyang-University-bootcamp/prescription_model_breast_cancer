# 추천 후보 두 가지 문제: 환자와 맞지 않는 후보, 약이 다른 급여 행 인용 (B 전달, 2026-11-03)

작성: 담당 A. 받는 사람: B. 앞 메모 [handoff_recommend_prompt_to_B_2026-11-02.md](handoff_recommend_prompt_to_B_2026-11-02.md)의 후속이다.

B의 `f846af9`(PR #100) 뒤 VC-0103을 화면 2로 다시 돌린 결과다. 질문지 문제는 풀렸고 후보가 5개 나온다
(전날 0개). B 코드는 고치지 않았다. 고칠지와 방법은 B가 정한다.

## 1. 실행 조건과 결과

main `39053f5` (2026-11-03), `[recommend]` qwen3:14b (GPU 서버, SSH 터널), 화면 1 기본값으로 확정한 VC-0103 v1, 57초.

| 순서 | therapy | drugs | evidence | 급여 | 지침 인용 |
|---|---|---|---|---|---|
| 1 | Fulvestrant—palbociclib | fulvestrant, palbociclib | LoE I, GoR A | 조건 확인 필요 | `esmo-mbc-2026-05-luminal-1l-0fd38a` |
| 2 | Fulvestrant—ribociclib | fulvestrant, ribociclib | LoE I, GoR A | 조건 확인 필요 | 같음 |
| 3 | Fulvestrant—abemaciclib | abemaciclib, fulvestrant | LoE I, GoR A | 조건 확인 필요 | 같음 |
| 4 | ET alone | (없음) | LoE V, GoR B | 조건 확인 필요 | `esmo-mbc-2026-05-luminal-1l-e03e88` |
| 5 | **AI—palbociclib** | **palbociclib** | (없음) | 조건 확인 필요 | `esmo-mbc-2026-05-fig2-a9baa4` |

1~3번은 시나리오 정답과 맞다 (보조 ET 중 재발 → fulvestrant + CDK4/6). `safety_violations()`는 위반 0건이다.

## 2. 문제 1: 5번 후보가 환자와 맞지 않는다

- VC-0103은 **보조 anastrozole(비스테로이드성 AI) 투여 중 재발**했다 (`treatment_history`: anastrozole, adjuvant, PD, progression.
  확정값 `endocrine_relapse_12m` = yes).
- 5번의 rationale은 "AI—CDK4/6 inhibitor is recommended for … de novo or recurring >12 months after the end of adjuvant ET"로,
  **환자와 반대 조건**의 권고다. 인용한 `fig2-a9baa4`는 "보조 ET 중 또는 종료 12개월 이내 재발" 경로라
  rationale 문장이 인용 청크의 경로와도 맞지 않는다.
- `drugs`가 `palbociclib` 하나다. 후처리 규칙 7이 인용 청크에서 채웠는데, "AI"(계열 이름)는 약으로 풀리지 않았다.
- 안전 검사 ③(기준일 전 진행한 약 재추천)은 약 이름(anastrozole)만 보므로, AI 계열(letrozole·anastrozole) 후보를 잡지 못한다.

A 제안 (B가 정함):
1. 후처리에서 rationale의 조건과 확정값을 대조: `endocrine_relapse_12m = yes`인데 ">12 months"·"de novo" 경로의 AI 병용을 쓰면 지우거나 `conflicts`로
2. 안전 검사 ③을 약 이름뿐 아니라 진행한 약의 `drug_subclass`(AI_nonsteroidal 등)로도 보기 (PROJECT.md 문구는 팀 확인)
3. 규칙 7이 therapy의 계열 이름(AI, ET)을 약으로 풀지 못하면 `drugs`를 비운 채 두고 표시

## 3. 문제 2: 후보마다 약이 다른 급여 행까지 인용한다

1~3번 후보가 **같은 급여 행 8개**를 인용한다 (4·5번은 그중 1차 행 6개):

| 급여 행 | 행의 약 |
|---|---|
| `hira-booklet-20261101-bc-pal-endo-2lplus-r07` | palbociclib, fulvestrant |
| `…-2lplus-r08` | abemaciclib, fulvestrant |
| `…-1l-r01` / `r02` | palbociclib + letrozole / anastrozole |
| `…-1l-r03` / `r04` | abemaciclib + letrozole / anastrozole |
| `…-1l-r05` / `r06` | ribociclib + letrozole / anastrozole |

예: fulvestrant + ribociclib 후보에 맞는 행은 `…-2lplus-r09`(ribociclib + fulvestrant)인데, 이 행은 검색되어 질문지에도 들어갔지만
인용하지 않고 맞지 않는 8개를 인용했다.

- 후처리 5번(`_classify`)은 인용한 행이 시행 중인지만 보고, **행의 약이 후보 약과 맞는지는 보지 않는다.**
- `make_conditions_checker`는 인용 행 중 **하나라도 충족이면 충족**이다. 지금은 `conditions_reviewed=False`라 "조건 확인 필요"로만 나오지만,
  검수가 끝나 `True`가 되면 다른 약의 행(예: palbociclib + letrozole 1차 행) 조건으로 fulvestrant 후보가 "급여"가 될 수 있다.

A 제안 (B가 정함):
1. 후처리에서 후보 `drugs`가 모두 행의 `drugs`에 있는 행만 남기기 (C `search_reimbursement`의 "후보 약이 모두 행에 있어야" 규칙과 같게)
2. 남는 행이 없으면 `no_criteria`, 이유에 "후보 약과 맞는 급여 행 없음"
3. 맞는 행을 LLM이 인용하지 않은 경우(2번 후보와 r09)는, 후처리가 넘겨받은 급여 청크 중 약이 맞는 행을 찾아 붙이는 방법도 있다 (급여 판정은 어차피 conditions_eval이 한다)

## 4. 재현

```bash
python -m src.app.script.screen1 --llm-host http://127.0.0.1:11435
```

화면 1에서 VC-0103 확정 → 화면 2. 추천 결과는 `data/app/recommendations/VC-0103/c1.json` (git에 올라가지 않음).
공고 원문은 옮기지 않고 청크 ID와 약 이름만 적었다.
## 5. B 반영 확인 (2026-11-04)

B의 `264a449`·`a8f312f`·`22c3e32`·`a95a4eb`·`7076d71`(PR #121·#123·#124) 뒤, D가 검수한 급여 청크(공고책자 2026-11-01, 급여 131개)를 색인하고 다시 돌렸다.
조건: main `ba33610`, `[recommend]` qwen3:14b (GPU 서버, SSH 터널), 각 사례의 gold `expected/confirmed_state.json`, `python -m src.app.script.run_flow --out data/app/runs/20261104`.

### 5.1 VC-0103: 문제 1·2 모두 풀림 (139초)

| 순서 | therapy | drugs | 급여 | 급여 인용 | 지침 인용 |
|---|---|---|---|---|---|
| 1 | Fulvestrant—palbociclib | fulvestrant, palbociclib | 급여 | `…-2lplus-r07` | `luminal-1l-0fd38a` |
| 2 | Fulvestrant—ribociclib | fulvestrant, ribociclib | 급여 | `…-2lplus-r09` | 같음 |
| 3 | Fulvestrant—abemaciclib | fulvestrant, abemaciclib | 급여 | `…-2lplus-r08` | 같음 |

- 문제 1: AI—palbociclib 후보가 없어졌다. 시나리오대로 fulvestrant + CDK4/6 셋만 나온다.
- 문제 2: 후보마다 약이 같은 급여 행 하나만 인용한다. 앞에서 빠졌던 ribociclib 행 `r09`도 붙었다. 셋 다 D 검수 조건으로 "급여"이고, 이유에 "의료진 검토 전"이 붙는다.

### 5.2 46건 전체

`run_flow` 46건(VC-0106b, VC-0129는 gold 확정값이 없어 뺌). 실행 오류 0건, 사례당 80~424초(평균 약 164초).
C 정답(28건, 모두 `reviewed`, PR #130)과 대조한 결과다. VC-0124는 C의 검색 수정(`dbf9b7c`, ER 저발현이면 TNBC 권고도 찾음) 전에 돌려 다시 돌려야 한다.

| 항목 | 결과 |
|---|---|
| 정답 청크를 검색 | 28/28 |
| 후보가 정답 청크를 인용 | 18/28 |
| 1순위 후보가 정답 청크를 인용 | 16/28 |
| C가 `not_expected`로 둔 청크를 인용 | 9건 (VC-0101·0102·0123은 모두 `luminal-2l-4bcee1`, 세 건 모두 1순위는 맞음) |

급여 분류(후보 130개): 급여 30, 조건 확인 필요 53, 해당 기준 없음 47.

### 5.3 B가 볼 것 (A 제안, B가 정함)

**1) 후보가 0개인 6건.** 화면 2에 빈 목록이 나온다.

| 사례 | 원인 (`c1.json`의 `log`) |
|---|---|
| VC-0110, VC-0114, VC-0116 | LLM 답이 두 번 모두 스키마 불통과: 급여 분류가 `no_criteria`가 아닌데 `reimbursement_citations`가 빈 목록. VC-0110은 질문지 길이 제한으로 급여 청크 19개를 빼고 보냈다(424초) |
| VC-0134, VC-0142 | 후보마다 근거 문장에 지침 인용이 없어 후처리가 모든 후보를 지움. VC-0134는 부모 ID(`esmo-ebc-2024-02-hrpos`)를 인용해 "받지 않은 청크 ID"로 지워진 문장도 있음 |
| VC-0126 | LLM이 처음부터 빈 `options`를 냄 (`out_of_scope` false, log 없음) |

제안: 첫 3건은 스키마에서 떨어뜨리는 대신, 급여 인용이 비면 후처리가 `no_criteria`로 바꾸고 이유를 적거나, 넘겨받은 급여 청크 중 약이 맞는 행을 붙인다(§3 제안 3과 같음).
VC-0134는 부모 ID를 인용하면 그 부모의 자식 청크 중 넘겨받은 것으로 바꾸는 방법도 있다.

**2) 정답 청크를 받고도 인용하지 않은 사례.** 후보는 나왔다: VC-0104(TNBC 1차), VC-0107, VC-0112(HER2+ 1차), VC-0117, VC-0121.

**3) 골 보호제.** 주 후보 5칸을 차지하거나(VC-0113·VC-0124 1위) 빠지는(VC-0108) 문제는 팀 안건 A(`team_agenda_A_2026-11-04.md`, PR #129)와 스키마 초안 PR #131(`supportive_options`)에서 따로 다룬다. 같은 파일(`llm_link.py`, 프롬프트, 후처리)을 고치게 되니 1)과 함께 보면 재실행을 한 번에 할 수 있다.

### 5.4 재현

```bash
python -m src.app.script.run_flow --out data/app/runs/<이름> --llm-host http://127.0.0.1:11435
python -m src.app.script.run_flow --out data/app/runs/<이름> --summary
```

결과 `data/app/runs/20261104/<사례>/c1.json`, 표 `summary.csv`(git에 올라가지 않음). 공고 원문은 옮기지 않고 청크 ID와 약 이름만 적었다.
