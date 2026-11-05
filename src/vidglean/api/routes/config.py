"""设置、模型、模板、分类与标签。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from vidglean import bootstrap, config, templates_builtin
from vidglean.ai import client as ai_client
from vidglean.api.common import ok
from vidglean.api.schemas import CategoryIn, ModelIn, ModelPatch, SettingsIn, TemplateIn
from vidglean.core.errors import AppError, from_exception
from vidglean.security import secrets as secret_store
from vidglean.store import repo

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- 设置


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    values = repo.get_settings()
    values["data_dir"] = str(config.data_root())
    values["secrets_backend"] = secret_store.backend()
    return ok(values)


@router.put("/settings")
async def put_settings(payload: SettingsIn) -> dict[str, Any]:
    repo.set_settings(payload.values)
    values = bootstrap.apply_settings()
    values["data_dir"] = str(config.data_root())
    values["secrets_backend"] = secret_store.backend()
    return ok(values)


# ---------------------------------------------------------------- 分类


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    return ok({"items": repo.list_categories()})


@router.post("/categories")
async def create_category(payload: CategoryIn) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise AppError("CONFLICT", "分类名不能为空")
    return ok(repo.create_category(name))


@router.patch("/categories/{category_id}")
async def rename_category(category_id: str, payload: CategoryIn) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise AppError("CONFLICT", "分类名不能为空")
    repo.rename_category(category_id, name)
    return ok({"renamed": True})


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str) -> dict[str, Any]:
    repo.delete_category(category_id)
    return ok({"deleted": True})


# ---------------------------------------------------------------- 标签


@router.get("/tags")
async def list_tags() -> dict[str, Any]:
    return ok({"items": repo.list_tags()})


@router.delete("/tags/{name}")
async def delete_tag(name: str) -> dict[str, Any]:
    from vidglean.store import db

    db.execute(
        "DELETE FROM document_tags WHERE tag_id IN (SELECT id FROM tags WHERE name = ?)", (name,)
    )
    db.execute("DELETE FROM tags WHERE name = ?", (name,))
    return ok({"deleted": True})


# ---------------------------------------------------------------- 模板


def _template_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "description": row["description"],
        "is_default": bool(row["is_default"]),
        "preview": templates_builtin.template_text(row)[:400],
        "variables": sorted(set(templates_builtin.VARIABLE_RE.findall(templates_builtin.template_text(row)))),
    }


@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    return ok({"items": [_template_payload(row) for row in repo.list_templates()]})


@router.post("/templates")
async def upload_template(payload: TemplateIn) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise AppError("CONFLICT", "模板名称不能为空")
    if repo.find_template_by_name(name):
        raise AppError("CONFLICT", "模板名称已存在")
    errors = templates_builtin.validate(payload.content)
    if errors:
        raise AppError("BAD_TEMPLATE", "；".join(errors))
    template_id = repo.create_template(name=name, kind="custom", description=payload.description.strip())
    path = config.templates_dir() / f"{template_id}.md"
    path.write_text(payload.content, "utf-8")
    from vidglean.store import db

    db.execute("UPDATE templates SET path = ? WHERE id = ?", (str(path), template_id))
    row = repo.get_template(template_id)
    assert row is not None
    return ok(_template_payload(row))


@router.post("/templates/{template_id}/default")
async def set_default(template_id: str) -> dict[str, Any]:
    if repo.get_template(template_id) is None:
        raise AppError("NOT_FOUND", "模板不存在", status=404)
    repo.set_default_template(template_id)
    repo.set_setting("template_id", template_id)
    return ok({"default": template_id})


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict[str, Any]:
    row = repo.get_template(template_id)
    if row is None:
        raise AppError("NOT_FOUND", "模板不存在", status=404)
    if row["kind"] == "builtin":
        raise AppError("CONFLICT", "内置模板不能删除")
    path = Path(row["path"]) if row["path"] else None
    if path and path.exists():
        path.unlink()
    repo.delete_template(template_id)
    return ok({"deleted": True})


# ---------------------------------------------------------------- 模型


def _model_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["has_key"] = secret_store.has_secret(f"model:{row['id']}")
    return payload


@router.get("/models")
async def list_models() -> dict[str, Any]:
    return ok({"items": [_model_payload(row) for row in repo.list_models()]})


@router.post("/models")
async def create_model(payload: ModelIn) -> dict[str, Any]:
    if not payload.base_url.strip() or not payload.model.strip():
        raise AppError("CONFLICT", "Base URL 与模型名不能为空")
    model_id = repo.create_model(
        name=payload.name.strip() or payload.model.strip(),
        base_url=payload.base_url.strip(),
        model=payload.model.strip(),
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        timeout=payload.timeout,
    )
    if payload.api_key.strip():
        secret_store.set_secret(f"model:{model_id}", payload.api_key.strip())
    row = repo.get_model(model_id)
    assert row is not None
    return ok(_model_payload(row))


@router.patch("/models/{model_id}")
async def update_model(model_id: str, payload: ModelPatch) -> dict[str, Any]:
    if repo.get_model(model_id) is None:
        raise AppError("NOT_FOUND", "模型不存在", status=404)
    fields = payload.model_dump(exclude_none=True)
    api_key = fields.pop("api_key", None)
    if api_key is not None:
        secret_store.set_secret(f"model:{model_id}", api_key.strip())
    repo.update_model(model_id, **fields)
    row = repo.get_model(model_id)
    assert row is not None
    return ok(_model_payload(row))


@router.delete("/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    repo.delete_model(model_id)
    secret_store.delete_secret(f"model:{model_id}")
    return ok({"deleted": True})


@router.post("/models/{model_id}/current")
async def switch_model(model_id: str) -> dict[str, Any]:
    if repo.get_model(model_id) is None:
        raise AppError("NOT_FOUND", "模型不存在", status=404)
    repo.set_current_model(model_id)
    return ok({"current": model_id})


@router.post("/models/{model_id}/test")
async def test_model(model_id: str) -> dict[str, Any]:
    model = repo.get_model(model_id)
    if model is None:
        raise AppError("NOT_FOUND", "模型不存在", status=404)
    try:
        text, _usage = await ai_client.complete(
            model, [{"role": "user", "content": "只回复两个字：正常"}], max_tokens=16
        )
    except AppError as error:
        return ok({"ok": False, "error": error.to_dict()})
    except Exception as exc:  # pragma: no cover
        return ok({"ok": False, "error": from_exception(exc).to_dict()})
    return ok({"ok": True, "reply": text[:100]})


@router.get("/models/{model_id}/key")
async def model_key_present(model_id: str) -> dict[str, Any]:
    return ok({"has_key": secret_store.has_secret(f"model:{model_id}")})


# ---------------------------------------------------------------- B 站凭证


@router.get("/bilibili/credential")
async def credential_status() -> dict[str, Any]:
    return ok({"configured": secret_store.has_secret("bilibili:sessdata")})


@router.put("/bilibili/credential")
async def set_credential(payload: dict[str, str]) -> dict[str, Any]:
    sessdata = (payload.get("sessdata") or "").strip()
    if not sessdata:
        raise AppError("CONFLICT", "SESSDATA 不能为空")
    secret_store.set_secret("bilibili:sessdata", sessdata)
    return ok({"configured": True})


@router.delete("/bilibili/credential")
async def clear_credential() -> dict[str, Any]:
    secret_store.delete_secret("bilibili:sessdata")
    return ok({"configured": False})
