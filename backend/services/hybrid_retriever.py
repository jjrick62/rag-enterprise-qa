"""Hybrid 检索器——BM25 关键词 + 向量语义，双路召回 + RRF 融合

流程：
  BM25 Top-20 + 向量 Top-20 → RRF 融合 Top-15 → 返回给 Pipeline
  Pipeline 再将这 15 个送 Reranker 精排取 5。

RRF 的作用是廉价预筛——纯数学运算（O(N)）把 40 个候选砍到 15 个，
省下 25 次 Reranker Cross-encoder 调用（每次 ~50ms）。
"""
from typing import List, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from services.base import BaseRetriever
from schemas.chat import Chunk, RetrievalResult


class HybridRetriever(BaseRetriever):
    """BM25 + 向量 Hybrid 检索器

    实现 BaseRetriever 接口，对外跟 ChromaRetriever 一样用。
    内部维护 BM25 索引，add_embeddings() 时自动重建。
    """

    RRF_K = 60  # RRF 平滑参数，行业标准值

    def __init__(self, vector_retriever: BaseRetriever):
        self._vector = vector_retriever
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_chunks: List[Chunk] = []  # 跟 BM25 语料库一一对应

    def search(
        self,
        query_embedding,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        query_text: Optional[str] = None,
    ) -> List[RetrievalResult]:
        # 双路并行召回
        vector_results = self._vector.search(
            query_embedding, top_k=20, category_filter=category_filter
        )
        bm25_results = self._bm25_search(query_text or "", top_k=20)

        # RRF 融合
        merged = self._rrf_merge(vector_results, bm25_results, top_k=15)
        return merged

    def add_embeddings(self, chunks: List[Chunk], embeddings) -> int:
        count = self._vector.add_embeddings(chunks, embeddings)
        self._bm25_chunks.extend(chunks)
        self._rebuild_bm25()
        return count

    def delete_by_document(self, source_doc: str) -> int:
        count = self._vector.delete_by_document(source_doc)
        self._bm25_chunks = [
            c for c in self._bm25_chunks
            if c.metadata.source_doc != source_doc
        ]
        self._rebuild_bm25()
        return count

    # ── BM25 ──

    def _rebuild_bm25(self):
        """全量重建 BM25 索引——rank-bm25 不支持增量"""
        if not self._bm25_chunks:
            self._bm25 = None
            return
        # 简单空格分词——BM25 对英文天然友好，中文需要先分词但当前语料全是英文
        tokenized = [c.content.lower().split() for c in self._bm25_chunks]
        self._bm25 = BM25Okapi(tokenized)

    def _bm25_search(self, query: str, top_k: int) -> List[RetrievalResult]:
        if not self._bm25 or not query.strip():
            return []
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        # 取 Top-K 索引
        if len(scores) == 0:
            return []
        indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in indices:
            if scores[idx] <= 0:
                continue
            chunk = self._bm25_chunks[idx]
            results.append(RetrievalResult(chunk=chunk, score=float(scores[idx])))
        return results

    # ── RRF ──

    def _rrf_merge(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """RRF (Reciprocal Rank Fusion) 融合双路结果

        公式: RRF(d) = Σ 1/(k + rank_i(d))
        只看排名不看原始分——解决 BM25 [0,+∞) 和向量 [0,1] 量纲不统一的问题。
        """
        # 用 chunk content 的 hash 作为去重 key
        scores: dict[int, float] = {}
        chunk_map: dict[int, RetrievalResult] = {}

        for rank, r in enumerate(vector_results):
            key = hash(r.chunk.content)
            scores[key] = scores.get(key, 0) + 1.0 / (self.RRF_K + rank + 1)
            chunk_map[key] = r

        for rank, r in enumerate(bm25_results):
            key = hash(r.chunk.content)
            scores[key] = scores.get(key, 0) + 1.0 / (self.RRF_K + rank + 1)
            chunk_map[key] = r

        # 按 RRF 分降序
        sorted_keys = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [
            RetrievalResult(chunk=chunk_map[k].chunk, score=scores[k])
            for k in sorted_keys
        ]
