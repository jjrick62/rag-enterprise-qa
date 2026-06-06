import asyncio

import pytest
from fastapi import HTTPException

from routers import documents


class _FakeRetriever:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        return 7


class _FakePipeline:
    def __init__(self):
        self._retriever = _FakeRetriever()
        self.ingested = []

    async def ingest(self, file_path: str, category: str):
        self.ingested.append((file_path, category))
        return 3


def test_reingest_all_clears_retriever_without_deleting_database_directory(
    monkeypatch,
):
    pipeline = _FakePipeline()
    saved_states = []

    monkeypatch.setattr(documents, "_get_pipeline", lambda: pipeline)
    monkeypatch.setattr(
        documents.glob,
        "glob",
        lambda pattern: ["first.md", "second.md"],
    )
    monkeypatch.setattr(documents, "_file_hash", lambda path: f"hash:{path}")
    monkeypatch.setattr(documents, "_save_state", saved_states.append)

    result = asyncio.run(documents.reingest_all())

    assert pipeline._retriever.clear_calls == 1
    assert pipeline.ingested == [
        ("first.md", "IBM_Docs"),
        ("second.md", "IBM_Docs"),
    ]
    assert result["total_chunks"] == 6
    assert result["failed"] == []
    assert len(saved_states) == 1


def test_ingest_missing_file_returns_404_before_pipeline_initialization(
    monkeypatch,
):
    missing_path = "definitely-missing-document.md"
    pipeline_requested = False

    def get_pipeline():
        nonlocal pipeline_requested
        pipeline_requested = True
        raise AssertionError("pipeline should not be initialized for a missing file")

    monkeypatch.setattr(documents, "_get_pipeline", get_pipeline)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            documents.ingest_document(
                documents.IngestRequest(file_path=str(missing_path))
            )
        )

    assert exc_info.value.status_code == 404
    assert str(missing_path) in exc_info.value.detail
    assert pipeline_requested is False


def test_force_update_stops_when_existing_vectors_cannot_be_deleted(
    monkeypatch,
):
    file_path = __file__
    file_name = documents.os.path.basename(file_path)

    class FailingRetriever:
        def delete_by_document(self, source_doc):
            raise RuntimeError("vector store unavailable")

    class RecordingPipeline:
        def __init__(self):
            self._retriever = FailingRetriever()
            self.ingest_calls = 0

        async def ingest(self, file_path, category):
            self.ingest_calls += 1
            return 1

    pipeline = RecordingPipeline()
    original_state = {
        "files": {
            file_name: {
                "hash": "old-hash",
                "chunks": 2,
                "category": "General",
            }
        }
    }
    saved_states = []

    monkeypatch.setattr(documents, "_get_pipeline", lambda: pipeline)
    monkeypatch.setattr(documents, "_load_state", lambda: original_state)
    monkeypatch.setattr(documents, "_file_hash", lambda path: "new-hash")
    monkeypatch.setattr(documents, "_save_state", saved_states.append)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            documents.ingest_document(
                documents.IngestRequest(
                    file_path=file_path,
                    category="General",
                    force=True,
                )
            )
        )

    assert exc_info.value.status_code == 500
    assert "vector store unavailable" in exc_info.value.detail
    assert pipeline.ingest_calls == 0
    assert saved_states == []
