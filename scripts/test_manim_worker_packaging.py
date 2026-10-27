from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_manim_worker as builder
from scripts import verify_manim_worker as verifier


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _worker(tmp_path: Path) -> Path:
    root = tmp_path / "worker"
    root.mkdir()
    executable = root / "muta-manim"
    executable.write_bytes(b"binary")
    executable.chmod(0o755)
    target = root / "_internal/libcodec.dylib"
    target.parent.mkdir()
    target.write_bytes(b"library")
    freetype = root / "_internal/libfreetype.6.dylib"
    freetype.write_bytes(b"freetype")
    harfbuzz = root / "_internal/libharfbuzz.0.dylib"
    harfbuzz.write_bytes(b"harfbuzz")
    alias = root / "_internal/libcodec.1.dylib"
    alias.symlink_to("libcodec.dylib")
    license_index = root / "licenses/index.json"
    license_index.parent.mkdir()
    license_text = root / "licenses/test.txt"
    license_text.write_text("test licence")
    license_index.write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": name,
                        "version": version,
                        "license_files": ["test.txt"],
                    }
                    for name, version in verifier.read_pins(
                        verifier.REPO_ROOT / "desktop/manim/requirements.lock"
                    ).items()
                ]
            }
        )
    )
    files = [
        {
            "path": "muta-manim",
            "type": "file",
            "size_bytes": executable.stat().st_size,
            "sha256": _sha(executable),
        },
        {
            "path": "_internal/libcodec.dylib",
            "type": "file",
            "size_bytes": target.stat().st_size,
            "sha256": _sha(target),
        },
        {
            "path": "_internal/libcodec.1.dylib",
            "type": "symlink",
            "target": "libcodec.dylib",
        },
        {
            "path": "_internal/libfreetype.6.dylib",
            "type": "file",
            "size_bytes": freetype.stat().st_size,
            "sha256": _sha(freetype),
        },
        {
            "path": "_internal/libharfbuzz.0.dylib",
            "type": "file",
            "size_bytes": harfbuzz.stat().st_size,
            "sha256": _sha(harfbuzz),
        },
        {
            "path": "licenses/index.json",
            "type": "file",
            "size_bytes": license_index.stat().st_size,
            "sha256": _sha(license_index),
        },
        {
            "path": "licenses/test.txt",
            "type": "file",
            "size_bytes": license_text.stat().st_size,
            "sha256": _sha(license_text),
        },
    ]
    (root / verifier.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": 1,
                "target": {"os": "macos", "arch": "aarch64"},
                "runtime": {
                    "python": "3.11.15",
                    "manim": "0.22.0",
                    "typst": "0.15.0",
                    "pyinstaller": "6.22.2",
                    "minimum_macos": "14.0",
                },
                "source": {
                    "entrypoint_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "desktop/manim/entrypoint.py"
                    ),
                    "requirements_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "desktop/manim/requirements.lock"
                    ),
                    "native_license_policy_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "desktop/manim/native-licenses.json"
                    ),
                    "builder_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "scripts/build_manim_worker.py"
                    ),
                    "metadata_collector_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "scripts/manim_worker_metadata.py"
                    ),
                    "verifier_sha256": verifier.sha256_file(
                        verifier.REPO_ROOT / "scripts/verify_manim_worker.py"
                    ),
                },
                "native_libraries": [
                    {
                        "path": path.relative_to(root).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha(path),
                        "license_coverage": {
                            "rule": "test-distribution",
                            "component": "test codec",
                            "notice": "Copyright test codec contributors",
                            "source": "licenses/index.json",
                            "owner": "test codec",
                            "owner_version": "",
                            "license_files": [
                                {
                                    "id": "test codec",
                                    "path": "licenses/test.txt",
                                    "sha256": _sha(license_text),
                                }
                            ],
                            "distribution_index": False,
                        },
                    }
                    for path in (target, freetype, harfbuzz)
                ],
                "native_repairs": [
                    {"path": "_internal/libfreetype.6.dylib"},
                    {"path": "_internal/libharfbuzz.0.dylib"},
                ],
                "files": files,
            }
        )
    )
    return root


def _pillow_collision_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "worker"
    private = root / "_internal/PIL/.dylibs"
    private.mkdir(parents=True)
    prefix = tmp_path / "builder"
    (prefix / "lib").mkdir(parents=True)
    for name in ("libharfbuzz.0.dylib", "libfreetype.6.dylib"):
        (private / name).write_bytes(f"pillow-{name}".encode())
        (root / "_internal" / name).symlink_to(f"PIL/.dylibs/{name}")
    return root, prefix


def test_arm_worker_repairs_pillow_pango_library_collisions(tmp_path: Path) -> None:
    root, prefix = _pillow_collision_tree(tmp_path)
    for name in ("libharfbuzz.0.dylib", "libfreetype.6.dylib"):
        (prefix / "lib" / name).write_bytes(f"conda-{name}".encode())

    repairs = builder._repair_pillow_pango_collisions(root, prefix, "aarch64")

    assert {item["path"] for item in repairs} == {
        "_internal/libharfbuzz.0.dylib",
        "_internal/libfreetype.6.dylib",
    }
    for name in ("libharfbuzz.0.dylib", "libfreetype.6.dylib"):
        repaired = root / "_internal" / name
        assert not repaired.is_symlink()
        assert repaired.read_bytes() == f"conda-{name}".encode()


def test_intel_worker_preserves_safe_private_pillow_aliases(tmp_path: Path) -> None:
    root, prefix = _pillow_collision_tree(tmp_path)

    repairs = builder._repair_pillow_pango_collisions(root, prefix, "x86_64")

    assert repairs == []
    for name in ("libharfbuzz.0.dylib", "libfreetype.6.dylib"):
        alias = root / "_internal" / name
        assert alias.is_symlink()
        assert alias.resolve().is_file()


def test_worker_manifest_accepts_safe_relative_aliases(tmp_path: Path) -> None:
    root = _worker(tmp_path)
    verifier.verify_manifest(root, "aarch64")


def test_worker_manifest_rejects_tampered_runtime(tmp_path: Path) -> None:
    root = _worker(tmp_path)
    (root / "muta-manim").write_bytes(b"tampered")
    with pytest.raises(verifier.VerificationError, match="byte-size|SHA-256"):
        verifier.verify_manifest(root, "aarch64")


def test_worker_manifest_rejects_stale_packaging_source(tmp_path: Path) -> None:
    root = _worker(tmp_path)
    manifest_path = root / verifier.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["source"]["requirements_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(verifier.VerificationError, match="stale packaging source"):
        verifier.verify_manifest(root, "aarch64")


def test_worker_manifest_rejects_unowned_distribution_license_mapping(tmp_path: Path) -> None:
    root = _worker(tmp_path)
    manifest_path = root / verifier.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    coverage = manifest["native_libraries"][0]["license_coverage"]
    coverage.update(
        {
            "owner": "missing-package",
            "owner_version": "1",
            "distribution_index": True,
        }
    )
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(verifier.VerificationError, match="owner has no populated"):
        verifier.verify_manifest(root, "aarch64")


def test_worker_manifest_rejects_unpinned_frozen_build_tool(tmp_path: Path) -> None:
    root = _worker(tmp_path)
    payload = root / "_internal/pip/untrusted.py"
    payload.parent.mkdir(parents=True)
    payload.write_text("untrusted")
    manifest_path = root / verifier.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].append(
        {
            "path": payload.relative_to(root).as_posix(),
            "type": "file",
            "size_bytes": payload.stat().st_size,
            "sha256": _sha(payload),
        }
    )
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(verifier.VerificationError, match="unpinned build-tool payload"):
        verifier.verify_manifest(root, "aarch64")


def test_native_policy_prefers_libavif_over_ffmpeg_glob() -> None:
    policy = json.loads(
        (verifier.REPO_ROOT / "desktop/manim/native-licenses.json").read_text()
    )
    relative = "_internal/PIL/.dylibs/libavif.16.4.2.dylib"
    import fnmatch

    matched = next(
        rule for rule in policy["coverage_rules"] if fnmatch.fnmatch(relative, rule["pattern"])
    )
    assert matched["id"] == "pillow-avif"


def test_native_closure_rejects_build_machine_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    root.mkdir()
    binary = root / "muta-manim"
    binary.write_bytes(b"binary")

    def fake_command(*command: str) -> str:
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64\n"
        if command[:2] == ("otool", "-L"):
            return f"{binary}:\n\t/opt/homebrew/lib/libcairo.2.dylib (compatibility version 2.0.0)\n"
        if command[:2] == ("otool", "-l"):
            return "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 11.0\n"
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    with pytest.raises(verifier.VerificationError, match="build-machine dependency"):
        verifier.verify_native_closure(root, "aarch64")


def test_native_closure_rejects_universal_binary_for_thin_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    root.mkdir()
    (root / "muta-manim").write_bytes(b"binary")

    def fake_command(*command: str) -> str:
        if command[0] == "file":
            return "Mach-O universal binary with 2 architectures: [x86_64] [arm64]\n"
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    with pytest.raises(verifier.VerificationError, match="wrong Manim worker architecture"):
        verifier.verify_native_closure(root, "aarch64")


def test_native_closure_rejects_newer_macos_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    root.mkdir()
    (root / "muta-manim").write_bytes(b"binary")

    def fake_command(*command: str) -> str:
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64\n"
        if command[:2] == ("otool", "-L"):
            return "muta-manim:\n"
        if command[:2] == ("otool", "-l"):
            return "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 15.0\n"
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    with pytest.raises(verifier.VerificationError, match="requires macOS 15.0"):
        verifier.verify_native_closure(root, "aarch64")


def test_native_closure_rejects_unresolved_rpath_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    root.mkdir()
    binary = root / "muta-manim"
    binary.write_bytes(b"binary")

    def fake_command(*command: str) -> str:
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64\n"
        if command[:2] == ("otool", "-L"):
            return f"{binary}:\n\t@rpath/libmissing.dylib (compatibility version 1.0.0)\n"
        if command[:2] == ("otool", "-l"):
            return (
                "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 11.0\n"
                "Load command 2\n          cmd LC_RPATH\n      cmdsize 32\n"
                "         path @loader_path (offset 12)\n"
            )
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    with pytest.raises(verifier.VerificationError, match="does not resolve inside"):
        verifier.verify_native_closure(root, "aarch64")


def test_native_closure_does_not_borrow_unrelated_binary_rpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    library_dir = root / "borrowed"
    library_dir.mkdir(parents=True)
    executable = root / "muta-manim"
    broken = root / "broken.so"
    unrelated = root / "unrelated.so"
    dependency = library_dir / "libfoo.dylib"
    for item in (executable, broken, unrelated, dependency):
        item.write_bytes(item.name.encode("utf-8"))

    def fake_command(*command: str) -> str:
        target = Path(command[-1])
        if command[0] == "file":
            return "Mach-O 64-bit dynamically linked shared library arm64\n"
        if command[:2] == ("otool", "-L"):
            if target == broken:
                return (
                    f"{broken}:\n"
                    "\t@rpath/libfoo.dylib (compatibility version 1.0.0)\n"
                )
            return f"{target}:\n"
        if command[:2] == ("otool", "-l"):
            rpath = ""
            if target == unrelated:
                rpath = (
                    "Load command 2\n          cmd LC_RPATH\n      cmdsize 32\n"
                    "         path @loader_path/borrowed (offset 12)\n"
                )
            return (
                "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 11.0\n"
                + rpath
            )
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    with pytest.raises(verifier.VerificationError, match="does not resolve inside"):
        verifier.verify_native_closure(root, "aarch64")


def test_native_closure_ignores_self_id_and_resolves_real_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worker"
    root.mkdir()
    executable = root / "muta-manim"
    library = root / "libself.dylib"
    dependency = root / "libdependency.dylib"
    executable.write_bytes(b"executable")
    library.write_bytes(b"library")
    dependency.write_bytes(b"dependency")

    def fake_command(*command: str) -> str:
        target = Path(command[-1])
        if command[0] == "file":
            return "Mach-O 64-bit dynamically linked shared library arm64\n"
        if command[:2] == ("otool", "-L"):
            if target == executable:
                return f"{executable}:\n"
            if target == library:
                return (
                    f"{library}:\n"
                    "\t@rpath/libself.dylib (compatibility version 1.0.0)\n"
                    "\t@rpath/libdependency.dylib (compatibility version 1.0.0)\n"
                )
            return (
                f"{dependency}:\n"
                "\t@rpath/libdependency.dylib (compatibility version 1.0.0)\n"
                "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n"
            )
        if command[:2] == ("otool", "-l"):
            if target == executable:
                return "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 11.0\n"
            name = "libself.dylib" if target == library else "libdependency.dylib"
            return (
                "Load command 1\n      cmd LC_BUILD_VERSION\n    minos 11.0\n"
                "Load command 2\n          cmd LC_ID_DYLIB\n"
                f"         name @rpath/{name} (offset 24)\n"
                "Load command 3\n          cmd LC_RPATH\n      cmdsize 32\n"
                "         path @loader_path (offset 12)\n"
            )
        return ""

    monkeypatch.setattr(verifier, "_command", fake_command)
    assert verifier.verify_native_closure(root, "aarch64") == 3


def test_frozen_entrypoint_enables_multiprocessing_before_manim_import() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "desktop/manim/entrypoint.py"
    ).read_text(encoding="utf-8")
    assert source.index("multiprocessing.freeze_support()") < source.index(
        "from manim.__main__ import main"
    )


def test_frozen_gateway_includes_animation_worker_dispatch_module() -> None:
    source = (
        verifier.REPO_ROOT / "desktop/pyinstaller/muta_gateway.spec"
    ).read_text(encoding="utf-8")
    assert 'hiddenimports += ["orchestrator.gateway.animation_worker"]' in source
