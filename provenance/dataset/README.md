# Dataset evidence

The current model was fine-tuned on the private `licensed-mcq` corpus. The
later 300,350-row corpus was a separate campaign and its models were not
promoted.

## Incumbent fine-tuning corpus

| Split | Rows | Sources | SHA-256 |
|---|---:|---|---|
| Train | 10,756 | ARC-Challenge 1,061; ARC-Easy 2,105; QASC 7,590 | `0d1b52db8dc0785fe8c0b62cbe374e79c35192b9ccd7fe86480c998808c3734c` |
| Validation | 566 | ARC-Challenge 48; ARC-Easy 120; QASC 398 | `fd48e23f20afb5ae8986730b19cb42523610cd0620e71021e9e2e8aa99dbf69b` |

The source revisions are ARC `210d026faf9955653af8916fad021475a3f00453`
and QASC `a34ba204eb9a33b919c10cc08f4f1c8dae5ec070`. The recorded licenses
are CC-BY-SA-4.0 for ARC and CC-BY-4.0 for QASC. Source validation and test
sets were excluded from training; the manifest also records overlap and
duplicate checks. The trainer masks prompt tokens and computes loss on the
assistant completion.

## Later full-data challenger corpus

This private artifact was used only for the three later, non-promoted
treatments:

| Field | Recorded value |
|---|---|
| Artifact | `muta-stem-v2-sft-300k-quality-first-20260917-v1` |
| Size | 300,350 JSONL rows; 14 shards; 776,449,831 bytes |
| Manifest SHA-256 | `93b7dbcbad72350e099d8951effcbc9a253693dc364b25ffc165102a6e844f4e` |
| Dataset fingerprint | `037edf28cccff62d90c23e2d6caf56b9998dea6928080f98af2a513f9f92910e` |
| Private mirror | [Hugging Face dataset](https://huggingface.co/datasets/timiiowolabi/muta-stem-v2-sft-300k-quality-first-20260917-v1) |
| Access | Private/authenticated; provenance link, not a redistribution grant |
| Development split | Separate 5,000-row manifest; not counted in the 300,350 rows |

Its recorded inventory is 280,000 Muta-authored MIT rows, 20,000 DeepMind
Mathematics Apache-2.0 rows, 47 WAEC restricted rows, and 303 CheetahWAEC
restricted/third-party rows. The restricted rows remain private; no publisher
permission is inferred. The corpus was deduplicated and quality-filtered;
malformed, contradictory, unsupported, and unresolved examples were excluded.
The public-safe six-row projection contains only the Muta and Apache-2.0
sources.

## Vocabulary-pruning corpus

The final `vocab32k` artifact used a 26,015-row, 4,051,489-token corpus to
choose the tokenizer keep-set. It combines the 10,756 incumbent training rows
with a separate 15,259-row licensed-hybrid corpus. This corpus was used for
token-retention analysis only; it was not an additional gradient-training run.
All observed tokens were retained (100% token-mass coverage). Its source
hashes and verification fields are in
[`../pruning/vocab32k-prune-receipt.json`](../pruning/vocab32k-prune-receipt.json).

`training-sample6-20260919.json` is a public-safe inspection sample from the
later challenger corpus, not a sample of the incumbent's 10,756 training
rows. It is not statistically representative and is not an all-row
rows. It is not statistically representative and is not an all-row
correctness audit. Its SHA-256 is
`ead432cf16ca03cc9d3c2b0ae08e3fa9c411a83443e9cca93a7a7320eca23c5d`.
