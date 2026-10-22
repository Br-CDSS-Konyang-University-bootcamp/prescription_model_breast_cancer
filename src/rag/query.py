# src/rag/query.py
# B의 biomarker_record(schemas/biomarker_record.json)로 지침 검색 질의와 검색 인자를 만든다.
# B의 추천 모듈은 이렇게 부르면 된다:
#     from src.rag import search_guidelines
#     from src.rag.query import search_args
#     patient = {"metastatic_sites": ["bone"], "menopausal_status": "premenopausal", "pcr": None,
#                "stage_at_diagnosis": "early", "prior_subclasses": ["AI_nonsteroidal"], "prior_classes": []}
#     results = search_guidelines(**search_args(record, **patient))
#     for args in extra_search_args(record, **patient):  # 부위별(뼈·뇌 전이)·de novo 권고는 따로 찾는다
#         results += search_guidelines(**args)
#     rows = search_reimbursement(["palbociclib", "letrozole"], setting="metastatic", line="1L", as_of="2026-10-20")
#     # 후보 요법마다 급여 행을 찾고, 행의 reimbursement.conditions와 환자 정보로 급여 분류를 정한다 (B)
# patient 값은 A의 patient_state에서 온다: stage.metastatic_sites·recurrence.metastatic_sites, patient.menopausal_status,
# neoadjuvant_response.pcr, stage.disease_extent(진단 시 범주), treatment_history[]의 drug_subclass·drug_class.
# confirmed_state(의사 확정값)로 부르면 retrieve.from_confirmed_state가 같은 값을 만들고, endocrine_relapse_12m·high_risk_early도 더한다.
# 같은 환자 조건이라도 폐경 상태(OFS 권고), pCR(잔존 질환 권고), de novo(원발 종양 수술 권고), 이전 치료(후반 차수)에 따라
# 권고가 갈린다. 이 정보가 없으면 질의가 같아져 구분하지 못한다 (평가 --auto-query, 2026-10-20).
# 질의 문장은 코드 값을 지침이 쓰는 영어 대표 표현(guideline_terms.csv의 preferred)으로 바꿔 이어 붙인다.
# 예: HR+/HER2-, metastatic, 2L, ESR1 positive → "ER-positive, HER2-negative MBC second-line ESR1-mutated"
from .guideline_terms import load_terms, query_terms

# 질의에 넣는 바이오마커 상태. 음성·미시행·VUS는 넣지 않는다 (질의가 "없다"는 권고로 끌려가지 않게)
QUERY_STATUSES = {"positive", "low", "ultralow"}

# 청크 biomarker_tags(= B의 rag_tags) → biomarker_record의 marker:status. 평가 문제집처럼 태그만 있을 때 쓴다
TAG_TO_MARKER = {
    "HER2-low": "HER2:low",
    "HER2-ultralow": "HER2:ultralow",
    "ER-low": "ER:low",
    "gBRCA": "gBRCA1:positive",
    "sBRCA": "sBRCA1:positive",
    "gPALB2": "PALB2:positive",
    "PIK3CA-mut": "PIK3CA:positive",
    "AKT1-mut": "AKT1:positive",
    "PTEN-alt": "PTEN:positive",
    "ESR1-mut": "ESR1:positive",
    "PD-L1+": "PD-L1:positive",
}


def _patient_profile(metastatic_sites=None, menopausal_status=None, pcr=None, stage_at_diagnosis=None,
                     prior_subclasses=None, prior_classes=None, endocrine_relapse_12m=None,
                     high_risk_early=None) -> dict:
    return {
        "endocrine_relapse_12m": endocrine_relapse_12m,
        "high_risk_early": high_risk_early,
        "metastatic_sites": _sites(metastatic_sites),
        "menopausal_status": menopausal_status,
        "pcr": pcr,
        "stage_at_diagnosis": stage_at_diagnosis,
        "prior_subclasses": list(prior_subclasses or []),
        "prior_classes": list(prior_classes or []),
    }


def profile_from_record(record: dict, **patient) -> dict:
    """biomarker_record + 환자 정보(patient_state에서 고른 값) → query_terms가 받는 프로필."""
    setting = record.get("setting") or {}
    markers = [f"{r['marker']}:{r['status']}" for r in record.get("records", []) if r.get("status") in QUERY_STATUSES]
    return {
        "subtype": record.get("subtype"),
        "disease": setting.get("disease"),
        "line": setting.get("line"),
        "markers": markers,
        **_patient_profile(**patient),
    }


def profile_from_tags(subtype, disease, line, biomarker_tags=(), **patient) -> dict:
    """태그로 프로필을 만든다 (평가 문제집용)."""
    return {
        "subtype": subtype,
        "disease": disease,
        "line": line,
        "markers": [TAG_TO_MARKER[t] for t in biomarker_tags if t in TAG_TO_MARKER],
        **_patient_profile(**patient),
    }


QUERY_STYLES = ("adaptive", "full", "focused")


def build_query(profile: dict, terms: list[dict] = None, style: str = "adaptive") -> str:
    """프로필 → 질의 문장. 사전에 없는 값과 unknown은 빠진다.
    이전 치료는 "after AI, CDK4/6 inhibitor"처럼 뒤에 붙인다. 그냥 이어 붙이면 그 약을 권하는 질의처럼 읽힌다.
    style="focused"는 아형·병기 표현을 뺀다. 둘 다 하드 필터로 이미 걸렀는데 질의에 있으면, 재정렬 모델이 그 표현이
    많이 겹치는 일반 권고를 높게 보고 폐경 상태 같은 구분 정보가 묻힌다 (--auto-query E01·E02).
    style="adaptive"(기본)는 focused로 만들되, 남는 것이 차수·이전 치료뿐이면 full로 되돌린다. "first-line"만 남으면
    아형과 무관한 부위별 권고가 올라왔다 (M08·M09·E08). 2026-10-20 비교: MRR full 0.70, focused 0.80."""
    if style not in QUERY_STYLES:
        raise ValueError(f"style은 {QUERY_STYLES} 중 하나: {style!r}")
    terms = terms or load_terms()
    prior_keys = ("prior_subclasses", "prior_classes")
    current = query_terms({k: v for k, v in profile.items() if k not in prior_keys}, terms)
    if style in ("focused", "adaptive"):
        # 국소 진행성(stage III)은 남긴다: EBC 청크의 setting이 [early, locally_advanced]라 필터로는 III기가 갈리지 않는다
        disease = profile.get("disease") if profile.get("disease") in ("early", "metastatic") else None
        filtered = query_terms({"subtype": profile.get("subtype"), "disease": disease}, terms)
        focused = [t for t in current if t not in filtered]
        line_only = query_terms({"line": profile.get("line")}, terms)
        if style == "focused" or [t for t in focused if t not in line_only]:
            current = focused
    prior = [t for t in query_terms({k: profile.get(k, []) for k in prior_keys}, terms) if t not in current]
    return " ".join(current + (["after " + ", ".join(prior)] if prior else []))


# 음성으로 볼 상태 (B는 VUS를 음성으로 처리한다, src/biomarker/README.md)
NEGATIVE_STATUSES = {"negative", "vus"}
# 태그 → 그 태그를 음성으로 보려면 음성이어야 하는 레코드 (marker, 음성 상태들). 모두 음성이어야 태그가 음성이다.
# HER2-low 권고는 HER2가 0(negative)이나 초저발현이면 맞지 않는다. ER-low는 TNBC 소단원의 설명 권고라 넣지 않는다
TAG_NEGATIVE_WHEN = {
    "gBRCA": [("gBRCA1", NEGATIVE_STATUSES), ("gBRCA2", NEGATIVE_STATUSES)],
    "sBRCA": [("sBRCA1", NEGATIVE_STATUSES), ("sBRCA2", NEGATIVE_STATUSES)],
    "gPALB2": [("PALB2", NEGATIVE_STATUSES)],
    "PIK3CA-mut": [("PIK3CA", NEGATIVE_STATUSES)],
    "AKT1-mut": [("AKT1", NEGATIVE_STATUSES)],
    "PTEN-alt": [("PTEN", NEGATIVE_STATUSES)],
    "ESR1-mut": [("ESR1", NEGATIVE_STATUSES)],
    "PD-L1+": [("PD-L1", {"negative"})],
    "HER2-low": [("HER2", {"negative", "ultralow"})],
    "HER2-ultralow": [("HER2", {"negative"})],
}


def negative_tags(record: dict) -> list[str]:
    """biomarker_record에서 환자가 음성으로 확인된 바이오마커의 태그 (검색 감점용). 미시행·기록 없음은 넣지 않는다."""
    status = {r["marker"]: r.get("status") for r in record.get("records", [])}
    return [tag for tag, needs in TAG_NEGATIVE_WHEN.items() if all(status.get(m) in ok for m, ok in needs)]


PATIENT_KEYS = ("metastatic_sites", "menopausal_status", "pcr", "stage_at_diagnosis", "prior_subclasses", "prior_classes",
                "endocrine_relapse_12m", "high_risk_early")


def search_args(record: dict, query_style: str = "adaptive", **kwargs) -> dict:
    """biomarker_record + 환자 정보 → search_guidelines(**인자). top_k, with_parent 등 나머지 키는 그대로 넘긴다."""
    patient = {k: kwargs.pop(k) for k in PATIENT_KEYS if k in kwargs}
    overrides = kwargs
    profile = profile_from_record(record, **patient)
    tags = []
    for r in record.get("records", []):
        if r.get("status") in QUERY_STATUSES:
            tags += [t for t in r.get("rag_tags", []) if t not in tags]
    setting = record.get("setting") or {}
    args = {
        "query_text": build_query(profile, style=query_style),
        "setting": setting.get("disease"),
        "subtype": record.get("subtype"),
        "line": setting.get("line"),
        "biomarker_tags": tags,
        "metastatic_sites": profile["metastatic_sites"] or None,
        "negative_tags": negative_tags(record),
    }
    if profile.get("endocrine_relapse_12m") in ("yes", "no"):  # confirmed_state일 때만 (검색 감점, searcher._relapse_adjust)
        args["endocrine_relapse_12m"] = profile["endocrine_relapse_12m"]
    args.update(overrides)
    return args


# 부위별 추가 검색: 주 치료 질의와 섞으면 뼈 전이 골 보호제 같은 보조 권고가 묻힌다 (--auto-query M15).
# 전이 부위 → 그 부위 권고를 찾는 질의 (guideline_terms.csv의 metastatic_sites 대표 표현과 같은 말)
SITE_QUERIES = {
    "bone": "bone metastases bone-modifying agents radiotherapy",
    "brain": "brain metastases local therapy systemic treatment",
}


def site_search_args(record: dict, top_k: int = 3, **kwargs) -> list[dict]:
    """환자에게 있는 전이 부위마다 부위별 권고를 찾는 search_guidelines 인자 목록. 부위 권고는 차수와 무관하므로 line을 뺀다."""
    patient = {k: kwargs.pop(k) for k in PATIENT_KEYS if k in kwargs}
    base = search_args(record, top_k=top_k, **patient, **kwargs)
    out = []
    for site in _sites(patient.get("metastatic_sites")):
        query = SITE_QUERIES.get(str(site).strip().lower())
        if query:
            out.append({**base, "query_text": query, "line": None})
    return out


# 상황별 추가 검색: de novo IV기(진단 시 전이성)의 원발 종양 수술·국소 치료 권고는 환자 정보가 아니라 별도 질문이라
# 주 치료 질의로는 찾지 못했다 (--auto-query M17). 진단 시·현재 모두 전이성이면 한 번 더 찾는다
DE_NOVO_QUERY = "newly diagnosed stage IV breast cancer intact primary tumour locoregional therapy surgery"


def extra_search_args(record: dict, top_k: int = 3, **kwargs) -> list[dict]:
    """주 치료 검색과 따로 돌릴 검색 인자 목록: 전이 부위별(site_search_args) + de novo. 차수와 무관해 line을 뺀다."""
    patient = {k: kwargs.get(k) for k in PATIENT_KEYS if k in kwargs}
    out = site_search_args(record, top_k=top_k, **kwargs)
    disease = (record.get("setting") or {}).get("disease")
    if disease == "metastatic" and patient.get("stage_at_diagnosis") == "metastatic":
        base = search_args(record, top_k=top_k, **kwargs)
        out.append({**base, "query_text": DE_NOVO_QUERY, "line": None})
    return out


def _sites(metastatic_sites) -> list:
    # patient_state의 metastatic_sites는 목록 또는 "[Not Available]" 같은 괄호 코드다
    return list(metastatic_sites) if isinstance(metastatic_sites, (list, tuple)) else []
