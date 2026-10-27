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
    AnimationPlanBriefError,
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


@pytest.mark.parametrize("concept", ["Explain division", "Explain 14 ÷ 4", "Explain 12 divided by 3", "Divide twelve by three", "Share 12 objects among 3 friends"])
def test_whole_number_division_never_uses_unverified_process_arithmetic(concept):
    engine = _Engine([_valid()])
    request = _request().model_copy(update={"topic": concept, "concept": concept, "requirements": ""})
    project, repaired = plan_animation_project(engine, request)
    assert project is None and repaired is False
    assert engine.local.calls == []


def test_planner_schema_is_closed_and_contains_no_source_fields() -> None:
    schema = animation_planner_schema()
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    encoded = json.dumps(schema).lower()
    for forbidden in ("javascript", "html", "shader", "url", "source", "renderer"):
        assert f'"{forbidden}"' not in encoded

    exact = animation_planner_schema(3)["schema"]["properties"]["steps"]
    assert exact["minItems"] == 3
    assert exact["maxItems"] == 3


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


def test_explicit_unresolved_function_never_becomes_a_prose_storyboard() -> None:
    for concept in (
        "Plot y = mystery(x) from −π to π",
        "x = mystery(t)",
        "f(x) = mystery(x)",
        "Plot x²",
        "Plot x⁻²",
        "Plot x from -π to π",
        "Graph -1/2*x from -π to π",
    ):
        engine = _Engine([_valid()])
        request = AnimationPlanRequest(
            student_id="learner",
            topic="An unresolved function",
            level="secondary",
            concept=concept,
            requirements="Draw labelled axes and trace the curve.",
        )
        project, repaired = plan_animation_project(engine, request)
        assert project is None
        assert repaired is False
        assert engine.local.calls == []


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


def test_truncated_generated_narration_gets_one_complete_sentence_repair() -> None:
    truncated = {**_valid()}
    truncated["steps"] = [dict(step) for step in _valid()["steps"]]
    truncated["steps"][0]["narration"] = "x" * 116 + " the"
    assert len(truncated["steps"][0]["narration"]) == 120
    engine = _Engine([truncated, _valid()])

    project, repaired = plan_animation_project(engine, _request())

    assert project is not None and repaired is True
    assert len(engine.local.calls) == 2
    first_system_prompt = engine.local.calls[0][0][0]["content"]
    assert "one complete age-appropriate sentence of 60 to 90 characters" in first_system_prompt
    assert "well before the 120-character schema limit" in first_system_prompt
    repair_prompt = engine.local.calls[1][0][1]["content"]
    assert "incomplete_sentence" in repair_prompt
    assert "rewrite rather than truncating" in repair_prompt


def test_generated_narration_with_trailing_article_is_not_made_valid_by_punctuation() -> None:
    incomplete = {**_valid()}
    incomplete["steps"] = [dict(step) for step in _valid()["steps"]]
    incomplete["steps"][1]["narration"] = "The balance remains the."
    engine = _Engine([incomplete])

    project, repaired = plan_animation_project(engine, _request())

    assert project is None and repaired is True
    assert len(engine.local.calls) == MAX_ANIMATION_PLAN_ATTEMPTS


@pytest.mark.parametrize(
    "narration",
    [
        "x" * 114 + " the.”",
        "The balance remains the.)",
        "The balance remains the...",
    ],
)
def test_closing_marks_cannot_conceal_an_incomplete_generated_sentence(
    narration: str,
) -> None:
    incomplete = {**_valid()}
    incomplete["steps"] = [dict(step) for step in _valid()["steps"]]
    incomplete["steps"][0]["narration"] = narration
    engine = _Engine([incomplete, _valid()])

    project, repaired = plan_animation_project(engine, _request())

    assert project is not None and repaired is True
    assert len(engine.local.calls) == 2


@pytest.mark.parametrize(
    "narration",
    [
        "水流进入第一个容器。",
        "ينتقل الماء إلى الوعاء الأول؟",
        "L’eau entre dans le premier récipient.»",
    ],
)
def test_generated_narration_accepts_multilingual_sentence_terminators(
    narration: str,
) -> None:
    multilingual = {**_valid()}
    multilingual["steps"] = [dict(step) for step in _valid()["steps"]]
    multilingual["steps"][0]["narration"] = narration
    engine = _Engine([multilingual])

    project, repaired = plan_animation_project(engine, _request())

    assert project is not None and repaired is False
    assert project.scenes[0].narration == narration


def test_generated_narration_keeps_complete_sentence_and_drops_only_clipped_suffix() -> None:
    clipped = {**_valid()}
    clipped["steps"] = [dict(step) for step in _valid()["steps"]]
    clipped["steps"][0]["narration"] = (
        "When you perform the same operation on both sides of an equation, you're keeping the "
        "balance the same. This is because, "
    )
    clipped["steps"][1]["narration"] = (
        "For example, if you have 2x = 4 and you add 3 to both sides, you get 2x + 3 = 4 + 3, "
        "which simplifies to 2x + 3 = 7. The"
    )
    clipped["steps"][2]["narration"] = (
        "The equality is preserved because the operation doesn't change the value of the "
        "equation. It just adds the same value to"
    )
    engine = _Engine([clipped])

    project, repaired = plan_animation_project(engine, _request())

    assert project is not None and repaired is False
    assert [scene.narration for scene in project.scenes] == [
        (
            "When you perform the same operation on both sides of an equation, you're keeping the "
            "balance the same."
        ),
        (
            "For example, if you have 2x = 4 and you add 3 to both sides, you get 2x + 3 = 4 + 3, "
            "which simplifies to 2x + 3 = 7."
        ),
        "The equality is preserved because the operation doesn't change the value of the equation.",
    ]


def test_explicit_requested_step_count_is_enforced_during_bounded_repair() -> None:
    too_many = {**_valid()}
    too_many["steps"] = [dict(_valid()["steps"][index % 3]) for index in range(8)]
    engine = _Engine([too_many, _valid()])
    request = AnimationPlanRequest(
        student_id="learner",
        topic="Why equal operations preserve equality",
        level="secondary",
        concept="A balanced equation",
        requirements="Explain the idea in three clear steps.",
    )

    project, repaired = plan_animation_project(engine, request)

    assert project is not None and repaired is True
    assert len(project.scenes) == 3
    assert "step_count_mismatch" in engine.local.calls[1][0][1]["content"]
    first_schema = engine.local.calls[0][1]["response_format"]["json_schema"]
    assert first_schema["schema"]["properties"]["steps"]["minItems"] == 3
    assert first_schema["schema"]["properties"]["steps"]["maxItems"] == 3
    assert "Return exactly 3 steps" in engine.local.calls[0][0][0]["content"]
    assert "return-to-storyboard" in engine.local.calls[0][0][0]["content"]


@pytest.mark.parametrize(
    "requirements",
    [
        "Explain in one step.",
        "Explain in nine steps.",
        "Explain in 9 steps.",
        "Explain in ten steps.",
        "Explain in 12 scenes.",
        "Explain in -3 steps.",
        "Explain in −3 steps.",
        "Explain in 2.5 steps.",
        "Explain in .5 steps.",
        "Explain in 2/3 steps.",
        "Explain in 2e3 steps.",
        "Explain in twenty-three steps.",
        "Explain in twenty three steps.",
        "Explain in one hundred and three steps.",
        "Explain in minus three steps.",
        "Explain in −three steps.",
        "Explain in 0 steps.",
        "Explain in 1000 steps.",
        "Explain in three steps and then in two stages.",
    ],
)
def test_unsupported_or_conflicting_step_counts_fail_before_model_contact(
    requirements: str,
) -> None:
    engine = _Engine([_valid()])
    request = AnimationPlanRequest(
        student_id="learner",
        topic="A bounded process",
        level="secondary",
        requirements=requirements,
    )

    with pytest.raises(AnimationPlanBriefError, match="scene count|two to eight"):
        plan_animation_project(engine, request)
    assert engine.local.calls == []


@pytest.mark.parametrize("count", ["3", "three", "+3", "＋3"])
def test_hyphenated_requested_step_count_reaches_schema_and_postdecode_validation(count) -> None:
    engine = _Engine([_valid()])
    request = AnimationPlanRequest(
        student_id="learner",
        topic="A bounded process",
        level="secondary",
        requirements=f"Create a {count}-step explanation.",
    )

    project, repaired = plan_animation_project(engine, request)

    assert project is not None and repaired is False
    steps_schema = engine.local.calls[0][1]["response_format"]["json_schema"]["schema"][
        "properties"
    ]["steps"]
    assert steps_schema["minItems"] == steps_schema["maxItems"] == 3


@pytest.mark.parametrize(
    "narration",
    [
        "The measured value is 3.14 and the",
        "Increase to 1.5 and keep the",
        "Use 0.5 of the",
        "Use e.g. a diagram and the",
        "Use e.g.",
        "Dr. The",
    ],
)
def test_generated_sentence_prefix_recovery_never_uses_decimals_or_abbreviations(
    narration: str,
) -> None:
    incomplete = {**_valid()}
    incomplete["steps"] = [dict(step) for step in _valid()["steps"]]
    incomplete["steps"][0]["narration"] = narration
    engine = _Engine([incomplete])

    project, repaired = plan_animation_project(engine, _request())

    assert project is None and repaired is True
    assert len(engine.local.calls) == MAX_ANIMATION_PLAN_ATTEMPTS


def test_prefix_recovery_preserves_decimal_value_in_an_already_complete_sentence() -> None:
    candidate = _valid()
    candidate["steps"][0]["narration"] = "The measured mass is 2.5 kg. Add the"
    engine = _Engine([candidate])

    project, _ = plan_animation_project(engine, _request())

    assert project is not None
    assert project.scenes[0].narration == "The measured mass is 2.5 kg."


@pytest.mark.parametrize(
    "requirements",
    ["Use nine steps.", "Use −3 steps.", "Use 2.5 steps.", "Use twenty-three steps."],
)
def test_invalid_count_route_returns_422_and_releases_generation_admission(
    monkeypatch, requirements,
) -> None:
    class _ConnectedRequest:
        @staticmethod
        async def is_disconnected() -> bool:
            return False

    monkeypatch.setattr("orchestrator.gateway.routes.wait_for_engine_ready", lambda: None)
    engine = _Engine([_valid()])
    generations = GenerationManager(max_active=1)
    sessions = SessionManager(slots_count=1)
    request = _request().model_copy(update={"requirements": requirements})

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            animation_plan(
                _ConnectedRequest(),
                request,
                engine=engine,
                sessions=sessions,
                ladder=DegradationLadder(free_probe=lambda: 8 * 1024**3),
                generations=generations,
                caller="learner",
            )
        )
    assert raised.value.status_code == 422
    assert "two to eight" in raised.value.detail
    assert engine.local.calls == []
    assert generations.status()["running"] == 0
    assert all(not slot["busy"] for slot in sessions.status()["slots"])


@pytest.mark.parametrize(
    ("title", "narration"),
    [
        ("End of animation", "The lesson is complete."),
        ("Return to storyboard", "Now, let's return to the storyboard."),
        ("Summary", "Thank you for learning!"),
    ],
)
def test_model_meta_states_are_rejected_after_decode(title: str, narration: str) -> None:
    filler = {**_valid()}
    filler["steps"] = [dict(step) for step in _valid()["steps"]]
    filler["steps"][0] = {"title": title, "narration": narration}
    engine = _Engine([filler, _valid()])

    project, repaired = plan_animation_project(engine, _request())

    assert project is not None and repaired is True
    assert "meta_step" in engine.local.calls[1][0][1]["content"]


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
    event = threading.Event()
    event.set()
    engine = _Engine([_valid()])
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
