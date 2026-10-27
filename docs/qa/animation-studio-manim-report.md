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

- Python: 2,394 tests collected; the full default suite reached 100% with expected platform skips
  and zero failures.
- Browser modules: 189/189 Node tests passed, including same-ID source, Manim render, and browser
  fallback-export races.
- Rust/Tauri: 12/12 launcher tests passed after a clean rebuild with temporary resource fixtures;
  the fixtures were removed after the run.
- Focused planner/render/contract gate: 78/78 passed; Ruff and diff whitespace checks passed.
- Real browser: desktop, 375 px portrait, and phone landscape screenshots; real authenticated
  trusted-source and MP4 requests; zero console errors. The rendered H.264 MP4 was decoded and
  played inside Muta with native controls and no autoplay. Its time scrubber appeared, the playback
  state advanced after Play, the explicit `Download rendered MP4` action remained distinct from
  browser-native export, and the layout had no horizontal overflow. Applying a scene edit removed
  the player and left zero blob video sources, proving stale playback was revoked. The captures are
  `animation-studio-desktop.png`, `animation-studio-mobile-375.png`, and
  `animation-studio-landscape.png`; `animation-studio-inline-mp4.png` records the final in-app
  playback state.
- Capability fallback browser QA used the explicit older-macOS reason. Canvas preview, timeline
  buttons, transcript, trusted source, and browser export remained available; only `Render Manim
  video` was disabled, exposed the reason as help text, and had a visibly disabled state. The
  capture is `animation-studio-manim-unavailable.png`.

## Unicode scalar/range acceptance regression

The exact packaged-app brief was re-run in the real Muta Study Studio:

- title: `A sine wave`
- concept: `Plot y = sin(x) from -π to π`
- requirements: `Draw labelled axes and trace the sine curve.`
- learner level: Secondary

It completed immediately as two typed `function` scenes. The visible validated-project disclosure
contained `expression_text: "sin(x)"`, a `call: sin` typed AST, and the exact numeric domain
`[-3.141592653589793, 3.141592653589793]`. The canvas showed labelled axes and a full sine cycle;
its accessible description and narration both used −π to π. The HTTP log contained only the
deterministic source and capability requests after generation, with no `/v1/animation/plan` model
request.

Regression coverage also checks Unicode minus variants, `between`, bracketed intervals, two-sided
inequalities, π/2 and ±2π/2pi bounds, rational bounds, negative fractional and decimal function
coefficients, and complete Unicode exponent runs such as `x²³` and `x⁻²`. Full scalar boundaries
prevent a numeric prefix such as the `2` in `2π` from being consumed while leaving `π` inside the
function expression. Explicit function requests that do not parse into the allow-listed typed AST
now fail closed in both browser and model-planner boundaries, so they cannot become prose-only
process storyboards. Non-mathematical novel process planning remains available.

Post-regression automated gates: 2,395 selected Python tests, 191/191 Node tests, focused Animation
Studio 33/33, focused planner 10/10, Ruff, whitespace, source-inventory, and built-asset parity.

## Artifacts and hashes

| Artifact | SHA-256 | Evidence |
|---|---|---|
| `animation-studio-manim-source.txt` | `fa99e3e32e4d27b72ffcdf2493404384fc9a12d3ff14b94c3b157335aa1122a6` | Exact trusted source |
| `animation-studio-manim-math.mp4` | `b8744d4674de94017b00b0d63c1e3caff95696eef8359eacdd43ccc0f0100485` | Final rendered H.264 video |
| `animation-studio-manim-contact.png` | `23c0858208d6ccb39df1f4c9462964aab64ab8839e15ba9e5edc734ea0220cc8` | One-second visual sampling across the complete video |
| `animation-studio-manim-long-copy.png` | `1a2c5d98507ae0f4290bf883eb6c195f056a7a9f85a8aafc09339d38ca9edd3b` | Long title/caption and short process-label layout |
| `animation-studio-manim-scientific.png` | `582f7850369018b1ae008e1102aefe9d23434dd29b65b94adc4bc913231f5b01` | Settled real-Manim frame proving `0.000001 × x` is typeset as grouped `1 × 10⁻⁶ · x` while its sampled curve uses the same value |
| `animation-studio-manim-scientific-powers.png` | `c6388a2caeb3772e218a0b8f8447740100c9ca29f23fde1c49deedf73ff08a73` | Settled real-Manim frames proving the scientific literal remains grouped as both exponent and exponent base |
| `animation-studio-inline-mp4.png` | `ed8fb13584696d1f19308370816e279243213246755f45495e778c0a52e183bd` | Real Muta browser showing decoded trusted MP4 playback, native controls, and the distinct rendered-MP4 download action |
| `animation-studio-manim-unavailable.png` | `1f4b7f21a37b00e0e6a14e8b046d17bdeae0c2af2dcd8c520c3abe65a13c7639` | Real Muta browser showing canvas/source preserved while only unavailable Manim rendering is disabled with the macOS reason |

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
- Process labels are individually capped at 120 characters, reject Unicode control/format
  characters, and require a letter, number, punctuation mark, or symbol at both browser import and
  public request boundaries before Pango or source generation sees them.
- Every saved project edit/reorder increments an in-memory revision, aborts the old source request,
  refreshes both disclosures, and rejects a late response even when the project ID is unchanged.
- The same revision invalidates an in-flight Manim render before playback or download and prevents
  an older completion handler from clearing the controller or status of a newer render.
- Trusted MP4 object URLs are revoked on edit, regeneration, replacement, and teardown; the player
  never autoplays, and its explicit rendered-MP4 download action cannot be confused with the browser
  canvas encoder's separate fallback action.
- Browser-native encoding has its own project revision and controller identity guard, so a stale
  same-ID export cannot download or clear a newer export's cancellation handle.
- Server numeric fields are strict: booleans and numeric strings cannot become counts, coordinates,
  timing, domains, calculus probes, or typed-AST numbers. Curve/derivative/integral probe fields
  have the same exclusivity rules in browser and server validation.
- An explicit packaging unavailable reason wins before discovery, and frozen builds never fall back
  to a host-installed `manim` on `PATH`.
- A second concurrent render receives immediate busy admission instead of queueing.
- Client cancellation and timeout terminate the complete worker process group.
- Final output selection accepts exactly one `MutaLesson.mp4` outside Manim partial files.
