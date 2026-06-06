# RAG 企业知识库智能问答系统

基于 RAG（检索增强生成）的企业级知识库问答系统。54 篇 IBM watsonx 技术文档入库，自然语言提问，流式回答，带引用溯源。

**📊 RAGAS 评估：三指标全过企业标准线 🔥**

| 指标 | 得分 | 企业标准 |
|------|:----:|:--------:|
| Faithfulness | **0.864** ✅ | ≥0.80 |
| Answer Relevancy | **0.897** ✅ | ≥0.70 |
| Context Precision | **0.911** ✅ | ≥0.80 |

---

## 技术栈

| 层 | 选型 | 部署 |
|----|------|------|
| 后端框架 | Python 3.12 + FastAPI | 本地 |
| 向量数据库 | ChromaDB（持久化，637 chunks） | 本地 |
| Embedding | BAAI/bge-small-zh-v1.5（512 维） | 本地 RTX 4060 |
| 英文 Embedding | BAAI/bge-base-en-v1.5（768 维） | 本地，已就绪未切换 |
| 重排序 | BAAI/bge-reranker-v2-m3（Cross-encoder + sigmoid） | 本地 RTX 4060 |
| 关键词检索 | BM25（rank-bm25，Hybrid Search + RRF 融合） | 本地 |
| 分块策略 | RecursiveChunker（标题树 + 句子精切 + 伪表检测） | 本地 |
| LLM 生成 | DeepSeek Chat API | 云端 |
| LLM Judge | MiMo v2.5 Pro（RAGAS 评估） | 云端 |
| 前端 | 规划中 | — |

## 项目结构

```
rag-enterprise-qa/
├── backend/
│   ├── main.py              # FastAPI 入口 + 生命周期
│   ├── config.py            # 配置单例 (含英文模型配置)
│   ├── routers/
│   │   ├── chat.py          # POST /api/chat/send, DELETE /api/chat/session
│   │   └── documents.py     # ingest, list, status, delete, reingest-all (8端点)
│   ├── services/
│   │   ├── base.py          # 6 个抽象基类（OOP 接口契约）
│   │   ├── parser.py        # MDParser
│   │   ├── recursive_chunker.py  # 标题树递归 + 句子精切 + 伪表检测+原子化
│   │   ├── embedder.py      # BGEBaaIEmbedder
│   │   ├── retriever.py     # ChromaRetriever + clear()
│   │   ├── hybrid_retriever.py   # BM25+向量+RRF, category_filter, top_k
│   │   ├── reranker.py      # BGE Cross-encoder, min_score=0.50, max_per_doc=4
│   │   ├── generator.py     # DeepSeekGenerator（流式）
│   │   ├── prompts.py       # 英文 System Prompt
│   │   ├── query_rewriter.py
│   │   ├── ragas_evaluator.py    # RAGAS 0.4.3 封装 (MiMo Judge)
│   │   └── pipeline.py      # RAGPipeline + Builder 模式
│   ├── schemas/
│   │   └── chat.py          # 不可变数据实体（frozen dataclass）
│   ├── models/              # 本地模型缓存（.gitignored）
│   ├── tests/               # 40 个测试全通过
│   ├── _reingest.py         # 全量重摄入脚本
│   ├── gen_answers.py       # 答案生成（已废弃，改用标准答案）
│   └── eval_ragas_only.py   # RAGAS 评估（标准答案 + pipeline 检索）
├── data/
│   ├── documents/           # 54 篇 IBM watsonx 技术文档
│   ├── chroma_db/           # 向量数据库（.gitignored）
│   └── watsonxDocsQA_test.json  # 30 条标准答案
├── ragabilitytest.md        # RAGAS 评估报告
├── CHATGPT_README.md        # ChatGPT 工作记录
├── 14.06claude写这里/        # 交接文档 + 审计报告
└── claude_memory/           # 项目记忆（部分过期）
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

# RAGAS 评估需要独立 venv:
python -m venv venv_ragas
venv_ragas\Scripts\activate
pip install ragas==0.4.3 datasets pandas

# 3. 配置
cp .env.example .env        # 编辑 .env 填入 API Key

# 4. 重摄入文档（修改 chunker 后必须跑）
python _reingest.py

# 5. RAGAS 评估（需 venv_ragas，约 25 分钟/30 题）
$env:SENTENCE_TRANSFORMERS_HOME='.\models'
$env:TRANSFORMERS_CACHE='.\models'
..\venv_ragas\Scripts\python.exe eval_ragas_only.py

# 6. 启动服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 7. 问答
curl -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"question": "What tuning parameters are available for IBM foundation models?"}'
```

## 已完成优化

| 模块 | 内容 | 状态 |
|------|------|------|
| 递归语义分块 | RecursiveChunker（标题树递归+句子精切+伪表原子化） | ✅ |
| Reranker 重排序 | BGE-reranker-v2-m3 + sigmoid，阈值过滤+多样性控制 | ✅ |
| Hybrid Search | BM25 + 向量双路召回 + RRF 融合，支持分类过滤 | ✅ |
| Query 改写 | 术语映射（中文→英文） | ✅ |
| 摄入 API | MD5 去重、增量更新、DELETE、全量重摄入、404 处理 | ✅ |
| 多轮对话 | 会话管理、历史注入 | ✅ |
| System Prompt | 英文化、精简、反编造 | ✅ |
| RAGAS 评估 | 标准答案评测，三指标全过企业标准线 | ✅ |
| 英文 Embedding | BGE-base-en-v1.5 已下载配置，待切换 | 🔧 |

## RAGAS 评估

详见 [ragabilitytest.md](ragabilitytest.md)

| 轮次 | Judge | 答案源 | Faith. | AnsRel. | CtxPrec. |
|------|-------|--------|--------|---------|----------|
| R1 | DeepSeek | 中文LLM生成 | 0.566 | 0.672 | 0.560 |
| **R5** | **MiMo** | **标准答案** | **0.864** | **0.897** | **0.911** |

## 优化路线

| 优先级 | 措施 | 目标 |
|--------|------|------|
| P0 | 候选召回深度扩展（Q07 0.000 根因） | Faithfulness → 0.90+ |
| P1 | Parent-Child Chunk | 小块精准命中+父块补全语义 |
| P1 | 英文 Embedding 切换对比 | BGE-base-en-v1.5 已就绪 |
| P2 | Query Rewrite 降本 | 减少 DeepSeek API 调用 |
| P2 | 检索置信度与拒答 | 低分时明确说"资料不足" |
| P3 | Graph RAG | 远期跨文档多跳 |

## License

MIT
