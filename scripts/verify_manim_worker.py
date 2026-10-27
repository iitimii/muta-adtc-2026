#!/usr/bin/env python3
"""Fail-closed validation for Muta's frozen, relocatable macOS Manim worker."""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

MANIFEST_NAME = "MUTA-MANIM-MANIFEST.json"
EXPECTED_RUNTIME = {"manim": "0.22.0", "typst": "0.15.0", "pyinstaller": "6.22.2"}
EXPECTED_MINIMUM_MACOS = "14.0"
EXPECTED_NATIVE_REPAIRS = {
    "aarch64": {"_internal/libfreetype.6.dylib", "_internal/libharfbuzz.0.dylib"},
    "x86_64": set(),
}
FORBIDDEN_DEPENDENCY_PREFIXES = ("/opt/homebrew/", "/usr/local/", "/private/tmp/", "/Users/")
REPO_ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    pass


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise VerificationError(f"worker dependency is not exactly pinned: {line}")
        name, version = line.split("==", 1)
        key = _canonical_name(name.strip())
        if not key or not version.strip() or key in pins:
            raise VerificationError(f"invalid worker dependency pin: {line}")
        pins[key] = version.strip()
    if not pins:
        raise VerificationError("worker dependency lock is empty")
    return pins


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise VerificationError(f"unsafe worker manifest path: {value!r}")
    return relative


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _safe_link(root: Path, path: Path, target: str) -> None:
    if Path(target).is_absolute():
        raise VerificationError(f"absolute symlink in worker: {path} -> {target}")
    resolved = (path.parent / target).resolve()
    if resolved != root and root not in resolved.parents:
        raise VerificationError(f"symlink escapes worker: {path} -> {target}")
    if not resolved.is_file():
        raise VerificationError(f"worker symlink does not resolve to a file: {path} -> {target}")


def verify_manifest(root: Path, expected_arch: str) -> dict:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise VerificationError(f"worker manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise VerificationError("unsupported Manim worker manifest schema")
    if manifest.get("target") != {"os": "macos", "arch": expected_arch}:
        raise VerificationError("Manim worker target differs from the requested package target")
    runtime = manifest.get("runtime") or {}
    for key, value in EXPECTED_RUNTIME.items():
        if runtime.get(key) != value:
            raise VerificationError(f"Manim worker {key} is not pinned to {value}")
    if not str(runtime.get("python", "")).startswith("3.11."):
        raise VerificationError("Manim worker is not frozen with pinned Python 3.11")
    if runtime.get("minimum_macos") != EXPECTED_MINIMUM_MACOS:
        raise VerificationError(
            f"Manim worker does not declare macOS {EXPECTED_MINIMUM_MACOS} compatibility"
        )
    source = manifest.get("source") or {}
    expected_source = {
        "entrypoint_sha256": sha256_file(REPO_ROOT / "desktop/manim/entrypoint.py"),
        "requirements_sha256": sha256_file(REPO_ROOT / "desktop/manim/requirements.lock"),
        "native_license_policy_sha256": sha256_file(
            REPO_ROOT / "desktop/manim/native-licenses.json"
        ),
        "builder_sha256": sha256_file(REPO_ROOT / "scripts/build_manim_worker.py"),
        "metadata_collector_sha256": sha256_file(
            REPO_ROOT / "scripts/manim_worker_metadata.py"
        ),
        "verifier_sha256": sha256_file(REPO_ROOT / "scripts/verify_manim_worker.py"),
    }
    if source != expected_source:
        raise VerificationError("Manim worker was built from stale packaging source inputs")
    repairs = {str(item.get("path")) for item in manifest.get("native_repairs", [])}
    if repairs != EXPECTED_NATIVE_REPAIRS[expected_arch]:
        raise VerificationError("Manim worker does not record the required Pillow/Pango ABI repairs")
    for relative in repairs:
        repaired = root / _safe_relative(relative)
        if not repaired.is_file() or repaired.is_symlink():
            raise VerificationError(f"Manim worker ABI repair is missing: {relative}")

    expected: dict[str, dict] = {}
    for entry in manifest.get("files", []):
        relative = _safe_relative(str(entry.get("path", ""))).as_posix()
        if relative in expected or relative == MANIFEST_NAME:
            raise VerificationError(f"duplicate or recursive worker manifest member: {relative}")
        expected[relative] = entry
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if (item.is_file() or item.is_symlink()) and item != manifest_path
    }
    if actual != set(expected):
        raise VerificationError(
            "worker tree differs from manifest; "
            f"missing={sorted(set(expected) - actual)}, extra={sorted(actual - set(expected))}"
        )
    for relative, entry in expected.items():
        path = root / relative
        kind = entry.get("type", "file")
        if kind == "symlink":
            if not path.is_symlink():
                raise VerificationError(f"worker manifest expected a symlink: {relative}")
            target = os.readlink(path)
            if target != entry.get("target"):
                raise VerificationError(f"worker symlink target mismatch: {relative}")
            _safe_link(root, path, target)
            continue
        if kind != "file" or path.is_symlink() or not path.is_file():
            raise VerificationError(f"worker manifest expected a regular file: {relative}")
        if path.stat().st_size != int(entry.get("size_bytes", -1)):
            raise VerificationError(f"worker byte-size mismatch: {relative}")
        if sha256_file(path) != entry.get("sha256"):
            raise VerificationError(f"worker SHA-256 mismatch: {relative}")
    native_entries = {
        relative: entry
        for relative, entry in expected.items()
        if entry.get("type", "file") == "file"
        and Path(relative).suffix in {".dylib", ".so"}
    }
    native_manifest = {
        str(entry.get("path")): entry for entry in manifest.get("native_libraries", [])
    }
    if set(native_manifest) != set(native_entries):
        raise VerificationError(
            "native licence inventory differs from the worker; "
            f"missing={sorted(set(native_entries) - set(native_manifest))}, "
            f"extra={sorted(set(native_manifest) - set(native_entries))}"
        )
    license_index_path = root / "licenses/index.json"
    try:
        license_index = json.loads(license_index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError("worker licence index is missing or invalid") from error
    python_licenses = {
        _canonical_name(str(package.get("name", ""))): package
        for package in license_index.get("packages", [])
        if package.get("name")
    }
    conda_licenses = {
        _canonical_name(str(package.get("name", ""))): package
        for package in license_index.get("conda_packages", [])
        if package.get("name")
    }
    pins = read_pins(REPO_ROOT / "desktop/manim/requirements.lock")
    indexed_packages: dict[str, dict] = {}
    for package in license_index.get("packages", []):
        name = _canonical_name(str(package.get("name", "")))
        if not name or name in indexed_packages:
            raise VerificationError(f"worker licence index has a duplicate package: {name!r}")
        indexed_packages[name] = package
    indexed_versions = {
        name: str(package.get("version") or "") for name, package in indexed_packages.items()
    }
    if indexed_versions != pins:
        raise VerificationError(
            "worker licence index differs from the exact dependency lock; "
            f"missing={sorted(set(pins) - set(indexed_versions))}, "
            f"extra={sorted(set(indexed_versions) - set(pins))}, "
            f"changed={sorted(name for name in pins.keys() & indexed_versions.keys() if pins[name] != indexed_versions[name])}"
        )
    for name, package in indexed_packages.items():
        if not package.get("license_files"):
            raise VerificationError(f"pinned Python package has no shipped licence text: {name}")
    internal = root / "_internal"
    for build_tool in ("pip", "setuptools", "wheel"):
        if (internal / build_tool).exists() and build_tool not in pins:
            raise VerificationError(
                f"frozen worker contains an unpinned build-tool payload: {build_tool}"
            )
    for metadata_dir in sorted(internal.glob("*.dist-info")):
        metadata_path = metadata_dir / "METADATA"
        if not metadata_path.is_file():
            raise VerificationError(f"frozen distribution metadata is incomplete: {metadata_dir.name}")
        metadata = email.parser.Parser().parsestr(metadata_path.read_text(encoding="utf-8"))
        name = _canonical_name(str(metadata.get("Name") or ""))
        version = str(metadata.get("Version") or "")
        if pins.get(name) != version:
            raise VerificationError(
                f"frozen distribution is absent from the exact dependency lock: "
                f"{name}=={version}"
            )
    for relative, native in native_manifest.items():
        file_entry = native_entries[relative]
        if (
            native.get("size_bytes") != file_entry.get("size_bytes")
            or native.get("sha256") != file_entry.get("sha256")
        ):
            raise VerificationError(f"native licence inventory hash mismatch: {relative}")
        coverage = native.get("license_coverage") or {}
        license_files = coverage.get("license_files") or []
        if not coverage.get("rule") or not coverage.get("component") or not coverage.get("owner"):
            raise VerificationError(f"native library has no licence mapping: {relative}")
        if not coverage.get("distribution_index") and not coverage.get("notice"):
            raise VerificationError(f"native component notice is missing: {relative}")
        if not license_files:
            raise VerificationError(f"native library has no actual licence text: {relative}")
        indexed_paths: set[str] | None = None
        if coverage.get("distribution_index"):
            owner = str(coverage["owner"])
            if owner == "python-runtime":
                indexed_paths = {"python-runtime/LICENSE.txt"}
            else:
                record = python_licenses.get(_canonical_name(owner)) or conda_licenses.get(
                    _canonical_name(owner)
                )
                if record is None or not record.get("license_files"):
                    raise VerificationError(
                        f"native library owner has no populated licence record: {relative}: {owner}"
                    )
                if str(record.get("version") or "") != str(
                    coverage.get("owner_version") or ""
                ):
                    raise VerificationError(
                        f"native library owner version is inconsistent: {relative}: {owner}"
                    )
                indexed_paths = {str(path) for path in record["license_files"]}
        for document in license_files:
            document_relative = _safe_relative(str(document.get("path", ""))).as_posix()
            document_path = root / document_relative
            if not document_path.is_file() or document_path.is_symlink():
                raise VerificationError(
                    f"native library licence text is missing: {relative}: {document_relative}"
                )
            if sha256_file(document_path) != document.get("sha256"):
                raise VerificationError(
                    f"native library licence text hash mismatch: {relative}: {document_relative}"
                )
            if indexed_paths is not None:
                try:
                    indexed_relative = document_path.relative_to(root / "licenses").as_posix()
                except ValueError as error:
                    raise VerificationError(
                        f"indexed native licence path escapes its root: {document_relative}"
                    ) from error
                if indexed_relative not in indexed_paths:
                    raise VerificationError(
                        f"native licence text is not owned by its distribution: "
                        f"{relative}: {indexed_relative}"
                    )
    executable = root / "muta-manim"
    if not executable.is_file() or executable.is_symlink():
        raise VerificationError("frozen Manim executable is missing")
    if not os.access(executable, os.X_OK):
        raise VerificationError("frozen Manim executable is not executable")
    if not license_index.get("packages"):
        raise VerificationError("Manim worker licence index has no pinned Python packages")
    return manifest


def _command(*command: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise VerificationError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def _rpaths(load_commands: list[str]) -> list[str]:
    values = []
    for index, line in enumerate(load_commands):
        if line.strip() != "cmd LC_RPATH":
            continue
        for candidate in load_commands[index + 1 : index + 5]:
            fields = candidate.split()
            if len(fields) >= 2 and fields[0] == "path":
                values.append(fields[1])
                break
    return values


def _dylib_id(load_commands: list[str]) -> str | None:
    for index, line in enumerate(load_commands):
        if line.strip() != "cmd LC_ID_DYLIB":
            continue
        for candidate in load_commands[index + 1 : index + 6]:
            fields = candidate.split()
            if len(fields) >= 2 and fields[0] == "name":
                return fields[1]
    return None


def _expand_macho_path(value: str, item: Path, root: Path) -> Path | None:
    for marker, base in (
        ("@loader_path", item.parent),
        ("@executable_path", root),
    ):
        if value == marker:
            return base
        if value.startswith(marker + "/"):
            return base / value[len(marker) + 1 :]
    if value.startswith("/"):
        return Path(value)
    return None


def _is_bundled_file(root: Path, candidate: Path) -> bool:
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return False
    return (resolved == root or root in resolved.parents) and resolved.is_file()


def _verify_dependency(
    root: Path,
    item: Path,
    dependency: str,
    reachable_rpath_dirs: list[Path],
) -> Path | None:
    if dependency.startswith(("/System/Library/", "/usr/lib/")):
        return None
    if dependency.startswith("@rpath/"):
        suffix = dependency.removeprefix("@rpath/")
        for base in reachable_rpath_dirs:
            candidate = base / suffix
            if _is_bundled_file(root, candidate):
                return candidate.resolve(strict=True)
        raise VerificationError(
            f"Manim worker dependency does not resolve inside its bundle: "
            f"{item}: {dependency}; rpaths={reachable_rpath_dirs}"
        )
    candidate = _expand_macho_path(dependency, item, root)
    if candidate is not None and _is_bundled_file(root, candidate):
        return candidate.resolve(strict=True)
    raise VerificationError(
        f"Manim worker dependency is neither a system library nor bundled: "
        f"{item}: {dependency}"
    )


def verify_native_closure(root: Path, expected_arch: str) -> int:
    marker = {"aarch64": "arm64", "x86_64": "x86_64"}[expected_arch]
    other_marker = {"aarch64": "x86_64", "x86_64": "arm64"}[expected_arch]
    macho_items: dict[Path, dict[str, object]] = {}
    for item in sorted(root.rglob("*")):
        if item.is_symlink() or not item.is_file():
            continue
        description = _command("file", "-b", str(item)).strip()
        if "Mach-O" not in description:
            continue
        if marker not in description or other_marker in description:
            raise VerificationError(f"wrong Manim worker architecture: {item}: {description}")
        load_commands = _command("otool", "-l", str(item)).splitlines()
        runtime_rpaths = _rpaths(load_commands)
        expanded_rpaths: list[Path] = []
        for value in runtime_rpaths:
            if value.startswith(FORBIDDEN_DEPENDENCY_PREFIXES):
                raise VerificationError(f"build-machine LC_RPATH leaked into worker: {value}")
            expanded = _expand_macho_path(value, item, root)
            if expanded is None:
                raise VerificationError(f"unsupported LC_RPATH in Manim worker: {item}: {value}")
            resolved = expanded.resolve()
            if resolved != root and root not in resolved.parents:
                raise VerificationError(f"LC_RPATH escapes Manim worker: {item}: {value}")
            if resolved not in expanded_rpaths:
                expanded_rpaths.append(resolved)
        dylib_id = _dylib_id(load_commands)
        dependencies = _command("otool", "-L", str(item)).splitlines()[1:]
        parsed_dependencies: list[str] = []
        for line in dependencies:
            dependency = line.strip().split(" ", 1)[0]
            if dependency == dylib_id:
                continue
            if dependency.startswith(FORBIDDEN_DEPENDENCY_PREFIXES):
                raise VerificationError(f"build-machine dependency leaked into worker: {dependency}")
            parsed_dependencies.append(dependency)
        minimum = None
        for index, line in enumerate(load_commands):
            command = line.strip()
            if command not in {"cmd LC_BUILD_VERSION", "cmd LC_VERSION_MIN_MACOSX"}:
                continue
            field = "minos" if command == "cmd LC_BUILD_VERSION" else "version"
            for candidate in load_commands[index + 1 : index + 7]:
                fields = candidate.split()
                if len(fields) >= 2 and fields[0] == field:
                    minimum = fields[1]
                    break
            if minimum:
                break
        if minimum is None:
            raise VerificationError(f"Manim worker Mach-O has no macOS minimum: {item}")
        current = tuple(int(part) for part in minimum.split(".")[:2])
        allowed = tuple(int(part) for part in EXPECTED_MINIMUM_MACOS.split("."))
        if current > allowed:
            raise VerificationError(
                f"Manim worker requires macOS {minimum}, above {EXPECTED_MINIMUM_MACOS}: {item}"
            )
        macho_items[item.resolve()] = {
            "item": item,
            "rpaths": expanded_rpaths,
            "dependencies": parsed_dependencies,
        }
    if not macho_items:
        raise VerificationError("Manim worker contains no Mach-O runtime")

    executable = (root / "muta-manim").resolve()
    if executable not in macho_items:
        raise VerificationError("frozen Manim executable is not a Mach-O runtime")
    executable_rpaths = list(macho_items[executable]["rpaths"])

    def walk(
        item_key: Path,
        inherited_rpaths: list[Path],
        active: frozenset[Path],
    ) -> None:
        if item_key in active:
            return
        info = macho_items[item_key]
        item = info["item"]
        reachable_rpaths = list(inherited_rpaths)
        for candidate in info["rpaths"]:
            if candidate not in reachable_rpaths:
                reachable_rpaths.append(candidate)
        next_active = active | {item_key}
        for dependency in info["dependencies"]:
            resolved = _verify_dependency(root, item, dependency, reachable_rpaths)
            if resolved is None:
                continue
            dependency_key = resolved.resolve()
            if dependency_key not in macho_items:
                raise VerificationError(
                    f"Manim worker dependency is not a verified Mach-O runtime: "
                    f"{item}: {dependency} -> {resolved}"
                )
            walk(dependency_key, reachable_rpaths, next_active)

    # Python can dlopen any bundled extension directly. Validate every Mach-O as a possible
    # load root, seeded only with the main executable's run paths; an unrelated extension's
    # LC_RPATH must never make another extension appear resolvable.
    for item_key in macho_items:
        inherited = [] if item_key == executable else executable_rpaths
        walk(item_key, inherited, frozenset())
    return len(macho_items)


SMOKE_SOURCE = '''from manim import *

class MutaLesson(Scene):
    def construct(self):
        title = Text("A rational function").scale(0.7)
        formula = MathTypst(r"f(x) = (x^2 + 1) / (x + 1)").scale(0.8)
        formula.next_to(title, DOWN)
        self.play(Write(title), Write(formula))
        self.wait(0.1)
'''


def smoke_render(root: Path, timeout: float) -> Path:
    executable = root.resolve() / "muta-manim"
    with tempfile.TemporaryDirectory(prefix="muta-manim-smoke-") as temporary:
        workspace = Path(temporary)
        source = workspace / "lesson.py"
        source.write_text(SMOKE_SOURCE, encoding="utf-8")
        media = workspace / "media"
        environment = dict(os.environ)
        for key in ("DYLD_LIBRARY_PATH", "PYTHONPATH", "MANIM_CONFIG_FILE"):
            environment.pop(key, None)
        environment["XDG_CACHE_HOME"] = str(workspace / "cache")
        result = subprocess.run(
            [
                str(executable),
                "-ql",
                "--format",
                "mp4",
                "--disable_caching",
                "--media_dir",
                str(media),
                str(source),
                "MutaLesson",
            ],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise VerificationError(f"Manim smoke render failed: {result.stderr[-4000:]}")
        videos = [
            path
            for path in media.rglob("*.mp4")
            if "partial_movie_files" not in path.parts and path.stat().st_size > 0
        ]
        if len(videos) != 1:
            raise VerificationError(f"Manim smoke did not create exactly one MP4: {videos}")
        if list(media.rglob("*.tex")):
            raise VerificationError("Manim smoke unexpectedly required a TeX source file")
        durable = Path(tempfile.mkstemp(prefix="muta-manim-smoke-", suffix=".mp4")[1])
        shutil.copy2(videos[0], durable)
        return durable


def verify(root: Path, expected_arch: str, *, smoke: bool = False, timeout: float = 180.0) -> dict:
    manifest = verify_manifest(root, expected_arch)
    mach_o_count = verify_native_closure(root, expected_arch)
    executable = root.resolve() / "muta-manim"
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, timeout=timeout, check=False
    )
    if version.returncode or "Manim Community v0.22.0" not in version.stdout:
        raise VerificationError("frozen worker does not report Manim Community v0.22.0")
    result = {"manifest": manifest, "mach_o_count": mach_o_count}
    if smoke:
        video = smoke_render(root, timeout)
        try:
            result["smoke"] = {"size_bytes": video.stat().st_size, "sha256": sha256_file(video)}
        finally:
            video.unlink(missing_ok=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--target-arch", choices=("aarch64", "x86_64"), required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        result = verify(args.root, args.target_arch, smoke=args.smoke, timeout=args.timeout)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, VerificationError) as error:
        print(f"Manim worker verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "mach_o_count": result["mach_o_count"], "smoke": result.get("smoke")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
