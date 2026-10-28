"""Legacy typed-project Manim source generation and bounded offline rendering.

This legacy path accepts only closed project models in ``contracts.models`` and converts
those validated values into fixed Manim constructs. New Studio model-written Python uses
``animation_program`` and the separate fail-closed ``animation_sandbox``, never this emitter.
Proposal-controlled strings are emitted with ``repr`` and reach only Manim ``Text`` objects.
"""

from __future__ import annotations

import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.models import AnimationCircleScene, AnimationFunctionScene, AnimationPlanProject
from orchestrator.gateway.visualization_v2 import (
    VisualizationV2Error,
    evaluate_expression_v2,
    parse_expression_v2,
)

MAX_SOURCE_BYTES = 256 * 1024
MAX_VIDEO_BYTES = 96 * 1024 * 1024
MAX_AST_NODES = 96
MAX_AST_DEPTH = 12
RENDER_TIMEOUT_SECONDS = 150

_render_lock = threading.Lock()
_UNARY = frozenset(
    {"abs", "acos", "asin", "atan", "cos", "cosh", "exp", "ln", "log", "sin", "sinh", "sqrt", "tan", "tanh"}
)
_BINARY = frozenset({"atan2", "min", "max"})


class AnimationRenderError(RuntimeError):
    """A safe source or render request could not be completed."""


class AnimationRenderBusyError(AnimationRenderError):
    """The single bounded offline render slot is already occupied."""


@dataclass(frozen=True)
class ManimCapability:
    available: bool
    executable: str | None
    detail: str


def _python_text(value: str) -> str:
    """Return an inert Python string literal, never executable source."""
    return repr(str(value))


def _wrapped_text(value: str, *, width: int, limit: int | None = None) -> str:
    clean = " ".join(str(value).split())
    if limit is not None and len(clean) > limit:
        clean = clean[: max(1, limit - 1)].rstrip() + "…"
    lines = textwrap.wrap(clean, width=width, break_long_words=False, break_on_hyphens=False)
    return "\n".join(lines) or clean


def _finite(value: float) -> str:
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1e9:
        raise AnimationRenderError("animation number is outside the trusted render budget")
    return repr(number)


def _tick_label(value: float) -> str:
    if abs(value) < 1e-10:
        return "0"
    return f"{value:.3g}"


def _circle_radius_label(value: float) -> str:
    """Mirror the browser's exact, bounded six-decimal circle representation."""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _expression_typst(
    node: dict[str, Any], variable: str, *, depth: int = 0, budget: list[int] | None = None
) -> str:
    """Compile the allow-listed typed AST into non-executable MathTypst notation."""
    if budget is None:
        budget = [0]

    def typst_number(number: float) -> str:
        if number.is_integer():
            return str(int(number))
        rendered = f"{number:.15g}"
        if "e" not in rendered.lower():
            return rendered
        mantissa, exponent = rendered.lower().split("e", maxsplit=1)
        return f"({mantissa} times 10^({int(exponent)}))"

    def compile_node(value: dict[str, Any], level: int) -> tuple[str, int, str]:
        budget[0] += 1
        if budget[0] > MAX_AST_NODES or level > MAX_AST_DEPTH or not isinstance(value, dict):
            raise AnimationRenderError("function expression exceeds the trusted AST budget")
        kind = value.get("type")
        if kind == "number" and set(value) == {"type", "value"}:
            number = float(value["value"])
            if not math.isfinite(number) or abs(number) > 1e9:
                raise AnimationRenderError("animation number is outside the trusted render budget")
            return typst_number(number), 6, "number"
        if kind == "constant" and set(value) == {"type", "name"}:
            if value["name"] not in {"pi", "e"}:
                raise AnimationRenderError("unsupported function constant")
            return str(value["name"]), 6, "constant"
        if kind == "variable" and set(value) == {"type", "name"}:
            if value["name"] != variable:
                raise AnimationRenderError("function expression uses an undeclared variable")
            return variable, 6, "variable"
        if kind == "unary" and set(value) == {"type", "op", "arg"} and value["op"] == "-":
            argument, precedence, _argument_kind = compile_node(value["arg"], level + 1)
            if precedence < 4:
                argument = f"({argument})"
            return f"-{argument}", 4, "unary"
        if kind == "binary" and set(value) == {"type", "op", "left", "right"}:
            operator = value["op"]
            if operator not in {"+", "-", "*", "/", "^"}:
                raise AnimationRenderError("unsupported function operator")
            left, left_precedence, left_kind = compile_node(value["left"], level + 1)
            right, right_precedence, right_kind = compile_node(value["right"], level + 1)
            if operator == "/":
                return f"frac({left}, {right})", 6, "fraction"
            precedence = {"+": 1, "-": 1, "*": 2, "^": 5}[operator]
            if left_precedence < precedence or (operator == "^" and left_kind == "binary-power"):
                left = f"({left})"
            right_needs_group = right_precedence < precedence
            if operator in {"-", "^"} and right_precedence == precedence:
                right_needs_group = True
            if operator == "*" and right_kind == "binary-product":
                right_needs_group = True
            if right_needs_group:
                right = f"({right})"
            symbol = " dot " if operator == "*" else f" {operator} " if operator != "^" else "^"
            result_kind = "binary-power" if operator == "^" else "binary-product" if operator == "*" else "binary"
            return f"{left}{symbol}{right}", precedence, result_kind
        if kind == "call" and set(value) == {"type", "name", "args"}:
            name = value["name"]
            args = value["args"]
            expected = 2 if name in _BINARY else 1 if name in _UNARY else 0
            if not isinstance(args, list) or len(args) != expected:
                raise AnimationRenderError("unsupported function call")
            compiled = [compile_node(argument, level + 1)[0] for argument in args]
            return f"{name}({', '.join(compiled)})", 6, "call"
        raise AnimationRenderError("invalid typed function expression")

    result, _precedence, _kind = compile_node(node, depth)
    return result


def _expression_variables(node: dict[str, Any], output: set[str] | None = None) -> set[str]:
    output = output if output is not None else set()
    kind = node.get("type")
    if kind == "variable":
        output.add(str(node.get("name")))
    elif kind == "unary" and isinstance(node.get("arg"), dict):
        _expression_variables(node["arg"], output)
    elif kind == "binary":
        for side in ("left", "right"):
            if isinstance(node.get(side), dict):
                _expression_variables(node[side], output)
    elif kind == "call" and isinstance(node.get("args"), list):
        for argument in node["args"]:
            if isinstance(argument, dict):
                _expression_variables(argument, output)
    return output


def _function_value(scene: AnimationFunctionScene, argument: float) -> float | None:
    try:
        result = evaluate_expression_v2(scene.data.expression_ast, {scene.data.variable: argument})
    except (VisualizationV2Error, KeyError, TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and abs(result) <= 1e10 else None


def _checked_derivative(scene: AnimationFunctionScene) -> float:
    data = scene.data
    assert data.parameter is not None
    centre = _function_value(scene, data.parameter)
    if centre is None:
        raise AnimationRenderError("the derivative point is outside the function domain")
    scale = max(1.0, abs(data.parameter))
    estimates: list[tuple[float, float, float]] = []
    for ratio in (1e-2, 5e-3, 2.5e-3, 1.25e-3, 6.25e-4):
        step = scale * ratio
        left = _function_value(scene, data.parameter - step)
        right = _function_value(scene, data.parameter + step)
        if left is None or right is None:
            raise AnimationRenderError("the derivative is undefined at the requested point")
        left_slope = (centre - left) / step
        right_slope = (right - centre) / step
        central = (right - left) / (2 * step)
        tolerance = max(1e-4, abs(central) * 0.01)
        estimates.append((central, abs(left_slope - right_slope), tolerance))
    recent = estimates[-3:]
    agreements = [agreement for _value, agreement, _tolerance in recent]
    agreement_converges = agreements[-1] <= recent[-1][2] or agreements[-1] <= agreements[0] * 0.35
    if not agreement_converges:
        raise AnimationRenderError("the derivative is undefined at the requested point")
    values = [value for value, _agreement, _tolerance in recent]
    estimate = values[-1]
    if max(values) - min(values) > max(1e-4, abs(estimate) * 0.005):
        raise AnimationRenderError("the derivative does not converge at the requested point")
    return estimate


def _checked_integral(scene: AnimationFunctionScene) -> float:
    data = scene.data
    assert data.bounds is not None
    start, end = data.bounds

    def integrate(intervals: int) -> float:
        width = (end - start) / intervals
        previous = _function_value(scene, start)
        if previous is None:
            return math.nan
        total = 0.0
        for sample in range(1, intervals + 1):
            current = _function_value(scene, start + sample * width)
            if current is None:
                return math.nan
            total += (previous + current) * width / 2
            previous = current
        return total

    estimates = [integrate(intervals) for intervals in (211, 307, 463, 701)]
    if not all(math.isfinite(value) for value in estimates):
        raise AnimationRenderError("the integral crosses an undefined function value")
    recent = estimates[-3:]
    estimate = recent[-1]
    if max(recent) - min(recent) > max(2e-4, abs(estimate) * 2e-4):
        raise AnimationRenderError("the integral does not converge on the requested interval")
    return estimate


def _validate_function_semantics(scene: AnimationFunctionScene) -> None:
    data = scene.data
    try:
        parsed = parse_expression_v2(data.expression_text)
    except VisualizationV2Error as exc:
        raise AnimationRenderError("function expression text is invalid") from exc
    if parsed != data.expression_ast:
        raise AnimationRenderError("function expression text and typed expression must agree")
    if _expression_variables(parsed) != {data.variable}:
        raise AnimationRenderError("function expression must use exactly its declared variable")
    _expression_typst(data.expression_ast, data.variable)
    if data.mode == "derivative":
        _checked_derivative(scene)
    elif data.mode == "integral":
        _checked_integral(scene)


def _scene_prelude(title: str, narration: str) -> list[str]:
    return [
        f"        scene_title = Text({_python_text(_wrapped_text(title, width=54))}, font_size=28)",
        "        _fit(scene_title, 12.0, 0.72).next_to(lesson_title, DOWN, buff=0.08)",
        f"        full_narration = {_python_text(narration)}",
        f"        caption = Text({_python_text(_wrapped_text(narration, width=64, limit=150))}, font_size=24, line_spacing=0.85)",
        "        _fit(caption, 12.2, 0.92).to_edge(DOWN)",
    ]


def _fraction_scene(index: int, scene) -> list[str]:
    data = scene.data
    bars = max(1, math.ceil(data.numerator / data.denominator))
    shaded = data.numerator
    lines = _scene_prelude(scene.title, scene.narration)
    lines += [
        "        cells = VGroup()",
        f"        for bar_index in range({bars}):",
        f"            for part_index in range({data.denominator}):",
        f"                order = bar_index * {data.denominator} + part_index",
        "                cell = Rectangle(width=9.0 / " + str(data.denominator) + ", height=0.9)",
        "                cell.move_to(LEFT * 4.5 + RIGHT * (part_index + 0.5) * (9.0 / "
        + str(data.denominator)
        + ") + DOWN * (bar_index - ("
        + str(bars)
        + " - 1) / 2) * 1.15)",
        "                cells.add(cell)",
        f"        formula = MathTypst({_python_text(f'{data.numerator}/{data.denominator}')}, font_size=46).next_to(cells, UP, buff=0.35)",
    ]
    if data.phase == "partition":
        lines += [
            "        content = cells",
            "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[Create(cell) for cell in cells], lag_ratio=0.06))",
        ]
    else:
        lines += [
            "        content = VGroup(cells, formula)",
            f"        selected_cells = list(cells)[:{shaded}]",
            "        shade_group = VGroup(*selected_cells)",
            "        shade = UpdateFromAlphaFunc(shade_group, lambda group, alpha: group.set_fill(TEAL, opacity=0.72 * alpha)) if selected_cells else Wait(0.05)",
            "        scene_intro = Succession(AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[Create(cell) for cell in cells], lag_ratio=0.04)), AnimationGroup(shade, Write(formula)))",
        ]
    return lines


def _array_scene(index: int, scene) -> list[str]:
    data = scene.data
    total = data.rows * data.columns
    repeated = " + ".join([str(data.columns)] * data.rows)
    lines = _scene_prelude(scene.title, scene.narration) + [
        "        dots = VGroup()",
        f"        for row in range({data.rows}):",
        f"            for column in range({data.columns}):",
        "                dots.add(Dot(radius=0.11, color=TEAL).move_to(RIGHT * (column - ("
        + str(data.columns)
        + " - 1) / 2) * 0.62 + DOWN * (row - ("
        + str(data.rows)
        + " - 1) / 2) * 0.62))",
        f"        addition = Text({_python_text(repeated + ' = ' + str(total))}, font_size=30).next_to(dots, DOWN, buff=0.35)",
        f"        equation = MathTypst({_python_text(f'{data.rows} times {data.columns} = {total}')}, font_size=42).next_to(dots, UP, buff=0.35)",
    ]
    if data.phase == "build":
        lines += [
            "        content = dots",
            "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[FadeIn(dot, scale=0.4) for dot in dots], lag_ratio=0.035))",
        ]
    elif data.phase == "addition":
        lines += [
            "        content = VGroup(dots, addition)",
            "        scene_intro = Succession(AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[FadeIn(dot, scale=0.4) for dot in dots], lag_ratio=0.025)), Write(addition))",
        ]
    else:
        lines += [
            "        content = VGroup(dots, equation)",
            "        scene_intro = Succession(AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[FadeIn(dot, scale=0.4) for dot in dots], lag_ratio=0.025)), Write(equation))",
        ]
    return lines


def _sample_function(scene: AnimationFunctionScene) -> list[list[tuple[float, float]]]:
    data = scene.data
    raw: list[tuple[float, float] | None] = []
    for index in range(241):
        argument = data.domain[0] + (data.domain[1] - data.domain[0]) * index / 240
        try:
            output = evaluate_expression_v2(data.expression_ast, {data.variable: argument})
        except (VisualizationV2Error, KeyError, TypeError, ValueError):
            raw.append(None)
            continue
        if math.isfinite(output) and abs(output) <= 1e6:
            raw.append((argument, output))
        else:
            raw.append(None)
    finite_values = [value for value in raw if value is not None]
    if len(finite_values) < 2:
        raise AnimationRenderError("function has too few finite samples to render")
    y_values = [value for _argument, value in finite_values]
    jump_limit = max(20.0, (max(y_values) - min(y_values)) * 0.35)
    segments: list[list[tuple[float, float]]] = [[]]
    previous: tuple[float, float] | None = None
    for point in raw:
        if point is None or (previous is not None and abs(point[1] - previous[1]) > jump_limit):
            if segments[-1]:
                segments.append([])
            previous = None
            continue
        segments[-1].append(point)
        previous = point
    return [segment for segment in segments if len(segment) >= 2]


def _function_scene(index: int, scene: AnimationFunctionScene) -> list[str]:
    data = scene.data
    _validate_function_semantics(scene)
    expression = _expression_typst(data.expression_ast, data.variable)
    segments = _sample_function(scene)
    samples = [point for segment in segments for point in segment]
    y_values = [value for _argument, value in samples]
    y_min, y_max = min(y_values), max(y_values)
    if math.isclose(y_min, y_max):
        y_min -= 1
        y_max += 1
    margin = max(0.5, (y_max - y_min) * 0.08)
    y_lower, y_upper = y_min - margin, y_max + margin
    x_ticks = [data.domain[0] + (data.domain[1] - data.domain[0]) * step / 4 for step in range(5)]
    y_ticks = [y_lower + (y_upper - y_lower) * step / 4 for step in range(5)]
    x_tick_source = repr([(value, _tick_label(value)) for value in x_ticks])
    y_tick_source = repr([(value, _tick_label(value)) for value in y_ticks])
    lines = _scene_prelude(scene.title, scene.narration) + [
        f"        axes = Axes(x_range=[{_finite(data.domain[0])}, {_finite(data.domain[1])}, ({_finite(data.domain[1])} - {_finite(data.domain[0])}) / 4], y_range=[{_finite(y_lower)}, {_finite(y_upper)}, ({_finite(y_upper)} - {_finite(y_lower)}) / 4], x_length=9.2, y_length=4.3, tips=False)",
        f"        axis_labels = axes.get_axis_labels(MathTypst({_python_text(data.variable)}, font_size=26), MathTypst({_python_text(data.output)}, font_size=26))",
        "        number_labels = VGroup()",
        f"        for tick, label in {x_tick_source}:",
        f"            number_labels.add(Text(label, font_size=16).next_to(axes.c2p(tick, {_finite(y_lower)}), DOWN, buff=0.08))",
        f"        for tick, label in {y_tick_source}:",
        f"            number_labels.add(Text(label, font_size=16).next_to(axes.c2p({_finite(data.domain[0])}, tick), LEFT, buff=0.08))",
        f"        domain_label = Text({_python_text(f'domain: {data.domain[0]:g} to {data.domain[1]:g}')}, font_size=18).next_to(axes, DOWN, buff=0.2)",
        "        curve_segments = VGroup()",
    ]
    for segment_index, segment in enumerate(segments):
        points = ", ".join(f"axes.c2p({_finite(x)}, {_finite(y)})" for x, y in segment)
        lines += [
            f"        curve_{segment_index} = VMobject(color=TEAL, stroke_width=4)",
            f"        curve_{segment_index}.set_points_as_corners([{points}])",
            f"        curve_segments.add(curve_{segment_index})",
        ]
    formula_typst = f"{data.output} = {expression}"
    lines += [
        f"        formula = MathTypst({_python_text(formula_typst)}, font_size=30).next_to(axes, UP, buff=0.18).align_to(axes, LEFT)",
        "        content = VGroup(axes, axis_labels, number_labels, domain_label, curve_segments, formula)",
        "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), Create(axes), FadeIn(axis_labels), FadeIn(number_labels), FadeIn(domain_label), Write(formula), LaggedStart(*[Create(segment) for segment in curve_segments], lag_ratio=0.12))",
    ]
    if data.mode == "derivative" and data.parameter is not None:
        center = _function_value(scene, data.parameter)
        if center is None:
            raise AnimationRenderError("derivative probe is undefined")
        slope = _checked_derivative(scene)
        span = (data.domain[1] - data.domain[0]) * 0.16
        lines += [
            f"        tangent = axes.plot(lambda value: {_finite(center)} + {_finite(slope)} * (value - {_finite(data.parameter)}), x_range=[{_finite(data.parameter - span)}, {_finite(data.parameter + span)}], color=YELLOW)",
            "        content.add(tangent)",
            "        scene_intro = Succession(scene_intro, Create(tangent))",
        ]
    elif data.mode == "integral" and data.bounds is not None:
        lower, upper = sorted(data.bounds)
        area_points = [(x, y) for x, y in samples if lower <= x <= upper]
        if len(area_points) < 2:
            raise AnimationRenderError("integral interval has too few finite samples")
        polygon_points = [(area_points[0][0], 0.0), *area_points, (area_points[-1][0], 0.0)]
        points = ", ".join(
            f"axes.c2p({_finite(x)}, {_finite(y)})" for x, y in polygon_points
        )
        lines += [
            f"        area = Polygon({points}, color=BLUE, fill_opacity=0.35, stroke_width=1)",
            "        content.add(area)",
            "        scene_intro = Succession(scene_intro, FadeIn(area))",
        ]
    return lines


def _process_scene(index: int, scene) -> list[str]:
    data = scene.data
    lines = _scene_prelude(scene.title, scene.narration) + ["        cards = VGroup()"]
    for step_index, step in enumerate(data.steps):
        colour = "TEAL" if step_index == data.active else "GREY_B"
        lines += [
            f"        card_{step_index} = RoundedRectangle(width=10.5, height=0.65, corner_radius=0.12, color={colour})",
            f"        label_{step_index} = Text({_python_text(_wrapped_text(step, width=46))}, font_size=22, line_spacing=0.82)",
            f"        _fit(label_{step_index}, 9.8, 0.48)",
            f"        label_{step_index}.move_to(card_{step_index})",
            f"        cards.add(VGroup(card_{step_index}, label_{step_index}))",
        ]
    lines += [
        "        cards.arrange(DOWN, buff=0.14)",
        "        content = cards",
        "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), LaggedStart(*[FadeIn(card, shift=RIGHT * 0.2) for card in cards], lag_ratio=0.1))",
    ]
    return lines


def _vector_scene(index: int, scene) -> list[str]:
    data = scene.data
    bound = max(1.0, abs(data.x), abs(data.y)) * 1.25
    return _scene_prelude(scene.title, scene.narration) + [
        f"        plane = NumberPlane(x_range=[-{_finite(bound)}, {_finite(bound)}, {_finite(bound / 4)}], y_range=[-{_finite(bound)}, {_finite(bound)}, {_finite(bound / 4)}], x_length=8.2, y_length=4.6)",
        f"        arrow = Arrow(plane.c2p(0, 0), plane.c2p({_finite(data.x)}, {_finite(data.y)}), buff=0, color=TEAL)",
        f"        vector_label = Text({_python_text(data.label)}, font_size=30).next_to(arrow.get_end(), UR, buff=0.12)",
        "        content = VGroup(plane, arrow, vector_label)",
        "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), Create(plane), GrowArrow(arrow), FadeIn(vector_label))",
    ]


def _circle_scene(index: int, scene: AnimationCircleScene) -> list[str]:
    data = scene.data
    radius_label = _circle_radius_label(data.radius)
    lines = _scene_prelude(scene.title, scene.narration) + [
        "        circle = Circle(radius=2.2, color=TEAL, stroke_width=5)",
        "        centre = Dot(ORIGIN, radius=0.08, color=WHITE)",
        "        radius_line = Line(ORIGIN, RIGHT * 2.2, color=YELLOW, stroke_width=5)",
        f"        radius_label = MathTypst({_python_text(f'r = {radius_label}')}, font_size=34).next_to(radius_line, UP, buff=0.12)",
    ]
    if data.phase == "construct":
        lines += [
            "        content = VGroup(circle, centre)",
            "        scene_intro = AnimationGroup(FadeIn(scene_title), FadeIn(caption), Create(circle), FadeIn(centre))",
        ]
    else:
        lines += [
            "        content = VGroup(circle, centre, radius_line, radius_label)",
            "        scene_intro = Succession(AnimationGroup(FadeIn(scene_title), FadeIn(caption), Create(circle), FadeIn(centre)), AnimationGroup(Create(radius_line), Write(radius_label)))",
        ]
    return lines


def _division_scene(index: int, scene) -> list[str]:
    data = scene.data
    quotient, remainder = divmod(data.dividend, data.divisor)
    lines = _scene_prelude(scene.title, scene.narration) + [
        "        groups = VGroup()",
        f"        for group_index in range({data.divisor}):",
        "            groups.add(RoundedRectangle(width=2.45, height=1.05, corner_radius=0.12))",
        f"        groups.arrange_in_grid(cols={min(4, data.divisor)}, buff=0.18)",
        "        dots = VGroup()",
        f"        for object_index in range({data.dividend}):",
        "            dots.add(Dot(radius=0.055, color=TEAL))",
        "        if len(dots):",
        "            dots.arrange_in_grid(cols=min(24, len(dots)), buff=0.12)",
        "        dots.next_to(groups, DOWN, buff=0.3)",
        f"        equation = Text({_python_text(f'{data.dividend} ÷ {data.divisor} = {quotient} · remainder {remainder}')}, font_size=28).next_to(groups, UP, buff=0.25)",
        "        content = VGroup(groups, dots)" if data.phase == "count" else "        content = VGroup(groups, dots, equation)",
    ]
    if data.phase == "count":
        intro = [
            "        return AnimationGroup(FadeIn(scene_title), FadeIn(caption), FadeIn(groups), FadeIn(dots))",
        ]
    else:
        intro = [
            "        sharing = []",
            f"        for object_index in range({data.divisor * quotient}):",
            f"            group_index = object_index % {data.divisor}",
            f"            place_index = object_index // {data.divisor}",
            f"            target = groups[group_index].get_center() + RIGHT * ((place_index % 4) - ({min(quotient, 4)} - 1) / 2) * 0.42 + UP * (0.28 - (place_index // 4) * 0.28)",
            "            sharing.append(dots[object_index].animate.move_to(target))",
            "        deal = LaggedStart(*sharing, lag_ratio=0.02) if sharing else Wait(0.05)",
            "        return Succession(AnimationGroup(FadeIn(scene_title), FadeIn(caption), FadeIn(groups), FadeIn(dots)), deal, Write(equation))",
        ]
    # Resolve target positions only after the common content fitting/translation step.
    lines.append("        def division_intro():")
    lines.extend("    " + line for line in intro)
    return lines


def emit_manim_source(project: AnimationPlanProject) -> str:
    """Emit deterministic, inspectable Manim Python from a validated project."""
    project = AnimationPlanProject.model_validate(project)
    lines = [
        "from manim import *",
        "import math",
        "",
        "def _fit(mobject, max_width, max_height):",
        "    factor = min(1.0, max_width / max(mobject.width, 1e-9), max_height / max(mobject.height, 1e-9))",
        "    return mobject.scale(factor)",
        "",
        "class MutaLesson(Scene):",
        "    def construct(self):",
        "        self.camera.background_color = '#181715'",
        f"        lesson_title = Text({_python_text(_wrapped_text(project.title, width=64))}, font_size=38, line_spacing=0.85)",
        "        _fit(lesson_title, 12.2, 0.78).to_edge(UP)",
        "        self.add(lesson_title)",
    ]
    for index, scene in enumerate(project.scenes):
        if scene.kind == "fraction":
            block = _fraction_scene(index, scene)
        elif scene.kind == "array":
            block = _array_scene(index, scene)
        elif scene.kind == "circle":
            block = _circle_scene(index, scene)
        elif scene.kind == "division":
            block = _division_scene(index, scene)
        elif scene.kind == "function":
            block = _function_scene(index, scene)
        elif scene.kind == "vector":
            block = _vector_scene(index, scene)
        elif scene.kind == "process":
            block = _process_scene(index, scene)
        else:  # Pydantic discriminator makes this unreachable; retain fail-closed behaviour.
            raise AnimationRenderError("unsupported animation scene kind")
        lines.extend(block)
        lines.append("        _fit(content, 12.0, 4.6).shift(DOWN * 0.25)")
        if scene.kind == "division":
            lines.append("        scene_intro = division_intro()")
        lines += [
            "        scene_group = VGroup(scene_title, content, caption)",
            "        self.play(scene_intro, run_time=0.75)",
            f"        self.wait({_finite(max(0.2, scene.duration_ms / 1000 - 1.1))})",
        ]
        if index < len(project.scenes) - 1:
            lines.append("        self.play(FadeOut(scene_group), run_time=0.35)")
        else:
            lines.append("        self.wait(0.35)")  # Keep the final teaching frame for replay/seek.
    source = "\n".join(lines) + "\n"
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise AnimationRenderError("trusted animation source exceeds the size budget")
    return source


def source_filename(project: AnimationPlanProject) -> str:
    return f"{project.id}-manim.py"


def manim_capability() -> ManimCapability:
    unavailable_reason = os.environ.get("MUTA_MANIM_UNAVAILABLE_REASON", "").strip()
    if unavailable_reason:
        return ManimCapability(False, None, unavailable_reason)
    configured = os.environ.get("MUTA_MANIM_BIN", "").strip()
    runtime = os.environ.get("MUTA_MANIM_RUNTIME_DIR", "").strip()
    bundled = str(Path(runtime) / "bin" / "manim") if runtime else ""
    executable = configured or bundled
    if not executable and not getattr(sys, "frozen", False):
        executable = shutil.which("manim") or ""
    if executable and Path(executable).is_file() and os.access(executable, os.X_OK):
        return ManimCapability(True, str(Path(executable).resolve()), "Offline Manim is ready.")
    return ManimCapability(
        False,
        None,
        "Offline Manim is not installed in this build; the trusted scene source is still available.",
    )


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:  # pragma: no cover - Windows only
        process.kill()


def _run_manim_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    cancel_event: threading.Event | None = None,
) -> bytes:
    """Run Manim in its own process group so timeouts terminate every child renderer."""
    options: dict[str, Any] = {
        "cwd": cwd,
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "posix":
        options["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):  # pragma: no cover - Windows only
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(command, **options)
    deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
    while process.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            _stop_process_group(process)
            process.communicate()
            raise AnimationRenderError("Manim render was cancelled")
        if time.monotonic() >= deadline:
            _stop_process_group(process)
            process.communicate()
            raise AnimationRenderError("Manim render exceeded the offline time budget")
        time.sleep(0.05)
    output, _stderr = process.communicate()
    if process.returncode != 0:
        tail = (output or b"").decode("utf-8", errors="replace")[-1200:]
        raise AnimationRenderError(f"Manim could not render this lesson. {tail}")
    return output or b""


def _animation_worker_command(manim_command: list[str]) -> list[str]:
    """Select a source-development worker or the frozen gateway's fixed dispatch."""
    configured = os.environ.get("MUTA_ANIMATION_WORKER_BIN", "").strip()
    if configured:
        worker = Path(configured).resolve()
        if not worker.is_file() or not os.access(worker, os.X_OK):
            raise AnimationRenderError("configured animation worker is not executable")
        return [str(worker), "--animation-worker", *manim_command]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--animation-worker", *manim_command]
    worker_script = Path(__file__).with_name("animation_worker.py")
    if not worker_script.is_file():
        raise AnimationRenderError("animation worker source is missing from the development build")
    return [sys.executable, str(worker_script), *manim_command]


def render_manim_video(
    project: AnimationPlanProject, *, cancel_event: threading.Event | None = None
) -> bytes:
    """Render the trusted emitted source in one bounded, offline worker."""
    capability = manim_capability()
    if not capability.available or capability.executable is None:
        raise AnimationRenderError(capability.detail)
    source = emit_manim_source(project)
    if not _render_lock.acquire(blocking=False):
        raise AnimationRenderBusyError("Another offline animation render is already in progress")
    try:
        return _render_manim_video_locked(
            project, source=source, capability=capability, cancel_event=cancel_event
        )
    finally:
        _render_lock.release()


def _render_manim_video_locked(
    project: AnimationPlanProject,
    *,
    source: str,
    capability: ManimCapability,
    cancel_event: threading.Event | None,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="muta-manim-") as temporary:
        root = Path(temporary)
        script = root / "lesson.py"
        media = root / "media"
        script.write_text(source, encoding="utf-8")
        environment = {
            "PATH": os.pathsep.join(
                part for part in [str(Path(capability.executable).parent), "/usr/bin", "/bin"] if part
            ),
            "HOME": str(root),
            "TMPDIR": str(root),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_PROXY": "*",
            "no_proxy": "*",
        }
        runtime = os.environ.get("MUTA_MANIM_RUNTIME_DIR", "").strip()
        if runtime:
            library = str(Path(runtime) / "lib")
            environment["DYLD_LIBRARY_PATH"] = library
            environment["LD_LIBRARY_PATH"] = library
            environment["PATH"] = os.pathsep.join(
                [str(Path(runtime) / "bin"), environment["PATH"]]
            )
        ffmpeg = os.environ.get("MUTA_MANIM_FFMPEG_BIN", "").strip()
        if ffmpeg and Path(ffmpeg).is_file() and os.access(ffmpeg, os.X_OK):
            environment["PATH"] = os.pathsep.join(
                [str(Path(ffmpeg).resolve().parent), environment["PATH"]]
            )
        manim_command = [
            capability.executable,
            "--silent",
            "-qm",
            "--format",
            "mp4",
            "--disable_caching",
            "--media_dir",
            str(media),
            str(script),
            "MutaLesson",
        ]
        command = _animation_worker_command(manim_command)
        _run_manim_process(
            command,
            cwd=root,
            environment=environment,
            cancel_event=cancel_event,
        )
        candidates = [
            path
            for path in media.rglob("MutaLesson.mp4")
            if path.is_file() and "partial_movie_files" not in path.parts
        ]
        if len(candidates) != 1:
            raise AnimationRenderError("Manim did not produce exactly one lesson video")
        video = candidates[0].read_bytes()
        if not video or len(video) > MAX_VIDEO_BYTES:
            raise AnimationRenderError("Manim video is empty or exceeds the output budget")
        return video
