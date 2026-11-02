# Prompt sensitivity (pre-registered secondary; D20 / A14, made per-model by D21 / A15, 2026-11-02)

Replaces the brief's earlier text, which treated wording as a random factor.

- **Primary wording.** W3 is valid for all five models, both in round 2 and on the held-out set. It is the single
  wording of the pooled confirmatory tests (D21 item 1).
- **Per-model wording sets** (held-out check, `gates/S3/results/heldout_summary.json` → `valid_by_model`; text locked
  in the coordination record's `PROTOCOL_SPEC.md`):

  | model | valid wordings |
  |---|---|
  | Llama-3.1-8B | W3, W4, W5 |
  | Gemma-2-9B | W3, W5 |
  | Qwen3.5-9B | W3, W4 |
  | Gemma-3-27B | W3, W4, W5, W6 |
  | Qwen3.5-27B | W3, W4, W5, W6 |

  A model is never run, for any estimate, in a wording that failed for it.
- **Where the variants run.** In the kernel battery, and in a seeded share of live runs (the share is set at S9). Each
  model runs only in its own valid wordings.
- **Per-model consistency check** (not a random factor).
  - For each model, both confirmatory contrasts (board effect; pulse persistence) are estimated in each of its valid
    wordings, with the same paired, start-blocked model as the primary.
  - The model's result is **consistent across wording** if all its estimates have the same sign and their intervals
    overlap. Otherwise it is reported as wording-dependent for that model.
  - The report gives the count of consistent models. No pooled across-wording test is made.
- **Sensitivity findings to report:**
  - W2's structural failure in round 2 (report moved next to the question; Gemma-2 own vote 0.683);
  - the wording-fragility pattern from the held-out check (`gates/S3/S3_REPORT.md`, "Finding: wording fragility").
