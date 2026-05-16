from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path

import jieba
import base64
import io

import fitz  # PyMuPDF
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


def _extract_pdf_images(path: Path) -> list[bytes]:
    """使用 PyMuPDF 从 PDF 中提取嵌入图片的原始字节。"""
    images: list[bytes] = []
    try:
        doc = fitz.open(str(path))
        for page in doc:
            for img_tuple in page.get_images(full=True):
                xref = img_tuple[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        images.append(base_image["image"])
                except Exception:
                    continue
        doc.close()
    except Exception:
        pass
    return images


def _describe_images_with_vl(images: list[bytes], api_key: str) -> list[str]:
    """使用 Qwen-VL 多模态模型对图片生成文字描述。"""
    if not images or not api_key:
        return []

    try:
        from dashscope import MultiModalConversation
    except ImportError:
        return []

    descriptions: list[str] = []
    for i, img_bytes in enumerate(images):
        # 跳过太小的图片（可能是图标或装饰元素）
        if len(img_bytes) < 2048:
            continue

        # 限制图片数量，避免 API 调用过多
        if i >= 10:
            break

        b64 = base64.b64encode(img_bytes).decode()
        messages = [{
            "role": "user",
            "content": [
                {"image": f"data:image/png;base64,{b64}"},
                {"text": "请详细描述这张图片中的内容。如果是数据图表，说明图表类型、坐标轴、趋势和关键数据；如果是数学公式，完整写出公式；如果是流程图或示意图，说明结构和关键节点。请用中文回答，控制在200字以内。"},
            ],
        }]
        try:
            resp = MultiModalConversation.call(
                model="qwen-vl-plus",
                api_key=api_key,
                messages=messages,
            )
            if resp.status_code == 200:
                text = resp.output.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(text, list):
                    text = " ".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in text
                    )
                if text.strip():
                    descriptions.append(f"[图片描述 {len(descriptions) + 1}] {text.strip()}")
        except Exception:
            continue

    return descriptions


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf_file(path: Path, vl_api_key: str | None = None) -> str:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # 提取 PDF 中嵌入的图片，用 Qwen-VL 生成描述
    if vl_api_key:
        images = _extract_pdf_images(path)
        if images:
            descriptions = _describe_images_with_vl(images, vl_api_key)
            if descriptions:
                text += "\n\n## 图片内容描述\n" + "\n".join(descriptions)

    return text


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
    def __init__(self, knowledge_dir: Path, index_path: Path, embedding_api_key: str | None = None, vl_api_key: str | None = None) -> None:
        self.knowledge_dir = knowledge_dir
        self.index_path = index_path
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.chunks: list[Chunk] = []
        self.embedding_api_key = embedding_api_key
        self.vl_api_key = vl_api_key or embedding_api_key
        self._embedding_matrix = None

    def _iter_files(self) -> list[Path]:
        if not self.knowledge_dir.exists():
            return []
        files: list[Path] = []
        for pattern in ("*.pdf", "*.md", "*.txt"):
            files.extend(self.knowledge_dir.rglob(pattern))
        return sorted(set(files))

    def _read_file(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return _read_pdf_file(path, self.vl_api_key)
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

    # =============== 阿里云百练 Embedding 检索 ===============

    def build_embedding_index(self, batch_size: int = 25) -> dict:
        """使用阿里云百练 text-embedding-v2 构建向量索引。"""
        if not self.embedding_api_key:
            return {"error": "未配置 embedding_api_key"}

        # 确保 chunks 已加载
        if not self.chunks:
            files = self._iter_files()
            if not files:
                return {"files": 0, "chunks": 0}

        try:
            import numpy as np
            from dashscope import TextEmbedding
        except ImportError:
            return {"error": "请安装 dashscope: pip install dashscope"}

        chunk_texts = [c.content for c in self.chunks]
        all_embeddings: list[np.ndarray] = []

        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i : i + batch_size]
            resp = TextEmbedding.call(
                model="text-embedding-v2",
                api_key=self.embedding_api_key,
                input=batch,
            )
            if resp.status_code != 200:
                return {"error": f"Embedding API 失败: {resp.code} {resp.message}"}
            for item in resp.output.get("embeddings", []):
                all_embeddings.append(np.array(item["embedding"]))

        self._embedding_matrix = np.stack(all_embeddings)
        return {"files": len(set(c.source for c in self.chunks)), "chunks": len(self.chunks), "dim": self._embedding_matrix.shape[1]}

    def query_embedding(self, question: str, top_k: int = 6) -> list[tuple[Chunk, float]]:
        """使用 embedding 向量相似度检索（语义匹配）。"""
        if self._embedding_matrix is None:
            if not self.build_embedding_index():
                return []

        import numpy as np
        from dashscope import TextEmbedding

        resp = TextEmbedding.call(
            model="text-embedding-v2",
            api_key=self.embedding_api_key,
            input=question,
        )
        if resp.status_code != 200:
            return []

        query_vec = np.array(resp.output["embeddings"][0]["embedding"])
        scores = np.dot(self._embedding_matrix, query_vec) / (
            np.linalg.norm(self._embedding_matrix, axis=1) * np.linalg.norm(query_vec) + 1e-10
        )
        ranked = scores.argsort()[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in ranked if scores[i] > 0.3]

    def query_hybrid(self, question: str, top_k: int = 6, alpha: float = 0.5) -> list[Chunk]:
        """混合检索：TF-IDF（关键词） + Embedding（语义），alpha 控制语义权重。"""
        tfidf_results = self.query(question, top_k=top_k)
        if self._embedding_matrix is None and not self.embedding_api_key:
            return tfidf_results

        emb_results = self.query_embedding(question, top_k=top_k)

        if not emb_results:
            return tfidf_results
        if not tfidf_results:
            return [c for c, _ in emb_results]

        # 融合分数
        tfidf_scores: dict[str, float] = {}
        for i, c in enumerate(tfidf_results):
            tfidf_scores[c.content[:60]] = 1.0 - i / max(len(tfidf_results), 1)

        emb_scores: dict[int, float] = {}
        for c, s in emb_results:
            for j, tc in enumerate(self.chunks):
                if tc.source == c.source and tc.chunk_id == c.chunk_id:
                    emb_scores[j] = s
                    break

        combined: list[tuple[Chunk, float]] = []
        for i, c in enumerate(tfidf_results):
            key = c.content[:60]
            tfidf_s = tfidf_scores.get(key, 0.0)
            emb_s = emb_scores.get(i, 0.0)
            score = alpha * emb_s + (1 - alpha) * tfidf_s
            combined.append((c, score))

        combined.sort(key=lambda x: x[1], reverse=True)
        return self._dedup([c for c, _ in combined[: top_k * 2]])[:top_k]

    def _dedup(self, chunks: list[Chunk]) -> list[Chunk]:
        seen: set[str] = set()
        result: list[Chunk] = []
        for c in chunks:
            key = c.content[:60]
            if key not in seen:
                seen.add(key)
                result.append(c)
        return result

    @property
    def has_embeddings(self) -> bool:
        return self._embedding_matrix is not None