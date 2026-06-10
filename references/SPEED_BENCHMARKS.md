# Speed Benchmarks

## Pipeline Speed (Local — No Vision API)

| Mode | Total Time | vs File Mode | Notes |
|------|-----------|--------------|-------|
| `pipeline_v2.py --json-input file.json` | 196ms | baseline | Writes JSON to temp file, Python subprocess reads it |
| `pipeline_stdin.py` (pipe) | 71ms | **2.5x faster** | Skip file I/O, pipe JSON directly |
| Python startup only | 50ms | — | Just `python3 -c ""` (base overhead) |

**Bottleneck:** Python subprocess startup (~50ms) + JSON deserialization (~20ms). Stdin mode already minimizes this.

## End-to-End (Vision API + Pipeline)

| Workflow | Total Time | Steps |
|----------|-----------|-------|
| **PREFERRED** Hermes `vision_analyze` → pipe `pipeline_stdin.py` | **~1.5-2.5s** | 2 steps |
| `pipeline_v2.py --engine vision` on image | ~2-4s | 1 step but less reliable |
| `pipeline_v2.py --engine fast-ocr` on image | ~4-6s | 1 step, lower accuracy |

## PREFERRED Hermes Workflow (Fastest + Most Reliable)

```
User sends screenshot
    → Hermes calls vision_analyze(image) 
      [~1-2s, structured JSON extraction]
    → pipe JSON string to pipeline_stdin.py --caveman
      [~71ms analysis + formatting]
    → output formatted report to Telegram
      [~0ms — inline]
Total: ~1.5-2.5s
```

This beats `--engine vision` mode because:
1. Hermes' vision call is more reliable than pipeline's internal OpenAI call
2. Two-step avoids a single point of failure
3. Stdin pipe is 2.5x faster than file mode

## Bash Aliases (Speed Ranked)

| Alias | Command | Speed | 
|-------|---------|-------|
| `ob-pipe-c` | `pipeline_stdin.py --caveman` | Fastest (71ms) — needs JSON input |
| `ob-v` | `pipeline_v2.py --engine vision` | Fast image-to-report (~0.5-2s vision) |
| `ob-fast` | Vision + caveman + history | Best daily-use (~1s) |
| `ob-c` | `pipeline_v2.py --caveman` | Auto-select engine (~1-18s) |
