# IDX Orderbook Analysis — Integration Guide

## Usage Patterns

### 1. CLI (Direct)
```bash
~/.hermes/hermes-agent/venv/bin/python3.11 orderbook_pipeline.py screenshot.png
```
**Best for:** Quick analysis, scripting, cron jobs

### 2. Hermes Skill Trigger
```bash
hermes run "analisa saham ini" --image screenshot.png
```
**Best for:** Integrated workflows, Hermes automation

### 3. Telegram Bot (Manual Integration)

#### Option A: Simple Curl Wrapper
```bash
#!/bin/bash
IMAGE=$1
CHAT_ID="123456789"
BOT_TOKEN="YOUR_BOT_TOKEN"

python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/orderbook_pipeline.py "$IMAGE" --output /tmp/result.md

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d text="$(head -100 /tmp/result.md)" \
  -d parse_mode="Markdown"
```

#### Option B: Hermes Telegram Plugin
```bash
hermes plugins install telegram
hermes config set telegram.bot_token "YOUR_BOT_TOKEN"
hermes config set telegram.chat_id "123456789"
hermes restart
```

Then trigger via Telegram message: "analisa saham ini" + image

#### Option C: python-telegram-bot (Full Control)
See `scripts/telegram_orderbook_bot.py` template for complete bot implementation.

### 4. Webhook / API Server
Wrap pipeline in Flask/FastAPI for HTTP endpoint:
```python
from flask import Flask, request
from orderbook_pipeline import OrderbookPipeline

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze():
    image = request.files['image']
    image.save('/tmp/upload.png')
    
    pipeline = OrderbookPipeline()
    result = pipeline.run('/tmp/upload.png', output_format='json')
    
    return result
```

## Trigger Phrases (Hermes)

- "analisa saham ini" + [image]
- "orderbook [TICKER]" + [image]
- "sell or keep [TICKER]" + [image]
- "update IRRA/KAEF/etc" + [image]
- "analisa orderbook screenshot" + [image]

## Output Formats

- **Markdown** (default): Human-readable report with tables
- **JSON**: Machine-readable, includes all intermediate results

## Common Workflows

### Workflow 1: Single Screenshot Analysis
```bash
python3.11 orderbook_pipeline.py screenshot.png --output report.md
cat report.md
```

### Workflow 2: Portfolio Position Tracking
```bash
# Create portfolio.json
echo '{"avg_price": 168, "lot": 3, "pemantauan_khusus": false}' > portfolio.json

# Analyze with portfolio context
python3.11 orderbook_pipeline.py screenshot.png --portfolio portfolio.json
```

### Workflow 3: Delta Tracking (Multiple Snapshots)
```bash
# First snapshot
python3.11 orderbook_pipeline.py snap1.png --output snap1.json --format json

# Second snapshot (later)
python3.11 orderbook_pipeline.py snap2.png --prev-snapshot snap1.json --output snap2.md
```

### Workflow 4: Batch Analysis
```bash
for img in screenshots/*.png; do
  python3.11 orderbook_pipeline.py "$img" --output "${img%.png}.md"
done
```

## Troubleshooting

### "No such file or directory" errors
- Ensure you're running from skill directory or use absolute paths
- Python path must be: `~/.hermes/hermes-agent/venv/bin/python3.11`

### Low confidence (<70%)
- Check image quality (dark mode, contrast, rotation)
- Use `--save-intermediate` to inspect preprocessing steps
- Consider manual verification

### OCR misreads (TACO, 7AS7)
- Validator flags these automatically
- Check validation report for confidence score
- Preprocessing may help (contrast, denoise)

### Missing dependencies
```bash
# Ensure all packages installed in venv
~/.hermes/hermes-agent/venv/bin/pip install pytesseract opencv-python-headless pillow
```

## Performance Notes

- **Preprocessing**: ~500ms (image I/O + CLAHE)
- **OCR**: ~2-3s (Tesseract on typical orderbook)
- **Analysis**: ~100ms (calculations)
- **Total**: ~3-4s per screenshot

For batch processing, consider parallelization or caching.

## Session-Specific Notes (2026-05-11)

- Tested with real screenshot (ANALY): confidence 74.9%, all 3 tiers generated
- Ground truth validation: KAEF (heavily bearish), IRRA (bearish), FIRE (neutral), WBSA (sell verdict)
- All 5 pipeline components tested and passing
- Preprocessing handles dark mode mobile screenshots correctly
