"""生成器——DeepSeek API 流式调用

使用 OpenAI 兼容 SDK（openai 包），因为 DeepSeek API 与 OpenAI 接口完全兼容。
流式生成 → AsyncIterator[GenerateEvent]，每个 event 是 token/sources/done 之一。
"""
from typing import List, AsyncIterator
from openai import AsyncOpenAI
from services.base import BaseGenerator
from services.prompts import SYSTEM_PROMPT, build_user_message
from schemas.chat import RetrievalResult, GenerateEvent, Source


class DeepSeekGenerator(BaseGenerator):
    """DeepSeek API 流式生成器

    流程：
      1. 拼接 System Prompt + 检索上下文 + 用户问题
      2. 调用 DeepSeek Chat API（stream=True）
      3. 逐 delta 产出 token event
      4. 流结束后产出 sources event + done event
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
    ):
        # AsyncOpenAI——异步客户端，支持 stream
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
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
        )

        # 逐 token 产出
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield GenerateEvent(type="token", content=delta.content)

        # 流结束后一次性发送引用来源
        sources = [
            Source(
                document_name=result.chunk.metadata.source_doc,
                heading=result.chunk.metadata.heading,
                excerpt=result.chunk.content[:200],
                score=result.score,
            )
            for result in contexts
        ]
        yield GenerateEvent(type="sources", sources=sources)

        # 结束信号
        yield GenerateEvent(type="done")
