#!/usr/bin/env python3
"""Freeze a pinned, architecture-matched and relocatable macOS Manim worker."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from manim_worker_metadata import canonical_name, read_pins
from verify_manim_worker import MANIFEST_NAME, verify

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "desktop" / "manim" / "entrypoint.py"
REQUIREMENTS = REPO_ROOT / "desktop" / "manim" / "requirements.lock"
NATIVE_LICENSES = REPO_ROOT / "desktop" / "manim" / "native-licenses.json"
MINIMUM_MACOS = "14.0"


class BuildError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: list[str], *, capture: bool = False, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() if capture else ""
        raise BuildError(f"command exited {result.returncode}: {' '.join(command)} {detail}")
    return result


def _builder_identity(python: Path) -> dict:
    script = """
import importlib.metadata as m, json, platform, sys
print(json.dumps({
    'architecture': platform.machine(),
    'prefix': sys.prefix,
    'python': platform.python_version(),
    'manim': m.version('manim'),
    'typst': m.version('typst'),
    'pyinstaller': m.version('pyinstaller'),
}))
"""
    result = _run([str(python), "-c", script], capture=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise BuildError("builder interpreter returned invalid identity metadata") from error


def _safe_link(root: Path, path: Path) -> str:
    target = os.readlink(path)
    if Path(target).is_absolute():
        raise BuildError(f"absolute symlink in frozen worker: {path} -> {target}")
    resolved = (path.parent / target).resolve()
    if resolved != root and root not in resolved.parents:
        raise BuildError(f"symlink escapes frozen worker: {path} -> {target}")
    if not resolved.is_file():
        raise BuildError(f"broken frozen worker symlink: {path} -> {target}")
    return target


def _repair_pillow_pango_collisions(
    root: Path, builder_prefix: Path, target_arch: str
) -> list[dict]:
    """Keep Pillow's private copies private while Pango resolves its matching Conda ABI."""
    repairs = []
    repair_names = {
        "aarch64": ("libharfbuzz.0.dylib", "libfreetype.6.dylib"),
        # The Intel dependency closure does not load these names through Pango, and its
        # architecture-matched Conda runtime intentionally does not ship root HarfBuzz.
        "x86_64": (),
    }[target_arch]
    for name in repair_names:
        destination = root / "_internal" / name
        source = builder_prefix / "lib" / name
        if destination.is_symlink():
            if not source.is_file() or source.is_symlink():
                raise BuildError(f"Conda compatibility library is missing: {source}")
            target = os.readlink(destination)
            if not target.startswith("PIL/.dylibs/"):
                raise BuildError(f"unexpected PyInstaller library collision: {destination} -> {target}")
            destination.unlink()
            shutil.copy2(source, destination)
            repairs.append(
                {
                    "path": destination.relative_to(root).as_posix(),
                    "source": f"builder-prefix/lib/{name}",
                    "reason": "prevent Pillow's private ABI from shadowing Pango",
                }
            )
        elif not destination.is_file():
            raise BuildError(f"frozen compatibility library is missing: {destination}")
    return repairs


def manifest_entries(root: Path) -> list[dict]:
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            entries.append({"path": relative, "type": "symlink", "target": _safe_link(root, path)})
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return entries


def native_libraries(root: Path) -> list[dict]:
    policy_path = root / "licenses" / "native-policy.json"
    if not policy_path.is_file():
        raise BuildError(f"native licence policy is missing: {policy_path}")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    rules = policy.get("coverage_rules") or []
    documents = policy.get("license_documents") or {}
    owner_map = policy.get("python_binary_owners") or {}
    index_path = root / "licenses" / "index.json"
    if not index_path.is_file():
        raise BuildError(f"licence index is missing: {index_path}")
    license_index = json.loads(index_path.read_text(encoding="utf-8"))
    python_packages = {
        canonical_name(str(package["name"])): package
        for package in license_index.get("packages", [])
    }
    conda_by_library: dict[str, list[dict]] = {}
    for package in license_index.get("conda_packages", []):
        for name in package.get("provided_dylibs", []):
            conda_by_library.setdefault(str(name), []).append(package)

    def indexed_files(paths: list[str], *, owner: str) -> list[dict]:
        if not paths:
            raise BuildError(f"licence owner has no copied notice text: {owner}")
        result = []
        for relative in paths:
            document_path = root / "licenses" / relative
            if not document_path.is_file() or document_path.is_symlink():
                raise BuildError(f"copied licence notice is missing: {owner}: {relative}")
            result.append(
                {
                    "id": owner,
                    "path": document_path.relative_to(root).as_posix(),
                    "sha256": sha256_file(document_path),
                }
            )
        return result

    libraries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix not in {".dylib", ".so"}:
            continue
        relative = path.relative_to(root).as_posix()
        rule = next(
            (candidate for candidate in rules if fnmatch.fnmatch(relative, candidate["pattern"])),
            None,
        )
        if rule is None:
            raise BuildError(f"native library has no licence coverage rule: {relative}")
        license_files = []
        for identifier in rule.get("licenses", []):
            document = documents.get(identifier)
            if not document:
                raise BuildError(f"unknown native licence document {identifier}: {relative}")
            license_files.append(
                {
                    "id": identifier,
                    "path": f"licenses/native/{document['file']}",
                    "sha256": document["sha256"],
                }
            )
        owner = ""
        owner_version = ""
        if rule.get("license_index"):
            first = Path(relative).parts[1]
            owner = str(rule.get("owner") or owner_map.get(first) or "")
            if not owner:
                raise BuildError(f"native Python library has no specific owner: {relative}")
            if owner == "python-runtime":
                runtime_license = root / "licenses/python-runtime/LICENSE.txt"
                license_files.extend(
                    indexed_files(
                        [runtime_license.relative_to(root / "licenses").as_posix()], owner=owner
                    )
                )
            else:
                package = python_packages.get(canonical_name(owner))
                if package is None:
                    raise BuildError(f"native Python library owner is not pinned: {relative}: {owner}")
                owner_version = str(package.get("version") or "")
                license_files.extend(
                    indexed_files(list(package.get("license_files") or []), owner=owner)
                )
        if rule.get("conda_package"):
            matches = [
                package
                for package in conda_by_library.get(Path(relative).name, [])
                if package.get("license_files")
            ]
            if len(matches) != 1:
                raise BuildError(
                    f"native Conda library does not resolve to one licence record: "
                    f"{relative}: {[item.get('name') for item in matches]}"
                )
            package = matches[0]
            owner = str(package["name"])
            owner_version = str(package.get("version") or "")
            license_files.extend(
                indexed_files(list(package.get("license_files") or []), owner=owner)
            )
        if not license_files:
            raise BuildError(f"native licence rule has no actual notice text: {relative}")
        libraries.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "license_coverage": {
                    "rule": rule["id"],
                    "component": rule["component"],
                    "notice": str(rule.get("notice") or ""),
                    "source": rule["source"],
                    "owner": owner or rule["component"],
                    "owner_version": owner_version,
                    "license_files": license_files,
                    "distribution_index": bool(
                        rule.get("license_index") or rule.get("conda_package")
                    ),
                },
            }
        )
    return libraries


def build(args: argparse.Namespace) -> Path:
    if sys.platform != "darwin":
        raise BuildError("the macOS Manim worker must be frozen on macOS")
    # A venv launcher is commonly a symlink to its base interpreter. Resolving it would leave
    # the prepared environment and silently lose the pinned Manim dependencies.
    python = args.builder_python.expanduser().absolute()
    if not python.is_file():
        raise BuildError(f"builder interpreter is missing: {python}")
    identity = _builder_identity(python)
    expected_machine = {"aarch64": "arm64", "x86_64": "x86_64"}[args.target_arch]
    if identity.get("architecture") != expected_machine:
        raise BuildError(
            f"builder architecture is {identity.get('architecture')}, expected {expected_machine}"
        )
    if not str(identity.get("python", "")).startswith("3.11."):
        raise BuildError("Manim worker builder must use CPython 3.11")
    pins = read_pins(REQUIREMENTS)
    for package in ("manim", "typst", "pyinstaller"):
        if identity.get(package) != pins[package]:
            raise BuildError(
                f"builder {package} is {identity.get(package)}, expected {pins[package]}"
            )

    output = args.output.expanduser().resolve()
    work_root = args.work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    scratch = work_root / f"manim-worker-{args.target_arch}-{os.getpid()}"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir()
    dist = scratch / "dist"
    _run(
        [
            str(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "muta-manim",
            "--distpath",
            str(dist),
            "--workpath",
            str(scratch / "work"),
            "--specpath",
            str(scratch / "spec"),
            "--collect-all",
            "manim",
            "--collect-all",
            "manimpango",
            "--collect-all",
            "typst",
            str(ENTRYPOINT),
        ]
    )
    frozen = dist / "muta-manim"
    if not (frozen / "muta-manim").is_file():
        raise BuildError("PyInstaller did not produce the expected onedir worker")

    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(frozen, staging, symlinks=True)
    repairs = _repair_pillow_pango_collisions(
        staging, Path(str(identity["prefix"])), args.target_arch
    )
    executable = staging / "muta-manim"
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    licenses = staging / "licenses"
    metadata_result = _run(
        [
            str(python),
            str(REPO_ROOT / "scripts" / "manim_worker_metadata.py"),
            "--requirements",
            str(REQUIREMENTS),
            "--native-policy",
            str(NATIVE_LICENSES),
            "--output",
            str(licenses),
        ],
        capture=True,
    )
    metadata = json.loads(metadata_result.stdout.strip().splitlines()[-1])
    manifest = {
        "schema": 1,
        "target": {"os": "macos", "arch": args.target_arch},
        "runtime": {
            "python": identity["python"],
            "manim": identity["manim"],
            "typst": identity["typst"],
            "pyinstaller": identity["pyinstaller"],
            "minimum_macos": MINIMUM_MACOS,
        },
        "source": {
            "entrypoint_sha256": sha256_file(ENTRYPOINT),
            "requirements_sha256": sha256_file(REQUIREMENTS),
            "native_license_policy_sha256": sha256_file(NATIVE_LICENSES),
            "builder_sha256": sha256_file(Path(__file__).resolve()),
            "metadata_collector_sha256": sha256_file(
                REPO_ROOT / "scripts" / "manim_worker_metadata.py"
            ),
            "verifier_sha256": sha256_file(REPO_ROOT / "scripts" / "verify_manim_worker.py"),
        },
        "license_index": "licenses/index.json",
        "ffmpeg": metadata.get("ffmpeg", {}),
        "native_libraries": native_libraries(staging),
        "native_repairs": repairs,
        "files": manifest_entries(staging),
    }
    (staging / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify(staging, args.target_arch, smoke=args.smoke, timeout=args.timeout)
    if output.exists():
        shutil.rmtree(output)
    staging.replace(output)
    shutil.rmtree(scratch)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--builder-python", type=Path, required=True)
    parser.add_argument("--target-arch", choices=("aarch64", "x86_64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        output = build(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, BuildError) as error:
        print(f"Manim worker build failed: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
