# Gate S0: pipeline and harness (2026-10-31)

**Verdict (2026-10-31, final): S0 PASSES.** One finding needs the owner's decision before S4 (section 4).

- The CPU parts passed first.
- The GPU box identity check then passed for all five models, on two pods the same day (section 1b).
- The pipeline release, the SPT replay and the inherited code are as reported below.

**Publication.**
- The pipeline release is published: branch `release/v1.2.0` and a lightweight tag `v1.2.0` at the pinned commit
  `5ca15f56a71f`. `main` took it by merge `4632409` (PR #16), with the same tree.
- A clean `pip install` at the pinned commit from GitHub passes `stpt.manifest.check_environment` for all five models.
- The coordination record is published, and StPT pins its latest commit (`pins.yaml`).

All numbers below are read from the files in `artifacts/`.

## 1. Pipeline (Step 0): sae-ethos-pipeline v1.2.0, commit `5ca15f56a71f`, LOCKED

| check | result | file |
|---|---|---|
| Lineup file vs every profile; every serializer registered (5 models) | 5/5 ok | `pipeline_identity_local.json` |
| HF API at each pinned revision: revision resolves; weight_hash and chat_template_hash recomputed | 5/5 ok | `pipeline_identity_offline.json` |
| The weight-hash function reproduces the three pod-measured pins (Llama-8B, Gemma-9B, Gemma-27B) | 3/3 exact | pipeline `tests/test_lineup.py` |
| Lineup tests at the tagged commit (Qwen serializer = Qwen's own template on 22 renderings, strings and token ids; profiles through `modelcfg`; serve command; readout; identity block) | 59 passed | `pipeline_lineup_tests.txt` |
| Existing pipeline suites after the additive changes | registry 6/6, gemma3 12/12, modelcfg 24/24, Llama model_io 30 | pipeline `RELEASE_NOTES.md` |
| Wheel built from the tag, clean venv: imports; `qwen3_5` resolves by entry point; ships lineup data, no tests or data | pass | pipeline `RELEASE_NOTES.md` |
| **Box identity check** (GPU, all five models) | **PASS 5/5** (section 1b) | `artifacts/gpu/box_identity_summary.json` |

## 1b. Box identity check (GPU)

**Hardware and stack.**
- One NVIDIA RTX PRO 6000 Blackwell Server Edition (96 GB), driver 595.91, RunPod secure cloud.
- This was the owner's fallback: no A100 80GB was available in 15 attempts over 30 minutes.
- Serving stack: Python 3.11.13, vLLM 0.19.1, torch 2.10.0+cu128, transformers 5.5.3. Pipeline 1.2.0 installed from
  GitHub at the pinned commit.
- Driver: `gpu/box_identity.sh`, committed before the run. Launcher: `gpu/launch.py`.
- The driver performs the steps of the pipeline's `pod/serve_lineup.sh`. That script was not used because of a v1.2.0
  defect (`python -m lineup.serve` cannot import `lineup`; coordination record A3).

**Results, per model.** Each model was served twice; the server was restarted between the two starts.
- Within one server start, 8 identical requests on each of 3 prompts gave bit-identical logprobs.
- "Restart" is the largest change in any option's log-probability between the two server starts.
- Every option was read from the top 20, and the restricted-request fallback reproduced each of those reads exactly
  (`fallback_consistency`).

| model | weights re-hashed = pin | template | bit-identical within a start | fallback exact | restart: max Δ log P | non-A/B mass (plain / board / lopsided) |
|---|---|---|---|---|---|---|
| Llama-3.1-8B-Instruct | 495b73750141622d, 11/11 files | agree | yes | yes | 0.115 | 0.20 / 0.24 / 0.01 |
| Gemma-2-9B-IT | 7055bc8c5f456ced, 11/11 | system-free 3/3 (official template refuses system role) | yes | yes | **0.0** | 0.89 / 0.21 / 0.002 |
| Qwen3.5-9B | 4b570a1e6e5db4b9, 11/11 | agree | yes | yes | 0.123 | 0.01 / 0.02 / 0.001 |
| Gemma-3-27B-IT | 34f745e7c6ef5b7b, 23/23 | agree | yes | yes | 0.250 | 0.999 / 0.000 / 0.000 |
| Qwen3.5-27B | 5e536c8708a9430b, 19/19 | agree | yes | yes | 0.226 | 0.03 / 0.006 / 0.001 |

Notes:
- The two Qwen weight hashes, pinned at Step 0 from Hugging Face metadata alone, are now confirmed from the bytes.
  All five models are byte-verified.
- Files: `artifacts/gpu/20261031T1605Z/` (first pod) and `artifacts/gpu/20261031T1621Z/` (rerun). Per-model files:
  `summary_*`, `readout_*`, `preflight_*`, `tokenizer_*`, logs. Collated in `artifacts/gpu/box_identity_summary.json`.

**Run record.** These were operational failures, not model failures.
- **First pod** (`xnbyb65lcj7ock`, 16:05–16:20 UTC): the three 9B-class models passed. Both 27B downloads failed with
  "No space left on device": the 120 GB disk I chose filled with Hugging Face's xet chunk cache.
- **Rerun** (`akcajq9m33o9wl`, 16:21–16:32 UTC): the two 27B models only, 200 GB disk, xet cache cleared after each
  model.
- **Self-delete:** the first pod's self-delete did not work. The REST DELETE with the pod's own key returns 403, so I
  terminated that pod from here. The rerun removed itself through the `runpodctl` fallback.
- **Lesson:** the in-pod hard deadline cannot rely on the REST delete. Watchers here must enforce it.
- **Cost:** about 26 pod-minutes at $2.49/h, roughly $1.10.

## 2. SPT harness replay against the tagged release

Setup:
- Fresh clone of `social-phase-transitions-public` at tag `v1.0.1`; HEAD = `c37a91d2d256` (the pinned commit).
- The release's own hash-locked environment: Python 3.13.18, 4 CPUs.
- Its replication steps `qc.canary s1.cache s1.fits s1.summary`, fast mode, offline (`SPT_OFFLINE=1`: a request
  missing from the cache is an error, never an API call).

| step | result | detail |
|---|---|---|
| fetch | pass | 31 cache snapshots, all SHA-256-verified |
| qc.canary | PASS | the comparator rejects one-byte and one-ulp corruptions |
| s1.cache | PASS (3.3 min) | 28 battery CSVs, 264,647 rows rebuilt from the battery prompts and looked up in the cache: 0 unmatched, 0 unexplained. 7,422 rows sit in duplicate-request groups (two contact permutations render the same prompt). 426 of them differ from the committed row, and each equals a committed answer of its own group: SPT's documented rule. |
| s1.fits | PASS (7.5 min) | 20 fit files, 0 differ (profile `fit`) |
| s1.summary | PASS (0.2 min) | 17 files, 0 differ |
| claim C1 headline numbers | 10/10 | `spt_replay_REPORT.md` |

Total 11.0 min; largest process 4,649 MB.
Files: `spt_replay_REPORT.md`, `spt_replay_report.json`, `spt_replay_cache_check.json`, `spt_replay_console.log`.

This is a harness check, not kernel inheritance. No SPT kernel, fit or transition enters StPT.

## 3. Inherited harness and simulator

The 12 vendored files are SPT's battery, live-network runner, client, kernel battery, surrogate and table-kernel
simulators, transition locator and Viana–Bray / heat-bath simulators. Each equals the blob at the pinned SPT commit:
12/12 (`inherited_verify.json`).

## Manifest

`artifacts/manifest.json`, from `stpt.manifest.header()`. It names:
- the pipeline v1.2.0 commit;
- the SPT v1.0.1 commit;
- the coordination record commit `93a9ee77429d`;
- the brief revision.

It was written before this report was committed, so it records StPT commit `1a8efe7` with `dirty: true` (the
uncommitted S0 files).

Reproduce: `bash gates/S0/run_s0.sh WORKDIR`.

## 4. Finding for the owner: logprobs are not bit-identical across a server restart (4 of 5 models)

**What was seen.**
- Within one server start, every model is bit-identical (8 of 8 requests, 3 prompts).
- Across a restart, Llama-8B, Qwen-9B, Gemma-3-27B and Qwen-27B move by one or two bf16 steps on the logit (0.125 or
  0.25 nats). Gemma-2-9B does not move.
- The largest moves (0.25) occur where A and B are both far in the tail. Gemma-3's plain prompt is the example: 99.9% of
  the mass is elsewhere.
- Every start used the FLASH_ATTN backend and ran vLLM's kernel autotuner. A plausible cause, **not established**, is
  that the autotuner picks different kernels on different starts.

**Why it matters.**
- StPT runs will span many server starts. A per-start shift of up to 0.25 nats is a nuisance factor close to S4's
  0.3-nat repeat-noise limit.
- "Deterministic kernels" is established within a start, not across starts.

**Options.**
- **(a) Accept it.** Record the server start in every manifest and spread runs over starts; S4 then measures repeat noise
  across starts, not only within one.
- **(b) Test candidate settings for v1.2.1 on one pod (about $1–2), then re-pin both studies.** For example: disable
  the autotuner, `--enforce-eager`, or vLLM's batch-invariant mode.
- Recommendation: (b), before S4.

## Open items for the owner

1. ~~Push the pipeline release.~~ Done 2026-10-31 (see the update at the top).
2. ~~Create `RandallSPQR/StPT-MP-Coordination` and push the record.~~ Done 2026-10-31. Location accepted (D7).
3. ~~GPU for the box identity check.~~ Approved and done 2026-10-31 (section 1b).
5. **GPU type for all StPT serving.** Determinism was checked on the RTX PRO 6000 Blackwell, so StPT should serve on that
   type, or re-run this check on another.
6. **The restart finding** (section 4): option (a) or (b).
4. **Proposal awaiting a decision:** P6, the SPT tag v1.0.1 for the replay. The Qwen pair, the stack and bf16 were
   accepted (D8–D10).
