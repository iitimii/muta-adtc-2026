from __future__ import annotations

import argparse
import base64
import json
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path

import collect_desktop_package as package
import collect_desktop_release as collect
import generate_latest_json as latest
import prepare_tauri_release as prepare
import pytest


def test_tauri_public_key_is_validated_and_normalized():
    raw = b"Ed" + bytes(range(40))
    document = (
        "untrusted comment: minisign public key\n"
        + base64.b64encode(raw).decode("ascii")
        + "\n"
    )
    wrapped = base64.b64encode(document.encode("utf-8")).decode("ascii")

    assert prepare.normalize_tauri_public_key(document) == wrapped
    assert prepare.normalize_tauri_public_key(wrapped) == wrapped


def test_collector_requires_a_signed_update(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "appimage").mkdir(parents=True)
    (bundle / "appimage/Muta.AppImage").write_bytes(b"app")
    kit = tmp_path / "offline-kit"
    kit.mkdir()
    (kit / "README.txt").write_text("offline", encoding="utf-8")
    args = argparse.Namespace(
        platform="linux-x86_64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "release",
    )
    try:
        collect.collect(args)
    except collect.CollectError as error:
        assert "signature is missing" in str(error)
    else:
        raise AssertionError("unsigned updater was accepted")


def test_latest_manifest_contains_all_native_targets(tmp_path: Path, monkeypatch):
    suffixes = {
        "darwin-aarch64": ".app.tar.gz",
        "darwin-x86_64": ".app.tar.gz",
        "linux-x86_64": ".AppImage",
        "windows-x86_64": "-setup.exe",
    }
    for platform, suffix in suffixes.items():
        root = tmp_path / platform
        root.mkdir()
        artifact = root / f"Muta_1.2.3_{platform}{suffix}"
        artifact.write_bytes(b"update")
        Path(f"{artifact}.sig").write_text(f"signature-{platform}\n", encoding="utf-8")
    output = tmp_path / "latest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_latest_json.py",
            "--version",
            "1.2.3",
            "--tag",
            "v1.2.3",
            "--repository",
            "owner/repo",
            "--assets-root",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )
    assert latest.main() == 0
    body = json.loads(output.read_text(encoding="utf-8"))
    assert set(body["platforms"]) == set(suffixes)
    assert body["version"] == "1.2.3"
    assert all(value["url"].startswith("https://") for value in body["platforms"].values())


def test_unsigned_package_collector_creates_linux_offline_archive(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "appimage").mkdir(parents=True)
    (bundle / "appimage/Muta.AppImage").write_bytes(b"appimage")
    kit = tmp_path / "offline-kit"
    (kit / "model-pack").mkdir(parents=True)
    (kit / "model-pack/model-pack.json").write_text('{"schema": 1}', encoding="utf-8")
    args = argparse.Namespace(
        platform="linux-x86_64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "output",
    )

    archive = package.collect(args)

    assert archive.name == "Muta_1.2.3_linux-x86_64_offline.tar.gz"
    assert archive.is_file()
    assert Path(f"{archive}.sha256").is_file()
    with tarfile.open(archive, "r:gz") as package_archive:
        root = "Muta_1.2.3_linux-x86_64_offline"
        names = set(package_archive.getnames())
        assert f"{root}/{package.INSTALL_GUIDE}" in names
        launcher = package_archive.getmember(f"{root}/Muta.sh")
        assert launcher.mode & stat.S_IXUSR
        script = package_archive.extractfile(launcher)
        assert script is not None
        assert b'chmod +x "$app"' in script.read()


def test_unsigned_package_collector_adds_macos_private_test_launcher(
    tmp_path: Path, monkeypatch
):
    bundle = tmp_path / "bundle"
    app = bundle / "macos/Muta.app"
    app.mkdir(parents=True)
    (app / "placeholder").write_bytes(b"app")
    kit = tmp_path / "offline-kit"
    (kit / "model-pack").mkdir(parents=True)
    (kit / "model-pack/model-pack.json").write_text('{"schema": 1}', encoding="utf-8")
    args = argparse.Namespace(
        platform="darwin-aarch64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "output",
    )

    sealed: list[Path] = []
    monkeypatch.setattr(package, "_adhoc_sign_macos_app", sealed.append)

    archive = package.collect(args)

    assert sealed == [args.output / "Muta_1.2.3_darwin-aarch64_offline/Muta.app"]

    with tarfile.open(archive, "r:gz") as package_archive:
        root = "Muta_1.2.3_darwin-aarch64_offline"
        names = set(package_archive.getnames())
        assert f"{root}/{package.INSTALL_GUIDE}" in names
        launcher = package_archive.getmember(f"{root}/Muta.command")
        assert launcher.mode & stat.S_IXUSR
        script = package_archive.extractfile(launcher)
        assert script is not None
        body = script.read()
        assert b'/usr/bin/xattr -c -r "$app"' in body
        assert b'/usr/bin/open "$app"' in body
        guide = package_archive.extractfile(f"{root}/{package.INSTALL_GUIDE}")
        assert guide is not None
        instructions = guide.read()
        assert b"/bin/zsh " in instructions
        assert b"Double-click Muta.command" not in instructions


def test_macos_package_preserves_file_and_framework_directory_symlinks(
    tmp_path: Path, monkeypatch
):
    bundle = tmp_path / "bundle"
    app = bundle / "macos/Muta.app"
    worker = app / "Contents/Resources/resources/bin/muta-manim/_internal"
    worker.mkdir(parents=True)
    library = worker / "av/.dylibs/libavcodec.dylib"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"library")
    (worker / "libavcodec.dylib").symlink_to("av/.dylibs/libavcodec.dylib")
    versions = app / "Contents/Frameworks/Test.framework/Versions"
    (versions / "A/Resources").mkdir(parents=True)
    (versions / "Current").symlink_to("A", target_is_directory=True)
    kit = tmp_path / "offline-kit"
    (kit / "model-pack").mkdir(parents=True)
    (kit / "model-pack/model-pack.json").write_text('{"schema": 1}', encoding="utf-8")
    args = argparse.Namespace(
        platform="darwin-aarch64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "output",
    )
    monkeypatch.setattr(package, "_adhoc_sign_macos_app", lambda _app: None)

    archive = package.collect(args)

    root = "Muta_1.2.3_darwin-aarch64_offline/Muta.app"
    with tarfile.open(archive, "r:gz") as package_archive:
        file_alias = package_archive.getmember(
            f"{root}/Contents/Resources/resources/bin/muta-manim/_internal/libavcodec.dylib"
        )
        directory_alias = package_archive.getmember(
            f"{root}/Contents/Frameworks/Test.framework/Versions/Current"
        )
        assert file_alias.issym()
        assert file_alias.linkname == "av/.dylibs/libavcodec.dylib"
        assert directory_alias.issym()
        assert directory_alias.linkname == "A"
        package_archive.extractall(tmp_path / "extracted")

    extracted = tmp_path / "extracted" / root
    assert (
        extracted
        / "Contents/Resources/resources/bin/muta-manim/_internal/libavcodec.dylib"
    ).is_symlink()
    assert (
        extracted / "Contents/Frameworks/Test.framework/Versions/Current"
    ).is_symlink()


def test_macos_private_test_seal_signs_then_strictly_verifies(tmp_path: Path, monkeypatch):
    app = tmp_path / "Muta.app"
    app.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(package.sys, "platform", "darwin")
    monkeypatch.setattr(package.shutil, "which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(package, "_mach_o_files", lambda _app: [])
    monkeypatch.setattr(
        package.subprocess,
        "run",
        lambda command, check: calls.append(command),
    )

    package._adhoc_sign_macos_app(app)

    assert calls == [
        [
            "/usr/bin/codesign",
            "--force",
            "--sign",
            "-",
            "--timestamp=none",
            str(app),
        ],
        [
            "/usr/bin/codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app),
        ],
    ]


def test_macos_macho_scan_tolerates_non_utf8_file_metadata(
    tmp_path: Path, monkeypatch
):
    app = tmp_path / "Muta.app"
    candidate = app / "Contents/Resources/non-utf8-metadata"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"binary")

    def fake_run(command, **kwargs):
        assert command == ["/usr/bin/file", "-b", str(candidate)]
        assert kwargs["text"] is True
        assert kwargs["errors"] == "replace"
        return subprocess.CompletedProcess(command, 0, "Mach-O 64-bit arm64 \ufffd\n", "")

    monkeypatch.setattr(package.subprocess, "run", fake_run)

    assert package._mach_o_files(app) == [candidate]


def test_macos_seal_restores_tauri_dereferenced_worker_aliases(
    tmp_path: Path, monkeypatch
):
    app = tmp_path / "Muta.app"
    worker = app / "Contents/Resources/resources/bin/muta-manim"
    target = worker / "_internal/av/.dylibs/libavcodec.dylib"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"same-library")
    alias = worker / "_internal/libavcodec.dylib"
    alias.write_bytes(target.read_bytes())
    (worker / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "files": [
                    {
                        "path": "_internal/libavcodec.dylib",
                        "type": "symlink",
                        "target": "av/.dylibs/libavcodec.dylib",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(package.sys, "platform", "darwin")
    monkeypatch.setattr(package.shutil, "which", lambda _command: "/usr/bin/codesign")
    monkeypatch.setattr(package, "_mach_o_files", lambda _app: [])
    monkeypatch.setattr(package.subprocess, "run", lambda *_args, **_kwargs: None)

    package._adhoc_sign_macos_app(app)

    assert alias.is_symlink()
    assert alias.readlink() == Path("av/.dylibs/libavcodec.dylib")


def test_macos_seal_rejects_changed_dereferenced_worker_alias(tmp_path: Path):
    app = tmp_path / "Muta.app"
    worker = app / "Contents/Resources/resources/bin/muta-manim"
    target = worker / "_internal/av/.dylibs/libavcodec.dylib"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"expected")
    alias = worker / "_internal/libavcodec.dylib"
    alias.write_bytes(b"changed")
    (worker / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "files": [
                    {
                        "path": "_internal/libavcodec.dylib",
                        "type": "symlink",
                        "target": "av/.dylibs/libavcodec.dylib",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(package.PackageError, match="differs from target"):
        package._restore_manim_worker_symlinks(app)


def test_macos_seal_rejects_worker_root_symlink_outside_app(tmp_path: Path):
    app = tmp_path / "Muta.app"
    worker_parent = app / "Contents/Resources/resources/bin"
    worker_parent.mkdir(parents=True)
    external = tmp_path / "external-worker"
    external.mkdir()
    (external / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps({"schema": 1, "files": []}), encoding="utf-8"
    )
    (worker_parent / "muta-manim").symlink_to(external, target_is_directory=True)

    with pytest.raises(package.PackageError, match="path contains a symlink"):
        package._restore_manim_worker_symlinks(app)


def test_macos_seal_rejects_intermediate_alias_parent_symlink(tmp_path: Path):
    app = tmp_path / "Muta.app"
    worker = app / "Contents/Resources/resources/bin/muta-manim"
    internal = worker / "_internal"
    internal.mkdir(parents=True)
    real_parent = worker / "real-parent"
    real_parent.mkdir()
    target = real_parent / "target.dylib"
    target.write_bytes(b"library")
    alias_parent = internal / "redirected"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    alias = alias_parent / "alias.dylib"
    alias.write_bytes(target.read_bytes())
    (worker / "MUTA-MANIM-MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "files": [
                    {
                        "path": "_internal/redirected/alias.dylib",
                        "type": "symlink",
                        "target": "target.dylib",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(package.PackageError, match="parent escapes its root"):
        package._restore_manim_worker_symlinks(app)
    assert alias.read_bytes() == b"library"


def test_macos_private_test_refreshes_manifests_after_nested_signing(
    tmp_path: Path, monkeypatch
):
    app = tmp_path / "Muta.app"
    resources = app / "Contents/Resources/resources"
    resources.mkdir(parents=True)
    (resources / "desktop-product.json").write_text("{}", encoding="utf-8")
    nested = resources / "bin/muta-manim/muta-manim"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"worker")
    events: list[str] = []

    monkeypatch.setattr(package.sys, "platform", "darwin")
    monkeypatch.setattr(package.shutil, "which", lambda _command: "/usr/bin/codesign")
    monkeypatch.setattr(package, "_mach_o_files", lambda _app: [nested])
    monkeypatch.setattr(
        package,
        "refresh_desktop_manifests",
        lambda root: events.append(f"refresh:{root}"),
    )

    def fake_run(command, **_kwargs):
        events.append("sign:" + command[-1])

    monkeypatch.setattr(package.subprocess, "run", fake_run)

    package._adhoc_sign_macos_app(app)

    assert events == [
        f"sign:{nested}",
        f"refresh:{resources}",
        f"sign:{app}",
        f"sign:{app}",
    ]


def test_macos_private_test_refreshes_workerless_package_before_outer_seal(
    tmp_path: Path, monkeypatch
):
    app = tmp_path / "Muta.app"
    resources = app / "Contents/Resources/resources"
    resources.mkdir(parents=True)
    (resources / "desktop-product.json").write_text("{}", encoding="utf-8")
    events: list[str] = []

    monkeypatch.setattr(package.sys, "platform", "darwin")
    monkeypatch.setattr(package.shutil, "which", lambda _command: "/usr/bin/codesign")
    monkeypatch.setattr(package, "_mach_o_files", lambda _app: [])
    monkeypatch.setattr(
        package,
        "refresh_desktop_manifests",
        lambda root: events.append(f"refresh:{root}"),
    )

    def fake_run(command, **_kwargs):
        events.append("sign:" + command[-1])

    monkeypatch.setattr(package.subprocess, "run", fake_run)

    package._adhoc_sign_macos_app(app)

    assert events == [
        f"refresh:{resources}",
        f"sign:{app}",
        f"sign:{app}",
    ]


def test_unsigned_package_collector_names_windows_install_guide(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "nsis").mkdir(parents=True)
    (bundle / "nsis/Muta-setup.exe").write_bytes(b"installer")
    kit = tmp_path / "offline-kit"
    (kit / "model-pack").mkdir(parents=True)
    (kit / "model-pack/model-pack.json").write_text('{"schema": 1}', encoding="utf-8")
    args = argparse.Namespace(
        platform="windows-x86_64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "output",
    )

    archive = package.collect(args)

    with zipfile.ZipFile(archive) as package_archive:
        root = "Muta_1.2.3_windows-x86_64_offline"
        names = set(package_archive.namelist())
        assert f"{root}/{package.INSTALL_GUIDE}" in names
        assert f"{root}/Install-Muta.cmd" in names
        guide = package_archive.read(f"{root}/{package.INSTALL_GUIDE}")
        assert b"HOW TO INSTALL MUTA ON WINDOWS\r\n" in guide
        installer = package_archive.read(f"{root}/Install-Muta.cmd")
        assert b"\r\n" in installer
        assert b"\r\r\n" not in installer


def test_signed_macos_release_uses_notarized_install_guide(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "macos").mkdir(parents=True)
    update = bundle / "macos/Muta.app.tar.gz"
    update.write_bytes(b"signed update")
    Path(f"{update}.sig").write_text("signature", encoding="utf-8")
    kit = tmp_path / "offline-kit"
    (kit / "Muta.app").mkdir(parents=True)
    (kit / "model-pack").mkdir()
    (kit / "README.txt").write_text("old instructions", encoding="utf-8")
    args = argparse.Namespace(
        platform="darwin-aarch64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "release",
    )

    collect.collect(args)

    archive = args.output / "Muta_1.2.3_darwin-aarch64_offline.tar.gz"
    with tarfile.open(archive, "r:gz") as package_archive:
        names = set(package_archive.getnames())
        assert "offline-kit/HOW TO INSTALL.txt" in names
        assert "offline-kit/README.txt" not in names
        assert "offline-kit/Muta.command" not in names
        guide = package_archive.extractfile("offline-kit/HOW TO INSTALL.txt")
        assert guide is not None
        assert b"Developer ID signed and notarized" in guide.read()


def test_signed_windows_release_uses_install_helper_and_guide(tmp_path: Path):
    bundle = tmp_path / "bundle"
    (bundle / "nsis").mkdir(parents=True)
    update = bundle / "nsis/Muta-setup.exe"
    update.write_bytes(b"signed installer")
    Path(f"{update}.sig").write_text("signature", encoding="utf-8")
    kit = tmp_path / "offline-kit"
    (kit / "model-pack").mkdir(parents=True)
    (kit / "README.txt").write_text("old instructions", encoding="utf-8")
    args = argparse.Namespace(
        platform="windows-x86_64",
        version="1.2.3",
        bundle_root=bundle,
        offline_kit=kit,
        output=tmp_path / "release",
    )

    collect.collect(args)

    archive = args.output / "Muta_1.2.3_windows-x86_64_offline.zip"
    with zipfile.ZipFile(archive) as package_archive:
        names = set(package_archive.namelist())
        assert "offline-kit/HOW TO INSTALL.txt" in names
        assert "offline-kit/README.txt" not in names
        assert "offline-kit/Install-Muta.cmd" in names
        assert b"\r\r\n" not in package_archive.read("offline-kit/Install-Muta.cmd")
