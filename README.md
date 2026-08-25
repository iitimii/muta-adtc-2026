# Muta — ADTC 2026 Laptop LLM Submission

**Muta** is an offline tutor that teaches African students to *reason through* mathematics and science problems — working, principle, and self-check — on an ordinary 8 GB, CPU-only laptop with no internet connection.

This repository is Muta's entry for the **Africa Deep Tech Challenge 2026** Laptop LLM track, domain **`math_scientific_reasoning`**. It follows the official [ADTC 2026 submission template](https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template).

- 📄 Technical report: [REPORT.md](REPORT.md) · extended experiment report: [muta-iq.vercel.app](https://muta-iq.vercel.app/)
- 🤗 Model weights: [timiiowolabi/Muta-Tutor-Qwen3.5-0.8B-ADTC-GGUF](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen3.5-0.8B-ADTC-GGUF)
- 🏁 Challenge: [adtc-2026.devpost.com](https://adtc-2026.devpost.com)

---

## Submission at a glance

| Field | Value |
|---|---|
| Team ID | `muta` |
| Domain | `math_scientific_reasoning` |
| Submitter | Nelson Elijah · [@nelsonifechukwu](https://github.com/nelsonifechukwu) |
| Cross-disciplinary pairing | Education (load-bearing) |
| Model | `Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf` — fine-tuned [Qwen/Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B) |
| Runtime | `llama.cpp` |
| Quantization | GGUF Q4_0 |
| Parameters | ~800M (772,845,888 in the GGUF header) |
| File size | 513 MB |
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
│   └── Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf   ← Downloaded by the script. Not committed.
├── .gitignore             ← Excludes model/*.gguf and local profiler output
└── LICENSE                ← GPL-3.0 (inherited from the template)
```

---

## Quick start

```bash
# 1. Download the weights (513 MB, public Hugging Face URL, safe to re-run)
bash download_model.sh

# 2. Try it with llama.cpp (CPU only, fully offline)
llama-cli -m model/Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf -t 4 \
  -p "A market woman in Onitsha buys 50 tubers of yam at 300 naira each. On the way to the market, 5 tubers spoil and cannot be sold. What price must she sell each of the remaining tubers for, so that she still makes a 20% profit on everything she spent? Show your working and check your answer."

# 3. Reproduce the profiler run (participant mode)
python3 -m pip install "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"
adtc-profiler run --submission . --mode participant --output submission.json
```

`download_model.sh` writes to exactly the path declared in `metadata.json` → `_runtime.model_path` (`model/Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf`), skips the download if the file already exists, and needs only `curl` or `wget`.

**Integrity:** SHA-256 `552de22f7ea6f161a458985900e2c961d7578baa1ea9c23018ae27151623ff26`

---

## The model

- **Base:** `Qwen/Qwen3.5-0.8B`, fine-tuned with BF16 LoRA (rank 16, 400 steps, lr 2e-5, seed 3407) on 15,355 multiple-choice maths/science questions drawn only from the *training* splits of ARC-Easy, ARC-Challenge, OpenBookQA and QASC, de-duplicated against 8,477 held-out questions. The adapter is merged and exported as Q4_0 GGUF.
- **Why this model:** it was the winner of a 15-candidate sweep across Qwen3.5-0.8B and Qwen2.5-1.5B on the challenge's combined accuracy / throughput / memory objective under the *scalar* CPU kernels the official profiler is built with. Full rationale, alternatives rejected, and lessons learned are in [REPORT.md](REPORT.md).
- **Provenance:** the Hugging Face repo ships the training manifest, dataset manifest (with source licences and revisions), artifact hashes, and the full fine-tuning summary alongside the weights.

### Test prompts (`metadata.json` → `test_prompts`)

1. **tp_001** — *A market woman in Onitsha buys 50 tubers of yam at 300 naira each. On the way to the market, 5 tubers spoil and cannot be sold. What price must she sell each of the remaining tubers for, so that she still makes a 20% profit on everything she spent? Show your working and check your answer.*
2. **tp_002** — *A student writes: "A heavier ball falls faster than a lighter one, because gravity pulls harder on it." Say exactly what is correct and what is mistaken in that reasoning, explain what actually determines how fast each ball speeds up, and describe one simple observation the student could make to test it.*

---

## Benchmarks

Development benchmarks (throughput, memory, accuracy) are in [REPORT.md](REPORT.md#benchmarks). Official scores are measured by the ADTC profiler on the standard evaluation machine.

---

## Open-source tools used

[llama.cpp](https://github.com/ggerganov/llama.cpp) (GGUF conversion, Q4_0 quantization, `llama-bench`) · [adtc-profiler](https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler) with [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) · [PyTorch](https://pytorch.org) 2.7 / CUDA 12.8 for LoRA fine-tuning · [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B) base weights · training data from [AI2 ARC](https://huggingface.co/datasets/allenai/ai2_arc) (CC-BY-SA-4.0), [OpenBookQA](https://huggingface.co/datasets/allenai/openbookqa), and [QASC](https://huggingface.co/datasets/allenai/qasc) (CC-BY-4.0) · weights hosted on [Hugging Face](https://huggingface.co).

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
