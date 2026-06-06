"""生成器——LLM 流式调用（OpenAI 兼容协议）

OOP 设计：
  LLMGenerator(BaseGenerator) — 接受 LLMProvider，工厂模式解耦
  DeepSeekGenerator(BaseGenerator) — 旧接口，向后兼容
"""
from typing import List, AsyncIterator
from openai import AsyncOpenAI
from services.base import BaseGenerator
from services.prompts import SYSTEM_PROMPT, build_user_message
from schemas.chat import RetrievalResult, GenerateEvent, Source


class LLMGenerator(BaseGenerator):
    """LLM 流式生成器——接受 LLMProvider，解耦供应商配置

    用法:
        gen = LLMGenerator(provider=get_provider("generate"))
    """

    def __init__(self, provider, temperature: float = 0.2):  # 低随机性，减少编造但不僵化
        self._client = provider.create_async_client()
        self._model = provider.model
        self._extra_body = provider.extra_body
        self._temperature = temperature

    async def generate(
        self,
        question: str,
        contexts: List[RetrievalResult],
    ) -> AsyncIterator[GenerateEvent]:
        user_message = build_user_message(question, contexts)

        stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            extra_body=self._extra_body or None,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield GenerateEvent(type="token", content=delta.content)

        # 评测必须使用生成答案时实际看到的完整上下文。该内部事件不会由 SSE 路由发给前端。
        yield GenerateEvent(
            type="contexts",
            contexts=[result.chunk.content for result in contexts],
        )

        sources = [
            Source(
                document_name=result.chunk.metadata.source_doc,
                heading=result.chunk.metadata.heading_stack[-1] if result.chunk.metadata.heading_stack else "",
                excerpt=result.chunk.content[:200],
                score=result.score,
            )
            for result in contexts
        ]
        yield GenerateEvent(type="sources", sources=sources)
        yield GenerateEvent(type="done")


class DeepSeekGenerator(LLMGenerator):
    """旧接口——向后兼容，内部委托给 LLMGenerator"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
    ):
        from services.llm_factory import LLMProvider
        provider = LLMProvider(
            name="DeepSeek",
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        super().__init__(provider, temperature=temperature)
