"""S10: pre-registered predictions (brief: "simulate fresh kernels ... propagating kernel uncertainty"; S9 plan §5).
CPU only. The predicted values are written ONCE to a sealed file (same mechanism as D27) and never printed; only the
file's sha256 is printed. The proposal is to unseal it into the OSF registration at posting, after the freeze.

  python gates/S10/predictions.py -> gates/S10/sealed/s10_predictions.json.gz.b64
Procedure: for each of the 200 kernel bootstrap draws (S9, from S8) and 5 simulated runs per draw, simulate every
confirmatory cluster (its actual graph, allocation and evidence; D25 initial vote with a balanced placeholder; D26
pulse; S4 start jitter) under each model, and compute the pre-registered estimands exactly as the confirmatory analysis
defines them: the board effect on the sweep 25-30 window (D31) and ITT persistence, per model and pooled over the four
confirmatory models. The predictive distribution (mean, 5/50/95 percentiles) includes kernel uncertainty and run
noise. Per-cluster predictions are stored for calibration and discrepancy measures after the run.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S9")); sys.path.insert(0, str(ROOT / "gates/S8"))
import s9_kernels as KK  # noqa: E402
import s9_sim as S  # noqa: E402
from analyse_s8 import write_sealed  # noqa: E402
from stpt import evidence as E  # noqa: E402

DRAWS, REPS = 200, 5


def main():
    KD = KK.point_and_draws(DRAWS)
    T = {m: v["T"] for m, v in json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"].items()}
    vc = json.load(open(ROOT / "gates/S4/results/s4_variance_components.json"))
    js = {m: math.sqrt(vc[m]["w3"]["var_probe_x_start_nats2"]) / T[m] for m in KK.ALL}
    cl = json.load(open(ROOT / "gates/S10/clusters/confirmatory_clusters.json"))
    prepared = []
    for c in cl:
        truth = c["truth"]
        typ = np.zeros(100, np.int64); fav = np.zeros(100, np.int64)
        for pos, ids in c["alloc"]["holders"].items():
            if ids:
                it = c["alloc"]["items"][ids[0]]
                typ[int(pos)] = KK.ACC_TYPE[it["accuracy"]]; fav[int(pos)] = int(it["favours"] == truth)
        adj = c["adj"]; indptr = np.cumsum([0] + [len(a) for a in adj]).astype(np.int64); nbr = np.array([j for a in adj for j in a], np.int64)
        prepared.append((c["cluster"], indptr, nbr, typ, fav))
    rng = np.random.Generator(np.random.PCG64(E.seed_of("S10-predictions")))
    per = {m: {"board": [], "persistence": []} for m in KK.ALL}
    per_cluster = {m: {"board": np.zeros((DRAWS * REPS, len(cl))), "persistence": np.zeros((DRAWS * REPS, len(cl)))} for m in KK.ALL}
    k = 0
    for d in range(DRAWS):
        for _ in range(REPS):
            streams = [S.make_stream(rng, 30, 5, 3, 5) for _ in prepared]
            boards = [S.make_cluster(rng, lambda N_, d_, s_, ip=ip, nb=nb: (ip, nb, None), 0, typ_override=(typ, fav))
                      for (_, ip, nb, typ, fav) in prepared]
            for m in KK.ALL:
                b, p = [], []
                for jj, (cl_, st) in enumerate(zip(boards, streams)):
                    r = S.simulate_cluster(cl_, st, KD[m]["draws"][d], js[m], 30, 5, 3, 5)
                    bw = float(np.mean(np.array(r["live"][25:31]) - np.array(r["blind"][25:31])))
                    b.append(bw); p.append(r["persistence"])
                    per_cluster[m]["board"][k, jj] = bw; per_cluster[m]["persistence"][k, jj] = r["persistence"]
                per[m]["board"].append(float(np.mean(b))); per[m]["persistence"].append(float(np.mean(p)))
            k += 1
        if d % 50 == 49:
            print("draws", d + 1, flush=True)
    q = lambda a: {"mean": float(np.mean(a)), "p05": float(np.quantile(a, 0.05)), "p50": float(np.quantile(a, 0.5)), "p95": float(np.quantile(a, 0.95))}
    pooled = {ctr: q(np.mean([per[m][ctr] for m in KK.CONF], 0)) for ctr in ("board", "persistence")}
    out = {"doc": __doc__, "n_simulated_studies": DRAWS * REPS, "pooled_confirmatory": pooled,
           "per_model": {m: {ctr: q(per[m][ctr]) for ctr in ("board", "persistence")} for m in KK.ALL},
           "per_cluster_mean": {m: {ctr: per_cluster[m][ctr].mean(0).tolist() for ctr in ("board", "persistence")} for m in KK.ALL},
           "per_cluster_p05_p95": {m: {ctr: [np.quantile(per_cluster[m][ctr], 0.05, 0).tolist(), np.quantile(per_cluster[m][ctr], 0.95, 0).tolist()]
                                       for ctr in ("board", "persistence")} for m in KK.ALL},
           "clusters": [c["cluster"] for c in cl]}
    h = write_sealed(out, ROOT / "gates/S10/sealed/s10_predictions.json.gz.b64")
    print("sealed predictions written once; sha256", h)


if __name__ == "__main__":
    main()
