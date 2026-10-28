"""Local-model Manim authoring and defence-in-depth source validation.

Validation is NOT isolation. Only the separately proven OS sandbox may execute this source.
Unlike the legacy scene emitter, this module never constructs mathematical scene source.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import math
import re
import secrets
import threading
import uuid
from datetime import UTC, datetime

from contracts.models import AnimationProgram, AnimationProgramRequest
from runtime.chat import ChatEngine
from runtime.client import InferenceStreamError

MAX_PROGRAM_CHARS = 24000
MAX_AST_NODES = 2400
MAX_OBJECT_CALLS = 512
MAX_LOOP_PRODUCT = 128
_GENERATION_KEY = secrets.token_bytes(32)

CONSTRUCTORS = frozenset(
    [
        "Circle",
        "Ellipse",
        "Square",
        "Rectangle",
        "RoundedRectangle",
        "Triangle",
        "Polygon",
        "RegularPolygon",
        "Line",
        "Arrow",
        "DoubleArrow",
        "Vector",
        "Dot",
        "Arc",
        "ArcBetweenPoints",
        "Annulus",
        "Sector",
        "Angle",
        "RightAngle",
        "Brace",
        "BraceBetweenPoints",
        "NumberLine",
        "Axes",
        "NumberPlane",
        "ThreeDAxes",
        "VGroup",
        "Group",
        "Text",
        "MathTypst",
        "DecimalNumber",
        "Integer",
        "ValueTracker",
        "Surface",
        "Sphere",
        "Cube",
        "Prism",
        "Cylinder",
        "Cone",
        "Torus",
        "Dot3D",
        "ParametricFunction",
        "VMobject",
        "Create",
        "Uncreate",
        "Write",
        "Unwrite",
        "FadeIn",
        "FadeOut",
        "Transform",
        "ReplacementTransform",
        "TransformFromCopy",
        "TransformMatchingShapes",
        "Rotate",
        "GrowArrow",
        "GrowFromCenter",
        "Indicate",
        "Circumscribe",
        "Flash",
        "Wiggle",
        "MoveAlongPath",
        "AnimationGroup",
        "Succession",
        "LaggedStart",
        "Wait",
    ]
)
CONSTANTS = frozenset(
    [
        "ORIGIN",
        "UP",
        "DOWN",
        "LEFT",
        "RIGHT",
        "IN",
        "OUT",
        "UL",
        "UR",
        "DL",
        "DR",
        "X_AXIS",
        "Y_AXIS",
        "Z_AXIS",
        "PI",
        "TAU",
        "DEGREES",
        "WHITE",
        "BLACK",
        "RED",
        "BLUE",
        "GREEN",
        "YELLOW",
        "ORANGE",
        "PURPLE",
        "PINK",
        "TEAL",
        "GOLD",
        "GRAY",
        "GREY",
        "RED_A",
        "RED_B",
        "RED_C",
        "RED_D",
        "RED_E",
        "BLUE_A",
        "BLUE_B",
        "BLUE_C",
        "BLUE_D",
        "BLUE_E",
        "GREEN_A",
        "GREEN_B",
        "GREEN_C",
        "GREEN_D",
        "GREEN_E",
        "YELLOW_A",
        "YELLOW_B",
        "YELLOW_C",
        "TEAL_A",
        "TEAL_B",
        "TEAL_C",
        "TEAL_D",
        "TEAL_E",
    ]
)
METHODS = frozenset(
    [
        "set_color",
        "set_fill",
        "set_stroke",
        "set_opacity",
        "move_to",
        "shift",
        "scale",
        "rotate",
        "stretch",
        "scale_to_fit_width",
        "scale_to_fit_height",
        "set_width",
        "set_height",
        "next_to",
        "to_edge",
        "to_corner",
        "align_to",
        "center",
        "arrange",
        "arrange_in_grid",
        "add",
        "remove",
        "get_center",
        "get_start",
        "get_end",
        "get_corner",
        "get_left",
        "get_right",
        "get_top",
        "get_bottom",
        "get_width",
        "get_height",
        "get_value",
        "set_value",
        "increment_value",
        "point_from_proportion",
        "c2p",
        "coords_to_point",
        "p2c",
        "plot",
        "get_graph",
        "plot_parametric_curve",
        "get_area",
        "get_vertical_line",
        "get_horizontal_line",
        "get_axis_labels",
        "get_x_axis_label",
        "get_y_axis_label",
        "get_z_axis_label",
        "add_coordinates",
        "apply_matrix",
        "put_start_and_end_on",
        "become",
    ]
)
SCENE_METHODS = frozenset(
    [
        "play",
        "wait",
        "add",
        "remove",
        "clear",
        "set_camera_orientation",
        "move_camera",
        "begin_ambient_camera_rotation",
        "stop_ambient_camera_rotation",
        "add_fixed_in_frame_mobjects",
        "add_fixed_orientation_mobjects",
    ]
)
READ_ATTRIBUTES = frozenset(
    ["animate", "width", "height", "x_axis", "y_axis", "z_axis", "submobjects"]
)
NUMERIC_FUNCTIONS = frozenset(
    [
        "sin",
        "cos",
        "tan",
        "arcsin",
        "arccos",
        "arctan",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "sqrt",
        "log",
        "log10",
        "abs",
        "minimum",
        "maximum",
    ]
)
BUILTINS = frozenset(["abs", "min", "max", "round", "int", "float", "str", "len", "range"])
GLOBALS = CONSTRUCTORS | CONSTANTS | BUILTINS | {"self", "np", "math"}
_STYLE_KEYS = frozenset(
    {
        "color",
        "fill_color",
        "fill_opacity",
        "stroke_color",
        "stroke_width",
        "stroke_opacity",
        "z_index",
    }
)
_ANIMATION_KEYS = frozenset(
    {"run_time", "lag_ratio", "shift", "scale", "about_point", "axis", "angle", "path_arc"}
)
_KEYWORDS = {
    "Circle": {"radius"},
    "Ellipse": {"width", "height"},
    "Square": {"side_length"},
    "Rectangle": {"width", "height"},
    "RoundedRectangle": {"width", "height", "corner_radius"},
    "RegularPolygon": {"n", "start_angle"},
    "Dot": {"point", "radius"},
    "Dot3D": {"point", "radius", "resolution"},
    "Line": {"start", "end", "buff", "path_arc"},
    "DashedLine": {"start", "end", "buff", "dash_length", "dashed_ratio"},
    "Arrow": {"start", "end", "buff", "tip_length", "max_tip_length_to_length_ratio"},
    "DoubleArrow": {"start", "end", "buff", "tip_length"},
    "Vector": {"direction", "buff"},
    "Arc": {"radius", "start_angle", "angle", "num_components"},
    "ArcBetweenPoints": {"start", "end", "radius", "angle"},
    "Annulus": {"inner_radius", "outer_radius"},
    "Sector": {"outer_radius", "inner_radius", "start_angle", "angle"},
    "Angle": {"radius", "quadrant", "other_angle"},
    "RightAngle": {"length", "quadrant"},
    "Brace": {"direction", "buff"},
    "BraceBetweenPoints": {"direction", "buff"},
    "Axes": {"x_range", "y_range", "x_length", "y_length", "tips"},
    "NumberPlane": {"x_range", "y_range", "x_length", "y_length", "tips"},
    "ThreeDAxes": {"x_range", "y_range", "z_range", "x_length", "y_length", "z_length", "tips"},
    "NumberLine": {
        "x_range",
        "length",
        "include_numbers",
        "font_size",
        "numbers_to_include",
        "unit_size",
        "include_tip",
    },
    "Text": {"font_size", "font", "weight", "slant", "line_spacing"},
    "MathTypst": {"font_size"},
    "DecimalNumber": {
        "number",
        "num_decimal_places",
        "font_size",
        "include_sign",
        "group_with_commas",
    },
    "Integer": {"number", "font_size", "include_sign"},
    "ValueTracker": {"value"},
    "Surface": {"u_range", "v_range", "resolution", "checkerboard_colors"},
    "Sphere": {"center", "radius", "resolution"},
    "Cube": {"side_length"},
    "Prism": {"dimensions"},
    "Cylinder": {"radius", "height", "direction", "resolution"},
    "Cone": {"base_radius", "height", "direction", "resolution"},
    "Torus": {"major_radius", "minor_radius", "resolution"},
    "ParametricFunction": {"t_range", "use_smoothing"},
    "play": {"run_time"},
    "wait": {"duration", "frozen_frame"},
    "Wait": {"duration", "frozen_frame", "run_time"},
    "set_camera_orientation": {"phi", "theta", "gamma", "zoom", "frame_center"},
    "move_camera": {"phi", "theta", "gamma", "zoom", "frame_center", "run_time"},
    "begin_ambient_camera_rotation": {"rate", "about"},
    "set_fill": {"color", "opacity"},
    "set_stroke": {"color", "width", "opacity", "background"},
    "set_color": {"color"},
    "set_opacity": {"opacity"},
    "move_to": {"point_or_mobject", "aligned_edge"},
    "shift": {},
    "scale": {"scale_factor", "about_point"},
    "rotate": {"angle", "axis", "about_point"},
    "next_to": {"direction", "buff", "aligned_edge"},
    "to_edge": {"edge", "buff"},
    "to_corner": {"corner", "buff"},
    "arrange": {"direction", "buff", "aligned_edge", "center"},
    "arrange_in_grid": {"rows", "cols", "buff"},
    "plot": {"x_range", "use_smoothing", "color", "stroke_width", "discontinuities"},
    "get_graph": {"x_range", "use_smoothing", "color", "stroke_width"},
    "plot_parametric_curve": {"t_range", "color", "stroke_width"},
    "get_area": {"x_range", "color", "opacity"},
    "get_axis_labels": {"x_label", "y_label", "z_label"},
    "Flash": {"line_length", "num_lines", "flash_radius", "color", "run_time"},
}


class AnimationProgramError(ValueError):
    """A model program failed validation or bounded generation."""

    def __init__(self, message: str, *, source: str = "") -> None:
        super().__init__(message)
        self.source = source[:MAX_PROGRAM_CHARS]


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _generation_token(program: AnimationProgram) -> str:
    value = program.model_dump(exclude={"generation_token"})
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(_GENERATION_KEY, payload.encode(), hashlib.sha256).hexdigest()


def program_origin(program: AnimationProgram) -> str:
    """A self-reported model id/hash is not authenticated generation provenance."""
    return (
        "local-model"
        if re.fullmatch(r"[a-f0-9]{64}", program.generation_token)
        and hmac.compare_digest(program.generation_token, _generation_token(program))
        else "saved-or-imported"
    )


def isolated_program_capability(
    *, cancel_event: threading.Event | None = None
) -> dict[str, object]:
    from orchestrator.gateway.animation_render import manim_capability

    capability = manim_capability()
    if not capability.available or not capability.executable:
        return {"available": False, "detail": capability.detail}
    try:
        from orchestrator.gateway.animation_sandbox import program_capability
    except ImportError:
        return {"available": False, "detail": "This build has no verified model-code sandbox."}
    return program_capability(capability.executable, cancel_event=cancel_event)


def render_authored_program(
    program: AnimationProgram, *, cancel_event: threading.Event | None = None
) -> bytes:
    from orchestrator.gateway.animation_render import manim_capability

    source = validate_manim_program(program.source)
    if source != program.source or source_hash(source) != program.source_sha256:
        raise AnimationProgramError(
            "The source bytes/hash changed; regenerate or re-import a complete program."
        )
    capability = isolated_program_capability(cancel_event=cancel_event)
    if not capability["available"]:
        raise AnimationProgramError(str(capability["detail"]))
    from orchestrator.gateway.animation_sandbox import render_program_source

    executable = manim_capability().executable
    if not executable:
        raise AnimationProgramError("The offline Manim worker is not available.")
    return render_program_source(source, executable=executable, cancel_event=cancel_event)


def _number(node: ast.AST, values: dict[str, float]) -> float | None:
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        try:
            return float(node.value)
        except OverflowError:
            return None
    if isinstance(node, ast.Name):
        return {"PI": math.pi, "TAU": math.tau, "DEGREES": math.pi / 180}.get(
            node.id, values.get(node.id)
        )
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"np", "math"}
    ):
        return {"pi": math.pi, "e": math.e}.get(node.attr)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _number(node.operand, values)
        return None if value is None else (-value if isinstance(node.op, ast.USub) else value)
    if isinstance(node, ast.BinOp):
        left, right = _number(node.left, values), _number(node.right, values)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                value = left / right
            elif isinstance(node.op, ast.FloorDiv):
                value = left // right
            elif isinstance(node.op, ast.Mod):
                value = left % right
            elif isinstance(node.op, ast.Pow) and 0 <= right <= 6:
                value = left**right
            else:
                return None
            return value if math.isfinite(value) and abs(value) <= 1e6 else None
        except (ValueError, OverflowError, ZeroDivisionError):
            return None
    return None


class _Validator(ast.NodeVisitor):
    """Closed Python syntax and public Manim API; no reflective/file/config authority."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.values: dict[str, float] = {}
        self.multiplier = 1
        self.object_calls = 0
        self.duration = 0.0
        self.lambda_depth = 0
        self.sequence_names: set[str] = set()
        self.types: dict[str, str] = {}
        self.bounds: dict[str, float] = {}

    def generic_visit(self, node: ast.AST) -> None:
        allowed = (
            ast.Expr,
            ast.Assign,
            ast.Name,
            ast.Load,
            ast.Store,
            ast.Constant,
            ast.Call,
            ast.Attribute,
            ast.keyword,
            ast.List,
            ast.Tuple,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.USub,
            ast.UAdd,
            ast.Subscript,
            ast.Slice,
            ast.Starred,
            ast.JoinedStr,
            ast.FormattedValue,
            ast.IfExp,
            ast.Compare,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.Eq,
            ast.NotEq,
        )
        if not isinstance(node, allowed):
            raise AnimationProgramError(f"Unsupported Python syntax: {type(node).__name__}.")
        super().generic_visit(node)

    def bind(self, name: str) -> None:
        if (
            name != "_" and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name)
        ) or name in GLOBALS:
            raise AnimationProgramError("Use local variable names without private/reserved names.")
        self.names.add(name)

    def visit_Name(self, node: ast.Name) -> None:
        if (node.id.startswith("_") and node.id != "_") or node.id not in GLOBALS | self.names:
            raise AnimationProgramError(f"Unknown or forbidden name: {node.id[:64]}.")

    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        if type(value) in {int, float}:
            if abs(value) > 10000 or not math.isfinite(value):
                raise AnimationProgramError("Numeric literals must be finite and within 10000.")
        elif isinstance(value, str):
            if len(value) > 800 or "\x00" in value:
                raise AnimationProgramError("Keep text literals within 800 characters.")
        elif value is not None and type(value) is not bool:
            raise AnimationProgramError("Unsupported Python literal.")

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise AnimationProgramError("Assign only to a single local variable, not attributes.")
        target = node.targets[0].id
        if target in self.names:
            raise AnimationProgramError(
                f"Variable '{target}' was already assigned: use a DIFFERENT name for the new value, and preserve the old numeric value."
            )
        if isinstance(node.value, ast.Name) and node.value.id in GLOBALS:
            raise AnimationProgramError("Do not alias modules, constructors, constants or self.")
        self.visit(node.value)
        value_type = self.expression_type(node.value)
        self.bind(target)
        self.types[target] = value_type
        if value_type in {"number", "vector"}:
            bound = self.expression_bound(node.value)
            if not math.isfinite(bound) or bound > 1e6:
                raise AnimationProgramError(
                    "Numerical expressions exceed the bounded arithmetic budget."
                )
            self.bounds[target] = bound
        if (
            isinstance(node.value, (ast.List, ast.Tuple, ast.JoinedStr))
            or (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
            or (isinstance(node.value, ast.Name) and node.value.id in self.sequence_names)
        ):
            self.sequence_names.add(target)
        else:
            self.sequence_names.discard(target)
        value = _number(node.value, self.values)
        if value is not None:
            self.values[target] = value
        else:
            self.values.pop(target, None)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise AnimationProgramError("Python introspection/private attributes are forbidden.")
        if isinstance(node.value, ast.Name) and node.value.id in {"np", "math"}:
            allowed = NUMERIC_FUNCTIONS | {"pi", "e", "array", "linspace", "arange"}
            if node.attr not in allowed:
                raise AnimationProgramError("Only bounded numerical module functions are allowed.")
        elif isinstance(node.value, ast.Name) and node.value.id == "self":
            if node.attr not in SCENE_METHODS:
                raise AnimationProgramError(
                    "Scene renderer, camera, configuration and files are private."
                )
        elif node.attr not in METHODS | READ_ATTRIBUTES:
            raise AnimationProgramError(f"Unsupported Manim attribute: {node.attr[:64]}.")
        self.visit(node.value)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if any(
            self.expression_type(operand) not in {"number", "vector"}
            for operand in (node.left, node.right)
        ):
            raise AnimationProgramError(
                "Arithmetic accepts only numerical values/vectors, not text, lists or objects."
            )
        if self.expression_bound(node) > 1e6:
            raise AnimationProgramError("Computed arithmetic exceeds its numerical budget.")
        for operand in (node.left, node.right):
            if (
                isinstance(operand, (ast.List, ast.Tuple, ast.JoinedStr))
                or (isinstance(operand, ast.Constant) and isinstance(operand.value, str))
                or (isinstance(operand, ast.Name) and operand.id in self.sequence_names)
            ):
                raise AnimationProgramError(
                    "String/list arithmetic or repetition is not supported."
                )
        if isinstance(node.op, ast.Pow):
            exponent = _number(node.right, self.values)
            if exponent is None or not 0 <= exponent <= 6:
                raise AnimationProgramError("Powers require a constant exponent from 0 through 6.")
        self.generic_visit(node)

    def expression_type(self, node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return "number" if type(node.value) in {int, float} else "text"
        if isinstance(node, ast.JoinedStr):
            return "text"
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"np", "math"}
            and node.attr in {"pi", "e"}
        ):
            return "number"
        if isinstance(node, ast.Name):
            if node.id in {"PI", "TAU", "DEGREES"}:
                return "number"
            if node.id in {
                "ORIGIN",
                "UP",
                "DOWN",
                "LEFT",
                "RIGHT",
                "IN",
                "OUT",
                "UL",
                "UR",
                "DL",
                "DR",
                "X_AXIS",
                "Y_AXIS",
                "Z_AXIS",
            }:
                return "vector"
            return self.types.get(node.id, "unknown")
        if isinstance(node, ast.UnaryOp):
            return self.expression_type(node.operand)
        if isinstance(node, ast.BinOp):
            kinds = {self.expression_type(node.left), self.expression_type(node.right)}
            if kinds <= {"number", "vector"}:
                return "vector" if "vector" in kinds else "number"
            return "unknown"
        if isinstance(node, (ast.List, ast.Tuple, ast.ListComp)):
            return "sequence"
        if isinstance(node, ast.Subscript):
            return (
                "number"
                if self.expression_type(node.value) == "vector"
                and _number(node.slice, self.values) is not None
                else "unknown"
            )
        if isinstance(node, ast.IfExp):
            left, right = self.expression_type(node.body), self.expression_type(node.orelse)
            return left if left == right else "unknown"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == "str":
                    return "text"
                if node.func.id in BUILTINS - {"range"}:
                    return "number"
                return "object"
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in {"np", "math"}:
                    if node.func.attr == "array":
                        return (
                            "matrix"
                            if node.args
                            and isinstance(node.args[0], (ast.List, ast.Tuple))
                            and any(
                                isinstance(item, (ast.List, ast.Tuple))
                                for item in node.args[0].elts
                            )
                            else "vector"
                        )
                    return (
                        "vector"
                        if node.func.attr == "linspace"
                        or any(self.expression_type(arg) == "vector" for arg in node.args)
                        else "number"
                    )
                if node.func.attr in {"get_value", "get_width", "get_height"}:
                    return "number"
                if node.func.attr in {
                    "c2p",
                    "coords_to_point",
                    "p2c",
                    "get_center",
                    "get_start",
                    "get_end",
                    "get_corner",
                    "get_left",
                    "get_right",
                    "get_top",
                    "get_bottom",
                }:
                    return "vector"
                return "object"
        return "unknown"

    def expression_bound(self, node: ast.AST) -> float:
        lower, upper = self.expression_interval(node)
        return max(abs(lower), abs(upper))

    def expression_interval(self, node: ast.AST) -> tuple[float, float]:
        """Conservative scalar/component intervals, not a proof of the requested mathematics."""
        unknown = (-math.inf, math.inf)
        value = _number(node, self.values)
        if value is not None:
            return value, value
        if isinstance(node, ast.Name):
            if node.id in CONSTANTS:
                return -1.0, 1.0
            bound = self.bounds.get(node.id, math.inf)
            return -bound, bound
        if isinstance(node, ast.UnaryOp):
            low, high = self.expression_interval(node.operand)
            return (-high, -low) if isinstance(node.op, ast.USub) else (low, high)
        if isinstance(node, ast.BinOp):
            a, b = self.expression_interval(node.left)
            c, d = self.expression_interval(node.right)
            if not all(math.isfinite(value) for value in (a, b, c, d)):
                return unknown
            if isinstance(node.op, ast.Add):
                return a + c, b + d
            if isinstance(node.op, ast.Sub):
                return a - d, b - c
            if isinstance(node.op, ast.Mult):
                terms = (a * c, a * d, b * c, b * d)
                if ast.dump(node.left) == ast.dump(node.right):
                    return (0 if a <= 0 <= b else min(a * a, b * b), max(a * a, b * b))
                return min(terms), max(terms)
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if c <= 0 <= d:
                    return unknown
                if isinstance(node.op, ast.Mod):
                    return -max(abs(c), abs(d)), max(abs(c), abs(d))
                terms = (a / c, a / d, b / c, b / d)
                if not all(math.isfinite(value) for value in terms):
                    return unknown
                if isinstance(node.op, ast.FloorDiv):
                    return float(math.floor(min(terms))), float(math.floor(max(terms)))
                return min(terms), max(terms)
            if isinstance(node.op, ast.Pow):
                exponent = _number(node.right, self.values)
                if (
                    exponent is None
                    or not 0 <= exponent <= 6
                    or max(abs(a), abs(b)) > 1e6
                    or (a < 0 and not exponent.is_integer())
                ):
                    return unknown
                terms = (a**exponent, b**exponent)
                return (
                    0
                    if exponent > 0
                    and exponent.is_integer()
                    and int(exponent) % 2 == 0
                    and a <= 0 <= b
                    else min(terms),
                    max(terms),
                )
        if isinstance(node, ast.Call):
            name = (
                node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            )
            intervals = [self.expression_interval(arg) for arg in node.args]
            if name in {"sin", "cos", "tanh"}:
                return -1, 1
            if name in {"arcsin", "arccos", "arctan"}:
                return -math.pi, math.pi
            if name in {"log", "log10"}:
                return -745, 745  # Finite binary64 logarithms; invalid domains fail in Manim.
            if intervals:
                a, b = intervals[0]
                if name in {"int", "float"}:
                    return a, b
                if name == "round":
                    return a - 1, b + 1
                if name in {"abs", "sqrt"}:
                    upper = max(abs(a), abs(b)) if name == "abs" else math.sqrt(max(0, b))
                    return 0, upper
                if name in {"exp", "sinh", "cosh"}:
                    if not all(math.isfinite(v) and abs(v) <= 700 for v in (a, b)):
                        return unknown
                    fn = getattr(math, name)
                    return (0 if name == "cosh" else min(fn(a), fn(b)), max(fn(a), fn(b)))
                if name in {"min", "minimum"}:
                    return min(x[0] for x in intervals), min(x[1] for x in intervals)
                if name in {"max", "maximum"}:
                    return max(x[0] for x in intervals), max(x[1] for x in intervals)
            if name == "array" and node.args:

                def leaves(value):
                    if isinstance(value, (ast.List, ast.Tuple)):
                        return [pair for item in value.elts for pair in leaves(item)]
                    return [self.expression_interval(value)]

                items = leaves(node.args[0])
                return (
                    (min(pair[0] for pair in items), max(pair[1] for pair in items))
                    if items
                    else unknown
                )
            if name == "linspace" and len(intervals) == 3:
                return min(intervals[0][0], intervals[1][0]), max(intervals[0][1], intervals[1][1])
            return -1e6, 1e6
        if isinstance(node, ast.Subscript) and self.expression_type(node.value) == "vector":
            return self.expression_interval(node.value)
        if isinstance(node, ast.IfExp):
            a, b = self.expression_interval(node.body)
            c, d = self.expression_interval(node.orelse)
            return min(a, c), max(b, d)
        return unknown

    def visit_FormattedValue(self, node: ast.FormattedValue) -> None:
        if node.conversion != -1:
            raise AnimationProgramError("Use plain numerical f-string interpolation.")
        if node.format_spec is not None:
            values = node.format_spec.values
            if (
                len(values) != 1
                or not isinstance(values[0], ast.Constant)
                or not isinstance(values[0].value, str)
                or not re.fullmatch(r"\.[0-6][fg]", values[0].value)
            ):
                raise AnimationProgramError("Only a small numerical precision format is supported.")
        self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self.expression_type(node.value) == "vector":
            index = _number(node.slice, self.values)
            if index is None or not index.is_integer() or not -1024 <= index <= 1024:
                raise AnimationProgramError(
                    "Numerical vectors support only a constant scalar index, not slices or added dimensions."
                )
        self.generic_visit(node)

    def range_count(self, node: ast.AST) -> int:
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "range"
        ):
            raise AnimationProgramError("Loops use only a bounded constant range(...).")
        values = [_number(arg, self.values) for arg in node.args]
        if (
            node.keywords
            or not 1 <= len(values) <= 3
            or any(value is None or not value.is_integer() for value in values)
        ):
            raise AnimationProgramError("Use one to three constant integer range arguments.")
        try:
            count = len(range(*(int(value) for value in values if value is not None)))
        except (ValueError, OverflowError) as exc:
            raise AnimationProgramError("Invalid iteration range.") from exc
        if count > 64 or count * self.multiplier > MAX_LOOP_PRODUCT:
            raise AnimationProgramError("Iteration exceeds the 128-operation nested-loop budget.")
        return count

    def visit_For(self, node: ast.For) -> None:
        if not isinstance(node.target, ast.Name) or node.orelse:
            raise AnimationProgramError("Use a plain local loop variable without for/else.")
        count = self.range_count(node.iter)
        if node.target.id in self.values:
            raise AnimationProgramError("Loop variables cannot overwrite numerical constants.")
        self.bind(node.target.id)
        self.values.pop(node.target.id, None)
        self.types[node.target.id] = "number"
        self.bounds[node.target.id] = max(
            abs(_number(item, self.values) or 0) for item in node.iter.args
        )
        previous = self.multiplier
        self.multiplier *= max(1, count)
        for statement in node.body:
            self.visit(statement)
        self.multiplier = previous

    def visit_ListComp(self, node: ast.ListComp) -> None:
        if len(node.generators) != 1:
            raise AnimationProgramError("Use one bounded range per list comprehension.")
        generator = node.generators[0]
        if generator.is_async or generator.ifs or not isinstance(generator.target, ast.Name):
            raise AnimationProgramError("Unsupported comprehension shape.")
        count = self.range_count(generator.iter)
        scope = (
            set(self.names),
            dict(self.values),
            dict(self.types),
            dict(self.bounds),
            set(self.sequence_names),
        )
        self.bind(generator.target.id)
        self.values.pop(generator.target.id, None)
        self.types[generator.target.id] = "number"
        self.bounds[generator.target.id] = max(
            abs(_number(item, self.values) or 0) for item in generator.iter.args
        )
        previous = self.multiplier
        self.multiplier *= max(1, count)
        try:
            self.visit(node.elt)
        finally:
            self.multiplier = previous
            self.names, self.values, self.types, self.bounds, self.sequence_names = scope

    def visit_Lambda(self, node: ast.Lambda) -> None:
        if (
            self.lambda_depth
            or node.args.defaults
            or node.args.vararg
            or node.args.kwarg
            or node.args.kwonlyargs
            or node.args.posonlyargs
        ):
            raise AnimationProgramError("Use a simple one- or two-variable numerical lambda.")
        if not 1 <= len(node.args.args) <= 2:
            raise AnimationProgramError("Plot lambdas take one or two numerical variables.")
        previous = set(self.names)
        previous_values = dict(self.values)
        previous_types = dict(self.types)
        previous_bounds = dict(self.bounds)
        for argument in node.args.args:
            self.bind(argument.arg)
            self.values.pop(argument.arg, None)
            self.types[argument.arg] = "number"
            self.bounds[argument.arg] = 10.0
        self.lambda_depth += 1
        self.visit(node.body)
        self.lambda_depth -= 1
        self.names = previous
        self.values = previous_values
        self.types = previous_types
        self.bounds = previous_bounds

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in CONSTRUCTORS | BUILTINS:
                raise AnimationProgramError("Call only approved Manim or numerical functions.")
            if name in CONSTRUCTORS:
                if self.lambda_depth:
                    raise AnimationProgramError("Plot lambdas must return numerical values.")
                self.object_calls += self.multiplier
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
            self.visit(node.func)
            if self.lambda_depth and not (
                isinstance(node.func.value, ast.Name) and node.func.value.id in {"np", "math"}
            ):
                raise AnimationProgramError("Numerical plot lambdas cannot call object methods.")
            if isinstance(node.func.value, ast.Name) and node.func.value.id in {"np", "math"}:
                if name == "array" and (
                    len(node.args) != 1 or not isinstance(node.args[0], (ast.List, ast.Tuple))
                ):
                    raise AnimationProgramError("Use only literal bounded numerical arrays.")
                if name == "arange":
                    raise AnimationProgramError(
                        "Use bounded range loops or numerical plot lambdas instead."
                    )
        else:
            raise AnimationProgramError("Indirect or dynamically selected calls are forbidden.")
        # Optional geometry/sampling settings are keyword-only in our supported
        # subset, even when upstream Manim accepts them positionally. Never let
        # unpacking hide arguments from this boundary.
        variadic = {
            "VGroup",
            "Group",
            "Polygon",
            "AnimationGroup",
            "Succession",
            "LaggedStart",
            "play",
            "add",
            "remove",
            "shift",
            "add_fixed_in_frame_mobjects",
            "add_fixed_orientation_mobjects",
        }
        caps = {
            "Axes": 0,
            "NumberPlane": 0,
            "ThreeDAxes": 0,
            "NumberLine": 0,
            "Text": 1,
            "MathTypst": 1,
            "Sphere": 1,
            "Surface": 1,
            "Torus": 0,
            "Cylinder": 0,
            "Cone": 0,
            "Dot3D": 1,
            "ParametricFunction": 1,
            "plot": 1,
            "get_graph": 1,
            "plot_parametric_curve": 1,
            "Arc": 0,
            "Flash": 1,
            "RegularPolygon": 1,
            "arrange_in_grid": 0,
        }
        if name not in variadic and any(isinstance(arg, ast.Starred) for arg in node.args):
            raise AnimationProgramError(
                "Supply explicit positional arguments; do not unpack geometry options."
            )
        if len(node.args) > caps.get(name, 4) and name not in variadic:
            raise AnimationProgramError(
                "Supply optional geometry and sampling settings by named arguments."
            )
        if name == "add" and not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        ):
            raise AnimationProgramError(
                "Build groups with VGroup(*[...]); do not mutate object graphs with add."
            )
        if isinstance(node.func, ast.Name) and name in BUILTINS - {"range", "str", "len"}:
            limits = {"min": (2, 16), "max": (2, 16), "round": (1, 2)}
            lower, upper = limits.get(name, (1, 1))
            if not lower <= len(node.args) <= upper or any(
                self.expression_type(arg) != "number" for arg in node.args
            ):
                raise AnimationProgramError(
                    "Numerical builtins accept only explicit scalar numerical arguments."
                )
            if name == "round" and len(node.args) == 2:
                precision = _number(node.args[1], self.values)
                if precision is None or not precision.is_integer() or not 0 <= precision <= 6:
                    raise AnimationProgramError(
                        "Round precision must be a constant from zero through six."
                    )
        if name == "str" and (
            len(node.args) != 1 or self.expression_type(node.args[0]) not in {"number", "text"}
        ):
            raise AnimationProgramError(
                "Convert only bounded numerical values or text to captions."
            )
        if name == "len" and (
            len(node.args) != 1 or not isinstance(node.args[0], (ast.List, ast.Tuple, ast.Constant))
        ):
            raise AnimationProgramError("Length accepts only literal bounded sequences.")
        if self.object_calls > MAX_OBJECT_CALLS:
            raise AnimationProgramError("The program exceeds its object/animation budget.")
        numerical = (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"np", "math"}
        )
        if numerical and node.keywords:
            raise AnimationProgramError(
                "Numerical calls do not accept dtype, output or dynamic options."
            )
        if numerical and name == "array":

            def numeric_items(value):
                return (
                    all(numeric_items(item) for item in value.elts)
                    if isinstance(value, (ast.List, ast.Tuple))
                    else self.expression_type(value) == "number"
                )

            if not numeric_items(node.args[0]):
                raise AnimationProgramError("Arrays contain only bounded numerical values.")

            def shape(value, depth=0):
                if depth > 2 or len(value.elts) > 32:
                    raise AnimationProgramError(
                        "Numerical arrays are limited to two dimensions of at most 32 scalars."
                    )
                for item in value.elts:
                    if isinstance(item, (ast.List, ast.Tuple)):
                        shape(item, depth + 1)

            shape(node.args[0], 1)
        elif numerical and name == "linspace":
            values = [_number(arg, self.values) for arg in node.args]
            if (
                len(values) != 3
                or any(value is None or not math.isfinite(value) for value in values)
                or not values[2].is_integer()
                or not 2 <= values[2] <= 1024
            ):
                raise AnimationProgramError(
                    "linspace needs constant scalar endpoints and an explicit 2–1024 sample count."
                )
        elif numerical and (
            not 1 <= len(node.args) <= 2
            or any(self.expression_type(arg) not in {"number", "vector"} for arg in node.args)
        ):
            raise AnimationProgramError(
                "Numerical functions accept only bounded scalar or one-dimensional vector arguments."
            )
        allowed_keywords = set(_KEYWORDS.get(name, ()))
        if name in CONSTRUCTORS:
            allowed_keywords.update(_STYLE_KEYS)
            if name in {
                "Create",
                "Uncreate",
                "Write",
                "Unwrite",
                "FadeIn",
                "FadeOut",
                "Transform",
                "ReplacementTransform",
                "TransformFromCopy",
                "TransformMatchingShapes",
                "Rotate",
                "GrowArrow",
                "GrowFromCenter",
                "Indicate",
                "Circumscribe",
                "Wiggle",
                "MoveAlongPath",
                "AnimationGroup",
                "Succession",
                "LaggedStart",
            }:
                allowed_keywords.update(_ANIMATION_KEYS)
        if any(keyword.arg not in allowed_keywords for keyword in node.keywords):
            raise AnimationProgramError(
                f"Unsupported keyword for {name}; use only {', '.join(sorted(allowed_keywords)) or 'positional arguments'}."
            )
        if name in {"Axes", "NumberPlane", "ThreeDAxes", "NumberLine"} and node.args:
            raise AnimationProgramError("Supply axis ranges by named bounded range arguments.")
        if (
            name in {"Text", "MathTypst", "Sphere", "Surface", "Torus", "Cylinder", "Cone"}
            and len(node.args) > 1
        ):
            raise AnimationProgramError(
                "Supply optional text/geometry settings by named arguments."
            )
        if name == "RegularPolygon":
            count = (
                _number(node.args[0], self.values)
                if node.args
                else next(
                    (_number(item.value, self.values) for item in node.keywords if item.arg == "n"),
                    6,
                )
            )
            if count is None or not count.is_integer() or not 3 <= count <= 64:
                raise AnimationProgramError("Polygons support 3–64 vertices.")
        if name == "range":
            self.range_count(node)
        if name in {"play", "wait", "Wait", "move_camera"}:
            duration = 1.0
            if name in {"wait", "Wait"} and node.args:
                duration = _number(node.args[0], self.values)
                if len(node.args) > 1:
                    raise AnimationProgramError("Wait accepts one bounded duration.")
            for keyword in node.keywords:
                if keyword.arg in {"run_time", "duration"}:
                    duration = _number(keyword.value, self.values)
            if name == "play" and not any(item.arg == "run_time" for item in node.keywords):
                raise AnimationProgramError(
                    "Set an explicit constant run_time on every self.play call."
                )
            if duration is None or not 0 <= duration <= 8:
                raise AnimationProgramError(
                    "Each play/wait duration must be constant and at most 8 seconds."
                )
            if name != "Wait":
                self.duration += duration * self.multiplier
            if self.duration > 60:
                raise AnimationProgramError("The animation exceeds the one-minute timeline budget.")
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg.startswith("_"):
                raise AnimationProgramError("Dynamic/private keyword arguments are forbidden.")
            if keyword.arg in {"font", "font_family"} and (
                not isinstance(keyword.value, ast.Constant)
                or keyword.value.value
                not in {
                    "Onest",
                    "Arial",
                    "sans-serif",
                    "serif",
                }
            ):
                raise AnimationProgramError("Use a bundled/default font, never a font path.")
            if keyword.arg in {"font_size", "run_time", "num_decimal_places"}:
                value = _number(keyword.value, self.values)
                limit = {"font_size": 96, "run_time": 8, "num_decimal_places": 6}[keyword.arg]
                if value is None or not 0 <= value <= limit:
                    raise AnimationProgramError(f"Keep {keyword.arg} within {limit}.")
            if keyword.arg in {"x_range", "y_range", "z_range", "u_range", "v_range", "t_range"}:
                if (
                    not isinstance(keyword.value, (ast.List, ast.Tuple))
                    or not 2 <= len(keyword.value.elts) <= 3
                ):
                    raise AnimationProgramError(
                        "Axis/plot ranges require two or three numerical constants."
                    )
                values = [_number(item, self.values) for item in keyword.value.elts]
                if any(value is None for value in values) or values[0] >= values[1]:
                    raise AnimationProgramError("Ranges must have constant increasing endpoints.")
                if len(values) == 3 and (
                    values[2] <= 0 or (values[1] - values[0]) / values[2] > 256
                ):
                    raise AnimationProgramError(
                        "Explicit sampling/tick ranges permit at most 256 intervals."
                    )
                if len(values) == 2 and values[1] - values[0] > 64:
                    raise AnimationProgramError("A default-step range may span at most 64 units.")
            if keyword.arg in {
                "resolution",
                "num_samples",
                "n_points",
                "num_dashes",
                "num_components",
                "num_lines",
                "rows",
                "cols",
            }:
                parts = (
                    keyword.value.elts
                    if isinstance(keyword.value, (ast.List, ast.Tuple))
                    else [keyword.value]
                )
                if len(parts) > 2 or any(
                    (value := _number(item, self.values)) is None
                    or not value.is_integer()
                    or not 1 <= value <= 32
                    for item in parts
                ):
                    raise AnimationProgramError(
                        "Geometry sample counts must be constant and at most 32 per dimension."
                    )
        if name in {"MathTypst", "Text"} and node.args:
            literal = node.args[0]
            if name == "MathTypst" and (
                not isinstance(literal, ast.Constant)
                or not isinstance(literal.value, str)
                or "#" in literal.value
            ):
                raise AnimationProgramError(
                    "MathTypst accepts literal mathematical notation, not Typst commands."
                )
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_List(self, node: ast.List) -> None:
        if len(node.elts) > 128:
            raise AnimationProgramError("Literal lists are limited to 128 items.")
        self.generic_visit(node)

    visit_Tuple = visit_List


def validate_manim_program(source: str) -> str:
    """Validate real model-written Manim source without executing it or replacing its scene."""
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_PROGRAM_CHARS:
        raise AnimationProgramError("Manim source must contain 1–24000 characters.")
    source = source.strip() + "\n"
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise AnimationProgramError(f"Python syntax error: {str(exc)[:180]}") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise AnimationProgramError("The Manim program exceeds its syntax budget.")
    classes = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            if (
                statement.module != "manim"
                or statement.level
                or any(
                    alias.asname
                    or alias.name not in CONSTRUCTORS | CONSTANTS | {"*", "Scene", "ThreeDScene"}
                    for alias in statement.names
                )
            ):
                raise AnimationProgramError("Only approved imports from manim are allowed.")
        elif isinstance(statement, ast.Import):
            if len(statement.names) != 1 or (
                statement.names[0].name,
                statement.names[0].asname,
            ) not in {("numpy", "np"), ("math", None)}:
                raise AnimationProgramError("Only numpy as np and math imports are allowed.")
        elif isinstance(statement, ast.ClassDef):
            classes.append(statement)
        else:
            raise AnimationProgramError("Keep all scene code inside MutaLesson.construct(self).")
    if len(classes) != 1:
        raise AnimationProgramError("Return exactly one class named MutaLesson.")
    scene = classes[0]
    if (
        scene.name != "MutaLesson"
        or scene.decorator_list
        or scene.keywords
        or len(scene.bases) != 1
        or not isinstance(scene.bases[0], ast.Name)
        or scene.bases[0].id not in {"Scene", "ThreeDScene"}
    ):
        raise AnimationProgramError("Define class MutaLesson(Scene) or MutaLesson(ThreeDScene).")
    if len(scene.body) != 1 or not isinstance(scene.body[0], ast.FunctionDef):
        raise AnimationProgramError(
            "The scene defines only construct(self), with no class side effects."
        )
    construct = scene.body[0]
    args = construct.args
    if (
        construct.name != "construct"
        or construct.decorator_list
        or construct.returns
        or len(args.args) != 1
        or args.args[0].arg != "self"
        or args.args[0].annotation
        or args.defaults
        or args.kwonlyargs
        or args.vararg
        or args.kwarg
        or args.posonlyargs
    ):
        raise AnimationProgramError(
            "Use exactly def construct(self) without decorators or annotations."
        )
    validator = _Validator()
    try:
        for statement in construct.body:
            validator.visit(statement)
    except (RecursionError, OverflowError, ZeroDivisionError) as exc:
        raise AnimationProgramError(
            "The source exceeds safe expression depth or numerical bounds."
        ) from exc
    if validator.object_calls == 0 or validator.duration <= 0:
        raise AnimationProgramError(
            "Create visible Manim objects and play/wait to produce a video."
        )
    return source


def author_manim_program(
    engine: ChatEngine,
    request: AnimationProgramRequest,
    *,
    cancel_event: threading.Event | None = None,
) -> AnimationProgram:
    """One bounded local-model turn; every brief, including a circle, reaches this call."""
    system = (
        "You write Manim Community 0.22 Python for an offline educational animation. Return ONLY complete Python, no explanation. "
        "Use from manim import * and optionally import numpy as np or import math. Define exactly class MutaLesson(Scene): def construct(self):. "
        "Use local variables, approved geometry/axes/Text/MathTypst, Create/Write/FadeIn/Transform, self.play and self.wait. Keep it concise: at most 40 lines, six plays, no comments. "
        "Never use MathTex/Tex/LaTeX, external files/assets, configuration, renderer/camera attributes, imports other than those above, or Python introspection. "
        "Preserve requested mathematical values, axis domains, units and scale honestly. The renderer handles camera framing; never replace a requested domain with screen coordinates. "
        "Use Text for plain captions and MathTypst for literal math (no # commands); use font_size=32. "
        "Use explicit bounded numeric ranges for axes; plot with lambda x: arithmetic or np.sin(x). "
        "Loops only for i in range(N), N<=64; no while/recursion, no helper definitions. "
        "Set explicit run_time=2 on every self.play call; each play/wait at most 8 seconds, total at most 60. "
        "Use a fresh name for each assignment; build groups as VGroup(*[Dot(...) for i in range(N)]), never object.add or copy. "
        "Use optional geometry/sampling settings as keyword arguments, never starred option lists; array dimensions at most 32. "
        "Do not fade out the final teaching frame. "
        "Preserve all requested entities, quantities and relationships. Never replace an unsupported request by a generic text storyboard."
    )
    reference = (
        "\nMANDATORY CODE INTERFACE (not an animation template):\n"
        "from manim import *\nimport numpy as np\nclass MutaLesson(Scene):\n    def construct(self):\n        # Write your complete requested animation here.\n"
        "\nAPI notes: Axes(x_range=[minimum,maximum,tick_step], y_range=[minimum,maximum,tick_step], x_length=9, y_length=4). "
        "A range's third value is a STEP, not a sample count. Plot with axes.plot(lambda x: expression, x_range=[minimum,maximum], color=BLUE). "
        "axes.get_axis_labels(x_label=Text('x'), y_label=Text('y')). Do not call set_x_range, set_y_range, set_axis_labels or arange. Plot lambdas do not need precomputed arrays. "
        "For groups use VGroup with a range comprehension; loop only over range, never groups. "
        "Do not use '_' as a loop name. Use self.play(Create(object), run_time=2) and self.wait(1). "
        "Use only the learner's requested mathematical values and domains. Camera framing is automatic; do not change a radius or axis domain to fit the screen. "
        "Position captions with next_to, to_edge or shift; never put a label at the same origin as the diagram. "
        "Use Text for English and MathTypst only for mathematical notation. "
        "Your only class MUST be MutaLesson, NOT another descriptive class name."
    )
    # The minimal Studio derives a display title from the visible brief. Repeating
    # that same full request as a second instruction confused the small tutor in
    # real sine trials. Omit only redundant prompt text, never stored title/brief.
    normalized_topic = " ".join(request.topic.split())
    normalized_concept = " ".join(request.concept.split())
    topic_line = "" if normalized_topic == normalized_concept else f"Topic: {request.topic}\n"
    user = f"Learner level: {request.level}\n{topic_line}Prompt: {request.concept}\nRequirements: {request.requirements}"
    user += reference
    # Short API demonstrations teach syntax to the small installed tutor. They are
    # prompt examples, never selected/substituted scene implementations: the actual
    # returned program remains wholly authored by the model for the current brief.
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "API example: show a blue square with caption A."},
        {
            "role": "assistant",
            "content": 'from manim import *\nimport numpy as np\nclass MutaLesson(Scene):\n    def construct(self):\n        shape = Square(side_length=2, color=BLUE).shift(LEFT*2)\n        caption = Text("A", font_size=28).next_to(shape, DOWN)\n        self.play(Create(shape), Write(caption), run_time=2)\n        self.wait(1)\n',
        },
        {
            "role": "user",
            "content": "API example: trace the line y=x+1 from -2 to2, with labelled axes.",
        },
        {
            "role": "assistant",
            "content": 'from manim import *\nimport numpy as np\nclass MutaLesson(Scene):\n    def construct(self):\n        axes = Axes(x_range=[-2,2,1], y_range=[-2,4,1], x_length=8, y_length=4)\n        labels = axes.get_axis_labels(x_label=Text("x",font_size=24),y_label=Text("y",font_size=24))\n        curve = axes.plot(lambda x:x+1, x_range=[-2,2], color=BLUE)\n        title = Text("y=x+1",font_size=28).to_edge(UP)\n        self.play(Create(axes), Write(labels), Write(title), run_time=2)\n        self.play(Create(curve), run_time=2)\n        self.wait(1)\n',
        },
        {
            "role": "user",
            "content": "API example: arrange six dots as two rows of three, then show a count caption.",
        },
        {
            "role": "assistant",
            "content": 'from manim import *\nimport numpy as np\nclass MutaLesson(Scene):\n    def construct(self):\n        dots = VGroup(*[Dot(color=TEAL).shift((i%3)*RIGHT+(i//3)*DOWN) for i in range(6)]).center()\n        caption = Text("2 rows, 3 per row: 6 dots",font_size=32).next_to(dots,DOWN)\n        self.play(FadeIn(dots), Write(caption), run_time=2)\n        self.wait(1)\n',
        },
        {
            "role": "user",
            "content": user
            + "\nNow write a NEW complete animation for this learner's request, not any API example.",
        },
    ]
    if request.previous_source:
        messages.extend(
            [
                {"role": "assistant", "content": request.previous_source},
                {
                    "role": "user",
                    "content": f"Your program was rejected: {request.feedback}\nRewrite the COMPLETE program, not a patch. Fix this diagnostic while keeping the original quantities and requirements. Use class MutaLesson(Scene). Return only Python.",
                },
            ]
        )
    params = {"temperature": 0.15, "top_p": 0.9, "max_tokens": 2400, "enable_thinking": False}
    if cancel_event is not None and cancel_event.is_set():
        raise AnimationProgramError("Animation generation cancelled.")
    stream = None
    cancel_event = cancel_event or threading.Event()
    deadline = threading.Timer(180, cancel_event.set)
    deadline.daemon = True
    deadline.start()
    chunks = []
    try:
        messages, fitted = engine._fit_request(
            messages,
            params,
            protected_tail_messages=3 if request.previous_source else 1,
        )
        client = getattr(engine.client, "local", engine.client)
        if cancel_event is not None:
            fitted["_muta_cancel_event"] = cancel_event
        stream = client.stream_events(messages, **fitted)
        length = 0
        for event, value in stream:
            if cancel_event is not None and cancel_event.is_set():
                raise AnimationProgramError("Animation generation cancelled.")
            if event == "content" and value:
                length += len(value)
                if length > MAX_PROGRAM_CHARS:
                    raise AnimationProgramError("The model program exceeds the source budget.")
                chunks.append(value)
        source = "".join(chunks).strip()
        fenced = re.fullmatch(r"```(?:python)?\s*\n(.*?)\n```", source, re.DOTALL)
        if fenced:
            source = fenced.group(1)
        try:
            source = validate_manim_program(source)
        except AnimationProgramError as exc:
            raise AnimationProgramError(str(exc), source=source) from exc
        program = AnimationProgram(
            id=f"program-{uuid.uuid4().hex[:24]}",
            title=" ".join((request.topic or request.concept).split())[:180],
            level=request.level,
            source=source,
            source_sha256=source_hash(source),
            model_id=str(getattr(client, "model", ""))[:180],
            created_at=datetime.now(UTC).isoformat(),
            brief=json.dumps(
                {
                    "topic": request.topic,
                    "level": request.level,
                    "concept": request.concept,
                    "requirements": request.requirements,
                },
                ensure_ascii=False,
            ),
        )
        return program.model_copy(update={"generation_token": _generation_token(program)})
    except InferenceStreamError as exc:
        partial = "".join(chunks) or exc.partial_text
        raise AnimationProgramError(
            "The model did not finish a complete program; return a shorter complete scene.",
            source=partial,
        ) from exc
    finally:
        deadline.cancel()
        close = getattr(stream, "close", None)
        if callable(close):
            close()
