# src/rag/retrieve.py
# B의 추천 모듈(src/recommend/pipeline.py의 recommend)에 넘길 지침·급여 청크를 한 번에 준비한다.
#     from src.rag import retrieve_for_recommend, close_searcher
#     guideline_chunks, reimbursement_chunks = retrieve_for_recommend(patient_state, biomarker_record, as_of="2026-10-20")
#     recommendation, log, errors = recommend(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, llm, ...)
# 하는 일:
#   1. patient_state(A, schemas/patient_state.json)에서 질의에 쓸 환자 정보를 꺼낸다 (patient_from_state)
#   2. 지침: 주 검색(search_args) + 부위별·de novo 추가 검색(extra_search_args). 부모 소단원을 붙인다 (B의 프롬프트가 쓴다)
#   3. 급여: 찾은 지침 권고에 나오는 약마다 search_reimbursement로 급여 행을 찾는다. recommend()는 LLM에 묻기 전에
#      급여 청크를 받아야 하는데, 후보 약은 지침 권고에 이미 있으므로 그 약으로 미리 찾는다. 약 하나씩 찾는 이유:
#      권고 하나에 대안 약이 함께 적혀 있어(예: elacestrant or imlunestrant) 묶어서 찾으면 '모두 포함' 규칙에 걸린다
# A·B의 내부 코드는 가져오지 않고 공용 스키마 형식(patient_state, biomarker_record, chunk)만 읽는다.
import csv

from .chunk_common import BASE_DIR
from .query import extra_search_args, search_args

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


def retrieve_for_recommend(patient_state: dict, biomarker_record: dict, as_of=None, top_k: int = 5,
                           extra_top_k: int = 3, reimbursement_per_drug: int = 5, rerank: bool = True):
    """→ (지침 청크 목록, 급여 청크 목록). 둘 다 schemas/chunk.json 형식에 검색 정보(score, parent 등)를 더한 것.
    지침: 주 검색 top_k개 + 추가 검색 각 extra_top_k개 (중복 없이, 주 검색이 앞). 급여: 지침 권고의 약마다
    맞는 행 reimbursement_per_drug개까지 (현재 병기 범주·차수로 거름, as_of 기준 시행 중인 행만)."""
    from .reimbursement_search import search_reimbursement
    from .searcher import search_guidelines

    setting = biomarker_record.get("setting") or {}
    disease, line = setting.get("disease"), setting.get("line")
    patient = patient_from_state(patient_state, disease)

    guideline, seen = [], set()
    searches = [search_args(biomarker_record, top_k=top_k, **patient)]
    searches += extra_search_args(biomarker_record, top_k=extra_top_k, **patient)
    for args in searches:
        for chunk in search_guidelines(**{**args, "with_parent": True, "rerank": rerank}):
            if chunk["chunk_id"] not in seen:
                guideline.append(chunk)
                seen.add(chunk["chunk_id"])

    drugs = []
    for chunk in guideline:
        drugs += [d for d in chunk.get("drugs") or [] if d not in drugs]
    reimbursement, seen = [], set()
    for drug in drugs:
        for row in search_reimbursement([drug], setting=disease, line=line, as_of=as_of,
                                        top_k=reimbursement_per_drug):
            if row["chunk_id"] not in seen:
                reimbursement.append(row)
                seen.add(row["chunk_id"])
    return guideline, reimbursement
