# Stigmergic Phase Transitions (StPT), revision 3

**Question.** Agents see only their contacts' current votes. Do those votes change how memoryless LLM agents use
dispersed private evidence? And does a temporary change to what agents see leave a lasting mark on the board?

**Status (2026-11-02): S0 and S1 closed; S2 passed (D15–D19); S3 passes with W3, confirmed on a held-out set (D20–D21); S4 passes, D14 tripwire triggered (blocking by start mandatory, A16); S5 passes (all models monotone in strength and direction; wide spread in responsiveness); S6 fails on Llama-3.1-8B, which leaves the pooled confirmatory tests (D24; four-model confirmatory set); initial-vote rule decided (D25); S7 (branch isolation) in progress.**
- Not frozen. No paid collection. Nothing confirmatory.
- Brief: https://claude.ai/artifact/Q36cWtMumtJPs3semD76ni (revision 3).
- Missing Piece is the complementary study. Both share the pipeline and the coordination record below.

## Pins (`pins.yaml`; copied into every run manifest by `stpt.manifest.header`)

| what | where | tag | commit |
|---|---|---|---|
| Shared five-model pipeline (LOCKED) | RandallSPQR/SAE-Ethos-Calibration | `v1.2.0` | `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` |
| SPT release (harness + simulator source; S0 replay) | RandallSPQR/social-phase-transitions-public | `v1.0.1` | `c37a91d2d2561fdf78fc61af500ea000aac3ea2f` |
| Shared coordination record | RandallSPQR/StPT-MP-Coordination | none | `7c4430adc40fca9ae2e51223b0243fdac053ba18` |

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
| S7: branch isolation | **CPU part passes** (mock model, negative control detected; `gates/S7/results/s7_cpu.json`); **GPU part running 2026-11-02** (`gates/S7/S7_PLAN.md`) |
| S8–S10 | not started |

## Layout

- `pins.yaml`: tags and commits.
- `stpt/`: StPT code.
  - `manifest.py`: header and environment check.
  - `inherit.py`: verify the inherited files.
- `inherited/spt_v1.0.1/`: SPT harness and simulator, verbatim, blob-verified.
- `gates/S0/`: the S0 script (`run_s0.sh`), report and artifacts.
- `handoff/`: git bundles used to publish the pipeline release and the coordination record (both now on GitHub; kept for provenance).
- `CLAUDE.md`: standing rules.
