import json
from pathlib import Path
from google.oauth2.credentials import Credentials
import gspread

def get_gspread_client():
    token_path = Path.home() / ".hermes" / "google_token.json"
    if not token_path.exists():
        return None
    try:
        creds_data = json.load(open(token_path))
        creds = Credentials.from_authorized_user_info(creds_data)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"[MAS-Integrator] Error: {e}")
        return None

def fetch_high_conviction_tickers(sheet_id="1vOMj5p-X1GAZEAd4Hp_RoSgYtauBiCKF9RW7GRHVxHM"):
    """
    Read MAS 'Rekomendasi Beli' data.
    Filter for high conviction: Score v2 >= 60 OR Action contains BREAKOUT
    """
    gc = get_gspread_client()
    if not gc: return []

    try:
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet("Rekomendasi Beli")
        values = ws.get_all_values()
        if len(values) < 5: return []
        
        headers = values[3]
        col_map = {h.strip(): i for i, h in enumerate(headers)}
        
        results = []
        for row in values[4:]:
            if not row or not row[0]: continue
            
            score = 0
            try:
                score = float(row[col_map.get("Score v2", 5)])
            except:
                pass
            
            action = row[col_map.get("Action", 14)] if len(row) > 14 else ""
            
            if score >= 60 or "BREAKOUT" in action.upper():
                results.append({
                    "ticker": row[col_map.get("Ticker", 0)].replace("IDX:", ""),
                    "score": score,
                    "action": action,
                    "buy_price": row[col_map.get("Buy Price", 9)] if len(row) > 9 else None,
                    "sl": row[col_map.get("SL_Practical", 10)] if len(row) > 10 else None,
                    "tp": row[col_map.get("TP", 11)] if len(row) > 11 else None,
                    "rr": row[col_map.get("R/R Ratio", 12)] if len(row) > 12 else None,
                })
        return results
    except Exception as e:
        print(f"[MAS-Integrator] Error: {e}")
        return []

if __name__ == "__main__":
    data = fetch_high_conviction_tickers()
    print(json.dumps(data, indent=2))
