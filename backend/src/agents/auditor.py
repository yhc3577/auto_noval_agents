"""剧情审核Agent：大纲贴合度、人设一致性、文笔质量校验"""

import json
import re

from ..core.llm import call_llm
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _parse_audit_response(response: str) -> dict:
    """从 LLM 响应中解析结构化审核结果"""
    # 尝试提取 JSON 块
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    json_text = match.group(1) if match else response

    # 修复常见 JSON 格式问题
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
        }
    except (json.JSONDecodeError, ValueError):
        pass

    # fallback：从纯文本中启发式提取
    lower = response.lower()
    passed = "pass" in lower and "fail" not in lower
    return {
        "result": "pass" if passed else "fail",
        "score": 80 if passed else 50,
        "opinion": response,
        "outline_issues": [],
        "character_issues": [],
    }


async def audit_chapter(
    chapter_content: str,
    chapter_outline: str,
    character_info: str,
    global_summary: str,
) -> dict:
    """剧情质量审核"""
    system_prompt = """你是一位专业的小说审核编辑。对提交的章节进行严格质量审核。

## 审核维度

1. **大纲贴合度**（最重要）：逐一检查细纲中的每个情节点，确认正文中是否都有体现。遗漏任何一个情节点即为不通过。
2. **人设一致性**：人物行为、对话、决策是否符合角色设定。
3. **剧情连贯性**：是否与前文摘要矛盾，是否有逻辑漏洞。
4. **文笔质量**：语句是否流畅，节奏是否合理，有无灌水。
5. **内容合规**：是否包含敏感、违规内容。

## 输出要求

你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：

```json
{
  "result": "pass 或 fail",
  "score": 0-100 的整数分数,
  "opinion": "总体审核意见",
  "outline_issues": ["列出细纲中未被正文体现的情节点，如果没有则为空数组"],
  "character_issues": ["列出人设不一致的问题，如果没有则为空数组"]
}
```

评分标准：
- 90+分：优秀，完全贴合细纲，人设一致，文笔流畅
- 70-89分：良好，基本贴合细纲但有小瑕疵
- 60-69分：及格，有明显遗漏但主线完整
- 60分以下：不通过，严重偏离细纲或人设崩塌

注意：只要细纲中有任何情节点被遗漏或严重变形，result 必须为 "fail"。"""

    user_prompt = f"""本章细纲：
{chapter_outline}

角色设定：
{character_info}

前文摘要：
{global_summary}

本章正文：
{chapter_content}

请进行严格的质量审核，按照 JSON 格式输出审核结果。"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        return _parse_audit_response(response)
    except Exception as e:
        logger.error(f"剧情审核失败: {e}", exc_info=True)
        return {"result": "fail", "score": 0, "opinion": f"审核异常: {str(e)}", "outline_issues": [], "character_issues": []}
