---
name: outline-adherence
description: 大纲贴合度校验 — 逐项核对细纲情节点是否在正文中体现
version: 1.0.0
tags: [validation, quality-gate, hybrid]
check_method: hybrid
failure: block
priority: 3
---

# 大纲贴合度校验

## 程序化检查（快速通道）

### 1. 情节点关键词覆盖
- 方法：jieba 从细纲提取名词/动词关键词 → 在正文中匹配
- 阈值：核心关键词命中率 ≥ 80%
- 失败动作：warn（可能遗漏，交给 LLM 确认）

### 2. 情节点密度
- 方法：细纲按「，」「。」「；」分句得到情节点列表 → 统计数量
- 阈值：每 1000 字至少对应 1 个情节点
- 失败动作：warn

## LLM 辅助检查（结构化逐项核验）

当程序化检查产出 warn 或 fail 时启用。要求 LLM 对每个情节点输出结构化核验结果，必须引用原文作为证据。

### LLM 输出格式要求

```json
{
  "outline_points": [
    {
      "id": 1,
      "expected": "细纲情节点原文",
      "found_in_text": true,
      "evidence": "正文中对应的原文引用（必须原文摘录）",
      "coverage": "full | partial | missing",
      "missing_detail": "若 coverage 非 full，说明缺失了什么"
    }
  ],
  "keyword_coverage": {
    "expected_keywords": ["关键词列表"],
    "hit": ["命中的关键词"],
    "missed": ["未命中的关键词"],
    "hit_rate": 0.85
  },
  "overall_pass": false,
  "fail_reason": "具体未通过原因，引用情节点 ID"
}
```

- 阈值：所有 outline_points 的 coverage 必须为 "full"
