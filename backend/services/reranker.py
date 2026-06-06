"""BGE cross-encoder reranking with configurable noise filtering."""
from collections import defaultdict
from typing import List, Tuple

from sentence_transformers import CrossEncoder

from schemas.chat import RetrievalResult
from services.base import BaseReranker


def adaptive_noise_filter(
    candidates: List[RetrievalResult],
    cutoff_ratio: float,
    keep_min: int = 3,
) -> List[RetrievalResult]:
    """Keep candidates within a ratio of the best score, with a minimum floor."""
    if len(candidates) <= keep_min:
        return candidates

    cutoff = candidates[0].score * cutoff_ratio
    filtered = [candidate for candidate in candidates if candidate.score >= cutoff]
    return filtered if len(filtered) >= keep_min else candidates[:keep_min]


class BgeReranker(BaseReranker):
    """BAAI/bge-reranker-v2-m3 cross-encoder reranker."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        cache_folder: str = "./models",
        min_score: float = 0.50,
        max_chunks_per_document: int = 4,
        adaptive_cutoff_ratio: float | None = 0.75,
        adaptive_keep_min: int = 3,
    ):
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        if max_chunks_per_document < 1:
            raise ValueError("max_chunks_per_document must be at least 1")
        if (
            adaptive_cutoff_ratio is not None
            and not 0.0 < adaptive_cutoff_ratio <= 1.0
        ):
            raise ValueError("adaptive_cutoff_ratio must be in (0, 1] or None")
        if adaptive_keep_min < 1:
            raise ValueError("adaptive_keep_min must be at least 1")

        self._model = CrossEncoder(
            model_name,
            device=device,
            cache_folder=cache_folder,
            local_files_only=True,
        )
        self._min_score = min_score
        self._max_chunks_per_document = max_chunks_per_document
        self._adaptive_cutoff_ratio = adaptive_cutoff_ratio
        self._adaptive_keep_min = adaptive_keep_min

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        if not candidates:
            return []

        pairs: List[Tuple[str, str]] = [
            (query, candidate.chunk.content) for candidate in candidates
        ]

        import numpy as np

        scores = np.array(
            self._model.predict(pairs, show_progress_bar=False)
        )
        scores = 1.0 / (1.0 + np.exp(-scores))
        scored = sorted(
            zip(candidates, scores),
            key=lambda item: item[1],
            reverse=True,
        )

        result: List[RetrievalResult] = []
        per_document_count: dict[str, int] = defaultdict(int)
        for candidate, new_score in scored:
            if new_score < self._min_score:
                continue

            source_doc = candidate.chunk.metadata.source_doc
            if per_document_count[source_doc] >= self._max_chunks_per_document:
                continue

            result.append(
                RetrievalResult(
                    chunk=candidate.chunk,
                    score=float(new_score),
                )
            )
            per_document_count[source_doc] += 1
            if len(result) >= top_k:
                break

        if self._adaptive_cutoff_ratio is not None:
            result = adaptive_noise_filter(
                result,
                cutoff_ratio=self._adaptive_cutoff_ratio,
                keep_min=self._adaptive_keep_min,
            )

        if not result and scored:
            candidate, new_score = scored[0]
            result.append(
                RetrievalResult(
                    chunk=candidate.chunk,
                    score=float(new_score),
                )
            )

        return result
