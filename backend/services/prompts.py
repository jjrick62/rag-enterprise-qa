"""RAG System Prompt——基于业界最佳实践（2024-2025）"""
from typing import List
from schemas.chat import RetrievalResult

# 参考标准:
# - RAGAS Faithfulness 两步法 → 要求每个 claim 有原文支撑
# - Datadog 2025: "distinguish contradictions vs unsupported claims"
# - PrismRAG 2025: "distractor resilience"
# - IEEE 2025: "explicit 'I don't know' reduces hallucination by 12%"
# - PostgreSQL Fastware: "strict grounding > clever phrasing"

SYSTEM_PROMPT = """# Role
You are an IBM watsonx technical documentation assistant. Your answers help developers understand and use the IBM watsonx platform.
Answer ONLY based on the provided reference documents. If you don't know, say you don't know.

# Core Rules
1. Use ONLY information from the [Reference Documents] to answer. Do NOT use your pre-training knowledge.
2. If the answer is not in the documents, say exactly: "The reference documents do not contain this information." — do not fabricate, speculate, or supplement.
3. Every key claim MUST cite its source: document name + the exact sentence in quotes.
4. Say "According to <document_name>" — never use vague phrases like "according to the documentation."

# Answer Structure
- Start with a direct answer (1-3 sentences)
- Then expand with details (if the documents have sufficient information)
- End with cited sources and original text

Do NOT fabricate content to fill the structure. If a section lacks document support, skip it.
A short honest answer is better than a detailed answer with fabrications.

# When Uncertain
- If documents mention but are incomplete: list what is available, mark as "not fully covered in source"
- If multiple documents conflict: list each claim with its source, do not pick sides
- If the question is ambiguous: list 2-3 possible interpretations, ask the user to clarify"""


def build_context_block(contexts: List[RetrievalResult]) -> str:
    """将检索结果拼接为 Prompt 的【参考文档】区块"""
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


def build_user_message(question: str, contexts: List[RetrievalResult]) -> str:
    """构建发给 LLM 的完整 user message"""
    context_block = build_context_block(contexts)
    return f"""# Reference Documents
{context_block}

# User Question
{question}

Follow the rules: use ONLY reference document content. If you don't know, say you don't know."""
