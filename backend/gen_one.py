"""单组答案生成 —— 支持温度对比 + 检索上下文复用

用法:
  # Phase A: 捕获检索上下文（跑一次，温控无关）
  python gen_one.py --capture-contexts --output contexts_r075.json

  # Phase B: 复用上下文，逐个温度生成答案
  python gen_one.py --temp 0.2 --reuse-contexts contexts_r075.json --output eval_dataset_r075_t02.json
  python gen_one.py --temp 0.0 --reuse-contexts contexts_r075.json --output eval_dataset_r075_t00.json
  python gen_one.py --temp 0.3 --reuse-contexts contexts_r075.json --output eval_dataset_r075_t03.json
"""
import argparse
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
from schemas.chat import RetrievalResult, Chunk, ChunkMetadata


async def generate_answer(generator, question, contexts):
    answer = ""
    full_contexts = []
    async for event in generator.generate(question, contexts):
        if event.type == "token":
            answer += event.content or ""
        elif event.type == "contexts":
            full_contexts = event.contexts or []
    return answer, full_contexts


def _resolve_model(model_name: str, cache_dir: str) -> str:
    short = model_name.split("/")[-1].lower().replace("-", "").replace("_", "").replace(".", "")
    search_roots = [
        os.path.join(cache_dir, "AI-ModelScope"),
        os.path.join(cache_dir, "models--" + model_name.replace("/", "--")),
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, _ in os.walk(root):
            if os.path.isfile(os.path.join(dirpath, "config.json")):
                dname = os.path.basename(dirpath).lower().replace("-", "").replace("_", "").replace(".", "")
                if short in dname or dname in short:
                    return os.path.abspath(dirpath)
    return model_name


def _serialize_contexts(contexts):
    """将 RetrievalResult 列表转为可 JSON 序列化的结构"""
    out = []
    for r in contexts:
        meta = r.chunk.metadata
        out.append({
            "content": r.chunk.content,
            "source_doc": meta.source_doc,
            "heading_stack": meta.heading_stack,
            "score": r.score,
        })
    return out


def _deserialize_contexts(raw_list):
    """从 JSON 还原 RetrievalResult 列表"""
    results = []
    for item in raw_list:
        chunk = Chunk(
            content=item["content"],
            metadata=ChunkMetadata(
                source_doc=item.get("source_doc", ""),
                category="",
                page_number=0,
                heading_stack=item.get("heading_stack", []),
                char_start=0,
                char_end=0,
            ),
            chunk_index=0,
        )
        results.append(RetrievalResult(chunk=chunk, score=item.get("score", 0.0)))
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--temp", type=float, default=0.2)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--capture-contexts", action="store_true",
                        help="仅捕获检索上下文，不生成答案")
    parser.add_argument("--reuse-contexts", type=str, default="",
                        help="复用已有的检索上下文文件")
    args = parser.parse_args()

    if args.capture_contexts and args.reuse_contexts:
        print("ERROR: --capture-contexts 和 --reuse-contexts 互斥")
        sys.exit(1)

    config = Config.load()
    project_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    data_dir = os.path.join(project_data_dir, "evaluations", "datasets")
    os.makedirs(data_dir, exist_ok=True)
    qa_path = os.path.join(project_data_dir, "watsonxDocsQA_test.json")
    qa_pairs = json.load(open(qa_path, "r", encoding="utf-8"))

    models_dir = os.path.abspath(config.model_cache_path)
    RATIO = 0.75

    # ── Phase A: 捕获上下文 ──
    if args.capture_contexts:
        embedder = BGEBaaIEmbedder(
            model_name=_resolve_model(config.embedding_model, models_dir),
            device="cpu", cache_folder=models_dir,
        )
        retriever = HybridRetriever(ChromaRetriever(config.chroma_path, embedder))
        reranker = BgeReranker(
            model_name=_resolve_model("BAAI/bge-reranker-v2-m3", models_dir),
            device="cpu", cache_folder=models_dir,
        )
        rewriter = QueryRewriter(provider=get_provider("rewrite"))

        print(f"Capturing retrieval contexts (cutoff={RATIO})...")
        started = time.time()
        captured = []

        for index, (question, ground_truth) in enumerate(qa_pairs, 1):
            search_query = await rewriter.rewrite(question)
            if not search_query or not search_query.strip():
                search_query = question  # 空查询回退原问题
            query_embedding = embedder.embed([search_query])[0]
            candidates = retriever.search(
                query_embedding=query_embedding, top_k=20,
                query_text=search_query,
            )
            common_top5 = reranker.rerank(question, candidates, top_k=5)
            contexts = adaptive_noise_filter(common_top5, RATIO, keep_min=3)

            captured.append({
                "question": question,
                "ground_truth": ground_truth,
                "search_query": search_query,
                "contexts": _serialize_contexts(contexts),
            })
            elapsed = time.time() - started
            print(f"  [{index:2d}/30] ctx={len(contexts)}  {elapsed:.0f}s  {question[:60]}...")

        out_name = args.output or "contexts_r075.json"
        path = os.path.join(data_dir, out_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        total = time.time() - started
        print(f"\nContexts saved: {path}  ({total:.0f}s)")
        return

    # ── Phase B: 复用上下文生成答案 ──
    reuse_file = args.reuse_contexts
    if not os.path.isabs(reuse_file):
        reuse_file = os.path.join(data_dir, reuse_file)

    if not os.path.exists(reuse_file):
        print(f"ERROR: contexts file not found: {reuse_file}")
        sys.exit(1)

    contexts_data = json.load(open(reuse_file, "r", encoding="utf-8"))
    print(f"Loaded {len(contexts_data)} pre-captured contexts from {os.path.basename(reuse_file)}")

    provider = get_provider("generate")
    generator = LLMGenerator(provider, temperature=args.temp)

    dataset = []
    started = time.time()
    print(f"Generating answers: temp={args.temp}, model={provider.model}")

    for index, item in enumerate(contexts_data, 1):
        question = item["question"]
        ground_truth = item["ground_truth"]
        contexts = _deserialize_contexts(item["contexts"])

        answer, full_contexts = await generate_answer(generator, question, contexts)

        dataset.append({
            "question": question,
            "answer": answer,
            "contexts": full_contexts,
            "ground_truth": ground_truth,
            "experiment": "r075",
            "adaptive_cutoff_ratio": RATIO,
            "temperature": args.temp,
        })
        n = len(contexts)
        elapsed = time.time() - started
        print(f"  [{index:2d}/30] ctx={n}  {elapsed:.0f}s  {question[:60]}...")

    out_name = args.output or f"eval_dataset_r075_t{str(args.temp).replace('.', '')}.json"
    path = os.path.join(data_dir, out_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    total = time.time() - started
    print(f"\nDone: {path}  ({total:.0f}s, {total/len(contexts_data):.1f}s/QA)")


if __name__ == "__main__":
    asyncio.run(main())
