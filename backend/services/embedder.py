"""嵌入器——BGE 模型封装

将自然语言文本转为稠密数值向量。语义相近的文本，其向量在空间中距离也近。
"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from services.base import BaseEmbedder


class BGEBaaIEmbedder(BaseEmbedder):
    """BAAI/bge-small-zh-v1.5 本地嵌入器

    使用 sentence-transformers 库加载模型，支持 CPU/CUDA 推理。

    为什么 normalize_embeddings=True？
      归一化后向量点积等价于余弦相似度，ChromaDB 用余弦距离时
      计算结果更准确，且向量比较时只需点积，速度快。
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu"):
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        self._dimension = self._model.get_embedding_dimension()

    def embed(self, texts: List[str]) -> "np.ndarray":
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,   # L2 归一化，等价于余弦相似度
            show_progress_bar=False,
        )
        return np.array(embeddings, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension
