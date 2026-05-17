# AI 长篇小说自动生成系统

基于大语言模型（LLM）的全自动长篇小说创作平台。支持多题材、多文风，自动生成大纲体系，一键启动无人值守的全自动创作流水线。

## 核心功能

- **小说项目管理** — 创建小说项目，配置题材、文风、世界观、角色人设、章节数量
- **三层大纲生成** — 自动生成全书总纲 → 分卷大纲 → 逐章细纲，层层约束保证剧情连贯
- **全自动创作流水线** — 逐章自动写作：正文创作 → 摘要提取 → 质量审核 → 版权校验，全流程无人值守
- **质量与版权保障** — 剧情审核不通过自动重写（最多 3 次），版权相似度超标自动降重
- **多 LLM 适配** — 支持 vLLM、DeepSeek、Minimax、Mimo、OpenAI 等多种大模型
- **向量记忆检索** — 基于 FAISS 的长期记忆系统，长篇小说人物关系、剧情伏笔不遗忘
- **多格式导出** — 支持 TXT / HTML / EPUB 一键导出

## 技术栈

| 层 | 技术 |
|---|------|
| **后端** | Python 3.11 + FastAPI + LangChain + LangGraph |
| **前端** | Vue 3 + TypeScript + Element Plus + Pinia |
| **数据库** | MongoDB（持久化）+ Redis（缓存/任务队列） |
| **向量库** | FAISS（故事记忆检索） |
| **容器化** | Docker + Docker Compose |

## 快速开始

### 本地开发

**后端**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 配置 LLM
bash dev.sh
# API 文档: http://localhost:8080/docs
```

**前端**

```bash
cd frontend
npm install
cp .env.example .env   # 编辑 .env 配置 API 地址
npm run dev
# 前端页面: http://localhost:5173
```

### Docker 部署

```bash
# 1. 准备配置
cp .env.example .env   # 编辑 .env，配置 LLM 密钥和 MongoDB/Redis 连接

# 2. 本地构建镜像
./scripts/docker-build.sh

# 3. 一键部署到服务器
./scripts/docker-deploy.sh root@你的服务器IP:/opt/novel
```

详细部署说明见上一节 Docker 部署文档。

## 项目结构

```
novel/
├── backend/                 # FastAPI 后端
│   ├── src/
│   │   ├── agents/          # AI Agent：规划/写作/审核/版权检查
│   │   ├── api/             # REST API 路由
│   │   ├── core/            # 核心模块：配置/数据库/认证/LLM
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 业务服务：创作/缓存/向量检索
│   │   └── utils/           # 工具：日志/密码
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── components/      # 通用组件
│   │   ├── views/           # 页面：首页/创作/章节/导出/登录
│   │   ├── stores/          # Pinia 状态管理
│   │   ├── services/        # API 请求封装
│   │   └── router/          # 路由配置
│   ├── Dockerfile
│   └── package.json
├── scripts/                 # 部署脚本
│   ├── docker-build.sh      # 本地构建镜像
│   ├── docker-deploy.sh     # 一键部署
│   ├── docker-compose.yml   # 容器编排
│   └── .env                 # 部署环境变量
└── docker-compose.yml       # 容器编排（项目根目录）
```

## API 概览

| 接口 | 说明 |
|------|------|
| `POST /api/auth/register` | 用户注册 |
| `POST /api/auth/login` | 用户登录 |
| `POST /api/novels` | 创建小说项目 |
| `GET /api/novels` | 获取小说列表 |
| `GET /api/novels/{id}` | 获取小说详情（含大纲） |
| `POST /api/creations/{novel_id}/start` | 启动全自动创作 |
| `POST /api/creations/{novel_id}/pause` | 暂停创作 |
| `POST /api/creations/{novel_id}/resume` | 恢复创作 |
| `GET /api/chapters/{novel_id}` | 获取章节列表 |
| `GET /api/chapters/{novel_id}/{chapter_no}` | 获取章节详情 |
| `POST /api/export/{novel_id}` | 导出小说 |

完整 API 文档见 [backend/API.md](backend/API.md)，或启动后端后访问 `http://localhost:8080/docs`。

## 支持的 LLM 模型

在 `.env` 中配置 `LLM_PROVIDER` 即可切换：

| Provider | 配置值 | 说明 |
|----------|--------|------|
| vLLM | `vllm` | 本地/自部署模型 |
| DeepSeek | `deepseek` | DeepSeek Chat API |
| Minmax | `minimax` | MiniMax M2 API |
| Mimo | `mimo` | Mimo 系列模型 |
| OpenAI | `openai` | OpenAI 兼容 API |

## License

MIT
