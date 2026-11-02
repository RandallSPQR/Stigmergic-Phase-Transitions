# Pre-registered analyses added by D21 (owner, 2026-11-02; prospective, no study outcome exists)

All five models stay in the confirmatory set (D2: one pooled test per contrast, models as fixed strata, W3 runs). The
analyses below use the same outcome, units, paired design and server-start blocking as the primary. None of them
changes the primary estimand, and none enters Holm.

**(a) Within-family size contrasts (secondary).**
- For each confirmatory contrast (board effect; pulse persistence): Gemma-3-27B minus Gemma-2-9B, and Qwen3.5-27B minus
  Qwen3.5-9B. Each is the difference between the two models' per-model estimates.
- Two-sided intervals, no power target.
- Caveats, stated now:
  - The Gemma pair differs in generation (Gemma 2 vs Gemma 3) as well as size.
  - The Qwen pair is one generation, both dense, thinking off (D8), so it is the cleaner size contrast.
  - The 9B models' comprehension is weaker (S3), so a size difference can partly be a comprehension difference.
    See (b).

**(b) Comprehension score as a descriptive cross-model moderator (no inference).**
- The score is each model's W3 held-out comprehension, as the mean of its three accuracies and as the minimum of them
  (`gates/S3/results/heldout_summary.json`), together with the fragility type (contacts / own vote / letter / none).
- The per-model estimates of both contrasts are tabulated and plotted against it.
- With five models, there are no tests, no fitted slopes reported as evidence, and no claims of moderation.

**(c) Sensitivity analysis on the 27B models alone.**
- Both confirmatory contrasts, re-estimated with Gemma-3-27B and Qwen3.5-27B only (fixed strata). The 27B models pass
  every comprehension cell at ≥ 0.979 in every wording.
- No power target.
- If either contrast's conclusion (rejection, equivalence or neither) differs from the five-model primary, the primary
  is reported as dependent on the smaller models.

**(d) Sensitivity analysis without Qwen3.5-9B.** Unchanged from D20: `analysis/SENSITIVITY_WITHOUT_QWEN9B.md`.

**Also recorded (D21 item 4):** the wording-fragility pattern is a reported finding (`gates/S3/S3_REPORT.md`).
