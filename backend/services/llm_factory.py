"""LLM 工厂——所有 LLM 配置集中管理，OOP 模块化

消除 gen_answers.py / eval_ragas_only.py / generator / ragas_evaluator 中的硬编码。
新增 Provider 只需加一个工厂方法。
"""
import httpx
from openai import OpenAI, AsyncOpenAI


class LLMProvider:
    """LLM 供应商配置——API key、base_url、模型名、额外参数"""

    def __init__(self, name: str, api_key: str, base_url: str,
                 model: str, extra_body: dict = None, use_api_key_header: bool = False):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.extra_body = extra_body or {}
        self._use_api_key_header = use_api_key_header

    def create_client(self) -> OpenAI:
        timeout = httpx.Timeout(300.0, connect=10.0)
        if self._use_api_key_header:
            return OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=300.0,
                http_client=httpx.Client(
                    headers={"api-key": self.api_key},
                    timeout=timeout,
                ),
            )
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=300.0)

    def create_async_client(self) -> AsyncOpenAI:
        timeout = httpx.Timeout(300.0, connect=10.0)
        if self._use_api_key_header:
            return AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=300.0,
                http_client=httpx.AsyncClient(
                    headers={"api-key": self.api_key},
                    timeout=timeout,
                ),
            )
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=300.0)

MIMO = None
MIMO_THINK = None


def _require_key(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} is not configured. Add it to backend/.env.")
    return value


def _get_mimo(thinking: bool):
    global MIMO, MIMO_THINK
    cached = MIMO_THINK if thinking else MIMO
    if cached is None:
        from config import Config
        config = Config.load()
        # 订阅套餐版：api-key header，无 extra_body（不传 enable_thinking/reasoning_effort）
        is_subscription = "token-plan" in config.mimo_base_url
        cached = LLMProvider(
            name="MiMo-Think" if thinking else "MiMo",
            api_key=_require_key("MIMO_API_KEY", config.mimo_api_key),
            base_url=config.mimo_base_url,
            model=config.mimo_model,
            extra_body={},
            use_api_key_header=is_subscription,
        )
        if thinking:
            MIMO_THINK = cached
        else:
            MIMO = cached
    return cached


# ── 角色→Provider 映射 ──

def get_provider(role: str) -> LLMProvider:
    """按角色获取 LLM Provider

    role:
      - 'generate': 答案生成 → MiMo（免费，关 thinking）
      - 'judge':    RAGAS 评估 → MiMo（开 thinking）
      - 'rewrite':  Query 改写 → MiMo（关 thinking）
    """
    if role in ('judge', 'generate', 'rewrite'):
        return _get_mimo(thinking=(role == 'judge'))
    raise ValueError(f"Unknown role: {role}")


def get_client(role: str) -> OpenAI:
    return get_provider(role).create_client()


def get_async_client(role: str) -> AsyncOpenAI:
    return get_provider(role).create_async_client()
