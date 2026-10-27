"""Bounded local-model authoring for lesson-animation process storyboards.

The model may choose inert teaching copy and an ordered sequence only.  It cannot author
browser source, markup, styles, URLs, expressions, or renderer instructions.  The gateway
validates a closed JSON schema, performs at most one structured repair, then constructs the
versioned project that the deterministic canvas player validates again in the browser.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.models import (
    AnimationPlanProject,
    AnimationPlanRequest,
    AnimationProcessData,
    AnimationProcessScene,
)
from runtime.chat import ChatEngine

log = logging.getLogger("muta.gateway.animation_planner")

MAX_ANIMATION_PLAN_ATTEMPTS = 2


def _is_explicit_function_request(request: AnimationPlanRequest) -> bool:
    value = "\n".join(
        part for part in (request.topic, request.concept or "", request.requirements or "") if part
    ).replace("π", "pi")
    if re.search(r"\b[yzsv]\s*=", value, re.IGNORECASE):
        return True
    return bool(
        re.search(
            r"\b(?:plot|graph|trace)\b[^\n;]{0,180}"
            r"(?:\b[a-z][a-z0-9]*\s*\(|\b[xt]\s*\^|\b[xt](?:\s*[+*/-]|\s*$))",
            value,
            re.IGNORECASE,
        )
    )


class _ProposalStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=140)
    narration: str = Field(min_length=1, max_length=120)


class _AnimationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=1, max_length=700)
    steps: list[_ProposalStep] = Field(min_length=2, max_length=8)


def animation_planner_schema() -> dict[str, Any]:
    """Return the closed llama.cpp JSON-schema response format."""
    return {
        "name": "muta_lesson_animation_plan",
        "strict": True,
        "schema": _AnimationProposal.model_json_schema(),
    }


def _decode_candidate(
    engine: ChatEngine,
    messages: list[dict[str, str]],
    *,
    cancel_event: threading.Event | None,
) -> tuple[object | None, str | None]:
    params = {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "seed": 4242,
        "max_tokens": 700,
        "enable_thinking": False,
        "response_format": {"type": "json_schema", "json_schema": animation_planner_schema()},
    }
    stream = None
    try:
        fitted_messages, fitted_params = engine._fit_request(
            messages, params, protected_tail_messages=1
        )
        client = getattr(engine.client, "local", engine.client)
        stream_params = dict(fitted_params)
        if cancel_event is not None:
            stream_params["_muta_cancel_event"] = cancel_event
        stream = client.stream_events(fitted_messages, **stream_params)
        chunks: list[str] = []
        for event, value in stream:
            if cancel_event is not None and cancel_event.is_set():
                return None, "cancelled"
            if event == "content" and value:
                chunks.append(value)
        try:
            return json.loads("".join(chunks)), None
        except (TypeError, json.JSONDecodeError):
            return None, "json_invalid"
    except Exception:
        log.warning("local lesson-animation planner failed", exc_info=True)
        return None, "planner_unavailable"
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()


def _proposal_errors(candidate: object) -> tuple[_AnimationProposal | None, list[dict[str, str]]]:
    try:
        proposal = _AnimationProposal.model_validate(candidate)
    except ValidationError as exc:
        errors = [
            {
                "code": "schema_invalid",
                "detail": ".".join(str(part) for part in item["loc"]) + ": " + item["msg"],
            }
            for item in exc.errors(include_url=False)[:8]
        ]
        return None, errors
    blank_fields = []
    if not proposal.title.strip():
        blank_fields.append("title")
    if not proposal.summary.strip():
        blank_fields.append("summary")
    for index, step in enumerate(proposal.steps):
        if not step.title.strip():
            blank_fields.append(f"steps.{index}.title")
        if not step.narration.strip():
            blank_fields.append(f"steps.{index}.narration")
    if blank_fields:
        return None, [
            {
                "code": "blank_text",
                "detail": "Visible text is required at: " + ", ".join(blank_fields),
            }
        ]
    normalized = [step.narration.strip().casefold() for step in proposal.steps]
    if len(set(normalized)) != len(normalized):
        return None, [
            {
                "code": "duplicate_step",
                "detail": "Every step must describe a distinct visible teaching state.",
            }
        ]
    return proposal, []


def _project_from_proposal(
    request: AnimationPlanRequest, proposal: _AnimationProposal
) -> AnimationPlanProject:
    now = datetime.now(UTC).isoformat()
    step_copy = [step.narration.strip() for step in proposal.steps]
    scenes = [
        AnimationProcessScene(
            id=f"step-{index + 1}",
            title=step.title.strip(),
            narration=step.narration.strip(),
            duration_ms=2600,
            data=AnimationProcessData(steps=step_copy, active=index),
        )
        for index, step in enumerate(proposal.steps)
    ]
    return AnimationPlanProject(
        id=f"lesson-{uuid.uuid4().hex[:20]}",
        title=proposal.title.strip(),
        topic=request.topic.strip(),
        level=request.level,
        summary=proposal.summary.strip(),
        created_at=now,
        updated_at=now,
        scenes=scenes,
    )


def plan_animation_project(
    engine: ChatEngine,
    request: AnimationPlanRequest,
    *,
    cancel_event: threading.Event | None = None,
) -> tuple[AnimationPlanProject | None, bool]:
    """Ask the installed local model for a safe ordered composition, repairing once."""
    if _is_explicit_function_request(request):
        # This planner can produce only prose process scenes. An unresolved explicit function must
        # stay unresolved rather than being converted into an authoritative-looking storyboard.
        return None, False
    system = (
        "Create one concise educational animation plan as JSON only. Follow the closed schema. "
        "Choose two to eight distinct visual teaching states in causal order. The renderer is "
        "a deterministic local process storyboard, so describe only what each state should teach. "
        "Do not emit code, HTML, JavaScript, Python, Manim, URLs, styles, colours, assets, renderer "
        "commands, or executable expressions. All strings are inert learner-facing text."
    )
    brief = (
        f"TOPIC: {request.topic}\nLEARNER LEVEL: {request.level}\n"
        f"CONCEPT: {request.concept or 'not separately specified'}\n"
        f"REQUIRED SEQUENCE: {request.requirements or 'choose the clearest causal sequence'}\n\n"
        "Preserve requested entities and order. Use age-appropriate wording. Return the complete plan."
    )
    errors: list[dict[str, str]] = []
    for attempt in range(MAX_ANIMATION_PLAN_ATTEMPTS):
        if cancel_event is not None and cancel_event.is_set():
            return None, attempt > 0
        user = brief
        if errors:
            user += (
                "\n\nThe previous proposal was rejected. Return a complete replacement. "
                "Structured validation errors:\n"
                + json.dumps(errors, ensure_ascii=False, separators=(",", ":"))
            )
        candidate, decode_error = _decode_candidate(
            engine,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            cancel_event=cancel_event,
        )
        if decode_error in {"cancelled", "planner_unavailable"}:
            return None, attempt > 0
        if decode_error:
            errors = [{"code": decode_error, "detail": "Return one valid JSON object only."}]
            continue
        proposal, errors = _proposal_errors(candidate)
        if proposal is not None:
            try:
                return _project_from_proposal(request, proposal), attempt > 0
            except ValidationError as exc:
                errors = [
                    {
                        "code": "project_invalid",
                        "detail": ".".join(str(part) for part in item["loc"])
                        + ": "
                        + item["msg"],
                    }
                    for item in exc.errors(include_url=False)[:8]
                ]
        log.info(
            "lesson-animation proposal rejected on attempt %d: %s",
            attempt + 1,
            ",".join(error["code"] for error in errors),
        )
    return None, True

