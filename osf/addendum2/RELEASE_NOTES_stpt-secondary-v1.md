## stpt-secondary-v1: S10 secondary-analysis code, reviewer-finalized, before unblinding

This release archives the StPT code that will run the S10 secondary analyses (registration §6) and the §8 model check.
It was written and tested blind, then reviewed blind twice, before any confirmatory or secondary outcome was computed
or seen. It also adds the pre-registration's addendum 2 (`osf/addendum2/ADDENDUM_2.md`): the collection report and the
secondary-analysis choices fixed blind.

**Secondary-analysis code:** identical to `42c7264` (the second reviewer's patch, applied unchanged)
**Run code:** unchanged since `stpt-run-v1.2.1` (`3404b7e`); the confirmatory analysis (`gates/S10/analysis/confirmatory.py`) unchanged since addendum 1
**Pipeline:** SAE-Ethos-Calibration v1.2.0, `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b` (unchanged)
**Freeze:** `osf/verify_freeze.py --addendum osf/addendum1/DECLARED_CHANGES.json` passes (no undeclared design change)
**Tests:** 246 pass (`pytest tests`); 44 of them in `tests/test_secondary_analysis.py`
**Coordination record:** D62–D64, A65–A69

### What is in it
- `gates/S10/analysis/secondary.py`: every registered secondary analysis and the model check.
  - Per-model estimates, prompt sensitivity, the subset and size sensitivity analyses, the comprehension table.
  - The informed/uninformed split and the persistence secondaries, including propagation and the self/social
    decomposition with its kernel cross-check.
  - The T = 1 regime, calibration and the G checks, the rule (ii) comparison, kernel consistency, the final-sweep
    effect and trajectories, the model check against the sealed predictions, and the execution descriptives.
- `gates/S10/analysis/SECONDARY_ANALYSIS_SPEC.md`: the specification map, with the owner's choices A–H (D63, D64).
- `gates/S10/analysis/SECONDARY_REVIEW_PACKET.md`: the review packet and both reviews' dispositions.
- `tests/test_secondary_analysis.py`: mock-record identities, estimators with planted values, negative controls, and
  the blinding guard.
- `osf/addendum2/ADDENDUM_2.md`: addendum 2 to the pre-registration.

### The owner's choices, fixed blind (D63, D64)
- **A:** a variant wording is compared with the model's 61-cluster W3 estimate, with the same-cluster paired
  comparison beside it.
- **B:** subset conclusions use Holm + TOST within the subset.
- **C:** size contrasts are per-cluster differences.
- **D:** propagation is measured over D + W from onset, with the W window beside it.
- **E:** "contacts off" uses blind-board cells after restoration (a model-based check only).
- **F:** the T = 1 arm is descriptive, with a sign check against the primary.
- **G:** the rule (ii) early rounds are summarised over sweeps 1–5.
- **H:** kernels are compared within the study, with a cluster-robust SE; the battery comparison is secondary.

### Reviews
- **First blind review:** 8 defects and 5 omissions, all fixed.
- **Second blind review** of `a9525b2`: 4 defects. Its patch was applied unchanged; its 6 regression tests fail
  before and pass after.

### Blinding guard
Real records load only if both of these hold:
- the coordination record holds a committed, accepted owner decision titled exactly "S10 unblinding authorised"
  that names this tag;
- the code runs exactly at this tag's commit, unmodified, with the tag on GitHub at the same commit.

### Collection (complete; integrity passed for all ten stages)
- Four confirmatory models × 61 clusters (core), plus every drawn secondary arm of all five models.
- Every record was verified by full recomputation, with 0 missing calls.
- Spend $142.16: $68.12 core, $74.04 secondary.
- No outcome has been computed.
