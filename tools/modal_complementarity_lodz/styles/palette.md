# Palette — flagship Lodz cartography (F4)

PRD §7 requirements: sequential, single-hue, deuteranopia-safe, monotonic lightness,
grayscale-readable, not red, consistent with (future) logo. Values below were run through the
`dataviz` skill's `scripts/validate_palette.js` — **do not hand-edit a hex without re-running
it**, the checks are load-bearing (this is exactly the kind of thing "looks fine" fails at).

## P1 — `tram_share_pop_p50_c30` (hero image), 7 classes, blue

Anchor hue: blue (`#2a78d6`, the `dataviz` skill's default sequential/categorical-slot-1 hue —
picked so it's easy for a future Easy-R5 logo to sit in "the same family" per
`docs/notes/logo-brief.md` §3 point 3, and is far from r5r/r5py's teal `#1B87A8`).

| class | hex | range |
|---|---|---|
| 1 | `#87b3e8` | 0–5% |
| 2 | `#619be1` | 5–15% |
| 3 | `#3a82d9` | 15–25% |
| 4 | `#256cc0` | 25–40% |
| 5 | `#1e569a` | 40–55% |
| 6 | `#164173` | 55–70% |
| 7 | `#0f2b4d` | >70% |

```
node scripts/validate_palette.js "#87b3e8,#619be1,#3a82d9,#256cc0,#1e569a,#164173,#0f2b4d" \
  --mode light --surface "#FAF8F4" --pairs all --ordinal
→ ALL CHECKS PASS (lightness monotone, adjacent ΔL >= 0.06, light-end contrast 2.05:1
  vs the #FAF8F4 canvas, hue spread 2°)
```

## P2 — `transfer_premium_rel_pop_p50_c30`, 5 classes, orange

Anchor hue: orange (`#eb6834`, categorical-slot-2 — "the second sequential context takes the
next categorical slot's hue" per the skill's `palette.md`). Distinct from P1's blue so the two
maps are never confused; still nowhere near red.

| class | hex | range |
|---|---|---|
| 1 | `#f0906a` | 0% |
| 2 | `#ea5d25` | 0–5% |
| 3 | `#b03f11` | 5–10% |
| 4 | `#822e0d` | 10–20% |
| 5 | `#541e08` | >20% |

```
node scripts/validate_palette.js "#f0906a,#ea5d25,#b03f11,#822e0d,#541e08" \
  --mode light --surface "#FAF8F4" --pairs all --ordinal
→ ALL CHECKS PASS (light-end contrast 2.22:1, hue spread 3°)
```

## Fixed non-ramp colors (both maps)

| role | hex | source |
|---|---|---|
| "No transit access in 30 min" class | `#E6E3DE` | PRD §7, literal | 
| `pop_total = 0` hexagons | transparent | PRD §7 |
| City boundary line | `#B9B4AC`, 0.6 px | PRD §7 |
| Canvas background | `#FAF8F4` | PRD §7 |
| Tram network inset line | `#3a3a38` (dark neutral, not blue/orange — must read as "the network," not as more data) | chosen for this milestone |

The "no access" gray has zero saturation; both ramps' lightest class is fully chromatic (blue
or orange) — confirmed visually distinguishable at render time (see `make_figures.py` output).
Grayscale readability follows structurally from the validator's "lightness monotone" pass: a
ramp that reads light→dark in color reads light→dark after desaturating, by construction.

## P3 bar chart — case colors

Not a ramp (categorical: 4 modal cases). Colors reused from P1/P2 rather than the `dataviz`
categorical slot *order*, so a reader who has seen the hero image recognizes "blue = tram,
orange = bus" instantly in the bar chart too — cross-figure identity consistency outranks strict
slot-order here, a deliberate deviation from the skill's default rule, noted for the record.

| case | hex | reasoning |
|---|---|---|
| `W` (walk only) | `#898781` (muted ink, chart chrome) | baseline, not a "mode" being compared |
| `T` (tram+walk) | `#2a78d6` | = P1's anchor hue |
| `B` (bus+walk) | `#eb6834` | = P2's anchor hue |
| `TB` (full network) | `#4a3aa7` (categorical slot 7, violet) | distinct highlight; also logo-brief.md §4's "dark violet" candidate direction, kept available for a future consistent logo hue |
| `no_transfer` marker | `#0b0b0b` dashed line, not a bar | overlaid on the TB bar at `max(T,B)` height — the complementarity gap *is* the space between this line and the TB bar top |

## Logo

No Easy-R5 logo exists yet (`docs/notes/logo-brief.md` is a brief, not a delivered asset — its
own "Pliki do wyprodukowania" list is unchecked). PRD §7 asks for a logo corner on the hero
image; **this milestone omits it** rather than fabricate a placeholder mark — adding a fake logo
would misrepresent unfinished brand work. Revisit once logo-brief.md's open decision (Michał's
"do rozstrzygnięcia" in §1) is closed.
