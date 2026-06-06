"""纯文本题对比trace — 看chunk是否被完整传递"""
import asyncio, sys, os, io, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from config import Config
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter

async def trace(q, label):
    c = Config.load()
    emb = BGEBaaIEmbedder(model_name=c.embedding_model, device='cpu', cache_folder=c.model_cache_path)
    reranker = BgeReranker(device='cpu', cache_folder=c.model_cache_path)
    rewriter = QueryRewriter(api_key=c.deepseek_api_key)

    rw = q  # skip rewriter — DeepSeek API unreachable
    vec_retriever = ChromaRetriever(persist_path=c.chroma_path, embedder=emb)
    hybrid = HybridRetriever(vector_retriever=vec_retriever)
    q_emb = emb.embed([rw])[0]

    bm25 = hybrid._bm25_search(rw, top_k=20)
    vec = vec_retriever.search(q_emb, top_k=20)
    rrf = hybrid._rrf_merge(vec, bm25, top_k=15)
    reranked = reranker.rerank(rw, rrf, top_k=5)

    print(f'\n{"="*60}')
    print(f'  {label}: {q[:70]}')
    print(f'  RW: {rw[:80]}')
    print(f'{"="*60}')

    # 找 eval 里的 ground truth 和 answer
    with open('../data/eval_dataset.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        if item['question'] == q:
            print(f'  GT(前250): {item["ground_truth"][:250]}')
            print(f'  ANSWER(前250): {item["answer"][:250]}')
            break

    print(f'\n  --- Reranker Top-3 chunks (完整内容) ---')
    for i, r in enumerate(reranked[:3]):
        src = r.chunk.metadata.source_doc
        print(f'  [#{i+1} score={r.score:.3f} | {src[:40]}')
        print(f'  {r.chunk.content[:400]}')
        print()

async def main():
    qs = [
        ('Q03', 'What are tokens and tokenization?'),
        ('Q13', 'What is the retrieval-augmented generation pattern?'),
        ('Q10', 'What is trust calibration?'),
        ('Q18', 'What are the key functions of the geospatial library?'),
    ]
    for label, q in qs:
        await trace(q, label)

asyncio.run(main())
