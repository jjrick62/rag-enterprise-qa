# RAG 企业知识库智能问答系统

基于 RAG（检索增强生成）的企业级知识库问答系统。54 篇 IBM watsonx 技术文档入库，自然语言提问，流式回答，带引用溯源。

**📊 QA 基准：watsonxDocsQA 30/30 全通过 ✅**

---

## 技术栈

| 层 | 选型 | 部署 |
|----|------|------|
| 后端框架 | Python 3.12 + FastAPI | 本地 |
| 向量数据库 | ChromaDB（持久化） | 本地 |
| Embedding | BAAI/bge-small-zh-v1.5（512 维） | 本地 RTX 4060 |
| 重排序（规划中） | BAAI/bge-reranker-v2-m3 | 本地 RTX 4060 |
| 关键词检索（规划中） | BM25（rank-bm25） | 本地 |
| LLM 生成 | DeepSeek Chat API | 云端 |
| 前端（规划中） | React 18 + TypeScript + Vite | 浏览器 |

## 项目结构

```
rag-enterprise-qa/
├── backend/
│   ├── main.py              # FastAPI 入口 + 生命周期
│   ├── config.py            # 配置单例
│   ├── routers/
│   │   ├── chat.py          # POST /api/chat/send（SSE 流式）
│   │   └── documents.py     # POST /api/documents/ingest, GET /api/documents/list
│   ├── services/
│   │   ├── base.py          # 5 个抽象基类（OOP 接口契约）
│   │   ├── parser.py        # MDParser
│   │   ├── chunker.py       # FixedChunker（递归分块规划中）
│   │   ├── embedder.py      # BGEBaaIEmbedder
│   │   ├── retriever.py     # ChromaRetriever
│   │   ├── generator.py     # DeepSeekGenerator（流式）
│   │   ├── prompts.py       # 七维度 System Prompt
│   │   └── pipeline.py      # RAGPipeline + Builder 模式
│   ├── schemas/
│   │   └── chat.py          # 6 个不可变数据实体（frozen dataclass）
│   ├── models/              # 本地模型缓存（.gitignored）
│   └── tests/               # 11 个单元测试
├── data/
│   ├── documents/           # 54 篇 IBM 技术文档
│   └── chroma_db/           # 向量数据库（.gitignored）
├── docs/                    # 设计文档 + 计划 + 日程
├── frontend/                # React 前端（骨架已搭，待开发）
└── claude_memory/           # 项目记忆
```

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/jjrick62/rag-enterprise-qa.git
cd rag-enterprise-qa/backend

# 2. 环境
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 3. 配置
cp .env.example .env        # 编辑 .env 填入 DeepSeek API Key

# 4. 启动
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 5. 摄入文档
curl -X POST http://localhost:8000/api/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "../data/documents/xxx.md", "category": "IBM_Docs"}'

# 6. 问答
curl -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I deploy a Decision Optimization model?"}'
```

## 已完成优化

| 模块 | 内容 | 状态 |
|------|------|------|
| 后端 MVP | FastAPI + ChromaDB + BGE + DeepSeek | ✅ |
| 递归语义分块 | RecursiveChunker（标题树递归+句子精切） | ✅ |
| Reranker 重排序 | BGE-reranker-v2-m3（Cross-encoder 精排） | ✅ |
| Hybrid Search | BM25 + 向量双路召回 + RRF 融合 | ✅ |
| Query 改写 | DeepSeek 改写（中文→英文术语，54篇索引辅助） | ✅ |
| 摄入 API | MD5 去重、增量更新、DELETE、全量重摄入 | ✅ |
| 多轮对话 | 会话管理、历史注入生成、检索不受影响 | ✅ |
| System Prompt 简化 | 1498字→450字，去除强制结构，减少编造 | ✅ |

## RAGAS 企业级评估

| 指标 | 当前值 | 企业标准 | 差距 |
|------|--------|---------|------|
| Faithfulness | **0.566** | ≥0.80 | -0.234 |
| Answer Relevancy | **0.672** | ≥0.70 | -0.028 |
| Context Precision | **0.560** | ≥0.80 | -0.240 |

**根因**: Chunk 信噪比太低。含关键信息的句子被埋在大段无关内容里，检索到的 chunk 只有 20% 是真正相关的内容。不是文档缺失——答案都在库里，但被切碎稀释了。

## 优化路线

| 优先级 | 措施 | 目标 |
|--------|------|------|
| **P0** | Chunk 信噪比优化（关键术语独立成 chunk，不被稀释） | 全指标提升 |
| **P2** | Graph RAG 知识图谱 | 远期炫技 |

## 文档索引

| 文档 | 说明 |
|------|------|
| [RAGAS评估报告](ragabilitytest.md) | 企业级评估结果 + 问题诊断 |
| [设计规格书](docs/superpowers/specs/2026-06-03-rag-enterprise-qa-design.md) | MVP 架构设计 |
| [数据流时序](claude_memory/data-flow-spec.md) | OOP 实现基准 |
| [RAG优化QA记录](RAG优化方案QA文档.md) | 完整决策记录 |
| [个人贡献](个人贡献——RAG优化方案QA问答记录.md) | 本人回答原文 |
| [API 文档](docs/API文档.md) | 9 个端点 |

## License

MIT
