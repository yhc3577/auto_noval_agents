# 实现计划：AI长篇小说自动生成系统

**分支**: `001-ai-novel-system` | **日期**: 2026-05-10 | **规格**: [spec.md](spec.md)
**输入**: 功能规格文档 `specs/001-ai-novel-system/spec.md`

## 概述

构建一套支持10万+字长篇小说全自动创作的AI系统。基于LangGraph 6大智能体闭环协作，实现从创建项目、生成大纲、自动写章、质检审核、版权校验到全书导出的全流程无人值守自动化创作。核心解决传统AI写作的失忆、人设OOC、剧情断层、逻辑冲突、仿写洗稿等痛点。

## 技术上下文

**语言/版本**: Python 3.11+（后端） / Vue 3 + TypeScript（前端）
**主要依赖**: FastAPI、LangGraph、LangChain、LangChain-OpenAI、Element Plus、Pinia、Axios
**存储**: MongoDB（结构化数据持久化）、Redis（缓存/状态/锁）、FAISS（本地向量记忆/查重）
**测试**: pytest（后端）、Vitest（前端）
**目标平台**: Linux 服务器 + 现代浏览器
**项目类型**: Web应用（前后端分离）
**性能目标**: 单章创作（含审核校验）平均耗时不超过3分钟；大纲生成不超过5分钟
**约束**: 每次状态变更立即持久化，异常恢复后零丢失；单章最多重写3次防死循环
**规模**: 单本小说50-500章，每章2000-5000字；单用户项目数量无上限

## 章程检查

*关卡：Phase 0 研究前必须通过。Phase 1 设计后重新检查。*

| 原则 | 检查项 | 状态 |
|------|--------|------|
| I. 技术栈规范 | 后端Python、前端Vue+TS、中文交互 | ✅ 通过 |
| II. 全异步后端 | FastAPI异步框架、Motor异步MongoDB驱动、aioredis异步Redis、aiofiles异步文件操作 | ✅ 通过 |
| III. 代码注释规范 | 公共API文档字符串、复杂逻辑中文注释 | ✅ 通过 |

## 项目结构

### 文档（本功能）

```text
specs/001-ai-novel-system/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
└── tasks.md             # Phase 2 输出（由 /speckit.tasks 生成）
```

### 源代码（仓库根目录）

```text
backend/
├── src/
│   ├── api/             # FastAPI 路由和接口
│   │   ├── novel.py     # 小说项目接口
│   │   ├── chapter.py   # 章节管理接口
│   │   ├── creation.py  # 创作控制接口
│   │   └── export.py    # 导出接口
│   ├── agents/          # LangGraph 6个智能体
│   │   ├── dispatcher.py    # 调度Agent
│   │   ├── planner.py       # 规划Agent
│   │   ├── writer.py        # 写作Agent
│   │   ├── summarizer.py    # 摘要Agent
│   │   ├── auditor.py       # 剧情审核Agent
│   │   └── copyrighter.py   # 版权合规Agent
│   ├── models/          # 数据模型
│   ├── services/        # 业务服务层
│   ├── core/            # 核心配置、状态机、存储
│   └── utils/           # 工具函数
└── tests/
    ├── unit/
    ├── integration/
    └── contract/

frontend/
├── src/
│   ├── views/           # 页面组件
│   │   ├── Home.vue         # 首页-小说列表
│   │   ├── CreateNovel.vue  # 新建小说
│   │   ├── Console.vue      # 创作控制台
│   │   ├── ChapterView.vue  # 章节阅读编辑
│   │   └── Export.vue       # 导出与设置
│   ├── components/      # 通用组件
│   ├── stores/          # Pinia 状态管理
│   ├── services/        # API 调用封装
│   └── router/          # Vue Router 配置
└── tests/
```

**结构决策**: 采用 Web 应用结构（Option 2），前后端完全分离。后端基于 FastAPI + LangGraph 实现6智能体协作，前端使用 Vue 3 + TypeScript + Element Plus。

## 复杂度追踪

> 无章程违规，无需记录。
