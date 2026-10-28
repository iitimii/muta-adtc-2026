# Model-authored Manim Animator

## Human intent and scope

Replace normal Studio generation by prompt -> installed local model -> actual Manim Python
source -> isolated rendering -> MP4. Do not select a fixed mathematical scene family or invent
a successful generic storyboard. Keep existing saved lessons readable, but do not present the
old typed scene catalogue as the new model-driven workflow.

The user has authorised implementation and local Apple Silicon/Intel rebuilding. Other OS
builds, publication, deployment and source pushes remain gated. Preserve primary checkout edits,
the user's saved projects/models, all existing release files and the paused candidate evidence.

## First gate: isolation feasibility

Model-generated Python is untrusted. An AST validator is defence in depth, not an OS sandbox.
Before executing it, prove a macOS child sandbox that permits reads only from immutable worker
resources/system runtime resources, writes only within the job directory, and no networking.
Prove forbidden read/write/network/process operations fail using disposable canary files, never
real secrets. Keep wall time, process-tree RSS, output size and cancellation bounded. If isolation
is unavailable, fail closed with a useful capability message; do not run on the host as fallback.
The local sandbox-exec manual marks that interface deprecated: treat successful local tests as
platform-specific evidence, not a guarantee of future or other-OS support. Keep the app's existing
macOS 12 baseline and optional Manim macOS 14 minimum honest.

## Program boundary

The model authors normal Scene/ThreeDScene construct code, composing approved Manim primitives,
geometry, axes, mathematical text, transformations, bounded iteration and numerical plot lambdas.
It may not import arbitrary modules, inspect Python internals, read arbitrary files, change
renderer paths/configuration, launch arbitrary processes or request network resources. These
are security and resource constraints, not equation-specific templates.

Validate the complete Python AST and bound source/nodes/literals/loops before launching the
sandbox. The code displayed/exported must be the actual code rendered; never claim model
provenance for server-written scene substitutions. Use the bundled Manim/Typst capabilities,
without downloading TeX, fonts or packages at runtime.

### Rendering refinement from actual tutor tests (28 October)

The installed small tutor can author valid sine code with compact generic API demonstrations,
but sometimes draws valid geometry outside Manim's default frame and ignores repair feedback.
Use a fixed, separately reviewed worker runner that imports the original `lesson.py` bytes
unchanged. It frames visible 2D geometry/animation targets by uniformly adjusting only the
camera, clears Cairo/static projection caches, and preserves object coordinates, ratios and
labelled mathematical values. This is a renderer viewport policy, not an equation-specific
scene fallback. Refuse extreme framing that makes labels unreadable; reject nonfinite geometry
and empty/transparent final frames. Three-dimensional projection is not automatically framed.
These boundary/final checks are not a proof of subject correctness or every intermediate frame.

### Prompt and acceptance limits

Real installed Qwen2.5-1.5B trials revealed a frontend/backend prompt mismatch: the minimal
Studio derives its display title from the complete concept, so the model received the same
instruction twice as Topic and Prompt. A sine request then repeated animation code until its
token budget, while the same request with the redundant Topic removed returned a complete
scene using the exact requested domain. Omit that line only when the whitespace-normalized
topic and concept match; retain original title and brief metadata. Distinct topic context stays.

Generic API prompt experiments are evidence, not a success catalogue. Some stronger-looking
instructions made the small tutor less reliable and were reverted. A successful render does
not establish fidelity: one real circle request omitted its requested radius segment, and a
division source used a count grid rather than a clearly staged sharing explanation. Keep the
visible review-before-sharing warning and report such limitations. Do not claim universal STEM
correctness, conceal failures, or replace rejected model code with trusted example scenes.

### Native data-preservation gate

Before generating a new native test lesson, inspection found the eight-project library silently
discarded the oldest entry on a ninth save. Keep the bounded storage budget, but reject a new
project when all eight slots are occupied, before any write or event. Existing-ID updates must
still work. The finished video remains available with an explicit save warning and export;
only the learner may choose which saved project to remove. Test that the original serialized
library is byte-identical after rejection, including mixed legacy/program documents. Do not
exercise a ninth native save until the corrected source has been reviewed and rebuilt.

## Public contract (freeze before UI/backend split)

- POST /v1/animation/program: authenticated learner brief and optional bounded previous source /
  render diagnostic; local model call under existing generation/session admission; return the
  actual validated Manim program, source identity/model provenance and repair state.
- POST /v1/animation/program/render: authenticated program -> validated and isolated render ->
  MP4, with existing single-render admission, disconnect cancellation and safe download headers.
- Existing capability response will explicitly distinguish model-code isolation availability
  from legacy trusted-emitter availability. Never advertise code rendering on unsupported hosts.
- Existing typed-project endpoints remain for legacy saved lessons. New Studio Generate must
  always use the model program path, including the radius-5.6 test.

Prefer stateless source+binary render requests over an unbounded video/job database. Keep the
client's generate/repair/render budget bounded, with visible progress and at most two repair
turns. Every individual server request is also time/resource/admission bounded; validation,
rendering and provenance checks never depend solely on client state.

## Minimal UI and persistence

Keep the established concept + learner-level brief and one video stage. Generate shows local
code generation/render/repair progress; successful output is a single paused video with one
Download video action. Actual source, brief and advanced controls remain collapsed. No new
colours, framework or redundant preview. Cancellation/edit/navigation must invalidate stale
results and revoke blobs. Persist/import/export bounded program documents without executing
Python in the browser; render imported source only through the same server checks/sandbox.

## Verification and acceptance

1. Fresh adversarial review of the execution boundary and all malicious/resource probes.
2. Model-call tests prove every new Generate brief reaches the installed model; no deterministic
   geometry bypass or fixed-scene success fallback. Verify cancellation, admission and repairs.
3. Exact prompt radius 5.6, changed radii/centres/units, sin/cubic/derivative, vectors and multi-
   object geometry, then unseen STEM prompts. Inspect mathematical values and actual video
   frames, not merely exit code. Record unsupported cases honestly; no universal accuracy claim.
4. Browser/native single-stage, source/video parity, exports, saved projects, light/dark,
   keyboard/narrow/reduced-motion, cancellation/stale-state checks.
5. Complete source regression suites, generated OpenAPI/UI parity and fresh independent review.
6. Only then freeze an exact source SHA, rebuild Mac ARM/Intel, re-extract/inspect/sign/verify,
   run the real frozen model-to-code-to-video path per architecture, and final native checks.

## Ownership

Root owns this integration worktree's contracts, source/program validation, API and UI changes.
Muta packaging initially owns only isolated disposable sandbox feasibility probes, not a final
build or concurrent changes to Root files. Freeze the sandbox module interface before any
production-file handoff. Fresh independent reviewers are required by AGENTS.md.
