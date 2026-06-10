#!/usr/bin/env python3
"""
Pipeline v2 — STDIN mode (skip file I/O)
Reads pre-extracted JSON from stdin, runs analysis, outputs result.
Auto-fetches prev snapshot from history DB for delta analysis.

Usage:
    cat data.json | python3.11 pipeline_stdin.py [--caveman] [--save]
    echo '{"ticker":"..."}' | python3.11 pipeline_stdin.py --caveman --save
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


def main():
    caveman = "--caveman" in sys.argv
    save = "--save" in sys.argv

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
        print(result["caveman"])
    else:
        print(result["report"])

    return 0

if __name__ == "__main__":
    sys.exit(main())
