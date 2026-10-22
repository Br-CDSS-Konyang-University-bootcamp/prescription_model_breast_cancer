# src/rag/retrieve.py
# B의 추천 모듈(src/recommend/pipeline.py의 recommend)에 넘길 지침·급여 청크를 한 번에 준비한다.
#     from src.rag import retrieve_for_recommend, close_searcher
#     guideline_chunks, reimbursement_chunks = retrieve_for_recommend(confirmed_state, as_of="2026-10-21")
#     (옛 방식도 받는다: retrieve_for_recommend(patient_state, biomarker_record, as_of=...))
# 입력:
#   - confirmed_state(schemas/confirmed_state.json, 화면 1에서 의사가 확정한 값): items.*.confirmed만 읽는다
#     (from_confirmed_state). 2단계는 이 파일 하나만 받는다 (src/input/handoff_confirmed_state_to_B.md)
#   - 옛 방식: biomarker_record(B) + patient_state(A). B가 confirmed_state로 바꿀 때까지 둔다
# 하는 일:
#   1. 입력에서 질의에 쓸 환자 정보를 꺼낸다 (from_confirmed_state 또는 patient_from_state)
#   2. 지침: 주 검색(search_args) + 부위별·de novo 추가 검색(extra_search_args). 부모 소단원을 붙인다 (B의 프롬프트가 쓴다).
#      알고리즘 그림 경로(chunk_kind = algorithm)는 같은 조건으로 따로 찾아 뒤에 붙인다 (권고와 함께 찾으면 권고가 밀린다)
#   3. 급여: 찾은 지침 권고에 나오는 약마다 search_reimbursement로 급여 행을 찾는다. recommend()는 LLM에 묻기 전에
#      급여 청크를 받아야 하는데, 후보 약은 지침 권고에 이미 있으므로 그 약으로 미리 찾는다. 약 하나씩 찾는 이유:
#      권고 하나에 대안 약이 함께 적혀 있어(예: elacestrant or imlunestrant) 묶어서 찾으면 '모두 포함' 규칙에 걸린다
# A·B의 내부 코드는 가져오지 않고 공용 스키마 형식(patient_state, biomarker_record, chunk)만 읽는다.
import csv

from .chunk_common import BASE_DIR
from .query import TAG_TO_MARKER, extra_search_args, search_args

DRUG_CLASSES_CSV = BASE_DIR / "data" / "dictionaries" / "drug_classes.csv"
# 이전 치료로 질의에 넣지 않는 계열 (보조약·골 보호제 등은 차수 권고와 관계없다)
SKIP_CLASSES = {"Bone-modifying Agent", "Supportive Care", "Vaccine", "Other", "Unknown"}

_drug_info = None


def _drug_classes() -> dict:
    global _drug_info
    if _drug_info is None:
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig", newline="") as f:
            _drug_info = {r["generic_name"].strip().lower(): (r["drug_class"], r["drug_subclass"])
                          for r in csv.DictReader(f)}
    return _drug_info


def _value(field):
    """추출값({status, value})에서 값. 값이 없거나 괄호 코드([Not Available] 등)면 None."""
    if not isinstance(field, dict) or field.get("status") != "present":
        return None
    value = field.get("value")
    return None if isinstance(value, str) and value.startswith("[") else value


def patient_from_state(patient_state: dict, disease: str = None) -> dict:
    """patient_state → query.search_args가 받는 환자 정보.
    disease(현재 병기 범주, biomarker_record.setting.disease)가 metastatic일 때만 이전 치료를 넣는다:
    조기·국소 진행성의 선행요법 정보는 pcr로 들어가고, '이전 치료'는 전이성 차수 권고를 가르는 데 쓴다."""
    f = (patient_state or {}).get("fields") or {}
    stage, recurrence = f.get("stage") or {}, f.get("recurrence") or {}
    sites = []
    for value in (_value(stage.get("metastatic_sites")), _value(recurrence.get("metastatic_sites"))):
        for site in value if isinstance(value, list) else []:
            if site not in sites:
                sites.append(site)
    menopausal = _value((f.get("patient") or {}).get("menopausal_status"))
    subclasses, classes = [], []
    if disease == "metastatic":
        info = _drug_classes()
        for therapy in f.get("treatment_history") or []:
            for drug in therapy.get("drugs") or []:
                drug_class, subclass = info.get(str(drug).strip().lower(), ("", ""))
                if drug_class in SKIP_CLASSES or not drug_class:
                    continue
                if subclass and subclass not in subclasses:
                    subclasses.append(subclass)
                elif not subclass and drug_class not in classes:
                    classes.append(drug_class)
    return {
        "metastatic_sites": sites,
        "menopausal_status": menopausal if menopausal != "indeterminate" else None,
        "pcr": _value((f.get("neoadjuvant_response") or {}).get("pcr")),
        "stage_at_diagnosis": _value(stage.get("disease_extent")),
        "prior_subclasses": subclasses,
        "prior_classes": classes,
    }


# ---------- confirmed_state (의사 확정값) ----------

# 내분비 차수로 주 검색하는 아형. HR+/HER2+는 ESMO 전이성 지침의 HER2 양성 장에서 다루고(1·2차가 항HER2 순서,
# 내분비는 항HER2에 곁들이는 선택지) 그래서 항암 차수로 찾는다. 급여 행은 두 차수 모두에서 찾는다
HR_POSITIVE = ("HR+/HER2-",)
LINE_ORDER = ["1L", "2L", ">=3L"]
# 심평원 차수 간주 규칙 (confirmed_state items.deemed_lines). met이면 그 계열 급여 행을 한 차수 위까지 찾는다.
# 예: 보조 내분비요법 중 재발(DEEM-ENDO-ADJ-1Y)이면 내분비 1차 시점에 공고의 '2차 이상' 내분비 요법이 급여다 (VC-0103).
# 어느 약에 적용되는지(약제별 +1)는 D·B가 판정한다. C는 해당할 수 있는 행을 빠뜨리지 않게 넓게 찾기만 한다
DEEMED_ENDOCRINE = ("DEEM-ENDO-ADJ-1Y",)
DEEMED_CHEMO = ("DEEM-ANTHRA-TAXANE", "DEEM-SG-1Y", "DEEM-HER2ADC-6M")
# confirmed_state의 마커 이름 → biomarker_record 레코드 이름. gBRCA·sBRCA는 하나로 확정되므로 1·2 두 레코드로 펴서
# 기존 태그 규칙(TAG_NEGATIVE_WHEN: gBRCA1·gBRCA2 모두 음성이어야 gBRCA 음성)을 그대로 쓴다
MARKER_RECORDS = {"gBRCA": ("gBRCA1", "gBRCA2"), "sBRCA": ("sBRCA1", "sBRCA2")}
_MARKER_TAG = {marker_status: tag for tag, marker_status in TAG_TO_MARKER.items()}


def is_confirmed_state(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("items"), dict) and "decision_context" in data


def _confirmed(items: dict, key: str):
    item = items.get(key)
    return item.get("confirmed") if isinstance(item, dict) else None


def _next_line(line):
    return LINE_ORDER[min(LINE_ORDER.index(line) + 1, len(LINE_ORDER) - 1)] if line in LINE_ORDER else line


def decision_lines(items: dict) -> dict:
    """검색에 쓸 차수. confirmed_state는 전이성 차수를 고식적 내분비·항암으로 나눠 확정한다 (심평원 투여단계).
    → {"guideline": [주 검색 차수, (추가 검색 차수)], "reimbursement": [급여 행을 찾을 차수들]}
    - 조기: setting.phase (neoadjuvant / adjuvant)
    - 전이성 HR+/HER2-: 내분비 차수 (ESMO 호르몬 양성 장의 1·2·3차는 내분비 기반 치료 순서). 내분비를 더 쓰지 않으면
      (not_applicable) 항암 차수. 두 차수가 다르면 항암 차수로도 한 번 더 찾는다
    - 전이성 HER2 양성(HR+/HER2+ 포함)·TNBC: 항암 차수
    - 급여: 위 차수들 + 간주 규칙이 met인 계열의 한 차수 위
    - classes: 이번 결정의 치료 계열 (HR+/HER2- 내분비 결정이면 Hormone Therapy, 그 밖은 항암·항HER2)"""
    disease = _confirmed(items, "setting.disease")
    if disease != "metastatic":
        phase = _confirmed(items, "setting.phase")
        return {"guideline": [phase or "unknown"], "reimbursement": [phase] if phase else [None]}
    subtype = _confirmed(items, "subtype")
    endo = _confirmed(items, "setting.line_endocrine")
    chemo = _confirmed(items, "setting.line_chemo")
    endo = endo if endo in LINE_ORDER else None
    chemo = chemo if chemo in LINE_ORDER else None
    if subtype in HR_POSITIVE and endo:
        guideline = [endo] + ([chemo] if chemo and chemo != endo else [])
    else:
        guideline = [chemo or endo or "unknown"]
    deemed = _confirmed(items, "deemed_lines") or {}
    reimbursement = []
    for line, rules in ((endo, DEEMED_ENDOCRINE), (chemo, DEEMED_CHEMO)):
        if not line:
            continue
        reimbursement.append(line)
        if any(deemed.get(rule) == "met" for rule in rules):
            reimbursement.append(_next_line(line))
    reimbursement = list(dict.fromkeys(reimbursement)) or [guideline[0] if guideline[0] != "unknown" else None]
    # 이번 결정의 치료 계열 (연결되지 않은 급여 행을 늘어놓는 순서에 쓴다): HR+에서 내분비 차수를 고르면 내분비요법
    classes = ["Hormone Therapy"] if subtype in HR_POSITIVE and endo else ["Chemotherapy", "HER2-targeted Therapy"]
    return {"guideline": guideline, "reimbursement": reimbursement, "classes": classes}


def from_confirmed_state(confirmed_state: dict):
    """confirmed_state → (biomarker_record 꼴의 레코드, 환자 정보, 차수). 검색 코드는 그대로 쓰고 입력만 바꾼다.
    읽는 값은 items.*.confirmed뿐이다 (system·previous는 보지 않는다)."""
    items = confirmed_state.get("items") or {}
    subtype = _confirmed(items, "subtype")
    disease = _confirmed(items, "setting.disease")
    lines = decision_lines(items)
    records = []
    for marker, item in (items.get("markers") or {}).items():
        status = item.get("confirmed") if isinstance(item, dict) else None
        if status is None:
            continue
        for name in MARKER_RECORDS.get(marker, (marker,)):
            tag = _MARKER_TAG.get(f"{name}:{status}")
            records.append({"marker": name, "status": status, "rag_tags": [tag] if tag else []})
    record = {"subtype": subtype, "setting": {"disease": disease, "line": lines["guideline"][0]}, "records": records}

    subclasses, classes = [], []
    if disease == "metastatic":  # 이전 치료는 전이성 차수 권고를 가르는 데만 쓴다 (patient_from_state와 같은 규칙)
        known = {s for _, s in _drug_classes().values() if s}
        for regimen in _confirmed(items, "prior_regimens") or []:
            for value in regimen.get("subclasses") or []:
                if value in SKIP_CLASSES:
                    continue
                target = subclasses if value in known else classes
                if value not in target:
                    target.append(value)
    pcr = _confirmed(items, "pcr")
    relapse = _confirmed(items, "endocrine_relapse_12m")
    # de novo(진단 시부터 전이성): 재발이 없었거나 무병 기간이 해당 없음 (confirmed_state에 진단 시 범주 칸이 없다)
    de_novo = disease == "metastatic" and (_confirmed(items, "recurrence_type") == "none"
                                          or _confirmed(items, "dfi_days") == "not_applicable")
    patient = {
        "metastatic_sites": _confirmed(items, "metastatic_sites") or [],
        "menopausal_status": _confirmed(items, "menopausal_status"),
        "pcr": pcr if pcr in ("yes", "no") else None,
        "stage_at_diagnosis": "metastatic" if de_novo else None,
        "prior_subclasses": subclasses,
        "prior_classes": classes,
        "endocrine_relapse_12m": relapse if relapse in ("yes", "no") else None,
    }
    return record, patient, lines


def retrieve_for_recommend(state: dict, biomarker_record: dict = None, as_of=None, top_k: int = 5,
                           extra_top_k: int = 3, algorithm_top_k: int = 2, reimbursement_per_drug: int = 5,
                           rerank: bool = True, with_reimbursement_only: bool = False):
    """→ (지침 청크 목록, 급여 청크 목록). 둘 다 schemas/chunk.json 형식에 검색 정보(score, parent 등)를 더한 것.
    state: confirmed_state 하나 (biomarker_record 없이), 또는 옛 방식의 patient_state (+ biomarker_record).
    as_of: 급여 판정 기준일. confirmed_state면 비울 때 confirmed_at의 날짜를 쓴다.
    지침: 주 검색 top_k개 + 추가 검색 각 extra_top_k개 (부위별·de novo, 전이성 HR+/HER2-의 항암 차수) + 알고리즘 그림 경로
    algorithm_top_k개 (중복 없이, 주 검색이 앞). 알고리즘 경로의 약은 급여 검색에 쓰지 않는다 (권고에 이미 있고, 다음 차수
    약까지 들어 있다). 급여: 지침 권고의 약마다, 급여 차수(decision_lines)마다 맞는 행 reimbursement_per_drug개까지
    (현재 병기 범주·차수로 거름, as_of 기준 시행 중인 행만). 조건 판정은 D·B가 한다.
    with_reimbursement_only=True면 세 번째 목록을 더해 (지침, 급여, 연결되지 않은 급여 행)을 돌려준다: 같은 병기·차수·아형의
    급여 행 중 이번에 찾은 지침 권고의 약으로 찾지 못한 것 (search_reimbursement_rows). ESMO 권고가 아예 없는 요법만이
    아니라 다른 차수 권고의 약도 들어간다. 이번 결정의 치료 계열(decision_classes) 행이 앞에 온다.
    개수가 많아(VC-0103 기준 57행) 화면에 낼 때는 B의 조건 판정을 거친다 (팀 회의 2026-10-21)."""
    from .reimbursement_search import search_reimbursement, search_reimbursement_rows
    from .searcher import search_guidelines

    if biomarker_record is None:
        if not is_confirmed_state(state):
            raise TypeError("confirmed_state 하나 또는 (patient_state, biomarker_record)를 넘기세요.")
        biomarker_record, patient, lines = from_confirmed_state(state)
        as_of = as_of or (state.get("confirmed_at") or "")[:10] or None
    else:
        setting = biomarker_record.get("setting") or {}
        patient = patient_from_state(state, setting.get("disease"))
        lines = {"guideline": [setting.get("line")], "reimbursement": [setting.get("line")]}
    disease = (biomarker_record.get("setting") or {}).get("disease")

    guideline, seen = [], set()
    main = search_args(biomarker_record, top_k=top_k, **patient)
    searches = [main] + extra_search_args(biomarker_record, top_k=extra_top_k, **patient)
    for line in lines["guideline"][1:]:  # 전이성 HR+/HER2-에서 내분비·항암 차수가 다르면 항암 차수 권고도 찾는다
        searches.append({**main, "line": line, "top_k": extra_top_k})
    if algorithm_top_k:
        searches.append({**main, "top_k": algorithm_top_k, "chunk_kind": "algorithm"})
    for args in searches:
        for chunk in search_guidelines(**{**args, "with_parent": True, "rerank": rerank}):
            if chunk["chunk_id"] not in seen:
                guideline.append(chunk)
                seen.add(chunk["chunk_id"])

    drugs = []
    for chunk in guideline:
        if chunk.get("chunk_kind") == "algorithm":
            continue
        drugs += [d for d in chunk.get("drugs") or [] if d not in drugs]
    reimbursement, seen = [], set()
    for drug in drugs:
        for line in lines["reimbursement"]:
            for row in search_reimbursement([drug], setting=disease, line=line, as_of=as_of,
                                            top_k=reimbursement_per_drug):
                if row["chunk_id"] not in seen:
                    reimbursement.append(row)
                    seen.add(row["chunk_id"])
    if not with_reimbursement_only:
        return guideline, reimbursement
    only = search_reimbursement_rows(setting=disease, lines=lines["reimbursement"],
                                     subtype=biomarker_record.get("subtype"), as_of=as_of, exclude_ids=seen,
                                     prefer_classes=lines.get("classes", ()))
    return guideline, reimbursement, only
