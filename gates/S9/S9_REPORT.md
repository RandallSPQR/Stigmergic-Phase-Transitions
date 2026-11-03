# Gate S9: power simulation and tier table, 2026-11-03

**Results.**
- **Horizon: 30 sweeps stands** (D28 rule met).
- **Tier Strong at ρ = 1 (D29):**
  - **61 clusters** on the final-sweep outcome, matching the back-of-envelope estimate: about **$77 core, $144 with
    all secondary arms**;
  - **48 clusters** if the primary outcome is the mean over sweeps 25–30 (the D28 proposal): about **$61 core, $113
    with all arms**.
- **Three validation flags** go to the owner. On reading they are consistent with chance, and none makes the sizing
  less conservative.

Plan: `S9_PLAN.md` (approved; D29 changes). Code: `s9_kernels.py`, `s9_sim.py`, `s9_run.py` (committed before the run
finished). Results:
- `results/s9_tiers.json`;
- `results/kernels_s8.json` (the kernel tables, the S10 inputs for predictions);
- `results/rho_from_s8.json`.

CPU only, about 11 min; no model call; **no sealed value used or opened**. The output contains no level of either
confirmatory contrast, only changes, spreads, ratios, powers and costs.

## Simulator
- **Kernel tables** per model at its D23 T, from the exact S8 readout probabilities, in three tables: live (type ×
  own-vote agreement × contacts showing the reference option, 0–4), blind, and initial (D25). Sparse cells are shrunk
  toward a logistic fit (weight n/(n + 20)). There are 200 cluster-bootstrap draws.
- **Clusters:** fresh N = 100, d = 4 graphs and D18 allocations. Every model sees the same clusters and random streams,
  as the study keys randomness by cluster. The D26 pulse; the unpulsed branch is the live continuation.
- **Start jitter:** from S4 (σ of probe × start ÷ T) on every call.
- **Size:** a pool of 200 clusters × (point + 200 draws) × 5 models for sizing, and 2,000 fresh boards per model for
  the horizon.

## Validation against S8 (open quantities only; `validation` in `s9_tiers.json`)
| quantity | S8 | simulation (central 95%) | inside |
|---|---|---|---|
| pooled live slope, sweeps 20–30 (per sweep) | 0.0030 | −0.0062 to 0.0067 | yes |
| pooled immediate response | 0.155 | 0.115 to 0.188 | yes |
| exposure | 0.958 | 0.947 (mean) | — |
| pooled between-cluster SD, board effect | 0.059 | 0.045 to 0.101 (median 0.070) | yes |
| pooled between-cluster SD, persistence | 0.046 | 0.037 to 0.090 (median 0.059) | yes |

**Flags (pre-stated rule: any S8 quantity outside the simulation's central 95% goes to the owner, uncorrected):**
1. **Gemma-2-9B, blind support at sweep 10:** S8 0.624 against the simulated range of up to 0.612. The other 6 sweeps
   are inside.
2. **Gemma-3-27B, blind support at sweep 10:** also just outside; the other sweeps are inside.
3. **Gemma-3-27B, between-cluster SD of the board effect:** S8 0.015, against a simulated range of 0.026–0.123. S8 is
   *lower* than the simulation.

**Reading.**
- 38 comparisons were made, so about 2 flags are expected at 5% by chance.
- Flags 1 and 2 fall at the same sweep in models that share S8's clusters and random numbers, so they are one
  correlated excursion, not two.
- Flag 3 means the simulation is the more conservative of the two for that model. It does not make the sizing less
  safe.
- No systematic misfit appears in trajectories, slope, immediate response or spread. The pooled simulated SDs are
  1.17× (board) and 1.29× (persistence) S8's.

## Horizon (D28): **30 sweeps stands**
- 2,000 fresh boards per model at the point kernels.
- The change in the expected live − blind contrast across the final 10 sweeps is at most |0.0043| for every H from 30
  to 60 and every model.
- Its 80th percentile over the 200 kernel draws is ≤ 0.0149.
- Both are well inside ±0.025, for every confirmatory model.
- The levels are not reported.

**Live-only trend (D28 item 2).**
- The simulation's expected live support changes by only +0.0002 to +0.0029 over sweeps 20–30.
- S8's pooled slope (+0.030 per 10 sweeps) is larger, but lies inside the simulation's 95% range for an 8-cluster
  pilot.
- So the simulation does not reproduce a gross trend, and S8's trend is consistent with pilot noise. It is reported for
  the owner's judgement.

## Final window (D28 item 3)
- The variance of the board effect measured as the mean over sweeps 25–30, against the final sweep: ratio 0.51–0.62
  per model (SD ratio about 0.78).
- That is equivalent to **about 1.7× as many clusters**.

## Sizing at ρ = 1 (D27, D29)
| contrast | simulated 80th-percentile SD (ρ = 1) | S8 conservative SD | **sizing SD** (the larger) |
|---|---|---|---|
| board effect, final sweep | 0.070 | 0.071 | **0.071** (S8) |
| board effect, window 25–30 | 0.055 | 0.056 (S8 × the simulated window ratio) | **0.056** (S8) |
| persistence (ITT) | 0.063 | 0.055 | **0.063** (simulation) |

The cross-model correlation (ρ) of cluster deviations from the simulation itself is about **0.30** for the board
effect and **0.41** for persistence (medians over draws). So sizing at ρ = 1 is conservative, as intended.

## Tier table (ρ = 1; superiority α = 0.025 two-sided, 80% power; TOST at ±0.03)
**Final-sweep outcome (the current primary):**

| tier | clusters | driven by | MDE board / persistence | TOST power α 0.05 (board / persistence) | TOST α 0.025 | core cost | with all arms |
|---|---|---|---|---|---|---|---|
| Lean | 20 | board | 0.049 / 0.043 | 0.19 / 0.38 | 0.00 / 0.14 | $27 (10.7 GPU-h) | $49 (19.6 h) |
| Standard | 49 | board | 0.031 / 0.028 | 0.81 / 0.91 | 0.68 / 0.84 | $62 (25.0 h) | $116 (46.8 h) |
| **Strong** | **61** | board | **0.028 / 0.025** | **0.90 / 0.96** | 0.82 / 0.93 | **$77 (30.9 h)** | **$144 (57.9 h)** |

**Window outcome (mean over sweeps 25–30; proposed for the pre-registration):**

| tier | clusters | driven by | MDE board / persistence | TOST α 0.05 | TOST α 0.025 | core | with all arms |
|---|---|---|---|---|---|---|---|
| Lean | 15 | persistence | 0.044 / 0.050 | 0.34 / 0.17 | 0.10 / 0.00 | $21 | $37 |
| Standard | 38 | persistence | 0.028 / 0.031 | 0.91 / 0.81 | 0.82 / 0.68 | $49 | $91 |
| **Strong** | **48** | persistence | **0.025 / 0.028** | **0.96 / 0.91** | 0.92 / 0.83 | **$61 (24.3 h)** | **$113 (45.6 h)** |

**Costs.**
- They come from S8's measured seconds per cluster at H = 30, with self-reset on 50% of saved states.
- Added: start overhead (4 min per start per model, 4 clusters per start), the setup of 3 pods, and a 10% failed-pod
  margin, at $2.49/h.
- "All arms" adds: Llama on every cluster; T = 1 on 20%; rule (ii) on 20%; and each valid variant wording on 20% per
  model.

## Checks
- **Normal approximation** (complete studies resampled from the simulated clusters, native ρ, effect centred; 4,000
  studies per n): empirical TOST power 0.69 against normal 0.75 at n = 20; 0.992 against 0.993 at n = 49; 0.999
  against 0.999 at n = 61. The normal approximation is slightly optimistic only at small n, and accurate at the
  Standard and Strong sizes.
- **Generalisation to new stories (story random effect, D29)**, at Strong, final-sweep outcome:

  | story SD | board TOST power | persistence TOST power |
  |---|---|---|
  | 0 | 0.90 | 0.96 |
  | 0.02 | 0.83 | 0.91 |
  | 0.04 | 0.60 | 0.70 |

  On the window outcome: 0.96 / 0.91 / 0.69 for the board effect. Generalisation inference is secondary. A story SD
  near 0.04 would make it noticeably weaker.

## For the owner
1. **Strong at ρ = 1 is 61 clusters** (final sweep), as the back-of-envelope estimate said. The cost is higher than
   quoted: **$77 core, $144 with all arms**, against $69 / $116. The earlier estimate left out start overhead, pod
   setup and the 10% failure margin.
2. **The window outcome (D28 item 3)** reduces the board effect's variance by about 40%. Strong then needs **48
   clusters** ($61 / $113), and persistence becomes the binding contrast. Adopting the window outcome is the owner's
   decision for the pre-registration.
3. **The three validation flags** are above. Recommendation: accept them as chance and conservative, respectively.
4. **Horizon:** 30 sweeps stands under D28.
