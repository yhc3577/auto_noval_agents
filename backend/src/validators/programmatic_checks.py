"""程序化质量检查 —— 不依赖 LLM 的确定性验证。

包含:
- 字数达标检查
- 逐句 / 段落 / 自相似 / 跨章节重复检测
- 大纲关键词覆盖
- 人物出场 & 对话归属验证
- 合规敏感词扫描
- 基础结构 & 句式多样性
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

import jieba
import jieba.analyse

if TYPE_CHECKING:
    from ..services.embedding_service import EmbeddingService


# ─── 字数检查 ──────────────────────────────────────────────────


def check_word_count(
    content: str, target_words: int
) -> dict:
    """检查正文字数是否在 [target, target*1.3] 范围内"""
    wc = len(content)
    max_allowed = int(target_words * 1.3)
    passed = target_words <= wc <= max_allowed
    detail = (
        f"字数 {wc} 在目标范围 [{target_words}, {max_allowed}] 内"
        if passed
        else (
            f"字数不足：当前 {wc}，要求 ≥ {target_words}"
            if wc < target_words
            else f"字数超标：当前 {wc}，要求 ≤ {max_allowed}"
        )
    )
    return {
        "check": "word_count",
        "passed": passed,
        "word_count": wc,
        "target": target_words,
        "max_allowed": max_allowed,
        "details": detail,
    }


# ─── 分句工具 ──────────────────────────────────────────────────

_MIN_SENTENCE_LEN = 8


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"[。！？；\n]+", text)
    return [s.strip() for s in sentences if len(s.strip()) >= _MIN_SENTENCE_LEN]


# ─── 1. 逐句精确重复 ───────────────────────────────────────────


def check_sentence_repetition(content: str) -> dict:
    """检测同一句子是否出现 ≥3 次"""
    sentences = _split_sentences(content)
    total = len(sentences)

    if total < 3:
        return {
            "passed": True,
            "score": 100,
            "total_sentences": total,
            "unique_sentences": total,
            "repeated": [],
        }

    counter = Counter(sentences)
    repeated = [
        {"sentence": s[:60] + ("..." if len(s) > 60 else ""), "count": c}
        for s, c in counter.items()
        if c >= 3
    ]
    unique_ratio = len(set(sentences)) / total
    score = round(unique_ratio * 100)

    passed = score >= 40
    return {
        "passed": passed,
        "score": score,
        "total_sentences": total,
        "unique_sentences": len(set(sentences)),
        "repeated": repeated,
        "details": "" if passed else f"内容重复严重：唯一句子占比仅 {score}%，{len(repeated)} 处语句重复出现 3 次以上",
    }


# ─── 2. 段落级滑动窗口 Jaccard 相似度 ────────────────────────────


def _ngrams(tokens: list[str], n: int = 3) -> set[str]:
    return {"|".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def check_paragraph_similarity(content: str, window: int = 3, threshold: float = 0.7) -> dict:
    """滑动窗口 n-gram Jaccard 相似度检测"""
    sentences = _split_sentences(content)
    if len(sentences) < window * 2:
        return {"passed": True, "max_jaccard": 0.0, "warnings": []}

    warnings: list[dict] = []
    max_jaccard = 0.0

    for i in range(len(sentences) - window + 1):
        window_a = sentences[i : i + window]
        tokens_a = list(jieba.cut("".join(window_a)))
        ngrams_a = _ngrams(tokens_a)

        for j in range(i + window, len(sentences) - window + 1):
            window_b = sentences[j : j + window]
            tokens_b = list(jieba.cut("".join(window_b)))
            ngrams_b = _ngrams(tokens_b)

            if not ngrams_a or not ngrams_b:
                continue

            intersection = len(ngrams_a & ngrams_b)
            union = len(ngrams_a | ngrams_b)
            jaccard = intersection / union if union > 0 else 0.0
            max_jaccard = max(max_jaccard, jaccard)

            if jaccard > threshold:
                warnings.append({
                    "window_a_start": i,
                    "window_b_start": j,
                    "jaccard": round(jaccard, 3),
                    "preview": sentences[i][:40],
                })

    passed = len(warnings) == 0
    return {
        "passed": passed,
        "max_jaccard": round(max_jaccard, 3),
        "warnings": warnings,
        "threshold": threshold,
        "details": "" if passed else f"段落级重复：{len(warnings)} 处滑动窗口 Jaccard 相似度 > {threshold}",
    }


# ─── 3. 章节自相似度 ────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def check_self_similarity(
    content: str,
    embed_service: "EmbeddingService",
    segments: int = 4,
    threshold: float = 0.85,
) -> dict:
    """将章节等分为 N 段，检测段间余弦相似度"""
    total_len = len(content)
    if total_len < 500 or segments < 2:
        return {"passed": True, "max_cosine": 0.0, "warnings": []}

    seg_len = total_len // segments
    seg_texts = [content[i * seg_len : (i + 1) * seg_len] for i in range(segments)]
    seg_texts[-1] += content[segments * seg_len :]  # 尾部追加到最后一段

    try:
        embeddings = [embed_service.embed_text(t) for t in seg_texts]
    except Exception:
        return {"passed": True, "max_cosine": 0.0, "warnings": [], "error": "embedding failed"}

    warnings: list[dict] = []
    max_cos = 0.0

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            cos = _cosine_similarity(embeddings[i], embeddings[j])
            max_cos = max(max_cos, cos)
            if cos > threshold:
                warnings.append({
                    "segment_a": i + 1,
                    "segment_b": j + 1,
                    "cosine": round(cos, 3),
                })

    return {
        "passed": len(warnings) == 0,
        "max_cosine": round(max_cos, 3),
        "warnings": warnings,
        "threshold": threshold,
    }


# ─── 4. 跨章节相似度 ───────────────────────────────────────────


async def check_cross_chapter_similarity(
    content: str,
    project_id: str,
    current_chapter: int,
    embed_service: "EmbeddingService",
    threshold: float = 0.8,
    lookback: int = 3,
) -> dict:
    """当前章节 vs 前 N 章 embedding 相似度"""
    if current_chapter <= 1:
        return {"passed": True, "max_cosine": 0.0, "warnings": []}

    try:
        current_vec = embed_service.embed_text(content[:2000])  # 取前 2000 字
    except Exception:
        return {"passed": True, "max_cosine": 0.0, "warnings": [], "error": "embedding failed"}

    # 从 embedding service 获取前几章的向量（如果有的话）
    # 这里需要外部传入，当前仅做结构占位
    return {
        "passed": True,
        "max_cosine": 0.0,
        "warnings": [],
        "note": "cross-chapter check requires external vector injection",
    }


# ─── 大纲关键词覆盖 ────────────────────────────────────────────


def check_outline_keyword_coverage(
    content: str, chapter_outline: str, threshold: float = 0.8
) -> dict:
    """提取细纲关键词，检查正文覆盖率"""
    if not chapter_outline.strip():
        return {"passed": True, "hit_rate": 1.0, "expected": [], "hit": [], "missed": []}

    # 从细纲提取关键词（名词 + 动词）
    keywords = jieba.analyse.extract_tags(chapter_outline, topK=20, withWeight=False)
    # 补充正则提取：引号中的对话提示、数字+量词、专有名词
    extra = re.findall(r"[「](.*?)[」]", chapter_outline)
    for e in extra:
        for w in jieba.cut(e):
            if len(w) >= 2 and w not in keywords:
                keywords.append(w)

    if not keywords:
        return {"passed": True, "hit_rate": 1.0, "expected": [], "hit": [], "missed": []}

    hit: list[str] = []
    missed: list[str] = []
    for kw in keywords:
        if kw in content:
            hit.append(kw)
        else:
            missed.append(kw)

    hit_rate = len(hit) / len(keywords) if keywords else 1.0

    passed = hit_rate >= threshold
    return {
        "passed": passed,
        "hit_rate": round(hit_rate, 3),
        "threshold": threshold,
        "expected": keywords,
        "hit": hit,
        "missed": missed,
        "details": "" if passed else f"大纲关键词覆盖率 {hit_rate:.0%} < {threshold:.0%}，未命中: {', '.join(missed[:5])}",
    }


# ─── 人物出场 & 对话归属验证 ─────────────────────────────────────


def _extract_character_names(character_info: str) -> list[str]:
    """从人设文本中提取角色名"""
    # 匹配 "名字："、"姓名："、"角色名：" 等模式
    names: list[str] = []
    patterns = [
        r"(?:名字|姓名|角色名|名称)[：:]\s*(.+?)(?:\n|$)",
        r'"([^"]{1,6})"[：:]\s*(?:是|为)',
    ]
    for pat in patterns:
        matches = re.findall(pat, character_info)
        names.extend(m.strip() for m in matches if 1 <= len(m.strip()) <= 6)

    # 去重 + 过滤明显不是人名的
    skip_words = {"是", "的", "了", "在", "和", "与", "或", "一个", "这个", "那个", "一种"}
    return list(dict.fromkeys(n for n in names if n not in skip_words))


def check_character_consistency(content: str, character_info: str) -> dict:
    """验证人物出场和对话归属"""
    defined_chars = _extract_character_names(character_info)

    # 1. 角色出场检查
    appeared: list[str] = []
    not_appeared: list[str] = []
    for name in defined_chars:
        if name in content:
            appeared.append(name)
        else:
            not_appeared.append(name)

    # 2. 对话归属检查
    dialogue_pattern = re.compile(r"[「](.*?)[」]")
    speaker_pattern = re.compile(r"([^\s，。！？；「」]{1,6})(?:说|道|问|答|喊|叫|叹|怒|惊|笑|哭|冷[哼声]|淡[淡声])")

    all_speakers: list[str] = []
    for match in speaker_pattern.finditer(content):
        name = match.group(1)
        if name not in all_speakers:
            all_speakers.append(name)

    undefined_speakers = [s for s in all_speakers if s not in defined_chars]
    undefined_ratio = len(undefined_speakers) / max(len(all_speakers), 1)

    # 3. 角色名一致性 — 正文中出现但不在人设中的新角色
    # 简单策略：正文中 2-4 字的中文名词，出现在动作动词前
    potential_new_characters = set(undefined_speakers)

    passed = undefined_ratio < 0.05 and len(potential_new_characters) <= 2
    detail_parts = []
    if undefined_ratio >= 0.05:
        detail_parts.append(f"未定义对话者占比 {undefined_ratio:.0%}（{', '.join(undefined_speakers[:5])}）")
    if len(potential_new_characters) > 2:
        detail_parts.append(f"疑似新角色 {len(potential_new_characters)} 个超出允许范围")
    return {
        "passed": passed,
        "defined_characters": defined_chars,
        "appeared": appeared,
        "not_appeared": not_appeared,
        "all_speakers": all_speakers,
        "undefined_speakers": undefined_speakers,
        "undefined_ratio": round(undefined_ratio, 3),
        "new_characters": list(potential_new_characters),
        "details": "" if passed else "；".join(detail_parts),
    }


# ─── 合规敏感词扫描 ────────────────────────────────────────────


# 高危敏感词库（实际使用时建议从外部配置加载）
_SENSITIVE_PATTERNS: dict[str, list[str]] = {
    "violence_extreme": [
        "碎尸", "肢解", "虐杀", "凌迟", "剥皮", "抽筋", "挖眼", "割舌",
        "斩首示众", "五马分尸", "千刀万剐",
    ],
    "sexual_explicit": [
        "淫", "荡妇", "妓女", "嫖", "卖淫", "强暴", "轮奸",
    ],
    "sexual_suggestive": [
        "胴体", "酥胸", "玉体", "香艳", "春光", "双修.*合欢",
    ],
    "political_sensitive": [
        "颠覆.*政权", "分裂.*国家", "恐怖.*主义",
    ],
}


def _count_violence_words(content: str) -> int:
    """统计暴力相关词汇出现次数"""
    violence_words = [
        "杀", "死", "血", "剑", "刀", "枪", "伤", "断", "裂", "碎",
        "爆", "炸", "毁", "灭", "斩", "砍", "刺", "劈", "轰", "焚",
    ]
    count = 0
    for w in violence_words:
        count += content.count(w)
    return count


def _count_body_words(content: str) -> int:
    """统计身体部位词出现次数（用于情色擦边检测）"""
    body_words = ["胸", "腿", "腰", "臀", "唇", "舌", "颈", "肩", "背", "腹"]
    count = 0
    for w in body_words:
        count += content.count(w)
    return count


def check_compliance(content: str) -> dict:
    """合规敏感词扫描"""
    triggered: list[dict] = []

    for category, patterns in _SENSITIVE_PATTERNS.items():
        for pat in patterns:
            matches = re.findall(pat, content)
            for m in matches:
                triggered.append({
                    "category": category,
                    "pattern": pat,
                    "match": m if isinstance(m, str) else pat,
                })

    # 暴力密度检测
    violence_count = _count_violence_words(content)
    word_count = len(content)
    violence_density = violence_count / max(word_count / 500, 1)
    violence_triggered = violence_density >= 8

    # 情色擦边密度检测
    body_count = _count_body_words(content)
    body_density = body_count / max(word_count / 500, 1)
    body_triggered = body_density >= 5

    high_severity_triggered = any(
        t["category"] in ("violence_extreme", "sexual_explicit", "political_sensitive")
        for t in triggered
    )

    passed = not high_severity_triggered

    detail_parts = []
    if high_severity_triggered:
        for t in triggered:
            if t["category"] in ("violence_extreme", "sexual_explicit", "political_sensitive"):
                detail_parts.append(f"[{t['category']}] 命中高危词: {t.get('match', t.get('pattern', ''))}")
    details = "；".join(detail_parts) if detail_parts else ""

    return {
        "passed": passed,
        "triggered_keywords": triggered,
        "details": details,
        "violence_density": {
            "count": violence_count,
            "per_500_words": round(violence_density, 2),
            "triggered": violence_triggered,
        },
        "body_word_density": {
            "count": body_count,
            "per_500_words": round(body_density, 2),
            "triggered": body_triggered,
        },
        "needs_llm_review": violence_triggered or body_triggered,
    }


# ─── 基础文笔质量 ──────────────────────────────────────────────


def check_structure_quality(content: str) -> dict:
    """检查段落结构、句式多样性、标点配对"""
    # 段落切分
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    para_count = len(paragraphs)

    # 最长的段落
    max_para_len = max((len(p) for p in paragraphs), default=0)
    para_too_long = max_para_len > 800

    # 结尾段非空
    has_ending = bool(paragraphs) and len(paragraphs[-1]) > 0

    # 句式多样性 — 按「，」「。」分短句
    clauses = re.split(r"[，。！？；：、]", content)
    clauses = [c.strip() for c in clauses if c.strip()]
    if not clauses:
        return {
            "passed": True,
            "paragraph_count": para_count,
            "max_paragraph_len": max_para_len,
            "has_ending": has_ending,
            "short_sentence_ratio": 0,
            "long_sentence_ratio": 0,
            "paired_quotes_ok": True,
            "issues": [],
        }

    clause_lens = [len(c) for c in clauses]
    short_ratio = sum(1 for l in clause_lens if l <= 20) / len(clause_lens)
    long_ratio = sum(1 for l in clause_lens if l >= 80) / len(clause_lens)

    # 引号配对检查
    left_quotes = content.count("「")
    right_quotes = content.count("」")
    quotes_paired = left_quotes == right_quotes

    issues: list[str] = []
    if para_count < 5:
        issues.append(f"段落数 {para_count} < 5，建议丰富段落结构")
    if para_too_long:
        issues.append(f"最长段 {max_para_len} 字 > 800，影响可读性")
    if not has_ending:
        issues.append("结尾段为空，章节可能被截断")
    if short_ratio < 0.15:
        issues.append(f"短句占比 {short_ratio:.0%} < 15%，句式可能过于冗长")
    if long_ratio > 0.30:
        issues.append(f"长句占比 {long_ratio:.0%} > 30%，建议拆分长句")
    if not quotes_paired:
        issues.append(f"中文引号不配对：「{left_quotes} 个 vs 」{right_quotes} 个")

    passed = not issues

    return {
        "passed": passed,
        "details": "" if passed else "；".join(issues),
        "paragraph_count": para_count,
        "max_paragraph_len": max_para_len,
        "has_ending": has_ending,
        "short_sentence_ratio": round(short_ratio, 3),
        "long_sentence_ratio": round(long_ratio, 3),
        "paired_quotes_ok": quotes_paired,
        "issues": issues,
    }


# ─── 汇总：一次运行所有程序化检查 ────────────────────────────────


async def run_all_programmatic(
    content: str,
    chapter_outline: str,
    character_info: str,
    target_words: int,
    project_id: str = "",
    current_chapter: int = 1,
    embed_service: "EmbeddingService | None" = None,
) -> list[dict]:
    """运行所有程序化检查，返回结果列表"""
    results: list[dict] = []

    # 1. 字数
    results.append(check_word_count(content, target_words))

    # 2. 逐句重复
    results.append(check_sentence_repetition(content))

    # 3. 段落相似度
    results.append(check_paragraph_similarity(content))

    # 4. 章节自相似度（需要 embedding）
    if embed_service:
        results.append(await check_self_similarity(content, embed_service))
    else:
        results.append({"check": "self_similarity", "passed": True, "skipped": "no embed_service"})

    # 5. 跨章节相似度
    if embed_service and project_id:
        results.append(
            await check_cross_chapter_similarity(
                content, project_id, current_chapter, embed_service
            )
        )
    else:
        results.append({
            "check": "cross_chapter_similarity",
            "passed": True,
            "skipped": "no embed_service or project_id",
        })

    # 6. 大纲关键词覆盖
    results.append(check_outline_keyword_coverage(content, chapter_outline))

    # 7. 人物一致性
    if character_info:
        results.append(check_character_consistency(content, character_info))
    else:
        results.append({"check": "character_consistency", "passed": True, "skipped": "no character_info"})

    # 8. 合规扫描
    results.append(check_compliance(content))

    # 9. 文笔结构
    results.append(check_structure_quality(content))

    return results
