# S10 secondary analyses: specification map (written blind; owner's instruction D62)

**Status:** written on 2026-11-11 while collection was finishing. No confirmatory outcome had been computed or seen by
anyone. The owner decided choices A–H blind, before unblinding (D63; A–G as proposed, F with a sign statement added, H
amended); this map states them as decided. The code (`gates/S10/analysis/secondary.py`) is developed and tested on
**mock records and synthetic data only** (`tests/test_secondary_analysis.py`). Its loader refuses real records unless
the coordination record (a git clone) holds, **committed and in its "Accepted" table**, an owner decision whose bold
title is exactly **"S10 unblinding authorised"**. A row that only mentions unblinding (such as D62 or D63), a
qualified title, a proposed row or an uncommitted edit does not count. The output records the decision row and the
record's commit. This map is the reference the code is checked against.

**Review.** An independent blind review (mock and synthetic data only) found 8 defects and 5 omissions in the first
version; all are fixed here. The corrections that touch a D63 choice are:
- E's starting state;
- H's standard error;
- the model check's observed statistic and its pooling.

They are marked "(review)" below.

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
- **Choice A (D63).** The consistency rule uses the model's 61-cluster W3 estimate (item 1). Reported prominently
  beside it, for each variant, the **same-cluster paired comparison**: the per-cluster difference variant − W3 on the
  variant's clusters (confirmatory model; block label = the pair of starts). Also the W3 estimate on those clusters and
  the consistency rule applied to it.
- W2's structural failure and the wording-fragility finding are reported from `gates/S3/S3_REPORT.md` (no new
  computation).

## 3. Sensitivity analyses (R§6; D20, D21, D24)
- **Without Qwen3.5-9B** (three models) and **27B models alone** (two models): `confirmatory.subset_estimate` for each
  contrast. The registration asks whether the **conclusion** (rejection, equivalence or neither) changes.
  - **Choice B (D63).** The primary's procedure within each subset: Holm across the two contrasts at 0.05, plus the
    TOST, through `confirmatory.decide`. Each subset's decision is set beside the primary's.
- **Within-family size contrasts** (D21a): per cluster `d_j = effect(27B, j) − effect(9B, j)` for Gemma and for Qwen,
  with the confirmatory model.
  - **Choice C (D63).** Per-cluster differences with the confirmatory model. D21a says "the difference between the two
    models' per-model estimates"; pairing on the shared clusters gives the same point estimate and a correct interval.
    The block label for a cluster is the pair of the two models' starts, as in the primary.
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
  - **Choice D (D63).** Over the D + W sweeps from pulse onset, as `pulse_design.py` averaged it, with the W window
    after restoration reported beside it.
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
  - **Choice E (D63).** After restoration every agent (recipients and the rest) uses the blind-board kernel cell for
    its type and own vote.
    - Both simulations start from the **pulsed branch's state at restoration, with no reset** (review: the first
      version started from the self-reset state, which already isolates the social part).
    - Full-kernel persistence = pulsed − unpulsed with contacts. Contacts-off persistence ("self") = the same with
      contacts off. Each is taken against the unpulsed state at the same step, on the same random stream.
    - Simulated social = full − self, compared with the measured social part, by model and per cluster.
    - Beside it: the kernel analogue of the self-reset branch (recipients reset, full kernel, minus unpulsed).
    - Kernels: this study's live and blind main-run cells (item 8). A cell never seen takes the mean of its type and
      own-vote cells.
    - 200 simulation runs per self-reset cluster (an implementation setting, not fixed by D63).
    - It is a model-based check only.

## 6. Decision-noise secondary regime T = 1 (R§6; D23)
- **The T1 arm** (16 drawn clusters): both contrasts per model with the same model, and the paired difference
  T1 − primary on those clusters.
  - **Choice F (D63).** The T1 arm's per-model estimates and the paired T1 − primary differences are descriptive
    secondary results, with no conclusion attached. **For each T = 1 estimate, whether its sign matches the primary's**:
    the model's 61-cluster primary estimate (the reference, as in A), with the same-cluster primary beside it.
- **Calibration's generalisation:** each model's probability of following a lone 9/10 report, against Bayes 0.90,
  from this study's own informed first calls (blind, evidence-only, at the primary T). The 3/5 source is not in the
  confirmatory evidence (sources 3/4 and 9/10 only), so the 3/5 figure is reported from development
  (`analysis/results/t_checks.json`), marked as such. Also the 3/4 figure against 0.75 as the anchor's check. Reported
  two ways: the mean probability over calls, and σ(mean reference logit / T), development's form (`t_checks.py`),
  with the range over stories.
- **Llama as the weakly social agent:** the contact response measured on this study's live uninformed calls: the
  change in P(vote A) from 0 to 4 displayed contacts showing A, averaged over own vote, for every model (the
  development figure was 0.20 for Llama, 0.59–0.77 for the others).
- **Gemma-3-27B at T ≈ 10.4:** checks G1 (contact gradient), G2 (saturation) and G6 (conflict), recomputed on this
  study's primary-arm main-run calls as `analysis/t_checks.py` computed them on the S4 probes:
  - G1 on uninformed live calls; flagged unless strictly increasing for both own votes.
  - G2 on every live and blind call, as the share with |ℓ|/T > ln 99.
  - G6 on informed live calls whose report is shown by at most one of the four contacts.
  - Gemma-3-27B is compared with the other four models, Llama included.
  - G3–G5 and G7 need the S4 probe design and are reported from development only.

## 7. Initial-vote rule (ii) arm (R§6; D25)
On the 12 rule-(ii) clusters, per model: the live support trajectory under rule (ii) minus rule (i) (the primary arm on
the same cluster), at every sweep 0–30; the same for the blind board (expected to agree within about 0.003 by two
updates per agent); and the board effect under rule (ii) with its paired difference from rule (i).
- **Choice G (D63).** "Especially in the early rounds": the mean live difference over sweeps 1–5 (before the pulse
  time) as the summary, estimated with the confirmatory model, with the full trajectory shown.

## 8. Kernel consistency (R§6; the kickoff brief; choice H as amended, D63)
The brief: "Kernels re-estimated from live-run updates within each condition (blind, live, during and after pulses),
on configuration cells with a pre-specified minimum count, must match the battery kernel within the restart-drift
bound. A mismatch means a harness or serving problem."
- **Cells:** as the S9 kernel tables: agent type (uninformed; informed 3/4; informed 9/10) × own vote agrees with the
  reference (report's option for informed agents; own vote for uninformed) × displayed contacts showing the reference
  (0–4; none on the blind board). The cell value is the mean exact readout probability σ(ℓ_ref / T) over its calls.
- **Conditions** (primary arm, the same confirmatory stories):
  - blind main runs;
  - live main runs;
  - pulsed branches while the pulse is on (the displayed contacts as recorded);
  - pulsed branches after restoration;
  - the informed agents' first calls, which use the W3 blind-board prompt with the placeholder as own vote
    (`s10_core.initial_state`). These give the blind board a comparison within the study.
- **Main check, within this study (D63).** The conditions' kernels are compared with each other on the cells they
  share:
  - blind vs first calls (informed cells);
  - live vs pulse-on;
  - live vs post-restoration;
  - pulse-on vs post-restoration.

  A cell is checked when it has at least **30 calls on each side**. Bound:
  **2 · √(s_drift² + SE_a² + SE_b²)**, where:
  - s_drift is the S4 between-start SD in probability, p(1 − p) · √(var_start_offset + var_probe_x_start) / T, from
    `gates/S4/results/s4_variance_components.json`, at p = the mean of the two cell values;
  - SE is each cell's standard error across contexts. **Reading (review): group-robust (cluster-robust) across
    clusters**, SE² = G/(G − 1) · Σ_g (n_g (ȳ_g − ȳ))² / n², with the cell value still the mean over its calls.
    - Why not a per-call SE: identical prompts recur. The mock had 36,000 blind calls and 400 distinct prompts. Each
      first call repeats a blind-board prompt, and pulsed-branch calls mostly repeat the live run's call at the same
      step. A per-call SE flagged mismatches on a perfect mock harness: Gemma-2 10 of 79 cells, Qwen3.5-9B 3 of 79.
    - With the group-robust SE: 0 of 79 for both; Llama 2 of 67, about what a 2-SD bound gives by chance.
    - A cell needs calls from at least 5 clusters on each side (an implementation setting).

  A cell outside the bound is a mismatch. The report gives the cells checked and the mismatches per model and
  comparison, with every cell's values.
- **Secondary: the battery comparison (D63).** Each condition is compared with the development battery at the model's
  T, with the same bound formula: the drift SD combined with the S10 cell's SE and the battery cell's SE.
  - Live conditions are compared with the S4 W3 live probes. These are start-averaged over all six starts, the
    battery used to fit the development kernels in `analysis/pulse_design.py`.
  - Blind conditions are compared with the S5 W3 blind probes (one start).
  - A battery context's value is the mean over its layouts. A battery cell needs at least 2 contexts for an SE (an
    implementation setting).
  - A mismatch here reads **"harness or story dependence"**, since the battery used development stories.
- **Readings the code takes of D63 (for the check):**
  - "Combined" is taken as root-sum-of-squares inside the factor 2.
  - "Across contexts" is taken as group-robust across clusters on the S10 side, and across contexts (one value each)
    on the battery side.
  - Missing calls are left out.
  - No outcome depends on this check.
- **What it can and cannot see** (mock negative controls, `tests/test_secondary_analysis.py`):
  - A response fault confined to one condition is flagged in every checked cell: 0.3 nats toward the reference
    while the pulse is on gave 25 of 25 cells for both models tested; clean data gave 0.
  - A fault that favours one fixed content option (A) mostly widens the cells' spread and moves their means little,
    because cells are defined relative to the reference. A 0.5-nat shift was flagged in 1–2 of 25 cells; a 1-nat
    shift in 3–4.
  - Letter bias is balanced out of the cells. It is reported by item 11's letter balance per start instead.

## 9. Final-sweep board effect and trajectories (R§6)
- The board effect at the final sweep (30), live minus blind (`confirmatory.outcomes` "board_final"), pooled and per
  model.
- Support trajectories: per model, the mean over clusters of live and blind support at each sweep 0–30, with 95%
  intervals across clusters; and the recipients' share voting the pulse direction, pulsed and unpulsed, at each sweep
  from t0 (the onset share, common to both) to t0 + D + W. Figures and tables only.

## 10. The model check (R§8)
Against the sealed predictions (`gates/S10/sealed/s10_predictions.json.gz.b64`, opened at the freeze; its sha256 is
checked first):
- whether each observed pooled estimate (both contrasts) lies inside its 90% predictive interval;
- the share of per-model estimates inside their 90% intervals (five models × two contrasts);
- per-cluster calibration: the share of (model, cluster) values inside their per-cluster 90% intervals, and the slope
  of observed on predicted per-cluster means (ordinary least squares), by model and pooled over the **four
  confirmatory models only** (review: Llama is never pooled, D24);
- the predictive intervals' widths.

**Observed statistic (review).** The sealed predictions are of each simulated study's arithmetic mean over the 61
clusters (`gates/S10/predictions.py`): per model, the mean over clusters; pooled, the mean of the four confirmatory
models' means. The observed value compared with them is the same arithmetic mean. The confirmatory model's θ
(REML, block-weighted) is reported beside it.
A gap is reported as a model discrepancy, not a test of either hypothesis (R§8).

## 11. Execution descriptives (R§5 "Missing data")
Missing calls by condition (initial, live, blind, pulsed, self-reset) and model; non-A/B mass (mean, 99th percentile,
max) by condition; letter balance per server start (share of main-run calls showing content A as letter A); and the
code that produced the records (commit, payload, cluster manifest, pins, from each record's manifest), by model.
(The integrity checks already cover these; they are repeated in the secondary report.)

---

## Decisions (owner, D63, made blind before unblinding)
| | item | decided |
|---|---|---|
| A | W3 comparator for wording consistency | the model's 61-cluster W3 estimate; the same-cluster paired comparison reported prominently beside it |
| B | "conclusion" in the subset sensitivity analyses | the primary's procedure within each subset (Holm + TOST) |
| C | size contrasts | per-cluster differences with the confirmatory model |
| D | propagation window | D + W sweeps from onset (as `pulse_design.py`); W window beside it |
| E | "contact terms off" in the cross-check | blind-board kernel cells for all agents after restoration; model-based check only |
| F | T1 arm | per-model estimates and paired T1 − primary differences, descriptive; for each T = 1 estimate, whether its sign matches the primary's |
| G | "early rounds" in the rule (ii) comparison | mean live difference over sweeps 1–5; full trajectory shown |
| H | kernel consistency | amended: main check within this study across conditions (bound 2 × S4 between-start SD in probability combined with each cell's SE; ≥ 30 calls per cell); secondary the battery comparison (drift SD and both sides' SEs), a mismatch read as harness or story dependence |

## Implementation notes (not design choices)
- An estimate needs at least 3 clusters. With fewer, it is reported as absent.
- Some sets have no variation, or so little that the frozen REML fit fails (for example one nonzero value in
  singleton blocks). Such a set is reported with no interval, marked "degenerate", and is not fitted.
- Every record's identity is checked against the protocol before use: model, cluster, arm, T, wording, initial
  wording, rule, run key, parameters, not a mock, and the file name.
- Each scheduled block must run in one server start, and each start serves one block.
- A full run requires every scheduled (model, arm) pair and exactly its scheduled clusters. A model whose secondary
  folder is left out is refused.
- An identical copy of a record in two listed folders is accepted; differing copies are refused.
- Usage, and the tests, are in the module's docstring and `tests/test_secondary_analysis.py`.
