#!/usr/bin/env python3
"""IDX market session reminders + DB deep check."""
import json, os, sys
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path.home() / ".hermes/skills/finance/idx-orderbook-analysis/scripts"
sys.path.insert(0, str(SKILL_DIR))

now = datetime.now()
hour = now.hour
minute = now.minute

# ── Session messages ──
messages = {
    "prime_start":   "📊 *Sesi prime start* 09:30\nLiquiditas puncak, ideal entry. Cek orderbook lu.",
    "pre_break":     "☕ *Pre-break* 11:00\nVolum mulai turun, spread melebar. Reduce posisi kalo ada.",
    "session2":      "📈 *Sesi 2 start* 13:30\nSore sering reversal. Pantau wall baru masuk.",
    "closing_push":  "🏁 *Closing push* 14:50\nInstitusi defend. Jangan entry baru, close floating.",
    "post_close":    "✅ Market closed.\nHarian selesai. Mau review day summary?",
}

def get_db_summary():
    """Quick DB stat for closing review."""
    try:
        from orderbook_history import get_all_tickers, get_snapshots_since
        tickers = get_all_tickers()
        lines = []
        for t in tickers[:3]:
            snaps = get_snapshots_since(t, datetime.now().replace(hour=0, minute=0, second=0))
            if snaps:
                walls = []
                for s in snaps:
                    w = s.get("walls", {})
                    for mw in w.get("mega_walls", []):
                        walls.append(f"{mw['price']}:{mw['lot']:,}")
                lines.append(f"• {t}: {len(snaps)} snap, walls [{', '.join(walls[:3])}]")
        return "\n".join(lines) if lines else "Ga ada snapshot hari ini."
    except Exception:
        return "DB error — skip."

# ── Schedule matching ──
if hour == 9 and minute >= 30 and minute < 35:
    print(messages["prime_start"])
elif hour == 11 and minute < 5:
    print(messages["pre_break"])
elif hour == 13 and minute >= 30 and minute < 35:
    print(messages["session2"])
elif hour == 14 and minute >= 50:
    print(messages["closing_push"])
elif hour == 15 and minute >= 5 and minute < 10:
    summary = get_db_summary()
    print(f"{messages['post_close']}\n\n{summary}")
else:
    # Quiet — nothing to say
    pass
