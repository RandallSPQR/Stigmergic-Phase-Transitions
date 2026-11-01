# Pre-registered secondary analysis: board effect by informed status (D19, 2026-11-01)

Registered before any live data, as a prospective decision (coordination record D19, A11).

- **Primary, unchanged.** The all-agent final support for the correct option, live minus blind, is the first
  confirmatory contrast.
- **Secondary.** The same contrast is estimated separately in two subgroups:
  - **Uninformed agents, transmission.** Agents whose allocation gives them no report. Their blind-board support is
    near 0.5 by construction, so any live-board gain is evidence carried by the board.
  - **Informed agents, social override.** Agents holding a report. The contrast measures whether the board pulls them
    toward the truth beyond their own report, or away from it.
- **How subgroups are assigned.** Membership is fixed by the allocation, which is drawn by its own seed before the
  run, and never by anything that happens during it. The subgroups are the same in the live and blind runs of a
  cluster, which share the allocation (common random numbers).
- **Estimation.** The same model as the primary contrast is run in each subgroup:
  - paired within cluster and within one server start (D14);
  - the start ID as a blocking factor;
  - models as fixed strata;
  - clusters as graph × allocation.

  Results are reported with intervals and no power target, and no multiplicity correction is applied beyond what the
  primary needs. The subgroup difference (transmission minus override) is reported descriptively.
- **Reading.** A positive all-agent effect carried mostly by uninformed agents is aggregation through transmission. A
  negative effect concentrated in informed agents is harmful override, and a candidate input to the rung-1b cascade
  test (no cascade claim in the core).
