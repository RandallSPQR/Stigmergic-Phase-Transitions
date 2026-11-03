"""Cross-model correlation of cluster-level deviations in the S8 pilot (coordination D29 item 3). Variance-only: the
per-cluster contrasts are computed in memory and never written or printed; only covariances and correlations are output.

  python gates/S9/rho_from_s8.py -> gates/S9/results/rho_from_s8.json
For each confirmatory model and each rule-(i) cluster: the board effect (live - blind support for the truth at the
final sweep) and ITT persistence (cluster mean of its two pulsed branches), as defined in gates/S8/analyse_s8.py. Each
model's values are centred on its own mean within each evidence setting (D27); the 4 x 4 covariance across models is
taken over the 6 clusters (df = 6 - 2 = 4). Reported: the covariance and correlation matrices, the mean off-diagonal
correlation rho, and the ratio Var(cross-model mean) / (mean variance / 4) = 1 + 3 rho_eff.
"""
import glob
import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gates/S8"))
import analyse_s8 as A  # noqa: E402

CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]


def main():
    clusters = {c["cluster"]: c for c in json.load(open(ROOT / "gates/S8/inputs/clusters.json"))}
    prm = json.load(open(ROOT / "gates/S8/s8_params.json"))
    vals = {"board_effect": {}, "persistence_itt": {}}
    for f in glob.glob(str(ROOT / "gates/S8/artifacts/*/s8_*_c*.json.gz")):
        r = json.loads(gzip.decompress(open(f, "rb").read())); m = r["model"]; res = r["result"]
        if m not in CONF or res["rule"] != "i":
            continue
        c = clusters[res["cluster"]]; N, informed, fav, truth = A.info(c)
        t0, D, W = prm["t0"] * N, prm["D"] * N, prm["W"] * N
        v0 = res["initial_votes"]
        vl, _, _ = A.replay(v0, res["live"]); vb, _, _ = A.replay(v0, res["blind"])
        vals["board_effect"][(m, res["cluster"])] = (c["setting"], A.truth_share(vl, truth) - A.truth_share(vb, truth))
        vt0, _, _ = A.replay(v0, res["live"][:t0])
        pe = []
        for p in res["pulses"]:
            _, _, sp = A.replay(vt0, p["rows"], watch=p["recipients"], direction=p["direction"])
            _, _, su = A.replay(vt0, res["live"][t0:t0 + D + W], watch=p["recipients"], direction=p["direction"])
            pe.append(float((np.array(sp) - np.array(su))[D:].mean()))
        vals["persistence_itt"][(m, res["cluster"])] = (c["setting"], float(np.mean(pe)))
    out = {"doc": __doc__, "models": CONF}
    for k, d in vals.items():
        cl = sorted({j for (_, j) in d})
        X = np.array([[d[(m, j)][1] for m in CONF] for j in cl])          # clusters x models (in memory only)
        sett = [clusters[j]["setting"] for j in cl]
        for s in set(sett):
            idx = [i for i, x in enumerate(sett) if x == s]
            X[idx] -= X[idx].mean(0)                                       # centre per model within setting
        df = len(cl) - len(set(sett))
        C = X.T @ X / df
        sd = np.sqrt(np.diag(C)); R = C / np.outer(sd, sd)
        off = R[~np.eye(len(CONF), dtype=bool)]
        var_mean = float(np.ones(4) @ C @ np.ones(4) / 16); mean_var = float(np.mean(np.diag(C)))
        out[k] = {"df": df, "covariance": C.tolist(), "correlation": R.tolist(), "rho_mean_offdiag": float(off.mean()),
                  "rho_offdiag_range": [float(off.min()), float(off.max())],
                  "var_of_cross_model_mean": var_mean, "ratio_to_independent_models": var_mean / (mean_var / 4),
                  "rho_effective": (var_mean / (mean_var / 4) - 1) / 3}
        del X
    (ROOT / "gates/S9/results").mkdir(parents=True, exist_ok=True)
    (ROOT / "gates/S9/results/rho_from_s8.json").write_text(json.dumps(out, indent=1))
    for k in vals:
        o = out[k]
        print(f"{k}: rho mean off-diagonal {o['rho_mean_offdiag']:.2f} (range {o['rho_offdiag_range'][0]:.2f} to {o['rho_offdiag_range'][1]:.2f}), "
              f"effective rho {o['rho_effective']:.2f}, df {o['df']}")


if __name__ == "__main__":
    main()
