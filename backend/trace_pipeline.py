"""跟踪 pipeline.query() 每一步的输入输出"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
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
from services.prompts import build_context_block

async def main():
    c = Config.load()
    emb = BGEBaaIEmbedder(model_name=c.embedding_model, device='cpu', cache_folder=c.model_cache_path)
    reranker = BgeReranker(device='cpu', cache_folder=c.model_cache_path)
    rewriter = QueryRewriter(provider=get_provider("rewrite"))

    q = 'What are parameters in CLEM'

    # Step 1: Rewrite
    rw = await rewriter.rewrite(q)
    print(f'[Step 1: Rewrite]')
    print(f'  IN : {q}')
    print(f'  OUT: {rw}')
    print()

    # Step 2: BM25 + Vector raw scores
    vec_retriever = ChromaRetriever(persist_path=c.chroma_path, embedder=emb)
    hybrid = HybridRetriever(vector_retriever=vec_retriever)

    q_emb = emb.embed([rw])[0]
    bm25_results = hybrid._bm25_search(rw, top_k=20)
    vec_results = vec_retriever.search(q_emb, top_k=20)

    print(f'[Step 2a: BM25 Top-20]')
    for i, r in enumerate(bm25_results[:10]):
        doc = r.chunk.metadata.source_doc
        print(f'  #{i+1} score={r.score:6.1f} | {doc[:60]}')
        if 'CLEM' in r.chunk.content or 'clem' in r.chunk.content.lower():
            print(f'        *** CONTAINS CLEM ***')
    print(f'  ... (total {len(bm25_results)})')
    print()

    print(f'[Step 2b: Vector Top-20]')
    for i, r in enumerate(vec_results[:10]):
        doc = r.chunk.metadata.source_doc
        print(f'  #{i+1} score={r.score:.3f} | {doc[:60]}')
        if 'CLEM' in r.chunk.content or 'clem' in r.chunk.content.lower():
            print(f'        *** CONTAINS CLEM ***')
    print(f'  ... (total {len(vec_results)})')
    print()

    # Step 3: RRF merge
    rrf_results = hybrid._rrf_merge(vec_results, bm25_results, top_k=15)
    print(f'[Step 3: RRF Top-15]')
    clem_in_rrf = False
    for i, r in enumerate(rrf_results):
        doc = r.chunk.metadata.source_doc
        has_clem = 'CLEM' in r.chunk.content or 'clem' in r.chunk.content.lower()
        print(f'  #{i+1} RRF={r.score:.4f} | {doc[:55]}')
        if has_clem:
            print(f'        *** CONTAINS CLEM ***')
            clem_in_rrf = True
    print(f'  CLEM chunk in RRF Top-15: {clem_in_rrf}')
    print()

    # Step 4: Reranker
    reranked = reranker.rerank(rw, rrf_results, top_k=5)
    print(f'[Step 4: Reranker Top-5]')
    clem_in_rerank = False
    for i, r in enumerate(reranked):
        doc = r.chunk.metadata.source_doc
        has_clem = 'CLEM' in r.chunk.content or 'clem' in r.chunk.content.lower()
        print(f'  #{i+1} score={r.score:.3f} | {doc[:55]} | excerpt: {r.chunk.content[:80]}')
        if has_clem:
            print(f'        *** CONTAINS CLEM ***')
            clem_in_rerank = True
    print(f'  CLEM chunk in Reranker Top-5: {clem_in_rerank}')
    print()

    # Summary
    print('=' * 60)
    if clem_in_rrf and not clem_in_rerank:
        print('DIAGNOSIS: CLEM chunk survived RRF but Reranker dropped it')
        print('→ Reranker IS the bottleneck')
    elif not clem_in_rrf:
        print('DIAGNOSIS: CLEM chunk did NOT reach Reranker')
        print('→ BM25/Vector/RRF is the bottleneck')
    else:
        print('DIAGNOSIS: CLEM chunk reached LLM but still got rejected')
        print('→ LLM/System Prompt is the bottleneck')

asyncio.run(main())
