# Difficulty by simulated power: results (2026-11-01)

Plan: `POWER_PLAN.md`, committed before any power number. Data: `results/per_board.json`, a re-run on identical seeds
that reproduces `results/grid.json` exactly. Results: `results/power.json`. CPU only.

**Chosen setting (pre-stated rule, informed fraction 0.5): strong sources {3/4, 9/10}.**
- **Region (S8 pilots from it):** {3/4, 9/10} and the provisionally approved {3/5, 3/4, 9/10}.
- **Unconstrained optimum, reported only:** informed fraction 0.7 with {3/4, 9/10}.
- Nothing was chosen on a simulated live effect. The effect is fixed at ±0.05, and the simulation supplies only blind
  accuracy and the board-to-board variance of the paired contrast.

## Power surface, representative boards

How to read the columns:
- **Score** is the 75th percentile across the 81 proxy kernels of n_80. n_80 is the clusters per model for 80% power
  in the worse direction of ±0.05: one pooled test over 5 models, two-sided α = 0.025. Lower is better.
- **SD of contrast** is the median across kernels of the SD of (live − blind) across the 40 boards.

| f | sources | score (p75 n_80) | median n_80 | p90 n_80 | SD of contrast | blind accuracy |
|---|---|---|---|---|---|---|
| **0.5** | **MS {3/4, 9/10}** | **3.1** | 1.5 | 6.8 | 0.044 | 0.597 |
| **0.5** | **WMS {3/5, 3/4, 9/10}** | **3.6** | 1.9 | 8.1 | 0.050 | 0.579 |
| 0.5 | WM {3/5, 3/4} | 7.1 | 1.9 | 16.5 | 0.049 | 0.534 |
| 0.5 | W {3/5} | 10.8 | 1.8 | 34.9 | 0.049 | 0.504 |
| 0.3 | MS / WMS / WM / W | 4.4 / 6.0 / 8.4 / 8.3 | 1.8–2.1 | | 0.049–0.053 | 0.512–0.565 |
| 0.7 | MS / WMS / WM / W | 2.4 / 2.6 / 4.9 / 8.0 | 1.0–1.7 | | 0.036–0.048 | 0.512–0.643 |

The challenge-set stratum (labelled; reported, never used to choose) scores 4.7–8.0. Its full surface is in
`results/power.json`.

**Why stronger sources win.** Stronger evidence anchors informed agents, so the board-to-board variance of the
contrast drops (SD 0.044 vs 0.049). With weak sources, a minority of plausible kernels lets live boards tip one way or
the other. That fattens the tail: the 90th-percentile n_80 is 35 for W, against 6.8 for MS. Both directions stay
feasible everywhere: blind accuracy is between 0.50 and 0.64, so +0.05 and −0.05 both fit inside the bounds.

## Caveats

- These are **proxy-kernel** variances. Real boards add the between-start shift (D14), between-model differences,
  kernel misfit and LLM-specific noise. The absolute n_80 values (2–11 clusters per model) are therefore optimistic,
  and S9 sets cluster counts from measured kernels and the pilot.
- Only the **ranking** of cells is used here. After S3–S5 the same computation is re-run with measured kernels; the
  choice may move, and that move would be logged.
