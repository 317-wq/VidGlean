"""内置 Markdown 模板与变量校验。"""

from __future__ import annotations

import re
from typing import Any

VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

ALLOWED_VARIABLES = {
    "video_title",
    "author",
    "platform",
    "url",
    "duration",
    "date",
    "content_type",
    "transcript",
    "extra",
    "depth",
}

BUILTIN_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "builtin-general",
        "name": "通用知识文档",
        "description": "适合大多数内容：一句话概述、内容大纲、核心内容、关键结论。",
        "content": """# {{video_title}}

## 一句话概述
（用一句话说清这个视频讲了什么、值不值得看）

## 内容大纲
- 按主题列出 3 到 5 个板块（不是按视频播放顺序）

## 核心内容
每个板块用「**板块名**」起一段，讲清它是什么、有什么用、有什么坑；
同一主题的信息合并到一段，重要的概念、数字、结论必须保留

## 关键结论
- 3 到 5 条可以带走的结论

## 关键名词
- 视频里出现的术语、工具、人名，简要解释""",
    },
    {
        "id": "builtin-tech",
        "name": "技术教程",
        "description": "适合编程、工具、课程类内容：原理、步骤、代码、坑点。",
        "content": """# {{video_title}}

## 一句话概述
（这个教程解决了什么问题）

## 涉及的技术栈
- 语言、框架、工具、版本

## 原理与背景
解释为什么需要它、它解决了什么问题

## 实现步骤
1. 按操作顺序给出步骤，关键处附代码块

## 代码与命令
```语言
// 只保留真正有价值的代码，不要臆造
```

## 常见坑与注意事项
- 视频里提到的坑、报错、兼容性问题

## 面试/复习要点
- 可以被追问的点""",
    },
    {
        "id": "builtin-opinion",
        "name": "观点与讨论",
        "description": "适合访谈、评论、观点类内容：论点、论据、结论。",
        "content": """# {{video_title}}

## 一句话概述
（核心主张是什么）

## 核心观点
1. **观点**：论据与例子

## 分歧与反驳
- 视频中提到的不同意见、被反驳的说法

## 结论
- 作者的最终结论与前提条件

## 值得追问的问题
- 2 到 3 个视频没有回答但值得思考的问题""",
    },
]

BUILTIN_CONTENT = {item["id"]: item["content"] for item in BUILTIN_TEMPLATES}


def validate(text: str) -> list[str]:
    """返回错误列表；空列表表示通过。"""
    errors: list[str] = []
    if not text.strip():
        errors.append("模板内容为空")
    unknown = {name for name in VARIABLE_RE.findall(text) if name not in ALLOWED_VARIABLES}
    if unknown:
        errors.append("存在未知变量：" + "、".join(sorted(unknown)))
    return errors


def render(text: str, values: dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name, "")
        return str(value)

    return VARIABLE_RE.sub(_replace, text)


def template_text(row: dict[str, Any]) -> str:
    """从数据库行取模板正文：内置模板用代码里的内容，自定义模板读文件。"""
    if row.get("kind") == "builtin":
        return BUILTIN_CONTENT.get(row["id"], "")
    path = row.get("path") or ""
    if not path:
        return ""
    try:
        from pathlib import Path

        return Path(path).read_text("utf-8")
    except OSError:
        return ""
