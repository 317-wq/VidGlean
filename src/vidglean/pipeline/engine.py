"""任务引擎：调度、并发、阶段推进、重试与取消。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timedelta
from typing import Any

from vidglean import config
from vidglean.core.errors import AppError, from_exception
from vidglean.core.events import bus
from vidglean.core.models import StageName, StageStatus, TaskStatus
from vidglean.core.utils import now_iso
from vidglean.pipeline.stages import STAGES, TaskContext
from vidglean.store import repo

_log = logging.getLogger(__name__)

POLL_SECONDS = 0.8


def _backoff(attempt: int) -> float:
    return min(2.0**attempt, 30.0) + random.uniform(0, 1)


class TaskEngine:
    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task[None]] = {}
        self._wake = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None
        self._stopping = False

    # ------------------------------------------------------------ 生命周期

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        self._stopping = False
        self._loop_task = asyncio.create_task(self._scheduler(), name="vg-scheduler")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        for task in list(self._running.values()):
            task.cancel()
        for task in list(self._running.values()):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._loop_task is not None:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._loop_task
            self._loop_task = None

    def notify(self) -> None:
        self._wake.set()

    # ------------------------------------------------------------ 对外操作

    @property
    def active_count(self) -> int:
        return len(self._running)

    def is_running(self, task_id: str) -> bool:
        return task_id in self._running

    async def cancel(self, task_id: str) -> None:
        repo.update_task(task_id, status=TaskStatus.CANCELED, next_retry_at=None)
        task = self._running.get(task_id)
        if task is not None:
            task.cancel()
        self._publish(task_id, TaskStatus.CANCELED, "")

    def pause(self, task_id: str) -> None:
        task = repo.get_task(task_id)
        if task is None:
            return
        if task["status"] in (TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.FAILED):
            repo.update_task(task_id, status=TaskStatus.PAUSED, next_retry_at=None)
            self._publish(task_id, TaskStatus.PAUSED, task.get("current_stage") or "")

    def resume(self, task_id: str) -> None:
        task = repo.get_task(task_id)
        if task is None:
            return
        if task["status"] == TaskStatus.PAUSED:
            repo.update_task(task_id, status=TaskStatus.PENDING)
            self.notify()

    def retry(self, task_id: str) -> None:
        task = repo.get_task(task_id)
        if task is None:
            return
        stages = repo.get_stages(task_id)
        failing = next((s["stage"] for s in stages if s["status"] != StageStatus.SUCCEEDED), None)
        repo.reset_stages(task_id, failing or StageName.ORDER[0])
        repo.update_task(
            task_id,
            status=TaskStatus.PENDING,
            retry_count=0,
            next_retry_at=None,
            error_code="",
            error_message="",
        )
        self.notify()

    # ------------------------------------------------------------ 调度

    async def _scheduler(self) -> None:
        while not self._stopping:
            self._wake.clear()
            try:
                await self._tick()
            except Exception:  # pragma: no cover - 调度器不能挂
                _log.exception("调度循环异常")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=POLL_SECONDS)
            except TimeoutError:
                continue

    async def _tick(self) -> None:
        settings = repo.get_settings()
        limit = max(1, int(settings.get("concurrency_video") or 2))
        candidates: list[str] = []
        for task_id in repo.pending_task_ids():
            candidates.append(task_id)
        for task_id in repo.due_retry_ids(now_iso()):
            if task_id not in candidates:
                candidates.append(task_id)
        for task_id in candidates:
            if len(self._running) >= limit:
                break
            if task_id in self._running:
                continue
            self._running[task_id] = asyncio.create_task(self._run(task_id), name=f"vg-task-{task_id}")

    # ------------------------------------------------------------ 执行

    async def _run(self, task_id: str) -> None:
        try:
            await self._execute(task_id)
        except asyncio.CancelledError:
            task = repo.get_task(task_id)
            if task:
                stage = task.get("current_stage") or ""
                if stage:
                    row = next(
                        (item for item in repo.get_stages(task_id) if item["stage"] == stage), None
                    )
                    if row and row["status"] == StageStatus.RUNNING:
                        repo.set_stage(task_id, stage, StageStatus.SKIPPED)
                if task["status"] not in (TaskStatus.CANCELED, TaskStatus.PAUSED):
                    repo.update_task(task_id, status=TaskStatus.CANCELED)
            raise
        except Exception as exc:  # pragma: no cover - 兜底
            _log.exception("任务执行异常 %s", task_id)
            error = from_exception(exc)
            repo.update_task(
                task_id, status=TaskStatus.FAILED, error_code=error.code, error_message=error.message
            )
        finally:
            self._running.pop(task_id, None)

    async def _execute(self, task_id: str) -> None:
        task = repo.get_task(task_id)
        if task is None:
            return
        if task["status"] not in (TaskStatus.PENDING, TaskStatus.FAILED):
            return

        repo.update_task(
            task_id,
            status=TaskStatus.RUNNING,
            next_retry_at=None,
            error_code="",
            error_message="",
        )
        self._publish(task_id, TaskStatus.RUNNING, task.get("current_stage") or "")

        ctx = TaskContext(task=task, workdir=config.task_dir(task_id))
        current_stage = ""
        try:
            for stage in StageName.ORDER:
                fresh = repo.get_task(task_id)
                if fresh is None:
                    return
                if fresh["status"] in (TaskStatus.PAUSED, TaskStatus.CANCELED):
                    self._publish(task_id, fresh["status"], current_stage)
                    return
                stages = {row["stage"]: row for row in repo.get_stages(task_id)}
                if stages.get(stage, {}).get("status") == StageStatus.SUCCEEDED:
                    continue
                current_stage = stage
                repo.update_task(task_id, current_stage=stage)
                repo.set_stage(task_id, stage, StageStatus.RUNNING)
                self._publish(task_id, TaskStatus.RUNNING, stage)
                ctx.task = repo.get_task(task_id) or task
                await STAGES[stage](ctx)
                repo.set_stage(task_id, stage, StageStatus.SUCCEEDED)
        except AppError as error:
            await self._handle_failure(task_id, current_stage, error)
            return

        repo.update_task(task_id, status=TaskStatus.SUCCEEDED, current_stage="", error_code="", error_message="")
        self._publish(task_id, TaskStatus.SUCCEEDED, "")

    async def _handle_failure(self, task_id: str, stage: str, error: AppError) -> None:
        if stage:
            repo.set_stage(
                task_id,
                stage,
                StageStatus.FAILED,
                error_code=error.code,
                error_message=error.message,
            )
        task = repo.get_task(task_id)
        if task is None:
            return
        settings = repo.get_settings()
        max_retries = max(0, int(settings.get("max_retries") or 0))
        attempts = int(task.get("retry_count") or 0)
        if error.retriable and attempts < max_retries:
            delay = _backoff(attempts + 1)
            next_at = (datetime.now() + timedelta(seconds=delay)).replace(microsecond=0).isoformat()
            repo.update_task(
                task_id,
                status=TaskStatus.FAILED,
                retry_count=attempts + 1,
                next_retry_at=next_at,
                error_code=error.code,
                error_message=error.message,
            )
            _log.warning("任务 %s 将在 %.1fs 后重试（第 %d 次）：%s", task_id, delay, attempts + 1, error.message)
        else:
            repo.update_task(
                task_id,
                status=TaskStatus.FAILED,
                next_retry_at=None,
                error_code=error.code,
                error_message=error.message,
            )
            _log.warning("任务 %s 失败：%s", task_id, error.message)
        self._publish(task_id, TaskStatus.FAILED, stage, error_code=error.code)

    @staticmethod
    def _publish(task_id: str, status: str, stage: str, *, error_code: str = "") -> None:
        event: dict[str, Any] = {"type": "task", "task_id": task_id, "status": status, "stage": stage}
        if error_code:
            event["error_code"] = error_code
        bus.publish(event)


engine = task_engine = TaskEngine()
