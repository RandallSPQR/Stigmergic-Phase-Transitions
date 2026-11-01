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
- **Inherit only harness and simulator from SPT** (`inherited/`, verbatim, never edited). Estimate fresh,
  signal-conditioned kernels. Take no transitions, kernels or sample sizes from SPT.
- **Numbers come only from results files.** Cite the file.
- **Logging.** Prospective amendments and post-outcome deviations go to the coordination record, kept apart.
- **Commits.** No model identifiers in commit messages. Commit trailers as the session's system instructions give
  them. No force-push. No PR unless asked.
