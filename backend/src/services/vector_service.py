"""FAISS 向量库管理：索引创建、向量存储、语义检索"""

import json
import os
from pathlib import Path

import faiss
import numpy as np

from ..core.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VectorService:
    """FAISS 向量库管理服务"""

    def __init__(self):
        self.index_path = Path(settings.faiss_index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_id: str) -> Path:
        """获取项目向量库目录"""
        project_dir = self.index_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def _get_copyright_dir(self) -> Path:
        """获取公共版权比对库目录"""
        copyright_dir = self.index_path / "copyright"
        copyright_dir.mkdir(parents=True, exist_ok=True)
        return copyright_dir

    def create_project_index(self, project_id: str, dimension: int = 768):
        """为项目创建 FAISS 索引（已存在但维度不匹配时自动重建）"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        if index_file.exists():
            existing = faiss.read_index(str(index_file))
            if existing.d != dimension:
                logger.warning(
                    f"FAISS 索引维度不匹配 (现有: {existing.d}, 期望: {dimension})，重建索引"
                )
                index_file.unlink()
                mapping_file.unlink(missing_ok=True)

        if not index_file.exists():
            index = faiss.IndexFlatL2(dimension)
            faiss.write_index(index, str(index_file))
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            logger.info(f"为项目 {project_id} 创建 FAISS 索引 (dim={dimension})")

    def add_vectors(
        self, project_id: str, vectors: list[list[float]], metadata: list[dict]
    ):
        """向项目索引中添加向量和元数据"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        vec_dim = len(vectors[0])
        if not index_file.exists():
            self.create_project_index(project_id, vec_dim)

        # 读取索引和映射
        index = faiss.read_index(str(index_file))
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        # 最后一次防线：维度不匹配则重建
        if index.d != vec_dim:
            logger.warning(
                f"FAISS 索引维度不匹配 (索引: {index.d}, 向量: {vec_dim})，重建索引后重试"
            )
            index_file.unlink()
            mapping_file.unlink(missing_ok=True)
            self.create_project_index(project_id, vec_dim)
            index = faiss.read_index(str(index_file))
            mapping = []

        # 添加向量
        vectors_np = np.array(vectors, dtype=np.float32)
        index.add(vectors_np)

        # 更新映射
        start_id = len(mapping)
        for i, meta in enumerate(metadata):
            mapping.append({"id": start_id + i, **meta})

        # 保存
        faiss.write_index(index, str(index_file))
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False)

    def search(
        self, project_id: str, query_vector: list[float], top_k: int = 5
    ) -> list[dict]:
        """在项目索引中语义检索"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        if not index_file.exists():
            return []

        index = faiss.read_index(str(index_file))
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        if index.ntotal == 0:
            return []

        query_np = np.array([query_vector], dtype=np.float32)
        distances, indices = index.search(query_np, min(top_k, index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(mapping):
                results.append({**mapping[idx], "distance": float(dist)})
        return results

    def remove_vectors_by_chapter(self, project_id: str, chapter_number: int):
        """按章节号移除向量（重建索引，跳过指定章节）"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        if not index_file.exists():
            return

        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        # 过滤掉目标章节
        new_mapping = [m for m in mapping if m.get("chapter_number") != chapter_number]
        removed = len(mapping) - len(new_mapping)
        if removed == 0:
            return

        if not new_mapping:
            # 全部移除：重建空索引
            index_file.unlink()
            mapping_file.unlink(missing_ok=True)
            logger.info(f"FAISS 索引已清空: project={project_id}, chapter={chapter_number}")
            return

        # 重建索引
        import faiss
        import numpy as np
        index = faiss.read_index(str(index_file))
        dim = index.d
        new_index = faiss.IndexFlatL2(dim)
        new_vectors = np.zeros((len(new_mapping), dim), dtype=np.float32)

        # 从旧索引中提取保留的向量
        old_index = index
        for i, m in enumerate(new_mapping):
            old_id = m["id"]
            new_vectors[i] = old_index.reconstruct(old_id)

        new_index.add(new_vectors)

        # 更新映射 ID
        for i, m in enumerate(new_mapping):
            m["id"] = i

        faiss.write_index(new_index, str(index_file))
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(new_mapping, f, ensure_ascii=False)
        logger.info(f"FAISS 已移除: project={project_id}, chapter={chapter_number}, 剩余 {len(new_mapping)} 条")

    def search_copyright(
        self, query_vector: list[float], top_k: int = 5
    ) -> list[dict]:
        """在公共版权比对库中检索相似内容"""
        copyright_dir = self._get_copyright_dir()
        index_file = copyright_dir / "copyright.index"
        mapping_file = copyright_dir / "mapping.json"

        if not index_file.exists():
            return []

        index = faiss.read_index(str(index_file))
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        if index.ntotal == 0:
            return []

        query_np = np.array([query_vector], dtype=np.float32)
        distances, indices = index.search(query_np, min(top_k, index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(mapping):
                results.append({**mapping[idx], "distance": float(dist)})
        return results
