# Incumbent chat-template packaging

The requested `qwen35_judge_hybrid.jinja` is embedded as
`tokenizer.chat_template` in the packaged GGUF
`Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-qwen35-judge-hybrid.gguf`.

The incumbent remains unchanged. The output has the same 338 tensors and the
same tensor-only SHA256; only the chat-template metadata changed. The output
was loaded by llama.cpp without an external template override and passed the
single-turn and multi-turn smoke requests. Exact hashes are in
[`chat-template-embedding-receipt.json`](chat-template-embedding-receipt.json)
and [`chat-template-hf-upload.json`](chat-template-hf-upload.json).

The template is Qwen3.5-oriented while the weights/tokenizer are Qwen2.5, so
this is a mechanically validated candidate, not an automatic replacement for
the incumbent. Use the existing matched quality suites before promotion.
