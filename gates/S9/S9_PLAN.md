# Gate S9: power simulation and tier table. Plan for the owner's approval; nothing is run before approval.

**Brief.** S9 returns a tier table (Lean / Standard / Strong) for the **two confirmatory contrasts only**: the board
effect (live − blind) and pulse persistence.
- One pooled test per contrast: the average over the four confirmatory models as fixed strata (D2, D24). Holm across
  the two contrasts. Power is by **independent cluster count**.
- Per tier: clusters, cost (from the pilot's measured per-call costs), MDE at 80% power, TOST power at the proposed
  bound **±0.03**, and the reference effect **0.05** shown as a reference line.
- If no affordable tier reaches a meaningful effect, the scope is cut rather than the sample inflated.

S9 also carries:
- the D28 horizon decision and the final-window outcome;
- D27: tiers sized on conservative variances;
- D14 and A16: between-start variance, with blocking by start;
- the cost of the secondary arms.

CPU only, on development data. No model call. **No sealed value is used or opened.**

## 1. Simulator
- **Kernels, per model, at its D23 T, as cell tables** (replacing the pilot's linear-logistic summary). Each cell holds
  the mean of the *exact* readout probabilities σ(ℓ/T), not counts of sampled votes, from the S8 development
  readouts:
  - **live cells:** informed (by source 3/4 or 9/10, from the S_a clusters, with S_b's 3/5 reports as an extra stratum)
    or uninformed × own vote agrees with the reference option × number of contacts showing it (0–4). About 40,000 live
    updates per model.
  - **blind cells:** the same without contacts, from the S8 blind runs.
  - Sparse cells are shrunk toward the logistic fit, with a pre-stated weight: n / (n + 20).
- **Kernel uncertainty:** 200 cluster-bootstrap draws of the S8 clusters per model. Every simulated quantity is
  reported over the draws.
- **Boards:** fresh random-regular graphs (N = 100, d = 4) and fresh allocations at the confirmatory setting (D18:
  f = 0.5, sources {3/4, 9/10}).
  - Initial vote by rule (i), from the blind kernel with a balanced placeholder (D25).
  - Random-sequential updates. Live and blind share every random number (as the harness does). The pulse follows D26.
  - Graph-to-graph spread at N = 100 is native, since every simulated cluster gets a new graph. This is the S1
    concern.
- **Between-start variance (D14):** each simulated start adds a probe × start jitter to every logit. Its SD per model
  comes from S4 (`gates/S4/results/s4_variance_components.json`), scaled by 1/T. The start offset is ≤ 1e-4 nats²,
  effectively zero. Clusters are assigned to starts and the analysis blocks by start, as in the study.
- **Design that the tiers count:** the same clusters for all four confirmatory models (as in S8), so models are strata
  over shared clusters. One live and one blind run per cluster, one saved state at t0 with two pulsed branches. The
  variant "two saved states per cluster" is also costed (§4).

## 2. Validation against S8 (only quantities that reveal no contrast)
Simulate the 8 S8 clusters themselves (same graphs and allocations), 200 times each per kernel draw, and compare with
the open S8 results:
- blind support trajectories;
- the live slope over sweeps 20–30 (D28's consistency check);
- the immediate response (manipulation check);
- exposure;
- the between-cluster SDs of both contrasts.

Live and blind levels are never compared separately against S8, so no live − blind value is reconstructed.

**Pre-stated discrepancy flags:**
- an S8 open quantity outside the simulation's central 95% range;
- or a simulated between-cluster SD below 0.7 × S8's.

A flag goes to the owner and is never auto-corrected.

## 3. Horizon (D28) and the final-window outcome
- **Boards:** ≥ 1,000 per model per kernel draw (point estimate) and 200 per draw (over the 200 draws), run to 60
  sweeps.
- **Rule:** for H in {30, 35, …, 60}, compute the change in the expected live − blind contrast across sweeps H − 10 to
  H.
  - **30 stands** if |change| < 0.025 for every confirmatory model, at the kernel point estimate and at the
    80th-percentile kernel draw.
  - Otherwise S9 proposes the smallest H that meets the rule, for approval.
- **What is reported: only the change, never the contrast's level.**
- The simulated live-only slope over sweeps 20–30 is compared with S8's open slope (+0.008 to +0.052 per 10 sweeps). A
  gross mismatch goes to the owner (D28 item 2).
- **Final window (D28 item 3):** the variance of the board effect measured at the final sweep versus as the mean over
  sweeps (H − 5) to H. The precision gained is reported as a variance ratio and as an equivalent cluster count.

## 4. Power, MDE, TOST and tiers
- **Per contrast:** the pooled estimator is the mean over models of each model's mean over clusters. Its SE comes from
  the variance across clusters of the cluster's cross-model mean, start-blocked.
  - From the simulation, over the kernel draws.
  - From S8 directly: a new variance-only computation on the S8 rows, outputting the between-cluster variance of the
    cross-model mean (settings-centred, as D27). It produces no point estimate.
- **Sizing SD = max(simulated 80th-percentile SD, S8 conservative SD),** per contrast (D27).
- **Persistence:** its SE uses the cluster-mean of the branches and the between-branch variance, so the table shows
  both levers: more clusters, or more saved states per cluster.
- **Tests:**
  - superiority: two-sided α = 0.025 (Holm's first step; conservative for both contrasts), 80% power;
  - **MDE** = (z₀.₉₈₇₅ + z₀.₈) · SE;
  - **TOST** at ±0.03: two one-sided tests at α = 0.05 (α = 0.025 also shown), true effect 0.
  - The power curves come from the normal approximation, checked by simulating complete studies at three cluster
    counts.
- **Tiers** (proposed definitions):
  - **Lean:** the smallest n with MDE ≤ 0.05 on both contrasts (detects the reference effect);
  - **Standard:** the smallest n with TOST power ≥ 0.80 at ±0.03 on both;
  - **Strong:** the smallest n with TOST power ≥ 0.90 on both.
  - If a tier is unreachable within $500, the table says so (the scope rule).
- **Cost:** per confirmatory rule-(i) cluster, about $0.96 for the four models (S8: about 23 GPU-minutes). Plus:
  - server-start overhead (about 4 min per start per model);
  - the secondary arms, at proposed shares:
    - Llama, the comparison agent: all clusters;
    - T = 1, the secondary regime: 20% of clusters;
    - rule (ii) start: 20%;
    - self-reset branch: 50% of saved states;
    - variant wordings for the per-model consistency check: 20% of clusters per valid variant.
  - Each tier shows the core cost and the cost with the secondary arms.

## 5. Outputs
- `gates/S9/results/s9_tiers.json` and `S9_REPORT.md`:
  - the tier table;
  - power curves;
  - the horizon decision (changes only);
  - final-window precision;
  - validation flags;
  - sizing SDs and their sources;
  - costs.
- The simulator's code is committed with its seeds. The kernel tables are written to
  `gates/S9/results/kernels_s8.json`, as the inputs for the predictions machinery at S10.
- **Not produced:** any simulated level of the live − blind contrast or of persistence. Pre-registered predictions are
  computed at S10 on the confirmatory graphs, from these kernels.

## 6. Questions for the owner (proposed defaults in brackets)
1. **Shared clusters across the four models,** versus independent clusters per model. [Shared, as in S8.]
2. **α for power:** Holm's first step, 0.025 two-sided, for both contrasts. [Yes.]
3. **Tier definitions** as in §4, and the $500 scope ceiling. [As proposed.]
4. **Shares for the secondary arms** as in §4. [As proposed.]

Expected CPU time: under 2 h (numba). No spend.
