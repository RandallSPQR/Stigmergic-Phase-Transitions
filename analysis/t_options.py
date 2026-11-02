"""Inputs and consequences for the decision-noise options (analysis/DECISION_NOISE_T_OPTIONS.md).

  python analysis/t_options.py  -> analysis/results/t_options.json
Development data only (S4 probes, start 1 of pod c0c6gqx5ycpsfp, W3; S5 W3). No live board, no outcome.
Per model: evidence response R(acc) (S5), no-report stickiness (S5), uninformed agents' response to contacts (S4 live
probes: mean content logit toward the contacts' majority, or toward the own vote for 2-2), between-start S_p (S4).
For each option, T per model and the implied probabilities sigma(logit / T).
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gates" / "S4"))
import analyse_s4 as A  # noqa: E402

MODELS = ["llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
sig = lambda z: 1 / (1 + math.exp(-z))


def inputs():
    s5 = json.load(open(ROOT / "gates/S5/results/s5_summary.json"))["models"]
    s4 = json.load(open(ROOT / "gates/S4/results/s4_summary.json"))["models"]
    probes, runs = A.load([ROOT / "gates/S4/artifacts/20261102T1535Zb"])
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates/S4/probes/s4_contexts.json"))}
    out = {}
    for m in MODELS:
        st = runs[m]; s0 = sorted(st, key=lambda s: st[s]["index"])[0]
        soc = defaultdict(list)
        for pid, (la, lb, _) in st[s0]["first"].items():
            p = probes[pid]; c = ctx[p["context_id"]]
            if p["wording"] != "w3" or not c["live"] or c["informed"]:
                continue
            lA = (la - lb) if p["layout"]["letter_of_content"]["A"] == "A" else (lb - la)
            nA, own = c["contacts_A"], c["own_vote"]
            if nA == 2:
                soc["2-2: toward own vote"].append(lA if own == "A" else -lA); continue
            maj = "A" if nA >= 3 else "B"
            k = ("4-0" if nA in (0, 4) else "3-1") + (" against own vote" if maj != own else " with own vote")
            soc[k + ": toward contacts"].append(lA if maj == "A" else -lA)
        W = s5[m]["wordings"]["w3"]
        out[m] = {"R": W["R"], "stick_no_report": W["baseline_logit_toward_own_vote"],
                  "social_uninformed": {k: float(np.mean(v)) for k, v in sorted(soc.items())},
                  "S_p_T1": s4[m]["wordings"]["w3"]["S_p"]}
    return out


def consequences(inp, T):
    r = {}
    for m in MODELS:
        x = inp[m]; t = T[m]
        r[m] = {"T": t,
                "P_follow_lone_report": {a: sig(v / t) for a, v in x["R"].items()},
                "P_keep_own_vote_no_report_no_contacts": sig(x["stick_no_report"] / t),
                "P_follow_4-0_contacts_against_own_vote_uninformed": sig(x["social_uninformed"]["4-0 against own vote: toward contacts"] / t),
                "P_follow_3-1_contacts_against_own_vote_uninformed": sig(x["social_uninformed"]["3-1 against own vote: toward contacts"] / t),
                "S_p_between_start": x["S_p_T1"] / t}
    return r


def main():
    inp = inputs()
    options = {
        "A_native_T1": {m: 1.0 for m in MODELS},
        "C_per_model_evidence_anchored": {m: inp[m]["R"]["3/4"] / math.log(3.0) for m in MODELS},
    }
    out = {"note": "development data only (S4 W3 live probes, uninformed; S5 W3); S_p scales as 1/T",
           "inputs": inp, "options": {k: consequences(inp, T) for k, T in options.items()}}
    (ROOT / "analysis/results").mkdir(exist_ok=True)
    (ROOT / "analysis/results/t_options.json").write_text(json.dumps(out, indent=1))
    for k, v in out["options"].items():
        print(k)
        for m in MODELS:
            x = v[m]
            print(f"  {m:16s} T {x['T']:.2f} | lone 3/5,3/4,9/10 " + "/".join(f"{x['P_follow_lone_report'][a]:.2f}" for a in ('3/5', '3/4', '9/10'))
                  + f" | keep own (nothing) {x['P_keep_own_vote_no_report_no_contacts']:.2f} | follow 4-0 {x['P_follow_4-0_contacts_against_own_vote_uninformed']:.2f}"
                  + f" 3-1 {x['P_follow_3-1_contacts_against_own_vote_uninformed']:.2f} | S_p {x['S_p_between_start']:.3f}")


if __name__ == "__main__":
    main()
