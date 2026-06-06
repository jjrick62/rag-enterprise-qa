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
            # 全文无 Markdown 标题 → 尝试 IBM 文档格式（纯文本标题）
            ibm_sections = self._detect_ibm_headings(text)
            if ibm_sections:
                return ibm_sections
            # 毫无标题线索 → 整篇作为一个节
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

    # ── IBM 纯文本文档标题检测（无 # Markdown 标题时的 fallback）──

    # IBM watsonx 文档典型格式：
    #   第一行：﻿ 文档标题（可能带 BOM ﻿ 和前导空格）
    #   小节：短行，前后有空行隔开，可能缩进，可能以 : 结尾
    #   定义列表：Term\n:   Definition（Term 不是标题，后面紧跟 : 行）
    _IBM_HEADING_CANDIDATE = re.compile(
        r'^(?:\s{0,4})(?![-*\d]+\s|```|http|:)(.{1,80})$'
    )
    _IBM_DEF_LIST_NEXT = re.compile(r'^\s*:\s{2,}')

    def _detect_ibm_headings(self, text: str) -> List[Tuple[str, List[str]]]:
        """检测 IBM 纯文本格式的标题结构

        规则（顺序）：
          1. 第一非空行 → 文档标题（去除 BOM 和前导空格）
          2. 后续的短行（≤80 字），前后有空行 → 视为小节标题
          3. 排除：列表项（- * 1.）、代码块、URL、IBM 定义列表的 Term 行

        Returns:
            与 _parse_heading_tree 同格式：[(section_text, heading_stack), ...]
        """
        lines = text.split('\n')
        if not lines:
            return []

        # Step 1: 提取文档标题
        title = ""
        title_line_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip().lstrip('﻿')
            if stripped:
                title = stripped[:80]
                title_line_idx = i
                break

        if not title:
            return []

        # Step 2: 扫描后续行，找小节标题候选
        # 候选条件：短行、非列表/代码/链接、前面是空行（或标题行）、
        #           后面不是 IBM 定义列表的 : 行
        section_boundaries = []  # [(line_idx, heading_text), ...]

        for i in range(title_line_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            if len(stripped) > 80:
                continue
            # 排除列表/代码/链接/URL/表格标题/表格数据行
            if re.match(r'^[-*]\s|^\d+[\.\)]|^```|^http|^\[|^\(', stripped):
                continue
            if self._TABLE_TITLE_PATTERN.match(stripped):
                continue
            # 排除伪表行（被连续空格拆出 ≥3 个字段 → 是数据行，不是标题）
            row_fields = [f for f in self._TABLE_ROW_PATTERN.split(stripped) if f]
            if len(row_fields) >= 3:
                continue
            # 排除明显的句子：以句号结尾 → 正文（除非有强标题信号）
            words = stripped.split()
            if stripped.endswith('.'):
                # 有缩进或冒号 → 可能是特殊格式标题，放行
                if not (line.startswith(' ') or ':' in stripped):
                    continue
            # 排除常见句子开头（≥4 词 → 完整句子）
            if re.match(r'^(The|A|An|This|These|It|They|You|We|To|In|For|With|If|When|After|Before)\s', stripped) and len(words) >= 4:
                continue
            # 前一行是空行（或就是标题行）
            prev_is_blank = i == 0 or not lines[i-1].strip()
            if not prev_is_blank:
                continue
            # 后一行不是 IBM 定义列表的 :  定义行
            if i + 1 < len(lines):
                next_line = lines[i+1]
                if self._IBM_DEF_LIST_NEXT.match(next_line):
                    continue
            # 后一行不是冒号开头（宽松匹配）
            if i + 1 < len(lines) and lines[i+1].strip().startswith(':'):
                continue

            # 通过所有检查 → 小节标题
            section_boundaries.append((i, stripped))

        # Step 3: 按边界切分文本
        if not section_boundaries:
            # 无小节标题 → 整篇为一个节，heading_stack = [文档标题]
            return [(text, [title])]

        result = []
        for j, (start_idx, heading) in enumerate(section_boundaries):
            # 从标题行开始（含），到下一个标题行之前
            end_idx = section_boundaries[j+1][0] if j + 1 < len(section_boundaries) else len(lines)
            section_text = '\n'.join(lines[start_idx:end_idx]).strip()
            if section_text:
                result.append((section_text, [title, heading]))

        return result if result else [(text, [title])]

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
            # 即使小段也查表——避免 IBM 标题检测把表单独切走后跳过表处理
            regions = self._detect_table_regions(text)
            if regions:
                chunks: List['Chunk'] = []
                pos = 0
                for region in regions:
                    if region['start_char'] > pos:
                        pre = text[pos:region['start_char']].strip()
                        if pre:
                            chunks.append(self._make_chunk(pre, heading_stack))
                    chunks.extend(self._chunk_table(
                        region, heading_stack, source_doc, category,
                    ))
                    pos = region['end_char']
                if pos < len(text):
                    post = text[pos:].strip()
                    if post:
                        chunks.append(self._make_chunk(post, heading_stack))
                return chunks
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
        return self._chunk_by_sentences(
            text,
            heading_stack,
            source_doc,
            category,
        )

    # ── 伪表格检测与转换 ──

    # 空格对齐伪表的行模式：一行被 ≥2 个连续空格切出 ≥3 个字段
    _TABLE_ROW_PATTERN = re.compile(r'\s{2,}')
    _TABLE_TITLE_PATTERN = re.compile(r'^Table\s*\d*:')

    def _detect_table_regions(self, text: str) -> List[dict]:
        """检测空格对齐伪表格区域

        工业参照：RAG-Architect Table Guard + Unstructured.io element detection。
        思路：逐行扫描，找到"连续≥3行的双空格多字段行"= 一个表。

        Returns: [{'start_char': int, 'end_char': int, 'lines': [str]}, ...]
        """
        lines = text.split('\n')
        regions: List[dict] = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            # 跳过空行和代码块
            if not stripped or stripped.startswith('```'):
                i += 1
                continue

            fields = self._TABLE_ROW_PATTERN.split(stripped)
            is_title = bool(self._TABLE_TITLE_PATTERN.match(stripped))
            n_fields = len([f for f in fields if f])  # 非空字段数

            if is_title or n_fields >= 3:
                start_i = i
                table_rows: List[str] = []

                # 收集 "Table N:" 标题行
                if is_title:
                    table_rows.append(stripped)
                    i += 1
                    # 跳过表头后的空行
                    if i < len(lines) and not lines[i].strip():
                        i += 1

                # 收数据行：每行 ≥3 字段，遇空行跳过、遇非表行停
                while i < len(lines):
                    row = lines[i].strip()
                    if not row:
                        i += 1
                        # 表内允许空行（如列名和首行数据之间的空行），
                        # 检查下一行是否还是表行，是就继续，不是才结束
                        if i < len(lines):
                            next_row = lines[i].strip()
                            next_fields = [f for f in self._TABLE_ROW_PATTERN.split(next_row) if f]
                            if len(next_fields) >= 3:
                                continue  # 跳过空行，继续收表数据
                        break
                    row_fields = [f for f in self._TABLE_ROW_PATTERN.split(row) if f]
                    if len(row_fields) >= 3:
                        table_rows.append(row)
                        i += 1
                    else:
                        break

                # 有效的表：标题/表头 + ≥2 行数据
                if len(table_rows) >= 3:
                    char_start = sum(len(ln) + 1 for ln in lines[:start_i])
                    char_end = sum(len(ln) + 1 for ln in lines[:i])
                    regions.append({
                        'start_char': char_start,
                        'end_char': char_end,
                        'lines': table_rows,
                    })
                continue  # 跳过 i+=1——while 循环内已推进

            i += 1

        return regions

    def _convert_pseudo_table(self, lines: List[str], title: str = "") -> str:
        """空格对齐伪表 → 紧凑 key-value 文本

        策略：
          - 只取前3列（参数名+可选值+默认值），丢弃 URL 列
          - 注入表标题（如 "Table 1: Tuning parameters"）让 BM25 可命中
          - 格式：一行一个参数，LLM 和 BM25 都友好
        """
        # 分离标题行和数据行
        title_line = ""
        data_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if self._TABLE_TITLE_PATTERN.match(stripped):
                title_line = stripped
                data_start = i + 1
                break

        rows: List[List[str]] = []
        for line in lines[data_start:]:
            fields = [f.strip() for f in self._TABLE_ROW_PATTERN.split(line) if f.strip()]
            if fields:
                rows.append(fields)

        if not rows:
            return '\n'.join(lines)

        col_names = rows[0]
        result_lines: List[str] = []
        if title_line:
            result_lines.append(title_line)
        elif title:
            result_lines.append(title)

        for row in rows[1:]:
            # 只取前3列：参数名、可选值、默认值（跳过 URL）
            name = row[0] if len(row) > 0 else ''
            options = row[1] if len(row) > 1 else ''
            default = row[2] if len(row) > 2 else ''
            if default:
                result_lines.append(f'- {name}: {options} (default: {default})')
            elif options:
                result_lines.append(f'- {name}: {options}')
            else:
                result_lines.append(f'- {name}')

        return '\n'.join(result_lines)

    def _chunk_table(
        self,
        table_info: dict,
        heading_stack: List[str],
        source_doc: str,
        category: str,
    ) -> List['Chunk']:
        """表转为 chunk——优先整表，超 chunk_size 才按行组拆"""
        md_table = self._enrich_table_text(
            self._convert_pseudo_table(table_info['lines']),
            table_info,
            heading_stack,
            source_doc,
            category,
        )

        # 表允许 3x 容差——表是单一语义单元，embedding 稀释远低于等长随机文本
        # 1227 字符的 6 行参数表一个 chunk 装下 > 拆成 6 个碎片
        if len(md_table) <= max(self.chunk_size * 3, 1500):
            return [self._make_chunk(md_table, heading_stack)]

        # 大表兜底：按行组拆分，每组带表头
        header_lines = table_info['lines'][:2]  # "Table N:" + 列名行
        chunks: List['Chunk'] = []
        batch = list(header_lines)
        for row in table_info['lines'][2:]:
            test = self._enrich_table_text(
                self._convert_pseudo_table(batch + [row]),
                table_info,
                heading_stack,
                source_doc,
                category,
            )
            if len(test) <= self.chunk_size:
                batch.append(row)
            else:
                chunks.append(self._make_chunk(
                    self._enrich_table_text(
                        self._convert_pseudo_table(batch),
                        table_info,
                        heading_stack,
                        source_doc,
                        category,
                    ),
                    heading_stack,
                ))
                batch = list(header_lines) + [row]
        if len(batch) > len(header_lines):
            chunks.append(self._make_chunk(
                self._enrich_table_text(
                    self._convert_pseudo_table(batch),
                    table_info,
                    heading_stack,
                    source_doc,
                    category,
                ),
                heading_stack,
            ))
        return chunks

    def _enrich_table_text(
        self,
        table_text: str,
        table_info: dict,
        heading_stack: List[str],
        source_doc: str,
        category: str,
    ) -> str:
        """用已有元数据为表格补充稳定、可检索的语义上下文。"""
        document_title = re.sub(
            r'\s+',
            ' ',
            re.sub(r'\.[^.]+$', '', source_doc).replace('_', ' '),
        ).strip()
        category_label = category.replace('_', ' ').strip()

        table_title = ""
        for line in table_info['lines']:
            stripped = line.strip()
            if self._TABLE_TITLE_PATTERN.match(stripped):
                table_title = self._TABLE_TITLE_PATTERN.sub(
                    '',
                    stripped,
                ).strip()
                break

        context_lines = [f"Document: {document_title}"]
        if category_label:
            context_lines.append(f"Category: {category_label}")
        if heading_stack:
            context_lines.append(f"Section: {' > '.join(heading_stack)}")
        if table_title:
            context_lines.append(
                f"Table context: {table_title} from {document_title}"
            )

        return '\n'.join(context_lines + [table_text])

    # ── 句子级精切 ──

    def _chunk_by_sentences(
        self,
        text: str,
        heading_stack: List[str],
        source_doc: str,
        category: str,
    ) -> List[Chunk]:
        """按句子切分，表区域先提取保护，非表部分句子切"""
        # Step 1: 检测并提取表区域
        regions = self._detect_table_regions(text)

        if not regions:
            # 无表——走原句子切分逻辑
            return self._sentence_chunk(text, heading_stack)

        # 有表——按表区域把文本切成"非表+表+非表..."
        chunks: List['Chunk'] = []
        pos = 0
        for region in regions:
            # 表之前的非表部分 → 句子切
            if region['start_char'] > pos:
                pre = text[pos:region['start_char']].strip()
                if pre:
                    chunks.extend(self._sentence_chunk(pre, heading_stack))
            # 表部分 → 整表保护
            chunks.extend(self._chunk_table(
                region,
                heading_stack,
                source_doc,
                category,
            ))
            pos = region['end_char']

        # 最后一段非表文本
        if pos < len(text):
            post = text[pos:].strip()
            if post:
                chunks.extend(self._sentence_chunk(post, heading_stack))

        return chunks

    def _sentence_chunk(
        self, text: str, heading_stack: List[str],
    ) -> List['Chunk']:
        """纯句子切分——原 _chunk_by_sentences 的核心逻辑"""
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
