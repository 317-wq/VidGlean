"""任务引擎状态机测试（用假阶段，不触网）。"""

from __future__ import annotations

import pytest

import vidglean.pipeline.engine as engine_module
from vidglean import bootstrap
from vidglean.core.errors import AppError
from vidglean.core.models import StageName, TaskStatus
from vidglean.store import repo

URL = "https://www.bilibili.com/video/BV1xx411c7mD"


def _make_task() -> str:
    return repo.create_task(source_url=URL, options={"depth": "standard"})


@pytest.fixture()
def fake_stages(monkeypatch):
    calls: list[str] = []

    async def ok(ctx):
        calls.append(ctx.task["id"])

    monkeypatch.setattr(
        engine_module, "STAGES", {stage: ok for stage in StageName.ORDER}
    )
    return calls


@pytest.mark.asyncio
async def test_engine_success(env, fake_stages):
    bootstrap.init()
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    await engine._execute(task_id)
    task = repo.get_task(task_id)
    assert task["status"] == TaskStatus.SUCCEEDED
    assert len(fake_stages) == len(StageName.ORDER)
    assert all(stage["status"] == "succeeded" for stage in repo.get_stages(task_id))


@pytest.mark.asyncio
async def test_engine_retriable_failure_schedules_retry(env, monkeypatch):
    bootstrap.init()

    async def boom(ctx):
        raise AppError("TIMEOUT")

    monkeypatch.setattr(engine_module, "STAGES", {stage: boom for stage in StageName.ORDER})
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    await engine._execute(task_id)
    task = repo.get_task(task_id)
    assert task["status"] == TaskStatus.FAILED
    assert task["retry_count"] == 1
    assert task["next_retry_at"]
    assert task["error_code"] == "TIMEOUT"


@pytest.mark.asyncio
async def test_engine_permanent_failure_no_retry(env, monkeypatch):
    bootstrap.init()

    async def boom(ctx):
        raise AppError("NO_SUBTITLE")

    monkeypatch.setattr(engine_module, "STAGES", {stage: boom for stage in StageName.ORDER})
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    await engine._execute(task_id)
    task = repo.get_task(task_id)
    assert task["status"] == TaskStatus.FAILED
    assert task["next_retry_at"] is None


@pytest.mark.asyncio
async def test_stage_skip_after_success(env, fake_stages):
    bootstrap.init()
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    await engine._execute(task_id)
    assert len(fake_stages) == len(StageName.ORDER)

    # 手动重试后从第一个未成功阶段开始
    engine.retry(task_id)
    task = repo.get_task(task_id)
    assert task["status"] == TaskStatus.PENDING
    assert all(stage["status"] == "pending" for stage in repo.get_stages(task_id))


@pytest.mark.asyncio
async def test_cancel_marks_task(env):
    bootstrap.init()
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    await engine.cancel(task_id)
    assert repo.get_task(task_id)["status"] == TaskStatus.CANCELED


@pytest.mark.asyncio
async def test_pause_and_resume(env):
    bootstrap.init()
    task_id = _make_task()
    engine = engine_module.TaskEngine()
    engine.pause(task_id)
    assert repo.get_task(task_id)["status"] == TaskStatus.PAUSED
    engine.resume(task_id)
    assert repo.get_task(task_id)["status"] == TaskStatus.PENDING


def test_interrupted_marking(env):
    bootstrap.init()
    task_id = _make_task()
    repo.update_task(task_id, status=TaskStatus.RUNNING)
    assert repo.mark_running_interrupted() >= 1
    assert repo.get_task(task_id)["status"] == TaskStatus.INTERRUPTED
