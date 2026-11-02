# Decision noise T (decided 2026-11-02; coordination D23 / A18; prospective, no live data exists)

## Decision
- **Primary regime (C): per-model T with a Bayesian anchor.** Each model's T is set so that its response to a lone
  3/4 report equals that report's **Bayesian posterior, 0.75** (50/50 prior, LR 3).
  - T_m = R_m(3/4) / ln 3, where R_m(3/4) is the model's mean logit toward the reported option. Source: S5, W3, blind,
    averaged over 6 development stories, both directions, both own votes and 4 layouts.
  - This is a calibration to a stated standard, not a tuned constant. It uses the blind response to evidence only,
    never the board.
- **Secondary regime (A): T = 1 for every model (native sampling).** It runs on a seeded share of graphs and
  allocations (the share is set at S9). No power target. The confirmatory tests use C.
- **Values** (`analysis/results/t_options.json`; fixed now, used for every wording of the model, for the initial vote,
  and for every update):

  | model | Llama-3.1-8B | Gemma-2-9B | Qwen3.5-9B | Gemma-3-27B | Qwen3.5-27B |
  |---|---|---|---|---|---|
  | T (C) | 0.50 | 2.15 | 1.78 | 10.40 | 2.88 |

## Pre-registered with it (owner's items)
1. **The anchor is Bayesian.** Every report and the protocol state T as "calibrated so that a lone 3/4 report gives
   its Bayesian posterior (0.75)".
2. **How far the calibration generalises.** Under C, each model's response to a lone 9/10 source is reported against
   Bayes (0.90), and to a 3/5 source against 0.60. These are signed misses and per-story ranges, a diagnostic of how
   un-Bayesian each model's strength response is. Development values (`analysis/results/t_checks.json`):

   | model | 3/5 (Bayes 0.60) | 9/10 (Bayes 0.90) | 9/10 per story |
   |---|---|---|---|
   | Llama-3.1-8B | 0.70 (+0.10) | 0.77 (−0.13) | 0.72–0.85 |
   | Gemma-2-9B | 0.69 (+0.09) | 0.83 (−0.07) | 0.76–0.88 |
   | Qwen3.5-9B | 0.71 (+0.11) | 0.79 (−0.11) | 0.76–0.80 |
   | Gemma-3-27B | 0.72 (+0.12) | 0.78 (−0.12) | 0.77–0.80 |
   | Qwen3.5-27B | 0.68 (+0.08) | 0.78 (−0.12) | 0.74–0.80 |

   Every model, once matched at 3/4, **compresses** the strength scale: it over-trusts the weak source and
   under-trusts the strong one. Gemma-2-9B compresses least. (Probabilities are σ(mean logit / T), the definition the
   anchor uses.)
3. **Llama-3.1-8B is the honest exception, reported as the weakly social agent, not as a failure.**
   - The measured contact response (S4 development probes, uninformed live agents, at its T) is the change in P(content
     A) from 0 to 4 contacts showing A, averaged over own vote. It is 0.20 for Llama, against 0.59–0.77 for the other
     four models. Against a 4–0 majority opposing its own vote, Llama follows with P about 0.5.
   - So it is **weakly**, not entirely, non-social. The study reports it with that number, as the within-study
     contrast for what social processing adds: a model that reads its evidence and largely ignores the board.
   - Its board effect and pulse persistence are reported in that light, in the per-model estimates and the
     comprehension moderator table (D21).
   - It stays in the pooled confirmatory set (D21).
4. **Gemma-3-27B at T ≈ 10.4 is well-behaved on development data.** Seven checks were fixed before computing
   (`analysis/T_CALIBRATION_CHECKS.md`); none flags (`analysis/results/t_checks.json`).
   - **G1, contact gradient:** strictly increasing for both own votes (0.23 → 0.86 and 0.13 → 0.76).
   - **G2, saturation:** P > 0.99 in 0% of probes, as for the others.
   - **G3, ceiling pile-up:** 0.2% of probes within 0.5 nats of its largest |ℓ| (23.1). Its logits are graded, not
     clipped.
   - **G4, resolution:** the bf16 step at its median |ℓ|, divided by T, is 0.006 nats.
   - **G5, presentation effects at T:** letter 0.24 and option order 0.21 nats, within the others' range (up to 0.34
     and 0.45).
   - **G6, report vs an opposing contact majority:** P(follow the report) is 0.47, against 0.45–0.57 for the others.
   - **G7, between-start shift at T:** 0.005.

   The rescale leaves it inside the other models' envelope on every check, not only at the anchor.

## Side findings for the kernels and S8 (descriptive)
- **Non-monotone contact gradients.** At their own T, two models are not strictly monotone in the contact count for
  every own vote:
  - Gemma-2-9B with own vote B: 0.07, 0.50, 0.45, 0.64, 0.85;
  - Llama with own vote A: 0.49, 0.64, 0.70, 0.67, 0.72.

  A rescale cannot create or remove a reorder, so these are native. Each cell has 20 development probes across
  scenarios. The fresh kernels (estimated with uncertainty) will show whether they persist.
- **Between-start shift at T** (S_p / T): Llama 0.036 (its T < 1 amplifies it), all others ≤ 0.011. Blocking is
  mandatory anyway (A16). S9 uses the variance components scaled by 1/T.
