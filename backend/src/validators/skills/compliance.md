---
name: compliance
description: 内容合规检查 — 扫描违规内容（血腥暴力、色情擦边、政治敏感）
version: 1.0.0
tags: [validation, quality-gate, hybrid]
check_method: hybrid
failure: block
priority: 5
---

# 内容合规检查

## 程序化检查（关键词扫描）

### 1. 高危关键词扫描
- 方法：正则匹配预定义敏感词库
- 类别：色情、暴力、政治敏感、违法犯罪
- 阈值：命中任一高危词 → fail

### 2. 情色擦边检测
- 方法：统计身体部位词 + 动作词的共现密度
- 阈值：每 500 字内出现 ≥5 个敏感组合 → 触发 LLM 复核

### 3. 暴力描写密度检测
- 方法：统计血腥/暴力相关词汇密度
- 阈值：每 500 字内出现 ≥8 个暴力词汇 → 触发 LLM 复核

## LLM 辅助检查（上下文判断）

仅当程序化检查触发阈值时启用。关键词命中可能是正常情节需要，需要 LLM 判断上下文。

### LLM 输出格式要求

```json
{
  "triggered_keywords": ["命中的敏感词列表"],
  "context_analysis": [
    {
      "keyword": "敏感词",
      "sentence_context": "包含该词的完整句子",
      "is_violation": false,
      "reason": "判断理由"
    }
  ],
  "overall_pass": true,
  "violation_details": []
}
```
