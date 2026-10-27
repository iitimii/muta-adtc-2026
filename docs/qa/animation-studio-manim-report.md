# Trusted Manim render evidence

Date: 2026-10-27  
Source branch: `codex/studio-animation-workspace`  
Base source: `cc5dde310633b676ed7062e32dc18db30e0ce75a`

## Runtime contract exercised

- Manim: offline 0.22 runtime at `/tmp/muta-manim-feasibility.ODFfkv/arm64`
- Entry point: `bin/manim`
- FFmpeg: `/opt/homebrew/bin/ffmpeg`
- Gateway configuration: `MUTA_MANIM_RUNTIME_DIR`, `MUTA_MANIM_BIN`, and
  `MUTA_MANIM_FFMPEG_BIN`
- Frozen worker contract: the packaged gateway's `--animation-worker` dispatch, optionally selected
  explicitly with `MUTA_ANIMATION_WORKER_BIN`; development alone uses `animation_worker.py`
- Fixed Manim arguments: `--silent -qm --format mp4 --disable_caching`, fixed
  `MutaLesson` scene, fresh temporary media directory
- Network mode during real-app QA: `MUTA_OFFLINE=1`, `HF_HUB_OFFLINE=1`, and
  `TRANSFORMERS_OFFLINE=1`

The checked-in source fixture is the exact server-emitted source used for the checked-in MP4.
It contains fraction partition/shade, multiplication-array build/addition, cubic graph,
derivative/tangent, and definite-integral scenes. The browser generated the same cubic family from
`Plot y = x^3 and show the tangent at x = 2`, displayed the trusted source, and completed
`POST /v1/animation/render` with HTTP 200. Browser console warnings/errors: zero.

Final automated gates after the review fixes:

- Python: 2,375 tests collected; the full default suite reached 100% with expected platform skips
  and zero failures.
- Browser modules: 184/184 Node tests passed, including same-ID edit/reorder source races.
- Rust/Tauri: 12/12 launcher tests passed after a clean rebuild with temporary resource fixtures;
  the fixtures were removed after the run.
- Focused planner/render/contract gate: 59/59 passed; Ruff and diff whitespace checks passed.
- Real browser: desktop, 375 px portrait, and phone landscape screenshots; real authenticated
  trusted-source and MP4 requests; zero console errors. The captures are
  `animation-studio-desktop.png`, `animation-studio-mobile-375.png`, and
  `animation-studio-landscape.png`.

## Artifacts and hashes

| Artifact | SHA-256 | Evidence |
|---|---|---|
| `animation-studio-manim-source.txt` | `fa99e3e32e4d27b72ffcdf2493404384fc9a12d3ff14b94c3b157335aa1122a6` | Exact trusted source |
| `animation-studio-manim-math.mp4` | `b8744d4674de94017b00b0d63c1e3caff95696eef8359eacdd43ccc0f0100485` | Final rendered H.264 video |
| `animation-studio-manim-contact.png` | `23c0858208d6ccb39df1f4c9462964aab64ab8839e15ba9e5edc734ea0220cc8` | One-second visual sampling across the complete video |
| `animation-studio-manim-long-copy.png` | `1a2c5d98507ae0f4290bf883eb6c195f056a7a9f85a8aafc09339d38ca9edd3b` | Long title/caption and short process-label layout |
| `animation-studio-manim-scientific.png` | `da2ae6f3233353e71d846ecbefdb3310c497d9d0610aaa4c41fc191892599233` | Settled real-Manim frame proving `0.000001 × x` is typeset as `1 × 10⁻⁶ · x` while its sampled curve uses the same value |

`ffprobe` result for the final MP4:

```text
codec_name=h264
width=1280
height=720
r_frame_rate=30/1
duration=9.326823
size=519300
```

Visual inspection confirmed parameter-correct partitioning/shading with all cell edges aligned,
the approved warm graphite stage, progressive dot-array build,
repeated addition, labelled numeric axes/domain, clean `y = x^3` typesetting, cubic shape and origin
crossing, tangent at input two, bounded signed area, readable wrapped titles/captions, and no frame
clipping.

## Safety and failure probes

- Model/user strings remain Python constants routed only to Manim text objects.
- Typed expression text must parse to the same AST and use exactly the declared variable.
- An absolute-value cusp at zero is rejected as an undefined derivative.
- A pole inside a requested integral is rejected as non-convergent.
- Smooth stationary points such as the derivative of `x^2` at zero are accepted.
- Undefined curve samples become segment gaps rather than zero values.
- Scientific-notation formula text is compiled from the same numeric typed AST used to sample its
  curve; exponent text is never passed through as an ambiguous literal such as `1e-06`.
- Process labels are individually capped at 120 visible, non-control characters at the public
  request/import boundary before Pango or source generation sees them.
- Every saved project edit/reorder increments an in-memory revision, aborts the old source request,
  refreshes both disclosures, and rejects a late response even when the project ID is unchanged.
- A second concurrent render receives immediate busy admission instead of queueing.
- Client cancellation and timeout terminate the complete worker process group.
- Final output selection accepts exactly one `MutaLesson.mp4` outside Manim partial files.
