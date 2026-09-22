# Muta — ADTC 2026 Gate 2 Master Checklist

Deadline: **22 September 2026**. Confirm the exact cutoff time and timezone with the organizers.

This is the living source of truth for Gate 2. Update this file as evidence lands.

- `[x]` means the item is fully supported by the current repository or a completed verification.
- `[ ]` means the item is open or missing.
- `[ ] PARTIAL` means useful work exists, but the final requirement is not met.
- `[ ] BLOCKED` means owner confirmation, organizer clarification, or target hardware is required.
- Leave umbrella items open until every required sub-item is complete.
- Prefer committed, clean-clone-reproducible evidence over prose claims or mutable external links.
- Unlabeled tasks are organizer requirements or implementation needed to satisfy them. `[INTERNAL]` marks an extra safeguard we chose; `[CLARIFICATION]` marks an ambiguity to resolve.

Audit baseline: the tracked local and public `main` commit was `a3e5f085387678e2dafd61cc25349a47f9916d41`; the working tree also contained untracked Gate 2 drafts. Audited 13 September 2026.

## Current truth

| Area | Status | Repository evidence |
|---|---|---|
| Gate 1 core repository and root files | Complete | Public GitHub remote; `metadata.json`, `download_model.sh`, `REPORT.md`, and `model/` exist; the Gate 2 evidence bundle is under [`provenance/`](provenance/README.md) |
| Model weights excluded from Git | Complete | Ignore rules cover GGUF/bin/safetensors in `model/`; history contains no model weights |
| Final Gate 2 model | Not frozen | `NEWREPORT.md` selects Qwen2.5 1.5B, but every tracked release artifact still selects Qwen3.5 0.8B |
| Accuracy/usefulness evidence | Partial | Initial judge-prompt comparison exists; blind held-out and tutoring-quality gates remain open |
| Gate 2 provenance | Partial | [`provenance/`](provenance/README.md) now contains the adapter, scripts/configs, loss logs/curves, private-safe dataset proof, quantization receipts, and SHA256 ledger; the final release metadata/report still need synchronization |
| Benchmark reproducibility | Partial | Numbers and some settings exist; raw runs, pinned tools, exact target validation, thermal and crash evidence do not |
| Offline release | Partial | Offline inference is described, but no bundled/pinned runtime or clean offline rehearsal is stored |
| Eligibility attestations | Blocked | Personal, project-age, stage, residency, and funding facts require owner confirmation |
| Updated two-minute video | Missing from repository | An external/Devpost video may exist, but the repository contains no file or stable link and its status is unverified |

> **Do not cut over release files yet.** Qwen2.5 1.5B is the working candidate, not the settled submission model. Model selection must pass capability, adaptation, safety, provenance, and score gates first.

## 0. Rules, deadline, and clarifications

- [x] Record the Gate 2 deadline as 22 September 2026.
- [x] Treat the Gate 2 guideline as additional to the existing Challenge Rules and approved template.
- [x] Treat every Gate 2 item as mandatory unless the guideline explicitly calls it a recommendation.
- [ ] `[CLARIFICATION]` Confirm the submission cutoff time and timezone.
- [ ] `[CLARIFICATION]` Confirm the exact approved template version/revision to audit against.
- [ ] `[CLARIFICATION]` Ask what “The Git Commit SHA” in `metadata.json` must identify: submission commit, training commit, base-model revision, or another SHA.
- [ ] `[CLARIFICATION]` Ask whether a literal URL assigned to `MODEL_URL` is accepted, or whether the URL must appear directly in each `curl`/`wget` command.
- [x] `[CLARIFICATION]` Ask the organizers to resolve any other conflict between the Gate 2 guideline and the official rules before relying on an interpretation.
- [x] Save a non-sensitive summary of organizer questions and replies in the repository; keep personal or confidential correspondence private.

Organizer contact: `africadeeptechcommunity@gmail.com`. Send clarification questions **before** 22 September 2026.

## 1. Repository and template baseline

- [x] Use a public open-source GitHub repository: `iitimii/muta-adtc-2026` was anonymously reachable during this audit.
- [x] Include an open-source license: [LICENSE](LICENSE) is GPL-3.0.
- [x] Include [metadata.json](metadata.json).
- [x] Include executable [download_model.sh](download_model.sh).
- [x] Include [REPORT.md](REPORT.md).
- [x] Include `model/` through `model/.gitkeep`.
- [x] Ignore `model/*.gguf`, `model/*.bin`, and `model/*.safetensors` in [.gitignore](.gitignore).
- [x] Keep model weights out of the current tree and all existing Git history.
- [ ] Verify the whole repository against the exact approved Gate 2 template revision.
- [ ] Update and commit the Gate 2 repository content. `NEWREPORT.md` and this tracker are currently local working-tree additions until committed.
- [ ] `[INTERNAL]` Remove ignored workstation debris before release where practical, including `.DS_Store`.
- [ ] Make the final Git tree clean and push only this nested repository to its own remote.

## 2. Problem, scope, and model-choice gate

- [x] Define the problem: an offline adaptive maths and scientific-reasoning tutor for African learners. See [REPORT.md](REPORT.md#problem).
- [x] Explain the African connectivity, hardware, and educational context in the report.
- [ ] PARTIAL — Language scope is declared, but the report lacks substantive localization context and qualified validation.
- [ ] PARTIAL — A local, untracked draft records the Gate 1 result and judge-prompt re-analysis in [NEWREPORT.md](NEWREPORT.md), but it contains known contradictions and is absent from public `main`.
- [x] The local draft records a preliminary Qwen3.5-versus-Qwen2.5 comparison on the exact judge prompts and links to mutable external output evidence.
- [x] The local draft records preliminary speed and memory comparisons for both candidates.
- [ ] Correct the Qwen2.5 link in `NEWREPORT.md`; it currently points to the Qwen3.5 Hugging Face repository.
- [ ] Correct the summary in `NEWREPORT.md`: its own table does **not** show a Qwen2.5 win on the 4-TOPS prompt or bilingual photosynthesis prompt.
- [ ] Stop calling Qwen2.5 the final choice until every model gate below passes.
- [ ] Define a tutoring-accuracy rubric aligned with the judges: correctness, reasoning consistency, instruction following, clarity, pedagogy, localization, and safety—not generic ARC score alone.
- [ ] Build a versioned, uncontaminated evaluation set that includes:
  - [ ] The exact Gate 1 judge prompts.
  - [ ] Hidden-style variants that do not copy the two public metadata prompts.
  - [ ] Long-form maths derivation and misconception repair.
  - [ ] Scientific explanation and causal reasoning.
  - [ ] Numerical-unit and constraint-analysis problems.
  - [ ] Multiple-choice answer/calculation consistency.
  - [ ] Age-appropriate tutoring and follow-up questions.
  - [ ] Nigeria/West Africa context without sacrificing factual accuracy.
  - [ ] Every language retained in `language_scope`, reviewed by qualified speakers.
- [ ] Store prompts, outputs, inference settings, rubrics, grader decisions, and summary metrics in the repository.
- [ ] Run the same evaluation conditions across all serious base models, adapted models, and quantizations.
- [ ] Resolve current release blocker G2-01: training targets MCQs, not the judge’s tutoring rubric.
- [ ] Resolve G2-02: explanations can contradict the final answer.
- [ ] Resolve G2-03: Yorùbá is unreliable; validate it properly or remove the claim.
- [ ] Resolve G2-04: final artifact lacks a verified embedded Muta tutoring policy.
- [ ] Resolve G2-05: Q4_K_M is slow on the scalar profiler path; compare viable quantizations.
- [ ] Resolve G2-06: Qwen2.5 secondary blind held-out evaluation is missing.
- [ ] Resolve G2-07: training code, manifests, and clean-clone evidence are missing.
- [ ] Demonstrate that the candidate is genuinely useful and responsive across the stated domain.
- [ ] Demonstrate that scope/capability was not reduced mainly to inflate throughput or efficiency.
- [ ] `[INTERNAL]` Have at least two independent reviewers challenge the model for triviality, factual failure, prompt overfitting, and inconsistent tutoring behavior.
- [ ] Freeze the final model only after it passes capability, adaptation, provenance, runtime, safety, and weighted-score gates.

If two or more judges independently flag the model as too simplistic or trivial for its stated domain, the organizers may disqualify it under the anti-gaming rule.

## 3. Final runtime and artifact gate

- [x] The current Gate 1 release declares llama.cpp as its only runtime.
- [x] The current Gate 1 release declares a quantized GGUF artifact.
- [ ] Update all runtime evidence for the eventual Gate 2 model; Qwen2.5 is not wired into the tracked release.
- [ ] Verify the exact final GGUF loads and generates correctly through llama.cpp only.
- [ ] Pin the llama.cpp commit/release and record the build flags and executable source.
- [ ] Test on the ADTC standard class of machine: 8 GB RAM, 4 vCPU, Intel i5 10th–12th generation, integrated graphics, and no GPU acceleration.
- [ ] Verify the submitted llama.cpp/GGUF inference process fits within 8 GB at the maximum supported context/output length.
- [ ] `[INTERNAL]` Verify the complete packaged solution also fits with safe operating-system and runtime headroom.
- [ ] Verify inference works with network access disabled after the one-time fresh model download.
- [ ] Eliminate runtime downloads of weights, tokenizers, templates, packages, APIs, or other dependencies.
- [ ] `[INTERNAL]` Supply or reproducibly provision the required llama.cpp executable; the current quick start assumes `llama-cli` is already installed despite `binary_bundle` metadata.
- [ ] Run repeated, long-context, malformed-input, and sustained-use tests without OOM, illegal-instruction faults, sandbox crashes, or hangs.
- [ ] Verify package temperature stays at or below 85 °C and that sustained inference does not throttle.

Hard failures: any OOM or sandbox execution crash disqualifies the submission. Temperature above 85 °C or throttling incurs the stated 10-point penalty.

## 4. Model provenance and adaptation authenticity

- [x] A high-level Qwen3.5 training summary, dataset names/counts, and aggregate before/after scores exist as historical evidence.
- [ ] Decide and state the final adaptation path: LoRA, QLoRA, full fine-tune, or prompt/system-prompt-only. The evidence bundle records BF16 LoRA; the release files still need to be synchronized.
- [ ] Add a section literally titled `Model Provenance` to `REPORT.md`.
- [ ] State the exact final base-model name.
- [ ] State the exact public source repository.
- [ ] State the immutable base-model commit/revision.
- [ ] State the exact fine-tuning/adaptation method and material settings.
- [ ] If no weights were trained, state that explicitly and explain the prompt-only adaptation.
- [ ] For every training dataset, record its name, canonical source, immutable revision, approximate size, license, selection/filtering method, and split policy.
- [ ] Add at least two full same-prompt comparisons: unmodified base output beside final adapted-GGUF output under identical inference conditions.
- [ ] Show that changes are material and improve the stated tutoring task; aggregate benchmark gains alone are insufficient.
- [x] Create `provenance/`.
- [x] For LoRA/QLoRA, stage `provenance/adapter_model.safetensors`.
- [x] For LoRA/QLoRA, stage `provenance/adapter_config.json`.
- [x] Stage the exact training script/config in `provenance/scripts/` and `provenance/configs/`.
- [x] Stage step- and epoch-level loss/metric logs plus rendered curves in `provenance/logs/` and `provenance/loss-curves/`.
- [ ] Include the training dataset where size and license allow it; the mixed private corpus is intentionally not copied.
- [x] For the private corpus, provide **all** required substitutes: description, representative sample, link, source, size, and license in [`provenance/dataset/README.md`](provenance/dataset/README.md).
- [x] Record SHA-256 for the exact base-model file in [`provenance/SHA256SUMS`](provenance/SHA256SUMS).
- [x] Record SHA-256 for the adapter and each recorded full-run adapter in [`provenance/SHA256SUMS`](provenance/SHA256SUMS) / [`provenance/README.md`](provenance/README.md).
- [x] Record SHA-256 for the exact final quantized GGUF in [`provenance/SHA256SUMS`](provenance/SHA256SUMS) / [`provenance/README.md`](provenance/README.md).
- [x] Stage the exact merge, GGUF conversion, and quantization script/config in `provenance/scripts/` and `provenance/quantization/`.
- [x] Record tool versions/commits and reproduction commands in the quantization manifests and `provenance/README.md`.
- [x] Hosted-notebook link: not applicable; training/export used authenticated SSH/Slurm/Oracle infrastructure, as recorded in `provenance/README.md`.
- [ ] Ensure the training evidence, hashes, report, metadata, download URL, and downloaded bytes describe one identical final artifact.

The repository currently claims weight-level LoRA training, so the prompt-only exemption cannot be used unless that claim and the final adaptation path genuinely change.

If the final model is materially indistinguishable from its stock base without demonstrated fine-tuning or meaningful adaptation, Accuracy becomes 0 and disqualification remains possible.

## 5. Downloader and model integrity

- [x] `download_model.sh` is executable and passes `bash -n`.
- [ ] PARTIAL — The current Qwen3.5 URL is plainly readable, but the download command expands `$MODEL_URL`; obtain organizer confirmation or inline the literal before declaring §3.2 complete.
- [x] The current URL is not assembled from environment variables, computed logic, or an external lookup.
- [x] Use the guideline’s recommended Hugging Face hosting for the current artifact.
- [x] The current URL is public, ungated, needs no credentials, and resolved successfully during this audit.
- [x] The current destination path matches `_runtime.model_path` in `metadata.json`.
- [x] The script downloads to a `.partial` file before moving it to the final path.
- [x] The script has idempotent skip behavior when the final-named file already exists.
- [ ] Retarget the script only after the final Gate 2 GGUF is frozen and hosted.
- [ ] `[INTERNAL]` Use a durable URL pinned to an immutable Hugging Face revision instead of mutable `resolve/main`.
- [ ] Resolve the organizer’s interpretation of variable substitution; use a direct URL in `curl`/`wget` if needed.
- [ ] `[INTERNAL]` Verify SHA-256, file size, and GGUF magic after download and before accepting the artifact.
- [ ] `[INTERNAL]` Reject and replace a corrupt, truncated, stale, or wrong pre-existing final-named file instead of blindly skipping it.
- [ ] `[INTERNAL]` Test interruption/resume or safe restart without leaving a bad final artifact.
- [ ] Run the final downloader from a completely clean clone with no cache or credentials.
- [ ] Run it a second time and verify the expected idempotent result.
- [ ] `[INTERNAL]` Store the clean-download log and measured checksum as release evidence.

A URL that cannot be verified statically can trigger manual review, require resubmission, and block judging until a compliant script is supplied.

## 6. `metadata.json`

- [x] Parse as valid JSON.
- [x] Declare the problem domain as `math_scientific_reasoning`.
- [x] Contain exactly two public test prompts.
- [x] Keep both prompts inside the stated problem domain.
- [ ] Add the required Git Commit SHA using the organizer-confirmed field name and meaning.
- [ ] Update model name, runtime, quantization, parameter estimate, packaging, and runtime path for the final Gate 2 artifact.
- [ ] Ensure the runtime path exactly matches the downloader’s final destination.
- [ ] Validate every retained language claim; remove unsupported languages, especially Yorùbá unless retesting passes.
- [ ] Substantiate or revise `african_alpha_claim` and `budget_laptop_claim` using final evidence.
- [ ] Add/confirm the authoritative team roster and roles wherever the official schema requires them.
- [ ] Explain the legitimate ownership/role mapping between metadata handle `nelsonifechukwu`, GitHub repository owner `iitimii`, and Hugging Face owner `timiiowolabi`.
- [ ] Validate the completed file against the official template/schema with no stale values or placeholders.

Organizers will add two hidden prompts. The two public prompts must not become the training target or the whole evaluation suite.

## 7. `REPORT.md` and feedback resolution

Existing Gate 1 content already answers these template topics:

- [x] Problem being solved.
- [x] Design decisions.
- [x] Gate 1 model selection.
- [x] Gate 1 quantization rationale.
- [x] Alternatives evaluated.
- [x] Hardware constraints.
- [x] Connectivity constraints.
- [ ] PARTIAL — Training observations exist, but `REPORT.md` does not yet address data availability, rights, representativeness, contamination, and other data constraints as a coherent constraint section.
- [x] Observed inference speed.
- [x] Observed memory use.
- [x] Starter citations to the current base model, named datasets, and major tools.

Gate 2 finalization remains open:

- [ ] Merge the useful Gate 2 analysis from `NEWREPORT.md` into the final reporting structure and commit it.
- [ ] Make the final model decision consistent across `REPORT.md`, `NEWREPORT.md`, `README.md`, `metadata.json`, `download_model.sh`, provenance, and the hosted GGUF.
- [ ] Add the complete `Model Provenance` section and evidence links.
- [ ] Replace preliminary or stale benchmark claims with final reproducible measurements.
- [ ] Link raw benchmark runs, evaluation outputs, checksums, and configs stored in the repository.
- [ ] Explain accuracy in the judges’ tutoring sense rather than presenting ARC or final-answer accuracy as the whole criterion.
- [ ] Correct Qwen2.5 overstatements, mislabeled links, and the photosynthesis subject label.
- [ ] Reconcile the broad multilingual claim with the failed Yorùbá evidence.
- [ ] Reconcile claims of embedded tutoring behavior with the judge-observed exposed reasoning/no-final-answer failure.
- [ ] Reconcile the report’s 7 GB internal safety budget with the official 8 GB machine and clearly distinguish safety margin from rule limit.
- [ ] State temperature and throttling results from a sensor-capable sustained run.
- [ ] State limitations and remaining risks without disguising missing measurements as passes.
- [ ] Finish a concise feedback-resolution ledger: exact feedback → evidence → change → validation → status.
- [ ] Prepare reviewer clarification answers and a technical Q&A evidence pack if requested by the organizers.
- [ ] If submitting an optional one-page feedback response or updated benchmark report, keep it consistent with the main report and final artifact.
- [ ] End with one unambiguous, evidence-backed final decision.

## 8. Benchmark honesty, performance, efficiency, and safety

- [x] Record the existing Qwen3.5 participant-mode `adtc-profiler` speed and RSS result in `REPORT.md`.
- [x] Record preliminary Qwen2.5 scalar/vector speed and RSS results plus key GCP settings in `NEWREPORT.md`.
- [ ] Commit raw profiler output for every final number reported.
- [ ] Pin the official profiler source/version instead of installing a moving Git head.
- [ ] Record the final GGUF SHA, llama.cpp commit, compiler flags, CPU details, thread count, context, batch, sampling, seed, prompt length, output length, warmup, and command line.
- [ ] Measure prompt processing, time to first token, decode tokens/second, wall time, and peak whole-process-tree RSS.
- [ ] Run enough repetitions to report median and variance, not a cherry-picked run.
- [ ] Test representative short, long, and maximum-context workloads.
- [ ] Repeat on the ADTC standard class of Intel i5 laptop; GCP Xeon evidence is useful development data, not final target proof.
- [ ] Capture sustained package temperature and explicit throttling status on hardware that exposes the sensors.
- [ ] Run OOM, long-context, repeated-generation, and crash/exit-code safety tests.
- [ ] Run once with networking blocked to prove offline inference.
- [ ] Reproduce the final benchmark from a fresh clone and fresh model download.
- [ ] `[INTERNAL]` Have a second person independently reproduce the benchmark and explain any material discrepancy.
- [ ] Ensure every speed, memory, efficiency, temperature, and accuracy number in `REPORT.md` matches its retained raw evidence.
- [ ] Compute a **provisional** weighted estimate from comparable final runs using stated assumptions: `0.50 × Accuracy + 0.30 × Performance + 0.20 × Efficiency − thermal penalty`. Only organizers can produce the official score; add any organizer-awarded African-relevance bonus of up to 10 points separately.
- [ ] Choose the highest-scoring candidate only among models that already pass usefulness, authenticity, offline, provenance, and safety gates.
- [x] Treat semifinalist Performance/Efficiency mean, median, and mode as context—not official pass thresholds.

Semifinalist reference scores from the guideline:

| Criterion | Mean | Median | Mode |
|---|---:|---:|---:|
| Efficiency | 81.83 | 84.65 | 84.64 |
| Performance | 37.66 | 24.50 | 24.47 |

## 9. Originality, citations, licenses, and data rights

- [x] Cite the official template and retain its license.
- [x] Maintain a starter citation list for llama.cpp, the profiler/evaluation tools, base models, and named datasets in `README.md`.
- [ ] Audit every code fragment, report passage, model, library, dataset, external result, image, and other borrowed item for attribution.
- [ ] Confirm no code, report text, or other material was copied from another ADTC 2026 team.
- [ ] Clearly separate permitted official-template boilerplate from original project content.
- [ ] Add exact versions/commits, authors/canonical sources, and licenses for external tools and models.
- [ ] Resolve the missing/unclear OpenBookQA license and record all dataset licenses locally.
- [ ] Confirm that every model and dataset license permits the submitted training, adaptation, redistribution, and evidence use.
- [ ] Add required model-license notices and a clear modification statement for the derivative artifact.
- [ ] Do not ingest WAEC or other copyrighted exam material without documented rights, source, license/permission, and contamination controls.
- [ ] Add an explicit team declaration that the submission is original work and that all external material is cited.
- [ ] Run a final similarity/manual provenance review before submission.

## 10. Eligibility and team attestations

- [x] Record that this repository’s visible Git history begins on 15 June 2026; this is supporting context only, not proof of the wider project’s age.
- [ ] BLOCKED — Confirm every participant is above the legal age of majority in their country of residence.
- [ ] BLOCKED — Confirm every participant resides in an eligible African country.
- [ ] BLOCKED — Confirm the project is less than 12 months old under the organizer’s measurement date.
- [ ] BLOCKED — Confirm the project is at ideation, concept, or early proof-of-concept stage.
- [ ] BLOCKED — Confirm total external dilutive capital plus non-dilutive grants does not exceed USD 25,000.
- [ ] BLOCKED — Confirm the authoritative team roster, team-size compliance, and each person’s role.
- [ ] BLOCKED — Confirm all required participation agreements have been accepted.
- [ ] Gather truthful supporting records needed for a pre-Gate-2 or finalist background check; keep age, residency, identity, and funding records private and submit them only through organizer-approved channels.
- [ ] Ensure the repository, submission form, video, and spoken Q&A make identical eligibility claims.

Misrepresentation of age, residence, project stage/age, funding, or other eligibility facts can cause immediate disqualification and forfeiture of prizes.

## 11. African relevance and cross-disciplinary evidence

- [x] State an African education use case and offline/budget-laptop motivation.
- [x] Declare education as the load-bearing cross-disciplinary pairing in `metadata.json`.
- [ ] Add evidence of educator/learner co-design, curriculum alignment, or qualified pedagogical review.
- [ ] Test with representative African learning contexts rather than relying on place-name substitution.
- [ ] Validate claimed language/localization quality with qualified speakers and record the method.
- [ ] Remove any language or African-relevance claim the evidence does not support.
- [ ] Document how the final model remains scientifically accurate while localizing explanations.
- [ ] Make the case for the optional African-relevance bonus with evidence, not metadata flags alone.

## 12. Reviewer clarifications and technical Q&A

The competition’s public Gate 2 process also describes reviewer clarification responses and a scheduled 30-minute technical Q&A. Confirm the exact process with the organizers.

- [ ] `[CLARIFICATION]` Confirm whether the technical Q&A and any optional feedback/benchmark attachments apply to this submission and obtain the schedule.
- [ ] Collect the exact reviewer clarification prompts without paraphrasing them.
- [ ] Answer each clarification with a concise claim and a direct link to reproducible evidence.
- [ ] Keep a non-sensitive clarification-response ledger in the repository.
- [ ] Prepare a 30-minute Q&A pack covering model choice, data, adaptation, provenance, llama.cpp/GGUF conversion, accuracy failures, performance, memory, thermal behavior, offline operation, and limitations.
- [ ] Run an adversarial mock Q&A with someone who did not prepare the model.
- [ ] Attend the scheduled Q&A and retain the organizer-approved receipt/status; do not publish private correspondence without consent.
- [ ] Submit an optional one-page feedback response or benchmark update only if useful and fully consistent with the final artifact.

## 13. Updated video and presentation artifacts

- [ ] Create an updated video no longer than 2 minutes.
- [ ] Explain the problem and current solution.
- [ ] Explain the development journey, Gate 1 feedback, and what changed for Gate 2.
- [ ] Demonstrate the exact final model and current repository state.
- [ ] Show useful domain behavior, offline operation, and responsiveness without misleading edits.
- [ ] Ensure every model name, quantization, benchmark, capability, and limitation matches the final report and metadata.
- [ ] Add captions and make all key text readable within the time limit.
- [ ] Upload to the required destination and verify access without the owner account.
- [ ] Store a stable video link and duration in the repository/submission materials.
- [ ] Add any required updated screenshots or short clips.

## 14. Final release rehearsal and submission

- [ ] Freeze one final model, quantization, system prompt/chat template, runtime version, and inference configuration.
- [ ] Update all model references atomically across every submission artifact.
- [ ] Commit `NEWREPORT.md` or merge it into the chosen final report structure; do not leave Gate 2 evidence untracked.
- [ ] Commit the complete `provenance/` package and raw evaluation/benchmark evidence.
- [ ] Clone the public repository anonymously into a new directory.
- [ ] Confirm no model weights are present in the clone or Git history.
- [ ] Run `download_model.sh` fresh without credentials and verify the pinned SHA-256.
- [ ] Confirm the exact downloaded GGUF loads through the pinned llama.cpp runtime.
- [ ] Disable networking and run both public prompts plus hidden-style held-out prompts.
- [ ] Run the official profiler on the standard target configuration and compare every reported result.
- [ ] Complete sustained thermal, throttling, OOM, crash, and maximum-context checks.
- [ ] Confirm `metadata.json` has exactly two prompts and the organizer-confirmed Git SHA field.
- [ ] After the final release commit, populate and verify the required SHA using the organizer-confirmed method without creating a self-referential commit-hash loop.
- [ ] Confirm all public links work anonymously: GitHub, model, datasets, notebook, evidence, and video.
- [ ] Confirm `README.md`, `REPORT.md`, metadata, downloader, provenance, Hugging Face card, video, and submission form describe the same artifact.
- [ ] Confirm all required citations, licenses, originality statements, and eligibility attestations are present and true.
- [ ] Get an adversarial final review from someone who did not build the release.
- [ ] Ensure `git status` is clean and inspect the exact diff/commit to be submitted.
- [ ] Push the final commit to this nested repository’s own Git remote.
- [ ] Submit before the confirmed 22 September 2026 cutoff and archive the final commit SHA, model SHA-256, submission receipt, and video link.

## Open inconsistencies found by the audit

| ID | Inconsistency | Resolution required |
|---|---|---|
| C-01 | `NEWREPORT.md` selects Qwen2.5; `README.md`, `REPORT.md`, `metadata.json`, and `download_model.sh` still select Qwen3.5 | Keep Qwen2.5 labeled as candidate, then update every artifact together only after final selection |
| C-02 | The link labeled Qwen2.5 in `NEWREPORT.md` opens the Qwen3.5 Hugging Face repo | Replace with the exact candidate/final repository and immutable revision |
| C-03 | `NEWREPORT.md` prose claims Qwen2.5 wins the TOPS and photosynthesis tests, while its table reports both-model failures/ties | Rewrite the conclusion to match the recorded evidence |
| C-04 | `metadata.json`/README claim 28 languages, while Yorùbá testing is unreliable | Validate each retained language or narrow `language_scope` |
| C-05 | `metadata.json` says `binary_bundle`, but the repository contains no runtime binary or reproducible runtime bundle | Add the bundle/provisioning evidence or correct the packaging declaration |
| C-06 | README says the existing file was validated, but the downloader itself accepts any pre-existing final-named file without checking hash or GGUF magic | Add integrity validation and retain clean-run logs |
| C-07 | Current model URL uses mutable `resolve/main` | Pin the final URL to an immutable revision |
| C-08 | Training/provenance claims point partly to external Hugging Face manifests, but Gate 2 requires auditable repository evidence | Add the full local `provenance/` package |
| C-09 | Preliminary benchmark numbers have no committed raw profiler bundle | Retain raw outputs, exact commands/config, hashes, and target-hardware evidence |
| C-10 | Temperature was unavailable and Qwen2.5 physical-target validation remains pending | Run a sustained test on sensor-capable target hardware |

## Definition of done

Gate 2 is done only when every mandatory checkbox above is checked or is explicitly documented as not applicable under an organizer-confirmed rule. A prose claim, preliminary development run, mutable link, or result for a superseded model does not close a final-model requirement.
