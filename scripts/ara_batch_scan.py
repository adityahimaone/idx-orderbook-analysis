#!/usr/bin/env python3.11
"""
ARA Batch Orderbook Scanner
1. Reads top 12 ARA tickers from ARA Screener (via MAS GSpread API)
2. Runs analysis via pipeline_stdin.py for each
3. Outputs combined results

Usage:
    python3.11 ara_batch_scan.py [--staging]
"""

import json
import os
import sys
import subprocess
from pathlib import Path

# Setup paths
MAS_DIR = Path.home() / ".hermes/skills/research/market-alpha-scout/scripts"
PIPELINE_DIR = Path.home() / ".hermes/skills/finance/idx-orderbook-analysis/scripts"
sys.path.insert(0, str(MAS_DIR))
sys.path.insert(0, str(PIPELINE_DIR))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_service():
    creds_data = json.load(open(os.path.expanduser('~/.hermes/google_token.json')))
    creds = Credentials.from_authorized_user_info(creds_data)
    return build('sheets', 'v4', credentials=creds)

def main():
    # Use production unless arg says otherwise (for dev/test)
    mode = 'production' if '--prod' in sys.argv else 'staging'
    
    # 1. Fetch top ARA tickers
    config = json.load(open(MAS_DIR / '../data/comprehensive_sheet.json'))
    sheet_id = config.get('staging_sheet_id') if mode == 'staging' else config['sheet_id']
    
    service = get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="'ARA Screener'!A2:H13", # Top 12
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    
    rows = result.get('values', [])
    if not rows:
        print("[ARA Batch] No tickers found in ARA Screener")
        return 0

    tickers = [row[1] for row in rows if len(row) > 1]
    print(f"[ARA Batch] Scanning {len(tickers)} tickers: {', '.join(tickers)}")

    # 2. Run pipeline for each ticker
    # Note: Requires OCR data. If no OCR snapshot exists, this will fail or return incomplete analysis.
    # We trigger the pipeline with --mas to use the confluence integration.
    
    for ticker in tickers:
        print(f"\n--- Scanning {ticker} ---")
        input_json = json.dumps({"ticker": ticker})
        
        try:
            # Using pipeline_stdin.py with --mas
            proc = subprocess.Popen(
                ["python3.11", str(PIPELINE_DIR / "pipeline_stdin.py"), "--caveman", "--mas"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(input=input_json)
            
            if stdout:
                print(stdout)
            if stderr:
                print(f"[ERROR] {ticker}: {stderr}", file=sys.stderr)
                
        except Exception as e:
            print(f"[FATAL] {ticker} pipeline failed: {e}")

if __name__ == '__main__':
    main()
