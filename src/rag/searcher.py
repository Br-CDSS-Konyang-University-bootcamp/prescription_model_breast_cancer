# src/rag/searcher.py
import copy
import math
import re
import warnings

from qdrant_client.models import Filter, FieldCondition, IsEmptyCondition, MatchAny, MatchValue, PayloadField
from .chunk_store import get_parent
from .client import get_qdrant_client, get_embedding_model, get_reranker, close_client, COLLECTION_NAME

LINE_MATCH_BONUS = 0.1  # 요청 차수와 청크 차수가 같을 때
LINE_ANY_BONUS = 0.03  # 청크 차수가 any일 때
# 청크 차수가 요청과 명확히 다를 때 (예: 2차 환자에게 1차 권고). 빼지 않고 뒤로 보낸다.
# 재정렬 모델은 1차 권고 문장의 "ER-positive, HER2-negative … MBC"가 질의와 글자 그대로 겹치면 거의 만점(≈1.0)을 줘서,
# 차수 가점(+0.1)이나 -0.3 감점으로는 2·3차 질의에서도 1차 권고가 1위였다 (평가 --auto-query M10·M11, 2026-10-20).
# 점수 범위(약 0~1.2)보다 크게 깎아, 차수가 다른 권고는 맞는 차수·any 권고 뒤에만 온다 (맞는 권고가 모자라면 채워짐)
LINE_MISMATCH_PENALTY = 1.0
TAG_BONUS = 0.05  # 요청 바이오마커 태그가 청크 태그와 하나 겹칠 때마다
RERANK_CANDIDATES = 20  # 재정렬할 때 뜻 검색으로 먼저 뽑는 후보 수
SITE_MATCH_BONUS = 0.05  # 환자에게 있는 전이 부위의 부위별 권고
# 환자에게 없는 전이 부위의 부위별 권고. 차수 감점과 같은 이유로 점수 범위보다 크게 깎는다: 재정렬 점수가
# "HER2 양성 뇌 전이 2차 T-DXd" 권고에 0.97이라 -0.3으로는 일반 2차 권고(0.15)보다 계속 위였다 (--auto-query M10).
# 부위를 알면 그런 권고는 후보에서도 뺀다(_mismatched_site_parents). 감점은 그 목록 밖의 경우를 위한 안전장치
SITE_MISMATCH_PENALTY = 1.0
# 부위별 소단원(부모 청크 이름 끝) → 그 권고가 맞는 전이 부위 (field_vocab.csv의 metastatic_sites 값).
# 연수막 전이(LMD)는 표준값이 없어 "other: leptomeningeal ..."처럼 적힌 값을 찾는다. 뇌 전이만으로는 LMD로 보지 않는다.
# de novo IV기(site-denovo)와 소수 전이(site-omd)는 부위가 아닌 상황이라 여기 넣지 않는다.
SITE_SECTIONS = {
    "site-bone": {"bone"},
    "site-bm": {"brain"},
    "site-bm-lrt": {"brain"},
    "site-bm-her2": {"brain"},
    "site-bm-her2neg": {"brain"},
    "site-lmd": {"leptomeningeal"},
}
# 환자가 음성으로 확인된 바이오마커만을 조건으로 하는 권고 (예: gBRCA 음성 환자에게 gBRCA 변이용 olaparib).
# 권고 문장이 "adjuvant … HR-positive EBC"처럼 질의와 겹쳐 재정렬 점수가 높아도 맞지 않는다 (--auto-query E01·E02·E05)
NEGATIVE_MARKER_PENALTY = 1.0
# 보조 내분비요법과 재발 시점: ESMO MBC 1차는 "보조 ET 복용 중 또는 종료 후 12개월 이내 재발"(fulvestrant-CDK4/6)과
# "de novo 또는 12개월 넘어 재발"(AI-CDK4/6)로 갈린다. 두 권고 문장이 이 한 구절만 달라 재정렬 모델이 구분하지 못했다
# (VC-0103 check_case: 12개월 이내 재발 환자에게 AI-CDK4/6이 1위, 2026-10-21). 의사가 확정한 endocrine_relapse_12m이
# 있으면 다른 갈래만 가리키는 권고·그림 경로를 차수 감점처럼 뒤로 보낸다
RELAPSE_WITHIN_12M = re.compile(r"while (receiving|on) adjuvant (ET|endocrine)|≤\s?12 months after (the )?end of adjuvant",
                                re.IGNORECASE)
RELAPSE_AFTER_12M = re.compile(r">\s?12 months after (the )?end of adjuvant", re.IGNORECASE)
RELAPSE_MISMATCH_PENALTY = 1.0
# 폐경 상태: ESMO 권고·그림 경로 중 한쪽 폐경 상태만을 대상으로 하는 것 (조기 보조 ET는 폐경 전 tamoxifen·OFS / 폐경 후 AI,
# 전이성은 폐경 전·이행기 OFS 추가). 환자의 폐경 상태와 반대쪽만 말하면 감점한다 (VC-0103 폐경 후 환자에게 폐경 전·이행기
# OFS 권고가 3위, 2026-11-02 check_case). 대상을 정하는 표현만 본다: "premenopausal node positive" 같은 예시나
# "postmenopausal or undergoing OFS"처럼 두 쪽을 다 말하는 경우, 그림 경로의 각주는 보지 않는다
PREMENOPAUSAL_SCOPE = re.compile(r"\bpremenopausal patients\b|\bpre- and perimenopausal women\b|→ premenopausal(?= →)",
                                 re.IGNORECASE)
POSTMENOPAUSAL_SCOPE = re.compile(r"\bpostmenopausal patients\b|→ postmenopausal(?= →)", re.IGNORECASE)
MENOPAUSE_MISMATCH_PENALTY = 1.0
# 장기 위기(visceral crisis): ESMO MBC는 장기 부전 임박이면 ChT를 권고한다 (luminal-1l-5c55b4, 그림 2 각주 a). 의사가 장기 위기를
# 확정했는데 내분비 기반 권고(AI-CDK4/6, fulvestrant-CDK4/6, ET 단독 …)가 질의와 겹쳐 1위에 왔다 (VC-0126 check_case, 2026-11-03).
# 장기 위기가 yes면 내분비 기반 치료만 권하는 권고·그림 경로를 감점한다. ChT·ADC·장기 부전을 함께 말하거나 "내분비 부적합"
# 경로(그림 4)는 그대로 두고, 그림 경로는 각주를 빼고 본다 (각주 a의 ChT 문장은 모든 1차 경로에 붙는다)
ENDOCRINE_BASED = re.compile(r"\bAI\b|\bET\b|endocrine|fulvestrant|tamoxifen|letrozole|anastrozole|exemestane|"
                             r"CDK4/6|elacestrant|imlunestrant|camizestrant|everolimus|capivasertib|alpelisib|inavolisib|"
                             r"\bOFS\b|ovarian (function )?suppression", re.IGNORECASE)
NOT_ENDOCRINE_ONLY = re.compile(r"\bChT\b|chemotherapy|imminent organ failure|visceral crisis|deruxtecan|T-DXd|"
                                r"sacituzumab|Dato-DXd|not suitable for ET|endocrine-resistant|endocrine or non-?endocrine|"
                                r"capecitabine|taxane|paclitaxel|docetaxel|eribulin|anthracycline|vinorelbine|"
                                r"carboplatin|platinum", re.IGNORECASE)
VISCERAL_CRISIS_PENALTY = 1.0
# 전이 후 고식 항암 여부: ESMO MBC HR+/HER2- 3차 이후는 "이전 ChT 없음"(capecitabine·taxane, T-DXd)과 "ChT 1차례 이상 뒤"
# (T-DXd HER2-low, sacituzumab, Dato-DXd)로 갈린다 (그림 4 'No previous ChT' / 'Previous ChT'). 고식 항암이 없는 환자에게
# "ChT 1차례 이상 뒤" 권고가 정답보다 위에 왔다 (VC-0113 check_case, 2026-11-03). 확정 고식 항암 차수로 반대 갈래를 감점한다.
# 보조·선행 항암은 세지 않는다 (DESTINY-Breast04처럼 보조 항암 6개월 안 재발을 1차례로 치는 예외는 차수 확정 때 의사가 정한다)
# 'beyond third-line' 재투여(ae383b)도 고식 항암 뒤 갈래로 본다: 고식 항암 없이 내분비 3차 이후에 항암을 처음 고르는 환자
# (VC-0113, VC-0125)에게 들어와 LLM이 인용했다 (A run_flow 2026-11-05 C-6)
NEEDS_PRIOR_CHEMO = re.compile(r"after at least one (prior )?line of ChT|received at least one prior line of ChT|"
                               r"→ Previous ChT →|beyond third-line treatment", re.IGNORECASE)
NO_PRIOR_CHEMO = re.compile(r"not previously received ChT|→ No previous ChT →", re.IGNORECASE)
PRIOR_CHEMO_MISMATCH_PENALTY = 1.0
# 조기 보조 결정의 갈래: ESMO EBC 권고·그림 경로는 '수술 먼저 한 환자'(stage I 수술 뒤 paclitaxel-trastuzumab, 병기 II-III
# 수술 뒤 보조 항암, 그림 6·7의 cT1 N0 → 수술 경로)와 '선행 뒤'(잔존 → T-DM1·capecitabine, pCR 갈래)로 갈리고, TNBC 잔존
# capecitabine은 '면역항암을 받지 않은' 환자만이다. 선행 뒤 환자에게 수술 먼저 stage I 권고가, 선행 pembrolizumab 환자에게
# 'ICI를 받지 않은 잔존 capecitabine'이 1위로 왔다 (VC-0105·0117·0118·0120 check_case, 2026-11-03). 확정 이력으로 반대 갈래를 감점한다.
# 두 갈래를 다 말하는 권고(예: 'multiple positive LNs after primary surgery or residual high-risk after neoadjuvant')는 그대로
SURGERY_FIRST = re.compile(r"initial surgery|primary surgery may be carried out|after primary surgery|"
                           r"pathological stage II|stage III or high-risk non-pCR|"
                           r"N0 → (Surgery|Primary surgery)", re.IGNORECASE)
AFTER_NEOADJUVANT = re.compile(r"residual (invasive )?disease|non-?pCR|→ pCR →|after neoadjuvant|→ Neoadjuvant therapy|"
                               r"throughout the neoadjuvant phase", re.IGNORECASE)
RESIDUAL = re.compile(r"residual (invasive )?disease|non-?pCR", re.IGNORECASE)
PCR_BRANCH = re.compile(r"→ pCR →")
NO_ICI_RECEIVED = re.compile(r"did not receive ICIs", re.IGNORECASE)
ADJUVANT_ICI = re.compile(r"9 cycles pembrolizumab|nine 3-week cycles during the adjuvant phase", re.IGNORECASE)
EARLY_BRANCH_PENALTY = 1.0
# ER 상태: ESMO HER2 양성 장은 같은 아형 필터(HR+/HER2+·HR-/HER2+를 함께 태그)에 ER 양성 전용(유지 ET·ET 병용·OFS)과
# ER 음성 전용 권고가 섞여 있다. ER 음성 환자에게 ER 양성 유지요법 권고가 1~4위를 차지했다 (VC-0112 check_case).
# 아형의 HR 상태와 반대쪽만 대상으로 하는 권고를 감점한다 (괄호 안 선택지 하나만 ER 양성인 권고는 그대로)
ER_POSITIVE_ONLY = re.compile(r"HER2-positive, ER-positive (tumours|MBC)|women with ER-positive disease", re.IGNORECASE)
ER_NEGATIVE_ONLY = re.compile(r"HER2-positive, ER-negative (tumours|MBC)", re.IGNORECASE)
ER_MISMATCH_PENALTY = 1.0
# HER2 양성 보조 항HER2 종료 6-12개월 안 재발: ESMO는 2차 선택지를 권한다. 확정 간주 규칙(DEEM-HER2ADC-6M)이 not_met이면 감점
HER2_EARLY_RELAPSE = re.compile(r"within 6-12 months of completing adjuvant", re.IGNORECASE)
HER2_RELAPSE_PENALTY = 1.0
# 표적 변이: ESMO HR+/HER2- 2차의 fulvestrant 기반·everolimus 권고(455f68, 4bcee1, 그림 3 0f09b4)는 '표적 변이가 없을 때'다.
# ESR1·AKT1 변이 환자(VC-0101, VC-0123)에게 이 권고가 검색돼 LLM이 인용했다 (A run_flow 2026-11-05 C-3).
# 환자에게 표적 변이 태그가 하나라도 있으면 감점한다 (그림 각주는 보지 않는다)
NO_TARGETABLE = re.compile(r"absence of targetable alterations|no targetable alterations", re.IGNORECASE)
TARGETABLE_TAGS = {"gBRCA", "sBRCA", "gPALB2", "PIK3CA-mut", "AKT1-mut", "PTEN-alt", "ESR1-mut"}
TARGETABLE_PENALTY = 1.0
# 3차: ESMO TNBC '2차 이후' 소단원은 청크 차수가 [2L, >=3L]이라, 본문이 'third-line'인 권고(ea837e, a5e9d7, ec3102)가
# 2차 환자에게 2차 권고(e9b4f6)와 같은 점수를 받았다 (VC-0127, A run_flow 2026-11-05 C-2). 1·2차 환자에게는 감점한다.
# 그림 경로는 보지 않는다 (2차 경로 끝의 '→ [PD] → Third-line treatment'는 다음 차수 안내다)
THIRD_LINE = re.compile(r"\bthird-line\b", re.IGNORECASE)
THIRD_LINE_PENALTY = 1.0
# 선행요법 결정: 수술 뒤에만 쓰는 권고(보조 비스포스포네이트 fca2a7, '국소 치료를 마친 뒤' abemaciclib 1f97a2·olaparib 7568e8,
# 보조 olaparib과 함께 ET 936c81, 5년 넘는 연장 ET cca75c)가 선행 결정(VC-0121, VC-0124)에 검색돼 LLM이 인용했다
# (A run_flow 2026-11-05 C-5, B-11). 차수가 neoadjuvant면 감점한다. 그림 경로는 보지 않는다 (수술 뒤 단계까지 이어 그린다)
POST_SURGERY_ONLY = re.compile(r"Bisphosphonates \(up to 5 years\)|after completion of locoregional therapy|"
                               r"Following completion of \(neo\)adjuvant and locoregional therapy|with adjuvant olaparib|"
                               r"Extended ET beyond 5 years", re.IGNORECASE)
PHASE_PENALTY = 1.0
# 조기 고위험: '병기 III 또는 고위험 II기' abemaciclib(1f97a2)과 '고위험' 연장 ET(cca75c)가 고위험이 아닌 환자(VC-0107)에게
# 나왔다 (A run_flow 2026-11-05 B-11, C-4: 그 자리에 정답 OFS 6308eb가 밀림). high_risk_early가 no면 감점한다.
# '특히 고위험이면'(fca2a7), '고위험이면 OFS'(6308eb)처럼 고위험이 아닌 갈래도 말하는 권고는 그대로다
HIGH_RISK_ONLY = re.compile(r"high-risk stage II|should be considered in high-risk EBC", re.IGNORECASE)
HIGH_RISK_PENALTY = 1.0
# 바이오마커 범위: ESMO TNBC 1차 권고는 'gBRCA 정상이고 PD-L1 음성'(taxane a2bd8f, ADC 2d012a)처럼 범위를 본문에 적고
# 청크 태그는 비어 있다. PD-L1 양성 환자(VC-0104)·gBRCA 변이 환자(VC-0116)에게 이 권고가 들어왔다 (A run_flow 2026-11-05 C-6).
# 환자에게 양성 태그가 있는데 본문이 그 마커 음성(정상)만 대상으로 하면 감점한다 (그림 각주는 보지 않는다)
MARKER_NEGATIVE_SCOPE = {
    "PD-L1+": re.compile(r"PD-L1[- ]negative", re.IGNORECASE),
    "gBRCA": re.compile(r"BRCA1/2[- ]+wild[- ]type", re.IGNORECASE),
}
MARKER_SCOPE_PENALTY = 1.0
# 무병 기간: 'DFI ≥12개월' 환자 대상 재투여 권고(ae383b)가 de novo 환자(VC-0114, 무병 기간 없음)에게 들어왔다 (C-6).
# 진단 시 전이성(stage_at_diagnosis metastatic)이면 감점한다
DFI_REQUIRED = re.compile(r"disease-free interval \(DFI\) ≥ ?12 months|DFI ≥ ?12 months", re.IGNORECASE)
DFI_PENALTY = 1.0
CACHE_SIZE = 256  # 같은 조건의 검색 결과를 기억해 두는 개수. 색인이 바뀌면 indexer가 비운다

_cache = {}
_reranker_failed = False  # 재정렬 모델을 못 불러왔으면 한 번만 경고하고 뜻 검색 점수로 대신한다


def search_guidelines(
        query_text: str,
        setting: str = None,
        subtype: str = None,
        line: str = None,
        source: str = None,
        biomarker_tags: list[str] = None,
        top_k: int = 5,
        with_parent: bool = False,
        rerank: bool = True,
        metastatic_sites: list[str] = None,
        negative_tags: list[str] = None,
        chunk_kind: str = "recommendation",
        endocrine_relapse_12m: str = None,
        menopausal_status: str = None,
        visceral_crisis: str = None,
        prior_metastatic_chemo: str = None,
        neoadjuvant_received: str = None,
        ici_received: str = None,
        pcr: str = None,
        her2_adjuvant_relapse: str = None,
        high_risk_early: str = None,
        stage_at_diagnosis: str = None,
) -> list[dict]:
    """지침 권고 청크를 찾는다. with_parent=True면 각 결과에 부모(소단원) 청크를 "parent" 키로 붙인다
    (LLM에는 소단원 전체를 함께 넘긴다, PROJECT.md §6).
    rerank=True(기본, PROJECT.md §6)면 뜻 검색으로 후보 RERANK_CANDIDATES개를 뽑은 뒤 재정렬 모델(bge-reranker-v2-m3)의
    점수로 순위를 다시 매긴다. 모델이 없거나 불러오지 못하면 경고하고 뜻 검색 점수를 쓴다.
    차수는 같으면 가점, 청크가 다른 차수만 가리키면 감점한다. 차수·태그 가점은 두 경우 모두 더한다. 결과의 score는 그 최종 점수다.
    metastatic_sites(예: ["bone", "liver"])를 주면 부위별 권고(뼈·뇌·연수막 전이)를 그 부위 전이가 있으면 가점,
    없으면 후보에서 뺀다. 주지 않거나 빈 목록이면 부위를 모르는 것으로 보고 점수를 바꾸지 않는다.
    negative_tags(예: ["gBRCA"])는 환자가 음성으로 확인된 바이오마커의 태그다. 권고의 바이오마커 태그가 모두 여기에
    들면 감점한다 (예: "PIK3CA, AKT1 or PTEN" 권고는 셋 다 음성일 때만). src/rag/query.py의 search_args가 만든다.
    chunk_kind는 찾을 청크 종류다. 기본은 권고(recommendation). 알고리즘 그림 경로(algorithm)는 같은 권고를 그림 순서로
    다시 적은 것이라 함께 찾으면 상위 자리를 차지해 권고가 밀린다 (평가 MRR 0.97 → 0.65, 2026-10-20). 그래서 따로 찾는다
    (retrieve_for_recommend). None이면 종류를 가리지 않는다.
    endocrine_relapse_12m("yes" / "no", confirmed_state의 의사 확정값)을 주면, 보조 내분비요법 중·12개월 이내 재발 여부가
    반대인 갈래만 가리키는 권고를 감점한다 (ESMO MBC 1차의 fulvestrant-CDK4/6 / AI-CDK4/6 갈림길). 없으면 바꾸지 않는다.
    menopausal_status("premenopausal" / "perimenopausal" / "postmenopausal")를 주면, 반대쪽 폐경 상태만을 대상으로 하는
    권고·그림 경로를 감점한다 (이행기는 폐경 전으로 본다, confirmed_state 규칙). 없거나 그 밖의 값이면 바꾸지 않는다.
    visceral_crisis("yes")를 주면 내분비 기반 치료만 권하는 권고·그림 경로를 감점한다 (장기 부전 임박이면 ChT). 그 밖의 값은 무시.
    prior_metastatic_chemo("yes" / "no", 전이 후 고식 항암을 받았는가)를 주면 반대 갈래("ChT 1차례 이상 뒤" / "이전 ChT 없음")만
    가리키는 권고·그림 경로를 감점한다.
    neoadjuvant_received·ici_received·pcr("yes" / "no", 조기 보조 결정의 확정 이력)를 주면 '수술 먼저' / '선행 뒤', 잔존 / pCR,
    '면역항암을 받지 않은 잔존' / 보조 pembrolizumab 갈래 중 반대쪽만 가리키는 권고·그림 경로를 감점한다 (_early_adjust).
    HER2 양성 아형이면 HR 상태와 반대쪽 ER 상태만 대상으로 하는 권고를 감점한다 (_er_adjust, 인자 없이 subtype으로).
    her2_adjuvant_relapse("no")면 '보조 항HER2 종료 6-12개월 안 재발' 권고를 감점한다.
    high_risk_early("no")면 고위험 전용 권고를, stage_at_diagnosis("metastatic")면 'DFI ≥12개월' 권고를 감점한다.
    차수가 neoadjuvant면 수술 뒤에만 쓰는 권고를, biomarker_tags에 PD-L1+·gBRCA가 있으면 그 마커 음성 전용 권고를 감점한다.
    같은 조건의 검색은 기억해 둔 결과를 돌려준다 (색인을 바꾸면 비워진다)."""
    sites = _site_keys(metastatic_sites)
    negatives = frozenset(negative_tags or ())
    key = (query_text, setting, subtype, line, source, tuple(biomarker_tags or ()), top_k, with_parent, rerank,
           tuple(sorted(sites)) if sites is not None else None, negatives, chunk_kind, endocrine_relapse_12m,
           menopausal_status, visceral_crisis, prior_metastatic_chemo, neoadjuvant_received, ici_received, pcr,
           her2_adjuvant_relapse, high_risk_early, stage_at_diagnosis)
    if key not in _cache:
        if len(_cache) >= CACHE_SIZE:
            _cache.clear()
        _cache[key] = _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank,
                              sites, negatives, chunk_kind, endocrine_relapse_12m, menopausal_status,
                              visceral_crisis, prior_metastatic_chemo, (neoadjuvant_received, ici_received, pcr),
                              her2_adjuvant_relapse, high_risk_early, stage_at_diagnosis)
    return copy.deepcopy(_cache[key])  # 받은 쪽이 결과를 고쳐도 기억해 둔 값은 그대로


def clear_search_cache():
    _cache.clear()


def _site_keys(metastatic_sites):
    """환자 전이 부위를 SITE_SECTIONS와 비교할 값으로 바꾼다. 모르면 None (점수를 바꾸지 않음)."""
    if not metastatic_sites or isinstance(metastatic_sites, str):  # "[Not Available]" 같은 값
        return None
    keys = set()
    for site in metastatic_sites:
        s = str(site).strip().lower()
        if "lepto" in s or "mening" in s or s.endswith("lmd"):
            keys.add("leptomeningeal")
        elif s:
            keys.add(s)
    return keys or None


def _mismatched_site_parents(sites) -> list[str]:
    """환자에게 없는 전이 부위의 부위별 소단원(부모 청크) ID 목록."""
    from .chunk_store import load_guideline_chunks
    out = []
    for chunk in load_guideline_chunks():
        pid = chunk["chunk_id"]
        for section, needed in SITE_SECTIONS.items():
            if pid.endswith("-" + section) and not needed & sites:
                out.append(pid)
    return out


def _site_adjust(parent_id, sites) -> float:
    if sites is None or not parent_id:
        return 0.0
    for section, needed in SITE_SECTIONS.items():
        if parent_id.endswith("-" + section):
            return SITE_MATCH_BONUS if needed & sites else -SITE_MISMATCH_PENALTY
    return 0.0


def _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank,
            sites=None, negatives=frozenset(), chunk_kind="recommendation", relapse_12m=None,
            menopause=None, crisis=None, prior_chemo=None, early=(None, None, None), her2_relapse=None, high_risk=None,
            stage_at_diagnosis=None) -> list[dict]:
    client = get_qdrant_client()
    model = get_embedding_model()

    must_conditions = []

    # 1. doc_type 하드 필터: 지침(guideline) 데이터만 검색 (D 파트 급여 데이터와 분리)
    must_conditions.append(FieldCondition(key="doc_type", match=MatchValue(value="guideline")))
    # 개정으로 대체된 청크(superseded_by에 후속 청크 ID)는 찾지 않는다 (PROJECT.md §6). 색인에는 최신 청크만 두기로 해
    # 지금은 걸리는 것이 없지만, 옛 청크가 섞여 색인돼도 검색에는 나오지 않게 한다. 급여 검색도 같은 규칙이다
    must_conditions.append(IsEmptyCondition(is_empty=PayloadField(key="superseded_by")))

    if source and source.lower() != "unknown":
        must_conditions.append(FieldCondition(key="source", match=MatchValue(value=source)))
    if chunk_kind:
        must_conditions.append(FieldCondition(key="chunk_kind", match=MatchValue(value=chunk_kind)))

    # 2. 하드 필터: setting은 정확히 일치 (chunk.json의 setting에는 any가 없다),
    #    subtype은 요청값과 일치하거나 청크 값이 "any"이면 통과
    if setting and setting.lower() != "unknown":
        must_conditions.append(FieldCondition(key="setting", match=MatchValue(value=setting)))

    if subtype and subtype.lower() != "unknown":
        must_conditions.append(
            Filter(
                should=[
                    FieldCondition(key="subtype", match=MatchValue(value=subtype)),
                    FieldCondition(key="subtype", match=MatchValue(value="any"))
                ]
            )
        )

    # 쿼리 벡터 변환
    query_vector = model.encode(query_text).tolist()
    # 환자 전이 부위를 알면, 없는 부위의 부위별 권고는 후보에서 뺀다. 감점(-1.0)은 뽑힌 후보 안에서만 순위를 바꾸므로,
    # 그런 권고가 후보 자리를 채우면 맞는 권고가 후보에 못 들어간다 (retrieve 연결 확인, 2026-10-20)
    must_not = [FieldCondition(key="parent_id", match=MatchAny(any=_mismatched_site_parents(sites)))] \
        if sites is not None and _mismatched_site_parents(sites) else []
    query_filter = Filter(must=must_conditions, must_not=must_not) if must_conditions or must_not else None

    # Qdrant 검색 실행 (가점 부여를 위해 top_k보다 여유 있게 검색)
    limit = max(top_k * 3, RERANK_CANDIDATES) if rerank else top_k * 3
    hits = []
    if line and line.lower() != "unknown":
        # 후보의 절반은 차수가 맞거나 any인 권고에서 먼저 뽑는다. 가점·감점은 뽑힌 후보 안에서만 순위를 바꾸므로,
        # 질의가 다른 차수 권고와 글자가 많이 겹치면 맞는 차수 권고가 후보에 아예 못 들어갔다 (--auto-query M10·M11)
        line_filter = Filter(must=must_conditions + [FieldCondition(key="line", match=MatchAny(any=[line, "any"]))],
                             must_not=must_not)
        hits = client.query_points(collection_name=COLLECTION_NAME, query=query_vector, query_filter=line_filter,
                                   limit=limit // 2).points
    seen = {hit.id for hit in hits}
    for hit in client.query_points(collection_name=COLLECTION_NAME, query=query_vector, query_filter=query_filter,
                                   limit=limit).points:
        if len(hits) >= limit:
            break
        if hit.id not in seen:
            hits.append(hit)
            seen.add(hit.id)
    base_scores = [hit.score for hit in hits]
    if rerank and hits:
        base_scores = _rerank_scores(query_text, [hit.payload.get("text", "") for hit in hits]) or base_scores

    scored_results = []
    target_tags = set(biomarker_tags) if biomarker_tags else set()

    for hit, score in zip(hits, base_scores):
        payload = hit.payload

        # 3. line(치료 차수)은 거르지 않고 점수로 반영한다 (같으면 가점, 다른 차수면 감점)
        if line and line.lower() != "unknown":
            chunk_lines = payload.get("line", [])
            if isinstance(chunk_lines, str):
                chunk_lines = [chunk_lines]

            # 차수가 정확히 일치하면 가점. any 청크는 수가 많아 같은 가점을 주면 차수로 순위를 가르지 못한다
            if line in chunk_lines:
                score += LINE_MATCH_BONUS
            elif "any" in chunk_lines:
                score += LINE_ANY_BONUS
            elif chunk_lines:
                score -= LINE_MISMATCH_PENALTY

        # 바이오마커 태그 중복도에 따른 가점
        chunk_tags = set(payload.get("biomarker_tags", []))
        overlap = len(target_tags.intersection(chunk_tags))
        score += overlap * TAG_BONUS

        # 전이 부위: 부위별 소단원 권고만 해당
        score += _site_adjust(payload.get("parent_id"), sites)

        # 음성 바이오마커: 권고가 조건으로 삼는 태그가 모두 환자에게 음성이면 감점
        if negatives and chunk_tags and chunk_tags <= negatives:
            score -= NEGATIVE_MARKER_PENALTY

        # 보조 내분비요법 중·12개월 이내 재발 여부: 반대 갈래만 가리키는 권고는 감점
        score -= _relapse_adjust(payload.get("text", ""), relapse_12m)
        # 폐경 상태: 반대쪽 폐경 상태만을 대상으로 하는 권고는 감점
        score -= _menopause_adjust(payload.get("text", ""), menopause)
        # 장기 위기: 내분비 기반 치료만 권하는 권고는 감점
        score -= _crisis_adjust(payload.get("text", ""), crisis)
        # 전이 후 고식 항암 여부: 반대 갈래만 가리키는 권고는 감점
        score -= _prior_chemo_adjust(payload.get("text", ""), prior_chemo)
        # 조기 보조 결정: 수술 먼저 / 선행 뒤, 잔존 / pCR, 면역항암 여부의 반대 갈래만 가리키는 권고는 감점
        score -= _early_adjust(payload.get("text", ""), *early)
        # HER2 양성: 아형의 HR 상태와 반대쪽 ER 상태 전용 권고, 해당 없는 '보조 종료 6-12개월 안 재발' 권고는 감점
        score -= _er_adjust(payload.get("text", ""), subtype)
        if her2_relapse == "no" and HER2_EARLY_RELAPSE.search(payload.get("text", "").split(" Footnotes: ", 1)[0]):
            score -= HER2_RELAPSE_PENALTY
        # 표적 변이가 있는 환자에게 '표적 변이가 없을 때' 권고, 1·2차 환자에게 '3차' 권고는 감점
        score -= _targetable_adjust(payload.get("text", ""), target_tags)
        score -= _third_line_adjust(payload.get("text", ""), line)
        # 선행 결정에 수술 뒤 권고, 고위험이 아닌 환자에게 고위험 전용 권고, 양성 마커 환자에게 그 마커 음성 전용 권고,
        # de novo 환자에게 'DFI ≥12개월' 권고는 감점
        score -= _phase_adjust(payload.get("text", ""), line)
        score -= _high_risk_adjust(payload.get("text", ""), high_risk)
        score -= _marker_scope_adjust(payload.get("text", ""), target_tags)
        score -= _dfi_adjust(payload.get("text", ""), stage_at_diagnosis)

        scored_results.append({
            "score": score,
            "version": payload.get("version", "0000-00"),
            "data": payload
        })

    # 최종 점수로 내림차순 정렬
    scored_results.sort(key=lambda x: (x["score"], x["version"]), reverse=True)
    # score: 뜻 검색(또는 재정렬) 점수 + 차수·태그 가점. 평가와 "근거 부족" 기준에 쓴다
    results = [{**item["data"], "score": round(item["score"], 4)} for item in scored_results[:top_k]]
    if with_parent:
        results = [{**r, "parent": get_parent(r)} for r in results]
    return results


def _relapse_adjust(text: str, relapse_12m) -> float:
    """권고가 환자의 재발 시점과 반대 갈래만 가리키면 감점할 크기. 두 갈래를 다 말하거나 둘 다 말하지 않으면 0."""
    if relapse_12m not in ("yes", "no"):
        return 0.0
    within, after = bool(RELAPSE_WITHIN_12M.search(text)), bool(RELAPSE_AFTER_12M.search(text))
    if relapse_12m == "yes" and after and not within:
        return RELAPSE_MISMATCH_PENALTY
    if relapse_12m == "no" and within and not after:
        return RELAPSE_MISMATCH_PENALTY
    return 0.0


def _menopause_adjust(text: str, menopause) -> float:
    """권고가 환자와 반대쪽 폐경 상태만 대상으로 하면 감점할 크기. 두 쪽을 다 말하거나 말하지 않으면 0.
    그림 경로는 각주를 빼고 경로 글만 본다 (각주의 'OFS … pre- and perimenopausal women'은 모든 경로에 붙는 참고다)."""
    side = {"premenopausal": "pre", "perimenopausal": "pre", "postmenopausal": "post"}.get(menopause)
    if side is None:
        return 0.0
    text = text.split(" Footnotes: ", 1)[0]
    pre, post = bool(PREMENOPAUSAL_SCOPE.search(text)), bool(POSTMENOPAUSAL_SCOPE.search(text))
    if side == "post" and pre and not post:
        return MENOPAUSE_MISMATCH_PENALTY
    if side == "pre" and post and not pre:
        return MENOPAUSE_MISMATCH_PENALTY
    return 0.0


def _crisis_adjust(text: str, crisis) -> float:
    """장기 위기가 확정됐는데 권고가 내분비 기반 치료만 말하면 감점할 크기. 그림 경로는 각주를 빼고 본다."""
    if crisis != "yes":
        return 0.0
    text = text.split(" Footnotes: ", 1)[0]
    if ENDOCRINE_BASED.search(text) and not NOT_ENDOCRINE_ONLY.search(text):
        return VISCERAL_CRISIS_PENALTY
    return 0.0


def _prior_chemo_adjust(text: str, prior_chemo) -> float:
    """권고가 환자의 고식 항암 여부와 반대 갈래만 가리키면 감점할 크기. 그림 경로는 각주를 빼고 본다."""
    if prior_chemo not in ("yes", "no"):
        return 0.0
    text = text.split(" Footnotes: ", 1)[0]
    needs, none = bool(NEEDS_PRIOR_CHEMO.search(text)), bool(NO_PRIOR_CHEMO.search(text))
    if prior_chemo == "no" and needs and not none:
        return PRIOR_CHEMO_MISMATCH_PENALTY
    if prior_chemo == "yes" and none and not needs:
        return PRIOR_CHEMO_MISMATCH_PENALTY
    return 0.0


def _early_adjust(text: str, neoadjuvant=None, ici=None, pcr=None) -> float:
    """조기 보조 결정에서 권고가 환자 이력과 반대 갈래만 가리키면 감점할 크기 (여러 갈래가 어긋나도 한 번만). 그림 각주는 보지 않는다."""
    text = text.split(" Footnotes: ", 1)[0]
    first, after = bool(SURGERY_FIRST.search(text)), bool(AFTER_NEOADJUVANT.search(text))
    wrong = (neoadjuvant == "yes" and first and not after) or (neoadjuvant == "no" and after and not first)
    if neoadjuvant == "yes" and pcr == "yes" and RESIDUAL.search(text) and not first:
        wrong = True
    if neoadjuvant == "yes" and pcr == "no" and PCR_BRANCH.search(text):
        wrong = True
    if ici == "yes" and NO_ICI_RECEIVED.search(text):
        wrong = True
    if ici == "no" and ADJUVANT_ICI.search(text):
        wrong = True
    return EARLY_BRANCH_PENALTY if wrong else 0.0


def _targetable_adjust(text: str, tags) -> float:
    """환자에게 표적 변이 태그가 있는데 권고가 '표적 변이가 없을 때'만 가리키면 감점할 크기. 그림 각주는 보지 않는다."""
    if not TARGETABLE_TAGS.intersection(tags or ()):
        return 0.0
    return TARGETABLE_PENALTY if NO_TARGETABLE.search(text.split(" Footnotes: ", 1)[0]) else 0.0


def _third_line_adjust(text: str, line) -> float:
    """1·2차 결정인데 권고 본문이 '3차(third-line)'를 가리키면 감점할 크기. 그림 경로는 보지 않는다
    (2차 그림 경로는 끝이 '→ [PD] → Third-line treatment (see Figure 4)'로 다음 차수를 가리킬 뿐이다)."""
    if line not in ("1L", "2L") or "(algorithm path)" in text:
        return 0.0
    return THIRD_LINE_PENALTY if THIRD_LINE.search(text.split(" Footnotes: ", 1)[0]) else 0.0


def _body(text: str) -> str:
    return text.split(" Footnotes: ", 1)[0]


def _phase_adjust(text: str, line) -> float:
    """선행요법 결정인데 권고가 수술 뒤에만 쓰는 치료면 감점할 크기. 그림 경로는 보지 않는다."""
    if line != "neoadjuvant" or "(algorithm path)" in text:
        return 0.0
    return PHASE_PENALTY if POST_SURGERY_ONLY.search(text) else 0.0


def _high_risk_adjust(text: str, high_risk) -> float:
    """조기 고위험이 no인데 권고가 고위험 환자만 대상으로 하면 감점할 크기. 그림 각주는 보지 않는다."""
    if high_risk != "no":
        return 0.0
    return HIGH_RISK_PENALTY if HIGH_RISK_ONLY.search(_body(text)) else 0.0


def _marker_scope_adjust(text: str, tags) -> float:
    """환자의 양성 마커(PD-L1+, gBRCA)와 반대로 그 마커 음성·정상 환자만 대상으로 하는 권고면 감점할 크기 (한 번만)."""
    body = _body(text)
    for tag, pattern in MARKER_NEGATIVE_SCOPE.items():
        if tag in (tags or ()) and pattern.search(body):
            return MARKER_SCOPE_PENALTY
    return 0.0


def _dfi_adjust(text: str, stage_at_diagnosis) -> float:
    """진단 시 전이성(de novo, 무병 기간 없음)인데 권고가 'DFI ≥12개월' 환자 대상이면 감점할 크기."""
    if stage_at_diagnosis != "metastatic":
        return 0.0
    return DFI_PENALTY if DFI_REQUIRED.search(_body(text)) else 0.0


def _er_adjust(text: str, subtype) -> float:
    """HER2 양성 아형에서 권고가 반대쪽 ER 상태만 대상으로 하면 감점할 크기."""
    if subtype not in ("HR+/HER2+", "HR-/HER2+"):
        return 0.0
    text = text.split(" Footnotes: ", 1)[0]
    pos, neg = bool(ER_POSITIVE_ONLY.search(text)), bool(ER_NEGATIVE_ONLY.search(text))
    if (subtype == "HR-/HER2+" and pos and not neg) or (subtype == "HR+/HER2+" and neg and not pos):
        return ER_MISMATCH_PENALTY
    return 0.0


def _rerank_scores(query_text: str, texts: list[str]):
    """재정렬 모델 점수를 0~1로 맞춘다. 버전에 따라 0~1 확률 또는 원점수(logit)가 나오므로 범위를 보고 sigmoid를 씌운다.
    0~1로 맞춰야 뜻 검색 점수(코사인 유사도)에 맞춘 차수·태그 가점의 크기가 그대로 통한다.
    모델을 불러오지 못하면(미설치, 내려받기 실패) None을 돌려주고, 검색은 뜻 검색 점수로 계속한다."""
    global _reranker_failed
    if _reranker_failed:
        return None
    try:
        reranker = get_reranker()
    except Exception as e:  # sentence_transformers 미설치, 네트워크 차단, 모델 파일 손상 등
        _reranker_failed = True
        warnings.warn(f"재정렬 모델을 불러오지 못해 뜻 검색 점수만 씁니다: {e}")
        return None
    raw = [float(x) for x in reranker.predict([(query_text, t) for t in texts])]
    if all(0.0 <= x <= 1.0 for x in raw):
        return raw
    return [1 / (1 + math.exp(-x)) for x in raw]


def close_searcher():
    close_client()
