# Muta ADTC 2026 — Combined Technical Report

**Domain:** Mathematics and Scientific Reasoning

<details>
<summary><strong>Gate 1 — Problem, Design Decisions, Results & Re-analysis</strong></summary>

## Technical Report for Muta: Offline Adaptive STEM Tutor for African Students

View our comprehensive report [here](https://muta-iq.vercel.app/).

**Team ID:** muta

**Domain:** `math_scientific_reasoning`

**Model:** Fine-tuned Qwen3.5 0.8B Q4_0

**Runtime:** llama.cpp / GGUF

**Deployment target:** CPU-only consumer laptops

> **Submitted model:** `Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf` — fine-tuned Qwen3.5 0.8B, GGUF Q4_0

> (SHA-256 `552de22f7ea6f161a458985900e2c961d7578baa1ea9c23018ae27151623ff26`).

> The Qwen2.5 1.5B Q4_K_M model discussed below was our strongest **alternative** and was **not** submitted.

---

## Problem

Across many African classrooms, the problem is not simply access to information.

A student may have a textbook and still not have someone available to patiently explain the exact concept they do not understand. A teacher may be responsible for too many students to provide truly individual attention. Even where AI tools are available, they commonly depend on continuous internet access, cloud inference, and hardware or subscriptions that cannot be assumed for every learner.

Muta addresses this problem by working toward a **truly personal educational AI tutor that can run locally on the laptop**.

Our target user is primarily a secondary-school student learning Mathematics and Science who needs more than a system that returns an answer. Muta is intended to explain concepts, reason through problems, respond to follow-up questions, and adapt the educational interaction around the learner.

Since Muta runs locally, it means that a student can continue learning when the internet is unavailable, unreliable, or expensive. It removes the requirement for a dedicated GPU or continuous cloud inference. It reduces the marginal cost of each additional question and provides a path to deploying AI tutoring in schools and homes where connectivity cannot be treated as always available infrastructure.

This is particularly important to our broader vision for Muta: **Muta is not the underlying language model.** The model is a replaceable intelligence engine inside a larger educational system. Our long-term goal is for Muta to become the educational intelligence layer that connects the student, teacher, parent, institution, and curriculum, while accumulating learning context over time.

---

## Design Decisions

### Base model

Our submitted model is a **fine-tuned Qwen3.5 0.8B**, deployed as GGUF using **Q4_0 quantization**. Our strongest alternative was a fine-tuned Qwen2.5 1.5B Instruct at Q4_K_M; the rest of this section explains why the smaller model won.

We did not begin by assuming that this would be the final model.

We first [studied](https://muta-iq.vercel.app/) the relationship between model size, reasoning quality, memory consumption, and generation speed. Larger models predictably gave better reasoning performance, but their additional accuracy had to justify the corresponding increase in RAM and weight bandwidth on a low-resource CPU.

We subsequently widened the search across several architectures and sizes, including:

* Qwen3 and Qwen3.5 models from 0.8B to 4B

* Qwen2 and Qwen2.5 at 1.5B and 3B

* Llama 3.2 at 1B and 3B

* Gemma 2 2B

* Phi-4 Mini

* Orca Mini

* specialist mathematical fine-tunes

* an 8B ternary BitCPM4 candidate

The goal was not to select the model with the highest raw accuracy. We selected based on the competition's combined accuracy, performance, and memory objectives.

Our 8B BitCPM4 TQ2_0 experiment illustrates this clearly. It achieved the highest raw ARC-Easy result we measured during an earlier search, but its scalar decoding throughput was only approximately 0.81 tok/s. Even after vector acceleration substantially raised it, it still failed to beat the smaller dense Qwen candidates on the combined objective.

The most accurate model was therefore not necessarily the best model to deploy.

### Quantization

We selected **Q4_0** for the submitted Qwen3.5 0.8B model. (Q4_K_M was used for the Qwen2.5 1.5B alternative.)

One of our most important findings was that quantization cannot be considered independently of the CPU kernel that executes it.

Initially, Q4_0 appeared substantially better than several theoretically more sophisticated formats because the supplied scalar profiler had an optimized SIMD implementation for Q4_0 while K-quants fell back to slower generic code.

We therefore built a second, portable CPU configuration with:

`AVX=ON`

`AVX2=ON`

`FMA=ON`

`F16C=ON`

`NATIVE=OFF`

`AVX-512=OFF`

Once AVX2/FMA/F16C were available, the ranking changed. Q4_K_M could use an efficient vectorized path, making it substantially more attractive.

For Qwen2.5 1.5B, the vectorized Q4_K_M model gave us the best measured balance among the larger matched candidate set between reasoning accuracy, throughput, and memory.

This taught us an important lesson:

> **The quantization format is also a kernel decision. Fewer bits do not automatically mean faster inference.**

### Fine-tuning

After narrowing the architecture search, we fine-tuned both finalists rather than relying only on post-training quantization.

We trained **15 candidates** across Qwen3.5 0.8B and Qwen2.5 1.5B, varying:

* LoRA rank

* BF16 LoRA versus QLoRA

* dataset mixture

* learning rate

* training duration

We discovered that much of the original training mixture emphasized long-worked solutions and tutoring dialogue, while the profiler's accuracy evaluation used short-answer continuations. We also discovered a tokenization-level issue: the training data builder had omitted the leading space between `Answer:` and the expected continuation, changing the BPE token sequence used during training.

We rebuilt the data pipeline, corrected the continuation format, used verified answers, checked for held-out contamination, and aligned the training objective much more closely with the evaluation task.

The resulting metric-aligned fine-tuning improved:

* **Qwen3.5 0.8B:** 55.2% → **70.2%**

* **Qwen2.5 1.5B:** 74.4% → **77.8%**

on 500-item evaluations.

Importantly, these accuracy gains did not significantly increase model memory usage or reduce throughput.

### Behaviour embedded in the GGUF

The competition evaluates the GGUF without the complete Muta application surrounding it.

That created another problem: a good base model is not automatically a good tutor.

We therefore developed a mechanism for embedding Muta's tutoring behaviour directly into the model metadata and chat template so that the educational behaviour can survive outside the full application.

Our packaged model policy includes:

* a Muta tutoring persona

* a defined chat template

* direct-answer behaviour

* controlled sampling defaults

* suppression of unnecessary hidden reasoning when the calling runtime does not provide its own setting

This became important during live tests. Unrestricted reasoning could consume the entire response budget internally before returning a useful answer to the learner. The model, therefore, needs to be optimized not only for benchmark accuracy, but for actual interactive tutoring behavior.

---

## Alternatives Considered

We did not arrive at the current model through a single quantization experiment. Several optimization paths were investigated and either adopted, rejected, or retained only for the full Muta product.

### Qwen3.5 0.8B Q4_0 — submitted

This is our **scalar-profiler leader** and the model we submitted.

After fine-tuning, it achieved:

* **70.2% ARC-Easy**, n=500

* **13.60 tok/s**

* approximately **691 MiB estimated profiler RSS**

* **80.3664** fixed-15 scalar score

The official ADTC profiler builds llama.cpp with `GGML_AVX`, `AVX2`, `FMA` and `F16C` all **off** (see its Dockerfile), i.e. the scalar kernel path — the configuration in which this candidate leads on the combined objective.

### Qwen2.5 1.5B Q4_K_M — not submitted

This is our **vector-configuration leader** where AVX2/FMA/F16C are available.

After fine-tuning, it achieved:

* **77.8% ARC-Easy**, n=500

* **17.44 tok/s**

* approximately **1,706 MiB estimated profiler RSS**

* **84.1387** fixed-15 vector score

It wins the combined objective only when AVX2 vector kernels are available. Under the scalar kernels the official profiler uses, it drops to \~5.6 tok/s and loses to the 0.8B model, so it was not submitted.

### Math-Expert 0.6B

A specialist Qwen3-based mathematical fine-tune initially produced an attractive small-sample result and very high throughput under the vector runtime.

However, once the finalists were evaluated on a larger, matched 500-item sample, its estimated accuracy dropped sufficiently that it no longer led the combined objective.

This was an important reminder not to optimize against a small benchmark sample.

### BitCPM4 8B TQ2_0

We explored a very different strategy: use many more parameters but aggressively compress them with ternary weights.

The candidate achieved very strong reasoning accuracy, but its computational representation was poorly matched to the scalar CPU kernel. The resulting inference speed made it uncompetitive despite its accuracy.

We therefore rejected the assumption that extreme compression automatically produces an efficient CPU model.

### Larger 2B–4B models

Several larger models produced stronger raw reasoning results, but they moved substantially more weight data for every generated token and consumed more memory.

On this target, additional parameters were only useful when the extra accuracy outweighed both memory and throughput penalties.

Many did not.

### Mixed-precision quantization

We tested combinations in which sensitive tensors or final layers were stored at higher precision.

The additional precision increased file size and/or used slower kernel paths without recovering enough accuracy to justify the cost.

These variants were rejected.

### Weight and layer pruning

Removing a Qwen transformer layer improved decode speed modestly but cost enough ARC-Easy accuracy to lose on the combined score.

Unstructured sparsity was also unattractive because dense GGUF storage and the evaluated kernels did not provide a practical memory or inference advantage for zero-valued weights.

### Vocabulary pruning

For the BitCPM branch, vocabulary pruning was useful. We reduced its vocabulary from 73,448 to 44,416 tokens, saving approximately 164 MB while preserving checked English tokenization.

The technique was not safely transferable to every finalist and therefore did not determine the final Qwen candidate.

### Weight streaming

We implemented a custom residency-window streaming engine in Muta's own runtime.

On a historical 2.2 GB BitCPM test, fully streaming the model reduced peak RSS to approximately **279 MiB**, demonstrating that substantial model memory reductions are possible when weights are paged from storage.

However, this requires a modified runtime.

The competition evaluates our GGUF using the organizer's llama.cpp runtime, so this optimization cannot be applied within the submitted model file.

It remains a **Muta product optimization**, not a competition-model optimization.

---

## Constraints

Muta was designed around the competition's low-resource target rather than around a development workstation.

### Hardware constraints

The target environment is an ordinary consumer laptop:

* Intel Core i5-class CPU

* 10th–12th generation competition target

* integrated graphics

* approximately 8 GB system RAM

* **7 GB hard competition RAM ceiling**

* no discrete GPU

* CPU-only inference

Our model must therefore perform useful mathematical and scientific reasoning while sharing memory with the operating system and inference runtime.

### Runtime constraints

The submitted model must run using:

* **llama.cpp**

* **GGUF weights**

This distinction strongly affected our work.

Some of the most useful optimizations we developed for Muta—such as custom weight streaming, runtime repacking policy, thread configuration, KV-cache configuration, and mmap behaviour—belong to the inference engine rather than the GGUF.

They improve the full product, but they cannot legitimately be counted toward the model-only competition result because the organizer supplies the runtime.

We therefore maintained a strict boundary between:

**GGUF-contained optimizations**

and

**Muta runtime optimizations.**

### CPU portability

We explicitly keep **AVX-512 disabled** to avoid producing a binary that may execute illegal instructions on eligible consumer CPUs.

Our portable vector experiments use AVX2, FMA, and F16C while keeping architecture-specific `NATIVE` optimizations disabled.

### Connectivity constraints

Muta is designed to remain useful without internet connectivity.

The model therefore cannot depend on a remote inference API for its core tutoring behaviour. Once installed, the student must be able to ask questions and receive useful responses entirely on-device.

Connectivity is an enhancement to Muta, not a prerequisite for learning.

### Power constraints

A low-resource device is not only constrained by RAM.

CPU inference also consumes battery power and produces heat. In the complete Muta application, this led us to implement power-aware behavior such as **Eco Mode**, where automatic reasoning and response length can be bounded when the machine is running on battery.

Those product-level controls are separate from the submitted GGUF, but the same concern influenced our preference for smaller models that achieve strong reasoning performance without requiring several billion additional parameters.

---

## Benchmarks

Our benchmark evidence is deliberately separated by CPU configuration because we discovered that CPU instruction-set support can change the model ranking. The official profiler uses the scalar configuration.

### Submitted model — Qwen3.5 0.8B Q4_0

Development sweep (scalar build, matched 500-item evaluation):

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Metric</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Value</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Model</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Fine-tuned Qwen3.5 0.8B</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Quantization</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Q4_0</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>ARC-Easy accuracy</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>70.2%</strong>, n=500</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Generation speed</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>13.60 tok/s</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Estimated profiler RSS</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>691 MiB</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Fixed-15 scalar total</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>80.3664</strong></td>
  </tr>
</table>

</div>

Official-profiler run on the submitted GGUF (`adtc-profiler 0.1.0`, participant mode, llama-bench 512 prompt / 128 generated tokens):

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Metric</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Value</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Machine</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Intel Xeon @ 2.80 GHz (4 vCPU), 7.8 GB RAM, no GPU, Ubuntu 22.04.5</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Generation speed</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>12.98 tok/s</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Time to first token</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">≈ 15.0 s (512-token prompt; profiler approximation from prompt-processing rate)</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Peak RSS</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>674 MB</strong> (steady state 629 MB)</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>ARC-Easy acc_norm</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>0.72</strong> (n=50)</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>CPU utilisation p99</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">54.2%</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Temperature</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not exposed by the benchmark host</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Thermal throttling</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not flagged</td>
  </tr>
</table>

</div>


### Alternative (vector build, not submitted) — Qwen2.5 1.5B Q4_K_M

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Metric</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Value</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Model</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Fine-tuned Qwen2.5 1.5B</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Quantization</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Q4_K_M</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Runtime</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">llama.cpp</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Benchmark configuration</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Portable vector CPU build</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>CPU features</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">AVX2, FMA, F16C enabled; AVX-512 disabled</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Workload</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">512 prompt tokens / 128 generated tokens</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Evaluation threads</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">2 physical-core threads</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>ARC-Easy accuracy</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>77.8%</strong>, n=500</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Generation speed</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>17.44 tok/s</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Estimated profiler RSS</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>1,706 MiB</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Fixed-15 estimated total</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>84.1387</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Time to first token</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Final tuned candidate re-measurement pending</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Temperature</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not exposed by current GCP benchmark host</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Thermal throttling</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Physical-target validation pending</td>
  </tr>
</table>

</div>

These are **self-reported development measurements**, not official ADTC evaluation results.

Q4_K_M performs strongly when the appropriate AVX2 vector kernels are available, while Q4_0 remains much more competitive under the scalar configuration the official profiler uses.

---

## What the Optimization Process Taught Us

The most important lesson from this project is that optimizing an offline language model is not the same as finding the smallest GGUF.

The effective system is:

**model architecture × training × quantization × CPU kernel × memory behaviour × evaluation objective**

Changing any one of those variables can change which model wins.

We observed models that were:

* more accurate but too slow,

* smaller but less accurate,

* theoretically better quantized but slower because of kernel dispatch,

* dramatically faster under AVX2 without any change to their weights,

* improved in training loss without improving the actual target metric,

* and excellent in the complete Muta runtime, but impossible to benefit from in a GGUF-only submission.

The current candidate is therefore the result of an empirical optimization campaign rather than a single model download and quantization pass.

---

## Final Decision

At the time of this report, our measured leaders are:

**Scalar configuration:**

Fine-tuned **Qwen3.5 0.8B Q4_0**

**AVX2 vector configuration:**

Fine-tuned **Qwen2.5 1.5B Q4_K_M**

**Submitted: fine-tuned Qwen3.5 0.8B Q4_0 (`Muta-Tutor-Qwen3.5-0.8B-Q4_0.gguf`).** It leads under the scalar CPU configuration the official profiler uses, runs at ≈0.67 GB peak RSS, and is the model referenced by `metadata.json` and `download_model.sh`. Qwen2.5 1.5B Q4_K_M remains our vector-build alternative for the full Muta product.

---

## Gate 1 Results & Re-analysis

**Domain:** Mathematics and Scientific Reasoning  

## Gate 1 result

<div align="center">

<table style="border-collapse: collapse; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 16px;">Accuracy and Quality</th>
    <th style="border: 1px solid #888; padding: 8px 16px;">Performance</th>
    <th style="border: 1px solid #888; padding: 8px 16px;">Efficiency</th>
    <th style="border: 1px solid #888; padding: 8px 16px;">Total</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 16px;">39.20</td>
    <td style="border: 1px solid #888; padding: 8px 16px;">56.00</td>
    <td style="border: 1px solid #888; padding: 8px 16px;">90.65</td>
    <td style="border: 1px solid #888; padding: 8px 16px;"><strong>54.53</strong></td>
  </tr>
</table>

</div>

Given our hardwork in Gate 1, our submission successfully passed the initial screening (a good total score comprising accuracy, performance and efficiency). However the feedback from the judges revealed the cardinal tradeoff that we made: We had traded accuracy to maximize performance and efficiency, and as they pointed out, this isn't ideal for an educational product.

We thought the same before submission and had tried to bypass this obvious outlook by fine-tuning on a specific dataset that comprises ARC-easy, ARC-challenge, etc, but when the judges tested our model on a broader analysis that shadows critical thinking, our model sometimes mingled correct-looking responses with bad arithmetic, units, science, analogies, final answers. Again, this is not ideal as students cannot reliably study with it.

<span id="our-def">As</span> we progress, **our definition of accuracy is the critical thinking ability of our model**, which is the heart of STEM and the core reason why Muta exists. A good and adaptive tutor must finish, follow instructions, stay internally consistent, correct misconceptions safely, and interact in the user's language correctly, and this we will acheive at the bleeding edge of the best performance and efficiency score that is possible.

## Gate 1 Re-analysis 

When we made our initial submission, we indicated a strong alternative model, our finetuned Muta tutor—[Qwen2.5 1.5B Q4_K_M model](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF)—which we didn't submit because of its file size that hampers efficiency and performance score a bit. We had tested this model and highlighted its outstanding STEM capabilities [here](https://muta-iq.vercel.app/#:~:text=Vector%20total-,Qwen2.5%201.5B%20Q4_K_M,-Vector%20leader). 

To validate that, we decided to compare it against our submitted [Qwen3.5 0.8B fine-tuned model](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen3.5-0.8B-ADTC-GGUF) on the judges prompt analysis in Gate 1. As expected, Qwen2.5 was clearly better on the mastery of ARC-easy and Ordinary differential equations (ODE) (Maths), DNA explanation (Biology), Photosynthesis (Chemistry) and CPU Tops calculation (Physics).

### Evidence


<div align="center">

<table style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Judges Analysis</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Qwen3.5 0.8B</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Qwen2.5 1.5B</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Gate 2 Reading</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.f50vhjz921kz">ARC-Easy-500</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">70.2%</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">77.8%</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.f50vhjz921kz">Qwen2.5 is stronger on this narrow benchmark</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.p1wl4oc1nxb7">Mastery ODE</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Wrong</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct solution and limit</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.p1wl4oc1nxb7">Qwen2.5 win</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.shd8xeougz9j">4 TOPS / 200 ms parameter limit</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Treated TOPS as clock rate and returned a token count as model size</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Treated tokens as operations or bytes and invented a size</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.shd8xeougz9j">Both fail: only an 8 × 10¹¹-operation budget is known; parameter count needs output length and operations per parameter per token</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.va7qh7hsv2y4">Chalk MCQ</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Total 8/8 per format; option also correct in 6/8 ASCII and 1/8 ₦ runs</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.va7qh7hsv2y4">Qwen2.5 knows the arithmetic but option selection is format-sensitive</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.9brehxatmqw6">Photosynthesis MCQ</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.9brehxatmqw6">Tie</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.or47dl8xexmx">Average speed</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct result; weak teaching</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct result; clearer method</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.or47dl8xexmx">Qwen2.5 win</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.8xd6cqt7cwqr">DNA relationships</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Unsafe factual claims</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Scientific core correct; analogy still weak</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.8xd6cqt7cwqr">Qwen2.5 win</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.ck1e4l5o3dc9">Yorùbá photosynthesis</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Incoherent</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Copied English or tone-marked but incoherent text; required content omitted</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.ck1e4l5o3dc9">Both fail</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.xfkvetauw8au">Two Sigma modelling</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Weak</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Same prompt ranged from R = kP to reversed limit behavior</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.xfkvetauw8au">Qwen2.5 is unstable</a></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.7mk5wvxye5vz">Rice profit</a></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Wrong</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Correct revenue/profit; wrong or incomplete percentage check</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><a href="https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?tab=t.0#heading=h.7mk5wvxye5vz">Qwen2.5 improves the work but still fails</a></td>
  </tr>
</table>

</div>



### Model breakdown during reasoning 

One judge observed that [an incorrect early arithmetic step sometimes propagated through the rest of the solution, alongside mixed currency symbols and inconsistencies in the verification section](https://docs.google.com/document/d/1AhLOdbIL8mfeW9avBal0IyTrSKot96niZk3xrBmDtn8/edit?disco=AAACHEgfFjM). We note that as a limitation of the submitted Qwen3.5-0.8B configuration.

This is because under the ADTC 8 GB RAM constraint, the context window must be restricted to control KV-cache memory usage. For complex questions, Qwen3.5 generates long intermediate reasoning traces which creates additional pressure on context, latency, and inference resources, while also increasing the likelihood that an early reasoning error will propagate.
<div align="center">

<table style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Qwen3.5-0.8B</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Qwen2.5-1.5B</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Reasoning path:</strong><br>
      <code>Question → variable-length reasoning → answer</code>
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Response path:</strong><br>
      <code>Question → controlled response</code>
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Reasoning length can vary from a few to hundreds/thousands of intermediate tokens
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Muta can enforce: <code>3 steps → calculate → verify → final answer</code>
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Higher and less predictable context/RAM usage
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      More efficient use of limited context
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Variable latency and token usage
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      More predictable inference and capped generation
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>0.8B parameters</strong>
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>~1.54B parameters</strong> (which implies more
      <a href="https://dengking.github.io/machine-learning/Theory/Deep-learning/Guide/Model-capacity/Model-capacity/">
        representational capacity
      </a>)
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Early errors can propagate:<br>
      <code>wrong step → later steps inherit error → wrong answer</code>
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Short, structured responses are easier to verify and correct
    </td>
  </tr>
</table>

</div>

The controlled responses of Qwen 2.5 1.5b on the other hand gives us a tighter control over context usage and latency while still providing clear step-by-step tutoring. It also allows the application layer to add safeguards such as explicit verification prompts, deterministic formatting, and calculator-based checks. Given Muta's structured tutoring workload, Qwen2.5-1.5B is a more predictable deployment choice within the ADTC 8 GB hardware constraint.

### Performance cost

As we prioritize the stronger model for the next accuracy work, it's expected that there is a performance drop because of the ~2x increase in file size as we switch from the Qwen 3.5 0.8B model to the Qwen2.5 1.5b model. The table below shows this tradeoff. 

<div align="center">

<table style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Scalar tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Scalar RSS</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Scalar total</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">AVX2 tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">AVX2 RSS</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">AVX2 total</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">
      Fine-tuned Qwen3.5 0.8B Q4_0
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;">13.60</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">691 MiB</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">80.3664</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">27.69</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">969 MiB</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">82.3962</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">
      Fine-tuned Qwen2.5 1.5B Q4_K_M
    </td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>5.63</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>1,117 MiB</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>67.0475</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">17.44</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1,706 MiB</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">84.1387</td>
  </tr>
</table>

</div>

Qwen2.5's median decode rate was 15.89 tok/s on AVX2 and 4.01 tok/s on scalar, with a ten-prompt run taking 1,166 seconds.


### Reproduction

To reproduce the above evidenced comparison, we decided to share our configurations that produced the evidence.
<div align="center">

<table style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Setting</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Value</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Host</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Ubuntu OS on GCP, 2 physical cores / 4 logical CPUs, 7.8 GiB RAM
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Runtime</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      llama.cpp b10175, CPU-only, 2 threads, 4,096-token context
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Test sampling</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Temperature 0, top-p 1, seed 3407
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Tutor policy</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Prompt used by <code>opt/scripts/finalize_model.sh</code>
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Qwen3.5 template</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Direct answer with empty thinking block
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Qwen2.5 template</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      Plain ChatML; no Qwen3 thinking tokens
    </td>
  </tr>
</table>

</div>

### Decision moving forward

<p style="color: orange">Given the analysis above, Qwen3.5-0.8B is not sufficiently reliable for the educational product we want to build. Fine-tuning may improve its behaviour on specific tasks, but it cannot fundamentally overcome the capacity limitations of such a small base model. Its speed, efficiency, and performance are impressive for its size; however, correctness and reliability matter more when a student is learning. For that reason, we will not use Qwen3.5-0.8B going forward.</p>

</details>

<details>
<summary><strong>Gate 2 — Exploration and Improving Accuracy</strong></summary>

## Gate 2: Exploration

We could easily proceed with Muta’s alternative model, our fine-tuned **[Qwen2.5-1.5B Q4_K_M tutor](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF)**, as it has shown great promise in the results above. However, we believe our analysis in Gate 1 did not include a thorough comparison of the strongest models available within the ~1.5B parameter range (~1B ≤ parameter size ≤ ~2B) that we are now exploring. Therefore, before committing to Qwen2.5-1.5B, we first conduct broader research into the best small models in this range with strong mathematical and scientific reasoning capabilities. A summary of the results are presented below:


<table style="border-collapse: collapse; width: 100%; text-align: left;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Size</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Math</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Science / STEM</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Our Assessment</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>MiniCPM5-2B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">2.52B total</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Capability-first candidate</strong> for combined mathematics and science.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>LFM2.5-2.6B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">2.6B class</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Promising capability–efficiency balance</strong> for local STEM tutoring.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>LFM2.5-1.2B-Thinking</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1.17B</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Priority speed-focused candidate</strong> with low memory requirements; weaker knowledge-intensive science.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Qwen3.5-2B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">2B language model</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Broad-STEM reference</strong> for comparing capability and efficiency.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>MiniCPM5-1B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1.08B total</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Compact mathematics alternative</strong>, with less convincing scientific reasoning.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>VibeThinker-1.5B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1.5B class</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Unproven</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Mathematics specialist</strong>; lengthy reasoning may increase response time.
    </td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Falcon-H1-Tiny-R-0.6B</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.6B</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">⭐⭐⭐⭐⭐</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Unproven</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">
      <strong>Ultrasmall mathematics specialist</strong>; tiny weights do not guarantee short answers.
    </td>
  </tr>
</table>

Stars represent qualitative assessments from the review, not standardised benchmark scores. “Unproven” indicates insufficient broad-science evidence.

A more comprehensive analysis, including benchmarks, quantization options, deployment caveats, and sources, can be found [here](https://muta-iq.vercel.app/#gate-2-overview).

### Model evaluation and ranking

Building on the shortlist above, we evaluated the qualifying models using a test suite comprising **100 custom STEM prompts** that we developed which can be found [here](https://huggingface.co/datasets/timiiowolabi/Muta-STEM-100), **500 ARC-Easy questions, and all Gate 1 prompts**. For each model, we measured **accuracy, generation speed (tokens/s), and resource efficiency**, then ranked the models by their suitability for Muta’s **8 GB RAM, CPU-only deployment**. A summary of the results is presented below:

<div style="overflow-x: auto; width: 100%;">

<table style="border-collapse: collapse; width: 100%; text-align: left;">

  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">ARC-Easy<br>Accuracy</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Full STEM<br>Passes (/100)</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Core-Correct<br>(/100)</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Gate 1<br>Score (/100)</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Completed<br>Answers</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Scalar Score<br>Proxy</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">AVX2 Score<br>Proxy</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Selection<br>Outcome</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Muta Tutor Qwen2.5 1.5B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>77.8%</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">57</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">80</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>47/100</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>10/10</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">67.0617</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>84.1383</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Advance as the development control</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>MiniCPM5-2B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">67.6%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">17</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">35</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">20/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">2/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">57.1241</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">71.3754</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>LFM2.5-2.6B QAD-Q4_0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">45.4%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">60</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">75</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">20/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">2/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">50.2891</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">55.8421</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>LFM2.5-1.2B-Thinking Q4_0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">46.0%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">41</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">53</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">25/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">2/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">68.3197</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">69.2310</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Qwen3.5-2B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">65.2%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>77</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>95</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">20/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">2/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">57.4536</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">70.9515</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Retain as the STEM challenger</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Qwen3-1.7B Q4_0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">65.2%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">59</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">81</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">28/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">3/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">64.8317</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">77.1843</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>MiniCPM5-1B pure Q4_0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">55.8%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">6</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">16</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">24/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">3/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;"><strong>75.8713</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">74.8643</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>VibeThinker-1.5B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">39.2%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">16</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">22</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">28/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">2/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">47.6639</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">64.4903</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>Falcon-H1-Tiny-R-0.6B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">30.4%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Not completed</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Not completed</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Failed</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">0/5</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">61.1957</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">63.0630</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Runtime failure; unranked</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>OpenReasoning Nemotron-1.5B Q4_K_M</strong></td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">53.6%</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">35</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">60</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">0/100</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">0/10</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">55.2269</td>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: center;">72.0394</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not selected</td>
  </tr>

</table>

</div>

**How to read the columns:**

* **ARC-Easy Accuracy:** Percentage correct across 500 ARC-Easy questions.
* **Full STEM Passes (/100):** Responses meeting the full STEM rubric: correct answer, coherent working, no contradiction, and required explanation or format.
* **Core-Correct (/100):** Responses with the correct central answer, even if they failed the stricter full-pass criteria.
* **Gate 1 Score (/100):** Reviewed score across the ten reproduced Gate 1 prompts.
* **Completed Answers:** Prompts that produced a usable final answer. Falcon completed only five prompts, hence `0/5`.
* **Scalar Score Proxy:** Estimated competition score using scalar CPU throughput, RSS, and ARC-Easy accuracy.
* **AVX2 Score Proxy:** Equivalent estimate using AVX2-enabled measurements. Both proxies exclude target-laptop temperature and are therefore not official profiler scores.
* **Selection Outcome:** Final model-selection decision based on the combined evaluation.

Our Muta Tutor Qwen2.5-1.5B delivered the strongest overall balance: the highest ARC-Easy accuracy, highest Gate 1 score, complete answer delivery, and highest AVX2 score proxy. <span style="color: orange">Therefore, our fine-tuned Muta Tutor Qwen2.5-1.5B is the model selected for further development.</span>

A comprehensive account of the methodology, experimental setup, complete candidate field, retained responses, and detailed results is available in the [full report](https://muta-iq.vercel.app/#gate-2-audit).

## Gate 2: Improving Accuracy

As we previously highlighted <a href="#our-def">here</a>, at Muta, it is paramount that a model built for education demonstrates strong critical thinking and, consequently, high accuracy.

Our selected **Muta Tutor Qwen2.5-1.5B** achieves **47% on the judges’ Gate 1 evaluation**, an improvement over the **39.20%** previously recorded. While this is a meaningful gain, it is still not good enough for us. We believe our users may one day become experts in their fields, and that journey should begin with the strongest foundation possible.

Therefore, we conducted further analysis to identify a more accurate Muta Tutor.

### Dataset and Training Strategy

To develop a more accurate Muta, we decided to **distill, fine-tune, and quantize** our model: distill stronger answers from a larger **GPT-5.6 Sol** model, fine-tune for our desired tutoring behaviour, and quantize so the final model remains deployable on the target laptop.

We first curated a **[2,500,350-row STEM dataset](https://huggingface.co/datasets/timiiowolabi/muta_tutor_full_dataset)**, spanning mathematics, physics, chemistry, biology, and integrated science, then augmented it with WAEC/WASSCE material to better reflect the African educational context. And we distilled and verified all their answers with the larger GPT-5.6 Sol model.

### Full dataset

<div style="display: flex; gap: 16px; align-items: flex-start; width: 100%; overflow-x: auto;">

<table style="border-collapse: collapse; flex: 1; min-width: 280px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Source Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Source</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Muta verified STEM v2</td><td style="border: 1px solid #888; padding: 8px 12px;">1,085,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">DeepMind Mathematics</td><td style="border: 1px solid #888; padding: 8px 12px;">1,052,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">TemplateGSM</td><td style="border: 1px solid #888; padding: 8px 12px;">350,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">GSM8K</td><td style="border: 1px solid #888; padding: 8px 12px;">6,500</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">QASC</td><td style="border: 1px solid #888; padding: 8px 12px;">6,500</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">WAEC questions</td><td style="border: 1px solid #888; padding: 8px 12px;">350</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;"><strong>Total</strong></td><td style="border: 1px solid #888; padding: 8px 12px;"><strong>2,500,350</strong></td></tr>
</table>

<table style="border-collapse: collapse; flex: 1; min-width: 240px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Subject Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Subject</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Mathematics</td><td style="border: 1px solid #888; padding: 8px 12px;">1,680,061</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Physics</td><td style="border: 1px solid #888; padding: 8px 12px;">292,980</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Chemistry</td><td style="border: 1px solid #888; padding: 8px 12px;">227,856</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Biology</td><td style="border: 1px solid #888; padding: 8px 12px;">227,853</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Integrated science</td><td style="border: 1px solid #888; padding: 8px 12px;">71,600</td></tr>
</table>

<table style="border-collapse: collapse; flex: 1; min-width: 260px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Tutoring-Style Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Tutoring style</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Concise answer</td><td style="border: 1px solid #888; padding: 8px 12px;">1,167,001</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Worked solution</td><td style="border: 1px solid #888; padding: 8px 12px;">790,846</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Exam marking scheme</td><td style="border: 1px solid #888; padding: 8px 12px;">217,002</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Misconception correction</td><td style="border: 1px solid #888; padding: 8px 12px;">217,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Socratic hint</td><td style="border: 1px solid #888; padding: 8px 12px;">108,501</td></tr>
</table>

</div>


### Why we did not fine-tune on all ~2.5M rows

Training on the entire dataset would not necessarily produce a better Muta:

1. **Diminishing returns:** More data is not automatically better. Large amounts of repetitive or narrow supervised data can add little improvement while increasing compute and the risk of over-specialization or catastrophic forgetting of useful base-model behaviour.
2. **Unsafe rows:** The 363,000 TemplateGSM, GSM8K, and QASC rows were excluded from training because we found systematic defects in our review.
3. **Dataset imbalance:** Mathematics heavily dominates the full dataset and could dilute representation from physics, chemistry, biology, integrated science, and tutoring behaviour.
4. **Repetition:** Many rows are parameterized variants of the same task families. More variants increase training cost much faster than they add new reasoning signal.
5. **Evaluation leakage:** Template holdouts and canonical near-duplicates must remain outside the training set.


We therefore created a deliberately balanced **[300,350-row training sample](https://huggingface.co/datasets/timiiowolabi/muta_tutor_quality_sample)**, maintaining a strong representation across the STEM subjects and tutoring styles.

### Selected training sample
<div style="display: flex; gap: 16px; align-items: flex-start; width: 100%; overflow-x: auto;">

<table style="border-collapse: collapse; flex: 1; min-width: 280px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Source Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Source</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Muta verified STEM v2</td><td style="border: 1px solid #888; padding: 8px 12px;">280,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">DeepMind Mathematics</td><td style="border: 1px solid #888; padding: 8px 12px;">20,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Private WAEC e-learning review</td><td style="border: 1px solid #888; padding: 8px 12px;">47</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Private Cheetah WAEC review</td><td style="border: 1px solid #888; padding: 8px 12px;">303</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;"><strong>Total</strong></td><td style="border: 1px solid #888; padding: 8px 12px;"><strong>300,350</strong></td></tr>
</table>

<table style="border-collapse: collapse; flex: 1; min-width: 240px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Subject Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Subject</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Mathematics</td><td style="border: 1px solid #888; padding: 8px 12px;">150,311</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Physics</td><td style="border: 1px solid #888; padding: 8px 12px;">54,030</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Chemistry</td><td style="border: 1px solid #888; padding: 8px 12px;">42,006</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Biology</td><td style="border: 1px solid #888; padding: 8px 12px;">42,003</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Integrated science</td><td style="border: 1px solid #888; padding: 8px 12px;">12,000</td></tr>
</table>

<table style="border-collapse: collapse; flex: 1; min-width: 260px;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 12px; text-align: center;">Tutoring-Style Distribution</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Tutoring style</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Rows</th>
  </tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Worked solution</td><td style="border: 1px solid #888; padding: 8px 12px;">120,350</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Exam marking scheme</td><td style="border: 1px solid #888; padding: 8px 12px;">60,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Misconception correction</td><td style="border: 1px solid #888; padding: 8px 12px;">60,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Socratic hint</td><td style="border: 1px solid #888; padding: 8px 12px;">30,000</td></tr>
  <tr><td style="border: 1px solid #888; padding: 8px 12px;">Concise answer</td><td style="border: 1px solid #888; padding: 8px 12px;">30,000</td></tr>
</table>

</div>

The **300,350-row sample** is therefore our controlled first fine-tuning dataset: all **25 subject × tutoring-style combinations** are represented, only verified sources are used, and each selected row contributes a canonical training task.

### Fine-tuning


#### 1. Baseline and method

The Gate 1 Muta model was produced with BF16 LoRA:

<div style="display: flex; gap: 20px; align-items: flex-start; justify-content: center; flex-wrap: wrap; width: 100%;">

  <!-- Main Fine-Tuning Settings -->
  <table style="border-collapse: collapse; text-align: center;">
    <tr>
      <th colspan="2" style="border: 1px solid #888; padding: 8px 16px;">Fine-Tuning Settings</th>
    </tr>
    <tr>
      <th style="border: 1px solid #888; padding: 8px 16px;">Item</th>
      <th style="border: 1px solid #888; padding: 8px 16px;">Setting</th>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Base</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">Qwen2.5-1.5B-Instruct</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Adapter</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">LoRA, rank 16</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Learning rate</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">2 × 10⁻⁵</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Steps</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">500</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Loss</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">Assistant-only</td>
    </tr>
  </table>

  <!-- Shared Pilot Settings -->
  <table style="border-collapse: collapse; text-align: center;">
    <tr>
      <th colspan="2" style="border: 1px solid #888; padding: 8px 16px;">Shared Pilot Settings</th>
    </tr>
    <tr>
      <th style="border: 1px solid #888; padding: 8px 16px;">Item</th>
      <th style="border: 1px solid #888; padding: 8px 16px;">Setting</th>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Effective batch size</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">64</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Max sequence length</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">512 tokens</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>LoRA α</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">Rank-specific</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Dropout</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">0</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Seed</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">3407</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Schedule</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">Warmup + cosine</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>LoRA targets</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">Attention + MLP projections</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Training rows</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">20,000</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Validation rows</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">5,000</td>
    </tr>
    <tr>
      <td style="border: 1px solid #888; padding: 8px 16px;"><strong>Optimizer steps</strong></td>
      <td style="border: 1px solid #888; padding: 8px 16px;">313</td>
    </tr>
  </table>

</div>

For the subsequent experiements, we kept BF16 LoRA because it uses the available GPU memory efficiently and finetunes faster rather than QLoRA and we varied the Learning rate and the rank.

#### 2. 20K hyperparameter pilots

To identify the most promising hyperparameter direction before full-scale fine-tuning, we tested several configurations on a **20,000-row subset**. In total, we completed **eight BF16 LoRA pilot experiments** across runs initialized from the base Qwen2.5-1.5B weights and the existing Muta Tutor checkpoint.

The values on the left are **final validation losses**. Lower indicates better optimization on the validation set, but does **not** directly represent accuracy or tutoring quality. We therefore evaluated each pilot on downstream STEM and judges' prompts, shown on the right.

<table width="100%" style="border-collapse: collapse;">
<tr>

<td width="43%" valign="top" style="padding-right: 10px; border: none;">

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="5" style="border: 1px solid #888; padding: 8px 10px;">Pilot Validation Loss</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Pilot</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Init.</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Rank</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">LR</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Dev Loss</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>warm-r16-lr2e5</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">2 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>0.217060</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r32-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">32</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.339828</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">clean-r32-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Qwen</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">32</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.346829</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r16-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.578009</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">clean-r16-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Qwen</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.593257</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r32-lr5e6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">32</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5 × 10⁻⁶</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.685911</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r16-lr5e6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5 × 10⁻⁶</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.961763</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r8-lr5e6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">8</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5 × 10⁻⁶</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1.151685</td>
  </tr>
</table>

</td>

<td width="57%" valign="top" style="padding-left: 10px; border: none;">

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="5" style="border: 1px solid #888; padding: 8px 10px;">Downstream Evaluation</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">MC Correct<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Written Correct<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Written Complete<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Judges<br>/96</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Previous Muta</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">38</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">28</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">53</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">clean-r16-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>42</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">28</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">34</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">clean-r32-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">23</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">18</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r8-lr5e6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">40</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">32</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">18</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>warm-r16-lr5e6</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">37</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>33</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>23</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>56</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r16-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">37</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">31</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>23</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r16-lr2e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">26</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">13</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">54</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r32-lr5e6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">32</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">19</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">44</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">warm-r32-lr1e5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">34</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">26</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">14</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">41</td>
  </tr>
</table>

<br>

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="2" style="border: 1px solid #888; padding: 8px 10px;">
      <a href="https://huggingface.co/datasets/timiiowolabi/Muta-STEM-100">Muta STEM-100</a>
    </th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Evaluation</th>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Previous Muta</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>63/100</strong></td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Unmodified Qwen</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">62/100</td>
  </tr>
  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Best-scoring new pilot</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">60/100</td>
  </tr>
</table>

</td>

</tr>
</table>

The results show why **validation loss alone was not sufficient for model selection**. Although `warm-r16-lr2e5` achieved the lowest validation loss (**0.217060**), its downstream performance did not translate into the strongest tutoring model.

The best new pilot was **`warm-r16-lr5e6`**, achieving the strongest written performance and **56/96 on the judges' evaluation**. However, it was still **not a clear overall upgrade over the Previous Muta**, which remained stronger on the Muta STEM-100 initial evaluation (**63/100 vs. 60/100**).

This configuration therefore became our leading direction for the full fine-tuning run. Here is the loss curves for [all eight pilots](https://muta-iq.vercel.app/#g2-exp-pilots) alongside an [interactive gallery ](https://muta-iq.vercel.app/#g2-exp-loss).

#### 3. Full-data runs

Based on the pilot results, we moved to **full-data fine-tuning** and compared three training experiments: a fresh Qwen2.5 1.5b initialization, a warm start from our initial Muta Tutor, and a continuation of the best pilot experiment.

<table width="100%" style="border-collapse: collapse;">
<tr>

<td width="43%" valign="top" style="padding-right: 10px; border: none;">

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="4" style="border: 1px solid #888; padding: 8px 10px;">Full-Data Training Runs</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Run</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Initialization</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Rank / LR</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Final Dev Loss</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Clean</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Fresh Qwen2.5-1.5B-Instruct</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16 / 1 × 10⁻⁵</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>0.018999</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Warm</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">Recovered Muta parent</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16 / 5 × 10⁻⁶</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.022473</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Pilot continuation</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">
      <code>warm-r16-lr5e6</code> lineage;<br>
      fresh optimizer and schedule
    </td>
    <td style="border: 1px solid #888; padding: 8px 10px;">16 / 5 × 10⁻⁶</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.022921</td>
  </tr>
</table>

<p>
The selected full-run checkpoint was <strong>step 4693</strong>. Loss curves and provenance are documented in the
<a href="https://muta-iq.vercel.app/#g2-exp-full">full-data experiment section</a>
and
<a href="https://muta-iq.vercel.app/#g2-exp-loss">loss record</a>.
</p>

</td>

<td width="57%" valign="top" style="padding-left: 10px; border: none;">

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="5" style="border: 1px solid #888; padding: 8px 10px;">Matched Evaluation Results</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">MC Correct<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">MC Reasoning<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Written Correct<br>/50</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Judges<br>/96</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Previous Muta</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">38</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>37</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">28</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">46</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>20K warm pilot</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">37</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>33</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>55</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full clean</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">38</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">24</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full pilot continuation</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>39</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">36</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">24</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full fresh warm</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>39</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">40</td>
  </tr>
</table>

<br>

<table width="100%" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th colspan="3" style="border: 1px solid #888; padding: 8px 10px;">Fresh Generalization vs. Known Judges</th>
  </tr>
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Fresh Test<br>/100</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Known Judges<br>/96</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Previous Muta</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>41.68</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;">46</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Warm 20K pilot</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">13.55</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>55</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full fresh warm</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1.55</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">40</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full clean</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1.20</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Full pilot continuation</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1.15</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47</td>
  </tr>
</table>

</td>

</tr>
</table>

The full-data runs achieved very low validation losses, but this **did not translate into better downstream generalization**. All three full-data models performed substantially worse than the Previous Muta on the fresh test, despite some matching or exceeding it on the already-known judges' prompts.

The **20K warm pilot** remained the strongest new variant on written and judges' performance, but its fresh-test score also dropped sharply.

#### 4. Science and tutoring fine-tune

Although accuracy had improved, training solely on question–answer pairs is not ideal for a critical-thinking model. It must learn conversations, tutoring styles, how to identify erroneous assumptions, challenge flawed reasoning, ask clarifying questions, adapt explanations to a learner’s level, and guide users toward the correct answer rather than simply providing it. We therefore built a smaller **science + multi-turn tutoring corpus**  designed to teach misconception repair, adaptive explanation, scientific reasoning, clarification, and consistency across turns, so that the model can observe how reasoning evolves.

<table width="100%" style="border-collapse: collapse;">
<tr>

<td width="50%" valign="top" style="padding-right:10px; border:none;">

<table width="100%" style="border-collapse:collapse; text-align:left;">
  <tr>
    <th colspan="3" style="border:1px solid #888; padding:8px 10px; text-align:center;">Dataset Blend</th>
  </tr>
  <tr>
    <th style="border:1px solid #888; padding:8px 10px;">Dataset</th>
    <th style="border:1px solid #888; padding:8px 10px;">Size</th>
    <th style="border:1px solid #888; padding:8px 10px;">Contribution</th>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><a href="https://huggingface.co/datasets/zd21/SciInstruct">SciInstruct</a></td>
    <td style="border:1px solid #888; padding:8px 10px;">≈91.8K</td>
    <td style="border:1px solid #888; padding:8px 10px;">Science and mathematics explanations</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><a href="https://github.com/lupantech/ScienceQA">ScienceQA</a></td>
    <td style="border:1px solid #888; padding:8px 10px;">21,208</td>
    <td style="border:1px solid #888; padding:8px 10px;">Concepts, lessons and explanations</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><a href="https://huggingface.co/datasets/eth-nlped/mathdial">MathDial</a></td>
    <td style="border:1px solid #888; padding:8px 10px;">2,861 dialogues</td>
    <td style="border:1px solid #888; padding:8px 10px;">Misconception repair and tutoring dialogue</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><a href="https://huggingface.co/datasets/masharma/convolearn">ConvoLearn</a></td>
    <td style="border:1px solid #888; padding:8px 10px;">2,134 dialogues</td>
    <td style="border:1px solid #888; padding:8px 10px;">Science dialogue and formative questioning</td>
  </tr>
</table>

<br>

<table width="100%" style="border-collapse:collapse; text-align:center;">
  <tr>
    <th colspan="2" style="border:1px solid #888; padding:8px 10px;">Final Data Split</th>
  </tr>
  <tr>
    <th style="border:1px solid #888; padding:8px 10px;">Split</th>
    <th style="border:1px solid #888; padding:8px 10px;">Rows</th>
  </tr>
  <tr><td style="border:1px solid #888; padding:8px 10px;">Training</td><td style="border:1px solid #888; padding:8px 10px;"><strong>8,002</strong></td></tr>
  <tr><td style="border:1px solid #888; padding:8px 10px;">Development</td><td style="border:1px solid #888; padding:8px 10px;"><strong>1,577</strong></td></tr>
  <tr><td style="border:1px solid #888; padding:8px 10px;">Final holdout</td><td style="border:1px solid #888; padding:8px 10px;"><strong>1,591</strong></td></tr>
</table>

</td>

<td width="50%" valign="top" style="padding-left:10px; border:none;">

<table width="100%" style="border-collapse:collapse; text-align:center;">
  <tr>
    <th colspan="6" style="border:1px solid #888; padding:8px 10px;">Development Selection</th>
  </tr>
  <tr>
    <th style="border:1px solid #888; padding:8px 10px;">Candidate</th>
    <th style="border:1px solid #888; padding:8px 10px;">M /64</th>
    <th style="border:1px solid #888; padding:8px 10px;">S /32</th>
    <th style="border:1px solid #888; padding:8px 10px;">T /32</th>
    <th style="border:1px solid #888; padding:8px 10px;">Index</th>
    <th style="border:1px solid #888; padding:8px 10px;">Decision</th>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>P2-half</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>52</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;">17</td>
    <td style="border:1px solid #888; padding:8px 10px;">24</td>
    <td style="border:1px solid #888; padding:8px 10px;">72.66%</td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>Advance</strong></td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">P1-end</td>
    <td style="border:1px solid #888; padding:8px 10px;">51</td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>18</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>26</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>74.22%</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;">Guard failure</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">P4-half</td>
    <td style="border:1px solid #888; padding:8px 10px;">45</td>
    <td style="border:1px solid #888; padding:8px 10px;">15</td>
    <td style="border:1px solid #888; padding:8px 10px;">25</td>
    <td style="border:1px solid #888; padding:8px 10px;">66.41%</td>
    <td style="border:1px solid #888; padding:8px 10px;">Reject</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">P3-half</td>
    <td style="border:1px solid #888; padding:8px 10px;">45</td>
    <td style="border:1px solid #888; padding:8px 10px;">6</td>
    <td style="border:1px solid #888; padding:8px 10px;">15</td>
    <td style="border:1px solid #888; padding:8px 10px;">51.56%</td>
    <td style="border:1px solid #888; padding:8px 10px;">Reject</td>
  </tr>
</table>

<p><code>P1-end</code> had the highest raw score but failed the preregistered regression guard, leaving <strong>P2-half</strong> as the only candidate advanced to final evaluation.</p>

<p>Science-pilot losses and selection record: <a href="https://muta-iq.vercel.app/#g2-exp-science">science experiment</a>.</p>

</td>

</tr>
</table>


#### 5. Final matched comparison

We then compared **P2-half** against our Muta Tutor, Base Qwen, the historical warm pilot, and a DeepSeek-distilled Qwen2.5 1.5b using held-out science, a [2,000-question practical dataset](https://huggingface.co/datasets/timiiowolabi/Muta-Practical-2000), tutoring quality, judges' prompts, and STEM MC.

<table width="100%" style="border-collapse:collapse;">
<tr>

<td width="72%" valign="top" style="padding-right:10px; border:none;">

<table width="100%" style="border-collapse:collapse; text-align:center;">
  <tr>
    <th colspan="6" style="border:1px solid #888; padding:8px 10px;">Final Evaluation</th>
  </tr>
  <tr>
    <th style="border:1px solid #888; padding:8px 10px;">Model</th>
    <th style="border:1px solid #888; padding:8px 10px;">Held-out Science</th>
    <th style="border:1px solid #888; padding:8px 10px;">Practical /2,000</th>
    <th style="border:1px solid #888; padding:8px 10px;">Tutor Quality /64</th>
    <th style="border:1px solid #888; padding:8px 10px;">Judges /100</th>
    <th style="border:1px solid #888; padding:8px 10px;">STEM MC /50</th>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>Previous Muta</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>83.565%</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>41.325</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>22</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;">57</td>
    <td style="border:1px solid #888; padding:8px 10px;">32</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">P2-half</td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>83.565%</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;">39.850</td>
    <td style="border:1px solid #888; padding:8px 10px;">12</td>
    <td style="border:1px solid #888; padding:8px 10px;">50</td>
    <td style="border:1px solid #888; padding:8px 10px;">32</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">Untouched Qwen</td>
    <td style="border:1px solid #888; padding:8px 10px;">82.554%</td>
    <td style="border:1px solid #888; padding:8px 10px;">38.425</td>
    <td style="border:1px solid #888; padding:8px 10px;">17</td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>61</strong></td>
    <td style="border:1px solid #888; padding:8px 10px;"><strong>35</strong></td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">Historical warm</td>
    <td style="border:1px solid #888; padding:8px 10px;">83.375%</td>
    <td style="border:1px solid #888; padding:8px 10px;">12.500</td>
    <td style="border:1px solid #888; padding:8px 10px;">8</td>
    <td style="border:1px solid #888; padding:8px 10px;">57</td>
    <td style="border:1px solid #888; padding:8px 10px;">30</td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">Untouched DeepSeek</td>
    <td style="border:1px solid #888; padding:8px 10px;">Answer-delivery failure</td>
    <td style="border:1px solid #888; padding:8px 10px;">0.200</td>
    <td style="border:1px solid #888; padding:8px 10px;">15</td>
    <td style="border:1px solid #888; padding:8px 10px;">Failed gate</td>
    <td style="border:1px solid #888; padding:8px 10px;">Failed gate</td>
  </tr>
</table>

</td>

<td width="28%" valign="top" style="padding-left:10px; border:none;">

<table width="100%" style="border-collapse:collapse; text-align:left;">
  <tr>
    <th style="border:1px solid #888; padding:8px 10px; text-align:center;">Final Decision</th>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">
      <strong>P2 tied Muta on held-out science</strong>, but regressed on tutoring quality, and judges' evaluation.
    </td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">
      The promotion rule required <strong>no material regression plus a tutoring advantage</strong>.
    </td>
  </tr>
  <tr>
    <td style="border:1px solid #888; padding:8px 10px;">
      <strong>Result: retain Previous Muta Tutor Qwen2.5-1.5B.</strong>
    </td>
  </tr>
</table>

</td>

</tr>
</table>

From the result, we see that additional fine-tuning did not produce a reliable overall improvement. Instead, the results suggest **diminishing returns and increasing regression risk** as we continued adapting the model.


<span style="color: orange"><strong>Therefore, we retain the Previous Muta Tutor Qwen2.5-1.5B as our strongest choice for deployment. None of the full-data runs earned promotion.</strong></span>


A more comprehensive Gate 2 record can be found in [03 · Improving Accuracy: Model fine-tuning](https://muta-iq.vercel.app/#gate-2-experiments), with dedicated sections for the [data](https://muta-iq.vercel.app/#g2-exp-data), [pilots](https://muta-iq.vercel.app/#g2-exp-pilots), [full runs](https://muta-iq.vercel.app/#g2-exp-full), [science-tutor selection](https://muta-iq.vercel.app/#g2-exp-science), [matched decision](https://muta-iq.vercel.app/#g2-exp-evaluation), [loss record](https://muta-iq.vercel.app/#g2-exp-loss), and [packaging](https://muta-iq.vercel.app/#g2-exp-packaging). A full experiment comparison can be found [here](https://muta-iq.vercel.app/#g2-exp-evaluation) and the loss histories can be found [here](https://muta-iq.vercel.app/#g2-exp-loss).
</details>


<details>

<summary><strong>Optimization and Final Decision</strong></summary>

## Optimizing the Selected Muta Tutor for CPU Deployment

After the Gate 2 experiments, we retained **Muta Tutor Qwen2.5-1.5B** as our strongest model for deployment. Our next question was therefore **how much we could compress and accelerate this already-selected model without destroying its accuracy that made us choose it?**

We explored pruning, quantization, distillation, vocabulary reduction, MoE conversion, width reduction, and quantization-aware training—all methods for optimizing models.

Thus, our resulting deployment is:
> **[Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf](https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF/resolve/4fda6989e2820016256a4390e33aab2e745d5d34/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf)** — a dense Qwen2.5 architecture with a pruned 32K vocabulary, **1.5B parameters** and approximately **830 MB**.

---

### 1. Optimization target and measurement

We optimized against the competition-style combined score and all scored measurements used the ADTC' **scalar llama.cpp b10175 build**, with no AVX acceleration, on GCP `n2` proxy machines.

`S_acc` was computed from ARC-Easy-50 and judges' accuracy on tutoring prompts. Our score of record used **30 held-out development prompts**, while the 10 official Gate 1 prompts were also evaluated separately.

Eight blind LLM graders scored responses from 0–10 using worked reference answers. Regrading the same answer set across four rounds produced **28.0, 31.0, 32.0, and 30.7**, giving an observed grader variation of roughly four points.

No evaluation or judge prompt was used for training.

---

### 2. CPU-only exploration

We first tested which compression directions were worth carrying into GPU training.

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px; text-align: left;">Direction</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">ARC-50</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Peak MB</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">S_total</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">Published Muta Tutor, Q4_K_M</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">84</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">5.77</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1100</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">70.40</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">21 layers, SFT-healed</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">78</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">7.15</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">904</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">70.78</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">Vocabulary 48K, Q4_K_M</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">82</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">6.29</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">948</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">70.93</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">Q4_K_M + imatrix</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">82</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">5.53</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1099</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">68.99</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">IQ3_M / IQ2_XXS + imatrix</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">80 / 72</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1.89 / 1.98</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">926 / 673</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">61.20 / 58.08</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px; text-align: left;">MoE 8×1120, top-4 / top-2</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">54 / 30</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">6.72 / 9.61</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">1288 / 1271</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">56.85 / 50.67</td>
  </tr>
</table>

</div>

These were our main findings:

1. **Depth matters unevenly.** We evaluated 215 contiguous layer-removal windows by perplexity and 77 by ARC. Middle blocks—particularly around layers 8–9 and 14–15—were relatively cheap to remove, while early and final layers were highly sensitive.
2. **Sparse/MoE conversion was not automatically faster.** Router overhead and multiple smaller matrix multiplications reduced the expected benefit in the scalar runtime.
3. **Q4_0 was uniquely attractive in the audit build.** It was the only tested format with an effective SSSE3-accelerated kernel. On identical weights, Q4_0 increased decode speed from roughly **5.48 → 10.88 tok/s**, although direct conversion also reduced accuracy.

This gave us the central optimization problem:

> **Make Q4_0 small and fast, then recover as much of the lost model quality as possible.**

---

### 3. Compression chain

#### Training infrastructure

We built a **104,475-row teacher corpus** from GSM8K, ARC, QASC, and OpenR1 training questions across four tutoring frames, answered by **Qwen2.5-7B-Instruct**.

We also built:

- a near-duplicate guard against all held-out prompts,
- a top-32 teacher log-probability cache,
- KL-based knowledge distillation,
- a 130-prompt termination gate with loop detection,
- bit-exact Q4_0/Q8_0 fake quantization with straight-through gradients.

<span id="vocab-pruning"></span>
#### Step 1 — Vocabulary pruning

Vocabulary was reduced from approximately **152K → 32K**, retaining byte tokens, special tokens, corpus-observed tokens, and merge-order coverage.

Embedding parameters fell from approximately **233M → 49M**.

Result:

- **+0.99 tok/s**
- **−108 MB RAM**
  
#### Step 2 — Layer pruning + distillation

The depth analysis identified two promising cuts:

- **26 layers:** remove 14–15
- **24 layers:** remove 13–16

Both were improved using **81.7M distillation tokens**.

The 26-layer model improved from: `val_kl 0.363 → 0.179`

The 24-layer model was around 1 tok/s faster but produced loops in **21/40 answers**, so it was rejected.

#### Step 3 — MoE conversion

We tested shared-expert + routed-expert variants with top-2 routing.

One MoE variant retained approximately **75% of the FFN active**, yet became **slower than its dense parent**:

`12.42 tok/s vs. 13.15 tok/s`

The smaller variant reached approximately **20 tok/s**, but looped in **27/40 answers**.

Both were rejected.

---

### 4. Width pruning, verified distillation, and QAT

Instead of MoE, we returned to a dense architecture and reduced the FFN width.

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 16px;">FFN Width</th>
    <th style="border: 1px solid #888; padding: 8px 16px;">Decode Speed</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 16px;">7680</td>
    <td style="border: 1px solid #888; padding: 8px 16px;">14.69 tok/s</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 16px;"><strong>7168</strong></td>
    <td style="border: 1px solid #888; padding: 8px 16px;"><strong>15.45 tok/s</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 16px;">6656</td>
    <td style="border: 1px solid #888; padding: 8px 16px;">16.22 tok/s</td>
  </tr>
</table>

</div>

We selected **7168** because it was the widest model that crossed the competition's **15 tok/s performance cap**.

#### Verified training data

Before the final distillation run, we re-audited the teacher corpus.

A hand-labelled sample exposed a parser bug that had incorrectly marked **33.5% of GSM8K answers as wrong**. After fixing the verifier, that fell to **6.8%**.

The final verified training mixture included:

- **54,896** retained teacher rows,
- **29,750** gold-checked Orca-Math/OpenBookQA rows,
- **1,508** regenerated GSM8K/ARC misses,
- **13,735** unrolled MathDial/ConvoLearn tutoring turns,
- a **15K-row style anchor** scored by the original full-precision Muta Tutor.

Competition mathematics was capped at **11% of tokens**.

#### Final distillation

Training used:

- KL + `0.3 × cross-entropy`
- learning rate `1 × 10⁻⁵`
- cosine schedule
- **324M training tokens**
- approximately **6.1 hours**
- approximately **14.8K training tok/s**

Result: Validation loss improved from `val_kl 0.279 → 0.197`

#### Quantization-aware training

We then trained under simulated pure-Q4_0 noise using:

`LR = 5 × 10⁻⁶`

By step 100:

`val_kl under Q4_0 noise: 0.2466 → 0.2128`

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 12px;">Training Stage</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Tokens</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">val_kl Start → End</th>
    <th style="border: 1px solid #888; padding: 8px 12px;">Clean-ending Gate</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">24L / 26L depth heal</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">81.7M each</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.507 → 0.225 / 0.363 → 0.179</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.800 / 0.854</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">MoE a / b</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">81.7M each</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.779 → 0.328 / → 0.227</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.708 / 0.838</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">FFN-7168 verified KD</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">324M</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.279 → 0.197</td>
    <td style="border: 1px solid #888; padding: 8px 12px;"><strong>0.900</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 12px;">QAT, Q4_0 noise</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">26M</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">0.2466 → 0.2128</td>
    <td style="border: 1px solid #888; padding: 8px 12px;">Not run</td>
  </tr>
</table>

</div>

---

### 5. Final audit results

#### 30 held-out development prompts

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">ARC-Easy</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Judges</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_acc</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_perf</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Peak RAM</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_eff</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_total</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Published Muta Tutor, Q4_K_M</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">82</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">60.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">71.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5.48</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">36.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1100 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">84.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">63.39</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Pure Q4_0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">54.50</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">10.88</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">72.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">992 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">86.2</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">66.24</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">+ Vocabulary 32K</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">39.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">54.83</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">11.87</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">79.1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">884 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">87.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">68.69</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">+ 26 layers + KD</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">28.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">49.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">13.15</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">87.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">810 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">68.54</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">MoE b — rejected</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">68</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">44.33</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">12.42</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">82.8</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">816 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">64.73</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">MoE a — rejected</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">60</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">2.3</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">31.17</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20.04</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">100.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">798 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.9</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">63.36</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">FFN-7168 + verified KD</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">24.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">15.42</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">100.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">683 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">90.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">71.59</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;"><strong>FFN-7168 + QAT — delivered</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>72</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>31.3</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>51.67</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>15.51</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>100.0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>706 MB</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>90.2</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>73.86</strong></td>
  </tr>
</table>

</div>

#### 10 official Gate 1 prompts

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">ARC-Easy</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Judges</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_acc</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_perf</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Peak RAM</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_eff</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_total</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Published Muta Tutor</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">82</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">45.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">63.50</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5.48</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">36.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1100 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">84.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">59.64</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Pure Q4_0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">27.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">48.50</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">10.88</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">72.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">992 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">86.2</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">63.24</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">+ Vocabulary</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">26.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">48.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">11.87</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">79.1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">884 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">87.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">65.27</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">+ 26 layers</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">45.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">57.50</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">13.15</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">87.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">810 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.7</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">72.79</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">MoE b — rejected</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">68</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">34.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">51.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">12.42</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">82.8</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">816 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.6</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">68.06</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">MoE a — rejected</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">60</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">14.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">37.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">20.04</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">100.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">798 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">88.9</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">66.27</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">FFN-7168 distilled</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">70</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">30.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">50.00</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">15.42</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">100.0</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">683 MB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">90.5</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">73.09</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;"><strong>FFN-7168 + QAT</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>72</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>35.0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>53.50</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>15.51</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>100.0</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>706 MB</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>90.2</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>74.78</strong></td>
  </tr>
</table>

</div>
### What improved

Compared with the published Muta Tutor, the full compression chain:

- increased scalar decode speed from roughly **5.5 → 15.5 tok/s**,
- reduced peak RAM from roughly **1.1 GB → 0.7 GB**,
- reduced the model to approximately **593 MB**,
- but sacrificed some judge and ARC accuracy.

This makes the fully compressed model a strong **efficiency-first variant**, but not a suitable replacement for our quality-first Muta Tutor.

---

### Final Decision

<span style="color: orange"><strong>
Since accuracy remains our highest priority for an educational model, we will not adopt the full compression chain. Instead, we will carry forward only the <a href="#vocab-pruning">vocabulary-pruning optimization</a>, which reduced model size and improved deployment efficiency without showing an accuracy regression in our evaluation. Our updated deployment model is therefore <code>Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf</code>, which preserves the capability of our selected Muta Tutor while being smaller and faster. It can be found <a href="https://huggingface.co/timiiowolabi/Muta-Tutor-Qwen2.5-1.5B-ADTC-GGUF/blob/main/Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf">here</a>.
</strong></span>

To validate this decision, we directly compared the vocabulary-pruned model against the incumbent Muta Tutor under the same audit setup using our curated [dataset](https://huggingface.co/datasets/timiiowolabi/Muta-GCP-Synthetic-Judges-20260922):

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Model</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Synthetic Accuracy*</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Decode tok/s<br>(capture)</th>
    <th style="border: 1px solid #888; padding: 8px 10px;"><code>llama-bench</code><br>tok/s</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Peak RSS</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_perf</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">S_eff</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">ADTC Proxy Total†</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>Muta-vocab32k.gguf</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>6/10 (60%)</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>5.277</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>6.370</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>896.4 MiB</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>42.47</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>87.49</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>60.24</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px;">Muta-incumbent.gguf</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">4/10 (40%)</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">4.705</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">5.367</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1,073.0 MiB</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">35.78</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">85.03</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">47.74</td>
  </tr>
</table>

</div>

The vocabulary-pruned model was **faster, used less memory, and showed no accuracy regression in this small synthetic comparison**, resulting in a substantially higher ADTC proxy score (**60.24 vs. 47.74**).

A more comprehensive report on the optimization experiments can be found [here](https://muta-iq.vercel.app/#gate-2-finetuning).

</details>

<details>
<summary><strong>Model Provenance</strong></summary>

- Base model name and exact source: [`Qwen/Qwen2.5-1.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/tree/775b11afaf83e0dc75bd5abaf90133e47b3ec082).

- Git Commit SHA: `775b11afaf83e0dc75bd5abaf90133e47b3ec082`.

- Fine-tuning method used: Weight-level BF16 LoRA (rank 16, 500 steps), with the adapter merged into the base model; this was not QLoRA or a full-weight fine-tune.

- Training datasets used: 10,756 training examples from [AI2 ARC](https://huggingface.co/datasets/allenai/ai2_arc/tree/210d026faf9955653af8916fad021475a3f00453) (3,166 ARC-Easy/ARC-Challenge rows; CC-BY-SA-4.0) and [QASC](https://huggingface.co/datasets/allenai/qasc/tree/a34ba204eb9a33b919c10cc08f4f1c8dae5ec070) (7,590 rows; CC-BY-4.0).

- Before/After Comparison

  - To verify that vocabulary pruning preserved the behaviour learned during fine-tuning, we compared the vocabulary-pruned Muta directly against the untouched **Qwen2.5-1.5B-Instruct** base model under the same CPU setup.

---

#### Prompt 1 — Scientific reasoning and misconception correction

**Prompt**

> A student says:
>
> “At chemical equilibrium, the reaction has stopped because the amounts of reactants and products are now equal.”
>
> Respond as a science tutor helping the student understand the mistake.
>
> Your response should:
> 1. Identify which parts of the student's statement are wrong.
> 2. Explain what chemical equilibrium actually means.
> 3. Clearly distinguish “equal reaction rates” from “equal concentrations.”
> 4. Give one simple example or analogy.
> 5. Correct the misconception without sounding dismissive.
> 6. End with one short question that checks whether the student now understands the idea.

We evaluated both responses against the scientific and tutoring requirements:

<div align="center">

<table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th style="border: 1px solid #888; padding: 8px 10px;">Criterion</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Base Qwen2.5-1.5B</th>
    <th style="border: 1px solid #888; padding: 8px 10px;">Vocab-pruned Muta</th>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Recognises that equilibrium is dynamic</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0 / 2</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>2 / 2</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Equal forward and reverse reaction rates</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">2 / 2</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>2 / 2</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Concentrations need not be equal</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">2 / 2</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>2 / 2</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Diagnoses the student's misconception</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 / 1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>1 / 1</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Useful analogy or example</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.5 / 1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">0.5 / 1</td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Supportive tutoring style</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 / 1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>1 / 1</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;">Checks learner understanding</td>
    <td style="border: 1px solid #888; padding: 8px 10px;">1 / 1</td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>1 / 1</strong></td>
  </tr>

  <tr>
    <td style="border: 1px solid #888; padding: 8px 10px; text-align: left;"><strong>Total</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>7.5 / 10</strong></td>
    <td style="border: 1px solid #888; padding: 8px 10px;"><strong>9.5 / 10</strong></td>
  </tr>
</table>

</div>

The main difference was **scientific consistency**. The base model initially explained equilibrium correctly, but later reintroduced the student's original misconception by stating that **“the reaction has stopped.”**

The vocabulary-pruned Muta preserved the crucial concept that equilibrium is **dynamic**: the forward and reverse reactions continue at equal rates, while the macroscopic concentrations remain constant and need not be equal.

This first comparison, therefore, shows that the vocabulary-pruned fine-tuned model preserved the reasoning and tutoring behavior learned during fine-tuning and outperformed the untouched base model on this misconception-correction task.

---

#### Prompt 2 — Pending

A second prompt will test a different capability so that the comparison is not based on a single type of scientific reasoning task.


- LoRA adapter weights: [adapter_model.safetensors](provenance/adapter_model.safetensors) and config: [adapter_config.json](provenance/adapter_config.json)
- The training/fine-tuning script or config that produced the model: [train_lora.py](provenance/scripts/train_lora.py)
- Training run logs: [logs](provenance/logs)
- The training dataset: [dataset](provenance/dataset)
- SHA256 checksums of the base model file: [checksums](provenance/SHA256SUMS)
- The merge/quantization script: [merge_and_quantize.py](provenance/scripts/merge_and_quantize.py)
</details>
