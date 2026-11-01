# Stigmergic Phase Transitions (StPT), revision 3

**Question.** Agents see only their contacts' current votes. Do those votes change how memoryless LLM agents use
dispersed private evidence? And does a temporary change to what agents see leave a lasting mark on the board?

**Status (2026-10-31): Step 0 done and published; gate S0 PASSED (all five models byte-verified on GPU); one finding awaits the owner before S4.**
- Not frozen. No paid collection. Nothing confirmatory.
- Brief: https://claude.ai/artifact/Q36cWtMumtJPs3semD76ni (revision 3).
- Missing Piece is the complementary study. Both share the pipeline and the coordination record below.

## Pins (`pins.yaml`; copied into every run manifest by `stpt.manifest.header`)

| what | where | tag | commit |
|---|---|---|---|
| Shared five-model pipeline (LOCKED) | RandallSPQR/SAE-Ethos-Calibration | `v1.2.0` | `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` |
| SPT release (harness + simulator source; S0 replay) | RandallSPQR/social-phase-transitions-public | `v1.0.1` | `c37a91d2d2561fdf78fc61af500ea000aac3ea2f` |
| Shared coordination record | RandallSPQR/StPT-MP-Coordination | none | `46baa832341fd879ce21075c09fd4ea3401af704` |

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
| S0: pipeline + SPT harness replay | **PASS**; restart drift unresolved: the v1.2.1 fix failed confirmation, staying on v1.2.0 (`gates/S0/S0_REPORT.md` 4c) |
| S1–S10 | not started |

## Layout

- `pins.yaml`: tags and commits.
- `stpt/`: StPT code.
  - `manifest.py`: header and environment check.
  - `inherit.py`: verify the inherited files.
- `inherited/spt_v1.0.1/`: SPT harness and simulator, verbatim, blob-verified.
- `gates/S0/`: the S0 script (`run_s0.sh`), report and artifacts.
- `handoff/`: git bundles used to publish the pipeline release and the coordination record (both now on GitHub; kept for provenance).
- `CLAUDE.md`: standing rules.
