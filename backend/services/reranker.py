"""重排序器——BGE Cross-encoder 精排

Embedding 粗排（快但不准）→ Reranker 精排（慢但准）。
Cross-encoder 把 [query, document] 拼成一对送模型做阅读理解，
而不是分别编码再算相似度，所以精度远高于 Embedding。
"""
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
    ):
        self._model = CrossEncoder(
            model_name,
            device=device,
            cache_folder=cache_folder,
        )

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

        # Cross-encoder 批量打分
        scores = self._model.predict(
            pairs,
            show_progress_bar=False,
        )

        # 分数归一化到 [0, 1]（Cross-encoder 输出是 logits）
        # 用 sigmoid 把 logits 映射为概率
        import numpy as np
        scores = 1.0 / (1.0 + np.exp(-np.array(scores)))

        # 按分數降序排列
        scored = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        # 取 Top-K，覆盖 score 字段
        result: List[RetrievalResult] = []
        for cand, new_score in scored[:top_k]:
            result.append(RetrievalResult(
                chunk=cand.chunk,
                score=float(new_score),
            ))

        return result
