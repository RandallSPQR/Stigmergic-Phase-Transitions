# Items the pre-registration (S10) must contain

A running checklist. S10 does not freeze until each item is in the pre-registration text.

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
3. **Operational horizon** (D28; decided in S9).
4. **Tier and cluster count** (D29: Strong at ρ = 1; the exact n from S9).
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
