# IDX Orderbook Analysis

Complete orderbook analysis pipeline for IDX stocks. From screenshot → OCR → analysis → 3-tier recommendations.

## Quick Start

```bash
# Basic analysis
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png

# With portfolio position
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png --portfolio portfolio.json

# With delta tracking
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png --prev-snapshot prev.json

# Save intermediate results
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png --save-intermediate

# JSON output
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png --format json --output result.md
```

## Features

### Phase 1: Preprocessing
- Dark mode detection and inversion
- Contrast enhancement (CLAHE)
- Rotation/skew correction
- Denoise for screen refresh artifacts
- Auto-crop header vs orderbook table

### Phase 2: Validation
- Confidence threshold (70%)
- Price sanity checks (detect absurd values like 1134118)
- Ticker artifact handling (TACO, 7AS7 misreads)
- Lot spike detection
- ARA/ARB consistency checks

### Phase 3: Analysis
- Wall detection with lot/freq ratio
- Smart money detection (institutional vs retail)
- Bid/ask imbalance with proven thresholds
- Support/resistance identification
- Momentum scoring (0-100)

### Phase 4: Recommendations
- **Aggressive**: Entry near current price, 1:1-1.2:1 R/R
- **Moderat**: Entry at pullback, 1.5:1-1.8:1 R/R
- **Low Risk**: Entry at strong support, 2:1-2.5:1 R/R (priority tier)
- Sell/Keep/Hold verdict for existing positions

### Phase 5: Tracking
- Delta comparison between snapshots
- Distribution pattern detection
- Trend analysis (bid/ask ratio, momentum, volume)

### Phase 6: Output
- Markdown report with tables
- JSON export for automation

## Portfolio File Format

```json
{
  "avg_price": 168,
  "lot": 3,
  "pemantauan_khusus": false
}
```

## Testing

Run test suite with ground truth data:

```bash
~/.hermes/hermes-agent/venv/bin/python3.11 test_runner.py
```

Test cases:
- KAEF 09:15 (heavily bearish, ratio 3.41)
- IRRA 09:18 (bearish, ratio 1.63)
- FIRE 09:19 (neutral, ratio 1.05)
- WBSA 09:30 (sell verdict, IEP at ARB)

## Individual Components

### Preprocessor
```bash
python3.11 orderbook_preprocessor.py screenshot.png -o preprocessed.png --debug
```

### Validator
```bash
python3.11 orderbook_validator.py ocr_output.json --debug
```

### Analyzer
```bash
python3.11 orderbook_analyzer.py validated_data.json --debug
```

### Recommendation Engine
```bash
python3.11 recommendation_engine.py analysis.json --portfolio portfolio.json --debug
```

### Tracker
```bash
python3.11 orderbook_tracker.py snapshot1.json snapshot2.json snapshot3.json --debug
```

### Formatter
```bash
python3.11 output_formatter.py pipeline_result.json --format markdown --output report.md
```

## Output Example

```markdown
# Analisis Orderbook KAEF — 09:15

## Data Utama
| Metric | Value |
|--------|-------|
| Ticker | KAEF |
| Time | 09:15 |
| Prev | 635 |
| ARA | 790 |
| ARB | 540 |
| Avg | 699 |

## Analisis Teknikal
- **Rasio**: 3.41 → 🔴 **HEAVILY_BEARISH** (score 12/100)
- **Tembok Ask**: 🏛️ 790 (33,750 lot, strength 95/100)
- **Support Bid**: 760 (4,004 lot, strength 78/100)
- **Smart Money**: 1 institutional signal(s) detected
- **Konteks**: Weak momentum, caution advised

## Rekomendasi

### 🚀 Aggressive
- **Entry**: 534 - 540
- **TP**: 790
- **SL**: 745
- **R/R**: 1.18:1

### ⚖️ Moderat
- **Entry**: 768 - 783
- **TP**: 665
- **SL**: 738
- **R/R**: 1.52:1

### 🛡️ Low Risk (Priority)
- **Entry**: 752 - 768
- **TP1**: 745
- **TP2**: 790
- **SL**: 730
- **R/R**: 2.31:1
  - Entry at strongest support wall (752-768)
  - Wall strength: 95/100
  - Institutional support detected
  - Wall lot: 33,750 (1,245 freq)
```

## Dependencies

- Python 3.11+
- Tesseract 5.3.4+ (system package)
- OpenCV (python3-opencv)
- Pillow (python3-pil)
- pytesseract
- EasyOCR (optional, for improved accuracy)

## Notes

- Always use `~/.hermes/hermes-agent/venv/bin/python3.11` for execution
- Dark mode mobile screenshots require inversion preprocessing
- Confidence threshold: <70% → flag for manual verification
- Price sanity: detect absurd values (e.g., 1134118)
- Artifact handling: TACO, 7AS7 misreads

## Ground Truth

Based on live trading sessions:
- KAEF (09:15, 09:17) — heavily bearish distribution
- IRRA (09:18, 09:41, 10:33) — gradual distribution pattern
- FIRE (09:19) — neutral with strong bid wall
- WBSA (09:30) — sell verdict (IEP at ARB + Pemantauan Khusus)

## Version

v1.0.0 — Initial release (2026-05-11)
