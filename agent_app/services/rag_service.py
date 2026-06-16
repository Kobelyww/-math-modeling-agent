from __future__ import annotations

from pathlib import Path

from agent_app.infra.paths import ensure_within, validate_run_id
from agent_app.rag import PaperRAG


class RagService:
    def __init__(self, index_root: Path, embedding_api_key: str | None = None) -> None:
        self.index_root = Path(index_root).resolve()
        self.embedding_api_key = embedding_api_key
        self._instances: dict[str, PaperRAG] = {}

    def _index_path(self, run_id: str) -> Path:
        safe_run_id = validate_run_id(run_id)
        return ensure_within(self.index_root / f"{safe_run_id}_rag.pkl", self.index_root)

    def build_index(self, knowledge_dir: Path, run_id: str) -> dict:
        self.index_root.mkdir(parents=True, exist_ok=True)
        index_path = self._index_path(run_id)
        rag = PaperRAG(
            knowledge_dir=Path(knowledge_dir),
            index_path=index_path,
            embedding_api_key=self.embedding_api_key,
        )
        stats = rag.build_index()
        self._instances[run_id] = rag
        return stats

    def query(self, query: str, run_id: str, top_k: int = 6) -> list[str]:
        index_path = self._index_path(run_id)
        rag = self._instances.get(run_id)
        if rag is None:
            rag = PaperRAG(knowledge_dir=self.index_root, index_path=index_path)
            if not rag.load_index():
                return []
            self._instances[run_id] = rag
        return [chunk.content for chunk in rag.query(query, top_k=top_k)]
