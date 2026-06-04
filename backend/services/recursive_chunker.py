"""递归语义分块器——按标题层级递归切分

策略（三级降级）：
  1. 优先按 Markdown 标题层级切（# → ## → ###）
  2. 节超过 chunk_size 且无子标题 → 按句子精切
  3. overlap 动态计算：min(chunk_size × overlap_ratio, max_overlap)
"""
import re
from typing import List, Tuple
from services.base import BaseChunker
from schemas.chat import Chunk, ChunkMetadata


class RecursiveChunker(BaseChunker):
    """递归语义分块器

    跟 FixedChunker 的区别：
      - FixedChunker：固定窗口滑动，不管断在哪（粗暴但简单）
      - RecursiveChunker：标题边界 → 句子边界，断点始终在语义完整处
    """

    # 中英文分句：句号、感叹号、问号、换行后断开
    SENTENCE_PATTERN = re.compile(r'(?<=[。！？.!?\n])\s*')

    def __init__(
        self,
        chunk_size: int = 500,
        overlap_ratio: float = 0.15,
        max_overlap: int = 50,
    ):
        if not (0 < overlap_ratio < 1):
            raise ValueError(f"overlap_ratio 必须在 (0, 1)，收到 {overlap_ratio}")
        self.chunk_size = chunk_size
        self.overlap_ratio = overlap_ratio
        self.max_overlap = max_overlap

    # ── 入口 ──

    def chunk(self, text: str, category: str, source_doc: str) -> List[Chunk]:
        if not text or not text.strip():
            return []
        sections = self._parse_heading_tree(text)
        chunks: List[Chunk] = []
        index = 0

        for section_text, heading_stack in sections:
            sub_chunks = self._chunk_section(
                section_text, heading_stack, source_doc, category
            )
            for c in sub_chunks:
                chunks.append(Chunk(
                    content=c.content,
                    metadata=ChunkMetadata(
                        source_doc=source_doc,
                        category=category,
                        page_number=0,
                        heading_stack=list(c.metadata.heading_stack),
                        char_start=-1,  # 递归切分后字符位置不可靠
                        char_end=-1,
                    ),
                    chunk_index=index,
                ))
                index += 1

        return chunks

    # ── 标题树解析 ──

    def _parse_heading_tree(self, text: str) -> List[Tuple[str, List[str]]]:
        """解析 Markdown 为节列表

        返回: [(section_text, heading_stack), ...]
          如 [("## 1.1 里的内容...", ["# 第一章", "## 1.1"]), ...]

        原理：
          找到所有 # 标题的位置 → 相邻标题之间的文本就是一个"节"
          → 每个节的 heading_stack 是从根到当前标题的完整路径
        """
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        if not matches:
            # 全文无标题 → 整篇作为一个节
            return [(text, [])]

        sections: List[Tuple[str, List[str]]] = []
        stack: List[Tuple[int, str]] = []  # [(层级, 标题文本), ...]

        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # 弹出栈中 >= 当前层级的标题（h2 出现时，旧的 h2/h3 出栈）
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading_text))

            # 节文本：当前标题之后 → 下一个标题之前（或文本末尾）
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()

            if section_text:
                current_stack = [h for _, h in stack]
                sections.append((section_text, current_stack))

        # 第一个标题之前的前言文本
        if matches and matches[0].start() > 0:
            pre_text = text[:matches[0].start()].strip()
            if pre_text:
                sections.insert(0, (pre_text, []))

        return sections

    # ── 递归切分 ──

    def _chunk_section(
        self, text: str, heading_stack: List[str],
        source_doc: str, category: str,
    ) -> List[Chunk]:
        """递归切分一个节

        决策树：
          - 文本 ≤ chunk_size → 直接成块
          - 文本 > chunk_size 且有子标题 → 递归切子节
          - 文本 > chunk_size 且无子标题 → 按句子精切
        """
        if len(text) <= self.chunk_size:
            return [self._make_chunk(text, heading_stack)]

        # 尝试按子标题继续切
        sub_sections = self._parse_heading_tree(text)
        if len(sub_sections) > 1:
            result: List[Chunk] = []
            for sub_text, sub_stack in sub_sections:
                merged_stack = heading_stack + sub_stack
                result.extend(
                    self._chunk_section(sub_text, merged_stack, source_doc, category)
                )
            return result

        # 没有子节——按句子精切
        return self._chunk_by_sentences(text, heading_stack)

    # ── 句子级精切 ──

    def _chunk_by_sentences(
        self, text: str, heading_stack: List[str],
    ) -> List[Chunk]:
        """按句子切分，尽量接近 chunk_size 但不截断句子"""
        sentences = [s.strip() for s in self.SENTENCE_PATTERN.split(text) if s.strip()]
        if not sentences:
            return [self._make_chunk(text, heading_stack)]

        chunks: List[Chunk] = []
        current = ""
        overlap_size = min(int(self.chunk_size * self.overlap_ratio), self.max_overlap)

        for sent in sentences:
            if len(current) + len(sent) > self.chunk_size and current:
                # 当前块满了，保存
                chunks.append(self._make_chunk(current, heading_stack))

                # overlap：从上一块末尾取 overlap_size 字符作为上下文的种子
                if len(current) > overlap_size:
                    current = current[-overlap_size:] + sent
                else:
                    current = sent
            else:
                current = (current + " " + sent).strip() if current else sent

        if current:
            chunks.append(self._make_chunk(current, heading_stack))

        return chunks

    # ── 工厂方法 ──

    def _make_chunk(self, content: str, heading_stack: List[str]) -> Chunk:
        """创建临时 Chunk——char 位置和 index 由外层统一设置"""
        return Chunk(
            content=content,
            metadata=ChunkMetadata(
                source_doc="",       # 外层填
                category="",          # 外层填
                page_number=0,
                heading_stack=list(heading_stack),
                char_start=-1,
                char_end=-1,
            ),
            chunk_index=-1,           # 外层统一编号
        )
