"""请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PreviewIn(BaseModel):
    urls: list[str] = Field(default_factory=list)


class ImportItem(BaseModel):
    url: str
    depth: str = "auto"
    template_id: str = ""
    extra: str = ""
    force: bool = False


class ImportIn(BaseModel):
    items: list[ImportItem] = Field(default_factory=list)


class ContentIn(BaseModel):
    content: str
    snapshot: bool = True


class PatchDocumentIn(BaseModel):
    title: str | None = None
    starred: bool | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    content_type: str | None = None


class RegenerateIn(BaseModel):
    depth: str | None = None
    template_id: str | None = None
    extra: str | None = None


class AssistIn(BaseModel):
    instruction: str


class ApplyIn(BaseModel):
    content: str


class NoteIn(BaseModel):
    content: str


class ChatIn(BaseModel):
    message: str


class CategoryIn(BaseModel):
    name: str


class TemplateIn(BaseModel):
    name: str
    description: str = ""
    content: str


class TemplateUpdate(BaseModel):
    content: str
    name: str | None = None
    description: str | None = None


class ModelIn(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str = ""
    temperature: float = 0.5
    max_tokens: int = 8192
    timeout: int = 120


class ModelPatch(BaseModel):
    name: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: int | None = None


class SettingsIn(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class BackupIn(BaseModel):
    path: str = ""
    password: str = ""


class RestoreIn(BaseModel):
    path: str
    password: str = ""


class DataDirIn(BaseModel):
    path: str
