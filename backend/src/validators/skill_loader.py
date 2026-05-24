"""Skill 文件加载器 — 解析 YAML frontmatter + Markdown body 的 Skill 文件。

Skill 文件格式:
---
name: skill-name
description: 一句话描述
version: 1.0.0
tags: [validation, quality-gate]
check_method: programmatic | llm | hybrid
failure: block | warn
priority: 1-10
---

# Skill 标题
## 检查项
### 1. 检查项名称
- 方法: ...
- 阈值: ...
"""

import os
import re
from dataclasses import dataclass, field

import yaml


@dataclass
class CheckItem:
    name: str
    method: str  # "programmatic" | "llm" | "hybrid"
    threshold_desc: str
    failure_action: str  # "block" | "warn"
    raw_content: str  # 原始 Markdown 内容


@dataclass
class SkillSpec:
    name: str
    description: str
    version: str
    tags: list[str] = field(default_factory=list)
    check_method: str = "hybrid"
    failure: str = "block"
    priority: int = 10
    body: str = ""
    check_items: list[CheckItem] = field(default_factory=list)
    file_path: str = ""

    @property
    def is_programmatic(self) -> bool:
        return self.check_method in ("programmatic", "hybrid")

    @property
    def needs_llm(self) -> bool:
        return self.check_method in ("llm", "hybrid")

    @property
    def is_blocking(self) -> bool:
        return self.failure == "block"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter 和 Markdown body"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, match.group(2).strip()


def _extract_check_items(body: str) -> list[CheckItem]:
    """从 Markdown body 中提取检查项"""
    items: list[CheckItem] = []
    # 匹配 "### N. 检查项名称" 模式
    pattern = re.compile(r"###\s+\d+\.\s+(.+?)\n(.*?)(?=###\s+\d+\.|$)", re.DOTALL)
    for match in pattern.finditer(body):
        name = match.group(1).strip()
        content = match.group(2).strip()

        method = "programmatic"
        if "LLM" in content or "llm" in content:
            if "程序化" in content or "关键词" in content or "正则" in content:
                method = "hybrid"
            else:
                method = "llm"

        failure = "warn" if "warn" in content.lower() else "block"

        items.append(CheckItem(
            name=name,
            method=method,
            threshold_desc=_extract_threshold(content),
            failure_action=failure,
            raw_content=content,
        ))
    return items


def _extract_threshold(content: str) -> str:
    """从检查项内容中提取阈值描述"""
    patterns = [
        r"阈值[：:]\s*(.+?)(?:\n|$)",
        r"失败动作[：:]\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.group(1).strip()
    return ""


def load_skill(file_path: str) -> SkillSpec:
    """加载单个 Skill 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    metadata, body = _parse_frontmatter(content)
    check_items = _extract_check_items(body)

    return SkillSpec(
        name=metadata.get("name", os.path.splitext(os.path.basename(file_path))[0]),
        description=metadata.get("description", ""),
        version=metadata.get("version", "1.0.0"),
        tags=metadata.get("tags", []),
        check_method=metadata.get("check_method", "hybrid"),
        failure=metadata.get("failure", "block"),
        priority=metadata.get("priority", 10),
        body=body,
        check_items=check_items,
        file_path=file_path,
    )


def load_all_skills(skills_dir: str) -> list[SkillSpec]:
    """加载目录下所有 Skill 文件，按 priority 排序"""
    skills: list[SkillSpec] = []
    if not os.path.isdir(skills_dir):
        return skills

    for filename in sorted(os.listdir(skills_dir)):
        if filename.endswith(".md"):
            filepath = os.path.join(skills_dir, filename)
            try:
                skill = load_skill(filepath)
                skills.append(skill)
            except Exception:
                continue

    skills.sort(key=lambda s: s.priority)
    return skills
