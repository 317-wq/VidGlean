"""统一错误类型。

错误码同时用于：任务失败原因、日志、前端提示。可重试的错误由任务引擎自动退避重试。
"""

from __future__ import annotations

from typing import Any

# 错误码 -> (用户可读默认文案, 是否可重试)
ERRORS: dict[str, tuple[str, bool]] = {
    "INVALID_URL": ("链接格式无法识别", False),
    "UNSUPPORTED_URL": ("暂不支持该链接", False),
    "VIDEO_NOT_FOUND": ("视频不存在或已删除", False),
    "VIDEO_PRIVATE": ("该视频需要登录或已被设为私密", False),
    "NO_SUBTITLE": ("该视频没有可用字幕，暂不支持", False),
    "AUTH_REQUIRED": ("需要配置 B 站登录凭证（SESSDATA）", False),
    "AUTH_EXPIRED": ("B 站登录凭证已失效，请重新配置", False),
    "RATE_LIMIT": ("请求过于频繁，稍后自动重试", True),
    "TIMEOUT": ("网络请求超时", True),
    "NETWORK": ("网络连接异常", True),
    "SERVER_ERROR": ("服务暂时不可用", True),
    "API_KEY_INVALID": ("API Key 无效", False),
    "INSUFFICIENT_QUOTA": ("账户余额不足", False),
    "MODEL_NOT_FOUND": ("模型不存在或无权访问", False),
    "API_ERROR": ("AI 服务返回错误", False),
    "BAD_TEMPLATE": ("Markdown 模板校验失败", False),
    "NOT_FOUND": ("对象不存在", False),
    "CONFLICT": ("操作与当前状态冲突", False),
    "UNKNOWN": ("未知错误", False),
}


class AppError(Exception):
    """业务错误。``code`` 必须出现在 :data:`ERRORS` 中。"""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        retriable: bool | None = None,
        status: int = 400,
        detail: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        default_message, default_retriable = ERRORS.get(code, ERRORS["UNKNOWN"])
        self.code = code
        self.message = message or default_message
        self.retriable = default_retriable if retriable is None else retriable
        self.status = status
        self.detail = detail
        self.extra = extra or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail:
            data["detail"] = self.detail
        return data

    def __str__(self) -> str:  # pragma: no cover - 便于日志阅读
        return f"{self.code}: {self.message}"


def from_exception(exc: Exception) -> AppError:
    """把任意异常收敛成 AppError，供任务引擎记录。"""
    if isinstance(exc, AppError):
        return exc
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timed out" in text:
        return AppError("TIMEOUT", detail=str(exc))
    if "connection" in name or "connect" in text or "network" in text:
        return AppError("NETWORK", detail=str(exc))
    return AppError("UNKNOWN", detail=f"{type(exc).__name__}: {exc}")
