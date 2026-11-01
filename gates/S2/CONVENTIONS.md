# StPT evidence conventions (gate S2): APPROVED AS PROVISIONAL VALUES (owner, 2026-11-01; coordination D15–D17)

The brief lists "evidence-model conventions, pooled margin, informed fraction, bank sizes" as decisions still required.
The values below are **proposals**. The development bank is built on them, so S3–S8 can run. Each can be changed
before the freeze (S10); a change is a prospective amendment, logged in the coordination record.

| convention | proposal | why |
|---|---|---|
| Evidence item | a report from a named source with a **stated accuracy in plain frequencies**, favouring one option ("A guard who is right 3 times out of 4 says the east bridge is open.") | The designed likelihood ratio follows from the text: LR = a/(1 − a) for a symmetric source. That makes it objective and separate from model responsiveness (S5). |
| Accuracy levels | 3 in 5 (LR 1.5), 3 in 4 (LR 3), 9 in 10 (LR 9), equal weights | Weak, moderate and strong evidence, spaced about evenly in log LR (0.41, 1.10, 2.20) |
| Informed fraction | 0.5: 50 of 100 positions hold one report; the other 50 are told they have no report | The middle level. Rung 2 varies it (the dose). |
| Reports per informed agent | 1 | Keeps the kernel's evidence input one-dimensional (an accuracy level and a direction). |
| Report direction | drawn from the generative model: favours the true option with probability = its stated accuracy | Representative allocations. No selection on outcomes. |
| Dependence | a **shared report** (one item_id) held by several agents counts once; a declared dependence group counts once (its strongest member) | Brief: shared items counted once. |
| Prior | 0.5 | Brief |
| Pooled margin | pooled log-odds toward the truth ≥ **3.0** (posterior ≥ 0.95) | A solvable board: the pooled evidence is decisive, while single reports are not. |
| Unsolvable draw | if a representative allocation misses the margin, the next seed in a fixed sequence replaces it, and the replacement is logged | This selects on the evidence (design), never on a group outcome. |
| Conditional challenge set | constructed minority-correct profiles (for example, 12 reports at 9 in 10 for the truth and 30 at 3 in 5 against it), always labelled | Brief: labelled, and never mixed into representative results. |
| Shared-report variants | development bank only: two stories (bridge, crate), both truths, add one weak shared report (3 in 5) against the truth, held by 10 agents | This lets S3–S8 measure double counting. **The confirmatory bank has none (D16).** |
| Banks | development: 6 stories × both truths = 12 scenarios + 4 shared-report variants (2 stories × both truths) = 16; confirmatory: 6 **different** stories × both truths = 12 scenario specs | Truth is balanced across content within each story. The two banks share no story. |
| Development allocations | 4 representative allocations per development scenario (64), plus 2 challenge-set allocations for each of 4 scenarios (room and drawer, both truths; 8) | Enough for S3 comprehension, S5, S6 and the pilot |
| Confirmatory allocations | **not drawn now**. After S9 sets the tier, K allocations per scenario are drawn from the fixed seed sequence `conf-alloc|<scenario_id>|<k>`, k = 0…K−1 | Bank size comes from S9. The draw rule is fixed now, so nothing is chosen later. |

**Decided 2026-11-01 (D15–D17):**
- The accuracy levels, informed fraction 0.5 and margin 3.0 are accepted as provisional values.
- The confirmatory bank has no shared-report variants.
- Difficulty is chosen by blind-board accuracy only (`gates/S2/difficulty/`).

Still open: the bank sizes (after S9), and the difficulty setting (CPU grid now; measured kernels after S3–S5; S8
pilots 2–3 settings).
