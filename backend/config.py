"""配置模块——从 .env 加载，单例不可变"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# 模块级单例变量——frozen dataclass 上不能设类属性
_config_instance: "Config | None" = None


@dataclass(frozen=True)
class Config:
    mimo_api_key: str
    mimo_base_url: str
    mimo_model: str
    embedding_model: str
    chroma_path: str
    english_embedding_model: str
    english_chroma_path: str
    model_cache_path: str

    @classmethod
    def load(cls) -> "Config":
        global _config_instance
        if _config_instance is not None:
            return _config_instance
        _config_instance = Config(
            mimo_api_key=os.getenv("MIMO_API_KEY", ""),
            mimo_base_url=os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
            mimo_model=os.getenv("MIMO_MODEL", "mimo-v2.5-pro"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            chroma_path=os.getenv("CHROMA_PATH", "../data/chroma_db"),
            english_embedding_model=os.getenv(
                "ENGLISH_EMBEDDING_MODEL",
                "BAAI/bge-base-en-v1.5",
            ),
            english_chroma_path=os.getenv(
                "ENGLISH_CHROMA_PATH",
                "../data/chroma_db_bge_base_en",
            ),
            model_cache_path=os.getenv("MODEL_CACHE_PATH", "./models"),
        )
        return _config_instance
