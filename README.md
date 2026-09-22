# Muta — ADTC 2026 Laptop LLM Submission

**Muta** is a personal educational companion that helps African students, from nursery school through tertiary education, **reason critically through mathematics and science problems**—fully offline on an **8 GB, CPU-only laptop**.

This repository is Muta's entry for the **Africa Deep Tech Challenge 2026** Laptop LLM track, domain **`math_scientific_reasoning`**. It follows the official [ADTC 2026 submission template](https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template).

- Technical report: [REPORT.md](REPORT.md)
- Extended experiment report: [muta-iq.vercel.app](https://muta-iq.vercel.app/)
- Model weights: [timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF/resolve/4fda6989e2820016256a4390e33aab2e745d5d34/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf)


---

## Submission at a glance

| Field | Value |
|---|---|
| Team ID | `muta` |
| Domain | `math_scientific_reasoning` |
| Submitter | Nelson Elijah · [@nelsonifechukwu](https://github.com/nelsonifechukwu) |
| Cross-disciplinary pairing | Education (load-bearing) |
| Model | `Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf` — fine-tuned [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) |
| Runtime | `llama.cpp` |
| Quantization | GGUF Q4_0 |
| Parameters | ~1.5B |
| File size | 830 MB |
| Packaging | `binary_bundle` |
| Language scope | `en` plus 27 further interface languages (see [metadata.json](metadata.json)) |
| African Use Case bonus | Claimed |
| Budget laptop profile | Claimed (4 vCPU · 8 GB RAM · integrated GPU · CPU-only inference) |

---

## Repository layout

```
muta-adtc-2026/
├── metadata.json          ← Team, model, and test-prompt metadata (read by the ADTC profiler)
├── download_model.sh      ← Fetches the GGUF from Hugging Face into model/ (idempotent, no credentials)
├── REPORT.md              ← Technical writeup: problem, design decisions, constraints, benchmarks
├── model/
│   └── Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf ← Downloaded by the script. Not committed.
├── .gitignore             ← Excludes model/*.gguf and local profiler output
└── LICENSE                ← GPL-3.0 (inherited from the template)
```

---

## Quick start

```bash
# 1. Download the weights (830 MB, public Hugging Face URL, safe to re-run)
bash download_model.sh

# 2. Try it with llama.cpp (CPU only, fully offline)
llama-cli -m model/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf -t 4 \
  -p "Multiple choice: A school in Lagos buys 6 boxes of chalk at ₦500 per box. What is the total cost? A. ₦1,000 B. ₦2,500 C. ₦3,000 D. ₦3,500. Answer with the correct option and one calculation."

# 3. Reproduce the profiler run (participant mode)
python3 -m pip install "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"
adtc-profiler run --submission . --mode participant --output submission.json
```

`download_model.sh` writes to exactly the path declared in `metadata.json` → `_runtime.model_path` (`model/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf`), skips the download if the file already exists, and needs only `curl` or `wget`.

**Integrity:** SHA-256 `552de22f7ea6f161a458985900e2c961d7578baa1ea9c23018ae27151623ff26`

---

## The model

- **Base:** `Qwen/Qwen2.5-1.5B-Instruct`, fine-tuned with BF16 LoRA (rank 16, 400 steps, lr 2e-5, seed 3407) on 15,355 multiple-choice maths/science questions drawn only from the *training* splits of ARC-Easy, ARC-Challenge, OpenBookQA, and QASC, de-duplicated against 8,477 held-out questions. The adapter is merged and exported as Q4_K_M GGUF.
- **Why this model:** It was the winner of a 15-candidate sweep across Qwen3.5-0.8B and Qwen2.5-1.5B on the challenge's combined accuracy/throughput/memory objective under the *scalar* CPU kernels the official profiler is built with. The full rationale, rejected alternatives, and lessons learned are in [REPORT.md](REPORT.md).

### Test prompts (`metadata.json` → `test_prompts`)

1. **tp_001** — *Multiple choice: A school in Lagos buys 6 boxes of chalk at ₦500 per box. What is the total cost? A. ₦1,000 B. ₦2,500 C. ₦3,000 D. ₦3,500. Answer with the correct option and one calculation.*
2. **tp_002** — *Multiple choice: Which process allows green plants to use sunlight to make food? A. Respiration B. Photosynthesis C. Evaporation D. Condensation. Answer with the correct option and one sentence of explanation.*

---

## Benchmarks

Development benchmarks (throughput, memory, accuracy) are in [REPORT.md](REPORT.md#benchmarks). Official scores are measured by the ADTC profiler on the standard evaluation machine.

---

## Open-source tools used

- [llama.cpp](https://github.com/ggerganov/llama.cpp) (GGUF conversion, Q4_0 quantization, `llama-bench`)
- [adtc-profiler](https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler)
- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
- [PyTorch](https://pytorch.org) 2.7 / CUDA 12.8 for LoRA fine-tuning
- [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) base weights
- training data from [AI2 ARC](https://huggingface.co/datasets/allenai/ai2_arc) (CC-BY-SA-4.0)
- [OpenBookQA](https://huggingface.co/datasets/allenai/openbookqa)
- [QASC](https://huggingface.co/datasets/allenai/qasc) (CC-BY-4.0)
- weights hosted on [Hugging Face](https://huggingface.co).

---

## ✅ Submission checklist

- [x] Repository is **public** on GitHub
- [x] `metadata.json` is fully filled in — no placeholder values remain
- [x] `metadata.json` contains exactly **2 test prompts** for `math_scientific_reasoning`
- [x] `download_model.sh` downloads the model to `model/` (verified from a clean directory: 513 MB, exit 0)
- [x] The downloaded file is a valid **GGUF** (`GGUF` magic, SHA-256 matches the Hugging Face artifact)
- [x] `model/*.gguf` is listed in `.gitignore` — no weight files are committed
- [x] `REPORT.md` contains the technical writeup
- [x] `bash download_model.sh` is idempotent — a second run skips the download and exits 0
- [x] The model runs entirely **offline** through `llama.cpp` — zero network calls during inference

## Rules compliance

1. **Public repository** — yes, and it stays public through evaluation.
2. **No model weights in git** — weights are fetched fresh by `download_model.sh`.
3. **100 % offline during evaluation** — the only network access is the one-time download before profiling.
4. **llama.cpp only** — GGUF Q4_0 weights; verified to load and generate on llama.cpp CPU builds.
5. **8 GB RAM limit** — peak RSS ≈ 0.67 GB, well inside the 7 GB efficiency budget.
6. **Two test prompts** — provided above.

---

## License

Repository contents are licensed under the [GNU GPL v3](LICENSE) (inherited from the ADTC template). The model weights are released under Apache-2.0 on their Hugging Face model card.
