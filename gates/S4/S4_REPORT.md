# Gate S4: noise (development bank), 2026-11-02

**Verdict: S4 PASSES. The D14 tripwire is TRIGGERED (by Gemma-3-27B).**
- **Gate (within-start repeat SD ≤ 0.3 nats):** 0.0000 for every model in every start. All 14,400 repeat pairs are
  bit-identical (5 models × 6 starts × 480 pairs).
- **Between-start shift:** about 0.05 nats for four models, with no systematic start offset. Gemma-2-9B does not move
  at all.
- **Gemma-3-27B** moves about 0.24 nats near the operating point. Its tripwire statistic S_p = 0.049–0.056 is above
  0.025 in all four wordings. Under the pre-stated rule, blocking by server start becomes mandatory for every
  analysis, and the trigger is logged (coordination A16).

Plan: `S4_PLAN.md`, committed before any S4 call and amended before any call for per-model wordings (D21).
Results:
- `results/s4_summary.json`;
- `results/s4_variance_components.json` (the S9 input);
- `results/s4_shift_by_logit_band.json` and `results/s4_start_states.json` (diagnostics);
- raw: `artifacts/20261102T1535Z/` (pod `w7lelecs4ddjgx`) and `artifacts/20261102T1535Zb/` (pod `c0c6gqx5ycpsfp`).

## Run
- **Two pods,** both RTX PRO 6000 Blackwell, driver 595.91.07, vLLM 0.19.1, torch 2.10.0. They were on different
  hosts: readouts on `w7lelecs4ddjgx` took about 35% longer.
- **3 cold starts per model per pod,** so 6 starts per model and 30 in all. Every start came up.
- Pipeline v1.2.0 checked by `check_pin`; weights re-hashed to their pins. The probe set (sha256 `b94a246733bcdd20…`)
  was rendered and verified on each pod.
- **Wordings per model** (D21): Llama W3/W4/W5, Gemma-2 W3/W5, Qwen3.5-9B W3/W4, and the 27B models W3–W6. W3 has
  480 probes per start, and each other wording 480. Letter mapping is balanced 50/50 in every start.
- **Cost:** about 63 min + 75 min of pod time, about $5.70 (cap $10). Both pods removed themselves after their last
  upload.

## 1. Within-start repeat SD (the gate)

| model | starts | repeat pairs bit-identical | largest per-start SD (nats) | pass (≤ 0.3) |
|---|---|---|---|---|
| Llama-3.1-8B | 6 | 2,880 / 2,880 | 0.0000 | **yes** |
| Gemma-2-9B | 6 | 2,880 / 2,880 | 0.0000 | **yes** |
| Qwen3.5-9B | 6 | 2,880 / 2,880 | 0.0000 | **yes** |
| Gemma-3-27B | 6 | 2,880 / 2,880 | 0.0000 | **yes** |
| Qwen3.5-27B | 6 | 2,880 / 2,880 | 0.0000 | **yes** |

## 2–3. Between-start shift and the tripwire (W3; other wordings in `s4_summary.json`)

S_p = 0.25 × the RMS pairwise shift in ℓ, i.e. the vote-probability shift at p = 0.5, T = 1. S_offset is the
systematic part. The tripwire fires when either is above 0.025.

| model | probes used | σ_b (nats) | S_p | S_offset | largest probe shift (nats) | within-pod σ_b (two pods) | pod-mean difference (nats) | tripwire |
|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B | 471 at operating point | 0.051 | 0.018 | 0.0005 | 0.15 | 0.045 / 0.053 | −0.0004 | no |
| Gemma-2-9B | 184 at operating point | **0.000** | 0.000 | 0.000 | 0.00 | 0 / 0 | 0 | no |
| Qwen3.5-9B | 323 at operating point | 0.058 | 0.020 | 0.0027 | 0.19 | 0.060 / 0.057 | −0.0009 | no |
| Gemma-3-27B | all 480 (only 31 at the operating point; rule: < 40 → all) | **0.141** | **0.050** | 0.0043 | 0.75 | 0.164 / 0.135 | −0.0038 | **YES** |
| Qwen3.5-27B | 206 at operating point | 0.052 | 0.018 | 0.0021 | 0.27 | 0.052 / 0.053 | +0.0038 | no |

- **Gemma-3-27B by wording:** S_p is 0.050 (W3), 0.056 (W4), 0.051 (W5) and 0.049 (W6). Every other model is ≤ 0.021
  in every one of its wordings.
- **The Gemma-3-27B reading is not an artifact of using all probes** (`s4_shift_by_logit_band.json`).
  - Near the operating point the shift is larger, not smaller: σ_b = 0.24 nats for |ℓ| < 2.2 (31 probes), against
    0.11 for |ℓ| ≥ 10.
  - The measured change in P(A) between starts, on the probes with start-averaged P(A) in [0.35, 0.65], is 0.065–0.13
    at T = 1 (7–9 probes). The other models are at 0.017–0.020.
  - 82% of its probes move between some pair of starts.
- **The shifts are jitter, not offsets.** For every model, the start offsets are tiny (S_offset ≤ 0.0043): across
  many probes, no start sits systematically higher or lower. Pods add nothing beyond starts: pod-mean differences are
  ≤ 0.005 nats, and within-pod σ_b is close to the overall σ_b.
- **Starts fall into discrete numerical states** (`s4_start_states.json`; a state = readouts bit-identical on every
  probe):

  | model | distinct states among 6 starts |
  |---|---|
  | Gemma-2-9B | 1 (identical across starts and hosts) |
  | Gemma-3-27B | 3, recurring across both pods |
  | Llama-3.1-8B | 5 |
  | Qwen3.5-9B | 6 |
  | Qwen3.5-27B | 6 |

  This fits the S0 reading: a start picks among a finite set of kernel choices. It is not continuous drift.

**Tripwire consequence (pre-stated, D14 item 5):**
- Blocking by server start is mandatory for every StPT analysis, not only for the paired contrasts. It is logged as
  coordination A16.
- The design already ran every paired contrast within one start, so the protocol does not change. The analysis
  carries start as a blocking factor everywhere, including descriptive and per-model estimates.

**Missing Piece** (its tripwire is 0.05, measured on this shared pipeline):
- Gemma-3-27B's S_p is 0.0499 under W3, and 0.051–0.056 under the variants. It is at or just above Missing Piece's
  threshold.
- This is an owner decision (see below). StPT's probes are not Missing Piece's prompts.

## 4. Variance components for S9 (`results/s4_variance_components.json`)
For each model and wording: the start-offset variance, the probe × start variance and the between-pod difference. In
W3:
- probe × start variance: about 0.0026 nats² (Llama), 0.0033 (Qwen3.5-9B), 0.0027 (Qwen3.5-27B), 0.020 (Gemma-3-27B)
  and 0 (Gemma-2-9B);
- start-offset variance: ≤ 1e-4 nats² for every model.

S9 carries both into kernel uncertainty and the power tiers (D14 item 4). Gemma-3-27B's component is about 8× the
others'.

## 5. Presentation effects (start 1 of each pod, W3; not pass/fail; for S5 and S9)

| model | letter preference (nats, + = letter A) | option-order effect (nats, + = listed first) | SD across a context's 4 layouts (nats) | share answered A |
|---|---|---|---|---|
| Llama-3.1-8B | +0.17 | −0.18 | 0.43 | 0.55 |
| Gemma-2-9B | −0.21 | **−0.96** | 1.80 | 0.43 |
| Qwen3.5-9B | −0.05 | −0.14 | 0.47 | 0.49 |
| Gemma-3-27B | **−2.55** | **−2.19** | 4.61 | 0.45 |
| Qwen3.5-27B | +0.08 | −0.02 | 0.49 | 0.51 |

- **Both Gemma models carry large presentation effects.**
  - Gemma-3-27B leans about 2.5 nats toward the letter B, and about 2.2 nats toward the option listed second.
  - Gemma-2-9B leans about 1 nat toward the option listed second.
- The design balances the letter mapping within every start (D20) and randomises option order per call. So these
  effects cancel in the order-marginalised kernel, but they add call-level variance. The two pods agree to the
  second decimal.
- The layout SD is inflated for Gemma-3-27B by its large logits (median |ℓ| ≈ 13.5).

## 6. Format (start 1 of each pod)
- **Non-A/B mass at the vote question:**
  - Under W3, the mean is ≤ 0.004 for every model, and the largest single value is 0.023 (Qwen3.5-9B).
  - Under W4, Qwen3.5-9B's mean is 0.019 and its largest value 0.044. This matches the held-out check, where its
    variants also carried more mass than W3.
  - Every other model and wording has a mean ≤ 0.0016.
- **Readout path:** the A and B logits came from the top-20 list in every readout, except 2–3 of 2,400 per start for
  Gemma-3-27B. Those used the exact restricted fallback.

## For the owner
1. **S4 passes.** The tripwire fired, so blocking by start is now mandatory everywhere in StPT (A16). No protocol
   change is needed beyond that.
2. **Missing Piece's tripwire (0.05):** Gemma-3-27B is at 0.0499 in W3 and up to 0.056 in the variants, on StPT's
   probes.
   - Recommendation: treat it as triggered for Missing Piece too. That is conservative, and Missing Piece already
     blocks its four cells by start.
   - The alternative is for Missing Piece to measure the shift on its own prompts.
3. **Gemma-3-27B's start-to-start jitter** (about 0.24 nats near p = 0.5) is the largest variance source S4 found. It
   enters S9 as its own component. Over hundreds of calls in a run it mostly averages out, because there is no
   systematic offset, but it widens that model's intervals.
4. **Presentation effects for S5:** the Gemma models' letter and order preferences are large. S5 (responsiveness) and
   the kernel battery should keep full balance of letter mapping and option order within every start.
