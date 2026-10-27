"""Fixed resource-limit wrapper for the trusted offline Manim subprocess."""

from __future__ import annotations

import os
import sys

try:
    import resource
except ImportError:  # pragma: no cover - Windows package builds
    resource = None  # type: ignore[assignment]

MAX_VIDEO_BYTES = 96 * 1024 * 1024


def _install_limits() -> None:
    if resource is None:
        return
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_VIDEO_BYTES, MAX_VIDEO_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    # RLIMIT_NPROC is per user rather than per process on common POSIX systems. Setting it
    # here can prevent Manim from starting FFmpeg when the desktop already has other local
    # workers, so concurrency is bounded by the gateway's single render admission instead.


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--animation-worker":
        args.pop(0)
    if not args:
        return 64
    _install_limits()
    executable = os.path.realpath(args[0])
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        return 69
    os.execve(executable, [executable, *args[1:]], dict(os.environ))
    return 70  # pragma: no cover - execve replaces the process on success


if __name__ == "__main__":
    raise SystemExit(main())
