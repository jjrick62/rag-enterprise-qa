# RAG 系统能力评估报告 (RAGAS 正统框架)

> **评估日期**: 2026-06-06
> **框架**: RAGAS 0.4.3（两步法 Faithfulness + 多维度指标）
> **LLM Judge**: DeepSeek Chat (temperature=0.0)
> **测试数据集**: watsonxDocsQA / question_answers / test (20 条)

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
| Faithfulness | **0.566** | 0.645 | -0.079 | RAGAS两步法更严格 |
| Answer Relevancy | **0.672** | 0.680 | -0.008 | |
| Context Precision | **0.560** | 0.675 | -0.115 | |

### 综合评级

```
综合评级 (RAGAS): demo 级别
Faithfulness=0.566 | AnswerRelevancy=0.672 | ContextPrecision=0.560
```

### 企业标准对照

| 指标 | 当前值 | 企业及格线 | 差距 |
|------|--------|-----------|------|
| Faithfulness | 0.566 | ≥0.80 | 0.234 |
| Answer Relevancy | 0.672 | ≥0.70 | 0.028 |
| Context Precision | 0.560 | ≥0.80 | 0.240 |

---

## 三、跟自研方案对比

| 维度 | 自研 | RAGAS | 结论 |
|------|------|-------|------|
| Faithfulness | 一步整体打分 0.645 | 两步法 0.566 | RAGAS 分得更细，自研可能偏乐观 |
| Context Precision | 一步整体 0.675 | 逐句评分 0.560 | |
| Answer Relevancy | LLM 打分 0.680 | embedding+LLM 0.672 | |

---

## 四、改进路线

1. P0: Reranker 分数阈值过滤（低于阈值不送 LLM）
2. P0: System Prompt 简化（去结构化压力，减少编造空间）
3. P1: 知识库扩展 + Query 改写术语映射增强

---

> 评估脚本: `backend/eval_ragas_only.py` | 生成回答: `backend/gen_answers.py`
