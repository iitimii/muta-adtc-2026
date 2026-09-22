# Model provenance

This directory records the training, export, evaluation, and packaging
evidence for the Muta Tutor Qwen2.5 model. Large model and dataset files are
kept in their named external locations; hashes make each input and output
checkable.

## Current artifact

The current model is the vocabulary-pruned Q4_K_M export:

| Item | Recorded value |
|---|---|
| File | `Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf` |
| Source | [Hugging Face artifact](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF/blob/main/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf) |
| Size | 830,115,168 bytes |
| SHA-256 | `3038036a93039e80d282581d451abfdf998cd2929d2d26720a2cc711bff33a94` |
| HF revision | `4fda6989e2820016256a4390e33aab2e745d5d34` |
| Operation | Post-export vocabulary pruning; no additional gradient update |

The unpruned Q4_K_M file is the source and the file used for the original
incumbent measurements:

| Item | Recorded value |
|---|---|
| File | `Muta-Tutor-Qwen2.5-1.5B-Q4_K_M.gguf` |
| SHA-256 | `a750d00d458c6ab38925364ea1413db00648449180941e47025736d09922e1eb` |
| Model card | [timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF) |

The old `qwen35-judge-hybrid` file is a separate template-packaging
experiment. It is not the current artifact and did not change model tensors.
The three 300,350-row training treatments are also historical challengers;
none was promoted.

## Fine-tuning lineage

The current artifact inherits the following fine-tuning run from the unpruned
source:

| Item | Value |
|---|---|
| Base | `Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` |
| Base license | Apache-2.0; `model.safetensors` SHA-256 `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee` |
| Method | BF16 LoRA; not QLoRA and not full-weight training |
| LoRA | rank 16, α 16, dropout 0; target projections `q/k/v/o/up/down/gate` |
| Optimisation | learning rate 2e-5; batch 4 × gradient accumulation 4 (effective batch 16); max length 1,024; seed 3407 |
| Run | 500 optimizer steps (about 0.744 epoch); A100-SXM4-40GB; CUDA 12.8; PyTorch 2.7.0 |
| Data | 10,756 training rows and 566 validation rows |
| Loss | Completion-only; prompt tokens masked |

The adapter and its configuration are `adapter_model.safetensors` and
`adapter_config.json`. The adapter represents the fine-tuning step; vocabulary
pruning is a later packaging transformation.

## Dataset used for the incumbent

The incumbent was trained on the private, license-recorded `licensed-mcq`
split, not on the later 300,350-row corpus. Its training manifest records:

- 10,756 training rows: 1,061 ARC-Challenge, 2,105 ARC-Easy, and 7,590 QASC;
- 566 validation rows: 48 ARC-Challenge, 120 ARC-Easy, and 398 QASC;
- train SHA-256 `0d1b52db8dc0785fe8c0b62cbe374e79c35192b9ccd7fe86480c998808c3734c`;
- validation SHA-256 `fd48e23f20afb5ae8986730b19cb42523610cd0620e71021e9e2e8aa99dbf69b`;
- source revisions ARC `210d026faf9955653af8916fad021475a3f00453` and QASC
  `a34ba204eb9a33b919c10cc08f4f1c8dae5ec070`;
- recorded licenses CC-BY-SA-4.0 (ARC) and CC-BY-4.0 (QASC).

The separate 300,350-row private corpus is documented in
[`dataset/README.md`](dataset/README.md) as a later, non-promoted campaign.
Its rights inventory is retained for audit, but it must not be described as
the training set for the current model.

The three later runs used one epoch and 4,693 optimizer steps each. Their
selected development losses were 0.01899942942 (fresh `r16/lr1e-5`),
0.02247324772 (fresh warm `r16/lr5e-6`), and 0.02292131260 (warm-pilot
continuation `r16/lr5e-6`). Their complete adapter and GGUF receipts remain in
`configs/`, `logs/`, and `quantization/`.

## Merge, quantization, and vocabulary pruning

The reproducible model path is:

1. Load the pinned Qwen2.5 base and the incumbent LoRA adapter.
2. Merge the adapter into BF16 weights.
3. Convert the merged weights to F16 GGUF.
4. Quantize the F16 GGUF to Q4_K_M.
5. Build a tokenizer keep-set and prune the vocabulary and its embedding/output
   rows to 32,000 entries.

The pruning receipt is
[`pruning/vocab32k-prune-receipt.json`](pruning/vocab32k-prune-receipt.json).
It records the source and output hashes, the Qwen tokenizer revision, and the
verification results. The vocabulary changed from 151,936 to 32,000 tokens;
merge rules changed from 151,387 to 31,722. The keep-set corpus contained
26,015 rows and 4,051,489 tokens (the 10,756 incumbent training rows plus a
separate 15,259-row licensed-hybrid corpus). All observed tokens were retained.
The artifact retained 338 tensors; non-vocabulary tensors and retained
vocabulary rows were byte-exact. This step did not retrain the model.

Converter and quantizer hashes, inputs, outputs, and logs are in
`quantization/*-quantization-manifest.json`. The llama.cpp revision used for
the recorded export is `60bccc3763395e01b039aa1ddeacc8cc0ea69f70`.

## Evaluation scope

The 77.8% ARC-Easy result and the scalar/vector totals in the model card are
measurements of the unpruned `a750…` source, not measurements of the current
`vocab32k` file. Results for the pruned artifact are recorded separately in
the Gate 2 report and must not be substituted into this training receipt.

## Evidence checklist

| Required evidence | Location | Status |
|---|---|---|
| LoRA adapter and configuration | `adapter_model.safetensors`, `adapter_config.json` | Present |
| Training script and run configuration | `scripts/train_lora.py`, `scripts/train_lora_round2.py`, `configs/*training-manifest.json` | Present |
| Training logs and metrics | `logs/`, `loss-curves/` | Present |
| Dataset description, sample, source, size, and rights | `dataset/README.md`, `dataset/training-sample6-20260919.json` | Present; full corpus remains private |
| Base, adapter, and final GGUF checksums | `ARTIFACT-SHA256SUMS`, `SHA256SUMS`, `pruning/vocab32k-prune-receipt.json` | Present |
| Merge and quantization procedure | `scripts/merge_and_quantize.py`, `quantization/` | Present |
| Hosted notebook link | No hosted notebook was used; training ran through authenticated SSH/GPU infrastructure | Not applicable |

## Reproducibility

No hosted notebook was used. Training and export ran through authenticated
SSH/GPU infrastructure. Exact local scripts, manifests, logs, curves, and
hashes are included here. See [`SHA256SUMS`](SHA256SUMS) for files in this
bundle and [`ARTIFACT-SHA256SUMS`](ARTIFACT-SHA256SUMS) for external binaries.
