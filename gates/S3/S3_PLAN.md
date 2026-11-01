# Gate S3: comprehension (development bank, branched), plan committed before any model call

**Pass rule (brief):** accuracy ≥ 0.90 for each question type, for each model. Each of the five models is judged on
its own; a model that fails is reported, and the next step for it is the owner's call.

**Question types.** 240 prompts each, from the development bank only:
- `own_evidence`: which option the agent's own report favours. Informed positions only.
- `own_vote`: the agent's own current vote.
- `contact_majority`: which option more of its 4 contacts show. Patterns 3–1 or 4–0 only.

**Prompts.** `gates/S3/prompts/s3_prompts.json`, 720 prompts, sha256 `0495d0062e48b29a…` (full hash in
`prompts/SHA256`). Built by `make_prompts.py` from the S2 development bank with a recorded seed. The board prompt is
the draft StPT template, `stpt/prompts.py`. Randomised per prompt and recorded: letter mapping, option order, contact
order, own vote, contact pattern, the scenario and its allocation. Correct letters are balanced: 120–124 A per type.

**Branched.** A comprehension question is the board context with the vote question replaced. Agents are memoryless,
so the branch is the whole call. Nothing feeds back into any trajectory, and no trajectory runs at S3.

**Scoring.** The pinned pipeline's exact readout gives log P(A) and log P(B), at batch size 1 with raw logprobs and
the canonical serializer. The answer is the option with the higher log-probability, so no sampling is involved.

Also reported (not pass/fail):
- mean P(correct) renormalised over A and B;
- non-A/B mass;
- accuracy split by report accuracy (3/5, 3/4, 9/10), by which letter is listed first, by letter mapping, and by
  contact pattern.

**Run.**
- One RTX PRO 6000 Blackwell pod (D12), pipeline v1.2.0 at its pinned commit (`check_pin` refuses any other), serving
  flags of v1.2.0 (D14).
- The five models in sequence, one server start each. Every model's run manifest records:
  - the server-start ID;
  - the pipeline identity block, the StPT commit, and `pins.yaml`;
  - the prompt-set sha256.
- Weights are verified at download by preflight `--hash` (bytes re-read; amended before any model was served: on the first pod the blob-name mode could not verify, because huggingface-hub 1.x cache blob names are not the LFS sha256) and deleted after each model.
- Results upload to the private HF dataset after every model.
- Hard cap 1.5 h (about $3.74); expected about 25 min, about $1. The watcher here terminates the pod on DONE or at the
  deadline.

Outputs: `gates/S3/results/<model>.json`, `gates/S3/results/summary.json` and `gates/S3/S3_REPORT.md`.
