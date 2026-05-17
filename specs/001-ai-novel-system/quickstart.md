# 快速启动指南：AI长篇小说自动生成系统

**日期**: 2026-05-10

## 前置条件

- Python 3.11+
- Node.js 18+
- MongoDB 6.0+（已通过 Docker 运行在 27017）
- Redis 7.0+（已通过 Docker 运行在 6379）
- LLM 服务（以下任选其一）：
  - **本地 vLLM**：已部署在 localhost:8000
  - **DeepSeek API**：需要 API Key
  - **Minimax API**：需要 API Key
  - **Mimo API**：需要 API Key

## 端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| vLLM | 8000 | 本地大模型推理服务 |
| FastAPI 后端 | 8080 | 本系统后端 API |
| Vue 前端 | 5173 | 本系统前端页面 |
| MongoDB | 27017 | 数据库 |
| Redis | 6379 | 缓存 |

## 后端启动

### 1. 安装依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，选择 LLM Provider：

**使用本地 vLLM（默认）**：
```bash
LLM_PROVIDER=vllm
LLM_API_KEY=EMPTY
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
LLM_BASE_URL=http://localhost:8000/v1
```

**使用 DeepSeek**：
```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=your-deepseek-api-key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
```

**使用 Minimax**：
```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your-minimax-api-key
LLM_MODEL=MiniMax-Text-01
LLM_BASE_URL=https://api.minimax.chat/v1
```

**使用 Mimo**：
```bash
LLM_PROVIDER=mimo
LLM_API_KEY=your-mimo-api-key
LLM_MODEL=mimo-2.5-pro
LLM_BASE_URL=https://api.mimo.ai/v1
```

### 3. 启动服务

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

后端服务启动后访问 http://localhost:8080/docs 查看 API 文档。

## 前端启动

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

前端访问 http://localhost:5173。API 请求会自动代理到 http://localhost:8080。

## 验证流程

### 1. 注册并登录

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

### 2. 创建小说项目

```bash
curl -X POST http://localhost:8080/api/novel/create \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试小说",
    "genre": "玄幻",
    "style": "热血",
    "world_setting": "修仙世界，分为九大境界...",
    "chapter_count": 50,
    "words_per_chapter": 3000,
    "characters": [
      {
        "name": "李天",
        "role_type": "protagonist",
        "personality": "坚韧不拔、重情重义",
        "background": "出身贫寒的少年"
      }
    ]
  }'
```

### 3. 启动创作

```bash
curl -X POST http://localhost:8080/api/novel/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<project_id>"}'
```

### 4. 查看进度

在前端页面打开创作控制台，或通过 SSE 接口：

```bash
curl -N http://localhost:8080/api/novel/progress?project_id=<project_id> \
  -H "Authorization: Bearer <token>"
```

## 常见问题

### Q: 创作过程中断了怎么办？

A: 系统支持断点续跑。进度已自动保存到 Redis，重新调用 `/api/novel/start` 即可从断点继续。

### Q: 如何切换大模型？

A: 修改 `.env` 中的 `LLM_PROVIDER`、`LLM_API_KEY`、`LLM_MODEL` 和 `LLM_BASE_URL` 配置，重启服务即可。所有 provider 统一使用 OpenAI 兼容接口。

### Q: 版权查重阈值如何调整？

A: 调用 `/api/novel/update` 接口修改 `copyright_threshold` 字段，值越低越严格。

### Q: vLLM 端口冲突怎么办？

A: vLLM 默认占用 8000 端口，本系统后端默认使用 8080 端口，不会冲突。如需修改，编辑 `.env` 中的 `SERVER_PORT`。
