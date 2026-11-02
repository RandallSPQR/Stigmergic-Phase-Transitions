"""Calibration checks for decision noise T under C (analysis/T_CALIBRATION_CHECKS.md, fixed before computing).

  python analysis/t_checks.py  -> analysis/results/t_checks.json
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
G3M = "gemma-3-27b-it"
sig = lambda z: 1 / (1 + math.exp(-z))
BAYES = {"3/5": 0.60, "3/4": 0.75, "9/10": 0.90}


def bf16_step(x):
    return 2.0 ** (math.floor(math.log2(abs(x))) - 7) if x else 0.0


def main():
    T = {m: v["T"] for m, v in json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"].items()}
    s5 = json.load(open(ROOT / "gates/S5/results/s5_summary.json"))["models"]
    s4 = json.load(open(ROOT / "gates/S4/results/s4_summary.json"))["models"]
    out = {"plan": "analysis/T_CALIBRATION_CHECKS.md", "T": T, "item2_generalisation": {}, "item4": {}}
    # item 2
    for m in MODELS:
        W = s5[m]["wordings"]["w3"]; tr = W["template_r"]
        stories = sorted({k.split("|")[0] for k in tr})
        P = {a: sig(W["R"][a] / T[m]) for a in BAYES}
        per_story = {s: {a: sig(np.mean([tr[f"{s}|{a}|{d}"] for d in "AB"]) / T[m]) for a in BAYES} for s in stories}
        out["item2_generalisation"][m] = {"P_follow": P, "miss_vs_bayes": {a: P[a] - BAYES[a] for a in BAYES},
                                          "per_story_P_follow": per_story,
                                          "per_story_range_9/10": [min(v["9/10"] for v in per_story.values()), max(v["9/10"] for v in per_story.values())]}
    # item 4 (S4 W3 probes, mean logit over all six starts)
    probes, runs = A.load([ROOT / "gates/S4/artifacts/20261102T1535Z", ROOT / "gates/S4/artifacts/20261102T1535Zb"])
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates/S4/probes/s4_contexts.json"))}
    per = {}
    for m in MODELS:
        st = runs[m]; sids = sorted(st)
        ids = [p for p in probes if probes[p]["wording"] == "w3"]
        L = {p: float(np.mean([A.ell(st[s]["first"][p]) for s in sids])) for p in ids}
        Lall = {p: [A.ell(st[s]["first"][p]) for s in sids] for p in ids}
        t = T[m]
        g1 = defaultdict(list); conflict = []
        for p in ids:
            q = probes[p]; c = ctx[q["context_id"]]
            lA = L[p] if q["layout"]["letter_of_content"]["A"] == "A" else -L[p]
            if c["live"] and not c["informed"]:
                g1[(c["own_vote"], c["contacts_A"])].append(sig(lA / t))
            if c["live"] and c["informed"] and c["contacts_A"] != 2:
                maj = "A" if c["contacts_A"] >= 3 else "B"
                if maj != c["report_favours"]:
                    lf = lA if c["report_favours"] == "A" else -lA
                    conflict.append(sig(lf / t))
        grad = {own: [float(np.mean(g1[(own, k)])) for k in range(5)] for own in "AB"}
        absl = np.array([abs(v) for v in L.values()])
        diffs = sorted({round(abs(a - b), 6) for v in Lall.values() for a in v for b in v if a != b})
        pf = s4[m]["wordings"]["w3"]["presentation_and_format"]
        per[m] = {"T": t,
                  "G1_contact_gradient_P_contentA": grad,
                  "G1_strictly_increasing": all(all(x < y for x, y in zip(g, g[1:])) for g in grad.values()),
                  "G2_share_P_over_0.99": float(np.mean(absl / t > math.log(99))),
                  "G3_share_within_0.5_of_max_abs_logit": float(np.mean(absl >= absl.max() - 0.5)), "max_abs_logit": float(absl.max()),
                  "median_abs_logit": float(np.median(absl)),
                  "G4_bf16_step_at_median_over_T": bf16_step(float(np.median(absl))) / t,
                  "G4_smallest_nonzero_between_start_diff_over_T": (diffs[0] / t) if diffs else None,
                  "G5_letter_effect_over_T": max(abs(x["letter_effect_nats_mean"]) for x in pf.values()) / t,
                  "G5_order_effect_over_T": max(abs(x["option_order_effect_nats_mean"]) for x in pf.values()) / t,
                  "G6_conflict_P_follow_report": float(np.mean(conflict)), "G6_n": len(conflict),
                  "G7_S_p_over_T": s4[m]["wordings"]["w3"]["S_p"] / t}
    for m in MODELS:   # added for the owner's item 3 (descriptive, after the plan): contact swing from G1's gradient
        g1 = per[m]["G1_contact_gradient_P_contentA"]
        per[m]["contact_swing_P_4A_minus_0A_mean_over_own_vote"] = float(np.mean([g1[o][4] - g1[o][0] for o in "AB"]))
    o = [m for m in MODELS if m != G3M]; g = per[G3M]
    flags = {
        "G1": not g["G1_strictly_increasing"],
        "G2": g["G2_share_P_over_0.99"] > max(per[m]["G2_share_P_over_0.99"] for m in o) + 0.10,
        "G3": g["G3_share_within_0.5_of_max_abs_logit"] > 0.10,
        "G4": g["G4_bf16_step_at_median_over_T"] > 0.01,
        "G5": g["G5_letter_effect_over_T"] > max(per[m]["G5_letter_effect_over_T"] for m in o) or g["G5_order_effect_over_T"] > max(per[m]["G5_order_effect_over_T"] for m in o),
        "G6": not (min(per[m]["G6_conflict_P_follow_report"] for m in o) - 0.15 <= g["G6_conflict_P_follow_report"] <= max(per[m]["G6_conflict_P_follow_report"] for m in o) + 0.15),
        "G7": g["G7_S_p_over_T"] > 0.025,
    }
    out["item4"] = {"per_model": per, "gemma3_flags": flags, "gemma3_any_flag": any(flags.values())}
    (ROOT / "analysis/results/t_checks.json").write_text(json.dumps(out, indent=1))
    for m in MODELS:
        x = out["item2_generalisation"][m]
        print(f"{m:16s} T {T[m]:5.2f} | P follow 3/5 {x['P_follow']['3/5']:.2f} (Bayes .60)  9/10 {x['P_follow']['9/10']:.2f} (Bayes .90) | 9/10 per story {x['per_story_range_9/10'][0]:.2f}-{x['per_story_range_9/10'][1]:.2f}")
    for m in MODELS:
        p = per[m]
        print(f"{m:16s} G1 {p['G1_strictly_increasing']} {[[round(v,2) for v in g] for g in p['G1_contact_gradient_P_contentA'].values()]} | G2 {p['G2_share_P_over_0.99']:.2f} | G3 {p['G3_share_within_0.5_of_max_abs_logit']:.3f} (max {p['max_abs_logit']:.1f}) | G4 {p['G4_bf16_step_at_median_over_T']:.4f} | G5 {p['G5_letter_effect_over_T']:.2f}/{p['G5_order_effect_over_T']:.2f} | G6 {p['G6_conflict_P_follow_report']:.2f} (n {p['G6_n']}) | G7 {p['G7_S_p_over_T']:.3f}")
    print("contact swing:", {m: round(per[m]["contact_swing_P_4A_minus_0A_mean_over_own_vote"], 2) for m in MODELS})
    print("Gemma-3-27B flags:", flags)


if __name__ == "__main__":
    main()
