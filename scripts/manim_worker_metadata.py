#!/usr/bin/env python3
"""Verify the pinned Manim build environment and collect its distributable licences."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import sys
import urllib.request
from pathlib import Path


class MetadataError(RuntimeError):
    pass


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise MetadataError(f"worker dependency is not exactly pinned: {line}")
        name, version = line.split("==", 1)
        key = canonical_name(name.strip())
        if not key or not version.strip() or key in pins:
            raise MetadataError(f"invalid worker dependency pin: {line}")
        pins[key] = version.strip()
    if not pins:
        raise MetadataError("worker dependency lock is empty")
    return pins


def _license_files(distribution: importlib.metadata.Distribution) -> list[Path]:
    result: list[Path] = []
    for relative in distribution.files or ():
        name = Path(str(relative)).name.lower()
        parts = tuple(part.lower() for part in Path(str(relative)).parts)
        if not (
            name.startswith(("license", "copying", "notice"))
            or "licenses" in parts
        ):
            continue
        source = Path(distribution.locate_file(relative))
        if (
            source.is_file()
            and not source.is_symlink()
            and source.suffix.lower() not in {".so", ".dylib", ".dll", ".pyd"}
        ):
            result.append(source)
    return sorted(set(result))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _native_documents(policy_path: Path, output: Path) -> tuple[dict, list[dict]]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema") != 2:
        raise MetadataError("unsupported native licence policy schema")
    documents = policy.get("license_documents") or {}
    base_url = str(policy.get("document_base_url") or "")
    if not documents or not base_url.startswith("https://"):
        raise MetadataError("native licence policy has no pinned HTTPS documents")
    collected = []
    for identifier, specification in sorted(documents.items()):
        filename = str(specification.get("file") or "")
        expected = str(specification.get("sha256") or "")
        if not filename or Path(filename).name != filename or len(expected) != 64:
            raise MetadataError(f"invalid native licence document: {identifier}")
        url = base_url + filename
        request = urllib.request.Request(url, headers={"User-Agent": "Muta-packager/1"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        except OSError as error:
            raise MetadataError(f"could not fetch native licence text: {url}") from error
        if sha256_bytes(body) != expected:
            raise MetadataError(f"native licence text failed SHA-256 verification: {identifier}")
        destination = output / "native" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        collected.append(
            {
                "id": identifier,
                "path": destination.relative_to(output).as_posix(),
                "sha256": expected,
                "source": url,
            }
        )
    shutil.copy2(policy_path, output / "native-policy.json")
    return policy, collected


def _conda_packages(output: Path) -> list[dict]:
    metadata_root = Path(sys.prefix) / "conda-meta"
    if not metadata_root.is_dir():
        return []
    packages = []
    for record_path in sorted(metadata_root.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        provided = sorted(
            {
                Path(relative).name
                for relative in record.get("files", [])
                if Path(relative).suffix == ".dylib"
            }
        )
        if not provided:
            continue
        extracted = Path(str(record.get("extracted_package_dir") or ""))
        license_root = extracted / "info" / "licenses"
        copied = []
        if license_root.is_dir():
            for source in sorted(license_root.rglob("*")):
                if not source.is_file() or source.is_symlink():
                    continue
                relative = source.relative_to(license_root)
                destination = output / "conda" / str(record["name"]) / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied.append(destination.relative_to(output).as_posix())
        packages.append(
            {
                "name": str(record["name"]),
                "version": str(record.get("version") or ""),
                "license": str(record.get("license") or "unknown"),
                "source": str(record.get("url") or record.get("channel") or ""),
                "provided_dylibs": provided,
                "license_files": copied,
            }
        )
    return packages


def collect(requirements: Path, native_policy: Path, output: Path) -> dict:
    pins = read_pins(requirements)
    output.mkdir(parents=True, exist_ok=True)
    policy, native_documents = _native_documents(native_policy, output)
    overrides = policy.get("python_license_overrides") or {}
    packages = []
    for name, expected in sorted(pins.items()):
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise MetadataError(f"pinned worker package is missing: {name}=={expected}") from error
        actual = distribution.version
        if actual != expected:
            raise MetadataError(
                f"worker package differs from lock: {name} expected {expected}, got {actual}"
            )
        copied = []
        for index, source in enumerate(_license_files(distribution), start=1):
            destination = output / "python" / name / f"{index:03d}-{source.name}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(destination.relative_to(output).as_posix())
        metadata = distribution.metadata
        if not copied and name in overrides:
            for identifier in overrides[name]:
                document = next(
                    (item for item in native_documents if item["id"] == identifier), None
                )
                if document is None:
                    raise MetadataError(
                        f"unknown native licence override for {name}: {identifier}"
                    )
                copied.append(document["path"])
        packages.append(
            {
                "name": str(metadata.get("Name") or name),
                "version": actual,
                "license": str(
                    metadata.get("License-Expression") or metadata.get("License") or "unknown"
                ),
                "project_url": str(metadata.get("Home-page") or ""),
                "license_files": copied,
            }
        )

    python_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    python_license_relative = ""
    if python_license.is_file():
        destination = output / "python-runtime" / "LICENSE.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(python_license, destination)
        python_license_relative = destination.relative_to(output).as_posix()

    ffmpeg: dict[str, object] = {}
    try:
        import av._core

        ffmpeg = {
            "version": str(av._core.ffmpeg_version_info),
            "libraries": av._core.library_meta,
        }
    except (ImportError, AttributeError):
        pass

    body = {
        "schema": 1,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "architecture": platform.machine(),
            "license_file": python_license_relative,
        },
        "packages": packages,
        "ffmpeg": ffmpeg,
        "native_documents": native_documents,
        "conda_packages": _conda_packages(output),
    }
    (output / "index.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--native-policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        body = collect(
            args.requirements.resolve(), args.native_policy.resolve(), args.output.resolve()
        )
    except (OSError, ValueError, MetadataError) as error:
        parser.error(str(error))
    print(json.dumps(body, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
