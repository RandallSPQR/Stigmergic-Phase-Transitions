# Gate S8: pilot (development bank), 2026-11-02/03

**Verdict: S8 PASSES. Pre-stated rules 1–3 are met.** Rule 4 (the horizon) was replaced before any result by D28: the
horizon is decided in S9, and the pilot slope is descriptive.

Plan: `S8_PLAN.md` (approved, D27; horizon amended, D28). Results:
- `results/s8_summary.json`: open quantities only;
- `results/s8_cpu_validation.json`;
- the sealed point estimates, `sealed/s8_sealed.json.gz.b64`, sha256
  `e6b1bc7ac35d28591428efc8dbc9836f8b9d6ff98b2cb55fcf76fa72f16a95a8`, written once and not opened;
- raw: `artifacts/20261102T2223Z/` (pod `y4p8w5jy3tlmcc`: Gemma-3-27B, Qwen3.5-9B, Llama) and `artifacts/20261102T2234Z/`
  (pod `nfr1mn4olf3pc7`: Qwen3.5-27B, Gemma-2-9B).

**Run.**
- 8 development clusters × 5 models, at D23 T and in W3.
- 2 cold server starts per model, with clusters assigned to starts as planned.
- Payload sha256 `9edec3a6050e9ec4…`, verified on both pods.
- Pod time:
  - the first pod for Qwen3.5-27B/Gemma-2-9B (`wkj6590uxvqgrt`) never started its container and was terminated after
    11 min, about $0.46;
  - its replacement ran 1 h 47 min;
  - the other pod ran 2 h 9 min.
  - Total about 4.1 pod-hours, **about $10.25** (cap $22.40). Both pods removed themselves after their last upload.

## Pre-stated rules
1. **Execution: pass.**
   - 57,600 readouts per model (288,000 in all), **0 missing or failed calls**.
   - Every run and branch completed, and every harness invariant held (no exception raised).
   - The 20 fixed probes were **bit-identical within every start** (10 of 10 starts).
   - Letter mapping is exactly 0.500 A-as-A in the main runs.
2. **Exposure (intention to treat): pass.** 0.958 of assigned recipients updated while the pulse was on, for every
   model; the simulation expected 0.95.
   - It is identical across models by design: agent order and draws are keyed by cluster and step, not by model.
   - 12 pulses per model, 10 recipients each.
3. **Manipulation check: pass.** Pooled immediate response over the four confirmatory models (24 cluster × model
   units): **0.155, 95% CI 0.135 to 0.175**, lower bound > 0. Per model:
   - Gemma-2-9B 0.117;
   - Qwen3.5-9B 0.169;
   - Gemma-3-27B 0.169;
   - Qwen3.5-27B 0.165;
   - Llama-3.1-8B (secondary) **−0.002**: the weakly social agent shows no immediate response, as D23 anticipated.

## Reported, no pass/fail
- **Live slope over sweeps 20–30 (descriptive, D28):** mean 0.0030 per sweep, 95% CI 0.0008 to 0.0052. That implies a
  change of **+0.008 to +0.052 over the 10 sweeps**.
  - **Live support for the truth was still rising at sweep 30.**
  - The interval is narrower than the pre-launch prediction (±0.045 around zero) and excludes 0.
  - Under D28, S9's simulation on the live-fitted kernels decides the horizon. If the simulation does not show this
    trend, it goes to the owner.
- **Settling** (sweeps until the mean trajectory stays within 0.02 of its final value) is not reliable at 6 clusters.
  Live does not settle by sweep 30 for any model (30 or "not settled"), and blind settles at 20–30. These are
  noise-limited; the horizon question is S9's.
- **Blind support for the truth by setting** (the D18 check; the band is 0.50–0.85):
  - S_a {3/4, 9/10}: 0.607–0.653 across the four confirmatory models;
  - S_b {3/5, 3/4, 9/10}: 0.520–0.543.
  - **S_a is inside the band.** The D18 choice stands.
- **Initial-vote rules (D25),** live support rule (i) minus rule (ii), sweeps 0–5:
  - +0.03 to +0.07 at sweep 0;
  - mixed and mostly negative at sweeps 2–5.
  - This compares 6 rule-(i) clusters with 2 rule-(ii) clusters on **different** allocations, so it is dominated by
    between-cluster differences and is **not informative at this size**. S9 simulates the paired comparison on the
    live kernels.
- **Variance components** (between clusters; pooled across settings, each centred on its own mean; D27). The
  conservative SD is the square root of the 80th percentile of the variance's sampling distribution, which S9 sizes
  tiers on.

  | | board effect (live − blind, final sweep): SD (df) | conservative SD | persistence (ITT, cluster mean of 2 branches): SD (df) | conservative SD | between-branch s² |
  |---|---|---|---|---|---|
  | Gemma-2-9B | 0.105 (4) | 0.164 | 0.048 (4) | 0.074 | 0.0073 |
  | Qwen3.5-9B | 0.043 (4) | 0.067 | 0.048 (4) | 0.075 | 0.0073 |
  | Gemma-3-27B | 0.015 (4) | 0.024 | 0.056 (4) | 0.088 | 0.0123 |
  | Qwen3.5-27B | 0.031 (4) | 0.048 | 0.024 (4) | 0.038 | 0.0052 |
  | **pooled, four confirmatory** | **0.059 (16)** | **0.071** | **0.046 (16)** | **0.055** | — |
  | Llama-3.1-8B (secondary) | 0.081 (4) | 0.126 | 0.019 (4) | 0.029 | 0.0005 |

  Per-model df = 4, so per-model variances are very uncertain. S9 should use the pooled values, or a hierarchical
  model.
- **Live-fitted kernels at T,** in the same form as the proxy (`s8_summary.json` → `live_kernel_at_T`). The S9
  simulation and the model-based decomposition cross-check use them.
- **Between-start shift,** on the 20 fixed probes, at T:
  - Gemma-3-27B 0.006;
  - Qwen3.5-27B 0.006;
  - Gemma-2-9B and Qwen3.5-9B 0 (identical across starts on these probes);
  - Llama 0.042, amplified by its T = 0.5.

  Blocking stays mandatory (A16).
- **Cost per cluster** (8,200 calls for rule (i), 6,000 for rule (ii)):
  - Gemma-2-9B about 195 s;
  - Qwen3.5-9B about 235 s;
  - Gemma-3-27B about 450 s;
  - Qwen3.5-27B about 505 s;
  - Llama about 160 s.

  That is about 31 min of GPU per rule-(i) cluster across the four confirmatory models, **about $1.30 per cluster for
  all four** at $2.49/h.

## Sealing (D27)
- The point estimates of the two confirmatory contrasts are **sealed, not reported**: live − blind, persistence, its
  self/social decomposition, and ITT versus exposed.
- The sealed file's sha256 is recorded in the coordination record's `SEALED.md`. Opening it requires the owner's
  request, through `open_sealed.py`, which logs the opening first.
- **Guard fix, recorded honestly.** The analysis's leak guard (no summary number may equal a sealed number) refused the
  first write.
  - It reported only *where* values coincided, never the values. Every hit was in the D25 rule (i) − (ii) early-support
    difference array, which includes sweep 0, before any update.
  - Shares on N = 100 boards fall on a coarse grid, so such coincidences are expected. That field, and the blind support
    per setting, both planned grid-valued reports and not contrasts, were exempted from the value check.
  - Nothing had been written, and no sealed value was seen. The key-name check and the value check on every other field
    remain.
- **The pilot's 8 clusters are never reused in confirmatory work** (A24).
