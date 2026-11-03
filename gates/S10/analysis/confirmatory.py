"""StPT confirmatory analysis (pre-registered at S10; coordination D2, D14/A16, D20-D21, D24, D26, D28-D31).

Outcomes per (model m, cluster j), from the run records (rows as written by gates/S8/s8_core.py, the harness format):
  board effect  b_mj = Y_live - Y_blind, Y = mean over sweeps 25-30 inclusive (snapshots at the end of sweeps 25..30)
                of the share of ordinary agents voting the correct option (D31). Live and blind share one initial state,
                one run key and one server start (paired; D14).
  persistence   p_mj = mean over the cluster's two pulsed branches of the ITT recipient effect: the share of ALL assigned
                recipients voting the pulse direction, averaged over the 5 sweeps after restoration, pulsed minus
                unpulsed (the unpulsed branch is the live main continuation) (D26).
Pooled estimand (D2, D24): theta = mean over the four confirmatory models of each model's mean effect; with shared
clusters this is the mean over clusters of c_j = mean_m (effect_mj).
Primary model, conditional on the story bank (D29): c_j = theta + u_block(j) + e_j, u ~ N(0, s_b^2) (server-start
block, mandatory under A16), REML; t reference with containment df = (number of start blocks - 1).
Generalisation to new stories (D29): c_j = theta + u_block + v_story + e_j, REML; df = min(blocks, stories) - 1.
Tests per contrast: superiority, two-sided, Holm across the two contrasts at family alpha 0.05; equivalence, TOST at
+/-0.03 with alpha 0.05 (90% interval inside the bound). Decision: effect / small effect within bound / equivalence /
inconclusive.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats

CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
BOUND, FAMILY_ALPHA, TOST_ALPHA = 0.03, 0.05, 0.05
N = 100


# ---------------------------------------------------------------- outcomes from records
def replay(votes0, rows, every=None, watch=None, direction=None):
    v = list(votes0); snaps = []; share = []
    for k, row in enumerate(rows):
        v[row[1]] = row[4]
        if watch is not None:
            share.append(sum(v[i] == direction for i in watch) / len(watch))
        if every and (k + 1) % every == 0:
            snaps.append(list(v))
    return v, snaps, share


def support(v, truth):
    return sum(x == truth for x in v) / len(v)


def check_pairing(res):
    """Refuse a cluster whose live and blind runs are not paired (same initial state, same agents and draws)."""
    if len(res["live"]) != len(res["blind"]):
        raise ValueError("live and blind runs differ in length")
    for a, b in zip(res["live"], res["blind"]):
        if a[0] != b[0] or a[1] != b[1] or a[6] != b[6]:
            raise ValueError("live and blind runs are not paired (agent or draw differs)")


def check_branch(res, t0):
    for p in res["pulses"]:
        for a, b in zip(p["rows"], res["live"][t0:]):
            if a[0] != b[0] or a[1] != b[1] or a[6] != b[6]:
                raise ValueError("pulsed branch does not share the main trajectory's agents and draws")


def outcomes(res, truth, t0=5, D=3, W=5, window=(25, 30)):
    check_pairing(res)
    v0 = res["initial_votes"]
    _, sl, _ = replay(v0, res["live"], every=N)
    _, sb, _ = replay(v0, res["blind"], every=N)
    live = [support(v0, truth)] + [support(v, truth) for v in sl]
    blind = [support(v0, truth)] + [support(v, truth) for v in sb]
    lo, hi = window
    out = {"Y_live": float(np.mean(live[lo:hi + 1])), "Y_blind": float(np.mean(blind[lo:hi + 1])),
           "board_final": live[-1] - blind[-1]}
    out["board"] = out["Y_live"] - out["Y_blind"]
    if res.get("pulses"):
        check_branch(res, t0 * N)
        vt0, _, _ = replay(v0, res["live"][:t0 * N])
        itt, imm, exp_ = [], [], []
        for p in res["pulses"]:
            _, _, sp = replay(vt0, p["rows"], watch=p["recipients"], direction=p["direction"])
            _, _, su = replay(vt0, res["live"][t0 * N:(t0 + D + W) * N], watch=p["recipients"], direction=p["direction"])
            d = np.array(sp) - np.array(su)
            itt.append(float(d[D * N:].mean())); imm.append(float(d[:D * N].mean()))
            upd = {row[1] for row in p["rows"][:D * N]}
            ex = [i for i in p["recipients"] if i in upd]
            if ex:
                _, _, ep = replay(vt0, p["rows"], watch=ex, direction=p["direction"])
                _, _, eu = replay(vt0, res["live"][t0 * N:(t0 + D + W) * N], watch=ex, direction=p["direction"])
                exp_.append(float((np.array(ep) - np.array(eu))[D * N:].mean()))
        out.update({"persistence": float(np.mean(itt)), "immediate": float(np.mean(imm)),
                    "persistence_exposed": float(np.mean(exp_)) if exp_ else None})
    return out


# ---------------------------------------------------------------- REML random-intercept model
def reml(y, groups):
    """y: (n,), groups: list of integer label arrays (one per random intercept). Returns theta, se, variance components."""
    y = np.asarray(y, float); n = len(y)
    Zs = []
    for g in groups:
        g = np.asarray(g); lev = {v: k for k, v in enumerate(sorted(set(g.tolist())))}
        Z = np.zeros((n, len(lev)))
        Z[np.arange(n), [lev[v] for v in g.tolist()]] = 1.0
        Zs.append(Z)
    X = np.ones((n, 1))

    def V_of(lp):
        V = math.exp(lp[0]) * np.eye(n)
        for Z, l in zip(Zs, lp[1:]):
            V += math.exp(l) * Z @ Z.T
        return V

    def nll(lp):
        V = V_of(lp)
        try:
            L = np.linalg.cholesky(V)
        except np.linalg.LinAlgError:
            return 1e10
        Vi = np.linalg.inv(V)
        XtViX = (X.T @ Vi @ X).item()
        beta = (X.T @ Vi @ y).item() / XtViX
        r = y - beta
        return 0.5 * (2 * np.log(np.diag(L)).sum() + math.log(XtViX) + float(r @ Vi @ r))

    v0 = max(np.var(y, ddof=1), 1e-8)
    best = None
    for init in ([math.log(v0)] + [math.log(v0 / 4)] * len(Zs), [math.log(v0)] + [math.log(v0 / 100)] * len(Zs)):
        r = optimize.minimize(nll, init, method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 4000})
        if best is None or r.fun < best.fun:
            best = r
    lp = np.clip(best.x, -40, 5)
    V = V_of(lp); Vi = np.linalg.inv(V)
    XtViX = (X.T @ Vi @ X).item()
    theta = (X.T @ Vi @ y).item() / XtViX
    return {"theta": theta, "se": math.sqrt(1.0 / XtViX), "var_resid": math.exp(lp[0]),
            "var_groups": [math.exp(l) for l in lp[1:]]}


def infer(y, blocks, stories=None):
    """Conditional (block RE) or generalisation (block + story RE) inference for one contrast."""
    groups = [blocks] if stories is None else [blocks, stories]
    fit = reml(y, groups)
    nb = len(set(np.asarray(blocks).tolist()))
    df = nb - 1 if stories is None else min(nb, len(set(np.asarray(stories).tolist()))) - 1
    t = fit["theta"] / fit["se"]
    p = 2 * stats.t.sf(abs(t), df)
    tq = stats.t.ppf(1 - TOST_ALPHA, df)
    ci90 = (fit["theta"] - tq * fit["se"], fit["theta"] + tq * fit["se"])
    tq95 = stats.t.ppf(0.975, df)
    return {**fit, "df": df, "t": t, "p_two_sided": p, "ci90": ci90,
            "ci95": (fit["theta"] - tq95 * fit["se"], fit["theta"] + tq95 * fit["se"]),
            "tost_equivalent": bool(ci90[0] > -BOUND and ci90[1] < BOUND)}


def holm(pvals: dict, alpha=FAMILY_ALPHA):
    order = sorted(pvals, key=pvals.get); rej = {}; stop = False
    for k, name in enumerate(order):
        if not stop and pvals[name] <= alpha / (len(order) - k):
            rej[name] = True
        else:
            stop = True; rej[name] = False
    return rej


def decide(sig, eq):
    return {(True, True): "small effect within the equivalence bound", (True, False): "effect",
            (False, True): "equivalence (no effect beyond +/-0.03)", (False, False): "inconclusive"}[(sig, eq)]


def primary(table, cluster_meta, generalisation=True):
    """table[(model, cluster)] = outcomes dict; cluster_meta[cluster] = {'start_block', 'story_key'}.
    Returns the two confirmatory results (conditional = confirmatory; generalisation reported beside)."""
    clusters = sorted(cluster_meta)
    for m in CONF:
        for j in clusters:
            if (m, j) not in table:
                raise ValueError(f"missing outcome for {m}, cluster {j}")
    blocks = [cluster_meta[j]["start_block"] for j in clusters]
    stories = [cluster_meta[j]["story_key"] for j in clusters]
    res = {}
    for contrast in ("board", "persistence"):
        c = [float(np.mean([table[(m, j)][contrast] for m in CONF])) for j in clusters]
        res[contrast] = {"conditional": infer(c, blocks), "n_clusters": len(c)}
        if generalisation:
            res[contrast]["generalisation"] = infer(c, blocks, stories)
    rej = holm({k: res[k]["conditional"]["p_two_sided"] for k in res})
    for k in res:
        res[k]["holm_significant"] = rej[k]
        res[k]["decision"] = decide(rej[k], res[k]["conditional"]["tost_equivalent"])
    return res


def subset_estimate(table, cluster_meta, models, contrast):
    """Secondary/sensitivity: the same conditional model on the mean over a subset of models (D20, D21, D24)."""
    clusters = sorted(cluster_meta)
    c = [float(np.mean([table[(m, j)][contrast] for m in models])) for j in clusters]
    return infer(c, [cluster_meta[j]["start_block"] for j in clusters])
