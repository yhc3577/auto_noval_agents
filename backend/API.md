# AI 长篇小说自动生成系统 — 后端 API 文档

**Base URL**: `http://localhost:8080`  
**认证方式**: JWT Bearer Token（`Authorization: Bearer <token>`）  
**API 文档**: http://localhost:8080/docs （Swagger UI 交互式文档）

---

## 目录

1. [认证接口](#1-认证接口)
2. [小说项目接口](#2-小说项目接口)
3. [创作控制接口](#3-创作控制接口)
4. [章节管理接口](#4-章节管理接口)
5. [导出接口](#5-导出接口)
6. [数据模型](#6-数据模型)
7. [状态机](#7-状态机)
8. [错误码](#8-错误码)

---

## 1. 认证接口

### 1.1 用户注册

```
POST /api/auth/register
```

**请求体**:
```json
{
  "username": "testuser",    // 3-20 字符
  "password": "password123"  // 6-50 字符
}
```

**响应** `201 Created`:
```json
{
  "id": "6641a2b3c4d5e6f7a8b9c0d1",
  "username": "testuser",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**错误**:
- `409` 用户名已存在

**curl 示例**:
```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

---

### 1.2 用户登录

```
POST /api/auth/login
```

**请求体**:
```json
{
  "username": "testuser",
  "password": "password123"
}
```

**响应** `200 OK`: 同注册响应格式

**错误**:
- `401` 用户名或密码错误

**curl 示例**:
```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

---

## 2. 小说项目接口

> 以下接口均需认证：`Authorization: Bearer <token>`

### 2.1 创建小说项目

```
POST /api/novel/create
```

**请求体**:
```json
{
  "title": "我的修仙小说",           // 1-50 字符
  "genre": "玄幻",                  // 类型
  "style": "热血",                  // 文风
  "world_setting": "修仙世界...",    // 世界观设定
  "chapter_count": 50,              // 章节数 50-500
  "words_per_chapter": 3000,        // 每章字数 2000-5000
  "characters": [
    {
      "name": "李天",
      "role_type": "protagonist",   // protagonist | antagonist | supporting
      "personality": "坚韧不拔",
      "background": "出身贫寒的少年",
      "relationships": []
    }
  ]
}
```

**响应** `201 Created`:
```json
{
  "project_id": "6641a2b3c4d5e6f7a8b9c0d1",
  "title": "我的修仙小说",
  "status": "created",
  "message": "项目创建成功，大纲生成中..."
}
```

**功能说明**: 创建项目后自动触发 3 层大纲生成（全书大纲 → 卷大纲 → 章节细纲），通过 LangGraph Planner Agent 异步完成。

**curl 示例**:
```bash
curl -X POST http://localhost:8080/api/novel/create \
  -H "Authorization: Bearer $TOKEN" \
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

---

### 2.2 获取项目列表

```
GET /api/novel/list?page=1&page_size=20
```

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码 (≥1) |
| page_size | int | 20 | 每页条数 (1-100) |

**响应** `200 OK`:
```json
{
  "total": 3,
  "items": [
    {
      "project_id": "6641a2b3...",
      "title": "测试小说",
      "genre": "玄幻",
      "status": "writing",
      "current_chapter": 12,
      "chapter_count": 50,
      "created_at": "2026-05-10T12:00:00+00:00"
    }
  ]
}
```

**curl 示例**:
```bash
curl http://localhost:8080/api/novel/list \
  -H "Authorization: Bearer $TOKEN"
```

---

### 2.3 查看项目详情

```
GET /api/novel/detail?project_id=<id>
```

**响应**: 项目设定、完整大纲、角色信息等

**curl 示例**:
```bash
curl "http://localhost:8080/api/novel/detail?project_id=$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 2.4 修改项目设定

```
PUT /api/novel/update
```

**请求体**:
```json
{
  "project_id": "6641a2b3...",
  "world_setting": "更新后的世界观",
  "style": "沉稳",
  "copyright_threshold": 0.15
}
```

所有字段（除 `project_id`）均为可选，只传需要修改的字段。

---

### 2.5 版权查重报告

```
GET /api/novel/copyright/report?chapter_id=<id>
```

**响应**:
```json
{
  "chapter_id": "...",
  "originality_score": 85,
  "max_similarity": 0.15,
  "passed": true,
  "similar_entries": []
}
```

---

### 2.6 语义召回（FAISS）

```
GET /api/novel/recall?project_id=<id>&query=主角在第三章做了什么&top_k=5
```

**响应**: 基于向量检索的前文相关片段

---

## 3. 创作控制接口

> 以下接口均需认证

### 3.1 启动创作

```
POST /api/novel/start
```

**请求体**:
```json
{
  "project_id": "6641a2b3..."
}
```

**响应**:
```json
{
  "status": "started",
  "message": "6Agent 创作流水线已启动"
}
```

**功能说明**: 启动 LangGraph 6Agent 流水线，后台异步执行：
```
调度 → 写作 → 摘要 → 剧情审核 → 版权校验 → [通过/重写/人工介入]
```

创作过程中可通过 SSE 进度接口实时监控。支持断点续跑（从上次暂停的章节继续）。

**curl 示例**:
```bash
curl -X POST http://localhost:8080/api/novel/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"project_id\": \"$PROJECT_ID\"}"
```

---

### 3.2 暂停创作

```
POST /api/novel/pause
```

**请求体**:
```json
{
  "project_id": "6641a2b3..."
}
```

**响应**:
```json
{
  "status": "paused",
  "message": "创作已暂停，当前章节完成后停止"
}
```

**功能说明**: 当前章节完成后暂停，已写内容不丢失。再次调用 `/start` 可从断点继续。

---

### 3.3 实时进度查询（SSE）

```
GET /api/novel/progress?project_id=<id>
```

**响应**: Server-Sent Events 流，每 2 秒推送一次：

```
data: {"project_id":"...","current_chapter":12,"total_chapters":50,"progress":24.0,"status":"writing","chapter_status":"auditing","log":"第12章剧情审核中..."}

data: {"project_id":"...","current_chapter":12,"total_chapters":50,"progress":24.0,"status":"writing","chapter_status":"completed","log":"第12章创作完成"}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|------|------|------|
| current_chapter | int | 当前章节号 |
| total_chapters | int | 总章节数 |
| progress | float | 进度百分比 0-100 |
| status | string | 项目状态：writing / paused / completed |
| chapter_status | string | 章节状态：writing / summarizing / auditing / copyright_checking / completed |
| log | string | 当前操作描述 |

**前端使用示例**:
```javascript
const es = new EventSource('/api/novel/progress?project_id=xxx', {
  headers: { 'Authorization': 'Bearer ' + token }
})
es.onmessage = (e) => {
  const data = JSON.parse(e.data)
  console.log(`进度: ${data.progress}% - ${data.log}`)
  if (data.status === 'completed') es.close()
}
```

---

## 4. 章节管理接口

> 以下接口均需认证

### 4.1 章节目录

```
GET /api/chapter/list?project_id=<id>&page=1&page_size=50
```

**响应**:
```json
{
  "total": 50,
  "items": [
    {
      "chapter_id": "...",
      "chapter_number": 1,
      "volume_number": 1,
      "title": "第1章",
      "status": "completed",
      "word_count": 3120,
      "updated_at": "2026-05-10T12:30:00+00:00"
    }
  ]
}
```

---

### 4.2 章节详情

```
GET /api/chapter/detail?chapter_id=<id>
```

**响应**:
```json
{
  "chapter_id": "...",
  "chapter_number": 1,
  "title": "第1章",
  "outline": "本章细纲内容...",
  "content": "章节正文...",
  "summary": "章节摘要...",
  "word_count": 3120,
  "status": "completed",
  "audit_records": [
    {
      "audit_type": "plot_audit",
      "result": "pass",
      "score": 85,
      "opinion": "剧情贴合大纲，人物行为符合设定...",
      "created_at": "..."
    }
  ],
  "copyright_report": {
    "originality_score": 85,
    "max_similarity": 0.15,
    "passed": true,
    "similar_entries": []
  },
  "edit_history": [
    {
      "edited_at": "...",
      "summary": "字数变化: +120"
    }
  ]
}
```

---

### 4.3 编辑章节

```
PUT /api/chapter/edit
```

**请求体**:
```json
{
  "chapter_id": "...",
  "content": "修改后的章节内容..."
}
```

**响应**:
```json
{
  "chapter_id": "...",
  "word_count": 3240,
  "message": "章节内容已更新"
}
```

**限制**: 状态为 `writing` / `auditing` / `copyright_checking` 的章节不允许编辑。

---

## 5. 导出接口

### 5.1 全书导出

```
GET /api/novel/export?project_id=<id>&format=txt
```

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| project_id | string | 必填 | 项目 ID |
| format | string | txt | 导出格式：`txt` 或 `markdown` |

**响应**: 文件下载（`Content-Disposition: attachment`）

- `format=txt`: 纯文本格式，章节间用分隔线隔开
- `format=markdown`: Markdown 格式，章节标题用 `##` 标记

**curl 示例**:
```bash
# 导出 TXT
curl "http://localhost:8080/api/novel/export?project_id=$PROJECT_ID&format=txt" \
  -H "Authorization: Bearer $TOKEN" \
  -o 小说.txt

# 导出 Markdown
curl "http://localhost:8080/api/novel/export?project_id=$PROJECT_ID&format=markdown" \
  -H "Authorization: Bearer $TOKEN" \
  -o 小说.md
```

---

## 6. 数据模型

### 6.1 小说项目 (novel_projects)

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | ObjectId | 项目 ID |
| user_id | string | 所属用户 ID |
| title | string | 小说标题 |
| genre | string | 类型（玄幻/科幻/都市等） |
| style | string | 文风（热血/沉稳/幽默等） |
| world_setting | string | 世界观设定 |
| chapter_count | int | 计划章节数 |
| words_per_chapter | int | 每章目标字数 |
| copyright_threshold | float | 版权查重阈值（默认 0.2） |
| status | string | 项目状态 |
| current_chapter | int | 当前创作到第几章 |
| rewrite_count | int | 当前章重写次数 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 6.2 章节 (chapters)

| 字段 | 类型 | 说明 |
|------|------|------|
| _id | ObjectId | 章节 ID |
| project_id | string | 所属项目 ID |
| volume_number | int | 卷号 |
| chapter_number | int | 章节号 |
| title | string | 章节标题 |
| outline | string | 章节细纲 |
| content | string | 正文内容 |
| summary | string | 章节摘要 |
| word_count | int | 字数 |
| status | string | 章节状态 |
| rewrite_count | int | 重写次数 |

### 6.3 审核记录 (audit_records)

| 字段 | 类型 | 说明 |
|------|------|------|
| chapter_id | string | 关联章节 ID |
| project_id | string | 关联项目 ID |
| audit_type | string | 审核类型（plot_audit） |
| result | string | pass / fail |
| score | int | 评分 0-100 |
| opinion | string | 审核意见 |

### 6.4 版权记录 (copyright_records)

| 字段 | 类型 | 说明 |
|------|------|------|
| chapter_id | string | 关联章节 ID |
| project_id | string | 关联项目 ID |
| originality_score | int | 原创度分数 0-100 |
| max_similarity | float | 最高相似度 0-1 |
| passed | bool | 是否通过 |
| similar_entries | list | 相似条目列表 |

---

## 7. 状态机

### 7.1 项目状态

```
created → outline_generating → ready → writing → paused → completed
```

| 状态 | 说明 |
|------|------|
| created | 已创建，等待大纲生成 |
| outline_generating | 大纲生成中 |
| ready | 大纲就绪，可启动创作 |
| writing | 创作进行中 |
| paused | 已暂停 |
| completed | 全书创作完成 |

### 7.2 章节状态

```
pending → writing → summarizing → auditing → copyright_checking → completed
                                                               ↘ rewriting → writing (循环，最多3次)
                                                               ↘ manual_review
```

| 状态 | 说明 |
|------|------|
| pending | 等待创作 |
| writing | 写作中 |
| summarizing | 摘要生成中 |
| auditing | 剧情审核中 |
| copyright_checking | 版权校验中 |
| completed | 完成 |
| rewriting | 重写中 |
| manual_review | 重写超限，需人工介入 |
| failed | 失败 |

### 7.3 LangGraph 流水线节点

```
dispatch → writer → summarizer → auditor → copyrighter
                                              ↓
                                    ┌─── pass ──→ advance_chapter → END
                                    ├─── fail + rewrite < 3 ──→ rewrite → writer (循环)
                                    └─── fail + rewrite ≥ 3 ──→ manual_review → END
```

---

## 8. 错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 / 业务限制 |
| 401 | 未认证 / Token 无效或过期 |
| 404 | 资源不存在 |
| 409 | 冲突（如用户名已存在） |
| 500 | 服务器内部错误 |

**错误响应格式**:
```json
{
  "detail": "错误描述信息"
}
```

---

## 快速测试流程

```bash
# 1. 注册
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 2. 创建小说
PROJECT_ID=$(curl -s -X POST http://localhost:8080/api/novel/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试","genre":"玄幻","style":"热血","world_setting":"修仙世界","chapter_count":50,"words_per_chapter":3000,"characters":[{"name":"李天","role_type":"protagonist","personality":"坚韧","background":"少年"}]}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['project_id'])")

# 3. 启动创作
curl -X POST http://localhost:8080/api/novel/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"project_id\":\"$PROJECT_ID\"}"

# 4. 查看进度（SSE）
curl -N "http://localhost:8080/api/novel/progress?project_id=$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN"

# 5. 查看章节
curl "http://localhost:8080/api/chapter/list?project_id=$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN"

# 6. 导出
curl "http://localhost:8080/api/novel/export?project_id=$PROJECT_ID&format=txt" \
  -H "Authorization: Bearer $TOKEN" -o novel.txt
```
