# RAG 企业知识库智能问答 — 项目概览

## 状态：优化第二阶段（BM25 bug 已修复，Chunk 信噪比优化待做）

## 技术栈
- 后端: Python FastAPI + OOP（6 个 ABC 抽象基类）
- Embedding: BAAI/bge-small-zh-v1.5（本地 RTX 4060）
- Reranker: BAAI/bge-reranker-v2-m3（本地）
- 向量库: ChromaDB（持久化）
- 关键词: BM25（rank-bm25 库）
- 生成: DeepSeek Chat API
- 评估: RAGAS 0.4.3 正统框架

## 已完成优化（2026-06-05 ~ 06-06）

1. 递归语义分块（RecursiveChunker，标题树递归+句子精切）
2. Reranker 二阶段重排（Cross-encoder，sigmoid 归一化）
3. Hybrid Search（BM25 + 向量 + RRF 融合）
4. Query 改写（DeepSeek，中文→英文术语）
5. 摄入 API（MD5 去重、增量更新、DELETE、全量重摄入）
6. 多轮对话（会话管理、历史注入）
7. System Prompt 简化（1498→450字）
8. RAGAS 评估上线（Faithfulness=0.566 基线）

## Bug 修复
- **BM25 从未构建**（2026-06-06）：HybridRetriever.__init__() 新增 _rebuild_from_chromadb()

## 当前瓶颈
- Chunk 信噪比太低：含关键信息的句子被埋在大段无关内容里
- RAGAS Faithfulness=0.566，距企业标准 0.80 差 0.234
- Answer Relevancy=0.672，差 0.028 达标

## 已砍掉的伪需求
- 知识库扩展：答案已在 54 篇文档中，不需要更多文档
- 文档级去重：长文档多 chunk 场景是负优化

## 下一优先
Chunk 信噪比优化——关键术语独立成 chunk
