"""Prompt 模板数据模型 —— MongoDB prompt_templates 集合文档结构

每个文档存储用户对某个 prompt_key 的自定义覆盖。
未覆盖的 prompt 使用 default_prompts.py 中的默认值。
"""

from datetime import datetime, timezone
from typing import Any


class PromptTemplate:
    """MongoDB prompt_templates 文档结构"""

    collection = "prompt_templates"

    @staticmethod
    def new_doc(
        prompt_key: str,
        user_id: str,
        name: str,
        description: str,
        agent_type: str,
        prompt_type: str,
        template_content: str,
        variables: list[str],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "prompt_key": prompt_key,
            "user_id": user_id,
            "name": name,
            "description": description,
            "agent_type": agent_type,
            "prompt_type": prompt_type,
            "template_content": template_content,
            "variables": variables,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
