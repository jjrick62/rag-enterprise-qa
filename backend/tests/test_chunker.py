"""FixedChunker 单元测试

测试覆盖：
  1. 能正确返回 Chunk 列表
  2. metadata 携带正确的 category 和 source_doc
  3. chunk_index 连续递增
  4. overlap 生效（相邻 chunk 有内容重叠）
  5. heading 检测正确
  6. 每个 chunk 不超过 chunk_size
"""
import pytest
from services.chunker import FixedChunker

# 模拟一份企业制度文档
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

    def test_returns_list_of_chunks(self):
        """切分后返回的是 Chunk 列表，且非空"""
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_metadata_has_category(self):
        """每个 Chunk 的 metadata 必须包含正确的 category 和 source_doc"""
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for chunk in result:
            assert chunk.metadata.category == "员工手册"
            assert chunk.metadata.source_doc == "员工手册.md"

    def test_chunk_indices_sequential(self):
        """chunk_index 从 0 开始连续递增"""
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunk_overlap(self):
        """相邻 chunk 在原文中有重叠——前一块末尾位置 > 后一块起始位置"""
        chunker = FixedChunker(chunk_size=200, overlap=50)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        if len(result) >= 2:
            # 后一块的 char_start 应该在前一块的 char_end 之前（重叠）
            assert result[1].metadata.char_start < result[0].metadata.char_end

    def test_heading_detection(self):
        """第一个 chunk 能检测到最近的标题"""
        chunker = FixedChunker(chunk_size=200, overlap=30)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        assert result[0].metadata.heading_stack[-1] == "第一章 考勤制度"

    def test_chunk_size_limit(self):
        """每个 chunk 的内容长度不超过 chunk_size"""
        chunker = FixedChunker(chunk_size=100, overlap=10)
        result = chunker.chunk(SAMPLE_TEXT, "员工手册", "员工手册.md")
        for chunk in result:
            assert len(chunk.content) <= 100, (
                f"chunk {chunk.chunk_index} 长度 {len(chunk.content)} > 100"
            )
