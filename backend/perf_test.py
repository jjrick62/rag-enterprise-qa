"""性能基准测试 —— 检索延迟 / 端到端延迟 / Chunk 统计

用法：
    cd backend
    .\venv\Scripts\python.exe perf_test.py

测试范围：
    1. Chunk 统计（总数、大小分布）
    2. Vector 检索延迟（不含 Embedding 耗时）
    3. BM25 检索延迟
    4. Hybrid (RRF) 检索延迟
    5. Reranker 延迟
    6. 端到端延迟（不含 LLM 生成）
"""
import time
import json
import statistics
import os
import sys

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from services.parser import MDParser
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter
from services.llm_factory import get_provider
from services.pipeline import RAGPipeline

# 30 道 QA 的问题（跳过 Query Rewrite 环节，直接测检索）
TEST_QUERIES = [
    "What foundation models are available in watsonx.ai?",
    "What is greedy decoding?",
    "What tuning parameters are available for IBM foundation models?",
    "What are tokens and tokenization?",
    'What is the "random seed" parameter in prompt tuning experiments?',
    "How to build reusable prompts?",
    "What is the workflow for a Federated Learning experiment?",
    "What are the benefits of using IBM Federated Learning?",
    "How do I delete a deployment using the Python client?",
    "What is the retrieval-augmented generation pattern?",
    "How do I create a connection to Microsoft SQL Server?",
    "What is the purpose of the Sim Eval node in IBM SPSS Modeler?",
    "What are the key functions of the geospatial library?",
    "What are the properties of the Bayes Net node in Clementine?",
    "How can I search for assets across the platform?",
    "What's the difference between prompt tuning and fine-tuning?",
    "How to use the Python client for model deployment?",
    "What IBM database connections are supported?",
    "How to set up Box connection?",
    "What are the prerequisites for Decision Optimization?",
]


def build_pipeline():
    config = Config.load()
    embedder = BGEBaaIEmbedder(
        model_name=config.embedding_model, device="cpu",
        cache_folder=config.model_cache_path,
    )
    return (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(embedder)
        .with_retriever(HybridRetriever(
            vector_retriever=ChromaRetriever(
                persist_path=config.chroma_path, embedder=embedder,
            )
        ))
        .with_reranker(BgeReranker(
            model_name="BAAI/bge-reranker-v2-m3", device="cpu",
            cache_folder=config.model_cache_path,
        ))
        .with_rewriter(QueryRewriter(provider=get_provider("rewrite")))
        .build()
    )


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000:.1f}ms"


def main():
    print("=" * 60)
    print("RAG Pipeline Performance Test")
    print("=" * 60)

    # ── 1. Chunk 统计 ──
    print("\n[1/5] Chunk Statistics...")
    config = Config.load()
    embedder = BGEBaaIEmbedder(
        model_name=config.embedding_model, device="cpu",
        cache_folder=config.model_cache_path,
    )
    retriever = HybridRetriever(
        vector_retriever=ChromaRetriever(
            persist_path=config.chroma_path, embedder=embedder,
        )
    )
    # Rebuild BM25
    retriever._rebuild_from_chromadb()

    chunks = retriever._bm25_chunks
    if not chunks:
        print("  WARNING: No chunks found — BM25 index empty. Run re-ingestion first.")
        chunk_count = retriever._vector._collection.count()
        print(f"  ChromaDB document count: {chunk_count}")
    else:
        sizes = [len(c.content) for c in chunks]
        docs = set(c.metadata.source_doc for c in chunks)
        empty_headings = sum(1 for c in chunks if not c.metadata.heading_stack)
        print(f"  Total chunks:     {len(chunks)}")
        print(f"  Unique documents: {len(docs)}")
        print(f"  Avg chunk size:   {statistics.mean(sizes):.0f} chars")
        print(f"  Median size:      {statistics.median(sizes):.0f} chars")
        print(f"  Min / Max:        {min(sizes)} / {max(sizes)}")
        print(f"  Empty headings:   {empty_headings}/{len(chunks)}")
        # Size distribution
        bins = [(0, 200), (200, 400), (400, 600), (600, 1000), (1000, 2000)]
        for lo, hi in bins:
            n = sum(1 for s in sizes if lo <= s < hi)
            bar = "█" * (n * 40 // max(len(chunks), 1))
            print(f"  {lo:>4}-{hi:<4}: {n:>4} ({n*100/len(chunks):5.1f}%) {bar}")

    # ── 2. Embedding 延迟（7 个查询预热，取后 15 个）──
    print("\n[2/5] Embedding Latency...")
    warmup = TEST_QUERIES[:5]
    test_qs = TEST_QUERIES[5:]
    for q in warmup:
        _ = embedder.embed(q)
    emb_times = []
    for q in test_qs:
        t0 = time.perf_counter()
        _ = embedder.embed(q)
        emb_times.append(time.perf_counter() - t0)
    print(f"  Mean:   {fmt_ms(statistics.mean(emb_times))}")
    print(f"  Median: {fmt_ms(statistics.median(emb_times))}")
    print(f"  P95:    {fmt_ms(sorted(emb_times)[int(len(emb_times)*0.95)])}")

    # ── 3. 检索延迟 ──
    print("\n[3/5] Retrieval Latency (Vector / BM25 / Hybrid)...")
    vec_times, bm25_times, hybrid_times = [], [], []
    for q in test_qs:
        emb = embedder.embed(q)

        t0 = time.perf_counter()
        _ = retriever._vector.search(emb, top_k=20)
        vec_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = retriever._bm25_search(q, top_k=20)
        bm25_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = retriever.search(emb, top_k=20)
        hybrid_times.append(time.perf_counter() - t0)

    for name, times in [("Vector", vec_times), ("BM25", bm25_times), ("Hybrid RRF", hybrid_times)]:
        print(f"  {name:12s}: mean={fmt_ms(statistics.mean(times)):>8s}  "
              f"median={fmt_ms(statistics.median(times)):>8s}  "
              f"P95={fmt_ms(sorted(times)[int(len(times)*0.95)]):>8s}")

    # ── 4. Reranker 延迟 ──
    print("\n[4/5] Reranker Latency...")
    reranker = BgeReranker(
        model_name="BAAI/bge-reranker-v2-m3", device="cpu",
        cache_folder=config.model_cache_path,
    )
    rerank_times = []
    for q in test_qs:
        emb = embedder.embed(q)
        results = retriever.search(emb, top_k=20)
        t0 = time.perf_counter()
        _ = reranker.rerank(q, results)
        rerank_times.append(time.perf_counter() - t0)
    print(f"  Mean:   {fmt_ms(statistics.mean(rerank_times))}")
    print(f"  Median: {fmt_ms(statistics.median(rerank_times))}")
    print(f"  P95:    {fmt_ms(sorted(rerank_times)[int(len(rerank_times)*0.95)])}")

    # ── 5. 端到端延迟（不含 LLM）──
    print("\n[5/5] End-to-End Latency (embed + retrieve + rerank, no LLM)...")
    e2e_times = []
    for q in test_qs:
        t0 = time.perf_counter()
        emb = embedder.embed(q)
        results = retriever.search(emb, top_k=20)
        reranked = reranker.rerank(q, results)
        # Apply default filtering
        filtered = [r for r in reranked if r.score >= 0.50]
        e2e_times.append(time.perf_counter() - t0)
    print(f"  Mean:   {fmt_ms(statistics.mean(e2e_times))}")
    print(f"  Median: {fmt_ms(statistics.median(e2e_times))}")
    print(f"  P95:    {fmt_ms(sorted(e2e_times)[int(len(e2e_times)*0.95)])}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("Summary (15 queries, CPU mode)")
    print(f"  Embedding:          {fmt_ms(statistics.mean(emb_times))}")
    print(f"  Vector retrieval:   {fmt_ms(statistics.mean(vec_times))}")
    print(f"  BM25 retrieval:     {fmt_ms(statistics.mean(bm25_times))}")
    print(f"  Hybrid (RRF):       {fmt_ms(statistics.mean(hybrid_times))}")
    print(f"  Reranker:           {fmt_ms(statistics.mean(rerank_times))}")
    print(f"  End-to-end (no LLM):{fmt_ms(statistics.mean(e2e_times))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
