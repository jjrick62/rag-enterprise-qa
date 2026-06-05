# RAG 系统能力评估报告

> **评估框架**: RAGAS 0.4.3 | **LLM Judge**: DeepSeek Chat | **测试集**: watsonxDocsQA (20 条)
> **被测系统**: RecursiveChunker + Hybrid(BM25+Vector+RRF) + BGE-Reranker-v2-m3 + QueryRewriter + DeepSeek

---

## 一、评估方法

采用 RAGAS 框架三个核心指标：

### Faithfulness（忠实度）

两步法评估：先将回答拆解为原子声明（claims），再逐条核验每条声明是否能在检索到的文档中找到依据。

- 得分 = 核验通过的 claims / 总 claims
- 高分意味着"回答没有编造"
- 低分意味着"回答中包含文档里找不到的内容"

### Answer Relevancy（回答相关性）

将回答和原问题分别向量化（本地 BGE 模型），计算语义相似度。同时用 LLM 从回答反向生成问题，与原始问题比较。

- 高分意味着"回答直接回应了问题"
- 低分意味着"回答跑题了或有大量无关内容"

### Context Precision（上下文精度）

LLM 逐段判断检索到的文档内容是否与问题相关。

- 高分意味着"检索系统找到了正确的文档"
- 低分意味着"检索回来的文档跟问题不沾边"

---

## 二、评估结果

| 指标 | 得分 | 说明 |
|------|------|------|
| Faithfulness | **0.575** | 约 57.5% 的回答内容可在文档中找到原文依据 |
| Answer Relevancy | **0.714** | 回答与问题的相关性较好 |
| Context Precision | **0.487** | 仅 48.7% 的检索结果与问题直接相关 |

### 性能等级

| 指标 | 当前值 | 企业级 | 差距 |
|------|--------|--------|------|
| Faithfulness | 0.575 | ≥0.80 | **-0.225** |
| Answer Relevancy | 0.714 | ≥0.70 | +0.014 ✅ |
| Context Precision | 0.487 | ≥0.80 | **-0.313** |

**综合评级：Demo 级别**。系统可稳定运行、回答结构完整，但检索精度和忠实度不满足生产环境要求。

---

## 三、问题分析

### 3.1 Faithfulness = 0.575：回答存在编造

RAGAS 两步法比人工一眼看去严格得多——它会逐条拆解你的回答，然后逐条去文档里找原文。我们 1500+ 字的回答被拆成 10-15 条声明，其中约 4-6 条在文档中找不到直接依据。

**典型问题**：System Prompt 要求 LLM 按"结论摘要→制度依据→关键提示→引用清单→关联线索"五段结构输出。当检索到的文档只能支撑前两段时，LLM 为了填满结构会"合理推断"后三段的内容——这些推断在 RAGAS 看来就是编造。

### 3.2 Context Precision = 0.487：检索召回不准

近一半的检索结果跟问题不完全相关。这发生在跨主题查询（如"What is an ontology?"——知识库没有哲学本体论文档，召回的是语义相近但不相关的 IBM 术语表）和模糊查询上。

**典型问题**：54 篇 IBM 文档集中在 Decision Optimization 和 Foundation Models 两个领域。一旦用户问到这两个领域之外的问题，BM25+向量做的是"尽量找相似的"而非"告诉你找不到"。

### 3.3 Answer Relevancy = 0.714：刚过线

回答基本能回应问题本身，说明生成链路（DeepSeek + Prompt 模板）在"回答问题"这个基本任务上合格。但提升空间在于——当检索精度低时，LLM 被不相关的上下文带偏，回答中会出现大量问题没问但文档里有的冗余内容。

---

## 四、改进路线

### P0：检索精度——Context Precision 0.487 → 0.70

| 措施 | 预期提升 | 难度 |
|------|---------|------|
| Reranker 分数阈值过滤：score < 0.5 的 chunk 不送 LLM | +0.10 | 低 |
| Query 改写 Prompt 优化：增加跨主题术语映射表 | +0.08 | 低 |
| 知识库扩展：补充当前覆盖薄弱领域（NLP、数据库、安全）的文档 | +0.05 | 中 |

### P0：忠实度——Faithfulness 0.575 → 0.75

| 措施 | 预期提升 | 难度 |
|------|---------|------|
| 简化 System Prompt 输出结构：去掉"关联线索"等非必要段落，减少 LLM 填充压力 | +0.10 | 低 |
| 检索精度提升（见上）——输入更干净，输出自然更忠实 | +0.05 | — |
| Faithfulness 分档监控：每次部署前跑 RAGAS，低于 0.70 不发布 | — | 低 |

### P1：持续评估

| 措施 | 说明 |
|------|------|
| 每次改 Prompt 或改检索参数后重跑评估 | `python backend/eval_ragas_only.py` |
| 回答有更新时重新生成数据集 | `python backend/gen_answers.py` |

---

## 五、附录

- **评估脚本**: `backend/eval_ragas_only.py`（从缓存 JSON 读回答，只跑评估）
- **回答生成**: `backend/gen_answers.py`（跑一遍 Pipeline，存 JSON 供评估复用）
- **数据集**: `data/eval_dataset.json`（20 条 QA，含 question/answer/contexts/ground_truth）
- **参考**: https://docs.ragas.io/
