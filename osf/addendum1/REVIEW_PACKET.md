# Confirmation packet: the seven fixes (addendum 1)

For the reviewer of the execution review of `cb10726e3d359d8094fbd083f336453d6af9280d`. Fixed code: `FIX_COMMIT`
(tag `stpt-run-v1` on the commit that adds the addendum). Everything below runs on CPU with a mock model; no model call.

## Reproduce
```bash
git checkout stpt-run-v1
python -m pytest -q tests                                   # 93 tests; tests/test_review_fixes.py holds every adversarial case
python osf/addendum1/before_after.py                        # each defect on cb10726, and its absence on the fix
python gates/S10/run/validate_driver_cpu.py /tmp/drv        # driver criteria D1-D5 (about 1 min)
python gates/S10/analysis/validate_confirmatory.py          # synthetic validation of the analysis (about 20 min)
python osf/verify_freeze.py <clone of StPT-MP-Coordination> --addendum osf/addendum1/DECLARED_CHANGES.json --out /tmp/v.json
git diff cb10726 FIX_COMMIT -- gates/S10/s10_core.py gates/S10/analysis/confirmatory.py
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

## Not changed
`stpt/board.py` (byte-identical), prompts, clusters, bank, parameters, T values, the analysis model and its numbers
(the synthetic validation reproduces run 2 exactly), the registered text. Design files changed, with reasons:
`osf/addendum1/DECLARED_CHANGES.json`.

## Known limits
- `pod.py` and `s10_driver.sh` (real vLLM control) mirror the S8 pod code but have not run on a GPU. The first paid use
  starts with one smoke block, after the owner's OK.
- The proposed caps are the S9 cost model split by stage, scaled to the accepted totals; the owner approves them
  before any paid run (the driver refuses a caps file not marked APPROVED).
- Branch-level resume reuses checkpoints only within one server start. After a cap stop the server is stopped, so a
  resumed arm restarts from its initial state, and the partial branches are kept under `abandoned/` with a log entry.
