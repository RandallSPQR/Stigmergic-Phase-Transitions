# Gate S3, round 2: wording revision (owner-approved, 2026-11-01). Plan committed before any model call.

**Why.** In round 1, Qwen3.5-9B failed the own-report question (0.867). Its errors came from interference: its own vote
or its contacts pulled its answer away from its report. Gemma-2 showed the same pattern mildly. Llama-3.1-8B put most
of its probability outside A/B. The owner chose option (a): revise the wording on the development bank and re-run S3.
This is a prospective change, logged as coordination A12. Round 1's results stay on record.

**Wordings** (`stpt/prompts.py`). Every wording carries the same content: question, options, report text, own vote,
contacts.
- **W1:** round 1, unchanged.
- **W2, structured:** labelled sections. The board (own vote, contacts) comes first; the private report comes last,
  quoted, next to the question.
- **W3, minimal change:** W1's order, with the report labelled and quoted and the votes labelled.
- W2 and W3 end every question with "Reply with exactly one letter, A or B, and nothing else."

**Prompts** (`prompts/s3_round2_prompts.json`, sha256 in `prompts/SHA256_round2`):
- Round 1's 720 contexts, rendered in W2 and W3: 1,440 comprehension prompts. W1 re-renders byte-identically on all
  720 contexts, so the wordings compare like for like.
- 240 contexts × W1, W2 and W3 with the actual **vote question**: 720 readouts that measure non-A/B mass where it
  matters. They are reported and not scored, because the non-A/B rule is still the owner's decision.

**Decision rule (fixed now).**
1. A wording is **valid** if all five models score ≥ 0.90 on each of the three comprehension types with it. W1's
   round-1 results count for W1, which is therefore not valid, because Qwen3.5-9B scored 0.867.
2. **The study's wording set = the valid wordings.** If more than one is valid, they form the pre-registered
   prompt-sensitivity factor. They are chosen on comprehension only, never on any vote or outcome.
3. **If no wording is valid for all five,** S3 is reported per model and wording, and the next step is the owner's.

**Run.** Same pod setup as round 1: RTX PRO 6000 Blackwell, pipeline v1.2.0 checked by `check_pin`, one server start
per model (its ID recorded), weights re-hashed to their pins. Hard cap 1.5 h; expected about 35 min, about $1.50.
Outputs: `artifacts/<run>/`, `results/round2_summary.json`, `S3_REPORT.md` (section "Round 2").
