import math

import numpy as np
import pytest

from schemas.chat import Chunk, ChunkMetadata, RetrievalResult
from services import reranker as reranker_module


def _chunk(content: str, source_doc: str, index: int) -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            source_doc=source_doc,
            category="test",
            page_number=0,
            heading_stack=[],
            char_start=0,
            char_end=len(content),
        ),
        chunk_index=index,
    )


def _result(content: str, source_doc: str, index: int) -> RetrievalResult:
    return RetrievalResult(
        chunk=_chunk(content, source_doc, index),
        score=0.0,
    )


def _logit(probability: float) -> float:
    return math.log(probability / (1.0 - probability))


class _FakeCrossEncoder:
    def __init__(self, scores):
        self._scores = scores

    def predict(self, pairs, show_progress_bar=False):
        return np.array(
            [_logit(self._scores[content]) for _, content in pairs],
            dtype=np.float32,
        )


def _build_reranker(monkeypatch, scores, **kwargs):
    monkeypatch.setattr(
        reranker_module,
        "CrossEncoder",
        lambda *args, **constructor_kwargs: _FakeCrossEncoder(scores),
    )
    return reranker_module.BgeReranker(**kwargs)


def test_reranker_filters_candidates_below_minimum_score(monkeypatch):
    reranker = _build_reranker(
        monkeypatch,
        {"strong": 0.90, "borderline": 0.55, "weak": 0.49},
        min_score=0.50,
    )
    candidates = [
        _result("strong", "a.md", 0),
        _result("borderline", "b.md", 0),
        _result("weak", "c.md", 0),
    ]

    results = reranker.rerank("query", candidates, top_k=5)

    assert [result.chunk.content for result in results] == [
        "strong",
        "borderline",
    ]


def test_reranker_keeps_best_candidate_when_all_scores_are_below_threshold(
    monkeypatch,
):
    reranker = _build_reranker(
        monkeypatch,
        {"best": 0.49, "worse": 0.20},
        min_score=0.50,
    )
    candidates = [
        _result("worse", "a.md", 0),
        _result("best", "b.md", 0),
    ]

    results = reranker.rerank("query", candidates, top_k=5)

    assert len(results) == 1
    assert results[0].chunk.content == "best"
    assert results[0].score == pytest.approx(0.49, abs=1e-6)


def test_reranker_limits_chunks_from_the_same_document(monkeypatch):
    reranker = _build_reranker(
        monkeypatch,
        {
            "a1": 0.95,
            "a2": 0.90,
            "a3": 0.85,
            "b1": 0.80,
            "c1": 0.75,
        },
        min_score=0.50,
        max_chunks_per_document=2,
    )
    candidates = [
        _result("a1", "a.md", 0),
        _result("a2", "a.md", 1),
        _result("a3", "a.md", 2),
        _result("b1", "b.md", 0),
        _result("c1", "c.md", 0),
    ]

    results = reranker.rerank("query", candidates, top_k=5)

    assert [result.chunk.content for result in results] == [
        "a1",
        "a2",
        "b1",
        "c1",
    ]


def test_reranker_default_diversity_limit_keeps_four_chunks_per_document(
    monkeypatch,
):
    reranker = _build_reranker(
        monkeypatch,
        {
            "a1": 0.95,
            "a2": 0.90,
            "a3": 0.85,
            "a4": 0.80,
            "a5": 0.75,
            "b1": 0.70,
        },
    )
    candidates = [
        _result("a1", "a.md", 0),
        _result("a2", "a.md", 1),
        _result("a3", "a.md", 2),
        _result("a4", "a.md", 3),
        _result("a5", "a.md", 4),
        _result("b1", "b.md", 0),
    ]

    results = reranker.rerank("query", candidates, top_k=5)

    assert [result.chunk.content for result in results] == [
        "a1",
        "a2",
        "a3",
        "a4",
        "b1",
    ]
