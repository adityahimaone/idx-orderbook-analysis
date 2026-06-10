---
name: idx-orderbook-analysis
description: |
  Analyze IDX stock orderbook from screenshot. Extracts data via OCR, calculates bid/ask imbalance, 
  detects walls, and generates 3-tier entry recommendations. Includes preprocessing for mobile screenshots,
  confidence validation, and smart money detection.
version: 1.0.0
author: adit
metadata:
  hermes:
    tags: ["Stock", "Trading", "Orderbook", "Analysis", "IDX", "OCR", "Technical Analysis"]
  depends_on: ["stock-orderbook-analysis"]
triggers:
  - "analisa orderbook"
  - "analisis orderbook"
  - "analisa saham"
  - "analisis saham"
  - "orderbook"
  - "screening orderbook"
  - "scan orderbook"
  - "check orderbook"
  - "cek orderbook"
  - "orderbook [TICKER]"
  - "analisa [TICKER]"
  - "analisis [TICKER]"
  - "gimana [TICKER]"
  - "entry [TICKER]"
  - "buy [TICKER]"
  - "layak beli [TICKER]"
  - "sell or keep [TICKER]"
  - "vision orderbook"
  - "batch orderbook"
  - "history orderbook"
  - "caveman orderbook"
  - "fase [TICKER]"
  - "red flag [TICKER]"
  - "entry condition [TICKER]"
  - "delta [TICKER]"
  - "support resistance [TICKER]"
  - "rekomendasi [TICKER]"
---

# IDX Orderbook Analysis Skill v1.0

Comprehensive orderbook analysis pipeline for IDX stocks. From screenshot → OCR → analysis → 3-tier recommendations.

## Overview

This skill improves upon the existing `stock-orderbook-analysis` by adding:
1. **Mobile screenshot preprocessing** (contrast enhancement, rotation detection, dark mode inversion)
2. **Confidence & sanity validation** (detect absurd OCR values, flag low confidence)
3. **Enhanced wall detection** with lot/freq ratio analysis
4. **Smart money detection** (institutional vs retail patterns)
5. **3-tier recommendation engine** (Aggressive, Moderat, Low Risk)
6. **Delta tracking** between snapshots

## Architecture

```
[User Input: Screenshot]
        ↓
[Image Preprocessing] → contrast, rotation, dark mode inversion
        ↓
[OCR Extraction] → Tesseract (primary), EasyOCR (future)
        ↓
[Data Validation] → sanity checks, confidence scoring
        ↓
[Orderbook Analysis] → walls, imbalance, smart money, support/resistance
        ↓
[Recommendation Engine] → 3-tier entry with R/R ratios
        ↓
[Output Formatter] → markdown report with tables
```

## File Structure

```
~/.hermes/skills/finance/idx-orderbook-analysis/
├── SKILL.md                    ← This file
├── orderbook_preprocessor.py   ← Phase 1: image preprocessing
├── orderbook_validator.py      ← Phase 2: confidence + sanity checks
├── orderbook_ocr.py            ← OCR extraction (improved)
├── orderbook_analyzer.py       ← Phase 3: analysis engine
├── recommendation_engine.py    ← Phase 4: 3-tier recommendations
├── orderbook_tracker.py        ← Phase 5: delta tracking
├── output_formatter.py         ← Phase 6: markdown output
├── orderbook_pipeline.py       ← Orchestrator
└── tests/
    ├── test_kaef_0915.json     ← Ground truth from live sessions
    ├── test_irra_0918.json
    ├── test_fire_0919.json
    └── test_wbsa_0930.json
```

## Usage

### CLI
```bash
# Full pipeline
python3.11 orderbook_pipeline.py screenshot.png

# Step by step
python3.11 orderbook_preprocessor.py screenshot.png --output preprocessed.png
python3.11 orderbook_ocr.py preprocessed.png --json --engine tesseract
python3.11 orderbook_analyzer.py < ocr_output.json
```

### Python API
```python
from orderbook_pipeline import analyze_orderbook

result = analyze_orderbook("screenshot.png", portfolio_avg=168, portfolio_lot=3)
print(result["recommendations"]["low_risk"]["entry_range"])
```

## Output Format

Markdown report with:
- Orderbook summary table
- Bid/ask imbalance ratio
- Wall detection results
- Smart money signals
- 3-tier entry recommendations
- Sell/Keep/Hold verdict (if portfolio data provided)
- Delta comparison (if previous snapshot available)

## Dependencies

- Tesseract 5.3.4+ (system package)
- OpenCV (python3-opencv)
- Pillow (python3-pil)
- pytesseract (Python wrapper)
- EasyOCR (optional, for improved accuracy)

## Notes

- Always use `~/.hermes/hermes-agent/venv/bin/python3.11` for Python execution
- Dark mode mobile screenshots require inversion preprocessing
- Confidence threshold: <70% → flag for manual verification
- Price sanity: detect absurd values (e.g., 1134118)
- Artifact handling: TACO, 7AS7 misreads
- **Path resolution**: Scripts in `scripts/` directory reference files in `references/` via `script_dir.parent / "references"` pattern
- **Integration**: See `references/INTEGRATION_GUIDE.md` for Telegram, CLI, and API usage patterns
- **⚠️ Confidence pitfalls**: See `references/OCR_CONFIDENCE_PITFALLS.md` — fast OCR can report high confidence with incomplete data; validate ticker and orderbook structure before trusting results

## Pitfalls & Critical Bugs Fixed (v2.0.1)

### 1. Footer Totals vs Visible Sums (CRITICAL)
IDX broker apps show footer totals (all queued levels) that are MUCH larger than the sum of visible 10-13 levels. Always use footer totals for bid:ask ratio calculation. Without this, ratio can be inverted (e.g., 1.56x bullish when actual is 0.54x bearish).
- `total_bid_lot` / `total_ask_lot` fields passed through `_standardize()` → analyzer uses these when > 0

### 2. Nested vs Flat Data Format
Vision API extracts: `{header:{open,high,...}, orderbook:{bids,asks,totals}}`
Fast OCR extracts: `{open, high, bids, asks, ...}` (flat)
`_standardize()` in pipeline_v2.py handles both shapes. Check `header`, `orderbook`, `stats` nested dicts first, fall back to top-level keys.

### 3. Analysis Result Must Include Market Fields
`OrderbookPlanAnalyzer.analyze_snapshot()` must pass through: `price`, `high`, `low`, `avg`, `ara`, `arb`, `open`, `prev`, `volume_lot` into the result dict. Formatter + rec engine need these downstream.

### 4. --json-input Mode for Hermes Integration
When running from Hermes chat (vision extracts JSON mid-conversation), use:
```bash
python3.11 pipeline_v2.py --json-input /tmp/extracted.json --caveman
```
This skips OCR entirely and runs analysis → recs → format directly.

### 5. Volume String Parsing
Header `lot` field can be string ("14.98M") or numeric. `_standardize()` handles M/K suffixes with case-insensitive parsing.

### 6. Vision API Fallback (CRITICAL)
When `--engine vision` fails with "All OCR/vision engines failed" but the image is valid:
- The pipeline's built-in vision call can fail due to timing, provider rate limits, or image path issues
- **PREFERRED WORKFLOW:** Use Hermes `vision_analyze()` tool directly with a structured prompt asking for JSON → then pipe to `pipeline_stdin.py`
- This two-step approach is MORE reliable AND faster (~1.5-2.5s total) than relying on pipeline's internal vision call
- See `references/SPEED_BENCHMARKS.md` for the full workflow

### 7. Unified Caveman Template v2 (CRITICAL — DO NOT VARY)
Adit wants a SINGLE comprehensive template for ALL market conditions — no switching, no variant modes.
The caveman format is FIXED across all output — see `references/CAVEMAN_TEMPLATE_V2.md` for full spec with legend.

```
━━━ {TICKER} {PRICE} {EMOJI_TREND}{PCT_CHG}% | {TIME} ━━━
H:{HIGH} L:{LOW}{LOW_FLAG} Avg:{AVG}({DIV_PCT}%)
Vol:{VOL} Val:{VAL}

BID {BID_TOT}lot f{BID_FREQ}  ║  ASK {ASK_TOT}lot f{ASK_FREQ}
▬▬▬▬▬▬▬ {RATIO}x {RATIO_LABEL} ▬▬▬▬▬▬▬
FASE ░ {PHASE}  Cond:{COND}/5  Size:{SIZE}%

🟢 BID WALLS          🔴 ASK WALLS
{B1_PRC} │{B1_LOT}│f{B1_FRQ}  {A1_PRC} │{A1_LOT}│f{A1_FRQ} {A1_TAG}
{B2_PRC} │{B2_LOT}│f{B2_FRQ}  {A2_PRC} │{A2_LOT}│f{A2_FRQ}
FLOOR→{FL_PRC}│{FL_LOT}{FL_DIR}│f{FL_FRQ}

CONDITIONS [LR]
{C1} Wall bid hold/tebal    {C2} Harga flat di low
{C3} Candle reversal        {C4} Volume spike naik
{C5} Bid naik 2+ snapshot

▸ AGG  {AGG_STATUS}
       E:{A_E} SL:{A_SL} TP1:{A_T1} TP2:{A_T2} RR:{A_RR}x
▸ MOD  E:{M_E} SL:{M_SL} TP1:{M_T1} TP2:{M_T2} RR:{M_RR}x
▸ LR   E:{L_E} SL:{L_SL} TP1:{L_T1} TP2:{L_T2} RR:{L_RR}x
       SL-dist:{L_SLD}pt | TP1-dist:{L_T1D}pt

⚡ DELTA (vs {PREV_TIME})
   Price {D_PRC} │ Low {D_LOW} │ Vol {D_VOL}
   Bid {D_BID} │ Ask {D_ASK} │ Ratio {D_RAT}
   Wall {D_WALL_NAME}: {D_WALL_CHG}

⚠️ {ALERT_MSG}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Key changes from v1 template:
- Full market data header (H/L/Avg/Vol/Val)
- Bid/Ask with total lot + freq (not just ratio)
- 3 bid walls + 3 ask walls displayed (not just floor/ceil)
- Wall direction flags: ↑↓⚡✂️ per snapshot delta
- TP split into TP1 + TP2 per tier
- SL-dist + TP1-dist in points
- Conditions as individual checklist (✅⏳❌) not just count
- Delta section with Price/Low/Vol/Bid/Ask/Wall changes
- AGG status: SKIP/VALID/PARTIAL with reason
- Size rule table: 0-1→0%, 2→30%, 3→50%, 4→75%, 5→100%

DO NOT:
- Skip tiers when red flags are present — tiers are ALWAYS generated
- Vary the format based on market condition — single template always
- Omit the DELTA section when prev snapshot exists in history DB

### 8. Recommendation Engine Always Generates Tiers
Previously `recommendation_engine_v2.py` returned early with `return result` on red flags, skipping all tier generation. This was WRONG — Adit wants tier data (entry/tp/sl) even when market is bearish or red flags active. The engine now marks `red_flag_warning` but still generates all 3 tiers. The formatter's Blocker line communicates viability.

### 9. pipeline_stdin.py — Fastest Local Mode
Script `pipeline_stdin.py` reads JSON from stdin (no file I/O). Benchmark:
- `--json-input` (file): **196ms**
- `stdin` (pipe): **71ms**
Use this when piping vision output directly in Hermes. Available via `ob-pipe` and `ob-pipe-c` bash aliases.

## Support Files

- `references/README.md` — Quick start and feature overview
- `references/INTEGRATION_GUIDE.md` — CLI, Telegram, API, and webhook usage patterns
- `references/TEST_INFRASTRUCTURE.md` — Test runner pattern and ground truth validation
- `references/SPEED_BENCHMARKS.md` — Pipeline speed benchmarks, vision fallback workflow, stdin vs file comparison
- `references/CAVEMAN_TEMPLATE_V2.md` — Comprehensive compact template v2 with full spec, legend, examples, and v1→v2 diff
- `references/SPEED_OPTIMIZATION.md` — Historical speed optimization notes (deprecated, superseded by SPEED_BENCHMARKS.md)
- `references/fast-ocr-improvements-2026-05-11.md` — Fast OCR ticker detection and number parsing improvements (79% → 100% confidence)
- `references/test_kaef_0915.json` — Ground truth: KAEF heavily bearish (ratio 3.41)
- `references/test_irra_0918.json` — Ground truth: IRRA bearish (ratio 1.63)
- `references/test_fire_0919.json` — Ground truth: FIRE neutral (ratio 1.05)
- `references/test_wbsa_0930.json` — Ground truth: WBSA sell verdict (IEP at ARB)
- `templates/portfolio_example.json` — Portfolio position template
- `scripts/test_runner.py` — Complete test suite (5 components, all passing)

## Pipeline v2 — Plan.md Complete Implementation

### New Scripts (v2)

| Script | Purpose |
|--------|---------|
| `scripts/orderbook_analyzer_v2.py` | Full plan.md analysis engine (all 13 sections) |
| `scripts/recommendation_engine_v2.py` | Plan.md 3-tier entry with condition counter + sizing |
| `scripts/output_formatter_v2.py` | Telegram-friendly report + caveman 1-liner |
| `scripts/pipeline_v2.py` | Master pipeline (OCR/Vision → Analysis → Recs → Report) |
| `scripts/orderbook_history.py` | SQLite wall persistence + batch parallel scanner |
| `scripts/orderbook_vision.py` | Vision API extraction (skip OCR entirely) |

### Usage (v2)

```bash
cd ~/.hermes/skills/finance/idx-orderbook-analysis/scripts

# Full pipeline (auto engine selection)
python3.11 pipeline_v2.py screenshot.png

# JSON input mode (skip OCR — feed pre-extracted vision data)
python3.11 pipeline_v2.py --json-input extracted_data.json

# STDIN pipe mode (fastest: 71ms — skip file I/O)
cat data.json | python3.11 pipeline_stdin.py --caveman

# Vision mode (fastest image-to-report)
python3.11 pipeline_v2.py screenshot.png --engine vision

# With delta tracking (compare to previous)
python3.11 pipeline_v2.py screenshot.png --prev previous_analysis.json

# Save to history DB + caveman output
python3.11 pipeline_v2.py screenshot.png --save-history --caveman

# Batch scan (parallel)
python3.11 orderbook_history.py batch img1.png img2.png img3.png --parallel 3

# Wall persistence check
python3.11 orderbook_history.py history TPIA --hours 6
```

### What v2 Adds Over v1

| Feature | v1 | v2 |
|---------|----|----|
| Bid:Ask Ratio | Basic ratio | 6-tier classification with warnings |
| Freq Ratio | Not separate | Standalone metric + freq-vs-lot analysis |
| Avg Divergence | Not calculated | Full divergence % with 4 categories |
| Wall Classification | By lot size | 4 types by proximity (Bid/Ask/Mega Bid/Mega Ask) |
| Wall Genuine Check | Not available | Score 0-100, cross-snapshot persistence |
| Phase Identification | Not available | 5 phases with confidence + strategi |
| Delta Signals | Basic compare | 10+ specific bullish/bearish/reversal signals |
| Entry Conditions | Not available | 5-condition counter with sizing rules |
| Red Flags | Not available | 6 abort conditions (auto-skip) |
| IHSG Context | Partial (ARA/ARB) | Full: session zones, ARA proximity, lot tiers |
| Dynamic S/R Flip | Not available | Detects broken levels → flip |
| SQLite History | Not available | Wall persistence tracking across sessions |
| Batch Scanning | Not available | Parallel multi-ticker (3 workers) |
| Vision API | Not available | Skip OCR entirely, use Claude/GPT vision |
| Caveman Output | Separate tool | Built-in 1-liner compact mode |

### Speed Comparison

| Engine | Time | Accuracy | Use When |
|--------|------|----------|----------|
| Vision API | ~0.5-2s | 90%+ | Default for Telegram (fastest UX) |
| Fast OCR | ~1.5s | 50-70% | Fallback if vision fails |
| Full OCR | ~18s | 95% | When high accuracy needed + time OK |
| Batch (3x) | ~3s total | Mixed | Screening multiple tickers |

## GitHub Repository

Published at: https://github.com/adityahimaone/idx-orderbook-analysis
Contains full docs, plan.md methodology, v1+v2 scripts, tests, and templates.

## Bash Aliases (VPS)

Configured in `~/.bash_aliases` — prefix `ob-*`:

| Alias | Action |
|-------|--------|
| `ob [FILE]` | Full pipeline (auto engine) |
| `ob-v [FILE]` | Force Vision API (fastest) |
| `ob-c [FILE]` | Caveman compact output |
| `ob-sc [FILE]` | Save history + caveman (daily default) |
| `ob-fast [FILE]` | Vision + caveman + history (ultimate speed) |
| `ob-json [FILE]` | JSON input direct (skip OCR — pre-extracted data) |
| `ob-pipe` | STDIN pipe mode (fastest local: 71ms) |
| `ob-pipe-c` | STDIN pipe + caveman output |
| `ob-batch [FILES...]` | Parallel multi-ticker scan |
| `ob-hist [TICKER]` | Wall persistence check from SQLite DB |

## Keyword Routing (Telegram / Hermes Chat)

Specific keywords route to sub-functions:
- `fase [TICKER]` → phase identification only
- `red flag [TICKER]` → check abort conditions
- `entry condition [TICKER]` → count low-risk conditions (5/5)
- `delta [TICKER]` → multi-snapshot signal analysis
- `support resistance [TICKER]` → wall-based S/R mapping
- `rekomendasi [TICKER]` → 3-tier entry + sizing

## Changelog

- **v2.0.1** — Critical bugfixes: (1) Footer totals now override visible-level sums for ratio (was showing 1.56x bullish instead of actual 0.54x bearish) (2) `_standardize()` handles nested vision JSON `{header,orderbook}` and flat OCR formats (3) `analyze_snapshot()` now passes `price, high, low, avg, ara, arb, open, prev, volume_lot` through to result (4) Added `--json-input` mode for Hermes mid-conversation vision extract (5) Volume string parsing for "14.98M" format
- v2.0.0 — Complete plan.md implementation (all 13 sections): Phase ID, Freq Ratio, Avg Divergence, Wall Classification (4 types), Wall Genuine Score, Delta Signal Interpreter (10+ signals), Entry Condition Counter (5/5 system), Sizing Rules, Red Flags (6 abort), IHSG Context (sessions/ARA/lots), Dynamic S/R Flip, SQLite wall history, batch scanning, vision API mode
- v1.0.0 — Initial release with preprocessing, validation, enhanced analysis, and recommendation engine
- Based on live trading sessions: KAEF (09:15, 09:17), IRRA (09:18, 09:41, 10:33), FIRE (09:19), WBSA (09:30)
- All 5 pipeline components tested and validated
- Integration guide for CLI, Telegram, and API usage
- Test infrastructure pattern documented for reuse in other finance skills