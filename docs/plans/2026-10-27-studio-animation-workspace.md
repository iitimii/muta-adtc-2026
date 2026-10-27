# Muta Studio animation workspace

## Scope and boundaries

Build an offline lesson-animation authoring workspace inside the existing Study Studio and Playground. The implementation must be useful without a network, generative image service, or arbitrary code execution. It must preserve Muta's typed-spec, no-`eval`, strict-CSP boundary while supporting a separately packaged, trusted Manim runtime for high-quality source and MP4 output.

This branch starts from `cc5dde310633b676ed7062e32dc18db30e0ce75a`. It does not modify the primary checkout, its `.gitignore`, or its untracked `media/` directory. It will not package, merge, push, publish, or deploy.

## Reference-video inventory

The complete 129.58-second reference video was inspected at two-second intervals, including the opening form, generation sequence, both lesson examples, expanded source panel, playback, and the final offline demonstration. A separate full local Moonshine transcription confirmed the narrator's core claim: a local model turns the prompt into a Manim/Python scene and a rendered video, generated code is shown for judges, and Wi-Fi is off. Muta reproduces the learner-facing workflow while deliberately replacing executable generated code with a strict declarative project.

Observed product capabilities:

1. A two-column authoring workspace: lesson brief on the left, live animation preview on the right.
2. Tested-lesson shortcuts for a fraction lesson and an array-multiplication lesson.
3. Topic and learner-level selectors, an editable concept/question, and editable animation requirements.
4. A disclosure showing the prompt sent to the generation system.
5. A generate action with visible, staged progress rather than a blinking cursor.
6. A ready preview with title, explanatory subtitle/caption, play/pause, seeking, fullscreen, and replay-like use.
7. Download actions for the video and generated tutorial source.
8. A fraction animation that divides a bar into four equal parts, shades three, labels `3/4`, and states that three of four equal parts are shaded.
9. A multiplication animation that builds six rows of four dots, connects the array to repeated addition, and concludes `6 × 4 = 24`.
10. The browser remains usable after Wi-Fi is switched off.

The Muta implementation will reproduce the useful workflow rather than the reference's unsafe boundary. The local model still emits only closed declarative JSON. A server-owned emitter converts a validated project into inspectable Manim Python; that exact trusted source can be viewed/downloaded and passed to a bounded offline Manim worker. Model-authored or user-authored Python is never executed.

## Architecture

### Trusted project specification

Add a versioned `muta.lesson-animation.v1` project format. Only allow-listed scene families, finite bounded numbers, inert strings, and known transition/control enums are accepted. Unknown keys, prototype-pollution keys, over-budget projects, invalid ratios, and unsupported scene kinds fail closed. Proposal-controlled strings reach only text nodes, canvas text, form values, filenames after sanitisation, or JSON downloads.

Initial parameterised scene families:

- fraction bars for bounded proper and improper fractions;
- multiplication arrays and repeated addition;
- general one-variable function graphs backed by Muta's existing safe typed-expression parser/specification, including trigonometric, exponential, rational, and polynomial expressions;
- tertiary derivative/tangent and definite-integral scenes with bounded numerical checks;
- process/storyboard flows for science and general ordered explanations;
- vector/force scenes for direction-and-magnitude explanations.

These are families, not exact-prompt templates. A general storyboard fallback will make an honest visual from user-supplied ordered steps without claiming domain-specific geometry that was not derived.

### Deterministic authoring and playback

Add a lazily used browser module, `animation-studio.js`, exposing a small `MutaAnimator` API. It will:

- validate, normalise, and freeze projects;
- derive bounded project specs from the Studio form;
- render responsive, deterministic Canvas 2D frames;
- provide a text description and synchronized captions for every scene;
- play, pause, restart, seek, and change speed without runaway loops;
- pause while hidden/offscreen and respect reduced motion;
- cancel animation frames, observers, listeners, and media-export resources on teardown;
- persist a bounded recent-project list locally;
- import/export safe `.mutaanim` JSON projects;
- export a real playable video only when `canvas.captureStream`, `MediaRecorder`, and a supported video MIME type are available.

If real video encoding is unavailable, the UI will say so explicitly and offer the project and transcript exports. It will never label JSON, frames, or an unsupported blob as a video.

### Studio and Playground integration

Replace the current animation-like dead end with an integrated workspace:

- tested-lesson chips;
- topic, learner level, concept, and requirements fields;
- a prompt/spec disclosure;
- staged local generation feedback;
- responsive preview and transport controls;
- editable scene titles, narration, duration, ordering, and visibility;
- regenerate-from-brief and update-preview actions;
- saved-project cards in Playground with reopen, duplicate, export, and delete actions.

The visual language will use the existing Muta v5 tokens: Onest, warm off-white surfaces, ink/mint primary actions, pastel subject accents, modest radii, and visible focus. It will not import the reference video's styling.

### Trusted Manim source and bounded renderer

Add a backend module that accepts only the strict `muta.lesson-animation.v1` project models. It
emits a fixed-import `MutaLesson` scene from allow-listed scene families and a typed arithmetic
expression AST. Strings are escaped as inert `Text` arguments; no proposal string becomes Python
syntax, a filesystem path, an import, a URL, markup, TeX source, or a subprocess argument.

The render worker writes only that server-owned source into a fresh temporary directory and invokes
a configured local Manim executable with a fixed argument vector, bounded wall time, output size,
process/file descriptors, and (where supported) CPU/address-space limits. It permits no network
resources, plugins, shell expansion, or arbitrary scene name. Source generation remains available
when Manim is not installed; rendering returns an explicit capability error.

The browser shows the generated Manim source in an accessible disclosure, downloads it as `.py`,
requests a real MP4 from the bounded worker, and exposes that result in an in-app HTML video player
with native controls plus an explicitly named MP4 download action. A project revision change pauses
the player, removes its source, and revokes its object URL before rebuilding the workspace. The
existing deterministic canvas player remains
the immediate preview and browser-native video export remains a fast fallback, but neither is
misrepresented as the requested Manim render.

Runtime/package contract:

- `MUTA_MANIM_RUNTIME_DIR` points at the relocated offline runtime root, with the executable at
  `bin/manim` and its shared libraries at `lib/`.
- `MUTA_MANIM_BIN` may override the executable for development or packaging validation.
- `MUTA_MANIM_FFMPEG_BIN` may point at the packaged FFmpeg executable; only its parent directory is
  added to the worker's minimal `PATH`.
- Source development launches `animation_worker.py` with the active Python interpreter. A frozen
  gateway launches its own fixed `--animation-worker` dispatch instead; it never treats the frozen
  executable as a Python interpreter or relies on a source `.py` path. `MUTA_ANIMATION_WORKER_BIN`
  may explicitly identify that frozen gateway/worker executable when packaging stages it elsewhere.
- The gateway passes `--silent`, uses a fixed scene name and argument vector, selects only the final
  `MutaLesson.mp4`, and never accepts a caller-controlled command or output path.
- Process labels are bounded to 120 characters, reject Unicode control/format characters, and
  require a visible base character at schema validation, matching the browser and planner budgets
  before any text reaches source emission or Pango.
- Every numeric project field uses strict JSON-number validation. Booleans and numeric strings are
  rejected rather than coerced, including number leaves inside the typed expression AST; browser
  and server enforce the same mutually exclusive curve/derivative/integral probe fields.
- Production video uses Manim's fixed medium-quality profile (1280 × 720 at 30 fps); the browser
  canvas remains the immediate low-cost preview.
- Formulae use Manim 0.22's offline `MathTypst`; numeric tick labels use inert `Text`, so the runtime
  does not require a LaTeX installation or network font/resource lookup.
- One render is admitted at a time. Further requests fail immediately rather than forming an
  unbounded queue; disconnect/cancellation and timeout terminate the complete render process group.
- `MUTA_MANIM_UNAVAILABLE_REASON` is the packaging-to-feature capability contract: when set, it
  prevents executable discovery and supplies the learner-facing reason. Frozen builds never probe
  host `PATH`; the Studio checks the capability endpoint, disables only trusted MP4 rendering, and
  keeps canvas preview and trusted source available.

## Unicode scalar and range regression milestone

The packaged-app acceptance prompt `Plot y = sin(x) from −π to π` exposed a boundary mismatch:
the shared typed-expression parser accepts Unicode π, but the Studio's range extractor recognized
only the ASCII spelling `pi`. When extraction failed, the otherwise valid range words remained in
the expression and incorrectly forced the slower local planner.

Implementation and QA plan:

1. Normalize common Unicode minus characters and π at the Studio's function-input boundary before
   both scalar-range extraction and typed-expression parsing. Keep this as data normalization only;
   the existing typed AST remains the sole executable mathematical representation.
2. Replace the single range regex with a small bounded set of grammatical range forms: `from … to`,
   `between … and`, interval notation after `on`/`over`/`for`, and a two-sided scalar inequality.
   Support ordinary π multiples and fractions without accepting arbitrary source text.
3. Remove only the recognized range span before parsing the equation, preserving the original
   expression semantics and deterministic fast path.
4. Treat an explicit unresolved equation/function request as a typed-function error, not as a
   generic process-storyboard opportunity. Enforce the same narrow rule at the local model planner
   boundary so a direct request cannot turn unresolved mathematics into plausible but unverified
   prose scenes.
5. Add regressions for the exact packaged-app brief, ASCII compatibility, Unicode minus/π,
   `between`, bracketed intervals, π multiples/fractions, and two-sided inequalities. Confirm an
   actual two-variable or unsupported explicit function fails closed without entering the prose
   planner, while genuinely novel non-mathematical compositions retain the bounded planner path.
   Require every scalar match to end at a grammatical boundary so unsupported endpoint arithmetic
   cannot be split between a domain and a changed function. Cover strict inequalities, full
   superscript runs, rational coefficients/domains, and derivative probes such as `2π` and `.5`.
   Apply concrete-fraction guards only after the typed-function path has had the opportunity to
   validate the complete expression.
6. Run focused Animation Studio tests, the complete Node and Python suites, lint/diff checks, and a
   real-browser generation of the exact brief. Freeze a clean commit and require a fresh independent
   adversarial review before handing the SHA back for packaging integration.

## Acceptance criteria

### Semantic and authoring correctness

- `3/4` produces four equal regions, exactly three shaded, with matching caption and accessible description.
- `6 × 4` produces six rows of four marks, repeated addition with six addends, and total 24.
- Other valid fractions and multiplication dimensions are parameterised rather than routed by exact prompt text.
- A safe secondary/tertiary function example renders labelled axes and sampled values without executing source text.
- Sine, exponential, and rational examples use the shared typed AST; rational undefined points become visible gaps rather than connected asymptotes.
- A tertiary tangent workflow computes and displays the local derivative, while a definite-integral workflow computes and shades the requested bounded signed area.
- Ordered science/process requirements produce the same number and order of stages in the storyboard.
- Editing a scene's title, narration, duration, visibility, or order changes replay and the persisted project.
- Imported projects pass strict validation before rendering; corrupt or oversized projects show a recoverable error.

### Interaction and accessibility

- Play/pause, restart, previous/next scene, seek, and speed controls work with pointer, touch, and keyboard.
- Every interactive control has an accessible name, visible focus, and a minimum 44 × 44 CSS-pixel target.
- Timeline list items wrap native scene-selector buttons rather than replacing their button roles.
- The canvas has an accessible description, captions update with the current scene, and a full transcript is available.
- Editing or reordering a saved project refreshes both JSON and Manim-source disclosures. Source
  responses carry a local revision guard, so an older same-ID request cannot replace the current
  project source or be downloaded as if it matched the rendered video.
- The same project revision guard aborts in-flight Manim requests and checks again after the video
  blob arrives, so an old same-ID render cannot populate playback, download, or clear the controller
  for a newer render.
- Browser-native fallback encoding uses the same revision/controller identity rule: edits abort it,
  stale blobs are discarded before download, and an older completion cannot clear a newer export.
- A successful trusted render appears in-app with native play/pause, seek, volume, and platform
  fullscreen controls and never autoplays; the separate download action is unambiguous.
- Reduced-motion users do not receive automatic motion; hidden/offscreen previews stop scheduling frames.
- Desktop, 375 px and 430 px portrait, and phone landscape layouts have no horizontal overflow or composer obstruction.
- Light and dark themes preserve contrast and readable diagrams.

### Offline, safety, performance, and lifecycle

- No network requests, CDN resources, model-authored HTML/JS/Python/shader source, `eval`, or `new Function`.
- The only Python execution is the trusted server emitter's output, constructed from validated
  enums, finite bounded numbers, typed expressions, and escaped inert text.
- Renderer and export workloads are capped by scene, duration, dimensions, frame rate, and recent-project budgets.
- Ordinary chat and non-animation Studio startup do not instantiate an animation loop or load export work.
- Video download is visible/enabled only for an actual supported playable encoding; fallback language is explicit.
- Repeated mount/unmount, regeneration, import, and export do not leak RAF loops, observers, listeners, streams, or object URLs.

## Verification plan

1. Unit tests for schema validation, family planning, semantic invariants, persistence bounds, inert strings, and lifecycle cleanup.
2. UI tests for Studio form generation, staged status, editing, transport controls, saved-project Playground integration, import/export, and honest video capability detection.
3. Existing Python, Node, localisation-inventory, CSP, and offline-export suites relevant to touched surfaces.
4. Real browser testing of fraction, multiplication, graph, process, edits, saved/reopened projects, project download/import, desktop/mobile/landscape, light/dark, keyboard, reduced motion, hidden/offscreen behavior, console errors, and responsive overflow.
5. Source-emitter golden/security tests, a fake-worker timeout/size/cleanup matrix, and a real local
   Manim render of fraction, array, function, derivative/integral, vector, and process scenes when
   the local runtime is available.
6. A clean candidate commit followed by a fresh adversarial review in a separate agent context. Concrete findings are fixed and re-verified before final handoff.

## Deliberate non-goals for this branch

- Packaging or shipping a Manim/Python/TeX toolchain in this branch (the dedicated packaging task
  owns that), though this branch defines and verifies the runtime contract.
- Pretending all WebKit versions can encode video.
- Arbitrary user-authored executable code or expressions outside the existing typed expression boundary.
- Network sharing or cloud project links. “Shareable” means a validated portable project file that another Muta installation can import.
- Push, merge, release, package, or deployment.
