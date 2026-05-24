---
name: character-consistency
description: 人设一致性校验 — 检查人物行为/对话是否符合设定
version: 1.0.0
tags: [validation, quality-gate, hybrid]
check_method: hybrid
failure: block
priority: 4
---

# 人设一致性校验

## 程序化检查

### 1. 角色出场验证
- 方法：从人设文本中正则提取所有已定义角色名 → 在正文中搜索
- 输出：出场角色列表 + 未出场角色列表

### 2. 对话归属检查
- 方法：正则提取所有「XX说/道/问/答/喊/叫/叹/怒/惊/笑/哭」模式
- 验证：每个说话者是否在人设中已定义
- 阈值：未定义角色对话占比 < 5%

### 3. 角色名一致性检查
- 方法：人设中角色名 vs 正文中出现的新角色名（不在人设中）
- 阈值：新增未定义角色 ≤ 2 个（允许路人角色）

## LLM 辅助检查（逐角色行为核验）

当程序化检查产出 warn 或正文较长（>2000 字）时启用。要求 LLM 对每个出场角色进行行为一致性核验。

### LLM 输出格式要求

```json
{
  "characters": [
    {
      "name": "角色名",
      "expected_traits": ["性格特征1", "性格特征2"],
      "actions_in_chapter": ["本章行为1", "本章行为2"],
      "dialogue_in_chapter": ["「对话原文摘录1」", "「对话原文摘录2」"],
      "trait_violations": [
        {
          "action": "违反设定的行为",
          "evidence": "原文证据",
          "expected": "根据人设应有的行为"
        }
      ],
      "pass": true
    }
  ],
  "new_characters": [
    {
      "name": "新角色名",
      "role_hint": "从上下文推断的角色定位"
    }
  ],
  "overall_pass": true
}
```

- 阈值：所有已定义角色的 trait_violations 必须为空
