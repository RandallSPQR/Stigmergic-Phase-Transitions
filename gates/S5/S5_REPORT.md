# Gate S5: responsiveness (development stories), 2026-11-02

**Verdict: S5 PASSES.** Under the rule committed before any call, every model passes both tests in W3:
- **direction:** every pooled cell is positive;
- **strength:** the response is strictly increasing over 3/5 < 3/4 < 9/10.

Every variant wording passes too, so no wording is dropped for any model.

The models differ widely in how much the evidence moves them and how strongly they hold their own vote. That is
descriptive, and it is what the fresh kernels will carry.

- Plan: `S5_PLAN.md`. Probes: `probes/s5_probes.json`, sha256 `f110b1684cb9064f…`, verified on the pod.
- Results:
  - `results/s5_summary.json`;
  - `results/s5_conditional_on_own_vote.json` (a derived diagnostic);
  - raw: `artifacts/20261102T1807Z/`.
- Run:
  - Pod `o5w27qdduhy468`, RTX PRO 6000 Blackwell, pipeline v1.2.0 checked by `check_pin`, weights re-hashed to their
    pins.
  - One cold server start per model, with its ID in the manifest. Every model read in its D21 wordings.
  - All 1,680 W3 repeat pairs are bit-identical.
  - About 34 min, about $1.40. The pod removed itself after its last upload.

## Pass/fail (W3)

R is the mean logit toward the option the report names. It averages over 6 stories, both directions, both own votes
and 4 layouts.

| model | R(3/5) | R(3/4) | R(9/10) | smallest direction cell | direction | strength | per-story monotone cells | templates with r > 0 |
|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B | 0.43 | 0.55 | 0.61 | 0.38 | pass | pass | 10/12 | 35/36 |
| Gemma-2-9B | 1.71 | 2.37 | 3.45 | 1.62 | pass | pass | 12/12 | 36/36 |
| Qwen3.5-9B | 1.61 | 1.96 | 2.38 | 1.54 | pass | pass | 12/12 | 36/36 |
| Gemma-3-27B | 9.95 | 11.43 | 13.15 | 9.41 | pass | pass | 12/12 | 36/36 |
| Qwen3.5-27B | 2.17 | 3.16 | 3.70 | 2.14 | pass | pass | 12/12 | 36/36 |

**Variants:** all pass for every model (`s5_summary.json`).
- Llama: W4 and W5.
- Gemma-2: W5.
- Qwen3.5-9B: W4.
- 27B models: W4–W6.

Per-story monotone counts are 9–12 of 12. Llama's weakest is W5 with 9/12; Gemma-3's is W6 with 10/12.

## Descriptive: responsiveness, stickiness, saturation (W3; not pass/fail)

| model | slope on designed log LR (Bayes = 1) | intercept (nats) | own-vote stickiness (nats) | no report: P(keep own vote), T = 1 | own vote against a 3/5 / 3/4 / 9/10 report: P(follow report), T = 1 | share with P(favoured) > 0.99 |
|---|---|---|---|---|---|---|
| Llama-3.1-8B | **0.10** | 0.41 | 0.55 | 0.81 | **0.46 / 0.51 / 0.52** | 0.00 |
| Gemma-2-9B | 0.97 | 1.31 | 0.50 | 0.94 | 0.64 / 0.82 / 0.92 | 0.16 |
| Qwen3.5-9B | 0.43 | 1.45 | 0.96 | 0.89 | 0.65 / 0.72 / 0.78 | 0.01 |
| Gemma-3-27B | 1.77 | **9.33** | 3.61 | **1.00** (17.9 nats) | 0.79 / 0.92 / 0.99 | **0.89** |
| Qwen3.5-27B | 0.82 | 2.00 | 1.92 | 0.97 | 0.51 / 0.77 / 0.87 | 0.37 |

**What this says (descriptive):**
1. **Llama-3.1-8B barely distinguishes strength.** A 9/10 source moves it about as much as a 3/5 source: slope 0.10.
   When its own vote opposes the report, it follows the report only about half the time at any strength. It passes
   because the ordering and direction hold, but its evidence response is weak.
2. **Gemma-2-9B tracks designed strength almost at the Bayesian rate** (slope 0.97), with an added constant of 1.3
   nats.
3. **Gemma-3-27B is extremely confident.** Even a 3/5 report gives about 10 nats. With no report, it never leaves its
   own vote (17.9 nats). At T = 1, 89% of its informed readouts exceed P = 0.99, so its trajectories would be almost
   deterministic.
4. **Every model holds its own vote with no report** (P = 0.81–1.00 at T = 1). For uninformed agents, the contacts
   have to overcome that, so status-quo stickiness will shape the board dynamics as much as evidence does.
5. **Story-level content preferences with no report** are small, |ℓ| ≤ 0.7 nats (`baseline_logit_toward_content_A`).
   Non-A/B mass is ≤ 0.009 in W3.

## For the owner
1. **S5 passes.** The next gate is S6, the solo pooled-evidence check (development bank; correct ≥ 0.90; GPU).
2. **Decision noise T,** still open ("Decisions still required"), now has data behind it. Gemma-3-27B's responses are
   3–20 times the others' in nats, so a single T across models would leave it near-deterministic at T = 1, or the others
   near-random at large T.
   - The brief samples votes at T from logits/T; whether T is common or per-model is undecided.
   - S5 and S4 give the inputs: the logit scale per model, and stickiness.
   - This choice should be settled before the S8 pilot. It affects power (S9) and how much the board can move anyone.
3. **Llama-3.1-8B's flat strength response** is not a failure under the rule. But in the live board, its informed
   agents will differ little from its uninformed ones, which bears on the D19 informed-status split for that model.
   Its comprehension was fine (S3), so this is weak use of the stated accuracy, not misreading.
