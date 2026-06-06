"""瞬间扫评：per-question 答案 vs 上下文 vs ground truth"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('../data/eval_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for i, item in enumerate(data):
    q = item['question']
    a = item.get('answer', '')
    ctxs = item.get('contexts', [])
    gt = item.get('ground_truth', '')

    # 快速分析
    a_len = len(a)
    ctx_count = len(ctxs)
    ctx_total_chars = sum(len(c) for c in ctxs)

    # 检查 answer 里是否出现了 ground truth 的关键词
    gt_words = set(gt.lower().split()) - {'the', 'a', 'an', 'is', 'are', 'of', 'in', 'to', 'for', 'and', 'or', 'it', 'that', 'this', 'be', 'as', 'by', 'on', 'at', 'with', 'from'}
    a_words = set(a.lower().split())
    overlap = gt_words & a_words
    overlap_ratio = len(overlap) / len(gt_words) if gt_words else 0

    # 检查上下文是否覆盖 ground truth 关键词
    ctx_text = ' '.join(ctxs).lower()
    ctx_hits = sum(1 for w in gt_words if w in ctx_text)
    ctx_coverage = ctx_hits / len(gt_words) if gt_words else 0

    print(f'Q{i:02d} | ans={a_len}ch | ctx={ctx_count}seg/{ctx_total_chars}ch | gt_overlap={overlap_ratio:.1%} | ctx_cover={ctx_coverage:.1%} | {q[:70]}')

print('\n--- 每道题详细: 答案前200字 + 上下文第一段前100字 ---')
for i, item in enumerate(data):
    q = item['question']
    a = item.get('answer', '')
    ctxs = item.get('contexts', [])

    print(f'\n===== Q{i:02d}: {q[:80]} =====')
    print(f'ANSWER(前200): {a[:200]}')
    if ctxs:
        print(f'CTX[0](前150): {ctxs[0][:150]}')
    else:
        print('CTX: EMPTY!')
