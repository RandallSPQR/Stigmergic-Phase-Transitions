# Decision noise T: options for the owner (2026-11-02)

**What T does.** Each vote is sampled from P(A) = σ(ℓ / T), where ℓ = log P(A) − log P(B) is the exact readout.
- T rescales a model's whole logit, so its **relative** weights stay native: evidence vs own vote vs contacts. Only
  its overall decisiveness changes.
- It also scales the between-start noise in vote probability (S_p ∝ 1/T).
- T is one of the brief's open decisions. It should be fixed before the S8 pilot, because it sets how far the board
  can move each model, and so power (S9).

**What S4 and S5 show** (development data only; computed by `analysis/t_options.py`, output
`analysis/results/t_options.json`). These are probabilities at T = 1.

| model | lone 3/5 / 3/4 / 9/10 report: P(follow) | no report, no contacts: P(keep own vote) | uninformed, contacts 4–0 against own vote: P(follow contacts) | 3–1 against: P(follow) |
|---|---|---|---|---|
| Llama-3.1-8B | 0.61 / 0.64 / 0.65 | 0.84 | 0.50 | 0.44 |
| Gemma-2-9B | 0.85 / 0.91 / 0.97 | 0.98 | 0.99 | 0.81 |
| Qwen3.5-9B | 0.83 / 0.88 / 0.92 | 0.90 | 0.87 | 0.68 |
| Gemma-3-27B | 1.00 / 1.00 / 1.00 | 1.00 | 1.00 | 1.00 |
| Qwen3.5-27B | 0.90 / 0.96 / 0.98 | 0.97 | 0.97 | 0.94 |

At native sampling, the models span two extremes:
- **Gemma-3-27B** is a near-deterministic agent: it keeps its vote, follows any report, and follows any contact
  majority. That is SPT's zero-temperature regime.
- **Llama-3.1-8B** barely responds to contacts (a 4–0 majority against it moves it to 0.50) or to report strength.
- The other three models lie in between.

## Options

**A. T = 1 for every model (native sampling).**
- For: no fitted parameter, and the obvious default. The result describes the models as they are.
- Against:
  - The five strata run in very different regimes. Gemma-3-27B is deterministic (zero-T dynamics, prone to freezing);
    Llama is weakly driven.
  - So the pooled estimand (D2) averages across unlike dynamics.
  - Gemma-3-27B's trajectories have almost no sampling variance.
- Between-start S_p as measured: at most 0.050 (Gemma-3-27B). The tripwire has already fired (A16).

**B. One common T ≠ 1.** Not recommended.
- The models' logit scales differ 3–20× (S5). Any single T that softens Gemma-3-27B (it needs about 10) makes Llama
  near-random (its 3/4 response falls to 0.51). Any T that sharpens Llama freezes the rest.

**C. Per-model T, anchored on evidence alone** (computed now, from blind S5 data).
- T_m = R_m(3/4) / ln 3. So a lone 3/4 report, read by that model in W3 with no contacts, moves it to P = 0.75: a
  calibrated reader of one report.
- T: Llama 0.50, Gemma-2 2.15, Qwen3.5-9B 1.78, Gemma-3-27B 10.40, Qwen3.5-27B 2.88. The same T_m for all of a
  model's wordings.

  | model | lone 3/5 / 3/4 / 9/10: P(follow) | P(keep own vote) | 4–0 against: P(follow) | 3–1 against: P(follow) | S_p |
  |---|---|---|---|---|---|
  | Llama-3.1-8B | 0.70 / 0.75 / 0.77 | 0.97 | 0.51 | 0.37 | 0.036 |
  | Gemma-2-9B | 0.69 / 0.75 / 0.83 | 0.86 | 0.89 | 0.66 | 0.000 |
  | Qwen3.5-9B | 0.71 / 0.75 / 0.79 | 0.78 | 0.75 | 0.60 | 0.011 |
  | Gemma-3-27B | 0.72 / 0.75 / 0.78 | 0.85 | 0.77 | 0.67 | 0.005 |
  | Qwen3.5-27B | 0.68 / 0.75 / 0.78 | 0.77 | 0.78 | 0.73 | 0.006 |

- For:
  - Four of five models land in comparable regimes: they keep their vote 0.77–0.86 and follow a 4–0 majority
    0.75–0.89.
  - Models then differ only in their native relative weighting of evidence, own vote and contacts, which is what the
    study asks about.
  - The anchor is the blind response to one report. It is not the board mechanism under test, so nothing is tuned on
    the live effect (the spirit of D17). It is fixed from development data before any live run.
- Against:
  - It is a counterfactual ("each model made as decisive as a calibrated reader"), not native behaviour.
  - The anchor (one 3/4 report → 0.75) is a convention.
  - Llama is sharpened (T = 0.5): its stickiness rises to 0.97, and its S_p doubles to 0.036. Blocking is mandatory
    anyway (A16).
  - Llama stays weakly social under any T, because its 4–0 logit is about 0.

**D. Per-model T anchored on the response to contacts.** Not recommended.
- It would tune the very mechanism the board effect measures.
- It is impossible for Llama: its 4–0 logit is about 0, so no T moves it.

**E. Both A and C, one primary and one secondary.** Votes are sampled from logits / T, so the two regimes produce
different trajectories, and the secondary needs its own runs. It would run on a seeded share of graphs and allocations,
with no power target.

## Recommendation
**C as the primary regime, with A as a pre-registered secondary on a seeded share (E).**
- C removes the 3–20× difference in decisiveness, which comes mostly from each model's calibration, not from its use
  of evidence or of the board.
- C anchors on a quantity outside the board mechanism, and keeps each model's native relative weights.
- A keeps the native answer on record.

If you prefer simplicity, A alone is defensible. The report would then read Gemma-3-27B's stratum as zero-temperature
dynamics.

**Either way, before S8:**
1. Log the rule and the T values in the coordination record. Under C: the formula, the values above, and the source
   files.
2. Use the same T for the initial vote, which is still an open rule.
3. Have S9 simulate power under the chosen regime, with the S4 variance components scaled by 1/T.
