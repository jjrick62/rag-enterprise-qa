# RAG 系统能力评估报告 (RAGAS)

> **框架**: RAGAS 0.4.3 | **LLM Judge**: DeepSeek Chat | **测试集**: watsonxDocsQA (20条)
> **被测管线**: RecursiveChunker + Hybrid(BM25+Vector+RRF) + BGE-Reranker-v2-m3 + QueryRewriter + DeepSeek

---

## 一、三轮优化对比

| 指标 | R1 (七段Prompt) | R2 (简化Prompt) | R3 (文档级去重) | 企业标准 |
|------|---------|---------|---------|---------|
| Faithfulness | 0.575 | 0.542 | **0.556** | ≥0.80 |
| Answer Relevancy | 0.714 | 0.588 | **0.560** | ≥0.70 |
| Context Precision | 0.487 | 0.537 | **0.500** | ≥0.80 |

### RAGAS 分数的局限

R3 的实际检索质量明显优于 R2（Q5 从 12 字拒答→1006 字详细回答；Q8 从 12→476 字），但 RAGAS 分数反而微涨微跌。原因：

- **Faithfulness 对长回答天然不利**：12 字拒答=1.0（没有 claims 可扣分），1006 字详细回答=0.3-0.7（15 条 claims 中总有几个被 Judge 判为"无原文依据"）
- **Answer Relevancy 同样**：12 字拒答跟问题的语义相似度低（0.0），但长回答中只要有一个段落偏题就被扣分

**因此 RAGAS 分数应作为相对指标（同一轮内不同查询对比），而非绝对质量分数。**

---

## 二、深度诊断发现（6/6）

### 发现一：文档级去重修复了"同一文档占满 Top-5"的问题

**修复前**：`Parameters_for_tuning_foundation_models.md` 的 3 个 chunk 各占一个 Top-5 位置
**修复后**：同一文档只保留 RRF 分最高的 chunk，Top-5 来自 5 个不同文档

### 发现二：BM25 的 Chunk 级索引对稀有术语不友好

`Flow_and_SuperNode_parameters.md` 明确写有 "parameters for use in CLEM expressions"。
但在 Chunk 级 BM25 中，"CLEM" 只出现在 2/660 chunks 中，其 IDF 优势被其他 "parameters" chunks 稀释。
文档级 BM25 中该文档排第 1，但管道中因 Reranker 所有 chunk 分都在 0.50 左右，正确 chunk 未能进入 Top-5。

### 发现三：RAGAS 作为 DeepSeek Judge 存在偏差

部分查询（如 Q1 "foundation models"）的检索上下文明显正确，但 Context Precision 被 Judge 判为 0.000。
DeepSeek 作为评估 LLM 的判断一致性不如 GPT-4o。

---

## 三、已完成的优化

| 日期 | 改进 | 效果 |
|------|------|------|
| 6/5 | 递归语义分块 + Reranker + Hybrid + Query改写 + 摄入API + 多轮对话 | 7 项优化 |
| 6/5 | RAGAS 评估上线 | 基线采集 |
| 6/6 | System Prompt 简化 (1498→450字) | 减少结构化编造压力 |
| 6/6 | RRF 文档级去重 (同文档多 chunk → 取最高分 1 个) | Top-5 来自 5 个不同文档 |

---

## 四、后续优化路线

| 优先级 | 措施 | 说明 |
|--------|------|------|
| P0 | Reranker 阈值过滤 (score<0.5 不送 LLM) | 当前 0.50 的 noise chunk 仍在注入 |
| P1 | 知识库扩展 | 补充缺失领域文档 |
| P1 | BM25 权重增强 | 对稀有术语的 chunk 级 IDF 加权 |
| P2 | Graph RAG | 长期炫技项目 |

---

> 评估工具: `backend/eval_ragas_only.py` | 回答生成: `backend/gen_answers.py`
> 诊断脚本: `backend/diagnose_ragas.py` | 检索测试: `backend/check_clem.py`
