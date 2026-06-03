"""配置模块——从 .env 加载，单例不可变"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    deepseek_api_key: str
    deepseek_base_url: str
    embedding_model: str
    chroma_path: str

    _instance: "Config | None" = None  # type: ignore

    @classmethod
    def load(cls) -> "Config":
        if cls._instance is not None:
            return cls._instance
        # 绕过 frozen 限制，构造时一次性写入
        object.__setattr__(cls, "_instance", Config(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            chroma_path=os.getenv("CHROMA_PATH", "data/chroma_db"),
        ))
        return cls._instance
