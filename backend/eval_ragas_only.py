"""Step 2: 从 JSON 读取回答 → RAGAS 评估（不重新生成，秒级重跑）"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from services.ragas_evaluator import RagasEvaluator
from config import Config

config = Config.load()
data_path = os.path.join(os.path.dirname(__file__), "..", "data", "eval_dataset.json")
dataset = json.load(open(data_path, "r", encoding="utf-8"))

print(f"Loaded {len(dataset)} QA pairs from eval_dataset.json")
print(f"Running RAGAS 3-metric evaluation...\n")

evaluator = RagasEvaluator(
    api_key=config.deepseek_api_key,
    base_url="https://api.deepseek.com/v1",
)
import asyncio
t0 = time.time()
report = asyncio.run(evaluator.evaluate(dataset))
elapsed = time.time() - t0

print(f"\nDone in {elapsed:.0f}s")
print(f"Faithfulness:       {report.faithfulness:.3f}")
print(f"Answer Relevancy:   {report.answer_relevancy:.3f}")
print(f"Context Precision:  {report.context_precision:.3f}")
print(f"\n{report.summary}")

md_path = os.path.join(os.path.dirname(__file__), "..", "ragabilitytest.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(f"""# RAG 系统能力评估报告 (RAGAS 正统框架)

> **评估日期**: 2026-06-06
> **框架**: RAGAS 0.4.3（两步法 Faithfulness + 多维度指标）
> **LLM Judge**: DeepSeek Chat (temperature=0.0)
> **测试数据集**: watsonxDocsQA / question_answers / test ({len(dataset)} 条)

---

## 一、评估方法

RAGAS 正统框架三步指标：

| 指标 | 方法 | 说明 |
|------|------|------|
| Faithfulness | RAGAS 两步法 | Step1: LLM拆claims → Step2: 逐条核验 |
| Answer Relevancy | RAGAS (本地BGE embeddings) | 回答与问题语义匹配度 |
| Context Precision | RAGAS (LLM逐句评分) | 检索文档的相关性占比 |

---

## 二、评估结果

| 指标 | RAGAS 值 | 自研一步法 | 差异 | 说明 |
|------|---------|-----------|------|------|
| Faithfulness | **{report.faithfulness:.3f}** | 0.645 | {report.faithfulness-0.645:+.3f} | RAGAS两步法{('更严格' if report.faithfulness < 0.645 else '更宽松')} |
| Answer Relevancy | **{report.answer_relevancy:.3f}** | 0.680 | {report.answer_relevancy-0.680:+.3f} | |
| Context Precision | **{report.context_precision:.3f}** | 0.675 | {report.context_precision-0.675:+.3f} | |

### 综合评级

```
{report.summary}
```

### 企业标准对照

| 指标 | 当前值 | 企业及格线 | 差距 |
|------|--------|-----------|------|
| Faithfulness | {report.faithfulness:.3f} | ≥0.80 | {0.80-report.faithfulness:.3f} |
| Answer Relevancy | {report.answer_relevancy:.3f} | ≥0.70 | {0.70-report.answer_relevancy:.3f} |
| Context Precision | {report.context_precision:.3f} | ≥0.80 | {0.80-report.context_precision:.3f} |

---

## 三、跟自研方案对比

| 维度 | 自研 | RAGAS | 结论 |
|------|------|-------|------|
| Faithfulness | 一步整体打分 0.645 | 两步法 {report.faithfulness:.3f} | RAGAS 分得更细，{('自研可能偏乐观' if report.faithfulness < 0.645 else '自研偏悲观')} |
| Context Precision | 一步整体 0.675 | 逐句评分 {report.context_precision:.3f} | |
| Answer Relevancy | LLM 打分 0.680 | embedding+LLM {report.answer_relevancy:.3f} | |

---

## 四、改进路线

1. P0: Reranker 分数阈值过滤（低于阈值不送 LLM）
2. P0: System Prompt 简化（去结构化压力，减少编造空间）
3. P1: 知识库扩展 + Query 改写术语映射增强

---

> 评估脚本: `backend/eval_ragas_only.py` | 生成回答: `backend/gen_answers.py`
""")
print(f"Report saved: {md_path}")
