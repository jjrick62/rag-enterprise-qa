# 项目概览

> 更新：2026-06-06。旧 `claude_memory` 文件可能是历史设计；当前状态优先参考根 README 和 `14.06claude写这里/README.md`。

## 状态

端到端 RAGAS 正式基线：

```text
Faithfulness       0.918
Answer Relevancy   0.826
Context Precision  0.844
```

测试：`48 passed`。

## 架构

- FastAPI + SSE
- ChromaDB
- BGE small zh Embedding
- BM25 + Vector + RRF
- BGE reranker v2 m3
- RecursiveChunker + IBM 伪表原子化
- DeepSeek 生成
- MiMo RAGAS Judge

## 当前默认

```text
min_score=0.50
max_chunks_per_document=4
adaptive_cutoff_ratio=0.75
adaptive_keep_min=3
```

## 关键事实

- RAGAS 使用生成时完整上下文，不使用前端 200 字摘要。
- 标准答案实验不代表端到端系统成绩。
- API Key 只能放在 `backend/.env`。
- 当前瓶颈是候选召回深度，重点 Q08。

## 下一步

候选池 20/30/40/50 离线实验，记录 Recall@5、MRR、答案覆盖率和耗时。
