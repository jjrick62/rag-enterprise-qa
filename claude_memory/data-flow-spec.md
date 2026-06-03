# RAG 系统数据流时序规格

## 一、系统启动——文档摄入（Ingest）

```
main.py:startup()
│
├─► config.py: Config.load()
│   从 .env 加载 DEEPSEEK_API_KEY, EMBEDDING_MODEL, CHROMA_PATH 等
│   返回: Config 单例（不可变 dataclass）
│
├─► pipeline.py: RAGPipeline.builder()
│   │
│   ├─ .with_parser(MDParser())         # 注入 BaseParser 子类
│   ├─ .with_chunker(FixedChunker(      # 注入 BaseChunker 子类
│   │       chunk_size=500,
│   │       overlap=50
│   │   ))
│   ├─ .with_embedder(BGEBaaIEmbedder(  # 注入 BaseEmbedder 子类
│   │       model_name="BAAI/bge-small-zh-v1.5",
│   │       device="cuda"
│   │   ))
│   ├─ .with_retriever(ChromaRetriever( # 注入 BaseRetriever 子类
│   │       persist_path=config.CHROMA_PATH,
│   │       embedder=embedder           # 共享 embedder 实例
│   │   ))
│   └─ .with_generator(DeepSeekGenerator(
│           api_key=config.DEEPSEEK_API_KEY,
│           model="deepseek-chat",
│           system_prompt=PROMPT,       # 之前定义的生产级 System Prompt
│           temperature=0.3
│       ))
│   返回: RAGPipeline（不可变，各组件已注入）
│
├─► pipeline.py: pipeline.ingest("data/documents/员工手册.md", category="员工手册")
│   │
│   ├─► MDParser.parse(file_path) → str
│   │   读取文件，返回原始文本
│   │
│   ├─► FixedChunker.chunk(text) → List[Chunk]
│   │   │
│   │   │  Chunk (frozen dataclass):
│   │   │    content: str           # "第二章 考勤制度\n公司实行..."
│   │   │    metadata: ChunkMetadata
│   │   │    chunk_index: 0
│   │   │
│   │   │  ChunkMetadata (frozen dataclass):
│   │   │    source_doc: "员工手册.md"
│   │   │    category: "员工手册"
│   │   │    page_number: 0
│   │   │    heading: "第二章 考勤制度"
│   │   │    char_start: 0
│   │   │    char_end: 487
│   │   │
│   │   返回: List[Chunk]（假设切出 45 个 chunk）
│   │
│   ├─► BGEBaaIEmbedder.embed(texts: List[str]) → np.ndarray
│   │   texts = [chunk.content for chunk in chunks]
│   │   返回: shape (45, 512) float32
│   │
│   └─► ChromaRetriever.add_embeddings(
│           chunks=List[Chunk],
│           embeddings=np.ndarray
│       )
│       批量写入 ChromaDB，附带 metadata
│       返回: int（写入数量 45）
│
返回: 45（ingested chunk count）
```

---

## 二、实时问答——检索+生成（Query）

触发条件：用户在前端输入框发送消息

```
        ┌──────────────┐
        │   前端 (TS)   │
        │  ChatPanel    │
        │  → ChatClient │
        └──────┬───────┘
               │ POST /api/chat/send
               │ Body: {"question": "年假怎么申请", "category": null}
               │ Accept: text/event-stream
               ▼
        ┌──────────────┐
        │ 后端 (Python) │
        │ router/chat   │
        └──────┬───────┘
               │
               │ ──► pipeline.query("年假怎么申请", category=None)
               │
               │     ┌─────────────────────────────────────────┐
               │     │ RAGPipeline.query()                     │
               │     │                                         │
               │     │ ① embedder.embed(["年假怎么申请"])       │
               │     │    → np.ndarray shape (1, 512)          │
               │     │                                         │
               │     │ ② retriever.search(                     │
               │     │       query_embedding,                  │
               │     │       top_k=5,                          │
               │     │       category_filter=None              │
               │     │    )                                    │
               │     │    → List[RetrievalResult]              │
               │     │    │                                    │
               │     │    │  RetrievalResult (frozen):         │
               │     │    │   chunk: Chunk                     │
               │     │    │   score: 0.8742                    │
               │     │    │                                    │
               │     │    │   sorted by score DESC             │
               │     │    │                                    │
               │     │    ┌─────────────────────────┐          │
               │     │    │ ChromaRetriever.search() │          │
               │     │    │ 内部:                    │          │
               │     │    │  a. 相同 embedder 向量化 │          │
               │     │    │  b. collection.query()   │          │
               │     │    │  c. 构造 RetrievalResult │          │
               │     │    │  d. category_filter →    │          │
               │     │    │     过滤 metadata        │          │
               │     │    └─────────────────────────┘          │
               │     │                                         │
               │     │ ③ generator.generate(                   │
               │     │       question="年假怎么申请",           │
               │     │       contexts=List[RetrievalResult]    │
               │     │    )                                    │
               │     │    → AsyncIterator[GenerateEvent]       │
               │     │    │                                    │
               │     │    │  GenerateEvent 类型:               │
               │     │    │   - token: str                     │
               │     │    │   - sources: List[Source]          │
               │     │    │   - done: None                     │
               │     │    │                                    │
               │     │    ┌─────────────────────────┐          │
               │     │    │ DeepSeekGenerator        │          │
               │     │    │  a. 拼接 System Prompt   │          │
               │     │    │  b. 拼接 contexts →      │          │
               │     │    │     【参考文档】区块      │          │
               │     │    │  c. POST DeepSeek API    │          │
               │     │    │     stream=True           │          │
               │     │    │  d. 逐 delta yield token │          │
               │     │    │  e. 流结束后 yield       │          │
               │     │    │     sources + done       │          │
               │     │    └─────────────────────────┘          │
               │     │                                         │
               │     │ ④ async for event in generator:         │
               │     │     yield SSE event to HTTP response    │
               │     │                                         │
               │     └─────────────────────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ 返回 SSE 流   │
        │ event: token   │
        │ data: "年"     │
        │                │
        │ event: token   │
        │ data: "假"     │
        │ ...            │
        │ event: sources │
        │ data:{"sources":[{...}]}
        │                │
        │ event: done    │
        │ data: null     │
        └──────┬───────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ 前端 ChatClient (EventEmitter 子类)       │
│                                          │
│ POST /api/chat/send                      │
│ body: {question, category?}              │
│ headers: {Accept: "text/event-stream"}   │
│                                          │
│ 读取 ReadableStream:                     │
│                                          │
│ ┌────────────────────────────────────┐   │
│ │ while (true) {                     │   │
│ │   const {done, value} = reader.read()│  │
│ │   if (done) break                  │   │
│ │                                    │   │
│ │   parse SSE line →                 │   │
│ │                                    │   │
│ │   if event === "token":            │   │
│ │     this.emit("message", {         │   │
│ │       type: "token",               │   │
│ │       content: data                │   │
│ │     })                             │   │
│ │     → ChatPanel.appendToken(data)  │   │
│ │       → MessageBubble 增量渲染     │   │
│ │                                    │   │
│ │   if event === "sources":          │   │
│ │     this.emit("message", {         │   │
│ │       type: "sources",             │   │
│ │       sources: JSON.parse(data)    │   │
│ │     })                             │   │
│ │     → ChatPanel.attachSources()    │   │
│ │       → SourcePopover 填充引用     │   │
│ │                                    │   │
│ │   if event === "done":             │   │
│ │     this.emit("message", {         │   │
│ │       type: "done"                 │   │
│ │     })                             │   │
│ │     → ChatPanel.markComplete()     │   │
│ │       → 停止 loading 动画          │   │
│ │     break                          │   │
│ │ }                                  │   │
│ └────────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

---

## 三、类图 —— 完整关系

```
┌──────────────────────────────────────────────────────────────┐
│                         RAGPipeline                          │
│  ──────────────────────────────────────────────────────────  │
│  - _parser: BaseParser                                       │
│  - _chunker: BaseChunker                                     │
│  - _embedder: BaseEmbedder                                   │
│  - _retriever: BaseRetriever                                 │
│  - _generator: BaseGenerator                                 │
│  ──────────────────────────────────────────────────────────  │
│  + async ingest(file_path, category) → int                   │
│  + async query(question, category_filter?) → AsyncIterator   │
└──────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│BaseParser│  │BaseChunker│  │BaseEmbedder│ │BaseRetriever │
│ (ABC)    │  │ (ABC)    │  │ (ABC)     │  │ (ABC)        │
├──────────┤  ├──────────┤  ├──────────┤  ├──────────────┤
│+parse()  │  │+chunk()  │  │+embed()  │  │+search()      │
│ → str    │  │ →List[C] │  │ →ndarray │  │ →List[Result] │
│          │  │          │  │          │  │+add_embeddings│
│          │  │          │  │          │  │+delete()      │
└──────────┘  └──────────┘  └──────────┘  └──────────────┘
     △             △             △              △
     │             │             │              │
┌────┴───┐  ┌─────┴────┐  ┌─────┴──────┐  ┌────┴────────┐
│MDParser│  │FixedChunker│ │BGEBaaIEmb..│ │ChromaRetri..│
│ (done) │  │ (done)     │ │ (done)     │ │ (done)       │
└────────┘  └────────────┘ └────────────┘ └──────────────┘


┌──────────────────┐
│  BaseGenerator   │
│  (ABC)           │
├──────────────────┤
│+async generate() │
│ → AsyncIterator  │
│   [GenerateEvent]│
└──────────────────┘
          △
          │
  ┌───────┴───────┐
  │DeepSeekGene.. │
  │ (done)        │
  │ (stream)      │
  └───────────────┘


        ┌──────────────────────────┐
        │  ChatClient (前端 TS)     │
        │  extends EventEmitter     │  ← 继承，不是组合
        ├──────────────────────────┤
        │  - abortController        │
        │  - reader: ReadableStream │
        ├──────────────────────────┤
        │  + send(question,cat?)    │
        │  + abort()                │
        │                           │
        │  Events (via EventEmitter)│
        │   'message' → {type,      │
        │     content?, sources?}   │
        │   'error'   → Error       │
        │   'done'    → void        │
        └──────────────────────────┘
                  │
                  │ used by
                  ▼
        ┌──────────────────────────┐
        │  ChatPanel (React FC)    │
        │  ──────────────────────  │
        │  state:                  │
        │    messages: Message[]   │
        │    isStreaming: bool     │
        │  ──────────────────────  │
        │  handleSend(text)        │
        │    → chatClient.send()   │
        │  chatClient.on('msg',)   │
        │    → setMessages(...)    │
        └──────────────────────────┘
```

---

## 四、状态机 —— ChatClient 生命周期

```
                    ┌──────────┐
                    │   IDLE   │ ← 初始态 / 回答完成后回归
                    └────┬─────┘
                         │ send(question)
                         ▼
                    ┌──────────┐
                    │CONNECTING│
                    └────┬─────┘
                         │ HTTP 200 + stream ready
                         ▼
              ┌────────────────────┐
              │    STREAMING       │ ◄── 循环接收 SSE event
              │ ┌────────────────┐ │
              │ │ on token:       │ │    触发 'message' {type:'token'}
              │ │   拼接文本      │ │
              │ │ on sources:     │ │    触发 'message' {type:'sources'}
              │ │   存储引用      │ │
              │ │ on done:        │ │    触发 'done'
              │ │   → IDLE       │ │
              │ └────────────────┘ │
              └────────┬───────────┘
                       │ error / abort()
                       ▼
              ┌────────────────────┐
              │      ERROR         │
              │  触发 'error'       │
              │  → IDLE             │
              └────────────────────┘
```

---

## 五、数据实体类定义

```python
# services/entities.py（或 schemas/ 下）

from dataclasses import dataclass, field
from typing import Optional, Literal
import numpy as np

@dataclass(frozen=True)
class ChunkMetadata:
    """不可变——创建后不能改，保证数据溯源可靠"""
    source_doc: str          # "员工手册.md"
    category: str            # "员工手册"
    page_number: int         # 0-based
    heading: str             # 最近的标题
    char_start: int          # 在原文档中的起始字符位置
    char_end: int            # 在原文档中的结束字符位置

@dataclass(frozen=True)
class Chunk:
    content: str
    metadata: ChunkMetadata
    chunk_index: int

@dataclass(frozen=True)
class RetrievalResult:
    chunk: Chunk
    score: float             # cosine similarity, [0, 1]

@dataclass(frozen=True)
class Source:
    """前端渲染引用卡片用的轻量结构"""
    document_name: str
    heading: str
    excerpt: str             # 原文摘录，最多 200 字
    score: float

@dataclass(frozen=True)
class GenerateEvent:
    """生成器产出的三种事件之一"""
    type: Literal["token", "sources", "done"]
    content: Optional[str] = None          # type=token 时
    sources: Optional[list[Source]] = None  # type=sources 时

@dataclass(frozen=True)
class QueryRequest:
    question: str
    category: Optional[str] = None

@dataclass(frozen=True)
class SSEEvent:
    """SSE 协议封装"""
    event: str               # "token" | "sources" | "done" | "error"
    data: str                # JSON string
```

---

## 六、前端 TypeScript 类型定义

```typescript
// types/index.ts

interface Source {
  documentName: string;
  heading: string;
  excerpt: string;
  score: number;
}

type SSEEventType = 'token' | 'sources' | 'done' | 'error';

interface SSEMessage {
  type: SSEEventType;
  content?: string;         // token 事件
  sources?: Source[];       // sources 事件
  error?: string;           // error 事件
}

// EventEmitter 事件映射
interface ChatClientEvents {
  message: (msg: SSEMessage) => void;
  error: (err: Error) => void;
  done: () => void;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;          // 对于 assistant，这是累积的完整文本
  sources?: Source[];
  isStreaming: boolean;
  createdAt: number;
}
```

---

## 七、后端文件 → 类 → 职责映射

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| `config.py` | `Config` | 加载 .env，单例，不可变 |
| `services/base.py` | `BaseParser(ABC)` | 定义 `parse(file_path) → str` |
| | `BaseChunker(ABC)` | 定义 `chunk(text) → List[Chunk]` |
| | `BaseEmbedder(ABC)` | 定义 `embed(texts) → np.ndarray` |
| | `BaseRetriever(ABC)` | 定义 `search(embedding, top_k, filter) → List[RetrievalResult]` |
| | `BaseGenerator(ABC)` | 定义 `async generate(question, contexts) → AsyncIterator[GenerateEvent]` |
| `services/parser.py` | `MDParser(BaseParser)` | 读 .md 文件返回纯文本 |
| `services/chunker.py` | `FixedChunker(BaseChunker)` | 固定窗口 + overlap 切分 |
| `services/embedder.py` | `BGEBaaIEmbedder(BaseEmbedder)` | sentence-transformers 加载 BGE |
| `services/retriever.py` | `ChromaRetriever(BaseRetriever)` | ChromaDB 客户端封装 |
| `services/generator.py` | `DeepSeekGenerator(BaseGenerator)` | OpenAI 兼容 SDK 流式调用 DeepSeek |
| `services/pipeline.py` | `RAGPipeline` | 编排器，组合上述组件 |
| | `RAGPipelineBuilder` | Builder 模式，逐步注入依赖 |
| `routers/chat.py` | (函数式路由) | POST /chat/send → SSE |
| `schemas/chat.py` | 参见第五节 | Pydantic 请求/响应模型 |
| `main.py` | `app: FastAPI` | 生命周期管理，启动时构建 pipeline |
