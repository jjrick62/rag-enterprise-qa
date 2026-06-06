"""RAGAS 评估——使用标准答案 + 当前 pipeline 检索上下文

两阶段可分离：
  Phase 1 (本脚本): 跑 pipeline 检索上下文 + 用标准答案 → 存 eval_dataset.json
  Phase 2 (重跑本脚本): 如果 eval_dataset.json 已存在，直接读缓存跑 RAGAS
"""
import asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from services.ragas_evaluator import RagasEvaluator
from config import Config

config = Config.load()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
GT_PATH = os.path.join(DATA_DIR, "watsonxDocsQA_test.json")
EVAL_CACHE = os.path.join(DATA_DIR, "eval_dataset.json")

# Phase 1: 如果没有缓存，用标准答案 + pipeline 检索重建
if not os.path.exists(EVAL_CACHE):
    print("No eval_dataset.json found — running pipeline retrieval with GT answers...")
    from services.embedder import BGEBaaIEmbedder
    from services.retriever import ChromaRetriever
    from services.hybrid_retriever import HybridRetriever
    from services.reranker import BgeReranker
    from services.pipeline import RAGPipeline
    from services.parser import MDParser
    from services.recursive_chunker import RecursiveChunker
    from services.generator import DeepSeekGenerator

    qa_pairs = json.load(open(GT_PATH, "r", encoding="utf-8"))
    emb = BGEBaaIEmbedder(model_name=config.embedding_model, device="cpu", cache_folder=config.model_cache_path)
    reranker = BgeReranker(device="cpu", cache_folder=config.model_cache_path)
    hybrid = HybridRetriever(ChromaRetriever(config.chroma_path, emb))

    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(500, 0.15, 50))
        .with_embedder(emb)
        .with_retriever(HybridRetriever(ChromaRetriever(config.chroma_path, emb)))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(reranker)
        .build()
    )

    dataset = []
    t0 = time.time()
    for i, (q, gt) in enumerate(qa_pairs, 1):
        # 直接用 HybridRetriever + Reranker 检索（同步，不调 LLM）
        q_emb = emb.embed([q])[0]
        rrf_results = hybrid.search(q_emb, top_k=20)
        results = reranker.rerank(q, rrf_results, top_k=5)
        contexts = [r.chunk.content[:500] for r in results]
        dataset.append({
            "question": q,
            "answer": gt[:1500],      # 用标准答案！
            "contexts": contexts,
            "ground_truth": gt,
        })
        if i % 5 == 0:
            print(f"  {i}/{len(qa_pairs)} questions retrieved...")
    json.dump(dataset, open(EVAL_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Saved {len(dataset)} QA to {EVAL_CACHE} ({time.time()-t0:.0f}s)")
else:
    print(f"Loading cached eval dataset from {EVAL_CACHE}")

# Phase 2: RAGAS 评估
dataset = json.load(open(EVAL_CACHE, "r", encoding="utf-8"))
print(f"Evaluating {len(dataset)} QA pairs with RAGAS (MiMo)...\n")

evaluator = RagasEvaluator(
    api_key="sk-chxgsdnbeafvw2dfatn2iz5gtbpj5s1xz2l8e319v3t0l8jy",
    base_url="https://api.xiaomimimo.com/v1",
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
