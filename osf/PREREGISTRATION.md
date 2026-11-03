# Stigmergic Phase Transitions (StPT), core study: pre-registration

**Status:** frozen at the StPT commit tagged `stpt-prereg-v1` (tag pushed by the owner). Posted to OSF before any
confirmatory run. The OSF registration DOI and the Zenodo DOI of the frozen commit are recorded in the coordination
record when issued.

- **Repositories:** StPT `RandallSPQR/Stigmergic-Phase-Transitions`; coordination record `RandallSPQR/StPT-MP-Coordination`
  (decisions D1–D31, amendments A1–A29, sealed-file register `SEALED.md`).
- **Every number below comes from a committed results file, cited in place.**

## 1. Question and hypotheses
**Question.** Agents see only their contacts' current votes. Do those votes change how memoryless LLM agents use
dispersed private evidence? And does a temporary change to what agents see leave a lasting mark on the board?

**Two confirmatory contrasts** (D3). Holm across the two. Each also has its own equivalence test.
- **H-board:** the board effect. Ordinary agents' support for the correct option differs between the live board
  (agents see their 4 contacts' displayed votes) and the blind board (agents see no one). The sign is not predicted:
  aggregation (+) or harm (−).
- **H-pulse:** pulse persistence. A temporary display pulse leaves an effect on its recipients after normal displays
  are restored. Agents are memoryless, so any persistence must be stored in the board.

Everything else is secondary (§6), reported with intervals and no power target.

## 2. Agents and models (pipeline v1.2.0, LOCKED)
- **Confirmatory set (D24):** Gemma-2-9B-IT, Qwen3.5-9B, Gemma-3-27B-IT, Qwen3.5-27B. These are the four models that
  passed every gate (S3 comprehension, S5 responsiveness, S6 solo pooled check).
- **Secondary comparison agent:** Llama-3.1-8B-Instruct. It failed S6 (0.832 < 0.90; `gates/S6/results/s6_summary.json`).
  It runs every cluster, has per-model estimates, and is never pooled. It is the weakly social agent of D23.
- **Serving:** pipeline `sae-ethos-pipeline` v1.2.0, commit `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b`; vLLM 0.19.1;
  batch size 1; raw logprobs; prefix cache off; bf16; RTX PRO 6000 Blackwell (D9, D10, D12). The exact binary readout
  gives log P(A) and log P(B), and non-A/B mass is recorded.
- **SPT release replayed at S0:** `social-phase-transitions-public` v1.0.1, commit
  `c37a91d2d2561fdf78fc61af500ea000aac3ea2f`. Only the harness and simulator are inherited; no kernel, transition or
  sample size comes from SPT.

## 3. Design
- **Board:** random-regular graph, d = 4, N = 100. Contacts are unlabelled and anonymous. Each call shows:
  - the agent's own evidence (one report or none);
  - its own current vote;
  - its 4 contacts' displayed votes (live) or the line that it sees no one (blind).
- **Prompt wording (D20, D21):** board wording **W3** is primary; its exact text is locked in the coordination record's
  `PROTOCOL_SPEC.md`. Every question ends with "Reply with exactly one letter, A or B, and nothing else." Contact order,
  option order and letter mapping are randomised per call and recorded. The letter mapping is balanced within every
  server-start block.
- **Evidence (D18):** half the agents informed (one report each). Sources are right 3 in 4 (LR 3) or 9 in 10 (LR 9),
  in equal shares. Each report names the truth with its stated accuracy.
- **Confirmatory bank (D29):** 26 stories × truth A/B = 52 specs (`gates/S2/banks/`, manifest sha256
  `f9058fb6347bf5acc6b08f40efcbb5cf40d786702900520aef07b4e96aac5098`). The bank is disjoint from the development
  stories and linted (`gates/S2/results/story_lint.json`).
- **Clusters (D29, D31):** 61 confirmatory clusters, drawn by the seed rule fixed before any draw
  (`gates/S2/CONFIRMATORY_SEED_RULE.md`). The cluster file's sha256 is
  `48a3eb8da9ec0052cef13b43551f3156d4d874133feb32a724c01e95895c42f0` (`gates/S10/clusters/MANIFEST.json`).
  - They use all 26 stories and all 52 specs; truth is 31 A / 30 B; every allocation is solvable.
  - A cluster = a graph × an evidence allocation × a story.
  - All models run on the same clusters (shared clusters; models are fixed strata).
  - **Pilot (S8) clusters and development allocations are never reused.**
- **Conditions (D4):** blind board; live board; randomised display pulse. Committed nodes, prerecorded boards and
  reversal branches are rung 1b and are not part of this study.

## 4. Protocol
- **Decision noise (D23).** Each vote is sampled as u < σ(ℓ/T), where ℓ is the exact A/B logit and u is a seeded
  uniform; never argmax.
  - **Primary T, per model, Bayesian anchor:** T is set so that a lone 3/4 report, read with no contacts, gives its
    Bayesian posterior 0.75. Values: Gemma-2-9B 2.15, Qwen3.5-9B 1.78, Gemma-3-27B 10.40, Qwen3.5-27B 2.88, Llama 0.50
    (`analysis/results/t_options.json`).
  - **Secondary regime:** T = 1, on 16 of the 61 clusters (seeded share 0.2).
- **Initial vote (D25):**
  - **Rule (i):** each agent's first vote is sampled at T from its W3 blind, evidence-only call. That call carries a
    seeded **placeholder own vote**, balanced within evidence type, within server-start blocks and across graph
    positions. The placeholder assignment, and so the initial state, is identical for the live and blind runs of a
    cluster. Uninformed agents' first votes follow the balanced placeholder. Rule (i) equals rule (ii) followed by one
    blind update; on development data the blind board differs between the rules by ≤ 0.003 after two updates per agent.
  - **Sensitivity arm, rule (ii):** a seeded 50/50 start, on 12 clusters.
- **Updates:** random-sequential with replacement. **Operational horizon: 30 sweeps** (3,000 updates per run; D28, met
  in S9: `gates/S9/results/s9_tiers.json`).
- **Server starts (D14, A16):**
  - every run manifest records the server-start ID;
  - the live and blind runs of a cluster, and its pulsed and unpulsed branches, run within one start;
  - clusters go to starts in blocks of 4 (16 blocks per model);
  - **blocking by start is mandatory in every analysis**: the D14 tripwire was triggered at S4.
- **Failed or invalid calls:** 3 seeded retries; then the agent keeps its previous vote, counted as missing. S8 had 0
  missing calls in 288,000.
- **Display pulse (D26):**
  - at a fixed time, t0 = 5 sweeps, from the live run's saved state;
  - **two pulsed branches** (one toward A, one toward B; independent recipient sets);
  - r = 10 recipients, drawn by their own seed, independent of evidence;
  - each recipient sees **k = 3** of its 4 contacts' displays set to the pulse direction for **3 sweeps**; then normal
    displays are restored. Real votes and evidence are unchanged.
  - The unpulsed branch is the live main continuation, byte-identical under common random numbers (S7).
- **Self-reset branch (D26):** on 33 of 61 saved states (seeded share 0.5), for one direction. At restoration each
  recipient's own vote is reset to its value at pulse onset; all other votes are unchanged.
- **Variant wordings (D21):** each model runs, on a seeded 20% of clusters, each variant wording valid for it on the
  held-out check, for the per-model consistency check.
- **Tie rule:** no core outcome uses a majority (both outcomes are shares), so no tie rule enters the confirmatory
  analysis. In any descriptive majority, ties are reported as ties.
- **Isolation:** probes and branches never feed back. Main trajectories were byte-identical with and without probes
  and branches on all five models (S7, `gates/S7/S7_REPORT.md`).

## 5. Outcomes and the confirmatory analysis
- **Primary board-effect outcome (D31):** per run, the **mean of ordinary agents' support for the correct option over
  sweeps 25–30 inclusive**. Support is the share of the 100 agents voting the true option at the end of each of sweeps
  25, 26, …, 30. All agents are ordinary in the core: there are no committed nodes.
  - Board effect for (model m, cluster j): b_mj = Y_live − Y_blind, paired within the cluster.
- **Pulse persistence (D26):** for each pulsed branch, the share of **all assigned recipients** (intention to treat)
  voting the pulse direction, averaged over the **5 sweeps after restoration**, pulsed minus unpulsed. For (m, j), the
  outcome is the mean of the cluster's two branches.
- **Pooled estimand (D2, D24):** θ = the mean over the four confirmatory models of each model's mean effect. With
  shared clusters this is the mean over clusters of c_j = mean_m(effect_mj).
- **Model** (`gates/S10/analysis/confirmatory.py`): c_j = θ + u_block(j) + e_j, with a random intercept for the
  server-start block; REML. **Inference is conditional on the story bank** (the confirmatory tests).
  - t reference with containment df = blocks − 1 = 15.
  - **Superiority:** two-sided, Holm across the two contrasts at family α = 0.05.
  - **Equivalence:** TOST at **±0.03**, α = 0.05 (the 90% interval inside the bound).
  - **Decision per contrast:** effect / small effect within the bound / equivalence (no effect beyond ±0.03) /
    inconclusive.
  - **Reference effect:** 0.05.
- **Generalisation to new stories (D29):** the same model plus a story random intercept; df = min(blocks, stories) − 1.
  Reported beside the conditional result.
- **Missing data:** missing calls are counted by condition and model. No cluster or run is excluded on any outcome. A
  cluster whose live/blind pairing or branch alignment fails the code's integrity checks is reported as a protocol
  failure; it is never silently dropped.
- **Validation before data:** `gates/S10/results/analysis_validation.json`.
  - Extraction is exact against an independent recomputation, and tampered pairing or branches are refused.
  - Type I error, Holm family-wise error, sign recovery, interval coverage and TOST behaviour were checked on synthetic
    data on this cluster layout; see §11.

## 6. Secondary and sensitivity analyses (no power target; Holm does not apply)
- **Per-model estimates** of both contrasts, Llama's included (D2).
- **Prompt sensitivity, per model (D20, D21):** both contrasts in each wording valid for that model. A model is
  consistent if its estimates have the same sign and overlapping intervals. Also reported: W2's structural failure and
  the wording-fragility finding (`gates/S3/S3_REPORT.md`).
- **Sensitivity analyses:**
  - without Qwen3.5-9B (D20; three models);
  - **the 27B models alone** (D21c);
  - within-family size contrasts, Gemma 27B − 9B and Qwen 27B − 9B (D21a);
  - comprehension as a descriptive moderator (D21b).
- **Board effect by informed status (D19):** uninformed (transmission) vs informed (social override) agents.
- **Persistence:**
  - **self/social decomposition (D26):** social = persistence in the self-reset branch; self = total − social;
    cross-checked by kernel simulation with the contact terms off after restoration;
  - ITT vs exposed-only;
  - immediate response;
  - propagation to agents at distance ≥ 2 from every recipient and never exposed;
  - end-of-window persistence.
- **Decision-noise secondary regime T = 1 (D23).** Pre-registered reports:
  - the Bayesian-anchor calibration's generalisation (each model's response to a lone 9/10 source against 0.90, and to
    a 3/5 source against 0.60);
  - Llama as the weakly social agent;
  - Gemma-3-27B at T ≈ 10.4.
- **Initial-vote rule (ii) arm (D25):** the live-board difference between the rules, especially in the early rounds.
- **The final-sweep version of the board effect,** and support trajectories.
- **Kernel consistency:** kernels re-estimated from live updates per condition, against the battery, within the
  restart-drift bound.
- **The model check** (§8).

## 7. Sample size and stopping
- **61 clusters** (D29, D31): the Strong tier sized at cross-model correlation ρ = 1. Strong means TOST power ≥ 0.90 at
  ±0.03 on both contrasts.
- **Sizing SDs** (D27; the larger of the simulated 80th-percentile SD and S8's conservative SD; `gates/S9/S9_REPORT.md`):
  window board effect 0.056, persistence 0.063.
- **At 61 clusters** (`gates/S9/results/power_at_61.json`), with the containment df of 15:

  | contrast | MDE (80% power) | TOST power at ±0.03 (α 0.05) | power at the 0.05 reference effect |
  |---|---|---|---|
  | board effect (window) | 0.022 | 0.973 | > 0.999 |
  | persistence | 0.025 | 0.934 | 0.999 |

  - Generalisation to new stories, TOST power for the board effect: 0.96 at story SD 0.02, 0.76 at 0.04.
  - The simulated cross-model correlation is about 0.30 (board) and 0.41 (persistence), so ρ = 1 is conservative.
- **No interim analysis and no early stopping.** All 61 clusters are run.
- **Cost (accepted, D31):** about $77 core and $144 with all secondary arms. Spend is flagged to the owner at 80%.

## 8. Predictions (sealed until posting; proposed to be unsealed into this registration)
- **Procedure** (`gates/S10/predictions.py`): kernels estimated from the S8 development readouts at each model's T (200
  cluster-bootstrap draws), simulated on the 61 confirmatory graphs and allocations with the D25 start, the D26 pulse
  and the S4 start jitter, 5 runs per draw. Kernel uncertainty is propagated.
- **The predictions:** the predictive distribution (mean; 5th, 50th and 95th percentiles) of both pooled estimands and
  of each model's estimates, plus per-cluster predictions.
- **Sealed file:** `gates/S10/sealed/s10_predictions.json.gz.b64`, sha256 **[filled at the freeze commit]**. It was
  written once and not opened before the freeze.
- **Calibration and discrepancy measures, reported after the run:**
  - whether each observed pooled estimate lies inside its 90% predictive interval;
  - the share of per-model estimates inside their 90% intervals;
  - per-cluster calibration (the share of clusters inside their 90% predictive interval, and the slope of observed on
    predicted);
  - the predictive intervals' widths.

  A gap between prediction and observation is reported as a model discrepancy. It is not a test of either hypothesis.

## 9. Sealed pilot estimates (D30)
- The S8 pilot's point estimates of both confirmatory contrasts were **sealed when computed and not seen** by anyone
  before this freeze:
  - live − blind;
  - pulse persistence, with its self/social decomposition and ITT vs exposed.
- The sealed file is `gates/S8/sealed/s8_sealed.json.gz.b64`, sha256
  **`e6b1bc7ac35d28591428efc8dbc9836f8b9d6ff98b2cb55fcf76fa72f16a95a8`**.
- The study was sized on variance components only (D27): S8's between-cluster SDs and S9's simulation.
- **Openings of the sealed files (from `SEALED.md` at the freeze):** none. This table is copied from the coordination
  record at the freeze commit.

## 10. Deviations
- Every post-registration change goes in the coordination record's `AMENDMENTS.md`, labelled prospective or
  post-outcome, and is reported in the paper.
- Pilot (S8) data are development data and are not pooled with confirmatory data.

## 11. Analysis-code validation results
**[filled at the freeze commit from `gates/S10/results/analysis_validation.json`]**
