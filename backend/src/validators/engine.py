"""验证引擎 —— 加载 Skills、运行程序化+LLM 检查、产出统一结果。

流程:
1. 加载所有 Skill 文件
2. 运行程序化检查（快速、免费、确定性）
3. 程序化全部通过 → 抽样 10% 做 LLM 深度检查
4. 程序化有 warn/fail → 触发 LLM 结构化核验
5. 汇总所有结果 → 决定 pass / rewrite / manual_review
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..utils.logger import get_logger
from .programmatic_checks import run_all_programmatic
from .llm_checker import run_llm_checks
from .skill_loader import load_all_skills, SkillSpec

if TYPE_CHECKING:
    from ..services.embedding_service import EmbeddingService

logger = get_logger(__name__)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")


@dataclass
class ValidationResult:
    """统一校验结果"""
    passed: bool
    score: int
    feedback: str
    # 分类反馈
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # 各维度明细
    programmatic_results: list[dict] = field(default_factory=list)
    llm_results: dict[str, dict] = field(default_factory=dict)
    # 元数据
    checks_run: int = 0
    checks_passed: int = 0
    llm_calls_made: int = 0
    llm_calls_saved: int = 0


async def validate_chapter(
    content: str,
    chapter_outline: str,
    character_info: str,
    target_words: int,
    project_id: str = "",
    current_chapter: int = 1,
    embed_service: "EmbeddingService | None" = None,
    llm_sample_rate: float = 0.1,
) -> ValidationResult:
    """对章节内容执行完整校验。

    Args:
        content: 章节正文
        chapter_outline: 章节细纲
        character_info: 人物设定文本
        target_words: 目标字数
        project_id: 项目 ID（用于跨章节对比）
        current_chapter: 当前章节号
        embed_service: 嵌入服务（用于相似度计算）
        llm_sample_rate: 程序化全通过时的 LLM 抽样率（0-1）

    Returns:
        ValidationResult with passed, score, feedback, and detailed results
    """
    skills = load_all_skills(SKILLS_DIR)
    logger.info(
        f"[验证引擎] 加载 {len(skills)} 个 Skills，"
        f"开始校验 chapter={current_chapter}, words={len(content)}"
    )

    # ── Phase 1: 程序化检查 ──
    prog_results = await run_all_programmatic(
        content=content,
        chapter_outline=chapter_outline,
        character_info=character_info,
        target_words=target_words,
        project_id=project_id,
        current_chapter=current_chapter,
        embed_service=embed_service,
    )
    prog_pass = all(r.get("passed", True) for r in prog_results)

    blocking_issues: list[str] = []
    warnings: list[str] = []

    for r in prog_results:
        check_name = r.get("check", "unknown")
        if not r.get("passed", True):
            detail = r.get("details", "") or r.get("issues", [])
            if isinstance(detail, list):
                if detail:
                    blocking_issues.extend(f"[{check_name}] {d}" for d in detail)
                else:
                    # 兜底：检查失败但没有提供 details/issues，自动生成
                    blocking_issues.append(f"[{check_name}] 检查未通过（score={r.get('score', r.get('hit_rate', 'N/A'))}）")
            elif detail:
                blocking_issues.append(f"[{check_name}] {detail}")

        # 收集 warning 级别的问题
        warnings_list = r.get("warnings", [])
        if warnings_list:
            if isinstance(warnings_list, list) and warnings_list:
                if isinstance(warnings_list[0], dict):
                    warnings.extend(
                        f"[{check_name}] {w.get('preview', str(w))}"
                        for w in warnings_list
                    )
                else:
                    warnings.extend(f"[{check_name}] {w}" for w in warnings_list)

    # ── Phase 2: LLM 检查（按需触发）──
    llm_results: dict[str, dict] = {}
    llm_calls_made = 0
    llm_calls_saved = len(skills)  # 假设所有 skill 都有 LLM 部分

    import random
    if prog_pass and random.random() > llm_sample_rate:
        # 程序化全通过 + 未被抽样 → 跳过 LLM
        logger.info("[验证引擎] 程序化检查全通过，跳过 LLM 核验（未命中抽样）")
    else:
        # 程序化有失败项 或 被抽样 → 执行 LLM 核验
        llm_results = await run_llm_checks(
            content=content,
            chapter_outline=chapter_outline,
            character_info=character_info,
            programmatic_results=prog_results,
        )
        llm_calls_made = len(llm_results)
        llm_calls_saved = len(skills) - llm_calls_made

        # 将 LLM 结果也纳入判定
        for llm_check_name, llm_result in llm_results.items():
            if not llm_result.get("overall_pass", True):
                # 从 LLM 结果提取人类可读的失败原因
                fail_reason = llm_result.get("fail_reason", "")
                if not fail_reason:
                    # 从 outline_points 或 characters 中提取第一个失败
                    if "outline_points" in llm_result:
                        failed = [
                            p for p in llm_result["outline_points"]
                            if p.get("coverage") in ("partial", "missing")
                        ]
                        if failed:
                            fail_reason = f"大纲贴合度: {len(failed)} 个情节点未完整覆盖"
                    elif "characters" in llm_result:
                        failed_chars = [
                            c["name"] for c in llm_result["characters"] if not c.get("pass", True)
                        ]
                        if failed_chars:
                            fail_reason = f"人设一致性: {', '.join(failed_chars)} 行为违反设定"
                    elif "context_analysis" in llm_result:
                        violations = [
                            c for c in llm_result["context_analysis"] if c.get("is_violation")
                        ]
                        if violations:
                            fail_reason = f"合规: {len(violations)} 处内容违规"
                    else:
                        fail_reason = str(llm_result.get("error", "LLM 核验未通过"))

                blocking_issues.append(f"[llm:{llm_check_name}] {fail_reason}")

    # ── Phase 3: 汇总判定 ──
    all_passed = len(blocking_issues) == 0

    # 计算分数
    score = 100
    # 程序化扣分
    for r in prog_results:
        if not r.get("passed", True):
            check_name = r.get("check", "")
            if check_name == "word_count":
                score -= 20
            elif check_name == "sentence_repetition":
                score -= 15
            elif check_name == "compliance":
                score -= 30
            else:
                score -= 5
    # LLM 扣分
    for llm_name, llm_r in llm_results.items():
        if not llm_r.get("overall_pass", True):
            score -= 10

    score = max(0, min(100, score))

    # 构建反馈信息
    feedback_parts: list[str] = []
    if blocking_issues:
        feedback_parts.append("## 必须修正的问题")
        feedback_parts.extend(f"- {issue}" for issue in blocking_issues)
    if warnings:
        feedback_parts.append("## 建议优化")
        feedback_parts.extend(f"- {w}" for w in warnings)
    if not feedback_parts:
        feedback_parts.append("所有质量检查通过")

    # 检查运行统计
    checks_run = len(prog_results) + llm_calls_made
    checks_passed = sum(1 for r in prog_results if r.get("passed", True))
    checks_passed += sum(
        1 for r in llm_results.values() if r.get("overall_pass", True)
    )

    result = ValidationResult(
        passed=all_passed,
        score=score,
        feedback="\n".join(feedback_parts),
        blocking_issues=blocking_issues,
        warnings=warnings,
        programmatic_results=prog_results,
        llm_results=llm_results,
        checks_run=checks_run,
        checks_passed=checks_passed,
        llm_calls_made=llm_calls_made,
        llm_calls_saved=llm_calls_saved,
    )

    failed_checks = [r.get("check", "?") for r in prog_results if not r.get("passed", True)]
    logger.info(
        f"[验证引擎] 校验完成: passed={all_passed}, score={score}, "
        f"checks={checks_run}/{checks_passed} passed, "
        f"llm_calls={llm_calls_made} made / {llm_calls_saved} saved"
        + (f", failures=[{', '.join(failed_checks)}]" if failed_checks else "")
    )
    if blocking_issues:
        for issue in blocking_issues[:3]:
            logger.info(f"[验证引擎]   block: {issue}")
    return result
