# OCR Confidence Reporting Pitfalls

## Session: 2026-05-11 (Telegram orderbook analysis)

### Issue: Inconsistent confidence reporting and incomplete data extraction

**Observed behavior:**
1. `telegram_production.py` reports 100% confidence but extracts incomplete data
2. `orderbook_pipeline.py` reports lower confidence (49-71%) with more complete extraction
3. Ticker detection inconsistent: "ANALY" appears as fallback when actual tickers are OGRA, CORN, etc.

**Examples from session:**

```
Image 1 (img_4cbae13ccc7d.jpg):
- telegram_production: confidence N/A, ticker None, no orderbook data
- orderbook_pipeline: confidence 79.1%, ticker "ANALY", full 10-level orderbook extracted

Image 2 (img_640beb6112e6.jpg):
- telegram_production: confidence 100%, ticker "OGRA", incomplete data (only header)
- orderbook_pipeline: confidence 49.1%, ticker "ANALY", only 1 bid/ask level

Image 3 (img_c9e9051cd7e0.jpg):
- telegram_production: confidence 100%, ticker "CORN", incomplete data
- orderbook_pipeline: confidence 70.7%, ticker "ANALY", full orderbook but questionable accuracy
```

### Root Cause Analysis

1. **Fast OCR confidence calculation** may be optimistic when it successfully reads header fields (ticker, time, prev/high/low) but fails on orderbook table structure
2. **"ANALY" ticker artifact** suggests OCR misreading or a default fallback value in the pipeline
3. **Hybrid mode threshold (70%)** triggers fallback, but fallback doesn't always improve results

### Recommendations

**For users:**
- Don't trust confidence scores alone — verify ticker name matches expectation
- If ticker shows "ANALY" or other nonsense, screenshot quality is poor
- Look for "MANUAL VERIFICATION REQUIRED" flag in output
- Best results: landscape orientation, zoom on orderbook table, avoid glare

**For skill maintenance:**
1. Add ticker validation: reject results where ticker is "ANALY" or doesn't match IDX format (4 letters, all caps)
2. Add structural validation: count extracted bid/ask levels, flag if < 5 levels per side
3. Separate confidence metrics:
   - Header confidence (ticker, time, OHLC)
   - Orderbook confidence (bid/ask table structure)
   - Overall confidence (weighted average)
4. Add post-OCR sanity checks:
   - Prices should be monotonic (bid descending, ask ascending)
   - Spread should be reasonable (< 5% of price)
   - No absurd values (e.g., 4950 bid when other bids are 150-186)

### Quick Fix Pattern

When confidence is reported but data is incomplete:

```python
# After OCR extraction, before analysis
def validate_orderbook_structure(ocr_data):
    issues = []
    
    # Check ticker
    ticker = ocr_data.get("ticker", "")
    if not ticker or ticker == "ANALY" or len(ticker) != 4:
        issues.append("Invalid ticker")
    
    # Check orderbook depth
    bid_levels = len(ocr_data.get("bid", []))
    ask_levels = len(ocr_data.get("ask", []))
    
    if bid_levels < 5 or ask_levels < 5:
        issues.append(f"Incomplete orderbook: {bid_levels} bid, {ask_levels} ask levels")
    
    # Check price monotonicity
    bids = [b["price"] for b in ocr_data.get("bid", [])]
    asks = [a["price"] for a in ocr_data.get("ask", [])]
    
    if bids != sorted(bids, reverse=True):
        issues.append("Bid prices not monotonic descending")
    
    if asks != sorted(asks):
        issues.append("Ask prices not monotonic ascending")
    
    return issues

# Adjust confidence based on structural issues
if issues:
    confidence *= 0.5  # Halve confidence if structural problems detected
    metadata["validation_warnings"] = issues
```

### User Preference

When analysis fails or produces low-confidence results, user expects:
- Clear indication that data is unreliable
- Suggestion to retake screenshot with better quality
- No false confidence (don't say 100% when orderbook is incomplete)

## Related

- See `SPEED_OPTIMIZATION.md` for fast vs full OCR tradeoffs
- See `TEST_INFRASTRUCTURE.md` for ground truth validation patterns
