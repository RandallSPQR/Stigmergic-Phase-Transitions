# StPT pre-registration, addendum 1: execution review fixes and a clarification

**Registration:** OSF https://osf.io/sm8xr (DOI 10.17605/OSF.IO/SM8XR); registered text = `osf/PREREGISTRATION.md` at
commit `cb10726e3d359d8094fbd083f336453d6af9280d` (tag `stpt-prereg-v1-final`; Zenodo 10.5281/zenodo.23924793).
**This addendum:** filed after registration and **before any confirmatory data exist** (no confirmatory model call has
been made). Code commit with the fixes: `1031a83559f70a9ba82739cb7ea10c791d515f3d`. Tag: `stpt-run-v1` (on the commit that adds this text).
Coordination record: D48, D49, A36.

## What happened
An independent execution review of the registered code (commit `cb10726`) checked whether the code does what the
registration says. It reported seven findings, all accepted by the owner. Six are code-to-registration conformance
defects (#2–#7): the code is changed to do what the registered text already says. One (#1) is an ambiguity in the
registered text, resolved below as a clarification. **No hypothesis, outcome, estimand, analysis model, test, bound,
sample size, cluster, story, wording or parameter changes.** The registered pre-registration text is unchanged (byte
for byte). No confirmatory run starts until all seven fixes are verified and this addendum is posted.

Each defect is demonstrated on the registered code and shown absent on the fixed code by
`osf/addendum1/before_after.py` (result `osf/addendum1/before_after.json`).

## Findings, fixes and evidence

| # | registered requirement (pre-registration section) | defect in the registered code | fix | evidence on the registered code → fixed code |
|---|---|---|---|---|
| 1 | Initial vote, rule (i) (§4) | see *Clarification* below | `gates/S10/s10_core.py` `initial_state` | 100 → 50 initial calls per cluster (only the 50 informed agents); uninformed first vote = placeholder |
| 2 | 30 sweeps = 3,000 updates per run; two pulsed branches, toward A and toward B; r = 10 recipients (§4, §5) | the extraction accepted truncated runs, one pulsed branch, two branches in the same direction and duplicate recipients | `confirmatory.py` `check_record`: exactly 3,000 updates with consecutive steps; exactly two branches with opposite directions; 10 distinct recipients in 0–99; exactly (D + W) × N branch rows; every row well formed and finite | accepted → refused: runs truncated to 2,900; one branch; same direction twice; duplicate recipient |
| 3 | 61 frozen clusters; blocking by the recorded server start (§3, §4, §5); confirmatory = primary arm | `primary()` took the cluster list and block labels from the caller and did not check the arm or NaN | `confirmatory.py` `primary`/`check_table`: universe from the frozen, hashed 61-cluster manifest only; block label of a cluster = the server-start IDs recorded in its run records (one start per run, all branches); every entry must be the primary arm (primary T, W3, rule (i), frozen parameters, the cluster's run key), not a mock run; NaN or infinite values refused at every input; caller metadata no longer accepted | accepted → refused: a T = 1 entry; a NaN outcome; caller metadata that drops a cluster; caller block labels (all clusters in one block turned df 60 into df 1) |
| 4 | server starts recorded; live/blind and pulsed/unpulsed within one start; blocks of 4; spend flagged at 80% (§4, §7, D31) | no confirmatory collection driver existed | new `gates/S10/run/driver.py` (+ `pod.py`, `gpu/s10_driver.sh`): only the 61 frozen clusters; per-model T and the pipeline pin enforced; one server start per block; start ID recorded per branch; a partial arm from an earlier start is restarted, never mixed; checkpoint after every branch; resume without duplication; per-stage caps (proposed: `gates/S10/run/caps_proposed.json`, $77 core / $144 all arms) with a stop at the 80% flag until the owner acknowledges | CPU validation, mock model (`gates/S10/results/driver_cpu_validation.json`): D1–D5 pass, including a cap kill mid-cluster with resume and a SIGKILL of the driver with re-attach to the same start |
| 5 | placeholder balanced within evidence type, **within server-start blocks** and across graph positions (§4) | balanced within each cluster only; up to 3 more of one letter than the other in a block × evidence group | `s10_core.py` `block_placeholders`: within every start block (4 clusters) × evidence group, \|A − B\| ≤ 1, and ≤ 1 within every cluster × group | max block imbalance 3 → 1 |
| 6 | self-reset on 33 of 61 saved states; T = 1 on 16 clusters; rule (ii) on 12; variant wordings on a seeded 20% (§4) | the runner ignored the drawn flags (`c["arms"]`); self-reset ran by default | `s10_core.py` `arm_spec`/`arms_for`/`run_cluster`: only drawn arms run (others refused); self-reset only when drawn and only in the primary arm; default off; T is never a free argument | self-reset when not drawn: yes → no; T = 1 arm when not drawn: runs → refused |
| 7 | rule (i) uses the **W3** blind, evidence-only call (§4) | in a variant-wording arm the initial call used the variant wording | `s10_core.py` `run_cluster`: the initial call always uses W3; a variant wording applies to the updates only | initial prompts in a variant arm equal to W3's: no → yes |

## Clarification (#1): the initial vote of uninformed agents
The registered text (§4, rule (i)) says both "each agent's first vote is sampled at T from its W3 blind, evidence-only
call" and "Uninformed agents' first votes follow the balanced placeholder". The registered code read the first
sentence literally and sampled every agent, including uninformed ones, from a call. **The protocol is:** an
uninformed agent's first vote **is** its balanced placeholder, with no model call; an informed agent's first vote is
sampled at T from its W3 blind, evidence-only call carrying the placeholder own vote. The init calls' letter mappings
are balanced in pairs over the informed agents (D20). This is the reading under which "follow the balanced
placeholder" holds exactly; it removes model calls that carried no evidence.

**Effect on the registered predictions (§8).** The sealed predictions were simulated with uninformed first votes
following the placeholder with each model's estimated probability (0.77–0.91, `gates/S9/results/kernels_s8.json`,
`init`), not with probability 1. Because placeholders are balanced, the expected initial support among uninformed
agents is 0.5 either way. The predictions are registered and are **not** re-run or changed; the calibration
measures in §8 are reported against them as registered, with this note.

## Verification
- **Tests:** 93 tests pass, including every adversarial case of the review as a permanent test that must refuse
  (`tests/test_review_fixes.py`).
- **Synthetic validation of the analysis code**, rerun on the fixed code (`gates/S10/results/analysis_validation.json`,
  run 3; log `analysis_validation_run3_addendum1.log`): every numeric result is identical to run 2 (criteria A1–A3 and B1–B6 in all four scenarios). The B1 lower-band shortfall in one scenario remains, as accepted in D46 (DV2).
- **Driver**, CPU with the mock model: criteria D1–D5 pass (`gates/S10/results/driver_cpu_validation.json`).
- **Freeze** (`osf/verify_freeze.py --addendum osf/addendum1/DECLARED_CHANGES.json`, result
  `osf/addendum1/FREEZE_VERIFICATION_ADDENDUM1.json`, run 2026-11-03 19:07:39 UTC): **PASS.** 35 of 35 unchanged design files byte-identical to the freeze; 5 declared changes, each with its reason, and no undeclared change; the registered text byte-identical to `cb10726` and its design parts identical to the freeze; sealed files 2 of 2 identical; the coordination record's protocol files unchanged and its logs insert-only (7 of 7 pass).

## What did not change
`stpt/board.py`, the prompts and wordings, the cluster files, the bank, every parameter (H 30, t0 5, D 3, W 5, r 10,
k 3), the T values, the outcomes, the model, the tests and bounds, the sample size, the sealed files and the
registered text. The S8 pilot used the registered initial-vote code; it is development data and is unaffected.
