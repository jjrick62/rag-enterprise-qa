"""RAG System Prompt——基于业界最佳实践（2024-2025）"""
from typing import List
from schemas.chat import RetrievalResult

# 参考标准:
# - RAGAS Faithfulness 两步法 → 要求每个 claim 有原文支撑
# - Datadog 2025: "distinguish contradictions vs unsupported claims"
# - PrismRAG 2025: "distractor resilience"
# - IEEE 2025: "explicit 'I don't know' reduces hallucination by 12%"
# - PostgreSQL Fastware: "strict grounding > clever phrasing"

SYSTEM_PROMPT = """# 角色
你是 IBM watsonx 技术文档助手。你的回答帮助开发者理解和使用 IBM watsonx 平台。
你只根据提供的参考文档回答，不知道就说不知道。

# 核心规则
1. 只使用【参考文档】里的内容回答问题。禁止使用你的预训练知识。
2. 如果文档里没有答案，直接说："参考文档中未包含该信息。"——不编造、不推测、不补充。
3. 每一条关键陈述必须引用来源：文档名 + 原文关键句（双引号标出）。
4. 不要说"根据文档规定"——要说"根据《XXX文档》"。

# 回答结构
- 先给出直接回答（1-3句话）
- 再展开细节（如果文档有足够信息）
- 最后列出引用的文档和原文

不要为了填满结构而编造内容。如果某个部分没有文档支撑，就跳过它。
简短的诚实回答好过详尽但包含编造的回答。

# 不确定时
- 如果文档提到但不完整：列出已有信息，标注"原文未展开"
- 如果多个文档说法矛盾：列出各自的说法和文档来源，不要私自选一个
- 如果问题模糊不清：列出2-3种可能的理解，请用户澄清"""


def build_context_block(contexts: List[RetrievalResult]) -> str:
    """将检索结果拼接为 Prompt 的【参考文档】区块"""
    blocks: List[str] = []
    for i, result in enumerate(contexts, 1):
        chunk = result.chunk
        meta = chunk.metadata
        block = (
            f"[文档{i}] 来源：{meta.source_doc}\n"
            f"章节：{' > '.join(meta.heading_stack) if meta.heading_stack else '（无标题）'}\n"
            f"内容：{chunk.content}"
        )
        blocks.append(block)
    return "\n---\n".join(blocks)


def build_user_message(question: str, contexts: List[RetrievalResult]) -> str:
    """构建发给 LLM 的完整 user message"""
    context_block = build_context_block(contexts)
    return f"""【参考文档】
{context_block}

【用户问题】
{question}

请遵守规则：只使用参考文档的内容回答。不知道就说不知道。"""
