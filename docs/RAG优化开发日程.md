# RAG 优化开发日程

> 更新：2026-06-07
> 当前阶段：端到端评测可信化完成，进入召回深度优化。

## 已完成

| 日期 | 工作 | 结果 |
|---|---|---|
| 6/5 | RecursiveChunker、Hybrid Search、Reranker、Query Rewrite | 主链路建立 |
| 6/5 | 摄入 API、多轮对话、SSE | MVP 可运行 |
| 6/6 | BM25 重建、分类过滤、RRF top_k | 检索正确性修复 |
| 6/6 | IBM 伪表原子化 | Q02 参数表可完整召回 |
| 6/6 | 阈值和每文档多样性实验 | `0.50`、每文档 4 条 |
| 6/6 | RAGAS 完整上下文修复 | 消除约 200 字评测截断 |
| 6/6 | 相对过滤四组实验 | 默认 `0.75` |
| 6/6 | Prompt 平衡化 | 表格可归纳、部分证据可回答 |
| 6/6 | 密钥与目录整理 | Key 迁移 `.env`，评测归档 |
| 6/7 | MiMo 温度/思考模式实验 | T02 三项均值 0.897，综合最优 |
| 6/7 | D4P 冻结上下文严格对照 | D4P 更忠实，MiMo 更相关，总体近似持平 |

## 当前基线

```text
Model              MiMo v2.5 Pro, non-thinking, temperature=0.2
Faithfulness       0.946
Answer Relevancy   0.876
Context Precision  0.869
Mean               0.897
Tests              68 passed (excluding local-model cache tests)
```

D4P 严格对照：`0.968 / 0.851 / 0.831`。D4P 的 Faithfulness 更高，MiMo 的 Answer Relevancy 和综合均值更高。

## 下一阶段

| 优先级 | 工作 | 成功标准 |
|---|---|---|
| P0 | 候选池 20/30/40/50 消融 | Q08 正确 chunk 进入 Reranker；记录耗时 |
| P0 | 30 题离线 Recall@5、MRR | 建立无 LLM、可重复基线 |
| P1 | Q08/Q18 固定上下文重复生成 | 区分随机拒答与检索缺失 |
| P1 | Parent-Child / 邻居 chunk 设计 | 仅在召回扩展不足时启动 |
| P2 | 英文 Embedding 对比 | 独立索引、同配置、明确收益 |
| P2 | Query Rewrite 降本 | 减少 API 调用且不降低召回 |
| P3 | Graph RAG | 仅用于明确多跳需求 |

## 暂不做

- 不继续盲调 Prompt。
- 不用标准答案冒充模型答案做端到端评分。
- 不在没有离线基线的情况下切换 Embedding。
- 不删除 ChromaDB 活动目录。
