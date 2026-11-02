"""How fast live and blind support for the truth settle on the development proxy kernels (for the S8 pilot horizon).
Development data only.  python analysis/horizon_proxy.py -> analysis/results/horizon_proxy.json
Live: the pulse-design proxy kernels (analysis/results/pulse_design.json). Blind: S5 at T (a, b per accuracy from
analysis/results/initial_vote.json; uninformed keep from analysis/results/t_options.json). D18 evidence, rule (i).
Settling sweep = first sweep after which the ensemble mean support stays within 0.01 of its mean over sweeps 30-40."""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stpt import sim, evidence as E  # noqa: E402

N, SW, REPS = 100, 40, 200
sig = lambda z: 1 / (1 + math.exp(-z))


def run(kind, K, blindp, rng, indptr, nbr):
    informed = np.zeros(N, bool); informed[rng.choice(N, N // 2, replace=False)] = True
    acc = np.where(rng.random(N) < 0.5, 0.75, 0.9); fav = (rng.random(N) < acc).astype(int)
    q0 = K["q0"]
    s = np.array([(fav[i] if rng.random() < q0["3/4" if acc[i] == 0.75 else "9/10"] else 1 - fav[i]) if informed[i] else int(rng.random() < 0.5) for i in range(N)])
    traj = []
    for t in range(SW * N):
        i = int(rng.integers(N)); u = rng.random()
        if kind == "live":
            ref = fav[i] if informed[i] else s[i]
            m = sum(s[j] == ref for j in nbr[indptr[i]:indptr[i + 1]])
            p = sig(K["a_i"] + K["b_i"] * (1 if s[i] == ref else -1) + K["c_i"] * (m - 2)) if informed[i] else sig(K["a_u"] + K["c_u"] * (m - 2))
        else:
            if informed[i]:
                ref = fav[i]; ab = blindp["3/4" if acc[i] == 0.75 else "9/10"]
                p = ab["a"] if s[i] == ref else ab["b"]
            else:
                ref = s[i]; p = blindp["keep"]
        s[i] = ref if u < p else 1 - ref
        if (t + 1) % N == 0:
            traj.append(s.mean())
    return traj


def main():
    pd = json.load(open(ROOT / "analysis/results/pulse_design.json"))["kernels"]
    iv = json.load(open(ROOT / "analysis/results/initial_vote.json"))["models"]
    to = json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"]
    out = {}
    for m, K in pd.items():
        blindp = {a: {"a": iv[m]["chain"][a]["a"], "b": iv[m]["chain"][a]["b"]} for a in ("3/4", "9/10")}
        blindp["keep"] = to[m]["P_keep_own_vote_no_report_no_contacts"]
        res = {}
        for kind in ("live", "blind"):
            rng = np.random.Generator(np.random.PCG64(E.seed_of("horizon-proxy", m, kind)))
            T = []
            for g in range(8):
                indptr, nbr, _ = sim.rrg(N, 4, E.seed_of("pulse-design-graph", g))
                T += [run(kind, K, blindp, rng, indptr, nbr) for _ in range(REPS // 8)]
            mean = np.mean(T, 0); final = mean[29:].mean()
            settle = next(k for k in range(SW) if np.all(np.abs(mean[k:] - final) < 0.01)) + 1
            res[kind] = {"mean_by_sweep": mean.tolist(), "final": float(final), "settling_sweep": int(settle),
                         "between_run_sd_final": float(np.std([np.mean(x[29:]) for x in T], ddof=1))}
        out[m] = res
        print(m, {k: (round(v["final"], 3), v["settling_sweep"], round(v["between_run_sd_final"], 3)) for k, v in res.items()})
    (ROOT / "analysis/results/horizon_proxy.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
