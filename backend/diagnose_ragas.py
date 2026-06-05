"""RAGAS 深度诊断——逐条分析低分根因"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision
from openai import OpenAI
from ragas.llms import llm_factory

data = json.load(open('../data/eval_dataset.json', 'r', encoding='utf-8'))
c = OpenAI(api_key='sk-ed5b2d43637d45648c325b52a2c24835', base_url='https://api.deepseek.com/v1')
llm = llm_factory('deepseek-chat', client=c, temperature=0.0)
faithfulness.llm = llm
context_precision.llm = llm

results = []
for i, d in enumerate(data):
    ds = Dataset.from_list([d])
    r = evaluate(ds, metrics=[faithfulness, context_precision])
    f_raw = r['faithfulness']; cp_raw = r['context_precision']
    f_val = float(f_raw[0]) if isinstance(f_raw, list) else float(f_raw)
    cp_val = float(cp_raw[0]) if isinstance(cp_raw, list) else float(cp_raw)
    ans_len = len(d['answer'])
    ctx_count = len(d['contexts'])
    results.append((i+1, d['question'][:60], f_val, cp_val, ans_len, ctx_count))

# Summary
print(f"{'#':<4} {'Question':<50} {'Faith':<7} {'CtxPrec':<8} {'AnsLen':<7} {'CtxCnt':<7}")
print('-' * 85)
for r in results:
    print(f"{r[0]:<4} {r[1]:<50} {r[2]:<7.3f} {r[3]:<8.3f} {r[4]:<7} {r[5]:<7}")

print()
print('=== 低 Faithfulness 样本 (< 0.6) ===')
low = [r for r in results if r[2] < 0.6]
for r in low:
    d = data[r[0]-1]
    print(f'Q{r[0]}: {d["question"]}')
    print(f'  Faith={r[2]:.3f}  CtxPrec={r[3]:.3f}  Len={r[4]}  CtxCnt={r[5]}')
    ctx_preview = d['contexts'][0][:150] if d['contexts'] else '(none)'
    print(f'  Context[0]: {ctx_preview}')
    ans_preview = d['answer'][:200]
    print(f'  Answer: {ans_preview}')
    print()

# Correlation check
high_cp = [r for r in results if r[3] >= 0.6]
low_cp = [r for r in results if r[3] < 0.6]
if high_cp and low_cp:
    avg_f_high = sum(r[2] for r in high_cp) / len(high_cp)
    avg_f_low = sum(r[2] for r in low_cp) / len(low_cp)
    print(f'=== 检索→生成 关联分析 ===')
    print(f'ContextPrecision >= 0.6: avg Faithfulness = {avg_f_high:.3f} ({len(high_cp)}条)')
    print(f'ContextPrecision <  0.6: avg Faithfulness = {avg_f_low:.3f} ({len(low_cp)}条)')
    print(f'差距: {avg_f_high - avg_f_low:.3f}')
