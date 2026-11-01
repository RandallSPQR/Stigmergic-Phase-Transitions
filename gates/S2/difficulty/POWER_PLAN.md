# Difficulty by simulated power (owner's addendum, 2026-11-01). Plan committed before any power number is computed.

**Owner's rule.** The difficulty band is not set by hand. From the proxy-kernel simulation, choose the region that
maximises simulated power to detect a board effect of ±0.05 in **both** directions: aggregation (+) and cascade (−).
Power uses blind-board accuracy and between-graph variance. The power surface is reported, and the chosen region and
its rationale go into the coordination record before any live data.

**D17 still applies:**
- Nothing is chosen on the size of any simulated live effect. The effect is fixed at ±0.05; the simulation supplies
  only variances and blind accuracy.
- The informed fraction stays at the middle level, 0.5.
- Challenge-set boards are a labelled stratum: reported, never used to choose.

## Data

- The difficulty grid of `PLAN.md` is re-run on identical seeds (same graphs, allocations, starts and update seeds),
  now storing each board's blind and live accuracy. This is `run_grid.py --per-board`.
- The per-cell means must equal `results/grid.json`, which checks that the re-run is the same simulation.

## Power per (cell, kernel)

Notation:
- p is the mean blind accuracy (all 100 agents) over the cell's 40 boards.
- σ_d is the SD across the 40 boards of the paired contrast (live − blind) on the same board. This is the
  between-graph variance of the contrast; a cluster is a graph and allocation.

Steps:
1. **Variance under an effect δ.** σ_d(δ)² = σ_d² × [p(1 − p) + (p + δ)(1 − p − δ)] / [2 p(1 − p)]. This is a
   Bernoulli rescaling, so the two directions differ near the bounds. A direction with p + δ outside [0.01, 0.99] has
   power 0.
2. **Design.** One pooled test over the five models (fixed strata, equal n clusters per model, a common effect):
   SE = σ_d(δ) / √(5 n).
3. **Power.** Power(δ, n) = Φ(|δ|/SE − z) + Φ(−|δ|/SE − z), with z = z_{0.9875} for two-sided α = 0.025 (Holm's
   first step over the two confirmatory contrasts).
4. **n_80** = the smallest n (clusters per model, continuous) with power ≥ 0.80 in the **worse** direction.

## Choice

- **Cell score:** the 75th percentile, across the 81 kernels, of n_80 in the worse direction. Lower is better. This
  is robust to kernel uncertainty: it is the n that serves 3 in 4 plausible kernels.
- **Chosen setting:** among the f = 0.5 cells (representative boards), the source set with the lowest score.
- **Region:** f = 0.5 cells whose score is within 25% of the best. S8 pilots up to 3 settings from the region; if it
  has fewer than 2, the next-best f = 0.5 cell is added.
- **Also reported:** the full surface (every cell, both strata), power at n = 10 and n = 20 clusters per model, and
  the unconstrained optimum over all f. The unconstrained optimum is for transparency; it does not choose.

The result goes to `results/power.json` and `POWER_REPORT.md`. The coordination record gets the chosen setting,
region and rationale. CPU only.
