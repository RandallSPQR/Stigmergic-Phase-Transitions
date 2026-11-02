"""Display-pulse settings for S8: exposure, immediate response and (reported, not used to choose) persistence, simulated
with development proxy kernels. Development data only; no live board has run.

  python analysis/pulse_design.py  -> analysis/results/pulse_design.json

Proxy kernel per model, at its D23 T, fitted by least squares to the S4 W3 live probes (mean logit over the six
starts, divided by T):
  uninformed:  logit P(keep own vote)            = a_u + c_u (m - 2),   m = contacts showing the own vote
  informed:    logit P(vote the reported option) = a_i + b_i s + c_i (m - 2),   s = +1 if own vote = reported option
                                                   else -1, m = contacts showing the reported option
Boards: random-regular d = 4, N = 100; D18 evidence (half informed, sources 3/4 and 9/10, report right with its
accuracy); initial votes by rule (i) (informed follow their report with q0 from analysis/results/initial_vote.json,
uninformed 50/50). Burn-in 5 sweeps, then a saved state; pulsed and unpulsed branches share every random number
(common random numbers, as the harness does). Pulse: r recipients (random), k of each recipient's contacts shown to it
as voting the pulse direction (random A/B) for D sweeps; then a persistence window of W = 5 sweeps after restoration.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gates" / "S4"))
sys.path.insert(0, str(ROOT))
import analyse_s4 as A  # noqa: E402
from stpt import sim  # noqa: E402
from stpt import evidence as E  # noqa: E402

MODELS = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b", "llama-3.1-8b-it"]
N, BURN, W = 100, 5, 5
GRID_K, GRID_D, GRID_R = (2, 3, 4), (1, 2, 3, 5), (5, 10, 20)
REPS, GRAPHS = 400, 8


def fit_kernels():
    T = {m: v["T"] for m, v in json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"].items()}
    probes, runs = A.load([ROOT / "gates/S4/artifacts/20261102T1535Z", ROOT / "gates/S4/artifacts/20261102T1535Zb"])
    ctx = {c["context_id"]: c for c in json.load(open(ROOT / "gates/S4/probes/s4_contexts.json"))}
    out = {}
    for m in MODELS:
        st = runs[m]; sids = sorted(st)
        Xu, yu, Xi, yi = [], [], [], []
        for pid, p in probes.items():
            c = ctx[p["context_id"]]
            if p["wording"] != "w3" or not c["live"]:
                continue
            lA = np.mean([A.ell(st[s]["first"][pid]) for s in sids])
            lA = lA if p["layout"]["letter_of_content"]["A"] == "A" else -lA
            ref = c["report_favours"] if c["informed"] else c["own_vote"]
            lref = (lA if ref == "A" else -lA) / T[m]
            mm = c["contacts_A"] if ref == "A" else 4 - c["contacts_A"]
            if c["informed"]:
                Xi.append([1.0, 1.0 if c["own_vote"] == ref else -1.0, mm - 2.0]); yi.append(lref)
            else:
                Xu.append([1.0, mm - 2.0]); yu.append(lref)
        bu = np.linalg.lstsq(np.array(Xu), np.array(yu), rcond=None)[0]
        bi = np.linalg.lstsq(np.array(Xi), np.array(yi), rcond=None)[0]
        iv = json.load(open(ROOT / "analysis/results/initial_vote.json"))["models"][m]["chain"]
        out[m] = {"T": T[m], "a_u": float(bu[0]), "c_u": float(bu[1]), "a_i": float(bi[0]), "b_i": float(bi[1]), "c_i": float(bi[2]),
                  "q0": {a: iv[a]["q0_rule_i"] for a in ("3/4", "9/10")}, "n_uninformed_probes": len(yu), "n_informed_probes": len(yi)}
    return out


@njit(cache=True)
def _sig(z):
    return 1.0 / (1.0 + math.exp(-z))


@njit(cache=True)
def _step(i, s, indptr, nbr, informed, fav, par, alt_on, alt_dir, alt_mask, u):
    # displayed contacts for viewer i
    m_ref = 0
    ref = fav[i] if informed[i] else s[i]
    for q in range(indptr[i], indptr[i + 1]):
        j = nbr[q]
        shown = s[j]
        if alt_on and alt_mask[q]:
            shown = alt_dir
        if shown == ref:
            m_ref += 1
    if informed[i]:
        sgn = 1.0 if s[i] == ref else -1.0
        p = _sig(par[2] + par[3] * sgn + par[4] * (m_ref - 2.0))
    else:
        p = _sig(par[0] + par[1] * (m_ref - 2.0))
    s[i] = ref if u < p else 1 - ref


@njit(cache=True)
def _burn(order, unif, s, indptr, nbr, informed, fav, par):
    nomask = np.zeros(nbr.shape[0], np.bool_)
    for t in range(order.shape[0]):
        _step(order[t], s, indptr, nbr, informed, fav, par, False, 0, nomask, unif[t])


@njit(cache=True)
def _pair(indptr, nbr, informed, fav, par, s0, order, unif, recip_mask, alt_mask, alt_dir, D, Wn, Nn, prop_mask):
    """Run unpulsed and pulsed branches from s0 with the same order and uniforms. Returns per-step shares (recipients
    voting dir; propagation pool voting dir) for both branches, and whether each recipient updated during the pulse."""
    steps = order.shape[0]
    sp = s0.copy(); su = s0.copy()
    rec_share = np.zeros((2, steps)); prop_share = np.zeros((2, steps))
    nrec = recip_mask.sum(); nprop = prop_mask.sum()
    updated = np.zeros(Nn, np.int8)
    for t in range(steps):
        i = order[t]
        on = t < D
        _step(i, su, indptr, nbr, informed, fav, par, False, alt_dir, alt_mask, unif[t])
        _step(i, sp, indptr, nbr, informed, fav, par, on and recip_mask[i], alt_dir, alt_mask, unif[t])
        if on and recip_mask[i]:
            updated[i] = 1
        a = 0; b = 0; c = 0; d = 0
        for v in range(Nn):
            if recip_mask[v]:
                a += su[v] == alt_dir; b += sp[v] == alt_dir
            if prop_mask[v]:
                c += su[v] == alt_dir; d += sp[v] == alt_dir
        rec_share[0, t] = a / nrec; rec_share[1, t] = b / nrec
        if nprop > 0:
            prop_share[0, t] = c / nprop; prop_share[1, t] = d / nprop
    return rec_share, prop_share, updated


def simulate(par, q0, k, Dsw, r, seed):
    rng = np.random.Generator(np.random.PCG64(seed))
    res = {"exposure": [], "immediate": [], "persist_window": [], "persist_end": [], "propagation": [], "prop_pool": []}
    for g in range(GRAPHS):
        indptr, nbr, _ = sim.rrg(N, 4, E.seed_of("pulse-design-graph", g))
        for _ in range(REPS // GRAPHS):
            informed = np.zeros(N, np.int64); informed[rng.choice(N, N // 2, replace=False)] = 1
            acc = np.where(rng.random(N) < 0.5, 0.75, 0.9)
            fav = np.where(rng.random(N) < acc, 1, 0).astype(np.int64)          # truth = 1
            s = np.zeros(N, np.int64)
            for i in range(N):
                if informed[i]:
                    qq = q0["3/4"] if acc[i] == 0.75 else q0["9/10"]
                    s[i] = fav[i] if rng.random() < qq else 1 - fav[i]
                else:
                    s[i] = 1 if rng.random() < 0.5 else 0
            burn = rng.integers(0, N, BURN * N); ub = rng.random(BURN * N)
            _burn(burn, ub, s, indptr, nbr, informed, fav, par)
            R = rng.choice(N, r, replace=False); recip = np.zeros(N, np.bool_); recip[R] = True
            alt = np.zeros(len(nbr), np.bool_)
            for i in R:
                q = np.arange(indptr[i], indptr[i + 1]); alt[rng.choice(q, k, replace=False)] = True
            closed = recip.copy()
            for i in R:
                closed[nbr[indptr[i]:indptr[i + 1]]] = True
            prop = ~closed
            dirn = int(rng.integers(0, 2))
            D = Dsw * N; steps = D + W * N
            order = rng.integers(0, N, steps); u = rng.random(steps)
            rs, ps, upd = _pair(indptr, nbr, informed, fav, par, s, order, u, recip, alt, dirn, D, W * N, N, prop)
            diff = rs[1] - rs[0]; pdiff = ps[1] - ps[0]
            res["exposure"].append(upd[R].mean())
            res["immediate"].append(diff[:D].mean())
            res["persist_window"].append(diff[D:].mean())
            res["persist_end"].append(diff[-1])
            res["propagation"].append(pdiff.mean())
            res["prop_pool"].append(prop.sum())
    out = {}
    for key, v in res.items():
        v = np.array(v, float)
        out[key] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1))}
    sdp = out["persist_window"]["sd"]
    out["pairs_for_80pct_power_at_0.05"] = float(((1.96 + 0.84) * sdp / 0.05) ** 2)
    return out


def main():
    K = fit_kernels()
    out = {"doc": __doc__, "kernels": K, "grid": {}}
    for m in MODELS:
        kk = K[m]; par = np.array([kk["a_u"], kk["c_u"], kk["a_i"], kk["b_i"], kk["c_i"]])
        for k in GRID_K:
            for Dsw in GRID_D:
                for r in GRID_R:
                    out["grid"][f"{m}|k={k}|D={Dsw}|r={r}"] = simulate(par, kk["q0"], k, Dsw, r, E.seed_of("pulse-design", m, k, Dsw, r))
        print(m, {x: round(v, 2) for x, v in kk.items() if isinstance(v, float)})
    (ROOT / "analysis/results/pulse_design.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
