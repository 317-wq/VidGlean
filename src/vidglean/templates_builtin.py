"""内置 Markdown 模板与变量校验。

模板只定义文档结构，内容由模型根据视频实际内容生成。文档开头的视频信息块由
程序统一添加，所以模板从一级标题开始，不重复写作者/链接等表头。
"""

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
        "description": "适合大多数知识类、信息类和综合类视频。",
        "content": """# {{video_title}}

## 一句话概述

用简洁的语言说明视频的主要内容和核心价值。

## 内容概览

按照主题组织视频的主要内容，帮助读者快速了解整体结构。

## 核心内容

围绕重要主题展开，保留关键知识、观点、案例和必要细节。

## 关键结论

提炼最值得记住的结论和信息。

## 补充信息

根据实际内容选择性整理重要术语、数据、人物或相关背景。""",
    },
    {
        "id": "builtin-tech",
        "name": "技术教程",
        "description": "适合编程教学、技术分享、软件工具使用、开发实践和技术课程。",
        "content": """# {{video_title}}

## 一句话概述

说明教程解决的问题、最终实现的效果。

## 技术栈与环境

整理涉及的语言、框架、工具、版本和运行环境。

## 原理与背景

解释相关技术的作用、设计思路和关键原理。

## 实现过程

按照实际操作顺序整理实现步骤，说明每一步的目的和关键细节。

## 核心代码与命令

保留视频中有价值的代码、配置和命令，必要时补充简要解释。

## 问题与注意事项

整理视频中出现的报错、常见问题、兼容性限制和容易出错的地方。

## 总结

归纳最终实现效果、核心知识和需要掌握的内容。""",
    },
    {
        "id": "builtin-opinion",
        "name": "观点与讨论",
        "description": "适合观点表达、时事评论、行业分析、技术讨论和辩论。",
        "content": """# {{video_title}}

## 一句话概述

概括视频讨论的主题和核心主张。

## 核心观点

逐条整理作者表达的主要观点，并说明对应的理由。

## 论据与案例

整理支撑观点的数据、事实、案例和推理过程。

## 不同观点与争议

整理视频中出现的不同立场、反驳意见和争议焦点。

## 最终结论

归纳作者最终表达的判断，以及成立所依赖的前提条件。

## 值得进一步思考的问题

整理视频中尚未充分讨论但具有思考价值的问题。""",
    },
    {
        "id": "builtin-science",
        "name": "知识科普",
        "description": "适合科学原理、自然现象、历史知识、社会知识和专业概念科普。",
        "content": """# {{video_title}}

## 一句话概述

说明视频解释的现象、知识或核心问题。

## 核心概念

解释重要概念、定义及其意义。

## 原理与机制

按照逻辑或因果关系解释相关现象是如何产生的。

## 典型案例

整理视频中用于解释原理的实际案例或具体例子。

## 常见误解

说明视频中明确纠正的错误认识。

## 适用范围与限制

说明相关结论成立的条件、适用范围和局限性。""",
    },
    {
        "id": "builtin-experience",
        "name": "经验分享",
        "description": "适合个人经历、项目复盘、职业经验、学习心得和避坑分享。",
        "content": """# {{video_title}}

## 一句话概述

总结分享者的主要经历和最终获得的经验。

## 背景与前提

说明分享者所处的场景、面临的问题和客观条件。

## 核心经验

提炼分享者总结出的重要经验和方法。

## 实践方法

整理可以实际执行的操作、步骤和建议。

## 效果与反思

总结实际效果、遇到的问题、付出的成本和经验教训。

## 适用条件

说明这些经验适用于什么情况，以及可能不适用的场景。""",
    },
    {
        "id": "builtin-life",
        "name": "生活技巧",
        "description": "适合生活教程、家居技巧、烹饪方法、日常操作和实用技能。",
        "content": """# {{video_title}}

## 一句话概述

说明这项技巧能够解决什么实际问题。

## 准备事项

整理所需材料、工具、环境和其他前置条件。

## 操作步骤

按照实际操作顺序整理具体步骤。

## 关键技巧

说明影响操作效果的重要细节。

## 常见问题

整理可能出现的问题及视频中提供的解决办法。

## 注意事项

根据实际内容整理安全、卫生、保存等相关提醒。""",
    },
    {
        "id": "builtin-fun",
        "name": "娱乐内容",
        "description": "适合游戏实况、搞笑视频、生活记录、娱乐剪辑和轻量内容。",
        "content": """# {{video_title}}

## 内容简介

用简短的语言介绍视频主要讲了什么。

## 内容梗概

按照视频中的重要片段或事件整理主要内容。

## 精彩片段

提取有趣、特别或值得回看的内容。

## 主要亮点

总结视频最有趣、最有特色或最值得关注的地方。""",
    },
    {
        "id": "builtin-review",
        "name": "产品评测",
        "description": "适合产品开箱、设备评测、软件体验、产品对比和购买建议。",
        "content": """# {{video_title}}

## 一句话概述

说明评测对象和视频给出的主要结论。

## 产品基本信息

整理产品名称、型号、版本、定位和视频中提到的价格等信息。

## 核心功能与表现

整理产品的主要功能、实际体验和测试结果。

## 优点

归纳视频中实际验证或明确提到的优势。

## 缺点与限制

归纳视频中发现的问题、使用限制和不足。

## 对比分析

如果视频包含竞品对比，整理关键差异和对比结果。

## 总结与建议

总结产品适合的人群、使用场景以及视频给出的购买建议。""",
    },
    {
        "id": "builtin-interview",
        "name": "访谈对话",
        "description": "适合人物访谈、播客、圆桌讨论和多人对话。",
        "content": """# {{video_title}}

## 一句话概述

说明参与者、讨论主题和最有价值的信息。

## 出场人物

整理主要参与者的姓名、身份和相关背景。

## 主要议题

按照讨论主题整理各参与者表达的观点和理由。

## 关键观点与判断

提炼对话中重要的判断、预测、经验和结论，并标明发言者。

## 值得记录的表达

摘录具有代表性的原话，尽可能保留原意并标明发言者。

## 尚未解决的问题

整理对话中提出但没有充分讨论的问题。""",
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
