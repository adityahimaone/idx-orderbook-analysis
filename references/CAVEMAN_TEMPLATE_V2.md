# IDX Orderbook Template v2 — Comprehensive Compact

## TEMPLATE (dengan variabel)

```
━━━ {TICKER} {PRICE} {EMOJI_TREND}{PCT_CHG}% | {TIME} ━━━
H:{HIGH} L:{LOW}{LOW_FLAG} Avg:{AVG}({DIV_PCT}%) 
Vol:{VOL} Val:{VAL}

BID {BID_TOT}lot f{BID_FREQ}  ║  ASK {ASK_TOT}lot f{ASK_FREQ}
▬▬▬▬▬▬▬ {RATIO}x {RATIO_LABEL} ▬▬▬▬▬▬▬
FASE ░ {PHASE}  Cond:{COND}/5  Size:{SIZE}%

🟢 BID WALLS          🔴 ASK WALLS
{B1_PRC} │{B1_LOT}│f{B1_FRQ}  {A1_PRC} │{A1_LOT}│f{A1_FRQ} {A1_TAG}
{B2_PRC} │{B2_LOT}│f{B2_FRQ}  {A2_PRC} │{A2_LOT}│f{A2_FRQ}
{B3_PRC} │{B3_LOT}│f{B3_FRQ}  {A3_PRC} │{A3_LOT}│f{A3_FRQ}
FLOOR→{FL_PRC}│{FL_LOT}{FL_DIR}│f{FL_FRQ}

CONDITIONS [LR]
{C1} Wall bid hold/tebal    {C2} Harga flat di low
{C3} Candle reversal        {C4} Volume spike naik
{C5} Bid naik 2+ snapshot

▸ AGG  {AGG_STATUS}
       E:{A_E} SL:{A_SL} TP1:{A_T1} TP2:{A_T2} RR:{A_RR}x
▸ MOD  E:{M_E} SL:{M_SL} TP1:{M_T1} TP2:{M_T2} RR:{M_RR}x
▸ LR   E:{L_E} SL:{L_SL} TP1:{L_T1} TP2:{L_T2} RR:{L_RR}x
       SL-dist:{L_SLD}pt | TP1-dist:{L_T1D}pt

⚡ DELTA (vs {PREV_TIME})
   Price {D_PRC} │ Low {D_LOW} │ Vol {D_VOL}
   Bid {D_BID} │ Ask {D_ASK} │ Ratio {D_RAT}
   Wall {D_WALL_NAME}: {D_WALL_CHG}

⚠️ {ALERT_MSG}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## LEGEND & ATURAN PENGISIAN

### Header Line
| Variabel | Isi | Contoh |
|---|---|---|
| `{EMOJI_TREND}` | 🟢 naik / 🔴 turun / ⬜ flat | 🔴 |
| `{LOW_FLAG}` | `▼` jika new low terbentuk snapshot ini, kosong jika tidak | ▼ |
| `{DIV_PCT}` | `((Price - Avg) / Avg) * 100`, 1 desimal | -4.5 |

### Ratio Label
| Nilai | Label |
|---|---|
| ≥ 3.0 | `BID_SANGAT_KUAT 🔥` |
| 2.0–2.9 | `BID_DOMINAN` |
| 1.3–1.9 | `BID_UNGGUL` |
| 0.8–1.2 | `BALANCE ⚠` |
| 0.5–0.7 | `ASK_UNGGUL` |
| < 0.5 | `ASK_MENDOMINASI 🚨` |

### Phase Options
```
DISTRIBUSI        → harga turun dari high, ask walls muncul
CAPITULATION      → harga jatuh cepat, new lows terus terbentuk
SILENT_ACCUM      → harga flat di low, bid naik diam-diam
REVERSAL_CONFIRM  → harga mulai naik, wall bid hold
RECOVERY          → bounce signifikan, mendekati resistance
RANGE_BOUND       → konsolidasi antara support & resistance
UNDETERMINED      → tidak cukup sinyal untuk klasifikasi
```

### Wall Direction Flag
| Simbol | Arti |
|---|---|
| `↑` | Wall bertambah tebal vs snapshot sebelumnya |
| `↓` | Wall menipis / berkurang |
| `⚡` | Wall baru muncul (tidak ada di snapshot sebelumnya) |
| `✂️` | Wall hilang / di-pull |
| *(kosong)* | Tidak ada perubahan signifikan |

### Conditions Checklist
| Simbol | Status |
|---|---|
| `✅` | Terpenuhi |
| `⏳` | Belum terpenuhi / dalam proses |
| `❌` | Jelas tidak terpenuhi |

### AGG Status Options
```
— SKIP ({alasan})     → jika tidak layak entry
✅ VALID              → entry bisa dilakukan
⚠️ PARTIAL ({alasan}) → entry dengan size dikurangi
```

### Size Rule
| Cond terpenuhi | Size |
|---|---|
| 0–1 | 0% (SKIP) |
| 2 | 30% |
| 3 | 50% |
| 4 | 75% |
| 5 | 100% |

## CONTOH FILLED — TPIA 13:54

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
       E:- SL:- TP1:- TP2:- RR:-
▸ MOD  E:1808–1815 SL:1792 TP1:1830 TP2:1845 RR:1.8x
▸ LR   E:1803–1810 SL:1788 TP1:1825 TP2:1840 RR:2.2x
       SL-dist:15–22pt | TP1-dist:15–22pt

⚡ DELTA (vs 13:49)
   Price -25 │ Low ▼1835→1830 │ Vol +190K
   Bid +43K↑ │ Ask -17K↓ │ Ratio 1.21→1.75
   Wall 1,800: +11,780lot (58,350→91,813)

⚠️ Entry LR hanya setelah touch 1,800 + wall hold
   2+ menit + candle reversal terkonfirmasi.
   Jika 1,800 jebol → ABORT semua setup.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## CONTOH FILLED — TPIA 13:39 (SILENT ACCUMULATION)

```
━━━ TPIA 1,845 🔴-5.63% | 13:39 ━━━
H:2070 L:1835 Avg:1963(-6.0%)
Vol:11.90M Val:2.33T

BID 192,198lot f2,498  ║  ASK 74,834lot f465
▬▬▬▬▬▬▬ 2.57x BID_DOMINAN ▬▬▬▬▬▬▬
FASE ░ SILENT_ACCUM  Cond:4/5  Size:75%

🟢 BID WALLS            🔴 ASK WALLS
1,840 │ 16,432 │ f373   1,890 │ 20,100 │ f49  CEIL
1,820 │ 16,422 │ f153   1,895 │ 12,973 │ f45
1,805 │ 19,896 │ f226   1,900 │ 12,652 │ f62
FLOOR→1,800│70,130↑│f748

CONDITIONS [LR]
✅ Wall bid makin tebal    ✅ Harga flat di low
⏳ Candle reversal         ✅ Bid naik 2+ snapshot
✅ Volume spike naik

▸ AGG  ✅ VALID
       E:1845–1848 SL:1828 TP1:1860 TP2:1875 RR:1.5x
▸ MOD  E:1838–1843 SL:1822 TP1:1858 TP2:1870 RR:1.8x
▸ LR   E:1838–1845 SL:1822 TP1:1860 TP2:1875 RR:2.0x
       SL-dist:16–23pt | TP1-dist:15–22pt

⚡ DELTA (vs 13:35)
   Price 0 │ Low →1835 (hold) │ Vol +170K
   Bid +53K↑↑ │ Ask +20K↑ │ Ratio 2.55→2.57
   Wall 1,800: +11,780lot (58,350→70,130)

⚠️ SILENT ACCUM terkonfirmasi — bid +53K dalam 4 menit
   meski harga flat. Entry 60% sekarang, 40% kalau
   ada dip ke 1,835–1,838.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## PERBEDAAN vs Template v1

| Aspek | v1 (lama) | v2 (ini) |
|---|---|---|
| Bid/Ask detail | Ratio saja | Total lot + freq + ratio |
| Wall info | Floor + Ceil only | 3 level bid + 3 level ask + floor |
| Wall behavior | Tidak ada | ↑↓⚡✂ per snapshot |
| TP split | TP tunggal | TP1 + TP2 per tier |
| SL distance | Tidak ada | SL-dist + TP1-dist dalam poin |
| Conditions | Count saja (1/5) | Checklist per kondisi ✅⏳❌ |
| Delta section | Tidak ada | Price + Low + Vol + Bid + Ask + Wall |
| Phase | UNDETERMINED saja | 7 opsi fase spesifik |
| AGG status | Entry langsung | SKIP / VALID / PARTIAL dengan alasan |
| Size rule | Tidak ada rule | Tabel rule berdasarkan cond count |
