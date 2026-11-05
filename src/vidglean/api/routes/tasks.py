"""任务列表、详情与控制。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vidglean.api.common import ok
from vidglean.core.errors import AppError
from vidglean.core.models import StageName
from vidglean.pipeline import task_engine
from vidglean.store import repo

router = APIRouter(prefix="/api")


def _task_payload(task_id: str) -> dict[str, Any]:
    task = repo.get_task(task_id)
    if task is None:
        raise AppError("NOT_FOUND", "任务不存在", status=404)
    document = repo.get_document(task["document_id"]) if task.get("document_id") else None
    stages = repo.get_stages(task_id)
    ordered = sorted(stages, key=lambda row: StageName.ORDER.index(row["stage"]))
    return {
        "task": task,
        "stages": [
            {**row, "label": StageName.LABELS.get(row["stage"], row["stage"])} for row in ordered
        ],
        "document_title": document["title"] if document else "",
    }


@router.get("/tasks")
async def list_tasks(
    status: str | None = None, limit: int = 100, include_done: bool = False
) -> dict[str, Any]:
    tasks = repo.list_tasks(status=status, limit=limit, include_done=include_done)
    return ok({"items": tasks})


@router.post("/tasks/cleanup")
async def cleanup_tasks() -> dict[str, Any]:
    removed = repo.delete_finished_tasks()
    return ok({"removed": removed})


@router.get("/tasks/{task_id}")
async def task_detail(task_id: str) -> dict[str, Any]:
    return ok(_task_payload(task_id))


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str) -> dict[str, Any]:
    task = repo.get_task(task_id)
    if task is None:
        raise AppError("NOT_FOUND", "任务不存在", status=404)
    task_engine.retry(task_id)
    return ok(_task_payload(task_id))


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str) -> dict[str, Any]:
    task_engine.pause(task_id)
    return ok(_task_payload(task_id))


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str) -> dict[str, Any]:
    task_engine.resume(task_id)
    return ok(_task_payload(task_id))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, Any]:
    await task_engine.cancel(task_id)
    return ok(_task_payload(task_id))
