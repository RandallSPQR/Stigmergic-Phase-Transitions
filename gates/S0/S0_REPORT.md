# Gate S0: pipeline and harness (2026-10-31)

**Verdict: the CPU parts PASS. S0 is NOT complete:**
- The pipeline's box identity check (GPU) has not run. It needs the owner's OK for GPU spend.
- The pipeline release is not yet on GitHub (push refused to this session).

Gate S1 does not start until both are resolved, or the owner rules otherwise.

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
| **Box identity check** (`pipeline/lineup/pod/serve_lineup.sh`, once per model) | **NOT RUN** | none |

The box identity check, per model, covers:
- the weight bytes re-hashed to the pin;
- the tokenizer facts;
- template agreement on the box;
- 8 identical readouts, bit-identical;
- exact-fallback consistency.

Until it runs:
- The two Qwen weight hashes are metadata-pinned. Their bytes have not been read.
- "Deterministic kernels" on the vLLM 0.19.1 stack is a requirement, not a result, for all five models.

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

Reproduce: `bash gates/S0/run_s0.sh WORKDIR`. It needs the pipeline on GitHub.

## Open items for the owner (S0 cannot close without them)

1. **Push the pipeline release.** This session was refused push access to `RandallSPQR/SAE-Ethos-Calibration`.
   `handoff/sae-ethos-pipeline_v1.2.0.bundle` holds branch `release/v1.2.0` and tag `v1.2.0` with the exact hashes
   (see `handoff/README.md`).
2. **Create `RandallSPQR/StPT-MP-Coordination`** and push `handoff/stpt-mp-coordination.bundle`. Alternatively choose
   another location; the pin in `pins.yaml` then changes and the change is logged.
3. **GPU for the box identity check:** about one pod-hour per model on one 48–80 GB GPU (5 models). Needs an OK.
4. **Proposals awaiting a decision** (coordination record `DECISIONS.md` P1–P6):
   - the Qwen pair (Qwen3.5-9B/27B, dense, thinking off);
   - the vLLM 0.19.1 stack;
   - bf16 for all five models;
   - the coordination location;
   - the SPT tag.
