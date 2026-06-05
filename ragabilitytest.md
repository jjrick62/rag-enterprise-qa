# RAG 系统能力评估报告 (RAGAS)

> **框架**: RAGAS 0.4.3 | **LLM Judge**: DeepSeek Chat | **测试集**: watsonxDocsQA (20条)
> **当前基线**: Faithfulness=0.566 / AnswerRelevancy=0.672 / ContextPrecision=0.560

---

## 一、四轮优化历史

| 轮次 | 改动 | Faith. | AnsRel. | CtxPrec. |
|------|------|--------|---------|----------|
| R1 | 七段 Prompt | 0.575 | 0.714 | 0.487 |
| R2 | 简化 Prompt | 0.542 | 0.588 | 0.537 |
| R3 | 文档级去重(已回滚) | 0.556 | 0.560 | 0.500 |
| R4 | **BM25修复**(关键) | **0.566** | **0.672** | **0.560** |

---

## 二、关键发现

### Bug：BM25 从未被构建

`HybridRetriever.__init__()` 没从 ChromaDB 读取已有数据重建 BM25 索引。每次新建 Pipeline（服务重启、gen_answers、trace 脚本）BM25 都是空的。**向量检索单腿跳了全程。**

修复：新增 `_rebuild_from_chromadb()`，在 `__init__` 时从 ChromaDB 读取 660 个 chunk 重建 BM25。

### 真实瓶颈：Chunk 信噪比

BM25 和向量都能把正确文档排到第 1 名。但 BGE-reranker 对正确 chunk 的 sigmoid 分只有 0.68——因为 chunk 包含 80% 无关内容（Flow/SuperNode）+ 20% 相关信息（CLEM）。信噪比太低。

不是文档缺失。不是 Reranker 坏了。是 Chunk 策略需要优化。

---

## 三、剩余改进项

| 优先级 | 措施 | 说明 |
|--------|------|------|
| P0 | Chunk 信噪比优化 | 关键术语独立成 chunk，不被无关内容稀释 |
| P2 | Graph RAG | 远期炫技 |

---

> 评估工具: `backend/eval_ragas_only.py` | 生成回答: `backend/gen_answers.py`
> 管道诊断: `backend/trace_pipeline.py`
