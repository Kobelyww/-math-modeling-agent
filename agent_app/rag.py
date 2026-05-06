from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import jieba
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _jieba_tokenizer(text: str) -> list[str]:
    return [w.strip() for w in jieba.cut(text) if w.strip()]


@dataclass
class Chunk:
    source: str
    chunk_id: int
    content: str


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf_file(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    text_len = len(cleaned)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(cleaned[start:end])
        if end >= text_len:
            break
        start = max(end - overlap, 0)
    return chunks


class PaperRAG:
    def __init__(self, knowledge_dir: Path, index_path: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self.index_path = index_path
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.chunks: list[Chunk] = []

    def _iter_files(self) -> list[Path]:
        if not self.knowledge_dir.exists():
            return []
        files: list[Path] = []
        for pattern in ("*.pdf", "*.md", "*.txt"):
            files.extend(self.knowledge_dir.rglob(pattern))
        return sorted(set(files))

    def _read_file(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return _read_pdf_file(path)
        return _read_text_file(path)

    def build_index(self) -> dict:
        files = self._iter_files()
        all_chunks: list[Chunk] = []
        for file_path in files:
            text = self._read_file(file_path)
            for idx, chunk_text in enumerate(_chunk_text(text)):
                all_chunks.append(Chunk(source=file_path.name, chunk_id=idx, content=chunk_text))

        if not all_chunks:
            self.vectorizer = None
            self.matrix = None
            self.chunks = []
            return {"files": 0, "chunks": 0}

        self.chunks = all_chunks
        self.vectorizer = TfidfVectorizer(
            tokenizer=_jieba_tokenizer,
            max_features=7000,
            ngram_range=(1, 2),
        )
        self.matrix = self.vectorizer.fit_transform([c.content for c in self.chunks])

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("wb") as fp:
            pickle.dump(
                {"vectorizer": self.vectorizer, "matrix": self.matrix, "chunks": self.chunks},
                fp,
            )

        return {"files": len(files), "chunks": len(all_chunks)}

    def load_index(self) -> bool:
        if not self.index_path.exists():
            return False
        with self.index_path.open("rb") as fp:
            data = pickle.load(fp)
        self.vectorizer = data["vectorizer"]
        self.matrix = data["matrix"]
        self.chunks = data["chunks"]
        return True

    def query(self, question: str, top_k: int = 6) -> list[Chunk]:
        if not question.strip():
            return []
        if self.vectorizer is None or self.matrix is None or not self.chunks:
            if not self.load_index():
                return []
        query_vec = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = scores.argsort()[::-1][:top_k]
        return [self.chunks[i] for i in ranked if scores[i] > 0]

    @property
    def is_ready(self) -> bool:
        return self.vectorizer is not None and len(self.chunks) > 0