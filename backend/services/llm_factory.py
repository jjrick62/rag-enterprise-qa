"""LLM 工厂——所有 LLM 配置集中管理，OOP 模块化

消除 gen_answers.py / eval_ragas_only.py / generator / ragas_evaluator 中的硬编码。
新增 Provider 只需加一个工厂方法。
"""
from openai import OpenAI, AsyncOpenAI
class LLMProvider:
    """LLM 供应商配置——API key、base_url、模型名、额外参数"""

    def __init__(self, name: str, api_key: str, base_url: str,
                 model: str, extra_body: dict = None):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.extra_body = extra_body or {}

    def create_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def create_async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


MIMO = None
MIMO_THINK = None
DEEPSEEK_V4 = None


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
        cached = LLMProvider(
            name="MiMo-Think" if thinking else "MiMo",
            api_key=_require_key("MIMO_API_KEY", config.mimo_api_key),
            base_url=config.mimo_base_url,
            model=config.mimo_model,
            extra_body={"enable_thinking": thinking},
        )
        if thinking:
            MIMO_THINK = cached
        else:
            MIMO = cached
    return cached


def _get_deepseek_v4():
    global DEEPSEEK_V4
    if DEEPSEEK_V4 is None:
        from config import Config
        c = Config.load()
        DEEPSEEK_V4 = LLMProvider(
            name="DeepSeek-V4-Pro",
            api_key=_require_key("DEEPSEEK_API_KEY", c.deepseek_api_key),
            base_url=c.deepseek_base_url,
            model="deepseek-v4-pro",
        )
    return DEEPSEEK_V4


# ── 角色→Provider 映射 ──

def get_provider(role: str) -> LLMProvider:
    """按角色获取 LLM Provider

    role:
      - 'generate': 答案生成 → DeepSeek V4 Pro
      - 'judge':    RAGAS 评估 → MiMo (开 thinking)
      - 'rewrite':  Query 改写 → MiMo (关 thinking, 便宜)
    """
    if role == 'judge':
        return _get_mimo(thinking=True)
    elif role == 'generate':
        return _get_deepseek_v4()
    elif role == 'rewrite':
        return _get_mimo(thinking=False)
    raise ValueError(f"Unknown role: {role}")


def get_client(role: str) -> OpenAI:
    return get_provider(role).create_client()


def get_async_client(role: str) -> AsyncOpenAI:
    return get_provider(role).create_async_client()
