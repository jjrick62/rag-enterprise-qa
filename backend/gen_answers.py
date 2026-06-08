"""Generate isolated answer datasets for adaptive reranker experiments."""
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


EXPERIMENTS = {
    "off": None,
    "r070": 0.70,
    "r075": 0.75,
    "r080": 0.80,
}


async def generate_answer(generator, question, contexts):
    answer = ""
    full_contexts = []
    async for event in generator.generate(question, contexts):
        if event.type == "token":
            answer += event.content or ""
        elif event.type == "contexts":
            full_contexts = event.contexts or []
    return answer, full_contexts


def save_datasets(data_dir, datasets):
    for label, dataset in datasets.items():
        path = os.path.join(data_dir, f"eval_dataset_{label}.json")
        with open(path, "w", encoding="utf-8") as output:
            json.dump(dataset, output, ensure_ascii=False, indent=2)


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
        model_name=config.embedding_model,
        device="cpu",
        cache_folder=config.model_cache_path,
    )
    retriever = HybridRetriever(ChromaRetriever(config.chroma_path, embedder))
    reranker = BgeReranker(
        device="cpu",
        cache_folder=config.model_cache_path,
        adaptive_cutoff_ratio=None,
    )
    rewriter = QueryRewriter(provider=get_provider("rewrite"))
    generator = LLMGenerator(provider=get_provider("generate"))
    datasets = {label: [] for label in EXPERIMENTS}

    print(f"Loaded {len(qa_pairs)} QA; experiments={list(EXPERIMENTS)}")
    started = time.time()
    for index, (question, ground_truth) in enumerate(qa_pairs, 1):
        search_query = await rewriter.rewrite(question)
        query_embedding = embedder.embed([search_query])[0]
        candidates = retriever.search(
            query_embedding=query_embedding,
            top_k=20,
            query_text=search_query,
        )
        common_top5 = reranker.rerank(question, candidates, top_k=5)

        counts = []
        for label, ratio in EXPERIMENTS.items():
            contexts = (
                common_top5
                if ratio is None
                else adaptive_noise_filter(common_top5, ratio, keep_min=3)
            )
            answer, full_contexts = await generate_answer(
                generator,
                question,
                contexts,
            )
            datasets[label].append(
                {
                    "question": question,
                    "answer": answer,
                    "contexts": full_contexts,
                    "ground_truth": ground_truth,
                    "experiment": label,
                    "adaptive_cutoff_ratio": ratio,
                }
            )
            counts.append(f"{label}:{len(full_contexts)}")

        save_datasets(data_dir, datasets)
        print(f"#{index:02d} {' '.join(counts)} | {question[:60]}")

    print(f"Saved four isolated datasets in {time.time() - started:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
