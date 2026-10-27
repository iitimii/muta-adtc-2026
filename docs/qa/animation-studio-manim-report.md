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
inequalities (strict and inclusive), π/2 and ±2π/2pi bounds, rational bounds, negative fractional
and decimal function coefficients, and complete Unicode exponent runs such as `x²³` and `x⁻²`.
Full scalar boundaries prevent a numeric prefix such as the `2` in `2π` from being consumed while
leaving `π` inside the function expression. They also reject unsupported endpoint tails such as
`2π+1`, `2π×2`, and `π/π` rather than splitting them between a domain and an altered equation.
Valid typed functions containing values that resemble concrete fraction lessons, including
`10/2*x`, `-10/2*x`, and rational domain endpoints, are parsed before those lesson-family guards.
Derivative probes retain `2π` and leading-decimal points without contaminating the expression AST.
An explicitly requested but invalid probe such as `x = 2π+1` or `x = foo` fails closed; the
default probe at zero is used only when the learner did not specify an `at`/`when` point.
The probe variable must also match the typed function's independent variable, so a function of `t`
cannot silently reinterpret a requested `x` probe (or vice versa).
Likewise, malformed explicit integral bounds such as `from 0 to foo` or `from 0 to π+1` cannot
fall back to [0, 1]; that default is reserved for requests which state no bounds.
Scalar clauses are consumed only when their complete same-line tail is valid: appended arithmetic,
punctuation followed by another token, multiple explicit probe clauses, and incomplete `from`/`between`/
interval clauses all fail closed. Explicit range variables obey the same x/t agreement invariant.
Every title, concept and requirement line is checked; identical repeated context is allowed, while
conflicting or malformed range/probe clauses in any later field invalidate the complete request.
The same rule covers explicit function relations: repeated typed AST context is allowed, while
conflicting equations, outputs, or independent variables cannot be silently ignored.
Brief clauses are checked across both newlines and semicolons. Probe-only requirements such as
“Show the tangent at x=2” are not misclassified as new equations, while standalone domain clauses
such as “Use domain x in [-pi, pi]” or “Use range for x = [-pi, pi]” are parsed into the
function's typed range. Multiple probes or ranges in one semicolon-delimited field and dangling
positive or negative arithmetic tails fail closed.
Explicit function requests that do not parse into the allow-listed typed AST now fail closed in both
browser and model-planner boundaries, so they cannot become prose-only process storyboards.
Non-mathematical novel process planning remains available.

Generated process narrations are also checked for completion before project construction. The
planner requests one concise 60–90-character sentence per step, ending well before the existing
120-character schema limit. Missing punctuation and obvious incomplete endings trigger the single
bounded structured repair with “incomplete_sentence”; Muta does not conceal truncation by appending
punctuation to cut-off model text. Completion checks ignore inert closing quotes/brackets before
inspecting the last lexical word and accept common Latin, CJK and Arabic sentence terminators.
User-authored process labels remain unchanged.

If the bounded local model supplies one or more complete generated sentences followed only by a
clipped fragment, the planner keeps the already-complete sentence prefix and discards that fragment
before revalidation. It never invents punctuation or words. An explicit request for two through
eight steps is also enforced against the proposal, including during the one structured repair.
The model prompt excludes thank-you, end-screen, return-to-storyboard and other interface/meta
states so the bounded scene budget remains focused on the requested teaching sequence.
The same exclusions are validated after decode. Unsupported one- or nine-plus-scene requests and
conflicting counts fail before model contact; digit, word and hyphenated two-through-eight forms
share the exact schema/post-decode count. Caption-prefix recovery excludes decimal points, short
abbreviations and non-boundary periods.
The final focused regression gate passes 87 Python cases and all 193 Node cases. It includes the
public plan route returning HTTP 422 (without contacting the model) for an invalid count, with no
generation/session slot left busy. Full-suite and final extracted-package evidence are recorded
separately against their immutable source identity; a passing source fixture is not package approval.
The preview/render action area persistently tells the learner to review every scene and the maths
before rendering because open-ended tutor narration is not formally verified. Typed function ASTs
and numerical calculus checks remain deterministic; that does not certify model-written analogies.

Final whole-brief/caption gate: 2,328 Python tests passed, 77 skipped and one deselected (2,405
selected); 193/193 Node tests passed; focused Animation Studio 35/35 and planner 20/20 passed.
Touched-file Ruff, whitespace, generated localisation inventory, and source/built-asset parity also
passed.

The exact packaged Qwen2.5 model was exercised through the development gateway with the equality
brief that had previously returned HTTP 503. The revised planner returned HTTP 200 on its first
attempt in 10.38 seconds, with exactly three scenes and three complete captions. Trusted Manim
source generation preserved all three captions. One generated seesaw analogy was still
semantically ambiguous, demonstrating why open-ended narrative is labelled for learner review and
must not be described as formally verified. The packaging gate must configure the bundled Manim
worker and inspect the resulting MP4; the plain development environment does not stand in for that
packaged-runtime check.

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
