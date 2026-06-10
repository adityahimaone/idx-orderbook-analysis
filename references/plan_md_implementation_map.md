# Plan.md → Code Implementation Map

Last updated: 2026-06-10

## Coverage Matrix

| Plan.md Section | Function in `orderbook_analyzer_v2.py` | Status |
|---|---|---|
| §3a Bid:Ask Ratio (6 tiers) | `classify_bid_ask_ratio()` | ✅ |
| §3b Freq Ratio | `analyze_freq_ratio()` | ✅ |
| §3c Avg vs Price Divergence | `calc_divergence()` | ✅ |
| §4a Wall Identification | `classify_walls()` — mean*2.5 threshold | ✅ |
| §4b Wall Classification (4 types) | `classify_walls()` — Bid Wall, Ask Wall, Mega Wall Bid/Ask | ✅ |
| §4c Wall Genuine vs Fake | `wall_genuine_score()` — freq, duration, lot reaction | ✅ |
| §5b Multi-Snapshot Delta | `interpret_delta_signals()` | ✅ |
| §6 Phase Identification (5 phases) | `identify_phase()` — DISTRIBUSI, CAPITULATION, SILENT_ACCUMULATION, REVERSAL_CONFIRMATION, RECOVERY | ✅ |
| §7b Dynamic S/R Flip | `check_sr_flip()` | ✅ |
| §8 Entry Conditions (5/5) | `count_entry_conditions()` | ✅ |
| §9 TP & SL Framework | `recommendation_engine_v2.py` → `generate_tiers_planmd()` | ✅ |
| §10 Red Flags (6 abort) | `check_red_flags()` | ✅ |
| §11 IHSG Context | `ihsg_context()` — session zones, ARA proximity, lot tiers | ✅ |

## Wall Detection Logic (Updated 2026-06-10)

### Thresholds (plan.md §11)
- `>= 100,000 lot` → Mega Wall (institutional floor/ceiling)
- `> 2.5x mean lot` → Wall (significant concentration)
- Neither → Level (top-3 fallback for display)

### Fallback Logic
If `classify_walls()` finds no bid_walls AND no mega_walls → populate `bid_walls` with top-3 bids by lot.
If no ask_walls AND no Mega Wall Ask → populate `ask_walls` with top-3 asks by lot.
This ensures the template wall display never shows empty columns.

### FLOOR Delta Arrow
- `_get_prev_floor_lot(prev, curr_walls)` extracts previous floor lot
- Checks prev mega_walls (Bid side) first, falls back to prev bid_walls top
- Formatter shows: ↑ (lot grew), ↓ (lot shrank), → (no prev data or unchanged)

## Entry Conditions (plan.md §8)

Order in output (matches code `cond_labels` list):
1. `harga_dekat_mega_wall_bid` — "Dekat mega wall bid"
2. `wall_tidak_berkurang` — "Wall bid hold/tebal"
3. `harga_flat_2_snapshot` — "Harga flat 2+ snap"
4. `bid_total_naik_lintas_snapshot` — "Bid total naik"
5. `candle_reversal_volume_spike` — "Candle reversal + vol"

## Size Rule (plan.md §8)
```
cond 0-1 → 0% (SKIP)
cond 2   → 30%
cond 3   → 50%
cond 4   → 75%
cond 5   → 100%
```

## DB Schema (orderbook_history.py)

### Tables
- `snapshots` — ticker, timestamp, price, high, low, avg, ara, arb, bid_total, ask_total, bid_ask_ratio, phase, session_time, created_at
- `walls` — snapshot_id (FK), side, price, lot, freq, tipe, is_mega
- `red_flags` — snapshot_id (FK), flag_id, flag_name, severity

### Key Functions
- `save_snapshot(analysis_dict)` → saves snapshot + walls + red_flags
- `get_latest_snapshot(ticker)` → reconstructs prev_data dict for delta analysis
- `get_all_tickers()` → distinct tickers in DB
- `get_snapshots_since(ticker, since_datetime)` → batch retrieval with wall join
- `purge_old_snapshots(days=30)` → cleanup
