# API 契约：AI长篇小说自动生成系统

**日期**: 2026-05-10
**基础路径**: `/api`

所有接口（除认证接口外）需要在请求头中携带 `Authorization: Bearer <token>`。

## 认证接口

### POST /api/auth/register

注册新用户。

**请求体**:
```json
{
  "username": "string (3-20字符)",
  "password": "string (6-50字符)"
}
```

**响应 201**:
```json
{
  "id": "string",
  "username": "string",
  "token": "string (JWT)"
}
```

**错误响应**:
- 400: 参数校验失败
- 409: 用户名已存在

---

### POST /api/auth/login

用户登录。

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应 200**:
```json
{
  "id": "string",
  "username": "string",
  "token": "string (JWT)"
}
```

**错误响应**:
- 401: 用户名或密码错误

---

## 小说项目接口

### POST /api/novel/create

新建小说项目，初始化大纲和向量索引。

**请求体**:
```json
{
  "title": "string (1-50字符)",
  "genre": "string (题材)",
  "style": "string (文风)",
  "world_setting": "string (世界观设定)",
  "chapter_count": "integer (50-500)",
  "words_per_chapter": "integer (2000-5000, 默认3000)",
  "characters": [
    {
      "name": "string",
      "role_type": "protagonist|antagonist|supporting",
      "personality": "string",
      "background": "string",
      "relationships": [
        {
          "character_name": "string",
          "relation": "string"
        }
      ]
    }
  ]
}
```

**响应 201**:
```json
{
  "project_id": "string",
  "title": "string",
  "status": "draft",
  "message": "项目创建成功，大纲生成中"
}
```

**错误响应**:
- 400: 参数校验失败
- 401: 未认证

---

### GET /api/novel/list

获取当前用户的小说项目列表。

**查询参数**:
- `page`: 页码，默认1
- `page_size`: 每页数量，默认20

**响应 200**:
```json
{
  "total": "integer",
  "items": [
    {
      "project_id": "string",
      "title": "string",
      "genre": "string",
      "status": "draft|writing|paused|completed",
      "current_chapter": "integer",
      "chapter_count": "integer",
      "created_at": "datetime"
    }
  ]
}
```

---

### GET /api/novel/detail

查看项目设定和完整大纲。

**查询参数**:
- `project_id`: 项目ID（必填）

**响应 200**:
```json
{
  "project_id": "string",
  "title": "string",
  "genre": "string",
  "style": "string",
  "world_setting": "string",
  "chapter_count": "integer",
  "words_per_chapter": "integer",
  "status": "string",
  "current_chapter": "integer",
  "outline": {
    "full_outline": "string",
    "volume_outlines": [
      {
        "volume_number": "integer",
        "volume_title": "string",
        "content": "string"
      }
    ],
    "chapter_outlines": [
      {
        "chapter_number": "integer",
        "title": "string",
        "content": "string"
      }
    ]
  },
  "characters": [
    {
      "name": "string",
      "role_type": "string",
      "personality": "string",
      "background": "string"
    }
  ],
  "created_at": "datetime"
}
```

**错误响应**:
- 404: 项目不存在

---

### PUT /api/novel/update

修改项目设定（人设、世界观、文风等）。

**请求体**:
```json
{
  "project_id": "string",
  "world_setting": "string (可选)",
  "style": "string (可选)",
  "characters": "array (可选)",
  "copyright_threshold": "float (可选, 0-1)"
}
```

**响应 200**:
```json
{
  "project_id": "string",
  "message": "项目设定已更新"
}
```

**错误响应**:
- 400: 项目状态不允许修改（创作中）
- 404: 项目不存在

---

## 创作控制接口

### POST /api/novel/start

启动或恢复6Agent全自动创作。

**请求体**:
```json
{
  "project_id": "string"
}
```

**响应 200**:
```json
{
  "project_id": "string",
  "status": "writing",
  "message": "创作已启动"
}
```

**错误响应**:
- 400: 项目状态不允许（已完成/已在创作中）
- 404: 项目不存在

---

### POST /api/novel/pause

暂停创作，保存断点状态。

**请求体**:
```json
{
  "project_id": "string"
}
```

**响应 200**:
```json
{
  "project_id": "string",
  "status": "paused",
  "current_chapter": "integer",
  "message": "创作已暂停，进度已保存"
}
```

**错误响应**:
- 400: 项目当前不在创作状态
- 404: 项目不存在

---

### GET /api/novel/progress

实时查询创作进度（SSE流式响应）。

**查询参数**:
- `project_id`: 项目ID（必填）

**响应**: `Content-Type: text/event-stream`

```
data: {"project_id":"xxx","current_chapter":5,"total_chapters":50,"progress":10.0,"status":"writing","chapter_status":"writing","log":"正在创作第5章..."}

data: {"project_id":"xxx","current_chapter":5,"total_chapters":50,"progress":10.0,"status":"writing","chapter_status":"auditing","log":"第5章剧情审核中..."}
```

**错误响应**:
- 404: 项目不存在

---

## 章节管理接口

### GET /api/chapter/list

获取章节目录。

**查询参数**:
- `project_id`: 项目ID（必填）
- `page`: 页码，默认1
- `page_size`: 每页数量，默认50

**响应 200**:
```json
{
  "total": "integer",
  "items": [
    {
      "chapter_id": "string",
      "chapter_number": "integer",
      "volume_number": "integer",
      "title": "string",
      "status": "pending|writing|pending_audit|auditing|pending_copyright|copyright_checking|completed|rewriting|manual_review",
      "word_count": "integer",
      "updated_at": "datetime"
    }
  ]
}
```

---

### GET /api/chapter/detail

查看章节正文、摘要、审核意见、版权报告。

**查询参数**:
- `chapter_id`: 章节ID（必填）

**响应 200**:
```json
{
  "chapter_id": "string",
  "chapter_number": "integer",
  "title": "string",
  "outline": "string",
  "content": "string",
  "summary": "string",
  "word_count": "integer",
  "status": "string",
  "audit_records": [
    {
      "audit_type": "plot_audit|copyright_audit",
      "result": "pass|fail",
      "score": "float",
      "opinion": "string",
      "created_at": "datetime"
    }
  ],
  "copyright_report": {
    "originality_score": "float",
    "max_similarity": "float",
    "passed": "boolean",
    "similar_entries": [
      {
        "source": "string",
        "similarity": "float",
        "excerpt": "string"
      }
    ]
  },
  "edit_history": [
    {
      "edited_at": "datetime",
      "summary": "string"
    }
  ]
}
```

**错误响应**:
- 404: 章节不存在

---

### PUT /api/chapter/edit

人工编辑章节内容。

**请求体**:
```json
{
  "chapter_id": "string",
  "content": "string"
}
```

**响应 200**:
```json
{
  "chapter_id": "string",
  "word_count": "integer",
  "message": "章节内容已更新"
}
```

**错误响应**:
- 400: 章节状态不允许编辑（创作中/审核中）
- 404: 章节不存在

---

## 版权与记忆接口

### GET /api/novel/copyright/report

获取单章版权查重报告。

**查询参数**:
- `chapter_id`: 章节ID（必填）

**响应 200**:
```json
{
  "chapter_id": "string",
  "originality_score": "float",
  "max_similarity": "float",
  "passed": "boolean",
  "similar_entries": [
    {
      "source": "string",
      "similarity": "float",
      "excerpt": "string"
    }
  ],
  "created_at": "datetime"
}
```

---

### GET /api/novel/recall

手动FAISS语义召回前文剧情。

**查询参数**:
- `project_id`: 项目ID（必填）
- `query`: 检索文本（必填）
- `top_k`: 返回数量，默认5

**响应 200**:
```json
{
  "results": [
    {
      "chapter_number": "integer",
      "content_snippet": "string",
      "relevance_score": "float"
    }
  ]
}
```

---

## 导出接口

### GET /api/novel/export

全书导出。

**查询参数**:
- `project_id`: 项目ID（必填）
- `format`: 导出格式，`txt` 或 `markdown`，默认 `txt`

**响应 200**:
- `Content-Type`: `text/plain` 或 `text/markdown`
- `Content-Disposition`: `attachment; filename="{title}.{ext}"`
- 响应体为合并后的全书内容
