# src/rag/__init__.py
# qdrant_client, sentence_transformers는 함수를 부를 때 불러온다.
# 그래야 색인 패키지 없이도 청커(python -m src.rag.chunker_asco_all)를 돌릴 수 있다.


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


def search_guidelines(*args, **kwargs):
    from .searcher import search_guidelines as _search_guidelines
    return _search_guidelines(*args, **kwargs)


__all__ = ["index_chunks", "init_collection", "delete_by_doc_type", "delete_guideline_chunks", "search_guidelines"]
