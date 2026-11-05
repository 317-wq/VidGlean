"""Markdown 渲染：代码高亮 + 公式保护。

公式在 Markdown 解析前被替换成占位符，解析后原样还原，交给前端的 KaTeX 处理，
避免 Markdown 把 ``_`` ``*`` 之类的字符吃掉。
"""

from __future__ import annotations

import re

import markdown

_MATH_RE = re.compile(r"(\$\$[\s\S]+?\$\$)|(?<!\\)\$[^$\n]+?(?<!\\)\$")
_PLACEHOLDER = "VGMATHPLACEHOLDER{}END"

_EXTENSIONS = [
    "fenced_code",
    "tables",
    "sane_lists",
    "toc",
    "codehilite",
]

_EXTENSION_CONFIGS = {
    "codehilite": {
        "guess_lang": False,
        "css_class": "codehilite",
        "noclasses": False,
    },
    "toc": {"permalink": False},
}


def render(text: str) -> str:
    if not text:
        return ""
    protected: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return _PLACEHOLDER.format(len(protected) - 1)

    replaced = _MATH_RE.sub(_stash, text)
    html = markdown.markdown(
        replaced, extensions=_EXTENSIONS, extension_configs=_EXTENSION_CONFIGS, output_format="html5"
    )
    for index, formula in enumerate(protected):
        html = html.replace(_PLACEHOLDER.format(index), formula)
    return html


def strip_code_fence(text: str) -> str:
    """模型有时会把整篇 Markdown 包在 ```markdown 里，去掉外层围栏。"""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return stripped
    if not stripped.endswith("```"):
        return stripped
    return stripped[first_newline + 1 : -3].strip()
