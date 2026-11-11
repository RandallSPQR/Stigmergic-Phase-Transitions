# S10 secondary analyses: review packet (blind; D62, D63)

**Unblinding gate (owner, D64).** No unblinding until this code is finalized by the reviewer and pushed under a tag.

**For the checker.** The code was written and tested before any confirmatory outcome was computed or seen. Please
review it on mock records and synthetic data only. Do not open any S10 run folder or record (`rec_c*.json.gz`), and
do not download from the dataset. The loader refuses real records until the owner records the unblinding decision, but
the rule is yours to keep as well.

## What to read
| file | role |
|---|---|
| `gates/S10/analysis/SECONDARY_ANALYSIS_SPEC.md` | the specification: items 1–11, the owner's choices A–H (D63), the readings the code takes, implementation notes |
| `gates/S10/analysis/secondary.py` | the code under review |
| `tests/test_secondary_analysis.py` | 44 tests: blinding guard, record-level identities on mock records, estimators on synthetic tables, negative controls |
| `gates/S10/analysis/confirmatory.py` | the frozen confirmatory analysis it builds on (`outcomes`, `replay`, `infer`, `holm`, `decide`); not under review |
| `gates/S10/s10_core.py` | record layout: `compact` rows, the init rows in `run_cluster`, pulses, self-reset |
| `osf/PREREGISTRATION.md` §5, §6, §8 | what is registered |
| `gates/S8/analyse_s8.py`, `analysis/pulse_design.py`, `analysis/t_checks.py`, `gates/S10/predictions.py` | the definitions the code must match (pilot social/self; propagation pool; G1, G2, G6; the predictions' statistic) |

## How to run
```bash
python -m pytest -q tests/test_secondary_analysis.py
```
This takes about 2 minutes on CPU. It builds 135 mock records with `s10_core.run_cluster(..., s7_core.MockKernel())`
(10 clusters × 5 models × their scheduled arms). The full suite is `python -m pytest -q tests`. The freeze check,
`python osf/verify_freeze.py <coordination clone> --addendum osf/addendum1/DECLARED_CHANGES.json`, must pass; no
design file is changed.

To try any function on mock data, build records as `tests/test_secondary_analysis.py::make` does and call
`secondary.run_all(records, frozen_clusters(), full=False)`.

## Points most worth checking
1. Record-level windows and indices in `record_outcomes`:
   - the pulse onset state (`replay(initial_votes, live[:t0·N])`);
   - the D·N split;
   - the pulsed restoration state and the self-reset state;
   - the informed/uninformed split;
   - the propagation pool (graph distance ≥ 2) and its two windows.
2. The kernel cells (`_cell`, `kernel_cells`, `battery_cells`):
   - the reference option and the contact count;
   - the content-A sign and the `letter_of_content` handling;
   - T scaling;
   - the claim that the first calls use the same prompt as the blind board.
3. The H bound (`_stats`, `compare_cells`): the group-robust SE (the owner's meaning, D64).
4. The choice-E cross-check (`self_social_crosscheck`): the start states and the full − contacts-off difference.
5. The estimators:
   - block labels (pairs of starts for pooled and paired values);
   - pooling over the four confirmatory models only;
   - Holm + TOST within subsets;
   - the wording consistency rule;
   - T1 sign flags;
   - the model check's observed statistic.
6. The unblinding guard (`require_unblinding`, `require_tagged_code`, `load_records`). Can anything unlock it but
   both of these?
   - a committed, accepted owner row titled exactly "S10 unblinding authorised" that names one tag;
   - the code running exactly at that tag, unmodified, with the tag on `origin` at the same commit (D64)?

## Readings of D63 the code takes
- **H, "each cell's standard error across contexts".** A group-robust SE across clusters, **confirmed by the owner
  as the intended meaning (D64)**. A per-call SE
  treats repeated identical prompts as independent: on a perfect mock harness it flagged 10 of 79 Gemma-2 cells and 3
  of 79 Qwen3.5-9B cells, against 0 of 79 for both with the group-robust SE. With the group-robust SE a planted
  response fault (0.3 nats toward the reference, during the pulse only) is flagged in 25 of 25 cells.
- **H, "combined".** Root-sum-of-squares inside the factor 2.
- **Implementation settings D63 did not fix:**
  - 5 clusters minimum per cell (H);
  - 2 contexts minimum per battery cell;
  - 200 simulation runs per self-reset cluster (E).
- **Item 10.** The observed value set against the predictions is the arithmetic mean over clusters, the statistic
  the predictions are of; the confirmatory θ is reported beside it.

## First review (independent, blind) and what changed
| # | finding | disposition |
|---|---|---|
| 1 | E cross-check simulated from the self-reset state (already the social part) | fixed: starts from the pulsed restoration state; the self-reset analogue is reported beside it; test: zero simulated social when contacts do not matter |
| 2 | H standard errors assumed distinct prompts per call; false mismatches on a perfect harness | fixed: group-robust SE across clusters (confirmed, D64); negative controls added |
| 3 | a model or arm absent altogether passed a full run | fixed: every scheduled (model, arm) required |
| 4 | identical duplicate records refused; the cluster in the file name unchecked | fixed |
| 5 | the frozen REML can raise `ValueError` on near-degenerate sets | fixed: reported as degenerate, not fitted |
| 6 | the model check pooled Llama | fixed: four confirmatory models only |
| 7 | recipient trajectories omitted sweep t0 | fixed |
| 8 | the guard accepted uncommitted edits, qualified titles and non-accepted rows | fixed: committed, "Accepted" table, exact title; the owner source may be qualified ("owner, …") |
| — | omissions: item 11 mass and letter balance; per-model transmission − override; pool size per branch; development-form story range; record code versions | added |
| — | the model check compared θ with predictions of the arithmetic mean | fixed: arithmetic mean, θ beside |
| — | `check_arm` allowed one start to serve two blocks | fixed |

## Second review (independent, blind, of `a9525b2`) and what changed
The reviewer worked from the bundle `stpt-secondary-review-a9525b2.tar.gz` (sha256 `629cf3b4…1923`) and supplied
`stpt_secondary_a9525b2_review.diff` (sha256 `f119a176…d01b`). The patch was applied unchanged at `42c7264`.
- Its 6 regression tests fail on `a9525b2` and pass with the patch.
- Full suite: 246 pass.
- The freeze check passes.

| # | finding | disposition |
|---|---|---|
| 1 | the guard accepted an author cell beginning with "owner" (e.g. "ownerbot") | fixed: the author token must be exactly "owner" (a qualifier may follow a comma) |
| 2 | a degenerate subset contrast aborted the whole report | fixed: reported with no fit or decision; the two-test Holm family is kept (p = 1 for the unfitted contrast) |
| 3 | recipient trajectory bands treated the two pulsed branches of a cluster as independent | fixed: branches are averaged within each cluster first |
| 4 | constant predicted means crashed the model check or gave a spurious slope | fixed: the slope is null when the predictor does not vary |

The reviewer also independently recomputed five pulse-window quantities on fresh mock branches: immediate response,
ITT persistence, end-of-window persistence, and propagation from onset and after restoration. All agreed within
1e-12. The reviewer found no further defect in choices A–H.

## Known limits (stated, not fixed)
- The within-study H comparisons pool contexts that differ in mix between conditions (different sweeps, agents and
  stories within a cell). The group-robust SE absorbs between-cluster mix differences, but not a mix difference shared
  by every cluster.
- A fault that favours one fixed content option moves reference-based cell means little. It is visible mainly as
  spread. Letter faults show in the item 11 letter balance.
- The rule (ii) early-round summary is blocked on the rule (ii) run's start only. Under the one-start-per-block
  layout this is the same partition as the pair of starts.
