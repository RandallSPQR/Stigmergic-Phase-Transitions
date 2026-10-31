# Inherited from SPT (harness and simulator only)

`spt_v1.0.1/` holds 12 files copied verbatim from Social Phase Transitions v1.0.1
(https://github.com/RandallSPQR/social-phase-transitions-public, tag `v1.0.1`, commit `c37a91d2d256`, Apache-2.0,
same author). `MANIFEST.json` records each file's git blob OID and sha256 at that commit and its role. `python -m
stpt.inherit verify` checks them, and gate S0 checks them against the tag itself.

- **Harness:** `battery.py`, `stage3.py`, `client.py`, `fetch_cache.py`, `k_avg.py`, `test_stage3.py`.
- **Simulator:** `surrogate.py`, `kernel_test.py`, `confirm_sim.py`, `stage2.py`, `vbsim.py`, `asym.py`.
- The set is the import closure of those entry points within SPT.

**Not inherited:**
- kernels, fitted parameters or transitions;
- sample sizes or replicate structures;
- endpoints or providers.

SPT constants that live inside these files (points P1–P5, budgets, kmax, graph seeds) are never read by StPT code.
StPT estimates fresh, signal-conditioned kernels for its own models, prompts and degree. These files are never edited.
An adapted copy lives under `stpt/` with its source named.
