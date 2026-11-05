"""提示词构建。"""

from __future__ import annotations

from typing import Any

from vidglean.core.models import ContentType, Depth

TYPE_GUIDES = {
    ContentType.TECH: (
        "这是技术教程。重点提取：要解决的问题、涉及的技术栈与版本、原理、操作步骤、"
        "关键代码、踩过的坑。代码必须放进对应语言的代码块，命令行放进 shell 代码块。"
    ),
    ContentType.SCIENCE: "这是知识科普。重点提取：概念定义、背景、因果关系、结论与适用边界。",
    ContentType.EXPERIENCE: "这是经验分享。重点提取：具体做法、判断依据、效果、可复用的建议。",
    ContentType.OPINION: "这是观点讨论。重点提取：核心主张、论据、反方观点、结论成立的前提。",
    ContentType.LIFE: "这是生活技巧。重点提取：可执行的步骤、材料、注意事项，用编号清单表达。",
    ContentType.FUN: "这是娱乐内容。用简短概述和少量要点即可，不要强行展开。",
    ContentType.OTHER: "按内容本身的逻辑组织章节，不要套用固定结构。",
}

DEPTH_GUIDES = {
    Depth.BRIEF: "篇幅控制在 400 字以内，只保留最关键的结论。",
    Depth.STANDARD: "篇幅控制在 800 到 1200 字，覆盖主要内容。",
    Depth.DETAILED: "尽量完整，可以到 2000 字以上，保留推导、例子和细节。",
}

SYSTEM_PROMPT = """你是一个视频知识萃取编辑。用户会给你一段视频字幕（口语化、无标点、可能有识别错误）。
你的任务是把字幕整理成一份可以直接长期保存的 Markdown 知识文档。

要求：
1. 过滤口头禅、寒暄、重复表达和明显与主题无关的内容。
2. 不要编造字幕里没有的事实、数字、代码或引用；不确定的内容宁可不写。
3. 严格输出 Markdown 正文，不要用 ``` 包裹整篇内容。
4. 只使用一级标题和二级标题，不要出现三级以下标题。
5. 第一行必须是文档标题（# 开头）。
6. 不要输出「根据字幕」「视频中提到」这类元叙述，直接给结论。"""


def system_prompt(depth: str, content_type: str) -> str:
    guide = TYPE_GUIDES.get(content_type, TYPE_GUIDES[ContentType.OTHER])
    depth_guide = DEPTH_GUIDES.get(depth, DEPTH_GUIDES[Depth.STANDARD])
    return f"{SYSTEM_PROMPT}\n\n内容类型：{content_type}。{guide}\n篇幅要求：{depth_guide}"


def _extra_block(extra: str) -> str:
    if not extra.strip():
        return ""
    return f"\n## 用户的额外要求\n{extra.strip()}\n"


def summary_user_prompt(
    *,
    meta: dict[str, Any],
    template_text: str,
    transcript: str,
    extra: str,
) -> str:
    return (
        f"## 视频信息\n"
        f"- 标题：{meta.get('title', '')}\n"
        f"- UP 主：{meta.get('author', '')}\n"
        f"- 平台：Bilibili\n"
        f"- 时长：{meta.get('duration_text', '')}\n"
        f"- 类型判断：{meta.get('content_type', '')}\n"
        f"{_extra_block(extra)}\n"
        f"## 输出结构\n请按下面的模板组织章节，可以按内容删减或增加章节，但不要保留模板里的括号说明：\n\n"
        f"{template_text}\n\n"
        f"## 视频字幕\n{transcript}\n"
    )


def chunk_prompt(chunk: str, index: int, total: int) -> str:
    return (
        f"这是长视频字幕的第 {index}/{total} 段。请提炼这一段的要点，保留专有名词、数字、代码、结论，"
        f"用无序列表输出，不要写总结性的开场白。\n\n## 字幕片段\n{chunk}"
    )


def reduce_prompt(*, meta: dict[str, Any], template_text: str, notes: str, extra: str) -> str:
    return (
        f"## 视频信息\n"
        f"- 标题：{meta.get('title', '')}\n"
        f"- UP 主：{meta.get('author', '')}\n"
        f"- 时长：{meta.get('duration_text', '')}\n"
        f"- 类型判断：{meta.get('content_type', '')}\n"
        f"{_extra_block(extra)}\n"
        f"## 输出结构\n请按下面的模板组织章节，可以按内容删减或增加章节，但不要保留模板里的括号说明：\n\n"
        f"{template_text}\n\n"
        f"## 分段要点\n{notes}\n"
    )


def assist_prompt(content: str, instruction: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是 Markdown 文档编辑。根据用户要求修改给定文档，"
                "只输出修改后的完整 Markdown 正文，不要解释，不要用代码块包裹整篇。"
                "用户没有要求修改的部分保持原样。"
            ),
        },
        {
            "role": "user",
            "content": f"## 用户要求\n{instruction}\n\n## 当前文档\n{content}",
        },
    ]


def classify_prompt(title: str, author: str, transcript: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "判断视频内容类型。只输出以下之一，不要输出其它任何文字："
                "技术教程、知识科普、经验分享、观点讨论、生活技巧、娱乐内容、其他。"
            ),
        },
        {"role": "user", "content": f"标题：{title}\nUP主：{author}\n字幕开头：{transcript[:1500]}"},
    ]


def chat_system(document: str, subtitle: str) -> str:
    subtitle_block = subtitle[:4000]
    return (
        "你是这篇视频笔记的专属助手。回答时优先依据下面的 Markdown 文档，"
        "文档没有覆盖的细节可以参考原始字幕，仍然不知道就直接说不知道。\n\n"
        f"## 当前文档\n{document[:8000]}\n\n"
        f"## 原始字幕（节选）\n{subtitle_block}"
    )
