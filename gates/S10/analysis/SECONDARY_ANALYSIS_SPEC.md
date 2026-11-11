# S10 secondary analyses: specification map (written blind; owner's instruction D62)

**Status:** written on 2026-11-11 while collection was finishing. No confirmatory outcome had been computed or seen by
anyone. The code (`gates/S10/analysis/secondary.py`) is developed and tested on **mock records and synthetic data
only**. Its loader refuses real records until the owner records an unblinding decision. This map is the reference the
code is checked against.

**Sources.** Registration `osf/PREREGISTRATION.md` §5, §6, §8 (cited "R§"); `analysis/PULSE_SETTINGS.md` (D26);
`analysis/SECONDARY_INFORMED_SPLIT.md` (D19); `analysis/PROMPT_SENSITIVITY.md` (D20, D21);
`analysis/SENSITIVITY_WITHOUT_QWEN9B.md` (D20); `analysis/PREREGISTERED_D21.md` (D21); `analysis/CONFIRMATORY_SET.md`
(D24); `analysis/INITIAL_VOTE_RULE.md` (D25); `analysis/DECISION_NOISE_T.md` and `analysis/T_CALIBRATION_CHECKS.md`
(D23); the kickoff brief; the S8 pilot analysis `gates/S8/analyse_s8.py` (sealed pilot definitions, R§9); the pulse
design simulation `analysis/pulse_design.py`.

**Common rules (every item).**
- Every record passes `confirmatory.verify_record` (full recomputation) before any value is taken from it. Nothing is
  excluded on an outcome (R§5 "Missing data"); a record that fails is reported as a protocol failure.
- **Blocking by server start is mandatory** (R§4, A16): every estimate uses the confirmatory model
  `c_j = θ + u_block(j) + e_j`, REML, Satterthwaite df (`confirmatory.infer`), with block labels from the recorded
  server-start IDs. Models are fixed strata; a pooled estimate averages the models within a cluster first.
- **No power target, no Holm** (R§6). Every estimate is reported with its 95% interval; the 90% interval and the
  ±0.03 TOST are also reported where the registration speaks of equivalence or conclusions.
- **Units** are the confirmatory ones: support shares (R§5).
- Llama-3.1-8B has per-model estimates and is **never pooled** (D24).

---

## 1. Per-model estimates (R§6 bullet 1; D2, D24)
For each of the five models and each contrast (board effect, sweeps 25–30; ITT persistence): the confirmatory model
on that model's 61 primary-arm values, blocked by that model's server starts. No decision rule.

## 2. Prompt sensitivity, per model (R§6; D20, D21; `PROMPT_SENSITIVITY.md`)
For each model and each variant wording drawn for it (`wording:<w>` arms, on its drawn clusters), both contrasts with
the same model. **Consistency** for a model: all its estimates (W3 and each variant) have the same sign and their 95%
intervals overlap; otherwise "wording-dependent". Report the count of consistent models.
- **Decision needed (A).** Which W3 estimate to compare: (a) the model's W3 estimate on all 61 clusters (item 1), or
  (b) its W3 estimate on the same clusters as the variant. *Proposed: (a) for the consistency rule, as the registration
  compares "estimates in each wording"; (b) reported beside it as a paired check.*
- W2's structural failure and the wording-fragility finding are reported from `gates/S3/S3_REPORT.md` (no new
  computation).

## 3. Sensitivity analyses (R§6; D20, D21, D24)
- **Without Qwen3.5-9B** (three models) and **27B models alone** (two models): `confirmatory.subset_estimate` for each
  contrast. The registration asks whether the **conclusion** (rejection, equivalence or neither) changes.
  - **Decision needed (B).** Which test gives the "conclusion": (a) the primary's procedure applied within the subset
    (Holm across the two contrasts at 0.05, plus the TOST), or (b) an unadjusted two-sided test at 0.05 plus the TOST.
    *Proposed: (a), so the comparison with the primary is like for like.*
- **Within-family size contrasts** (D21a): per cluster `d_j = effect(27B, j) − effect(9B, j)` for Gemma and for Qwen,
  with the confirmatory model.
  - **Decision needed (C).** D21a says "the difference between the two models' per-model estimates". Per-cluster
    pairing on the shared clusters is the same point estimate and a correct interval. The block label for a cluster
    is then the pair of the two models' starts, as in the primary. *Proposed: per-cluster differences.*
- **Comprehension moderator** (D21b): a table of the five models' per-model estimates beside each model's W3 held-out
  comprehension (the mean and the minimum of its three accuracies, and its fragility type;
  `gates/S3/results/heldout_summary.json`). No tests, no slopes.

## 4. Board effect by informed status (R§6; D19; `SECONDARY_INFORMED_SPLIT.md`)
The confirmatory board outcome restricted to (a) uninformed agents (transmission) and (b) informed agents (social
override): for each run, the share of the subgroup voting the truth, averaged over sweeps 25–30, live minus blind.
Membership comes from the frozen allocation. Estimated pooled over the four models and per model; the subgroup
difference (transmission minus override) is reported descriptively, per cluster with its interval.

## 5. Persistence (R§6; D26; `PULSE_SETTINGS.md`)
All from the two pulsed branches of each primary-arm record, against the unpulsed (live main) continuation, with the
same windows as the confirmatory outcome (pulse at t0 = 5 sweeps, D = 3 sweeps on, W = 5 sweeps after restoration).
- **ITT vs exposed-only:** exposed recipients are those who updated at least once while the pulse was on
  (`confirmatory.outcomes`, as the sealed pilot). Exposed-only persistence is the same outcome on them. Also reported:
  the exposure rate.
- **Immediate response:** the recipients' share voting the pulse direction averaged over the D pulse sweeps, pulsed
  minus unpulsed (`confirmatory.outcomes`).
- **End-of-window persistence:** the recipients' share at the end of the window (after the last update), pulsed minus
  unpulsed, mean of the two branches (`PULSE_SETTINGS.md`: "the share at the window's end").
- **Propagation:** the pool is every agent at graph distance ≥ 2 from every recipient of that branch (not a recipient
  and not a recipient's neighbour), as in `analysis/pulse_design.py` (`prop = ~closed`). Its share voting the pulse
  direction, pulsed minus unpulsed, mean of the two branches.
  - **Decision needed (D).** Over which steps: (a) the D + W sweeps from pulse onset, as `pulse_design.py` averaged
    it, or (b) the W sweeps after restoration, as persistence. *Proposed: (a), the registered simulation's definition;
    (b) reported beside it.*
  - "Never exposed": only recipients ever see altered displays, so the pool is never exposed by construction. Its size
    per branch is reported.
- **Self/social decomposition** (D26; on the 33 self-reset clusters): social = the recipients' share voting the pulse
  direction in the self-reset branch over the W window, minus the unpulsed share over the same window; self = the same
  pulsed branch's persistence minus social. This is the sealed pilot's definition (R§9: "self is the pulsed branch's
  persistence minus social; they therefore do not sum to the ITT mean").
  - **Cross-check** (D26: "kernel simulation with the contact terms switched off after restoration"). With kernels
    re-estimated from this study's own live updates (item 8), simulate from each self-reset cluster's state at
    restoration in two ways: with the full kernel, and with the contact terms off (every agent responds as on the blind
    board) after restoration. Report the simulated social part and compare it with the measured one, by model.
  - **Decision needed (E).** The registration does not say how the simulated recipients' "contact terms off" is
    implemented. *Proposed: recipients and everyone else use the blind-board kernel cell for their type and own vote
    after restoration; the simulated social part is the full-kernel persistence minus the contacts-off persistence.
    Reported as a model-based check only, by model, with the bootstrap spread over runs.*

## 6. Decision-noise secondary regime T = 1 (R§6; D23)
- **The T1 arm** (16 drawn clusters): both contrasts per model with the same model, and the paired difference
  T1 − primary on those clusters.
  - **Decision needed (F).** The registration lists only the three "pre-registered reports" below under this heading.
    *Proposed: report the T1 arm's per-model estimates and the paired T1 − primary differences as descriptive
    secondary results, with no conclusion attached.*
- **Calibration's generalisation:** each model's probability of following a lone 9/10 report, against Bayes 0.90,
  from this study's own informed first calls (blind, evidence-only, at the primary T). The 3/5 source is not in the
  confirmatory evidence (sources 3/4 and 9/10 only), so the 3/5 figure is reported from development
  (`analysis/results/t_checks.json`), marked as such. Also the 3/4 figure against 0.75 as the anchor's check.
- **Llama as the weakly social agent:** the contact response measured on this study's live uninformed calls: the
  change in P(vote A) from 0 to 4 displayed contacts showing A, averaged over own vote, for every model (the
  development figure was 0.20 for Llama, 0.59–0.77 for the others).
- **Gemma-3-27B at T ≈ 10.4:** checks G1 (contact gradient), G2 (saturation) and G6 (conflict), recomputed on this
  study's live calls exactly as `T_CALIBRATION_CHECKS.md` defines them. G3–G5 and G7 need the S4 probe design and are
  reported from development only.

## 7. Initial-vote rule (ii) arm (R§6; D25)
On the 12 rule-(ii) clusters, per model: the live support trajectory under rule (ii) minus rule (i) (the primary arm on
the same cluster), at every sweep 0–30; the same for the blind board (expected to agree within about 0.003 by two
updates per agent); and the board effect under rule (ii) with its paired difference from rule (i).
- **Decision needed (G).** "Especially in the early rounds": *proposed: the mean live difference over sweeps 1–5
  (before the pulse time) as the summary, with the full trajectory shown.*

## 8. Kernel consistency (R§6; the kickoff brief)
The brief: "Kernels re-estimated from live-run updates within each condition (blind, live, during and after pulses),
on configuration cells with a pre-specified minimum count, must match the battery kernel within the restart-drift
bound. A mismatch means a harness or serving problem."
- **Cells:** as the S9 kernel tables: agent type (uninformed; informed 3/4; informed 9/10) × own vote agrees with the
  reference (report's option for informed agents; own vote for uninformed) × displayed contacts showing the reference
  (0–4; none on the blind board). The cell value is the mean exact readout probability σ(ℓ_ref / T).
- **Conditions:** blind main runs; live main runs; pulsed branches while the pulse is on (the displayed contacts as
  recorded); pulsed branches after restoration.
- **Battery:** the S4 W3 live probes and the S5 W3 blind probes, at the model's T (the battery used to fit the
  development kernels in `analysis/pulse_design.py`).
- **Decision needed (H).** The minimum count and the bound were never fixed. *Proposed: minimum 30 calls per cell;
  bound = 2 × the S4 between-start standard deviation in vote probability at the cell's battery value, i.e.
  2 · p(1 − p) · √(var_start_offset + var_probe_x_start) / T from `gates/S4/results/s4_variance_components.json`.
  A cell outside the bound is listed as a mismatch; the report gives the count of cells checked and of mismatches per
  model and condition. No outcome depends on it.*

## 9. Final-sweep board effect and trajectories (R§6)
- The board effect at the final sweep (30), live minus blind (`confirmatory.outcomes` "board_final"), pooled and per
  model.
- Support trajectories: per model, the mean over clusters of live and blind support at each sweep 0–30, with 95%
  intervals across clusters; and the recipients' share voting the pulse direction, pulsed and unpulsed, at each sweep
  from t0 to t0 + D + W. Figures and tables only.

## 10. The model check (R§8)
Against the sealed predictions (`gates/S10/sealed/s10_predictions.json.gz.b64`, opened at the freeze; its sha256 is
checked first):
- whether each observed pooled estimate (both contrasts) lies inside its 90% predictive interval;
- the share of per-model estimates inside their 90% intervals (five models × two contrasts);
- per-cluster calibration: the share of (model, cluster) values inside their per-cluster 90% intervals, and the slope
  of observed on predicted per-cluster means (ordinary least squares, by model and pooled);
- the predictive intervals' widths.
A gap is reported as a model discrepancy, not a test of either hypothesis (R§8).

## 11. Execution descriptives (R§5 "Missing data")
Missing calls by condition (initial, live, blind, pulsed, self-reset) and model; non-A/B mass summaries; letter
balance per start. (These come from the integrity checks already run; repeated in the secondary report.)

---

## Decisions needed from the owner before unblinding
| | item | proposed |
|---|---|---|
| A | W3 comparator for wording consistency | the model's 61-cluster W3 estimate; same-cluster W3 beside it |
| B | "conclusion" in the subset sensitivity analyses | the primary's procedure within the subset (Holm + TOST) |
| C | size contrasts | per-cluster differences with the confirmatory model |
| D | propagation window | D + W sweeps from onset (as `pulse_design.py`); W window beside it |
| E | "contact terms off" in the cross-check | blind-board kernel cells after restoration; model-based check only |
| F | T1 arm | per-model estimates and paired T1 − primary differences, descriptive |
| G | "early rounds" in the rule (ii) comparison | mean live difference over sweeps 1–5; full trajectory shown |
| H | kernel consistency | ≥ 30 calls per cell; bound 2 × S4 between-start SD in probability |
