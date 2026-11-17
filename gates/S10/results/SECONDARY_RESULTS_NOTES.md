# S10 secondary results: owner's follow-ups (D67), from registered outputs only

Source for every number: `gates/S10/results/secondary_results.json` (StPT `aa3168b`, sha256 `fd581946…56d6`), produced
at tag `stpt-secondary-v1`. No new analysis. All items are **secondary** (registration §6: no power target; no Holm).

## 1. ±0.03 TOST on the pooled social persistence component (secondary)
The pooled social part comes from the self/social decomposition on the 33 self-reset clusters, pooled over the four
confirmatory models. The model is the confirmatory one: the server-start block random effect, REML, Satterthwaite df.

| component | θ | 95% CI | 90% CI | df | p (two-sided) | TOST ±0.03 |
|---|---|---|---|---|---|---|
| social | +0.0083 | [−0.0136, +0.0303] | **[−0.0097, +0.0264]** | 14.3 | 0.43 | **equivalent**: the 90% interval lies inside ±0.03 |
| self (beside it) | +0.0486 | [+0.0237, +0.0735] | [+0.0282, +0.0690] | 14.1 | 0.0009 | not equivalent |

**Conclusion (secondary):** the pooled social component is equivalent to zero within ±0.03. That is, the data
exclude a social contribution to recipients' persistence larger than 0.03 in either direction, at α = 0.05.

## 2. Board effect in each variant wording (secondary; choice A)
The table gives each variant arm's own board-effect estimate, from the same model, beside the model's 61-cluster W3
estimate. "Crosses zero" is read two ways:
- **Sign:** the estimate's sign is opposite to W3's.
- **CI:** the 95% interval includes 0.

| model | W3 (61 clusters) | variant | clusters | board effect, variant | 95% CI | sign opposite to W3 | 95% CI includes 0 |
|---|---|---|---|---|---|---|---|
| Gemma-2-9B | +0.0559 [+0.0372, +0.0745] | W5 | 11 | −0.0198 | [−0.0601, +0.0204] | **yes** | yes |
| Qwen3.5-9B | +0.0709 [+0.0573, +0.0845] | W4 | 18 | +0.0178 | [−0.0039, +0.0394] | no | yes |
| Gemma-3-27B | +0.0847 [+0.0702, +0.0992] | W4 | 16 | +0.1025 | [+0.0507, +0.1542] | no | no |
| | | W5 | 10 | +0.0136 | [−0.0247, +0.0520] | no | yes |
| | | W6 | 6 | +0.1186 | [+0.0698, +0.1674] | no | no |
| Qwen3.5-27B | +0.0489 [+0.0360, +0.0618] | W4 | 8 | −0.0158 | [−0.0464, +0.0147] | **yes** | yes |
| | | W5 | 11 | +0.0148 | [−0.0116, +0.0413] | no | yes |
| | | W6 | 9 | −0.0076 | [−0.0440, +0.0289] | **yes** | yes |
| Llama-3.1-8B (W3 negative) | −0.0299 [−0.0541, −0.0057] | W4 | 12 | +0.0090 | [−0.0046, +0.0227] | **yes** | yes |
| | | W5 | 11 | −0.0350 | [−0.0655, −0.0045] | no | no |

**Across the four confirmatory models:**
- Three variant estimates have the opposite sign to W3: Gemma-2-9B W5, Qwen3.5-27B W4 and Qwen3.5-27B W6. In every
  one of them the 95% interval includes 0.
- No variant estimate is significantly opposite in sign to W3.
- Six of the eight confirmatory-model variants have a 95% interval that includes 0. Only Gemma-3-27B's W4 and W6
  exclude it, both positive.

The variant arms are small (6–18 clusters), so their intervals are wide.

## 3. Note: the display pulse reaches only recipients, so the social channel is a second-order loop
By design (registration §4, D26), only the r = 10 recipients of a pulsed branch see altered displays: k = 3 of their
4 contacts are shown in the pulse direction for D = 3 sweeps. No other agent ever sees an altered display. A social
contribution to recipients' persistence therefore has to run through a second-order loop:
1. the recipients' changed votes are shown to their neighbours;
2. the neighbours shift;
3. the recipients then see their neighbours' shifted votes after restoration.

The registered propagation outcome measures how far the pulse spread beyond that loop. It covers the agents at graph
distance ≥ 2 from every recipient: not a recipient and not a recipient's neighbour (`analysis/pulse_design.py`;
`secondary._pool`), an average of 58 agents per branch. Their share voting the pulse direction, pulsed minus
unpulsed, pooled over the four confirmatory models, is:
- **+0.0038 [+0.0028, +0.0048]** over the D + W sweeps from onset (choice D);
- +0.0053 [+0.0039, +0.0068] over the W sweeps after restoration.

**What this does and does not show.** The pool leaves out the recipients' neighbours (distance 1), which are the
loop's middle link. Propagation therefore does not bound the neighbours' shift directly. It is indirect evidence that
the pulse spread very little beyond the recipients, which limits how much the loop could build. The measured social
part agrees: +0.0083 [−0.0136, +0.0303], equivalent to zero within ±0.03 (item 1). No registered output measures the
neighbours' own shift; measuring it would be an exploratory analysis and needs the owner's approval first.
