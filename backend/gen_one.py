"""单组答案生成 —— 当前配置 r075（adaptive_cutoff_ratio=0.75）"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from services.embedder import BGEBaaIEmbedder
from services.generator import LLMGenerator
from services.hybrid_retriever import HybridRetriever
from services.llm_factory import get_provider
from services.query_rewriter import QueryRewriter
from services.reranker import BgeReranker, adaptive_noise_filter
from services.retriever import ChromaRetriever


async def generate_answer(generator, question, contexts):
    answer = ""
    full_contexts = []
    async for event in generator.generate(question, contexts):
        if event.type == "token":
            answer += event.content or ""
        elif event.type == "contexts":
            full_contexts = event.contexts or []
    return answer, full_contexts


async def main():
    config = Config.load()
    project_data_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data")
    )
    data_dir = os.path.join(project_data_dir, "evaluations", "datasets")
    os.makedirs(data_dir, exist_ok=True)
    qa_path = os.path.join(project_data_dir, "watsonxDocsQA_test.json")
    qa_pairs = json.load(open(qa_path, "r", encoding="utf-8"))

    embedder = BGEBaaIEmbedder(
        model_name=config.embedding_model, device="cpu",
        cache_folder=config.model_cache_path,
    )
    retriever = HybridRetriever(ChromaRetriever(config.chroma_path, embedder))
    reranker = BgeReranker(device="cpu", cache_folder=config.model_cache_path)
    rewriter = QueryRewriter(api_key=config.deepseek_api_key)
    generator = LLMGenerator(provider=get_provider("generate"))

    # 只用 0.75 一组
    RATIO = 0.75
    label = "r075"
    dataset = []

    print(f"Config: adaptive_cutoff_ratio={RATIO}, keep_min=3, min_score=0.50, top_k=5")
    print(f"Loaded {len(qa_pairs)} QA pairs")
    started = time.time()

    for index, (question, ground_truth) in enumerate(qa_pairs, 1):
        search_query = await rewriter.rewrite(question)
        query_embedding = embedder.embed([search_query])[0]
        candidates = retriever.search(
            query_embedding=query_embedding, top_k=20,
            query_text=search_query,
        )
        common_top5 = reranker.rerank(question, candidates, top_k=5)
        contexts = adaptive_noise_filter(common_top5, RATIO, keep_min=3)
        answer, full_contexts = await generate_answer(generator, question, contexts)

        dataset.append({
            "question": question,
            "answer": answer,
            "contexts": full_contexts,
            "ground_truth": ground_truth,
            "experiment": label,
            "adaptive_cutoff_ratio": RATIO,
        })
        n = len(contexts)
        elapsed = time.time() - started
        print(f"  [{index:2d}/30] ctx={n}  {elapsed:.0f}s  {question[:60]}...")

    path = os.path.join(data_dir, f"eval_dataset_{label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    total = time.time() - started
    print(f"\nDone: {path}  ({total:.0f}s, {total/len(qa_pairs):.1f}s/QA)")


if __name__ == "__main__":
    asyncio.run(main())
