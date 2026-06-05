# RAG 优化开发日程（v2 — 6/6 更新）

> **当前**: 七大优化模块已完成，RAGAS 评估上线。策略调整为**微调现有架构优先**，Graph RAG 后置。

---

## 已完成（6/5 一天）

| 模块 | 说明 |
|------|------|
| A. 递归语义分块 | FixedChunker → RecursiveChunker |
| C. Reranker | BGE-reranker-v2-m3 Cross-encoder 精排 |
| D. Query 改写 | DeepSeek 改写 + 54篇索引辅助 |
| B. Hybrid Search | BM25 + 向量 + RRF 融合 |
| H. 摄入API | MD5去重 + 增量 + DELETE + 全量重摄入 |
| G. 多轮对话 | 会话管理 + 历史注入 |
| — RAGAS 评估 | 正统框架上线，基线数据采集 |
| — System Prompt 简化 | 1498→450字，去强制结构 |

---

## Phase 1: 检索精度攻坚（6/6-6/7）

**目标**: Context Precision 0.537 → 0.70，Faithfulness 0.542 → 0.65

| 日期 | 措施 | 预期提升 | 工作量 |
|------|------|---------|--------|
| 6/6 | **Reranker 阈值过滤**: 修改 pipeline.query()，Reranker 后 score<0.5 的 chunk 不送 LLM | ContextPrec +0.10 | 30min |
| 6/6 | **Query 改写增强**: 分析 RAGAS 低分 query 的共性，补全跨领域术语映射表 | ContextPrec +0.05 | 1h |
| 6/7 | **全量重评**: 改完重跑 gen_answers + RAGAS，验证提升幅度 | — | 30min |
| 6/7 | **知识库扩展调研**: 识别 54 篇文档的覆盖盲区，规划补充方向 | — | 1h |

> **里程碑**: RAGAS 全指标对比报告（Round 1→2→3）

---

## Phase 2: 检索精度第二轮 + 前端（6/8-6/10）

**目标**: Context Precision → 0.75

| 日期 | 措施 | 预期提升 |
|------|------|---------|
| 6/8 | 知识库扩展：HuggingFace/网上找薄弱领域文档补充 | ContextPrec +0.07 |
| 6/9 | RAGAS 重评 + Prompt 微调 | — |
| 6/10 | 前端最小可用版（ChatPanel + 测试用例） | — |

> **里程碑**: RAGAS Context Precision ≥ 0.70

---

## Phase 3: Graph RAG（远期，日期待定）

**前置条件**: Context Precision 稳定在 ≥0.70 后启动

| 模块 | 内容 |
|------|------|
| 实体抽取 | 已有代码，需全量 54 篇抽取 |
| 社区检测 + 摘要 | Leiden 聚类 + LLM 摘要 |
| 图谱检索器 | 已实现 GraphRetriever，需集成 Pipeline |

---

## 策略变更说明

```
旧策略:  所有优化平行推进 → Graph RAG 排最后但是独立大模块
新策略:  先微调现有架构把 RAGAS 做上去 → Graph RAG 在检索稳定后启动

原因:   RAGAS 评估发现 Context Precision=0.537 是最大短板
       改 Retriever 参数比上新架构见效快、风险低
       Graph RAG 是长期炫技，不应该是救急方案
```
