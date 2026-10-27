# Reference-aligned Animation Studio

## Learner-facing change

The reference video was reviewed visually and with its full audio transcript (see the reference
inventory in the implementation plan). The candidate's separate Canvas storyboard and Manim
player did not match that workflow. Studio now has one stage and one normal path:

1. Describe a lesson and choose the learner level.
2. Generate plans, validates and renders the trusted Manim video locally.
3. Watch with native video controls and use one Download video action.

Lesson title, sequence and project import are under closed Lesson options. Examples are under a
closed disclosure. Editing, JSON, transcript and Manim source/export are under one closed tools
panel. The wider Studio chooser is hidden while authoring; Back restores it. No branding tokens,
frameworks, dependencies or executable-model-code permissions were added.

Only unavailable/failed/cancelled rendering or explicit scene edits use the clearly labelled
draft in that same stage. The Canvas and MP4 transports are never visible together. Render output
is revoked on revision changes; a cancelled or old response cannot replace a newer project.
Source requests are lazy and revision checked. Both generation and rendering are cancellable.
Playback never starts automatically, including under reduced motion.

## Division correction

The user's division screenshot contained a false remainder and an unrelated wave scene.
Whole-number division/equal sharing now uses a parameterised checked scene family, not prose
planner arithmetic. The dividend and divisor determine the object count, quotient, remainder and
captions. A quantity-free mathematical division request is explicitly labelled as an example.
Incomplete quantities, compound arithmetic, conflicting relationships, zero divisors, decimals
and out-of-budget dimensions are rejected instead of truncated or silently substituted.
Biological cell division is not mistaken for mathematical division.

The backend process planner refuses explicit mathematical division/equal-sharing briefs rather
than inventing arithmetic when the checked Studio path cannot represent them. This does not
certify unrelated model-written explanations; the review-before-sharing notice remains.

## Source acceptance

- Complete Python suite: exit 0; see the preserved final test log.
- Complete Node suite: exit 0, including real-controller lifecycle tests.
- Fresh separate read-only adversarial review: no remaining actionable P0/P1/P2 findings;
  45 focused Node and 117 focused Python tests pass. Independent browser/Pydantic enumeration of
  2,533 boundary combinations found the same 1,003 legal sharing combinations, with no mismatch.
- Added actual-controller tests for one visible MP4, no autoplay, unavailable/failure retry,
  cancellation/late completion, edit invalidation, lazy/stale source, concept-only novel planning,
  repeated graph regeneration and corrupt imports during rendering.
- Added shared schema/renderer tests and small-width object containment checks (375, 640, 960).
- Generated OpenAPI and localisation inventory refreshed; authored/built UI parity checked.
- Touched-file Ruff and whitespace checks pass.
- Division boundaries use a consuming prefix rather than regular-expression lookbehind, so the
  draft/source fallback does not require newer WebKit than the supported older macOS shell.

## Real UI and media evidence

An isolated source gateway used the existing bundled Manim worker, without changing the running
native app or unrelated inference process. Actual Muta UI generation of `Share 14 blocks among
4 friends` went directly to a single paused MP4. DOM inspection confirmed one visible video,
zero visible Canvas players and a closed tools panel. Playback and Download video worked.

Downloaded output: 280,946 bytes, H.264, 1280 × 720, 30 fps, 9.630990 seconds.
SHA-256: `f3d541b45dffa278c5493f85f17744a8beba74f5cda9706423fc9bc9aefc8150`.
The decoded final frame visibly retains four groups of three, two unshared objects, and the
check `14 = 4 × 3 + 2`, instead of fading to an empty title. A separate count-scene regression
prevents the not-yet-introduced equation from flashing during transition.

Real source UI was checked in dark and light appearances, at 375-pixel portrait and 812-pixel
landscape widths, with reduced motion. No horizontal document overflow or duplicate player was
observed. Existing colour tokens and 44-pixel controls remain. The exact Unicode sine prompt was
also exercised through the same direct-to-video flow. Candidate Mac packaging and final native
GUI verification are separate gates; source acceptance does not imply those are complete.

Temporary evidence is in `/tmp/muta-animator-minimal.oFyCzH/qa/` and full suite logs in
`/tmp/muta-animator-review.xnVeRK/minimal-*-final.log`; preserve these under package evidence
before disposable build cleanup. No source push, release upload, other-OS build or deployment
is authorised by this candidate gate.
