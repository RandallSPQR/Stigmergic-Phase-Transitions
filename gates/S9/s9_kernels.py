"""S9 kernel tables from the S8 development readouts (gates/S9/S9_PLAN.md §1). Development data only.

Types: 0 uninformed, 1 informed 3/5, 2 informed 3/4, 3 informed 9/10. Reference option: the report's option (informed)
or the agent's own vote (uninformed). Cells hold the mean of the EXACT readout probability P(vote reference) =
sigma(l_ref / T) over the S8 calls in the cell:
  live[type, s, m]  s = own vote agrees with the reference (always 1 for uninformed), m = contacts showing it (0-4)
  blind[type, s]    the same on the blind board (no contacts)
  init[type, s]     the first call (rule (i)): s = the placeholder agrees with the reference
Sparse cells are shrunk toward a per-type least-squares logistic fit (logit P = a + b s + c (m - 2)) with weight
n / (n + 20). A bootstrap draw resamples the 8 S8 clusters with replacement.
"""
from __future__ import annotations

import glob
import gzip
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
ALL = CONF + ["llama-3.1-8b-it"]
ACC_TYPE = {"3/5": 1, "3/4": 2, "9/10": 3}
SHRINK = 20.0


def sig(z):
    return 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))


def load_rows():
    """Per model, per S8 cluster: lists of (kind, type, s, m, l_ref/T)."""
    clusters = {c["cluster"]: c for c in json.load(open(ROOT / "gates/S8/inputs/clusters.json"))}
    out = {m: {} for m in ALL}
    for f in glob.glob(str(ROOT / "gates/S8/artifacts/*/s8_*_c*.json.gz")):
        r = json.loads(gzip.decompress(open(f, "rb").read())); m = r["model"]; res = r["result"]; T = res["T"]
        c = clusters[res["cluster"]]
        typ, fav = [0] * 100, [None] * 100
        for pos, ids in c["alloc"]["holders"].items():
            if ids:
                it = c["alloc"]["items"][ids[0]]; typ[int(pos)] = ACC_TYPE[it["accuracy"]]; fav[int(pos)] = it["favours"]
        rows = []
        for row in res["init"]:
            ag, ph, _, lA, miss = row
            if miss or lA is None:
                continue
            ref = fav[ag] if typ[ag] else ph
            rows.append(("init", typ[ag], int(ph == ref), 0, (lA if ref == "A" else -lA) / T))
        for kind in ("live", "blind"):
            for row in res[kind]:
                if row[7] or row[5] is None:
                    continue
                ag, own, shown, lA = row[1], row[2], row[3], row[5]
                ref = fav[ag] if typ[ag] else own
                rows.append((kind, typ[ag], int(own == ref), shown.count(ref) if kind == "live" else 0, (lA if ref == "A" else -lA) / T))
        out[m][res["cluster"]] = rows
    return out


def tables(rows_by_cluster, cluster_ids):
    """Kernel tables from the rows of the given clusters (with multiplicity)."""
    acc = {k: {} for k in ("live", "blind", "init")}
    fit = {k: {t: [] for t in range(4)} for k in ("live", "blind", "init")}
    for j in cluster_ids:
        for kind, t, s, m, l in rows_by_cluster[j]:
            key = (t, s, m)
            a = acc[kind].setdefault(key, [0.0, 0])
            a[0] += sig(l); a[1] += 1
            fit[kind][t].append((1.0, 2.0 * s - 1.0, m - 2.0, l))
    T = {"live": np.zeros((4, 2, 5)), "blind": np.zeros((4, 2)), "init": np.zeros((4, 2)),
         "n_live": np.zeros((4, 2, 5)), "n_blind": np.zeros((4, 2)), "n_init": np.zeros((4, 2))}
    for kind in ("live", "blind", "init"):
        for t in range(4):
            X = np.array(fit[kind][t]) if fit[kind][t] else None
            if X is not None and len(X) >= 3:
                cols = [0, 1, 2] if kind == "live" else [0, 1]
                beta = np.linalg.lstsq(X[:, cols], X[:, 3], rcond=None)[0]
                beta = np.concatenate([beta, np.zeros(3 - len(beta))])
            else:
                beta = np.zeros(3)
            for s in (0, 1):
                for m in (range(5) if kind == "live" else [0]):
                    prior = sig(beta[0] + beta[1] * (2 * s - 1) + beta[2] * (m - 2))
                    tot, n = acc[kind].get((t, s, m), [0.0, 0])
                    w = n / (n + SHRINK)
                    v = w * (tot / n if n else prior) + (1 - w) * prior
                    if kind == "live":
                        T["live"][t, s, m] = v; T["n_live"][t, s, m] = n
                    else:
                        T[kind][t, s] = v; T[f"n_{kind}"][t, s] = n
    return T


def point_and_draws(n_draws=200, seed=20261103):
    rows = load_rows()
    rng = np.random.Generator(np.random.PCG64(seed))
    out = {}
    for m in ALL:
        ids = sorted(rows[m])
        point = tables(rows[m], ids)
        draws = [tables(rows[m], list(rng.choice(ids, len(ids), replace=True))) for _ in range(n_draws)]
        out[m] = {"point": point, "draws": draws}
    return out
