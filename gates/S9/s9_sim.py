"""S9 board simulator (gates/S9/S9_PLAN.md §1). Kernel tables from s9_kernels; boards as in the harness.

A simulated cluster: a random-regular graph (N = 100, d = 4), an allocation (half informed; each informed agent's
source 3/4 or 9/10 with equal weight; its report names the truth with that probability; truth = 1), the D25 placeholder
(balanced within evidence type), and one random stream (agent order, uniforms, jitter normals) shared by the live run,
the blind run and the pulse branches, and by every model (the study keys randomness by cluster, not by model).
Votes: 0/1 contents; type 0 uninformed, 2 informed 3/4, 3 informed 9/10.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

N = 100


@njit(cache=True)
def _p(p, eps):
    if eps == 0.0:
        return p
    p = min(max(p, 1e-9), 1 - 1e-9)
    z = math.log(p / (1 - p)) + eps
    return 1.0 / (1.0 + math.exp(-z))


@njit(cache=True)
def init_votes(typ, fav, ph, Pinit, u, eps, jsd):
    s = np.zeros(typ.shape[0], np.int64)
    for i in range(typ.shape[0]):
        ref = fav[i] if typ[i] > 0 else ph[i]
        agree = 1 if ph[i] == ref else 0
        p = _p(Pinit[typ[i], agree], jsd * eps[i])
        s[i] = ref if u[i] < p else 1 - ref
    return s


@njit(cache=True)
def step(i, s, indptr, nbr, typ, fav, Plive, Pblind, live, alt_on, alt_mask, alt_dir, u, e):
    ref = fav[i] if typ[i] > 0 else s[i]
    agree = 1 if s[i] == ref else 0
    if live:
        m = 0
        for q in range(indptr[i], indptr[i + 1]):
            shown = alt_dir if (alt_on and alt_mask[q]) else s[nbr[q]]
            if shown == ref:
                m += 1
        p = Plive[typ[i], agree, m]
    else:
        p = Pblind[typ[i], agree]
    p = _p(p, e)
    s[i] = ref if u < p else 1 - ref


@njit(cache=True)
def run(s0, indptr, nbr, typ, fav, Plive, Pblind, live, order, unif, eps, jsd, every):
    """Run len(order) updates from s0; returns the final votes and the truth share after every `every` updates
    (including the start)."""
    s = s0.copy()
    nmask = np.zeros(nbr.shape[0], np.bool_)
    n_snap = order.shape[0] // every + 1
    snap = np.zeros(n_snap)
    snap[0] = s.mean()
    k = 1
    for t in range(order.shape[0]):
        step(order[t], s, indptr, nbr, typ, fav, Plive, Pblind, live, False, nmask, 0, unif[t], jsd * eps[t])
        if (t + 1) % every == 0:
            snap[k] = s.mean(); k += 1
    return s, snap


@njit(cache=True)
def pulse_pair(s0, indptr, nbr, typ, fav, Plive, Pblind, order, unif, eps, jsd, recip, alt_mask, alt_dir, D):
    """Pulsed and unpulsed branches from s0 with the same stream; per step, the recipients' share voting alt_dir in
    each branch, and whether each recipient updated during the pulse."""
    sp = s0.copy(); su = s0.copy()
    steps = order.shape[0]
    a = np.zeros(steps); b = np.zeros(steps)
    nrec = 0
    for i in range(recip.shape[0]):
        if recip[i]:
            nrec += 1
    upd = np.zeros(recip.shape[0], np.bool_)
    for t in range(steps):
        i = order[t]; on = t < D
        step(i, su, indptr, nbr, typ, fav, Plive, Pblind, True, False, alt_mask, alt_dir, unif[t], jsd * eps[t])
        step(i, sp, indptr, nbr, typ, fav, Plive, Pblind, True, on and recip[i], alt_mask, alt_dir, unif[t], jsd * eps[t])
        if on and recip[i]:
            upd[i] = True
        ca = 0; cb = 0
        for v in range(recip.shape[0]):
            if recip[v]:
                ca += su[v] == alt_dir; cb += sp[v] == alt_dir
        a[t] = ca / nrec; b[t] = cb / nrec
    return a, b, upd


def make_cluster(rng, rrg, graph_seed, typ_override=None):
    """A fresh cluster at the confirmatory setting (or with given types/favours for the S8 validation)."""
    indptr, nbr, _ = rrg(N, 4, graph_seed)
    if typ_override is None:
        typ = np.zeros(N, np.int64)
        inf = rng.choice(N, N // 2, replace=False)
        acc = np.where(rng.random(N // 2) < 0.5, 0.75, 0.9)
        typ[inf] = np.where(acc == 0.75, 2, 3)
        fav = np.zeros(N, np.int64)
        fav[inf] = (rng.random(N // 2) < acc).astype(np.int64)
    else:
        typ, fav = typ_override
    ph = np.zeros(N, np.int64)                      # placeholder balanced within evidence type (type x favour)
    for key in sorted({(int(t), int(f)) for t, f in zip(typ, fav)}):
        members = [i for i in range(N) if (typ[i], fav[i]) == key]
        members = list(rng.permutation(members))
        first = int(rng.integers(0, 2))
        for k, i in enumerate(members):
            ph[i] = first if k % 2 == 0 else 1 - first
    return {"indptr": indptr, "nbr": nbr, "typ": typ, "fav": fav, "ph": ph}


def make_stream(rng, H, t0, D, W):
    """One stream per cluster: init uniforms/normals; main-run order, uniforms, normals (shared by live and blind; the
    blind run uses the same arrays); per pulse direction an independent recipient set, its altered edges and its own
    branch stream starting at t0 (equal to the main stream from t0, so the unpulsed branch is the live continuation)."""
    steps = H * N
    st = {"u0": rng.random(N), "e0": rng.standard_normal(N), "order": rng.integers(0, N, steps), "unif": rng.random(steps),
          "eps": rng.standard_normal(steps), "pulses": []}
    for d in (0, 1):
        R = rng.choice(N, 10, replace=False)
        st["pulses"].append({"R": R, "dir": d, "pick": [rng.choice(4, 3, replace=False) for _ in range(10)]})
    return st


def simulate_cluster(cl, st, K, jsd, H, t0, D, W, every=N):
    """One cluster under one model's kernel tables K. Returns live and blind truth shares by sweep, persistence (ITT;
    mean of the two branches) and the per-branch values, the immediate response, and exposure."""
    s0 = init_votes(cl["typ"], cl["fav"], cl["ph"], K["init"], st["u0"], st["e0"], jsd)
    sv, live_snap = run(s0, cl["indptr"], cl["nbr"], cl["typ"], cl["fav"], K["live"], K["blind"], True,
                        st["order"], st["unif"], st["eps"], jsd, every)
    _, blind_snap = run(s0, cl["indptr"], cl["nbr"], cl["typ"], cl["fav"], K["live"], K["blind"], False,
                        st["order"], st["unif"], st["eps"], jsd, every)
    s_t0, _ = run(s0, cl["indptr"], cl["nbr"], cl["typ"], cl["fav"], K["live"], K["blind"], True,
                  st["order"][:t0 * N], st["unif"][:t0 * N], st["eps"][:t0 * N], jsd, N)
    lo, hi = t0 * N, (t0 + D + W) * N
    per, imm, expo = [], [], []
    for p in st["pulses"]:
        recip = np.zeros(N, np.bool_); recip[p["R"]] = True
        alt = np.zeros(cl["nbr"].shape[0], np.bool_)
        for r, pick in zip(p["R"], p["pick"]):
            alt[cl["indptr"][r] + pick] = True
        a, b, upd = pulse_pair(s_t0, cl["indptr"], cl["nbr"], cl["typ"], cl["fav"], K["live"], K["blind"],
                               st["order"][lo:hi], st["unif"][lo:hi], st["eps"][lo:hi], jsd, recip, alt, p["dir"], D * N)
        d = b - a
        imm.append(float(d[:D * N].mean())); per.append(float(d[D * N:].mean())); expo.append(float(upd[p["R"]].mean()))
    return {"live": live_snap, "blind": blind_snap, "persistence": float(np.mean(per)), "persistence_branches": per,
            "immediate": float(np.mean(imm)), "exposure": float(np.mean(expo))}
