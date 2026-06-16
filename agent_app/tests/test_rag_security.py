"""Tests for RAG index freshness and safe loading."""

from __future__ import annotations

import pickle

from agent_app.rag import PaperRAG


def test_load_index_rejects_legacy_pickle_without_metadata(tmp_path):
    knowledge_dir = tmp_path / "kb"
    knowledge_dir.mkdir()
    index_path = tmp_path / "rag_index.pkl"
    index_path.write_bytes(pickle.dumps({"vectorizer": object(), "matrix": object(), "chunks": []}))

    rag = PaperRAG(knowledge_dir=knowledge_dir, index_path=index_path)

    assert rag.load_index() is False
    assert rag.vectorizer is None
    assert rag.matrix is None
    assert rag.chunks == []


def test_load_index_rejects_stale_index_when_source_changes(tmp_path):
    knowledge_dir = tmp_path / "kb"
    knowledge_dir.mkdir()
    source = knowledge_dir / "modeling.md"
    source.write_text("first version", encoding="utf-8")
    index_path = tmp_path / "rag_index.pkl"

    rag = PaperRAG(knowledge_dir=knowledge_dir, index_path=index_path)
    assert rag.build_index()["chunks"] > 0

    source.write_text("changed version", encoding="utf-8")

    fresh = PaperRAG(knowledge_dir=knowledge_dir, index_path=index_path)
    assert fresh.load_index() is False
