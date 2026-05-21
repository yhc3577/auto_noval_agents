"""剧情审核Agent：大纲贴合度、人设一致性、文笔质量校验、内容重复检测（prompt 模板可配置）"""

import json
import re
from collections import Counter

from ..core.llm import call_llm
from ..services.prompt_service import format_prompt
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 最小检测长度：短于此值的句子不参与重复检测
_MIN_SENTENCE_LEN = 8


def _split_sentences(text: str) -> list[str]:
    """按中文标点分句"""
    sentences = re.split(r"[。！？；\n]+", text)
    return [s.strip() for s in sentences if len(s.strip()) >= _MIN_SENTENCE_LEN]


def _detect_repetition(text: str) -> dict:
    """程序化检测章节正文中的内容重复"""
    sentences = _split_sentences(text)
    total = len(sentences)

    if total < 3:
        return {"repetition_score": 100, "total_sentences": total,
                "repeated_sentences": [], "repetition_issues": []}

    counter = Counter(sentences)
    exact_dupes = {s: c for s, c in counter.items() if c >= 3}

    issues: list[str] = []
    for sentence, count in exact_dupes.items():
        issues.append(f"句子「{sentence[:40]}{'...' if len(sentence)>40 else ''}」重复出现 {count} 次")

    unique_ratio = len(set(sentences)) / total
    repetition_score = round(unique_ratio * 100)

    return {
        "repetition_score": repetition_score,
        "total_sentences": total,
        "unique_sentences": len(set(sentences)),
        "repeated_sentences": issues,
        "repetition_issues": issues,
    }


def _parse_audit_response(response: str) -> dict:
    """从 LLM 响应中解析结构化审核结果"""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    json_text = match.group(1) if match else response

    json_text = json_text.strip()
    json_text = re.sub(r",\s*([}\]])", r"\1", json_text)

    try:
        data = json.loads(json_text)
        return {
            "result": data.get("result", "fail"),
            "score": int(data.get("score", 50)),
            "opinion": data.get("opinion", response),
            "outline_issues": data.get("outline_issues", []),
            "character_issues": data.get("character_issues", []),
            "coherence_issues": data.get("coherence_issues", []),
            "repetition_issues": data.get("repetition_issues", []),
            "writing_quality_issues": data.get("writing_quality_issues", []),
            "compliance_issues": data.get("compliance_issues", []),
        }
    except (json.JSONDecodeError, ValueError):
        pass

    lower = response.lower()
    passed = "pass" in lower and "fail" not in lower
    return {
        "result": "pass" if passed else "fail",
        "score": 80 if passed else 50,
        "opinion": response,
        "outline_issues": [],
        "character_issues": [],
        "coherence_issues": [],
        "repetition_issues": [],
        "writing_quality_issues": [],
        "compliance_issues": [],
    }


async def audit_chapter(
    chapter_content: str,
    chapter_outline: str,
    character_info: str,
    global_summary: str,
) -> dict:
    """剧情质量审核（prompt 模板可配置）"""
    rep = _detect_repetition(chapter_content)

    if rep["repetition_score"] < 40:
        return {
            "result": "fail",
            "score": max(0, rep["repetition_score"]),
            "opinion": f"程序检测发现严重内容重复：{len(rep['repeated_sentences'])} 处语句重复出现 3 次以上。唯一句子占比仅 {rep['repetition_score']}%。请修正后重新提交。",
            "outline_issues": [],
            "character_issues": [],
            "coherence_issues": [],
            "repetition_issues": rep["repetition_issues"],
            "writing_quality_issues": [],
            "compliance_issues": [],
        }

    system_prompt = await format_prompt("auditor_system")

    rep_text = ""
    if rep["repeated_sentences"]:
        rep_text = "\n".join(f"- {issue}" for issue in rep["repeated_sentences"])

    user_prompt = await format_prompt(
        "auditor_user",
        chapter_outline=chapter_outline,
        character_info=character_info,
        global_summary=global_summary,
        rep_text=rep_text if rep_text else "未检测到明显的程序级重复",
        chapter_content=chapter_content,
    )

    try:
        response = await call_llm(system_prompt, user_prompt)
        result = _parse_audit_response(response)
        if rep["repetition_issues"] and not result.get("repetition_issues"):
            result["repetition_issues"] = rep["repetition_issues"]
        return result
    except Exception as e:
        logger.error(f"剧情审核失败: {e}", exc_info=True)
        return {
            "result": "fail", "score": 0, "opinion": f"审核异常: {str(e)}",
            "outline_issues": [], "character_issues": [], "coherence_issues": [],
            "repetition_issues": rep["repetition_issues"],
            "writing_quality_issues": [], "compliance_issues": [],
        }
