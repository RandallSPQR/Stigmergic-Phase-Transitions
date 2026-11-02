# Gate S8: pilot (development bank). Approved 2026-11-02 with four changes (coordination D27); no S8 model call before this commit.

**Approval with changes (owner, 2026-11-02).** These override the plan text below wherever they differ.
1. **Sealed estimates.**
   - The S8 report code outputs only the **variance components** of the two confirmatory contrasts.
   - The point estimates are written once, by `analyse_s8.py`, to a sealed file, `gates/S8/sealed/s8_sealed.json.gz.b64`:
     - live minus blind;
     - persistence;
     - its self/social decomposition;
     - intention to treat versus exposed.
   - The sealed file is encoded so that it is not human-readable at a glance, and it is never printed. The code refuses
     to overwrite it.
   - Its sha256 is recorded in the coordination record.
   - It is opened only at the owner's request, through `open_sealed.py --reason …`. That script first appends the
     opening (date, reason) to the coordination record.
   - **Pilot clusters are never reused in confirmatory work.** Their seeds are in `clusters.json`; their specs are in
     the development bank.
2. **Variance for S9.**
   - Between-cluster variance is pooled across the two evidence settings. The stated assumption: the contrast's
     between-cluster variance does not depend on the setting. Each setting is centred on its own mean, so pooled
     df = n − 2.
   - S9 sizes tiers on a **conservative quantile**: the 80th percentile of the variance's sampling distribution,
     σ²₈₀ = s² · df / χ²₀.₂₀,df, not the point estimate.
3. **Horizon rule, in equivalence form.**
   - Per (rule-(i) cluster × confirmatory model) unit: the least-squares slope of live support for the truth over
     sweeps 20–30.
   - Pooled: the mean slope, with a 95% t-interval.
   - **30 sweeps stands if the whole interval, times 10 sweeps, lies within ±0.01.** If the interval is too wide, or
     outside the band, the horizon comes to the owner as unresolved.
   - **Pre-launch note (written before any S8 call).** On the proxy kernels, the per-unit slope over sweeps 20–30 has
     SD about 0.011 per sweep, from run noise on N = 100 boards. With 24 units, the 95% half-width times 10 sweeps is
     about 0.045, against the band of 0.01. **The horizon rule is therefore expected to return "unresolved: interval
     too wide"**, which sends the horizon to the owner as the rule provides. This was reported to the owner before
     launch.
   - **Replaced by D28 (owner, recorded 2026-11-02T22:26:27Z, before any S8 result existed).** The horizon is
     decided in S9: the S8 live-fitted kernels are simulated on ≥ 1,000 boards per model, and the horizon is fixed
     where the expected live − blind contrast changes by less than ±0.025 across the final 10 sweeps. 30 sweeps stands
     if that holds; otherwise S9 proposes a horizon for approval. **In S8, the pooled live slope over sweeps 20–30 is a
     descriptive consistency check only**, not pass/fail. A gross trend in live boards that the simulation does not show
     goes to the owner. Proposed for the pre-registration: the primary outcome is the mean over a final window (sweeps
     25–30) rather than the final sweep; S9 reports the precision gained. S8 rules 1–3 are unchanged.
4. **Manipulation check.**
   - Unit: the cluster × confirmatory-model mean of its two pulsed branches' immediate response (recipients' share
     voting the pulse direction during the pulse, pulsed minus unpulsed, intention to treat).
   - Pass: the **95% lower bound of the pooled mean is > 0** (two-sided t-interval over the 24 units).


**Approval so far.** The owner approved S8 and the pulse settings (D26) on 2026-11-02. This plan sets the run sizes,
the cost cap and the pre-stated rules. The brief's S8 row reads "pulse mechanics, donor process, horizon, cost; pass:
pre-stated rules met". The donor process belongs to the prerecorded donors, which are rung 1b, so it is not in the
core pilot.

## What S8 does
1. **Runs the full protocol for the first time on live boards:**
   - initial vote by rule (i) (D25);
   - live and blind main runs from one shared initial state;
   - the pulse at t0 with two pulsed branches and a self-reset branch (D26).

   All five models, at their D23 T, in W3, development bank only.
2. **Checks pulse mechanics in live use:** exposure, and the immediate response (the manipulation check).
3. **Confirms the operational horizon.**
4. **Measures cost per cluster.**
5. **Supplies S9:** variance components of both confirmatory contrasts, live-fitted kernels, between-start shift, and
   the live-board difference between initial-vote rules (i) and (ii) in the early rounds (D25).

## Evidence settings (D17, D18)
- **S_a, the confirmatory setting {3/4, 9/10} at f = 0.5.** It currently exists only in the confirmatory bank, which
  the pilot must not touch. So before any call, `make_pilot_bank.py` derives 12 **development** specs from the 12
  non-shared development specs (6 stories × truth A/B): same story and truth, `accuracy_mix` {3/4, 9/10}, scenario ids
  `dev-<story>-<truth>-d18`. They are validated against schema v1.0, hashed, and logged as a development-bank addition
  in the coordination record.
- **S_b, the provisional setting {3/5, 3/4, 9/10} at f = 0.5:** the existing non-shared development specs.
- **No setting is changed on any live effect** (D17). S8 reports each setting's blind support, as the D18 check that
  the region is feasible in both directions. If blind support for S_a falls outside 0.50–0.85 in the pilot, the owner
  decides.

## Design (identical for every model, so models are strata over the same clusters)
- **8 clusters.** A cluster is a fresh random-regular graph (N = 100, d = 4) with its own allocation, story and truth
  (seeded `S8-cluster-<j>`; truth balanced A/B; stories rotated).
  - **6 rule-(i) clusters,** 3 per setting. Each runs:
    - a live and a blind main run of **30 sweeps** (3,000 updates each) from one shared initial state (100 calls);
    - at t0 = 5 sweeps, **two pulsed branches** (one toward A, one toward B; independent recipient sets; 8 sweeps
      each);
    - **one self-reset branch** (from one pulsed branch at restoration, direction alternating across clusters;
      5 sweeps).
    - The unpulsed branch is the main continuation (S7).
  - **2 rule-(ii) clusters,** 1 per setting: live and blind main runs of 30 sweeps from a seeded 50/50 start, with no
    pulses.
- **Server starts (D14):** 2 cold starts per model.
  - Start 1: rule-(i) clusters 1, 2 (S_a) and 4 (S_b), plus rule-(ii) S_a.
  - Start 2: clusters 3 (S_a), 5 and 6 (S_b), plus rule-(ii) S_b.
  - Every live/blind pair and every branch runs within its cluster's start. Letter mapping is balanced within each
    start (D20).
- **Within-start check:** 20 fixed probes are read at the beginning and at the end of each start. They must be
  bit-identical within the start; across starts, they give a fresh between-start shift.
- **Self-reset share:**
  - **Pilot: every saved state** (6 per model), so S9 has the decomposition's variance.
  - **Main study, proposed: one half of saved states.** A self-reset branch costs 500 calls against about 8,200 per
    rule-(i) cluster, so +3% at one half, +6% at every saved state. S9 can revise this within its cost tiers.

## Cost
Calls per model: 6 × (100 + 6,000 + 2 × 800 + 500) + 2 × 6,000 + 80 = **about 61,300**. Times come from the S7
measurements on board prompts (`gates/S7/artifacts/20261102T2054Z/` manifests: 29–123 ms per call).

| model | ms per call (S7) | readout time | with 2 cold starts, download and hash |
|---|---|---|---|
| Gemma-2-9B | 29 | about 30 min | about 40 min |
| Llama-3.1-8B (secondary) | 50 | about 51 min | about 60 min |
| Gemma-3-27B | 64 | about 65 min | about 80 min |
| Qwen3.5-9B | 83 | about 85 min | about 95 min |
| Qwen3.5-27B | 123 | about 126 min | about 140 min |

- **Two pods in parallel** (RTX PRO 6000, D12):
  - pod 1: Qwen3.5-27B and Gemma-2-9B, about 3.1 h;
  - pod 2: Gemma-3-27B, Qwen3.5-9B and Llama, about 4.0 h.
- **Expected about 7 pod-hours, about $18. Hard cap 4.5 h per pod, $22.40 in total.** The watcher terminates at the
  cap. Results upload after every cluster, so a capped pod loses at most one cluster.

## Pre-stated rules (the S8 pass)
1. **Execution:**
   - every run and branch completes;
   - failed or invalid calls are ≤ 0.5% per model (3 seeded retries, then the agent keeps its vote, counted as
     missing);
   - the within-start probes are bit-identical;
   - the harness invariants hold with no exception raised (probe state unchanged; pulse leaves real votes unchanged;
     self-reset touches recipients only).
2. **Exposure (intention to treat):** for each model, ≥ 0.85 of assigned recipients update while the pulse is on. The
   simulation expects 0.95.
3. **Manipulation check:** the immediate response (recipients' share voting the pulse direction during the pulse,
   pulsed minus unpulsed), pooled over the four confirmatory models, is > 0. Per-model values are reported, Llama's
   included.
4. **Horizon:** the operational horizon is **fixed at 30 sweeps**, because the proxy kernels settle by sweep 24 at the
   latest (`analysis/results/horizon_proxy.json`). It stands unless the pilot's live mean support, pooled over
   models, still trends over sweeps 20–30 (least-squares slope with a 95% interval excluding 0). In that case the
   owner decides.

**If any rule fails, S8 stops,** and the failure is reported.

## Reported (no pass/fail)
Point estimates of the two confirmatory contrasts are **withheld in the S8 report (recommended)**:
- live minus blind support;
- pulse persistence, including its self/social decomposition and the intention-to-treat versus exposed comparison.

The report gives only their **between-cluster variance** (the S9 input), so no design or sample-size choice can lean
on a pilot effect. The owner can ask to see them.

Reported in full:
- exposure and immediate response;
- settling of live and blind support (as sweeps to settle, not levels);
- blind support per setting (the D18 check);
- the rule (i) versus rule (ii) live difference in sweeps 1–5 (D25);
- kernels fitted to the live updates per model, for S9 and for the model-based decomposition cross-check;
- non-A/B mass, retries and missing calls;
- between-start shift;
- measured cost per cluster and per model.

## Before launch (after approval)
1. Build `make_pilot_bank.py` and the S8 runner on the S7-tested harness.
2. Validate the runner on CPU with the mock model: every branch type, the self-reset invariants, the replay of main
   continuations, and a synthetic check of the variance and blinding code.
3. Commit everything, with the payload sha256, before any S8 call.
