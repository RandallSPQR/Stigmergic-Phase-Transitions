# Sensitivity analysis without Qwen3.5-9B (pre-registered; coordination D20 / A14, 2026-11-02)

- **Why.** At S3, Qwen3.5-9B passed under W3 at exactly the threshold: own-report accuracy 0.900, 216 of 240
  (`gates/S3/results/round2_summary.json`). It shows context interference. Its own-report accuracy is 0.82 when its own
  vote disagrees with its report, against 0.99 when they agree. Its kernel may mix report-reading errors into evidence
  response.
- **What.** Both confirmatory contrasts are re-estimated with Qwen3.5-9B excluded: the board effect (live minus blind),
  and pulse persistence.
  - Four models as fixed strata; the same paired, server-start-blocked model, outcome and units as the primary.
  - Reported beside the primary. No power target. Holm is not applied to it, because it is a sensitivity analysis.
- **Reading.** If either contrast's conclusion (rejection, equivalence or neither) changes when Qwen3.5-9B is excluded,
  the primary result is reported as dependent on that model. The primary estimand (D2: one pooled test across the five
  models) is unchanged.
