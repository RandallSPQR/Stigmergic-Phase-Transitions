# Prompt sensitivity (pre-registered secondary; redefined 2026-11-02, coordination D20 / A14)

Replaces the brief's earlier text, which treated wording as a random factor.

- **Which wordings.** A wording is used only if all five models pass all three comprehension types at ≥ 0.90 (gate
  S3, including the held-out check of `gates/S3/HELDOUT_PLAN.md`). W3 is the primary wording. The W3 variants that pass
  the held-out check (same structure and content, different phrasing and label text; linted by
  `stpt.prompts.lint_same_content`) form the rest of the set. Their exact text is locked in the coordination record's
  `PROTOCOL_SPEC.md`.
- **Where they run.** The kernel battery, and a seeded share of live runs (the share is set at S9). The confirmatory
  tests use W3 runs.
- **Not a random factor.** With few valid wordings, a between-wording variance cannot be estimated usefully.
  - The two confirmatory contrasts (board effect; pulse persistence) are estimated **per valid wording**, with the
    same paired, start-blocked model as the primary.
  - **Consistency criterion:** the per-wording estimates have the same sign, and their intervals overlap.
  - A result that holds for one wording only is reported as wording-dependent. If W3 is the only valid wording, the
    report says so, and no consistency claim is made.
- **Sensitivity finding to report:** W2's structural failure at S3. W2 kept the content and moved the private report
  to the end, next to the question. Gemma-2's own-vote accuracy then fell to 0.683: it answered its own-vote question
  from the report (`gates/S3/S3_REPORT.md`, round 2). Comprehension depends on layout, not only on phrasing.
