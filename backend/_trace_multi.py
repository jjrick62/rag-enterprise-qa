"""快速多问题 trace"""
import asyncio, sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import Config
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter

async def trace_one(q):
    c = Config.load()
    emb = BGEBaaIEmbedder(model_name=c.embedding_model, device='cpu', cache_folder=c.model_cache_path)
    reranker = BgeReranker(device='cpu', cache_folder=c.model_cache_path)
    rewriter = QueryRewriter(api_key=c.deepseek_api_key)

    rw = await rewriter.rewrite(q)
    vec_retriever = ChromaRetriever(persist_path=c.chroma_path, embedder=emb)
    hybrid = HybridRetriever(vector_retriever=vec_retriever)
    q_emb = emb.embed([rw])[0]

    bm25 = hybrid._bm25_search(rw, top_k=20)
    vec = vec_retriever.search(q_emb, top_k=20)
    rrf = hybrid._rrf_merge(vec, bm25, top_k=15)
    reranked = reranker.rerank(rw, rrf, top_k=5)

    print('Q: %s' % q)
    print('RW: %s' % rw)
    print('BM25 #1: %s (%.1f)' % (bm25[0].chunk.metadata.source_doc[:50], bm25[0].score) if bm25 else 'NONE')
    print('Vec #1: %s (%.3f)' % (vec[0].chunk.metadata.source_doc[:50], vec[0].score) if vec else 'NONE')
    print('RRF #1: %s (%.4f)' % (rrf[0].chunk.metadata.source_doc[:50], rrf[0].score) if rrf else 'NONE')
    print('Rerank #1: %s (%.3f)' % (reranked[0].chunk.metadata.source_doc[:50], reranked[0].score) if reranked else 'NONE')
    print('Rerank scores: %s' % [round(r.score,3) for r in reranked])
    print('---')

async def main():
    for q in [
        'What is greedy decoding?',
        'What is trust calibration?',
        'What is the retrieval-augmented generation pattern?',
    ]:
        await trace_one(q)

asyncio.run(main())
