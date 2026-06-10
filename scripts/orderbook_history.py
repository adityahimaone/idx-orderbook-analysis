#!/usr/bin/env python3
"""
Orderbook Wall History & Batch Scanner
=======================================

SQLite-backed wall persistence for cross-snapshot analysis + parallel multi-ticker scanning.

Features:
- Wall history: track walls across snapshots, detect persistence/fake
- Batch scan: parallel OCR on multiple screenshots
- Dynamic S/R flip detection across sessions
"""

import sys
import json
import sqlite3
import os
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = Path.home() / ".hermes" / "orderbook_history.db"


# ──────────────────────────────────────────
#  DATABASE
# ──────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            timestamp TEXT,
            price INTEGER,
            high INTEGER,
            low INTEGER,
            avg INTEGER,
            ara INTEGER,
            arb INTEGER,
            bid_total INTEGER,
            ask_total INTEGER,
            bid_ask_ratio REAL,
            phase TEXT,
            session_time TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS walls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            side TEXT,
            price INTEGER,
            lot INTEGER,
            freq INTEGER,
            tipe TEXT,
            is_mega INTEGER DEFAULT 0,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS red_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            flag_id TEXT,
            flag_name TEXT,
            severity TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshot_ticker ON snapshots(ticker, created_at);
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_walls_snapshot ON walls(snapshot_id);
    """)
    conn.commit()
    conn.close()


def save_snapshot(data: Dict) -> int:
    """Save a snapshot and return its id."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    bid_total = data.get("bid_total", 0)
    ask_total = data.get("ask_total", 0)
    ratio = bid_total / max(ask_total, 1)

    c.execute("""
        INSERT INTO snapshots (ticker, timestamp, price, high, low, avg, ara, arb,
                               bid_total, ask_total, bid_ask_ratio, phase, session_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("ticker"),
        data.get("timestamp"),
        data.get("price"),
        data.get("high"),
        data.get("low"),
        data.get("avg"),
        data.get("ara"),
        data.get("arb"),
        bid_total,
        ask_total,
        ratio,
        data.get("phase", {}).get("fase", "UNKNOWN"),
        data.get("ihsg_context", {}).get("session", {}).get("nama", "Unknown"),
    ))
    snapshot_id = c.lastrowid

    # Save walls
    walls_data = data.get("walls", {})
    all_walls = (
        walls_data.get("bid_walls", []) +
        walls_data.get("ask_walls", []) +
        walls_data.get("mega_walls", [])
    )
    for w in all_walls:
        c.execute("""
            INSERT INTO walls (snapshot_id, side, price, lot, freq, tipe, is_mega)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            "bid" if "Bid" in w["tipe"] else "ask",
            w["price"],
            w["lot"],
            w["freq"],
            w["tipe"],
            1 if w.get("is_mega") else 0,
        ))

    # Save red flags
    for rf in data.get("red_flags", []):
        c.execute("""
            INSERT INTO red_flags (snapshot_id, flag_id, flag_name, severity)
            VALUES (?, ?, ?, ?)
        """, (snapshot_id, rf["id"], rf["nama"], rf["severitas"]))

    conn.commit()
    conn.close()
    return snapshot_id


def get_wall_history(ticker: str, hours_back: int = 6) -> Dict:
    """Get wall persistence history for a ticker."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.now() - timedelta(hours=hours_back)).isoformat()

    rows = conn.execute("""
        SELECT w.price, w.side, w.lot, w.freq, w.tipe, w.is_mega,
               s.timestamp, s.price as snap_price
        FROM walls w
        JOIN snapshots s ON w.snapshot_id = s.id
        WHERE s.ticker = ? AND s.created_at > ?
        ORDER BY s.created_at DESC
    """, (ticker, cutoff)).fetchall()

    conn.close()

    # Analyze wall persistence
    wall_map = {}
    for r in rows:
        key = (r["price"], r["side"])
        if key not in wall_map:
            wall_map[key] = {
                "price": r["price"],
                "side": r["side"],
                "tipe": r["tipe"],
                "count": 0,
                "lot_history": [],
                "is_mega": bool(r["is_mega"]),
            }
        wall_map[key]["count"] += 1
        wall_map[key]["lot_history"].append({"timestamp": r["timestamp"], "lot": r["lot"]})

    # Classify
    result = {"persistent": [], "volatile": [], "disappeared": []}
    for w in wall_map.values():
        if w["count"] >= 2:
            result["persistent"].append(w)
        elif w["count"] == 1 and w["lot_history"]:
            # Check if last was recent
            result["volatile"].append(w)

    result["persistent"].sort(key=lambda w: w["count"], reverse=True)
    return result


def get_all_tickers() -> List[str]:
    """Return distinct tickers in DB."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    rows = c.execute("SELECT DISTINCT ticker FROM snapshots ORDER BY ticker").fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def get_snapshots_since(ticker: str, since: datetime = None) -> List[Dict]:
    """Return all snapshots for a ticker since given time."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if since:
        rows = c.execute("""
            SELECT * FROM snapshots WHERE ticker = ? AND created_at >= ?
            ORDER BY created_at
        """, (ticker, since.strftime("%Y-%m-%d %H:%M:%S"))).fetchall()
    else:
        rows = c.execute("""
            SELECT * FROM snapshots WHERE ticker = ? ORDER BY created_at
        """, (ticker,)).fetchall()
    result = []
    for r in rows:
        snap = dict(r)
        # Fetch walls
        wall_rows = c.execute("""
            SELECT side, price, lot, freq, tipe, is_mega FROM walls WHERE snapshot_id = ?
        """, (r["id"],)).fetchall()
        walls = {"bid_walls": [], "ask_walls": [], "mega_walls": []}
        for w in wall_rows:
            entry = {"price": w["price"], "lot": w["lot"], "freq": w["freq"],
                     "tipe": w["tipe"], "is_mega": bool(w["is_mega"])}
            if "Mega" in w["tipe"]:
                walls["mega_walls"].append(entry)
            elif w["side"] == "BID":
                walls["bid_walls"].append(entry)
            else:
                walls["ask_walls"].append(entry)
        snap["walls"] = walls
        result.append(snap)
    conn.close()
    return result


def get_latest_snapshot(ticker: str) -> Optional[Dict]:
    """Get most recent snapshot as prev_data dict usable by analyze_snapshot.
    
    Returns a dict with keys: price, high, low, avg, bid_total, ask_total,
    ratio, timestamp, bids, asks, walls, volume_lot — or None if not found.
    """
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT s.*, GROUP_CONCAT(w.price || '|' || w.lot || '|' || w.freq || '|' || w.tipe || '|' || w.side, '||') as walls_str
        FROM snapshots s
        LEFT JOIN walls w ON w.snapshot_id = s.id
        WHERE s.ticker = ?
        GROUP BY s.id
        ORDER BY s.created_at DESC
        LIMIT 1
    """, (ticker,)).fetchone()

    if not row:
        conn.close()
        return None

    row = dict(row)
    
    # Reconstruct bids/asks from walls
    bids = []
    asks = []
    walls_out = {"bid_walls": [], "ask_walls": [], "mega_walls": []}
    if row.get("walls_str"):
        for wall_str in row["walls_str"].split("||"):
            parts = wall_str.split("|")
            if len(parts) >= 5:
                try:
                    p = int(parts[0])
                    l = int(parts[1])
                    f = int(parts[2])
                except (ValueError, IndexError):
                    continue
                t = parts[3]
                side = parts[4]
                common = {"price": p, "lot": l, "freq": f, "tipe": t, "is_mega": "Mega" in t}
                if side == "bid":
                    walls_out["bid_walls"].append({**common})
                    bids.append({"price": p, "lot": l, "freq": f})
                else:
                    walls_out["ask_walls"].append({**common})
                    asks.append({"price": p, "lot": l, "freq": f})
                if common["is_mega"]:
                    walls_out["mega_walls"].append(common)

    prev = {
        "price": row.get("price", 0),
        "high": row.get("high", 0),
        "low": row.get("low", 0),
        "avg": row.get("avg", 0),
        "bid_total": row.get("bid_total", 0),
        "ask_total": row.get("ask_total", 0),
        "ratio": row.get("bid_ask_ratio", 0),
        "timestamp": row.get("timestamp", ""),
        "bids": bids,
        "asks": asks,
        "walls": walls_out,
        "volume_lot": 0,
        "volume": 0,
    }

    conn.close()
    return prev


def purge_old_snapshots(days: int = 30) -> int:
    """Delete snapshots older than N days. Returns count deleted."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # Delete orphan walls first (those without a parent snapshot)
    c.execute("""
        DELETE FROM walls WHERE snapshot_id NOT IN (SELECT id FROM snapshots)
    """)
    c.execute("""
        DELETE FROM red_flags WHERE snapshot_id NOT IN (SELECT id FROM snapshots)
    """)

    # Find old snapshot IDs
    old_ids = [r[0] for r in c.execute(
        "SELECT id FROM snapshots WHERE created_at < ?", (cutoff,)
    ).fetchall()]

    if not old_ids:
        conn.commit()
        conn.close()
        return 0

    ids_str = ",".join("?" for _ in old_ids)

    # Delete associated walls and flags
    c.execute(f"DELETE FROM walls WHERE snapshot_id IN ({ids_str})", old_ids)
    c.execute(f"DELETE FROM red_flags WHERE snapshot_id IN ({ids_str})", old_ids)
    c.execute(f"DELETE FROM snapshots WHERE id IN ({ids_str})", old_ids)

    deleted = len(old_ids)
    conn.commit()
    conn.close()
    return deleted


# ──────────────────────────────────────────
#  BATCH SCANNER
# ──────────────────────────────────────────

def batch_scan(image_paths: List[str], engine: str = "auto",
               parallel: int = 3) -> List[Dict]:
    """
    Scan multiple orderbook images in parallel.

    Args:
        image_paths: list of image paths
        engine: "vision", "ocr_fast", "ocr", or "auto"
        parallel: max concurrent workers

    Returns:
        list of results, one per image
    """
    results = []

    def scan_one(path):
        """Single scan worker."""
        start = time.time()
        result = {"image": path, "status": "pending", "data": None, "time_s": 0}

        try:
            if engine == "vision":
                # Use vision model
                import subprocess
                vision_script = Path(__file__).parent / "orderbook_vision.py"
                proc = subprocess.run(
                    ["python3.11", str(vision_script), path],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    if "ticker" in data or "bids" in data:
                        result["data"] = data
                        result["status"] = "success_vision"
                    else:
                        # Fallback to OCR
                        result["data"] = _run_ocr(path)
                        result["status"] = "fallback_ocr"
                else:
                    raise Exception(proc.stderr)
            else:
                result["data"] = _run_ocr(path)
                result["status"] = "success_ocr"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        result["time_s"] = round(time.time() - start, 2)
        return result

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(scan_one, p): p for p in image_paths}
        for f in as_completed(futures):
            results.append(f.result())

    return results


def _run_ocr(path: str) -> Dict:
    """Run OCR and parse output."""
    import subprocess
    ocr_script = Path(__file__).parent / "orderbook_ocr_fast.py"
    proc = subprocess.run(
        ["python3.11", str(ocr_script), path, "--json"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"OCR failed: {proc.stderr}")
    ocr_data = json.loads(proc.stdout)

    # Map to standard format
    price = ocr_data.get("open") or (ocr_data.get("high", 0) + ocr_data.get("low", 0)) // 2
    return {
        "ticker": ocr_data.get("ticker"),
        "timestamp": ocr_data.get("timestamp"),
        "price": price,
        "high": ocr_data.get("high", 0),
        "low": ocr_data.get("low", 0),
        "avg": ocr_data.get("avg", 0),
        "ara": ocr_data.get("ara", 0),
        "arb": ocr_data.get("arb", 0),
        "volume_lot": ocr_data.get("lot", 0),
        "bids": ocr_data.get("bids", []),
        "asks": ocr_data.get("asks", []),
        "confidence": ocr_data.get("confidence", 0),
    }


# ──────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Orderbook wall history & batch scanner")
    sub = parser.add_subparsers(dest="cmd")

    # Save
    save_p = sub.add_parser("save", help="Save snapshot to DB")
    save_p.add_argument("input", help="Analysis JSON file")

    # History
    hist_p = sub.add_parser("history", help="Get wall history")
    hist_p.add_argument("ticker", help="Stock ticker")
    hist_p.add_argument("--hours", type=int, default=6, help="Hours back")

    # Batch scan
    batch_p = sub.add_parser("batch", help="Batch scan multiple images")
    batch_p.add_argument("images", nargs="+", help="Image paths")
    batch_p.add_argument("--engine", default="ocr_fast", choices=["vision", "ocr_fast", "ocr", "auto"])
    batch_p.add_argument("--parallel", type=int, default=3, help="Max parallel workers")

    args = parser.parse_args()

    if args.cmd == "save":
        with open(args.input) as f:
            data = json.load(f)
        sid = save_snapshot(data)
        print(f"Saved snapshot id={sid} | ticker={data.get('ticker')} @ {data.get('timestamp')}")

    elif args.cmd == "history":
        history = get_wall_history(args.ticker, args.hours_back)
        print(json.dumps(history, indent=2))

    elif args.cmd == "batch":
        results = batch_scan(args.images, args.engine, args.parallel)
        print(json.dumps(results, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    sys.exit(main())
