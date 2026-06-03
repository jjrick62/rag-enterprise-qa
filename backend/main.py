"""FastAPI 应用入口——生命周期管理 + CORS

启动流程：
  1. 加载 Config（.env）
  2. Builder 模式组装五层组件
  3. Pipeline 注入 app.state，全局共享
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import Config
from services.parser import MDParser
from services.chunker import FixedChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.generator import DeepSeekGenerator
from services.pipeline import RAGPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时构建 Pipeline，关闭时清理"""
    config = Config.load()

    # Embedder 是共享实例——ChromaRetriever 检索时也用它向量化问题
    embedder = BGEBaaIEmbedder(
        model_name=config.embedding_model,
        device="cpu",  # 先 CPU 跑通，后续装 CUDA 版 PyTorch 换 cuda
        cache_folder=config.model_cache_path,
    )

    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(FixedChunker(chunk_size=500, overlap=50))
        .with_embedder(embedder)
        .with_retriever(ChromaRetriever(
            persist_path=config.chroma_path,
            embedder=embedder,
        ))
        .with_generator(DeepSeekGenerator(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model="deepseek-chat",
            temperature=0.3,
        ))
        .build()
    )

    app.state.pipeline = pipeline
    print(f"[启动] Pipeline 就绪 | Embedding: {config.embedding_model} | "
          f"ChromaDB: {config.chroma_path}")

    yield  # 这里是 FastAPI 运行期间

    print("[关闭] 服务停止")


app = FastAPI(title="RAG 企业制度智能问答", lifespan=lifespan)

# CORS——前端开发时跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from routers.chat import router as chat_router  # noqa: E402
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
