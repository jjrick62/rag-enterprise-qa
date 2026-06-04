"""检索器——ChromaDB 封装

ChromaDB 是一个嵌入式向量数据库，数据直接存在本地文件系统。
不需要额外部署服务器，适合 demo 和小规模场景。
"""
from typing import List, Optional
import uuid
import chromadb
from chromadb.config import Settings
from services.base import BaseRetriever, BaseEmbedder
from schemas.chat import Chunk, ChunkMetadata, RetrievalResult


class ChromaRetriever(BaseRetriever):
    """基于 ChromaDB 的向量检索器

    核心操作：
      add_embeddings  → 批量写入向量 + metadata
      search          → 相似度检索 Top-K，支持 category 过滤
      delete_by_document → 按文档名清理旧向量（重新入库前用）
    """

    def __init__(self, persist_path: str, embedder: BaseEmbedder):
        self._client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(
            name="enterprise_docs",
            metadata={"hnsw:space": "cosine"},  # 余弦距离
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

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            similarity = 1.0 - distance  # cosine distance → similarity

            chunk_meta = ChunkMetadata(
                source_doc=meta.get("source_doc", ""),
                category=meta.get("category", ""),
                page_number=meta.get("page_number", 0),
                heading_stack=meta.get("heading_stack", []),
                char_start=meta.get("char_start", 0),
                char_end=meta.get("char_end", 0),
            )

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
                "heading_stack": chunk.metadata.heading_stack,
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
