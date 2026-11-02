"""Gate S4 analysis (gates/S4/S4_PLAN.md, fixed before any S4 call).

  python gates/S4/analyse_s4.py gates/S4/artifacts/<run1> [gates/S4/artifacts/<run2> ...]
    -> results/s4_summary.json, results/s4_variance_components.json
"""
from __future__ import annotations

import glob
import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIMIT, TRIP, MIN_OP = 0.3, 0.025, 40


def load(dirs):
    probes = {p["prompt_id"]: p for p in json.load(open(ROOT / "gates" / "S4" / "probes" / "s4_probes.json"))["prompts"]}
    runs = defaultdict(dict)                                   # model -> start id -> {"pod", "first": {pid: (lA, lB, mass)}, "repeat": ...}
    for d in dirs:
        for f in sorted(glob.glob(str(Path(d) / "s4_*_start*.json"))):
            r = json.load(open(f))
            man = r["manifest"]
            ss = man["server_start"]
            rec = {"pod": ss["pod"], "index": ss["index"], "first": {}, "repeat": {}, "read_by": defaultdict(int)}
            for x in r["rows"]:
                rec[x["read"]][x["prompt_id"]] = (x["logp_A"], x["logp_B"], x["non_option_mass"])
                rec["read_by"]["A:%s/B:%s" % (x["read_by"]["A"], x["read_by"]["B"]) if isinstance(x["read_by"], dict) else str(x["read_by"])] += 1
            runs[man["model"]][ss["id"]] = rec
    return probes, runs


def ell(t):
    return t[0] - t[1]


def pA(t):
    return 1.0 / (1.0 + math.exp(-(t[0] - t[1])))


def analyse(probes, runs):
    summary, comps = {"plan": "gates/S4/S4_PLAN.md", "limit_nats": LIMIT, "tripwire_p": TRIP, "models": {}}, {}
    wordings = sorted({p["wording"] for p in probes.values()}, key=lambda w: (w != "w3", w))
    for m, starts in sorted(runs.items()):
        sids = sorted(starts, key=lambda s: (starts[s]["pod"], starts[s]["index"]))
        pods = sorted({starts[s]["pod"] for s in sids})
        M = {"starts": sids, "pods": pods, "n_starts": len(sids), "wordings": {}}
        # 1. within-start repeats (W3)
        rep = []
        for s in sids:
            st = starts[s]
            pairs = [(ell(st["first"][p]), ell(st["repeat"][p])) for p in st["repeat"] if p in st["first"]]
            diffs = np.array([a - b for a, b in pairs])
            rep.append({"start": s, "n_pairs": len(pairs), "sd_nats": float(np.sqrt(np.mean(diffs ** 2) / 2)) if len(pairs) else None,
                        "bit_identical": int(sum(st["first"][p][:2] == st["repeat"][p][:2] for p in st["repeat"] if p in st["first"]))})
        M["within_start_repeat"] = rep
        M["within_start_repeat_max_sd"] = max(r["sd_nats"] for r in rep if r["sd_nats"] is not None)
        M["gate_pass"] = M["within_start_repeat_max_sd"] <= LIMIT
        for w in wordings:
            ids = sorted(p for p in probes if probes[p]["wording"] == w and all(p in starts[s]["first"] for s in sids))   # a model is read only in its valid wordings (D21)
            if not ids:
                continue
            L = np.array([[ell(starts[s]["first"][p]) for s in sids] for p in ids])          # probes x starts
            Pm = 1 / (1 + np.exp(-L.mean(1)))
            op = (Pm >= 0.1) & (Pm <= 0.9)
            use = op if op.sum() >= MIN_OP else np.ones(len(ids), bool)
            S = len(sids)
            D = L - L.mean(1, keepdims=True)
            res = {"n_probes": len(ids), "n_operating_point": int(op.sum()), "primary_uses": "operating-point probes" if op.sum() >= MIN_OP else "all probes (fewer than 40 at the operating point)"}
            if S >= 2:
                def sig(Dsub, n_s):
                    return float(np.sqrt((Dsub ** 2).sum() / (Dsub.shape[0] * (n_s - 1))))
                b = D[use].mean(0)
                pair = [L[use, i] - L[use, j] for i, j in itertools.combinations(range(S), 2)]
                rms_pair = float(np.sqrt(np.mean(np.concatenate(pair) ** 2)))
                near = (Pm >= 0.35) & (Pm <= 0.65)
                Pall = 1 / (1 + np.exp(-L))
                emp = [Pall[near, i] - Pall[near, j] for i, j in itertools.combinations(range(S), 2)] if near.any() else []
                res.update({
                    "sigma_b_nats": sig(D[use], S), "sigma_b_nats_all_probes": sig(D, S),
                    "start_offsets_nats": {s: float(v) for s, v in zip(sids, b)},
                    "rms_pairwise_shift_nats": rms_pair,
                    "S_p": 0.25 * rms_pair, "S_offset_p": 0.25 * float(b.max() - b.min()),
                    "empirical_rms_dp_near_half": float(np.sqrt(np.mean(np.concatenate(emp) ** 2))) if len(emp) else None,
                    "n_near_half": int(near.sum()),
                    "max_abs_shift_nats": float(np.abs(D).max()), "share_probes_any_shift": float((np.abs(D).max(1) > 0).mean()),
                })
                within = {}
                for pod in pods:
                    cols = [k for k, s in enumerate(sids) if starts[s]["pod"] == pod]
                    if len(cols) >= 2:
                        Lp = L[use][:, cols]; within[pod] = sig(Lp - Lp.mean(1, keepdims=True), len(cols))
                res["sigma_b_within_pod_nats"] = within
                if len(pods) == 2:
                    c0 = [k for k, s in enumerate(sids) if starts[s]["pod"] == pods[0]]; c1 = [k for k, s in enumerate(sids) if starts[s]["pod"] == pods[1]]
                    res["pod_mean_difference_nats"] = float(L[use][:, c0].mean() - L[use][:, c1].mean())
                    res["between_pod_rms_probe_difference_nats"] = float(np.sqrt(np.mean((L[use][:, c0].mean(1) - L[use][:, c1].mean(1)) ** 2)))
                res["tripwire"] = bool(res["S_p"] > TRIP or res["S_offset_p"] > TRIP)
                comps.setdefault(m, {})[w] = {"var_start_offset_nats2": float(np.var(b, ddof=1)) if S > 2 else None,
                                              "var_probe_x_start_nats2": float(((D[use] - b) ** 2).sum() / (use.sum() * (S - 1))),
                                              "sigma_b_nats": res["sigma_b_nats"],
                                              "between_pod_mean_difference_nats": res.get("pod_mean_difference_nats"),
                                              "n_starts": S, "n_pods": len(pods), "probes": res["primary_uses"]}
            # 5. presentation effects and 6. format, from each pod's first start
            pres = {}
            for pod in pods:
                s0 = [s for s in sids if starts[s]["pod"] == pod][0]
                by_ctx = defaultdict(list)
                for p in ids:
                    q = probes[p]; lc = ell(starts[s0]["first"][p]) * (1 if q["layout"]["letter_of_content"]["A"] == "A" else -1)
                    first_content = "A" if q["layout"]["letter_of_content"]["A"] == q["layout"]["listed_first_letter"] else "B"
                    by_ctx[q["context_id"]].append((q["layout"]["letter_of_content"]["A"] == "A", first_content == "A", lc))
                letter = [np.mean([v for a, _, v in c if a]) - np.mean([v for a, _, v in c if not a]) for c in by_ctx.values()]
                order = [np.mean([v for _, f, v in c if f]) - np.mean([v for _, f, v in c if not f]) for c in by_ctx.values()]
                resid = [np.std([v for *_, v in c], ddof=1) for c in by_ctx.values()]
                firsts = [starts[s0]["first"][p] for p in ids]
                pres[pod] = {"letter_effect_nats_mean": float(np.mean(letter)) / 2, "letter_effect_nats_sd": float(np.std(letter, ddof=1)) / 2,
                             "option_order_effect_nats_mean": float(np.mean(order)) / 2, "option_order_effect_nats_sd": float(np.std(order, ddof=1)) / 2,
                             "layout_sd_nats_mean": float(np.mean(resid)),
                             "share_answer_A": float(np.mean([t[0] > t[1] for t in firsts])),
                             "mean_P_A_renorm": float(np.mean([pA(t) for t in firsts])),
                             "non_option_mass_mean": float(np.mean([t[2] for t in firsts])), "non_option_mass_max": float(np.max([t[2] for t in firsts]))}
            res["presentation_and_format"] = pres
            M["wordings"][w] = res
        M["read_by"] = {s: dict(starts[s]["read_by"]) for s in sids}
        summary["models"][m] = M
    summary["gate_pass"] = all(M["gate_pass"] for M in summary["models"].values()) and len(summary["models"]) == 5
    summary["tripwire"] = any(r.get("tripwire") for M in summary["models"].values() for r in M["wordings"].values())
    return summary, comps


def main():
    probes, runs = load(sys.argv[1:])
    summary, comps = analyse(probes, runs)
    out = ROOT / "gates" / "S4" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "s4_summary.json").write_text(json.dumps(summary, indent=1))
    (out / "s4_variance_components.json").write_text(json.dumps(comps, indent=1))
    for m, M in summary["models"].items():
        w3 = M["wordings"].get("w3", {})
        print(f"{m:16s} starts {M['n_starts']} pods {len(M['pods'])} | repeat SD max {M['within_start_repeat_max_sd']:.4f} | "
              f"sigma_b {w3.get('sigma_b_nats', float('nan')):.4f} nats | S_p {w3.get('S_p', float('nan')):.4f} | "
              f"S_offset {w3.get('S_offset_p', float('nan')):.4f} | op probes {w3.get('n_operating_point')}")
    print("gate pass", summary["gate_pass"], "| tripwire", summary["tripwire"])


if __name__ == "__main__":
    main()
