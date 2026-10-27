"""Adversarial tests for the local model lesson-animation boundary."""

from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from contracts.models import AnimationPlanRequest
from orchestrator.gateway.animation_planner import (
    MAX_ANIMATION_PLAN_ATTEMPTS,
    animation_planner_schema,
    plan_animation_project,
)
from orchestrator.gateway.generations import GenerationManager
from orchestrator.gateway.ladder import DegradationLadder
from orchestrator.gateway.routes import animation_plan
from orchestrator.gateway.sessions import SessionManager


class _SequenceClient:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[list[dict], dict]] = []

    def stream_events(self, messages, **params):
        self.calls.append((messages, params))
        payload = self.payloads[min(len(self.calls) - 1, len(self.payloads) - 1)]
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        yield "content", raw[: max(1, len(raw) // 2)]
        yield "content", raw[max(1, len(raw) // 2) :]


class _Engine:
    def __init__(self, payloads: list[object]) -> None:
        self.local = _SequenceClient(payloads)
        self.client = SimpleNamespace(local=self.local)

    @staticmethod
    def _fit_request(messages, params, *, protected_tail_messages):
        assert protected_tail_messages == 1
        return messages, params


def _request() -> AnimationPlanRequest:
    return AnimationPlanRequest(
        student_id="learner",
        topic="How a seed becomes a plant",
        level="upper-primary",
        concept="germination",
        requirements="seed absorbs water, root emerges, shoot reaches light",
    )


def _valid() -> dict:
    return {
        "title": "From seed to seedling",
        "summary": "Follow the ordered visible changes during germination.",
        "steps": [
            {"title": "Take in water", "narration": "The seed absorbs water and swells."},
            {"title": "Grow a root", "narration": "The first root grows down into the soil."},
            {"title": "Reach the light", "narration": "The shoot grows upward and opens leaves."},
        ],
    }


def test_planner_schema_is_closed_and_contains_no_source_fields() -> None:
    schema = animation_planner_schema()
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    encoded = json.dumps(schema).lower()
    for forbidden in ("javascript", "html", "shader", "url", "source", "renderer"):
        assert f'"{forbidden}"' not in encoded


def test_valid_plan_builds_only_typed_process_scenes() -> None:
    engine = _Engine([_valid()])
    project, repaired = plan_animation_project(engine, _request())
    assert project is not None
    assert repaired is False
    assert [scene.kind for scene in project.scenes] == ["process"] * 3
    assert [scene.data.active for scene in project.scenes] == [0, 1, 2]
    assert project.scenes[2].data.steps[0] == "The seed absorbs water and swells."
    params = engine.local.calls[0][1]
    assert params["response_format"]["type"] == "json_schema"
    assert params["temperature"] == 0.0


def test_invalid_proposal_gets_one_structured_repair() -> None:
    invalid = {**_valid(), "steps": [{"title": "Only", "narration": "One state"}]}
    engine = _Engine([invalid, _valid()])
    project, repaired = plan_animation_project(engine, _request())
    assert project is not None and repaired is True
    assert len(engine.local.calls) == 2
    assert "Structured validation errors" in engine.local.calls[1][0][1]["content"]


def test_whitespace_text_is_repaired_instead_of_becoming_a_server_error() -> None:
    blank = {**_valid(), "title": "   "}
    engine = _Engine([blank, _valid()])
    project, repaired = plan_animation_project(engine, _request())
    assert project is not None and repaired is True
    assert "blank_text" in engine.local.calls[1][0][1]["content"]


def test_whitespace_topic_fails_request_validation() -> None:
    with pytest.raises(ValidationError, match="visible text"):
        AnimationPlanRequest(student_id="learner", topic="  ", level="secondary")


def test_unknown_executable_fields_fail_closed_after_bounded_attempts() -> None:
    unsafe = {**_valid(), "javascript": "alert(1)"}
    engine = _Engine([unsafe])
    project, repaired = plan_animation_project(engine, _request())
    assert project is None and repaired is True
    assert len(engine.local.calls) == MAX_ANIMATION_PLAN_ATTEMPTS


def test_cancelled_planner_never_contacts_model() -> None:
    event = threading.Event(); event.set(); engine = _Engine([_valid()])
    project, repaired = plan_animation_project(engine, _request(), cancel_event=event)
    assert project is None and repaired is False
    assert engine.local.calls == []


def test_http_planner_uses_generation_admission_and_drains(monkeypatch) -> None:
    class _ConnectedRequest:
        @staticmethod
        async def is_disconnected() -> bool:
            return False

    monkeypatch.setattr("orchestrator.gateway.routes.wait_for_engine_ready", lambda: None)
    engine = _Engine([_valid()])
    generations = GenerationManager(max_active=1)
    sessions = SessionManager(slots_count=1)
    response = asyncio.run(
        animation_plan(
            _ConnectedRequest(),
            _request(),
            engine=engine,
            sessions=sessions,
            ladder=DegradationLadder(free_probe=lambda: 8 * 1024**3),
            generations=generations,
            caller="learner",
        )
    )
    assert response.project.title == "From seed to seedling"
    assert generations.status()["running"] == 0
    assert all(not slot["busy"] for slot in sessions.status()["slots"])


def test_disconnected_queued_planner_is_stopped_and_releases_admission(monkeypatch) -> None:
    class _DisconnectedRequest:
        @staticmethod
        async def is_disconnected() -> bool:
            return True

    release = threading.Event()

    def blocker():
        yield "data: running\n\n"
        release.wait(timeout=2)
        yield 'data: {"done": true}\n\n'

    monkeypatch.setattr("orchestrator.gateway.routes.wait_for_engine_ready", lambda: None)
    generations = GenerationManager(max_active=1)
    blocking_job = generations.start(
        student_id="other",
        conversation_id="blocker",
        producer=blocker(),
    )
    sessions = SessionManager(slots_count=1)
    with pytest.raises(HTTPException, match="stopped before"):
        asyncio.run(
            animation_plan(
                _DisconnectedRequest(),
                _request(),
                engine=_Engine([_valid()]),
                sessions=sessions,
                ladder=DegradationLadder(free_probe=lambda: 8 * 1024**3),
                generations=generations,
                caller="learner",
            )
        )
    assert generations.status()["queued"] == 0
    assert all(not slot["busy"] for slot in sessions.status()["slots"])
    release.set()
    blocking_job.wait(timeout_s=2)

