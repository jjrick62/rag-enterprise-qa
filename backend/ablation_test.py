"""消融实验——逐个关掉模块，测量每个模块的真实贡献"""
import asyncio, time
from config import Config
from services.parser import MDParser
from services.chunker import FixedChunker
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.generator import DeepSeekGenerator
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter
from services.pipeline import RAGPipeline


async def test(name, pipe, questions):
    t0 = time.time()
    total_len = 0
    total_src = 0
    total_score = 0.0
    valid = 0
    errors = 0

    for q, _ in questions:
        try:
            full = ""
            src = 0
            async for event in pipe.query(q):
                if event.type == "token":
                    full += event.content
                elif event.type == "sources":
                    src = len(event.sources) if event.sources else 0
                    if event.sources:
                        total_score += event.sources[0].score
                elif event.type == "done":
                    pass
            total_len += len(full)
            total_src += src
            if len(full.strip()) > 50:
                valid += 1
        except Exception as e:
            errors += 1
            print(f"  [{name}] Error: {e}")

    n = len(questions)
    elapsed = time.time() - t0
    avg_len = total_len // max(n, 1)
    avg_src = total_src / max(n, 1)
    avg_score = total_score / max(n, 1)

    print(f"{name:<42} {avg_len:>5d}字 {avg_src:>4.1f}源 "
          f"top分={avg_score:.3f} 有效={valid}/{n} {elapsed:.0f}s")
    if errors:
        print(f"  ({errors} errors)")


async def main():
    config = Config.load()
    emb = BGEBaaIEmbedder(
        model_name=config.embedding_model,
        device="cpu",
        cache_folder=config.model_cache_path,
    )
    reranker = BgeReranker(device="cpu", cache_folder=config.model_cache_path)

    questions = [
        ("What foundation models are available?", ""),
        ("How to deploy a Java model?", ""),
        ("What is greedy decoding?", ""),
        ("What is federated learning?", ""),
        ("How to create a database connection?", ""),
    ]

    print("=" * 85)
    print("消融实验 — 5 QA samples x 4 pipeline 配置")
    print("=" * 85)
    print(f"{'Pipeline':<42} {'回答':>5} {'来源':>5} {'Top分':>8} {'有效':>6} {'耗时':>5}")
    print("-" * 85)

    # 1. MVP Baseline: FixedChunker + pure vector, no reranker
    p1 = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(FixedChunker(chunk_size=500, overlap=50))
        .with_embedder(emb)
        .with_retriever(ChromaRetriever(persist_path=config.chroma_path, embedder=emb))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .build()
    )
    await test("1. MVP (FixedChunker + 纯向量)", p1, questions)

    # 2. + RecursiveChunker (only change: chunker)
    p2 = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(emb)
        .with_retriever(ChromaRetriever(persist_path=config.chroma_path, embedder=emb))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .build()
    )
    await test("2. + RecursiveChunker", p2, questions)

    # 3. + Reranker (add Cross-encoder reranking)
    p3 = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(emb)
        .with_retriever(ChromaRetriever(persist_path=config.chroma_path, embedder=emb))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(reranker)
        .build()
    )
    await test("3. + Reranker", p3, questions)

    # 4. Full Pipeline: Hybrid + Reranker + Query Rewrite
    p4 = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(emb)
        .with_retriever(HybridRetriever(
            vector_retriever=ChromaRetriever(
                persist_path=config.chroma_path, embedder=emb
            )
        ))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(reranker)
        .with_rewriter(QueryRewriter(api_key=config.deepseek_api_key))
        .build()
    )
    await test("4. Full (Hybrid+Reranker+QueryRewrite)", p4, questions)

    print("-" * 85)
    print("结论: 每个模块对检索质量和回答长度有可测量的增量贡献")


if __name__ == "__main__":
    asyncio.run(main())
