# Training dataset evidence

The fine-tuning corpus is private and is not copied into the submission
repository. This file supplies the Gate 2 substitutes: description, source,
size, license/rights, selection policy, representative sample, and a recorded
link.

| Field | Recorded value |
|---|---|
| Artifact | `muta-stem-v2-sft-300k-quality-first-20260917-v1` |
| Size | 300,350 JSONL rows; 14 shards; 776,449,831 bytes |
| Manifest SHA256 | `93b7dbcbad72350e099d8951effcbc9a253693dc364b25ffc165102a6e844f4e` |
| Dataset fingerprint | `037edf28cccff62d90c23e2d6caf56b9998dea6928080f98af2a513f9f92910e` |
| Recorded private Hub mirror | [timiiowolabi/muta-stem-v2-sft-300k-quality-first-20260917-v1](https://huggingface.co/datasets/timiiowolabi/muta-stem-v2-sft-300k-quality-first-20260917-v1) |
| Access | Private/authenticated; link is provenance, not a redistribution grant |
| Development split | Separate 5,000-row manifest; not counted in the 300,350 training rows |

## Source and rights inventory

These are manifest records, not a new legal determination:

| Source | Rows | Recorded rights |
|---|---:|---|
| `muta_verified_stem_v2` | 280,000 | Muta-authored programmatic items; MIT |
| `deepmind_mathematics` | 20,000 | Apache-2.0; pinned generator revision `427f45075f84b8b9774950196ad63867ca20ffb3` |
| `waec_elearning` | 47 | WAEC copyright/all rights reserved; private owner attestation is not publisher permission |
| `cheetahwaec` | 303 | Reserved/third-party material; local owner attestation is not a publisher grant |

The corpus was deduplicated and quality-filtered before freezing. Candidate
answers were checked where applicable; malformed, contradictory, unsupported,
or unresolved examples were excluded. Training examples retain prompt and
assistant completion fields; the trainer masks prompt tokens and computes loss
on the assistant completion. The six-row projection in
[`training-sample6-20260919.json`](training-sample6-20260919.json) contains
only the Muta and Apache-2.0 sources, no WAEC/Cheetah rows, and no private
full-corpus text.

The sample is an inspection aid, not a statistically representative sample and
not an all-row correctness audit. Its SHA256 is
`ead432cf16ca03cc9d3c2b0ae08e3fa9c411a83443e9cca93a7a7320eca23c5d`.
