# 任务列表：AI长篇小说自动生成系统

**输入**: 设计文档 `specs/001-ai-novel-system/`
**前置**: plan.md（必需）、spec.md（必需）、data-model.md、contracts/api.md、research.md、quickstart.md

## 格式: `[ID] [P?] [Story] 描述`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1、US2、US3、US4、US5）
- 包含精确文件路径

## 路径约定

- 后端: `backend/src/`, `backend/tests/`
- 前端: `frontend/src/`, `frontend/tests/`

---

## 阶段 1: 项目初始化

**目的**: 搭建项目基础结构和开发环境

- [x] T001 创建后端项目结构 `backend/src/` 下的 api/、agents/、models/、services/、core/、utils/ 目录
- [x] T002 创建前端项目结构 `frontend/src/` 下的 views/、components/、stores/、services/、router/ 目录
- [x] T003 [P] 初始化后端依赖：FastAPI、Motor、aioredis、LangChain、LangGraph、FAISS、PyJWT、bcrypt 在 `backend/requirements.txt`
- [x] T004 [P] 初始化前端依赖：Vue 3、TypeScript、Element Plus、Pinia、Axios、Vue Router 在 `frontend/package.json`
- [x] T005 [P] 配置后端环境变量模板在 `backend/.env.example`（MONGODB_URL、REDIS_URL、SECRET_KEY、LLM_API_KEY、LLM_MODEL）
- [x] T006 [P] 配置前端环境变量模板在 `frontend/.env.example`（VITE_API_BASE_URL）
- [x] T007 [P] 配置 Python 代码规范：pyproject.toml 中的 ruff/mypy 配置在 `backend/pyproject.toml`
- [x] T008 [P] 配置前端代码规范：ESLint + Prettier 在 `frontend/.eslintrc.cjs` 和 `frontend/.prettierrc`

---

## 阶段 2: 基础设施（阻塞前置）

**目的**: 所有用户故事依赖的核心基础设施

**⚠️ 关键**: 用户故事实现必须等待此阶段完成

- [x] T009 实现数据库连接管理：MongoDB Motor 异步客户端、Redis aioredis 连接池在 `backend/src/core/database.py`
- [x] T010 [P] 实现 Redis 缓存服务：状态快照、分布式锁、进度缓存在 `backend/src/services/cache_service.py`
- [x] T011 [P] 实现 FAISS 向量库管理：索引创建、向量存储、语义检索在 `backend/src/services/vector_service.py`
- [x] T012 [P] 实现 JWT 认证中间件：Token 生成、验证、用户提取在 `backend/src/core/auth.py`
- [x] T013 [P] 实现密码哈希工具：bcrypt 加密和验证在 `backend/src/utils/password.py`
- [x] T014 [P] 实现结构化日志工具：JSON 格式业务日志在 `backend/src/utils/logger.py`
- [x] T015 [P] 实现 LLM 调用封装：LangChain 统一接口、多模型支持在 `backend/src/core/llm.py`
- [x] T016 实现 NovelState 状态机定义：LangGraph 全局 State TypedDict 在 `backend/src/core/state.py`
- [x] T017 实现 LangGraph 流水线编排：6Agent 节点连接、条件路由、循环重写逻辑在 `backend/src/agents/pipeline.py`
- [x] T018 实现 FastAPI 应用入口：CORS、路由注册、异常处理、启动事件在 `backend/src/main.py`
- [x] T019 实现 Vue 前端入口：路由配置、Pinia store 初始化、Axios 拦截器在 `frontend/src/main.ts` 和 `frontend/src/router/index.ts`
- [x] T020 [P] 实现前端 API 调用基础封装：Axios 实例、Token 注入、错误处理在 `frontend/src/services/api.ts`
- [x] T021 [P] 实现前端认证状态管理：登录状态、Token 存储、用户信息在 `frontend/src/stores/auth.ts`

**检查点**: 基础设施就绪，用户故事可并行实现

---

## 阶段 3: 用户故事 1 - 创建小说项目（优先级：P1）🎯 MVP

**目标**: 用户创建小说项目，配置参数，系统生成三层大纲

**独立测试**: 用户创建项目 → 填写配置 → 查看生成的大纲 → 验证大纲符合配置

### 用户故事 1 的数据模型

- [x] T022 [P] [US1] 实现 User 数据模型在 `backend/src/models/user.py`
- [x] T023 [P] [US1] 实现 NovelProject 数据模型在 `backend/src/models/novel_project.py`
- [x] T024 [P] [US1] 实现 Outline 数据模型在 `backend/src/models/outline.py`
- [x] T025 [P] [US1] 实现 Character 数据模型在 `backend/src/models/character.py`

### 用户故事 1 的后端服务

- [x] T026 [US1] 实现用户注册服务：用户名校验、密码哈希、创建用户在 `backend/src/services/auth_service.py`
- [x] T027 [US1] 实现用户登录服务：密码验证、JWT 生成在 `backend/src/services/auth_service.py`
- [x] T028 [US1] 实现小说项目创建服务：项目初始化、角色创建、大纲生成触发在 `backend/src/services/novel_service.py`
- [x] T029 [US1] 实现规划 Agent：三层大纲生成（全书总纲→分卷大纲→逐章细纲）在 `backend/src/agents/planner.py`
- [x] T030 [US1] 实现大纲查询服务：获取项目详情含完整大纲和角色在 `backend/src/services/novel_service.py`
- [x] T031 [US1] 实现项目设定修改服务：更新世界观、文风、角色，触发大纲重新生成在 `backend/src/services/novel_service.py`

### 用户故事 1 的后端接口

- [x] T032 [P] [US1] 实现认证接口：POST /api/auth/register、POST /api/auth/login 在 `backend/src/api/auth.py`
- [x] T033 [P] [US1] 实现项目接口：POST /api/novel/create 在 `backend/src/api/novel.py`
- [x] T034 [US1] 实现项目接口：GET /api/novel/list、GET /api/novel/detail、PUT /api/novel/update 在 `backend/src/api/novel.py`

### 用户故事 1 的前端页面

- [x] T035 [P] [US1] 实现登录/注册页面在 `frontend/src/views/Login.vue`
- [x] T036 [P] [US1] 实现首页小说列表页面：卡片展示、新建入口、进度预览在 `frontend/src/views/Home.vue`
- [x] T037 [US1] 实现新建小说页面：题材、文风、世界观、人设、章节配置表单在 `frontend/src/views/CreateNovel.vue`
- [x] T038 [US1] 实现小说详情页面：大纲展示、角色列表、设定编辑在 `frontend/src/views/NovelDetail.vue`
- [x] T039 [P] [US1] 实现小说项目状态管理在 `frontend/src/stores/novel.ts`

**检查点**: 用户可以创建项目、查看大纲、编辑设定。MVP 可交付。

---

## 阶段 4: 用户故事 2 - 启动全自动创作（优先级：P1）

**目标**: 用户一键启动6Agent全自动创作流水线，实时查看进度

**独立测试**: 启动创作 → 系统自动完成至少1章（正文+摘要+审核+版权校验）

### 用户故事 2 的数据模型

- [x] T040 [P] [US2] 实现 Chapter 数据模型在 `backend/src/models/chapter.py`
- [x] T041 [P] [US2] 实现 AuditRecord 数据模型在 `backend/src/models/audit_record.py`
- [x] T042 [P] [US2] 实现 CopyrightReport 数据模型在 `backend/src/models/copyright_report.py`

### 用户故事 2 的智能体

- [x] T043 [US2] 实现调度 Agent：初始化状态、调度其他Agent、异常处理、重写防护在 `backend/src/agents/dispatcher.py`
- [x] T044 [US2] 实现写作 Agent：依据细纲+人设+摘要+FAISS回忆创作正文在 `backend/src/agents/writer.py`
- [x] T045 [US2] 实现摘要 Agent：生成单章摘要、更新全局滚动摘要、Embedding入库在 `backend/src/agents/summarizer.py`
- [x] T046 [US2] 实现剧情审核 Agent：大纲贴合度、人设一致性、文笔质量校验在 `backend/src/agents/auditor.py`
- [x] T047 [US2] 实现版权合规 Agent：FAISS向量查重、原创度打分、防洗稿检测在 `backend/src/agents/copyrighter.py`

### 用户故事 2 的后端服务

- [x] T048 [US2] 实现创作启动服务：状态校验、分布式锁获取、后台任务启动在 `backend/src/services/creation_service.py`
- [x] T049 [US2] 实现进度推送服务：SSE 流式响应、Redis 进度读取在 `backend/src/services/progress_service.py`
- [x] T050 [US2] 实现章节创建与状态流转服务：章节状态机管理在 `backend/src/services/chapter_service.py`

### 用户故事 2 的后端接口

- [x] T051 [P] [US2] 实现创作控制接口：POST /api/novel/start 在 `backend/src/api/creation.py`
- [x] T052 [P] [US2] 实现进度查询接口：GET /api/novel/progress (SSE) 在 `backend/src/api/creation.py`

### 用户故事 2 的前端页面

- [x] T053 [US2] 实现创作控制台页面：启停按钮、进度条、状态展示、实时日志在 `frontend/src/views/Console.vue`
- [x] T054 [P] [US2] 实现创作状态管理：进度订阅、SSE 连接在 `frontend/src/stores/creation.ts`

**检查点**: 用户可以启动创作，系统自动完成全流程，实时显示进度。

---

## 阶段 5: 用户故事 3 - 暂停与续写创作（优先级：P2）

**目标**: 用户可随时暂停创作，系统保存进度，之后可恢复

**独立测试**: 启动创作 → 暂停 → 确认进度保存 → 恢复 → 从断点继续

### 用户故事 3 的后端服务

- [x] T055 [US3] 实现创作暂停服务：停止当前任务、保存 State 快照到 Redis 在 `backend/src/services/creation_service.py`
- [x] T056 [US3] 实现断点续写服务：从 Redis 恢复 State、从断点继续创作在 `backend/src/services/creation_service.py`
- [x] T057 [US3] 实现异常恢复机制：服务启动时检查未完成项目、自动恢复进度在 `backend/src/core/recovery.py`

### 用户故事 3 的后端接口

- [x] T058 [P] [US3] 实现暂停接口：POST /api/novel/pause 在 `backend/src/api/creation.py`

### 用户故事 3 的前端页面

- [x] T059 [US3] 在创作控制台添加暂停/恢复按钮和状态切换逻辑在 `frontend/src/views/Console.vue`

**检查点**: 用户可暂停创作，服务重启后进度零丢失，可从断点恢复。

---

## 阶段 6: 用户故事 4 - 阅读与编辑章节（优先级：P2）

**目标**: 用户可浏览章节目录、阅读正文、查看审核报告、手动编辑

**独立测试**: 查看章节目录 → 点击章节 → 查看正文+摘要+审核报告 → 编辑并保存

### 用户故事 4 的数据模型

- [x] T060 [P] [US4] 实现 EditHistory 数据模型在 `backend/src/models/edit_history.py`

### 用户故事 4 的后端服务

- [x] T061 [US4] 实现章节目录查询服务：分页、状态筛选在 `backend/src/services/chapter_service.py`
- [x] T062 [US4] 实现章节详情查询服务：正文+摘要+审核记录+版权报告聚合在 `backend/src/services/chapter_service.py`
- [x] T063 [US4] 实现章节编辑服务：内容更新、字数统计、编辑历史记录在 `backend/src/services/chapter_service.py`

### 用户故事 4 的后端接口

- [x] T064 [P] [US4] 实现章节接口：GET /api/chapter/list 在 `backend/src/api/chapter.py`
- [x] T065 [P] [US4] 实现章节接口：GET /api/chapter/detail 在 `backend/src/api/chapter.py`
- [x] T066 [P] [US4] 实现章节接口：PUT /api/chapter/edit 在 `backend/src/api/chapter.py`
- [x] T067 [P] [US4] 实现版权报告接口：GET /api/novel/copyright/report 在 `backend/src/api/novel.py`
- [x] T068 [P] [US4] 实现语义召回接口：GET /api/novel/recall 在 `backend/src/api/novel.py`

### 用户故事 4 的前端页面

- [x] T069 [US4] 实现章节阅读编辑页面：目录树、正文预览、摘要、审核记录、版权报告、编辑器在 `frontend/src/views/ChapterView.vue`
- [x] T070 [P] [US4] 实现章节状态管理在 `frontend/src/stores/chapter.ts`

**检查点**: 用户可浏览所有章节，查看详细信息，手动编辑并保存。

---

## 阶段 7: 用户故事 5 - 导出全书（优先级：P3）

**目标**: 用户可将全书导出为 TXT 或 Markdown 格式

**独立测试**: 选择格式 → 导出 → 下载包含所有章节的完整文件

### 用户故事 5 的后端服务

- [x] T071 [US5] 实现全书导出服务：章节合并、格式化、文件生成在 `backend/src/services/export_service.py`

### 用户故事 5 的后端接口

- [x] T072 [P] [US5] 实现导出接口：GET /api/novel/export 在 `backend/src/api/export.py`

### 用户故事 5 的前端页面

- [x] T073 [US5] 实现导出与设置页面：格式选择、下载触发、全局人设查看在 `frontend/src/views/Export.vue`

**检查点**: 用户可导出完整小说文件。

---

## 阶段 8: 收尾与跨切面

**目的**: 影响多个用户故事的改进

- [x] T074 [P] 实现全局异常处理器：统一错误响应格式在 `backend/src/core/exceptions.py`
- [x] T075 [P] 实现请求参数校验：Pydantic 模型校验在 `backend/src/api/schemas/`
- [ ] T076 [P] 实现 LangSmith 追踪集成：Agent 执行链路追踪在 `backend/src/core/tracing.py`
- [ ] T077 [P] 添加后端单元测试：核心服务和工具函数在 `backend/tests/unit/`
- [ ] T078 [P] 添加前端单元测试：组件和 store 测试在 `frontend/tests/unit/`
- [ ] T079 运行 quickstart.md 验证流程：端到端冒烟测试

---

## 依赖与执行顺序

### 阶段依赖

- **阶段 1（初始化）**: 无依赖，立即开始
- **阶段 2（基础设施）**: 依赖阶段 1 完成，阻塞所有用户故事
- **阶段 3（US1 创建项目）**: 依赖阶段 2 完成
- **阶段 4（US2 自动创作）**: 依赖阶段 2 完成，US1 中的大纲数据
- **阶段 5（US3 暂停续写）**: 依赖阶段 4 完成
- **阶段 6（US4 阅读编辑）**: 依赖阶段 2 完成，可与 US2/US3 并行
- **阶段 7（US5 导出）**: 依赖阶段 2 完成，可与其他 US 并行
- **阶段 8（收尾）**: 依赖所有用户故事完成

### 用户故事依赖

- **US1（创建项目）**: 阶段 2 完成后可开始，无其他 US 依赖
- **US2（自动创作）**: 阶段 2 完成后可开始，需要 US1 的大纲数据作为输入
- **US3（暂停续写）**: 依赖 US2 的创作流程实现
- **US4（阅读编辑）**: 阶段 2 完成后可开始，可与 US2/US3 并行
- **US5（导出）**: 阶段 2 完成后可开始，可与其他 US 并行

### 并行机会

- 阶段 1 中 T003/T004/T005/T006/T007/T008 可并行
- 阶段 2 中 T010/T011/T012/T013/T014/T015 可并行
- US1 中 T022/T023/T024/T025 模型可并行，T032/T033/T035/T036/T039 可并行
- US2 中 T040/T041/T042 模型可并行，T051/T052/T054 可并行
- US4 和 US5 可与 US2/US3 并行开发

---

## 并行示例：用户故事 1

```bash
# 并行创建数据模型:
T022: "User 数据模型 backend/src/models/user.py"
T023: "NovelProject 数据模型 backend/src/models/novel_project.py"
T024: "Outline 数据模型 backend/src/models/outline.py"
T025: "Character 数据模型 backend/src/models/character.py"

# 并行创建接口和前端:
T032: "认证接口 backend/src/api/auth.py"
T033: "项目创建接口 backend/src/api/novel.py"
T035: "登录页面 frontend/src/views/Login.vue"
T036: "首页列表 frontend/src/views/Home.vue"
T039: "项目状态管理 frontend/src/stores/novel.ts"
```

---

## 实现策略

### MVP 优先（仅用户故事 1）

1. 完成阶段 1: 项目初始化
2. 完成阶段 2: 基础设施（关键阻塞）
3. 完成阶段 3: 用户故事 1
4. **停止并验证**: 独立测试用户故事 1
5. 可部署/演示

### 增量交付

1. 初始化 + 基础设施 → 基础就绪
2. 添加 US1 → 独立测试 → 部署（MVP！用户可创建项目和大纲）
3. 添加 US2 → 独立测试 → 部署（核心功能！全自动创作）
4. 添加 US3 → 独立测试 → 部署（暂停续写能力）
5. 添加 US4 → 独立测试 → 部署（阅读编辑能力）
6. 添加 US5 → 独立测试 → 部署（导出能力）
7. 阶段 8 收尾 → 质量加固

---

## 备注

- [P] 任务 = 不同文件，无依赖
- [Story] 标签将任务映射到具体用户故事
- 每个用户故事应可独立完成和测试
- 每个任务完成后提交一次
- 任何检查点都可停下来独立验证该故事
