# 递归语义分块 — 实现计划

> **日期**: 2026-06-04
> **目标**: 用 RecursiveChunker 替换 FixedChunker，按标题层级递归切分，超过阈值再按句子精切
> **依赖**: BaseChunker（已有）

---

### Task 1: 扩展 ChunkMetadata — 加 heading_stack 字段

**Files:**
- Modify: `backend/schemas/chat.py`

- [ ] **Step 1: 修改 ChunkMetadata**

`backend/schemas/chat.py` 中 `ChunkMetadata` 的 `heading: str` 字段改为 `heading_stack: list[str]`：

```python
@dataclass(frozen=True)
class ChunkMetadata:
    source_doc: str
    category: str
    page_number: int
    heading_stack: list[str]   # 曾是 heading: str，现在是完整层级路径
    char_start: int
    char_end: int
```

- [ ] **Step 2: 同步修改所有引用了 `heading` 的代码**

需要全局搜索 `metadata.heading` 或 `meta.heading` 并改为 `metadata.heading_stack[-1] if metadata.heading_stack else ""`：
- `backend/services/chunker.py` — FixedChunker 构造 metadata 处
- `backend/services/retriever.py` — ChromaRetriever 重建 ChunkMetadata 处
- `backend/services/generator.py` — DeepSeekGenerator 构建 Source 处
- `backend/services/prompts.py` — build_context_block 处
- `backend/routers/chat.py` — SSE sources 序列化处
- `backend/tests/test_chunker.py` — 所有 `chunk.metadata.heading` 断言

- [ ] **Step 3: 跑全部测试，确保旧代码兼容**

```bash
cd backend
venv\Scripts\activate
pytest tests/ -v
```
Expected: 11 passed（FixedChunker 用 `heading_stack` 替代 `heading` 后行为不变）

- [ ] **Step 4: ChromaDB list 字段兼容性验证（🔥 关键——chroma 的 metadata 是 JSON，存 list 进去读出来是否还是 list？）**

```bash
cd backend
venv\Scripts\activate
python -c "
import chromadb, uuid
c = chromadb.PersistentClient(path='../data/chroma_db')
col = c.get_or_create_collection('_compat_test')
col.add(
    ids=[str(uuid.uuid4())],
    documents=['test'],
    embeddings=[[0.1]*512],
    metadatas=[{'heading_stack': ['# A', '## B'], 'source_doc': 'test.md'}]
)
r = col.get(include=['metadatas'])
meta = r['metadatas'][0]
print(f'heading_stack type: {type(meta[\"heading_stack\"]).__name__}')
print(f'heading_stack value: {meta[\"heading_stack\"]}')
assert isinstance(meta['heading_stack'], list), 'FAIL: heading_stack 不是 list!'
print('PASS: ChromaDB 正确保留了 list 类型')
c.delete_collection('_compat_test')
"
```
Expected: `PASS: ChromaDB 正确保留了 list 类型`

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "ChunkMetadata: heading 改为 heading_stack (list[str])，全局同步修改"
```

---

### Task 2: 实现 RecursiveChunker 类

**Files:**
- Create: `backend/services/recursive_chunker.py`

- [ ] **Step 1: 写 RecursiveChunker**

`backend/services/recursive_chunker.py`：

```python
"""递归语义分块器——按标题层级递归切分"""
import re
from typing import List, Tuple
from services.base import BaseChunker
from schemas.chat import Chunk, ChunkMetadata


class RecursiveChunker(BaseChunker):
    """递归语义分块器

    策略：
      1. 解析 Markdown 标题树（# → ## → ### → ...）
      2. 从根节点递归：每个节如果 ≤ chunk_size 直接成块，
         否则按子标题继续切，还不够就按句子精切
      3. heading_stack 记录完整层级路径
      4. overlap 动态计算：min(chunk_size × overlap_ratio, max_overlap)
    """

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

    def chunk(self, text: str, category: str, source_doc: str) -> List[Chunk]:
        sections = self._parse_heading_tree(text)
        chunks: List[Chunk] = []
        index = 0

        for section_text, heading_stack in sections:
            sub_chunks = self._chunk_section(
                section_text, heading_stack, source_doc, category
            )
            for c in sub_chunks:
                # 重建 chunk 带上正确的全局 index
                chunks.append(Chunk(
                    content=c.content,
                    metadata=ChunkMetadata(
                        source_doc=source_doc,
                        category=category,
                        page_number=0,
                        heading_stack=c.metadata.heading_stack,
                        char_start=c.metadata.char_start,
                        char_end=c.metadata.char_end,
                    ),
                    chunk_index=index,
                ))
                index += 1

        return chunks

    def _parse_heading_tree(self, text: str) -> List[Tuple[str, List[str]]]:
        """解析 Markdown 文本为标题树

        返回: [(section_text, heading_stack), ...]
          如 [("## 1.1 的内容...", ["# 第一章", "## 1.1"]), ...]
        """
        # 找到所有标题的位置
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        if not matches:
            # 没有标题，整个文本作为一个节
            return [(text, [])]

        sections: List[Tuple[str, List[str]]] = []
        stack: List[Tuple[int, str]] = []  # [(level, heading_text), ...]

        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # 弹出栈中所有 >= 当前层级的标题
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading_text))

            # 确定本节文本范围
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()

            if section_text:
                current_stack = [h for _, h in stack]
                sections.append((section_text, current_stack))

        # 第一个标题之前的内容
        if matches:
            first_start = matches[0].start()
            if first_start > 0:
                pre_text = text[:first_start].strip()
                if pre_text:
                    sections.insert(0, (pre_text, []))

        return sections

    def _chunk_section(
        self, text: str, heading_stack: List[str],
        source_doc: str, category: str,
    ) -> List[Chunk]:
        """递归切分一个节"""
        if len(text) <= self.chunk_size:
            return [self._make_chunk(text, heading_stack, source_doc, category)]

        # 1. 尝试按子标题继续切
        sub_sections = self._parse_heading_tree(text)
        if len(sub_sections) > 1:
            # 有子节——递归处理每个子节
            result: List[Chunk] = []
            for sub_text, sub_stack in sub_sections:
                merged_stack = heading_stack + sub_stack
                result.extend(
                    self._chunk_section(sub_text, merged_stack, source_doc, category)
                )
            return result

        # 2. 没有子节——按句子精切
        return self._chunk_by_sentences(text, heading_stack, source_doc, category)

    def _chunk_by_sentences(
        self, text: str, heading_stack: List[str],
        source_doc: str, category: str,
    ) -> List[Chunk]:
        """按句子切分，尽量接近 chunk_size"""
        sentences = [s.strip() for s in self.SENTENCE_PATTERN.split(text) if s.strip()]
        if not sentences:
            return [self._make_chunk(text, heading_stack, source_doc, category)]

        chunks: List[Chunk] = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) > self.chunk_size and current:
                chunks.append(
                    self._make_chunk(current, heading_stack, source_doc, category)
                )
                # overlap: 保留上一块末尾作为下一块的上下文
                overlap_size = min(
                    int(self.chunk_size * self.overlap_ratio), self.max_overlap
                )
                if len(current) > overlap_size:
                    current = current[-overlap_size:] + sent
                else:
                    current = sent
            else:
                current = (current + " " + sent).strip() if current else sent

        if current:
            chunks.append(
                self._make_chunk(current, heading_stack, source_doc, category)
            )

        return chunks

    def _make_chunk(
        self, content: str, heading_stack: List[str],
        source_doc: str, category: str,
    ) -> Chunk:
        """工厂方法——创建 Chunk，char_start/end 临时用 -1 占位"""
        return Chunk(
            content=content,
            metadata=ChunkMetadata(
                source_doc=source_doc,
                category=category,
                page_number=0,
                heading_stack=heading_stack,
                char_start=-1,
                char_end=-1,
            ),
            chunk_index=-1,  # 外部统一编号
        )
```

- [ ] **Step 2: 验证可导入**

```bash
cd backend
venv\Scripts\activate
python -c "from services.recursive_chunker import RecursiveChunker; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/recursive_chunker.py
git commit -m "RecursiveChunker 实现——标题树递归+句子精切+动态overlap"
```

---

### Task 3: RecursiveChunker 单元测试

**Files:**
- Create: `backend/tests/test_recursive_chunker.py`

- [ ] **Step 1: 写测试**

`backend/tests/test_recursive_chunker.py`：

```python
"""RecursiveChunker 单元测试"""
import pytest
from services.recursive_chunker import RecursiveChunker

DEEP_NESTED = """# 第一章

前言内容，简要介绍。

## 1.1 第一小节

这是第一小节的内容。包含多个句子。每个句子都是独立的。
还有一些补充说明。总共有五个句子。

## 1.2 第二小节

第二小节的内容同样丰富。
这里讨论了一些技术细节。
包括实现方式、性能考量、以及注意事项。

### 1.2.1 子小节

更深层的内容。
测试递归切分能力。
"""

FLAT_LONG = """这是一个没有标题的长文本。
它包含了很多很多句子。
""" + "这是填充内容。" * 100


class TestRecursiveChunker:

    def test_chunk_size_limit(self):
        """每个 chunk 不超过 chunk_size"""
        c = RecursiveChunker(chunk_size=200, overlap_ratio=0.15, max_overlap=50)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        for chunk in result:
            assert len(chunk.content) <= 200, (
                f"chunk {chunk.chunk_index} 长度 {len(chunk.content)} > 200"
            )

    def test_heading_stack_preserved(self):
        """递归切分后 heading_stack 包含完整层级"""
        c = RecursiveChunker(chunk_size=200, overlap_ratio=0.15, max_overlap=50)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        # 找到 ## 1.2.1 下的 chunk
        deep_chunks = [
            r for r in result
            if r.metadata.heading_stack and "1.2.1 子小节" in r.metadata.heading_stack
        ]
        assert len(deep_chunks) > 0
        for chunk in deep_chunks:
            # heading_stack 应包含完整路径
            assert any("第一章" in h for h in chunk.metadata.heading_stack)
            assert any("1.2 第二小节" in h for h in chunk.metadata.heading_stack)

    def test_flat_text_split_by_sentences(self):
        """无标题的长文本按句子精切"""
        c = RecursiveChunker(chunk_size=200, overlap_ratio=0.15, max_overlap=50)
        result = c.chunk(FLAT_LONG, "test", "test.md")
        assert len(result) > 1
        for chunk in result:
            assert len(chunk.content) <= 200

    def test_short_section_not_split(self):
        """短于 chunk_size 的节不被切分"""
        short_text = "# 短节\n只有一句话。"
        c = RecursiveChunker(chunk_size=500)
        result = c.chunk(short_text, "test", "test.md")
        assert len(result) == 1  # 只有一节 → 一个 chunk

    def test_chunk_indices_sequential(self):
        """chunk_index 连续递增"""
        c = RecursiveChunker(chunk_size=200)
        result = c.chunk(DEEP_NESTED, "test", "test.md")
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_overlap_between_neighbors(self):
        """相邻句子级 chunk 有重叠"""
        c = RecursiveChunker(chunk_size=100, overlap_ratio=0.3, max_overlap=50)
        result = c.chunk(FLAT_LONG, "test", "test.md")
        # 检查至少有一对相邻 chunk 有重叠内容
        found_overlap = False
        for i in range(len(result) - 1):
            # 前一块的末尾 20 字符出现在后一块中
            tail = result[i].content[-20:]
            if tail in result[i + 1].content:
                found_overlap = True
                break
        assert found_overlap, "应该有相邻 chunk 存在重叠内容"

    def test_empty_text(self):
        """空文本不报错"""
        c = RecursiveChunker()
        result = c.chunk("", "test", "test.md")
        assert result == []

    def test_no_heading_text(self):
        """无标题文本正常处理"""
        c = RecursiveChunker(chunk_size=100)
        result = c.chunk("这是普通文本。没有标题。", "test", "test.md")
        assert len(result) == 1
```

- [ ] **Step 2: 跑测试**

```bash
cd backend
venv\Scripts\activate
pytest tests/test_recursive_chunker.py -v
```
Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_recursive_chunker.py
git commit -m "RecursiveChunker 单元测试——8 个用例覆盖标题嵌套/长文本/空文本/overlap"
```

---

### Task 4: 切换到 RecursiveChunker + 全局验证

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: main.py 替换 Chunker**

`backend/main.py` lifespan 中：

```python
# 旧: FixedChunker
# 新: RecursiveChunker
from services.recursive_chunker import RecursiveChunker

# 改这一行:
.with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
```

- [ ] **Step 2: 跑全部测试**

```bash
pytest tests/ -v
```
Expected: 11 + 8 = 19 passed（旧 FixedChunker 测试仍在，RecursiveChunker 测试新增）

- [ ] **Step 3: 重新摄入文档，验证端到端**

```bash
# 清旧 ChromaDB
rm -r ../data/chroma_db

# 运行摄入 + 随机抽 5 条 QA 验证
python -c "
import asyncio, os, glob
from config import Config
from services.parser import MDParser
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.generator import DeepSeekGenerator
from services.pipeline import RAGPipeline

async def main():
    config = Config.load()
    embedder = BGEBaaIEmbedder(model_name=config.embedding_model, device='cpu', cache_folder=config.model_cache_path)
    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(embedder)
        .with_retriever(ChromaRetriever(persist_path=config.chroma_path, embedder=embedder))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .build()
    )
    doc_dir = '../data/documents'
    files = glob.glob(os.path.join(doc_dir, '*.md'))
    total = 0
    for f in files:
        try:
            n = await pipeline.ingest(f, category='IBM_Docs')
            total += n
            print(f'  {os.path.basename(f)}: {n} chunks')
        except Exception as e:
            print(f'  {os.path.basename(f)}: FAIL - {e}')
    print(f'\n摄入: {total} chunks / {len(files)} 篇')

    # 抽测 3 条
    test_questions = [
        'What foundation models are available?',
        'How to deploy a Java model?',
        'What is federated learning?',
    ]
    for q in test_questions:
        print(f'\nQ: {q}')
        full = ''
        src_count = 0
        async for event in pipeline.query(q):
            if event.type == 'token':
                full += event.content
            elif event.type == 'sources':
                src_count = len(event.sources)
            elif event.type == 'done':
                pass
        print(f'  回答: {len(full)} 字, 来源: {src_count} 条')
        print(f'  前80字: {full[:80]}...')

asyncio.run(main())
"
```
Expected: 摄入成功 + 3 条问答均有回答和来源

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "切换到 RecursiveChunker: main.py 替换 + 全量测试 + 端到端验证"
```

---

## 验证清单

- [ ] ChunkMetadata.heading_stack 全局同步，19 个测试全绿
- [ ] RecursiveChunker 8 个专有测试全绿
- [ ] 54 篇文档重新摄入成功（chunk 数相比 FixedChunker 的 628 个预期减少 15-25%，因为按节合并了小 chunk）
- [ ] 3 条抽测问答均有回答 + 来源
- [ ] heading_stack 在 Source 引用中正确展示（前端/API 能看到完整层级路径）
> **归档说明（2026-06-06）**：这是历史实施计划，RecursiveChunker 已完成并继续演进。
