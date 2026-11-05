"""跨模块共用的数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VideoMeta:
    """平台解析出的视频元信息。"""

    platform: str
    video_id: str
    title: str
    author: str = ""
    cover_url: str = ""
    duration: int = 0
    source_url: str = ""
    content_type: str = "其他"
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContentType:
    """PRD 5.3 的视频类型。"""

    TECH = "技术教程"
    SCIENCE = "知识科普"
    EXPERIENCE = "经验分享"
    OPINION = "观点讨论"
    LIFE = "生活技巧"
    FUN = "娱乐内容"
    OTHER = "其他"

    ALL = [TECH, SCIENCE, EXPERIENCE, OPINION, LIFE, FUN, OTHER]


class Depth:
    """PRD 5.2 的总结深度。"""

    AUTO = "auto"
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"

    ALL = [AUTO, BRIEF, STANDARD, DETAILED]

    LABELS = {
        AUTO: "自动",
        BRIEF: "简洁",
        STANDARD: "标准",
        DETAILED: "详细",
    }


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"

    ALL = [PENDING, RUNNING, PAUSED, SUCCEEDED, FAILED, CANCELED, INTERRUPTED]


class StageName:
    LINK = "link_parse"
    SUBTITLE = "subtitle"
    AI = "ai_analyze"
    RENDER = "render_md"

    ORDER = [LINK, SUBTITLE, AI, RENDER]

    LABELS = {
        LINK: "链接解析",
        SUBTITLE: "字幕获取",
        AI: "AI 内容分析",
        RENDER: "Markdown 生成",
    }


class StageStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
