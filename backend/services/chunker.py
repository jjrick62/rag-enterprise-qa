"""文本分块器实现

切分策略：固定窗口滑动 + overlap。overlap 防止关键句恰好落在两个 chunk 边界上被切断。
"""
import re
from typing import List
from services.base import BaseChunker
from schemas.chat import Chunk, ChunkMetadata


class FixedChunker(BaseChunker):
    """固定窗口分块器——按字符数滑动窗口切分

    为什么不用 token 数切分？
      MVP 阶段先简单处理。字符数对中文大致公平（1 字符 ≈ 1 token），
      后续可以升级为 SemanticChunker 按语义边界切。
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) 必须小于 chunk_size ({chunk_size})")
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

            # 到达文本末尾，退出
            if end == len(text):
                break

            # 滑动窗口：下一个 chunk 的起始 = 当前结束 - overlap
            start = end - self.overlap

        return chunks

    def _find_nearest_heading(self, text: str, position: int) -> str:
        """向上查找距离 position 最近的 Markdown 标题

        用 finditer 遍历全文所有标题，记录每个标题的位置，
        返回 position 之前（或恰好在 position 处）的最后一个标题。

        示例：
          位置 0: "# 第一章" → 返回 "第一章 考勤制度"
          位置 150（在 ## 1.2 之后）→ 返回 "1.2 迟到处理"
        """
        last_heading = ""
        for match in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
            if match.start() <= position:
                last_heading = match.group(1)
            else:
                break  # 后面的标题都在 position 之后，不用找了
        return last_heading
