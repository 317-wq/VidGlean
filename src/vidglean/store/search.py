"""中文友好的分词与 FTS 查询构造。

不引入 jieba：对 CJK 文本做二元切分（bigram），英文/数字按单词切分。
查询同样切分后与 FTS 索引匹配，两字以上的中文词可以正常命中。
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> str:
    """把原始文本切成空格分隔的检索词。"""
    if not text:
        return ""
    parts: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group()
        if "\u4e00" <= token[0] <= "\u9fff":
            if len(token) == 1:
                parts.append(token)
            else:
                parts.extend(token[i : i + 2] for i in range(len(token) - 1))
        else:
            parts.append(token.lower())
    return " ".join(parts)


def query_terms(text: str) -> list[str]:
    return tokenize(text).split()


def match_expression(text: str) -> str | None:
    """构造 FTS5 的 MATCH 表达式；没有可用词时返回 None。"""
    terms = query_terms(text)
    if not terms:
        return None
    escaped = [t.replace('"', '""') for t in terms]
    return " AND ".join(f'"{t}"' for t in escaped)


def needs_like_fallback(text: str) -> bool:
    """单字查询无法用 bigram 命中，退化为 LIKE。"""
    terms = query_terms(text)
    return len(terms) == 1 and len(terms[0]) == 1
