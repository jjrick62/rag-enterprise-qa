"""对话相关数据实体——全部不可变"""
from dataclasses import dataclass
from typing import Optional, Literal
from pydantic import BaseModel


# ── 不可变值对象（dataclass） ──

@dataclass(frozen=True)
class ChunkMetadata:
    """每个 Chunk 的元信息——不可变，保证溯源可靠"""
    source_doc: str         # 来源文档文件名
    category: str           # 文档分类（员工手册/IT规范/...）
    page_number: int        # 在原文档中的页码（MD 为 0）
    heading_stack: list[str]  # 完整标题层级路径 ["# 第一章", "## 1.1"]
    char_start: int         # 在原文档中的起始字符位置
    char_end: int           # 在原文档中的结束字符位置


@dataclass(frozen=True)
class Chunk:
    """文档分块——RAG 检索的最小单元"""
    content: str
    metadata: ChunkMetadata
    chunk_index: int


@dataclass(frozen=True)
class RetrievalResult:
    """单条检索结果——Chunk + 相似度分数"""
    chunk: Chunk
    score: float          # cosine similarity [0, 1]


@dataclass(frozen=True)
class Source:
    """传给前端渲染引用卡片的轻量结构"""
    document_name: str
    heading: str
    excerpt: str          # 原文摘录，最多 200 字
    score: float


@dataclass(frozen=True)
class GenerateEvent:
    """生成器产出的三种事件之一"""
    type: Literal["token", "sources", "done"]
    content: Optional[str] = None            # type=token 时
    sources: Optional[list[Source]] = None   # type=sources 时


# ── 请求/响应模型（Pydantic） ──

class QueryRequest(BaseModel):
    """POST /api/chat/send 的请求体"""
    question: str
    category: Optional[str] = None
    session_id: str = "default"  # 多轮对话会话 ID，默认 "default"


class SSEResponse(BaseModel):
    """SSE 事件的标准化结构"""
    event: str   # "token" | "sources" | "done" | "error"
    data: str    # JSON string
