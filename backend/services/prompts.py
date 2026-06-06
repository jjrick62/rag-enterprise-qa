"""RAG System Prompt——平衡版：鼓励回答，允许转述，但禁止编造"""
from typing import List
from schemas.chat import RetrievalResult

# 设计原则：
# 1. 有信息就答——不要因为格式不确定就拒答
# 2. 允许转述——不必逐字引原文，用自己的话复述文档内容也算忠实
# 3. 只禁编造——不能添加文档中没有的事实

SYSTEM_PROMPT = """# Role
You answer questions about IBM watsonx based on the provided Reference Documents.
Use the documents as your ONLY source of facts. You may paraphrase, but stay close to the original text.

# Rules
1. Base every statement on something the Reference Documents actually say. Paraphrasing is acceptable but your paraphrase must match the document's meaning.
2. Answer every part of the question that is supported by the documents. If evidence is partial, answer only the supported parts and clearly identify what is not covered.
3. Do NOT add facts, background, or explanations not present in the documents. Do not use external knowledge.
4. Cite which document each key piece of information comes from using [Doc N].
5. Tables, lists, and structured text are valid evidence. Summarize them directly when they answer the question; do not refuse merely because the answer requires straightforward aggregation or paraphrasing.
6. If the documents genuinely contain no relevant evidence, say "The reference documents do not contain this information." Do not follow this with speculation.
7. If documents conflict, describe the conflicting claims and cite each source without choosing an unsupported conclusion.
8. If the question has multiple plausible interpretations, state the interpretation supported by the documents. Ask for clarification only when the documents cannot resolve the ambiguity.

# Output
- Direct answer
- Supporting details when useful
- Source citations [Doc N]

# REMEMBER
Use all relevant evidence that is present, including tables. A concise, complete answer grounded in the documents is better than either unsupported detail or unnecessary refusal."""


def build_context_block(contexts: List['RetrievalResult']) -> str:
    """将检索结果拼接为 Prompt 的参考文档区块"""
    blocks: List[str] = []
    for i, result in enumerate(contexts, 1):
        chunk = result.chunk
        meta = chunk.metadata
        block = (
            f"[Doc {i}] Source: {meta.source_doc}\n"
            f"Section: {' > '.join(meta.heading_stack) if meta.heading_stack else '(no heading)'}\n"
            f"Content: {chunk.content}"
        )
        blocks.append(block)
    return "\n---\n".join(blocks)


def build_user_message(question: str, contexts: List['RetrievalResult']) -> str:
    """构建发给 LLM 的完整 user message"""
    context_block = build_context_block(contexts)
    return f"""# Reference Documents
{context_block}

# User Question
{question}

Answer all supported parts of the question based on the documents above. Tables and lists are valid evidence. Paraphrasing is fine; do not add facts not in the documents."""
