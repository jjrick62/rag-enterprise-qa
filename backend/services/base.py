"""抽象基类——定义 RAG Pipeline 五层接口契约

每个 ABC 只声明"必须有什么能力"，不关心"怎么实现"。
子类若不实现 @abstractmethod，实例化时会直接报 TypeError。

设计原则：
  - 依赖倒置：Pipeline 只依赖这些 ABC，不依赖具体类
  - 里氏替换：任何子类可以替换父类，行为一致
  - 接口隔离：每个 ABC 只定义最少必要方法
"""
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator
import numpy as np

# 延迟导入避免循环依赖——ABC 不依赖具体数据类
# 实际类型在 schemas/chat.py 中定义


class BaseParser(ABC):
    """解析器——原始文档文件 → 纯文本字符串

    职责单一：读文件，返回文本。不关心文本后续怎么处理。
    """

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """读取文档文件，返回纯文本字符串

        Args:
            file_path: 文档文件的绝对或相对路径

        Returns:
            去除格式后的纯文本内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...


class BaseChunker(ABC):
    """分块器——纯文本 → 语义块列表

    过长的文本不能直接塞给 LLM（上下文窗口限制 + 检索精度下降），
    需要切成小块。每个块携带 metadata 用于后续检索溯源。
    """

    @abstractmethod
    def chunk(self, text: str, category: str, source_doc: str) -> List["Chunk"]:
        """将文本切分为 Chunk 列表

        Args:
            text: 解析后的纯文本
            category: 文档分类标签（如"员工手册"）
            source_doc: 来源文件名

        Returns:
            Chunk 列表，每个 Chunk 包含内容和元信息
        """
        ...


class BaseEmbedder(ABC):
    """嵌入器——文本列表 → 向量矩阵

    将自然语言文本转为稠密数值向量，语义相近的文本向量距离也近。
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> "np.ndarray":
        """将文本列表转为向量矩阵

        Args:
            texts: 文本列表 ["第一段", "第二段", ...]

        Returns:
            shape (len(texts), dim) 的 float32 数组，L2 归一化
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量的维度，如 BGE-small 为 512"""
        ...


class BaseRetriever(ABC):
    """检索器——查询向量 → 相似文档块

    在向量数据库中搜索与查询最相似的 Top-K 个文档块。
    """

    @abstractmethod
    def search(
        self,
        query_embedding: "np.ndarray",
        top_k: int = 5,
        category_filter: Optional[str] = None,
    ) -> List["RetrievalResult"]:
        """根据查询向量检索最相似的 top_k 个 Chunk

        Args:
            query_embedding: 问题的嵌入向量 shape (dim,)
            top_k: 返回前 K 个结果
            category_filter: 可选，限定检索的文档类别

        Returns:
            按相似度降序排列的 RetrievalResult 列表
        """
        ...

    @abstractmethod
    def add_embeddings(self, chunks: List["Chunk"], embeddings: "np.ndarray") -> int:
        """批量存入向量数据库

        Args:
            chunks: 文档块列表
            embeddings: 对应的向量矩阵 shape (len(chunks), dim)

        Returns:
            写入数量
        """
        ...

    @abstractmethod
    def delete_by_document(self, source_doc: str) -> int:
        """删除指定文档的所有向量

        Args:
            source_doc: 文档文件名

        Returns:
            删除的向量数量
        """
        ...


class BaseReranker(ABC):
    """重排序器——对候选文档列表进行精排

    Embedding 检索用余弦相似度做粗排（速度快但不够精确），
    Reranker 用 Cross-encoder 做精排（把问题+文档拼一起做阅读理解）。

    流程位置：Retriever → Reranker → Generator
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List["RetrievalResult"],
        top_k: int = 5,
    ) -> List["RetrievalResult"]:
        """对候选列表精排，返回 Top-K

        Args:
            query: 用户原始问题
            candidates: 粗排后的候选列表
            top_k: 返回前 K 个

        Returns:
            按精排分数降序排列的 Top-K 结果，每个 score 字段已被 Reranker 覆盖
        """
        ...


class BaseGenerator(ABC):
    """生成器——问题 + 检索上下文 → 流式回答

    调用 LLM API，根据检索到的文档内容生成回答。
    流式返回（逐 token），前端可以实时渲染。
    """

    @abstractmethod
    async def generate(
        self,
        question: str,
        contexts: List["RetrievalResult"],
    ) -> AsyncIterator["GenerateEvent"]:
        """根据检索到的上下文生成回答

        Args:
            question: 用户原始问题
            contexts: 检索到的相关文档块（RetrievalResult 列表）

        Yields:
            GenerateEvent:
              - type="token"    → 回答的一个 token
              - type="sources"  → 所有引用来源（流结束后发）
              - type="done"     → 生成结束信号
        """
        ...
