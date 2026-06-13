from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class LLMConfig:
    """LLM配置"""
    primary_model: str = "mimo-v2.5"
    multimodal_model: str = "mimo-v2.5"
    embedding_model: str = "mimo-v2.5-embedding"
    api_base: str = "https://api.mimo.example.com"
    api_key: str = ""
    temperature: float = 0.3
    max_retries: int = 3
    
    def get_model_for_task(self, task_type: str) -> str:
        """根据任务类型获取合适的模型"""
        if task_type in ["multimodal", "image_understanding", "ocr"]:
            return self.multimodal_model
        elif task_type == "embedding":
            return self.embedding_model
        else:
            return self.primary_model

@dataclass
class ParserConfig:
    """解析器配置"""
    marker_model_path: str = "marker-model"
    use_local_marker: bool = True
    enable_ocr: bool = True
    max_file_size_mb: int = 100

@dataclass
class RAGConfig:
    """RAG配置"""
    vector_db_type: str = "chromadb"
    vector_db_path: str = "./data/vector_db"
    embedding_dim: int = 768
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5

@dataclass
class MemoryConfig:
    """记忆配置"""
    stm_max_tokens: int = 50000
    recent_window_size: int = 5
    compress_trigger: int = 30000
    ltm_db_path: str = "./data/long_term_memory.db"

@dataclass
class AppConfig:
    """应用配置"""
    llm: Optional[LLMConfig] = None
    parser: Optional[ParserConfig] = None
    rag: Optional[RAGConfig] = None
    memory: Optional[MemoryConfig] = None
    
    def __post_init__(self):
        if self.llm is None:
            self.llm = LLMConfig()
        if self.parser is None:
            self.parser = ParserConfig()
        if self.rag is None:
            self.rag = RAGConfig()
        if self.memory is None:
            self.memory = MemoryConfig()

def load_config() -> AppConfig:
    """从环境变量加载配置"""
    return AppConfig(
        llm=LLMConfig(
            primary_model=os.getenv("LLM_PRIMARY_MODEL", "mimo-v2.5"),
            multimodal_model=os.getenv("LLM_MULTIMODAL_MODEL", "mimo-v2.5"),
            embedding_model=os.getenv("LLM_EMBEDDING_MODEL", "mimo-v2.5-embedding"),
            api_key=os.getenv("MIMO_API_KEY", ""),
            api_base=os.getenv("MIMO_API_BASE", "https://api.mimo.example.com"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        ),
        parser=ParserConfig(
            marker_model_path=os.getenv("MARKER_MODEL_PATH", "marker-model"),
            use_local_marker=os.getenv("PARSER_USE_LOCAL_MARKER", "true").lower() == "true",
            enable_ocr=os.getenv("PARSER_ENABLE_OCR", "true").lower() == "true",
            max_file_size_mb=int(os.getenv("PARSER_MAX_FILE_SIZE_MB", "100")),
        ),
        rag=RAGConfig(
            vector_db_type=os.getenv("RAG_VECTOR_DB_TYPE", "chromadb"),
            vector_db_path=os.getenv("VECTOR_DB_PATH", "./data/vector_db"),
            embedding_dim=int(os.getenv("RAG_EMBEDDING_DIM", "768")),
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200")),
            top_k=int(os.getenv("RAG_TOP_K", "5")),
        ),
        memory=MemoryConfig(
            stm_max_tokens=int(os.getenv("MEMORY_STM_MAX_TOKENS", "50000")),
            recent_window_size=int(os.getenv("MEMORY_RECENT_WINDOW_SIZE", "5")),
            compress_trigger=int(os.getenv("MEMORY_COMPRESS_TRIGGER", "30000")),
            ltm_db_path=os.getenv("LTM_DB_PATH", "./data/long_term_memory.db"),
        ),
    )
