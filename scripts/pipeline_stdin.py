#!/usr/bin/env python3
"""
Pipeline v2 — STDIN mode (skip file I/O)
Reads pre-extracted JSON from stdin, runs analysis, outputs result.
Auto-fetches prev snapshot from history DB for delta analysis.

Usage:
    cat data.json | python3.11 pipeline_stdin.py [--caveman] [--save]
    echo '{"ticker":"..."}' | python3.11 pipeline_stdin.py --caveman --save
    echo '{"ticker":"..."}' | python3.11 pipeline_stdin.py --caveman --save --mas
"""
import sys, json, os
from pathlib import Path

SKILL_DIR = Path.home() / ".hermes/skills/finance/idx-orderbook-analysis/scripts"
sys.path.insert(0, str(SKILL_DIR))

from pipeline_v2 import _standardize, _run_from_json


def _get_prev_snapshot(ticker: str) -> dict | None:
    """Fetch most recent snapshot for ticker from history DB."""
    try:
        from orderbook_history import get_latest_snapshot, init_db
        init_db()
        return get_latest_snapshot(ticker)
    except Exception:
        return None


def _get_mas_context(ticker: str) -> dict | None:
    """Fetch MAS data for a single ticker (Score, Support, TP/SL)."""
    try:
        from mas_integration import get_gspread_client
        gc = get_gspread_client()
        if not gc:
            return None

        from mas_orderbook_screener import fetch_all_tickers, fetch_rekomendasi_beli, screen_high_conviction, ticker_detail
        tickers = fetch_all_tickers(gc)
        rb_items = fetch_rekomendasi_beli(gc)
        screened = screen_high_conviction(tickers, rb_items)
        detail = ticker_detail(screened, ticker)
        return detail
    except Exception as e:
        print(f"[MAS] Warning: {e}", file=sys.stderr)
        return None


def _format_mas_footer(mas: dict) -> str:
    """Format MAS context as footer line for caveman output."""
    if not mas:
        return ""
    parts = []
    parts.append(f"MAS Score:{mas.get('score', 0):.0f}")
    if mas.get("signal"):
        parts.append(f"Sig:{mas['signal'][:12]}")
    if mas.get("vol_ratio"):
        parts.append(f"VolR:{mas['vol_ratio']:.1f}x")
    if mas.get("rsi"):
        parts.append(f"RSI:{mas['rsi']:.0f}")
    if mas.get("entry_levels"):
        parts.append(f"→ {mas['entry_levels']}")
    hc = "✅ HC" if not mas.get("skip") else "➖ SKIP"
    return f"\n📡 MAS {hc} | {' | '.join(parts)}"


def main():
    caveman = "--caveman" in sys.argv
    save = "--save" in sys.argv
    use_mas = "--mas" in sys.argv

    # Read JSON from stdin
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: No JSON on stdin", file=sys.stderr)
        return 1

    try:
        ocr_data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

    # Auto-fetch prev from history DB
    ticker = ocr_data.get("ticker", "")
    prev_data = _get_prev_snapshot(ticker) if ticker else None

    result = _run_from_json(ocr_data, prev_data=prev_data, save_history=save)

    if caveman:
        output = result["caveman"]
        # Append MAS context if --mas flag
        if use_mas and ticker:
            mas = _get_mas_context(ticker)
            output += _format_mas_footer(mas)
        print(output)
    else:
        output = result["report"]
        if use_mas and ticker:
            mas = _get_mas_context(ticker)
            if mas:
                output += f"\n\n## Market Alpha Scout Context\n"
                output += f"- Score v2: {mas.get('score', 0):.0f}\n"
                output += f"- Signal: {mas.get('signal', '-')}\n"
                output += f"- Vol Ratio: {mas.get('vol_ratio', 0):.1f}x\n"
                output += f"- RSI14: {mas.get('rsi', '-')}\n"
                output += f"- Entry Levels: {mas.get('entry_levels', '-')}\n"
                output += f"- High Conviction: {'Yes' if not mas.get('skip') else 'No'}\n"
        print(output)

    return 0

if __name__ == "__main__":
    sys.exit(main())
