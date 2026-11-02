# Gate S4: noise (development bank). Plan committed before any S4 model call.

**Approval.** The owner approved S4 on 2026-11-02 (coordination D20), to run straight after the held-out wording check
with the wordings that pass. If W3 fails that check, S4 does not start.

**What S4 measures** (brief gate row; D14):
1. **Within-start repeat SD** on the logit scale. Limit: 0.3 nats. This is the pass/fail quantity.
2. **Between-start shift.** No pass/fail; it feeds the D14 tripwire and S9.
3. Both are also stated **in vote probability at the operating point**, p near 0.5.

Also reported, for S5 and S9 (not pass/fail): the presentation effects that the order-marginalised kernel averages over
(letter mapping, option order, contact order), letter preference (share of A), and non-A/B mass at the vote question.

## Probe set (`probes/`, built by `make_probes.py`)
- Development bank only. 120 contexts, seed `S4-probes-v1`. The context draw does not depend on the wording set.
  - 100 live: 50 informed and 50 uninformed. For each informed status, 10 contexts for each contact pattern (0–4
    contacts showing A).
  - 20 blind: 10 informed, 10 uninformed.
  - Own vote is balanced within every cell. Single-report positions only, as at S3.
- **Four layouts per context:** letter mapping × option order (2 × 2), with the contact order drawn per layout. So the
  **letter mapping is balanced within every start** (D20 item 4): 50% of probes show content A as letter A.
- The actual vote question, in every wording of the study's set (W3 first, then the variants that pass the held-out
  check, in order). 480 probes per wording.
- The probe file and its sha256 are committed before launch. The pod renders the probes from the compact contexts
  with `stpt/prompts.py` and refuses to run on a hash mismatch.

## Runs
- **Two pods** (RTX PRO 6000 Blackwell, D12), each running **3 cold server starts per model**, so 6 starts per model.
  "Cold" means every compile and autotune cache is cleared before the start, as on a fresh pod (the S0 restart test's
  procedure).
  - Pods are a level of the start factor: study runs will span pods.
  - If only one pod can be obtained within 60 minutes of the first, S4 runs with 3 starts. The report says so, and the
    between-pod component is then not estimated.
- Pipeline v1.2.0, checked by `check_pin`. Serving flags of v1.2.0 (D14). Weights re-hashed to their pins.
- In every start, readouts come in this order:
  1. the W3 block;
  2. each other wording's block;
  3. the W3 block again, as exact within-start repeats.

  The probe order is fixed and is the same in every start.
- Every start's manifest records:
  - the server-start ID (pod / start index / start time) and the cleared caches;
  - the pipeline identity block, the StPT commit and `pins.yaml`;
  - the probe sha256.
- Results upload to the private HF dataset after every start.
- **Cost.** Hard cap 2 h per pod (about $5 each, $10 total). Expected about 75 min per pod, about $6 for both.

## Analysis (`analyse_s4.py`; fixed now)
Notation:
- ℓ = log P(A) − log P(B) is the readout's A/B logit (letters). ℓc is the same logit in content space, for "the
  option that is content A".
- i indexes a probe, s a start, m a model and w a wording.
- The operating-point conversion is Δp = Δℓ · p(1 − p) / T at p = 0.5, i.e. 0.25 · Δℓ at T = 1. Decision noise T is
  not yet fixed; vote-probability figures are stated at T = 1 and scale as 1/T.

**1. Within-start repeat SD (gate).**
- For each model, wording W3 and start: the SD of the 480 repeat pairs, sqrt(mean((ℓ_first − ℓ_repeat)²) / 2). Also
  reported: the share of pairs that are bit-identical.
- **Pass:** every model's largest per-start value ≤ 0.3 nats.
- Expected to be 0, because S0 found readouts bit-identical within a start.

**2. Between-start shift.**
- For each model and wording: d_is = ℓ_is − mean_s ℓ_is, using each start's first read.
- σ_b = sqrt(Σ d² / (n_i (S − 1))): the per-probe SD across starts. It includes systematic start offsets and probe ×
  start jitter.
- Reported:
  - σ_b in nats;
  - the start offsets b_s = mean_i d_is;
  - a within-pod vs between-pod split: σ_b computed over the starts of one pod, and the difference in pod means.
- **Operating-point probes:** the probes whose start-averaged renormalised P(A) lies in [0.1, 0.9]. The primary
  statistics use these probes; all probes are reported too. If fewer than 40 probes of a model and wording fall in
  the range, the primary statistics use all probes, and that is stated.

**3. Tripwire statistic (D14).**
- For each model and wording: S = 0.25 · RMS, over operating-point probes and all start pairs, of (ℓ_is − ℓ_is'). This
  is the typical between-start shift in vote probability at p = 0.5, T = 1.
- Also: S_offset = 0.25 · the largest |b_s − b_s'|, the systematic part.
- Also: the empirical RMS of the actual change in renormalised P(A) between starts, over probes with start-averaged
  P(A) in [0.35, 0.65].
- **Trigger:** S or S_offset > 0.025 for any model in any wording of the set. The trigger makes blocking by start
  mandatory for every analysis, and it is logged in the coordination record. S4 passes or fails on item 1 only.

**4. Variance components for S9** (`results/s4_variance_components.json`), per model and wording:
- the variance of start offsets;
- the probe × start residual variance;
- the between-pod component (if two pods ran).

S9 carries these into kernel uncertainty and the power tiers (D14 item 4).

**5. Presentation effects** (start 1 of each pod; not pass/fail):
- letter effect: the mean of ℓc over layouts with content A shown as A, minus with content A shown as B. This is
  letter preference in nats;
- option-order effect: the same, by which content is listed first;
- the residual SD across a context's four layouts.

**6. Format:**
- mean non-A/B mass at the vote question;
- the share of probes answered A (higher probability);
- `read_by`: how often the exact fallback was needed.

S4 does not compare wordings on vote probabilities, and it does not contrast live with blind. Wordings were chosen on
comprehension only, and S4 measures noise only.

Outputs: `artifacts/<run>/`, `results/s4_summary.json`, `results/s4_variance_components.json`, `S4_REPORT.md`.
