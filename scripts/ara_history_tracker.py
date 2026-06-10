#!/usr/bin/env python3.11
"""
ARA History Tracker — Records tickers that hit/near ARA daily.
Runs post-market (after 15:15 WIB) to log which tickers reached ARA.

Usage:
    python3.11 ara_history_tracker.py [--staging|--prod] [--threshold 20] [--dry-run]

Appends rows to "ARA History" sheet. Does NOT overwrite existing data.
"""

import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

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


def sf(val):
    if val is None or val == '' or val == '#N/A' or val == 'N/A':
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def get_ara_limit(prev_close):
    """IDX ARA percentage based on price tier."""
    if prev_close <= 0:
        return 35
    elif prev_close < 50:
        return 35
    elif prev_close < 200:
        return 35
    elif prev_close < 5000:
        return 25
    else:
        return 20


def classify_pattern(data):
    """Classify the pre-ARA pattern from available data."""
    gap = data.get('gap', 0)
    vol_ratio = data.get('vol_ratio', 0)
    chg_pct = data.get('chg_pct', 0)
    
    if gap > 10 and vol_ratio > 2:
        return "GAP-UP SURGE"
    elif gap > 5:
        return "GAP-UP"
    elif vol_ratio > 5:
        return "VOLUME EXPLOSION"
    elif vol_ratio > 2:
        return "ACCUMULATION BREAKOUT"
    elif chg_pct > 20:
        return "MOMENTUM RUN"
    else:
        return "GRADUAL"


def main():
    parser = argparse.ArgumentParser(description='ARA History Tracker')
    parser.add_argument('--staging', action='store_true', default=True)
    parser.add_argument('--prod', action='store_true')
    parser.add_argument('--threshold', type=float, default=20.0,
                        help='Min change%% to consider as ARA/near-ARA (default: 20)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    config = load_config()
    if args.prod:
        sheet_id = config['sheet_id']
        mode = 'production'
    else:
        sheet_id = config.get('staging_sheet_id', config['sheet_id'])
        mode = 'staging'

    print(f"[ARA History] Mode: {mode} | Threshold: {args.threshold}%")
    service = get_service()

    # Fetch All Tickers
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="'All Tickers'!A1:BC1000",
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    values = result.get('values', [])
    if len(values) < 2:
        print("[ARA History] ERROR: No data")
        return 1

    print(f"[ARA History] Read {len(values)-1} tickers")
    today = datetime.now().strftime("%Y-%m-%d")

    # Find ARA/near-ARA tickers
    ara_tickers = []
    for row in values[1:]:
        if len(row) < 20:
            continue
        
        ticker = str(row[1]).replace('IDX:', '').strip() if len(row) > 1 else ''
        if not ticker:
            continue

        company = str(row[2])[:30] if len(row) > 2 else ''
        price = sf(row[5]) if len(row) > 5 else 0
        chg_pct = sf(row[6]) if len(row) > 6 else 0
        high = sf(row[9]) if len(row) > 9 else 0
        low = sf(row[10]) if len(row) > 10 else 0
        prev = sf(row[11]) if len(row) > 11 else 0
        gap = sf(row[12]) if len(row) > 12 else 0
        volume = sf(row[14]) if len(row) > 14 else 0
        vol_ratio = sf(row[16]) if len(row) > 16 else 0
        daily_range = sf(row[18]) if len(row) > 18 else 0
        open_price = sf(row[8]) if len(row) > 8 else 0
        score_v2 = sf(row[41]) if len(row) > 41 else 0
        trend = str(row[39]) if len(row) > 39 else ''

        # Only track stocks with change >= threshold
        if chg_pct < args.threshold:
            continue

        ara_limit = get_ara_limit(prev)
        ara_price = prev * (1 + ara_limit / 100) if prev > 0 else 0
        hit_ara = price >= ara_price * 0.98  # within 2% of ARA = "hit ARA"
        return_pct = round(chg_pct, 2)

        data = {
            'ticker': ticker,
            'company': company,
            'price': price,
            'prev': prev,
            'open_price': open_price,
            'high': high,
            'low': low,
            'ara_price': ara_price,
            'chg_pct': chg_pct,
            'gap': gap,
            'volume': volume,
            'vol_ratio': vol_ratio,
            'daily_range': daily_range,
            'score_v2': score_v2,
            'trend': trend,
            'hit_ara': hit_ara,
        }

        pattern = classify_pattern(data)

        ara_tickers.append({
            'date': today,
            'ticker': ticker,
            'company': company,
            'prev': prev,
            'ara_price': round(ara_price, 0),
            'open_price': open_price,
            'low': low,
            'time_to_ara': '',  # can't determine from EOD data
            'volume': int(volume),
            'vol_ratio_peak': round(vol_ratio, 2),
            'pattern': pattern,
            'trend_before': trend,
            'score_v2': round(score_v2, 1),
            'return_pct': return_pct,
            'success': "✅ ARA" if hit_ara else "🟡 NEAR-ARA",
            'notes': f"Range {daily_range:.1f}% | Gap {gap:.1f}%"
        })

    ara_tickers.sort(key=lambda x: -x['return_pct'])
    print(f"[ARA History] Found {len(ara_tickers)} tickers above {args.threshold}% threshold")

    if args.dry_run:
        for t in ara_tickers[:10]:
            print(f"  {t['ticker']:<7} +{t['return_pct']:.1f}% | VolR {t['vol_ratio_peak']:.1f}x | {t['pattern']} | {t['success']}")
        return 0

    if not ara_tickers:
        print("[ARA History] No ARA tickers today. Nothing to write.")
        return 0

    # Build rows
    rows = []
    for t in ara_tickers:
        rows.append([
            t['date'],
            t['ticker'],
            t['company'],
            t['prev'],
            t['ara_price'],
            t['open_price'],
            t['low'],
            t['time_to_ara'],
            t['volume'],
            t['vol_ratio_peak'],
            t['pattern'],
            t['trend_before'],
            t['score_v2'],
            t['return_pct'],
            t['success'],
            t['notes'],
        ])

    # Find next empty row in ARA History
    existing = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="'ARA History'!A:A",
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    next_row = len(existing.get('values', [])) + 1

    # Append
    write_range = f"'ARA History'!A{next_row}:P{next_row + len(rows) - 1}"
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=write_range,
        valueInputOption='RAW',
        body={'values': rows}
    ).execute()

    print(f"[ARA History] ✅ Appended {len(rows)} rows starting at row {next_row}")
    for t in ara_tickers[:5]:
        print(f"  {t['ticker']:<7} +{t['return_pct']:.1f}% | {t['pattern']} | {t['success']}")

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
