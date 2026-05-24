---
name: repetition-detection
description: 内容重复检测 — 多粒度检查章节内的文字重复
version: 1.0.0
tags: [validation, quality-gate, programmatic]
check_method: programmatic
failure: block
priority: 2
---

# 内容重复检测

## 检查项（全程序化，不依赖 LLM）

### 1. 逐句精确重复
- 方法：jieba 中文分句 → `collections.Counter`
- 阈值：同一句子出现 ≥3 次 → fail
- 最短句子长度：8 字符

### 2. 段落级滑动窗口相似度（新增）
- 方法：3-句滑动窗口 → 提取 n-gram 字符集 → Jaccard 相似度
- 阈值：任意两窗口相似度 > 0.7 → warn

### 3. 章节自相似度（新增）
- 方法：正文等分为 4 段 → 分别 embedding → 段间余弦相似度
- 阈值：任意两段相似度 > 0.85 → warn

### 4. 跨章节相似度（新增）
- 方法：当前章 embedding vs 前 3 章 embedding
- 阈值：任意前章相似度 > 0.8 → warn

## 输出格式

```json
{
  "check": "repetition-detection",
  "passed": true,
  "sentence_level": {
    "score": 95,
    "repeated": [],
    "total_sentences": 120,
    "unique_sentences": 114
  },
  "paragraph_level": {
    "max_jaccard": 0.35,
    "warnings": []
  },
  "self_similarity": {
    "max_cosine": 0.42,
    "warnings": []
  },
  "cross_chapter_similarity": {
    "max_cosine": 0.55,
    "warnings": []
  }
}
```
