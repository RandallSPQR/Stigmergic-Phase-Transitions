# Gate S3: comprehension (development bank, branched), 2026-11-01

**Verdict: S3 PASSES under round 2 (A12), with wording W3.**
- **Round 1, original wording W1:** 4 of 5 models passed; Qwen3.5-9B failed own-report (0.867). Kept on record below.
- **Round 2:** the owner chose to revise the wording (A12). Two revisions ran on the same 720 contexts. **W3 is valid:**
  all five models pass all three types. **W2 is not:** Gemma-2's own-vote accuracy is 0.683.
- Under the rule fixed before round 2, **the study's wording set is {W3}**.
- W3 also removes the answer-format problem: non-A/B mass at the vote question is 0.0–0.3% for every model.
- Qwen3.5-9B passes at exactly the threshold (0.900).

## Round 1 (W1)

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

## Round 2 (A12): wordings W2 and W3 on the same 720 contexts

Plan: `ROUND2_PLAN.md` (rule fixed before any call). Prompts: `prompts/s3_round2_prompts.json`, sha256 `e7d6a316…`. They
were rendered on the pod from the compact contexts and matched the committed hash.

Run details:
- The pod `8258g4pbif2xhh` ran all five models in about 20 min, roughly $0.85. Pipeline v1.2.0 was checked by
  `check_pin`, weights were re-hashed to their pins, and each model had one server start with its ID in the manifest.
- An earlier round-2 pod (`83hfku47mkxrf0`) never started its container (RunPod host problem). It was terminated after
  32 min, roughly $1.30. The watcher now terminates any pod whose container has not started after 10 min.
- An earlier launch was refused by RunPod because the request body was too large, so prompts are now rendered on the
  pod.
- Results: `artifacts/20261101T1755Z/`, `results/round2_summary.json`.

**Accuracy (own report / own vote / contact majority; pass is ≥ 0.90 on each)**

| model | W1 (round 1) | W2 | **W3** |
|---|---|---|---|
| Llama-3.1-8B | 0.954 / 1.000 / 0.950 | 0.971 / 1.000 / 1.000 | **0.963 / 1.000 / 0.996** |
| Gemma-2-9B | 0.908 / 1.000 / 0.983 | 1.000 / **0.683** / 0.992 | **1.000 / 0.942 / 1.000** |
| Qwen3.5-9B | **0.867** / 0.958 / 0.996 | 0.938 / 0.908 / 0.908 | **0.900 / 0.979 / 0.971** |
| Gemma-3-27B | 0.996 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | **1.000 / 1.000 / 1.000** |
| Qwen3.5-27B | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | **1.000 / 1.000 / 1.000** |
| **valid for all five?** | no (Qwen3.5-9B) | no (Gemma-2 own vote) | **yes** |

**Non-A/B mass at the actual vote question (240 contexts per wording; measured, not scored)**

| model | W1 | W2 | W3 |
|---|---|---|---|
| Llama-3.1-8B | 0.377 | 0.000 | 0.000 |
| Gemma-2-9B | 0.425 | 0.001 | 0.001 |
| Qwen3.5-9B | 0.007 | 0.002 | 0.003 |
| Gemma-3-27B | 0.593 | 0.000 | 0.000 |
| Qwen3.5-27B | 0.000 | 0.000 | 0.000 |

W1's plain "Answer with a single letter" let three models put 38–59% of their probability elsewhere. W3's strict
instruction ("Reply with exactly one letter, A or B, and nothing else") brings that to about zero. That largely settles
the question of a non-A/B rule: under W3, the vote is almost entirely A or B.

## What carries forward

1. **The study's wording is W3** (`stpt/prompts.py`, `render("w3", …)`), from S4 onward. W1 and W2 are retired: W1
   failed Qwen3.5-9B, and W2 failed Gemma-2's own vote.
2. **Qwen3.5-9B passes at the threshold.** Its own-report accuracy under W3 is 0.900: 216 of 240, one answer above
   the line. Interference remains: 0.817 when its own vote disagrees with its report, against 0.991 when they agree.
   Its kernel will carry some of that.
3. **Prompt-sensitivity factor.** The brief pre-registers several wordings as a random factor, but only one is valid
   so far. A random factor needs at least two valid wordings. Further variants of W3 would each have to pass S3 for all
   five models first. This is the owner's decision.
4. **Letter preference at the vote question.** The Gemma models choose A on 40–42% of vote readouts under W3, although
   letters are randomised per call. S4 and S5 measure this, and the randomisation and analysis already absorb it.
