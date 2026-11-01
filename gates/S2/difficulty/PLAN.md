# Difficulty grid, CPU only (owner's instruction 2026-11-01; selection rule D17). Plan committed before any run.

**Selection rule (D17, fixed before any result).**
- Difficulty is chosen by **blind-board accuracy only**, never by the size of any live-board effect. Live-board results
  are computed and reported for context and are never used to choose.
- The informed fraction stays at a middle level, because it is rung 2's dose factor.
- Challenge-set boards are a labelled stratum, never primary.
- After S3–S5, the same simulation is re-run with measured kernels. S8 then pilots 2–3 settings from the region.

**Pre-stated band and region.**
- A cell is **in the region** if, on representative boards, blind accuracy is between 0.60 and 0.85 for at least 2/3
  of the proxy kernels (54 of 81).
- Blind accuracy is the share of all 100 agents voting for the true option at the end of the horizon, averaged over
  boards.
- The same rule is applied, and reported, for mixtures with a challenge-set share.

## Grid

| axis | levels |
|---|---|
| informed fraction f | 0.3, 0.5 (middle; the approved value), 0.7 |
| source strength (accuracy set, equal weights) | W = {3/5}; WM = {3/5, 3/4}; **WMS = {3/5, 3/4, 9/10} (approved)**; MS = {3/4, 9/10} |
| challenge-set share c | 0, 0.25, 0.5 (a board mixture; computed per kernel from the two strata) |

**Representative boards** use the S2 generative model (`stpt.evidence.allocate`): round(f·100) positions hold one
report each; its accuracy is drawn from the set; it favours the truth with probability equal to that accuracy. A draw
below the pooled margin of 3.0 is replaced by the next seed and the replacement is logged.

**Challenge-set boards**, for n = round(f·100) informed agents:
- round(0.3 n) reports at the set's highest accuracy favour the truth;
- the rest, at its lowest accuracy, oppose it.

Such a board is minority-correct by construction. It is **N/A** where the set has one level (W), or where the pooled
log-odds miss the 3.0 margin; N/A cells are listed.

## Proxy kernels (81)

Logit of a vote for A:
- w_s × the signed log LR of the agent's own report (0 if uninformed);
- plus b × the sum of the contacts' displayed votes (±1);
- plus γ × the agent's own current vote (±1).

P(vote A) = σ(logit / T). On a **blind** board the social term is absent: no contacts are shown.

| parameter | levels | anchor |
|---|---|---|
| signal weight w_s | 0.5, 1, 2 | 1 = Bayesian response to the stated accuracy. SPT measured no evidence response, so the range covers under- and over-response. |
| social weight b (per contact, ±1 coding, degree 4) | 0.036, 0.386, 0.876 | 10th / 50th / 90th percentiles of b_a·4^(−α) over SPT's 16 Stage 1 endpoints, neutral framing with own position (`results/llm/fits/main/*.json`, SPT private repo) |
| own-vote weight γ | −1.440, −0.337, 2.425 | 10th / 50th / 90th percentiles of SPT's γ, same fits |
| decision noise T | 0.5, 1, 2 | StPT applies logits / T. 1 means the model's own distribution. |

The SPT values only bound a plausible range for this CPU exploration. No SPT kernel enters StPT. After S3–S5,
measured StPT kernels replace this family.

## Runs

- Boards: N = 100, random-regular d = 4 (`stpt.sim`, validated at S1). Random-sequential updates. Horizon of 20 sweeps
  (2,000 updates; the brief's operational horizon).
- Initial votes: 50/50 by a recorded seed. This is not yet the frozen initial-vote rule.
- 40 boards per (cell, kernel). Each board has its own graph, allocation, initial votes and update seeds, and the live
  and blind boards share all of them (common random numbers).
- Outputs, per (cell, stratum, kernel): blind accuracy, live accuracy, live − blind. Per cell: the median and the
  10th–90th percentile range of blind accuracy across kernels; the share of kernels in band; the region flag.
- Files: `results/grid.json`, `results/summary.json`, `REPORT.md`. CPU only; no model; no GPU.
