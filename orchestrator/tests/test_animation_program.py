"""Model-to-Manim tests; malicious test programs are parsed, NEVER executed."""

from __future__ import annotations

import json
import math
import re
import threading
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from contracts.models import AnimationProgramRequest
from orchestrator.gateway.animation_program import (
    AnimationProgramError,
    author_manim_program,
    isolated_program_capability,
    program_origin,
    render_authored_program,
    source_hash,
    validate_manim_program,
)


def source(body: str) -> str:
    return (
        "from manim import *\nimport numpy as np\n\nclass MutaLesson(Scene):\n    def construct(self):\n"
        + "\n".join("        " + line for line in body.splitlines())
        + "\n"
    )


VALID = source("c = Circle(radius=2, color=TEAL)\nself.play(Create(c), run_time=2)\nself.wait(1)")


@pytest.mark.parametrize(
    "body",
    [
        "a = Axes(x_range=[-3,3,1], y_range=[-4,4,1])\ng = a.plot(lambda x: x**3, color=BLUE)\nself.play(Create(g), run_time=2)",
        "a = Axes(x_range=[-3,3,1])\ng = a.plot(lambda x: np.sin(x), color=BLUE)\nself.play(Create(g), run_time=2)",
        "items = VGroup(*[Dot(np.array([i, 0, 0])) for i in range(8)])\nself.play(FadeIn(items), run_time=2)",
        'r = 5.6\nc = Circle(radius=r)\nt = Text(f"Radius {r:.2f}", font_size=32)\nself.play(Create(c), Write(t), run_time=3)',
        "s = Surface(lambda u, v: np.array([u, v, np.sin(u)]), u_range=[-2,2], v_range=[-2,2], resolution=(12,12))\nself.play(Create(s), run_time=2)",
        "a = Dot(LEFT)\nb = Dot(RIGHT)\nself.play(Transform(a, b), run_time=2)\nself.wait(duration=1)",
        "q = 12 // 3\nr = 12 % 3\nitems = VGroup(*[Dot() for _ in range(q)])\nself.play(Create(items),run_time=2)",
        "xs = np.linspace(-3.14,3.14,1000)\nys = np.sin(xs)\naxes = Axes(x_range=[-3.14,3.14,1])\ncurve = axes.plot(lambda x:np.sin(x))\nself.play(Create(curve),run_time=2)",
    ],
)
def test_actual_composable_manim_programs_pass_without_scene_family_matching(body):
    assert validate_manim_program(source(body)) == source(body)


@pytest.mark.parametrize("step", [0.01, 0, -1])
def test_range_repair_feedback_identifies_call_and_preserves_domain(step):
    candidate = source(
        "axes = Axes(x_range=[-3.14,3.14,1])\n"
        f"curve = axes.plot(lambda x: np.sin(x), x_range=[-3.14,3.14,{step}])\n"
        "self.play(Create(curve), run_time=2)"
    )
    with pytest.raises(AnimationProgramError) as rejected:
        validate_manim_program(candidate)
    message = str(rejected.value)
    assert "at most 256 intervals" in message
    assert f"axes.plot has x_range=[-3.14, 3.14, {step}]" in message
    assert f"at least {math.nextafter(6.28 / 256, math.inf)!r}" in message
    assert "omit the third value: x_range=[-3.14, 3.14]" in message
    assert "Keep the original endpoints and equation" in message


def test_range_repair_does_not_recommend_an_invalid_default_step_span():
    candidate = source("axes = Axes(x_range=[-100,100,0.1])")
    with pytest.raises(AnimationProgramError) as rejected:
        validate_manim_program(candidate)
    assert "Axes has x_range=[-100, 100, 0.1]" in str(rejected.value)
    assert "omit" not in str(rejected.value)


def test_range_interval_limit_is_unchanged_and_source_is_not_rewritten():
    candidate = source("axes = Axes(x_range=[0,256,1])\nself.play(Create(axes),run_time=2)")
    assert validate_manim_program(candidate) == candidate
    with pytest.raises(AnimationProgramError, match="at most 256 intervals"):
        validate_manim_program(source("axes = Axes(x_range=[0,257,1])"))


@pytest.mark.parametrize("end", ["1/3", "PI", "0.1", "3.14"])
def test_reported_minimum_range_step_round_trips_with_original_endpoints(end):
    with pytest.raises(AnimationProgramError) as rejected:
        validate_manim_program(source(f"axes = Axes(x_range=[0,{end},0.0001])"))
    message = str(rejected.value)
    minimum = re.search(r"step at least ([^ ]+)", message).group(1)
    candidate = source(
        f"axes = Axes(x_range=[0,{end},{minimum}])\nself.play(Create(axes),run_time=2)"
    )
    assert validate_manim_program(candidate) == candidate
    if end == "1/3":
        assert "x_range=[0, 1 / 3]" in message


@pytest.mark.parametrize(
    "body",
    [
        'open("/tmp/canary").read()',
        'import os\nos.system("id")',
        "x = self.renderer.file_writer",
        "x = Circle().__class__",
        'x = getattr(self, "renderer")',
        'exec("print(1)")',
        'self.add_sound("/tmp/canary")',
        'x = ImageMobject("/tmp/canary")',
        "self.camera.background_color = RED",
        "config.pixel_width = 10000",
        "while True:\n    self.wait(1)",
        'a = np.array([0], dtype="U1000000000")',
        'a = np.array(["canary"])',
        "Text(str(1) * (10000 ** 6))",
        's = ["x"][0]\nText(s * (10000 ** 6))',
        "n = 10000**6\nfor i in range(64):\n    n = n**6",
        'n = 1\nfor i in range(64):\n    n = n*64\nfor j in range(n):\n    Text("ok")',
        'n = 1\nfor n in range(64):\n    Text("ok")\nfor i in range(n**6):\n    Text("ok")',
        "for i in range(64):\n    Text(str((i**6)**6))",
        "Axes().plot(lambda x: str(x) * (10000 ** 6))",
        "x = 6\nAxes().plot(lambda x: x**x, x_range=[1,10000])",
        'MathTypst("x", template="#read("/tmp/canary")")',
        'MathTypst(text="#read("/tmp/canary")")',
        'MathTypst("#read("/tmp/canary")")',
        'Text(f"{1:1000000000}")',
        "self.wait(duration=10000 ** 6)",
        "self.play(Wait(10000 ** 6), run_time=1)",
        "self.play(Create(Circle(), run_time=8))",
        "NumberLine([-1000,1000,.000001])",
        "Sphere(1, (10000,10000))",
        "RegularPolygon(10000)",
        "n = " + "9" * 400,
        "ParametricFunction(lambda t: np.array([t,0,0]), [0,1,1e-100])",
        "Axes().plot(lambda x:x, [0,1,1e-100])",
        "Axes().plot(*[lambda x:x, [0,1,1e-100]])",
        "Sphere(*[ORIGIN,1,(10000,10000)])",
        "DashedLine(ORIGIN,RIGHT,dash_length=1e-100)",
        "Arc(0,1,1,10000)",
        "Flash(ORIGIN, 1, 10000)",
        's = str("' + "x" * 800 + '")\nv = [s for s in range(1)]\nText(s * (10000 * 100))',
        "s = max([[0,0,0]])\nv = [s for s in range(1)]\nText(str(s * (10000 * 100)))",
        "a = max([[0,0]])\nb = np.array([a,a])",
        "a = VGroup(Dot())\nb = VGroup(*[a.copy() for i in range(64)])",
        "a = VGroup()\nb = VGroup(a)\na.add(b)",
        "a = np.linspace(0,1,10000)",
        "a = np.array([[1,2],[3,4]])\nb = np.array([a[0],a[0]])",
        "a = np.array([1,2,3])\nb = a[:,None]",
    ],
)
def test_malicious_and_over_budget_source_rejected_before_any_execution(body):
    with pytest.raises(AnimationProgramError):
        validate_manim_program(source(body + '\nText("ok")\nself.wait(1)'))


def test_cumulative_object_and_timeline_limits():
    with pytest.raises(AnimationProgramError):
        validate_manim_program(
            source("for i in range(64):\n    for j in range(64):\n        Dot()\nself.wait(1)")
        )
    with pytest.raises(AnimationProgramError):
        validate_manim_program(
            source("for i in range(16):\n    self.play(Create(Circle()), run_time=8)")
        )


@pytest.mark.parametrize(
    "expression",
    [
        "2*np.sin(x)",
        "np.sin(x)+1",
        "x/2+1",
        "1/(1+x**2)",
        "4*np.exp(-x**2/4)*np.sin(2*x)",
        "np.sqrt(x**2+1)",
    ],
)
def test_ordinary_transformed_curves_use_conservative_arithmetic_intervals(expression):
    candidate = source(
        f"axes=Axes(x_range=[-3,3,1])\ncurve=axes.plot(lambda x:{expression})\nself.play(Create(curve),run_time=2)"
    )
    assert validate_manim_program(candidate) == candidate


def test_multiline_brief_remains_complete_but_display_title_is_single_line():
    program = author_manim_program(
        Engine(),
        request().model_copy(
            update={
                "topic": "Draw a circle\nLabel its radius",
                "concept": "Keep full\nmultiline brief",
            }
        ),
    )
    assert program.title == "Draw a circle Label its radius"
    assert json.loads(program.brief)["concept"] == "Keep full\nmultiline brief"


class Client:
    model = "local-test-model"

    def __init__(self, candidate=VALID):
        self.candidate = candidate
        self.calls = []

    def stream_events(self, messages, **params):
        self.calls.append((messages, params))
        yield "content", self.candidate


class Engine:
    def __init__(self, candidate=VALID):
        self.local = Client(candidate)
        self.client = SimpleNamespace(local=self.local)

    @staticmethod
    def _fit_request(messages, params, *, protected_tail_messages):
        assert protected_tail_messages in {1, 3}
        return messages, params


def request(**overrides):
    return AnimationProgramRequest(
        student_id="learner",
        topic="Lesson animation",
        level="secondary",
        concept="draw a circle with radius 5.6",
        **overrides,
    )


def test_every_prompt_reaches_local_model_and_source_is_not_substituted():
    engine = Engine()
    program = author_manim_program(engine, request())
    assert len(engine.local.calls) == 1
    assert "5.6" in json.dumps(engine.local.calls[0][0])
    assert "Axis ticks are not plotting samples" in engine.local.calls[0][0][-1]["content"]
    assert program.source == VALID  # Even this intentionally different stub source is not replaced.
    assert program.source_sha256 == source_hash(VALID)
    assert program.model_id == "local-test-model"
    assert program_origin(program) == "local-model"
    assert (
        program_origin(program.model_copy(update={"source": VALID + "# edited\n"}))
        == "saved-or-imported"
    )
    assert program_origin(program.model_copy(update={"model_id": "forged"})) == "saved-or-imported"
    assert (
        program_origin(program.model_copy(update={"generation_token": "é"})) == "saved-or-imported"
    )
    with pytest.raises(ValidationError):
        type(program).model_validate({**program.model_dump(), "generation_token": "é"})


def test_fenced_source_is_unwrapped_not_rewritten():
    program = author_manim_program(Engine(f"```python\n{VALID}```"), request())
    assert program.source == VALID


def test_derived_display_title_does_not_duplicate_the_model_instruction():
    engine = Engine()
    concept = "Plot y = sin(x)\nfrom -3.14 to 3.14"
    topic = " ".join(concept.split())
    program = author_manim_program(
        engine, request().model_copy(update={"topic": topic, "concept": concept})
    )
    final_prompt = engine.local.calls[0][0][-1]["content"]
    assert f"Prompt: {concept}" in final_prompt
    assert f"Topic: {topic}" not in final_prompt
    assert program.title == topic
    assert json.loads(program.brief)["concept"] == concept
    assert json.loads(program.brief)["topic"] == topic


def test_validation_diagnostic_retains_model_source_for_bounded_repair():
    candidate = source('open("/tmp/canary")')
    with pytest.raises(AnimationProgramError) as raised:
        author_manim_program(Engine(candidate), request())
    assert raised.value.source == candidate.strip()
    engine = Engine()
    author_manim_program(
        engine, request(previous_source=candidate, feedback="File access is not permitted")
    )
    assert candidate == engine.local.calls[0][0][-2]["content"]
    assert "File access is not permitted" in engine.local.calls[0][0][-1]["content"]


def test_cancelled_authoring_does_not_call_model():
    event = threading.Event()
    event.set()
    engine = Engine()
    with pytest.raises(AnimationProgramError, match="cancelled"):
        author_manim_program(engine, request(), cancel_event=event)
    assert engine.local.calls == []


def test_unproven_sandbox_fails_closed_and_never_executes_source(monkeypatch):
    from orchestrator.gateway import animation_program as module

    monkeypatch.setattr(
        module,
        "isolated_program_capability",
        lambda **_kwargs: {"available": False, "detail": "No proven sandbox"},
    )
    program = author_manim_program(Engine(), request())
    with pytest.raises(AnimationProgramError, match="No proven sandbox"):
        render_authored_program(program)
    with pytest.raises(AnimationProgramError, match="hash"):
        render_authored_program(program.model_copy(update={"source_sha256": "0" * 64}))


def test_capability_is_explicitly_separate_from_legacy_renderer(monkeypatch):
    from orchestrator.gateway import animation_render

    monkeypatch.setattr(
        animation_render,
        "manim_capability",
        lambda: SimpleNamespace(available=False, executable=None, detail="Worker absent"),
    )
    assert isolated_program_capability() == {"available": False, "detail": "Worker absent"}
