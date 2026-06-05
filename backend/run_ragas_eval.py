"""RAGAS 正统评估入口 —— 需在 venv_ragas 中运行

用法:
  venv_ragas\Scripts\activate
  python run_ragas_eval.py
"""
import asyncio, json, urllib.request, time, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from services.parser import MDParser
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.generator import DeepSeekGenerator
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter
from services.pipeline import RAGPipeline
from services.ragas_evaluator import RagasEvaluator, EvalSample


async def main():
    # ── Build Pipeline (same as main.py) ──
    config = Config.load()
    emb = BGEBaaIEmbedder(
        model_name=config.embedding_model, device="cpu",
        cache_folder=config.model_cache_path,
    )
    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(emb)
        .with_retriever(HybridRetriever(
            vector_retriever=ChromaRetriever(persist_path=config.chroma_path, embedder=emb)
        ))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(BgeReranker(device="cpu", cache_folder=config.model_cache_path))
        .with_rewriter(QueryRewriter(api_key=config.deepseek_api_key))
        .build()
    )

    # ── Load QA dataset ──
    qa_url = ("https://datasets-server.huggingface.co/rows?"
              "dataset=ibm-research%2FwatsonxDocsQA&"
              "config=question_answers&split=test&offset=0&length=50")
    with urllib.request.urlopen(qa_url) as resp:
        qa_data = json.loads(resp.read().decode())
    qa_pairs = [(r["row"]["question"], r["row"]["correct_answer"]) for r in qa_data["rows"]]
    print(f"Loaded {len(qa_pairs)} QA pairs\n")

    # ── Generate answers (run pipeline on all questions) ──
    dataset = []
    t0 = time.time()
    for i, (question, ground_truth) in enumerate(qa_pairs[:20], 1):
        full = ""; contexts = []
        async for event in pipeline.query(question):
            if event.type == "token": full += event.content
            elif event.type == "sources":
                contexts = [s.excerpt for s in (event.sources or [])]
        dataset.append({
            "question": question,
            "answer": full,
            "contexts": contexts,
            "ground_truth": ground_truth,
        })
        print(f"  #{i:02d} {question[:60]}... -> {len(full)}字 {len(contexts)}源")

    gen_time = time.time() - t0
    print(f"\nGeneration: {len(dataset)} QA in {gen_time:.0f}s\n")

    # ── RAGAS 评估 ──
    print("Running RAGAS evaluation (two-step faithfulness)...")
    evaluator = RagasEvaluator(
        api_key=config.deepseek_api_key,
        base_url="https://api.deepseek.com/v1",
    )
    t0 = time.time()
    report = await evaluator.evaluate(dataset)
    eval_time = time.time() - t0

    # ── Print Report ──
    print(f"\n{'='*60}")
    print(f"RAGAS Evaluation ({eval_time:.0f}s)")
    print(f"{'='*60}")
    print(f"Faithfulness:      {report.faithfulness:.3f}")
    print(f"Answer Relevancy:  {report.answer_relevancy:.3f}")
    print(f"Context Precision: {report.context_precision:.3f}")
    print(f"Context Recall:    {report.context_recall:.3f}")
    print(f"\n{report.summary}")

    # ── Save ──
    md = generate_report_md(report, dataset)
    report_path = os.path.join(os.path.dirname(__file__), "..", "ragabilitytest.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\nReport saved: {report_path}")


def generate_report_md(r, dataset) -> str:
    n = len(dataset)
    return f"""# RAG 系统能力评估报告 (RAGAS 正统框架)

> **评估日期**: 2026-06-05
> **框架**: RAGAS {__import__('ragas').__version__}（两步法 Faithfulness + 多维度指标）
> **LLM Judge**: DeepSeek Chat (temperature=0.0)
> **测试数据集**: watsonxDocsQA / question_answers / test ({n} 条)

---

## 一、评估方法

使用 RAGAS 正统框架，非自研替代方案：

| 指标 | 方法 | 说明 |
|------|------|------|
| Faithfulness | RAGAS 两步法 | Step1: LLM拆claims → Step2: 逐条核验 |
| Answer Relevancy | RAGAS | 回答与问题的语义匹配度 |
| Context Precision | RAGAS | 检索文档中相关内容的占比 |
| Context Recall | RAGAS | 标准答案在检索上下文中的覆盖率 |

**RAGAS 两步法 vs 自研一步法**:
- 两步法更精确：先细粒度拆声明，再逐条核验
- 一步法偏乐观：LLM 整体打分容易给模糊分数

---

## 二、评估结果

### 总览

| 指标 | RAGAS 值 | 自研值 | 差异 | 企业标准 |
|------|---------|--------|------|---------|
| Faithfulness | **{r.faithfulness:.3f}** | 0.645 | {r.faithfulness-0.645:+.3f} | ≥0.80 |
| Answer Relevancy | **{r.answer_relevancy:.3f}** | 0.680 | {r.answer_relevancy-0.680:+.3f} | ≥0.70 |
| Context Precision | **{r.context_precision:.3f}** | 0.675 | {r.context_precision-0.675:+.3f} | ≥0.80 |
| Context Recall | **{r.context_recall:.3f}** | N/A | — | ≥0.70 |

### 综合评级

```
{r.summary}
```

---

## 三、跟自研方案的对比

| 维度 | 自研 (LLMJudgeEvaluator) | RAGAS 正统 | 可靠性 |
|------|------------------------|-----------|--------|
| Faithfulness 评分粒度 | 一步整体打分 | 两步法（拆claims→逐条核验） | RAGAS 更可信 |
| Answer Relevancy | 一次 LLM 调用 | embedding 语义相似度 + LLM | RAGAS 更客观 |
| Context Precision | 一次 LLM 调用 | LLM 逐句判断相关性 | RAGAS 更精确 |
| Context Recall | 不支持 | LLM 对比标准答案 | RAGAS 独有 |

---

## 四、改进路线

基于 RAGAS {r.faithfulness:.3f} Faithfulness（距 ≥0.80 差 {0.80-r.faithfulness:.3f}）：

1. **P0**: Reranker 分数阈值过滤（低分 chunk 不送 LLM）
2. **P0**: System Prompt 简化（去结构化压力）
3. **P1**: Context Recall 提升（知识库扩展 + Query 改写优化）

---

> 评估脚本: `backend/run_ragas_eval.py` | 评估器: `backend/services/ragas_evaluator.py`
"""


if __name__ == "__main__":
    asyncio.run(main())
