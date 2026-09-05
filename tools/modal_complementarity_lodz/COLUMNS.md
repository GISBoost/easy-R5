# Column reference — `hex_modal` layer / `out/hex_modal.csv`, `out/city_summary.csv`

Computed by `compute_metrics.py` from the four `out/acc_<W|T|B|TB>.csv` runs
(`run_modal_cases.py`). Formulas are PRD
[`docs/prd/PR_easy-R5_flagship-lodz-modal.md`](../../docs/prd/PR_easy-R5_flagship-lodz-modal.md)
§4.4–4.5. **Read this before using `tram_gain` vs `tram_share` vs `mode_balance` — they
answer different questions and mixing them up is exactly the kind of mistake
`tools/accessibility_lodz/COLUMNS.md` warns about.**

## Scope of the per-hex fields

Computed for **opportunity = `pop_total`** (resident population — the headline opportunity,
PRD §4.2), **percentile = 50**, at all **four cutoffs** (15/30/45/60 min) — 14 metric fields ×
4 cutoffs = 56 fields, plus `hex_id`, `pop_total`, and one services field. **Not** computed for
every (opportunity × percentile) combination (that would be ~1,700 fields with no consumer
identified in F4/F5) — `srv_total`/category accessibility and the non-p50 percentiles exist
only in the raw `out/acc_*.csv` long files if ever needed later.

## Field naming

`<metric>_pop_p50_c<cutoff>` — e.g. `tram_share_pop_p50_c30` = tram_share, opportunity
pop_total, percentile 50, cutoff 30 min. `pop` and `p50` never vary in this run; they're in the
name so a field is self-describing out of context (a screenshot, a copy-pasted column).

## `hex_modal` fields

| Field | Meaning | Range | NULL when |
|---|---|---|---|
| `hex_id` | Hexagon id, joins to `hex_grid`/`hex_centroids`/`hex_destinations` in `lodz_modal.gpkg` | int | never |
| `pop_total` | Resident population of this hexagon (F2, area-weighted) — **not** an accessibility value | ≥ 0 | never |
| `acc_w_pop_p50_c<T>` | `A^W_i(T)` — population reachable **on foot alone** within `T` min | ≥ 0 | never |
| `acc_t_pop_p50_c<T>` | `A^T_i(T)` — population reachable by **tram + walk** within `T` min | ≥ 0 | never |
| `acc_b_pop_p50_c<T>` | `A^B_i(T)` — population reachable by **bus + walk** within `T` min | ≥ 0 | never |
| `acc_tb_pop_p50_c<T>` | `A^TB_i(T)` — population reachable by the **full network** (tram+bus+walk, intermodal transfers allowed) within `T` min | ≥ 0 | never |
| `tram_gain_pop_p50_c<T>` | `A^TB - A^B` — population reachable **only because tram exists** (absolute, people) | ≥ 0 (by I2) | never |
| `bus_gain_pop_p50_c<T>` | `A^TB - A^T` — population reachable **only because bus exists** (absolute, people) | ≥ 0 (by I2) | never |
| `no_transfer_pop_p50_c<T>` | `max(A^T, A^B)` — best single-mode reach, the "tram *or* bus, no transfer" case (PRD §4.1, not its own run) | ≥ 0 | never |
| `transfer_premium_pop_p50_c<T>` | `A^TB - no_transfer` — population reachable **only via an intermodal transfer** (absolute, people) | ≥ 0 (by I2) | never |
| `walk_share_pop_p50_c<T>` | `A^W / A^TB` — how much of the full-network reach needs no transit at all | 0–1 | `A^TB = 0` at this `T`, or hex fails the K-gate (below) |
| `tram_share_pop_p50_c<T>` | `tram_gain / A^TB` — **share of full-network reach that disappears if tram is removed. This is the hero-image metric.** | 0–1 | ″ |
| `bus_share_pop_p50_c<T>` | `bus_gain / A^TB` — share that disappears if bus is removed | 0–1 | ″ |
| `mode_balance_pop_p50_c<T>` | `(A^T - A^B) / A^TB` — which single mode reaches more on its own; **positive = tram-leaning**, negative = bus-leaning | -1–+1 | ″ |
| `transfer_premium_rel_pop_p50_c<T>` | `transfer_premium / A^TB` — share of full-network reach that exists **only** because of an intermodal transfer | 0–1 | ″ |
| `subadd_pop_p50_c<T>` | `Ã^TB / (Ã^T + Ã^B)` where `Ã^m = max(0, A^m - A^W)` (walk-base subtracted first, PRD §4.4) — **&lt;1 = tram and bus overlap (sub-additive), &gt;1 = they complement each other** | ≥ 0, usually 0.5–2 | ″, or when `Ã^T + Ã^B = 0` (both single modes add nothing beyond walking — undefined, not infinity) |
| `acc_tb_srv_p50_c30` | `A^TB_i(30)` for opportunity **`srv_total`** (services, not population) — carried only for `poi_control.py`'s Spearman check against the exact-POI run | ≥ 0 | never |

### The K-reliability gate (PRD §4.5 point 2)

All seven **share/ratio** fields above (`walk_share`, `tram_share`, `bus_share`,
`mode_balance`, `transfer_premium_rel`, `subadd` — at every cutoff, not just c30) are `NULL`
for a hexagon whose **`A^TB_i(cutoff=30, p50, pop_total) < K`** (K = 1,000 people; this run:
**474 of 1,479 hexagons** fail it — `out/run_meta.json`). One fixed reference combo gates all
four cutoffs' shares, so a hexagon isn't "reliable at 30 min but unreliable at 15 min" — it's
reliable or it isn't. The four **absolute** fields (`acc_*`, `tram_gain`, `bus_gain`,
`no_transfer`, `transfer_premium`) are never NULL — small numbers are still numbers; only
*dividing* by a near-zero `A^TB` is what produces meaningless ratios (PRD's "pułapka małego
mianownika", the −100%-of-1-building bug from the earlier student-accessibility pilot).

### `subadd`: per-hex vs. city-level — these are NOT the same number

`subadd_pop_p50_c30`'s **mean across hexagons** in this run is **1.03** (individually noisy,
some hexes well above 1), while `city_summary.csv`'s `subadd_city` at cutoff 30 is **0.9047**.
Both are correct — they're different statistics. The per-hex field averages a *ratio per
hexagon* (sensitive to hexagons with a tiny `Ã^T + Ã^B` denominator, a classic
ratio-of-small-numbers problem, same family as PRD §4.5's small-denominator trap). The city
number computes the ratio *of the city-wide weighted averages* (`Ã^TB_city / (Ã^T_city +
Ã^B_city)`), which is stable and is the one that belongs in a headline sentence — **cite
`subadd_city` from `city_summary.csv`, not a mean of the per-hex `subadd` column.**

## `out/city_summary.csv`

One row per (cutoff, case), 5 cases × 4 cutoffs = 20 rows. `case ∈ {W, T, B, no_transfer, TB}`.

| Column | Meaning |
|---|---|
| `cutoff` | 15 / 30 / 45 / 60 minutes |
| `case` | which of the 5 modal cases |
| `opportunity`, `percentile` | always `pop_total`, `50` in this run |
| `acc_weighted_mean` | `Ā^m(T)` — person-weighted average population reachable (PRD §4.4), i.e. Σ pop_i·A^m_i / Σ pop_i |
| `coverage_pct_K1000` | `cov^m(T)` — % of Łódź's population living in a hexagon with `A^m_i(T) ≥ 1,000` |
| `subadd_city` | City-level sub-additivity for this cutoff (same value repeated across all 5 case-rows of that cutoff, for convenient flat-table reading) — the number to quote, see above |

## `out/poi_control.json`

`{"rho": ..., "n": 1479, "threshold": 0.95, "reliable": true/false}` — Spearman's rho between
`srv_total_30min` computed on `hex_destinations` (POI pre-aggregated to hex centroids) and on
the exact 1,328 `poi_destinations` points, case TB, cutoff 30, p50. **This run: ρ = 0.9886** —
above threshold, so the services metric is trustworthy at hex-centroid resolution without a
caveat.

## `out/invariants.json`

`I1`/`I2` violation counts (must be 0) and `I3`'s value (must be > 0.05 — this run: **0.308**,
177,480 rows checked, meaning R5 genuinely respects `TRANSIT_SUBMODES` on the runner path).

## `out/run_meta.json`

Run parameters, per-case wall-clock timings, plugin/R5 version, and (after
`compute_metrics.py`) the K threshold and filtered-hexagon count.
