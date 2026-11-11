# StPT pre-registration, addendum 2: collection report and the secondary-analysis specification, before unblinding

**Registration:** OSF https://osf.io/sm8xr (DOI 10.17605/OSF.IO/SM8XR). The registered text is
`osf/PREREGISTRATION.md` at commit `cb10726e3d359d8094fbd083f336453d6af9280d` (tag `stpt-prereg-v1-final`; Zenodo
10.5281/zenodo.23924793). Addendum 1 (execution review fixes, tag `stpt-run-v1`) was posted before any confirmatory
model call.

**This addendum** is filed after all confirmatory and secondary data were collected and **before unblinding**. No
confirmatory or secondary outcome had been computed, displayed or seen by anyone. During collection, only the
integrity checks below were run on the records. They recompute every record but compute no contrast. Tag
`stpt-secondary-v1`, on the commit that adds this text. The secondary-analysis code in it is identical to commit
`42c7264`. Coordination record (StPT-MP-Coordination): D50–D64 and A41–A69.

## 1. Summary
- All 61 frozen clusters were collected for the four confirmatory models (core stage) and for every drawn secondary
  arm of all five models (secondary stage). All ten stages passed the collection integrity check (§2).
- Collection needed operational interventions (lost pods, a slow host, a setup failure, cap raises). **None changed
  the design:** the clusters, prompts, parameters, models, T values, outcomes, analysis, sample size, sealed files
  and registered text are all unchanged (§3).
- Before unblinding, the owner fixed the choices that the registration's secondary analyses (§6) and model check (§8)
  leave open (D63, D64; §4). The secondary-analysis code was written and tested blind, then reviewed blind by two
  independent reviews, and tagged (§5).
- Unblinding waits for an explicit owner decision naming the tag. The confirmatory analysis then runs first, exactly
  as registered (§6).

## 2. Collection
The integrity check is `gates/S10/run/collection_integrity.py`; one results file per stage is in `gates/S10/results/`.
For each stage it:
- verifies every scheduled record (full recomputation, `confirmatory.verify_record`) and refuses anything not
  scheduled;
- checks one server start per scheduled block;
- counts missing calls;
- reports the non-A/B mass, the letter balance per start, and the code versions, cluster manifest and version pins
  recorded in each record;
- checks the closed final spend ledger.

It computes no outcome.

| stage | records verified / scheduled | model calls | missing | server starts / scheduled blocks | spend / cap (USD) |
|---|---|---|---|---|---|
| Gemma-2-9B core | 61 / 61 | 483,150 | 0 | 16 / 16 | 10.85 / 12.18 |
| Qwen3.5-9B core | 61 / 61 | 483,150 | 0 | 16 / 16 | 13.29 / 14.02 |
| Gemma-3-27B core | 61 / 61 | 483,150 | 0 | 16 / 16 | 21.17 / 24.15 |
| Qwen3.5-27B core | 61 / 61 | 483,150 | 0 | 16 / 16 | 22.81 / 26.65 |
| Gemma-2-9B secondary | 39 / 39 | 278,550 | 0 | 15 / 15 | 7.17 / 7.65 |
| Qwen3.5-9B secondary | 46 / 46 | 332,100 | 0 | 14 / 14 | 12.07 / 14.00 |
| Gemma-3-27B secondary | 60 / 60 | 439,200 | 0 | 16 / 16 | 20.28 / 26.30 |
| Qwen3.5-27B secondary | 56 / 56 | 408,600 | 0 | 15 / 15 | 18.64 / 25.75 |
| Llama-3.1-8B secondary (all its runs, primary arm included; D24) | 112 / 112 | 853,500 | 0 | 16 / 16 | 15.88 / 17.60 |

- **Spend.** The figures are those recorded in each stage's final ledger. They include charged adjustments for pods
  lost before writing their ledger, added from RunPod's billing (A46, A48, A53, A60, A61).
  - Core: $68.12 against the approved $77.00.
  - Secondary: $74.04 against the raised $91.30 (§3).
  - Total: $142.16. Registration §7 estimated "about $77 core and $144 with all secondary arms".
- **Code.** Every record carries the commit and payload that produced it.
  - Gemma-2-9B's smoke block (clusters 1–4) ran on `stpt-run-v1.1` (`f810b64`). The rest of the core collection ran on
    `stpt-run-v1.2` (`8f22f97`). The two payloads differ only in `ledger.py` (spend seeding, A44), which neither
    produces nor alters records.
  - The secondary stage ran on `stpt-run-v1.2.1` (`3404b7e`; A54, setup failures upload their logs), with payloads
    rebuilt only to carry the raised caps file. Each was byte-identical to `stpt-run-v1.2.1` in its other 11 files
    (A56, A58; `gates/S10/ops/OPS_CHANGES.md`).
  - Every stage has one cluster manifest (the frozen one) and one set of version pins.
- **Letter balance** was 0.5 in every server start of every stage.
- **Non-A/B mass.** The largest single call per stage was:
  - Qwen3.5-9B: 0.030 core, 0.051 secondary;
  - Gemma-2-9B: 0.011 core, 0.0097 secondary;
  - Llama-3.1-8B: 0.0033;
  - Qwen3.5-27B: 0.0009 core, 0.0028 secondary;
  - Gemma-3-27B: below 0.0001.

  The mass is recorded and reported, as registered (§2). No cluster or run is excluded on any outcome (§5,
  "Missing data").

## 3. Operational events during collection (no design change)
Each event is logged in the coordination record. A stage that ran as a chain of pods restored the earlier pods'
finished records; the integrity check found the restored records byte-identical. An interrupted block is never
mixed across server starts: its partial output is set aside (`abandoned/`, kept for audit, never analysed) and the
block is rerun whole in one start (addendum 1, R2.3).

| event | what happened | effect on the data | record |
|---|---|---|---|
| payload delivery | the run payload exceeded the 128 KiB limit for one environment variable; it is now delivered in parts, or from the private dataset, and checked by sha256 | none | A41 |
| smoke block | Gemma-2-9B, clusters 1–4, run end to end before the full collection | its 4 records kept as block 1 | D51, A42 |
| stale intermediates | uploads remove superseded intermediate block copies; final records unchanged | none | A43 |
| restore failure | a chained pod's restore step ran nothing, and the pod restarted block 1; it was stopped before any duplicate record was finalised | partial branches set aside, never analysed | A44 |
| two lost pods | two core pods were deleted about 3 h after creation by the owner's own account-wide watchdog, which removes unregistered pods older than 3 h | finished records kept; the interrupted blocks rerun whole in the next pod | A45, A47, A49; D54, D55 (each pod registered with the watchdog from then on) |
| setup failure | a Qwen3.5-27B core pod removed itself during setup, before any model call and without logs; relaunched once as is | none | A52, A53 |
| setup logs | from the secondary stage on, a setup failure uploads its logs before the pod removes itself (`stpt-run-v1.2.1`) | none (operations only) | A54, A56 |
| operations tools | the read-only watcher and the launch wrapper used during collection were put on record, with every change to them | none (they never write to a pod or the dataset) | A55; `gates/S10/ops/OPS_CHANGES.md` |
| secondary caps | secondary branches took about 1.4 times as long as core branches, which the approved caps did not assume. Gemma-2-9B secondary stopped at its cap before block 12; the five secondary caps were raised to the measured projections plus 10%, and Qwen3.5-9B's to $14.00 after a slow host. Core caps unchanged | Gemma-2-9B secondary completed by a chained pod (29 records restored, byte-identical) | A57–A59; D58, D59, D60 |
| slow host | two Qwen3.5-9B secondary pods landed on a host running about half speed; both were stopped, and the stage was relaunched on another host. Their minutes were charged to the stage | finished records kept and restored | D60, D61; A60–A62 |

The 80% spend flag of every stage was acknowledged by the owner (D52, D54, D56, D58).

## 4. Secondary analyses: choices fixed blind (D62–D64)
The specification map is `gates/S10/analysis/SECONDARY_ANALYSIS_SPEC.md`. It covers registration §6 (all items) and
the §8 model check. The registration leaves eight choices open. The owner fixed them on 2026-11-11, with no outcome
computed or seen (D63):

| | open in the registered text | decided (D63) |
|---|---|---|
| A | which W3 estimate a variant wording is compared with | the model's 61-cluster W3 estimate; the same-cluster paired comparison (variant − W3 per cluster) reported prominently beside it |
| B | what "the conclusion" means in the subset sensitivity analyses | the primary's procedure within each subset: Holm across the two contrasts, plus the ±0.03 TOST |
| C | how the within-family size contrasts are formed | per-cluster differences (27B − 9B), confirmatory model, block label = the pair of starts |
| D | the propagation window | the D + W sweeps from pulse onset (as the registered simulation, `analysis/pulse_design.py`); the W window after restoration beside it |
| E | how "contact terms switched off after restoration" is implemented | every agent uses its blind-board kernel cell after restoration. Simulated social = full-kernel persistence − contacts-off persistence, both from the pulsed branch's state at restoration. A model-based check only |
| F | what is reported for the T = 1 arm | per-model estimates and paired T1 − primary differences, descriptive; for each T = 1 estimate, whether its sign matches the primary |
| G | the "early rounds" summary in the rule (ii) comparison | mean live difference over sweeps 1–5; full trajectory shown |
| H | kernel consistency: minimum count and bound (never fixed) | main check within this study: the blind, live, pulse-on and post-restoration kernels (and the blind-prompt first calls) compared with each other; bound = 2 · √(s_drift² + SE_a² + SE_b²), with s_drift the S4 between-start SD in probability; ≥ 30 calls per cell. Secondary: comparison with the development battery, a mismatch read as "harness or story dependence" |

**Readings and settings.**
- **H's standard error** "across contexts" is the cluster-robust standard error across clusters. The owner
  confirmed this as the intended meaning (D64). On a mock harness with no fault, a per-call SE gave false mismatches,
  because identical prompts recur; the cluster-robust SE gave none, and a planted response fault was flagged in every
  checked cell.
- **Model check.** The observed value compared with the sealed predictions is the arithmetic mean over the 61
  clusters, which is the statistic the predictions are of (`gates/S10/predictions.py`). The confirmatory θ is
  reported beside it. Pooled values use the four confirmatory models only; Llama is never pooled (D24).
- **Implementation settings D63 did not fix:**
  - at least 5 clusters per H cell;
  - at least 2 contexts per battery cell;
  - 200 simulation runs per self-reset cluster (E).
- **Degenerate sets.** A set with no variation is reported without a fit.
- **Subset tests.** In a subset analysis, an unfitted contrast keeps the two-test Holm family, with p = 1.

## 5. The secondary-analysis code: written blind, reviewed blind, tagged
- **Code and tests.** The code is `gates/S10/analysis/secondary.py`, with tests in `tests/test_secondary_analysis.py`
  (44). It was developed on mock records and synthetic data only. The first record-level step of every item is
  `confirmatory.verify_record`, and every estimate uses the confirmatory model, blocked by server start.
- **First independent blind review.** It found 8 defects and 5 omissions, all fixed (A66):
  - the E cross-check's start state;
  - per-call standard errors in H;
  - missing-arm detection;
  - loader checks;
  - near-degenerate fits;
  - Llama in a pooled calibration;
  - the trajectory onset;
  - the guard's strictness;
  - the item 11 descriptives.
- **Second independent blind review** (of `a9525b2`, from a bundle with sha256 `629cf3b4…1923`). It found 4 defects
  and supplied a patch (sha256 `f119a176…d01b`), applied unchanged at `42c7264` (A69):
  - the guard accepted an author cell beginning "owner";
  - a degenerate subset contrast aborted the report;
  - trajectory bands treated paired branches as independent;
  - constant predictions gave a spurious calibration slope.

  Its 6 regression tests fail on `a9525b2` and pass on `42c7264`. The reviewer independently recomputed five
  pulse-window quantities on fresh mock branches, which agreed within 1e-12, and found no further defect in choices
  A–H.
- **Blinding guard.** The code refuses real records unless both of these hold:
  - the coordination record holds, committed and in its accepted decisions, an owner decision titled exactly
    "S10 unblinding authorised" that names one tag;
  - the code runs exactly at that tag's commit, unmodified, with the tag on GitHub at the same commit (D64, A68).

## 6. Unblinding and the order of analyses
1. The owner records the decision "S10 unblinding authorised", naming tag `stpt-secondary-v1` (D64).
2. **The confirmatory analysis runs first, exactly as registered:** `gates/S10/analysis/confirmatory.py` as frozen
   with addendum 1's declared changes, on the 61 primary-arm records of the four confirmatory models. This gives two
   contrasts, Holm at 0.05, and the ±0.03 TOST (§5 of the registration).
3. The secondary analyses and the model check then run from the tag (§6 and §8 of the registration, as specified in
   §4 above). They are reported as secondary, with no power target. Holm applies only within the subset sensitivity
   analyses, as decided in B.
4. Any change after unblinding is a post-outcome deviation, logged separately in the coordination record and
   reported in the paper (registration §10).

## 7. Verification
- **Tests:** 246 pass at the tagged commit (`pytest tests`).
- **Freeze** (`osf/verify_freeze.py --addendum osf/addendum1/DECLARED_CHANGES.json`): **PASS**.
  - The 35 unchanged design files are byte-identical to the freeze.
  - The 5 changes declared in addendum 1, and no undeclared change.
  - The registered text is byte-identical to `cb10726`.
  - The sealed files (2 of 2) are identical.
  - The coordination record's protocol files pass.
- **Integrity:** the ten results files in `gates/S10/results/collection_integrity_*_{core,secondary}.json` all
  report `passed: true`.

## What did not change
- the hypotheses, the confirmatory contrasts, the outcomes, the analysis model, the tests and the ±0.03 bound;
- the 61 frozen clusters, the stories, the prompts and wordings;
- every parameter (H 30, t0 5, D 3, W 5, r 10, k 3) and the per-model T values;
- the models and the pipeline (v1.2.0, locked);
- the sample size and the drawn secondary arms;
- the sealed predictions and the registered text.

The secondary analyses implement registration §6 and §8. The choices in §4 settle only what that text leaves open,
and they were made before any outcome was seen.
