"""Gate S5 analysis (gates/S5/S5_PLAN.md, fixed before any S5 call).

  python gates/S5/analyse_s5.py gates/S5/artifacts/<run>  -> results/s5_summary.json
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ACC = ["3/5", "3/4", "9/10"]
LOGLR = {"3/5": math.log(1.5), "3/4": math.log(3.0), "9/10": math.log(9.0)}
MODELS = ("llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b")


def content_logit(p, lA, lB, content):
    """log P(content) - log P(other content), from the letter readout."""
    letter = p["layout"]["letter_of_content"][content]
    return (lA - lB) if letter == "A" else (lB - lA)


def fit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    b = np.polyfit(x, y, 1)
    return {"slope": float(b[0]), "intercept": float(b[1])}


def analyse_wording(rows, probes, ctx):
    t = defaultdict(list); own_eff = defaultdict(list); base = defaultdict(list); base_own = []; sat = []; mass = []
    for x in rows:
        p = probes[x["prompt_id"]]; c = ctx[p["context_id"]]
        mass.append(x["non_option_mass"])
        if c["informed"]:
            l = content_logit(p, x["logp_A"], x["logp_B"], c["report_favours"])
            t[(c["story_key"], c["report_accuracy"], c["report_favours"])].append(l)
            own_eff[(c["story_key"], c["report_accuracy"], c["report_favours"], c["own_vote"] == c["report_favours"])].append(l)
            sat.append(1 / (1 + math.exp(-l)) > 0.99)
        else:
            base[c["story_key"]].append(content_logit(p, x["logp_A"], x["logp_B"], "A"))
            base_own.append(content_logit(p, x["logp_A"], x["logp_B"], c["own_vote"]))
    stories = sorted({k[0] for k in t})
    r = {k: float(np.mean(v)) for k, v in t.items()}
    R_dir = {f"{a}|{d}": float(np.mean([r[(s, a, d)] for s in stories])) for a in ACC for d in ("A", "B")}
    R = {a: float(np.mean([r[(s, a, d)] for s in stories for d in ("A", "B")])) for a in ACC}
    direction = all(v > 0 for v in R_dir.values())
    strength = R["3/5"] < R["3/4"] < R["9/10"]
    mono_cells = sum(r[(s, "3/5", d)] < r[(s, "3/4", d)] < r[(s, "9/10", d)] for s in stories for d in ("A", "B"))
    pos_templates = sum(v > 0 for v in r.values())
    stick = float(np.mean([(np.mean(own_eff[(s, a, d, True)]) - np.mean(own_eff[(s, a, d, False)])) / 2
                           for s in stories for a in ACC for d in ("A", "B")]))
    per_story_fit = {s: fit([LOGLR[a] for a in ACC], [np.mean([r[(s, a, d)] for d in ("A", "B")]) for a in ACC]) for s in stories}
    return {"pass": bool(direction and strength), "direction_pass": bool(direction), "strength_pass": bool(strength),
            "R": R, "R_by_direction": R_dir,
            "fit_vs_designed_logLR": fit([LOGLR[a] for a in ACC], [R[a] for a in ACC]), "fit_per_story": per_story_fit,
            "monotone_story_direction_cells": f"{mono_cells}/{2 * len(stories)}", "templates_r_positive": f"{pos_templates}/{len(r)}",
            "template_r": {f"{s}|{a}|{d}": v for (s, a, d), v in sorted(r.items())},
            "own_vote_stickiness_nats": stick,
            "baseline_logit_toward_content_A": {s: float(np.mean(v)) for s, v in base.items()},
            "baseline_logit_toward_own_vote": float(np.mean(base_own)),
            "baseline_P_own_vote_T1": float(np.mean([1 / (1 + math.exp(-v)) for v in base_own])),
            "share_saturated_P_fav_gt_0.99": float(np.mean(sat)),
            "non_option_mass_mean": float(np.mean(mass)), "non_option_mass_max": float(np.max(mass))}


def main():
    run = Path(sys.argv[1])
    probes = {p["prompt_id"]: p for p in json.load(open(ROOT / "gates" / "S5" / "probes" / "s5_probes.json"))["prompts"]}
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates" / "S5" / "probes" / "s5_contexts.json"))}
    out = {"plan": "gates/S5/S5_PLAN.md", "models": {}}
    for f in sorted(glob.glob(str(run / "s5_*_start*.json"))):
        d = json.load(open(f)); man = d["manifest"]; m = man["model"]
        first = [x for x in d["rows"] if x["read"] == "first"]
        rep = {x["prompt_id"]: x for x in d["rows"] if x["read"] == "repeat"}
        same = sum((x["logp_A"], x["logp_B"]) == (rep[x["prompt_id"]]["logp_A"], rep[x["prompt_id"]]["logp_B"]) for x in first if x["prompt_id"] in rep)
        M = {"server_start": man["server_start"]["id"], "wordings_read": man["wordings"], "repeats_identical": f"{same}/{len(rep)}", "wordings": {}}
        for w in man["wordings"]:
            M["wordings"][w] = analyse_wording([x for x in first if probes[x["prompt_id"]]["wording"] == w], probes, ctx)
        M["w3_pass"] = M["wordings"]["w3"]["pass"]
        M["variants_dropped"] = [w for w in man["wordings"] if w != "w3" and not M["wordings"][w]["pass"]]
        out["models"][m] = M
    out["all_five_present"] = all(m in out["models"] for m in MODELS)
    out["gate_pass"] = out["all_five_present"] and all(out["models"][m]["w3_pass"] for m in MODELS)
    (ROOT / "gates" / "S5" / "results" / "s5_summary.json").write_text(json.dumps(out, indent=1))
    for m in MODELS:
        if m not in out["models"]:
            continue
        M = out["models"][m]
        for w, W in M["wordings"].items():
            print(f"{m:16s} {w} pass {W['pass']} | R " + " < ".join(f"{W['R'][a]:.2f}" for a in ACC)
                  + f" | min R(dir) {min(W['R_by_direction'].values()):.2f} | slope {W['fit_vs_designed_logLR']['slope']:.2f}"
                  + f" int {W['fit_vs_designed_logLR']['intercept']:.2f} | mono {W['monotone_story_direction_cells']} pos {W['templates_r_positive']}"
                  + f" | stick {W['own_vote_stickiness_nats']:.2f} | sat {W['share_saturated_P_fav_gt_0.99']:.2f}")
    print("gate pass", out["gate_pass"])


if __name__ == "__main__":
    main()
