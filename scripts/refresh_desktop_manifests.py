#!/usr/bin/env python3
"""Refresh desktop integrity manifests after macOS changes nested code signatures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_manim_worker import manifest_entries, native_libraries, sha256_file
from stage_desktop import StageError, _manifest_entries, verify_root
from verify_manim_worker import MANIFEST_NAME, VerificationError, verify


class RefreshError(RuntimeError):
    pass


def refresh(app_resources: Path) -> None:
    root = app_resources.resolve()
    product_path = root / "desktop-product.json"
    desktop_manifest_path = root / "desktop-manifest.json"
    if not product_path.is_file() or not desktop_manifest_path.is_file():
        raise RefreshError(f"desktop manifests are missing below {root}")

    product = json.loads(product_path.read_text(encoding="utf-8"))
    target = product.get("target") or {}
    if target.get("os") != "macos" or target.get("arch") not in {"aarch64", "x86_64"}:
        raise RefreshError("desktop manifest does not identify a supported macOS target")
    selected = product.get("manim_worker")
    if selected:
        worker_root = root / "bin" / "muta-manim"
        worker_manifest_path = worker_root / MANIFEST_NAME
        if not worker_manifest_path.is_file():
            raise RefreshError(f"Manim worker manifest is missing: {worker_manifest_path}")
        worker_manifest = json.loads(worker_manifest_path.read_text(encoding="utf-8"))
        if worker_manifest.get("target") != target:
            raise RefreshError("Manim worker target differs from the desktop package target")

        # Code signing changes the Mach-O bytes. Recompute the worker inventory first, then the
        # product's executable identity, and finally the enclosing desktop tree manifest.
        worker_manifest["native_libraries"] = native_libraries(worker_root)
        worker_manifest["files"] = manifest_entries(worker_root)
        worker_manifest_path.write_text(
            json.dumps(worker_manifest, indent=2) + "\n", encoding="utf-8"
        )

        executable = worker_root / "muta-manim"
        selected.update(
            {
                "path": "bin/muta-manim/muta-manim",
                "size_bytes": executable.stat().st_size,
                "sha256": sha256_file(executable),
                "manifest": f"bin/muta-manim/{MANIFEST_NAME}",
                "runtime": worker_manifest.get("runtime", {}),
            }
        )
        product_path.write_text(json.dumps(product, indent=2) + "\n", encoding="utf-8")

    desktop_manifest = json.loads(desktop_manifest_path.read_text(encoding="utf-8"))
    desktop_manifest["files"] = _manifest_entries(
        root, exclude={desktop_manifest_path.name}
    )
    desktop_manifest_path.write_text(
        json.dumps(desktop_manifest, indent=2) + "\n", encoding="utf-8"
    )

    if selected:
        verify(worker_root, str(target["arch"]))
    verify_root(root, desktop_manifest_path.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-resources", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        refresh(args.app_resources)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        RefreshError,
        StageError,
        VerificationError,
    ) as error:
        print(f"desktop manifest refresh failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
