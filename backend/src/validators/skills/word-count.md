---
name: word-count
description: 字数达标检查 — 验证章节正文字数是否在目标范围内
version: 1.0.0
tags: [validation, quality-gate, programmatic]
check_method: programmatic
failure: block
priority: 1
---

# 字数达标检查

## 检查项

### 1. 字数下限
- 方法：`len(chapter_content)` 
- 阈值：≥ `target_words`
- 失败动作：block（触发重写，要求扩充）

### 2. 字数上限
- 方法：`len(chapter_content)`
- 阈值：≤ `target_words * 1.3`
- 失败动作：block（触发重写，要求精简）

## 输出格式

```json
{
  "check": "word-count",
  "passed": true,
  "word_count": 3200,
  "target": 3000,
  "max_allowed": 3900,
  "details": "字数 3200 在目标范围 [3000, 3900] 内"
}
```
sk-d2daebfd3be246a7951012b405ec8111

sk-cp-_K-YtGKqQE4B7gtnhfUqqF1fKahjHPqoc3hwrdlZENZmTtK-M7ZVGN1QJdqm_c8nIqReLII4hIvASK7SwwgKx6YSzGTgFrWwmnqsPi7joS5C1tqNvYT419c