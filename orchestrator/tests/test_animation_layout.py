"""Trusted layout wrapper unit fixtures use fake Manim; no authored code is executed."""

import runpy
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from orchestrator.gateway.animation_layout import RUNNER_SOURCE


class Object:
    def __init__(self, width=2, height=2, x=0, y=0):
        self.points = np.array(
            [[x - width / 2, y - height / 2, 0], [x + width / 2, y + height / 2, 0]]
        )

    def get_all_points(self):
        return self.points

    def get_family(self):
        return [self]

    def get_fill_opacity(self):
        return 1

    def get_stroke_opacity(self):
        return 0

    def get_stroke_width(self):
        return 1


class Scene:
    def __init__(self):
        self.mobjects = []
        self.camera = SimpleNamespace(frame_center=[0, 0, 0], frame_width=14.2, frame_height=8)
        self.camera.pixel_array_to_cairo_context = {"old": "old projection"}
        self.renderer = SimpleNamespace(static_image="old projection")

    def play(self, *animations, **kwargs):
        self.plays = getattr(self, "plays", 0) + 1
        self.mobjects.extend(
            a.mobject for a in animations if getattr(a, "mobject", None) is not None
        )
        for animation in animations:
            if getattr(animation, "after", None):
                animation.after()

    def tear_down(self):
        pass


def wrapped(tmp_path, monkeypatch):
    fake = ModuleType("manim")
    fake.Mobject = Object
    fake.VMobject = Object
    fake.Scene = Scene
    fake.ThreeDScene = type("ThreeDScene", (Scene,), {})
    fake.Wait = lambda *args, **kwargs: SimpleNamespace(mobject=None)
    monkeypatch.setitem(sys.modules, "manim", fake)
    (tmp_path / "lesson.py").write_text(
        "from manim import Scene\nclass MutaLesson(Scene):\n    pass\n"
    )
    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER_SOURCE)
    return runpy.run_path(runner)["MutaLesson"]()


def test_normal_geometry_and_actual_animation_target_pass(tmp_path, monkeypatch):
    scene = wrapped(tmp_path, monkeypatch)
    scene.play(SimpleNamespace(mobject=Object()))
    scene.tear_down()
    assert len(scene.mobjects) == 1


def test_large_or_offscreen_composition_fits_camera_without_changing_geometry(
    tmp_path, monkeypatch
):
    for obj in (Object(11.2, 11.2), Object(x=20)):
        scene = wrapped(tmp_path, monkeypatch)
        original = obj.points.copy()
        scene.play(SimpleNamespace(mobject=obj))
        np.testing.assert_array_equal(obj.points, original)
        assert scene.camera.frame_height >= 8
        assert scene.camera.frame_width / scene.camera.frame_height == pytest.approx(14.2 / 8)
        assert scene.camera.pixel_array_to_cairo_context == {}
        assert scene.renderer.static_image is None


def test_extreme_viewport_is_rejected_instead_of_shrinking_labels_indefinitely(
    tmp_path, monkeypatch
):
    scene = wrapped(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="too large to keep labels readable"):
        scene.play(SimpleNamespace(mobject=Object(1000, 1000)))


def test_final_blank_and_nonfinite_geometry_are_not_presented_as_success(tmp_path, monkeypatch):
    scene = wrapped(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="final teaching frame is empty"):
        scene.tear_down()
    obj = Object()
    obj.points[0, 0] = np.nan
    with pytest.raises(ValueError, match="undefined coordinates"):
        scene.play(SimpleNamespace(mobject=obj))


def test_transparent_final_objects_do_not_count_as_visible(tmp_path, monkeypatch):
    scene = wrapped(tmp_path, monkeypatch)
    obj = Object()
    obj.get_fill_opacity = lambda: 0
    scene.mobjects = [obj]
    with pytest.raises(ValueError, match="empty or transparent"):
        scene.tear_down()


def test_nonrenderable_value_tracker_does_not_distort_bounds(tmp_path, monkeypatch):
    scene = wrapped(tmp_path, monkeypatch)

    class Tracker:
        def get_family(self):
            return [self]

    scene.mobjects = [Object(), Tracker()]
    scene.tear_down()


def test_post_animation_reframing_encodes_a_corrected_final_view(tmp_path, monkeypatch):
    scene = wrapped(tmp_path, monkeypatch)
    obj = Object()
    scene.play(SimpleNamespace(mobject=obj, after=lambda: obj.points.__iadd__([20, 0, 0])))
    assert scene.plays == 2  # Original animation, then an explicitly encoded fitted hold.
    assert scene.camera.frame_center[0] == pytest.approx(20)
