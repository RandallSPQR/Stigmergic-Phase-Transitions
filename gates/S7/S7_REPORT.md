# Gate S7: branch isolation, 2026-11-02

**Verdict: S7 PASSES.**
- Main trajectories are byte-identical with and without probes and display-pulse branches. This holds with a mock
  model on CPU (both initial-vote rules, with a detected negative control) and with every one of the five real models,
  in one server start each.
- Reversal branches are rung 1b and were not built, per the brief.

Plan: `S7_PLAN.md`, committed before any S7 model call. Harness: `stpt/board.py`; runner `s7_core.py`.
Results:
- `results/s7_cpu.json`;
- `results/s7_gpu_summary.json`;
- raw: `artifacts/20261102T2054Z/` (full records of every scenario, per model).

## CPU (mock model; `results/s7_cpu.json`)
Every check passes for both initial-vote rules (D25):
- C1/C2: main records and final state identical with probes, with branches, and with both.
- C3: unpulsed branches equal the main continuation.
- C4: pulse displays altered for recipients only, then restored, with the same agents and draws.
- C6: save/restore through JSON.
- C7: live and blind runs share the initial state and draws; the blind board shows no contacts.
- C8: placeholder balanced within evidence types (imbalance ≤ 1).
- C9: letter mapping 50/50.

**Negative control:** a mock model whose output drifts with the number of calls served is detected (C1 and C3 fail).

## GPU (`results/s7_gpu_summary.json`)
- Pod `z1kf6jnyjwra7l`, RTX PRO 6000; pipeline v1.2.0 checked by `check_pin`; weights re-hashed; payload sha256
  `8e112a417f5acd1e…` verified on the pod.
- One cold start per model (IDs in the manifests). Each model ran at its D23 T, under rule (i).
- 1,369 model calls per model, in this order within one start:
  1. base, 200 updates;
  2. the same with 19 probes and pulsed plus unpulsed branches of 50 updates at steps 60 and 130, interleaved;
  3. the blind run of the pair;
  4. base again.
- About 37 min, about $1.55. The pod removed itself after its last upload.

| model | C1 main identical (base = full = again) | C2 final state | C3 unpulsed = main | C4 pulse | C6 save/restore | C7 live/blind start and draws | letters 50/50 | pass |
|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B (secondary) | yes | yes | yes | yes | yes | yes | yes | **yes** |
| Gemma-2-9B | yes | yes | yes | yes | yes | yes | yes | **yes** |
| Qwen3.5-9B | yes | yes | yes | yes | yes | yes | yes | **yes** |
| Gemma-3-27B | yes | yes | yes | yes | yes | yes | yes | **yes** |
| Qwen3.5-27B | yes | yes | yes | yes | yes | yes | yes | **yes** |

Interleaving probes, branches and a blind run on the same server never changed a main readout.

## Note for S8 (pulse mechanics)
- In these test settings (5 recipients, N = 100, duration 20 steps), the number of recipient updates that fell
  inside a pulse was 0–2 per pulse. That is about 5 × 20 / 100 = 1 expected. A pulse is only a treatment if recipients
  update while it is on.
- The S8 pilot sets recipients, k and duration so that recipients update during the pulse. For example, a duration of
  several sweeps, or a larger r.
- This is a design parameter, not an isolation issue.
