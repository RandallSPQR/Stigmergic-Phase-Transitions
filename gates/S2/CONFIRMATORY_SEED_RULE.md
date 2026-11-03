# Confirmatory clusters: seed rule (fixed 2026-11-03, coordination D29). Nothing is drawn yet.

The confirmatory bank has 26 stories × truth A/B = **52 specs** (`gates/S2/banks/confirmatory/`, D18 setting, schema v1.0,
validated, linted by `gates/S2/lint_stories.py`). No model has seen any of them. Clusters are drawn only after S9 has
fixed n and the owner has approved the tier. The rule below is fixed now, so the draw involves no choice.

For confirmatory cluster j = 1, …, n (`stpt.evidence.seed_of` throughout):
1. **Spec.**
   - The 26 truth-A specs are ordered by `seed_of("conf-cluster-order", "A", scenario_id)`, and the 26 truth-B specs by
     `seed_of("conf-cluster-order", "B", scenario_id)`.
   - They are interleaved A₁, B₁, A₂, B₂, … into a sequence of 52.
   - Cluster j takes element (j − 1) mod 52. So every prefix is truth-balanced within one, the first 52 clusters use
     every spec once, and n > 52 cycles again.
2. **Allocation:** the S2 rule, `make_banks.draw(spec, f"conf-alloc|{j}")`, a representative allocation. An unsolvable
   draw is replaced by the next seed in the fixed sequence, and the replacement is logged.
3. **Graph:** `stpt.sim.rrg(100, 4, seed_of("conf-graph", j))`, random-regular, N = 100, d = 4, with its fingerprint
   recorded.
4. **Run key:** `f"CONF-c{j}"`. This keys agent order, draws, layouts, the placeholder, recipients and pulse contacts
   (`stpt/board.py`).
5. **Server starts:** clusters go to starts in blocks of 4 in index order: start s holds clusters 4s − 3 … 4s, per
   model.
6. **Secondary arms** (shares as approved at S9): cluster j is in arm X if `unif("conf-arm", X, j) < share_X`. The
   self-reset branch runs at a saved state if `unif("conf-arm", "self-reset", j, saved_state) < share`.
7. **Pilot clusters** (S8) and development allocations are never reused (D27).
