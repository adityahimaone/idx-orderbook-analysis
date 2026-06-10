#!/usr/bin/env python3
"""
Market Alpha Scout → Orderbook Screener
=========================================
Membaca data Market Alpha Scout Google Sheets, menemukan emiten High Conviction,
dan output rekomendasi screening orderbook — tanda tiker mana yang layak discan.

Output:
  --json    → JSON array tickers with MAS scores
  --caveman → compact terse caveman format
  --table   → Telegram-friendly table (default)

Usage:
  python3.11 mas_orderbook_screener.py
  python3.11 mas_orderbook_screener.py --json --top 5
  python3.11 mas_orderbook_screener.py --caveman
  python3.11 mas_orderbook_screener.py --ticker TPIA
"""
import sys, json
from pathlib import Path

MAS_CONFIG = {
    "sheet_id": "1vOMj5p-X1GAZEAd4Hp_RoSgYtauBiCKF9RW7GRHVxHM",
    "min_score": 60,
}

SKILL_DIR = Path.home() / ".hermes" / "skills" / "finance" / "idx-orderbook-analysis" / "scripts"
sys.path.insert(0, str(SKILL_DIR))
from mas_integration import get_gspread_client


def get_col_map(values, row_idx=3):
    headers = values[row_idx]
    return {h.strip(): i for i, h in enumerate(headers)}


def safe_float(val):
    if not val: return None
    try: return float(val)
    except: return None


def fetch_all_tickers(gc):
    """Read All Tickers sheet — the full 957 tickers with scores/signals."""
    from googleapiclient.discovery import build
    import json as j
    creds_fn = Path.home() / ".hermes" / "google_token.json"
    creds_data = j.load(open(creds_fn))
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_info(creds_data)
    service = build("sheets", "v4", credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=MAS_CONFIG["sheet_id"],
        range="All Tickers!A1:BC1000",
    ).execute()
    values = result.get("values", [])
    if not values: return []

    headers = values[0]
    col_map = {h.strip(): i for i, h in enumerate(headers)}

    # 55-col column mapping verified 2026-05-26
    tickers = []
    for row in values[1:]:
        if len(row) < 5: continue
        ticker = row[1].replace("IDX:", "").strip()
        if not ticker: continue

        entry = {
            "ticker": ticker,
            "price": safe_float(row[5]) if len(row) > 5 else None,
            "change_pct": safe_float(row[6]) if len(row) > 6 else None,
            "volume": safe_float(row[14]) if len(row) > 14 else None,
            "vol_ratio": safe_float(row[16]) if len(row) > 16 else None,
            "ma20": safe_float(row[31]) if len(row) > 31 else None,
            "ma50": safe_float(row[32]) if len(row) > 32 else None,
            "ma200": safe_float(row[33]) if len(row) > 33 else None,
            "support": safe_float(row[34]) if len(row) > 34 else None,
            "score_v2": safe_float(row[41]) if len(row) > 41 else None,
            "signal": row[38] if len(row) > 38 else "",
            "final_signal": row[43] if len(row) > 43 else "",
            "sl_practical": safe_float(row[44]) if len(row) > 44 else None,
            "atr14": safe_float(row[47]) if len(row) > 47 else None,
            "rsi14": safe_float(row[49]) if len(row) > 49 else None,
            "sector": row[2] if len(row) > 2 else "",
        }
        tickers.append(entry)
    return tickers


def fetch_rekomendasi_beli(gc):
    """Read Rekomendasi Beli sheet — top picks with TP/SL."""
    try:
        from googleapiclient.discovery import build
        import json as j
        creds_fn = Path.home() / ".hermes" / "google_token.json"
        creds_data = j.load(open(creds_fn))
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build("sheets", "v4", credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=MAS_CONFIG["sheet_id"],
            range="Rekomendasi Beli!A1:W100",
        ).execute()
        values = result.get("values", [])
        if len(values) < 5: return []

        col_map = get_col_map(values)
        items = []
        for row in values[4:]:
            if not row or not row[0]: continue
            ticker = row[col_map.get("Ticker", 0)].replace("IDX:", "")
            if not ticker: continue

            items.append({
                "ticker": ticker,
                "company": row[col_map.get("Company", 1)] if len(row) > 1 else "",
                "buy_price": safe_float(row[col_map.get("Buy Price", 9)]) if len(row) > 9 else None,
                "sl": safe_float(row[col_map.get("SL_Practical", 10)]) if len(row) > 10 else None,
                "tp": safe_float(row[col_map.get("TP", 11)]) if len(row) > 11 else None,
                "rr": safe_float(row[col_map.get("R/R Ratio", 12)]) if len(row) > 12 else None,
                "action": row[col_map.get("Action", 14)] if len(row) > 14 else "",
                "score_v2": safe_float(row[col_map.get("Score v2", 5)]) if len(row) > 5 else None,
            })
        return items
    except Exception as e:
        return []


def screen_high_conviction(tickers, rb_items):
    """
    Score-based filtering:
    - High Conviction = Score >= 60 OR Final_Signal = BREAKOUT/CONFIRM BUY
    - Has a good signal (not HOLD/AVOID)
    """
    rb_map = {r["ticker"]: r for r in rb_items}

    screened = []
    for t in tickers:
        score = t.get("score_v2") or 0
        signal = (t.get("final_signal") or t.get("signal") or "").upper()
        support = t.get("support")
        price = t.get("price")
        vol_ratio = t.get("vol_ratio") or 0
        rsi = t.get("rsi14")

        is_hc = score >= 60 or "BREAKOUT" in signal or "CONFIRM BUY" in signal
        is_avoid = "AVOID" in signal or "HOLD" in signal
        skip = not is_hc or is_avoid

        rb = rb_map.get(t["ticker"])

        # Pre-entry level untuk orderbook scan
        entry_levels = ""
        if rb and rb.get("buy_price"):
            entry_levels = f"E:{rb['buy_price']:,.0f}"
            if rb.get("sl"): entry_levels += f" SL:{rb['sl']:,.0f}"
            if rb.get("tp"): entry_levels += f" TP:{rb['tp']:,.0f}"
            if rb.get("rr"): entry_levels += f" RR:{rb['rr']:.1f}x"
        elif support and price:
            entry_levels = f"Support:{support:,.0f} (vs Price:{price:,.0f})"
            if support < price:
                entry_levels += f" upside:{((price-support)/support)*100:.1f}%"

        screened.append({
            "ticker": t["ticker"],
            "score": score,
            "signal": signal,
            "price": price,
            "support": support,
            "vol_ratio": vol_ratio,
            "rsi": rsi,
            "sector": t.get("sector", ""),
            "skip": skip,
            "entry_levels": entry_levels,
            "has_rb": rb is not None,
        })

    # Sort: HC first, then by score desc, then by vol_ratio desc
    screened.sort(key=lambda x: (
        0 if not x["skip"] else 1,
        -(x["score"] or 0),
        -(x["vol_ratio"] or 0),
    ))
    return screened


def format_screener_output(screened, fmt="table"):
    if fmt == "json":
        return json.dumps(screened, indent=2)

    lines = []
    if fmt == "caveman":
        lines.append("📡 MAS ORDERBOOK SCREENER")
    else:
        lines.append(f"📡 *Market Alpha Scout → Orderbook Screener*")
        lines.append(f"Total: {len([s for s in screened if not s['skip']])} high conviction of {len(screened)}")
        lines.append("")

    count = 0
    for s in screened:
        if s["skip"] and fmt != "json": continue
        count += 1
        if count > 15: break

        badge = "✅ HC" if not s["skip"] else "➖"
        score_str = f"S{s['score']:.0f}" if s["score"] else "S-"
        signal_short = (s["signal"] or "?")[:8]
        rsi_str = f"RSI{s['rsi']:.0f}" if s["rsi"] else ""
        vol_str = f"V{s['vol_ratio']:.1f}x" if s["vol_ratio"] else ""

        if fmt == "caveman":
            line = f"{badge} `{s['ticker']}` {score_str} {signal_short} {vol_str}"
            if s["entry_levels"]: line += f" | {s['entry_levels']}"
            lines.append(line)
        else:
            price_str = f"{s['price']:,.0f}" if s["price"] else "-"
            line = f"• **{s['ticker']}** — {badge} | Score:{score_str} | {price_str} | {vol_str}"
            if rsi_str: line += f" | {rsi_str}"
            if s["entry_levels"]: line += f"\n  → {s['entry_levels']}"
            lines.append(line)

    if not [s for s in screened if not s["skip"]]:
        lines.append("No high-conviction tickers found. Run MAS scout first.")

    if fmt == "caveman":
        lines.append(f"─── top {min(count,15)} of {len(screened)} ───")
    else:
        lines.append(f"\n_Top {min(count,15)} of {len(screened)} tickers scanned_")
        lines.append("_→ Use `--ticker TICKER` for deeper MAS + orderbook confluence_")

    return "\n".join(lines)


def ticker_detail(screened, ticker):
    """Deep-dive MAS data for one ticker, ready for orderbook confluence."""
    for s in screened:
        if s["ticker"] == ticker.upper():
            return s
    return None


def main():
    args = sys.argv[1:]

    gc = get_gspread_client()
    if not gc:
        print("[MAS] Error: Google credentials not available")
        sys.exit(1)

    # Fetch data
    tickers = fetch_all_tickers(gc)
    rb_items = fetch_rekomendasi_beli(gc)

    if not tickers:
        print("[MAS] Error: No tickers from All Tickers sheet")
        sys.exit(1)

    screened = screen_high_conviction(tickers, rb_items)

    # --ticker TICKER: single ticker detail
    ticker_filter = None
    for i, a in enumerate(args):
        if a == "--ticker" and i + 1 < len(args):
            ticker_filter = args[i + 1]

    if ticker_filter:
        detail = ticker_detail(screened, ticker_filter.upper())
        if detail:
            print(json.dumps(detail, indent=2))
        else:
            print(f"Ticker {ticker_filter.upper()} not found in MAS data")
        return

    fmt = "--json" if "--json" in args else "caveman" if "--caveman" in args else "table"
    if fmt in ("table", "caveman"):
        print(format_screener_output(screened, fmt))
    else:
        top_n = None
        for i, a in enumerate(args):
            if a == "--top" and i + 1 < len(args):
                top_n = int(args[i + 1])
        if top_n:
            print(json.dumps([s for s in screened if not s["skip"]][:top_n], indent=2))
        else:
            print(json.dumps(screened, indent=2))


if __name__ == "__main__":
    main()
