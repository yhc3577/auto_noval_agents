# ── Backend: Python FastAPI ──────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# pip 国内加速（可选，根据网络情况注释）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/

# 先装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码
COPY src/ ./src/
COPY pyproject.toml .

# FAISS 索引持久化目录
RUN mkdir -p /app/faiss_indexes

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
