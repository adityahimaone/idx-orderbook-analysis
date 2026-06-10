#!/usr/bin/env python3.11
"""
ARA Screener Refresh — Fast 30-ticker ARA probability scan
Reads All Tickers, calculates ARA score, writes top 30 to ARA Screener sheet.

Usage:
    python3.11 ara_screener_refresh.py [--staging|--prod] [--top N] [--dry-run]

Runtime: ~3-5 seconds (vs 45s full rebuild)
Designed for 5-minute cron during trading hours (09:00-15:00 WIB)
"""

import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# --- Setup imports ---
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, '/home/adityahimaone/.hermes/hermes-agent/venv/lib/python3.11/site-packages')

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def load_config():
    config_path = SCRIPT_DIR / '../data/comprehensive_sheet.json'
    return json.load(open(config_path))


def get_service():
    creds_data = json.load(open(os.path.expanduser('~/.hermes/google_token.json')))
    creds = Credentials.from_authorized_user_info(creds_data)
    return build('sheets', 'v4', credentials=creds)


def safe_float(val):
    """Safely convert to float, return 0 on failure."""
    if val is None or val == '' or val == '#N/A' or val == 'N/A':
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def calculate_ara_score(row):
    """
    Calculate ARA probability score (0-130+) from a single ticker row.
    
    Criteria:
    P1: Volume Surge (0-30pts) — institutional interest
    P2: Daily Range (0-25pts) — already moving aggressively
    P3: Price Movement (0-25pts) — momentum toward ARA
    P4: Signal Alignment (0-20pts) — technical confirmation
    P5: MA Position (0-15pts) — trend alignment
    P6: Gap-Up + Volume (0-10pts) — opening momentum
    P7: Score v2 Quality (0-10pts) — fundamental backing
    P8: RSI Momentum (0-5pts) — not exhausted
    """
    price = safe_float(row.get('price', 0))
    prev = safe_float(row.get('prev', 0))
    chg_pct = safe_float(row.get('chg_pct', 0))
    vol_ratio = safe_float(row.get('vol_ratio', 0))
    daily_range = safe_float(row.get('daily_range', 0))
    gap = safe_float(row.get('gap', 0))
    ma20 = safe_float(row.get('ma20', 0))
    ma50 = safe_float(row.get('ma50', 0))
    signal = str(row.get('signal', '')).upper()
    final_signal = str(row.get('final_signal', '')).upper()
    score_v2 = safe_float(row.get('score_v2', 0))
    rsi = safe_float(row.get('rsi', 0))

    max_chg = ((price - prev) / prev * 100) if prev > 0 else chg_pct
    ara = 0

    # P1: Volume Surge (institutional interest)
    if vol_ratio >= 5.0: ara += 30
    elif vol_ratio >= 3.0: ara += 28
    elif vol_ratio >= 2.0: ara += 22
    elif vol_ratio >= 1.5: ara += 15
    elif vol_ratio >= 1.2: ara += 8

    # P2: Daily Range (already moving hard)
    if daily_range >= 25: ara += 25
    elif daily_range >= 20: ara += 22
    elif daily_range >= 15: ara += 18
    elif daily_range >= 10: ara += 14
    elif daily_range >= 7: ara += 8

    # P3: Price Movement toward ARA
    if max_chg >= 25: ara += 25
    elif max_chg >= 20: ara += 22
    elif max_chg >= 15: ara += 18
    elif max_chg >= 10: ara += 14
    elif max_chg >= 5: ara += 8
    elif max_chg >= 3: ara += 4

    # P4: Signal Alignment
    sig_combined = final_signal or signal
    if 'BREAKOUT' in sig_combined: ara += 20
    elif 'CONFIRM' in sig_combined and 'BUY' in sig_combined: ara += 18
    elif 'STRONG_BUY' in signal: ara += 12
    elif 'BUY' in signal: ara += 6

    # P5: MA Position (trending up)
    if price > 0 and ma20 > 0 and price > ma20: ara += 10
    if price > 0 and ma50 > 0 and price > ma50: ara += 5

    # P6: Gap-Up with volume
    if gap > 5 and vol_ratio > 1.5: ara += 10
    elif gap > 3 and vol_ratio > 1.2: ara += 7
    elif gap > 1 and vol_ratio > 1.5: ara += 4

    # P7: Score v2 quality
    if score_v2 >= 70: ara += 10
    elif score_v2 >= 50: ara += 5
    elif score_v2 >= 40: ara += 3

    # P8: RSI Momentum
    if 55 <= rsi <= 75: ara += 5
    elif rsi > 75: ara += 3  # overbought, might still run but riskier

    return ara, max_chg


def classify_stage(chg_pct):
    """Classify where in the ARA lifecycle this ticker is."""
    if chg_pct >= 25: return "🔴 ARA_ZONE"
    elif chg_pct >= 15: return "🟠 LATE"
    elif chg_pct >= 5: return "🟡 MOMENTUM"
    elif chg_pct >= 2: return "🟢 EARLY"
    elif chg_pct >= 0: return "⚪ PRE"
    else: return "⬇️ RED"


def classify_confidence(ara_score, signal_ok, vol_ratio):
    """Confidence in ARA happening."""
    if ara_score >= 90 and signal_ok: return "🔥 HIGH"
    elif ara_score >= 70: return "⚡ MED-HIGH"
    elif ara_score >= 50: return "📊 MEDIUM"
    elif ara_score >= 35: return "📉 LOW"
    else: return "❄️ VERY LOW"


def calculate_ara_distance(price, prev):
    """Calculate distance to ARA price (25% for <200, 35% for >200, etc.)."""
    if prev <= 0 or price <= 0:
        return 0, 0
    # IDX ARA rules (simplified)
    if prev < 50: ara_pct = 35
    elif prev < 200: ara_pct = 35
    elif prev < 5000: ara_pct = 25
    else: ara_pct = 20
    
    ara_price = prev * (1 + ara_pct / 100)
    dist_pct = ((ara_price - price) / ara_price) * 100
    return ara_price, max(0, dist_pct)


def main():
    parser = argparse.ArgumentParser(description='ARA Screener Refresh')
    parser.add_argument('--staging', action='store_true', default=True)
    parser.add_argument('--prod', action='store_true')
    parser.add_argument('--top', type=int, default=30, help='Top N tickers to write')
    parser.add_argument('--dry-run', action='store_true', help='Print only, no write')
    args = parser.parse_args()

    config = load_config()
    if args.prod:
        sheet_id = config['sheet_id']
        mode = 'production'
    else:
        sheet_id = config.get('staging_sheet_id', config['sheet_id'])
        mode = 'staging'

    print(f"[ARA Screener] Mode: {mode} | Top: {args.top}")
    service = get_service()

    # Fetch All Tickers (UNFORMATTED_VALUE for clean numbers)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="'All Tickers'!A1:BC1000",
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    values = result.get('values', [])
    if len(values) < 2:
        print("[ARA Screener] ERROR: No data in All Tickers")
        return 1

    headers = values[0]
    print(f"[ARA Screener] Read {len(values)-1} tickers")

    # Column index mapping from comprehensive_sheet.json
    # B=1(ticker), C=2(company), D=3(sector), F=5(price), G=6(chg%), 
    # J=9(high), K=10(low), L=11(prev), M=12(gap), O=14(vol), Q=16(vol_ratio)
    # S=18(daily_range), AF=31(ma20), AG=32(ma50), AM=38(signal), 
    # AN=39(trend), AO=40(score_v1), AP=41(score_v2), AR=43(final_signal),
    # AX=49(rsi14)

    candidates = []
    for row in values[1:]:
        if len(row) < 44:
            continue
        
        ticker = str(row[1]).replace('IDX:', '').strip() if len(row) > 1 else ''
        if not ticker:
            continue

        data = {
            'ticker': ticker,
            'company': str(row[2])[:30] if len(row) > 2 else '',
            'sector': str(row[3])[:20] if len(row) > 3 else '',
            'price': safe_float(row[5]) if len(row) > 5 else 0,
            'chg_pct': safe_float(row[6]) if len(row) > 6 else 0,
            'high': safe_float(row[9]) if len(row) > 9 else 0,
            'low': safe_float(row[10]) if len(row) > 10 else 0,
            'prev': safe_float(row[11]) if len(row) > 11 else 0,
            'gap': safe_float(row[12]) if len(row) > 12 else 0,
            'volume': safe_float(row[14]) if len(row) > 14 else 0,
            'vol_ratio': safe_float(row[16]) if len(row) > 16 else 0,
            'daily_range': safe_float(row[18]) if len(row) > 18 else 0,
            'ma20': safe_float(row[31]) if len(row) > 31 else 0,
            'ma50': safe_float(row[32]) if len(row) > 32 else 0,
            'signal': str(row[38]) if len(row) > 38 else '',
            'trend': str(row[39]) if len(row) > 39 else '',
            'score_v2': safe_float(row[41]) if len(row) > 41 else 0,
            'final_signal': str(row[43]) if len(row) > 43 else '',
            'rsi': safe_float(row[49]) if len(row) > 49 else 0,
        }

        # Only consider stocks with positive change
        if data['chg_pct'] <= 0:
            continue

        ara_score, max_chg = calculate_ara_score(data)
        _, ara_dist = calculate_ara_distance(data['price'], data['prev'])
        stage = classify_stage(data['chg_pct'])
        
        sig_ok = any(x in (data.get('final_signal', '') or '').upper() 
                     for x in ['CONFIRM', 'BREAKOUT', 'BUY'])
        confidence = classify_confidence(ara_score, sig_ok, data['vol_ratio'])
        
        price_gt_ma20 = "✅" if (data['price'] > 0 and data['ma20'] > 0 and data['price'] > data['ma20']) else "❌"

        candidates.append({
            **data,
            'ara_score': ara_score,
            'ara_dist': ara_dist,
            'stage': stage,
            'confidence': confidence,
            'price_gt_ma20': price_gt_ma20,
        })

    # Sort by ARA score descending
    candidates.sort(key=lambda x: (-x['ara_score'], -x['vol_ratio']))
    top = candidates[:args.top]

    print(f"[ARA Screener] Candidates (chg%>0): {len(candidates)} | Top {args.top}")

    if args.dry_run:
        print(f"\n{'Tkr':<7} {'Price':>6} {'Chg%':>6} {'VolR':>5} {'ARA':>4} {'Dist':>5} {'Stage':<14} {'Conf':<10}")
        print('-' * 65)
        for c in top[:15]:
            print(f"{c['ticker']:<7} {c['price']:>6,.0f} {c['chg_pct']:>6.1f} {c['vol_ratio']:>5.1f} {c['ara_score']:>4} {c['ara_dist']:>5.1f} {c['stage']:<14} {c['confidence']:<10}")
        return 0

    # Build rows for Google Sheets
    now = datetime.now().strftime("%H:%M:%S")
    rows = []
    for i, c in enumerate(top, 1):
        rows.append([
            i,
            c['ticker'],
            c['company'],
            c['sector'],
            c['price'],
            round(c['chg_pct'], 2),
            c['ara_score'],
            round(c['ara_dist'], 1),
            c['stage'],
            round(c['vol_ratio'], 2),
            int(c['volume']),
            round(c['rsi'], 1) if c['rsi'] else '',
            c['signal'],
            c['final_signal'],
            c['confidence'],
            c['trend'],
            c['price_gt_ma20'],
            now
        ])

    # Clear old data and write new
    clear_range = f"'ARA Screener'!A2:R{args.top + 5}"
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range=clear_range
    ).execute()

    write_range = f"'ARA Screener'!A2:R{len(rows) + 1}"
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=write_range,
        valueInputOption='RAW',
        body={'values': rows}
    ).execute()

    top_str = ', '.join(f"{c['ticker']}({c['ara_score']})" for c in top[:3])
    print(f"[ARA Screener] ✅ Written {len(rows)} rows to {mode}")
    print(f"[ARA Screener] Top 3: {top_str}")
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
