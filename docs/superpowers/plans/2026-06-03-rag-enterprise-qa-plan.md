# RAG 企业制度智能问答 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可运行的 RAG 企业制度问答 MVP——后端 Python/FastAPI + 本地 BGE Embedding + DeepSeek 流式生成，前端 React/TypeScript + SSE 实时渲染。

**Architecture:** 后端五层抽象基类 (Parser/Chunker/Embedder/Retriever/Generator) → RAGPipeline Builder 模式组装 → FastAPI SSE 路由；前端 EventEmitter 基类 → ChatClient 继承 → React ChatPanel 消费事件。

**Tech Stack:** Python 3.11+, FastAPI, ChromaDB, sentence-transformers, openai SDK; React 18, TypeScript 5, Vite 5

---

### Task 1: 后端项目骨架 + 配置 + 数据实体

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/config.py`
- Create: `backend/schemas/__init__.py`
- Create: `backend/schemas/chat.py`
- Create: `backend/services/__init__.py`
- Create: `backend/routers/__init__.py`

- [ ] **Step 1: 写 requirements.txt**

`backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
chromadb==0.5.23
sentence-transformers==3.3.1
openai==1.58.1
python-dotenv==1.0.1
pydantic==2.10.4
```

- [ ] **Step 2: 写 .env.example**

`backend/.env.example`:
```
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
CHROMA_PATH=data/chroma_db
```

- [ ] **Step 3: 写 config.py**

`backend/config.py`:
```python
"""配置模块——从 .env 加载，单例不可变"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    deepseek_api_key: str
    deepseek_base_url: str
    embedding_model: str
    chroma_path: str

    _instance: "Config | None" = None  # type: ignore

    @classmethod
    def load(cls) -> "Config":
        if cls._instance is not None:
            return cls._instance
        # 绕过 frozen 限制，构造时一次性写入
        object.__setattr__(cls, "_instance", Config(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            chroma_path=os.getenv("CHROMA_PATH", "data/chroma_db"),
        ))
        return cls._instance
```

- [ ] **Step 4: 写 schemas/chat.py — 数据实体（frozen dataclass + Pydantic）**

`backend/schemas/chat.py`:
```python
"""对话相关数据实体——全部不可变"""
from dataclasses import dataclass, field
from typing import Optional, Literal
from pydantic import BaseModel


# ── 不可变值对象（dataclass） ──

@dataclass(frozen=True)
class ChunkMetadata:
    source_doc: str
    category: str
    page_number: int
    heading: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class Chunk:
    content: str
    metadata: ChunkMetadata
    chunk_index: int


@dataclass(frozen=True)
class RetrievalResult:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Source:
    """传给前端渲染引用卡片"""
    document_name: str
    heading: str
    excerpt: str
    score: float


@dataclass(frozen=True)
class GenerateEvent:
    type: Literal["token", "sources", "done"]
    content: Optional[str] = None
    sources: Optional[list[Source]] = None


# ── 请求/响应模型（Pydantic） ──

class QueryRequest(BaseModel):
    question: str
    category: Optional[str] = None


class SSEResponse(BaseModel):
    event: str  # "token" | "sources" | "done" | "error"
    data: str   # JSON string
```

- [ ] **Step 5: 创建空的 __init__.py**

`backend/schemas/__init__.py`, `backend/services/__init__.py`, `backend/routers/__init__.py`:
```python
# (空文件)
```

- [ ] **Step 6: 创建虚拟环境并安装依赖**

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

- [ ] **Step 7: 验证——Python 能导入所有模块**

```bash
python -c "from schemas.chat import Chunk, RetrievalResult, Source, GenerateEvent; print('OK')"
```
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "Task 1: 后端项目骨架 + config + schemas/chat.py 数据实体"
```

---

### Task 2: 抽象基类——五层接口契约

**Files:**
- Create: `backend/services/base.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_chunker.py`

- [ ] **Step 1: 写抽象基类**

`backend/services/base.py`:
```python
"""抽象基类——定义 RAG Pipeline 五层接口契约"""
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator
import numpy as np
from schemas.chat import Chunk, RetrievalResult, GenerateEvent


class BaseParser(ABC):
    """解析器——原始文档 → 纯文本"""

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """读取文档文件，返回纯文本字符串"""
        ...


class BaseChunker(ABC):
    """分块器——纯文本 → 语义块列表"""

    @abstractmethod
    def chunk(self, text: str, category: str, source_doc: str) -> List[Chunk]:
        """将文本切分为 Chunk 列表，每个 Chunk 携带 metadata"""
        ...


class BaseEmbedder(ABC):
    """嵌入器——文本列表 → 向量矩阵"""

    @abstractmethod
    def embed(self, texts: List[str]) -> "np.ndarray":
        """输入文本列表，返回 shape (N, dim) 的 float32 数组"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量的维度"""
        ...


class BaseRetriever(ABC):
    """检索器——查询向量 → 相似文档块列表"""

    @abstractmethod
    def search(
        self,
        query_embedding: "np.ndarray",
        top_k: int = 5,
        category_filter: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """根据查询向量检索最相似的 top_k 个 Chunk"""
        ...

    @abstractmethod
    def add_embeddings(self, chunks: List[Chunk], embeddings: "np.ndarray") -> int:
        """批量存入向量数据库，返回写入数量"""
        ...

    @abstractmethod
    def delete_by_document(self, source_doc: str) -> int:
        """删除指定文档的所有向量，返回删除数量"""
        ...


class BaseGenerator(ABC):
    """生成器——问题 + 上下文 → 流式回答"""

    @abstractmethod
    async def generate(
        self,
        question: str,
        contexts: List[RetrievalResult],
    ) -> AsyncIterator[GenerateEvent]:
        """根据检索到的上下文生成回答，异步迭代返回 GenerateEvent"""
        ...
```

- [ ] **Step 2: 写 Chunker 的单元测试**

`backend/tests/test_chunker.py`:
```python
"""测试 FixedChunker 的行为——先写测试，后写实现"""
import pytest
from services.base import BaseChunker


# 用最小实现来验证接口——FixedChunker 还没写，这里先定义测试契约
MOCK_TEXT = """# 第一章 考勤制度

公司实行弹性工作制。

## 1.1 上班时间

员工每日工作时间为 9:00 至 18:00，午休 1 小时。

## 1.2 迟到处理

迟到 30 分钟以内不扣工资。"""


def test_chunker_returns_list_of_chunks():
    """Chunker 必须返回 Chunk 列表"""
    # 这个测试在 FixedChunker 实现后才能跑
    # 现在只是定义规格
    pass


def test_chunk_metadata_contains_category():
    """每个 Chunk 的 metadata 必须包含 category"""
    pass


def test_chunk_overlap():
    """相邻 chunk 之间应有重叠内容"""
    pass
```

- [ ] **Step 3: 验证——Python 能导入所有抽象类**

```bash
python -c "from services.base import BaseParser, BaseChunker, BaseEmbedder, BaseRetriever, BaseGenerator; print('5 ABCs OK')"
```
Expected: `5 ABCs OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/base.py backend/tests/
git commit -m "Task 2: 五个抽象基类 + chunker 测试骨架"
```

---

### Task 3: MDParser + FixedChunker 具体实现

**Files:**
- Create: `backend/services/parser.py`
- Create: `backend/services/chunker.py`
- Modify: `backend/tests/test_chunker.py`

- [ ] **Step 1: 写 MDParser**

`backend/services/parser.py`:
```python
"""文档解析器实现"""
from services.base import BaseParser


class MDParser(BaseParser):
    """Markdown 解析器——直接读取 UTF-8 文本"""

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
```

- [ ] **Step 2: 写 FixedChunker**

`backend/services/chunker.py`:
```python
"""文本分块器实现"""
import re
from typing import List
from services.base import BaseChunker
from schemas.chat import Chunk, ChunkMetadata


class FixedChunker(BaseChunker):
    """固定窗口分块器——按字符数滑动窗口切分"""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, category: str, source_doc: str) -> List[Chunk]:
        chunks: List[Chunk] = []
        start = 0
        index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            content = text[start:end]

            # 找最近的标题作为 heading
            heading = self._find_nearest_heading(text, start)

            metadata = ChunkMetadata(
                source_doc=source_doc,
                category=category,
                page_number=0,
                heading=heading,
                char_start=start,
                char_end=end,
            )

            chunks.append(Chunk(
                content=content,
                metadata=metadata,
                chunk_index=index,
            ))

            index += 1
            if end == len(text):
                break
            start = end - self.overlap

        return chunks

    def _find_nearest_heading(self, text: str, position: int) -> str:
        """向上查找最近的 Markdown 标题"""
        before = text[:position]
        matches = re.findall(r"^#{1,6}\s+(.+)$", before, re.MULTILINE)
        return matches[-1] if matches else ""
```

- [ ] **Step 3: 写完整的 Chunker 测试**

`backend/tests/test_chunker.py`:
```python
"""FixedChunker 单元测试"""
import pytest
from services.chunker import FixedChunker
from schemas.chat import Chunk

SAMPLE_TEXT = """# 第一章 考勤制度

公司实行弹性工作制，员工可根据个人情况灵活安排上下班时间。

## 1.1 上班时间

员工每日工作时间为 9:00 至 18:00，午休 1 小时（12:00-13:00）。
弹性工作制允许员工在 8:00-10:00 之间到岗，对应下班时间为 17:00-19:00。

## 1.2 迟到处理

迟到 30 分钟以内不计入考勤异常，但需向直属上级报备。
迟到超过 30 分钟按事假半小时计算，超过 2 小时按半天事假计算。

## 1.3 加班规定

加班需提前在 OA 系统中提交申请，经部门经理审批后方可执行。
工作日加班按 1.5 倍工资计算，休息日加班按 2 倍计算。"""


class TestFixedChunker:
    """FixedChunker 的行为测试"""

    def test_returns_list_of_chunks(self):
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, Chunk) for c in result)

    def test_chunk_metadata_has_category(self):
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for chunk in result:
            assert chunk.metadata.category == "员工手册"
            assert chunk.metadata.source_doc == "员工手册.md"

    def test_chunk_indices_are_sequential(self):
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunk_overlap(self):
        """相邻 chunk 的 content 末尾/开头应有重叠"""
        chunker = FixedChunker(chunk_size=200, overlap=50)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        if len(result) >= 2:
            # 前一块末尾跟后一块开头应该有公共字符
            tail = result[0].content[-20:]
            head = result[1].content[:20]
            # 不一定完全匹配（可能在单字边界），但至少一块会覆盖另一块的区域
            # 验证 metadata 位置有重叠
            assert result[1].metadata.char_start < result[0].metadata.char_end

    def test_heading_detection(self):
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        # 第一个 chunk 的 heading 应该是 "第一章 考勤制度"
        assert result[0].metadata.heading == "第一章 考勤制度"

    def test_chunk_size_limit(self):
        chunker = FixedChunker(chunk_size=100, overlap=10)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for chunk in result:
            assert len(chunk.content) <= 100
```

- [ ] **Step 4: 运行 Chunker 测试**

```bash
cd backend
venv\Scripts\activate
pytest tests/test_chunker.py -v
```
Expected: 6 passed

- [ ] **Step 5: 验证 Parser 可导入**

```bash
python -c "from services.parser import MDParser; p = MDParser(); print(type(p).__name__, 'OK')"
```
Expected: `MDParser OK`

- [ ] **Step 6: Commit**

```bash
git add backend/services/parser.py backend/services/chunker.py backend/tests/test_chunker.py
git commit -m "Task 3: MDParser + FixedChunker 实现 + 6 个单测通过"
```

---

### Task 4: Embedder + Retriever 实现

**Files:**
- Create: `backend/services/embedder.py`
- Create: `backend/services/retriever.py`
- Create: `backend/tests/test_embedder.py`

- [ ] **Step 1: 写 BGEBaaIEmbedder**

`backend/services/embedder.py`:
```python
"""嵌入器——BGE 模型封装"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from services.base import BaseEmbedder


class BGEBaaIEmbedder(BaseEmbedder):
    """BAAI/bge-small-zh-v1.5 本地嵌入器"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu"):
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: List[str]) -> "np.ndarray":
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.array(embeddings, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension
```

- [ ] **Step 2: 写 Embedder 测试**

`backend/tests/test_embedder.py`:
```python
"""BGEBaaIEmbedder 单元测试"""
import pytest
import numpy as np
from services.embedder import BGEBaaIEmbedder


@pytest.fixture(scope="module")
def embedder():
    """模块级 fixture——模型只加载一次"""
    return BGEBaaIEmbedder(device="cpu")


class TestBGEBaaIEmbedder:
    """注意：首次运行会自动下载模型（约 100MB）"""

    def test_embed_returns_float32_array(self, embedder):
        result = embedder.embed(["测试文本"])
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    def test_embed_output_shape(self, embedder):
        texts = ["第一段文字", "第二段文字", "第三段文字"]
        result = embedder.embed(texts)
        assert result.shape == (3, embedder.dimension)

    def test_dimension_matches(self, embedder):
        assert embedder.dimension == 512  # bge-small 固定 512 维

    def test_embeddings_are_normalized(self, embedder):
        result = embedder.embed(["测试"])
        norm = np.linalg.norm(result[0])
        assert abs(norm - 1.0) < 0.01  # L2 范数接近 1

    def test_similar_texts_have_higher_similarity(self, embedder):
        """语义相近的文本余弦相似度更高"""
        a = embedder.embed(["年假怎么申请"])[0]
        b = embedder.embed(["员工休假流程"])[0]
        c = embedder.embed(["今天天气真好"])[0]
        sim_ab = np.dot(a, b)
        sim_ac = np.dot(a, c)
        assert sim_ab > sim_ac
```

- [ ] **Step 3: 写 ChromaRetriever**

`backend/services/retriever.py`:
```python
"""检索器——ChromaDB 封装"""
from typing import List, Optional
import uuid
import chromadb
from chromadb.config import Settings
from services.base import BaseRetriever, BaseEmbedder
from schemas.chat import Chunk, RetrievalResult


class ChromaRetriever(BaseRetriever):
    """基于 ChromaDB 的向量检索器"""

    def __init__(self, persist_path: str, embedder: BaseEmbedder):
        self._client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(
            name="enterprise_docs",
            metadata={"hnsw:space": "cosine"},
        )

    def search(
        self,
        query_embedding,
        top_k: int = 5,
        category_filter: Optional[str] = None,
    ) -> List[RetrievalResult]:
        where_filter = None
        if category_filter:
            where_filter = {"category": category_filter}

        results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output: List[RetrievalResult] = []
        if not results["ids"] or not results["ids"][0]:
            return output

        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine distance → similarity
            similarity = 1.0 - distance

            from schemas.chat import ChunkMetadata
            chunk_meta = ChunkMetadata(
                source_doc=meta.get("source_doc", ""),
                category=meta.get("category", ""),
                page_number=meta.get("page_number", 0),
                heading=meta.get("heading", ""),
                char_start=meta.get("char_start", 0),
                char_end=meta.get("char_end", 0),
            )

            from schemas.chat import Chunk
            chunk = Chunk(
                content=results["documents"][0][i],
                metadata=chunk_meta,
                chunk_index=meta.get("chunk_index", 0),
            )

            output.append(RetrievalResult(chunk=chunk, score=similarity))

        return output

    def add_embeddings(self, chunks: List[Chunk], embeddings) -> int:
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for chunk in chunks:
            ids.append(str(uuid.uuid4()))
            documents.append(chunk.content)
            metadatas.append({
                "source_doc": chunk.metadata.source_doc,
                "category": chunk.metadata.category,
                "page_number": chunk.metadata.page_number,
                "heading": chunk.metadata.heading,
                "char_start": chunk.metadata.char_start,
                "char_end": chunk.metadata.char_end,
                "chunk_index": chunk.chunk_index,
            })

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )
        return len(ids)

    def delete_by_document(self, source_doc: str) -> int:
        results = self._collection.get(
            where={"source_doc": source_doc},
            include=[],
        )
        ids_to_delete = results["ids"]
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)
```

- [ ] **Step 4: 运行 Embedder 测试**

```bash
cd backend
venv\Scripts\activate
pytest tests/test_embedder.py -v
```
Expected: 5 passed（首次运行会下载 BGE 模型 ~100MB）

- [ ] **Step 5: 验证 Retriever 可导入**

```bash
python -c "from services.retriever import ChromaRetriever; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/services/embedder.py backend/services/retriever.py backend/tests/test_embedder.py
git commit -m "Task 4: BGEBaaIEmbedder + ChromaRetriever 实现 + embedding 单测"
```

---

### Task 5: System Prompt + DeepSeekGenerator

**Files:**
- Create: `backend/services/prompts.py`
- Create: `backend/services/generator.py`

- [ ] **Step 1: 写 System Prompt 常量**

`backend/services/prompts.py`:
```python
"""RAG System Prompt——生产级七维度规范"""
from typing import List
from schemas.chat import RetrievalResult

SYSTEM_PROMPT = """# 角色定义
你是一位资深的企业制度合规顾问，服务于一家中大型企业的内部知识管理平台。
你的用户是该公司全体员工——从一线员工到中层管理者。
他们向你咨询的问题直接关系到实际工作中的合规判断、流程操作和权益保障，
因此你的每一个回答都必须是严谨、可追溯、可验证的。

# 一、信息来源铁律
1. 你只能依据【参考文档】中提供的内容作答。参考文档是你唯一的知识来源。
2. 禁止使用以下来源的信息：
   - 你的预训练知识中的法律法规、行业惯例、常识判断
   - 对其他公司制度的推测或类比
   - 用户在本次对话中未经验证的陈述
3. 当你需要引用文档内容时，必须包含三个要素：
   - 文档名称（完整标题）
   - 章节/条款编号（如原文有编号）
   - 原文关键句的直接引用（双引号标出）

# 二、答案质量门槛
在给出回答前，你必须在内部完成以下检查：
- 完整性检查：是否覆盖了参考文档中所有与问题相关的条款？
- 准确性检查：所有数字、日期、百分比、金额是否与原文完全一致？
- 适用性检查：该条款是否适用于提问者可能所在的部门/职级/场景？
- 时效性检查：引用的条款是否为最新版本？

# 三、回答结构规范
使用以下 Markdown 结构组织每个回答：

## 📋 结论摘要
1-3 句话给出核心结论。如果问题存在"视情况而定"的复杂性，在此标明"详见下方分类说明"。

## 📖 制度依据
按"一般规定 → 特殊情形 → 例外情况"的层级展开，每个层级附引用来源。

## ⚠️ 关键提示
用列表列出用户最容易忽略或误解的内容。

## 📎 引用清单
| 文档名称 | 章节/条款 | 原文关键句 | 可信度 |
|----------|----------|-----------|--------|
（可信度分三档：明确记载 > 合理推断 > 间接相关）

## 🔍 关联线索（可选）
如果参考文档中存在与问题部分相关但未直接回答的内容，在此提示。若没有，此项完全省略。

# 四、冲突处理协议
当多份参考文档对同一事项的规定不一致时：
1. 必须在回答中显式暴露冲突，不得私下选择其一而隐瞒另一份的存在；
2. 列出冲突条款的完整出处；
3. 按以下优先级判断：生效日期最新 > 审批层级更高 > 适用范围更具体；
4. 说明你判断优先级的理由。

# 五、边界与拒答
| 情况 | 标准回答 |
|------|---------|
| 知识库无相关内容 | "经检索，当前制度知识库中未收录与该问题直接相关的规定。" |
| 信息不完整 | "文档中有提及但未展开详细规定。现有信息如下：[列出]。如需完整规定，建议查阅原文或咨询相关部门。" |
| 超出制度范畴 | "该问题涉及的领域不在企业制度知识库覆盖范围内。" |
| 问题模糊 | 不要猜测。列出 2-3 种可能的理解方式，请用户澄清后再回答。 |

# 六、语气与风格
- 使用专业但平实的语言，让非专业岗位的员工也能看懂
- 涉及金额、时间、步骤时使用加粗或列表强化
- 不要说"根据公司规定"，始终说"根据《XXX文档》第X章规定"
- 只陈述"制度是如何规定的"，不对用户行为给出"你应该怎么做"的建议

# 七、输出前自检
1. 这段话里有没有原文找不到的内容？→ 删除
2. 有没有"一般来说""通常""可能"等模糊表述未经文档支撑？→ 替换或删除
3. 所有引用是否三要素齐全（文档名、章节号、原文句）？→ 补全
4. 看完这个回答能否直接知道该查哪份文档的哪一页？→ 不能就补上"""


def build_context_block(contexts: List[RetrievalResult]) -> str:
    """将检索结果拼接为 Prompt 的【参考文档】区块"""
    blocks: List[str] = []
    for i, result in enumerate(contexts, 1):
        chunk = result.chunk
        meta = chunk.metadata
        block = (
            f"[文档{i}] 来源：{meta.source_doc}\n"
            f"章节：{meta.heading or '（无标题）'}\n"
            f"内容：{chunk.content}\n"
        )
        blocks.append(block)
    return "\n---\n".join(blocks)


def build_user_message(question: str, contexts: List[RetrievalResult]) -> str:
    """构建发给 LLM 的完整 user message"""
    context_block = build_context_block(contexts)
    return f"""【参考文档】
{context_block}

【用户问题】
{question}

请严格按照 System Prompt 中的要求回答。"""
```

- [ ] **Step 2: 写 DeepSeekGenerator**

`backend/services/generator.py`:
```python
"""生成器——DeepSeek API 流式调用"""
from typing import List, AsyncIterator
from openai import AsyncOpenAI
from services.base import BaseGenerator
from services.prompts import SYSTEM_PROMPT, build_user_message, build_context_block
from schemas.chat import RetrievalResult, GenerateEvent, Source


class DeepSeekGenerator(BaseGenerator):
    """DeepSeek API 流式生成器"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
    ):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    async def generate(
        self,
        question: str,
        contexts: List[RetrievalResult],
    ) -> AsyncIterator[GenerateEvent]:
        user_message = build_user_message(question, contexts)

        stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield GenerateEvent(type="token", content=delta.content)

        # 流结束后一次性发送引用源
        sources = [
            Source(
                document_name=result.chunk.metadata.source_doc,
                heading=result.chunk.metadata.heading,
                excerpt=result.chunk.content[:200],
                score=result.score,
            )
            for result in contexts
        ]
        yield GenerateEvent(type="sources", sources=sources)

        # 发送结束信号
        yield GenerateEvent(type="done")
```

- [ ] **Step 3: 验证可导入**

```bash
cd backend
venv\Scripts\activate
python -c "from services.generator import DeepSeekGenerator; from services.prompts import SYSTEM_PROMPT; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/prompts.py backend/services/generator.py
git commit -m "Task 5: System Prompt + DeepSeekGenerator 流式生成实现"
```

---

### Task 6: RAGPipeline 编排器 + Builder 模式

**Files:**
- Create: `backend/services/pipeline.py`

- [ ] **Step 1: 写 RAGPipeline + RAGPipelineBuilder**

`backend/services/pipeline.py`:
```python
"""RAG Pipeline 编排器——Builder 模式组装五层组件"""
from typing import Optional, AsyncIterator
from services.base import (
    BaseParser, BaseChunker, BaseEmbedder,
    BaseRetriever, BaseGenerator,
)
from schemas.chat import GenerateEvent


class RAGPipelineBuilder:
    """Builder——逐步注入依赖，最后 build() 返回不可变 Pipeline"""

    def __init__(self):
        self._parser: Optional[BaseParser] = None
        self._chunker: Optional[BaseChunker] = None
        self._embedder: Optional[BaseEmbedder] = None
        self._retriever: Optional[BaseRetriever] = None
        self._generator: Optional[BaseGenerator] = None

    def with_parser(self, parser: BaseParser) -> "RAGPipelineBuilder":
        self._parser = parser
        return self

    def with_chunker(self, chunker: BaseChunker) -> "RAGPipelineBuilder":
        self._chunker = chunker
        return self

    def with_embedder(self, embedder: BaseEmbedder) -> "RAGPipelineBuilder":
        self._embedder = embedder
        return self

    def with_retriever(self, retriever: BaseRetriever) -> "RAGPipelineBuilder":
        self._retriever = retriever
        return self

    def with_generator(self, generator: BaseGenerator) -> "RAGPipelineBuilder":
        self._generator = generator
        return self

    def build(self) -> "RAGPipeline":
        if not all([self._parser, self._chunker, self._embedder,
                     self._retriever, self._generator]):
            missing = []
            for name, val in [
                ("parser", self._parser), ("chunker", self._chunker),
                ("embedder", self._embedder), ("retriever", self._retriever),
                ("generator", self._generator),
            ]:
                if val is None:
                    missing.append(name)
            raise ValueError(f"缺少组件: {', '.join(missing)}")
        return RAGPipeline(
            parser=self._parser,        # type: ignore
            chunker=self._chunker,      # type: ignore
            embedder=self._embedder,    # type: ignore
            retriever=self._retriever,  # type: ignore
            generator=self._generator,  # type: ignore
        )


class RAGPipeline:
    """编排器——组合五层组件，暴露 ingest / query 两个入口"""

    def __init__(
        self,
        parser: BaseParser,
        chunker: BaseChunker,
        embedder: BaseEmbedder,
        retriever: BaseRetriever,
        generator: BaseGenerator,
    ):
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._retriever = retriever
        self._generator = generator

    @classmethod
    def builder(cls) -> RAGPipelineBuilder:
        return RAGPipelineBuilder()

    async def ingest(self, file_path: str, category: str) -> int:
        """文档摄入：解析 → 分块 → Embedding → 入库"""
        # 从文件名提取 source_doc
        import os
        source_doc = os.path.basename(file_path)

        # ① 解析
        text = self._parser.parse(file_path)

        # ② 分块
        chunks = self._chunker.chunk(text, category=category, source_doc=source_doc)

        if not chunks:
            return 0

        # ③ Embedding
        texts = [c.content for c in chunks]
        embeddings = self._embedder.embed(texts)

        # ④ 入库
        count = self._retriever.add_embeddings(chunks, embeddings)
        return count

    async def query(
        self,
        question: str,
        category_filter: Optional[str] = None,
    ) -> AsyncIterator[GenerateEvent]:
        """检索 + 生成，流式返回"""
        # ① 问题向量化
        query_embedding = self._embedder.embed([question])[0]

        # ② 检索
        results = self._retriever.search(
            query_embedding=query_embedding,
            top_k=5,
            category_filter=category_filter,
        )

        # ③ 生成（流式）
        async for event in self._generator.generate(question, results):
            yield event
```

- [ ] **Step 2: 验证可导入 + Builder 校验能报错**

```bash
cd backend
venv\Scripts\activate
python -c "
from services.pipeline import RAGPipeline, RAGPipelineBuilder
b = RAGPipeline.builder()
try:
    b.build()
    print('ERROR: should have raised')
except ValueError as e:
    print(f'Builder 校验通过: {e}')
"
```
Expected: `Builder 校验通过: 缺少组件: parser, chunker, embedder, retriever, generator`

- [ ] **Step 3: Commit**

```bash
git add backend/services/pipeline.py
git commit -m "Task 6: RAGPipeline 编排器 + Builder 模式"
```

---

### Task 7: FastAPI 路由 + 入口

**Files:**
- Create: `backend/routers/chat.py`
- Create: `backend/main.py`

- [ ] **Step 1: 写 chat 路由（SSE 流式端点）**

`backend/routers/chat.py`:
```python
"""对话路由——SSE 流式问答"""
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from schemas.chat import QueryRequest
from services.pipeline import RAGPipeline

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_pipeline() -> RAGPipeline:
    """从 app.state 获取全局 pipeline 实例"""
    from main import app
    return app.state.pipeline


async def _sse_generator(question: str, category: str | None, pipeline: RAGPipeline):
    """将 RAGPipeline.query() 的 GenerateEvent 转为 SSE 格式"""
    async for event in pipeline.query(question, category_filter=category):
        if event.type == "token":
            yield f"event: token\ndata: {event.content}\n\n"
        elif event.type == "sources":
            sources_json = json.dumps(
                [{"documentName": s.document_name,
                  "heading": s.heading,
                  "excerpt": s.excerpt,
                  "score": s.score} for s in (event.sources or [])],
                ensure_ascii=False,
            )
            yield f"event: sources\ndata: {sources_json}\n\n"
        elif event.type == "done":
            yield "event: done\ndata: \n\n"


@router.post("/send")
async def send_message(request: QueryRequest):
    """发送消息，返回 SSE 流"""
    pipeline = _get_pipeline()
    return StreamingResponse(
        _sse_generator(request.question, request.category, pipeline),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: 写 main.py（FastAPI 入口 + 启动时构建 Pipeline）**

`backend/main.py`:
```python
"""FastAPI 应用入口——生命周期管理 + CORS"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import Config
from services.parser import MDParser
from services.chunker import FixedChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.generator import DeepSeekGenerator
from services.pipeline import RAGPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时构建 RAGPipeline，关闭时清理"""
    config = Config.load()

    # Builder 模式组装
    embedder = BGEBaaIEmbedder(
        model_name=config.embedding_model,
        device="cuda",  # RTX 4060
    )

    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(FixedChunker(chunk_size=500, overlap=50))
        .with_embedder(embedder)
        .with_retriever(ChromaRetriever(
            persist_path=config.chroma_path,
            embedder=embedder,
        ))
        .with_generator(DeepSeekGenerator(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model="deepseek-chat",
            temperature=0.3,
        ))
        .build()
    )

    app.state.pipeline = pipeline
    print(f"[启动] Pipeline 已就绪 | Embedding: {config.embedding_model} | ChromaDB: {config.chroma_path}")

    yield

    print("[关闭] 服务停止")


app = FastAPI(title="RAG 企业制度智能问答", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.chat import router as chat_router
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: 验证 FastAPI 能启动（无文档也能启）**

```bash
cd backend
venv\Scripts\activate
cp .env.example .env  # 先创建 .env（Windows: copy .env.example .env）
# 编辑 .env 填入真实的 DEEPSEEK_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8000
# 另开终端
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/chat.py backend/main.py
git commit -m "Task 7: FastAPI 路由 + SSE 端点 + 应用入口"
```

---

### Task 8: 测试文档 + 摄入验证

**Files:**
- Create: `data/documents/员工手册.md`

- [ ] **Step 1: 写测试文档**

`data/documents/员工手册.md`:
```markdown
# 员工手册

## 第一章 入职与转正

### 1.1 入职流程

新员工入职当日须携带身份证原件、学历证书复印件、离职证明（如有）至人力资源部办理入职手续。入职手续包括：签订劳动合同、录入考勤指纹、领取工牌及办公用品。

### 1.2 试用期规定

新员工试用期为 3 个月。试用期内表现优异者可申请提前转正，提前时间不超过 1 个月。试用期工资为转正工资的 80%。

### 1.3 转正考核

试用期满前 2 周，员工需提交《转正申请表》至直属上级。直属上级在 3 个工作日内完成评估，部门经理在 2 个工作日内完成审批。转正考核维度包括：工作能力（40%）、工作态度（30%）、团队协作（20%）、学习成长（10%）。

## 第二章 考勤与休假

### 2.1 工作时间

公司实行弹性工作制。核心工作时间为 10:00 至 16:00，在此期间所有员工须在岗。员工每日工作时长不少于 8 小时，午休时间为 12:00-13:00。

### 2.2 迟到与早退

迟到 30 分钟以内不计入考勤异常，但每月累计不得超过 3 次。迟到超过 30 分钟按事假半小时计算。早退需提前向直属上级报备并获批准。

### 2.3 年假制度

员工入职满 1 年后可享受带薪年假。工作年限 1-5 年：每年 5 天；5-10 年：每年 10 天；10 年以上：每年 15 天。年假须提前 1 周申请，经部门经理审批。当年未休完的年假可延期至次年 3 月 31 日，逾期作废。

### 2.4 病假与事假

病假需提供二级甲等以上医院出具的病假证明。病假期间工资按基本工资的 60% 发放。事假须提前 1 天申请，事假期间不发放工资。

## 第三章 薪酬与福利

### 3.1 薪酬结构

员工月薪 = 基本工资（60%）+ 岗位工资（30%）+ 绩效工资（10%）。每月 10 日发放上月工资，遇节假日顺延至最近工作日。

### 3.2 加班补贴

工作日加班（18:00 后）：按基本工资的 1.5 倍计算加班费。休息日加班：按基本工资的 2 倍计算。法定节假日加班：按基本工资的 3 倍计算。加班需提前在 OA 系统中提交申请，经部门经理审批后方可执行。

### 3.3 五险一金

公司依法为员工缴纳养老保险、医疗保险、失业保险、工伤保险、生育保险及住房公积金。缴纳基数按员工上年度月平均工资确定，比例按当地社保部门规定执行。

### 3.4 其他福利

公司提供免费午餐、年度体检、生日礼金（200 元）、结婚礼金（1000 元）。工作满 2 年后可申请公司低息购房借款，额度不超过 10 万元。

## 第四章 绩效考核

### 4.1 考核周期

绩效考核每季度进行一次，考核时间为每季度结束后 5 个工作日内。年度考核在每年 12 月进行，综合四个季度考核结果。

### 4.2 考核等级

考核分为四个等级：A（优秀，前 20%）、B（良好，40%）、C（合格，35%）、D（需改进，后 5%）。年度考核为 D 级的员工将进入绩效改进计划，连续两个季度为 D 级的员工公司保留解除劳动合同的权利。

### 4.3 晋升机制

年度考核为 A 级的员工可获得晋升提名资格。晋升需通过晋升评审委员会的答辩，评审委员会由部门经理、HR 经理及分管副总组成。

## 第五章 行政与安全

### 5.1 办公用品领用

员工可在每月 1-5 日通过 OA 系统申请当月办公用品。标准额度为每人每月 50 元，超额部分需部门经理审批。

### 5.2 信息安全

员工不得在非公司设备上存储公司敏感数据。离开工位时须锁定电脑屏幕。禁止使用个人邮箱发送带有公司机密信息的邮件。违反信息安全规定的员工将视情节严重程度给予警告、罚款乃至解除劳动合同的处分。

### 5.3 访客管理

来访人员须在前台登记，领取访客证后方可进入办公区。访客证当日有效，离开时须归还。员工接待访客期间对访客行为负责。
```

- [ ] **Step 2: 创建摄入脚本验证全链路**

```bash
cd backend
venv\Scripts\activate
python -c "
import asyncio
from config import Config
from services.parser import MDParser
from services.chunker import FixedChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.generator import DeepSeekGenerator
from services.pipeline import RAGPipeline

async def main():
    config = Config.load()
    embedder = BGEBaaIEmbedder(model_name=config.embedding_model, device='cpu')
    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(FixedChunker(chunk_size=500, overlap=50))
        .with_embedder(embedder)
        .with_retriever(ChromaRetriever(persist_path=config.chroma_path, embedder=embedder))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .build()
    )
    count = await pipeline.ingest('../data/documents/员工手册.md', category='员工手册')
    print(f'摄入完成: {count} 个 chunk')

asyncio.run(main())
"
```
Expected: `摄入完成: N 个 chunk`（N > 0）

- [ ] **Step 3: Commit + 推 GitHub**

```bash
git add data/documents/员工手册.md
git commit -m "Task 8: 测试文档 + 摄入验证"
```
```
git remote add origin https://github.com/mrw308/rag-enterprise-qa.git
git branch -M main
git push -u origin main
```

---

### Task 9: 前端项目搭建（Vite + React + TypeScript）

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: package.json**

`frontend/package.json`:
```json
{
  "name": "rag-enterprise-qa-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}
```

- [ ] **Step 2: tsconfig.json**

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: vite.config.ts**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: index.html**

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RAG 企业制度问答</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: 前端类型定义**

`frontend/src/types/index.ts`:
```typescript
export interface Source {
  documentName: string;
  heading: string;
  excerpt: string;
  score: number;
}

export type SSEEventType = 'token' | 'sources' | 'done' | 'error';

export interface SSEMessage {
  type: SSEEventType;
  content?: string;
  sources?: Source[];
  error?: string;
}

export interface ChatClientEvents {
  message: (msg: SSEMessage) => void;
  error: (err: Error) => void;
  done: () => void;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  isStreaming: boolean;
  createdAt: number;
}
```

- [ ] **Step 6: 安装依赖并验证**

```bash
cd frontend
npm install
npx tsc --noEmit
```
Expected: 无 TypeScript 错误

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "Task 9: 前端项目搭建 — Vite + React + TS + 类型定义"
```

---

### Task 10: EventEmitter 基类 + ChatClient（SSE 客户端）

**Files:**
- Create: `frontend/src/core/EventEmitter.ts`
- Create: `frontend/src/core/ChatClient.ts`

- [ ] **Step 1: 写 EventEmitter 基类**

`frontend/src/core/EventEmitter.ts`:
```typescript
type Listener = (...args: any[]) => void;

export class EventEmitter {
  private _listeners: Map<string, Listener[]> = new Map();

  /** 注册事件监听 */
  on(event: string, listener: Listener): this {
    const list = this._listeners.get(event);
    if (list) {
      list.push(listener);
    } else {
      this._listeners.set(event, [listener]);
    }
    return this;
  }

  /** 移除事件监听 */
  off(event: string, listener: Listener): this {
    const list = this._listeners.get(event);
    if (list) {
      const idx = list.indexOf(listener);
      if (idx !== -1) list.splice(idx, 1);
    }
    return this;
  }

  /** 触发事件 */
  protected emit(event: string, ...args: any[]): void {
    const list = this._listeners.get(event);
    if (list) {
      for (const fn of list) {
        fn(...args);
      }
    }
  }

  /** 移除所有监听 */
  removeAllListeners(): void {
    this._listeners.clear();
  }
}
```

- [ ] **Step 2: 写 ChatClient 类（继承 EventEmitter）**

`frontend/src/core/ChatClient.ts`:
```typescript
import { EventEmitter } from './EventEmitter';
import type { SSEMessage, Source } from '../types';

/** ChatClient 状态 */
type ClientState = 'IDLE' | 'CONNECTING' | 'STREAMING' | 'ERROR';

export class ChatClient extends EventEmitter {
  private _state: ClientState = 'IDLE';
  private _abortController: AbortController | null = null;

  get state(): ClientState {
    return this._state;
  }

  /** 发送问题，发起 SSE 连接 */
  async send(question: string, category?: string): Promise<void> {
    if (this._state === 'STREAMING' || this._state === 'CONNECTING') {
      console.warn('ChatClient: 已有请求进行中');
      return;
    }

    this._state = 'CONNECTING';
    this._abortController = new AbortController();

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ question, category: category ?? null }),
        signal: this._abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this._state = 'STREAMING';
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按双换行分割 SSE 事件
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || ''; // 最后一个可能不完整，留到下次

        for (const part of parts) {
          if (!part.trim()) continue;
          const parsed = this._parseSSE(part);
          if (parsed) {
            this.emit('message', parsed);
          }
        }
      }

      // 流结束，处理残留 buffer
      if (buffer.trim()) {
        const parsed = this._parseSSE(buffer);
        if (parsed) this.emit('message', parsed);
      }

      this.emit('done');
      this._state = 'IDLE';

    } catch (err: any) {
      if (err.name === 'AbortError') {
        // 用户主动取消，不算错误
        this._state = 'IDLE';
        return;
      }
      this._state = 'ERROR';
      this.emit('error', err instanceof Error ? err : new Error(String(err)));
      this._state = 'IDLE';
    }
  }

  /** 取消当前请求 */
  abort(): void {
    if (this._abortController) {
      this._abortController.abort();
      this._abortController = null;
    }
  }

  /** 解析单条 SSE 事件文本 */
  private _parseSSE(raw: string): SSEMessage | null {
    const lines = raw.split('\n');
    let eventType = '';
    let data = '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        data = line.slice(6);
      }
    }

    if (!eventType) return null;

    switch (eventType) {
      case 'token':
        return { type: 'token', content: data };
      case 'sources':
        try {
          const sources: Source[] = JSON.parse(data);
          return { type: 'sources', sources };
        } catch {
          return null;
        }
      case 'done':
        return { type: 'done' };
      case 'error':
        return { type: 'error', error: data };
      default:
        return null;
    }
  }
}
```

- [ ] **Step 3: 写 EventEmitter 单元测试**

`frontend/src/core/__tests__/EventEmitter.test.ts`:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { EventEmitter } from '../EventEmitter';

// 创建一个测试子类来暴露 protected emit
class TestEmitter extends EventEmitter {
  public emitPublic(event: string, ...args: any[]) {
    this.emit(event, ...args);
  }
}

describe('EventEmitter', () => {
  it('应触发已注册的监听器', () => {
    const emitter = new TestEmitter();
    const fn = vi.fn();
    emitter.on('test', fn);
    emitter.emitPublic('test', 'hello', 42);
    expect(fn).toHaveBeenCalledWith('hello', 42);
  });

  it('off 后不再触发', () => {
    const emitter = new TestEmitter();
    const fn = vi.fn();
    emitter.on('test', fn);
    emitter.off('test', fn);
    emitter.emitPublic('test');
    expect(fn).not.toHaveBeenCalled();
  });

  it('重复 on 会注册多次', () => {
    const emitter = new TestEmitter();
    const fn = vi.fn();
    emitter.on('x', fn).on('x', fn);
    emitter.emitPublic('x');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('removeAllListeners 清空所有', () => {
    const emitter = new TestEmitter();
    const fn = vi.fn();
    emitter.on('a', fn).on('b', fn);
    emitter.removeAllListeners();
    emitter.emitPublic('a');
    emitter.emitPublic('b');
    expect(fn).not.toHaveBeenCalled();
  });

  it('未注册事件 emit 不报错', () => {
    const emitter = new TestEmitter();
    expect(() => emitter.emitPublic('nonexistent')).not.toThrow();
  });
});
```

- [ ] **Step 4: 安装 vitest 并运行测试**

```bash
cd frontend
npm install -D vitest
npx vitest run
```
Expected: 5 passed

- [ ] **Step 5: 验证 TypeScript 编译无错**

```bash
npx tsc --noEmit
```
Expected: 无输出（无错误）

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "Task 10: EventEmitter 基类 + ChatClient SSE 客户端 + 5 单测"
```

---

### Task 11: ChatPanel + SourcePopover 组件

**Files:**
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/SourcePopover.tsx`

- [ ] **Step 1: 写 SourcePopover 组件**

`frontend/src/components/SourcePopover.tsx`:
```tsx
import { useState, useRef, useEffect } from 'react';
import type { Source } from '../types';

interface Props {
  sources: Source[];
}

export function SourcePopover({ sources }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [open]);

  if (!sources.length) return null;

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: '#f0f4ff',
          border: '1px solid #c3d0ff',
          borderRadius: 6,
          padding: '4px 10px',
          cursor: 'pointer',
          fontSize: 13,
          color: '#3355cc',
        }}
      >
        📎 引用来源 ({sources.length})
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: 0,
          marginBottom: 8,
          background: '#fff',
          border: '1px solid #e0e0e0',
          borderRadius: 8,
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          padding: 12,
          width: 380,
          maxHeight: 300,
          overflowY: 'auto',
          zIndex: 100,
        }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              marginBottom: i < sources.length - 1 ? 12 : 0,
              paddingBottom: i < sources.length - 1 ? 12 : 0,
              borderBottom: i < sources.length - 1 ? '1px solid #eee' : 'none',
            }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                📄 {s.documentName} · {s.heading || '（无标题）'}
                <span style={{ marginLeft: 8, color: '#999' }}>
                  相关度: {(s.score * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ fontSize: 13, color: '#333', lineHeight: 1.6 }}>
                {s.excerpt}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 写 ChatPanel 组件**

`frontend/src/components/ChatPanel.tsx`:
```tsx
import { useState, useRef, useEffect, useCallback } from 'react';
import { ChatClient } from '../core/ChatClient';
import { SourcePopover } from './SourcePopover';
import type { Message, Source } from '../types';

let idCounter = 0;
function nextId(): string {
  return `msg_${++idCounter}_${Date.now()}`;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const clientRef = useRef<ChatClient | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 初始化 ChatClient，绑定事件
  useEffect(() => {
    const client = new ChatClient();
    clientRef.current = client;

    client.on('message', (msg) => {
      if (msg.type === 'token') {
        // 增量追加到当前 assistant 消息
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant' && last.isStreaming) {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + (msg.content || ''),
            };
          }
          return updated;
        });
      } else if (msg.type === 'sources') {
        // 追加引用到当前 assistant 消息
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              sources: msg.sources,
            };
          }
          return updated;
        });
      }
    });

    client.on('done', () => {
      setStreaming(false);
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last && last.role === 'assistant') {
          updated[updated.length - 1] = { ...last, isStreaming: false };
        }
        return updated;
      });
    });

    client.on('error', (err) => {
      setStreaming(false);
      setMessages(prev => [...prev, {
        id: nextId(),
        role: 'assistant',
        content: `❌ 出错了：${err.message}`,
        isStreaming: false,
        createdAt: Date.now(),
      }]);
    });

    return () => {
      client.abort();
      client.removeAllListeners();
    };
  }, []);

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg: Message = {
      id: nextId(),
      role: 'user',
      content: text,
      isStreaming: false,
      createdAt: Date.now(),
    };

    const assistantMsg: Message = {
      id: nextId(),
      role: 'assistant',
      content: '',
      isStreaming: true,
      createdAt: Date.now(),
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setStreaming(true);

    clientRef.current?.send(text);
  }, [input, streaming]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      maxWidth: 800,
      margin: '0 auto',
      padding: '0 16px',
    }}>
      {/* 消息列表 */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px 0',
      }}>
        {messages.length === 0 && (
          <div style={{
            textAlign: 'center',
            color: '#999',
            marginTop: '30vh',
            fontSize: 16,
          }}>
            🤖 向企业制度知识库提问吧
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} style={{
            marginBottom: 20,
            display: 'flex',
            flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            {/* 气泡 */}
            <div style={{
              maxWidth: '80%',
              padding: '12px 16px',
              borderRadius: 12,
              background: msg.role === 'user' ? '#e8f0fe' : '#f5f5f5',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: 15,
              lineHeight: 1.7,
            }}>
              {msg.content}
              {msg.isStreaming && <span style={{
                display: 'inline-block',
                width: 8,
                height: 16,
                background: '#333',
                marginLeft: 2,
                animation: 'blink 0.8s infinite',
              }} />}
            </div>

            {/* 引用来源按钮 */}
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
              <div style={{ marginTop: 8 }}>
                <SourcePopover sources={msg.sources} />
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* 输入框 */}
      <div style={{
        padding: '12px 0 20px',
        borderTop: '1px solid #eee',
      }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题，按 Enter 发送..."
            disabled={streaming}
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid #ddd',
              fontSize: 15,
              outline: 'none',
            }}
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              border: 'none',
              background: streaming ? '#ccc' : '#3355cc',
              color: '#fff',
              fontSize: 15,
              cursor: streaming ? 'not-allowed' : 'pointer',
            }}
          >
            {streaming ? '思考中...' : '发送'}
          </button>
        </div>
      </div>

      {/* 闪烁动画 */}
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend
npx tsc --noEmit
```
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/
git commit -m "Task 11: ChatPanel + SourcePopover 组件"
```

---

### Task 12: App 根组件 + React 入口 + 样式

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: 写 App.tsx**

`frontend/src/App.tsx`:
```tsx
import { ChatPanel } from './components/ChatPanel';

export default function App() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部栏 */}
      <header style={{
        height: 52,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: '1px solid #e8e8e8',
        background: '#fff',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 18 }}>📋</span>
          <span style={{ fontWeight: 600, fontSize: 16 }}>RAG 企业制度问答</span>
        </div>
        <div style={{ fontSize: 12, color: '#999' }}>
          基于 DeepSeek + BGE + ChromaDB
        </div>
      </header>

      {/* 聊天区域 */}
      <main style={{ flex: 1, overflow: 'hidden' }}>
        <ChatPanel />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: 写 main.tsx**

`frontend/src/main.tsx`:
```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 3: 写 index.css**

`frontend/src/index.css`:
```css
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial,
    sans-serif;
  font-size: 14px;
  color: #333;
  background: #fafafa;
}
```

- [ ] **Step 4: 验证前端能启动**

```bash
cd frontend
npx vite --host 0.0.0.0
```
Expected: `VITE ready in xxx ms` ➜ `http://localhost:5173/`

- [ ] **Step 5: TypeScript 编译检查**

```bash
npx tsc --noEmit
```
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx frontend/src/index.css
git commit -m "Task 12: App 根组件 + React 入口 + 全局样式"
```

---

### Task 13: 端到端集成测试

**验证目标:** 后端摄入文档 → curl 发请求 → 收到 SSE 流式回答 → 前端页面正常渲染

- [ ] **Step 1: 确认 .env 已配置**

```bash
cd backend
cat .env
```
确认 `DEEPSEEK_API_KEY` 不是占位符，是真 key。

- [ ] **Step 2: 启动后端**

```bash
cd backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000
```
等看到 `Pipeline 已就绪` 后继续。

- [ ] **Step 3: 摄入文档**

```bash
curl -X POST http://localhost:8000/api/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "../data/documents/员工手册.md", "category": "员工手册"}'
```
Expected: `{"ingested": N}`（N > 0）
> 注：如果启动时已在 lifespan 中自动摄入，可跳过此步。此处为独立验证。

- [ ] **Step 4: curl 测试 SSE 问答**

```bash
curl -N -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"question": "年假怎么申请"}'
```
Expected: 逐 token 流式输出，末尾收到 `event: sources` + `event: done`

- [ ] **Step 5: 启动前端，浏览器验证**

```bash
cd frontend
npx vite --host 0.0.0.0
```
打开 `http://localhost:5173`，输入"年假怎么申请"，确认：
1. ✅ 回答逐字流式出现
2. ✅ 回答结束后出现 📎 引用来源按钮
3. ✅ 点击引用来源按钮弹出原文浮窗
4. ✅ 输入"今天天气怎么样"——应回答知识库无相关内容

- [ ] **Step 6: Commit + 推送**

```bash
git add -A
git commit -m "Task 13: 集成测试验证通过"
# 推送前替换 $GH_TOKEN 为实际值，推完擦除
git remote set-url origin https://jjrick62:$GH_TOKEN@github.com/jjrick62/rag-enterprise-qa.git
git push
git remote set-url origin https://github.com/jjrick62/rag-enterprise-qa.git
```

> ⚠️ `$GH_TOKEN` 需在执行前替换为实际 GitHub Personal Access Token，推完立即擦除 remote URL 中的 token。

---

## ✅ 全部 13 个 Task 编写完毕

MVP 文件清单对照：

| # | 文件 | Task | 状态 |
|---|------|------|------|
| 1 | `backend/requirements.txt` | 1 | ✅ |
| 2 | `backend/.env.example` | 1 | ✅ |
| 3 | `backend/config.py` | 1 | ✅ |
| 4 | `backend/schemas/chat.py` | 1 | ✅ |
| 5 | `backend/services/base.py` | 2 | ✅ |
| 6 | `backend/services/parser.py` | 3 | ✅ |
| 7 | `backend/services/chunker.py` | 3 | ✅ |
| 8 | `backend/services/embedder.py` | 4 | ✅ |
| 9 | `backend/services/retriever.py` | 4 | ✅ |
| 10 | `backend/services/prompts.py` | 5 | ✅ |
| 11 | `backend/services/generator.py` | 5 | ✅ |
| 12 | `backend/services/pipeline.py` | 6 | ✅ |
| 13 | `backend/routers/chat.py` | 7 | ✅ |
| 14 | `backend/main.py` | 7 | ✅ |
| 15 | `data/documents/员工手册.md` | 8 | ✅ |
| 16 | `frontend/package.json` 等配置文件 | 9 | ✅ |
| 17 | `frontend/src/types/index.ts` | 9 | ✅ |
| 18 | `frontend/src/core/EventEmitter.ts` | 10 | ✅ |
| 19 | `frontend/src/core/ChatClient.ts` | 10 | ✅ |
| 20 | `frontend/src/components/SourcePopover.tsx` | 11 | ✅ |
| 21 | `frontend/src/components/ChatPanel.tsx` | 11 | ✅ |
| 22 | `frontend/src/App.tsx` | 12 | ✅ |
| 23 | `frontend/src/main.tsx` | 12 | ✅ |
| 24 | `frontend/src/index.css` | 12 | ✅ |
| 25 | `backend/tests/test_chunker.py` | 3 | ✅ |
| 26 | `backend/tests/test_embedder.py` | 4 | ✅ |
| 27 | `frontend/src/core/__tests__/EventEmitter.test.ts` | 10 | ✅ |
> **归档说明（2026-06-06）**：这是历史实施计划，不代表当前待办。
