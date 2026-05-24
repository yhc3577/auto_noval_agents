---
name: quality-baseline
description: 基础文笔质量检查 — 结构完整性、句式多样性、可读性
version: 1.0.0
tags: [validation, quality-gate, hybrid]
check_method: hybrid
failure: warn
priority: 6
---

# 基础文笔质量检查

## 程序化检查

### 1. 段落结构完整性
- 方法：检查开头/中间/结尾段落长度分布
- 阈值：
  - 单段最长不超过 800 字（段落过长影响可读性）
  - 段落数 ≥ 5（至少 5 个自然段）
  - 结尾段必须 > 0 字（不能截断）

### 2. 句式多样性
- 方法：统计句子长度分布
- 阈值：
  - 短句（≤20 字）占比 ≥ 15%（避免全是长句）
  - 长句（≥80 字）占比 ≤ 30%（避免句式冗长）

### 3. 标点使用检查
- 方法：统计引号配对、省略号使用
- 阈值：
  - 中文引号「」必须成对出现
  - 省略号连续不超过 6 个点

## LLM 辅助检查

### LLM 输出格式要求

```json
{
  "structure": {
    "has_clear_opening": true,
    "has_clear_development": true,
    "has_clear_ending": true,
    "paragraph_issues": []
  },
  "sentence_variety": {
    "short_sentence_ratio": 0.22,
    "long_sentence_ratio": 0.15,
    "monotony_issues": []
  },
  "readability": {
    "score": 75,
    "issues": []
  },
  "overall_pass": true
}
```
