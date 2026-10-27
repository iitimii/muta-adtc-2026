# Offline Manim worker packaging for macOS

## Scope

Package the trusted animation renderer as a separate, architecture-matched macOS worker. The
worker is an application resource, not part of the frozen gateway and not resolved from the host
`PATH`. This change owns only the desktop launcher and packaging pipeline. It does not change the
animation schema, emitter, routes, or UI.

The initial shipping targets are Apple Silicon and Intel macOS. Linux and Windows remain
unchanged until a later, explicitly authorised build.

The worker is opt-in at the low-level desktop builder (`--manim-worker-dir`) so the existing
four-platform CI does not silently download a new runtime or fail on non-Animator builds. The
Mac candidate runbook uses `manual_desktop_worker.py`, which prepares and passes the verified
worker, and artifact acceptance uses `--require-manim-worker`. Public release automation must
provision this same verified layer and enable that acceptance flag before an Animator release.

## Runtime contract

The packaged executable is:

```text
Muta.app/Contents/Resources/resources/bin/muta-manim/muta-manim
```

`desktop/backend_entry.py` validates that executable against `desktop-product.json` and exports
its absolute path as `MUTA_MANIM_BIN`. The trusted renderer invokes the CLI without a shell:

```text
muta-manim -ql --format mp4 --disable_caching --media_dir <fresh-dir> lesson.py MutaLesson
```

Only server-emitted source is passed to it. End users install no Python, Manim, Typst, TeX,
Homebrew, Conda, or network dependency.

## Pinned worker and cache

- Python: CPython 3.11, architecture-matched to the application.
- Manim Community: 0.22.0.
- Typst Python binding/compiler: 0.15.0.
- PyInstaller: 6.22.2, onedir layout.
- NumPy: 2.2.6; SciPy: 1.15.3. The application keeps its macOS 12 baseline. The separately
  bundled Animator worker requires macOS 14 because 172 files in the verified Apple Silicon
  native closure declare a macOS 14 deployment target (including PyAV and SciPy extensions).
  On macOS 12 or 13, the launcher does not execute that worker and reports the renderer as
  unavailable while preserving animation preview, project export, transcript, and generated
  Manim source. This split baseline is encoded in the worker manifest and launcher capability
  check instead of silently raising the whole application's minimum version.
- All Python runtime dependencies are exact-version pinned in
  `desktop/manim/requirements.lock`.

`scripts/build_manim_worker.py` accepts a prepared, architecture-matched builder interpreter,
verifies the complete pinned dependency set, freezes the CLI entry point, collects every shipped
Python licence, writes a file-by-file SHA-256 runtime manifest, and runs the strict verifier.
The builder environment is disposable and never enters the application.

`scripts/manual_desktop_worker.py` keys the layer from the worker entry point, pins, builder,
verifier, and licence recipe. A verified `MUTA_MANIM_WORKER_DIR` may seed a missing cache; otherwise
`MUTA_MANIM_BUILDER_PYTHON` builds it. Cache hits are independently reverified before staging.

## Native closure and signing

`scripts/verify_manim_worker.py` fails closed unless:

- every manifest byte size and SHA-256 matches;
- every Mach-O is the requested thin architecture;
- every worker Mach-O declares a deployment target no newer than macOS 14.0, while the Tauri
  application remains targeted at macOS 12.0;
- no dependency or LC_RPATH names a build-machine path such as `/opt/homebrew`, `/usr/local`,
  `/private/tmp`, or `/Users`;
- Manim and Typst report the pinned versions;
- the licence inventory and executable are present;
- an optional smoke gate renders a Typst fraction/function scene to a real MP4 without producing
  a `.tex` file.

The existing nested signing pass signs every Mach-O under `app-resources` before Tauri seals a
release. Because a code signature changes Mach-O bytes, the build then regenerates the worker,
product, and desktop manifests before outer application signing. Private-test collection follows
the same order: sign nested Mach-O files, refresh those manifests from the signed bytes, sign the
outer app, then run strict deep verification. The artifact inspector also checks the worker
architecture, closure, and manifest.

## Provenance and licences

Each worker contains `MUTA-MANIM-MANIFEST.json` with runtime versions, target architecture,
source-input hashes, the native-library inventory, the licence index, and SHA-256 metadata for
every shipped file. Licence texts found in installed distribution metadata are copied below
`licenses/python/`. Standard third-party texts are fetched from a pinned SPDX licence-list tag,
verified against hashes in `native-licenses.json`, and shipped below `licenses/native/`. Every
discovered Mach-O library is bound to a named coverage rule and concrete shipped text or to its
own distribution's populated licence index. This includes pycairo's LGPL/MPL alternatives and
the FFmpeg/x264/x265 closure embedded by the pinned PyAV wheel.

## Verification

1. Unit-test manifest verification, dependency-path rejection, architecture rejection, staging,
   launcher path resolution, environment sanitisation, and cache invalidation.
2. Build one worker per architecture from the prepared feasibility environments.
3. Run the CLI and real Typst MP4 smoke from a relocated directory with `DYLD_LIBRARY_PATH` and
   `PYTHONPATH` unset.
4. Ad-hoc sign all nested Mach-O files, verify the signature deeply, and repeat the real render.
5. Integrate this reviewed packaging commit with the separately reviewed animator source; only
   then build the two local Mac application candidates.

## Deliberate non-goals

- No arbitrary model- or user-authored Python execution.
- No runtime package installation or fallback to host tools.
- No TeX distribution.
- No Windows/Linux worker in this change.
- No release upload, source push, main merge, or service deployment.
