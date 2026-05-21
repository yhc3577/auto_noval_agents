"""LangGraph 流水线编排：6Agent StateGraph 节点连接、条件路由、循环重写逻辑"""

from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ..core.database import get_mongodb
from ..core.state import NovelState
from ..services.cache_service import get_summary, save_progress, save_summary, save_chapter_memory, search_related_memories, publish_stream_token, publish_stream_done
from ..services.embedding_service import embed_text, build_chapter_embedding_text, build_query_embedding_text
from ..services.vector_service import VectorService
from ..utils.logger import get_logger
from .auditor import audit_chapter
from .copyrighter import check_copyright
from .dispatcher import dispatch_chapter
from .summarizer import generate_summary, update_global_summary, generate_chapter_title
from ..core.llm import call_llm_stream
from ..services.prompt_service import format_prompt
from .writer import _strip_meta, write_chapter_stream

logger = get_logger(__name__)

MAX_REWRITE_TIMES = 3
_vector_service = VectorService()


# ── 辅助函数 ──────────────────────────────────────────────


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关键词（使用 jieba 分词）"""
    import jieba
    import jieba.analyse

    # 使用 jieba TF-IDF 提取关键词
    keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=False)

    # 过滤长度为1的词和纯数字
    keywords = [w for w in keywords if len(w) > 1 and not w.isdigit()]

    # 额外提取人名（以"说"、"道"、"想"前面的词作为人名候选）
    import re
    name_pattern = r'([一-龥]{2,4})(?:说|道|想|笑|怒|惊|叹|问|答|叫|喊|哭)'
    names = re.findall(name_pattern, text)
    for name in names:
        if name not in keywords and len(name) >= 2:
            keywords.append(name)

    return keywords[:10]  # 最多10个关键词


async def _semantic_search(
    project_id: str,
    chapter_outline: str,
    chapter_number: int,
    limit: int = 15,
) -> list[dict]:
    """语义检索相关前文章节，失败时返回空列表"""
    try:
        query_text = build_query_embedding_text(chapter_outline, chapter_number)
        query_vector = embed_text(query_text)
        results = _vector_service.search(project_id, query_vector, top_k=limit)
        logger.info(f"[语义检索] 找到 {len(results)} 条相关记忆")
        return results
    except Exception as e:
        logger.warning(f"语义检索失败: {e}")
        return []


def _format_memories(memories: list[dict]) -> str:
    """格式化记忆为文本，包含关键事件、人物变化和伏笔"""
    if not memories:
        return ""
    lines = []
    for mem in memories:
        ch_num = mem.get("chapter_number", "?")
        lines.append(f"── 第{ch_num}章 ──")
        summary = mem.get("summary", "")
        if summary:
            lines.append(f"  摘要: {summary[:300]}")
        key_events = mem.get("key_events", [])
        if key_events:
            lines.append(f"  关键事件: {'; '.join(key_events)}")
        char_changes = mem.get("character_changes", [])
        if char_changes:
            lines.append(f"  人物变化: {'; '.join(char_changes)}")
        foreshadowing = mem.get("foreshadowing", [])
        if foreshadowing:
            lines.append(f"  伏笔: {'; '.join(foreshadowing)}")
    return "\n".join(lines)


async def _check_pause(project_id: str) -> dict | None:
    """检查项目是否已暂停，是则返回暂停状态字典"""
    db = await get_mongodb()
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    if project and project["status"] != "writing":
        logger.info(f"[暂停检测] 项目已暂停: {project_id}")
        return {
            "step": "paused",
            "error_info": "创作已暂停",
        }
    return None


# ── Node 函数 ──────────────────────────────────────────────


async def node_dispatch(state: NovelState) -> dict:
    """调度节点：加载项目配置、章节细纲、角色信息"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    logger.info(f"[调度节点] 开始调度: project_id={project_id}, chapter={current_chapter}")

    dispatch_result = await dispatch_chapter(project_id, current_chapter)
    logger.info(f"[调度节点] 调度完成: status={dispatch_result.get('status')}")

    if dispatch_result.get("status") == "paused":
        return {"step": "paused", "error_info": "创作已暂停"}

    if dispatch_result.get("status") == "manual_review":
        return {
            "step": "manual_review",
            "rewrite_times": 0,
        }

    if dispatch_result.get("status") != "ready":
        return {"step": "error", "error_info": f"调度失败: {dispatch_result}"}

    return {
        "step": "dispatched",
        "chapter_outline": dispatch_result.get("chapter_outline", ""),
        "chapter_title": dispatch_result.get("chapter_title", f"第{current_chapter}章"),
        "user_config": {
            "character_info": dispatch_result.get("character_info", ""),
            "global_summary": dispatch_result.get("global_summary", ""),
            "world_setting": dispatch_result.get("world_setting", ""),
            "style": dispatch_result.get("style", ""),
            "words_per_chapter": dispatch_result.get("words_per_chapter", 3000),
            "copyright_threshold": dispatch_result.get("copyright_threshold", 0.2),
        },
    }


async def node_writer(state: NovelState) -> dict:
    """写作节点：依据细纲+人设+摘要创作正文"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    config = state["user_config"]
    logger.info(f"[写作节点] 开始创作: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    pause_check = await _check_pause(project_id)
    if pause_check:
        return pause_check
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    total_chapters = project["chapter_count"] if project else 1
    progress_pct = round((current_chapter - 1) / total_chapters * 100, 1)

    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": total_chapters,
        "progress": progress_pct,
        "status": "writing",
        "chapter_status": "writing",
        "log": f"正在创作第{current_chapter}章...",
    })

    # 加载上一章摘要，用于衔接
    prev_summary = ""
    if current_chapter > 1:
        prev_chapter = await db["chapters"].find_one({
            "project_id": project_id,
            "chapter_number": current_chapter - 1,
        })
        if prev_chapter:
            prev_summary = prev_chapter.get("summary", "")

    # 混合检索：语义检索为主，关键词检索补充（去重）
    chapter_outline = state.get("chapter_outline", "")
    seen_chapters: set[int] = set()

    # 主路径：语义检索
    semantic_results = await _semantic_search(project_id, chapter_outline, current_chapter, limit=15)
    for m in semantic_results:
        seen_chapters.add(m.get("chapter_number", 0))

    # 补充路径：关键词检索（补充语义检索未覆盖的章节）
    keywords = _extract_keywords(chapter_outline)
    keyword_results = await search_related_memories(project_id, keywords, limit=10)
    for m in keyword_results:
        ch = m.get("chapter_number", 0)
        if ch not in seen_chapters:
            semantic_results.append(m)
            seen_chapters.add(ch)

    # 按章节号排序后取前 15 条
    semantic_results.sort(key=lambda x: x.get("chapter_number", 0))
    related_memories = semantic_results[:15]
    recalled_memories = _format_memories(related_memories)
    logger.info(f"[写作节点] 混合检索: 语义{sum(1 for m in related_memories if 'distance' in m)}条 + 关键词{len(keyword_results)}条 → 去重后{len(related_memories)}条")

    async def on_token(token: str):
        await publish_stream_token(project_id, token)

    # 构建重写反馈：将审核意见传递给 writer；重写时降低 temperature 减少发散
    audit_feedback = ""
    rewrite_times = state.get("rewrite_times", 0)
    temperature = 0.7
    if rewrite_times > 0:
        audit_opinion = state.get("audit_opinion", "")
        if audit_opinion:
            audit_feedback = f"【第{rewrite_times}次重写】上次审核未通过，审核意见如下：\n{audit_opinion}"
            logger.info(f"[写作节点] 带审核反馈重写: rewrite_times={rewrite_times}")
        # 重写时逐步降低 temperature，越重写越保守
        temperature = max(0.4, 0.7 - rewrite_times * 0.1)
        logger.info(f"[写作节点] 重写 temperature: {temperature}")

    try:
        content = await write_chapter_stream(
            chapter_outline=chapter_outline,
            character_info=config.get("character_info", ""),
            global_summary=config.get("global_summary", ""),
            previous_summary=prev_summary,
            recalled_memories=recalled_memories,
            world_setting=config.get("world_setting", ""),
            style=config.get("style", ""),
            words_per_chapter=config.get("words_per_chapter", 3000),
            chapter_number=current_chapter,
            on_token=on_token,
            audit_feedback=audit_feedback,
            temperature=temperature,
        )

        # 字数超标时精简压缩（最多压缩 3 次），避免直接送审被驳回
        target_words = config.get("words_per_chapter", 3000)
        max_words = int(target_words * 1.3)
        trim_count = 0
        while len(content) > max_words and trim_count < 3:
            trim_count += 1
            excess = len(content) - max_words
            logger.info(
                f"[写作节点] 字数超标 ({len(content)}/{target_words}~{max_words})，"
                f"第 {trim_count} 次精简压缩（超出 {excess} 字）..."
            )
            trim_prompt = await format_prompt(
                "pipeline_trim_user",
                chapter_number=current_chapter,
                content_length=str(len(content)),
                max_words=str(max_words),
                target_words=str(target_words),
                content=content,
            )

            try:
                trimmed_parts = []
                trim_system = await format_prompt("pipeline_trim_system")
                async for token in call_llm_stream(
                    system_prompt=trim_system,
                    user_prompt=trim_prompt,
                    temperature=max(0.3, temperature - 0.2),
                ):
                    trimmed_parts.append(token)
                    await publish_stream_token(project_id, token)
                trimmed_content = _strip_meta("".join(trimmed_parts))
                if trimmed_content and len(trimmed_content) < len(content):
                    content = trimmed_content
                    logger.info(
                        f"[写作节点] 精简完成: {len(content)} 字"
                        f"（压缩率 {(1 - len(content) / (len(content) + excess)) * 100:.0f}%）"
                    )
                    if len(content) <= max_words:
                        logger.info(f"[写作节点] 字数已达标 {max_words}，停止压缩")
                        break
                else:
                    logger.warning("[写作节点] 精简无效（未缩短或为空），停止压缩")
                    break
            except Exception as e:
                logger.error(f"精简压缩失败: {e}", exc_info=True)
                break

        if trim_count > 0:
            logger.info(
                f"[写作节点] 精简完成: 共压缩 {trim_count} 次, "
                f"最终字数 {len(content)}（达标范围 {target_words}~{max_words}）"
            )

        # 字数不足时续写扩展（最多扩展 3 次），续写时控制上限防止超标
        expand_count = 0
        while len(content) < target_words and expand_count < 3:
            expand_count += 1
            shortage = target_words - len(content)
            # 续写目标：补足差额但不超过上限，额外留 10% 余量
            expand_target = min(shortage + int(target_words * 0.1), max_words - len(content))
            logger.info(
                f"[写作节点] 字数不足 ({len(content)}/{target_words})，"
                f"第 {expand_count} 次续写扩展（目标 +{shortage}~{expand_target} 字）..."
            )
            expand_prompt = await format_prompt(
                "pipeline_expand_user",
                chapter_number=current_chapter,
                content_length=str(len(content)),
                target_words=str(target_words),
                max_words=str(max_words),
                shortage=str(shortage),
                expand_target=str(expand_target),
                content=content,
            )

            try:
                extra_parts = []
                expand_system = await format_prompt("pipeline_expand_system")
                async for token in call_llm_stream(
                    system_prompt=expand_system,
                    user_prompt=expand_prompt,
                    temperature=max(0.4, temperature - 0.1),
                ):
                    extra_parts.append(token)
                    await publish_stream_token(project_id, token)
                extra_content = _strip_meta("".join(extra_parts))
                if extra_content:
                    content = content + "\n\n" + extra_content
                    logger.info(
                        f"[写作节点] 续写完成: +{len(extra_content)}字, "
                        f"总计 {len(content)} 字"
                    )
                    # 已达上限则停止扩展，避免超标
                    if len(content) >= max_words:
                        logger.info(f"[写作节点] 已达字数上限 {max_words}，停止扩展")
                        break
                else:
                    logger.warning("[写作节点] 续写内容为空，停止扩展")
                    break
            except Exception as e:
                logger.error(f"续写扩展失败: {e}", exc_info=True)
                break

        if expand_count > 0:
            logger.info(
                f"[写作节点] 扩展完成: 共续写 {expand_count} 次, "
                f"最终字数 {len(content)}（达标范围 {target_words}~{max_words}）"
            )
    finally:
        await publish_stream_done(project_id)

    # 持久化章节内容到 MongoDB
    db = await get_mongodb()
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    chapter_number = state["current_chapter"]

    chapter_title = state.get("chapter_title", f"第{chapter_number}章")

    existing = await db["chapters"].find_one({
        "project_id": project_id,
        "chapter_number": chapter_number,
    })
    if existing:
        await db["chapters"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "title": chapter_title,
                "content": content,
                "word_count": len(content),
                "status": "writing",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    else:
        volume = (chapter_number - 1) // 10 + 1
        await db["chapters"].insert_one({
            "project_id": project_id,
            "volume_number": volume,
            "chapter_number": chapter_number,
            "title": chapter_title,
            "outline": state.get("chapter_outline", ""),
            "content": content,
            "summary": "",
            "word_count": len(content),
            "status": "writing",
            "rewrite_count": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

    logger.info(f"[写作节点] 创作完成: chapter={current_chapter}, word_count={len(content)}")
    return {"chapter_content": content, "step": "written"}


async def node_summarizer(state: NovelState) -> dict:
    """摘要节点：生成章节摘要、标题、结构化数据（不入库，审核通过后由 advance 节点统一入库）"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    content = state.get("chapter_content", "")
    logger.info(f"[摘要节点] 开始生成摘要: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    pause_check = await _check_pause(project_id)
    if pause_check:
        return pause_check
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    total_chapters = project["chapter_count"] if project else 1
    progress_pct = round((current_chapter - 1) / total_chapters * 100, 1)

    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": total_chapters,
        "progress": progress_pct,
        "status": "writing",
        "chapter_status": "summarizing",
        "log": f"第{current_chapter}章生成摘要中...",
    })

    summary_result = None
    try:
        summary_result = await generate_summary(content, current_chapter)
        chapter_summary = summary_result["summary"]
    except Exception as e:
        logger.error(f"摘要生成失败: {e}")
        chapter_summary = ""
        summary_result = {"summary": "", "key_events": [], "character_changes": [], "foreshadowing": []}

    # 更新全局滚动摘要（立刻写 Redis，供下一章 dispatch 使用）
    try:
        current_global = await get_summary(project_id)
        new_global = await update_global_summary(
            current_global, chapter_summary, current_chapter,
        )
        await save_summary(project_id, new_global)
    except Exception as e:
        logger.error(f"全局摘要更新失败: {e}")
        new_global = state.get("global_scroll_summary", "")

    # 自动生成章节标题（仅生成，不写入 DB）
    import re as _re
    _generic_title = _re.compile(r"^第[\d零一二三四五六七八九十百千]+章$")
    chapter_title = state.get("chapter_title", "")
    if not chapter_title or _generic_title.match(chapter_title.strip()):
        try:
            new_title = await generate_chapter_title(content, current_chapter)
            if new_title:
                chapter_title = new_title
                logger.info(f"[摘要节点] 自动生成章节标题: chapter={current_chapter}, title={new_title}")
        except Exception:
            logger.warning(f"章节标题生成失败（不影响创作流程）", exc_info=True)

    # 提取结构化摘要数据（暂不持久化）
    key_events = summary_result.get("key_events", [])
    character_changes = summary_result.get("character_changes", [])
    foreshadowing = summary_result.get("foreshadowing", [])

    logger.info(f"[摘要节点] 摘要生成完成: chapter={current_chapter}")
    return {
        "chapter_title": chapter_title,
        "chapter_summary": chapter_summary,
        "global_scroll_summary": new_global,
        "summary_key_events": key_events,
        "summary_character_changes": character_changes,
        "summary_foreshadowing": foreshadowing,
        "step": "summarized",
    }


async def node_auditor(state: NovelState) -> dict:
    """剧情审核节点：大纲贴合度、人设一致性、文笔质量"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    config = state["user_config"]
    logger.info(f"[审核节点] 开始剧情审核: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    pause_check = await _check_pause(project_id)
    if pause_check:
        return pause_check
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    total_chapters = project["chapter_count"] if project else 1
    progress_pct = round((current_chapter - 1) / total_chapters * 100, 1)

    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": total_chapters,
        "progress": progress_pct,
        "status": "writing",
        "chapter_status": "auditing",
        "log": f"第{current_chapter}章剧情审核中...",
    })

    audit_result = await audit_chapter(
        chapter_content=state.get("chapter_content", ""),
        chapter_outline=state.get("chapter_outline", ""),
        character_info=config.get("character_info", ""),
        global_summary=config.get("global_summary", ""),
    )

    # 持久化审核记录
    db = await get_mongodb()
    chapter = await db["chapters"].find_one({
        "project_id": project_id,
        "chapter_number": current_chapter,
    })
    if chapter:
        await db["audit_records"].update_one(
            {
                "chapter_id": str(chapter["_id"]),
                "audit_type": "plot_audit",
            },
            {"$set": {
                "project_id": project_id,
                "result": audit_result["result"],
                "score": audit_result["score"],
                "opinion": audit_result["opinion"],
                "outline_issues": audit_result.get("outline_issues", []),
                "character_issues": audit_result.get("character_issues", []),
                "coherence_issues": audit_result.get("coherence_issues", []),
                "repetition_issues": audit_result.get("repetition_issues", []),
                "writing_quality_issues": audit_result.get("writing_quality_issues", []),
                "compliance_issues": audit_result.get("compliance_issues", []),
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

    # 构建对 writer 有用的反馈摘要
    feedback_parts = []
    outline_issues = audit_result.get("outline_issues", [])
    character_issues = audit_result.get("character_issues", [])
    coherence_issues = audit_result.get("coherence_issues", [])
    repetition_issues = audit_result.get("repetition_issues", [])
    writing_quality_issues = audit_result.get("writing_quality_issues", [])
    compliance_issues = audit_result.get("compliance_issues", [])

    # 字数检查：不在达标范围内则覆写审核结果为不通过
    content = state.get("chapter_content", "")
    target_words = config.get("words_per_chapter", 2000)
    word_count = len(content)
    min_words = target_words
    max_words = int(target_words * 1.3)
    if word_count < min_words or word_count > max_words:
        audit_result["result"] = "fail"
        audit_result["score"] = min(audit_result.get("score", 50), 40)
        if word_count < min_words:
            feedback_parts.append(
                f"字数不足：当前{word_count}字，要求{min_words}~{max_words}字。"
                f"请在重写时扩充内容，确保每个情节点都有充分展开"
            )
        else:
            prefix = "存在重复水剧情且" if repetition_issues else ""
            feedback_parts.append(
                f"{prefix}字数超标：当前{word_count}字，要求{min_words}~{max_words}字。"
                f"请在重写时精简冗余内容，保持情节紧凑"
            )

    if outline_issues:
        feedback_parts.append("细纲遗漏：" + "；".join(outline_issues))
    if character_issues:
        feedback_parts.append("人设问题：" + "；".join(character_issues))
    if coherence_issues:
        feedback_parts.append("剧情连贯性问题：" + "；".join(coherence_issues))
    if repetition_issues:
        feedback_parts.append("内容重复：" + "；".join(repetition_issues))
    if writing_quality_issues:
        feedback_parts.append("文笔质量问题：" + "；".join(writing_quality_issues))
    if compliance_issues:
        feedback_parts.append("合规问题：" + "；".join(compliance_issues))
    if not feedback_parts:
        feedback_parts.append(audit_result["opinion"])
    audit_feedback = "\n".join(feedback_parts)

    logger.info(f"[审核节点] 审核完成: chapter={current_chapter}, result={audit_result['result']}, score={audit_result['score']}")
    return {
        "audit_result": audit_result["result"] == "pass",
        "audit_opinion": audit_feedback,
        "step": "audited",
    }


async def node_copyrighter(state: NovelState) -> dict:
    """版权合规节点：FAISS向量查重、原创度打分"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    config = state["user_config"]
    logger.info(f"[版权节点] 开始版权校验: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    pause_check = await _check_pause(project_id)
    if pause_check:
        return pause_check
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    total_chapters = project["chapter_count"] if project else 1
    progress_pct = round((current_chapter - 1) / total_chapters * 100, 1)

    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": total_chapters,
        "progress": progress_pct,
        "status": "writing",
        "chapter_status": "copyright_checking",
        "log": f"第{current_chapter}章版权校验中...",
    })

    copyright_result = await check_copyright(
        chapter_content=state.get("chapter_content", ""),
        project_id=project_id,
        threshold=config.get("copyright_threshold", 0.2),
    )

    # 持久化版权报告
    db = await get_mongodb()
    chapter = await db["chapters"].find_one({
        "project_id": project_id,
        "chapter_number": current_chapter,
    })
    if chapter:
        await db["copyright_records"].update_one(
            {
                "chapter_id": str(chapter["_id"]),
            },
            {"$set": {
                "project_id": project_id,
                "originality_score": copyright_result["originality_score"],
                "max_similarity": copyright_result["max_similarity"],
                "passed": copyright_result["passed"],
                "similar_entries": copyright_result.get("similar_entries", []),
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

    logger.info(f"[版权节点] 版权校验完成: chapter={current_chapter}, score={copyright_result['originality_score']}, passed={copyright_result['passed']}")
    return {
        "copyright_score": copyright_result["originality_score"],
        "copyright_similarity": copyright_result["max_similarity"],
        "copyright_pass": copyright_result["passed"],
        "copyright_opinion": copyright_result["opinion"],
        "step": "copyright_checked",
    }


async def node_advance_chapter(state: NovelState) -> dict:
    """推进到下一章：审核全部通过，统一持久化标题/摘要/记忆/embedding，标记完成"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    chapter_content = state.get("chapter_content", "")
    chapter_summary = state.get("chapter_summary", "")
    chapter_title = state.get("chapter_title", "")
    key_events = state.get("summary_key_events", [])
    character_changes = state.get("summary_character_changes", [])
    foreshadowing = state.get("summary_foreshadowing", [])
    logger.info(f"[推进节点] 审核通过，开始持久化: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    total_chapters = project["chapter_count"] if project else 1
    progress_pct = round(current_chapter / total_chapters * 100, 1)

    # 持久化章节：标题、摘要、状态
    chapter_updates: dict = {
        "status": "completed",
        "title": chapter_title,
        "summary": chapter_summary,
        "word_count": len(chapter_content),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["chapters"].update_one(
        {"project_id": project_id, "chapter_number": current_chapter},
        {"$set": chapter_updates},
    )
    logger.info(f"[推进节点] 章节已持久化: chapter={current_chapter}, title={chapter_title}")

    # 持久化章节记忆（用于后续记忆检索）
    try:
        await save_chapter_memory(
            project_id, current_chapter, chapter_summary,
            key_events, character_changes, foreshadowing,
        )
    except Exception:
        logger.warning(f"章节记忆保存失败（不影响创作流程）", exc_info=True)

    # 生成 embedding 并存入 FAISS 语义检索库
    try:
        _vector_service.remove_vectors_by_chapter(project_id, current_chapter)
        embedding_text = build_chapter_embedding_text(
            current_chapter, chapter_summary,
            key_events, character_changes, foreshadowing,
        )
        vector = embed_text(embedding_text)
        _vector_service.create_project_index(project_id)
        _vector_service.add_vectors(
            project_id,
            [vector],
            [{
                "chapter_number": current_chapter,
                "summary": chapter_summary,
                "key_events": key_events,
                "character_changes": character_changes,
                "foreshadowing": foreshadowing,
            }],
        )
        logger.info(f"[推进节点] embedding 已入库: chapter={current_chapter}")
    except Exception:
        logger.warning(f"embedding 入库失败（不影响创作流程）", exc_info=True)

    # 更新项目进度
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "current_chapter": current_chapter,
            "rewrite_count": 0,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": total_chapters,
        "progress": progress_pct,
        "status": "writing",
        "chapter_status": "completed",
        "log": f"第{current_chapter}章创作完成",
    })

    next_chapter = current_chapter + 1
    logger.info(f"第{current_chapter}章创作完成，下一章: {next_chapter}")

    return {
        "current_chapter": next_chapter,
        "rewrite_times": 0,
        "chapter_title": "",
        "chapter_content": "",
        "chapter_summary": "",
        "summary_key_events": [],
        "summary_character_changes": [],
        "summary_foreshadowing": [],
        "audit_result": False,
        "audit_opinion": "",
        "copyright_pass": False,
        "copyright_opinion": "",
        "copyright_score": 0.0,
        "copyright_similarity": 0.0,
        "step": "dispatch",
    }


async def node_rewrite(state: NovelState) -> dict:
    """重写节点：清空内容，重新进入写作流程"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    rewrite_times = state.get("rewrite_times", 0) + 1
    logger.info(f"[重写节点] 开始重写: project_id={project_id}, chapter={current_chapter}, rewrite_times={rewrite_times}")

    db = await get_mongodb()
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"rewrite_count": rewrite_times}},
    )
    await db["chapters"].update_one(
        {"project_id": project_id, "chapter_number": current_chapter},
        {"$set": {"status": "rewriting", "updated_at": datetime.now(timezone.utc)}},
    )

    logger.info(f"第{current_chapter}章审核未通过，第{rewrite_times}次重写")

    return {
        "rewrite_times": rewrite_times,
        "chapter_content": "",
        "chapter_summary": "",
        "summary_key_events": [],
        "summary_character_changes": [],
        "summary_foreshadowing": [],
        "audit_result": False,
        "audit_opinion": "",
        "copyright_pass": False,
        "copyright_opinion": "",
        "copyright_score": 0.0,
        "copyright_similarity": 0.0,
        "step": "rewriting",
    }


async def node_manual_review(state: NovelState) -> dict:
    """标记人工介入，跳到下一章"""
    project_id = state["project_id"]
    current_chapter = state["current_chapter"]
    logger.info(f"[人工介入节点] 标记人工介入: project_id={project_id}, chapter={current_chapter}")

    db = await get_mongodb()
    await db["chapters"].update_one(
        {"project_id": project_id, "chapter_number": current_chapter},
        {"$set": {"status": "manual_review", "updated_at": datetime.now(timezone.utc)}},
    )
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"rewrite_count": 0}},
    )

    logger.warning(f"第{current_chapter}章重写次数超限，标记人工介入")

    next_chapter = current_chapter + 1
    return {
        "current_chapter": next_chapter,
        "rewrite_times": 0,
        "chapter_content": "",
        "chapter_summary": "",
        "summary_key_events": [],
        "summary_character_changes": [],
        "summary_foreshadowing": [],
        "step": "dispatch",
    }


# ── 条件路由 ──────────────────────────────────────────────


def route_after_dispatch(state: NovelState) -> Literal["node_writer", "__end__"]:
    """调度后路由：暂停/错误 → END，就绪 → 写作"""
    if state.get("step") in ("paused", "error"):
        return END
    if state.get("step") == "manual_review":
        return END
    return "node_writer"


def _route_next_or_end(state: NovelState) -> Literal["__end__", "__continue__"]:
    """通用路由：如果已暂停/出错则结束，否则继续"""
    if state.get("step") in ("paused", "error"):
        return END
    return "__continue__"


def route_after_copyright(state: NovelState):
    """版权校验后路由：通过 → 下一章，不通过 → 重写或人工介入"""
    if state.get("step") in ("paused", "error"):
        return END
    audit_pass = state.get("audit_result", False)
    copyright_pass = state.get("copyright_pass", False)

    # 字数检查：必须在 [target_words, target_words*1.3] 范围内
    content = state.get("chapter_content", "")
    target_words = state.get("user_config", {}).get("words_per_chapter", 2000)
    max_words = int(target_words * 1.3)
    word_count_ok = target_words <= len(content) <= max_words

    if audit_pass and copyright_pass and word_count_ok:
        return "node_advance_chapter"

    rewrite_times = state.get("rewrite_times", 0)
    if rewrite_times >= MAX_REWRITE_TIMES:
        return "node_manual_review"

    return "node_rewrite"


# ── 图构建 ──────────────────────────────────────────────


def _build_chapter_graph() -> StateGraph:
    """构建单章创作 LangGraph StateGraph"""
    graph = StateGraph(NovelState)

    # 添加节点
    graph.add_node("node_dispatch", node_dispatch)
    graph.add_node("node_writer", node_writer)
    graph.add_node("node_summarizer", node_summarizer)
    graph.add_node("node_auditor", node_auditor)
    graph.add_node("node_copyrighter", node_copyrighter)
    graph.add_node("node_advance_chapter", node_advance_chapter)
    graph.add_node("node_rewrite", node_rewrite)
    graph.add_node("node_manual_review", node_manual_review)

    # 入口
    graph.set_entry_point("node_dispatch")

    # 调度 → 写作 / 结束
    graph.add_conditional_edges(
        "node_dispatch",
        route_after_dispatch,
        {"node_writer": "node_writer", END: END},
    )

    # 写作 → 摘要 → 审核 → 版权（每步都检查是否已暂停）
    graph.add_conditional_edges(
        "node_writer",
        _route_next_or_end,
        {"__continue__": "node_summarizer", END: END},
    )
    graph.add_conditional_edges(
        "node_summarizer",
        _route_next_or_end,
        {"__continue__": "node_auditor", END: END},
    )
    graph.add_conditional_edges(
        "node_auditor",
        _route_next_or_end,
        {"__continue__": "node_copyrighter", END: END},
    )

    # 版权 → 下一章 / 重写 / 人工介入 / 暂停结束
    graph.add_conditional_edges(
        "node_copyrighter",
        route_after_copyright,
        {
            "node_advance_chapter": "node_advance_chapter",
            "node_rewrite": "node_rewrite",
            "node_manual_review": "node_manual_review",
            END: END,
        },
    )

    # 重写 → 重新写作（跳过调度，直接写）
    graph.add_edge("node_rewrite", "node_writer")

    # 推进章节 → 结束（外层循环决定是否继续）
    graph.add_edge("node_advance_chapter", END)

    # 人工介入 → 结束（外层循环决定是否继续）
    graph.add_edge("node_manual_review", END)

    return graph


def compile_chapter_graph():
    """编译单章创作图，返回可调用的 compiled graph"""
    graph = _build_chapter_graph()
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# ── 主入口 ──────────────────────────────────────────────


async def run_pipeline(project_id: str):
    """运行 6Agent LangGraph 创作流水线"""
    db = await get_mongodb()
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})

    if not project:
        logger.error(f"项目不存在: {project_id}")
        return

    total_chapters = project["chapter_count"]
    if total_chapters <= 0:
        logger.error(f"项目章节数为0，无法启动流水线: {project_id}")
        await db["novel_projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
        )
        await save_progress(project_id, {
            "current_chapter": 0,
            "total_chapters": 0,
            "progress": 0,
            "status": "paused",
            "chapter_status": "",
            "log": "请先设置章节数量",
        })
        return

    start_chapter = project.get("current_chapter", 0) + 1
    global_summary = await get_summary(project_id)

    # 初始化 FAISS 语义检索索引
    _vector_service.create_project_index(project_id)

    compiled_graph = compile_chapter_graph()

    current_chapter = start_chapter
    while current_chapter <= total_chapters:
        # 检查暂停
        project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
        if project["status"] != "writing":
            logger.info(f"创作已暂停: {project_id}")
            break

        # 检查是否存在卡在非终态的章节（上次中断导致），重置后可安全重写
        stale_chapter = await db["chapters"].find_one({
            "project_id": project_id,
            "chapter_number": current_chapter,
        })
        if stale_chapter and stale_chapter["status"] not in ("completed",):
            logger.warning(
                f"发现卡住的章节: chapter={current_chapter}, status={stale_chapter['status']}，"
                f"重置后重新生成"
            )
            # 章节内容存在则保留（可能只需要补跑后续节点），但稳妥做法是重写
            await db["chapters"].update_one(
                {"_id": stale_chapter["_id"]},
                {"$set": {"status": "draft"}},
            )

        # 初始化本章状态
        initial_state: NovelState = {
            "user_config": {},
            "project_id": project_id,
            "full_outline": {},
            "chapter_outline": "",
            "chapter_title": f"第{current_chapter}章",
            "current_volume": (current_chapter - 1) // 10 + 1,
            "current_chapter": current_chapter,
            "chapter_content": "",
            "chapter_summary": "",
            "summary_key_events": [],
            "summary_character_changes": [],
            "summary_foreshadowing": [],
            "global_scroll_summary": global_summary,
            "character_status": {},
            "audit_result": False,
            "audit_opinion": "",
            "copyright_score": 0.0,
            "copyright_similarity": 0.0,
            "copyright_opinion": "",
            "copyright_pass": False,
            "step": "dispatch",
            "error_info": "",
            "rewrite_times": 0,
        }

        # 执行单章图
        config = {"configurable": {"thread_id": f"{project_id}_{current_chapter}"}}
        final_state = await compiled_graph.ainvoke(initial_state, config=config)

        # 检查结果
        step = final_state.get("step", "")
        if step in ("paused", "error"):
            logger.info(f"流水线停止: {step} - {final_state.get('error_info', '')}")
            break

        # 更新全局摘要供下一章使用
        global_summary = final_state.get("global_scroll_summary", global_summary)

        # 推进章节号（node_advance_chapter / node_manual_review 已 +1）
        current_chapter = final_state.get("current_chapter", current_chapter + 1)

    # 所有章节完成
    if current_chapter > total_chapters:
        await db["novel_projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc)}},
        )
        await save_progress(project_id, {
            "current_chapter": total_chapters,
            "total_chapters": total_chapters,
            "progress": 100,
            "status": "completed",
            "chapter_status": "",
            "log": "全书创作完成！",
        })
        logger.info(f"全书创作完成: {project_id}")
