"""BGEBaaIEmbedder 单元测试

首次运行会自动从 HuggingFace 下载模型（约 100MB），需要网络。
"""
import pytest
import numpy as np
from services.embedder import BGEBaaIEmbedder


@pytest.fixture(scope="module")
def embedder():
    """模块级 fixture——模型只加载一次，5 个测试共享同一个实例"""
    return BGEBaaIEmbedder(device="cpu")


class TestBGEBaaIEmbedder:

    def test_embed_returns_float32_array(self, embedder):
        """返回值是 float32 的 numpy 数组"""
        result = embedder.embed(["测试文本"])
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    def test_embed_output_shape(self, embedder):
        """3 段文本 → shape (3, 512)"""
        texts = ["第一段文字", "第二段文字", "第三段文字"]
        result = embedder.embed(texts)
        assert result.shape == (3, embedder.dimension)

    def test_dimension_is_512(self, embedder):
        """bge-small-zh-v1.5 固定 512 维"""
        assert embedder.dimension == 512

    def test_embeddings_are_normalized(self, embedder):
        """L2 归一化后，向量长度接近 1.0"""
        result = embedder.embed(["测试"])
        norm = np.linalg.norm(result[0])
        assert abs(norm - 1.0) < 0.01

    def test_similar_texts_closer_than_dissimilar(self, embedder):
        """语义相近的文本，余弦相似度 > 不相关的文本"""
        a = embedder.embed(["年假怎么申请"])[0]
        b = embedder.embed(["员工休假流程"])[0]
        c = embedder.embed(["今天天气真好"])[0]
        sim_ab = np.dot(a, b)  # 归一化后点积 = 余弦相似度
        sim_ac = np.dot(a, c)
        assert sim_ab > sim_ac, (
            f"相似文本的相似度 ({sim_ab:.3f}) 应 > 不相关文本 ({sim_ac:.3f})"
        )
