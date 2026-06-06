"""Evaluate one model-generated answer dataset without modifying it."""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from services.ragas_evaluator import RagasEvaluator
from config import Config


parser = argparse.ArgumentParser()
parser.add_argument(
    "dataset",
    nargs="?",
    default=os.path.join(
        "..", "data", "evaluations", "datasets", "eval_dataset_r075.json"
    ),
)
parser.add_argument("--output")
args = parser.parse_args()

config = Config.load()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_CACHE = os.path.abspath(os.path.join(BASE_DIR, args.dataset))

if not os.path.exists(EVAL_CACHE):
    raise FileNotFoundError(
        f"{EVAL_CACHE} does not exist. Generate the answer dataset first."
    )
print(f"Loading cached eval dataset from {EVAL_CACHE}")

# Phase 2: RAGAS 评估
dataset = json.load(open(EVAL_CACHE, "r", encoding="utf-8"))
print(f"Evaluating {len(dataset)} QA pairs with RAGAS (MiMo)...\n")

evaluator = RagasEvaluator(
    api_key=config.deepseek_api_key,
)
t0 = time.time()
report = asyncio.run(evaluator.evaluate(dataset))
elapsed = time.time() - t0

print(f"\nDone in {elapsed:.0f}s")
print(f"Faithfulness:       {report.faithfulness:.3f}")
print(f"Answer Relevancy:   {report.answer_relevancy:.3f}")
print(f"Context Precision:  {report.context_precision:.3f}")
print(f"\n{report.summary}")

# 输出 per-sample 分数
print("\n=== Per-Question Scores ===")
for s in report.per_sample:
    q = s.get('user_input', '')[:60]
    f = s.get('faithfulness', 'N/A')
    if isinstance(f, (int, float)):
        print(f"  Faith={f:.3f} | {q}")
    else:
        print(f"  Faith={f} | {q}")

if args.output:
    output_path = os.path.abspath(os.path.join(BASE_DIR, args.output))
    payload = {
        "dataset": EVAL_CACHE,
        "elapsed_seconds": elapsed,
        "faithfulness": report.faithfulness,
        "answer_relevancy": report.answer_relevancy,
        "context_precision": report.context_precision,
        "context_recall": report.context_recall,
        "summary": report.summary,
        "per_sample": report.per_sample,
    }
    with open(output_path, "w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved report to {output_path}")
