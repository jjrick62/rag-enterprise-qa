"""Q02: 追踪 3 个表碎片的下落"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from config import Config
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.reranker import BgeReranker

c = Config.load()
emb = BGEBaaIEmbedder(model_name=c.embedding_model, device='cpu', cache_folder=c.model_cache_path)
reranker = BgeReranker(device='cpu', cache_folder=c.model_cache_path)
vec = ChromaRetriever(persist_path=c.chroma_path, embedder=emb)
hybrid = HybridRetriever(vector_retriever=vec)
q = 'What tuning parameters are available for IBM foundation models?'
q_emb = emb.embed([q])[0]

bm25 = hybrid._bm25_search(q, top_k=20)
vec_res = vec.search(q_emb, top_k=20)
rrf = hybrid._rrf_merge(vec_res, bm25, top_k=20)

print('=== RRF Top-20 中 3 个表碎片的位置 ===')
for i, r in enumerate(rrf):
    content = r.chunk.content
    tag = ''
    if 'Initialization method' in content and 'Random' in content:
        tag = ' <<< FRAG-A (Init method + Init text)'
    elif 'Batch size' in content and 'Accumulation' in content:
        tag = ' <<< FRAG-B (Batch + Accumulation)'
    elif 'Learning rate' in content and 'Number of epochs' in content:
        tag = ' <<< FRAG-C (Learning rate + Epochs)'
    src = r.chunk.metadata.source_doc
    print(f'  RRF #{i+1:2d} score={r.score:.4f} | {src[:35]:35s} | {content[:80].strip()}{tag}')

print()
print('=== Reranker 重排 Top-20 ===')
reranked = reranker.rerank(q, rrf, top_k=20)
for i, r in enumerate(reranked):
    content = r.chunk.content
    tag = ''
    if 'Initialization method' in content and 'Random' in content:
        tag = ' *** FRAG-A (Init+Init)'
    elif 'Batch size' in content and 'Accumulation' in content:
        tag = ' *** FRAG-B (Batch+Acc)'
    elif 'Learning rate' in content and 'Number of epochs' in content:
        tag = ' *** FRAG-C (LR+Epoch)'
    src = r.chunk.metadata.source_doc
    marker = '>>> TOP-5 <<<' if i < 5 else ''
    print(f'  Rerank #{i+1:2d} score={r.score:.3f} {marker:12s} | {src[:35]:35s} | {content[:60].strip()}{tag}')
