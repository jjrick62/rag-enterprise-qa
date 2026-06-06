"""重排序器——BGE Cross-encoder 精排

Embedding 粗排（快但不准）→ Reranker 精排（慢但准）。
Cross-encoder 把 [query, document] 拼成一对送模型做阅读理解，
而不是分别编码再算相似度，所以精度远高于 Embedding。
"""
from collections import defaultdict
from typing import List, Tuple
from sentence_transformers import CrossEncoder
from services.base import BaseReranker
from schemas.chat import RetrievalResult, Source


class BgeReranker(BaseReranker):
    """BAAI/bge-reranker-v2-m3 Cross-encoder 精排器

    模型大小 ~1GB，首次运行自动下载到 cache_folder。
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        cache_folder: str = "./models",
        min_score: float = 0.50,
        max_chunks_per_document: int = 4,
    ):
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        if max_chunks_per_document < 1:
            raise ValueError("max_chunks_per_document must be at least 1")

        self._model = CrossEncoder(
            model_name,
            device=device,
            cache_folder=cache_folder,
            local_files_only=True,  # 模型已在本地，不连 HF
        )
        self._min_score = min_score
        self._max_chunks_per_document = max_chunks_per_document

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        if not candidates:
            return []

        # 构建 [query, doc] 对
        pairs: List[Tuple[str, str]] = [
            (query, c.chunk.content) for c in candidates
        ]

        # Cross-encoder predict() 输出原始 logits
        # sigmoid 把 logits 映射到 [0,1]——标准做法，保留单调性
        # logit=0 → 0.50 (不确定), logit>0 → >0.50 (相关), logit<0 → <0.50 (不相关)
        import numpy as np
        scores = np.array(self._model.predict(
            pairs,
            show_progress_bar=False,
        ))
        scores = 1.0 / (1.0 + np.exp(-scores))

        # 按分數降序排列
        scored = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        # 先过滤明确负相关结果，再限制单文档占位，避免 Top-K 被重复 chunk 挤满。
        result: List[RetrievalResult] = []
        per_document_count: dict[str, int] = defaultdict(int)
        for cand, new_score in scored:
            if new_score < self._min_score:
                continue

            source_doc = cand.chunk.metadata.source_doc
            if per_document_count[source_doc] >= self._max_chunks_per_document:
                continue

            result.append(RetrievalResult(
                chunk=cand.chunk,
                score=float(new_score),
            ))
            per_document_count[source_doc] += 1
            if len(result) >= top_k:
                break

        # 阈值不能把上下文全部清空；至少保留最高分候选供生成器判断。
        if not result and scored:
            cand, new_score = scored[0]
            result.append(RetrievalResult(
                chunk=cand.chunk,
                score=float(new_score),
            ))

        return result
