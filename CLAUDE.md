# Standing rules for StPT (read before any work)

- **Gates block spend.** Run them in order: S0 → S10. After each gate, stop and report to the owner.
- **No paid collection without the owner's explicit OK.** This covers GPU pods and API calls. **Nothing
  confirmatory** before S10 (freeze and OSF posting).
- **Pins.** Every run manifest starts with `stpt.manifest.header(model)`: pipeline tag + commit, SPT tag + commit,
  coordination-record commit, brief revision. `stpt.manifest.check_environment(model)` must pass before any model call.
  The pipeline is LOCKED at v1.2.0. Any change to it is a new pipeline version plus an entry in the coordination
  record's `AMENDMENTS.md`.
- **Server starts (D14).** Every run manifest records the server-start ID (`stpt.manifest.server_start_id`). Every
  paired contrast (live vs blind; pulsed vs unpulsed branch) runs within one server start, and conditions are balanced
  across starts. The start is a blocking factor in the analysis. Tripwire: a between-start shift above 0.025 in vote
  probability makes blocking mandatory everywhere, and the trigger is logged.
- **Wordings and letters (D20).** Board wording W3 is primary; only wordings that passed S3's held-out check are used
  (`stpt.prompts`, text locked in the coordination record's `PROTOCOL_SPEC.md`). The letter mapping is balanced within
  each server-start block.
- **Decision noise T (D23).** Primary: per-model T with the Bayesian anchor (a lone 3/4 report gives 0.75): Llama 0.50,
  Gemma-2 2.15, Qwen3.5-9B 1.78, Gemma-3-27B 10.40, Qwen3.5-27B 2.88 (`analysis/DECISION_NOISE_T.md`). Secondary: T = 1
  on a seeded share. Same T for the initial vote and every update.
- **Initial vote (D25).** Rule (i): first vote sampled at T from the W3 blind, evidence-only call with a seeded,
  balanced placeholder own vote, identical for live and blind. Rule (ii), a seeded 50/50 start, is a sensitivity arm.
- **Confirmatory set (D24).** Pooled confirmatory tests use the four models that passed every gate (Gemma-2-9B,
  Qwen3.5-9B, Gemma-3-27B, Qwen3.5-27B). Llama-3.1-8B failed S6 and is the secondary weakly social comparison agent:
  all runs and per-model estimates, never pooled (`analysis/CONFIRMATORY_SET.md`).
- **Inherit only harness and simulator from SPT** (`inherited/`, verbatim, never edited). Estimate fresh,
  signal-conditioned kernels. Take no transitions, kernels or sample sizes from SPT.
- **Numbers come only from results files.** Cite the file.
- **Logging.** Prospective amendments and post-outcome deviations go to the coordination record, kept apart.
- **Commits.** No model identifiers in commit messages. Commit trailers as the session's system instructions give
  them. No force-push. No PR unless asked.
