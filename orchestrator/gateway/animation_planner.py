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
_INCOMPLETE_SENTENCE_ENDING = re.compile(
    r"\b(?:a|an|the|and|or|but|because|to|of|with|by|for|from|as|at|in|on|into|"
    r"than|that|which|who|whose|your|their|its|this|these|those)$",
    re.IGNORECASE,
)
_SENTENCE_PUNCTUATION = frozenset(".!?…。！？؟۔")
_SENTENCE_CLOSERS = frozenset("\"'’”»›)]}")
_STEP_COUNT_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}


def _generated_narration_is_complete(value: str) -> bool:
    narration = value.strip()
    index = len(narration) - 1
    saw_sentence_punctuation = False
    while index >= 0 and narration[index] in _SENTENCE_PUNCTUATION | _SENTENCE_CLOSERS:
        if narration[index] in _SENTENCE_PUNCTUATION:
            saw_sentence_punctuation = True
        index -= 1
    lexical_ending = narration[: index + 1].rstrip()
    return (
        saw_sentence_punctuation
        and bool(lexical_ending)
        and _INCOMPLETE_SENTENCE_ENDING.search(lexical_ending) is None
    )


def _complete_generated_sentence_prefix(value: str) -> str:
    """Drop only a clipped suffix when the model already supplied a complete sentence."""
    narration = value.strip()
    if _generated_narration_is_complete(narration):
        return narration
    for punctuation_index in range(len(narration) - 1, -1, -1):
        if narration[punctuation_index] not in _SENTENCE_PUNCTUATION:
            continue
        end = punctuation_index + 1
        while end < len(narration) and narration[end] in _SENTENCE_CLOSERS:
            end += 1
        prefix = narration[:end].strip()
        if _generated_narration_is_complete(prefix):
            return prefix
    return narration


def _requested_step_count(request: AnimationPlanRequest) -> int | None:
    counts: set[int] = set()
    source = "\n".join(part for part in (request.topic, request.concept, request.requirements) if part)
    pattern = re.compile(
        r"\b(2|3|4|5|6|7|8|two|three|four|five|six|seven|eight)"
        r"(?:\s+(?:clear|distinct|ordered|simple|visual|animation))*"
        r"\s+(?:steps?|stages?|scenes?|states?)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(source):
        token = match.group(1).casefold()
        counts.add(int(token) if token.isdigit() else _STEP_COUNT_WORDS[token])
    return counts.pop() if len(counts) == 1 else None

_INTENT_SUPERSCRIPT = str.maketrans(
    {"⁻": "-", "⁺": "+", "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}
)


def _normalize_function_intent(value: str) -> str:
    normalized = value.translate(
        str.maketrans({"−": "-", "–": "-", "—": "-", "﹣": "-", "－": "-", "π": "pi"})
    )
    return re.sub(
        r"[⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹]+",
        lambda match: "^" + match.group(0).translate(_INTENT_SUPERSCRIPT),
        normalized,
    )


def _is_explicit_function_request(request: AnimationPlanRequest) -> bool:
    value = _normalize_function_intent(
        "\n".join(
            part
            for part in (request.topic, request.concept or "", request.requirements or "")
            if part
        )
    )
    if re.search(
        r"(?:^|[^\w])(?:[a-z]|[a-z][a-z0-9]*\s*\(\s*[a-z]\s*\))\s*=",
        value,
        re.IGNORECASE,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:plot|graph|trace)\b[^\n;]{0,180}"
            r"(?:\b[a-z][a-z0-9]*\s*\(|\b[xt]\s*"
            r"(?:\^|[+*/-]|(?:from|between|on|over|for)\b|$))",
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


def animation_planner_schema(requested_step_count: int | None = None) -> dict[str, Any]:
    """Return the closed llama.cpp JSON-schema response format."""
    schema = {
        "name": "muta_lesson_animation_plan",
        "strict": True,
        "schema": _AnimationProposal.model_json_schema(),
    }
    if requested_step_count is not None:
        steps = schema["schema"]["properties"]["steps"]
        steps["minItems"] = requested_step_count
        steps["maxItems"] = requested_step_count
    return schema


def _decode_candidate(
    engine: ChatEngine,
    messages: list[dict[str, str]],
    *,
    cancel_event: threading.Event | None,
    requested_step_count: int | None,
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
        "response_format": {
            "type": "json_schema",
            "json_schema": animation_planner_schema(requested_step_count),
        },
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


def _proposal_errors(
    candidate: object, *, requested_step_count: int | None = None
) -> tuple[_AnimationProposal | None, list[dict[str, str]]]:
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
    if requested_step_count is not None and len(proposal.steps) != requested_step_count:
        return None, [
            {
                "code": "step_count_mismatch",
                "detail": (
                    f"The brief requests exactly {requested_step_count} steps; "
                    f"the proposal supplied {len(proposal.steps)}."
                ),
            }
        ]
    for step in proposal.steps:
        step.narration = _complete_generated_sentence_prefix(step.narration)
    incomplete_fields = []
    for index, step in enumerate(proposal.steps):
        narration = step.narration.strip()
        if not _generated_narration_is_complete(narration):
            incomplete_fields.append(f"steps.{index}.narration")
    if incomplete_fields:
        return None, [
            {
                "code": "incomplete_sentence",
                "detail": (
                    "Each generated narration must be one complete sentence ending in punctuation; "
                    "rewrite rather than truncating: " + ", ".join(incomplete_fields)
                ),
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
    requested_step_count = _requested_step_count(request)
    system = (
        "Create one concise educational animation plan as JSON only. Follow the closed schema. "
        "Choose two to eight distinct visual teaching states in causal order. The renderer is "
        "a deterministic local process storyboard, so describe only what each state should teach. "
        "Write each narration as one complete age-appropriate sentence of 60 to 90 characters, "
        "ending with punctuation. Finish the sentence well before the 120-character schema limit. "
        "Do not add thank-you, end-screen, return-to-storyboard, or interface/meta states. "
        "Do not emit code, HTML, JavaScript, Python, Manim, URLs, styles, colours, assets, renderer "
        "commands, or executable expressions. All strings are inert learner-facing text."
    )
    if requested_step_count is not None:
        system += f" Return exactly {requested_step_count} steps as required by the brief."
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
            requested_step_count=requested_step_count,
        )
        if decode_error in {"cancelled", "planner_unavailable"}:
            return None, attempt > 0
        if decode_error:
            errors = [{"code": decode_error, "detail": "Return one valid JSON object only."}]
            continue
        proposal, errors = _proposal_errors(
            candidate, requested_step_count=requested_step_count
        )
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

