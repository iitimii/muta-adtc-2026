from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from orchestrator.gateway import animation_sandbox as sandbox
from orchestrator.gateway.animation_render import AnimationRenderBusyError, AnimationRenderError


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _runtime(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir(parents=True)
    executable = root / "muta-manim"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    payload = root / "payload.dat"
    payload.write_bytes(b"immutable runtime")
    alias = root / "payload-link"
    alias.symlink_to("payload.dat")
    manifest = {
        "schema": 1,
        "files": [
            {
                "path": "muta-manim",
                "type": "file",
                "size_bytes": executable.stat().st_size,
                "sha256": _sha(executable.read_bytes()),
            },
            {
                "path": "payload.dat",
                "type": "file",
                "size_bytes": payload.stat().st_size,
                "sha256": _sha(payload.read_bytes()),
            },
            {"path": "payload-link", "type": "symlink", "target": "payload.dat"},
        ],
    }
    (root / sandbox._MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return executable


@pytest.fixture(autouse=True)
def _clear_capability_state() -> None:
    with sandbox._cache_lock:
        sandbox._capability_cache.clear()
        sandbox._capability_failures.clear()
    yield
    with sandbox._cache_lock:
        records = list(sandbox._capability_cache.values())
        sandbox._capability_cache.clear()
        sandbox._capability_failures.clear()
    for record in records:
        if record.stage_container.exists():
            sandbox._remove_stage(record.stage_container)
        sandbox._stage_containers.discard(record.stage_container)


def _record(tmp_path: Path, key: tuple[object, ...] = ("worker",)) -> sandbox._CapabilityRecord:
    container = tmp_path / "stage"
    root = container / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    executable = root / "muta-manim"
    executable.write_bytes(b"worker")
    executable.chmod(0o755)
    return sandbox._CapabilityRecord(
        key,
        container,
        root,
        executable,
        "Verified model-code sandbox is ready.",
    )


def test_runtime_identity_requires_exact_manifest_and_safe_symlinks(tmp_path: Path) -> None:
    executable = _runtime(tmp_path)

    identity = sandbox._load_and_verify_runtime(executable)

    assert identity.executable == executable.resolve()
    assert identity.executable_sha256 == _sha(executable.read_bytes())
    assert identity.key[-2:] == (identity.executable_sha256, identity.manifest_sha256)


def test_runtime_identity_rejects_tampered_or_unlisted_files(tmp_path: Path) -> None:
    executable = _runtime(tmp_path)
    (executable.parent / "payload.dat").write_bytes(b"tampered")
    with pytest.raises(AnimationRenderError, match="does not match"):
        sandbox._load_and_verify_runtime(executable)

    executable = _runtime(tmp_path / "second")
    (executable.parent / "unlisted.py").write_text("untrusted")
    with pytest.raises(AnimationRenderError, match="file sets differ"):
        sandbox._load_and_verify_runtime(executable)


def test_staged_runtime_is_outside_home_read_only_and_reverified(
    monkeypatch, tmp_path: Path
) -> None:
    executable = _runtime(tmp_path / "source")
    identity = sandbox._load_and_verify_runtime(executable)
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(sandbox, "_PRIVATE_TEMP", private)
    monkeypatch.setattr(
        sandbox,
        "_clone_runtime_tree",
        lambda source, destination, _container, _cancel_event: shutil.copytree(
            source, destination, symlinks=True
        ),
    )

    record = sandbox._stage_runtime(identity)
    try:
        assert record.executable.read_bytes() == executable.read_bytes()
        assert not record.root.is_relative_to(Path.home())
        assert record.executable.stat().st_mode & 0o222 == 0
        assert record.root.stat().st_mode & 0o222 == 0
    finally:
        sandbox._remove_stage(record.stage_container)
        sandbox._stage_containers.discard(record.stage_container)


def test_runtime_staging_uses_fixed_apfs_clone_command(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "payload").write_bytes(b"worker")
    container = tmp_path / "container"
    container.mkdir()
    destination = container / "runtime"
    observed: dict[str, object] = {}

    def fake_run(command, *, cwd, environment, cancel_event):
        observed.update(
            command=command,
            cwd=cwd,
            environment=environment,
            cancel_event=cancel_event,
        )
        shutil.copytree(source, destination)
        return sandbox._ProcessResult(0, b"", 1)

    monkeypatch.setattr(sandbox, "_run_bounded_process", fake_run)
    sandbox._clone_runtime_tree(source, destination, container, None)
    assert observed["command"] == [
        "/bin/cp",
        "-cR",
        str(source),
        str(destination),
    ]
    assert observed["cwd"] == container
    assert observed["environment"]["PATH"] == "/usr/bin:/bin"
    assert (destination / "payload").read_bytes() == b"worker"


def test_profile_has_exact_worker_exec_and_no_network_or_home_access() -> None:
    profile = sandbox._profile_text()
    assert '(allow process-exec (literal (param "WORKER")))' in profile
    assert "allow network" not in profile
    assert "process-fork" not in profile
    assert str(Path.home()) not in profile
    assert '(subpath (param "WORKER_ROOT"))' in profile
    assert '(subpath (param "JOB"))' in profile
    assert '(subpath "/private/tmp")' in profile
    assert '(literal "/")' in profile
    assert '(allow file-map-executable (subpath (param "WORKER_ROOT")))' in profile


def test_disposable_probe_source_is_valid_and_exercises_all_boundaries(tmp_path: Path) -> None:
    source = sandbox._probe_source(tmp_path / "canary", tmp_path / "outside")
    ast.parse(source)
    for needle in (
        "open(",
        "socket.socket",
        "subprocess.run",
        'open("read-link"',
        "MathTypst",
        "escape-succeeded.json",
        "class MutaLesson(Scene)",
    ):
        assert needle in source


def test_capability_is_cached_by_verified_identity_not_path_presence(
    monkeypatch, tmp_path: Path
) -> None:
    executable = tmp_path / "worker"
    executable.write_bytes(b"worker")
    current = {"key": ("identity-one",)}
    calls = {"verify": 0, "probe": 0}

    monkeypatch.setattr(sandbox, "_unsupported_reason", lambda: None)
    monkeypatch.setattr(
        sandbox, "_quick_identity", lambda _path, _cancel_event=None: current["key"]
    )

    def verify(
        _path: Path, _cancel_event: threading.Event | None = None
    ) -> sandbox._WorkerIdentity:
        calls["verify"] += 1
        return sandbox._WorkerIdentity(current["key"], tmp_path, executable, "m", "e")

    def stage(
        identity: sandbox._WorkerIdentity, _cancel_event: threading.Event | None = None
    ) -> sandbox._CapabilityRecord:
        container = tmp_path / f"stage-{identity.key[0]}"
        root = container / "runtime"
        root.mkdir(parents=True)
        worker = root / "worker"
        worker.write_bytes(b"worker")
        return sandbox._CapabilityRecord(identity.key, container, root, worker, "ready")

    def probe(
        _record: sandbox._CapabilityRecord, _cancel_event: threading.Event | None = None
    ) -> None:
        calls["probe"] += 1

    monkeypatch.setattr(sandbox, "_load_and_verify_runtime", verify)
    monkeypatch.setattr(sandbox, "_stage_runtime", stage)
    monkeypatch.setattr(sandbox, "_probe_record", probe)

    assert sandbox.program_capability(str(executable)) == {"available": True, "detail": "ready"}
    assert sandbox.program_capability(str(executable))["available"] is True
    assert calls == {"verify": 1, "probe": 1}

    current["key"] = ("identity-two",)
    assert sandbox.program_capability(str(executable))["available"] is True
    assert calls == {"verify": 2, "probe": 2}


def test_failed_policy_probe_is_cached_fail_closed(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "worker"
    executable.write_bytes(b"worker")
    key = ("failed-identity",)
    record = _record(tmp_path, key)
    calls = 0

    monkeypatch.setattr(sandbox, "_unsupported_reason", lambda: None)
    monkeypatch.setattr(sandbox, "_quick_identity", lambda _path, _cancel_event=None: key)
    monkeypatch.setattr(
        sandbox,
        "_load_and_verify_runtime",
        lambda _path, _cancel_event=None: sandbox._WorkerIdentity(
            key, tmp_path, executable, "m", "e"
        ),
    )
    monkeypatch.setattr(
        sandbox, "_stage_runtime", lambda _identity, _cancel_event=None: record
    )

    def fail(
        _record: sandbox._CapabilityRecord, _cancel_event: threading.Event | None = None
    ) -> None:
        nonlocal calls
        calls += 1
        raise AnimationRenderError("policy denied")

    monkeypatch.setattr(sandbox, "_probe_record", fail)
    first = sandbox.program_capability(str(executable))
    second = sandbox.program_capability(str(executable))
    assert first == second == {"available": False, "detail": "policy denied"}
    assert calls == 1

    sandbox._capability_failures[key] = (0.0, "policy denied")
    assert sandbox.program_capability(str(executable))["available"] is False
    assert calls == 2


def test_program_capability_is_unavailable_on_unsupported_hosts(monkeypatch) -> None:
    monkeypatch.setattr(sandbox.sys, "platform", "linux")
    assert sandbox.program_capability("/must/not/be/read") == {
        "available": False,
        "detail": "Model-authored Manim is unavailable because this build has no verified OS sandbox.",
    }


def test_program_capability_missing_manifest_fails_closed_without_raw_os_error(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(sandbox, "_unsupported_reason", lambda: None)
    executable = tmp_path / "worker"
    executable.write_bytes(b"worker")
    executable.chmod(0o755)
    result = sandbox.program_capability(str(executable))
    assert result == {
        "available": False,
        "detail": "the animation worker manifest or executable is unavailable",
    }


def test_cancelled_capability_never_starts_a_render(monkeypatch) -> None:
    cancelled = threading.Event()
    cancelled.set()
    monkeypatch.setattr(
        sandbox,
        "_execute_source",
        lambda *args, **kwargs: pytest.fail("cancelled caller must not execute source"),
    )
    assert sandbox.program_capability("cached-worker", cancel_event=cancelled) == {
        "available": False,
        "detail": "Model-code sandbox verification was cancelled",
    }
    with pytest.raises(AnimationRenderError, match="verification was cancelled"):
        sandbox.render_program_source(
            "source",
            executable="cached-worker",
            cancel_event=cancelled,
        )


def test_cancelled_probe_is_not_cached_as_permanent_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    executable = tmp_path / "worker"
    executable.write_bytes(b"worker")
    key = ("cancelled-identity",)
    record = _record(tmp_path, key)
    cancelled = threading.Event()
    calls = 0
    monkeypatch.setattr(sandbox, "_unsupported_reason", lambda: None)
    monkeypatch.setattr(sandbox, "_quick_identity", lambda _path, _event=None: key)
    monkeypatch.setattr(
        sandbox,
        "_load_and_verify_runtime",
        lambda _path, _event=None: sandbox._WorkerIdentity(
            key, tmp_path, executable, "m", "e"
        ),
    )
    monkeypatch.setattr(sandbox, "_stage_runtime", lambda _identity, _event=None: record)

    def cancel_probe(
        _record: sandbox._CapabilityRecord, event: threading.Event | None = None
    ) -> None:
        nonlocal calls
        calls += 1
        assert event is cancelled
        cancelled.set()
        raise AnimationRenderError("Manim render was cancelled")

    monkeypatch.setattr(sandbox, "_probe_record", cancel_probe)
    result = sandbox.program_capability(str(executable), cancel_event=cancelled)
    assert result["available"] is False
    assert key not in sandbox._capability_failures
    assert key not in sandbox._capability_cache

    cancelled.clear()
    monkeypatch.setattr(sandbox, "_probe_record", lambda _record, _event=None: None)
    assert sandbox.program_capability(str(executable), cancel_event=cancelled)["available"] is True
    assert calls == 1


def test_capability_lock_releases_if_cancel_arrives_immediately_after_acquire() -> None:
    lock = threading.Lock()

    class CancelAfterAcquire:
        calls = 0

        def is_set(self) -> bool:
            self.calls += 1
            return self.calls >= 2

    with pytest.raises(AnimationRenderError, match="verification was cancelled"):
        sandbox._acquire_capability_lock(
            lock,
            cancel_event=CancelAfterAcquire(),  # type: ignore[arg-type]
            busy_detail="busy",
        )
    assert lock.acquire(blocking=False)
    lock.release()


def test_sandbox_command_fixes_worker_source_scene_output_and_quality(tmp_path: Path) -> None:
    record = _record(tmp_path)
    command = sandbox._sandbox_command(record, tmp_path / "job", quality="-qm")
    assert command[0] == str(sandbox._SANDBOX_EXEC)
    assert command[command.index("-D") + 1] == f"WORKER={record.executable}"
    assert command[-1] == "MutaLesson"
    assert command[-2].endswith("runner.py")
    assert command[command.index("--output_file") + 1] == "result.mp4"
    assert "-qm" in command


def test_output_path_is_fixed_per_approved_quality() -> None:
    assert sandbox._output_parts_for_quality("-ql") == (
        "media",
        "videos",
        "runner",
        "480p15",
        "result.mp4",
    )
    assert sandbox._output_parts_for_quality("-qm") == (
        "media",
        "videos",
        "runner",
        "720p30",
        "result.mp4",
    )
    with pytest.raises(AnimationRenderError, match="quality is not approved"):
        sandbox._output_parts_for_quality("-qh")


@pytest.mark.parametrize(("quality", "directory"), [("-ql", "480p15"), ("-qm", "720p30")])
def test_execute_source_reads_only_the_quality_specific_fixed_output(
    monkeypatch, tmp_path: Path, quality: str, directory: str
) -> None:
    record = _record(tmp_path)
    job = tmp_path / "job"
    job.mkdir()
    expected = job / "media" / "videos" / "runner" / directory / "result.mp4"
    video = b"\x00\x00\x00\x18ftypmp42fixed-video"

    def fake_run(command, *, cwd, environment, cancel_event):
        assert quality in command
        assert cwd == job
        assert environment["HOME"] == str(job)
        assert cancel_event is None
        assert (job / "lesson.py").read_bytes() == b"source"
        assert (job / "runner.py").read_text() == sandbox.RUNNER_SOURCE
        assert command[-2] == str(job / "runner.py")
        expected.parent.mkdir(parents=True)
        expected.write_bytes(video)
        return sandbox._ProcessResult(0, b"", 1)

    monkeypatch.setattr(sandbox, "_run_bounded_process", fake_run)
    assert (
        sandbox._execute_source(
            "source",
            record=record,
            job=job,
            quality=quality,
            cancel_event=None,
        )
        == video
    )


def test_safe_mp4_reader_uses_fixed_path_and_rejects_final_symlink(tmp_path: Path) -> None:
    output = tmp_path.joinpath(*sandbox._OUTPUT_PARTS)
    output.parent.mkdir(parents=True)
    video = b"\x00\x00\x00\x18ftypmp42safe-video"
    output.write_bytes(video)
    assert sandbox._safe_read_mp4(tmp_path) == video

    output.unlink()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(video)
    output.symlink_to(outside)
    with pytest.raises(AnimationRenderError, match="fixed lesson video"):
        sandbox._safe_read_mp4(tmp_path)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO test")
def test_safe_mp4_reader_nonblocking_open_rejects_fifo(tmp_path: Path) -> None:
    output = tmp_path.joinpath(*sandbox._OUTPUT_PARTS)
    output.parent.mkdir(parents=True)
    os.mkfifo(output)
    started = time.monotonic()
    with pytest.raises(AnimationRenderError, match="not a regular file"):
        sandbox._safe_read_mp4(tmp_path)
    assert time.monotonic() - started < 0.5


def test_job_usage_does_not_follow_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "large").write_bytes(b"x" * 4096)
    job = tmp_path / "job"
    job.mkdir()
    (job / "small").write_bytes(b"123")
    (job / "link").symlink_to(outside, target_is_directory=True)
    size, entries, has_symlink = sandbox._job_usage(job)
    assert size == 3
    assert entries == 2
    assert has_symlink is True


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_continuously_caps_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sandbox, "_MAX_CAPTURE_BYTES", 4096)
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    with pytest.raises(AnimationRenderError, match="diagnostic-output budget"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000); sys.stdout.flush()"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=None,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_honours_cancellation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    cancelled = threading.Event()
    cancelled.set()
    started = time.monotonic()
    with pytest.raises(AnimationRenderError, match="was cancelled"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=cancelled,
        )
    assert time.monotonic() - started < 2


def test_bounded_process_rejects_low_space_before_launch(monkeypatch, tmp_path: Path) -> None:
    usage_type = type(sandbox.shutil.disk_usage(tmp_path))
    monkeypatch.setattr(
        sandbox.shutil,
        "disk_usage",
        lambda _path: usage_type(10_000, 9_999, 1),
    )
    with pytest.raises(AnimationRenderError, match="not enough free space"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", "raise SystemExit(0)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=None,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_does_not_charge_unrelated_free_space_drop_to_job(
    monkeypatch, tmp_path: Path
) -> None:
    usage_type = type(sandbox.shutil.disk_usage(tmp_path))
    calls = 0

    def global_usage_drop(_path):
        nonlocal calls
        calls += 1
        free = 10_000 if calls == 1 else 8_000
        return usage_type(100_000, 100_000 - free, free)

    monkeypatch.setattr(sandbox.shutil, "disk_usage", global_usage_drop)
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 100)
    monkeypatch.setattr(sandbox, "_MAX_JOB_BYTES", 1024)
    monkeypatch.setattr(sandbox, "_DIRECTORY_SCAN_INTERVAL_SECONDS", 0)
    result = sandbox._run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(0.1)"],
        cwd=tmp_path,
        environment=dict(os.environ),
        cancel_event=None,
    )
    assert result.returncode == 0
    assert sandbox._job_usage(tmp_path)[0] <= sandbox._MAX_JOB_BYTES
    assert calls > 1


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_caps_aggregate_job_bytes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    monkeypatch.setattr(sandbox, "_MAX_JOB_BYTES", 1024)
    monkeypatch.setattr(sandbox, "_DIRECTORY_SCAN_INTERVAL_SECONDS", 0)
    script = (
        "from pathlib import Path; import time; "
        "Path('large.bin').write_bytes(b'x' * 8192); time.sleep(30)"
    )
    with pytest.raises(AnimationRenderError, match="isolated job budget"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=None,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_caps_aggregate_process_tree_rss(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    monkeypatch.setattr(sandbox, "_MAX_RSS_BYTES", 1)
    with pytest.raises(AnimationRenderError, match="process-tree memory budget"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=None,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_bounded_process_caps_wall_time(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    monkeypatch.setattr(sandbox, "_WALL_SECONDS", 0.08)
    with pytest.raises(AnimationRenderError, match="time budget"):
        sandbox._run_bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            cancel_event=None,
        )


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group test")
def test_resource_wrapper_applies_limits_without_preexec_model_bytes() -> None:
    command = ["/usr/bin/sandbox-exec", "-f", "/fixed/profile", "/fixed/worker"]
    wrapped = sandbox._resource_wrapped_command(command)
    assert wrapped[:2] == ["/bin/sh", "-c"]
    assert "set -eu" in wrapped[2]
    assert "ulimit -t" in wrapped[2]
    assert "ulimit -f" in wrapped[2]
    assert wrapped[-len(command) :] == command


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX process-group test")
def test_bounded_process_kills_descendants_after_leader_exits(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sandbox, "_MIN_FREE_BYTES", 1)
    pid_file = tmp_path / "child.pid"
    script = (
        "import os, pathlib, time\n"
        "pid = os.fork()\n"
        "if pid:\n"
        f"    pathlib.Path({str(pid_file)!r}).write_text(str(pid))\n"
        "    raise SystemExit(0)\n"
        "while True: time.sleep(1)\n"
    )
    result = sandbox._run_bounded_process(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        environment=dict(os.environ),
        cancel_event=None,
    )
    assert result.returncode == 0
    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and psutil.pid_exists(child_pid):
        time.sleep(0.02)
    assert not psutil.pid_exists(child_pid)


def test_render_reuses_single_admission_and_cleans_private_job(
    monkeypatch, tmp_path: Path
) -> None:
    record = _record(tmp_path)
    job = tmp_path / "job"
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        sandbox,
        "_get_capability_record",
        lambda _executable, cancel_event=None: record,
    )

    def new_job(_prefix: str) -> Path:
        job.mkdir()
        return job

    def execute(source, *, record, job, quality, cancel_event):
        observed.update(
            source=source,
            record=record,
            job=job,
            quality=quality,
            cancel_event=cancel_event,
        )
        return b"\x00\x00\x00\x18ftypmp42video"

    monkeypatch.setattr(sandbox, "_new_private_job", new_job)
    monkeypatch.setattr(sandbox, "_execute_source", execute)

    source = "from manim import *\nclass MutaLesson(Scene):\n    def construct(self): pass\n"
    video = sandbox.render_program_source(source, executable="worker")
    assert video.endswith(b"video")
    assert observed["source"] == source
    assert observed["quality"] == "-qm"
    assert not job.exists()

    sandbox._render_lock.acquire()
    try:
        with pytest.raises(AnimationRenderBusyError, match="already in progress"):
            sandbox.render_program_source(source, executable="worker")
    finally:
        sandbox._render_lock.release()


def test_render_releases_admission_when_private_job_creation_fails(
    monkeypatch, tmp_path: Path
) -> None:
    record = _record(tmp_path)
    monkeypatch.setattr(
        sandbox,
        "_get_capability_record",
        lambda _executable, cancel_event=None: record,
    )
    monkeypatch.setattr(
        sandbox,
        "_new_private_job",
        lambda _prefix: (_ for _ in ()).throw(AnimationRenderError("workspace unavailable")),
    )
    source = "from manim import *\nclass MutaLesson(Scene):\n    def construct(self): pass\n"
    with pytest.raises(AnimationRenderError, match="workspace unavailable"):
        sandbox.render_program_source(source, executable="worker")
    assert sandbox._render_lock.acquire(blocking=False)
    sandbox._render_lock.release()


def test_execute_source_rejects_oversized_input_before_launch(tmp_path: Path) -> None:
    record = _record(tmp_path)
    job = tmp_path / "job"
    job.mkdir()
    with pytest.raises(AnimationRenderError, match="source exceeds"):
        sandbox._execute_source(
            "x" * (sandbox._MAX_SOURCE_BYTES + 1),
            record=record,
            job=job,
            quality="-qm",
            cancel_event=None,
        )
    assert list(job.iterdir()) == []


def test_source_byte_budget_accepts_maximum_unicode_program_character_budget() -> None:
    # animation_program permits 24,000 characters.  Four-byte Unicode must still fit this
    # renderer's transport ceiling rather than being rejected after validation.
    assert len(("😀" * 24_000).encode("utf-8")) <= sandbox._MAX_SOURCE_BYTES
