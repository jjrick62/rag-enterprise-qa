"""Step 1: 生成回答 → 存 JSON"""
import asyncio, json, urllib.request, time, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from services.parser import MDParser
from services.recursive_chunker import RecursiveChunker
from services.embedder import BGEBaaIEmbedder
from services.retriever import ChromaRetriever
from services.hybrid_retriever import HybridRetriever
from services.generator import DeepSeekGenerator
from services.reranker import BgeReranker
from services.query_rewriter import QueryRewriter
from services.pipeline import RAGPipeline

async def main():
    config = Config.load()
    emb = BGEBaaIEmbedder(model_name=config.embedding_model, device="cpu", cache_folder=config.model_cache_path)
    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(500, 0.15, 50))
        .with_embedder(emb)
        .with_retriever(HybridRetriever(ChromaRetriever(config.chroma_path, emb)))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(BgeReranker(device="cpu", cache_folder=config.model_cache_path))
        .with_rewriter(QueryRewriter(api_key=config.deepseek_api_key))
        .build()
    )
    qa_url = "https://datasets-server.huggingface.co/rows?dataset=ibm-research%2FwatsonxDocsQA&config=question_answers&split=test&offset=0&length=50"
    with urllib.request.urlopen(qa_url) as r: qa_data = json.loads(r.read().decode())
    qa_pairs = [(r["row"]["question"], r["row"]["correct_answer"]) for r in qa_data["rows"]]
    dataset = []
    t0 = time.time()
    for i, (q, gt) in enumerate(qa_pairs[:20], 1):
        full = ""; contexts = []
        async for e in pipeline.query(q):
            if e.type == "token": full += e.content
            elif e.type == "sources": contexts = [s.excerpt[:500] for s in (e.sources or [])]
        dataset.append({"question": q, "answer": full[:1500], "contexts": contexts, "ground_truth": gt})
        print(f"  #{i:02d} {len(full)}字 {len(contexts)}源 | {q[:50]}...")
    path = os.path.join(os.path.dirname(__file__), "..", "data", "eval_dataset.json")
    json.dump(dataset, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nSaved {len(dataset)} QA to {path} ({time.time()-t0:.0f}s)")

asyncio.run(main())
