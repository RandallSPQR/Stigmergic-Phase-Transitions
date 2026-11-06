# StPT pre-registration, addendum 1: execution review fixes and a clarification

**Registration:** OSF https://osf.io/sm8xr (DOI 10.17605/OSF.IO/SM8XR); registered text = `osf/PREREGISTRATION.md` at
commit `cb10726e3d359d8094fbd083f336453d6af9280d` (tag `stpt-prereg-v1-final`; Zenodo 10.5281/zenodo.23924793).
**This addendum:** filed after registration and **before any confirmatory data exist** (no confirmatory model call has
been made). Fixes: round 1 in commit `1031a83559f70a9ba82739cb7ea10c791d515f3d`; round 2 (the reviewer's confirmation
pass on `bb0f12a`) in commit `e8f156de84bf3b82db1e0c0cce0cbefec8e2201e`; round 3 (the reviewer's operational review of
`fc0fc0c`) in commit `06572ae13c5f84707325f3be525dd7374f906fa3`; round 4 (the reviewer's launch-path review of
`0778869`) in commit `238de3ab8eaf04d705c779980ddd077ebd9072ef`; round 5 (the reviewer's final-upload review of
`de1cb9a`) in commit `39e60d3768aef59eb8def09f25531532220c1423`. Tag: `stpt-run-v1` (on the commit that adds the final text).
Coordination record: D48, D49, A36, A37, A38, A39, A40.

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

## Round 2: the reviewer's confirmation pass on `bb0f12a`
The same reviewer checked the round-1 fixes and reported five more defects in them, all accepted. Each is a permanent
test, and the reviewer's own script is kept verbatim (`osf/addendum1/reviewer_cases/stpt_reviewer_followup_bb0f12a.py`)
and run by the tests; its results on `bb0f12a` and on the fix: `osf/addendum1/reviewer_cases/results_before_after.json`.

| | defect in `bb0f12a` | fix | on `bb0f12a` → fixed |
|---|---|---|---|
| R2.1 | a cap stop raised inside a model call was caught by the harness's retry of failed calls and calls continued to the branch checkpoint | the driver's stop is a BaseException (not caught by the retry, which catches Exception); the meter checks every 10 calls | $0.20 cap: 3,050 calls ($3.05) → 209 calls ($0.21) |
| R2.2 | extraction accepted a valid-looking but altered record: an initial vote changed to the other letter, a recorded vote flipped, a missing call whose vote changed | `verify_record` recomputes every value from the run key, the frozen cluster and the replayed state: agents, draws, letter mappings; each own vote and displayed contacts (pulse displays included); each vote from its logit and u at T, or kept when the call was missing; initial votes from the block-balanced placeholders and the informed calls; pulse directions, recipients, altered contacts, saved state; self-reset only when drawn | all three accepted → refused (a flipped vote had moved the board effect from 0.00833 to 0.01000) |
| R2.3 | after a cap stop and resume, a scheduled block of 4 ran in two starts (cluster 1 in start 1, clusters 2–4 in start 2); the analysis only reported it | the block is the unit of work: its records become final only when the whole block finished in one start; an interrupted block resumed in another start is moved to `abandoned/` (logged) and rerun whole; the analysis refuses any model whose scheduled blocks are not one start each | block split → all four in one start; split tables refused |
| R2.4 | after a hard kill the next driver reset the meter, so the billable gap was not charged | the ledger meters wall-clock time and persists its open interval; the next driver charges the whole gap to the open stage | 1,000 s gap: $0.01 → $1.01 |
| R2.5 | a start-ID map with only some branches passed extraction | a start ID is required for exactly the arm's branches, all equal | accepted → refused |

**Known limit.** A recorded logit changed together with its vote, so that the pair stays consistent, cannot be detected
from the record. The logits are the readouts themselves; detecting it would need the model to be read again.

## Round 3: the reviewer's operational review of `fc0fc0c`
Three more defects, in the collection's operations rather than its analysis, all accepted. The reviewer's script is kept
verbatim (`osf/addendum1/reviewer_cases/stpt_final_operational_cases_fc0fc0c.py`); it reads `fc0fc0c`'s shell layout,
which this round restructured, so each of its cases is reproduced by `tests/test_review_round3.py` and by the driver's
CPU validation (D8–D10). Results on `fc0fc0c` and on the fix: `osf/addendum1/reviewer_cases/results_round3_before_after.json`.

| | defect in `fc0fc0c` | fix | on `fc0fc0c` → fixed |
|---|---|---|---|
| R3.1 | a failed upload returned success; the script then wrote DONE and removed the pod, so records not yet uploaded could be lost | outputs live on a persistent volume (`launch.py --data-safe`); `UPLOAD_PENDING` is set before the first paid model phase and cleared only after an upload verified file by file (name and size) on the dataset; upload failures are returned and retried; the pod script never deletes the pod; the launcher deletes it only when the marker is gone and otherwise **stops** it (the volume and every record survive); a restarted pod only retries the upload | exit 0, DONE written, pod removed → exit 5, marker kept, no DONE, pod stopped, not deleted |
| R3.2 | installation and weight downloads were not metered; a server's readiness wait had no cap check ($0.20 cap: $1.00 spent with no model call) | the ledger (stdlib-only `gates/S10/run/ledger.py`) opens at the pod script's first line and charges every phase (install, downloads, server starts, calls, teardown, the gaps between phases); a watchdog enforces the caps every 5 s during every paid phase (never an upload); a server start needs headroom for one start (300 s) and its readiness wait checks the cap every 5 s; a run resumed on a new pod takes the earlier pods' spend (caps are cumulative) and restores their finished records | $1.00 with no call → start refused at $0.00; a readiness wait past the cap stops within one check |
| R3.3 | non-A/B mass, which the registration (§2) says is recorded, was not saved | the runner records each call's mass (rows gain a 10th field, initial records a 7th); a readout without a valid mass stops the run; the analysis refuses records without it | no mass field → mass in every row, verified |

## Round 4: the reviewer's launch-path review of `0778869`
Three integration gaps between the pod script, the ledger and the model adapter, all accepted. No design file changed
in this round. The reviewer's script is kept verbatim and run by the tests and by the driver's CPU validation (D11);
results on `0778869` and on the fix: `osf/addendum1/reviewer_cases/results_round4_before_after.json`.

| | defect in `0778869` | fix | on `0778869` → fixed |
|---|---|---|---|
| R4.1 | an acknowledged 80% flag did not let a new pod resume: the pod script checked the cumulative ledger before the acknowledgement reached the driver | the ledger tool applies the owner's acknowledgements (`STPT_ACK`) in every check (pod script, watchdog, driver); an acknowledgement for a stage without a cap is refused | $8.10 of $10 with the acknowledgement: refused → resumes |
| R4.2 | the driver closed the ledger before the final uploads, so their time was not charged and the watchdog was idle | a driver's close is not the end of billing: the time after it is charged (to the stage that ran) and counted by the watchdog until the pod script's final close, which comes after the last upload and charges 120 s in advance for the one upload of the final ledger; each stage has its own stop file | $1.10 billable: $0.10 recorded, no stop → $1.10 recorded, watchdog stop |
| R4.3 | the real model adapter raised an ordinary error for a readout without its non-A/B mass, so the harness retried it and counted a missing call | the adapter checks the readout (both logits and a valid mass) and raises the non-retryable protocol error on a malformed one; transport failures are still retried, then missing, as registered | 4 attempts, missing → stopped after 1 |

## Round 5: the reviewer's final-upload review of `de1cb9a`
Two defects in the pod script's last step, both accepted. No design file changed. The reviewer's script is kept
verbatim and run by the tests and by the driver's CPU validation (D12); results on `de1cb9a` and on the fix:
`osf/addendum1/reviewer_cases/results_round5_before_after.json`.

| | defect in `de1cb9a` | fix | on `de1cb9a` → fixed |
|---|---|---|---|
| R5.1 | the final ledger upload was optional: when it failed, the script still cleared `UPLOAD_PENDING` and exited 0, so the pod could be deleted while the dataset held an earlier ledger, which a resumed pod uses for the remaining spend | the final upload (records, DONE and the final ledger, verified) is required: the marker is cleared only after it succeeds; otherwise exit 5, the marker stays, and the pod is stopped with its volume; a restarted pod (recovery) repeats the same required upload; a ledger that cannot be written also keeps the marker | exit 0, marker cleared → exit 5, marker kept |
| R5.2 | the final upload was charged a fixed 120 s, shorter than its retry schedule (930 s of backoff alone) | every final attempt has a hard time limit (300 s) and is charged through that limit before it starts; every backoff sleep is charged before it starts; successive charges add up from the point already charged, so they cover the worst case without counting time twice; a restarted pod charges from its own start, not for the time it sat stopped | 120 s charged for 930 s of sleep → 2,730 s charged (six 300 s attempts + 930 s) |

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
- **Tests:** 170 tests pass, including every adversarial case of the five review rounds as a permanent test
  that must refuse (`tests/test_review_fixes.py`, `tests/test_review_followup.py`, `tests/test_review_round3.py`,
  `tests/test_review_round4.py`, `tests/test_review_round5.py`).
- **Synthetic validation of the analysis code** (rounds 4 and 5 changed no analysis code), rerun on the fixed code (`gates/S10/results/analysis_validation.json`,
  run 5; log `analysis_validation_run5_addendum1_round3.log`): every numeric result is identical to run 2 (criteria A1–A3 and B1–B6 in all four scenarios; part A on a frozen confirmatory cluster, records with the non-A/B mass). The B1 lower-band shortfall in one scenario remains, as accepted in D46 (DV2).
- **Driver**, CPU with the mock model: criteria D1–D12 pass (`gates/S10/results/driver_cpu_validation.json`), including a cap stop within 10 calls, an interrupted block rerun whole in one start, a real SIGKILL whose billable gap is charged, a server start refused without headroom, a readiness wait stopped at the cap, the pod script keeping its records and the pod when the upload fails, the non-A/B mass in every record, and the reviewer's round-4 and round-5 scripts (D11, D12).
- **Freeze** (`osf/verify_freeze.py --addendum osf/addendum1/DECLARED_CHANGES.json`, result
  `osf/addendum1/FREEZE_VERIFICATION_ADDENDUM1.json`, run 2026-11-06 00:09:50 UTC): **PASS.** 35 of 35 unchanged design files byte-identical to the freeze; 5 declared changes, each with its reason, and no undeclared change; the registered text byte-identical to `cb10726` and its design parts identical to the freeze; sealed files 2 of 2 identical; the coordination record's protocol files unchanged and its logs insert-only (7 of 7 pass).

## What did not change
`stpt/board.py`, the prompts and wordings, the cluster files, the bank, every parameter (H 30, t0 5, D 3, W 5, r 10,
k 3), the T values, the outcomes, the model, the tests and bounds, the sample size, the sealed files and the
registered text. The external execution review came after the freeze; the owner will run it before the freeze in
future studies (for Missing Piece it is a pre-freeze gate, D49). The S8 pilot used the registered initial-vote code; it is development data and is unaffected.
