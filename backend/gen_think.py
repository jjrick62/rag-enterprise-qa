"""生成 MiMo 思考模式答案（复用已捕获的检索上下文）"""
import asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

from services.llm_factory import get_provider
from services.generator import LLMGenerator
from gen_one import generate_answer, _deserialize_contexts


async def main():
    data_dir = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
        "evaluations", "datasets",
    )
    contexts_file = os.path.join(data_dir, "contexts_r075.json")
    contexts_data = json.load(open(contexts_file, "r", encoding="utf-8"))

    provider = get_provider("judge")  # MiMo thinking=True
    generator = LLMGenerator(provider, temperature=0.0)

    print(f"Thinking mode: model={provider.model}")
    dataset = []
    started = time.time()

    for index, item in enumerate(contexts_data, 1):
        ctx = _deserialize_contexts(item["contexts"])
        answer, full_contexts = await generate_answer(generator, item["question"], ctx)
        dataset.append({
            "question": item["question"],
            "answer": answer,
            "contexts": full_contexts,
            "ground_truth": item["ground_truth"],
            "experiment": "r075",
            "adaptive_cutoff_ratio": 0.75,
            "temperature": 0.0,
            "mode": "thinking",
        })
        elapsed = time.time() - started
        print(f"  [{index:2d}/30] ctx={len(ctx)}  {elapsed:.0f}s  {item['question'][:60]}...")

    path = os.path.join(data_dir, "eval_dataset_r075_think.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    total = time.time() - started
    print(f"\nDone: {path}  ({total:.0f}s, {total/len(contexts_data):.1f}s/QA)")


if __name__ == "__main__":
    asyncio.run(main())
