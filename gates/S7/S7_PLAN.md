# Gate S7: branch isolation. Plan committed before any S7 model call.

**Approval.** The owner said "Proceed to the next gate" on 2026-11-02, after D25. That covers S7, including its small
GPU confirmation, about $1.50.

**Brief gate row.** Main trajectories are byte-identical with and without probes, reversal branches and pulse
branches. Exact. Reversal branches are rung 1b and are not built (brief), so S7 covers probes and display-pulse
branches.

## The harness under test (`stpt/board.py`)
- **Random numbers are counter-based.** Every number is a fixed function of (run key, purpose, index): agent choice,
  vote draw, layout, placeholder, recipients and pulse contacts. So:
  - live and blind runs of a pair share every draw and the initial state;
  - a branch from a saved state uses the main trajectory's numbers from that step on (common random numbers);
  - probes and branches never consume the main trajectory's numbers.
- **Initial vote (D25):** rule (i), the W3 blind evidence-only call with a balanced placeholder own vote; or rule (ii),
  a seeded 50/50 start.
- **Updates:** random-sequential with replacement; votes drawn at T (D23); letter mapping balanced in consecutive
  pairs of calls (D20).
- **Probes** read the state and never write it (asserted by state digest).
- **Pulses** override what a recipient is shown of k contacts, for a fixed number of steps. Real votes are untouched
  (asserted). Displays restore when the duration ends.

## Part 1, CPU (`run_s7_cpu.py`, a deterministic mock model; done before this plan was committed)
Results: `results/s7_cpu.json`, with **all checks passing for both initial-vote rules**:
- C1: main records identical with and without probes, branches, and both.
- C2: final state identical.
- C3: the unpulsed branch reproduces the main continuation byte for byte.
- C4: pulse displays are altered at the start for recipients only, restored at the end, with the same agents and
  draws as the unpulsed branch.
- C6: save/restore through JSON reproduces the continuation.
- C7: live and blind runs share the initial state, agents and draws; the blind board shows no contacts.
- C8: placeholder imbalance ≤ 1 within every evidence type.
- C9: letter mapping exactly 50/50.
- **Negative control:** a mock model whose output drifts with the number of calls it has served is detected (C1 and C3
  fail), so the checks can see a leak.
- Recorded honestly: the first CPU draft asked that a pulse visibly alter at least one recorded call. That fails by
  chance, because recipients may not be drawn to update during a short pulse. It was replaced, before any GPU call, by
  the direct display checks in C4. The number of calls that saw the pulse is still reported.

## Part 2, GPU (`gpu/s7_driver.sh`; one cold server start per model, all five)
The question is whether interleaving extra calls on the same server ever perturbs the main readouts. Only a real
server can show this.

**Inputs** (`inputs/s7_inputs.json`, payload sha256 in `inputs/PAYLOAD_SHA256`):
- graph: random-regular d = 4, N = 100, seed `S7-graph-v1`, fingerprint `3a32ab2916ca941d`;
- allocation: development representative `dev-bridge-A`, one report per position;
- W3; each model at its D23 T; rule (i).

**In one start, in this order:**
1. **base:** H = 200 main updates.
2. **full:** the same, with a probe every 10 steps, and pulsed plus unpulsed branches of 50 updates at steps 60 and
   130 (5 recipients, k = 2, toward A, duration 20). The branches run before the main continues, so their calls
   interleave.
3. **blind:** the blind run of the pair, 50 updates.
4. **again:** base repeated.

About 1,370 calls per model.

**Pass, per model, exact:**
- C1: base, full and again have identical main records.
- C2: identical final state.
- C3: the unpulsed branches equal the main continuation.
- C4: pulse displays altered and restored as specified, with the same agents and draws.
- C6: save/restore reproduces the continuation.
- C7: live and blind initial states, agents and draws identical.
- C9: letter mapping 50/50.

**If any check fails for any model, S7 stops,** and the failure is reported to the owner.

**Run.** One RTX PRO 6000 pod; pipeline v1.2.0 checked by `check_pin`; weights re-hashed; the server-start ID in each
manifest. Hard cap 1.5 h; expected about 40 min, about $1.70.

Outputs: `artifacts/<run>/`, `results/s7_gpu_summary.json`, `S7_REPORT.md`.
