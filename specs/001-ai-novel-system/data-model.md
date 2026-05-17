# 数据模型：AI长篇小说自动生成系统

**日期**: 2026-05-10
**功能**: 001-ai-novel-system

## 实体关系概览

```text
User (1) ──── (N) NovelProject
NovelProject (1) ──── (1) Outline
NovelProject (1) ──── (N) Chapter
NovelProject (1) ──── (N) Character
Chapter (1) ──── (N) AuditRecord
Chapter (1) ──── (1) CopyrightReport
Chapter (1) ──── (N) EditHistory
```

## 实体定义

### User（用户）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| username | String | 是 | 用户名，唯一索引 |
| password_hash | String | 是 | bcrypt 哈希后的密码 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### NovelProject（小说项目）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| user_id | ObjectId | 是 | 所属用户，外键 |
| title | String | 是 | 小说标题 |
| genre | String | 是 | 题材（玄幻、都市、科幻等） |
| style | String | 是 | 文风（热血、轻松、严肃等） |
| world_setting | String | 是 | 世界观设定 |
| chapter_count | Int | 是 | 计划章节数（50-500） |
| words_per_chapter | Int | 是 | 每章目标字数（2000-5000） |
| status | Enum | 是 | 项目状态：draft/writing/paused/completed |
| current_volume | Int | 否 | 当前创作卷号 |
| current_chapter | Int | 否 | 当前创作章号 |
| rewrite_count | Int | 否 | 当前章节重写次数（0-3） |
| copyright_threshold | Float | 否 | 版权相似度阈值，默认0.2 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

**状态流转**: draft → writing ↔ paused → completed

### Outline（大纲体系）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| project_id | ObjectId | 是 | 所属项目，外键 |
| full_outline | String | 是 | 全书总纲 |
| volume_outlines | Array | 是 | 分卷大纲列表 |
| volume_outlines[].volume_number | Int | 是 | 卷号 |
| volume_outlines[].volume_title | String | 是 | 卷标题 |
| volume_outlines[].content | String | 是 | 分卷大纲内容 |
| chapter_outlines | Array | 是 | 逐章细纲列表 |
| chapter_outlines[].chapter_number | Int | 是 | 章号 |
| chapter_outlines[].title | String | 是 | 章标题 |
| chapter_outlines[].content | String | 是 | 章节细纲内容 |
| version | Int | 是 | 大纲版本号（每次重新生成+1） |
| created_at | DateTime | 是 | 创建时间 |

### Character（角色）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| project_id | ObjectId | 是 | 所属项目，外键 |
| name | String | 是 | 角色名 |
| role_type | Enum | 是 | 角色类型：protagonist/antagonist/supporting |
| personality | String | 是 | 性格特征 |
| background | String | 是 | 身世背景 |
| relationships | Array | 否 | 与其他角色的关系 |
| relationships[].character_name | String | 是 | 关联角色名 |
| relationships[].relation | String | 是 | 关系描述 |
| status_history | Array | 否 | 状态变更历史 |
| status_history[].chapter_number | Int | 是 | 变更章节 |
| status_history[].status | String | 是 | 变更后的状态描述 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

### Chapter（章节）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| project_id | ObjectId | 是 | 所属项目，外键 |
| volume_number | Int | 是 | 所属卷号 |
| chapter_number | Int | 是 | 章号，项目内唯一 |
| title | String | 是 | 章标题 |
| outline | String | 是 | 章节细纲 |
| content | String | 否 | 正文内容 |
| summary | String | 否 | 章节摘要 |
| word_count | Int | 否 | 正文字数 |
| status | Enum | 是 | 章节状态 |
| rewrite_count | Int | 是 | 重写次数，默认0 |
| created_at | DateTime | 是 | 创建时间 |
| updated_at | DateTime | 是 | 更新时间 |

**状态流转**: pending → writing → pending_audit → auditing → pending_copyright → copyright_checking → completed / rewriting / manual_review

### AuditRecord（审核记录）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| chapter_id | ObjectId | 是 | 所属章节，外键 |
| project_id | ObjectId | 是 | 所属项目，外键 |
| audit_type | Enum | 是 | 审核类型：plot_audit / copyright_audit |
| result | Enum | 是 | 审核结果：pass / fail |
| score | Float | 否 | 评分（0-100） |
| opinion | String | 是 | 审核意见/修改建议 |
| details | Dict | 否 | 详细审核数据 |
| created_at | DateTime | 是 | 创建时间 |

### CopyrightReport（版权报告）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| chapter_id | ObjectId | 是 | 所属章节，外键 |
| project_id | ObjectId | 是 | 所属项目，外键 |
| originality_score | Float | 是 | 原创度分数（0-100） |
| max_similarity | Float | 是 | 最高相似度（0-1） |
| similar_entries | Array | 否 | 相似条目列表 |
| similar_entries[].source | String | 是 | 来源标识 |
| similar_entries[].similarity | Float | 是 | 相似度 |
| similar_entries[].excerpt | String | 是 | 相似片段摘要 |
| passed | Boolean | 是 | 是否通过 |
| created_at | DateTime | 是 | 创建时间 |

### EditHistory（编辑历史）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| _id | ObjectId | 是 | 主键 |
| chapter_id | ObjectId | 是 | 所属章节，外键 |
| user_id | ObjectId | 是 | 编辑用户，外键 |
| content_before | String | 是 | 编辑前内容（或差异标记） |
| content_after | String | 是 | 编辑后内容 |
| created_at | DateTime | 是 | 编辑时间 |

## FAISS 向量库结构

### 私有记忆向量库（每本小说独立）

- **索引文件**: `faiss_indexes/{project_id}/memory.index`
- **映射文件**: `faiss_indexes/{project_id}/mapping.json`
- **存储内容**: 章节摘要、关键事件、人物状态、伏笔的 Embedding 向量
- **用途**: 写作前语义检索前文，解决长篇失忆问题

### 公共版权比对向量库（全局共享）

- **索引文件**: `faiss_indexes/copyright/copyright.index`
- **映射文件**: `faiss_indexes/copyright/mapping.json`
- **存储内容**: 公开网文经典桥段、通用套路、热门设定的 Embedding 向量
- **用途**: 每章创作后自动查重，计算原创度分数

## Redis 缓存结构

| Key 模式 | 类型 | 说明 | TTL |
|----------|------|------|-----|
| `novel:{project_id}:state` | String | LangGraph 全局 State JSON | 无（持久化） |
| `novel:{project_id}:progress` | Hash | 当前创作进度 | 无 |
| `novel:{project_id}:lock` | String | 项目分布式锁 | 30s（自动释放） |
| `novel:{project_id}:summary` | String | 全局滚动摘要（最近5章） | 无 |
| `novel:{project_id}:config` | Hash | 版权阈值等配置缓存 | 无 |
| `user:{user_id}:token` | String | JWT 刷新令牌 | 7d |
