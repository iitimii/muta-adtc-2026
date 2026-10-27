from __future__ import annotations

import json
from pathlib import Path

from scripts import refresh_desktop_manifests, stage_desktop


def test_refresh_records_post_signing_worker_bytes(tmp_path: Path, monkeypatch) -> None:
    resources = tmp_path / "resources"
    worker = resources / "bin" / "muta-manim"
    worker.mkdir(parents=True)
    executable = worker / "muta-manim"
    executable.write_bytes(b"before-signing")
    executable.chmod(0o755)
    (worker / "licenses").mkdir()
    (worker / "licenses" / "index.json").write_text("{}", encoding="utf-8")
    worker_manifest = {
        "schema": 1,
        "target": {"os": "macos", "arch": "aarch64"},
        "runtime": {
            "python": "3.11.15",
            "manim": "0.22.0",
            "typst": "0.15.0",
            "pyinstaller": "6.22.2",
        },
        "files": [],
        "native_libraries": [],
    }
    (worker / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps(worker_manifest), encoding="utf-8"
    )
    product = {
        "schema": 1,
        "target": {"os": "macos", "arch": "aarch64"},
        "manim_worker": {"path": "bin/muta-manim/muta-manim"},
    }
    (resources / "desktop-product.json").write_text(json.dumps(product), encoding="utf-8")
    (resources / "desktop-manifest.json").write_text(
        json.dumps({"schema": 1, "files": []}), encoding="utf-8"
    )
    monkeypatch.setattr(refresh_desktop_manifests, "native_libraries", lambda _root: [])
    monkeypatch.setattr(refresh_desktop_manifests, "verify", lambda *_args: {})

    executable.write_bytes(b"after-signing")
    refresh_desktop_manifests.refresh(resources)

    refreshed = json.loads((resources / "desktop-product.json").read_text())
    assert refreshed["manim_worker"]["size_bytes"] == len(b"after-signing")
    assert refreshed["manim_worker"]["sha256"] == stage_desktop.sha256_file(executable)
    stage_desktop.verify_root(resources, "desktop-manifest.json")


def test_refresh_keeps_workerless_macos_package_manifest_coherent(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    nested = resources / "bin/ffmpeg"
    nested.parent.mkdir()
    nested.write_bytes(b"after-signing")
    product = {
        "schema": 1,
        "target": {"os": "macos", "arch": "aarch64"},
    }
    (resources / "desktop-product.json").write_text(json.dumps(product), encoding="utf-8")
    (resources / "desktop-manifest.json").write_text(
        json.dumps({"schema": 1, "files": []}), encoding="utf-8"
    )

    refresh_desktop_manifests.refresh(resources)

    refreshed_product = json.loads((resources / "desktop-product.json").read_text())
    assert "manim_worker" not in refreshed_product
    stage_desktop.verify_root(resources, "desktop-manifest.json")
