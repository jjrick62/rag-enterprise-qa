import asyncio
from pathlib import Path

from schemas.chat import Chunk, ChunkMetadata, RetrievalResult
from services import ragas_evaluator
from services.generator import LLMGenerator


class _EmptyStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _Completions:
    async def create(self, **kwargs):
        return _EmptyStream()


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class _Client:
    def __init__(self):
        self.chat = _Chat()


class _Provider:
    model = "test-model"
    extra_body = None

    def create_async_client(self):
        return _Client()


def test_generator_emits_full_evaluation_contexts_and_short_ui_excerpts():
    content = "A" * 800
    result = RetrievalResult(
        chunk=Chunk(
            content=content,
            metadata=ChunkMetadata(
                source_doc="Document",
                category="test",
                page_number=1,
                heading_stack=["Heading"],
                char_start=0,
                char_end=len(content),
            ),
            chunk_index=0,
        ),
        score=0.9,
    )

    async def collect_events():
        generator = LLMGenerator(provider=_Provider())
        return [
            event
            async for event in generator.generate(
                question="question",
                contexts=[result],
            )
        ]

    events = asyncio.run(collect_events())
    context_event = next(event for event in events if event.type == "contexts")
    source_event = next(event for event in events if event.type == "sources")

    assert context_event.contexts == [content]
    assert source_event.sources[0].excerpt == content[:200]


def test_ragas_dataset_preparation_preserves_full_answers_and_contexts():
    answer = "answer-" + ("A" * 5000)
    context = "context-" + ("C" * 5000)
    dataset = [
        {
            "question": "question",
            "answer": answer,
            "contexts": [context],
            "ground_truth": "ground truth",
        }
    ]

    prepared = ragas_evaluator.prepare_evaluation_dataset(dataset)

    assert prepared[0]["answer"] == answer
    assert prepared[0]["contexts"] == [context]


def test_evaluation_scripts_consume_internal_full_context_events():
    backend_dir = Path(__file__).resolve().parents[1]

    for script_name in ("gen_answers.py", "run_ragas_eval.py"):
        source = (backend_dir / script_name).read_text(encoding="utf-8")
        assert '.type == "contexts"' in source
        assert "s.excerpt" not in source


def test_answer_experiment_outputs_are_isolated_from_legacy_dataset():
    backend_dir = Path(__file__).resolve().parents[1]
    source = (backend_dir / "gen_answers.py").read_text(encoding="utf-8")

    for label in ("off", "r070", "r075", "r080"):
        assert f'"{label}"' in source
    assert "eval_dataset_{label}.json" in source
    assert '"evaluations", "datasets"' in source
