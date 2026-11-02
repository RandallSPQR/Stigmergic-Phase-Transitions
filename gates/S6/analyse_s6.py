"""Gate S6 analysis (gates/S6/S6_PLAN.md, fixed before any S6 call).

  python gates/S6/analyse_s6.py gates/S6/artifacts/<run>  -> results/s6_summary.json
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ("llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b")


def main():
    run = Path(sys.argv[1])
    probes = {p["prompt_id"]: p for p in json.load(open(ROOT / "gates" / "S6" / "probes" / "s6_probes.json"))["prompts"]}
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates" / "S6" / "probes" / "s6_contexts.json"))}
    out = {"plan": "gates/S6/S6_PLAN.md", "threshold": 0.90, "models": {}}
    for f in sorted(glob.glob(str(run / "s6_*_start*.json"))):
        d = json.load(open(f)); man = d["manifest"]; m = man["model"]
        first = [x for x in d["rows"] if x["read"] == "first"]
        rep = {x["prompt_id"]: x for x in d["rows"] if x["read"] == "repeat"}
        same = sum((x["logp_A"], x["logp_B"]) == (rep[x["prompt_id"]]["logp_A"], rep[x["prompt_id"]]["logp_B"]) for x in first if x["prompt_id"] in rep)
        g = defaultdict(list); pt = defaultdict(list); mass = []
        for x in first:
            p = probes[x["prompt_id"]]; c = ctx[p["context_id"]]
            tl = p["layout"]["letter_of_content"][p["truth"]]
            ol = "B" if tl == "A" else "A"
            lp = {"A": x["logp_A"], "B": x["logp_B"]}
            ok = lp[tl] > lp[ol]
            ptruth = 1 / (1 + math.exp(-(lp[tl] - lp[ol])))
            own = "own vote = truth" if p["own_vote"] == p["truth"] else "own vote against truth"
            for key in (p["kind"], f"{p['kind']}|{own}", f"story:{c['story']['source']}|{p['kind']}"):
                g[key].append(ok); pt[key].append(ptruth)
            mass.append(x["non_option_mass"])
        acc = {k: sum(v) / len(v) for k, v in g.items()}
        M = {"server_start": man["server_start"]["id"], "repeats_identical": f"{same}/{len(rep)}",
             "accuracy": {k: round(v, 4) for k, v in sorted(acc.items())},
             "correct_of": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(g.items())},
             "mean_P_truth_T1": {k: round(sum(v) / len(v), 4) for k, v in sorted(pt.items())},
             "non_option_mass_mean": sum(mass) / len(mass), "non_option_mass_max": max(mass)}
        M["pass"] = acc["representative"] >= 0.90
        M["challenge_set_solvable_solo"] = acc.get("conditional_challenge_set", 0) >= 0.90
        out["models"][m] = M
    out["all_five_present"] = all(m in out["models"] for m in MODELS)
    out["gate_pass"] = out["all_five_present"] and all(out["models"][m]["pass"] for m in MODELS)
    (ROOT / "gates" / "S6" / "results" / "s6_summary.json").write_text(json.dumps(out, indent=1))
    for m in MODELS:
        if m in out["models"]:
            M = out["models"][m]
            print(f"{m:16s} representative {M['correct_of']['representative']} ({M['accuracy']['representative']:.3f}) pass {M['pass']} | "
                  f"challenge {M['correct_of'].get('conditional_challenge_set')} ({M['accuracy'].get('conditional_challenge_set', float('nan')):.3f}) | "
                  f"P(truth) rep {M['mean_P_truth_T1']['representative']:.3f} ch {M['mean_P_truth_T1'].get('conditional_challenge_set', float('nan')):.3f} | repeats {M['repeats_identical']}")
    print("gate pass", out["gate_pass"])


if __name__ == "__main__":
    main()
