# Packaging records

The current artifact is the vocabulary-pruned
`Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-vocab32k.gguf`. Its post-export pruning
receipt is in [`../pruning/vocab32k-prune-receipt.json`](../pruning/vocab32k-prune-receipt.json).

The files in this directory document a separate experiment: embedding
`qwen35_judge_hybrid.jinja` as `tokenizer.chat_template` in
`Muta-Tutor-Qwen2.5-1.5B-Q4_K_M-qwen35-judge-hybrid.gguf`. That candidate
preserved the 338 tensors and changed metadata only. It is not the current
model, and the Qwen3.5-oriented template was not treated as a new fine-tune.
The exact conversion and smoke-test details are in
[`chat-template-embedding-receipt.json`](chat-template-embedding-receipt.json)
and [`chat-template-hf-upload.json`](chat-template-hf-upload.json).
