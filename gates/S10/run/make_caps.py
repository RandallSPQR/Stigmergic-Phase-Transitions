"""Proposed per-stage caps for the confirmatory driver (review #4). CPU only; reads committed files; no model call.

  python gates/S10/run/make_caps.py -> gates/S10/run/caps_proposed.json

S9's accepted cost model (gates/S9/s9_run.py cost(); inputs in gates/S9/results/s9_tiers.json "cost_assumptions"),
split by stage instead of summed: per model, "core" = the 61 primary-arm clusters (confirmatory models only) plus that
model's server-start overhead (16 starts x 240 s); "secondary" = every other arm actually drawn in the frozen cluster
file (T1, rule (ii), variant wordings) and, for Llama, all of its arms and starts. Pod setup and downloads (3 x 600 s +
5 x 300 s) are shared pro rata to each stage's GPU time, as in S9. Every figure carries S9's 10% failed-pod margin and
is priced at S9's $2.49 per GPU-hour. The accepted totals (D31) are $77 core and $144 with all arms; the driver flags
each stage at 80% of its cap and stops at 100%. With the arms actually drawn the estimate slightly exceeds the accepted
totals, so the caps are scaled down to them (core stages to $77; secondary stages to $144 - $77); the unscaled estimate
is reported. These caps are a PROPOSAL for the owner's approval.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
ALL = CONF + ["llama-3.1-8b-it"]


def main():
    s9 = json.loads((ROOT / "gates/S9/results/s9_tiers.json").read_text())
    ca = s9["cost_assumptions"]; sec = ca["per_model_seconds_per_S8_cluster"]; rate = ca["usd_per_gpu_hour"]
    man = json.loads((ROOT / "gates/S10/clusters/MANIFEST.json").read_text())
    n = man["n_clusters"]; starts = math.ceil(n / ca["clusters_per_start"]); arms = man["arm_counts"]
    H = 30; calls_cluster = ca["calls_per_cluster_at_H"]; rule2_frac = (2 * H * 100) / calls_cluster
    raw = {}
    for m in ALL:
        primary = n * sec[m] + starts * ca["start_overhead_s_per_start_per_model"]
        other = arms["T1"] * sec[m] + arms["rule_ii"] * sec[m] * rule2_frac + arms["variant_runs"][m] * sec[m]
        if m in CONF:
            raw[f"{m}:core"], raw[f"{m}:secondary"] = primary, other
        else:
            raw[f"{m}:secondary"] = primary + other
    setup = 3 * 600 + 5 * 300
    tot = sum(raw.values())
    est = {k: (v + setup * v / tot) * 1.10 / 3600 * rate for k, v in raw.items()}
    est_core = sum(v for k, v in est.items() if k.endswith(":core")); est_sec = sum(v for k, v in est.items() if k.endswith(":secondary"))
    f_core, f_sec = min(1.0, 77 / est_core), min(1.0, (144 - 77) / est_sec)
    caps = {k: round(v * (f_core if k.endswith(":core") else f_sec), 2) for k, v in est.items()}
    out = {"doc": __doc__, "status": "PROPOSED; requires the owner's approval before any paid run",
           "usd_per_gpu_hour": rate, "caps_usd": caps, "flag_fraction": 0.8,
           "estimate_usd_unscaled": {k: round(v, 2) for k, v in est.items()},
           "totals": {"estimate_core_usd": round(est_core, 2), "estimate_all_arms_usd": round(est_core + est_sec, 2),
                      "caps_core_usd": round(sum(v for k, v in caps.items() if k.endswith(":core")), 2),
                      "caps_all_arms_usd": round(sum(caps.values()), 2), "accepted_core_usd": 77, "accepted_all_arms_usd": 144,
                      "scale_core": round(f_core, 4), "scale_secondary": round(f_sec, 4)},
           "drawn_arm_counts": arms, "inputs": {"s9_cost_assumptions": ca}}
    (ROOT / "gates/S10/run/caps_proposed.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["totals"]), json.dumps(caps))


if __name__ == "__main__":
    main()
