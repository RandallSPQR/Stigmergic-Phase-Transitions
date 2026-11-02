# Gate S5: responsiveness (development stories). Plan committed before any S5 model call.

**Approval.** The owner approved S5 on 2026-11-02 (coordination D22).

**Brief gate row.** Single-agent response to each evidence template alone. It must be monotone in designed strength
and in direction; otherwise stop. S5 measures model responsiveness to evidence wording, kept separate from the
designed strength of the evidence model (S2).

## Probes (`probes/`, built by `make_probes.py`; sha256 in `probes/SHA256`)
- **Templates:** 6 development stories (bridge, crate, drawer, room, trail, well), each with its own source. Stated
  accuracy 3/5, 3/4 or 9/10 (LR 1.5, 3, 9). The report favours option A or B. That makes 36 reports, rendered by
  `stpt.evidence.render` exactly as in the banks. Each story's no-report sentence adds 6 baselines.
- **Each template alone:**
  - on the **blind board** (no contacts), with the actual vote question;
  - the agent's own current vote set to A and to B (balanced; the response averages over it);
  - four layouts: letter mapping × option order, balanced.
  - So 8 renderings per template: 336 probes per wording.
- **Wordings:** each model is read only in the wordings valid for it (D21; `gates/S4/wordings_by_model.json`). W3 is
  read first for every model.
- Development stories only. No allocation, board or confirmatory scenario is involved.

## Run
- One RTX PRO 6000 pod, pipeline v1.2.0 checked by `check_pin`, weights re-hashed to their pins.
- **One cold server start per model.** Every comparison S5 makes (between strength levels, directions and own votes)
  falls within one start, as A16 requires. The start ID is in the manifest. The W3 block is read twice, as in S4.
- The S5 driver is the S4 driver with S5's names.
- Hard cap 1.5 h (about $3.74); expected about 35 min, about $1.50.

## Measure
- For each probe: ℓ_fav = log P(the content the report favours) − log P(the other content), in content space, from
  the exact A/B readout.
- For the baselines: ℓ toward the content shown as option A in the scenario.
- **Template response** r(story, accuracy, direction) = the mean of ℓ_fav over the template's 8 renderings.
- **Pooled response:**
  - R(accuracy, direction) = the mean over the 6 stories;
  - R(accuracy) = the mean over stories and both directions.

## Pass rule (fixed now), per model, in W3
1. **Direction:** R(accuracy, direction) > 0 in all 6 cells (3 accuracies × 2 directions). Every report moves the
   vote toward the option it names, on average over stories, own votes and layouts.
2. **Strength:** R(3/5) < R(3/4) < R(9/10), strictly. A stronger stated source moves the vote further.

If W3 fails either test for any model, **S5 stops there**, with the failure reported, and the next step is the
owner's (brief: "else stop"). For each model, the same two tests are applied to every other wording valid for it. A
variant that fails is dropped for that model, with the reason recorded; W3 is unaffected.

## Reported, not pass/fail
- **Per-story monotonicity and direction:**
  - the number of the 12 story × direction cells that are strictly monotone;
  - the number of the 36 templates with r > 0.
- **Responsiveness vs designed strength:**
  - the least-squares slope and intercept of R(accuracy) on the designed log LR (0.405, 1.099, 2.197);
  - the same per story.
  - Reference: a Bayesian agent with a 50/50 prior that ignores its own vote has slope 1 and intercept 0 at T = 1.
    Values far from that are descriptive. They are what the fresh kernels will carry, and no pass/fail attaches.
- **Own-vote stickiness:**
  - half the difference in ℓ_fav between own vote = the favoured option and own vote = the other option;
  - for the baselines, ℓ toward the agent's own vote.
- **Baselines:** ℓ toward content A per story (a story-level content preference); P(own vote) with no report.
- **Saturation:** the share of renderings with P(favoured) > 0.99.
- **Format:** non-A/B mass.

Outputs: `artifacts/<run>/`, `results/s5_summary.json`, `S5_REPORT.md`.
