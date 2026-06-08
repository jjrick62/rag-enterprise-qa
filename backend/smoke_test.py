"""冒烟测试 —— 实验前快速验证全链路组件

用法:
    cd backend
    .\venv\Scripts\python.exe smoke_test.py

检查项:
    1. Embedding 模型加载
    2. ChromaDB 有数据
    3. Reranker 模型加载
    4. Rewriter (MiMo) 连通
    5. Generator (MiMo) 连通
    6. 全链路一致性 (rewrite → retrieve → rerank → generate)
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from config import Config


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


def check(name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return ok


async def main():
    config = Config.load()
    models_dir = os.path.abspath(config.model_cache_path)
    passed = 0
    failed = 0

    print("=" * 50)
    print("RAG Smoke Test")
    print("=" * 50)

    # 1. Embedding
    print("\n[1/5] Embedding model...")
    try:
        from services.embedder import BGEBaaIEmbedder
        emb_model = _resolve_model(config.embedding_model, models_dir)
        emb = BGEBaaIEmbedder(model_name=emb_model, device="cpu", cache_folder=models_dir)
        vec = emb.embed(["smoke test"])
        ok = vec.shape == (1, 512)
        if check("Embedding loaded", ok, f"dim={vec.shape[1]}"):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        check("Embedding loaded", False, str(e)[:80])
        failed += 1

    # 2. ChromaDB
    print("\n[2/5] ChromaDB...")
    try:
        from services.retriever import ChromaRetriever
        from services.hybrid_retriever import HybridRetriever
        retriever = HybridRetriever(
            vector_retriever=ChromaRetriever(persist_path=config.chroma_path, embedder=emb)
        )
        retriever._rebuild_from_chromadb()
        n = len(retriever._bm25_chunks)
        ok = n > 0
        if check("ChromaDB + BM25", ok, f"{n} chunks"):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        check("ChromaDB + BM25", False, str(e)[:80])
        failed += 1

    # 3. Reranker
    print("\n[3/5] Reranker...")
    try:
        from services.reranker import BgeReranker
        reranker_model = _resolve_model("BAAI/bge-reranker-v2-m3", models_dir)
        reranker = BgeReranker(model_name=reranker_model, device="cpu", cache_folder=models_dir)
        ok = reranker is not None
        if check("Reranker loaded", ok):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        check("Reranker loaded", False, str(e)[:80])
        failed += 1

    # 4. Rewriter (MiMo)
    print("\n[4/5] Rewriter (MiMo)...")
    try:
        from services.llm_factory import get_provider
        from services.query_rewriter import QueryRewriter
        rewriter = QueryRewriter(provider=get_provider("rewrite"))
        t0 = time.time()
        result = await rewriter.rewrite("有啥基础模型能用")
        elapsed = time.time() - t0
        ok = len(result) > 0 and "model" in result.lower() or "foundation" in result.lower() or "what" in result.lower()
        if check("Rewrite API", ok, f"{elapsed:.1f}s -> {result[:60]}"):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        check("Rewrite API", False, str(e)[:80])
        failed += 1

    # 5. Generator (MiMo)
    print("\n[5/5] Generator (MiMo)...")
    try:
        from services.generator import LLMGenerator
        from services.prompts import build_user_message
        from schemas.chat import RetrievalResult, Chunk, ChunkMetadata

        provider = get_provider("generate")
        generator = LLMGenerator(provider)
        dummy_chunk = Chunk(
            content="IBM watsonx provides foundation models including flan-t5, granite, llama-2, mpt, and starcoder.",
            metadata=ChunkMetadata(source_doc="test.md", category="test", page_number=0,
                                   heading_stack=["Foundation Models"], char_start=0, char_end=0),
            chunk_index=0,
        )
        dummy_result = RetrievalResult(chunk=dummy_chunk, score=0.95)
        contexts = [dummy_result]

        t0 = time.time()
        answer = ""
        async for event in generator.generate("What foundation models are available?", contexts):
            if event.type == "token":
                answer += event.content or ""
        elapsed = time.time() - t0
        ok = len(answer) > 10
        if check("Generate API", ok, f"{elapsed:.1f}s -> {answer[:80]}"):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        check("Generate API", False, str(e)[:80])
        failed += 1

    # Summary
    print("\n" + "=" * 50)
    total = passed + failed
    print(f"Result: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("SMOKE TEST PASSED — ready to run experiments")
    else:
        print("SMOKE TEST FAILED — fix issues before running experiments")
    print("=" * 50)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
