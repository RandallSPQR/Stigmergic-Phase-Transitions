# Stigmergic Phase Transitions (StPT), revision 3

**Question.** Agents see only their contacts' current votes. Do those votes change how memoryless LLM agents use
dispersed private evidence? And does a temporary change to what agents see leave a lasting mark on the board?

**Status (2026-11-03): S0 and S1 closed; S2 passed (D15–D19); S3 passes with W3, confirmed on a held-out set (D20–D21); S4 passes, D14 tripwire triggered (blocking by start mandatory, A16); S5 passes (all models monotone in strength and direction; wide spread in responsiveness); S6 fails on Llama-3.1-8B, which leaves the pooled confirmatory tests (D24; four-model confirmatory set); initial-vote rule decided (D25); S7 passes (branch isolation exact on CPU and on all five models); pulse settings decided (D26); S8 passes (execution, exposure 0.958, manipulation check 0.155 [0.135, 0.175]; contrast estimates sealed); S9 done (61 clusters; window outcome, D31); S10 passes: design frozen (commit `17063f5`, `osf/FREEZE_MANIFEST.json`), sealed files opened after the freeze (logged), pre-registration finalised and re-verified (commit `cb10726`, tag `stpt-prereg-v1-final`), registered on OSF (DOI 10.17605/OSF.IO/SM8XR) and archived on Zenodo (DOI 10.5281/zenodo.23924793) (D47). The confirmatory run has not started; it needs the owner's explicit OK.**
- Not frozen. No paid collection. Nothing confirmatory.
- Brief: https://claude.ai/artifact/Q36cWtMumtJPs3semD76ni (revision 3).
- Missing Piece is the complementary study. Both share the pipeline and the coordination record below.

## Pins (`pins.yaml`; copied into every run manifest by `stpt.manifest.header`)

| what | where | tag | commit |
|---|---|---|---|
| Shared five-model pipeline (LOCKED) | RandallSPQR/SAE-Ethos-Calibration | `v1.2.0` | `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` |
| SPT release (harness + simulator source; S0 replay) | RandallSPQR/social-phase-transitions-public | `v1.0.1` | `c37a91d2d2561fdf78fc61af500ea000aac3ea2f` |
| Shared coordination record | RandallSPQR/StPT-MP-Coordination | none | `80e9992f43e50f08a85b2f3d218ff9b2ea9d8c41` |

Models (pipeline v1.2.0):
- Llama-3.1-8B-Instruct, Gemma-2-9B-IT, Gemma-3-27B-IT.
- Qwen3.5-9B and Qwen3.5-27B, thinking off. These two are pencilled.

All five are self-hosted, served in bf16 at batch size 1, with exact logprobs.

## Design (core only; rung 1b is not built)

**Board.**
- Random-regular graph, d = 4, N = 100. Contacts are unlabelled and anonymous.
- Each call shows the agent its own evidence, its own vote, and its 4 contacts' displayed votes.
- Contact order, option order and letter mapping are randomised per call and recorded.
- Votes are **sampled** from the A/B probabilities at a fixed decision noise T (logits / T), with seeded draws. Never
  argmax.

**Conditions.**
- Blind board.
- Live board.
- Randomised display pulse, run on branches from saved states, one pulse per branch, never feeding back.

**Confirmatory contrasts (two).** Each is one pooled test across the five models, with models as fixed strata; Holm
across the two; a TOST for each.
1. Live minus blind, on ordinary agents' final support for the correct option.
2. Pulse persistence: recipients after restoration, pulsed minus unpulsed branch.

## Gates (in order; each blocks spend; stop and report after each)

| gate | status |
|---|---|
| Step 0: shared pipeline built, tagged, locked, published; SPT release pinned | **done** |
| S0: pipeline + SPT harness replay | **CLOSED 2026-11-01**: passed; restart drift accepted on v1.2.0 with server-start blocking (D14; `gates/S0/S0_REPORT.md`) |
| S1: simulator checks (CPU only) | **CLOSED 2026-11-01**: passes under Amendment 1 (DV1); original-plan failure kept on record (`gates/S1/S1_REPORT.md`) |
| S2: evidence specifications | **passes** (28 specs before any model call; schema v1.0); conventions accepted as provisional (D15–D16); difficulty chosen by simulated power before live data: f 0.5, sources {3/4, 9/10}; S8 region adds {3/5, 3/4, 9/10} (D18; `gates/S2/difficulty/POWER_REPORT.md`) |
| S3: comprehension (GPU) | **PASSES**: W3 valid for all five models in round 2 (A12) and on a held-out set (A14–A15); W3 is the single primary wording; variants W4–W6 valid per model only (D21); wording-fragility finding recorded (`gates/S3/S3_REPORT.md`) |
| S4: noise (GPU) | **PASSES 2026-11-02**: within-start repeat SD 0 (all repeats bit-identical); between-start σ_b ≈ 0.05 nats (Gemma-2-9B 0); **tripwire triggered by Gemma-3-27B** (S_p 0.050, σ_b ≈ 0.24 nats near p = 0.5): blocking by start mandatory everywhere (A16) (`gates/S4/S4_REPORT.md`) |
| S5: responsiveness (GPU) | **PASSES 2026-11-02**: every model and wording monotone in designed strength and direction; slopes on log LR 0.10 (Llama) to 1.77 (Gemma-3-27B); Gemma-3-27B saturates (`gates/S5/S5_REPORT.md`) |
| S6: solo pooled-evidence check (GPU) | **FAILS 2026-11-02 on Llama-3.1-8B** (representative 0.832; own vote against truth 0.711); other four pass (0.902–0.992); challenge set not solvable solo by any model; Llama becomes the secondary comparison agent (D24; `gates/S6/S6_REPORT.md`, `analysis/CONFIRMATORY_SET.md`) |
| S7: branch isolation | **PASSES 2026-11-02**: main trajectories byte-identical with and without probes and pulse branches, on CPU (negative control detected) and on all five models in one start each (`gates/S7/S7_REPORT.md`) |
| S8: pilot (GPU) | **PASSES 2026-11-03**: rules 1–3 met; horizon to S9 (D28); confirmatory-contrast estimates sealed (D27; `gates/S8/S8_REPORT.md`) |
| S9: power simulation (CPU) | **done 2026-11-03**: horizon 30 sweeps stands; Strong at ρ = 1 = 61 clusters (final sweep; $77 core / $144 all arms) or 48 (window 25–30; $61 / $113); 3 validation flags to the owner (`gates/S9/S9_REPORT.md`) |
| S10: freeze and pre-registration | **passes 2026-11-03** (D47): freeze commit `17063f5`; final pre-registration `cb10726` (tag `stpt-prereg-v1-final`; freeze re-verification PASS, `osf/FREEZE_VERIFICATION.json`); OSF https://osf.io/sm8xr (DOI 10.17605/OSF.IO/SM8XR); Zenodo DOI 10.5281/zenodo.23924793 |
| S10 addendum 1: execution review | 7 findings accepted (D48): fixes #2–#7 and clarification #1 in `gates/S10/s10_core.py` and `gates/S10/analysis/confirmatory.py`; collection driver `gates/S10/run/` (CPU-validated); every adversarial case a test (`tests/test_review_fixes.py`); round 2 after the reviewer's confirmation pass on `bb0f12a`: 5 more fixes, tests in `tests/test_review_followup.py`; round 3 after the reviewer's operational review of `fc0fc0c`: 3 more fixes (data-safe uploads and pod teardown, caps over the whole paid lifecycle, non-A/B mass recorded), tests in `tests/test_review_round3.py`; round 4 after the reviewer's launch-path review of `0778869`: 3 more fixes (acknowledgements reach every cap check, final upload time metered, malformed readouts stop the run), tests in `tests/test_review_round4.py`; freeze re-verified (`osf/addendum1/`); OSF addendum and the reviewer's confirmation pending; **no confirmatory run before both** |

## Layout

- `pins.yaml`: tags and commits.
- `stpt/`: StPT code.
  - `manifest.py`: header and environment check.
  - `inherit.py`: verify the inherited files.
- `inherited/spt_v1.0.1/`: SPT harness and simulator, verbatim, blob-verified.
- `gates/S0/`: the S0 script (`run_s0.sh`), report and artifacts.
- `handoff/`: git bundles used to publish the pipeline release and the coordination record (both now on GitHub; kept for provenance).
- `CLAUDE.md`: standing rules.
