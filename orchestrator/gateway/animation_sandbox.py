"""Fail-closed macOS isolation for validated, model-authored Manim programs.

The source validator in :mod:`animation_program` limits the language the model may use.  This
module is the separate operating-system boundary: it stages a manifest-verified frozen worker,
runs only that executable under a deny-by-default Seatbelt profile, bounds the whole process
tree and job directory, and reads one fixed MP4 without following links.

``sandbox-exec`` is deprecated by Apple.  Its absence, a failed policy probe, or an unverified
worker therefore makes the capability unavailable; there is deliberately no unsandboxed
fallback.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import psutil

from orchestrator.gateway.animation_layout import RUNNER_SOURCE
from orchestrator.gateway.animation_render import (
    MAX_VIDEO_BYTES,
    AnimationRenderBusyError,
    AnimationRenderError,
    _render_lock,
)

_SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
_PRIVATE_TEMP = Path("/private/tmp")
_MANIFEST_NAME = "MUTA-MANIM-MANIFEST.json"
_SCENE_NAME = "MutaLesson"
_SOURCE_NAME = "lesson.py"
_RUNNER_NAME = "runner.py"
_OUTPUT_PARTS_BY_QUALITY = {
    "-ql": ("media", "videos", "runner", "480p15", "result.mp4"),
    "-qm": ("media", "videos", "runner", "720p30", "result.mp4"),
}
_OUTPUT_PARTS = _OUTPUT_PARTS_BY_QUALITY["-qm"]

_MAX_SOURCE_BYTES = 96 * 1024
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_CAPTURE_BYTES = 128 * 1024
_MAX_JOB_BYTES = 384 * 1024 * 1024
_MAX_JOB_ENTRIES = 4096
_MAX_RSS_BYTES = 1536 * 1024 * 1024
_MIN_FREE_BYTES = 768 * 1024 * 1024
_MAX_PROCESSES = 16
_CPU_SECONDS = 140
_WALL_SECONDS = 150.0
_FILE_BYTES = 128 * 1024 * 1024
_MONITOR_INTERVAL_SECONDS = 0.03
_DIRECTORY_SCAN_INTERVAL_SECONDS = 0.25
_CAPABILITY_WAIT_SECONDS = 30.0
_FAILURE_CACHE_SECONDS = 15.0

_SYSTEM_READ_ROOTS = (
    "/System",
    "/usr/lib",
    "/usr/share",
    "/Library/Apple",
    "/Library/Fonts",
    "/usr/libexec/rosetta",
    "/private/var/db/oah",
    "/private/var/db/dyld",
    "/private/var/db/timezone",
    "/private/etc",
)
_METADATA_ANCESTORS = (
    "/",
    "/usr",
    "/Library",
    "/private",
    "/private/var",
    "/private/var/db",
    "/dev",
)


@dataclass(frozen=True)
class _WorkerIdentity:
    key: tuple[object, ...]
    root: Path
    executable: Path
    manifest_sha256: str
    executable_sha256: str


@dataclass(frozen=True)
class _CapabilityRecord:
    identity_key: tuple[object, ...]
    stage_container: Path
    root: Path
    executable: Path
    detail: str


@dataclass(frozen=True)
class _ProcessResult:
    returncode: int
    output: bytes
    peak_rss: int


_cache_lock = threading.Lock()
_probe_lock = threading.Lock()
_capability_cache: dict[tuple[object, ...], _CapabilityRecord] = {}
_capability_failures: dict[tuple[object, ...], tuple[float, str]] = {}
_stage_containers: set[Path] = set()


class _CapabilityCancelled(AnimationRenderError):
    """A caller cancelled capability verification; never cache this as an unavailable worker."""


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise _CapabilityCancelled("Model-code sandbox verification was cancelled")


def _cached_failure(key: tuple[object, ...]) -> str | None:
    failure = _capability_failures.get(key)
    if failure is None:
        return None
    expires_at, detail = failure
    if expires_at > time.monotonic():
        return detail
    _capability_failures.pop(key, None)
    return None


def _sha256_file(
    path: Path,
    *,
    maximum: int | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[str, int]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise AnimationRenderError("the animation worker contains a non-regular file")
        if maximum is not None and info.st_size > maximum:
            raise AnimationRenderError("the animation worker manifest exceeds its size budget")
        digest = hashlib.sha256()
        remaining = info.st_size
        while remaining:
            _raise_if_cancelled(cancel_event)
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise AnimationRenderError("the animation worker file changed while verified")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise AnimationRenderError("the animation worker file grew while verified")
        return digest.hexdigest(), info.st_size
    finally:
        os.close(descriptor)


def _safe_manifest_path(root: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise AnimationRenderError("the animation worker manifest has an invalid path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise AnimationRenderError("the animation worker manifest has an unsafe path")
    return root.joinpath(*pure.parts)


def _runtime_entries(
    root: Path, cancel_event: threading.Event | None = None
) -> set[str]:
    entries: set[str] = set()

    def walk(directory: Path) -> None:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                _raise_if_cancelled(cancel_event)
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if relative == _MANIFEST_NAME:
                    continue
                if entry.is_symlink():
                    entries.add(relative)
                elif entry.is_dir(follow_symlinks=False):
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    entries.add(relative)
                else:
                    raise AnimationRenderError("the animation worker contains a special file")

    walk(root)
    return entries


def _load_and_verify_runtime(
    executable: Path, cancel_event: threading.Event | None = None
) -> _WorkerIdentity:
    _raise_if_cancelled(cancel_event)
    if executable.is_symlink():
        raise AnimationRenderError("the animation worker executable may not be a symlink")
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise AnimationRenderError("the animation worker executable is unavailable") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise AnimationRenderError("the animation worker executable is not executable")
    root = resolved.parent
    manifest_path = root / _MANIFEST_NAME
    manifest_sha, manifest_size = _sha256_file(
        manifest_path,
        maximum=_MAX_MANIFEST_BYTES,
        cancel_event=cancel_event,
    )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(manifest_path, flags)
    try:
        manifest_bytes = os.read(descriptor, manifest_size + 1)
    finally:
        os.close(descriptor)
    if len(manifest_bytes) != manifest_size:
        raise AnimationRenderError("the animation worker manifest changed while verified")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnimationRenderError("the animation worker manifest is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise AnimationRenderError("the animation worker manifest schema is unsupported")
    files = manifest.get("files")
    if not isinstance(files, list) or not files or len(files) > 4096:
        raise AnimationRenderError("the animation worker manifest file list is invalid")

    listed: set[str] = set()
    executable_sha = ""
    for item in files:
        _raise_if_cancelled(cancel_event)
        if not isinstance(item, dict):
            raise AnimationRenderError("the animation worker manifest entry is invalid")
        path = _safe_manifest_path(root, item.get("path"))
        relative = path.relative_to(root).as_posix()
        if relative in listed:
            raise AnimationRenderError("the animation worker manifest contains a duplicate path")
        listed.add(relative)
        kind = item.get("type")
        if kind == "file":
            if set(item) != {"path", "type", "size_bytes", "sha256"}:
                raise AnimationRenderError("the animation worker file entry is invalid")
            expected_size = item.get("size_bytes")
            expected_sha = item.get("sha256")
            if (
                type(expected_size) is not int
                or expected_size < 0
                or not isinstance(expected_sha, str)
                or len(expected_sha) != 64
            ):
                raise AnimationRenderError("the animation worker file identity is invalid")
            actual_sha, actual_size = _sha256_file(path, cancel_event=cancel_event)
            if actual_size != expected_size or actual_sha != expected_sha:
                raise AnimationRenderError("the animation worker does not match its manifest")
            if path == resolved:
                executable_sha = actual_sha
        elif kind == "symlink":
            if set(item) != {"path", "type", "target"} or not isinstance(item.get("target"), str):
                raise AnimationRenderError("the animation worker symlink entry is invalid")
            if not path.is_symlink() or os.readlink(path) != item["target"]:
                raise AnimationRenderError("the animation worker symlink does not match its manifest")
            try:
                target = path.resolve(strict=True)
                target.relative_to(root)
            except (OSError, ValueError) as exc:
                raise AnimationRenderError("the animation worker symlink escapes its runtime") from exc
            if not target.is_file():
                raise AnimationRenderError("the animation worker symlink target is not a file")
        else:
            raise AnimationRenderError("the animation worker manifest entry type is unsupported")

    if listed != _runtime_entries(root, cancel_event):
        raise AnimationRenderError("the animation worker runtime and manifest file sets differ")
    if not executable_sha:
        raise AnimationRenderError("the animation worker executable is absent from its manifest")
    info = os.stat(resolved, follow_symlinks=False)
    key: tuple[object, ...] = (
        str(resolved),
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        executable_sha,
        manifest_sha,
    )
    return _WorkerIdentity(key, root, resolved, manifest_sha, executable_sha)


def _quick_identity(
    executable: Path, cancel_event: threading.Event | None = None
) -> tuple[object, ...]:
    _raise_if_cancelled(cancel_event)
    if executable.is_symlink():
        raise AnimationRenderError("the animation worker executable may not be a symlink")
    try:
        resolved = executable.resolve(strict=True)
        info = os.stat(resolved, follow_symlinks=False)
    except OSError as exc:
        raise AnimationRenderError("the animation worker executable is unavailable") from exc
    executable_sha, _size = _sha256_file(resolved, cancel_event=cancel_event)
    manifest_sha, _manifest_size = _sha256_file(
        resolved.parent / _MANIFEST_NAME,
        maximum=_MAX_MANIFEST_BYTES,
        cancel_event=cancel_event,
    )
    return (
        str(resolved),
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        executable_sha,
        manifest_sha,
    )


def _make_writable_for_cleanup(root: Path) -> None:
    if not root.exists():
        return
    for directory, names, _files in os.walk(root, topdown=False, followlinks=False):
        for name in names:
            path = Path(directory) / name
            if not path.is_symlink():
                try:
                    path.chmod(0o700)
                except OSError:
                    pass
        try:
            Path(directory).chmod(0o700)
        except OSError:
            pass


def _remove_stage(container: Path) -> None:
    if not container.exists():
        return
    _make_writable_for_cleanup(container)
    shutil.rmtree(container)


def _cleanup_stages() -> None:
    for container in tuple(_stage_containers):
        try:
            _remove_stage(container)
        except OSError:
            pass


atexit.register(_cleanup_stages)


def _stage_runtime(
    identity: _WorkerIdentity, cancel_event: threading.Event | None = None
) -> _CapabilityRecord:
    _raise_if_cancelled(cancel_event)
    if not _PRIVATE_TEMP.is_dir() or not os.access(_PRIVATE_TEMP, os.W_OK | os.X_OK):
        raise AnimationRenderError("the private renderer staging location is unavailable")
    home = Path.home().resolve()
    container = Path(tempfile.mkdtemp(prefix="muta-manim-runtime-", dir=_PRIVATE_TEMP)).resolve()
    if container == home or home in container.parents:
        _remove_stage(container)
        raise AnimationRenderError("the renderer runtime may not be staged in the user home")
    container.chmod(0o700)
    staged_root = container / "runtime"
    try:
        _clone_runtime_tree(identity.root, staged_root, container, cancel_event)
        _raise_if_cancelled(cancel_event)
        staged_executable = staged_root / identity.executable.name
        staged_identity = _load_and_verify_runtime(staged_executable, cancel_event)
        if (
            staged_identity.executable_sha256 != identity.executable_sha256
            or staged_identity.manifest_sha256 != identity.manifest_sha256
        ):
            raise AnimationRenderError("the staged animation worker identity changed")
        for directory, names, files in os.walk(staged_root, topdown=False, followlinks=False):
            _raise_if_cancelled(cancel_event)
            for name in files:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                mode = path.stat(follow_symlinks=False).st_mode
                path.chmod(0o555 if mode & 0o111 else 0o444)
            for name in names:
                path = Path(directory) / name
                if not path.is_symlink():
                    path.chmod(0o555)
            Path(directory).chmod(0o555)
        _stage_containers.add(container)
        return _CapabilityRecord(
            identity.key,
            container,
            staged_root,
            staged_executable,
            "Verified model-code sandbox is ready.",
        )
    except Exception:
        _remove_stage(container)
        raise


def _clone_runtime_tree(
    source: Path,
    destination: Path,
    container: Path,
    cancel_event: threading.Event | None,
) -> None:
    """Create an APFS clone so macOS preserves frozen native code-signature metadata."""
    if destination.exists():
        raise AnimationRenderError("the renderer runtime staging destination already exists")
    _run_bounded_process(
        ["/bin/cp", "-cR", str(source), str(destination)],
        cwd=container,
        environment={
            "HOME": str(container),
            "TMPDIR": str(container),
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
        cancel_event=cancel_event,
    )


def _profile_text() -> str:
    system_filters = "\n".join(f'    (subpath "{root}")' for root in _SYSTEM_READ_ROOTS)
    metadata_ancestors = "\n".join(
        f'    (literal "{root}")' for root in _METADATA_ANCESTORS
    )
    return f'''(version 1)
(deny default)
(allow process-exec (literal (param "WORKER")))
(allow process-info* (target self))
(allow signal (target self))
(allow sysctl-read)
(allow file-read-metadata
{metadata_ancestors}
    (subpath "/private/tmp")
{system_filters}
    (subpath (param "WORKER_ROOT"))
    (subpath (param "JOB"))
    (literal "/dev/null")
    (literal "/dev/urandom")
    (literal "/dev/random"))
(allow file-read*
    (literal "/")
{system_filters}
    (subpath (param "WORKER_ROOT"))
    (subpath (param "JOB"))
    (literal "/dev/null")
    (literal "/dev/urandom")
    (literal "/dev/random"))
(allow file-map-executable (subpath (param "WORKER_ROOT")))
(allow file-write* (subpath (param "JOB")) (literal "/dev/null"))
'''


def _write_new_file(path: Path, payload: bytes, *, executable: bool = False) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o700 if executable else 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _tree_usage(pid: int) -> tuple[int, int]:
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0, 0
    rss = 0
    count = 0
    for process in processes:
        try:
            rss += process.memory_info().rss
            count += 1
        except psutil.Error:
            continue
    return rss, count


def _job_usage(root: Path) -> tuple[int, int, bool]:
    total = 0
    entries = 0
    has_symlink = False
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as iterator:
            for entry in iterator:
                entries += 1
                if entry.is_symlink():
                    has_symlink = True
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                else:
                    has_symlink = True
    return total, entries, has_symlink


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _resource_wrapped_command(command: list[str]) -> list[str]:
    """Apply child-only limits without unsafe ``preexec_fn`` use in the threaded gateway."""
    # macOS /bin/sh expresses the file-size limit in 512-byte blocks.  The fixed script contains
    # no model-controlled bytes; every caller argument is passed through the positional array.
    file_blocks = (_FILE_BYTES + 511) // 512
    limits = (
        "set -eu; "
        f"ulimit -t {_CPU_SECONDS}; "
        f"ulimit -f {file_blocks}; "
        "ulimit -n 128; "
        "ulimit -c 0; "
        'exec "$@"'
    )
    return ["/bin/sh", "-c", limits, "muta-render-limits", *command]


def _safe_tail(payload: bytes) -> str:
    text = payload[-1600:].decode("utf-8", errors="replace")
    return "".join(character if character.isprintable() or character in "\n\t" else "?" for character in text)


def _run_bounded_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    cancel_event: threading.Event | None,
) -> _ProcessResult:
    if shutil.disk_usage(cwd).free < _MIN_FREE_BYTES:
        raise AnimationRenderError("There is not enough free space for an offline animation.")
    process = subprocess.Popen(
        _resource_wrapped_command(command),
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    captured = bytearray()
    output_total = 0
    output_exceeded = threading.Event()

    def drain() -> None:
        nonlocal output_total
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(16384)
            if not chunk:
                return
            output_total += len(chunk)
            if len(captured) < _MAX_CAPTURE_BYTES:
                captured.extend(chunk[: _MAX_CAPTURE_BYTES - len(captured)])
            if output_total > _MAX_CAPTURE_BYTES:
                output_exceeded.set()
                _kill_process_group(process.pid)

    reader = threading.Thread(target=drain, name="muta-manim-output", daemon=True)
    reader.start()
    started = time.monotonic()
    deadline = started + _WALL_SECONDS
    next_directory_scan = started
    peak_rss = 0
    reason: str | None = None
    try:
        while process.poll() is None:
            now = time.monotonic()
            rss, process_count = _tree_usage(process.pid)
            peak_rss = max(peak_rss, rss)
            if cancel_event is not None and cancel_event.is_set():
                reason = "cancelled"
            elif output_exceeded.is_set():
                reason = "output"
            elif peak_rss > _MAX_RSS_BYTES:
                reason = "memory"
            elif process_count > _MAX_PROCESSES:
                reason = "processes"
            elif now >= deadline:
                reason = "timeout"
            elif now >= next_directory_scan:
                try:
                    job_bytes, entries, _has_symlink = _job_usage(cwd)
                    free = shutil.disk_usage(cwd).free
                except OSError:
                    reason = "job"
                else:
                    if (
                        job_bytes > _MAX_JOB_BYTES
                        or entries > _MAX_JOB_ENTRIES
                        or free < _MIN_FREE_BYTES
                    ):
                        reason = "job"
                next_directory_scan = now + _DIRECTORY_SCAN_INTERVAL_SECONDS
            if reason is not None:
                _kill_process_group(process.pid)
                break
            time.sleep(_MONITOR_INTERVAL_SECONDS)
    finally:
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            _kill_process_group(process.pid)
            process.wait(timeout=2.0)
        # A malicious leader may exit while descendants retain output FDs.  Kill the original
        # group once more before joining the drain thread.
        _kill_process_group(process.pid)
        reader.join(timeout=2.0)

    if reader.is_alive():
        raise AnimationRenderError("The animation worker did not release its output stream.")
    if reason == "cancelled":
        raise AnimationRenderError("Manim render was cancelled")
    if reason == "output":
        raise AnimationRenderError("Manim exceeded the diagnostic-output budget")
    if reason == "memory":
        raise AnimationRenderError("Manim exceeded the process-tree memory budget")
    if reason == "processes":
        raise AnimationRenderError("Manim exceeded the process-count budget")
    if reason == "timeout":
        raise AnimationRenderError("Manim render exceeded the offline time budget")
    if reason == "job":
        raise AnimationRenderError("Manim exceeded the isolated job budget")
    if output_exceeded.is_set():
        raise AnimationRenderError("Manim exceeded the diagnostic-output budget")
    if process.returncode != 0:
        if process.returncode == -signal.SIGXCPU:
            raise AnimationRenderError("Manim exceeded the CPU budget")
        raise AnimationRenderError(
            f"Manim could not render this lesson. {_safe_tail(bytes(captured))}"
        )
    return _ProcessResult(process.returncode, bytes(captured), peak_rss)


def _sandbox_command(record: _CapabilityRecord, job: Path, *, quality: str) -> list[str]:
    _output_parts_for_quality(quality)
    profile = job / "renderer.sb"
    source = job / _RUNNER_NAME
    return [
        str(_SANDBOX_EXEC),
        "-D",
        f"WORKER={record.executable}",
        "-D",
        f"WORKER_ROOT={record.root}",
        "-D",
        f"JOB={job}",
        "-f",
        str(profile),
        str(record.executable),
        "--silent",
        quality,
        "--format",
        "mp4",
        "--disable_caching",
        "--output_file",
        "result.mp4",
        "--media_dir",
        str(job / "media"),
        str(source),
        _SCENE_NAME,
    ]


def _output_parts_for_quality(quality: str) -> tuple[str, ...]:
    try:
        return _OUTPUT_PARTS_BY_QUALITY[quality]
    except KeyError as exc:
        raise AnimationRenderError("the requested Manim quality is not approved") from exc


def _sandbox_environment(record: _CapabilityRecord, job: Path) -> dict[str, str]:
    return {
        "HOME": str(job),
        "TMPDIR": str(job),
        "XDG_CACHE_HOME": str(job / "cache"),
        "PATH": os.pathsep.join((str(record.root), "/usr/bin", "/bin")),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_PROXY": "*",
        "no_proxy": "*",
    }


def _safe_read_mp4(root: Path, parts: tuple[str, ...] = _OUTPUT_PARTS) -> bytes:
    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = [os.open(root, directory_flags)]
    try:
        for part in parts[:-1]:
            descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptors.append(os.open(parts[-1], file_flags, dir_fd=descriptors[-1]))
        descriptor = descriptors[-1]
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise AnimationRenderError("Manim output is not a regular file")
        if info.st_size <= 0 or info.st_size > MAX_VIDEO_BYTES:
            raise AnimationRenderError("Manim video is empty or exceeds the output budget")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise AnimationRenderError("Manim output ended before its verified size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise AnimationRenderError("Manim output changed while read")
        payload = b"".join(chunks)
        if len(payload) < 12 or b"ftyp" not in payload[:32]:
            raise AnimationRenderError("Manim output is not an MP4 file")
        return payload
    except OSError as exc:
        raise AnimationRenderError("Manim did not produce the fixed lesson video") from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _execute_source(
    source: str,
    *,
    record: _CapabilityRecord,
    job: Path,
    quality: str,
    cancel_event: threading.Event | None,
) -> bytes:
    encoded = source.encode("utf-8")
    if not encoded or len(encoded) > _MAX_SOURCE_BYTES or "\x00" in source:
        raise AnimationRenderError("validated Manim source exceeds the render budget")
    _write_new_file(job / _SOURCE_NAME, encoded)
    _write_new_file(job / _RUNNER_NAME, RUNNER_SOURCE.encode("utf-8"))
    _write_new_file(job / "renderer.sb", _profile_text().encode("utf-8"))
    _run_bounded_process(
        _sandbox_command(record, job, quality=quality),
        cwd=job,
        environment=_sandbox_environment(record, job),
        cancel_event=cancel_event,
    )
    return _safe_read_mp4(job, _output_parts_for_quality(quality))


def _new_private_job(prefix: str) -> Path:
    if not _PRIVATE_TEMP.is_dir() or not os.access(_PRIVATE_TEMP, os.W_OK | os.X_OK):
        raise AnimationRenderError("the private render workspace is unavailable")
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=_PRIVATE_TEMP)).resolve()
    path.chmod(0o700)
    return path


def _remove_job(path: Path) -> None:
    # All children are dead before this is called.  rmtree is fd-based and symlink-safe on the
    # supported macOS Python; the continuously enforced byte/entry limits bound cleanup work.
    if not shutil.rmtree.avoids_symlink_attacks:
        raise AnimationRenderError("safe renderer cleanup is unavailable")
    shutil.rmtree(path)


def _probe_source(canary: Path, outside_write: Path) -> str:
    canary_literal = repr(str(canary))
    outside_literal = repr(str(outside_write))
    typst_literal = repr(f'#read("{canary.as_posix()}")')
    return f'''from manim import *
import socket
import subprocess

class MutaLesson(Scene):
    def construct(self):
        escaped = []
        try:
            open({canary_literal}, "rb").read()
            escaped.append("read")
        except Exception:
            pass
        try:
            open({outside_literal}, "wb").write(b"changed")
            escaped.append("write")
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b"probe", ("127.0.0.1", 9))
            escaped.append("network")
        except Exception:
            pass
        try:
            subprocess.run(["/bin/sh", "-c", "printf escaped > exec-marker"], check=False)
            escaped.append("exec")
        except Exception:
            pass
        try:
            open("read-link", "rb").read()
            escaped.append("symlink")
        except Exception:
            pass
        try:
            MathTypst({typst_literal})
            escaped.append("typst")
        except Exception:
            pass
        if escaped:
            open("escape-succeeded.json", "w").write(str(escaped))
        circle = Circle(radius=1.0)
        self.play(Create(circle), run_time=0.05)
        self.wait(0.05)
'''


def _acquire_capability_lock(
    lock: threading.Lock,
    *,
    cancel_event: threading.Event | None,
    busy_detail: str,
) -> None:
    deadline = time.monotonic() + _CAPABILITY_WAIT_SECONDS
    while True:
        _raise_if_cancelled(cancel_event)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AnimationRenderBusyError(busy_detail)
        if lock.acquire(timeout=min(0.05, remaining)):
            try:
                _raise_if_cancelled(cancel_event)
            except _CapabilityCancelled:
                lock.release()
                raise
            return


def _probe_record(
    record: _CapabilityRecord, cancel_event: threading.Event | None = None
) -> None:
    _acquire_capability_lock(
        _render_lock,
        cancel_event=cancel_event,
        busy_detail="Another offline animation render is already in progress",
    )
    probe: Path | None = None
    try:
        probe = _new_private_job("muta-manim-policy-probe-")
        job = probe / "job"
        job.mkdir(mode=0o700)
        canary = probe / "protected-canary"
        outside_write = probe / "outside-write"
        _write_new_file(canary, b"MUTA_POLICY_CANARY")
        (job / "read-link").symlink_to(canary)
        _execute_source(
            _probe_source(canary, outside_write),
            record=record,
            job=job,
            quality="-ql",
            cancel_event=cancel_event,
        )
        if (
            canary.read_bytes() != b"MUTA_POLICY_CANARY"
            or outside_write.exists()
            or (job / "exec-marker").exists()
            or (job / "escape-succeeded.json").exists()
        ):
            raise AnimationRenderError("the model-code sandbox policy probe escaped isolation")
    finally:
        _render_lock.release()
        if probe is not None:
            _remove_job(probe)


def _unsupported_reason() -> str | None:
    if sys.platform != "darwin" or os.name != "posix":
        return "Model-authored Manim is unavailable because this build has no verified OS sandbox."
    if (
        not _SANDBOX_EXEC.is_file()
        or _SANDBOX_EXEC.is_symlink()
        or not os.access(_SANDBOX_EXEC, os.X_OK)
    ):
        return "Model-authored Manim is unavailable because the macOS sandbox is missing."
    if not shutil.rmtree.avoids_symlink_attacks:
        return "Model-authored Manim is unavailable because safe job cleanup is unsupported."
    return None


def _get_capability_record(
    executable: str, *, cancel_event: threading.Event | None = None
) -> _CapabilityRecord:
    _raise_if_cancelled(cancel_event)
    reason = _unsupported_reason()
    if reason:
        raise AnimationRenderError(reason)
    if not isinstance(executable, str) or not executable.strip():
        raise AnimationRenderError("the animation worker executable is unavailable")
    try:
        key = _quick_identity(Path(executable), cancel_event)
    except _CapabilityCancelled:
        raise
    except AnimationRenderError:
        raise
    except OSError as exc:
        raise AnimationRenderError(
            "the animation worker manifest or executable is unavailable"
        ) from exc
    with _cache_lock:
        if key in _capability_cache:
            _raise_if_cancelled(cancel_event)
            return _capability_cache[key]
        failure = _cached_failure(key)
    _raise_if_cancelled(cancel_event)
    if failure:
        raise AnimationRenderError(failure)

    _acquire_capability_lock(
        _probe_lock,
        cancel_event=cancel_event,
        busy_detail="Another model-code sandbox verification is already in progress",
    )
    try:
        with _cache_lock:
            if key in _capability_cache:
                _raise_if_cancelled(cancel_event)
                return _capability_cache[key]
            failure = _cached_failure(key)
        if failure:
            raise AnimationRenderError(failure)
        record: _CapabilityRecord | None = None
        try:
            identity = _load_and_verify_runtime(Path(executable), cancel_event)
            if identity.key != key:
                raise AnimationRenderError("the animation worker changed during verification")
            record = _stage_runtime(identity, cancel_event)
            _probe_record(record, cancel_event)
        except _CapabilityCancelled:
            if record is not None:
                _remove_stage(record.stage_container)
                _stage_containers.discard(record.stage_container)
            raise
        except AnimationRenderBusyError:
            if record is not None:
                _remove_stage(record.stage_container)
                _stage_containers.discard(record.stage_container)
            raise
        except Exception as exc:
            if record is not None:
                _remove_stage(record.stage_container)
                _stage_containers.discard(record.stage_container)
            if cancel_event is not None and cancel_event.is_set():
                raise _CapabilityCancelled(
                    "Model-code sandbox verification was cancelled"
                ) from exc
            detail = (
                str(exc)
                if isinstance(exc, AnimationRenderError)
                else "The model-code sandbox could not be verified."
            )
            with _cache_lock:
                _capability_failures[key] = (
                    time.monotonic() + _FAILURE_CACHE_SECONDS,
                    detail,
                )
            raise AnimationRenderError(detail) from exc
        with _cache_lock:
            _capability_cache[key] = record
        return record
    finally:
        _probe_lock.release()


def program_capability(
    executable: str, *, cancel_event: threading.Event | None = None
) -> dict[str, object]:
    """Return whether this exact manifest-verified worker passed the disposable policy probe."""
    try:
        record = _get_capability_record(executable, cancel_event=cancel_event)
    except AnimationRenderBusyError as exc:
        return {"available": False, "detail": str(exc)}
    except AnimationRenderError as exc:
        return {"available": False, "detail": str(exc)}
    return {"available": True, "detail": record.detail}


def render_program_source(
    source: str,
    *,
    executable: str,
    cancel_event: threading.Event | None = None,
) -> bytes:
    """Render already-validated source in the verified worker and return one bounded MP4."""
    record = _get_capability_record(executable, cancel_event=cancel_event)
    _raise_if_cancelled(cancel_event)
    if not _render_lock.acquire(blocking=False):
        raise AnimationRenderBusyError("Another offline animation render is already in progress")
    job: Path | None = None
    try:
        job = _new_private_job("muta-manim-program-")
        return _execute_source(
            source,
            record=record,
            job=job,
            quality="-qm",
            cancel_event=cancel_event,
        )
    finally:
        _render_lock.release()
        if job is not None:
            _remove_job(job)


def _reset_capability_cache_for_tests() -> None:
    """Test-only reset; production callers must never discard a verified stage mid-render."""
    with _cache_lock:
        records = list(_capability_cache.values())
        _capability_cache.clear()
        _capability_failures.clear()
    for record in records:
        _remove_stage(record.stage_container)
        _stage_containers.discard(record.stage_container)
