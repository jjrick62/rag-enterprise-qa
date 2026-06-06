"""Q02 全链路trace — 每步输入输出完整打印"""
import asyncio, sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from config import Config
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter
from services.generator import DeepSeekGenerator
from services.prompts import build_context_block

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    c = Config.load()
    emb = BGEBaaIEmbedder(model_name=c.embedding_model, device='cpu', cache_folder=c.model_cache_path)
    reranker = BgeReranker(device='cpu', cache_folder=c.model_cache_path)
    rewriter = QueryRewriter(api_key=c.deepseek_api_key)
    generator = DeepSeekGenerator(api_key=c.deepseek_api_key)

    q = 'What tuning parameters are available for IBM foundation models?'

    # 先看 eval 里的 ground truth
    eval_path = os.path.join(BASE_DIR, '..', 'data', 'eval_dataset.json')
    with open(eval_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        if 'tuning' in item['question'] and 'IBM' in item['question']:
            print('=== GROUND TRUTH ===')
            print(item['ground_truth'][:500])
            print()
            break

    # Step 1: Rewrite
    rw = await rewriter.rewrite(q)
    print('=== STEP 1: QUERY REWRITE ===')
    print(f'  IN : {q}')
    print(f'  OUT: {rw}')
    print()

    # Step 2: BM25 + Vector
    vec_retriever = ChromaRetriever(persist_path=c.chroma_path, embedder=emb)
    hybrid = HybridRetriever(vector_retriever=vec_retriever)
    q_emb = emb.embed([rw])[0]

    bm25_results = hybrid._bm25_search(rw, top_k=20)
    vec_results = vec_retriever.search(q_emb, top_k=20)

    print('=== STEP 2a: BM25 Top-10 ===')
    for i, r in enumerate(bm25_results[:10]):
        doc = r.chunk.metadata.source_doc
        print(f'  #{i+1} score={r.score:6.1f} | {doc[:60]}')
    print()

    print('=== STEP 2b: VECTOR Top-10 ===')
    for i, r in enumerate(vec_results[:10]):
        doc = r.chunk.metadata.source_doc
        print(f'  #{i+1} score={r.score:.3f} | {doc[:60]}')
    print()

    # Step 3: RRF Top-15 — show full chunk content
    rrf_results = hybrid._rrf_merge(vec_results, bm25_results, top_k=15)
    print('=== STEP 3: RRF Top-15 (FULL CHUNK CONTENT) ===')
    for i, r in enumerate(rrf_results):
        doc = r.chunk.metadata.source_doc
        print(f'--- RRF #{i+1} score={r.score:.4f} | {doc[:50]} ---')
        print(r.chunk.content[:300])
        print()
    print()

    # Step 4: Reranker Top-5 — show full content
    reranked = reranker.rerank(rw, rrf_results, top_k=5)
    print('=== STEP 4: RERANKER Top-5 (FULL CHUNK CONTENT) ===')
    for i, r in enumerate(reranked):
        doc = r.chunk.metadata.source_doc
        print(f'--- Rerank #{i+1} score={r.score:.3f} | {doc[:50]} ---')
        print(r.chunk.content[:400])
        print()

    # Step 5: Build context block (what LLM actually sees)
    context_block = build_context_block(reranked)
    print('=== STEP 5: CONTEXT BLOCK to LLM ===')
    print(context_block[:1500])
    print(f'  ... (total {len(context_block)} chars)')
    print()

    # Step 6: Generate answer
    print('=== STEP 6: LLM ANSWER ===')
    answer_parts = []
    async for event in generator.generate(rw, reranked):
        if event.type == 'token' and event.content:
            answer_parts.append(event.content)
    print(''.join(answer_parts)[:2000])

asyncio.run(main())
