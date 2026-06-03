# RAG 企业制度智能问答 — 设计规格书

**日期**: 2026-06-03  
**状态**: 设计完成，待进入实现计划

---

## 1. 项目概述

基于 RAG（检索增强生成）的企业管理制度智能问答系统。多份企业文档入库后，用户用自然语言提问，系统从文档中检索相关内容，生成带引用溯源的答案。

**核心价值**: 多文档管理 + 分类检索 + 引用溯源，三个点打出去面试能聊 20 分钟。

---

## 2. 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 后端框架 | Python + FastAPI | RAG 生态最全，LangChain/Sentence-Transformers 原生支持 |
| 前端框架 | React + TypeScript + Vite | 轻量，够用，SSE 处理简单 |
| 向量数据库 | ChromaDB | 嵌入式部署，零依赖，本地持久化 |
| Embedding | BAAI/bge-small-zh-v1.5 | 中文 SOTA，512 维，轻量，RTX 4060 跑无压力 |
| LLM | DeepSeek API（deepseek-chat） | OpenAI 兼容 SDK，便宜，中文好 |
| 文档解析 | PyPDF2 + python-docx + 内置 markdown | 覆盖三种主流企业文档格式 |
| 包管理 | pip（requirements.txt）/ npm（package.json） | 标准方案 |

---

## 3. 系统架构

### 3.1 物理架构

```
用户浏览器 (React) 
    ↕ SSE / REST
FastAPI 后端 (Python)
    ↕ 
ChromaDB 本地持久化 + DeepSeek API 云端
```

### 3.2 OOP 类继承体系

```
BaseParser(ABC)          → MDParser, PDFParser, DOCXParser
BaseChunker(ABC)         → FixedChunker, HeadingChunker, SemanticChunker
BaseEmbedder(ABC)        → BGEBaaIEmbedder
BaseRetriever(ABC)       → ChromaRetriever
BaseGenerator(ABC)       → DeepSeekGenerator
```

RAGPipeline（编排器，Builder 模式组合上述组件）

### 3.3 文件清单

```
rag-enterprise-qa/
├── backend/
│   ├── main.py              ✅
│   ├── config.py            ✅
│   ├── routers/
│   │   ├── chat.py          ✅
│   │   └── documents.py     🔜
│   ├── services/
│   │   ├── base.py          ✅  五个抽象基类
│   │   ├── parser.py        ✅  BaseParser + MDParser
│   │   │                    🔜 PDFParser, DOCXParser
│   │   ├── chunker.py       ✅  BaseChunker + FixedChunker
│   │   ├── embedder.py      ✅  BaseEmbedder + BGEBaaIEmbedder
│   │   ├── retriever.py     ✅  BaseRetriever + ChromaRetriever
│   │   ├── generator.py     ✅  BaseGenerator + DeepSeekGenerator
│   │   └── pipeline.py      ✅  RAGPipeline + Builder
│   ├── schemas/
│   │   ├── chat.py          ✅
│   │   └── document.py      🔜
│   └── requirements.txt     ✅
├── frontend/
│   ├── src/
│   │   ├── core/
│   │   │   ├── EventEmitter.ts   ✅
│   │   │   └── ChatClient.ts     ✅
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx     ✅
│   │   │   └── SourcePopover.tsx ✅
│   │   ├── types/index.ts        ✅
│   │   ├── App.tsx               ✅
│   │   └── main.tsx              ✅
│   ├── index.html                ✅
│   ├── package.json              ✅
│   ├── tsconfig.json             ✅
│   └── vite.config.ts            ✅
├── data/
│   └── documents/                ✅
├── docs/superpowers/specs/       ✅
├── claude_memory/                ✅
└── .gitignore                    ✅
```

✅ = 最小可用（MVP）  
🔜 = 后期补充

---

## 4. 数据流

### 4.1 文档摄入

```
.pdf/.docx/.md → Parser → 纯文本 → Chunker → List[Chunk]
→ Embedder → np.ndarray → ChromaRetriever.add_embeddings()
```

### 4.2 实时问答

```
用户提问 → ChatClient.send() → POST /chat/send (SSE)
→ pipeline.query()
  → embedder.embed(question)
  → retriever.search(embedding, top_k=5, category_filter?)
  → generator.generate(question, contexts)
    → async for token: yield SSE event "token"
    → yield SSE event "sources"
    → yield SSE event "done"
→ ChatClient 层层 emit → ChatPanel 增量渲染 → SourcePopover 填充引用
```

### 4.3 ChatClient 状态机

```
IDLE → CONNECTING → STREAMING → IDLE
                   ↘ ERROR → IDLE
```

---

## 5. API 设计

| 方法 | 路径 | 说明 | MVP |
|------|------|------|-----|
| POST | `/api/chat/send` | 发送消息，SSE 流式返回 | ✅ |
| POST | `/api/documents/upload` | 上传文档 | 🔜 |
| GET | `/api/documents` | 文档列表 | 🔜 |
| DELETE | `/api/documents/{id}` | 删除文档 | 🔜 |

### SSE 事件格式

```
event: token
data: 年

event: token
data: 假

event: sources
data: {"sources":[{"documentName":"员工手册.md","heading":"第三章 休假制度","excerpt":"员工入职满一年后可享受带薪年假...","score":0.8742}]}

event: done
data:
```

---

## 6. System Prompt（生产级七维度）

1. **信息源铁律** — 仅用参考文档，禁止预训练知识，引用三要素齐全
2. **答案质量门槛** — 完整性/准确性/适用性/时效性四重检查
3. **回答结构规范** — 结论摘要 → 制度依据 → 关键提示 → 引用清单 → 关联线索
4. **冲突处理协议** — 显式暴露冲突 → 列出出处 → 优先级判断 → 说明理由
5. **边界与拒答** — 四种场景的标准话术
6. **语气与风格** — 专业平实，不越界给行为建议
7. **输出前自检** — 四句内心默念

完整 Prompt 见 `claude_memory/data-flow-spec.md` 及代码中的常量定义。

---

## 7. 前端设计

### 7.1 页面布局（最小可用）

```
┌────────────────────────────────────┐
│  📁 [文档]          RAG 企业问答   │ ← 顶部栏
├────────────────────────────────────┤
│                                    │
│  用户：年假怎么申请？               │
│                                    │
│  🤖 根据《员工手册》第三章...       │
│     年假申请需满足以下条件...       │
│                                    │
│     📎 员工手册 §3.2  [hover 展开]  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 输入问题...              [→] │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
     文档抽屉（点击顶部 📁 滑出）
```

### 7.2 技术决策

- 无路由，单页应用
- 无状态管理库（React useState + ChatClient EventEmitter 足够）
- 无 CSS 框架（手写最小 CSS，或 Tailwind CDN）
- SSE 用 `fetch` + `ReadableStream`，不引入额外库

---

## 8. 核心 OOP 原则落地

| 原则 | 落地方式 |
|------|----------|
| 开闭原则 | 加新解析格式 → 继承 BaseParser |
| 里氏替换 | 任何子类可替换基类，行为一致 |
| 依赖倒置 | RAGPipeline 只依赖 ABC，不依赖具体实现 |
| 单一职责 | Parser 只解析，Chunker 只分块，互不越界 |
| 接口隔离 | 基类只定义必需方法 |
| Builder 模式 | RAGPipelineBuilder 逐步注入依赖 |

---

## 9. 测试文档语料

MVP 使用 1 份 Markdown 文档启动：
- `员工手册.md` — 包含考勤、休假、报销、福利、绩效考核等章节

后期补充 4 份：
- `IT安全规范.md`
- `差旅报销制度.md`
- `绩效考核办法.md`
- `入职培训材料.md`

---

## 10. 成功标准

1. 启动后端，摄入 1 份文档，能检索出相关片段
2. 前端输入问题，SSE 流式返回中文回答
3. 回答末尾显示引用来源（文档名 + 段落）
4. hover 引用卡片显示原文摘录
