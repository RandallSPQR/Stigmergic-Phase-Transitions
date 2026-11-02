"""Expected effect of the two proposed initial-vote rules (owner's item 4, 2026-11-02), development data only.

  python analysis/initial_vote.py -> analysis/results/initial_vote.json
Rules:
  (i)  evidence-based (proposed primary): the first vote is sampled at the model's T (D23) from its blind W3 call with
       its evidence and a seeded, balanced placeholder own vote (the W3 frame always shows a current vote; balancing
       the placeholder removes its pull on average). From S5 (W3, blind, development stories):
       q0 = P(first vote = the option its report names) = (a + b) / 2, where a = P(vote reported option | own vote =
       it) and b = P(vote reported option | own vote = the other), each the mean over renderings of sigma(l / T).
  (ii) random 50/50 start (proposed sensitivity arm): q0 = 0.5.
Blind board: no contacts, so each agent is a two-state chain: q_k = pi + (q0 - pi) lam^k, pi = b / (1 - a + b),
lam = a - b, after k of its own updates. Uninformed agents start and stay at 0.5 on average under both rules.
Population support for the truth = f * E_informed[acc q + (1 - acc)(1 - q)] + (1 - f) * 0.5, evaluated (1) on the 64
representative development allocations (their actual reports) and (2) at the D18 setting (f = 0.5, sources 3/4 and
9/10 equally, generative expectation). The live board needs contact kernels and is left to S8/S9.
"""
import glob
import json
import math
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gates" / "S5"))
import analyse_s5 as A  # noqa: E402

MODELS = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b", "llama-3.1-8b-it"]
K = [0, 1, 2, 5, None]
sig = lambda z: 1 / (1 + math.exp(-z))


def chain(m, T):
    probes = {p["prompt_id"]: p for p in json.load(open(ROOT / "gates/S5/probes/s5_probes.json"))["prompts"]}
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates/S5/probes/s5_contexts.json"))}
    d = json.load(open(ROOT / f"gates/S5/artifacts/20261102T1807Z/s5_{m}_start1.json"))
    g = defaultdict(list)
    for x in d["rows"]:
        p = probes[x["prompt_id"]]; c = ctx[p["context_id"]]
        if x["read"] != "first" or p["wording"] != "w3" or not c["informed"]:
            continue
        l = A.content_logit(p, x["logp_A"], x["logp_B"], c["report_favours"])
        g[(c["report_accuracy"], c["own_vote"] == c["report_favours"])].append(sig(l / T))
    out = {}
    for acc in ("3/5", "3/4", "9/10"):
        a, b = float(np.mean(g[(acc, True)])), float(np.mean(g[(acc, False)]))
        out[acc] = {"a": a, "b": b, "lam": a - b, "pi": b / (1 - a + b), "q0_rule_i": (a + b) / 2, "q0_rule_ii": 0.5}
    return out


def q_at(ch, acc, rule, k):
    c = ch[acc]; q0 = c[f"q0_rule_{rule}"]
    return c["pi"] if k is None else c["pi"] + (q0 - c["pi"]) * c["lam"] ** k


def support(ch, reports, f_informed, rule, k):
    """reports: list of (accuracy, favours_truth) for the informed agents (one report each)."""
    vals = [(q_at(ch, acc, rule, k) if fav else 1 - q_at(ch, acc, rule, k)) for acc, fav in reports]
    return f_informed * float(np.mean(vals)) + (1 - f_informed) * 0.5


def main():
    T = {m: v["T"] for m, v in json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"].items()}
    allocs = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "gates/S2/banks/development/allocations/*.json")))]
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in glob.glob(str(ROOT / "gates/S2/banks/development/*.json"))}
    out = {"doc": __doc__, "T": T, "models": {}}
    for m in MODELS:
        ch = chain(m, T[m]); M = {"chain": ch, "dev_representative": {}, "d18_setting": {}}
        for rule in ("i", "ii"):
            for k in K:
                key = f"rule_{rule}|k={'inf' if k is None else k}"
                vals = []
                for a in allocs:
                    if a["kind"] != "representative":
                        continue
                    truth = specs[a["scenario_id"]]["hidden_state"]
                    held = [(a["items"][i]["accuracy"], a["items"][i]["favours"] == truth) for hs in a["holders"].values() for i in hs[:1]]
                    vals.append(support(ch, held, len(held) / a["N"], rule, k))
                M["dev_representative"][key] = {"mean": float(np.mean(vals)), "min": float(np.min(vals)), "max": float(np.max(vals))}
                gen = [(acc, True, float(Fraction(acc))) for acc in ("3/4", "9/10")] + [(acc, False, 1 - float(Fraction(acc))) for acc in ("3/4", "9/10")]
                e = sum(w * (q_at(ch, acc, rule, k) if fav else 1 - q_at(ch, acc, rule, k)) for acc, fav, w in gen) / 2
                M["d18_setting"][key] = 0.5 * e + 0.5 * 0.5
        out["models"][m] = M
    (ROOT / "analysis/results/initial_vote.json").write_text(json.dumps(out, indent=1))
    for m in MODELS:
        M = out["models"][m]
        row = " | ".join(f"k={k if k is not None else 'inf'}: i {M['d18_setting'][f'rule_i|k={k if k is not None else chr(105)+chr(110)+chr(102)}']:.3f} ii {M['d18_setting'][f'rule_ii|k={k if k is not None else chr(105)+chr(110)+chr(102)}']:.3f}" for k in K)
        print(f"{m:16s} T {T[m]:5.2f} D18 support for truth: {row}")
        print(f"{'':16s} dev representative k=0: i {M['dev_representative']['rule_i|k=0']['mean']:.3f} ({M['dev_representative']['rule_i|k=0']['min']:.3f}-{M['dev_representative']['rule_i|k=0']['max']:.3f}) ii {M['dev_representative']['rule_ii|k=0']['mean']:.3f}")


if __name__ == "__main__":
    main()
