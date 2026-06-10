---
name: mas-orderbook
description: Market Alpha Scout → Orderbook Screener. Finds high-conviction IDX tickers from MAS Google Sheets, then feeds into orderbook analysis. Bridge antara Market Alpha Scout dan IDX Orderbook Analysis.
triggers: mas-orderbook, mas-screener, scan-mas, orderbook mas, hc tickers, high conviction screening, confluence
allowed-tools: terminal, file, read_file, write_file, patch, web
---

# Market Alpha Scout → Orderbook Screener

Menjembatani **Market Alpha Scout** (957 ticker IDX Google Sheets) dan **Orderbook Analysis** (real-time depth).

## Cara Kerja

1. **MAS Pre-screening** → `mas_orderbook_screener.py` membaca `All Tickers` (Score v2, Signal, RSI, Vol_Ratio) + `Rekomendasi Beli` dari comprehensive sheet
2. **Filter High Conviction** → Score v2 ≥ 60 ATAU Final_Signal = BREAKOUT/CONFIRM BUY
3. **Orderbook Confluence** → Bandingkan level Support (MAS) dengan Mega Wall Bid (Orderbook)
4. **Entry Decision** → Jika konvergen → Entry Low Risk Full Size

## Quick Commands

```bash
# Screener — cari ticker HC dari MAS untuk di-scan orderbook
ob-mas

# Screener + kirim ke Telegram
ob-mas | python3.11 ~/.hermes/skills/pipeline_stdin.py

# JSON output — top 5 HC tickers
ob-mas-json

# Detail single ticker (cocok buat confluence orderbook)
ob-mas-detail TPIA

# Pipeline dengan MAS context (append ke orderbook output)
echo '{"ticker":"TPIA",...}' | python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/pipeline_stdin.py --caveman --mas

# MAS support level vs orderbook wall
ob-mas-detail ADRO
# lalu cek orderbook: ob-pipe
```

## Alias

```bash
# Di ~/.zshrc
alias ob-mas='python3.11 /home/adityahimaone/.hermes/skills/finance/idx-orderbook-analysis/scripts/mas_orderbook_screener.py --caveman'
alias ob-mas-json='python3.11 /home/adityahimaone/.hermes/skills/finance/idx-orderbook-analysis/scripts/mas_orderbook_screener.py --json --top 10'
alias ob-mas-detail='python3.11 /home/adityahimaone/.hermes/skills/finance/idx-orderbook-analysis/scripts/mas_orderbook_screener.py --ticker'
```

## Files

| File | Fungsi |
|------|--------|
| `scripts/mas_integration.py` | Core: koneksi Google Sheets, fetch MAS data |
| `scripts/mas_orderbook_screener.py` | CLI: output caveman/JSON/table + single ticker detail |
| `plan.md` Section 2 | Methodology: MAS integration layer |

## Flowchart

```
MAS Google Sheets
    │
    ▼
mas_orderbook_screener.py
    │  Filter: Score >= 60 || BREAKOUT
    ▼
High Conviction Tickers (top 15)
    │
    ▼
Orderbook Screenshot + OCR/Vision
    │
    ▼
pipeline_stdin.py --mas
    │  Compare: Support (MAS) vs Mega Wall Bid (OB)
    ▼
Confluence Score → Entry Decision
    → ✅ Konvergen → LR Full Size
    → ⚠️ Divergen → MOD/Aggressive only
    → ❌ No confluence → SKIP
```

## Entry Enrichment Rule (MAS + Orderbook Confluence)

| Condition | Probability | Decision |
|-----------|-----------|----------|
| Support (MAS) ≈ Mega Wall Bid (OB) dalam 2 tick | >95% | ✅ LR Full Size |
| Harga orderbook menyentuh Support (MAS) tanpa bounce | — | ❌ Tunda, tunggu wall hold |
| MAS Score ≥ 70 + Vol_Ratio ≥ 1.5x + OB Bid wall tebal | >90% | ✅ MOD+ 80% size |
| MAS Signal "BREAKOUT" + OB baru reversal dari low | >85% | ✅ AGG entry |
| MAS "AVOID" apapun kondisi OB | — | ❌ SKIP total |

## Pitfalls

- MAS data bisa basi (1–2 jam delay dari Google Sheets) — selalu validasi dengan harga real-time orderbook
- Google Sheets API rate limit: max ~60 req/min — jangan spam `ob-mas` + pipeline dalam 1 detik
- `comprehensive_sheet.json` path hardcoded ke MAS skill — pastikan MAS masih jalan (`ensure_integrity()`)
