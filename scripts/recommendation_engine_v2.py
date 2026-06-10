#!/usr/bin/env python3
"""
Orderbook Recommendation Engine v2 — Plan.md 3-Tier Entry Framework
=============================================================

Implements:
  - Section 8: Entry Framework (3-tier system with condition counter)
  - Section 9: TP & SL Framework
  - Section 8: Entry Sizing Rule (0/5 → SKIP, 3/5 → 50%, 5/5 → Full)
"""

import sys
import json
import argparse
from typing import Dict, Optional, List, Tuple


def _tick_size(price: int) -> int:
    if price >= 5000: return 10
    if price >= 2000: return 5
    if price >= 500:  return 2
    return 1


def _calc_rr(entry: int, tp: int, sl: int) -> float:
    """Risk/Reward ratio."""
    if entry <= sl:
        return 0
    return (tp - entry) / (entry - sl)


def generate_tiers_planmd(analysis: Dict) -> Dict:
    """
    Generate 3-tier entry using plan.md framework.
    
    Args:
        analysis: Output from OrderbookPlanAnalyzer.analyze_snapshot()
    """
    ticker = analysis.get("ticker", "N/A")
    ts = analysis.get("timestamp", "N/A")
    walls = analysis.get("walls", {})
    bid_ask = analysis.get("bid_ask", {})
    entry_cond = analysis.get("entry_conditions", {})
    red_flags = analysis.get("red_flags", [])
    ihsg = analysis.get("ihsg_context", {})

    price = analysis.get("price", 0)
    tick = _tick_size(price)

    # Extract key walls
    bid_walls = walls.get("bid_walls", [])
    ask_walls = walls.get("ask_walls", [])
    mega_bid = [w for w in walls.get("mega_walls", []) if "Bid" in w["tipe"]]
    mega_ask = [w for w in walls.get("mega_walls", []) if "Ask" in w["tipe"]]

    # Support / Resistance levels
    support_lvls = sorted([w["price"] for w in (bid_walls + mega_bid)], reverse=True)
    resistance_lvls = sorted([w["price"] for w in (ask_walls + mega_ask)])

    strongest_support = support_lvls[0] if support_lvls else None
    strongest_resistance = resistance_lvls[0] if resistance_lvls else None

    # Base SL/TP targets
    low_hari = analysis.get("low", 0)
    ara = ihsg.get("ara", analysis.get("ara", 0))

    tier2_support = support_lvls[1] if len(support_lvls) > 1 else (
        strongest_support - tick if strongest_support else price - 5 * tick
    )

    conditions_met = entry_cond.get("kondisi_terpenuhi", 0)
    sizing = entry_cond.get("sizing", {})
    size_pct = sizing.get("size_persen", 0)

    red_flag_active = analysis.get("has_red_flag", False)

    result = {"ticker": ticker, "timestamp": ts, "tiers": {}, "summary": {}}

    # ──────────────────────────────────────
    #  Red flags — mark but STILL generate tiers
    # ──────────────────────────────────────
    if red_flag_active:
        result["red_flag_warning"] = f"Red flag(s) aktif: {', '.join(r['id'] for r in red_flags)}"

    # ──────────────────────────────────────
    #  TIER 1 — AGGRESSIVE
    #  Entry: current price / nearest ask
    #  SL: ~1 tick below strongest support
    #  TP: nearest resistance
    #  RR min: 1:1.5
    # ──────────────────────────────────────
    agg_entry_min = price
    agg_entry_max = price + tick
    agg_sl = (strongest_support - tick * 2) if strongest_support and strongest_support < price else price - tick * 3
    agg_tp = (strongest_resistance - tick) if strongest_resistance else price + 5 * tick
    agg_rr = _calc_rr(agg_entry_min, agg_tp, agg_sl)

    agg_valid = agg_rr >= 1.5 and conditions_met >= 2 and not red_flag_active

    result["tiers"]["aggressive"] = {
        "entry": f"{agg_entry_min}–{agg_entry_max}",
        "tp": agg_tp,
        "sl": agg_sl,
        "rr": round(agg_rr, 2),
        "valid": agg_valid,
        "reasoning": [
            f"Entry near current price ({agg_entry_min}–{agg_entry_max})",
            f"SL {tick}-tick below support {agg_sl}",
            f"TP at nearest resistance {agg_tp}",
            f"RR {agg_rr:.2f}:1 {'✅' if agg_rr >= 1.5 else '❌ < 1.5 minimum'}" if agg_rr > 0 else "RR: 🚫 entry <= SL",
        ]
    }
    if not agg_valid:
        result["tiers"]["aggressive"]["alasan"] = f"RR {agg_rr:.2f}:1 < 1.5 or conditions {conditions_met}/5"

    # ──────────────────────────────────────
    #  TIER 2 — MODERAT
    #  Entry: pullback to support
    #  SL: below strongest support
    #  TP: mid range
    #  RR min: 1:1.8
    # MOD
    mod_entry_min = tier2_support if tier2_support else price
    mod_entry_max = mod_entry_min + tick
    # SL must be < entry
    mod_sl = (strongest_support - tick * 2) if strongest_support and strongest_support < mod_entry_min else mod_entry_min - tick * 3
    mod_tp = (strongest_resistance - tick) if strongest_resistance and strongest_resistance > mod_entry_min else price + 5 * tick
    mod_rr = _calc_rr(mod_entry_min, mod_tp, mod_sl)

    mod_valid = mod_rr >= 1.8 and conditions_met >= 3

    result["tiers"]["moderat"] = {
        "entry": f"{mod_entry_min}–{mod_entry_max}",
        "tp": mod_tp,
        "sl": mod_sl,
        "rr": round(mod_rr, 2),
        "valid": mod_valid,
        "reasoning": [
            f"Entry at pullback to support {mod_entry_min}–{mod_entry_max}",
            f"SL 3 tick below support {mod_sl}",
            f"TP at resistance {mod_tp}",
            f"RR {mod_rr:.2f}:1 {'✅' if mod_rr >= 1.8 else '❌ < 1.8 minimum'}",
        ]
    }
    if not mod_valid:
        result["tiers"]["moderat"]["alasan"] = f"RR {mod_rr:.2f}:1 < 1.8 or conditions {conditions_met}/5 < 3"

    # LR
    # LR: use LOWEST support as floor (deepest accumulation zone per plan.md §8)
    lr_floor = min(support_lvls) if support_lvls else (low_hari or price)
    lr_entry_min = lr_floor
    lr_entry_max = lr_floor + tick * 2
    lr_sl = lr_floor - tick * 3
    # TP1: nearest support above entry
    lr_tp1 = next((s for s in support_lvls if s > lr_entry_max), price + tick * 2)
    lr_tp2 = (strongest_resistance - tick) if strongest_resistance and strongest_resistance > lr_entry_min else price + 5 * tick

    lr_rr = _calc_rr(lr_entry_min, lr_tp2, lr_sl)
    lr_valid = lr_rr >= 2.0 and conditions_met >= 3

    lr_reasoning = [
        f"Entry near support wall {lr_entry_min}–{lr_entry_max}",
        f"SL 3 tick below wall {lr_sl}",
        f"TP1: back to support {lr_tp1}",
        f"TP2: resistance {lr_tp2}",
        f"RR {lr_rr:.2f}:1 {'✅' if lr_rr >= 2.0 else '❌ < 2.0 minimum'}",
        f"Kondisi terpenuhi: {conditions_met}/5 → Size: {sizing.get('aksi', 'SKIP')}",
    ]

    if mega_bid:
        lr_reasoning.append(f"Floor: Mega bid wall {mega_bid[0]['price']} ({mega_bid[0]['lot']:,} lot, freq {mega_bid[0]['freq']})")
    if low_hari and lr_sl < low_hari:
        lr_reasoning.append(f"✅ SL {lr_sl} < Low {low_hari} — proteksi ekstra")

    result["tiers"]["low_risk"] = {
        "entry": f"{lr_entry_min}–{lr_entry_max}",
        "tp1": lr_tp1,
        "tp2": lr_tp2,
        "sl": lr_sl,
        "rr": round(lr_rr, 2),
        "size_persen": size_pct,
        "sizing_aksi": sizing.get("aksi", "SKIP"),
        "conditions_met": f"{conditions_met}/5",
        "valid": lr_valid,
        "reasoning": lr_reasoning,
    }

    # ──────────────────────────────────────
    #  Summary
    # ──────────────────────────────────────
    best_tier = "SKIP"
    for t in ("low_risk", "moderat", "aggressive"):
        if result["tiers"][t]["valid"]:
            best_tier = t.upper()
            break

    result["summary"] = {
        "bias": bid_ask.get("bias", "UNKNOWN"),
        "ratio": bid_ask.get("ratio", 0),
        "best_tier": best_tier,
        "sizing": sizing.get("aksi", "SKIP"),
    }

    # Inject additional context
    result["ihsg_warning"] = ihsg.get("ara_warning")

    return result


# ──────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plan.md recommendation engine")
    parser.add_argument("input", help="Analysis JSON from orderbook_analyzer_v2.py")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    with open(args.input) as f:
        analysis = json.load(f)

    result = generate_tiers_planmd(analysis)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        tiers = result.get("tiers", {})
        print(f"\n=== REKOMENDASI {result.get('ticker')} @ {result.get('timestamp')} ===\n")

        if result.get("status") == "SKIP":
            print(f"🚫 SKIP: {result.get('alasan', '')}")
            return

        for tname in ("aggressive", "moderat", "low_risk"):
            t = tiers.get(tname, {})
            valid = t.get("valid", False)
            icon = "✅" if valid else "❌"
            print(f"{icon} {tname.upper()}: Entry {t.get('entry')} | TP {t.get('tp')} | SL {t.get('sl')} | RR {t.get('rr', 0):.2f}:1")
            for r in t.get("reasoning", []):
                print(f"   • {r}")
            print()

        s = result.get("summary", {})
        print(f"Bias: {s.get('bias')} (ratio {s.get('ratio'):.1f}x)")
        print(f"Best Tier: {s.get('best_tier')} | Size: {s.get('sizing')}")

        if result.get("ihsg_warning"):
            print(f"⚠ {result['ihsg_warning']}")


if __name__ == "__main__":
    sys.exit(main())
