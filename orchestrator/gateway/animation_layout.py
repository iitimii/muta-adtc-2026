"""Fixed worker-side layout diagnostics; never generates or replaces learner geometry.

The model's original bytes remain lesson.py. This separate, trusted entry scene imports that
fixed file and frames its visible 2D extents uniformly at animation boundaries. The camera
changes, never geometry or mathematical values; unsupported/extreme layouts return feedback.
It is not a mathematical correctness proof or a full intermediate-frame collision checker.
"""

RUNNER_SOURCE = """from pathlib import Path
import importlib.util
import numpy as np
from manim import Mobject, VMobject, ThreeDScene, Wait

_spec = importlib.util.spec_from_file_location("muta_authored_lesson", Path(__file__).with_name("lesson.py"))
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_LearnerScene = _module.MutaLesson

class MutaLesson(_LearnerScene):
    def _muta_check_layout(self, animations=(), final=False):
        objects = list(self.mobjects)
        for animation in animations:
            for attribute in ("mobject", "target_mobject"):
                item = getattr(animation, attribute, None)
                if isinstance(item, Mobject):
                    objects.append(item)
                    target = getattr(item, "target", None)
                    if isinstance(target, Mobject):
                        objects.append(target)
        points = []
        seen = set()
        for parent in objects:
            for item in parent.get_family():
                if id(item) in seen or not isinstance(item, VMobject):
                    continue
                seen.add(id(item))
                filled = float(np.max(item.get_fill_opacity())) > 0
                stroked = float(np.max(item.get_stroke_opacity())) > 0 and float(np.max(item.get_stroke_width())) > 0
                if not (filled or stroked):
                    continue
                if len(item.points):
                    points.append(item.points)
        if not points:
            if final:
                raise ValueError("MUTA_LAYOUT: The final teaching frame is empty or transparent. Keep the finished diagram visible instead of fading everything out.")
            return
        if isinstance(self, ThreeDScene):
            return
        coordinates = np.concatenate(points, axis=0)[:, :2]
        if not np.isfinite(coordinates).all():
            raise ValueError("MUTA_LAYOUT: Geometry contains undefined coordinates. Choose a finite valid plotting domain.")
        low, high = coordinates.min(axis=0), coordinates.max(axis=0)
        center = np.array(self.camera.frame_center)[:2]
        size = np.array([self.camera.frame_width, self.camera.frame_height])
        available = size - 0.2
        if np.any(low < center - size/2 - 0.03) or np.any(high > center + size/2 + 0.03):
            extent = np.maximum(high - low, 0.01)
            factor = max(1.0, float(np.max((extent + 0.8) / available)))
            framed = size * factor
            if framed[1] > 32 or np.any(extent > 100):
                raise ValueError("MUTA_LAYOUT: The composition is too large to keep labels readable. Use a consistent display scale for geometry before animation and retain the original values in labels.")
            # Uniform camera framing preserves angles, lengths relative to one
            # another, labels, and the source's actual mathematical coordinates.
            self.camera.frame_width = float(framed[0])
            self.camera.frame_height = float(framed[1])
            self.camera.frame_center = np.array([(low[0]+high[0])/2, (low[1]+high[1])/2, self.camera.frame_center[2]])
            self.camera.pixel_array_to_cairo_context.clear()
            self.renderer.static_image = None
            return True
        return False

    def _muta_encode_fitted_frame(self):
        count = getattr(self, "_muta_framing_holds", 0) + 1
        if count > 12:
            raise ValueError("MUTA_LAYOUT: Too many abrupt framing changes. Keep a coherent, consistently scaled composition.")
        self._muta_framing_holds = count
        # Changing the camera after a play does not rewrite already encoded
        # frames. Explicitly encode a short corrected final view before finish.
        super().play(Wait(0.15, frozen_frame=False), run_time=0.15)

    def play(self, *animations, **kwargs):
        self._muta_check_layout(animations)
        result = super().play(*animations, **kwargs)
        if self._muta_check_layout():
            self._muta_encode_fitted_frame()
        return result

    def tear_down(self):
        if self._muta_check_layout(final=True):
            self._muta_encode_fitted_frame()
        return super().tear_down()
"""
