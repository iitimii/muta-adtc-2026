"""Security, semantic and worker tests for trusted Manim lesson rendering."""

from __future__ import annotations

import ast
import os
import sys
import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.models import AnimationPlanProject
from orchestrator.gateway import animation_render, animation_worker
from orchestrator.gateway.animation_render import (
    AnimationRenderBusyError,
    AnimationRenderError,
    emit_manim_source,
    render_manim_video,
)


def _project(scenes: list[dict]) -> AnimationPlanProject:
    return AnimationPlanProject.model_validate(
        {
            "id": "lesson-trusted-render",
            "title": "Maths in motion",
            "topic": "Fractions, arrays, functions and vectors",
            "level": "secondary",
            "summary": "A deterministic visual lesson.",
            "created_at": "2026-10-27T00:00:00Z",
            "updated_at": "2026-10-27T00:00:00Z",
            "scenes": scenes,
        }
    )


def _scene(identifier: str, kind: str, data: dict, **copy: str) -> dict:
    return {
        "id": identifier,
        "kind": kind,
        "title": copy.get("title", identifier.replace("-", " ").title()),
        "narration": copy.get("narration", "Follow the mathematical representation."),
        "duration_ms": 900,
        "data": data,
    }


def _function(mode: str = "curve") -> dict:
    data = {
        "expression_ast": {
            "type": "binary",
            "op": "^",
            "left": {"type": "variable", "name": "x"},
            "right": {"type": "number", "value": 3},
        },
        "expression_text": "x^3",
        "domain": [-3, 3],
        "variable": "x",
        "output": "y",
        "mode": mode,
    }
    if mode == "derivative":
        data["parameter"] = 2
    elif mode == "integral":
        data["bounds"] = [-1, 2]
    return data


def test_emitter_covers_parameterised_math_and_process_families() -> None:
    project = _project(
        [
            _scene("fraction", "fraction", {"numerator": 3, "denominator": 4, "phase": "shade"}),
            _scene("array", "array", {"rows": 6, "columns": 4, "phase": "equation"}),
            _scene("curve", "function", _function()),
            _scene("derivative", "function", _function("derivative")),
            _scene("integral", "function", _function("integral")),
            _scene("vector", "vector", {"x": 3, "y": 4, "label": "force"}),
            _scene(
                "process",
                "process",
                {"steps": ["Set up the model", "Apply the rule"], "active": 1},
            ),
        ]
    )
    source = emit_manim_source(project)
    compile(source, "lesson.py", "exec")
    assert "class MutaLesson(Scene)" in source
    assert "3/4" in source and "6 times 4 = 24" in source
    assert "curve_segments" in source and "tangent" in source and "area = Polygon" in source
    assert "Arrow(" in source and "Apply the rule" in source
    assert source.count("self.play(scene_intro") == len(project.scenes)
    assert "number_labels = VGroup()" in source and "domain: -3 to 3" in source
    assert "MathTypst('y = x^3'" in source
    assert "LaggedStart(*[Create(cell)" in source
    assert "LaggedStart(*[FadeIn(dot" in source
    assert "scale_to_fit_width" not in source


def test_model_text_is_inert_and_never_becomes_import_or_call_syntax() -> None:
    attack = "'); __import__('os').system('touch /tmp/pwned') #\nAwait f(x)"
    source = emit_manim_source(
        _project(
            [
                _scene(
                    "process",
                    "process",
                    {"steps": [attack.replace("\n", " "), "Finish safely"], "active": 0},
                    title=attack,
                    narration=attack,
                )
            ]
        )
    )
    tree = ast.parse(source)
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 2
    assert {node.module if isinstance(node, ast.ImportFrom) else node.names[0].name for node in imports} == {"manim", "math"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"eval", "exec", "compile", "__import__"}
        for node in ast.walk(tree)
    )
    assert attack in [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)]


def test_long_copy_is_wrapped_without_scaling_short_process_labels_up() -> None:
    long_caption = "A full learner transcript remains available while this visible caption " * 9
    source = emit_manim_source(
        _project(
            [
                _scene(
                    "process",
                    "process",
                    {"steps": ["Heat", "Observe the temperature change carefully"], "active": 0},
                    title=(
                        "A deliberately long scene title that must wrap inside the video frame "
                        "while preserving every requested concept and remaining legible"
                    ),
                    narration=long_caption,
                )
            ]
        )
    )
    assert repr(long_caption) in source
    assert "…" in source and "_fit(label_0, 9.8, 0.48)" in source
    assert "scale_to_fit_width" not in source


@pytest.mark.parametrize("step", ["x" * 121, "   ", "Line one\nLine two", "bad\x00step"])
def test_process_step_import_rejects_oversized_empty_or_control_text(step: str) -> None:
    with pytest.raises(ValidationError):
        _project(
            [
                _scene(
                    "process",
                    "process",
                    {"steps": [step, "Finish safely"], "active": 0},
                )
            ]
        )


@pytest.mark.parametrize(
    "expression",
    [
        {"type": "variable", "name": "y"},
        {"type": "call", "name": "system", "args": [{"type": "number", "value": 1}]},
        {"type": "python", "source": "open('/tmp/pwned','w')"},
    ],
)
def test_invalid_or_undeclared_expression_ast_fails_closed(expression: dict) -> None:
    data = _function(); data["expression_ast"] = expression
    with pytest.raises(AnimationRenderError):
        emit_manim_source(_project([_scene("curve", "function", data)]))


def test_function_mode_contract_rejects_inconsistent_calculus_fields() -> None:
    data = _function(); data["parameter"] = 2
    with pytest.raises(ValidationError, match="curve scenes"):
        _project([_scene("curve", "function", data)])


def test_backend_rejects_false_derivatives_divergent_integrals_and_mismatched_copy() -> None:
    absolute = {
        "expression_ast": {
            "type": "call",
            "name": "abs",
            "args": [{"type": "variable", "name": "x"}],
        },
        "expression_text": "abs(x)",
        "domain": [-2, 2],
        "variable": "x",
        "output": "y",
        "mode": "derivative",
        "parameter": 0,
    }
    with pytest.raises(AnimationRenderError, match="derivative is undefined"):
        emit_manim_source(_project([_scene("cusp", "function", absolute)]))

    pole = {
        "expression_ast": {
            "type": "binary",
            "op": "/",
            "left": {"type": "number", "value": 1},
            "right": {
                "type": "binary",
                "op": "-",
                "left": {"type": "variable", "name": "x"},
                "right": {"type": "number", "value": 0.123},
            },
        },
        "expression_text": "1/(x-0.123)",
        "domain": [0, 1],
        "variable": "x",
        "output": "y",
        "mode": "integral",
        "bounds": [0, 1],
    }
    with pytest.raises(AnimationRenderError, match="integral does not converge"):
        emit_manim_source(_project([_scene("pole", "function", pole)]))

    mismatch = _function()
    mismatch["expression_text"] = "999*x"
    with pytest.raises(AnimationRenderError, match="typed expression must agree"):
        emit_manim_source(_project([_scene("mismatch", "function", mismatch)]))


def test_bounded_worker_invokes_fixed_cli_and_returns_real_mp4_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    executable = tmp_path / "manim"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    observed: dict = {}

    def fake_run(command, *, cwd, environment, cancel_event=None):
        observed["command"] = command
        observed["cwd"] = cwd
        observed["environment"] = environment
        media = Path(command[command.index("--media_dir") + 1])
        output = media / "videos" / "lesson" / "480p15" / "MutaLesson.mp4"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42trusted-video")
        return b"rendered"

    monkeypatch.setenv("MUTA_MANIM_BIN", str(executable))
    monkeypatch.setattr(animation_render, "_run_manim_process", fake_run)
    video = render_manim_video(
        _project([_scene("array", "array", {"rows": 2, "columns": 3, "phase": "build"})])
    )
    assert video.endswith(b"trusted-video")
    command = observed["command"]
    assert command[0].endswith("python")
    assert command[1].endswith("animation_worker.py")
    assert command[2:8] == [str(executable), "--silent", "-qm", "--format", "mp4", "--disable_caching"]
    assert command[-1] == "MutaLesson"
    assert "http_proxy" not in observed["environment"]


@pytest.mark.parametrize(
    ("expression_text", "expression_ast", "parameter"),
    [
        (
            "x^2",
            {
                "type": "binary",
                "op": "^",
                "left": {"type": "variable", "name": "x"},
                "right": {"type": "number", "value": 2},
            },
            0,
        ),
        (
            "sin(x)",
            {"type": "call", "name": "sin", "args": [{"type": "variable", "name": "x"}]},
            1.5707963267948966,
        ),
    ],
)
def test_backend_accepts_valid_stationary_derivatives(
    expression_text: str, expression_ast: dict, parameter: float
) -> None:
    data = {
        "expression_ast": expression_ast,
        "expression_text": expression_text,
        "domain": [-2, 2],
        "variable": "x",
        "output": "y",
        "mode": "derivative",
        "parameter": parameter,
    }
    assert "tangent" in emit_manim_source(_project([_scene("stationary", "function", data)]))


def test_typst_formula_is_educational_copy_not_raw_ast_dump() -> None:
    data = {
        "expression_ast": {
            "type": "binary",
            "op": "/",
            "left": {
                "type": "binary",
                "op": "+",
                "left": {"type": "variable", "name": "x"},
                "right": {"type": "number", "value": 1},
            },
            "right": {
                "type": "binary",
                "op": "-",
                "left": {"type": "variable", "name": "x"},
                "right": {"type": "number", "value": 1},
            },
        },
        "expression_text": "(x+1)/(x-1)",
        "domain": [-3, 3],
        "variable": "x",
        "output": "y",
        "mode": "curve",
    }
    source = emit_manim_source(_project([_scene("fraction-function", "function", data)]))
    assert "MathTypst('y = frac(x + 1, x - 1)'" in source


def test_worker_timeout_is_reported_without_fallback_artifact(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "manim"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    monkeypatch.setenv("MUTA_MANIM_BIN", str(executable))

    def timeout(*args, **kwargs):
        raise AnimationRenderError("Manim render exceeded the offline time budget")

    monkeypatch.setattr(animation_render, "_run_manim_process", timeout)
    with pytest.raises(AnimationRenderError, match="time budget"):
        render_manim_video(
            _project([_scene("array", "array", {"rows": 2, "columns": 3, "phase": "build"})])
        )


def test_second_render_is_rejected_instead_of_forming_an_unbounded_queue(
    monkeypatch, tmp_path: Path
) -> None:
    executable = tmp_path / "manim"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    monkeypatch.setenv("MUTA_MANIM_BIN", str(executable))
    project = _project(
        [_scene("array", "array", {"rows": 2, "columns": 3, "phase": "build"})]
    )
    animation_render._render_lock.acquire()
    try:
        with pytest.raises(AnimationRenderBusyError, match="already in progress"):
            render_manim_video(project)
    finally:
        animation_render._render_lock.release()


def test_frozen_gateway_uses_explicit_worker_dispatch_without_source_python(
    monkeypatch, tmp_path: Path
) -> None:
    gateway = tmp_path / "muta-gateway"
    gateway.write_text("frozen gateway")
    gateway.chmod(0o755)
    monkeypatch.setattr(animation_render.sys, "frozen", True, raising=False)
    monkeypatch.setattr(animation_render.sys, "executable", str(gateway))
    monkeypatch.delenv("MUTA_ANIMATION_WORKER_BIN", raising=False)
    command = animation_render._animation_worker_command(["/runtime/bin/manim", "--silent"])
    assert command == [
        str(gateway),
        "--animation-worker",
        "/runtime/bin/manim",
        "--silent",
    ]
    assert "animation_worker.py" not in " ".join(command)


def test_fraction_shading_preserves_post_layout_geometry_and_uses_graphite_stage() -> None:
    source = emit_manim_source(
        _project(
            [
                _scene(
                    "fraction-shade",
                    "fraction",
                    {"numerator": 3, "denominator": 4, "phase": "shade"},
                )
            ]
        )
    )
    assert "self.camera.background_color = '#181715'" in source
    assert "UpdateFromAlphaFunc(shade_group" in source
    assert ".animate.set_fill" not in source


def test_small_coefficients_use_unambiguous_scientific_typst_and_same_numeric_ast() -> None:
    data = _function()
    data["expression_text"] = "0.000001*x"
    data["expression_ast"] = {
        "type": "binary",
        "op": "*",
        "left": {"type": "number", "value": 0.000001},
        "right": {"type": "variable", "name": "x"},
    }
    source = emit_manim_source(_project([_scene("small", "function", data)]))
    assert "y = 1 times 10^(-6) dot x" in source
    assert "MathTypst('y = 1e-06" not in source
    assert "axes.c2p(1.0, 1e-06)" in source


def test_worker_dispatch_strips_fixed_mode_before_exec(monkeypatch, tmp_path: Path) -> None:
    manim = tmp_path / "manim"
    manim.write_text("worker")
    manim.chmod(0o755)
    observed: dict = {}

    def fake_execve(executable, arguments, environment):
        observed.update(executable=executable, arguments=arguments, environment=environment)
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(animation_worker.os, "execve", fake_execve)
    monkeypatch.setattr(animation_worker, "_install_limits", lambda: None)
    with pytest.raises(RuntimeError, match="intercepted"):
        animation_worker.main(["--animation-worker", str(manim), "--silent"])
    assert observed["executable"] == str(manim)
    assert observed["arguments"] == [str(manim), "--silent"]


def test_cancel_event_stops_the_render_process_group_promptly(tmp_path: Path) -> None:
    cancelled = threading.Event()
    cancelled.set()
    started = time.monotonic()
    with pytest.raises(AnimationRenderError, match="was cancelled"):
        animation_render._run_manim_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=cancelled,
        )
    assert time.monotonic() - started < 2
