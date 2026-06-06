"""RecursiveChunker 单元测试

覆盖：
  1. chunk 不超限
  2. heading_stack 完整层级保留
  3. 无标题长文本 → 句子精切
  4. 短节不切
  5. chunk_index 连续
  6. overlap 生效
  7. 空文本不报错
  8. 无标题短文本 → 单 chunk
"""
import pytest
from services.recursive_chunker import RecursiveChunker

# ── 测试数据 ──

DEEP_NESTED = """# 第一章

前言内容，简要介绍背景。

## 1.1 第一小节

这是第一小节的内容。包含多个句子。每个句子都是独立的。
还有一些补充说明。总共有五个句子。

## 1.2 第二小节

第二小节的内容同样丰富。
这里讨论了一些技术细节。
包括实现方式、性能考量、以及注意事项。
"""

FLAT_LONG = "这是没有标题的长文本。" + "它包含很多句子需要切分。" * 120

SHORT = "# 短节\n只有一句话。"

NO_HEADING = "这是普通文本。没有标题。单段内容。"

TUNING_TABLE = """Parameters for tuning foundation models

Parameter details

The parameters that you change when you tune a model are related to the tuning experiment.

Table 1: Tuning parameters

Parameter name                      Value options  Default value  Learn more

Initialization method               Random, Text   Random         link
Initialization text                 None           None           link
Batch size                          1 - 16         16             link
Accumulation steps                  1 - 128        16             link
Learning rate                       0.01 - 0.5     0.3            link
Number of epochs (training cycles)  1 - 50         20             link
"""


class TestRecursiveChunker:

    def test_chunk_size_limit(self):
        """每个 chunk 不超过 chunk_size"""
        c = RecursiveChunker(chunk_size=200)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        assert len(result) > 0
        for chunk in result:
            assert len(chunk.content) <= 200, (
                f"chunk {chunk.chunk_index} 长度 {len(chunk.content)} > 200"
            )

    def test_heading_stack_preserved(self):
        """递归切分后 heading_stack 包含完整层级"""
        c = RecursiveChunker(chunk_size=300)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        # 找到 1.2 节下的 chunk
        deep_chunks = [
            r for r in result
            if r.metadata.heading_stack
            and any("1.2" in h for h in r.metadata.heading_stack)
        ]
        assert len(deep_chunks) > 0, "应该有属于 1.2 节的 chunk"
        for chunk in deep_chunks:
            # heading_stack 应包含完整路径
            assert any("第一章" in h for h in chunk.metadata.heading_stack)

    def test_flat_text_split_by_sentences(self):
        """无标题的长文本按句子精切，且不超限"""
        c = RecursiveChunker(chunk_size=200)
        result = c.chunk(FLAT_LONG, "test", "test.md")
        assert len(result) > 1, "长文本应该被切分为多块"
        for chunk in result:
            assert len(chunk.content) <= 200

    def test_short_section_not_split(self):
        """短于 chunk_size 的节不被切分"""
        c = RecursiveChunker(chunk_size=500)
        result = c.chunk(SHORT, "test", "test.md")
        assert len(result) == 1

    def test_chunk_indices_sequential(self):
        """chunk_index 从 0 连续递增"""
        c = RecursiveChunker(chunk_size=200)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_overlap_between_neighbors(self):
        """相邻句子级 chunk 应有重叠内容"""
        c = RecursiveChunker(chunk_size=100, overlap_ratio=0.3, max_overlap=50)
        result = c.chunk(FLAT_LONG, "test", "test.md")
        found_overlap = False
        for i in range(len(result) - 1):
            tail = result[i].content[-20:]
            if tail in result[i + 1].content:
                found_overlap = True
                break
        assert found_overlap, "至少有相邻 chunk 存在重叠内容"

    def test_empty_text(self):
        """空文本返回空列表，不报错"""
        c = RecursiveChunker()
        result = c.chunk("", "test", "test.md")
        assert result == []

    def test_no_heading_text(self):
        """无标题短文本 → 单 chunk"""
        c = RecursiveChunker(chunk_size=500)
        result = c.chunk(NO_HEADING, "test", "test.md")
        assert len(result) == 1

    def test_table_chunk_includes_deterministic_document_context(self):
        c = RecursiveChunker(chunk_size=500)

        result = c.chunk(
            TUNING_TABLE,
            "IBM_Docs",
            "Parameters_for_tuning_foundation_models.md",
        )

        table_chunk = next(
            chunk for chunk in result
            if "Table 1: Tuning parameters" in chunk.content
        )
        assert (
            "Document: Parameters for tuning foundation models"
            in table_chunk.content
        )
        assert "Category: IBM Docs" in table_chunk.content
        assert (
            "Table context: Tuning parameters from "
            "Parameters for tuning foundation models"
            in table_chunk.content
        )

    def test_non_table_chunk_content_is_not_context_enriched(self):
        c = RecursiveChunker(chunk_size=500)

        result = c.chunk(NO_HEADING, "IBM_Docs", "ordinary_document.md")

        assert result[0].content == NO_HEADING
