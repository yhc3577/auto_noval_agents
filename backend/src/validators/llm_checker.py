"""LLM 结构化校验 —— 用 LLM 进行逐项取证式核验，输出 JSON + evidence。

与旧 Auditor 的区别:
- 旧：一个 Prompt 让 LLM 自由裁量 6 个维度 → "pass"/"fail"
- 新：每个维度独立调用 LLM，强制输出结构化 JSON + 原文证据引用
  LLM 角色从"法官"变为"取证员"
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from ..core.llm import call_llm
from ..services.prompt_service import format_prompt
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .skill_loader import SkillSpec

logger = get_logger(__name__)


def _extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON"""
    # 尝试匹配 markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    json_text = match.group(1) if match else text
    json_text = json_text.strip()
    json_text = re.sub(r",\s*([}\]])", r"\1", json_text)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    # 尝试从文本中提取最外层花括号
    brace_match = re.search(r"\{.*\}", json_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ─── 大纲贴合度 LLM 核验 ────────────────────────────────────────


async def check_outline_adherence_llm(
    chapter_content: str,
    chapter_outline: str,
) -> dict:
    """逐情节点核验大纲贴合度，要求 LLM 引用原文证据"""
    if not chapter_outline.strip():
        return {"overall_pass": True, "outline_points": [], "note": "无细纲，跳过"}

    # 将细纲拆分成情节点列表
    outline_points = re.split(r"[。；\n]", chapter_outline)
    outline_points = [p.strip() for p in outline_points if len(p.strip()) >= 10]

    if not outline_points:
        return {"overall_pass": True, "outline_points": [], "note": "细纲过短，跳过"}

    system_prompt = """你是一位严格的稿件审核员。你的任务是逐项核对章节正文是否完整体现了细纲中的每个情节点。

你必须引用正文原文作为证据。你的输出直接被程序解析，必须严格遵循 JSON 格式。

## 核心规则
- 对每个情节点，必须在正文中找到对应的原文段落作为 evidence
- coverage 判定:
  - "full" — 情节点在正文中有完整的对应展开
  - "partial" — 情节点有对应但展开不充分，或只体现了部分内容
  - "missing" — 情节点在正文中完全没有对应
- 只要有一个情节点 coverage 为 "partial" 或 "missing"，overall_pass 必须为 false
- 禁止在 JSON 外输出任何解释文字"""

    points_text = "\n".join(
        f"情节点{i+1}: {p}" for i, p in enumerate(outline_points)
    )

    user_prompt = f"""细纲情节点列表：
{points_text}

本章正文：
{chapter_content}

请逐项核验每个情节点，输出 JSON。"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        result = _extract_json(response)
        if not result:
            return {
                "overall_pass": False,
                "outline_points": [],
                "error": "LLM 返回无法解析",
                "raw_response": response[:500],
            }
        return result
    except Exception as e:
        logger.error(f"大纲贴合度 LLM 核验失败: {e}")
        return {"overall_pass": False, "outline_points": [], "error": str(e)}


# ─── 人设一致性 LLM 核验 ────────────────────────────────────────


async def check_character_consistency_llm(
    chapter_content: str,
    character_info: str,
) -> dict:
    """逐角色核验行为一致性，要求引用原文证据"""
    if not character_info.strip():
        return {"overall_pass": True, "characters": [], "note": "无人设信息，跳过"}

    system_prompt = """你是一位严格的角色一致性审核员。根据提供的人物设定，逐角色核验本章正文中的人物行为、对话、决策是否符合设定。

你必须引用正文原文作为证据。输出严格遵循 JSON 格式。

## 核心规则
- 对每个出场角色，列出本章中的所有行为和对话
- trait_violations: 列出所有违反人设的行为，包括原文证据和期望的行为
- 只要有一个角色存在 trait_violation，overall_pass 必须为 false
- 如果角色未在本章出场，标注 not_appeared: true
- 禁止在 JSON 外输出任何解释文字

## 输出 JSON 格式
```json
{
  "characters": [
    {
      "name": "角色名",
      "expected_traits": ["性格特征（从人设提取）"],
      "not_appeared": false,
      "actions_in_chapter": ["行为描述 + 原文证据"],
      "dialogue_in_chapter": ["对话内容（原文摘录）"],
      "trait_violations": [
        {
          "action": "违反设定的行为",
          "evidence": "原文证据",
          "expected_behavior": "根据人设应有的行为"
        }
      ],
      "pass": true
    }
  ],
  "overall_pass": true
}
```"""

    user_prompt = f"""角色设定：
{character_info}

本章正文：
{chapter_content}

请逐角色核验，输出 JSON。"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        result = _extract_json(response)
        if not result:
            return {
                "overall_pass": False,
                "characters": [],
                "error": "LLM 返回无法解析",
                "raw_response": response[:500],
            }
        return result
    except Exception as e:
        logger.error(f"人设一致性 LLM 核验失败: {e}")
        return {"overall_pass": False, "characters": [], "error": str(e)}


# ─── 合规 LLM 复核（仅在程序化触发时调用）────────────────────────


async def check_compliance_llm(
    chapter_content: str,
    triggered_keywords: list[dict],
) -> dict:
    """对程序化扫描触发的关键词进行上下文复核"""
    if not triggered_keywords:
        return {"overall_pass": True, "context_analysis": [], "note": "无触发词"}

    kw_list = json.dumps(triggered_keywords, ensure_ascii=False, indent=2)

    system_prompt = """你是一位内容合规审核员。程序扫描发现一些可能敏感的词汇，请根据上下文判断是否构成违规。

## 判定原则
- 正常的战斗描写 ≠ 暴力违规
- 正常的情感描写 ≠ 色情违规
- 角色受伤、治疗等情节需要 ≠ 血腥违规
- 只有在刻意渲染暴力、色情细节或以不当方式描写时才判违规

输出严格遵循 JSON 格式：
```json
{
  "context_analysis": [
    {
      "keyword": "敏感词",
      "category": "violence_extreme / sexual_explicit / political_sensitive / ...",
      "surrounding_text": "包含该词的完整上下文（原文摘录，50-100字）",
      "is_violation": false,
      "reason": "判断理由"
    }
  ],
  "overall_pass": true,
  "violation_details": []
}
```"""

    user_prompt = f"""程序扫描发现的敏感词：
{kw_list}

本章正文：
{chapter_content[:8000]}

请根据上下文逐条复核。"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        result = _extract_json(response)
        if not result:
            return {
                "overall_pass": True,
                "context_analysis": [],
                "raw_response": response[:500],
            }
        return result
    except Exception as e:
        logger.error(f"合规 LLM 复核失败: {e}")
        return {"overall_pass": False, "context_analysis": [], "error": str(e)}


# ─── 文笔质量 LLM 检查 ─────────────────────────────────────────


async def check_quality_llm(
    chapter_content: str,
) -> dict:
    """基础文笔质量 LLM 检查 — 结构完整性、节奏、可读性"""
    system_prompt = """你是一位小说质量评审员。对章节进行结构和文笔评估。

输出严格遵循 JSON 格式：
```json
{
  "structure": {
    "has_clear_opening": true,
    "has_clear_development": true,
    "has_clear_ending": true,
    "opening_quality": "开头评价（1-2句）",
    "ending_quality": "结尾评价（1-2句，是否自然收束而非截断）",
    "paragraph_issues": ["段落结构问题列表"]
  },
  "rhythm": {
    "pacing_issues": ["节奏问题：过快/过慢/松紧失当"],
    "scene_transitions": "场景转换评价"
  },
  "overall_pass": true
}
```"""

    user_prompt = f"""本章正文：
{chapter_content[:8000]}

请评估结构和节奏。"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        result = _extract_json(response)
        if not result:
            return {"overall_pass": True, "raw_response": response[:500]}
        return result
    except Exception as e:
        logger.error(f"文笔质量 LLM 检查失败: {e}")
        return {"overall_pass": True, "error": str(e)}


# ─── 选择性 LLM 核验（仅对程序化未通过的维度）────────────────────


async def run_llm_checks(
    content: str,
    chapter_outline: str,
    character_info: str,
    programmatic_results: list[dict],
) -> dict[str, dict]:
    """根据程序化检查结果，选择性触发 LLM 核验。

    只在程序化检查有 warn/fail 时才调 LLM，节省成本。
    """
    llm_results: dict[str, dict] = {}

    # 查找程序化检查的通过状态
    prog_map = {r.get("check", ""): r for r in programmatic_results}

    # 大纲关键词覆盖率不足 → 触发大纲 LLM 核验
    outline_coverage = prog_map.get("outline_keyword_coverage", {})
    if not outline_coverage.get("passed", True):
        logger.info("[LLM校验] 大纲关键词覆盖率不足，触发 LLM 核验")
        llm_results["outline_adherence"] = await check_outline_adherence_llm(
            content, chapter_outline
        )

    # 人物一致性有问题 → 触发人设 LLM 核验
    char_check = prog_map.get("character_consistency", {})
    if not char_check.get("passed", True):
        logger.info("[LLM校验] 人物一致性问题，触发 LLM 核验")
        llm_results["character_consistency"] = await check_character_consistency_llm(
            content, character_info
        )

    # 合规触发 → LLM 复核
    compliance = prog_map.get("compliance", {})
    if compliance.get("needs_llm_review", False):
        logger.info("[LLM校验] 合规扫描触发，执行 LLM 复核")
        llm_results["compliance"] = await check_compliance_llm(
            content, compliance.get("triggered_keywords", [])
        )

    # 文笔结构问题 → LLM 评估
    structure = prog_map.get("structure_quality", {})
    if not structure.get("passed", True):
        logger.info("[LLM校验] 文笔结构问题，触发 LLM 评估")
        llm_results["quality"] = await check_quality_llm(content)

    return llm_results
