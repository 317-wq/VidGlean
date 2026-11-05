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
    {
        "id": "builtin-science",
        "name": "知识科普",
        "description": "适合原理、现象、历史、自然类内容：概念、机制、边界。",
        "content": """# {{video_title}}

## 一句话概述
（这个视频解释了什么现象或原理）

## 核心概念
- **概念**：定义 + 为什么重要

## 机制与原理
按因果链解释"为什么会这样"，必要时给出类比

## 常见误解
- 视频里点名纠正的错误理解

## 边界与限制
- 这个结论在什么条件下成立、什么情况下不适用

## 关键名词
- 术语、单位、人名，一句话解释""",
    },
    {
        "id": "builtin-experience",
        "name": "经验分享",
        "description": "适合复盘、心得、避坑类内容：背景、做法、效果。",
        "content": """# {{video_title}}

## 一句话概述
（分享者在什么场景下踩了什么坑、得出了什么结论）

## 背景与前提
- 分享者的身份、资源、约束条件（决定经验是否适用）

## 做法清单
- 具体动作，一条一句，能照做的那种

## 效果与代价
- 做了什么之后带来了什么变化，付出了什么成本

## 不建议做的事
- 视频里明确说"别这么做"的地方

## 适用条件
- 这套经验在什么情况下不适用""",
    },
    {
        "id": "builtin-life",
        "name": "生活技巧",
        "description": "适合教程类生活内容：步骤、材料、注意事项。",
        "content": """# {{video_title}}

## 一句话概述
（学会了能解决什么日常问题）

## 需要准备
- 材料、工具、时间

## 操作步骤
1. 按顺序写清楚，一步一行

## 关键细节
- 决定成败的小技巧

## 常见问题
- 容易失败的地方和补救办法

## 注意事项
- 安全、卫生、保存相关的提醒""",
    },
    {
        "id": "builtin-fun",
        "name": "娱乐内容",
        "description": "适合搞笑、游戏、vlog 等轻内容：短概述 + 几个亮点。",
        "content": """# {{video_title}}

## 一句话概述
（一两句话说清内容）

## 内容梗概
- 按片段写 3 到 6 条，每条一两句

## 亮点与笑点
- 值得单独拎出来的片段

## 适合谁看
- 一句话说清目标观众""",
    },
    {
        "id": "builtin-review",
        "name": "产品评测",
        "description": "适合开箱、横评、工具推荐：定位、优缺点、适用人群。",
        "content": """# {{video_title}}

## 一句话概述
（评测了什么，结论是什么）

## 产品定位
- 它解决什么问题、面向谁、价格区间

## 核心能力
- **能力**：表现 + 视频里的实测结果

## 优点
- 3 到 5 条

## 缺点与限制
- 视频里提到的短板、不适合的场景

## 与同类对比
- 和竞品比强在哪、弱在哪

## 购买建议
- 什么人值得买、什么人没必要""",
    },
    {
        "id": "builtin-interview",
        "name": "访谈对话",
        "description": "适合播客、访谈、圆桌：人物、观点、金句。",
        "content": """# {{video_title}}

## 一句话概述
（谁和谁聊了什么，最有价值的结论是什么）

## 出场人物
- 姓名、身份、立场

## 主要议题
1. **议题**：双方各自的观点与论据

## 关键判断
- 对话中给出的判断、预测、经验数字

## 金句
- 3 到 5 句值得记下来的原话（标明说话人）

## 未展开的问题
- 提到但没深聊的点""",
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
