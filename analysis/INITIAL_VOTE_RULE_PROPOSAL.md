# Initial-vote rule: proposal and expected effect on development data (for the owner's approval, 2026-11-02)

**Proposed (owner's item 4).**
- **Primary, rule (i):** each agent's first vote is sampled, at its model's T (D23), from its own blind, evidence-only
  response.
- **Sensitivity arm, rule (ii):** a random 50/50 start (seeded), pre-registered.

**How rule (i) is implemented.** The W3 frame always shows a current vote ("Your current vote: …"). So the first call
is the W3 **blind** board with the agent's evidence and a **seeded, balanced placeholder own vote**: half the agents
of each evidence type get A, half B. On average, balancing removes the placeholder's pull.
- This needs no new wording: the frame passed S3 and was measured at S5.
- The alternative is a new line ("You have not voted yet"). That is new text, so it would have to pass S3 before use.
  Not recommended.

## Expected effect (development data only; `analysis/initial_vote.py` → `analysis/results/initial_vote.json`)
Inputs:
- From S5 (W3, blind, at each model's T): a = P(vote the reported option | own vote = it), b = P(vote it | own vote =
  the other). Rule (i)'s first vote follows the report with q0 = (a + b)/2; rule (ii) with 0.5.
- **Blind board:** each agent is a two-state chain. After k of its own updates, q_k = π + (q0 − π) λ^k, where
  π = b/(1 − a + b) and λ = a − b (0.03–0.36 across models and sources).
- **Uninformed agents** start near 0.5 under both rules.

**Support for the truth, D18 setting** (f = 0.5, sources 3/4 and 9/10, generative expectation):

| model | rule (i), k = 0 | rule (ii), k = 0 | rule (i), k = 1 | rule (ii), k = 1 | both, k = 2 | stationary |
|---|---|---|---|---|---|---|
| Gemma-2-9B | 0.588 | 0.500 | 0.590 | 0.588 | 0.590 | 0.590 |
| Qwen3.5-9B | 0.584 | 0.500 | 0.600 | 0.584 | 0.600–0.603 | 0.603 |
| Gemma-3-27B | 0.585 | 0.500 | 0.594 | 0.585 | 0.594–0.595 | 0.595 |
| Qwen3.5-27B | 0.582 | 0.500 | 0.600 | 0.582 | 0.600–0.603 | 0.605 |
| Llama-3.1-8B (secondary) | 0.551 | 0.500 | 0.565 | 0.551 | 0.565–0.568 | 0.569 |

On the 64 representative development allocations (their actual reports), rule (i) starts at 0.560–0.564 mean support
(range 0.52–0.60 across allocations) for the four confirmatory models. Rule (ii) starts at 0.500.

**What this means:**
1. **On the blind board, rule (i) is rule (ii) advanced by one blind update.** After one update from a 50/50 start, an
   informed agent's expected vote is exactly (a + b)/2. By two updates per agent, the rules differ by ≤ 0.003 in
   expected support. **At any operational horizon of a few sweeps, the blind board does not depend on the rule.**
2. **On the live board they differ where it matters: the first rounds.** Under rule (ii), the first updates see
   contacts' votes that are pure noise about the truth. Under rule (i), contacts' first votes already carry the
   evidence: about 0.56–0.60 support, against 0.50. So rule (ii) delays and dilutes the social signal at the start,
   and with strong stickiness (S5, S6) early states persist.
   - The size of this on the live-minus-blind contrast needs the contact kernels. It is computed in the S8 pilot and
     the S9 simulation, not here.
3. **Rule (i) is the natural start** for agents who are given evidence before seeing anyone. Rule (ii) isolates the
   board from the evidence-driven start, which is a useful sensitivity arm. Pairing is unaffected: live and blind
   share the initial state in both rules, within one server start (D14).

**Recommendation:**
- Approve rule (i) as primary, implemented with the balanced placeholder own vote.
- Pre-register rule (ii) as the sensitivity arm, on a seeded share of graphs and allocations, with no power target.
- Have S8 and S9 report the live-board difference between the two rules.
