# Decision noise T: calibration checks (owner's items 2 and 4, 2026-11-02). Written before the checks are computed.

The data already exist (S4 and S5 readouts, development bank), but none has been analysed at the calibrated T. The
checks and flags below are fixed before computing them. They are diagnostics: a flag goes to the owner, and nothing
changes automatically.

**T under C (Bayesian anchor).** T_m = R_m(3/4) / ln 3. Here R_m(3/4) is model m's mean logit toward the option a lone
3/4 report names (S5, W3, blind, averaged over 6 stories, both directions, both own votes and 4 layouts). With this T,
the response to a lone 3/4 report equals its Bayesian posterior, 0.75, given a 50/50 prior. Values come from
`analysis/results/t_options.json`.

## Item 2: how the calibration generalises (every model)
- Under C, P(follow a lone 9/10 report), against its Bayesian posterior 0.90. Also P(follow a lone 3/5 report),
  against 0.60.
- Both are reported as signed misses from Bayes. T can match one point only, so the misses measure how un-Bayesian each
  model's strength response is.
- The same quantities are reported per story (6 stories), to show their spread.

## Item 4: Gemma-3-27B at T ≈ 10.4
A rescale cannot reorder any logit, so monotonicity holds at every T. These checks target what a tenfold rescale can
expose. Each is computed on the S4 W3 probes (development; 120 contexts × 4 layouts, all six starts), with every
model at its own C value of T, and Gemma-3-27B compared with the other four.

| # | check | flag if |
|---|---|---|
| G1 | **Contact gradient.** Uninformed live agents: mean P(content A) at T, by the number of contacts showing A (0–4), for each own vote | not strictly increasing in that number for either own vote (a reorder would show a pre-T problem) |
| G2 | **Saturation.** Share of probes with P(either option) > 0.99 at T | Gemma-3-27B's share exceeds the largest of the other four models' shares by more than 0.10 |
| G3 | **Pile-up at a ceiling.** Share of Gemma-3-27B probes whose start-averaged \|ℓ\| lies within 0.5 nats of its largest \|ℓ\| | > 0.10 (logits clipped or stacked at a limit, so a tenfold rescale would turn a ceiling into a false grade) |
| G4 | **Resolution.** The bf16 step at Gemma-3-27B's median \|ℓ\|, divided by T | > 0.01 nats (rescaled quantisation coarse enough to matter) |
| G5 | **Presentation effects at T.** \|letter effect\| / T and \|option-order effect\| / T (S4, start 1 of each pod) | larger than the largest of the other four models' values at their own T |
| G6 | **Conflict.** Informed live agents whose report opposes a 3–1 or 4–0 contact majority: P(follow the report) at T | outside the other four models' range by more than 0.15 |
| G7 | **Between-start noise at T.** S_p / T | > 0.025 (the tripwire is triggered anyway; reported for S9) |

Output: `analysis/results/t_checks.json` (by `analysis/t_checks.py`), summarised in `analysis/DECISION_NOISE_T.md`.
