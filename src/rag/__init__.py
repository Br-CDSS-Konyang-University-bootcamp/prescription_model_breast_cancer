# src/rag/__init__.py
# qdrant_client, sentence_transformers는 함수를 부를 때 불러온다.
# 그래야 색인 패키지 없이도 청커(python -m src.rag.chunker_esmo)를 돌릴 수 있다.


def init_collection(*args, **kwargs):
    from .indexer import init_collection as _init_collection
    return _init_collection(*args, **kwargs)


def index_chunks(*args, **kwargs):
    from .indexer import index_chunks as _index_chunks
    return _index_chunks(*args, **kwargs)


def delete_by_doc_type(*args, **kwargs):
    from .indexer import delete_by_doc_type as _delete_by_doc_type
    return _delete_by_doc_type(*args, **kwargs)


def delete_guideline_chunks(*args, **kwargs):
    from .indexer import delete_guideline_chunks as _delete_guideline_chunks
    return _delete_guideline_chunks(*args, **kwargs)


def close_indexer():
    """Qdrant 로컬 폴더 잠금을 푼다. 색인한 뒤 부른다 (로컬 모드는 한 프로세스만 폴더를 열 수 있다)."""
    from .indexer import close_indexer as _close_indexer
    return _close_indexer()


def search_guidelines(*args, **kwargs):
    from .searcher import search_guidelines as _search_guidelines
    return _search_guidelines(*args, **kwargs)


def close_searcher():
    """검색이 끝나면 부른다 (Qdrant 로컬 폴더 잠금을 푼다). 로컬 모드는 한 프로그램만 폴더를 열 수 있다.
    부르지 않아도 프로그램이 끝날 때 닫히지만, 같은 프로그램에서 색인(D)·검색을 번갈아 할 때는 직접 부른다."""
    from .searcher import close_searcher as _close_searcher
    return _close_searcher()


def search_reimbursement(*args, **kwargs):
    from .reimbursement_search import search_reimbursement as _search_reimbursement
    return _search_reimbursement(*args, **kwargs)


__all__ = ["index_chunks", "init_collection", "delete_by_doc_type", "delete_guideline_chunks", "close_indexer",
           "search_guidelines", "search_reimbursement", "close_searcher"]
