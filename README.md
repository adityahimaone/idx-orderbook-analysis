# IDX Orderbook Analysis

Framework analisis orderbook saham IHSG berbasis multi-snapshot delta analysis + Market Alpha Scout pre-screening.
**Multi-phase pipeline**: Screenshot → OCR/Vision → Wall Detection → Phase Identification → 3-Tier Recommendations.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)

## 🚀 Quick Start

```bash
# Screenshot orderbook → analisis instan
ob-pipe

# Save ke history DB (untuk delta analysis berikutnya)
ob-pipe-c

# Analisis dengan Market Alpha Scout context (Score, Support, TP/SL)
echo '{"ticker":"TPIA",...}' | python3.11 pipeline_stdin.py --caveman --save --mas

# MAS Screener — cari high conviction tickers
ob-mas
```

## 📂 Structure

```
idx-orderbook-analysis/
├── scripts/
│   ├── pipeline_v2.py          → Master orchestrator (screenshot → report)
│   ├── pipeline_stdin.py       → Stdin mode (JSON pipe + auto-delta + MAS)
│   ├── orderbook_analyzer_v2.py→ Logic engine (walls, phase, conditions, delta)
│   ├── recommendation_engine_v2.py → 3-tier entry (AGG/MOD/LR)
│   ├── output_formatter_v2.py  → IDX Orderbook Template v2 renderer
│   ├── orderbook_history.py    → SQLite persistence
│   ├── mas_integration.py      → Google Sheets MAS data fetcher    🆕
│   └── mas_orderbook_screener.py → MAS → Orderbook confluence CLI  🆕
├── references/
│   ├── IDX_Orderbook_Template_v2.md → Output format spec
│   ├── plan_md_implementation_map.md → Framework coverage tracker
│   └── SPEED_BENCHMARKS.md → OCR vs Vision performance
├── templates/
├── mas-orderbook-skill/        → Market Alpha Scout integration skill  🆕
│   └── SKILL.md
├── plan.md                     → Methodology (MAS-enhanced v3)         🆕
└── SKILL.md
```

## 📊 Output Format

Orderbook analysis mengikuti **IDX Orderbook Template v2** — compact, semua info dalam 15 baris:

```
━━━ TPIA 1,830 🔴-6.15% | 13:54 ━━━
H:2070 L:1830▼ Avg:1958(-6.5%)
Vol:12.40M Val:2.43T

BID 209,703lot f2,498  ║  ASK 119,577lot f718
▬▬▬▬▬▬▬ 1.75x BID_UNGGUL ▬▬▬▬▬▬▬
FASE ░ CAPITULATION-2  Cond:2/5  Size:30%

🟢 BID WALLS            🔴 ASK WALLS
1,810 │ 20,187 │ f187   1,860 │ 54,021 │ f79  ⚡CEIL
1,805 │ 25,885 │ f307   1,870 │ 18,458 │ f91
                         1,880 │ 10,262 │ f89
FLOOR→1,800│91,813↑│f952

CONDITIONS [LR]
✅ Wall bid makin tebal    ✅ Harga flat di low
⏳ Candle reversal         ⏳ Volume spike naik
⏳ Bid naik 2+ snapshot

▸ AGG  — SKIP (fase belum konfirmasi)
▸ MOD  E:1808-1815 SL:1792 TP1:1830 TP2:1845 RR:1.8x
▸ LR   E:1803-1810 SL:1788 TP1:1825 TP2:1840 RR:2.2x

⚡ DELTA (vs 13:49)
   Price -25 │ Low ▼1835→1830 │ Vol +190K
   Bid +43K↑ │ Ask -17K↓ │ Ratio 1.21→1.75
   Wall 1,800: +11,780lot (58,350→91,813)

⚠️ Entry LR hanya setelah touch 1,800 + wall hold

📡 MAS ✅ HC | MAS Score:72 | Sig:BREAKOUT | VolR:1.8x | → E:1,830 SL:1,792 TP:1,870 RR:2.2x
```

## 🔗 Market Alpha Scout Integration (NEW)

Sebelum scan orderbook, pre-filter pake MAS:

```bash
# Cari ticker High Conviction
python3.11 scripts/mas_orderbook_screener.py --caveman

# Detail single ticker + bandingkan Support vs Orderbook
python3.11 scripts/mas_orderbook_screener.py --ticker ADRO

# Pipeline dengan MAS enrichment
echo '{"ticker":"ADRO",...}' | python3.11 pipeline_stdin.py --caveman --save --mas
```

**Decision Matrix (MAS + Orderbook Confluence):**

| Condition | Probability | Decision |
|-----------|-----------|----------|
| Support (MAS) ≈ Mega Wall Bid (OB) ±2 tick | >95% | ✅ LR Full Size |
| MAS Score ≥ 70 + Vol_Ratio ≥ 1.5x + OB Bid wall tebal | >90% | ✅ MOD+ 80% |
| MAS BREAKOUT + OB baru reversal dari low | >85% | ✅ AGG entry |
| MAS AVOID (+ any OB condition) | — | ❌ SKIP |

## 🛡️ 3-Tier Entry System

| Tier | Trigger | RR Min | Size |
|------|---------|--------|------|
| **LR** (Low Risk) | 3/5 conditions + wall hold | 1:2.0 | 100% |
| **MOD** (Moderat) | 2 confirmation | 1:1.8 | 70-90% |
| **AGG** (Aggressive) | Early reversal signal | 1:1.5 | 50-70% |

## 📆 Cron Setup

```bash
# DB cleanup (30+ hari)
0 3 * * * python3.11 ~/.hermes/scripts/cleanup_orderbook_db.py

# Market session reminders
30 9 * * 1-5 python3.11 ~/.hermes/scripts/market_reminder.py
30 11 * * 1-5 python3.11 ~/.hermes/scripts/market_reminder.py
30 13 * * 1-5 python3.11 ~/.hermes/scripts/market_reminder.py
50 14 * * 1-5 python3.11 ~/.hermes/scripts/market_reminder.py
5 15 * * 1-5 python3.11 ~/.hermes/scripts/market_reminder.py
```

## 📖 References

- [Methodology Framework](plan.md) — Screening methodology + MAS integration
- [Template v2 Spec](references/IDX_Orderbook_Template_v2.md) — Output format detail
- [Implementation Map](references/plan_md_implementation_map.md) — Feature coverage vs plan.md
- [Speed Benchmarks](references/SPEED_BENCHMARKS.md) — OCR vs Vision performance

## 🔧 Aliases

```bash
alias ob-pipe='echo "Pastikan JSON sudah ter-copy" && python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/pipeline_stdin.py --caveman --save 2>/dev/null'
alias ob-pipe-c='ob-pipe'  # save always on
alias ob-mas='python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/mas_orderbook_screener.py --caveman'
alias ob-mas-detail='python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/mas_orderbook_screener.py --ticker'
```

## 📜 Methodology

Framework coverage dari `plan.md`:
- ✅ Wall Detection (Bid/Ask/Mega)
- ✅ Phase Identification (5 fase + 7 opsi)
- ✅ Multi-Snapshot Delta Analysis
- ✅ 3-Tier Entry System (AGG/MOD/LR)
- ✅ SL/TP Framework dengan RR minimum
- ✅ 5 Red Flags (Auto Abort)
- ✅ IHSG-specific (ARA/ARB, sesi waktu, lot size)
- ✅ Market Alpha Scout Integration (pre-screening + confluence) 🆕

## ⚡ Performance

| Mode | Speed | Accuracy |
|------|-------|----------|
| Vision API | ~0.5s | 99% clean screenshots |
| Fast OCR (Tesseract) | ~1.5s | 97% |
| Stdin pipe | ~0.1s | JSON pre-extracted |

## 📦 Dependencies

- Python 3.11+
- Tesseract 5.3.4+
- Google API Client (gspread, google-auth)
- OpenCV, Pillow, pytesseract

---

*Living framework — updated setiap sesi trading aktif. Market Alpha Scout provides pre-screening; Orderbook provides real-time entry validation.*
