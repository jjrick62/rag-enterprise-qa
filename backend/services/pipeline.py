"""RAG Pipeline 编排器——Builder 模式组装五层组件

Builder 模式的好处：
  1. 逐步注入依赖，构造函数不会出现 5 个参数的长列表
  2. build() 时校验完整性——缺任何一层直接报错，不会跑到一半才发现
  3. Pipeline 构造后不可变（字段私有），运行时组件不会被意外替换
"""
import os
from typing import Optional, AsyncIterator
from services.base import (
    BaseParser, BaseChunker, BaseEmbedder,
    BaseRetriever, BaseGenerator, BaseReranker,
)
from services.query_rewriter import QueryRewriter
from schemas.chat import GenerateEvent


class RAGPipelineBuilder:
    """Builder——逐步注入依赖，最后 build() 返回不可变 Pipeline"""

    def __init__(self):
        self._parser: Optional[BaseParser] = None
        self._chunker: Optional[BaseChunker] = None
        self._embedder: Optional[BaseEmbedder] = None
        self._retriever: Optional[BaseRetriever] = None
        self._generator: Optional[BaseGenerator] = None
        self._reranker: Optional[BaseReranker] = None  # 可选——不加 Reranker 也能跑
        self._rewriter: Optional[QueryRewriter] = None  # 可选——Query 改写

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

    def with_reranker(self, reranker: BaseReranker) -> "RAGPipelineBuilder":
        self._reranker = reranker
        return self

    def with_rewriter(self, rewriter: QueryRewriter) -> "RAGPipelineBuilder":
        self._rewriter = rewriter
        return self

    def build(self) -> "RAGPipeline":
        # 校验：五层核心组件缺一不可，Reranker 可选
        missing = []
        for name, val in [
            ("parser", self._parser), ("chunker", self._chunker),
            ("embedder", self._embedder), ("retriever", self._retriever),
            ("generator", self._generator),
        ]:
            if val is None:
                missing.append(name)
        if missing:
            raise ValueError(f"缺少组件: {', '.join(missing)}")
        return RAGPipeline(
            parser=self._parser,        # type: ignore[arg-type]
            chunker=self._chunker,      # type: ignore[arg-type]
            embedder=self._embedder,    # type: ignore[arg-type]
            retriever=self._retriever,  # type: ignore[arg-type]
            generator=self._generator,  # type: ignore[arg-type]
            reranker=self._reranker,    # 可选
            rewriter=self._rewriter,    # 可选
        )


class RAGPipeline:
    """编排器——组合五层组件，暴露 ingest / query 两个入口

    数据流：
      ingest:  文件 → parse → chunk → embed → ChromaDB
      query:   问题 → embed → search → generate (stream)
    """

    def __init__(
        self,
        parser: BaseParser,
        chunker: BaseChunker,
        embedder: BaseEmbedder,
        retriever: BaseRetriever,
        generator: BaseGenerator,
        reranker: Optional[BaseReranker] = None,
        rewriter: Optional[QueryRewriter] = None,
    ):
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._retriever = retriever
        self._generator = generator
        self._reranker = reranker
        self._rewriter = rewriter

    @classmethod
    def builder(cls) -> RAGPipelineBuilder:
        return RAGPipelineBuilder()

    async def ingest(self, file_path: str, category: str) -> int:
        """文档摄入：解析 → 分块 → Embedding → 入库

        Args:
            file_path: 文档路径
            category: 文档分类（"员工手册"、"IT规范" 等）

        Returns:
            入库的 chunk 数量
        """
        source_doc = os.path.basename(file_path)
        text = self._parser.parse(file_path)
        chunks = self._chunker.chunk(text, category=category, source_doc=source_doc)
        if not chunks:
            return 0
        texts = [c.content for c in chunks]
        embeddings = self._embedder.embed(texts)
        count = self._retriever.add_embeddings(chunks, embeddings)
        return count

    async def query(
        self,
        question: str,
        category_filter: Optional[str] = None,
    ) -> AsyncIterator[GenerateEvent]:
        """检索 + 生成，流式返回

        Args:
            question: 用户问题
            category_filter: 可选，限定检索的文档类别

        Yields:
            GenerateEvent —— token / sources / done
        """
        # Query 改写——中文→英文，口语→术语
        search_query = question
        if self._rewriter:
            search_query = await self._rewriter.rewrite(question)

        query_embedding = self._embedder.embed([search_query])[0]

        # 有 Reranker → 粗召 20 个候选人 → 精排取 5
        # 无 Reranker → 直接取 5
        top_k = 20 if self._reranker else 5

        results = self._retriever.search(
            query_embedding=query_embedding,
            top_k=top_k,
            category_filter=category_filter,
        )

        if self._reranker:
            results = self._reranker.rerank(question, results, top_k=5)

        async for event in self._generator.generate(question, results):
            yield event
