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
- Fixed Manim arguments: `--silent -qm --format mp4 --disable_caching`, fixed
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
| `animation-studio-manim-source.txt` | `92be2b9c0b4ae000ecb81e49937c0a5c7c9d78382dab626f72eb18f4228fc3fe` | Exact trusted source |
| `animation-studio-manim-math.mp4` | `e4222e09eefc7d40442d20728e0f5b75c9b75ed1536906c2cd41833f864fc0c7` | Final rendered H.264 video |
| `animation-studio-manim-contact.png` | `4f99a2df3914c6f4ef47900f6813eaf45ba0c5f4f8fc8c084c904f9799c865db` | One-second visual sampling across the complete video |
| `animation-studio-manim-long-copy.png` | `6c3443c565ce0d3dd3a4b04294b3c17d7a02e8b5f4b0f6a0cf327e57d6e73d74` | Long title/caption and short process-label layout |

`ffprobe` result for the final MP4:

```text
codec_name=h264
width=1280
height=720
r_frame_rate=30/1
duration=9.325977
size=514455
```

Visual inspection confirmed parameter-correct partitioning/shading, progressive dot-array build,
repeated addition, labelled numeric axes/domain, clean `y = x^3` typesetting, cubic shape and origin
crossing, tangent at input two, bounded signed area, readable wrapped titles/captions, and no frame
clipping.

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
