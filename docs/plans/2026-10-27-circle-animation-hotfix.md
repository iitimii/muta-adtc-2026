# Radius-defined circle animation hotfix

## Failure

The accepted Animator source does not recognise a request such as `draw a circle with radius
5.6`. The browser-side deterministic planner raises `planner_required`, so the request falls
through to the local-model process-storyboard planner. That planner is deliberately limited to
inert prose states and cannot author geometry. A prose storyboard is therefore not an honest
rendering of the requested circle.

## Scope and invariant

Add one closed, deterministic geometry family for exactly one origin-independent circle with one
explicit positive radius. The numeric radius is data, never code. The renderer may scale the
drawing to the fixed frame, but the radius label and narration must preserve the exact validated
value. Accepted radii are decimal literals from 0.001 through 1000 with at most six fractional
digits, so the browser planner and Python emitter share one lossless display representation. A
circle request with no radius, multiple conflicting radii, zero, a negative value, arithmetic,
extra numeric constraints, a named unit, a centre/coordinate constraint, another geometry, or an
out-of-budget value must fail visibly rather than fall back to model-authored prose.

The project schema gains a discriminated `circle` scene whose data contains only:

- `radius`: a finite number from 0.001 through 1000;
- `phase`: either `construct` or `radius`.

The deterministic planner creates two scenes: construction of the circle, followed by a centre-to-
circumference radius line labelled with the requested value. The draft canvas and trusted Manim
emitter implement the same semantics. The local model remains unable to emit this scene kind.

## Verification

1. Add parser, validation, project, draft-canvas, source-emitter, and contract tests for radius 5.6.
2. Add rejection tests for missing, conflicting, zero, negative, over-precise, named-unit,
   centre/coordinate, mixed-geometry, unsupported-expression, and out-of-budget radii; exercise
   both accepted boundaries and exact six-decimal formatting.
3. Regenerate the OpenAPI contract and UI distribution; run the focused Node, Python, contract,
   and desktop package gates.
4. Render the exact prompt through the frozen packaged gateway and bundled Manim worker, inspect
   representative frames, then rebuild both macOS candidates from the reviewed immutable commit.
5. Keep native download acceptance explicitly pending until the user's existing app can be closed;
   do not touch the current app process or learner data.
