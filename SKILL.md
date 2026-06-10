---
name: idx-orderbook-analysis
description: Analyze IDX stock orderbook from screenshot. Extracts data, runs multi-phase analysis (walls, phases, conditions, delta), generates 3-tier entry recommendations with caveman-format output. Uses pipeline_v2.py which now matches IDX_Orderbook_Template_v2.md format exactly.
triggers: analyze orderbook, check orderbook, analyze depth, screen stock, ob-analysis, ob-pipe, orderbook screenshot
allowed-tools: terminal, file, patch, write_file, read_file, search_files, image_generate
---

# IDX Orderbook Analysis

## Quick Start
```bash
# Single snapshot with caveman output
ob-pipe

# With history save (enables delta on next run)
ob-pipe-c
```

Or full:
```bash
echo '{"ticker":"TPIA",...}' | python3.11 ~/.hermes/skills/finance/idx-orderbook-analysis/scripts/pipeline_stdin.py --caveman --save 2>/dev/null
```

## Files
- `scripts/pipeline_v2.py` — Master orchestrator
- `scripts/pipeline_stdin.py` — Stdin mode (read JSON from pipe, auto-fetch prev from DB, output caveman/full)
- `scripts/orderbook_analyzer_v2.py` — Plan.md analyzer (walls, phase, conditions, delta)
- `scripts/recommendation_engine_v2.py` — 3-tier entry generation
- `scripts/output_formatter_v2.py` — Caveman + full report format (matches IDX_Orderbook_Template_v2.md)
- `scripts/orderbook_history.py` — SQLite persistence, `get_latest_snapshot()`, `purge_old_snapshots()`
- `~/.hermes/scripts/cleanup_orderbook_db.py` — Cron cleanup script (purge >30d)

## Cron
- `idx-history-cleanup` — Runs daily 3am, purges snapshots older than 30 days

## Output Format (v2 Template)
```
━━━ {TICKER} {PRICE} {EMOJI}{%CHG}% | {TIME} ━━━
H:{HIGH} L:{LOW}{LOW_FLAG} Avg:{AVG}({DIV}%)
Vol:{VOL} Val:{VAL}

BID {BID_TOT}lot f{BID_FREQ}  ║  ASK {ASK_TOT}lot f{ASK_FREQ}
▬▬▬▬▬▬▬ {RATIO}x {LABEL} ▬▬▬▬▬▬▬
FASE ░ {PHASE}  Cond:{COND}/5  Size:{SIZE}%

🟢 BID WALLS          🔴 ASK WALLS
{PRICE} │{LOT}│f{FREQ}  {PRICE} │{LOT}│f{FREQ} ⚡CEIL
{PRICE} │{LOT}│f{FREQ}  {PRICE} │{LOT}│f{FREQ}
{PRICE} │{LOT}│f{FREQ}  {PRICE} │{LOT}│f{FREQ}
FLOOR→{PRICE}│{LOT}{DIR}│f{FREQ}

CONDITIONS [LR]
{ICON} Dekat mega wall bid    {ICON} Wall bid hold/tebal
{ICON} Harga flat 2+ snap     {ICON} Bid total naik
{ICON} Candle reversal + vol

▸ AGG  {STATUS}
       E:{ENTRY} SL:{SL} TP1:{TP1} TP2:{TP2} RR:{RR}x
▸ MOD  E:{ENTRY} SL:{SL} TP1:{TP1} TP2:{TP2} RR:{RR}x
▸ LR   E:{ENTRY} SL:{SL} TP1:{TP1} TP2:{TP2} RR:{RR}x
       SL-dist:{X}–{Y}pt | TP1-dist:{X}–{Y}pt

⚡ DELTA (vs {PREV_TIME})
   {DETAILS...}

⚠️ {ALERT}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## When Output Looks Wrong
1. Check `output_formatter_v2.py` format_caveman_summary — all template fields must be populated
2. Check `orderbook_analyzer_v2.py` result dict keys — formatter reads from analysis dict
3. Check `pipeline_v2.py` _standardize — incoming JSON must have totals, value, timestamp
4. Run with `python3.11 pipeline_stdin.py` (no `--caveman`) for full diagnostic output

## Known Pitfalls
- `output_formatter_v2.py` wall formatting uses `fmt_lot()` for all lot numbers — keep consistent
- `get_latest_snapshot()` returns walls via `||` delimiter parsing — GROUP_CONCAT uses `||`
- Stdin JSON needs `totals` key with `bid_lot`, `ask_lot`, `bid_freq`, `ask_freq`
- `_standardize` is the single entry point — all field normalization happens there
- **NEVER leave placeholder comments** (`# ... rest of code same ...`) when patching output_formatter_v2.py — all function definitions (get_cond_icon, cond_labels, tier extraction, SL-dist calc) must be inline. Partial patches break NameError.
- **Template is gospel**: Output must match `references/IDX_Orderbook_Template_v2.md` exactly. User will notice deviations immediately ("kenapa ga pake template yang udah dibikin sih").
- **Wall thresholds (plan.md §11)**: >10K significant, >50K institutional, >=100K mega. If 2.5x mean threshold finds nothing, fallback to top-3 lots as "Level" entries so display is never empty.
- **Ask walls often empty** at 2.5x threshold because ask side is distributed. The fallback (top-3 lots sorted desc) ensures ask column always populates.
- **FLOOR arrow**: Must be dynamic (↑↓→) from `prev_floor_lot` in analysis dict, never hardcoded. Uses `_get_prev_floor_lot()` helper which checks prev mega_walls then bid_walls.
- **Condition labels order** (plan.md §8): 1) harga_dekat_mega_wall_bid, 2) wall_tidak_berkurang, 3) harga_flat_2_snapshot, 4) bid_total_naik_lintas_snapshot, 5) candle_reversal_volume_spike.
- **Always use `--save`** (`ob-pipe-c`) during intraday monitoring so DB has prev_data for next delta.
- **prev_timestamp**: Must be in analyzer result dict (from `prev.get("timestamp")`) so formatter can show `⚡ DELTA (vs {time})` correctly.
- **orderbook_history.py function naming**: `get_latest_snapshot` (singular prev for delta) vs `get_snapshots_since` (batch for review). Don't confuse with removed `get_recent_snapshots`.
- **Cron schedule syntax**: Hermes cron uses standard 5-field crontab. Multi-time schedules need separate jobs (one per time), NOT comma-separated hour+minute combos in single expression.

## Code Editing Rules
When modifying `output_formatter_v2.py`:
1. Read the FULL function before patching (offset=184 to end ~370)
2. Never use `# ... rest ...` placeholders — include complete logic
3. All nested functions (fmt_lot, fmt_val, get_cond_icon) must stay inside format_caveman_summary
4. Test import after every patch: `python3.11 -c "from output_formatter_v2 import format_caveman_summary"`
5. After full-function rewrite, run a pipeline test to confirm output matches template

When modifying `orderbook_analyzer_v2.py`:
1. Helper functions (`_get_prev_floor_lot`, `_calc_pct_delta`) live AFTER the class, before `main()`
2. New fields in result dict must be added inside `analyze_snapshot` → `result = {` block
3. `classify_walls()` has fallback logic at the bottom — don't remove it when patching wall detection

## Market Session Cron
Script: `~/.hermes/scripts/market_reminder.py` (copied from skill scripts dir)
Needs separate cron jobs per time slot (09:30, 11:00, 13:30, 14:50, 15:05 weekdays).
Script self-determines which message to show based on current hour/minute — single script, multiple triggers.