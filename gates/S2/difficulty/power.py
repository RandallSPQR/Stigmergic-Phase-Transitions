"""Difficulty by simulated power (POWER_PLAN.md). Reads results/per_board.json; checks it reproduces results/grid.json;
computes per (cell, kernel) the worse-direction n_80 and power at n = 10, 20 clusters per model; chooses per the plan."""
import json, math, sys
from pathlib import Path
import numpy as np
from scipy.stats import norm

D = Path(__file__).resolve().parent / "results"
DELTA, Z = 0.05, norm.ppf(1 - 0.025 / 2)
MODELS = 5


def power(delta, p, sd, n):
    q = p + delta
    if not 0.01 <= q <= 0.99 or sd <= 0:
        return 0.0 if not 0.01 <= q <= 0.99 else 1.0
    sdd = sd * math.sqrt((p * (1 - p) + q * (1 - q)) / (2 * p * (1 - p)))
    se = sdd / math.sqrt(MODELS * n)
    return float(norm.cdf(abs(delta) / se - Z) + norm.cdf(-abs(delta) / se - Z))


def n80(delta, p, sd):
    q = p + delta
    if not 0.01 <= q <= 0.99:
        return math.inf
    sdd = sd * math.sqrt((p * (1 - p) + q * (1 - q)) / (2 * p * (1 - p)))
    # solve power = 0.8 ignoring the negligible far tail: |delta| sqrt(5n)/sdd = Z + z_0.8
    return ((Z + norm.ppf(0.8)) * sdd / abs(delta)) ** 2 / MODELS


def main():
    pb = json.load(open(D / "per_board.json"))["rows"]
    gr = json.load(open(D / "grid.json"))["rows"]
    key = lambda r: (r["f"], r["set"], r["stratum"], r["ws"], r["b"], r["gamma"], r["T"])
    g = {key(r): r for r in gr}
    same = all(abs(g[key(r)]["blind"] - r["blind"]) < 1e-12 and abs(g[key(r)]["live"] - r["live"]) < 1e-12 for r in pb)
    out = []
    for r in pb:
        bl, lv = np.array(r["blind_boards"]), np.array(r["live_boards"])
        p, sd = float(bl.mean()), float(np.std(lv - bl, ddof=1))
        e = {k: r[k] for k in ("f", "set", "stratum", "ws", "b", "gamma", "T")}
        e.update(p=p, sd_contrast=sd, sd_blind=float(bl.std(ddof=1)),
                 n80_plus=n80(+DELTA, p, sd), n80_minus=n80(-DELTA, p, sd))
        e["n80_worse"] = max(e["n80_plus"], e["n80_minus"])
        for n in (10, 20):
            e[f"power_n{n}_worse"] = min(power(+DELTA, p, sd, n), power(-DELTA, p, sd, n))
        out.append(e)
    cells = {}
    for e in out:
        cells.setdefault((e["f"], e["set"], e["stratum"]), []).append(e)
    surf = []
    for (f, s, st), es in sorted(cells.items()):
        w = np.array([e["n80_worse"] for e in es])
        surf.append({"f": f, "set": s, "stratum": st, "score_p75_n80": float(np.percentile(w, 75)),
                     "n80_median": float(np.median(w)), "n80_p90": float(np.percentile(w, 90)),
                     "sd_contrast_median": float(np.median([e["sd_contrast"] for e in es])),
                     "blind_median": float(np.median([e["p"] for e in es])),
                     "power_n10_median": float(np.median([e["power_n10_worse"] for e in es])),
                     "power_n20_median": float(np.median([e["power_n20_worse"] for e in es])),
                     "power_n20_p25": float(np.percentile([e["power_n20_worse"] for e in es], 25))})
    rep = [c for c in surf if c["stratum"] == "representative"]
    mid = sorted([c for c in rep if c["f"] == 0.5], key=lambda c: c["score_p75_n80"])
    best = mid[0]
    region = [c for c in mid if c["score_p75_n80"] <= 1.25 * best["score_p75_n80"]]
    if len(region) < 2:
        region = mid[:2]
    unconstrained = min(rep, key=lambda c: c["score_p75_n80"])
    res = {"plan": "gates/S2/difficulty/POWER_PLAN.md", "reproduces_grid": same, "delta": DELTA, "alpha": 0.025,
           "models": MODELS, "surface": surf, "chosen": best, "region": region, "unconstrained_optimum": unconstrained,
           "per_kernel": out}
    json.dump(res, open(D / "power.json", "w"), indent=1)
    print("re-run reproduces grid.json:", same)
    for c in surf:
        print(f"f={c['f']} {c['set']:4s} {c['stratum'][:4]} score(p75 n80)={c['score_p75_n80']:7.1f} median n80={c['n80_median']:6.1f}"
              f" sd(contrast) {c['sd_contrast_median']:.3f} blind {c['blind_median']:.3f} power@20 median {c['power_n20_median']:.2f}")
    print("CHOSEN (f=0.5):", best["set"], round(best["score_p75_n80"], 1), "| REGION:", [c["set"] for c in region],
          "| unconstrained optimum:", unconstrained["f"], unconstrained["set"], round(unconstrained["score_p75_n80"], 1))


if __name__ == "__main__":
    main()
