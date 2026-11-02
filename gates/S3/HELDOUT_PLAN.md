# Gate S3, held-out wording check (owner's instruction, 2026-11-02). Plan committed before any model call.

**Why.** Round 2 chose W3 on the same 720 contexts that showed round 1's failure, so its pass could be fitted to those
contexts. The owner asked for a held-out check on a fresh set, together with two or three new W3 variants, so that the
prompt-sensitivity analysis can have more than one valid wording. Logged prospectively as coordination A14.

**Fresh set** (`prompts/s3_heldout_contexts.json`, built by `make_prompts_heldout.py`):
- Development bank only, round 1's procedure and eligibility: 240 contexts per question type (720), new seed
  `S3-heldout-v1`. The factored draw reproduces round 1's 720 contexts exactly with round 1's seed (checked on every
  run).
- No context repeats round 1's (scenario, allocation, position, own vote, contact pattern and layout): overlap 0.
- Correct letter A: 117 / 116 / 113 of 240 for own report / own vote / contact majority. 487 of the 720 contexts are
  informed positions.

**Wordings** (`stpt/prompts.py`, `TEMPLATES` and `QUESTIONS`). Same structure as W3: the same order (introduction,
question, options, the private report labelled and quoted in place, own vote, contacts or the blind line, question)
and a strict one-letter instruction. Phrasing and label text differ.

| | W3 (round 2) | W4 | W5 | W6 |
|---|---|---|---|---|
| report label | Your private report: | Private report you hold: | The report you received privately: | Your own report (no one else sees it): |
| own vote | Your current vote: | Your vote at the moment: | How you are voting right now: | Your own vote so far: |
| contacts | Votes currently shown by the 4 people you are connected to: | Your 4 connections' votes at the moment: | How the 4 people linked to you are voting right now: | Latest votes of your 4 contacts: |
| vote question | Which option do you vote for now? | Which option is your vote now? | Which choice do you vote for now? | What is your vote now? |
| instruction | Reply with exactly one letter, A or B, and nothing else. | Answer with one letter only, A or B, and no other text. | Respond with a single letter, A or B, and nothing more. | Give exactly one letter, A or B, with nothing else. |

The introductions, option headers and blind lines differ as well (full text in `stpt/prompts.py`). Lint
(`lint_same_content`, run on every context, live and blind): every wording carries the question, both options in the
listed order, the report text verbatim, the own-vote letter, the contact letters in contact order, and the final
question, in that order, in 13 lines. `tests/test_prompts.py` checks that the shared template renders W3 byte for byte
as round 2 did.

**Prompts** (`prompts/s3_heldout_prompts.json`, 3,840 prompts, sha256 `3edfcd891093efae…`, full hash in
`prompts/SHA256_heldout`):
- 720 contexts × 4 wordings with their comprehension question: 2,880 scored prompts.
- 240 own-vote contexts × 4 wordings with the actual vote question: 960 readouts, measured (non-A/B mass, share of A),
  not scored.

**Decision rule (fixed now).**
1. A wording is **valid** if all five models score ≥ 0.90 on each of the three comprehension types on the held-out
   set. The same rule applies to W3 and to each variant. Scoring is unchanged from round 1: the answer is the letter
   with the higher log-probability.
2. **W3 must pass to remain the primary wording.** If W3 fails, S4 does not start; the results are reported and the
   next step is the owner's.
3. If W3 passes, **the study's wording set = W3 (primary) plus every valid variant**, chosen on comprehension only,
   never on any vote or outcome. S4 starts straight after (owner's approval of 2026-11-02) with that set.
4. Round 2's W3 result stays on record; the held-out result is the binding one for every wording.

Also reported, not pass/fail: mean P(correct) renormalised over A and B; non-A/B mass and share of A at the vote
question; own-report accuracy split by own-vote agreement and by contact agreement (the interference diagnostics of
round 1).

**Run.** Round 2's setup: one RTX PRO 6000 Blackwell pod, pipeline v1.2.0 checked by `check_pin`, one server start per
model (its ID in the manifest), weights re-hashed to their pins, prompts rendered on the pod from the compact contexts
and checked against the committed sha256. Hard cap 1.5 h (about $3.74); expected about 35 min, about $1.50.
Outputs: `artifacts/<run>/`, `results/heldout_summary.json`, `S3_REPORT.md` (section "Held-out check").
