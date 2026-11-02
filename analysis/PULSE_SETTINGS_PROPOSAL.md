# Display-pulse settings for S8: proposal (for the owner's approval, 2026-11-02)

**Basis.** These are simulations with development proxy kernels. No live board has run. Source:
`analysis/pulse_design.py`, output `analysis/results/pulse_design.json`.
- Each model's kernel is fitted at its D23 T to the S4 W3 live probes:
  - uninformed agents: P(keep own vote), by the number of contacts showing it;
  - informed agents: P(vote the reported option), by own-vote agreement and the number of contacts showing it.
- Boards: N = 100, random-regular d = 4; D18 evidence; initial votes by rule (i).
- A 5-sweep burn-in, then a saved state, then pulsed and unpulsed branches with common random numbers, as the harness
  does.
- 400 branch pairs per setting on 8 graphs.
- Grid: k ∈ {2, 3, 4} altered contacts, duration D ∈ {1, 2, 3, 5} sweeps (1 sweep = N = 100 updates), r ∈ {5, 10, 20}
  recipients.
- The proxy kernels are coarse (8–40 probes per cell) and miss call-level and between-start noise, so the absolute
  numbers are optimistic. They rank settings; they do not size the study (S9 does).

**Rule for choosing (fixed by the brief and D17's spirit).** Settings are chosen on **exposure and immediate response**
(whether the manipulation reaches recipients and moves them while it is on), and on the size of the propagation pool.
They are **never chosen on persistence**, which is the confirmatory outcome. Persistence is reported below for
information only.

## Proposal

| setting | proposal | reason |
|---|---|---|
| **Duration D** | **3 sweeps (300 updates)** | The shortest duration at which recipients reliably update while the pulse is on: expected exposure 0.95 (1 sweep 0.63, 2 sweeps 0.86). S7 showed that a short pulse can miss its recipients. |
| **Altered contacts k** | **3 of 4** | The pulse direction is then the recipient's displayed majority whatever the real votes (3–1 or 4–0), and one real display stays visible, so the pulse alters the board rather than replacing it. k = 2 can leave a 2–2 tie. k = 4 replaces the whole view. |
| **Recipients r** | **10 (10% of the board)**, drawn by their own seed, independent of evidence | Keeps the propagation pool (agents at distance ≥ 2 from every recipient, never exposed) at about 58 of 100. With r = 20 it shrinks to about 32 and recipients' neighbourhoods overlap. r = 5 gives a noisy recipient mean. |
| **Direction** | randomised A/B, **balanced within each server-start block** (half toward A) | As the brief says. The direction relative to the truth (toward the correct or the incorrect option) is reported as a secondary split. |
| **Pulse time t0** | **a fixed update time: after 5 sweeps (500 updates)** | After the start-up transient, the blind board is near stationary within 2 updates per agent (D25). The S8 pilot checks the live board. |
| **Persistence window W** | **5 sweeps after restoration**. The outcome is recipients' share voting the pulse direction, averaged over the window, pulsed minus unpulsed. The share at the window's end is reported as secondary. | Each recipient updates about 5 times after restoration. This was fixed before the simulation was read. |
| **Branches** | at t0, **2 pulsed branches per saved state** (independent recipient sets; one toward A, one toward B), one pulse per branch | The **unpulsed branch is the main continuation itself** (S7 C3: byte-identical under common random numbers), so it costs no extra calls. Each pulsed branch costs (D + W) × N = 800 calls. |
| **Horizon** | the main trajectory runs at least t0 + D + W = 13 sweeps | The operational horizon itself is set in the S8 pilot. |

## Simulated outcomes at the proposal (k = 3, D = 3 sweeps, r = 10)

| model | exposure | immediate response (during the pulse) | persistence (5-sweep window; information only) | at the window's end | propagation |
|---|---|---|---|---|---|
| Gemma-2-9B | 0.95 | 0.158 | 0.061 | 0.007 | 0.004 |
| Qwen3.5-9B | 0.95 | 0.152 | 0.078 | 0.030 | 0.004 |
| Gemma-3-27B | 0.95 | 0.151 | 0.074 | 0.020 | 0.005 |
| Qwen3.5-27B | 0.95 | 0.141 | 0.057 | 0.012 | 0.004 |
| Llama-3.1-8B (secondary) | 0.95 | 0.045 | 0.019 | — | — |

- On these kernels, a pulse moves recipients by about 0.15 while it is on. After restoration it leaves a mark averaging
  about 0.06–0.08 over the window, which **mostly fades within 5 sweeps**. Propagation beyond the recipients'
  neighbourhoods is very small.
- On the proxy kernels, about 30 branch pairs per model would give 80% power at a 0.05 persistence effect. This is
  optimistic, and S9 sizes the study with measured kernels and every variance component.
- Llama, the weakly social comparison agent, responds about a third as much, as D23 predicts.

## What S8 then runs (once the settings are approved)
On the D18 difficulty region (sources {3/4, 9/10} and {3/5, 3/4, 9/10}, at f = 0.5; development bank):
- live and blind main runs per model, within server-start blocks;
- the two pulsed branches at t0;
- rule (ii) start runs, for the initial-vote comparison (D25).

Purpose, as the brief gives it:
- pulse mechanics in live use (exposure, immediate response);
- the operational horizon: when live and blind support settle;
- cost per run.

It also gives the live kernels for S9. S8 reports no confirmatory contrast. The run sizes and the cost cap will come
with the S8 plan for approval.
