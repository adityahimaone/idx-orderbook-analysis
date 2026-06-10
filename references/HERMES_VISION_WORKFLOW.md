# Hermes Vision Workflow for Orderbook Analysis

When user sends an orderbook screenshot in Telegram/chat, the optimal flow is:

## Flow

1. **Vision extract** — call `vision_analyze` with structured JSON prompt
2. **Save to temp JSON** — write extracted data to `/tmp/<ticker>_vision.json`
3. **Run pipeline_v2 with --json-input** — skip OCR entirely

## Step 1: Vision Prompt

```python
vision_analyze(
    image_url="/path/to/screenshot.jpg",
    question="""Extract the COMPLETE orderbook data. Return STRICT JSON:
{
  "ticker": "string",
  "last_price": int,
  "change": int,
  "change_percent": float,
  "header": {"open": int, "high": int, "low": int, "prev": int, "ARA": int, "ARB": int, "avg": int, "lot": "string", "val": "string"},
  "orderbook": {
    "bids": [{"freq": int, "lot": int, "price": int}],
    "asks": [{"price": int, "lot": int, "freq": int}],
    "totals": {"bid_freq": int, "bid_lot": int, "ask_lot": int, "ask_freq": int}
  }
}
Ensure bid prices sorted descending, ask prices sorted ascending."""
)
```

## Step 2: Critical — Footer Totals

The `totals` section is **critical**. Footer shows ALL queued orders, not just visible 10-13 levels.
Without totals, ratio calculation uses only visible levels and can be INVERTED.

Example: TPIA 2026-06-10
- Visible bids (13 levels): 215K lot → visible ratio 1.56x (bullish)
- Footer totals: 850K bid vs 1,572K ask → actual ratio 0.54x (BEARISH)

## Step 3: Run Pipeline

```bash
python3.11 pipeline_v2.py --json-input /tmp/tpia_vision.json --caveman
```

## Fallback: Manual Analysis

If pipeline_v2 fails (import errors, missing deps), do manual analysis from extracted data:

1. Ratio = total_bid_lot / total_ask_lot (use FOOTER totals)
2. Freq ratio = total_freq_bid / total_freq_ask
3. Divergence = (last_price - avg) / avg × 100%
4. Identify walls: levels with lot > 2.5× average of visible levels
5. Check freq on walls: high freq (100+) = genuine
6. Determine phase from price position vs avg + wall behavior
7. Count entry conditions (5/5 system)
8. Check red flags before recommending

## Data Structure Mapping

| Vision Output | _standardize() → Analyzer Input |
|---|---|
| `last_price` | `price` |
| `header.ARA` | `ara` |
| `header.ARB` | `arb` |
| `header.lot` ("14.98M") | `volume_lot` (parsed to int) |
| `orderbook.bids` | `bids` |
| `orderbook.asks` | `asks` |
| `orderbook.totals.bid_lot` | `total_bid_lot` (overrides visible sum) |
| `orderbook.totals.ask_lot` | `total_ask_lot` (overrides visible sum) |
