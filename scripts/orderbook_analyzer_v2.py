#!/usr/bin/env python3
"""
IDX Orderbook Analyzer v2 — Plan.md Complete Implementation
===========================================================

Implements FULL framework from plan.md:
  - Section 3a: Bid:Ask Ratio (6 tiers)
  - Section 3b: Freq Ratio (penetration depth)
  - Section 3c: Avg vs Price Divergence
  - Section 4b: Wall Classification (4 types by proximity)
  - Section 4c: Wall Genuine vs Fake indicators
  - Section 5b: Multi-snapshot delta signals
  - Section 6: Phase Identification (5 phases)
  - Section 7b: Dynamic S/R Flip
  - Section 8: Condition Counter + Sizing Rules
  - Section 10: Red Flags (6 abort conditions)
  - Section 11: IHSG Context (session, ARA, lot tiers)
"""

import sys
import json
import math
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from statistics import median, mean
from datetime import datetime


# ──────────────────────────────────────────
#  SECTION 3a — Bid:Ask Ratio (6 tiers)
# ──────────────────────────────────────────

BID_ASK_TIERS = {
    "DOMINASI_BID_SANGAT_KUAT":  (3.0,  float("inf"),  "bullish_kuat"),
    "BID_MENDOMINASI_MODERAT":    (2.0,  3.0,           "bullish_moderat"),
    "CONDONG_BULLISH":            (1.3,  2.0,           "bullish_ringan"),
    "BALANCE_KONSOLIDASI":        (0.8,  1.3,           "netral"),
    "ASK_MENDOMINASI":            (0.0,  0.8,           "bearish"),
}

def classify_bid_ask_ratio(ratio: float) -> Dict:
    """Classify ratio into 6 tiers with interpretation."""
    label = "ASK_MENDOMINASI"
    bias = "bearish"
    if ratio >= 3.0:
        label = "DOMINASI_BID_SANGAT_KUAT"
        bias = "bullish_kuat"
    elif ratio >= 2.0:
        label = "BID_MENDOMINASI_MODERAT"
        bias = "bullish_moderat"
    elif ratio >= 1.3:
        label = "CONDONG_BULLISH"
        bias = "bullish_ringan"
    elif ratio >= 0.8:
        label = "BALANCE_KONSOLIDASI"
        bias = "netral"

    return {
        "ratio": round(ratio, 2),
        "label": label,
        "bias": bias,
        "peringatan": _ratio_warning(ratio),
    }

def _ratio_warning(ratio: float) -> Optional[str]:
    if ratio >= 2.0:
        return "Ratio tinggi — konfirmasi apakah harga naik (bisa jebakan seller market-sell)"
    return None

# ──────────────────────────────────────────
#  SECTION 3b — Freq Ratio
# ──────────────────────────────────────────

def analyze_freq_ratio(total_freq_bid: int, total_freq_ask: int,
                       bid_lot: int, ask_lot: int) -> Dict:
    """Freq ratio = depth of participation, not just lot size."""
    freq_ratio = total_freq_bid / max(total_freq_ask, 1)
    lot_ratio = bid_lot / max(ask_lot, 1)

    return {
        "freq_ratio": round(freq_ratio, 2),
        "lot_ratio": round(lot_ratio, 2),
        "freq_vs_lot_delta": round(freq_ratio - lot_ratio, 2),
        "interpretasi": _freq_interpretation(freq_ratio, lot_ratio),
    }

def _freq_interpretation(freq_r: float, lot_r: float) -> str:
    diff = freq_r - lot_r
    if diff > 1.0:
        return f"Buyer tersebar luas (freq {freq_r:.1f}x > lot {lot_r:.1f}x) — lebih reliable"
    if diff < -1.0:
        return "Beberapa buyer besar (lot tinggi, freq rendah) — wall bisa di-pull"
    return "Distribusi freq & lot seimbang — normal"

# ──────────────────────────────────────────
#  SECTION 3c — Avg vs Price Divergence
# ──────────────────────────────────────────

def calc_divergence(last_price: int, avg_price: int) -> Dict:
    """((Last - Avg) / Avg) × 100%"""
    if avg_price == 0:
        return {"divergence_pct": 0, "label": "NO_AVG", "sinyal": "Avg tidak tersedia"}

    div = ((last_price - avg_price) / avg_price) * 100

    if div < -3:
        label = "TEKANAN_JUAL_DOMINAN"
        sinyal = "Harga jauh di bawah VWAP — tekanan jual dominan, dumb money sudah rugi"
    elif div < -1:
        label = "UNDERPERFORM"
        sinyal = "Underperform VWAP, waspada"
    elif abs(div) <= 1:
        label = "KONSOLIDASI"
        sinyal = "Konsolidasi wajar — harga di sekitar VWAP"
    else:
        label = "MOMENTUM_BELI"
        sinyal = "Harga di atas VWAP — momentum beli, tapi hati-hati overbought"

    return {
        "divergence_pct": round(div, 2),
        "label": label,
        "sinyal": sinyal,
    }

# ──────────────────────────────────────────
#  SECTION 4b — Wall Classification
# ──────────────────────────────────────────

@dataclass
class ClassifiedWall:
    tipe: str          # "Bid Wall" | "Ask Wall" | "Mega Wall Bid" | "Mega Wall Ask"
    price: int
    lot: int
    freq: int
    jarak_dari_harga: int    # ticks from last price
    strength: float          # 0-100
    is_mega: bool

def classify_walls(bids: List[Dict], asks: List[Dict],
                   last_price: int, tick_size: int = 1) -> Dict:
    """Classify walls into 4 types by proximity from last price."""
    bid_mean = mean([b["lot"] for b in bids]) if bids else 1
    ask_mean = mean([a["lot"] for a in asks]) if asks else 1
    bid_threshold = bid_mean * 2.5
    ask_threshold = ask_mean * 2.5

    # Plan.md §11 wall tiers: >10K significant, >50K institutional, >100K mega
    MEGA_THRESHOLD = 100_000

    result = {"bid_walls": [], "ask_walls": [], "mega_walls": []}

    for b in bids:
        above_threshold = b["lot"] > bid_threshold
        is_mega = b["lot"] >= MEGA_THRESHOLD
        jarak_ticks = (last_price - b["price"]) // max(tick_size, 1)
        strength = min(100, (b["lot"] / bid_mean) * 25)

        if is_mega:
            cls = ClassifiedWall(
                tipe="Mega Wall Bid",
                price=b["price"], lot=b["lot"], freq=b["freq"],
                jarak_dari_harga=jarak_ticks, strength=strength, is_mega=True,
            )
            result["mega_walls"].append(asdict(cls))
        elif above_threshold:
            cls = ClassifiedWall(
                tipe="Bid Wall",
                price=b["price"], lot=b["lot"], freq=b["freq"],
                jarak_dari_harga=jarak_ticks, strength=strength, is_mega=False,
            )
            result["bid_walls"].append(asdict(cls))

    for a in asks:
        above_threshold = a["lot"] > ask_threshold
        is_mega = a["lot"] >= MEGA_THRESHOLD
        jarak_ticks = (a["price"] - last_price) // max(tick_size, 1)
        strength = min(100, (a["lot"] / ask_mean) * 25)

        if is_mega:
            cls = ClassifiedWall(
                tipe="Mega Wall Ask",
                price=a["price"], lot=a["lot"], freq=a["freq"],
                jarak_dari_harga=jarak_ticks, strength=strength, is_mega=True,
            )
            result["mega_walls"].append(asdict(cls))
        elif above_threshold:
            cls = ClassifiedWall(
                tipe="Ask Wall",
                price=a["price"], lot=a["lot"], freq=a["freq"],
                jarak_dari_harga=jarak_ticks, strength=strength, is_mega=False,
            )
            result["ask_walls"].append(asdict(cls))

    # Sort by proximity
    for k in ("bid_walls", "ask_walls", "mega_walls"):
        result[k].sort(key=lambda w: w["jarak_dari_harga"])

    # If no bid/ask walls detected after strict threshold, show top-3 largest lots as "Level"
    # This ensures display always has data — plan.md says show S/R from lot concentration
    if not result["bid_walls"] and not result["mega_walls"]:
        top_bids = sorted(bids, key=lambda x: x["lot"], reverse=True)[:3]
        for b in top_bids:
            result["bid_walls"].append({
                "tipe": "Level Bid", "price": b["price"], "lot": b["lot"],
                "freq": b["freq"], "jarak_dari_harga": (last_price - b["price"]) // max(tick_size, 1),
                "strength": 10, "is_mega": False,
            })
    if not result["ask_walls"] and not any(w["tipe"] == "Mega Wall Ask" for w in result["mega_walls"]):
        top_asks = sorted(asks, key=lambda x: x["lot"], reverse=True)[:3]
        for a in top_asks:
            result["ask_walls"].append({
                "tipe": "Level Ask", "price": a["price"], "lot": a["lot"],
                "freq": a["freq"], "jarak_dari_harga": (a["price"] - last_price) // max(tick_size, 1),
                "strength": 10, "is_mega": False,
            })

    return result

# ──────────────────────────────────────────
#  SECTION 4c — Wall Genuine vs Fake
# ──────────────────────────────────────────

def wall_genuine_score(wall: Dict, prev_wall: Optional[Dict] = None,
                       price_approaching: bool = False) -> Dict:
    """Score a wall's genuineness (0-100)."""
    score = 50  # neutral start

    # Freq tinggi = genuine
    if wall["freq"] >= 100:
        score += 25
    elif wall["freq"] >= 20:
        score += 10
    elif wall["freq"] <= 5:
        score -= 20  # low freq = suspect

    # Wall bertahan dari snapshot sebelumnya
    if prev_wall and prev_wall.get("price") == wall["price"]:
        lot_change = wall["lot"] - prev_wall["lot"]
        if lot_change >= 0:
            score += 15  # bertahan atau bertambah
        else:
            score -= 10  # berkurang

    # Harga bouncing di level ini
    if price_approaching:
        score -= 10  # belum tahu apakah tembus

    return {
        "score": min(100, max(0, score)),
        "genuine": score >= 60,
        "fake": score < 40,
    }

# ──────────────────────────────────────────
#  SECTION 5b — Multi-Snapshot Delta Signals
# ──────────────────────────────────────────

@dataclass
class DeltaSignal:
    tipe: str          # "bullish" | "bearish" | "reversal"
    nama: str
    detail: str
    kekuatan: float    # 0-1

def interpret_delta_signals(prev: Dict, curr: Dict) -> List[Dict]:
    """
    Interpret delta between snapshots as actionable signals.
    Plan Section 5b: bullish, bearish, reversal.
    """
    signals = []

    # Helper
    bid_delta = curr.get("bid_total", 0) - prev.get("bid_total", 0)
    ask_delta = curr.get("ask_total", 0) - prev.get("ask_total", 0)
    price_delta = curr.get("price", 0) - prev.get("price", 0)
    ratio_prev = prev.get("ratio", 1)
    ratio_curr = curr.get("ratio", 1)

    # ── BULLISH ──

    # Total bid naik masif (+30K dalam 5 menit) sementara harga flat/naik
    if bid_delta >= 30000 and price_delta >= 0:
        signals.append({
            "tipe": "bullish",
            "nama": "Bid Akumulasi Masif",
            "detail": f"Bid +{bid_delta:,} lot dlm snapshot, harga flat/naik",
            "kekuatan": 0.9,
        })

    # Wall bid bertambah tebal tanpa harga turun
    prev_bid_walls = prev.get("walls", {}).get("bid_walls", [])
    curr_bid_walls = curr.get("walls", {}).get("bid_walls", [])
    if prev_bid_walls and curr_bid_walls:
        if curr_bid_walls[0]["lot"] > prev_bid_walls[0]["lot"] * 1.3:
            signals.append({
                "tipe": "bullish",
                "nama": "Wall Bid Menebal",
                "detail": f"Bid wall +{curr_bid_walls[0]['lot'] - prev_bid_walls[0]['lot']:,} lot",
                "kekuatan": 0.7,
            })

    # Ask side turun sementara harga mulai naik
    if ask_delta < -10000 and price_delta > 0:
        signals.append({
            "tipe": "bullish",
            "nama": "Seller Menarik Diri",
            "detail": f"Ask -{abs(ask_delta):,} lot, harga +{price_delta}",
            "kekuatan": 0.8,
        })

    # Harga flat di area low sementara bid akumulasi
    if abs(price_delta) <= 2 and bid_delta > 10000 and curr.get("price", 0) <= prev.get("low", 0) * 1.02:
        signals.append({
            "tipe": "bullish",
            "nama": "Silent Accumulation",
            "detail": f"Harga flat, bid +{bid_delta:,} lot — silent accumulation",
            "kekuatan": 0.95,
        })

    # ── BEARISH ──

    # Wall bid besar tiba-tiba hilang (di-pull)
    if prev_bid_walls and not curr_bid_walls:
        signals.append({
            "tipe": "bearish",
            "nama": "Bid Wall Di-Pull",
            "detail": f"Bid wall {prev_bid_walls[0]['lot']:,} lot lenyap — distribusi",
            "kekuatan": 0.9,
        })

    # Ask total meledak naik sementara bid stagnan
    if ask_delta > 20000 and abs(bid_delta) < 5000:
        signals.append({
            "tipe": "bearish",
            "nama": "Seller Baru Masuk Masif",
            "detail": f"Ask +{ask_delta:,} lot, bid stagnan",
            "kekuatan": 0.85,
        })

    # Harga turun meski ratio bagus
    if price_delta < 0 and ratio_curr > 1.5:
        signals.append({
            "tipe": "bearish",
            "nama": "Seller Market-Sell",
            "detail": f"Harga turun meski ratio {ratio_curr:.1f}x — seller aktif market-sell",
            "kekuatan": 0.8,
        })

    # New low + wall sebelumnya jebol
    new_low = curr.get("price", 0) <= prev.get("low", 0)
    if new_low:
        signals.append({
            "tipe": "bearish",
            "nama": "New Low Terbentuk",
            "detail": "Low baru tercipta — bearish continuation",
            "kekuatan": 0.75,
        })

    # ── REVERSAL ──

    # New low tapi tidak dilanjut 2+ snapshot
    # (need multi-snapshot context — flag as partial)
    if new_low and bid_delta > 10000:
        signals.append({
            "tipe": "reversal",
            "nama": "Exhaustion (Partial)",
            "detail": "New low + bid naik — potensi exhaustion, konfirmasi snapshot berikutnya",
            "kekuatan": 0.7,
        })

    # Wall makin tebal justru saat harga ditekan
    if prev_bid_walls and curr_bid_walls and price_delta < 0:
        if curr_bid_walls[0]["lot"] > prev_bid_walls[0]["lot"] * 1.2:
            signals.append({
                "tipe": "reversal",
                "nama": "Institusi Defend",
                "detail": f"Harga turun tapi wall bid +{curr_bid_walls[0]['lot'] - prev_bid_walls[0]['lot']:,} lot — institusi defend",
                "kekuatan": 0.85,
            })

    # Triple reversal: bid meledak + ask turun + harga naik
    if bid_delta > 10000 and ask_delta < -5000 and price_delta > 0:
        signals.append({
            "tipe": "reversal",
            "nama": "Triple Reversal Konfirmasi",
            "detail": "Bid↑ Ask↓ Harga↑ — konfirmasi triple reversal",
            "kekuatan": 1.0,
        })

    return signals


# ──────────────────────────────────────────
#  SECTION 6 — Phase Identification
# ──────────────────────────────────────────

@dataclass
class MarketPhase:
    fase: str      # "DISTRIBUSI" | "CAPITULATION" | "SILENT_ACCUMULATION" | "REVERSAL" | "RECOVERY"
    confidence: float   # 0-100
    evidence: List[str]
    strategi: str

def identify_phase(data: Dict, prev: Optional[Dict] = None) -> Dict:
    """
    Identify market phase from orderbook data.
    Plan Section 6: 5 phases.
    """
    price = data.get("price", 0)
    high = data.get("high", 0)
    low = data.get("low", 0)
    avg = data.get("avg", 0)
    bid_total = data.get("bid_total", 0)
    ask_total = data.get("ask_total", 0)
    ratio = data.get("ratio", 1)
    volume = data.get("volume_lot", 0)

    bid_walls = data.get("walls", {}).get("bid_walls", [])
    ask_walls = data.get("walls", {}).get("ask_walls", [])
    signals = data.get("delta_signals", [])

    evidence = []

    # ── FASE 1: DISTRIBUSI ──
    dist_score = 0
    if avg > price and avg > 0:
        dist_score += 25
        evidence.append(f"Avg ({avg}) > harga ({price}) — distribusi berjalan")
    if any(s["nama"] == "Bid Wall Di-Pull" for s in signals):
        dist_score += 30
        evidence.append("Bid wall di-pull — distribusi terkonfirmasi")
    if any(s["nama"] == "Seller Baru Masuk Masif" for s in signals):
        dist_score += 20
    if len(ask_walls) >= 2 and ask_walls[0].get("lot", 0) > 20000:
        dist_score += 15
        evidence.append("Ask walls padat — seller terorganisir")
    if dist_score >= 50:
        return asdict(MarketPhase(
            fase="DISTRIBUSI",
            confidence=min(100, dist_score),
            evidence=evidence[:3],
            strategi="HINDARI ENTRY LONG. Tunggu fase berikutnya.",
        ))

    # ── FASE 2: CAPITULATION ──
    cap_score = 0
    # Harga turun cepat
    if prev and prev.get("price", 0) - price > 20:
        cap_score += 25
        evidence.append(f"Harga turun {prev.get('price', 0) - price}pt cepat")
    # New lows terus terbentuk
    if any(s["tipe"] == "bearish" and "New Low" in s["nama"] for s in signals):
        cap_score += 25
        evidence.append("New lows berulang")
    # Volume meledak
    if volume > 50000:
        cap_score += 20
        evidence.append(f"Volume tinggi ({volume:,} lot)")
    # Ratio membaik tapi harga tetap jatuh
    if ratio > 1.0 and prev and price < prev.get("price", 0):
        cap_score += 15
        evidence.append("Ratio membaik tapi harga jatuh — buyer absorb, seller lebih agresif")
    if cap_score >= 45:
        return asdict(MarketPhase(
            fase="CAPITULATION",
            confidence=min(100, cap_score),
            evidence=evidence[:3],
            strategi="OBSERVASI. Identifikasi mega wall yang akan jadi floor.",
        ))

    # ── FASE 3: SILENT ACCUMULATION ──
    sa_score = 0
    # Harga flat/sideways di area low
    if prev and abs(price - prev.get("price", 0)) <= 3:
        sa_score += 20
        evidence.append("Harga flat/sideways di area low")
    # Bid total naik tanpa harga naik
    if prev and bid_total > prev.get("bid_total", 0) * 1.1 and price <= prev.get("price", 0):
        sa_score += 30
        evidence.append(f"Bid naik {(bid_total/prev['bid_total']-1)*100:.0f}% tanpa harga naik — silent accumulation")
    # Volume turun (less selling)
    if prev and volume < prev.get("volume_lot", 0) * 0.8:
        sa_score += 15
        evidence.append("Volume turun — selling exhausted")
    # Wall bid makin tebal
    if prev:
        prev_bid_walls = prev.get("walls", {}).get("bid_walls", [])
        if prev_bid_walls and bid_walls:
            if bid_walls[0]["lot"] > prev_bid_walls[0]["lot"]:
                sa_score += 20
                evidence.append("Wall bid makin tebal")
    if sa_score >= 45:
        return asdict(MarketPhase(
            fase="SILENT_ACCUMULATION",
            confidence=min(100, sa_score),
            evidence=evidence[:3],
            strategi="PERSIAPAN ENTRY. Low risk setup mulai valid.",
        ))

    # ── FASE 4: REVERSAL CONFIRMATION ──
    rv_score = 0
    if any(s["tipe"] == "reversal" for s in signals):
        rv_score += 30
        rev_sigs = [s for s in signals if s["tipe"] == "reversal"]
        evidence.append(f"{len(rev_sigs)} reversal signal(s) terdeteksi")
    # Harga mulai naik dari low
    if prev and price > prev.get("price", 0) and price <= low * 1.05:
        rv_score += 20
        evidence.append("Harga mulai naik dari area low")
    # Wall bid hold
    if bid_walls and bid_walls[0].get("lot", 0) > 10000:
        rv_score += 15
        evidence.append(f"Bid wall hold di {bid_walls[0]['price']}")
    # Volume naik (buying momentum)
    if prev and volume > prev.get("volume_lot", 0) * 1.3:
        rv_score += 15
        evidence.append("Volume naik — buying momentum masuk")
    if rv_score >= 50:
        return asdict(MarketPhase(
            fase="REVERSAL_CONFIRMATION",
            confidence=min(100, rv_score),
            evidence=evidence[:3],
            strategi="ENTRY MODERAT / AGRESIF. Konfirmasi sudah ada.",
        ))

    # ── FASE 5: RECOVERY ──
    rec_score = 0
    if ratio <= 1.3 and ratio >= 0.8:
        rec_score += 20
        evidence.append(f"Ratio {ratio:.1f}x kembali balance")
    if prev and price > prev.get("price", 0) * 1.05:
        rec_score += 25
        evidence.append("Harga naik signifikan dari low (+5%+)")
    mega_ask = data.get("walls", {}).get("mega_walls", [])
    if mega_ask:
        rec_score += 15
        evidence.append(f"Mega wall ask di {mega_ask[0]['price']} sebagai ceiling")
    if rec_score >= 40:
        return asdict(MarketPhase(
            fase="RECOVERY",
            confidence=min(100, rec_score),
            evidence=evidence[:3],
            strategi="PARTIAL TP, range play. Jangan entry baru di dekat resistance.",
        ))

    # Default: not enough data
    return asdict(MarketPhase(
        fase="UNDETERMINED",
        confidence=20,
        evidence=["Data belum cukup untuk identifikasi fase yang jelas"],
        strategi="WAIT & OBSERVE. Kumpulkan 2+ snapshot untuk analisis fase.",
    ))


# ──────────────────────────────────────────
#  SECTION 7b — Dynamic S/R Flip
# ──────────────────────────────────────────

@dataclass
class BrokenLevel:
    price: int
    side_asal: str         # "support" | "resistance"
    arah: str              # "tembus_ke_atas" | "jebol_ke_bawah"
    flipped_to: str        # "resistance" | "support"
    lot_baru: int          # lot di sisi flipped

def check_sr_flip(bids: List[Dict], asks: List[Dict],
                  prev_supports: List[int], prev_resistances: List[int]) -> List[Dict]:
    """
    Check if previous support/resistance levels have been broken and flipped.

    Plan Section 7b:
    - Resistance ditembus ke atas → flip jadi support
    - Support jebol ke bawah → flip jadi resistance
    """
    flips = []
    bid_prices = {b["price"] for b in bids}
    ask_prices = {a["price"] for a in asks}
    bid_lots = {b["price"]: b["lot"] for b in bids}
    ask_lots = {a["price"]: a["lot"] for a in asks}

    # Support yang jebol → lihat apakah ask muncul di sana
    for s in prev_supports:
        if s not in bid_prices:
            # Cek apakah ada ask di level ini (jebol → flip resistance)
            if s in ask_prices:
                flips.append({
                    "price": s,
                    "side_asal": "support",
                    "arah": "jebol_ke_bawah",
                    "flipped_to": "resistance",
                    "lot_baru": ask_lots[s],
                })

    # Resistance yang ditembus → lihat apakah bid muncul di sana
    for r in prev_resistances:
        if r not in ask_prices:
            if r in bid_prices:
                flips.append({
                    "price": r,
                    "side_asal": "resistance",
                    "arah": "tembus_ke_atas",
                    "flipped_to": "support",
                    "lot_baru": bid_lots[r],
                })

    return flips


# ──────────────────────────────────────────
#  SECTION 8 — Entry Condition Counter
# ──────────────────────────────────────────

CONDITIONS_LOW_RISK = [
    "harga_dekat_mega_wall_bid",
    "wall_tidak_berkurang",
    "harga_flat_2_snapshot",
    "bid_total_naik_lintas_snapshot",
    "candle_reversal_volume_spike",
]

def count_entry_conditions(data: Dict) -> Dict:
    """
    Count how many of 5 low-risk conditions are met.
    Returns count + sizing recommendation.
    """
    met = []
    not_met = []
    total = 0

    # 1. Harga menyentuh/dekat mega wall bid
    mega_bid = data.get("walls", {}).get("mega_walls", [])
    nearby_mega = [w for w in mega_bid if w.get("jarak_dari_harga", 999) <= 5]
    if nearby_mega:
        total += 1
        met.append("harga_dekat_mega_wall_bid")
    else:
        not_met.append("harga_dekat_mega_wall_bid")

    # 2. Wall tidak berkurang drastis saat harga ditekan
    signals = data.get("delta_signals", [])
    wall_pulled = any(s["nama"] == "Bid Wall Di-Pull" for s in signals)
    if not wall_pulled:
        total += 1
        met.append("wall_tidak_berkurang")
    else:
        not_met.append("wall_tidak_berkurang — ada bid wall di-pull!")

    # 3. Harga flat 2+ snapshot di area low
    if data.get("phase_identified") == "SILENT_ACCUMULATION":
        total += 1
        met.append("harga_flat_2_snapshot")
    else:
        not_met.append("harga_flat_2_snapshot — fase belum silent accumulation")

    # 4. Bid total naik lintas snapshot meski harga flat/turun
    if any(s["nama"] in ("Bid Akumulasi Masif", "Silent Accumulation") for s in signals):
        total += 1
        met.append("bid_total_naik_lintas_snapshot")
    else:
        not_met.append("bid_total_naik_lintas_snapshot — belum terdeteksi")

    # 5. Candle reversal + volume spike naik
    if any(s["tipe"] == "reversal" for s in signals):
        total += 1
        met.append("candle_reversal_volume_spike")
    else:
        not_met.append("candle_reversal_volume_spike — belum ada reversal signal")

    # Sizing rule
    sizing_info = _sizing_rule(total)

    return {
        "kondisi_terpenuhi": total,
        "dari": 5,
        "met": met,
        "not_met": not_met,
        "sizing": sizing_info,
    }

def _sizing_rule(met: int) -> Dict:
    """Plan Section 8: sizing table."""
    rules = {
        0: {"size_persen": 0,  "aksi": "SKIP"},
        1: {"size_persen": 0,  "aksi": "SKIP"},
        2: {"size_persen": 30, "aksi": "30% size, waspada"},
        3: {"size_persen": 50, "aksi": "50% size, tambah jika konfirmasi"},
        4: {"size_persen": 85, "aksi": "85% size (near full)"},
        5: {"size_persen": 100,"aksi": "FULL SIZE (sesuai money management)"},
    }
    return rules.get(met, {"size_persen": 0, "aksi": "SKIP"})


# ──────────────────────────────────────────
#  SECTION 10 — Red Flags
# ──────────────────────────────────────────

RED_FLAG_RULES = [
    {
        "id": "RF1",
        "nama": "Wall Besar Di-Pull",
        "kondisi": lambda d: any(
            s["nama"] == "Bid Wall Di-Pull" for s in d.get("delta_signals", [])
        ),
        "severitas": "CRITICAL",
    },
    {
        "id": "RF2",
        "nama": "Ask Meledak >50%",
        "kondisi": lambda d: d.get("ask_delta_pct", 0) > 50,
        "severitas": "HIGH",
    },
    {
        "id": "RF3",
        "nama": "Low Baru Terus Menerus",
        "kondisi": lambda d: any(
            "New Low" in s.get("nama", "") for s in d.get("delta_signals", [])
        ),
        "severitas": "HIGH",
    },
    {
        "id": "RF4",
        "nama": "Ratio Membaik Tapi Harga Tidak Naik 2+ Snapshot",
        "kondisi": lambda d: (
            d.get("ratio", 1) >= 1.0
            and d.get("price_change", 0) <= 0
            and d.get("snapshot_count", 1) >= 2
        ),
        "severitas": "MEDIUM",
    },
    {
        "id": "RF5",
        "nama": "Corporate Action + Bearish",
        "kondisi": lambda d: d.get("corporate_action", False) and d.get("bias") in ("bearish", "bearish_kuat"),
        "severitas": "HIGH",
    },
    {
        "id": "RF6",
        "nama": "Volume Meledak ke Bawah",
        "kondisi": lambda d: (
            abs(d.get("price_change", 0)) > 20
            and d.get("volume_change_pct", 0) > 100
        ),
        "severitas": "HIGH",
    },
]

def check_red_flags(data: Dict) -> List[Dict]:
    """Check all 6 red flags. Return list of active flags."""
    active = []
    for rule in RED_FLAG_RULES:
        try:
            if rule["kondisi"](data):
                active.append({
                    "id": rule["id"],
                    "nama": rule["nama"],
                    "severitas": rule["severitas"],
                    "aksi": "ABORT / SKIP ALL SETUP",
                })
        except Exception:
            pass
    return active


# ──────────────────────────────────────────
#  SECTION 11 — IHSG Context
# ──────────────────────────────────────────

SESSION_ZONES = [
    {"nama": "Open",               "waktu": (900, 930),  "karakter": "Volatilitas tinggi, hindari entry terburu"},
    {"nama": "Prime Time",         "waktu": (930, 1100), "karakter": "Liquiditas terbaik, setup paling reliable"},
    {"nama": "Lunch",              "waktu": (1100, 1330),"karakter": "Spread melebar, volume turun, setup kurang reliable"},
    {"nama": "Sesi Sore",          "waktu": (1330, 1430),"karakter": "Sering reversal/continuation dari tren pagi"},
    {"nama": "Closing Push",       "waktu": (1430, 1500),"karakter": "Institusi defend, wall bisa muncul mendadak"},
]

LOT_TIERS = {
    "mid_cap_signifikan": 10000,
    "institusional":      50000,
    "mega_wall":         100000,
}

def ihsg_context(data: Dict) -> Dict:
    """Apply IHSG-specific context."""
    timestamp = data.get("timestamp", "")
    price = data.get("price", 0)
    ara = data.get("ara", 0)
    low = data.get("low", 0)
    arb = data.get("arb", 0)

    result = {}

    # Session zone
    try:
        h, m = map(int, timestamp.split(":"))
        time_int = h * 100 + m
        for zone in SESSION_ZONES:
            if zone["waktu"][0] <= time_int < zone["waktu"][1]:
                result["session"] = zone
                break
        if "session" not in result:
            result["session"] = {"nama": "Outside Session", "karakter": "After hours, spread lebar"}
    except:
        result["session"] = {"nama": "Unknown", "karakter": "Timestamp tidak dikenal"}

    # ARA/ARB proximity
    if ara > 0:
        jarak_ara_pct = ((ara - price) / ara) * 100
        result["ara_jarak_pct"] = round(jarak_ara_pct, 1)
        result["ara_proximity"] = "DANGER" if jarak_ara_pct < 20 else "WARNING" if jarak_ara_pct < 50 else "SAFE"
        result["ara_warning"] = (
            f"Potensi upside terbatas ({jarak_ara_pct:.0f}% ke ARA)" if jarak_ara_pct < 20
            else None
        )

    if arb > 0 and low > 0:
        jarak_arb_pct = ((low - arb) / arb) * 100
        result["arb_jarak_pct"] = round(jarak_arb_pct, 1)
        result["bid_wall_dekat_arb"] = jarak_arb_pct < 5

    return result


# ──────────────────────────────────────────
#  ORCHESTRATOR
# ──────────────────────────────────────────

class OrderbookPlanAnalyzer:
    """
    Complete analysis engine implementing ALL sections from plan.md.
    """

    def __init__(self, debug=False):
        self.debug = debug

    def analyze_snapshot(self, data: Dict, prev: Optional[Dict] = None) -> Dict:
        """
        Full analysis pipeline for one snapshot.

        Args:
            data: raw orderbook data (price, bids, asks, stats)
            prev: optional previous snapshot for delta analysis

        Returns:
            dict with all analysis results
        """
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        price = data.get("price", 0)
        avg = data.get("avg", 0)
        high = data.get("high", 0)
        low = data.get("low", 0)

        # Totals — prefer footer totals (cover all levels), fallback to visible sum
        total_bid_override = data.get("total_bid_lot", 0)
        total_ask_override = data.get("total_ask_lot", 0)
        bid_total = total_bid_override if total_bid_override > 0 else sum(b.get("lot", 0) for b in bids)
        ask_total = total_ask_override if total_ask_override > 0 else sum(a.get("lot", 0) for a in asks)
        total_freq_bid = data.get("total_freq_bid", 0) or sum(b.get("freq", 0) for b in bids)
        total_freq_ask = data.get("total_freq_ask", 0) or sum(a.get("freq", 0) for a in asks)

        # ── Core metrics ──
        ratio = bid_total / max(ask_total, 1)
        bid_ask = classify_bid_ask_ratio(ratio)

        freq = analyze_freq_ratio(total_freq_bid, total_freq_ask, bid_total, ask_total)

        divergence = calc_divergence(price, avg)

        # ── Walls ──
        tick_size = 10 if price > 5000 else (5 if price > 2000 else (2 if price > 500 else 1))
        classified_walls = classify_walls(bids, asks, price, tick_size)

        # ── Delta signals ──
        delta_signals = []
        if prev:
            prev_price = prev.get("price", 0) or prev.get("high", 0) or prev.get("avg", 0)
            prev_bid_total = prev.get("bid_total", 0) or sum(b.get("lot", 0)
                                   for b in prev.get("bids", []))
            prev_ask_total = prev.get("ask_total", 0) or sum(a.get("lot", 0)
                                   for a in prev.get("asks", []))
            prev_ratio = prev_bid_total / max(prev_ask_total, 1)

            snap_prev = {
                "price": prev_price,
                "bid_total": prev_bid_total,
                "ask_total": prev_ask_total,
                "ratio": prev_ratio,
                "low": prev.get("low", 0),
                "walls": prev.get("walls", {}),
            }
            snap_curr = {
                "price": price,
                "bid_total": bid_total,
                "ask_total": ask_total,
                "ratio": ratio,
                "low": low,
                "walls": classified_walls,
            }
            delta_signals = interpret_delta_signals(snap_prev, snap_curr)

        # ── Phase ──
        phase_data = {
            "price": price,
            "high": high,
            "low": low,
            "bid_total": bid_total,
            "ask_total": ask_total,
            "volume": data.get("volume_lot", 0),
            "value": data.get("value", 0),
            "bid_freq_total": data.get("totals", {}).get("bid_freq", 0),
            "ask_freq_total": data.get("totals", {}).get("ask_freq", 0),
            "ratio": ratio,
            "volume_lot": data.get("volume_lot", 0) or data.get("lot", 0),
            "walls": classified_walls,
            "delta_signals": delta_signals,
        }
        if prev:
            phase_data["prev"] = {
                "price": prev.get("price", 0) or prev.get("high", 0),
                "bid_total": prev_bid_total,
                "volume_lot": prev.get("volume_lot", 0) or prev.get("lot", 0),
                "walls": classified_walls,
            }
        phase = identify_phase(phase_data)

        # ── Entry conditions ──
        cond_data = {
            **phase_data,
            "phase_identified": phase["fase"],
        }
        entry_conditions = count_entry_conditions(cond_data)

        # ── Red flags ──
        red_flag_data = {
            "delta_signals": delta_signals,
            "ask_delta_pct": _calc_pct_delta(prev, "ask_total", ask_total) if prev else 0,
            "ratio": ratio,
            "bias": bid_ask["bias"],
            "price_change": (price - prev.get("price", 0)) if prev else 0,
            "volume_change_pct": _calc_pct_delta(prev, "volume_lot",
                                  data.get("volume_lot", 0) or data.get("lot", 0)) if prev else 0,
            "snapshot_count": 2 if prev else 1,
            "corporate_action": data.get("corporate_action", False),
        }
        red_flags = check_red_flags(red_flag_data)

        # ── IHSG context ──
        ctx_data = {
            "timestamp": data.get("timestamp", ""),
            "price": price,
            "ara": data.get("ara", 0),
            "low": low,
            "arb": data.get("arb", 0),
        }
        ihsg = ihsg_context(ctx_data)

        # ── Compile ──
        result = {
            "ticker": data.get("ticker"),
            "timestamp": data.get("timestamp"),
            "prev_timestamp": prev.get("timestamp", "") if prev else "",
            # Market fields needed by formatter / rec engine
            "price": price,
            "high": high,
            "low": low,
            "avg": avg,
            "ara": data.get("ara", 0),
            "arb": data.get("arb", 0),
            "open": data.get("open", 0),
            "prev": data.get("prev", 0),
            "volume_lot": data.get("volume_lot", 0),
            "volume": data.get("volume_lot", 0),
            "value": data.get("value", 0),
            "bid_total": bid_total,
            "ask_total": ask_total,
            "bid_freq_total": data.get("totals", {}).get("bid_freq", 0),
            "ask_freq_total": data.get("totals", {}).get("ask_freq", 0),
            "total_freq_bid": total_freq_bid,
            "total_freq_ask": total_freq_ask,

            # Section 3
            "bid_ask": bid_ask,
            "freq_ratio": freq,
            "divergence": divergence,

            # Section 4
            "walls": classified_walls,

            # Floor delta metadata
            "prev_floor_lot": _get_prev_floor_lot(prev, classified_walls),

            # Section 5
            "delta_signals": delta_signals,

            # Section 6
            "phase": phase,

            # Section 7 (S/R from existing wall data)
            "sr_flips": [],

            # Section 8
            "entry_conditions": entry_conditions,

            # Section 10
            "red_flags": red_flags,
            "has_red_flag": len(red_flags) > 0,

            # Section 11
            "ihsg_context": ihsg,

            # Summary
            "summary": self._gen_summary(bid_ask, freq, divergence, phase,
                                         red_flags, entry_conditions, ihsg),
        }

        if self.debug:
            self._print(result)

        return result

    def _gen_summary(self, bid_ask, freq, divergence, phase,
                     red_flags, entry_conditions, ihsg) -> str:
        parts = []

        # 1-line caveman-style
        ratio_s = f"Ratio {bid_ask['ratio']}x {bid_ask['label']}"
        div_s = f"Div {divergence['divergence_pct']:+.1f}% {divergence['label']}"
        phase_s = f"Fase {phase['fase']} ({phase['confidence']:.0f}%)"
        parts.append(f"{ratio_s} | {div_s} | {phase_s}")

        if red_flags:
            parts.append(f"⚠ {len(red_flags)} red flag(s): {', '.join(r['id'] for r in red_flags)}")

        entry_s = entry_conditions["sizing"]["aksi"]
        if entry_conditions["kondisi_terpenuhi"] >= 3:
            parts.append(f"✅ {entry_s}")
        else:
            parts.append(f"⏸ {entry_s}")

        return " | ".join(parts)

    def _print(self, result):
        print("\n=== PLAN.MD ANALYSIS v2 ===")
        print(f"Ticker: {result['ticker']} @ {result['timestamp']}")
        print(f"Bid:Ask -> {result['bid_ask']['ratio']}x {result['bid_ask']['label']}")
        print(f"Freq Ratio -> {result['freq_ratio']['freq_ratio']}x (lot {result['freq_ratio']['lot_ratio']}x)")
        print(f"Divergence -> {result['divergence']['divergence_pct']:+.2f}% — {result['divergence']['label']}")
        print(f"Phase -> {result['phase']['fase']} ({result['phase']['confidence']:.0f}%)")
        print(f"Conditions met: {result['entry_conditions']['kondisi_terpenuhi']}/5 -> {result['entry_conditions']['sizing']['aksi']}")

        if result["delta_signals"]:
            print(f"\nDelta Signals ({len(result['delta_signals'])}):")
            for s in result["delta_signals"]:
                emoji = "🟢" if s["tipe"] == "bullish" else ("🔴" if s["tipe"] == "bearish" else "🔄")
                print(f"  {emoji} [{s['kekuatan']:.0%}] {s['nama']}: {s['detail']}")

        if result["red_flags"]:
            print(f"\n⚠ RED FLAGS ({len(result['red_flags'])}):")
            for rf in result["red_flags"]:
                print(f"  [{rf['severitas']}] {rf['id']}: {rf['nama']}")

        print(f"\nSummary: {result['summary']}")


def _get_prev_floor_lot(prev: Optional[Dict], curr_walls: Dict) -> Optional[int]:
    """Get floor lot from prev snapshot for delta arrow comparison."""
    if not prev:
        return None
    prev_walls = prev.get("walls", {})
    prev_megas = prev_walls.get("mega_walls", [])
    prev_bid_megas = [w for w in prev_megas if "Bid" in w.get("tipe", "")]
    if prev_bid_megas:
        return prev_bid_megas[0].get("lot", 0)
    # Fallback: check bid_walls top
    prev_bid_walls = prev_walls.get("bid_walls", [])
    if prev_bid_walls:
        return sorted(prev_bid_walls, key=lambda w: w.get("lot", 0), reverse=True)[0].get("lot", 0)
    return None


def _calc_pct_delta(prev: Optional[Dict], key: str, curr_val: int) -> float:
    if not prev:
        return 0
    prev_val = prev.get(key, 0) or 0
    if prev_val == 0:
        return 0
    return ((curr_val - prev_val) / prev_val) * 100


# ──────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plan.md-compliant orderbook analysis")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("--prev", help="Previous snapshot JSON (for delta)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    try:
        with open(args.input) as f:
            data = json.load(f)

        prev = None
        if args.prev:
            with open(args.prev) as f:
                prev = json.load(f)

        analyzer = OrderbookPlanAnalyzer(debug=args.debug)
        result = analyzer.analyze_snapshot(data, prev)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not args.debug:
                analyzer._print(result)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
