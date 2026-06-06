"""全量重摄入——用新 chunker 重建 ChromaDB"""
import asyncio, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
from services.parser import MDParser
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.generator import DeepSeekGenerator
from services.pipeline import RAGPipeline

async def main():
    config = Config.load()
    emb = BGEBaaIEmbedder(model_name=config.embedding_model, device="cpu", cache_folder=config.model_cache_path)

    vec = ChromaRetriever(config.chroma_path, emb)
    deleted = vec.clear()
    print(f"Cleared {deleted} existing chunks")

    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(500, 0.15, 50))
        .with_embedder(emb)
        .with_retriever(vec)
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .build()
    )

    docs_dir = os.path.join(os.path.dirname(__file__), "..", "data", "documents")
    files = sorted(glob.glob(os.path.join(docs_dir, "*.md")))
    print(f"Ingesting {len(files)} documents...")

    for i, fp in enumerate(files, 1):
        count = await pipeline.ingest(fp, "IBM_Docs")
        print(f"  {i}/{len(files)}: {os.path.basename(fp)} → {count} chunks")

    # 验证
    col = vec._client.get_collection("enterprise_docs")
    total = col.count()
    print(f"\nDone! {total} total chunks in ChromaDB")

asyncio.run(main())
