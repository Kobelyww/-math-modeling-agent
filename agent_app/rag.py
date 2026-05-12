from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path

import jieba
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 数模领域自定义词典
_MATH_DICT = [
    "层次分析法", "混合整数非线性规划", "变分不等式", "拟牛顿法",
    "NSGA-II", "Pareto前沿", "灰色关联度", "主成分分析", "因子分析",
    "聚类分析", "判别分析", "时间序列", "多元回归", "逻辑回归",
    "支持向量机", "随机森林", "XGBoost", "梯度下降", "遗传算法",
    "模拟退火", "粒子群优化", "蚁群算法", "神经网络", "深度学习",
    "马尔可夫链", "蒙特卡洛", "贝叶斯网络", "最小二乘法", "极大似然",
    "假设检验", "置信区间", "灵敏度分析", "一致性检验", "模糊综合评价",
    "数据包络分析", "博弈论", "排队论", "图论", "动态规划",
    "整数规划", "非线性规划", "多目标优化", "鲁棒优化", "随机规划",
    "变分法", "有限元", "差分方程", "偏微分方程", "常微分方程",
    "傅里叶变换", "拉普拉斯变换", "小波分析", "卡尔曼滤波",
    "熵权法", "TOPSIS法", "秩和比法", "优劣解距离法",
    "收敛性分析", "误差分析", "稳定性分析", "参数估计",
]
for term in _MATH_DICT:
    jieba.add_word(term)

_LATEX_PATTERN = re.compile(
    r'(?:\$\$[\s\S]*?\$\$)|(?:\$[^\$]*?\$)|(?:\\\[[\s\S]*?\\\])|(?:\\\([\s\S]*?\\\))'
)


def _protect_formulas(text: str) -> tuple[str, dict[str, str]]:
    """将 LaTeX 公式替换为占位符，保护其不被 jieba 切碎。"""
    placeholders: dict[str, str] = {}
    counter = [0]

    def _replace(match):
        key = f"__FORMULA_{counter[0]}__"
        placeholders[key] = match.group()
        counter[0] += 1
        return key

    protected = _LATEX_PATTERN.sub(_replace, text)
    return protected, placeholders


def _restore_formulas(text: str, placeholders: dict[str, str]) -> str:
    """恢复被保护的 LaTeX 公式。"""
    result = text
    for key, formula in placeholders.items():
        result = result.replace(key, formula)
    return result


def _jieba_tokenizer(text: str) -> list[str]:
    protected, formulas = _protect_formulas(text)
    tokens = [w.strip() for w in jieba.cut(protected) if w.strip()]
    return [_restore_formulas(t, formulas) for t in tokens]


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

    def query(self, question: str, top_k: int = 6, min_threshold: float | None = None) -> list[Chunk]:
        if not question.strip():
            return []
        if self.vectorizer is None or self.matrix is None or not self.chunks:
            if not self.load_index():
                return []
        query_vec = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vec, self.matrix).flatten()

        # 动态阈值：取 top_k 内平均分的 30% 作为下限
        ranked = scores.argsort()[::-1]
        top_scores = scores[ranked[:max(top_k, 1)]]
        if min_threshold is None:
            mean_score = float(top_scores.mean()) if len(top_scores) > 0 else 0.0
            min_threshold = max(0.03, mean_score * 0.3)

        # 初选：阈值过滤
        candidates = [
            (i, scores[i]) for i in ranked
            if scores[i] >= min_threshold
        ][:top_k * 2]  # 多取一些供 MMR 筛选

        if not candidates:
            return []

        # MMR 去重：优先相关度高且内容不重复的 chunk
        selected: list[Chunk] = []
        used_contents: list[str] = []

        best_idx, best_score = candidates[0]
        selected.append(self.chunks[best_idx])
        used_contents.append(self.chunks[best_idx].content)

        for idx, score in candidates[1:]:
            if len(selected) >= top_k:
                break
            content = self.chunks[idx].content
            # 简单去重：与已选 chunk 的 Jaccard 重合度
            overlap_ratio = self._content_overlap(content, used_contents)
            if overlap_ratio < 0.5:
                selected.append(self.chunks[idx])
                used_contents.append(content)

        return selected

    @staticmethod
    def _content_overlap(content: str, existing: list[str]) -> float:
        """计算 content 与已有内容的最高词语重合率（0-1）。"""
        words = set(content)
        if not words:
            return 0.0
        max_overlap = 0.0
        for existing_content in existing:
            existing_words = set(existing_content)
            overlap = len(words & existing_words) / len(words)
            if overlap > max_overlap:
                max_overlap = overlap
        return max_overlap

    @property
    def is_ready(self) -> bool:
        return self.vectorizer is not None and len(self.chunks) > 0