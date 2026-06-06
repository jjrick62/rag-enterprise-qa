import numpy as np
import pytest

from schemas.chat import Chunk, ChunkMetadata, RetrievalResult
from services.hybrid_retriever import HybridRetriever
from services.retriever import ChromaRetriever


def _chunk(content: str, category: str, index: int) -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            source_doc=f"{category}-{index}.md",
            category=category,
            page_number=0,
            heading_stack=[],
            char_start=0,
            char_end=len(content),
        ),
        chunk_index=index,
    )


class _EmptyCollection:
    def get(self, **kwargs):
        return {"ids": [], "documents": [], "metadatas": []}


class _FakeVectorRetriever:
    def __init__(self):
        self._collection = _EmptyCollection()
        self.clear_calls = 0

    def search(self, query_embedding, top_k=5, category_filter=None, query_text=None):
        return []

    def add_embeddings(self, chunks, embeddings):
        return len(chunks)

    def delete_by_document(self, source_doc):
        return 0

    def clear(self):
        self.clear_calls += 1
        return 4


class _RecordingCollection:
    def __init__(self):
        self.deleted_ids = []

    def get(self, **kwargs):
        return {"ids": ["chunk-1", "chunk-2"]}

    def delete(self, ids):
        self.deleted_ids.extend(ids)


class _RecordingVectorRetriever(_FakeVectorRetriever):
    def __init__(self, result_count=30):
        super().__init__()
        self.result_count = result_count
        self.search_top_k = []

    def search(self, query_embedding, top_k=5, category_filter=None, query_text=None):
        self.search_top_k.append(top_k)
        return [
            RetrievalResult(
                chunk=_chunk(f"result {index}", "public", index),
                score=1.0 - index / 100,
            )
            for index in range(min(top_k, self.result_count))
        ]


class _FailingCollection:
    def get(self, **kwargs):
        raise RuntimeError("cannot read chroma collection")


def test_category_filter_applies_to_bm25_results():
    vector = _FakeVectorRetriever()
    retriever = HybridRetriever(vector)
    retriever._bm25_chunks = [
        _chunk("employee benefits overview", "public", 0),
        _chunk("vacation policy details", "public", 1),
        _chunk("restricted payroll procedure", "private", 2),
        _chunk("security incident response", "private", 3),
    ]
    retriever._rebuild_bm25()

    results = retriever.search(
        query_embedding=np.zeros(2),
        query_text="restricted",
        category_filter="public",
    )

    assert results == []


def test_clear_resets_vector_and_bm25_indexes():
    vector = _FakeVectorRetriever()
    retriever = HybridRetriever(vector)
    retriever._bm25_chunks = [_chunk("payroll procedure", "private", 0)]
    retriever._rebuild_bm25()

    deleted = retriever.clear()

    assert deleted == 4
    assert vector.clear_calls == 1
    assert retriever._bm25_chunks == []
    assert retriever._bm25 is None


def test_chroma_clear_deletes_all_collection_ids():
    collection = _RecordingCollection()
    retriever = ChromaRetriever.__new__(ChromaRetriever)
    retriever._collection = collection

    deleted = retriever.clear()

    assert deleted == 2
    assert collection.deleted_ids == ["chunk-1", "chunk-2"]


@pytest.mark.parametrize(
    ("requested_top_k", "expected_candidate_k"),
    [(3, 20), (25, 25)],
)
def test_search_honors_requested_top_k(requested_top_k, expected_candidate_k):
    vector = _RecordingVectorRetriever()
    retriever = HybridRetriever(vector)

    results = retriever.search(
        query_embedding=np.zeros(2),
        query_text="",
        top_k=requested_top_k,
    )

    assert len(results) == requested_top_k
    assert vector.search_top_k == [expected_candidate_k]


def test_bm25_rebuild_failure_is_logged(caplog):
    vector = _FakeVectorRetriever()
    vector._collection = _FailingCollection()

    with caplog.at_level("WARNING"):
        retriever = HybridRetriever(vector)

    assert retriever._bm25 is None
    assert "cannot read chroma collection" in caplog.text
