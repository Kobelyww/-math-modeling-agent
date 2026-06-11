from __future__ import annotations

from pathlib import Path

from agent_app.rag import PaperRAG


class RagService:
    def __init__(self, index_root: Path, embedding_api_key: str | None = None) -> None:
        self.index_root = Path(index_root)
        self.embedding_api_key = embedding_api_key
        self._instances: dict[str, PaperRAG] = {}

    def build_index(self, knowledge_dir: Path, run_id: str) -> dict:
        self.index_root.mkdir(parents=True, exist_ok=True)
        rag = PaperRAG(
            knowledge_dir=Path(knowledge_dir),
            index_path=self.index_root / f"{run_id}_rag.pkl",
            embedding_api_key=self.embedding_api_key,
        )
        stats = rag.build_index()
        self._instances[run_id] = rag
        return stats

    def query(self, query: str, run_id: str, top_k: int = 6) -> list[str]:
        rag = self._instances.get(run_id)
        if rag is None:
            index_path = self.index_root / f"{run_id}_rag.pkl"
            rag = PaperRAG(knowledge_dir=self.index_root, index_path=index_path)
            if not rag.load_index():
                return []
            self._instances[run_id] = rag
        return [chunk.content for chunk in rag.query(query, top_k=top_k)]
