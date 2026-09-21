# Muta ADTC 2026 — Combined Technical Report

**Domain:** Mathematics and Scientific Reasoning

<details>
<summary><strong>Gate 1 — Initial Submission, Results & Re-analysis</strong></summary>

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

| Metric                 | Value                   |

| ---------------------- | ----------------------- |

| Model                  | Fine-tuned Qwen3.5 0.8B |

| Quantization           | Q4_0                    |

| ARC-Easy accuracy      | **70.2%**, n=500        |

| Generation speed       | **13.60 tok/s**         |

| Estimated profiler RSS | **691 MiB**             |

| Fixed-15 scalar total  | **80.3664**             |

Official-profiler run on the submitted GGUF (`adtc-profiler 0.1.0`, participant mode, llama-bench 512 prompt / 128 generated tokens):

| Metric                                 | Value                                                                 |

| -------------------------------------- | --------------------------------------------------------------------- |

| Machine                                | Intel Xeon @ 2.80 GHz (4 vCPU), 7.8 GB RAM, no GPU, Ubuntu 22.04.5    |

| Generation speed                       | **12.98 tok/s**                                                       |

| Time to first token (512-token prompt) | ≈ 15.0 s (profiler approximation from prompt-processing rate)         |

| Peak RSS                               | **674 MB** (steady state 629 MB)                                      |

| ARC-Easy acc_norm (n=50)               | **0.72**                                                              |

| CPU utilisation p99                    | 54.2 %                                                                |

| Temperature                            | Not exposed by the benchmark host                                     |

| Thermal throttling                     | Not flagged                                                           |

### Alternative (vector build, not submitted) — Qwen2.5 1.5B Q4_K_M

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
<summary><strong>Gate 2 — Exploration, Improving Accuracy & Final Selection</strong></summary>

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

### Final decision

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

### Decision

The full-data runs achieved very low validation losses, but this **did not translate into better downstream generalization**. All three full-data models performed substantially worse than the Previous Muta on the fresh test, despite some matching or exceeding it on the already-known judges' prompts.

The **20K warm pilot** remained the strongest new variant on written and judges' performance, but its fresh-test score also dropped sharply.

<span style="color: orange"><strong>Therefore, we retain the Previous Muta Tutor Qwen2.5-1.5B. None of the full-data runs earned promotion.</strong></span>

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

We then compared **P2-half** against the incumbent Muta, untouched Qwen, the historical warm pilot, and a DeepSeek-distilled Qwen2.5 1.5b using held-out science, a [2,000-question practical dataset](https://huggingface.co/datasets/timiiowolabi/Muta-Practical-2000), tutoring quality, judges' prompts, and STEM MC.

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

The additional fine-tuning did not produce a reliable overall improvement. Instead, the results suggest **diminishing returns and increasing regression risk** as we continued adapting the model. Our original Muta Tutor therefore remained the strongest deployment choice.

Full comparison: <a href="https://muta-iq.vercel.app/#g2-exp-evaluation">final matched decision</a> · Loss histories: <a href="https://muta-iq.vercel.app/#g2-exp-loss">loss gallery</a>.

#### 7. Post-selection packaging

After model selection, the requested Qwen3.5-style judge template was embedded
as metadata in a separate, tensor-identical GGUF. It is a packaging variant,
not a new fine-tune or a new winner. The original incumbent remains unchanged.
See the [Gate 2 packaging record](https://muta-iq.vercel.app/#g2-exp-packaging).

A more comprehensive Gate 2 record is in [03 · Improving Accuracy: Model fine-tuning](https://muta-iq.vercel.app/#gate-2-experiments), with dedicated anchors for the [data](https://muta-iq.vercel.app/#g2-exp-data), [pilots](https://muta-iq.vercel.app/#g2-exp-pilots), [full runs](https://muta-iq.vercel.app/#g2-exp-full), [science-tutor selection](https://muta-iq.vercel.app/#g2-exp-science), [matched decision](https://muta-iq.vercel.app/#g2-exp-evaluation), [loss record](https://muta-iq.vercel.app/#g2-exp-loss), and [packaging](https://muta-iq.vercel.app/#g2-exp-packaging).

</details>

<details>
<summary><strong>Optimization</strong></summary>
# Muta-Tutor: compressing a Qwen2.5-1.5B STEM tutor for a CPU-only audit — technical report

*16–21 September 2026 · delivered model: `refine-qat100-Q4_0.gguf` (dense Qwen2, 26 layers, FFN 7168, 32k vocabulary, 1.05 B parameters, 593 MB) · Hugging Face `timiiowolabi/muta-compress-20260920`*

## 1. Target and measurement

`S_total = 0.5·S_acc + 0.3·min(tok/s ÷ 15, 1)·100 + 0.2·(7 − peak GB) ÷ 7·100`, so 1 tok/s is worth 2.0 points, 1 accuracy point 0.5, 100 MB 0.29. Every scored row is one run of the organisers' profiler image — llama.cpp b10175 built **scalar** (no AVX), 4 threads — on GCP `n2` proxy VMs: decode tok/s, peak RSS, ARC-Easy-50 (±7 points at n = 50). `S_acc = mean(ARC-Easy-50, Judges' acc)`. Judges' acc: greedy answers to 40 tutoring prompts (30 held-out *dev* prompts written for this work = score of record; the 10 official Round-1 prompts beside it), scored 0–10 by 8 blind LLM graders against a rubric with worked reference answers. One fixed answer set was regraded in four rounds: 28.0, 31.0, 32.0, 30.7 — a ≈4-point grader band (≈1 `S_total`). No test item or judge prompt was ever trained on.

## 2. Exploration (16–19 Sep, CPU only)

- **Baseline.** The published tutor (LoRA fine-tune, Q4_K_M) audits at 5.8 tok/s, 1100 MB, ARC 84: speed-bound (S_perf 38).
- **Direction sweep, one audit per idea.** IQ2/IQ3/IQ4 imatrix quants decode at 1.9–2.9 tok/s in the scalar build (no SIMD dequant path): −24 S_perf for +6 S_eff. Imatrix on Q4_K_M: no gain. Training-free MoE (k-means experts, fitted router): ARC 54 at top-4, chance at top-2. Vocabulary 152k → 48k: +0.5. 21 layers, SFT-healed: +0.4 on ARC-50 but ARC-Easy-500 0.72 vs 0.78.
| Direction sweep (accuracy = ARC-50 only, so not comparable with §5) | ARC-50 | tok/s | Peak MB | S_total |
|---|---:|---:|---:|---:|
| Published tutor, Q4_K_M | 84 | 5.77 | 1100 | 70.40 |
| 21 layers, SFT-healed | 78 | 7.15 | 904 | 70.78 |
| Vocabulary 48k, Q4_K_M | 82 | 6.29 | 948 | 70.93 |
| Q4_K_M + imatrix | 82 | 5.53 | 1099 | 68.99 |
| IQ3_M / IQ2_XXS + imatrix | 80 / 72 | 1.89 / 1.98 | 926 / 673 | 61.20 / 58.08 |
| MoE 8×1120, untrained, top-4 / top-2 | 54 / 30 | 6.72 / 9.61 | 1288 / 1271 | 56.85 / 50.67 |

- **Exhaustive depth grid.** 215 contiguous layer windows scored by perplexity, 77 by ARC, on 8 boxes: mid-stack windows (8–9, 14–15) are nearly free; the first and last layers are fatal; cutting the lowest Block-Influence layers instead of a contiguous window cost 16 ARC points.
- **Kernel finding.** Pure **Q4_0 is the only format with a SIMD (SSSE3) kernel in the audit build**: 5.48 → 10.88 tok/s on the same weights, for −12 ARC and −21 judges' points. The rest of the work makes a Q4_0 model small, fast and accurate again.

## 3. Five-step chain (19–20 Sep, rented A100-40GB)

**Tooling.** 104,475-row teacher corpus (GSM8K, ARC, QASC, OpenR1 *train* questions × four tutoring frames, answered by Qwen2.5-7B-Instruct, near-duplicate guard against all held-out prompts); top-32 teacher log-prob cache with a residual bucket (59.4 M positions, 7.4 GB); KD trainer — KL on the top-32 support, fp32 masters under bf16 autocast, 8-bit AdamW, packed 16k-token micro-batches, 262k tokens/step; a 130-prompt termination gate with a text-loop detector; bit-exact Q4_0/Q8_0 fake-quant with straight-through gradients, verified against gguf-py and a C reference on 6.4 M elements including tie cases.

1. **Vocabulary pruning** to 32,000 (bytes + specials + corpus-seen ids + merge-order fill; embedding 233 M → 49 M parameters; patched GGUF converter). No training. +0.99 tok/s, −108 MB, accuracy level.
2. **Layer pruning + distillation.** Window-perplexity map → drop 14–15 (26 L) or 13–16 (24 L); heal with 81.7 M KD tokens. 26 L: val_kl 0.363 → 0.179, gate 0.854. 24 L was 1 tok/s faster but looped on 21/40 answers. An on-policy KD round made it worse (gate 0.80 → 0.68; hypothesis: the teacher scoring the student's own looping text endorses the loop).
3. **MoE conversion + distillation — negative.** Shared expert + routed experts (top-2), 81.7 M KD tokens each. Variant b (75 % of the FFN active) is *slower* than its dense parent in the audit build (12.42 vs 13.15 tok/s — routed matmuls cost more than they save there); variant a reaches 20 tok/s but loops on 27/40 answers. Dropped. The step-4 recipe grid (imatrix; sensitivity-ranked Q8_0 promotions) and a 26-minute QAT on the MoE were built but never scored.

## 4. Refinement (20–21 Sep, A100-40GB)

**Width pruning instead of MoE.** FFN neurons ranked by `E[a²]·‖W_down[:, j]‖²` on 200k calibration tokens; three widths exported *unhealed* and timed on the audit build, since speed depends only on shapes: 7680 → 14.69 tok/s, **7168 → 15.45**, 6656 → 16.22. Chosen: the widest width above the 15 tok/s cap (unhealed val_kl 0.279 vs 0.179 unpruned).

**Verified data (≈49 M tokens per pass).** Every teacher answer checked against the benchmark's gold answer; a hand-labelled sample exposed a parser bug that had marked 33.5 % of GSM8K answers wrong (6.8 % after the fix) → 54,896 rows kept, competition maths capped at 11 % of tokens. Added: 29,750 gold-checked orca-math/OpenBookQA rows (a second gold bug fixed: 4,377 → 18,118 usable questions), 1,508 regenerated GSM8K/ARC misses, 13,735 unrolled MathDial/ConvoLearn tutor turns, and a 15k-row style anchor scored by the original full-precision tutor.

**Training.** KL + 0.3·cross-entropy, lr 1e-5 cosine, 324 M tokens in 6.1 h at 14.8k tok/s: val_kl 0.279 → 0.197; termination gate 0.900, the best of the chain. **QAT** under pure-Q4_0 noise (lr 5e-6): val_kl-under-noise 0.2466 → 0.2128 by step 100. The GPU host became unreachable near step 160 of 362; the step-100 checkpoint survived via hourly off-box backups and was exported on a GCP CPU box. Q4_0 perplexity penalty: 7.6 % without QAT, 1.6 % with.

| Training progress | Tokens | val_kl start → end | Clean-ending gate (pass ≥ 0.835) |
|---|---:|---:|---:|
| Step 2 heal, 24 L / 26 L | 81.7 M each | 0.507 → 0.225 / 0.363 → 0.179 | 0.800 / 0.854 |
| Step 3 MoE a / b | 81.7 M each | 0.779 → 0.328 / → 0.227 | 0.708 / 0.838 |
| Refinement KD (FFN 7168) | 324 M | 0.279 → 0.197 | 0.900 |
| QAT, measured under Q4_0 noise | 26 M (step 100) | 0.2466 → 0.2128 | not run (host lost) |

## 5. Results (all Q4_0 unless named; audit build)

**Judges' acc = 30 held-out dev prompts (score of record)**

| Model | ARC-Easy acc | Judges' acc | S_acc | tok/s | S_perf | Peak RAM (MB) | S_eff | S_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Published tutor, 28 L, Q4_K_M | 82 | 60.0 | 71.00 | 5.48 | 36.5 | 1100 | 84.7 | 63.39 |
| 0 · same weights, pure Q4_0 | 70 | 39.0 | 54.50 | 10.88 | 72.5 | 992 | 86.2 | 66.24 |
| 1 · vocabulary → 32,000 | 70 | 39.7 | 54.83 | 11.87 | 79.1 | 884 | 87.7 | 68.69 |
| 2 · 26 layers + KD heal | 70 | 28.0 | 49.00 | 13.15 | 87.7 | 810 | 88.7 | 68.54 |
| 3 · MoE b + KD (rejected) | 68 | 20.7 | 44.33 | 12.42 | 82.8 | 816 | 88.6 | 64.73 |
| 3 · MoE a + KD (rejected) | 60 | 2.3 | 31.17 | 20.04 | 100.0 | 798 | 88.9 | 63.36 |
| R · FFN 7168 + verified KD | 70 | 24.0 | 47.00 | 15.42 | 100.0 | 683 | 90.5 | 71.59 |
| **R · + QAT (delivered)** | 72 | 31.3 | 51.67 | 15.51 | 100.0 | 706 | 90.2 | **73.86** |

**Judges' acc = 10 official prompts (n = 10, noisy)**

| Model | ARC-Easy acc | Judges' acc | S_acc | tok/s | S_perf | Peak RAM (MB) | S_eff | S_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Published tutor, Q4_K_M | 82 | 45.0 | 63.50 | 5.48 | 36.5 | 1100 | 84.7 | 59.64 |
| 0 · pure Q4_0 | 70 | 27.0 | 48.50 | 10.88 | 72.5 | 992 | 86.2 | 63.24 |
| 1 · vocabulary | 70 | 26.0 | 48.00 | 11.87 | 79.1 | 884 | 87.7 | 65.27 |
| 2 · 26 layers | 70 | 45.0 | 57.50 | 13.15 | 87.7 | 810 | 88.7 | 72.79 |
| 3 · MoE b (rejected) | 68 | 34.0 | 51.00 | 12.42 | 82.8 | 816 | 88.6 | 68.06 |
| 3 · MoE a (rejected) | 60 | 14.0 | 37.00 | 20.04 | 100.0 | 798 | 88.9 | 66.27 |
| R · distilled | 70 | 30.0 | 50.00 | 15.42 | 100.0 | 683 | 90.5 | 73.09 |
| **R · + QAT** | 72 | 35.0 | 53.50 | 15.51 | 100.0 | 706 | 90.2 | **74.78** |

A second blind grading of the delivered model gave 33.7 dev / 32.0 official → 74.45 / 74.03; its same-batch 26-layer control scored 69.54 and 69.21.

| Held-out capability | ARC-Easy-500 | GSM8K-100 | hit length cap | looping answers /40 | tutoring probe /10 |
|---|---:|---:|---:|---:|---:|
| 26-layer parent | 70.0 % | 49 % | 6 % | 8 | 3.24 |
| **Delivered** | 73.4 % | 53 % | 3 % | 4 | 3.26 |

**Reading.** Against the 26-layer model, `S_total` rises 4.3–5.2 points: **+3.70 is reaching the 15 tok/s cap**, +0.3 RAM, +0.3 to +1.3 accuracy — i.e. 17 % of the parameters were removed and quality was held, not raised. Judges' acc is level with the parent, inside grader noise (targets of 40–50 and ARC 75–80 were missed). ARC-Easy-500 (z ≈ 1.2) and GSM8K-100 point the right way but are not individually significant. Against the published tutor the chain gains +10.5 `S_total` by trading 29 judges' points and 10 ARC points for 2.8× the speed and −36 % RAM.

## 6. Negative results and limits

Scalar-build IQ quants; training-free and trained MoE; on-policy KD; the 24-layer cut; imatrix on the final model (inconclusive: −6 dev, +11 official). **Tutoring-dialogue mode does not work**: on 50 held-out MathDial dialogues the model lectures instead of guiding and 70 % of first turns contain a false statement (parent: 76 %; score 3.26 vs 3.24 of 10) (likely because dialogue rows were trained mostly toward the 7B teacher, not the human tutors' text). QAT ran 100 of 362 steps. Judges are LLM graders, a proxy for human judges. A post-delivery code review found false-accept paths in the answer verifier: re-running the corrected verifier bounds wrong answers in the main corpus at ≈0.03 % (a lower bound; ≤ ≈10 % on the orca rows, by hand-check only); 2/100 GSM8K and 1/500 ARC evaluation items have near-duplicates in the training pools, and excluding them leaves the gaps unchanged.

**Next, with a GPU:** finish QAT from the published checkpoint; retrain dialogue rows on the human text only, at a larger share; regenerate the skipped QASC misses. Full record: `RESULTS.md`, `docs/compression-pipeline-results.md`, `bench/measurements/{compress-20260919,refine-20260920}/`.


</details>

<details>
<summary><strong>Model Provenance</strong></summary>

</details>