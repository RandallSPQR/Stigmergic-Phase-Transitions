# Confirmatory model set after S6 (owner, 2026-11-02; coordination D24)

- **Gate outcome, not a deviation.** S6's pre-stated rule (`gates/S6/S6_PLAN.md`) is that a model must be correct
  ≥ 0.90 on the representative allocations. Llama-3.1-8B scored 0.832 and fails it, so it leaves the pooled confirmatory
  tests. D21 ("all five models stay in the confirmatory set") was decided after S3 and concerned S3. S6 was a later
  gate with its own rule.
- **Confirmatory set: the four models that passed every gate:** Gemma-2-9B, Qwen3.5-9B, Gemma-3-27B, Qwen3.5-27B.
  - Each confirmatory contrast is one pooled test across these four (fixed strata; D2).
  - S9 computes power for four strata.
  - Gemma-2-9B (0.910) and Qwen3.5-9B (0.902) passed S6 narrowly. That is on record and is read in the per-model
    estimates.
- **Llama-3.1-8B: the pre-registered secondary weakly social comparison agent** (D23 item 3).
  - It keeps all its runs (both T regimes, both initial-vote arms) and every per-model estimate.
  - It is reported beside the pooled result as the contrast for what social processing adds. Its S6 ceiling (0.83)
    and its profile (flat strength response, S5; weak contact response, D23; sticky own vote and report counting, S6)
    are stated with it.
  - It is never pooled into a confirmatory test.
- **Pre-registered analyses, updated:**
  - **27B-only sensitivity** (D21 c): unchanged, Gemma-3-27B and Qwen3.5-27B.
  - **Without Qwen3.5-9B** (D20): now three models (Gemma-2-9B, Gemma-3-27B, Qwen3.5-27B).
  - **Within-family size contrasts** (D21 a): unchanged (Gemma pair, Qwen pair).
  - **Comprehension moderator** (D21 b): descriptive, all five, Llama marked secondary.
  - **Per-model wording consistency** (D21): all five.
  - **Informed-status split** (D19): unchanged.
- **Challenge-set boards** (item 3): they stay a labelled stratum. They are read as **counting-versus-weighing**
  tests, not as aggregation success or failure, because no model solves the challenge set solo (S6: 0.41–0.84).
