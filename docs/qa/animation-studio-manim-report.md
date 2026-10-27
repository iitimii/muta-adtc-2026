# Trusted Manim render evidence

Date: 2026-10-27  
Source branch: `codex/studio-animation-workspace`  
Base source: `cc5dde310633b676ed7062e32dc18db30e0ce75a`

## Runtime contract exercised

- Manim: offline 0.22 runtime at `/tmp/muta-manim-feasibility.ODFfkv/arm64`
- Entry point: `bin/manim`
- FFmpeg: `/opt/homebrew/bin/ffmpeg`
- Gateway configuration: `MUTA_MANIM_RUNTIME_DIR`, `MUTA_MANIM_BIN`, and
  `MUTA_MANIM_FFMPEG_BIN`
- Fixed Manim arguments: `--silent -ql --format mp4 --disable_caching`, fixed
  `MutaLesson` scene, fresh temporary media directory
- Network mode during real-app QA: `MUTA_OFFLINE=1`, `HF_HUB_OFFLINE=1`, and
  `TRANSFORMERS_OFFLINE=1`

The checked-in source fixture is the exact server-emitted source used for the checked-in MP4.
It contains fraction partition/shade, multiplication-array build/addition, cubic graph,
derivative/tangent, and definite-integral scenes. The browser generated the same cubic family from
`Plot y = x^3 and show the tangent at x = 2`, displayed the trusted source, and completed
`POST /v1/animation/render` with HTTP 200. Browser console warnings/errors: zero.

## Artifacts and hashes

| Artifact | SHA-256 | Evidence |
|---|---|---|
| `animation-studio-manim-source.txt` | `6b1672c5081d78da872381c4e1eed597078afa007935ee92508e21c767ae5773` | Exact trusted source |
| `animation-studio-manim-math.mp4` | `7340d5c993c9483c61e69d9835f28023c02e6dcb2fc848e2c5cb78ee39936250` | Final rendered H.264 video |
| `animation-studio-manim-contact.png` | `fffde9fd6ec8a87447919eb6737d3a2523782f9f96288fbc3bcf78b4536077ee` | One-second visual sampling across the complete video |
| `animation-studio-manim-long-copy.png` | `bbbea68ad6cd4cbb757f91147e9f4776d5024d32eb1acc5ff036ee069362f5e7` | Long title/caption and short process-label layout |

`ffprobe` result for the final MP4:

```text
codec_name=h264
width=854
height=480
r_frame_rate=15/1
duration=9.800000
size=268956
```

Visual inspection confirmed parameter-correct partitioning/shading, progressive dot-array build,
repeated addition, labelled numeric axes/domain, cubic shape and origin crossing, tangent at input
two, bounded signed area, readable wrapped titles/captions, and no frame clipping.

## Safety and failure probes

- Model/user strings remain Python constants routed only to Manim text objects.
- Typed expression text must parse to the same AST and use exactly the declared variable.
- An absolute-value cusp at zero is rejected as an undefined derivative.
- A pole inside a requested integral is rejected as non-convergent.
- Smooth stationary points such as the derivative of `x^2` at zero are accepted.
- Undefined curve samples become segment gaps rather than zero values.
- A second concurrent render receives immediate busy admission instead of queueing.
- Client cancellation and timeout terminate the complete worker process group.
- Final output selection accepts exactly one `MutaLesson.mp4` outside Manim partial files.
