#!/usr/bin/env python3
"""
Orderbook Analysis Pipeline v2 — Plan.md Complete Implementation
=================================================================

FULL pipeline: Screenshot → OCR/Vision → Plan.md Analysis → Recs → Report
Speed modes: ultra-fast (vision, ~0.5s) or precise (OCR, ~1.5s)

Usage:
    python3.11 pipeline_v2.py screenshot.png
    python3.11 pipeline_v2.py screenshot.png --engine vision
    python3.11 pipeline_v2.py screenshot.png --save-history
    python3.11 pipeline_v2.py screenshot.png --caveman  (compact 1-liner)
"""

import sys
import json
import os
import argparse
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

SKILL_DIR = Path.home() / ".hermes/skills/finance/idx-orderbook-analysis/scripts"


def _run_ocr(image_path: str, engine: str = "auto") -> Dict:
    """Run OCR on image, return parsed data."""
    use_fast = engine in ("auto", "ocr_fast")
    use_vision = engine == "vision"

    if use_vision:
        # Vision API path (fastest, best accuracy)
        vision_script = SKILL_DIR / "orderbook_vision.py"
        proc = subprocess.run(
            ["python3.11", str(vision_script), image_path],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            if data.get("bids") and len(data["bids"]) >= 3:
                return data

        # Fallback to fast OCR
        if engine == "auto":
            return _run_ocr(image_path, "ocr_fast")

    # Fast OCR (Tesseract, ~1.5s)
    ocr_script = SKILL_DIR / "orderbook_ocr_fast.py"
    proc = subprocess.run(
        ["python3.11", str(ocr_script), image_path, "--json"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode == 0:
        data = json.loads(proc.stdout)
        if data.get("bids") or data.get("asks"):
            return data

    # Full OCR as final fallback
    if engine in ("auto", "ocr"):
        full_ocr = SKILL_DIR.parent.parent / "stock-orderbook-analysis/scripts/orderbook_ocr.py"
        proc = subprocess.run(
            ["python3.11", str(full_ocr), image_path, "--json", "--engine", "tesseract"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout)

    raise RuntimeError("All OCR/vision engines failed — images corrupt or no orderbook visible")


def _standardize(ocr_data: Dict) -> Dict:
    """Map OCR/Vision output to standard format that analyzer_v2 expects.
    
    Handles multiple input shapes:
    - Vision API: {ticker, header:{open,high,low,...}, orderbook:{bids,asks,totals}}
    - Fast OCR: {ticker, open, high, low, bids, asks, ...}
    - Direct JSON: {ticker, last_price, header:{...}, orderbook:{bids, asks, totals}}
    """
    # Detect nested format (vision / Hermes extract)
    header = ocr_data.get("header", {})
    orderbook = ocr_data.get("orderbook", {})
    stats = ocr_data.get("stats", {})

    # Price: try multiple sources
    price = (
        ocr_data.get("last_price", 0)
        or header.get("last_price", 0)
        or ocr_data.get("price", 0)
        or ocr_data.get("open", 0)
        or header.get("open", 0)
        or stats.get("open", 0)
        or ocr_data.get("avg", 0)
        or header.get("avg", 0)
    )

    high = header.get("high", 0) or stats.get("high", 0) or ocr_data.get("high", 0)
    low = header.get("low", 0) or stats.get("low", 0) or ocr_data.get("low", 0)
    avg = header.get("avg", 0) or stats.get("avg", 0) or ocr_data.get("avg", 0)
    ara = header.get("ARA", 0) or header.get("ara", 0) or stats.get("ara", 0) or ocr_data.get("ARA", 0) or ocr_data.get("ara", 0)
    arb = header.get("ARB", 0) or header.get("arb", 0) or stats.get("arb", 0) or ocr_data.get("ARB", 0) or ocr_data.get("arb", 0)
    open_p = header.get("open", 0) or stats.get("open", 0) or ocr_data.get("open", 0)
    prev_p = header.get("prev", 0) or stats.get("prev", 0) or ocr_data.get("prev", 0)

    # Volume: handle string like "14.98M" or numeric
    vol_raw = header.get("lot", 0) or stats.get("total_lot_million", 0) or ocr_data.get("lot", 0) or ocr_data.get("volume_lot", 0)
    if isinstance(vol_raw, str):
        vol_raw = vol_raw.upper().replace(",", "")
        if "M" in vol_raw:
            vol_lot = int(float(vol_raw.replace("M", "")) * 1_000_000)
        elif "K" in vol_raw:
            vol_lot = int(float(vol_raw.replace("K", "")) * 1_000)
        else:
            vol_lot = int(float(vol_raw)) if vol_raw else 0
    else:
        vol_lot = int(vol_raw) if vol_raw else 0

    # Bids/Asks: nested or flat
    bids = orderbook.get("bids", []) or ocr_data.get("bids", [])
    asks = orderbook.get("asks", []) or ocr_data.get("asks", [])
    
    # Totals from footer (override visible-level sums — critical for accuracy)
    totals = orderbook.get("totals", {}) or ocr_data.get("totals", {})
    bid_total_override = totals.get("bid_lot", 0)
    ask_total_override = totals.get("ask_lot", 0)

    # Value: handle string like "2.97T" or numeric
    val_raw = header.get("val", 0) or stats.get("val", 0) or ocr_data.get("val", 0) or ocr_data.get("value", 0)
    if isinstance(val_raw, str):
        val_raw = val_raw.upper().replace(",", "")
        if "T" in val_raw:
            value = int(float(val_raw.replace("T", "")) * 1_000_000_000_000)
        elif "B" in val_raw:
            value = int(float(val_raw.replace("B", "")) * 1_000_000_000)
        elif "M" in val_raw:
            value = int(float(val_raw.replace("M", "")) * 1_000_000)
        else:
            value = int(float(val_raw)) if val_raw else 0
    else:
        value = int(val_raw) if val_raw else 0

    return {
        "ticker": ocr_data.get("ticker", "N/A"),
        "timestamp": ocr_data.get("timestamp", "") or datetime.now().strftime("%H:%M"),
        "price": price,
        "open": open_p,
        "prev": prev_p,
        "high": high,
        "low": low,
        "avg": avg,
        "ara": ara,
        "arb": arb,
        "volume_lot": vol_lot,
        "value": value,
        "bids": bids,
        "asks": asks,
        "total_bid_lot": bid_total_override,
        "total_ask_lot": ask_total_override,
        "totals": totals,
        "confidence": ocr_data.get("confidence", 0),
    }


def run_full_pipeline(image_path: str, prev_data: Optional[Dict] = None,
                      engine: str = "auto", save_history: bool = False,
                      output_json: Optional[str] = None) -> Dict:
    """
    Run full plan.md pipeline:
    1. OCR/Vision → 2. Plan.md Analysis → 3. Recommendations → 4. Report
    """
    total_start = time.time()
    timings = {}

    # Phase 1: OCR
    t0 = time.time()
    ocr_data = _run_ocr(image_path, engine)
    data = _standardize(ocr_data)
    timings["ocr"] = round(time.time() - t0, 2)

    # Phase 2: Analysis (v2)
    t0 = time.time()
    from orderbook_analyzer_v2 import OrderbookPlanAnalyzer
    analyzer = OrderbookPlanAnalyzer(debug=False)
    analysis = analyzer.analyze_snapshot(data, prev_data)
    timings["analysis"] = round(time.time() - t0, 2)

    # Phase 3: Recommendations
    t0 = time.time()
    from recommendation_engine_v2 import generate_tiers_planmd
    recs = generate_tiers_planmd(analysis)
    timings["recommendations"] = round(time.time() - t0, 2)

    # Phase 4: Format report
    t0 = time.time()
    from output_formatter_v2 import format_plan_report, format_caveman_summary
    report = format_plan_report(ocr_data, analysis, recs)
    caveman = format_caveman_summary(analysis, recs)
    timings["format"] = round(time.time() - t0, 2)

    timings["total"] = round(time.time() - total_start, 2)

    result = {
        "ocr_data": ocr_data,
        "analysis": analysis,
        "recommendations": recs,
        "report": report,
        "caveman": caveman,
        "timings": timings,
    }

    # Save to history DB
    if save_history:
        try:
            from orderbook_history import save_snapshot, init_db
            init_db()
            save_snapshot(analysis)
        except Exception as e:
            if "--debug" in sys.argv:
                print(f"[WARN] History save failed: {e}", file=sys.stderr)

    # Save JSON output if requested
    if output_json:
        # Strip report string from JSON to avoid duplication
        json_out = {k: v for k, v in result.items() if k not in ("report", "caveman")}
        with open(output_json, "w") as f:
            json.dump(json_out, f, indent=2)

    return result


def _run_from_json(ocr_data: Dict, prev_data: Optional[Dict] = None,
                   save_history: bool = False,
                   output_json: Optional[str] = None) -> Dict:
    """Run pipeline from pre-extracted JSON (skip OCR/Vision)."""
    data = _standardize(ocr_data)
    from orderbook_analyzer_v2 import OrderbookPlanAnalyzer
    from recommendation_engine_v2 import generate_tiers_planmd
    from output_formatter_v2 import format_plan_report, format_caveman_summary

    analysis = OrderbookPlanAnalyzer(debug=False).analyze_snapshot(data, prev_data)
    recs = generate_tiers_planmd(analysis)
    report = format_plan_report(ocr_data, analysis, recs)
    caveman = format_caveman_summary(analysis, recs)

    result = {
        "ocr_data": ocr_data,
        "analysis": analysis,
        "recommendations": recs,
        "report": report,
        "caveman": caveman,
    }

    if save_history:
        try:
            from orderbook_history import save_snapshot, init_db
            init_db()
            save_snapshot(analysis)
        except Exception as e:
            if "--debug" in sys.argv:
                print(f"[WARN] History save failed: {e}", file=sys.stderr)

    if output_json:
        with open(output_json, "w") as f:
            json.dump({k: v for k, v in result.items() if k not in ("report", "caveman")}, f, indent=2)

    return result


# ──────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Orderbook Pipeline v2 — Plan.md Complete Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3.11 pipeline_v2.py screenshot.png
  python3.11 pipeline_v2.py screenshot.png --engine vision
  python3.11 pipeline_v2.py screenshot.png --caveman
  python3.11 pipeline_v2.py screenshot.png --save-history
  python3.11 pipeline_v2.py screenshot.png --prev prev.json
""")
    parser.add_argument("image", nargs="?", help="Orderbook screenshot path")
    parser.add_argument("--json-input", help="Pre-extracted JSON file (skip OCR)")
    parser.add_argument("--engine", choices=["auto", "vision", "ocr_fast", "ocr"],
                        default="auto", help="OCR/Vision engine")
    parser.add_argument("--prev", help="Previous analysis JSON for delta tracking")
    parser.add_argument("--save-history", action="store_true",
                        help="Save to wall history DB")
    parser.add_argument("--caveman", action="store_true",
                        help="Compact 1-liner output")
    parser.add_argument("--output-json", help="Save full result as JSON")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if not args.image and not args.json_input:
        print("Error: Provide either image path or --json-input", file=sys.stderr)
        return 1

    if args.image and not args.json_input and not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        return 1

    # Load previous snapshot if provided
    prev = None
    if args.prev:
        with open(args.prev) as f:
            prev = json.load(f)

    try:
        if args.json_input:
            # Direct JSON mode — skip OCR entirely
            with open(args.json_input) as f:
                ocr_data = json.load(f)
            result = _run_from_json(ocr_data, prev_data=prev,
                                    save_history=args.save_history,
                                    output_json=args.output_json)
        else:
            result = run_full_pipeline(
                args.image, prev_data=prev,
                engine=args.engine,
                save_history=args.save_history,
                output_json=args.output_json,
            )

        # Print output
        if args.caveman:
            print(result["caveman"])
        else:
            print(result["report"])

        # Timing footer
        if args.debug:
            print(f"\nTiming: {result['timings']}", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
