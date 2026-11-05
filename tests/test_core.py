"""纯函数单元测试。"""

from vidglean import markdown_render, templates_builtin
from vidglean.security.redact import redact
from vidglean.store import search


def test_tokenize_cjk_bigram():
    tokens = search.tokenize("网络编程").split()
    assert "网络" in tokens
    assert "编程" in tokens


def test_tokenize_mixed():
    tokens = search.tokenize("Reactor 模式与 epoll").split()
    assert "reactor" in tokens
    assert "epoll" in tokens
    assert "模式" in tokens


def test_match_expression_quotes():
    expression = search.match_expression("并发 编程")
    assert expression == '"并发" AND "编程"'


def test_single_char_uses_like_fallback():
    assert search.needs_like_fallback("网") is True
    assert search.needs_like_fallback("网络") is False


def test_markdown_renders_code_and_math():
    source = "# 标题\n\n```python\nprint(1)\n```\n\n公式 $a^2+b^2=c^2$ 结束\n"
    html = markdown_render.render(source)
    assert "<h1" in html
    assert "codehilite" in html
    assert "$a^2+b^2=c^2$" in html


def test_strip_code_fence():
    assert markdown_render.strip_code_fence("```markdown\n# 标题\n```") == "# 标题"


def test_template_validation():
    assert templates_builtin.validate("# {{video_title}}\n{{unknown}}") != []
    assert templates_builtin.validate("# {{video_title}}\n{{author}}") == []


def test_template_render():
    text = templates_builtin.render("# {{video_title}} - {{author}}", {"video_title": "标题", "author": "UP"})
    assert text == "# 标题 - UP"


def test_builtin_templates_present():
    assert {item["id"] for item in templates_builtin.BUILTIN_TEMPLATES} >= {
        "builtin-general",
        "builtin-tech",
        "builtin-opinion",
    }


def test_redact_secrets():
    text = "SESSDATA=abc123; Authorization: Bearer sk-abcdef123456"
    cleaned = redact(text)
    assert "abc123" not in cleaned
    assert "sk-abcdef123456" not in cleaned


def test_clean_tags_rejects_reasoning_text():
    from vidglean.ai.summarize import _clean_tags

    text = "主题或领域词。首先看文档内容, 爱情承诺, 每个不超过12字, 用逗号分隔"
    assert _clean_tags(text, 6) == ["爱情承诺"]


def test_fallback_terms_from_key_section():
    from vidglean.ai.summarize import _fallback_terms

    content = "## 关键名词\n- Reactor：事件驱动\n- epoll\n\n## 其他\n- 忽略"
    assert _fallback_terms(content, 5) == ["Reactor", "epoll"]
