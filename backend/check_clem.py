"""检查 CLEM 文档是否被检索到"""
import os, glob, numpy as np
from rank_bm25 import BM25Okapi
from services.embedder import BGEBaaIEmbedder

files = sorted(glob.glob('../data/documents/*.md'))
texts = [open(f, 'r', encoding='utf-8').read() for f in files]
query = 'What are parameters in CLEM'

# BM25
tokenized = [t.lower().split() for t in texts]
bm25 = BM25Okapi(tokenized)
scores = bm25.get_scores(query.lower().split())
bm25_top = np.argsort(scores)[::-1][:10]

print('=== BM25 Top-10 ===')
for rank, idx in enumerate(bm25_top):
    name = os.path.basename(files[idx])
    print(f'  Rank{rank+1}: {scores[idx]:.2f} | {name[:60]}')

# Vector
emb = BGEBaaIEmbedder(device='cpu', cache_folder='./models')
q_emb = emb.embed([query])[0]
doc_embs = emb.embed(texts)
vec_scores = np.dot(doc_embs, q_emb)
vec_top = np.argsort(vec_scores)[::-1][:10]

print()
print('=== Vector Top-10 ===')
for rank, idx in enumerate(vec_top):
    name = os.path.basename(files[idx])
    print(f'  Rank{rank+1}: {vec_scores[idx]:.3f} | {name[:60]}')

# Check RRF merge
rrf_k = 60
rrf_scores = {}
for rank, idx in enumerate(bm25_top[:20]):
    rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rrf_k + rank + 1)
for rank, idx in enumerate(vec_top[:20]):
    rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rrf_k + rank + 1)

rrf_top = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:15]
print()
print('=== RRF Top-15 ===')
for rank, (idx, s) in enumerate(rrf_top):
    name = os.path.basename(files[idx])
    print(f'  Rank{rank+1}: {s:.4f} | {name[:60]}')

# Where is the CLEM doc?
clem_idx = None
for i, f in enumerate(files):
    if 'supernode' in os.path.basename(f).lower() or 'flow' in os.path.basename(f).lower():
        clem_idx = i
        break

if clem_idx is not None:
    print(f'\n=== CLEM doc ({os.path.basename(files[clem_idx])}) rankings ===')
    # Find BM25 rank
    bm25_ranks = np.argsort(scores)[::-1]
    bm25_pos = list(bm25_ranks).index(clem_idx) + 1 if clem_idx in bm25_ranks else 'N/A'
    vec_pos = list(vec_top).index(clem_idx) + 1 if clem_idx in vec_top[:50] else 'N/A'
    rrf_pos = next((i+1 for i, (idx, _) in enumerate(rrf_top) if idx == clem_idx), 'N/A')

    print(f'  BM25 Rank: {bm25_pos}/{len(files)} (score={scores[clem_idx]:.2f})')
    print(f'  Vector Rank: {vec_pos}/{len(files)} (score={vec_scores[clem_idx]:.3f})')
    print(f'  RRF Merge Rank: {rrf_pos}/{len(rrf_top)}')
    print()
    print(f'  Document content preview:')
    print(f'  {texts[clem_idx][:300]}')
