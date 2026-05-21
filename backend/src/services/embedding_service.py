"""Embedding 服务：将文本转为向量，用于 FAISS 语义检索"""

import os
import threading

from ..utils.logger import get_logger

logger = get_logger(__name__)

# 本地 text2vec-base-chinese 模型，768 维，仅 CPU 推理
_MODEL_NAME = "/data/my_models/my_models/text2vec-base-chinese"
_DIMENSION = 768
_MODEL = None
_LOCK = threading.Lock()

# 在 torch 首次被 import 前强制禁用 CUDA，避免与 vLLM 争抢 GPU 显存导致 OOM
os.environ["CUDA_VISIBLE_DEVICES"] = ""


def _get_model():
    """懒加载 embedding 模型（线程安全）"""
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                from sentence_transformers import SentenceTransformer

                logger.info(f"加载 embedding 模型: {_MODEL_NAME}")
                _MODEL = SentenceTransformer(_MODEL_NAME, device="cpu")
                logger.info(f"embedding 模型加载完成，维度: {_MODEL.get_sentence_embedding_dimension()}")
    return _MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表转为向量列表"""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_text(text: str) -> list[float]:
    """将单个文本转为向量"""
    return embed_texts([text])[0]


def get_dimension() -> int:
    """返回当前 embedding 模型的向量维度"""
    return _DIMENSION


def build_chapter_embedding_text(
    chapter_number: int,
    chapter_summary: str,
    key_events: list[str],
    character_changes: list[str],
    foreshadowing: list[str],
) -> str:
    """拼接章节摘要和结构化信息，作为 embedding 的输入文本"""
    parts = [f"第{chapter_number}章"]
    if chapter_summary:
        parts.append(f"摘要: {chapter_summary}")
    if key_events:
        parts.append(f"关键事件: {'; '.join(key_events)}")
    if character_changes:
        parts.append(f"人物变化: {'; '.join(character_changes)}")
    if foreshadowing:
        parts.append(f"伏笔: {'; '.join(foreshadowing)}")
    return "\n".join(parts)


def build_query_embedding_text(chapter_outline: str, chapter_number: int) -> str:
    """拼接查询文本（用于检索相关前文章节）"""
    return f"第{chapter_number}章大纲: {chapter_outline}"
