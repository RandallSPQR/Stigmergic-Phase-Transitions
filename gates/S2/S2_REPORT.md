# Gate S2: evidence specifications (2026-11-01)

**Verdict: S2 PASSES its gate rule.** Every scenario's state, prior, designed likelihood ratios, dependence and pooled
margin are specified and committed before any model call on it. No model code is imported anywhere in S2. The
conventions the banks rest on are **provisional**; they are listed for the owner in `CONVENTIONS.md`.

## What S2 produced

| artefact | where |
|---|---|
| Evidence model: designed LR from stated source accuracy; dependence counting; seeded allocation; pooled benchmark; challenge-set construction; validator | `stpt/evidence.py`; tests `tests/test_evidence.py` (8 tests) |
| **Shared evidence schema v1.0** (StPT and Missing Piece) | coordination record `schema/evidence_schema_v1.0.json` |
| Provisional conventions (accuracy levels, informed fraction, margin, banks) | `CONVENTIONS.md` |
| Development bank: 16 scenario specs and 72 allocations | `banks/development/` |
| Confirmatory bank: 12 scenario specs. Allocations are drawn after S9 by the fixed seed rule. | `banks/confirmatory/` |
| sha256 of every spec and allocation | `banks/MANIFEST.json` (file sha256 prefix `4de05fa2e423416c`) |
| Build and validation | `make_banks.py`, `results/validation.json` |

## Checks (from `results/validation.json`)

| check | result |
|---|---|
| Every spec valid (internal validator) | 28/28 |
| Every spec valid against the shared JSON Schema v1.0 | 28/28 |
| Truth balanced | development 8 A / 8 B; confirmatory 6 A / 6 B |
| Development and confirmatory banks share no story | yes (6 stories each, disjoint) |
| Representative development allocations solvable (pooled log-odds toward the truth ≥ 3.0) | 64/64, none redrawn |
| Challenge-set allocations minority-correct, solvable and labelled | 8/8 |
| Model code imported | none |

Every evidence item reads like "A guard who is right 3 times out of 4 says the east bridge is open." The designed
likelihood ratio follows from the stated accuracy: 3 in 5 gives 1.5, 3 in 4 gives 3, 9 in 10 gives 9.

## A design property for the owner, before S3–S9

**The boards are easy in aggregate:**
- At informed fraction 0.5 with equal accuracy weights, the pooled log-odds of representative allocations run from
  20.0 to 60.0 toward the truth. The margin of 3.0 never binds.
- 52–88% of held reports favour the truth (median 72%). A majority of informed agents is right on every
  representative board.
- Single reports are weak, but the board is not hard. Representative boards can show whether traces help or harm
  evidence use (live vs blind). A ceiling, where the live board is near 100% correct, would shrink the room for an
  effect.
- **Levers:** a lower informed fraction, weaker accuracy levels, or a larger share of challenge-set boards. The S8
  pilot measures the live and blind levels, and S9 turns them into power. The choice is the owner's, among the
  conventions listed.

**Owner decisions (from `CONVENTIONS.md`):**
- accuracy levels;
- informed fraction;
- pooled margin;
- shared-report variants in the confirmatory bank;
- bank sizes (after S9);
- the difficulty point above.
