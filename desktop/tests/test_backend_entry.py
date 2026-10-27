import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

from desktop import backend_entry


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    resource = tmp_path / "resources"
    model_root = tmp_path / "model-pack"
    model = model_root / "models" / "core" / "core.gguf"
    projector = model_root / "models" / "core" / "mmproj.gguf"
    engine = (
        resource
        / "bin"
        / ("llama-server.exe" if __import__("sys").platform == "win32" else "llama-server")
    )
    for path in (model, projector, engine):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    (resource / "desktop-product.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "active_model": {
                    "path": "models/core/core.gguf",
                    "size_bytes": model.stat().st_size,
                    "sha256": _sha256(model),
                    "mmproj_path": "models/core/mmproj.gguf",
                    "mmproj_size_bytes": projector.stat().st_size,
                    "mmproj_sha256": _sha256(projector),
                },
            }
        )
    )
    return resource, model_root, model, engine


def test_configure_forces_offline_absolute_desktop_paths(tmp_path):
    resource, model_root, model, engine = _bundle(tmp_path)
    state = tmp_path / "state"
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--data-root",
            str(state),
            "--model-root",
            str(model_root),
            "--llama-server",
            str(engine),
            "--port",
            "19000",
            "--engine-port",
            "19080",
        ]
    )

    environment: dict[str, str] = {}
    values = backend_entry.configure(args, environment)

    assert values["MUTA_OFFLINE"] == "1"
    assert values["MUTA_ALLOW_MODEL_SWITCH"] == "1"
    assert values["MUTA_RT_AUTO_DOWNLOAD"] == "0"
    # Two 4,096-token chat lanes: room for the tutor prompt, document evidence and an answer.
    assert values["MUTA_RT_N_CTX"] == "8192"
    assert values["MUTA_RT_MODEL_DIR"] == str(model.parent)
    assert values["MUTA_MODEL_ROOT"] == str(model_root)
    assert values["MUTA_MODEL_SELECTION_PATH"] == str(state / "model-selection.json")
    assert values["MUTA_RT_DB_URL"].endswith("/state/muta.sqlite3")
    assert values["MUTA_LLAMA_SERVER_URL"] == "http://127.0.0.1:19080"
    assert environment == values
    assert (state / "logs").is_dir()
    assert not (resource / "data").exists()


def test_manifest_resource_escape_is_rejected(tmp_path):
    resource, model_root, _model, engine = _bundle(tmp_path)
    (resource / "desktop-product.json").write_text(
        json.dumps({"schema": 1, "active_model": {"path": "../outside.gguf"}})
    )
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--data-root",
            str(tmp_path / "state"),
            "--model-root",
            str(model_root),
            "--llama-server",
            str(engine),
        ]
    )

    with pytest.raises(ValueError, match="escapes"):
        backend_entry.configure(args)


def test_missing_product_manifest_fails_instead_of_guessing_a_model(tmp_path):
    resource = tmp_path / "resources"
    engine = resource / "bin" / "llama-server"
    engine.parent.mkdir(parents=True)
    engine.write_bytes(b"test")
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )

    with pytest.raises(FileNotFoundError, match="product manifest"):
        backend_entry.configure(args)


def test_model_hash_mismatch_fails_closed(tmp_path):
    resource, model_root, model, engine = _bundle(tmp_path)
    model.write_bytes(b"tampered")
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--model-root",
            str(model_root),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )

    with pytest.raises(ValueError, match="wrong byte size|SHA-256"):
        backend_entry.configure(args)


def test_inherited_engine_and_heartbeat_settings_are_not_used(tmp_path):
    resource, model_root, _model, engine = _bundle(tmp_path)
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--model-root",
            str(model_root),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )
    environment = {
        "MUTA_RT_EXTRA_SERVER_ARGS": '["--dangerous"]',
        "MUTA_RT_MMPROJ_PATH": "/tmp/stale",
        "MUTA_FLEET_URL": "https://unexpected.example",
        "MUTA_FLEET_INGEST_KEY": "unexpected",
        "MUTA_CLOUD_URL": "https://unexpected.example",
        "MUTA_CLOUD_MODEL": "unexpected",
        "MUTA_CLOUD_API_KEY": "unexpected",
        "MUTA_SEARCH_URL": "https://unexpected.example",
        "MUTA_MANIM_BIN": "/tmp/untrusted-manim",
        "MUTA_MANIM_RUNTIME_DIR": "/tmp/untrusted-runtime",
        "MUTA_MANIM_FFMPEG_BIN": "/tmp/untrusted-ffmpeg",
        "MUTA_MANIM_UNAVAILABLE_REASON": "untrusted reason",
        "MUTA_ANIMATION_WORKER_BIN": "/tmp/untrusted-animation-worker",
        "MUTA_RT_HF_REPO": "unexpected/repo",
    }

    values = backend_entry.configure(args, environment)

    assert "MUTA_RT_EXTRA_SERVER_ARGS" not in environment
    assert "MUTA_FLEET_URL" not in environment
    assert "MUTA_CLOUD_URL" not in environment
    assert "MUTA_SEARCH_URL" not in environment
    assert "MUTA_MANIM_BIN" not in environment
    assert "MUTA_MANIM_RUNTIME_DIR" not in environment
    assert "MUTA_MANIM_FFMPEG_BIN" not in environment
    assert "MUTA_MANIM_UNAVAILABLE_REASON" not in environment
    assert "MUTA_ANIMATION_WORKER_BIN" not in environment
    assert "MUTA_RT_HF_REPO" not in environment
    assert values["MUTA_RT_MMPROJ_PATH"].endswith("mmproj.gguf")


def test_packaged_manim_worker_is_verified_and_exported(tmp_path):
    resource, model_root, _model, engine = _bundle(tmp_path)
    worker = resource / "bin" / "muta-manim" / "muta-manim"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_bytes(b"trusted-worker")
    worker.chmod(0o755)
    worker_manifest = worker.parent / "MUTA-MANIM-MANIFEST.json"
    worker_manifest.write_text(
        json.dumps({"schema": 1, "runtime": {"minimum_macos": "14.0"}}),
        encoding="utf-8",
    )
    ffmpeg = resource / "bin" / "ffmpeg"
    ffmpeg.write_bytes(b"ffmpeg")
    manifest_path = resource / "desktop-product.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manim_worker"] = {
        "path": "bin/muta-manim/muta-manim",
        "size_bytes": worker.stat().st_size,
        "sha256": _sha256(worker),
        "manifest": "bin/muta-manim/MUTA-MANIM-MANIFEST.json",
        "runtime": {"minimum_macos": "14.0"},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--model-root",
            str(model_root),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )

    values = backend_entry.configure(args, {})

    assert values["MUTA_MANIM_BIN"] == str(worker)
    assert values["MUTA_MANIM_RUNTIME_DIR"] == str(worker.parent)
    assert values["MUTA_MANIM_FFMPEG_BIN"] == str(ffmpeg)


def test_packaged_manim_worker_is_disabled_without_disabling_app_on_older_macos(
    tmp_path, monkeypatch
):
    resource, model_root, _model, engine = _bundle(tmp_path)
    worker = resource / "bin" / "muta-manim" / "muta-manim"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_bytes(b"trusted-worker")
    worker.chmod(0o755)
    (worker.parent / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps({"schema": 1, "runtime": {"minimum_macos": "14.0"}}),
        encoding="utf-8",
    )
    manifest_path = resource / "desktop-product.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manim_worker"] = {
        "path": "bin/muta-manim/muta-manim",
        "size_bytes": worker.stat().st_size,
        "sha256": _sha256(worker),
        "manifest": "bin/muta-manim/MUTA-MANIM-MANIFEST.json",
        "runtime": {"minimum_macos": "14.0"},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    args = backend_entry._parser().parse_args(
        [
            "--print-config",
            "--resource-root",
            str(resource),
            "--model-root",
            str(model_root),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )
    monkeypatch.setattr(backend_entry, "_macos_supports_worker", lambda _minimum: False)

    values = backend_entry.configure(args, {})

    assert "MUTA_MANIM_BIN" not in values
    assert "MUTA_MANIM_RUNTIME_DIR" not in values
    assert values["MUTA_MANIM_UNAVAILABLE_REASON"].startswith(
        "Offline Manim rendering requires macOS 14.0"
    )


def test_manim_worker_macos_capability_check_is_fail_closed():
    assert backend_entry._macos_supports_worker(
        "14.0", platform_name="darwin", system_version="14.0"
    )
    assert backend_entry._macos_supports_worker(
        "14.0", platform_name="darwin", system_version="14"
    )
    assert not backend_entry._macos_supports_worker(
        "14.0", platform_name="darwin", system_version="13.6.9"
    )
    assert not backend_entry._macos_supports_worker(
        "14.0", platform_name="darwin", system_version=""
    )
    assert backend_entry._macos_supports_worker(
        "14.0", platform_name="linux", system_version=""
    )


def test_packaged_manim_worker_hash_mismatch_fails_closed(tmp_path):
    resource, model_root, _model, engine = _bundle(tmp_path)
    worker = resource / "bin" / "muta-manim" / "muta-manim"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_bytes(b"tampered")
    (worker.parent / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps({"schema": 1, "runtime": {"minimum_macos": "14.0"}}),
        encoding="utf-8",
    )
    manifest_path = resource / "desktop-product.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manim_worker"] = {
        "path": "bin/muta-manim/muta-manim",
        "size_bytes": worker.stat().st_size,
        "sha256": "0" * 64,
        "manifest": "bin/muta-manim/MUTA-MANIM-MANIFEST.json",
        "runtime": {"minimum_macos": "14.0"},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    args = backend_entry._parser().parse_args(
        [
            "--resource-root",
            str(resource),
            "--model-root",
            str(model_root),
            "--data-root",
            str(tmp_path / "state"),
            "--llama-server",
            str(engine),
        ]
    )

    with pytest.raises(ValueError, match="SHA-256"):
        backend_entry.configure(args, {})


def test_windows_uses_native_job_instead_of_posix_parent_watchdog():
    assert backend_entry._use_parent_watchdog(1234, "nt") is False
    assert backend_entry._use_parent_watchdog(1234, "posix") is True
    assert backend_entry._use_parent_watchdog(0, "posix") is False


def test_frozen_entrypoint_dispatches_animation_worker_before_argparse(monkeypatch):
    received: list[list[str]] = []
    module = types.ModuleType("orchestrator.gateway.animation_worker")
    module.main = lambda argv: received.append(argv) or 23
    monkeypatch.setitem(sys.modules, "orchestrator.gateway.animation_worker", module)

    result = backend_entry.main(
        ["--animation-worker", "/bundle/muta-manim", "-ql", "lesson.py", "MutaLesson"]
    )

    assert result == 23
    assert received == [
        ["--animation-worker", "/bundle/muta-manim", "-ql", "lesson.py", "MutaLesson"]
    ]


def test_packaged_heartbeat_overrides_inherited_fleet_and_printing_redacts_key(
    tmp_path, monkeypatch, capsys
):
    # main() deliberately exports into the real process environment for the subsequently
    # imported gateway. Give it a per-test copy so those launcher variables cannot leak into
    # later lifespan/configuration tests in the same pytest process.
    monkeypatch.setattr(backend_entry.os, "environ", dict(backend_entry.os.environ))
    resource, model_root, _model, engine = _bundle(tmp_path)
    manifest_path = resource / "desktop-product.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["heartbeat"] = {
        "url": "https://fleet.example",
        "ingest_key": "write-only-secret",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv = [
        "--print-config",
        "--resource-root",
        str(resource),
        "--model-root",
        str(model_root),
        "--data-root",
        str(tmp_path / "state"),
        "--llama-server",
        str(engine),
    ]

    assert backend_entry.main(argv) == 0
    printed = capsys.readouterr().out
    assert "https://fleet.example" in printed
    assert "write-only-secret" not in printed
    assert "<redacted>" in printed
