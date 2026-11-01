# Gate S3: comprehension (development bank, branched), 2026-11-01

**Verdict: 4 of 5 models pass; Qwen3.5-9B fails one question type.**
- Rule: accuracy ≥ 0.90 per question type, per model.
- Qwen3.5-9B scores 0.867 on its own report. Its errors are interference from the rest of the context, not misreading
  the report.
- Under the plan, a failing model is reported, and the next step for it is the owner's decision.

**Inputs and run.**
- Plan: `S3_PLAN.md`, committed before any model call.
- Prompts: `prompts/s3_prompts.json`, sha256 `0495d0062e48b29a…`, verified on the pod.
- Raw results: `artifacts/20261101T1556Z/` (one `s3_<model>.json` per model, manifest included). Summary:
  `results/summary.json`.
- Pod `7ekw451rm4ge53`, RTX PRO 6000 Blackwell, pipeline v1.2.0 (`5ca15f56a71f`, checked by `check_pin`), vLLM 0.19.1,
  one server start per model (its ID is in each manifest). Every weight set was re-hashed to its pin.
- The first pod (`pgjgmswm2yk1u9`) served no model: preflight's blob-name check cannot verify under huggingface-hub
  1.x, so the driver switched to `--hash` before any model was served. Cost: about $0.08, plus about $2.00 for the run.

## Results (accuracy = the higher of P(A) and P(B) is the correct letter; 240 prompts per type)

| model | own report | own vote | contact majority | pass | mean non-A/B mass (report / vote / majority) |
|---|---|---|---|---|---|
| Llama-3.1-8B-Instruct | 0.954 | 1.000 | 0.950 | **pass** | **0.33 / 0.62 / 0.79** |
| Gemma-2-9B-IT | 0.908 | 1.000 | 0.983 | **pass** (report: narrowly) | 0.03 / 0.15 / 0.04 |
| Qwen3.5-9B | **0.867** | 0.958 | 0.996 | **FAIL** (report) | 0.02 / 0.01 / 0.01 |
| Gemma-3-27B-IT | 0.996 | 1.000 | 1.000 | **pass** | 0.00 / 0.00 / 0.00 |
| Qwen3.5-27B | 1.000 | 1.000 | 1.000 | **pass** | 0.00 / 0.00 / 0.00 |

## Where the errors are (pre-stated diagnostics; `results/summary.json`)

**Qwen3.5-9B, own report (0.867).**

| split | accuracy |
|---|---|
| own vote agrees with the report / disagrees | 0.974 / **0.770** |
| contacts mostly agree with the report / tie / mostly disagree | 0.978 / 0.918 / **0.743** |
| correct letter B / A | 0.957 / **0.782** |
| correct option listed first / second | 0.915 / **0.820** |
| report accuracy 3/5 / 3/4 / 9/10 | 0.867 / 0.851 / 0.880 |

When the agent's own vote or its contacts point away from its report, the model often answers with the vote or the
board. It also leans toward the letter B and toward the option listed first. Report strength makes little difference.

**Gemma-2-9B** shows the same pattern, more mildly: own-report accuracy is 0.841 when its vote disagrees with the
report, and 0.982 when they agree.

**Llama-3.1-8B** ranks A against B correctly, but most of its probability goes to other tokens: on average 0.79 for
the contact-majority question and 0.62 for own vote. It does not answer in the requested one-letter format.

## What this means for the next gates (for the owner)

1. **Qwen3.5-9B: options.**
   - (a) Revise the board wording on the development bank only, then re-run S3 for all five models (about $2). A
     revision could label the report more distinctly, or place it next to the question. The brief already
     pre-registers several wordings as a random factor, so each wording would need to pass S3.
   - (b) Keep Qwen3.5-9B with the failure on record. Its own-vote and contact answers pass, but its kernel would mix
     report-reading errors into evidence response.
   - (c) Replace it. The Qwen pair was pencilled.

   Recommendation: (a). The failure is a context-interference pattern that wording can plausibly fix, and Gemma-2
   shows the same pattern at a milder level.
2. **Llama-3.1-8B's non-A/B mass** goes to the protocol. Votes are sampled from the A/B probabilities renormalised at
   decision noise T, with non-A/B mass recorded. A model that puts 60–80% of its mass elsewhere is answering a
   different format.
   - S4/S5 should report the mass at the vote question. A wording revision under (a) could also tighten the answer
     format.
   - Any rule for excluding a call or a model on non-A/B mass must be set before data.
3. **S3 tested one wording.** The pre-registered prompt-sensitivity factor (several wordings) needs each wording to
   pass S3 before it is used.
