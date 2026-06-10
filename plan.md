# IDX Orderbook Screening Methodology (Improvement Integration: Market Alpha Scout)

Framework untuk Intraday Trading IHSG berbasis Orderbook Analysis — Derived from live multi-snapshot sessions (TPIA, TLKM, NAYZ) with Market Alpha Scout (MAS) Pre-screening.

---

## 1. Filosofi Dasar
Orderbook bukan sekadar daftar harga bid/ask. Ia adalah peta niat pasar real-time. Framework ini membaca semua layer sistematis melalui multi-snapshot delta analysis (interval 3–7 menit) yang diperkaya dengan data pre-screening Market Alpha Scout untuk validasi emiten "High Conviction".

## 2. Market Alpha Scout (MAS) Integration Layer
Sebelum melakukan screening orderbook, lakukan pre-filter ticker menggunakan data Market Alpha Scout:
- **High Conviction Filter**: Hanya scan orderbook emiten dengan `Score v2 ≥ 60` atau `Final_Signal = "🚀 BREAKOUT"`.
- **Pre-check**: Cek `Rekomendasi Beli` sheet untuk level entry, SL, dan TP. Gunakan sebagai konfirmasi tambahan (confluence) dengan level S/R orderbook.
- **Data Source**: Menggunakan output `v27_dashboard_sector.py` yang divalidasi `ensure_integrity()`.

## 3. Data Point (Snapshot)
(Data dari `v27_dashboard_sector.py` + orderbook real-time)
- **Header**: Last Price, Open/Prev, ARA/ARB, Avg (VWAP).
- **MAS Data**: Score v2, Signal, Vol_Ratio, RSI14, Buy_Price, SL_Practical, TP, R/R Ratio, Max_Pos.

## 4. Kalkulasi & Deteksi
- **Bid:Ask Ratio**: `Total Bid Lot / Total Ask Lot`.
- **Wall Detection**: Level > 2.5x rata-rata 10 level, Mega Wall ≥ 100K lot.
- **MAS Confluence**: Jika Harga orderbook mendekati level `Support` dari MAS, dan `Score v2` tinggi, probabilitas reversal > 80%.

## 5. Entry Framework (MAS Enhanced)
- **Tier 1 (Aggressive)**: Entry saat harga market mendekati Support (orderbook) DAN signal MAS "HOLD" atau "BUY".
- **Tier 2 (Moderat)**: Entry setelah MAS "BREAKOUT" terkonfirmasi + Vol_Ratio > 1.5x.
- **Tier 3 (Low Risk)**: Entry hanya jika minimal 3/5 kondisi orderbook terpenuhi DAN `Score v2 >= 60`.

## 6. Phase Identification (MAS Context)
- **Fase 1 (Distribusi)**: MAS signal "AVOID", Ask walls meningkat, Bid wall di-pull.
- **Fase 3 (Silent Accumulation)**: MAS signal "ACCUM", Bid walls tebal, Harga flat.
- **Fase 4 (Reversal)**: MAS signal "🚀 BREAKOUT", Bid wall hold, volume naik.

## 7. Red Flags
- Wall besar di-pull saat harga mendekati level Support (dari MAS).
- Ask total melesat >50% dalam 1 snapshot tanpa kenaikan harga.
- `Score v2` MAS turun drastis (Data Quality Flag).

---

## 8. Workflow (The "Fast-Scan" Path)
1. `rtk python ~/.hermes/skills/research/market-alpha-scout/scripts/scout.py` (Dapatkan Top High Conviction tickers).
2. Ticker teratas → `ob-pipe` (Ambil screenshot orderbook).
3. Bandingkan `Support` (MAS sheet) dengan `Mega Wall Bid` (Orderbook).
4. Jika konvergen (hampir sama) → **Entry Low Risk (Full Size)**.

---
*Framework living document — update tiap sesi trading aktif.*
