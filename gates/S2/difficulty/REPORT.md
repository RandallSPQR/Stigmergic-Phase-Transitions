# Difficulty grid, CPU only: results (2026-11-01)

Plan and rule: `PLAN.md` (D17), committed before the run. Data: `results/grid.json` (one row per cell, stratum and
kernel) and `results/summary.json`. Runtime: 27 s. CPU only; no model; no GPU.

**Headline.** Under the pre-stated rule, all-agent blind accuracy in 0.60–0.85 for at least 2/3 of the 81 proxy
kernels, the region contains **one cell only: informed fraction 0.7 with strong sources {3/4, 9/10}**, and it
qualifies exactly at 2/3.
- **No cell at the middle informed fraction 0.5 qualifies.** The approved sources {3/5, 3/4, 9/10} reach 26% of
  kernels; the strong set reaches 44%.
- **The cause is structural.** Blind accuracy counts all 100 agents, and uninformed agents vote at chance. A board
  where every informed agent simply follows its report is capped at 0.5 + f × (mean accuracy − 0.5). At f = 0.5 that
  is 0.625 for the approved sources and 0.66 for the strong set, so the band's lower edge sits at the ceiling.
- The rule chooses on blind accuracy only. Live results appear below for context and were not used.

## Blind accuracy, representative boards (all 100 agents)

Median across the 81 kernels, with the 10th–90th percentile range. "Ceiling" means every informed agent follows its
report.

| f | sources | blind median [p10, p90] | kernels in 0.60–0.85 | in region | ceiling | live median (context only) |
|---|---|---|---|---|---|---|
| 0.3 | W {3/5} | 0.512 [0.501, 0.529] | 0.00 | no | 0.530 | 0.516 |
| 0.3 | WM {3/5, 3/4} | 0.522 [0.509, 0.552] | 0.00 | no | 0.552 | 0.539 |
| 0.3 | WMS (approved) | 0.537 [0.512, 0.565] | 0.00 | no | 0.575 | 0.565 |
| 0.3 | MS {3/4, 9/10} | 0.565 [0.531, 0.597] | 0.07 | no | 0.598 | 0.600 |
| **0.5** | W | 0.504 [0.494, 0.522] | 0.00 | no | 0.550 | 0.512 |
| **0.5** | WM | 0.534 [0.512, 0.564] | 0.00 | no | 0.588 | 0.552 |
| **0.5** | **WMS (approved)** | **0.579 [0.528, 0.612]** | **0.26** | **no** | **0.625** | 0.615 |
| **0.5** | MS | 0.597 [0.525, 0.658] | 0.44 | no | 0.662 | 0.653 |
| 0.7 | W | 0.512 [0.500, 0.538] | 0.00 | no | 0.570 | 0.524 |
| 0.7 | WM | 0.535 [0.506, 0.602] | 0.11 | no | 0.623 | 0.581 |
| 0.7 | WMS | 0.594 [0.529, 0.663] | 0.48 | no | 0.675 | 0.654 |
| 0.7 | MS | 0.643 [0.551, 0.727] | **0.67** | **yes** | 0.727 | 0.716 |

## What drives blind accuracy (all agents; from `grid.json`)

- **Signal weight w_s and decision noise T dominate.** At f = 0.5 with the approved sources, w_s = 0.5 puts no kernel
  in the band, while w_s = 2 puts 56% in; T = 2 drops the in-band share to 11%.
- **Own-vote weight γ matters next.** Strong anti-persistence (γ = −1.44) puts no kernel in the band; strong
  persistence (2.42) puts 44% in.
- **The social weight b does not change blind accuracy.** Blind boards show no contacts, so this is the expected result
  and a check on the code.

## Challenge-set stratum (labelled; never primary)

- Where the stratum is defined, blind accuracy is near chance: median 0.50–0.53. Most reports point the wrong way, by
  construction.
- Mixing it in only lowers blind accuracy; the mixtures with c = 0.25 and 0.5 are in `summary.json`.
- The stratum is not defined for W: one accuracy level cannot make a minority-correct board solvable.

## Post-result descriptive view (not part of the pre-stated rule)

Blind accuracy **among informed agents only**: `results/informed_only_derived.json`. It is derived as
(all − 0.5(1 − f)) / f, since uninformed agents average 0.5 by symmetry.

| f | sources | informed-only blind median [p10, p90] | kernels in 0.60–0.85 |
|---|---|---|---|
| 0.5 | WM | 0.569 [0.524, 0.627] | 0.22 |
| 0.5 | **WMS (approved)** | **0.657 [0.556, 0.724]** | **0.667** |
| 0.5 | MS | 0.695 [0.551, 0.816] | 0.815 |
| 0.3 | WMS / MS | 0.623 / 0.718 | 0.70 / 0.96 |
| 0.7 | WMS / MS | 0.634 / 0.704 | 0.70 / 0.85 |

On this view, which isolates how hard the evidence is from how many agents hold any, the approved setting sits
exactly at the threshold, and the strong sources sit inside it.

## Options for the owner (the rule stays: blind accuracy only, never live effects)

1. **Measure difficulty among informed agents** (accuracy over informed agents only), keeping the 0.60–0.85 band. Then
   f = 0.5 is in the region with the approved sources (at the threshold) and with the strong sources. The primary
   outcome stays all ordinary agents; only the difficulty yardstick changes.
2. **Keep all agents, but set the band relative to the ceiling**, for example 0.55–0.70 at f = 0.5.
3. **Use stronger sources at f = 0.5** (MS): 44% of kernels in band on the all-agent measure, 82% on the informed-only
   measure.
4. **Raise the middle informed fraction to 0.7**, the only all-agent region. Rung 2's doses would then have to sit
   around it.

Any of these is a prospective change, made before any model data, but after this CPU result. It would be logged as
such. After S3–S5, the same grid is re-run with measured kernels, and S8 pilots 2–3 settings from the region.
