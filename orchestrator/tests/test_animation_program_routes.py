"""Authenticated model-code routing, admission, errors and cooperative cancellation."""

import asyncio
import threading

import pytest
from fastapi import HTTPException

from contracts.models import AnimationProgramRenderRequest
from orchestrator.gateway import routes
from orchestrator.gateway.generations import GenerationManager
from orchestrator.gateway.ladder import DegradationLadder
from orchestrator.gateway.sessions import SessionManager
from orchestrator.tests.test_animation_program import VALID, Engine, author_manim_program, request


class Connected:
    async def is_disconnected(self):
        return False


def dependencies(monkeypatch):
    monkeypatch.setattr(routes, "_await_local_tutor", lambda: None)
    monkeypatch.setattr(
        routes,
        "isolated_program_capability",
        lambda **kw: {"available": True, "detail": "Verified test fixture"},
    )
    return {
        "engine": Engine(),
        "sessions": SessionManager(slots_count=1),
        "ladder": DegradationLadder(free_probe=lambda: 8 * 1024**3),
        "generations": GenerationManager(max_active=1),
        "caller": "learner",
    }


def test_real_authoring_route_uses_generation_admission_and_releases(monkeypatch):
    deps = dependencies(monkeypatch)
    result = asyncio.run(routes.animation_program(Connected(), request(), **deps))
    assert result.program.source == VALID
    assert len(deps["engine"].local.calls) == 1
    assert deps["generations"].status()["running"] == 0
    assert all(not slot["busy"] for slot in deps["sessions"].status()["slots"])


def test_authoring_error_returns_actual_repair_source_and_releases(monkeypatch):
    deps = dependencies(monkeypatch)
    deps["engine"] = Engine("bad Python")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes.animation_program(Connected(), request(), **deps))
    assert raised.value.status_code == 422
    assert raised.value.detail["source"] == "bad Python"
    assert raised.value.detail["repairable"] is True
    assert deps["generations"].status()["running"] == 0


def test_authoring_cannot_impersonate_or_bypass_unavailable_isolation(monkeypatch):
    deps = dependencies(monkeypatch)
    deps["caller"] = "other"
    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes.animation_program(Connected(), request(), **deps))
    assert raised.value.status_code == 403
    deps["caller"] = "learner"
    monkeypatch.setattr(
        routes,
        "isolated_program_capability",
        lambda **kw: {"available": False, "detail": "No proven isolation"},
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes.animation_program(Connected(), request(), **deps))
    assert raised.value.status_code == 503
    assert deps["engine"].local.calls == []


def test_cold_capability_runs_off_event_loop_and_drains_cancel(monkeypatch):
    stopped = threading.Event()

    def prepare(*, cancel_event):
        cancel_event.wait(1)
        stopped.set()
        return {"available": False, "detail": "cancelled"}

    monkeypatch.setattr(routes, "isolated_program_capability", prepare)

    class Disconnected:
        async def is_disconnected(self):
            return True

    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes._program_capability_for_request(Disconnected()))
    assert raised.value.status_code == 499
    assert stopped.is_set()


def test_program_render_source_identity_headers_and_error_mapping(monkeypatch):
    program = author_manim_program(Engine(), request())
    monkeypatch.setattr(routes, "render_authored_program", lambda *args, **kw: b"mp4 fixture")
    response = asyncio.run(
        routes.animation_program_render(
            AnimationProgramRenderRequest(program=program), Connected(), caller="learner"
        )
    )
    assert response.body == b"mp4 fixture"
    assert response.headers["x-muta-source-sha256"] == program.source_sha256
    assert response.headers["x-muta-code-origin"] == "local-model"
    imported = program.model_copy(update={"generation_token": ""})
    response = asyncio.run(
        routes.animation_program_render(
            AnimationProgramRenderRequest(program=imported), Connected(), caller="learner"
        )
    )
    assert response.headers["x-muta-code-origin"] == "saved-or-imported"


def test_cancelled_render_keeps_cleanup_ownership(monkeypatch):
    entered, stopped = threading.Event(), threading.Event()

    def render(program, *, cancel_event):
        entered.set()
        assert cancel_event.wait(2)
        stopped.set()
        raise routes.AnimationRenderError("cancelled")

    monkeypatch.setattr(routes, "render_authored_program", render)
    program = author_manim_program(Engine(), request())

    async def run():
        task = asyncio.create_task(
            routes.animation_program_render(
                AnimationProgramRenderRequest(program=program), Connected(), caller="learner"
            )
        )
        while not entered.is_set():
            await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()

    asyncio.run(run())
