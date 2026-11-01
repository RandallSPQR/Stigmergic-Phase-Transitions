# Gate S1: simulator checks (2026-11-01)

**Verdict: S1 FAILS as pre-stated, on one criterion.** The failure is a defect in the plan's tolerance, not in the
simulator.
- 5 of 6 sections pass: R, G, B1, B2, B4.
- In B3, both jump cases pass, but both smooth cases miss the single-realisation tolerance of 0.02 on the steep middle
  of the curve: 4 of 66 grid points.
- A post-outcome diagnostic over 10 independent realisations finds no systematic error. The average matches the exact
  curve at every point. The miss is realisation-to-realisation spread, which is large near the critical disorder. The
  plan assumed noise of about N^(−1/2) instead.
- **Nothing was re-run under a changed criterion.** An amended B3 criterion is proposed for the owner (section 5).

Plan: `S1_PLAN.md`, committed before any simulation. Runner: `run_s1.py`. Results: `results/` (`summary.json` and one
JSON per section). Environment: Python 3.13.18, numpy 2.5.3, numba 0.68.0, networkx 3.7, scipy 1.18.1, 4 CPUs.
Runtime: under 8 minutes.

## 1. Results by section

| section | what | result | numbers (from `results/*.json`) |
|---|---|---|---|
| R | reproducibility | **pass** | same seed gives bit-identical votes; a different seed differs; a copied state (votes, displays, generator) continues identically |
| G | graphs at N = 100, d = 4 and 6, 1,000 seeds each | **pass** | all 2,000 simple and d-regular; each fingerprint reproduced; all 2,000 connected; networkx 3.7 |
| B1 | Ising, uniform field, vs exact Bethe solution (8 points) | **pass** | max \|Δm\| 0.0025, max \|Δbond\| 0.0006 |
| B1× | SPT's inherited `surrogate.run` on the same graphs (4 points, d = 4) | **pass** | max \|Δm\| 0.0006 |
| B2 | random-field Ising, finite T, vs population dynamics (6 points) | **pass** | max \|Δm\| 0.0060, max \|Δbond\| 0.0049 |
| B3 | random-field Ising, T = 0 avalanches, vs Dhar–Shukla–Sethna (4 cases) | **fail** (2 of 4 cases) | see section 2 |
| B4 | threshold cascades vs Gleeson–Cahalane (10 points) | **pass** | max \|Δρ\| 0.0053 |

All differences are well inside each comparison's tolerance, except in B3.

## 2. B3 in detail

| case (d, σ) | grid points within 0.02 | largest \|Δm\| | jump: simulated vs exact | order independence |
|---|---|---|---|---|
| (4, 1.5), jumps | 32/32 | 0.0033 | H 1.116 vs 1.099; size 1.403 vs 1.406 (both within tolerance) | bit-identical |
| (6, 2.0), jumps | 33/33 | 0.0026 | H 1.886 vs 1.868; size 1.728 vs 1.754 (both within tolerance) | bit-identical |
| (4, 2.5), smooth | **30/33** (fails at H = 0.75, 1.0, 1.25) | **0.050** | none | bit-identical |
| (6, 3.5), smooth | **32/33** (fails at H = 1.0) | **0.036** | none | bit-identical |

## 3. Post-outcome diagnostic (labelled; not the gate result)

The question was whether the smooth-case misses are a systematic error, in the simulator or the reference, or the
spread between realisations. File: `diagnostics/B3_realisation_spread.json`.

**N-scan** (d = 4, σ = 2.5; H = 0.5, 1.0, 1.5; N = 5,000 to 320,000; 1–3 realisations each). There is no trend in N.
Mean differences are at most 0.015 at every size. At N = 20,000, the 3-realisation average at H = 1.0 is +0.006.

**10 realisations at N = 20,000 per smooth case:**

| case | every point's mean difference within 4 SE + 0.005? | largest \|mean Δm\| | largest SD across realisations | worst single realisation |
|---|---|---|---|---|
| (4, 2.5) | yes (33/33) | 0.011 | 0.025 (H = 1.0) | 0.042 |
| (6, 3.5) | yes (33/33) | 0.018 | 0.189 (H = 1.0) | 0.247 |

**Reading.**
- The average agrees with the exact curve, so neither the simulator nor the reference is wrong.
- A single realisation can miss by several times 0.02 on the steep part of the curve, where avalanches are large.
- σ = 3.5 at d = 6 is just above the critical disorder: the d = 6 curve jumps at σ = 3.0 but not at 3.5, and some
  finite graphs still show near-jumps. The plan chose that point too close to the transition, and used a
  single-realisation tolerance there.

## 4. What S1 establishes

These all hold, and nothing about them depends on the B3 miss:
- The simulator reproduces exact equilibrium results with uniform and with per-agent fields (B1, B2).
- It reproduces cascade sizes that depend on an agent's own vote (B4).
- It reproduces T = 0 avalanche jumps and order-independent fixed points (B3, jump cases).
- It agrees with SPT's validated simulator (B1×).
- It is reproducible (R).
- It builds valid boards at N = 100 (G).

## 5. Proposed amendment for B3 (owner's decision; would be a logged post-outcome deviation)

1. Compare B3's smooth cases as the mean over 10 realisations, with tolerance 4 SE + 0.005, the rule B1, B2 and B4
   already use.
2. Replace (6, 3.5) with a smooth point clearly above the critical disorder, (6, 4.5).
3. Re-run both smooth cases with new seeds, and keep the original failure on record.

The cost is CPU only, under a minute. If approved, it goes into the coordination record as a post-outcome deviation,
because it is decided after seeing this result.
