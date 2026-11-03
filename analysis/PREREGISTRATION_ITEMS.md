# Items the pre-registration (S10) must contain

A running checklist. S10 does not freeze until each item is in the pre-registration text.

**Status (2026-11-03): complete.** Every item below is in the registered pre-registration: `osf/PREREGISTRATION.md` at
commit `cb10726e3d359d8094fbd083f336453d6af9280d` (tag `stpt-prereg-v1-final`), posted to OSF as
https://osf.io/sm8xr (DOI 10.17605/OSF.IO/SM8XR) and archived on Zenodo (DOI 10.5281/zenodo.23924793). Coordination
record: D47, A35.

| item | where in the registered text |
|---|---|
| 1. Sealed pilot estimates, sha256, openings table | §9 (hash; estimates decoded from the sealed file after the freeze, D45; openings table quoted, empty at the freeze commit `17063f58`); §12 timeline |
| 2. Primary outcome window | §5: mean over sweeps 25–30 inclusive (D31) |
| 3. Operational horizon | §4: 30 sweeps |
| 4. Tier and cluster count | §7: Strong at ρ = 1, **61 clusters on the window outcome** (D31 kept 61 rather than 48, to protect generalisation) |
| 5. Story random effect; conditional and generalisation inference | §5, §11 (B6) |
| 6. Confirmatory seed rule and bank manifest hash | §3 |
| 7. Decisions in force (D14/A16, D19–D21, D23–D26) | §2–§6 |

The checklist below is kept as written before the freeze.

1. **Sealed pilot estimates (owner, 2026-11-03; coordination D30).** State that the S8 pilot's point estimates of both
   confirmatory contrasts were sealed when computed and not seen before the freeze:
   - live − blind;
   - pulse persistence, with its self/social decomposition and ITT versus exposed.

   Give the sealed file's sha256: `e6b1bc7ac35d28591428efc8dbc9836f8b9d6ff98b2cb55fcf76fa72f16a95a8`. The file is
   `gates/S8/sealed/s8_sealed.json.gz.b64`; the register is the coordination record's `SEALED.md`.
   - **Purpose:** a reader can verify that the study was sized on variance components only (D27, D29), without anyone
     looking at a pilot effect.
   - **At freeze, also state** whether the file was ever opened, quoting the openings table of `SEALED.md` (empty if
     never opened).
2. **Primary outcome window:** final sweep or the mean over a final window (D28 item 3), as decided after S9.
3. **Operational horizon:** 30 sweeps (D28 rule met in S9; `gates/S9/S9_REPORT.md`).
4. **Tier and cluster count** (D29: Strong at ρ = 1): 61 clusters on the final-sweep outcome, or 48 on the window
   outcome (S9; owner's decision).
5. **Story random effect;** conditional-on-bank and generalisation inference (D29).
6. **Confirmatory seed rule** (`gates/S2/CONFIRMATORY_SEED_RULE.md`) and the bank manifest hash.
7. **Decisions in force:**
   - D14 / A16: blocking by start;
   - D20 / D21: W3 primary; per-model wording consistency; the fragility finding;
   - D23: T, with its Bayesian anchor and the four items;
   - D24: confirmatory set of four; Llama secondary;
   - D25: initial vote;
   - D26: pulse settings, self-reset decomposition, ITT;
   - D19, D20, D21: the secondary and sensitivity analyses.
