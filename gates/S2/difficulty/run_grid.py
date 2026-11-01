"""Difficulty grid (gates/S2/difficulty/PLAN.md): blind- and live-board accuracy over informed fraction x source
strength x stratum, for 81 proxy kernels, on N = 100, d = 4 boards. CPU only; no model is called.

  python gates/S2/difficulty/run_grid.py
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E, sim  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
N, D, SWEEPS, BOARDS = 100, 4, 20, 40
FRACS = [0.3, 0.5, 0.7]
SETS = {"W": ["3/5"], "WM": ["3/5", "3/4"], "WMS": ["3/5", "3/4", "9/10"], "MS": ["3/4", "9/10"]}
WS, BS, GS, TS = [0.5, 1.0, 2.0], [0.036, 0.386, 0.876], [-1.440, -0.337, 2.425], [0.5, 1.0, 2.0]
KERNELS = list(itertools.product(WS, BS, GS, TS))
BAND, MOST = (0.60, 0.85), 2 / 3
MARGIN = 3.0


def scenario(f, accs, truth):
    return {"scenario_id": f"grid-{f}-{'_'.join(accs)}-{truth}", "hidden_state": truth, "prior": 0.5,
            "story": {"source": "a source", "options": {"A": "A", "B": "B"}, "report": "{source} {freq} {option}"},
            "evidence_model": {"accuracy_mix": accs, "accuracy_weights": [1] * len(accs), "informed_fraction": f, "shared": []},
            "pooled_margin_logodds": MARGIN}


def representative(scn, label):
    for t in range(100):
        a = E.allocate(scn, E.seed_of(label, t), N=N)
        if a["solvable"]:
            return a, t
    raise RuntimeError(label)


def evidence_field(alloc):
    """Signed log LR toward option A of each position's report (0 if uninformed)."""
    e = np.zeros(N)
    for pos, ids in alloc["holders"].items():
        for i in ids:
            it = alloc["items"][i]
            e[int(pos)] += math.log(it["lr"]) * (1 if it["favours"] == "A" else -1)
    return e


def table(e, ws, b, g, T, live):
    n = np.arange(D + 1)
    soc = b * (2 * n - D) if live else np.zeros(D + 1)
    own = np.array([-1.0, 1.0]) * g
    logit = ws * e[:, None, None] + own[None, :, None] + soc[None, None, :]
    return 1.0 / (1.0 + np.exp(-logit / T))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows, na = [], []
    for f, (sk, accs) in itertools.product(FRACS, SETS.items()):
        fr = [Fraction(a) for a in accs]
        boards = {"representative": [], "challenge": []}
        for k in range(BOARDS):
            truth = "A" if k % 2 == 0 else "B"
            scn = scenario(f, accs, truth)
            lab = f"grid|{f}|{sk}|{k}"
            rep, redraws = representative(scn, lab + "|rep")
            n_inf = int(round(f * N))
            ch = None
            if len(fr) > 1:
                n_true = int(round(0.3 * n_inf))
                ch = E.challenge_allocation(scn, E.seed_of(lab, "chal"), n_true, n_inf - n_true, strong=max(fr), weak=min(fr), N=N)
                if not ch["solvable"]:
                    ch = None
            graph = sim.rrg(N, D, E.seed_of(lab, "graph") % 2**31)
            s0 = np.where(np.random.Generator(np.random.PCG64(E.seed_of(lab, "start"))).random(N) < 0.5, 1, -1).astype(np.int8)
            common = {"truth": 1 if truth == "A" else -1, "graph": graph, "s0": s0, "seed": E.seed_of(lab, "updates")}
            boards["representative"].append({**common, "e": evidence_field(rep), "redraws": redraws,
                                             "pooled": rep["pooled_logodds_toward_truth"]})
            if ch is not None:
                boards["challenge"].append({**common, "e": evidence_field(ch), "pooled": ch["pooled_logodds_toward_truth"]})
        if len(boards["challenge"]) < BOARDS:
            na.append({"f": f, "set": sk, "challenge_boards": len(boards["challenge"]),
                       "why": "single accuracy level" if len(fr) == 1 else "profile misses the pooled margin"})
            boards["challenge"] = []
        for stratum, bl in boards.items():
            if not bl:
                continue
            for (ws, b, g, T) in KERNELS:
                acc = {"blind": [], "live": []}
                for bd in bl:
                    indptr, nbr, _ = bd["graph"]
                    for mode in ("blind", "live"):
                        ch_ = sim.Chain(indptr, nbr, table(bd["e"], ws, b, g, T, mode == "live"), bd["s0"], seed=bd["seed"])
                        ch_.sweeps(SWEEPS)
                        acc[mode].append(float(np.mean(ch_.s == bd["truth"])))
                bl_a, lv_a = np.array(acc["blind"]), np.array(acc["live"])
                rows.append({"f": f, "set": sk, "stratum": stratum, "ws": ws, "b": b, "gamma": g, "T": T,
                             "blind": float(bl_a.mean()), "blind_se": float(bl_a.std(ddof=1) / math.sqrt(len(bl_a))),
                             "live": float(lv_a.mean()), "live_minus_blind": float((lv_a - bl_a).mean()),
                             "pooled_median": float(np.median([bd["pooled"] for bd in bl]))})
        print(f"f={f} set={sk} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump({"plan": "gates/S2/difficulty/PLAN.md", "kernels": len(KERNELS), "boards_per_cell": BOARDS, "rows": rows,
               "challenge_na": na}, open(OUT / "grid.json", "w"), indent=1)
    summarise(rows, na)


def summarise(rows, na):
    cells, summ = {}, []
    for r in rows:
        cells.setdefault((r["f"], r["set"], r["stratum"]), []).append(r)
    def stats(vals):
        v = np.array(vals)
        inband = float(np.mean((v >= BAND[0]) & (v <= BAND[1])))
        return {"median": float(np.median(v)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
                "share_in_band": inband, "in_region": inband >= MOST}
    for f in FRACS:
        for sk in SETS:
            rep = cells.get((f, sk, "representative"), [])
            chl = {(r["ws"], r["b"], r["gamma"], r["T"]): r for r in cells.get((f, sk, "challenge"), [])}
            out = {"f": f, "set": sk, "blind_representative": stats([r["blind"] for r in rep]),
                   "live_representative_median": float(np.median([r["live"] for r in rep])),
                   "live_minus_blind_median": float(np.median([r["live_minus_blind"] for r in rep])),
                   "pooled_logodds_median": float(np.median([r["pooled_median"] for r in rep]))}
            if chl:
                out["blind_challenge"] = stats([r["blind"] for r in chl.values()])
                for c in (0.25, 0.5):
                    mix = [(1 - c) * r["blind"] + c * chl[(r["ws"], r["b"], r["gamma"], r["T"])]["blind"] for r in rep]
                    out[f"blind_mix_c{c}"] = stats(mix)
            summ.append(out)
    region = [(s["f"], s["set"]) for s in summ if s["blind_representative"]["in_region"]]
    json.dump({"band": BAND, "most": MOST, "cells": summ, "region_representative": region, "challenge_na": na},
              open(OUT / "summary.json", "w"), indent=1)
    print("REGION (representative boards):", region)
    for s in summ:
        b = s["blind_representative"]
        print(f"f={s['f']} {s['set']:4s} blind median {b['median']:.3f} [{b['p10']:.3f}, {b['p90']:.3f}] in-band {b['share_in_band']:.2f}"
              f" region {b['in_region']}  | live median {s['live_representative_median']:.3f}"
              + (f" | challenge blind median {s['blind_challenge']['median']:.3f}" if "blind_challenge" in s else ""))


if __name__ == "__main__":
    main()
