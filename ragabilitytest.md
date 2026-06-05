# RAG 系统能力评估报告

> **评估日期**: 2026-06-05
> **评估框架**: RAGAS 等效实现（LLM-as-Judge: DeepSeek Chat, temperature=0.0）
> **测试数据集**: watsonxDocsQA / question_answers / test（20 条样本）
> **参考标准**: RAGAS + Microsoft ISE 层级评估 + HERB Benchmark (Salesforce)
> **被测管线**: RecursiveChunker + Hybrid(BM25+Vector+RRF) + Reranker(bge-v2-m3) + QueryRewriter + DeepSeek

---

## 一、评估方法论

参考三大企业级 RAG 评估框架，设计了四维评估方案：

### 为什么自己实现而不直接用 RAGAS？

RAGAS 0.2.x 强依赖 `langchain-community.chat_models.vertexai`，该模块在新版 langchain 中已被移除，Windows 环境下安装必炸。本方案用相同的 Prompt 方法论 + DeepSeek API 实现等效评估：三条独立 Prompt，temperature=0.0 确保评分一致性，无额外依赖。

### 四维评估体系

| 维度 | 指标 | 评估方法 | 参考来源 |
|------|------|---------|-------------|
| **检索质量** | Context Precision | LLM 判断检索文档与问题的相关性（1.0=全相关） | RAGAS `context_precision` |
| **生成忠实度** | Faithfulness | LLM 逐句核验回答是否可追溯到参考文档（1.0=无编造） | RAGAS `faithfulness` |
| **回答相关性** | Answer Relevancy | LLM 判断回答是否直接、完整回应问题（1.0=完美） | RAGAS `answer_relevancy` |
| **系统鲁棒性** | 有效响应率 / 拒答率 | 统计有效回答占比 + 拒答行为分析 | HERB Benchmark |

**LLM-as-Judge Prompt 设计**:

- Faithfulness: 给 LLM 看参考上下文 + 回答 → 逐句核验每句话是否能在上下文中找到依据 → 输出 0.0-1.0
- Answer Relevancy: 给 LLM 看问题 + 回答 → 判断是否直接、完整回应 → 输出 0.0-1.0
- Context Precision: 给 LLM 看问题 + 检索到的文档 → 判断每篇文档的相关性 → 输出 0.0-1.0

---

## 二、评估结果

### 2.1 总览

```
综合评级: demo 级别 → 目标: 生产就绪

指标                 当前值      企业要求      差距
─────────────────────────────────────────────────────
Faithfulness         0.645       ≥ 0.80       -0.155
Answer Relevancy     0.680       ≥ 0.70       -0.020
Context Precision    0.675       ≥ 0.80       -0.125
有效响应率            100.0%      100%         ✅
拒答率               25.0%       适当          🟡
平均回答长度          1686 字     —            ✅
平均来源数            5.0 条      —            ✅
```

### 2.2 检索质量 (Retrieval)

| 指标 | 分数 | 企业及格线 | 状态 |
|------|------|-----------|------|
| **Context Precision** | **0.675** | ≥ 0.80 | 🔴 未达标 |
| 平均来源数 | 5.0 条/问 | — | ✅ |

**分档**: 优秀(>0.80): 10条 | 良好(0.60-0.80): 3条 | 较差(<0.60): 7条

**根因**: 35% 的查询检索精度偏低，主要出现在跨主题查询（如 "What is an ontology?"），
知识库缺少直接文档，BM25+向量召回的是语义接近但不精确的内容。

### 2.3 生成质量 (Generation)

| 指标 | 分数 | 企业及格线 | 状态 |
|------|------|-----------|------|
| **Faithfulness** | **0.645** | ≥ 0.80 | 🔴 未达标 |
| **Answer Relevancy** | **0.680** | ≥ 0.70 | 🟡 接近 |
| 平均回答长度 | 1686 字 | — | ✅ |

**分档**: 优秀(>0.80): 8条 | 良好(0.60-0.80): 4条 | 较差(<0.60): 8条

**根因**: 40% 样本 Faithfulness < 0.60。DeepSeek 在结构化回答模板
（结论摘要→制度依据→关键提示→引用清单）的压力下会"填充"无依据的框架内容。

### 2.4 系统鲁棒性 (Robustness)

| 指标 | 分数 | 说明 |
|------|------|------|
| **有效响应率** | **100%** | 无崩溃/空返回 |
| 拒答率 | 25.0% | 5/20 条被识别为知识库外 |

**根因**: 拒答率偏高的部分原因是检索精度不够，导致系统误判"没有相关内容"。

---

## 三、20 条逐条明细

| # | 问题 | Faith. | Rel. | Prec. | 长度 | 源 |
|---|------|--------|------|-------|------|-----|
| 1 | What foundation models are available in watsonx.ai? | 0.30 | 0.70 | 1.00 | 2107 | 5 |
| 2 | What is greedy decoding? | 0.30 | 1.00 | 1.00 | 2636 | 5 |
| 3 | What tuning parameters for IBM foundation models? | 0.30 | 0.30 | 0.70 | 1350 | 5 |
| 4 | What are tokens and tokenization? | 0.90 | 0.90 | 1.00 | 2065 | 5 |
| 5 | What is "random seed" in prompt tuning? | 0.30 | 0.00 | 0.30 | 916 | 5 |
| 6 | How to build reusable prompts? | 0.90 | 0.90 | 1.00 | 2481 | 5 |
| 7 | What are the functionalities of Prompt Lab? | 1.00 | 1.00 | 0.90 | 3227 | 5 |
| 8 | How to avoid repetitive text in prompt tuning? | 0.30 | 0.00 | 0.20 | 1355 | 5 |
| 9 | What happens to unsaved prompt text? | 0.90 | 0.70 | 0.90 | 992 | 5 |
| 10 | Why deploy a prompt template? | 0.30 | 0.90 | 1.00 | 1721 | 5 |
| 11 | What is trust calibration? | 0.70 | 1.00 | 0.30 | 1272 | 5 |
| 12 | What are parameters in CLEM? | 0.30 | 0.00 | 0.20 | 1720 | 5 |
| 13 | What is a data warehouse? | 0.70 | 1.00 | 0.70 | 1084 | 5 |
| 14 | What is retrieval-augmented generation pattern? | 0.70 | 1.00 | 0.30 | 1843 | 5 |
| 15 | Workflow for Federated Learning experiment? | 1.00 | 0.60 | 0.70 | 1577 | 5 |
| 16 | Benefits of IBM Federated Learning? | 0.30 | 0.70 | 1.00 | 1744 | 5 |
| 17 | How to delete deployment using Python client? | 0.70 | 1.00 | 1.00 | 1554 | 5 |
| 18 | What is an ontology? | 1.00 | 0.00 | 0.00 | 412 | 5 |
| 19 | Key functions of geospatial library? | 1.00 | 0.90 | 1.00 | 2696 | 5 |
| 20 | What is a map chart? | 1.00 | 1.00 | 0.30 | 963 | 5 |

---

## 四、改进路线

| 优先级 | 改进项 | 目标 | 预期提升 |
|--------|--------|------|---------|
| **P0** | Reranker 分数阈值过滤 | Faithfulness | +0.10 |
| **P0** | System Prompt 简化去结构化压力 | Faithfulness | +0.05 |
| **P1** | Query 改写领域术语映射增强 | Context Precision | +0.10 |
| **P1** | 拒答逻辑优化 | 精准拒答 | — |
| **P2** | 知识库扩展 | 覆盖缺失领域 | +0.05 |

**预期**: P0+P1 完成后 Faithfulness 可达 0.75-0.80。

---

## 五、方法论参考

| 来源 | 链接 | 借鉴 |
|------|------|------|
| RAGAS | https://docs.ragas.io/ | Faithfulness / Context Precision / Answer Relevancy 定义 |
| Microsoft ISE | https://devblogs.microsoft.com/ise/ | 检索→生成层级评估模式 |
| HERB Benchmark | https://aclanthology.org/2025.emnlp-industry.34/ | 多维度量化 + 知识库外问题处理 |
| ViDoRe V3 | https://huggingface.co/blog/QuentinJG/introducing-vidore-v3 | 企业级检索评估标准 |
| Open RAG Eval | https://venturebeat.com/ai/the-rag-reality-check/ | 可复现评估方法论 |

---

> **结论**: 当前系统在 20 条标准 QA 上 Faithfulness=0.645，距企业生产标准 (≥0.80) 差 0.155。
> 最大的两个问题——(1) 35% 查询检索精度不足 (2) 结构化 Prompt 导致 LLM 填充无依据内容。
> P0 改进项（Reranker 阈值过滤 + Prompt 简化）预计可将 Faithfulness 提升至 0.75-0.80。
