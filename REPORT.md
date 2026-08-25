# Technical Report for Muta: Offline Adaptive STEM Tutor for African Students
View our comprehensive report [here](https://muta-iq.vercel.app/).
**Team ID:** [TEAM ID]
**Domain:** `math_scientific_reasoning`
**Model:** Fine-tuned Qwen2.5 1.5B Instruct — Q4_K_M
**Runtime:** llama.cpp / GGUF
**Deployment target:** CPU-only consumer laptops

---

## Problem

Across many African classrooms, the problem is not simply access to information.

A student may have a textbook and still not have someone available to patiently explain the exact concept they do not understand. A teacher may be responsible for too many students to provide truly individual attention. Even where AI tools are available, they commonly depend on continuous internet access, cloud inference, and hardware or subscriptions that cannot be assumed for every learner.

Muta addresses this problem by working toward a **truly personal educational AI tutor that can run locally on the laptop a student already has**.

Our target user is primarily a secondary-school student learning Mathematics and Science who needs more than a system that returns an answer. Muta is intended to explain concepts, reason through problems, respond to follow-up questions, and adapt the educational interaction around the learner.

Running locally is fundamental to this use case.

It means that a student can continue learning when the internet is unavailable, unreliable, or expensive. It removes the requirement for a dedicated GPU or continuous cloud inference. It reduces the marginal cost of every additional question and gives us a path toward deploying AI tutoring in schools and homes where connectivity cannot be treated as infrastructure that is always available.

This is particularly important to our broader vision for Muta. **Muta is not the underlying language model.** The model is a replaceable intelligence engine inside a larger educational system. Our long-term goal is for Muta to become the educational intelligence layer connecting the student, teacher, parent, institution, and curriculum while accumulating learning context over time.

The immediate challenge for this competition was therefore very concrete:

> **How much useful mathematical and scientific reasoning can we place on an ordinary CPU-only laptop while remaining fast enough to feel interactive and small enough to operate comfortably inside the competition's memory budget?**

That question drove every model and systems decision we made.

---

## Design Decisions

### Base model

Our current vector-configuration candidate is a **fine-tuned Qwen2.5 1.5B Instruct model**, deployed as GGUF using **Q4_K_M quantization**.

We did not begin by assuming that this would be the final model.

We first studied the relationship between model size, reasoning quality, memory consumption, and generation speed. Larger models predictably gave better reasoning performance, but their additional accuracy had to justify the corresponding increase in RAM and weight bandwidth on a low-resource CPU.

We subsequently widened the search across several architectures and sizes, including:

* Qwen3 and Qwen3.5 models from 0.8B to 4B
* Qwen2 and Qwen2.5 at 1.5B and 3B
* Llama 3.2 at 1B and 3B
* Gemma 2 2B
* Phi-4 Mini
* Orca Mini
* specialist mathematical fine-tunes
* an 8B ternary BitCPM4 candidate

The goal was not to select the model with the highest raw accuracy. We selected according to the competition's combined accuracy, performance, and memory objective.

Our 8B BitCPM4 TQ2_0 experiment illustrates this clearly. It achieved the highest raw ARC-Easy result we measured during an earlier search, but its scalar decoding throughput was only approximately 0.81 tok/s. Even after vector acceleration raised it substantially, it still failed to beat the smaller dense Qwen candidates on the combined objective.

The most accurate model was therefore not necessarily the best deployable model.

### Quantization

We selected **Q4_K_M** for the Qwen2.5 1.5B vector candidate.

One of our most important findings was that quantization cannot be considered independently of the CPU kernel that executes it.

Initially, Q4_0 appeared substantially better than several theoretically more sophisticated formats because the supplied scalar profiler had an optimized SIMD implementation for Q4_0 while K-quants fell back to slower generic code.

We therefore built a second, portable CPU configuration with:

`AVX=ON`
`AVX2=ON`
`FMA=ON`
`F16C=ON`
`NATIVE=OFF`
`AVX-512=OFF`

Once AVX2/FMA/F16C were available, the ranking changed. Q4_K_M could use an efficient vectorized path and became substantially more attractive.

For Qwen2.5 1.5B, the vectorized Q4_K_M model gave us the best measured balance between reasoning accuracy, throughput, and memory among the larger matched candidate set.

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

The first eight runs failed to improve the metric that mattered.

That failure became useful.

We discovered that much of the original training mixture emphasized long worked solutions and tutoring dialogue, while the profiler's accuracy evaluation used short answer continuations. We also discovered a tokenization-level issue: the training data builder had omitted the leading space between `Answer:` and the expected continuation, changing the BPE token sequence used during training.

We rebuilt the data pipeline, corrected the continuation format, used verified answers, checked for held-out contamination, and aligned the training objective much more closely with the evaluation task.

The resulting metric-aligned fine-tuning improved:

* **Qwen3.5 0.8B:** 55.2% → **70.2%**
* **Qwen2.5 1.5B:** 74.4% → **77.8%**

on matched 500-item evaluations.

Importantly, these accuracy gains did not materially increase model memory usage or reduce throughput.

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

This became important during live tests. Unrestricted reasoning could consume the entire response budget internally before returning a useful answer to the learner. The model therefore needs to be optimized not only for benchmark accuracy, but for actual interactive tutoring behaviour.

The final tuned candidate still requires this metadata pass and final live-prompt revalidation before submission.

---

## Alternatives Considered

We did not arrive at the current model through a single quantization experiment. Several optimization paths were investigated and either adopted, rejected, or retained only for the full Muta product.

### Qwen3.5 0.8B Q4_0

This remains our **scalar-profiler leader**.

After fine-tuning, it achieved:

* **70.2% ARC-Easy**, n=500
* **13.60 tok/s**
* approximately **691 MiB estimated profiler RSS**
* **80.3664** fixed-15 scalar score

It is currently the safer choice if the final evaluator uses the same scalar kernel configuration as the supplied participant profiler.

### Qwen2.5 1.5B Q4_K_M

This is our **vector-configuration leader** and current candidate where AVX2/FMA/F16C are available.

After fine-tuning, it achieved:

* **77.8% ARC-Easy**, n=500
* **17.44 tok/s**
* approximately **1,706 MiB estimated profiler RSS**
* **84.1387** fixed-15 vector score

It sacrifices some memory efficiency relative to the 0.8B candidate but gains enough reasoning accuracy and vectorized throughput to win the combined objective.

### Math-Expert 0.6B

A specialist Qwen3-based mathematical fine-tune initially produced an attractive small-sample result and very high throughput under the vector runtime.

However, once the finalists were evaluated on a larger matched 500-item sample, its estimated accuracy dropped enough that it no longer led the combined objective.

This was an important reminder not to optimize against a small benchmark sample.

### BitCPM4 8B TQ2_0

We explored a very different strategy: use many more parameters but compress them aggressively using ternary weights.

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

The competition evaluates our GGUF using the organizer's llama.cpp runtime, so this optimization cannot travel inside the submitted model file.

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

CPU inference also consumes battery power and produces heat. In the complete Muta application, this led us to implement power-aware behaviour such as **Eco Mode**, where automatic reasoning and response length can be bounded when the machine is running on battery.

Those product-level controls are separate from the submitted GGUF, but the same concern influenced our preference for smaller models that achieve strong reasoning performance without requiring several billion additional parameters.

---

## Benchmarks

Our current benchmark evidence is deliberately separated by CPU configuration because we discovered that CPU instruction-set support can change the model ranking.

### Current vector candidate

| Metric                   | Value                                        |
| ------------------------ | -------------------------------------------- |
| Model                    | Fine-tuned Qwen2.5 1.5B                      |
| Quantization             | Q4_K_M                                       |
| Runtime                  | llama.cpp                                    |
| Benchmark configuration  | Portable vector CPU build                    |
| CPU features             | AVX2, FMA, F16C enabled; AVX-512 disabled    |
| Workload                 | 512 prompt tokens / 128 generated tokens     |
| Evaluation threads       | 2 physical-core threads                      |
| ARC-Easy accuracy        | **77.8%**, n=500                             |
| Generation speed         | **17.44 tok/s**                              |
| Estimated profiler RSS   | **1,706 MiB**                                |
| Fixed-15 estimated total | **84.1387**                                  |
| Time to first token      | Final tuned candidate re-measurement pending |
| Temperature              | Not exposed by current GCP benchmark host    |
| Thermal throttling       | Physical-target validation pending           |

These are **self-reported development measurements**, not official ADTC evaluation results. RSS is based on the measured benchmark child tree plus an estimated profiler-process allowance.

### Scalar fallback candidate

Because the supplied participant profiler uses a different kernel configuration, we also retain a separate scalar candidate:

| Metric                 | Value                   |
| ---------------------- | ----------------------- |
| Model                  | Fine-tuned Qwen3.5 0.8B |
| Quantization           | Q4_0                    |
| ARC-Easy accuracy      | **70.2%**, n=500        |
| Generation speed       | **13.60 tok/s**         |
| Estimated profiler RSS | **691 MiB**             |
| Fixed-15 scalar total  | **80.3664**             |

This split is not arbitrary.

Q4_K_M performs strongly when the appropriate AVX2 vector kernels are available, while Q4_0 remains much more competitive under the supplied scalar profiler configuration.

Therefore, our final submission decision depends on the exact CPU/kernel configuration used during the official audit.

---

## What the Optimization Process Taught Us

The largest lesson from this project is that optimizing an offline language model is not the same thing as finding the smallest GGUF.

The effective system is:

**model architecture × training × quantization × CPU kernel × memory behaviour × evaluation objective**

Changing any one of those variables can change which model wins.

We observed models that were:

* more accurate but too slow,
* smaller but less accurate,
* theoretically better quantized but slower because of kernel dispatch,
* dramatically faster under AVX2 without any change to their weights,
* improved in training loss without improving the actual target metric,
* and excellent in the complete Muta runtime but impossible to benefit from in a GGUF-only submission.

The current candidate is therefore the result of an empirical optimization campaign rather than a single model download and quantization pass.

---

## Current Status and Final Validation

At the time of this report, our measured leaders are:

**Scalar configuration:**
Fine-tuned **Qwen3.5 0.8B Q4_0**

**AVX2 vector configuration:**
Fine-tuned **Qwen2.5 1.5B Q4_K_M**

Before packaging the final competition artifact, we are completing the remaining validation steps:

1. Embed the final Muta tutoring policy into the tuned GGUF.
2. Repeat the live tutoring-prompt acceptance battery.
3. Verify model behaviour through the competition-compatible llama.cpp path.
4. Run repeated measurements on the physical target machine.
5. Measure whole-process-tree RSS.
6. Record temperature and confirm whether thermal throttling occurs.
7. Complete the remaining held-out validation for the Qwen2.5 candidate.

The goal is not merely to submit the model with the highest isolated benchmark.

The goal is to submit the model that best fulfills what Muta was built for:

> **A capable, responsive educational AI tutor that can meet a student where they are—even when all they have is an ordinary laptop and no internet connection.**
