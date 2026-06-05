# RAG 优化开发日程（v3 — 6/6 更新）

> **当前**: 8 个模块完成，BM25 bug 已修复，RAGAS 基线已建立。
> **下一目标**: Chunk 信噪比优化。

---

## 已完成

| 日期 | 模块 |
|------|------|
| 6/5 | A.递归语义分块 / C.Reranker / D.Query改写 / B.HybridSearch / H.摄入API / G.多轮对话 |
| 6/5 | RAGAS 评估上线，System Prompt 简化 |
| 6/6 | **BM25 bug 修复**（HybridRetriever 未从 ChromaDB 重建索引） |
| 6/6 | 管道诊断工具（trace_pipeline.py） |
| 6/6 | 文档级去重方案评估→回滚（长文档多 chunk 场景是负优化） |

---

## 待做

| 优先级 | 措施 | 预计耗时 |
|--------|------|---------|
| **P0** | Chunk 信噪比优化 | 1-2天 |
| P2 | Graph RAG | 远期 |

## 已砍

| 模块 | 原因 |
|------|------|
| 知识库扩展 | 伪需求——答案已在库中，chunk 切碎才是问题 |

---

## 诊断教训

1. 永远先验证每个组件是否真的在工作，再做复杂诊断（BM25 空跑了三小时才发现）
2. Reranker sigmoid 是正确的——0.68 vs 0.50 是 chunk 信噪比低的结果，不是激活函数的问题
3. `gen_answers.py`（生成回答）+ `eval_ragas_only.py`（RAGAS评估）分离是正确的架构决策
