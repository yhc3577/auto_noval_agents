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
        """为项目创建 FAISS 索引"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        if not index_file.exists():
            index = faiss.IndexFlatL2(dimension)
            faiss.write_index(index, str(index_file))
            # 初始化映射文件
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            logger.info(f"为项目 {project_id} 创建 FAISS 索引")

    def add_vectors(
        self, project_id: str, vectors: list[list[float]], metadata: list[dict]
    ):
        """向项目索引中添加向量和元数据"""
        project_dir = self._get_project_dir(project_id)
        index_file = project_dir / "memory.index"
        mapping_file = project_dir / "mapping.json"

        if not index_file.exists():
            self.create_project_index(project_id, len(vectors[0]))

        # 读取索引和映射
        index = faiss.read_index(str(index_file))
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

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
