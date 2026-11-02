# Gate S6: solo pooled-evidence check (development bank), 2026-11-02

**Verdict: S6 FAILS on Llama-3.1-8B.** Under the rule committed before any call, Llama-3.1-8B is below 0.90 on the
representative allocations (0.832). The other four models pass, two of them narrowly: Qwen3.5-9B 0.902 and Gemma-2-9B
0.910. Per the plan, S6 stops here, and the next step is the owner's.

**Also: the conditional challenge set is not solvable solo by any model** (0.41–0.84). Under the plan this is a
labelled stratum, not a gate failure.

- Plan: `S6_PLAN.md`. Probes: `probes/s6_probes.json`, sha256 `d1fa1cb749dedcfd…`, verified on the pod.
- Results:
  - `results/s6_summary.json`;
  - `results/s6_by_report_share.json` (a diagnostic added after the plan, labelled as such);
  - raw: `artifacts/20261102T1910Z/`.
- Run:
  - Pod `mips4qs0evwij8`, RTX PRO 6000, pipeline v1.2.0 checked by `check_pin`, weights re-hashed. One cold start per
    model, with its ID in the manifest.
  - All 2,880 repeat pairs are bit-identical.
  - About 30 min, about $1.25. The pod removed itself after its last upload. The pod kept running after Llama's
    failure was visible, to give the owner the full picture; that cost about 20 min.

## Results (W3; correct = the higher-probability letter is the truth's; 512 representative and 64 challenge-set probes per model)

| model | representative | **pass (≥ 0.90)** | own vote = truth | own vote against truth | challenge set | challenge: own vote = truth / against |
|---|---|---|---|---|---|---|
| Llama-3.1-8B | 426/512 = **0.832** | **FAIL** | 0.953 | **0.711** | 26/64 = 0.406 | 0.594 / 0.219 |
| Gemma-2-9B | 466/512 = 0.910 | pass | 0.988 | 0.832 | 44/64 = 0.688 | 0.938 / 0.438 |
| Qwen3.5-9B | 462/512 = 0.902 | pass | 0.965 | 0.840 | 50/64 = 0.781 | 0.781 / 0.781 |
| Gemma-3-27B | 494/512 = 0.965 | pass | 1.000 | 0.930 | 54/64 = 0.844 | 0.938 / 0.750 |
| Qwen3.5-27B | 508/512 = 0.992 | pass | 0.992 | 0.992 | 43/64 = 0.672 | 0.688 / 0.656 |

Non-A/B mass ≤ 0.004 for every model.

## What drives the errors
1. **The own vote.** Every model except Qwen3.5-27B loses accuracy when its current vote opposes the truth. Llama
   loses the most: 0.95 → 0.71. In every representative allocation the pooled evidence is overwhelming (log-odds toward
   the truth 20–60), so these are not close calls. An agent holding 42–51 reports still keeps its own vote.
2. **Report counting** (`s6_by_report_share.json`, diagnostic). Llama's accuracy rises with the share of reports that
   favour the truth: 0.75 at 60–70%, 0.85 at 70–80%, 0.92 at 80–90%. The pooled log-odds are large throughout, so
   Llama responds to the vote of the reports, not to their weight. That fits its flat strength response at S5 (slope
   0.10).
3. **The challenge set** (12 strong reports for the truth, 30 weak against; pooled log-odds 14.2) separates weighting
   from counting.
   - Gemma-3-27B weights best (0.84).
   - Qwen3.5-27B is at 0.67 whatever its own vote. It does not lean on its vote; it partly counts.
   - Llama mostly counts (0.41).
   - Under the plan, the challenge-set stratum is labelled **not solvable solo** for all five models.

## For the owner
S6 fails for one model. The options:

- **(a) Keep Llama-3.1-8B in the confirmatory set,** with the S6 failure on record as a post-outcome deviation.
  - Its profile is now consistent across gates: comprehension fine (S3); flat strength response (S5); weakly social
    (D23); sticky to its own vote and counting reports (S6).
  - Its per-model estimates would be read against its S6 ceiling of 0.83.
  - Against: it overrides the gate's stated pass rule.
- **(b) Move Llama-3.1-8B out of the pooled confirmatory set into a pre-registered secondary role,** as the weakly
  social comparison agent (the role D23 item 3 already gives it). It keeps all its runs and per-model estimates.
  - The confirmatory set becomes the four models that pass every gate (pooled test over four strata, D2).
  - The D20/D21 sensitivity analyses carry over: without Qwen3.5-9B means three models; the 27B pair is unchanged.
  - Against: it changes D21 item 3 ("all five stay"), and S9 power moves to four strata.
- **(c) Revise the S6 frame and re-run,** for example without the own-vote line, as a pure pooling ceiling.
  - Not recommended: that would be a post-outcome change made to rescue a model. The frame was chosen to match the
    study's call.

**Recommendation: (b).**
- The gate exists to establish that each confirmatory model can reach the truth when it holds the evidence. Llama
  cannot, reliably: from its own vote it fails 29% of the time, against overwhelming evidence.
- Keeping it as the pre-registered comparison agent preserves exactly the contrast D23 assigns it.

**Also for S8 and S9:**
- **The challenge-set stratum** is not solvable solo by any model. Any challenge-set board result should be read as
  counting versus weighting, not as aggregation success or failure.
- **Gemma-2-9B and Qwen3.5-9B pass narrowly,** and both show own-vote stickiness (0.83–0.84 against their own vote).
- **Stickiness to the own vote** is now the dominant non-evidence force in four of five models (S5, S6). That makes
  the initial-vote rule (still open) consequential, and it should be settled with this in view.
