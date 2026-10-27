"""Frozen CLI-compatible entry point for Muta's trusted Manim worker."""

from __future__ import annotations

import multiprocessing


def main() -> None:
    # PyInstaller must intercept Python's resource-tracker/spawn command lines before Manim's
    # heavy imports. Without this, a cold frozen render can spawn this CLI with Python's ``-B``
    # flag and leave a misleading Click error on stderr after a successful video render.
    multiprocessing.freeze_support()
    from manim.__main__ import main as manim_main

    manim_main()


if __name__ == "__main__":
    main()
