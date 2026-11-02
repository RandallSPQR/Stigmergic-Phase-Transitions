# Gate S6: solo pooled-evidence check (development bank). Plan committed before any S6 model call.

**Approval.** The owner approved S6 on 2026-11-02.

**Brief gate row.** One agent holds all the evidence. Pass: correct ≥ 0.90. No confirmatory selection on group
outcomes. The check asks whether a single model call can pool an allocation's evidence when it holds all of it: a
ceiling for aggregation, measured before any board runs.

## Probes (`probes/`, built by `make_probes.py`; sha256 in `probes/SHA256`)
- **Every development allocation:** 72 in all. 64 are representative: pooled log-odds toward the truth 20–60, with
  52–88% of the reports favouring it. 8 are the labelled conditional challenge set: 12 strong reports (9/10) for the
  truth and 30 weak ones (3/5) against it. Only 29% of the reports favour the truth, but pooled log-odds are 14.2.
  Every allocation is solvable under the S2 margin of 3.0.
- **The agent holds the allocation's distinct reports:** 42–51 of them. A shared report held by many positions
  appears once, as in the benchmark.
- **Prompt:** the W3 board, blind, with the actual vote question. The single report line becomes a labelled list,
  "Your private reports (n reports, one per line):", with one quoted report per line. Everything else is W3
  unchanged, including the introduction ("Each person has their own private report (or none)"). That keeps the call
  format of the study; the slight mismatch with holding many reports is noted here and accepted.
- **Balance:** own vote A and B. Four layouts (letter mapping × option order), each with its own seeded report order.
  That gives 576 probes per model, W3 only: S6 is a ceiling check, not a wording comparison.

## Run
One RTX PRO 6000 pod; pipeline v1.2.0 checked by `check_pin`; weights re-hashed; one cold server start per model, with
its ID in the manifest. The W3 block is read twice, as in S4 and S5. Hard cap 1.5 h; expected about 30 min, about
$1.30.

## Scoring and pass rule (fixed now)
- A probe is **correct** if the higher-probability letter is the truth's letter. This is the exact readout, as at S3;
  there is no sampling.
- **Pass, per model:** accuracy ≥ 0.90 on the **representative** allocations (512 probes).
  - The conditional challenge set (64 probes) is a labelled stratum, not primary (D17). It is reported against the
    same 0.90.
  - If a model falls below 0.90 there, its challenge-set stratum is labelled "not solvable solo for this model". It is
    not a gate failure.
- **If any model fails on the representative allocations, S6 stops there.** The failure is reported, and the next
  step is the owner's.

## Reported, not pass/fail
- Mean P(truth), renormalised, at T = 1.
- Accuracy by own vote (own vote = truth vs own vote against it), by story, and by allocation kind.
- On the challenge set: whether the model weights by stated accuracy (it answers with the truth) or counts reports (it
  answers with the majority of reports).
- Non-A/B mass.

Outputs: `artifacts/<run>/`, `results/s6_summary.json`, `S6_REPORT.md`.
