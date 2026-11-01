# Gate S1: simulator checks (plan, committed before any simulation)

**Pass rule.** S1 passes when every comparison below is within its stated tolerance. Tolerances are fixed here and are
not changed after results are seen. A failure is investigated and reported before S2. CPU only; no model calls.

**What is checked.** `stpt/sim.py` is the StPT simulator core, adapted from SPT's `surrogate.py` and `kernel_test.py`:
- random-sequential updates (with replacement; a sweep is N updates);
- a per-agent table kernel P[i, own vote, contacts showing +1];
- a display layer that the vote updates;
- all randomness from numpy PCG64 with recorded seeds.

It runs on random-regular graphs from networkx 3.7 (pinned), at the two degrees in the design: d = 4 (core) and d = 6
(robustness). Every reference is exact for N → ∞ on tree-like graphs and is computed in `stpt/references.py`,
independently of the simulator. Benchmarks use N = 20,000. Live boards are N = 100, which section G covers.

Tolerance notation: SE is the simulation's standard error (batch means over time, combined with the spread across
independent graphs where stated); SE_ref is the reference's own SE (population dynamics only).

## B1. Ising model, uniform field (exact Bethe solution)

Heat bath, J = 1, all agents share one table. Points (d, T, H):
- d = 4: (4, 2.0, 0.1), (4, 2.885, 0.1), (4, 4.0, 0.1), (4, 4.0, 0.0). Here T_c = 2.885.
- d = 6: (6, 3.5, 0.1), (6, 4.933, 0.1), (6, 7.0, 0.1), (6, 7.0, 0.0). Here T_c = 4.933.

Run: one graph per point; start all +1 when H > 0, random when H = 0; 500 warm-up sweeps; 1,000 measured sweeps.
Measures: magnetisation m and nearest-neighbour correlation (bond), each per sweep, SE from 20 batch means.

**Tolerance:** |sim − ref| ≤ 4 SE + 0.005 for m and for bond.
**Cross-check:** SPT's inherited `surrogate.run`, set to the same heat-bath rule (voter p = 0, α = 0, b_a = 2βJ,
b_r = 0, h_C = 2βH, no letter or order fields, all ties allies), on the same graph. Measure its signed m over 4 seeds
(SE across seeds), at the four d = 4 points. **Tolerance:** |m − ref| ≤ 4 SE + 0.005.

## B2. Random-field Ising model, finite temperature (population dynamics)

Per-agent Gaussian fields h_i ~ N(0, σ²), the stand-in for private evidence. Points (d, T, σ, H), chosen clear of the
ordering transition:
- d = 4: (4, 2.0, 1.0, 0.1) ordered; (4, 2.0, 3.0, 0.1) disordered; (4, 3.5, 1.0, 0.0) paramagnet.
- d = 6: (6, 3.5, 1.5, 0.1) ordered; (6, 3.5, 4.0, 0.1) disordered; (6, 6.0, 1.5, 0.0) paramagnet.

Run: 2 independent graph-and-field realisations per point, otherwise as B1. The reference uses population size
200,000, 400 iterations and 4 independent populations.

**Tolerance:** |sim − ref| ≤ 4 √(SE² + SE_ref²) + 0.005 for m and bond. SE combines both realisations.

## B3. Random-field Ising model at T = 0: avalanches under a rising field (Dhar–Shukla–Sethna)

Rule: an agent's vote is the sign of its local field. Start all −1 and raise H on a grid; at each H, relax to a fixed
point. Points (d, σ):
- (4, 2.5), smooth;
- (4, 1.5), jumps at H ≈ 1.099;
- (6, 3.5), smooth;
- (6, 2.0), jumps at H ≈ 1.867.

One realisation per point.

**Tolerances:**
- m(H) on the grid H = −4.0, −3.75, …, 4.0: |sim − ref| ≤ 0.02, excluding grid points within 0.1 of a reference jump.
- Jump location, on a fine grid of step 0.005 within ±0.3 of the reference jump: |H_sim − H_ref| ≤ 0.08. At this N the
  finite-size shift of an avalanche onset is expected around N^(−1/3) ≈ 0.04.
- Jump size: |size_sim − size_ref| ≤ 0.1.
- Order independence: relaxing the same configuration with two different update-order seeds gives a bit-identical
  final state at every grid H. Single-flip T = 0 dynamics of the ferromagnetic random-field model are abelian.

## B4. Threshold cascades from random seeds (Gleeson–Cahalane)

Monotone rule, which uses the own-vote dimension of the table: active agents stay active; an inactive agent activates
when its fraction of active contacts reaches its threshold φ_i ~ N(μ, 0.1²). Seeds: each agent starts active with
probability ρ0. Relax to a fixed point. Points (d, μ, ρ0), chosen clear of the jump to full activation:
- d = 4: (4, 0.5, 0.05), (4, 0.5, 0.1), (4, 0.5, 0.2), (4, 0.4, 0.05), (4, 0.4, 0.2);
- d = 6: the same five (μ, ρ0) pairs.

Run: 5 realisations (graph, thresholds, seeds) per point.

**Tolerance:** |ρ_sim − ρ_ref| ≤ 4 SE + 0.005, with SE across realisations.

## G. Graphs at the live size (N = 100)

For d = 4 and d = 6: 1,000 seeds each.
- **Required:** every graph is simple and d-regular; the same seed gives the same fingerprint twice; networkx is 3.7.
- **Reported:** the share of connected graphs. Any disconnected graph is reported. The study's graph-seed rule
  (redraw or keep) is set at the protocol freeze.

## R. Reproducibility

Required:
- the same seed and start give bit-identical votes after 50 sweeps of a stochastic kernel (N = 100, d = 4);
- a different seed gives different votes;
- a copied state (votes, displays, generator) continues identically. This is the property later branch gates rely on;
  S7 tests branches in full.

Outputs go to `gates/S1/results/` (one JSON per section, plus `summary.json`) and `gates/S1/S1_REPORT.md`.

## Amendment 1 (2026-11-01): post-outcome deviation, approved by the owner, committed before the re-run

This is decided after B3's original result was seen. That result is a FAIL on both smooth cases, kept on record in
`S1_REPORT.md` and `results/B3.json`. Logged in the coordination record as a post-outcome deviation.

- **Why.** The exact curve is an ensemble (large-N, averaged) result, so a single-graph comparison was mis-specified.
  Near the critical disorder, graph-to-graph spread is large: up to 0.025 at d = 4 on the steep section, and up to
  0.19 at d = 6, σ = 3.5 (`diagnostics/B3_realisation_spread.json`).
- **Amended B3 smooth-case rule.** Mean over 10 independent graph-and-field realisations at N = 20,000, on the same
  coarse grid (H = −4.0, −3.75, …, 4.0). Per grid point: |mean Δm| ≤ 4 SE + 0.005, with SE = SD across realisations
  / √10. The same rule as B1, B2 and B4.
- **Pass/fail points:** (d = 4, σ = 2.5) and (d = 6, σ = 4.5). The (6, 4.5) point replaces (6, 3.5), which sat just
  above the critical disorder.
- **(d = 6, σ = 3.5) is kept as a near-critical diagnostic:** 10 realisations, mean and spread reported, no pass/fail.
- **New seeds:** labels `B3A|<d>|<σ>|<k>`, distinct from the original run and from the diagnostic.
- **Unchanged:** the jump cases (4, 1.5) and (6, 2.0) passed the original rule and are not re-run. Order independence
  is checked again on every amended realisation (two update orders, bit-identical at every H).
- **Gate rule:** S1 passes if R, G, B1, B2, B4 (passed), B3's jump cases (passed) and the amended smooth-case points
  all pass.
