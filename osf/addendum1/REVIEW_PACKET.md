# Confirmation packet: the seven fixes (addendum 1)

For the reviewer of the execution review of `cb10726e3d359d8094fbd083f336453d6af9280d`. Round 1 fixes:
`1031a83559f70a9ba82739cb7ea10c791d515f3d` (packet at `bb0f12a`). Round 2 fixes, after your confirmation pass on
`bb0f12a`: `e8f156de84bf3b82db1e0c0cce0cbefec8e2201e`. Round 3 fixes, after your operational review of `fc0fc0c`:
`06572ae13c5f84707325f3be525dd7374f906fa3` (tag `stpt-run-v1` on the commit that adds the final addendum). Everything below runs on CPU with a mock model; no model call.

## Reproduce
```bash
git checkout stpt-run-v1
python -m pytest -q tests                                   # 148 tests: test_review_fixes, test_review_followup, test_review_round3
python osf/addendum1/reviewer_cases/stpt_reviewer_followup_bb0f12a.py .   # your round-2 script: every flag false
python osf/addendum1/before_after.py                        # each defect on cb10726, and its absence on the fix
python gates/S10/run/validate_driver_cpu.py /tmp/drv        # driver criteria D1-D5 (about 1 min)
python gates/S10/analysis/validate_confirmatory.py          # synthetic validation of the analysis (about 20 min)
python osf/verify_freeze.py <clone of StPT-MP-Coordination> --addendum osf/addendum1/DECLARED_CHANGES.json --out /tmp/v.json
git diff cb10726 1031a83559f70a9ba82739cb7ea10c791d515f3d -- gates/S10/s10_core.py gates/S10/analysis/confirmatory.py
```

## Per finding

| # | where the fix is | tests that must refuse (or hold) | evidence |
|---|---|---|---|
| 1 | `gates/S10/s10_core.py`: `initial_state` (uninformed = placeholder, no call; informed sampled at T from the W3 blind call; letter pairs over informed calls) | `test_1_uninformed_first_vote_is_placeholder_without_a_call`, `test_1_informed_first_vote_sampled_at_T`, `test_1_initial_call_refuses_live_or_variant_board` | `before_after.json` → `1_initial_vote` |
| 2 | `gates/S10/analysis/confirmatory.py`: `check_record`, `_check_rows` (called by `outcomes`) | `test_2_malformed_record_refused` (21 cases: short/long runs, 1 or 3 branches, same direction, duplicate / missing / out-of-range recipients, truncated branch rows, step gap, NaN draw, inf/NaN logit, logit without missing flag, bad vote, agent out of range, rule (ii) with pulses, bad initial votes, no pulses), `test_2_mixed_server_starts_refused`, `test_2_conforming_record_passes` | `2_run_shape` |
| 3 | `confirmatory.py`: `frozen_universe`, `check_table`, `primary` (keyword-only options; no caller metadata), `subset_estimate`, `infer` (NaN) | `test_3_nonconforming_table_refused` (17 cases: extra / missing cluster, Llama entry, no start ID, T1 arm, T = 1, wording w4, initial wording w4, rule (ii), wrong run key, wrong parameters, mock run, key mismatch, NaN board, inf persistence, missing contrast, no identity), `test_3_caller_metadata_not_accepted`, `test_3_block_labels_come_from_recorded_starts`, `test_3_tampered_manifest_refused`, `test_3_nan_refused_in_inference`, `test_3_conforming_table_passes` | `3_primary` |
| 4 | new `gates/S10/run/driver.py` (+ `pod.py`, `make_payload.py`, `make_caps.py`, `gates/S10/gpu/s10_driver.sh`) | `test_4_*` (unknown model, failed pipeline check before any call, stage without cap, one start per arm and enforced T, cap kill and resume without duplication, reused start ID, tampered / non-frozen cluster); CPU validation D1–D5 | `gates/S10/results/driver_cpu_validation.json` |
| 5 | `s10_core.py`: `block_placeholders`, `placeholders_for` | `test_5_placeholder_balance_within_block_and_cluster`, `test_5_placeholders_identical_across_models_arms_and_conditions` | `5_placeholders` |
| 6 | `s10_core.py`: `arm_spec`, `arms_for`, `run_cluster(c, model, kernel, prm=None, arm="primary", ...)` | `test_6_arms_follow_drawn_flags`, `test_6_self_reset_only_when_drawn_and_only_in_primary`, `test_6_undrawn_or_invalid_arm_refused` (5 cases), `test_6_variant_not_valid_for_model_refused`, `test_6_T_is_never_free` | `6_arms` |
| 7 | `s10_core.py`: `run_cluster` (W3 board for the initial call) | `test_7_variant_arm_initial_call_uses_w3` | `7_initial_wording` |

Also: `tests/test_s10_core.py::test_after_the_initial_state_the_runner_is_s8s`. Given S8's initial state, the fixed
runner reproduces S8's live, blind, pulsed and self-reset branches byte for byte, so nothing after the initial state
changed.

## Round 2 (your confirmation pass on `bb0f12a`)

| | where the fix is | tests | evidence |
|---|---|---|---|
| R2.1 cap stop swallowed by retries | `gates/S10/run/driver.py`: `Stop(BaseException)`, `CHECK_EVERY = 10` | `test_stop_escapes_the_retry_handler`, `test_cap_stop_bounds_calls`, driver validation D6 | `reviewer_cases/results_before_after.json`: 3,050 → 209 calls |
| R2.2 altered records accepted | `gates/S10/analysis/confirmatory.py`: `verify_record`, `_verify_rows` (called by `outcomes`) | `test_recorded_value_tampering_refused` (28 cases: initial vote, informed initial vote, placeholder, init call flag, live / blind / pulse / self-reset vote flipped, missing call with a changed vote, own vote, displayed contacts, pulse display override, agent, draw, letter mapping, directions, recipients, altered contacts, saved state, self-reset present when not drawn / removed, start IDs incomplete / extra / two starts, run key, truth, T, undrawn arm) | each refusal names the recomputed field |
| R2.3 block split on resume | `driver.py`: block folder, `_finalize`, `block_abandoned`; `confirmatory.py` `check_table`: each scheduled block one start per model | `test_4_cap_kill_then_resume_reruns_the_block_in_one_start`, `test_3_start_layout_not_matching_scheduled_blocks_refused` (3 layouts), driver validation D2 | split → one start |
| R2.4 hard-kill gap unmetered | `driver.py` `Ledger`: wall clock, persisted open interval, `close()` on a clean stop | `test_unclosed_interval_is_charged`, driver validation D4/D7 (real SIGKILL; the gap is charged) | $0.01 → $1.01 |
| R2.5 incomplete start-ID map | `confirmatory.py` `verify_record` | `start_ids_only_init`, `start_ids_extra_branch`, `start_ids_two_starts` | refused |

## Round 3 (your operational review of `fc0fc0c`)

| | where the fix is | tests | evidence |
|---|---|---|---|
| R3.1 failed upload deleted the pod | `gates/S10/gpu/s10_driver.sh`: `upload` (verified, returns failure), `upload_until_verified`, `finish` (never deletes; exit 5 keeps `UPLOAD_PENDING`), recovery mode; `gates/S0/gpu/launch.py --data-safe` (volume at /workspace; delete only without the marker, else stop) | `test_upload_failure_keeps_marker_and_never_deletes`, `test_verified_upload_clears_marker`, `test_upload_function_returns_failure`, `test_launch_data_safe_deletes_only_after_verified_upload` (2 cases); driver validation D9 | `reviewer_cases/results_round3_before_after.json` |
| R3.2 caps missed install, downloads and the readiness wait | `gates/S10/run/ledger.py` (meter from the pod's first line; continuous within a pod session; watchdog; cumulative `seed` across pods); `driver.py` (`headroom` before a start; `server.start(check=...)`); `pod.py` (`check()` every 5 s of the readiness wait; vLLM registered for the watchdog) | `test_server_start_needs_headroom`, `test_readiness_wait_is_cap_checked`, `test_pod_start_is_metered_from_its_first_line`, `test_time_between_phases_is_charged_within_a_pod_session`, `test_watchdog_stops_a_paid_phase_at_the_cap`, `test_cumulative_caps_across_pods`; driver validation D8 | $1.00 → $0.00 (refused) |
| R3.3 non-A/B mass not saved | `gates/S10/s10_core.py`: `MassRecorder`, `compact`, init records; `confirmatory.py`: 10-field rows, 7-field initial records, mass required | `test_mass_recorded_for_every_call`, `test_mass_tampering_refused` (6 cases), `test_kernel_without_mass_stops_the_run`; driver validation D10 | no field → every row |

Your round-3 script reads `fc0fc0c`'s shell layout by text slicing; the restructured script no longer has those
slices, so the script itself does not run on the fix. Its cases are the tests above.

## Not changed
`stpt/board.py` (byte-identical), prompts, clusters, bank, parameters, T values, the analysis model and its numbers
(the synthetic validation reproduces run 2 exactly), the registered text. Design files changed, with reasons:
`osf/addendum1/DECLARED_CHANGES.json`.

## Known limits
- A recorded logit altered together with its vote (a consistent pair) cannot be detected from the record; detecting it
  would need the model to be read again. Every other recorded value is recomputed.
- `pod.py`, `s10_driver.sh` and `launch.py --data-safe` (real vLLM control, volume, uploads) mirror the S8 pod code and
  are tested on CPU with stubs, but have not run on a GPU or against RunPod. The first paid use
  starts with one smoke block, after the owner's OK.
- The proposed caps are the S9 cost model split by stage, scaled to the accepted totals; the owner approves them
  before any paid run (the driver refuses a caps file not marked APPROVED).
- Resume reuses checkpoints only within one server start (re-attach after a hard kill). After a clean stop the server
  is stopped, so an interrupted block reruns whole in the next start; its earlier output is kept under `abandoned/`.
