#!/usr/bin/env python3
"""
Output Formatter v2 — Plan.md compact format for Telegram

Outputs structured report with all plan.md sections.
Designed for Telegram compact readability.
"""

import sys
import json
import argparse
from typing import Dict, List, Optional
from datetime import datetime


def format_plan_report(ocr_data: Dict, analysis: Dict, recommendations: Dict) -> str:
    """
    Full plan.md report — compact format for Telegram.

    Sections:
    - Header: ticker, time, bias, phase
    - Market: gap, session, divergence
    - Orderbook: ratio, freq ratio, spread
    - Walls: 4 types
    - Phase: current phase + evidence
    - Delta signals (if any)
    - Entry conditions: met/not met + sizing
    - Red flags (if any)
    - Recommendations: 3 tiers with reasoning
    """
    lines = []

    ticker = analysis.get("ticker", ocr_data.get("ticker", "N/A"))
    ts = analysis.get("timestamp", ocr_data.get("timestamp", "N/A"))
    price = analysis.get("price", 0) or ocr_data.get("price", 0) or ocr_data.get("avg", 0) or 0

    bid_ask = analysis.get("bid_ask", {})
    freq = analysis.get("freq_ratio", {})
    divergence = analysis.get("divergence", {})
    walls = analysis.get("walls", {})
    phase = analysis.get("phase", {})
    signals = analysis.get("delta_signals", [])
    entry_cond = analysis.get("entry_conditions", {})
    red_flags = analysis.get("red_flags", [])
    ihsg = analysis.get("ihsg_context", {})
    sr_flips = analysis.get("sr_flips", [])

    tiers = recommendations.get("tiers", {})
    summary = recommendations.get("summary", {})

    # ── Header ──
    bias_emoji = {
        "bullish_kuat": "🟢", "bullish_moderat": "🟢", "bullish_ringan": "🟩",
        "netral": "⚪", "bearish": "🔴"
    }.get(bid_ask.get("bias", ""), "⚪")

    phase_emoji = {
        "DISTRIBUSI": "🔴", "CAPITULATION": "🟠",
        "SILENT_ACCUMULATION": "🟡", "REVERSAL_CONFIRMATION": "🟢",
        "RECOVERY": "🟢", "UNDETERMINED": "⚪"
    }.get(phase.get("fase", ""), "⚪")

    lines.append(f"**{ticker} @ {ts}**")
    lines.append(f"Price: {price:,}")
    lines.append(f"Bias: {bias_emoji} {bid_ask.get('label', 'N/A')} (ratio {bid_ask.get('ratio', 0):.1f}x)")
    lines.append(f"Fase: {phase_emoji} {phase.get('fase', '?')} ({phase.get('confidence', 0):.0f}%)")
    lines.append("")

    # ── Market Context ──
    session = ihsg.get("session", {})
    session_name = session.get("nama", "?")
    session_note = session.get("karakter", "")

    lines.append(f"**Market**")
    lines.append(f"Session: {session_name} — {session_note}")
    lines.append(f"Divergence: {divergence.get('divergence_pct', 0):+.2f}% ({divergence.get('label', '?')})")
    if freq:
        lines.append(f"Freq Ratio: {freq.get('freq_ratio', 0):.1f}x (lot {freq.get('lot_ratio', 0):.1f}x) — {freq.get('interpretasi', '')}")
    ara_warn = ihsg.get("ara_warning")
    if ara_warn:
        lines.append(f"⚠ {ara_warn}")
    lines.append("")

    # ── Orderbook Summary ──
    lines.append(f"**Orderbook**")
    bid_total = analysis.get("bid_total", 0)
    ask_total = analysis.get("ask_total", 0)
    lines.append(f"Bid: {bid_total:,} lot vs Ask: {ask_total:,} lot")
    lines.append(f"Ratio: {bid_ask.get('ratio', 0):.2f}x — {bid_ask.get('label', '')}")
    if bid_ask.get("peringatan"):
        lines.append(f"⚠ {bid_ask['peringatan']}")
    lines.append("")

    # ── Walls ──
    bid_walls = walls.get("bid_walls", [])
    ask_walls = walls.get("ask_walls", [])
    mega = walls.get("mega_walls", [])

    if bid_walls or ask_walls or mega:
        lines.append(f"**Walls**")
        for w in bid_walls:
            lines.append(f"  Bid Wall: {w['price']:,} ({w['lot']:,} lot, freq {w['freq']}, jarak {w['jarak_dari_harga']} tick)")
        for w in ask_walls:
            lines.append(f"  Ask Wall: {w['price']:,} ({w['lot']:,} lot, freq {w['freq']}, jarak {w['jarak_dari_harga']} tick)")
        for w in mega:
            icon = "🟢" if "Bid" in w["tipe"] else "🔴"
            lines.append(f"  {icon} Mega {w['tipe']}: {w['price']:,} ({w['lot']:,} lot, freq {w['freq']})")
        lines.append("")

    # ── Phase Detail ──
    lines.append(f"**Phase: {phase.get('fase', '?')}**")
    for ev in phase.get("evidence", []):
        lines.append(f"  • {ev}")
    lines.append(f"  Strategi: {phase.get('strategi', '')}")
    lines.append("")

    # ── Delta Signals ──
    if signals:
        lines.append(f"**Signals ({len(signals)})**")
        for s in signals:
            emoji = "🟢" if s["tipe"] == "bullish" else ("🔴" if s["tipe"] == "bearish" else "🔄")
            lines.append(f"  {emoji} [{s['kekuatan']:.0%}] {s['nama']}: {s['detail']}")
        lines.append("")

    # ── S/R Flips ──
    if sr_flips:
        lines.append(f"**S/R Flip**")
        for f in sr_flips:
            arrow = "⬆" if f["arah"] == "tembus_ke_atas" else "⬇"
            lines.append(f"  {arrow} {f['price']:,}: {f['side_asal']} → {f['flipped_to']} (lot {f['lot_baru']:,})")
        lines.append("")

    # ── Entry Conditions ──
    met_count = entry_cond.get("kondisi_terpenuhi", 0)
    sizing = entry_cond.get("sizing", {})

    lines.append(f"**Entry Conditions: {met_count}/5**")
    for m in entry_cond.get("met", []):
        lines.append(f"  ✅ {m}")
    for n in entry_cond.get("not_met", []):
        lines.append(f"  ❌ {n}")
    lines.append(f"  → Size: {sizing.get('aksi', 'SKIP')} ({sizing.get('size_persen', 0)}%)")
    lines.append("")

    # ── Red Flags ──
    if red_flags:
        lines.append(f"**⚠ RED FLAGS**")
        for rf in red_flags:
            sev = "🚨" if rf["severitas"] == "CRITICAL" else ("⚠" if rf["severitas"] == "HIGH" else "⚡")
            lines.append(f"  {sev} [{rf['severitas']}] {rf['id']}: {rf['nama']}")
        lines.append("")

    # ── Recommendations ──
    lines.append(f"**Rekomendasi Entry**")
    if recommendations.get("status") == "SKIP":
        lines.append(f"🚫 {recommendations.get('alasan', '')}")
    else:
        for tname in ("aggressive", "moderat", "low_risk"):
            t = tiers.get(tname, {})
            valid = t.get("valid", False)
            icon = "✅" if valid else "❌"
            entry = t.get("entry", "?")
            tp = t.get("tp", "?")
            tp2 = t.get("tp2", "")
            sl = t.get("sl", "?")
            rr = t.get("rr", 0)
            lines.append(f"{icon} **{tname.upper()}**: Entry {entry} | TP {tp}" + (f" → {tp2}" if tp2 else "") + f" | SL {sl} | RR {rr:.2f}:1")
            for r in t.get("reasoning", []):
                lines.append(f"  • {r}")
            if t.get("conditions_met"):
                lines.append(f"  • Kondisi: {t['conditions_met']}, Size: {t.get('sizing_aksi', '?')}")
            lines.append("")

        best = summary.get("best_tier", "SKIP")
        lines.append(f"**Best Tier: {best}** | Bias: {summary.get('bias', '?')}")

    # ── Footer ──
    lines.append(f"---")
    lines.append(f"*Plan.md Analysis • {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def format_caveman_summary(analysis: Dict, recommendations: Dict) -> str:
    """Fixed template v2 — comprehensive compact format matching IDX_Orderbook_Template_v2.md"""
    ticker = analysis.get("ticker", "?")
    price = analysis.get("price", 0)
    bid_ask = analysis.get("bid_ask", {})
    phase = analysis.get("phase", {})
    red_flags = analysis.get("red_flags", [])
    entry_cond = analysis.get("entry_conditions", {})
    walls = analysis.get("walls", {})
    divergence = analysis.get("divergence", {})
    signals = analysis.get("delta_signals", [])
    ihsg = analysis.get("ihsg_context", {})

    # Header data
    high = analysis.get("high", 0)
    low = analysis.get("low", 0)
    avg = analysis.get("avg", 0)
    prev = analysis.get("prev", 0)
    bid_total = analysis.get("bid_total", 0)
    ask_total = analysis.get("ask_total", 0)
    bid_freq_total = analysis.get("bid_freq_total", 0)
    ask_freq_total = analysis.get("ask_freq_total", 0)
    vol = analysis.get("volume", 0)
    val = analysis.get("value", 0)

    # Walls
    bid_walls = walls.get("bid_walls", [])
    ask_walls = walls.get("ask_walls", [])
    mega_bid = [w for w in walls.get("mega_walls", []) if "Bid" in w["tipe"]]
    mega_ask = [w for w in walls.get("mega_walls", []) if "Ask" in w["tipe"]]
    all_bid_walls = sorted(bid_walls + mega_bid, key=lambda w: w["lot"], reverse=True)[:3]
    all_ask_walls = sorted(ask_walls + mega_ask, key=lambda w: w["lot"], reverse=True)[:3]

    # Tiers
    tiers = recommendations.get("tiers", {})

    # Derived
    ratio = bid_ask.get("ratio", 0)
    ratio_label = bid_ask.get("label", "?")
    div_pct = divergence.get("divergence_pct", 0)
    pct_chg = ((price - prev) / prev * 100) if prev else 0
    trend_emoji = "🟢" if pct_chg > 0 else ("🔴" if pct_chg < 0 else "⬜")
    fase = phase.get("fase", "UNDETERMINED")
    cond = entry_cond.get("kondisi_terpenuhi", 0)

    # Size rule
    size_map = {0: 0, 1: 0, 2: 30, 3: 50, 4: 75, 5: 100}
    size = size_map.get(cond, 0)

    # Low flag
    low_flag = "▼" if low == price else ""

    # Format helpers
    def fmt_lot(n):
        if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
        if n >= 1_000: return f"{n/1_000:.0f}K"
        return str(n)

    def fmt_val(n):
        if n >= 1_000_000_000_000: return f"{n/1_000_000_000_000:.2f}T"
        if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        return str(n)

    def get_cond_icon(key):
        for m in entry_cond.get("met", []):
            if key in m: return "✅"
        for n in entry_cond.get("not_met", []):
            if key in n:
                if "❌" in n or "jelas" in n.lower(): return "❌"
                return "⏳"
        return "⏳"

    ts = analysis.get("timestamp", datetime.now().strftime("%H:%M"))
    lines = []

    # ━━━ Header ━━━
    lines.append(f"━━━ {ticker} {price:,} {trend_emoji}{pct_chg:+.2f}% | {ts} ━━━")
    lines.append(f"H:{high:,} L:{low:,}{low_flag} Avg:{avg:,}({div_pct:+.1f}%)")
    lines.append(f"Vol:{fmt_lot(vol)} Val:{fmt_val(val)}")
    lines.append("")

    # ━━━ Bid/Ask Totals + Ratio ━━━
    lines.append(f"BID {bid_total:,}lot f{bid_freq_total:,}  ║  ASK {ask_total:,}lot f{ask_freq_total:,}")
    lines.append(f"▬▬▬▬▬▬▬ {ratio:.2f}x {ratio_label} ▬▬▬▬▬▬▬")
    lines.append(f"FASE ░ {fase}  Cond:{cond}/5  Size:{size}%")
    lines.append("")

    # ━━━ Walls ━━━
    lines.append("🟢 BID WALLS          🔴 ASK WALLS")
    max_walls = max(len(all_bid_walls), len(all_ask_walls))
    for i in range(min(max_walls, 3)):
        bid_part = ""
        ask_part = ""
        if i < len(all_bid_walls):
            bw = all_bid_walls[i]
            bid_part = f"{bw['price']:,} │ {fmt_lot(bw['lot'])} │ f{bw['freq']}"
        if i < len(all_ask_walls):
            aw = all_ask_walls[i]
            tag = " ⚡CEIL" if i == 0 else ""
            ask_part = f"{aw['price']:,} │ {fmt_lot(aw['lot'])} │ f{aw['freq']}{tag}"
        lines.append(f"{bid_part.ljust(22)}  {ask_part}")

    # Floor line with actual delta arrow
    if mega_bid:
        mb = mega_bid[0]
        # Check if prev data exists for floor delta
        fl_dir = "→"
        prev_floor = analysis.get("prev_floor_lot")
        if prev_floor is not None:
            if mb["lot"] > prev_floor:
                fl_dir = "↑"
            elif mb["lot"] < prev_floor:
                fl_dir = "↓"
        lines.append(f"FLOOR→{mb['price']:,}│{fmt_lot(mb['lot'])}{fl_dir}│f{mb['freq']}")
    lines.append("")

    # ━━━ Conditions ━━━
    cond_labels = [
        ("harga_dekat_mega_wall_bid", "Dekat mega wall bid"),
        ("wall_tidak_berkurang", "Wall bid hold/tebal"),
        ("harga_flat_2_snapshot", "Harga flat 2+ snap"),
        ("bid_total_naik_lintas_snapshot", "Bid total naik"),
        ("candle_reversal_volume_spike", "Candle reversal + vol"),
    ]

    lines.append("CONDITIONS [LR]")
    c1 = f"{get_cond_icon(cond_labels[0][0])} {cond_labels[0][1]}"
    c2 = f"{get_cond_icon(cond_labels[1][0])} {cond_labels[1][1]}"
    lines.append(f"{c1.ljust(26)}{c2}")
    c3 = f"{get_cond_icon(cond_labels[2][0])} {cond_labels[2][1]}"
    c4 = f"{get_cond_icon(cond_labels[3][0])} {cond_labels[3][1]}"
    lines.append(f"{c3.ljust(26)}{c4}")
    c5 = f"{get_cond_icon(cond_labels[4][0])} {cond_labels[4][1]}"
    lines.append(c5)
    lines.append("")

    # ━━━ Tiers ━━━
    agg = tiers.get("aggressive", {})
    mod = tiers.get("moderat", {})
    lr = tiers.get("low_risk", {})

    # AGG status
    agg_valid = agg.get("valid", False)
    if agg_valid:
        agg_status = "✅ VALID"
    elif cond >= 2:
        agg_status = f"⚠️ PARTIAL (cond {cond}/5)"
    else:
        reason = "ratio bearish" if ratio < 0.8 else ("fase belum konfirmasi" if fase == "UNDETERMINED" else "cond < 2")
        agg_status = f"— SKIP ({reason})"

    lines.append(f"▸ AGG  {agg_status}")
    if agg_valid or cond >= 2:
        lines.append(f"       E:{agg.get('entry', '-')} SL:{agg.get('sl', '-')} TP1:{agg.get('tp', '-')} TP2:{agg.get('tp2', '-')} RR:{agg.get('rr', 0):.1f}x")
    else:
        lines.append(f"       E:- SL:- TP1:- TP2:- RR:-")
    lines.append(f"▸ MOD  E:{mod.get('entry', '-')} SL:{mod.get('sl', '-')} TP1:{mod.get('tp', '-')} TP2:{mod.get('tp2', '-')} RR:{mod.get('rr', 0):.1f}x")

    # LR
    lr_tp1 = lr.get("tp1", lr.get("tp", "-"))
    lr_tp2 = lr.get("tp2", "-")
    lr_entry = lr.get("entry", "-")
    lr_sl = lr.get("sl", "-")
    lr_rr = lr.get("rr", 0)
    lines.append(f"▸ LR   E:{lr_entry} SL:{lr_sl} TP1:{lr_tp1} TP2:{lr_tp2} RR:{lr_rr:.1f}x")

    # SL/TP distance for LR
    sl_dist_low, sl_dist_high, tp1_dist_low, tp1_dist_high = 0, 0, 0, 0
    if lr_entry != "-" and lr_sl != "-":
        try:
            entry_low = int(str(lr_entry).split("–")[0].replace(",", ""))
            entry_high = int(str(lr_entry).split("–")[1].replace(",", "")) if "–" in str(lr_entry) else entry_low
            sl_val = int(str(lr_sl).replace(",", ""))
            tp1_val = int(str(lr_tp1).replace(",", "")) if lr_tp1 != "-" else 0
            sl_dist_low = entry_low - sl_val
            sl_dist_high = entry_high - sl_val
            tp1_dist_low = tp1_val - entry_low if tp1_val else 0
            tp1_dist_high = tp1_val - entry_high if tp1_val else 0
            lines.append(f"       SL-dist:{sl_dist_low}–{sl_dist_high}pt | TP1-dist:{tp1_dist_high}–{tp1_dist_low}pt")
        except (ValueError, IndexError):
            pass
    lines.append("")

    # ━━━ Delta ━━━
    if signals:
        lines.append(f"⚡ DELTA (vs {analysis.get('prev_timestamp', '-')})")
        for s in signals[:3]:
            lines.append(f"   {s.get('detail', '')}")
        lines.append("")

    # ━━━ Alert ━━━
    if red_flags:
        rf = red_flags[0]
        lines.append(f"⚠️ {rf.get('nama', rf.get('id', 'Red flag aktif'))}")
    elif cond < 3 and fase == "UNDETERMINED":
        lines.append(f"⚠️ Fase belum jelas — observe dulu")
    elif cond >= 3:
        lines.append(f"✅ Setup valid — entry sesuai tier & size rule")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# ──────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Format v2 reports")
    parser.add_argument("analysis", help="Analysis JSON from analyzer_v2")
    parser.add_argument("--recs", help="Recommendations JSON (optional)")
    parser.add_argument("--ocr", help="OCR data JSON (optional)")
    parser.add_argument("--caveman", action="store_true", help="Compact 1-liner instead of full")
    args = parser.parse_args()

    with open(args.analysis) as f:
        analysis = json.load(f)

    ocr_data = {}
    if args.ocr:
        with open(args.ocr) as f:
            ocr_data = json.load(f)

    recs = {}
    if args.recs:
        with open(args.recs) as f:
            recs = json.load(f)

    if args.caveman:
        print(format_caveman_summary(analysis, recs))
    else:
        print(format_plan_report(ocr_data, analysis, recs))


if __name__ == "__main__":
    sys.exit(main())
