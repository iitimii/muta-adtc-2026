# Model Provenance

This directory is the Gate 2 proof bundle for the retained Muta incumbent. It
contains the final LoRA adapter, reproducible training/export source, exact
loss records, private-safe dataset evidence, and SHA256 receipts. Large GGUF
and training-corpus files are intentionally not copied into this repository.

## Final artifact and decision

The retained deployment artifact is the previously published Muta model:

| Item | Value |
|---|---|
| Model | `Muta-Tutor-Qwen2.5-1.5B-Q4_K_M.gguf` |
| Hugging Face model card | [timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF) |
| Evaluated incumbent path | `models/candidates/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M.gguf` (not copied here) |
| Evaluated incumbent GGUF SHA256 | `a750d00d458c6ab38925364ea1413db00648449180941e47025736d09922e1eb` |
| Current packaged candidate | `Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-qwen35-judge-hybrid.gguf`; same tensors, embedded template metadata only |
| Packaged candidate GGUF SHA256 | `ac512cc323a84546333baa256216fdf2035668f6ef092df1e2928bcc04339e3c` |
| Decision | Retain incumbent weights; the three 300,350-row challengers were not promoted |

The adapter files at the root of this directory are the exact LoRA adapter
used for the evaluated incumbent weights. The current packaged candidate
adds only the separately recorded judge-hybrid chat template; it does not
change tensors or claim a new fine-tuning run. The three later full-data treatments are
represented by their manifests, step logs, curves, and quantization manifests;
their non-promoted adapter weights remain in the private campaign archive.

## Base model and adaptation

| Item | Value |
|---|---|
| Base | `Qwen/Qwen2.5-1.5B-Instruct` |
| Immutable revision | `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` |
| Base license | Apache-2.0 |
| Base `model.safetensors` SHA256 | `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee` |
| Method | BF16 LoRA; not QLoRA and not a full-weight fine-tune |
| Adapter | `adapter_model.safetensors` + `adapter_config.json` |
| LoRA settings | rank 16, alpha 16, dropout 0, learning rate 2e-5, effective batch 16, max length 1,024, one epoch / 500 steps for the incumbent |
| Trainable modules | `q_proj`, `k_proj`, `v_proj`, `o_proj`, `up_proj`, `down_proj`, `gate_proj` |
| Loss | Assistant-completion loss; prompt tokens masked |

The incumbent proof adapter is 70 MB and is intentionally committed directly,
as allowed by the Gate 2 requirement. Its hashes are in `SHA256SUMS`.

## Training evidence

The exact source/configuration files are under `scripts/` and `configs/`.
The incumbent run is the historical 10,756-row LoRA adaptation. The later
full-data campaign used the same base family and three independently recorded
treatments, each with 300,350 rows, one epoch, 4,693 optimizer steps, and
minimum scheduled development loss selection:

| Treatment | Selected dev loss | Adapter SHA256 | Final Q4_K_M SHA256 |
|---|---:|---|---|
| Clean fresh LoRA, `r16/lr1e-5` | 0.01899942942 | `312523b2c0c74f246cfee5ce37cdcb69c9a4541e73b1fc8c80654b1ad3e2e33d` | `720fcc69f1ec1b83d601d7406756e44b0ae96b96ba626b97d5fb5ac874108530` |
| Fresh warm LoRA, `r16/lr5e-6` | 0.02247324772 | `5dd66ca8c79455b8ef3deb0219f6e91397f412a05fc4f3846bd194e0fea2e5c6` | `75f6a7563ede859aca6c6ddba1625068156e143858c7f841b27ff6208a2b84f3` |
| Warm-pilot continuation, `r16/lr5e-6` | 0.02292131260 | `51ead3a0792dec2c022d824ac5f738d3ebfb1c099d2d43a20869c12ed0c50b46` | `426640b0f4089d63ba8328c6d7fd2b201aeb7e92dd552492f1be594d9f385352` |

Loss and step evidence is preserved as both CSV and JSONL under `logs/`, with
rendered SVG/PNG curves under `loss-curves/`. These are development metrics,
not claims of independent tutoring-quality improvement. The final comparison
retained the incumbent because the challengers did not show a robust overall
advantage under the frozen held-out, STEM, judges, and practical tests.

## Dataset and rights

The full training artifact is private and is not included here. Its size,
manifest, source attribution, license records, selection policy, and a
six-row public-safe projection are documented in
[`dataset/README.md`](dataset/README.md) and
[`dataset/training-sample6-20260919.json`](dataset/training-sample6-20260919.json).
The full manifest SHA256 is
`93b7dbcbad72350e099d8951effcbc9a253693dc364b25ffc165102a6e844f4e` and the
dataset fingerprint is
`037edf28cccff62d90c23e2d6caf56b9998dea6928080f98af2a513f9f92910e`.

Recorded private Hub mirror (authenticated access; not a redistribution grant):
[muta-stem-v2-sft-300k-quality-first-20260917-v1](https://huggingface.co/datasets/timiiowolabi/muta-stem-v2-sft-300k-quality-first-20260917-v1).
The separate evaluation sets are private [Muta-STEM-100](https://huggingface.co/datasets/timiiowolabi/Muta-STEM-100)
and [Muta-Practical-2000](https://huggingface.co/datasets/timiiowolabi/Muta-Practical-2000).

The rights table is deliberately conservative: 280,000 Muta-authored rows are
recorded MIT; 20,000 DeepMind Mathematics rows are recorded Apache-2.0; 47
WAEC and 303 CheetahWAEC rows are recorded restricted/all-rights-reserved or
third-party material. No publisher permission or public redistribution right
is inferred for those restricted rows. The committed sample excludes all 350
restricted rows and the full corpus remains private.

## Merge, conversion, and quantization

The reproducible path is:

1. Load the pinned Qwen2.5 base and the LoRA adapter with the training source
   in `scripts/`.
2. Merge the adapter into BF16 weights with the recorded merge/export source.
3. Convert the merged Hugging Face directory to F16 GGUF with
   `convert_hf_to_gguf.py`.
4. Quantize F16 to `Q4_K_M` with `llama-quantize`.

The three exact command/manifest receipts are in
`quantization/*-quantization-manifest.json`; they record converter and
quantizer hashes, llama.cpp commit `60bccc3763395e01b039aa1ddeacc8cc0ea69f70`,
inputs, outputs, and logs. The local copy of the project merge script is
`scripts/merge_and_quantize.py`.

## Hosted notebook and reproducibility note

No hosted notebook was used. Training and export ran through an authenticated
SSH/GPU infrastructure; the hosted-notebook-link requirement is
therefore not applicable. Exact local scripts, manifests, logs, curves, and
hashes are included here. The private corpus and remote checkpoint tree are
not reproduced in this public submission repository.

See [`SHA256SUMS`](SHA256SUMS) for the machine-checkable receipt and
[`ARTIFACT-SHA256SUMS`](ARTIFACT-SHA256SUMS) for the external base/GGUF
receipts whose large binaries are not copied here.
