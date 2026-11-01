"""Exact large-N references for gate S1, on random-regular graphs of degree d (locally tree-like, so the Bethe-lattice
/ cavity results below are exact as N -> infinity). Independent of stpt.sim: closed forms and fixed-point recursions.

  bethe_ising       Ising model, uniform field H, temperature T: cavity field h = H + (d-1) g(h),
                    g(x) = atanh(tanh(beta J) tanh(beta x)) / beta (e.g. Mezard & Montanari 2009, ch. 14)
  rfim_popdyn       random-field Ising model, Gaussian fields N(0, sigma^2), finite T: the same recursion as a
                    population of cavity fields (population dynamics); replica-symmetric, exact for the RFIM
  dss_hysteresis    random-field Ising model at T = 0, ascending branch from all -1 under a rising field H
                    (single-flip avalanche dynamics): Dhar, Shukla & Sethna (1997), exact on the Bethe lattice
  gleeson_cascade   monotone threshold cascades from a random seed fraction rho0: Gleeson & Cahalane (2007), exact
                    on tree-like graphs (Watts 2002 model)
Citations are given as reference points to be verified; every formula is implemented here and checked in the tests.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import comb, ndtr


def _g(x, beta, J=1.0):
    return np.arctanh(np.tanh(beta * J) * np.tanh(beta * x)) / beta


def bethe_ising(d, T, H, J=1.0, iters=200_000, tol=1e-15):
    """m and nearest-neighbour correlation for the Ising model on the d-regular Bethe lattice (H > 0 selects the
    + state below T_c; H = 0 above T_c gives m = 0)."""
    beta = 1.0 / T
    h = H + 1.0
    for _ in range(iters):
        new = H + (d - 1) * _g(h, beta, J)
        if abs(new - h) < tol:
            h = new
            break
        h = new
    m = math.tanh(beta * (H + d * _g(h, beta, J)))
    a, b = math.exp(beta * J) * math.cosh(2 * beta * h), math.exp(-beta * J)
    return {"m": m, "bond": (a - b) / (a + b), "cavity_h": h, "T_c": 1.0 / math.atanh(1.0 / (d - 1)) * J}


def rfim_popdyn(d, T, sigma, H, J=1.0, M=200_000, iters=400, R=4, seed=0):
    """Population dynamics for the RFIM cavity fields; returns m, bond and their standard errors over R
    independent populations."""
    beta = 1.0 / T
    rng = np.random.Generator(np.random.PCG64(seed))
    ms, bs = [], []
    for _ in range(R):
        pop = np.full(M, H + 1.0)
        for _ in range(iters):
            idx = rng.integers(0, M, size=(M, d - 1))
            pop = H + sigma * rng.standard_normal(M) + _g(pop[idx], beta, J).sum(axis=1)
        idx = rng.integers(0, M, size=(M, d))
        loc = H + sigma * rng.standard_normal(M) + _g(pop[idx], beta, J).sum(axis=1)
        ms.append(float(np.mean(np.tanh(beta * loc))))
        h1, h2 = pop[rng.integers(0, M, M)], pop[rng.integers(0, M, M)]
        a = np.exp(beta * J) * np.cosh(beta * (h1 + h2)); b = np.exp(-beta * J) * np.cosh(beta * (h1 - h2))
        bs.append(float(np.mean((a - b) / (a + b))))
    se = lambda v: float(np.std(v, ddof=1) / math.sqrt(len(v)))
    return {"m": float(np.mean(ms)), "m_se": se(ms), "bond": float(np.mean(bs)), "bond_se": se(bs)}


def _dss_f(P, H, z, sigma, J):
    k = np.arange(z)
    return float(np.sum(comb(z - 1, k) * P ** k * (1 - P) ** (z - 1 - k) * ndtr((H + J * (2 * k - z)) / sigma)))


def dss_hysteresis(z, sigma, H, J=1.0, iters=100_000, tol=1e-15):
    """Ascending-branch magnetisation m(H) at T = 0: P* = smallest fixed point of P = f(P) (iterated from P = 0),
    m = 2 sum_k C(z,k) P*^k (1-P*)^(z-k) Phi((H + J(2k - z))/sigma) - 1."""
    P = 0.0
    for _ in range(iters):
        new = _dss_f(P, H, z, sigma, J)
        if abs(new - P) < tol:
            P = new
            break
        P = new
    k = np.arange(z + 1)
    up = float(np.sum(comb(z, k) * P ** k * (1 - P) ** (z - k) * ndtr((H + J * (2 * k - z)) / sigma)))
    return {"m": 2 * up - 1, "P": P}


def dss_jump(z, sigma, J=1.0, lo=-4.0, hi=4.0, n=8001, min_jump=0.05):
    """Field and size of the largest discontinuity of the ascending branch on a fine grid (None if smooth)."""
    Hs = np.linspace(lo, hi, n)
    m = np.array([dss_hysteresis(z, sigma, H, J)["m"] for H in Hs])
    dm = np.diff(m)
    i = int(np.argmax(dm))
    if dm[i] < min_jump:
        return None
    return {"H": float(0.5 * (Hs[i] + Hs[i + 1])), "size": float(dm[i]), "grid_step": float(Hs[1] - Hs[0])}


def gleeson_cascade(d, rho0, F, iters=100_000, tol=1e-15):
    """Final active fraction for monotone threshold cascades from a random seed fraction rho0 on a d-regular tree-like
    graph; F(x) = P(threshold <= x) (an agent activates when its fraction of active contacts reaches its threshold)."""
    m = np.arange(d)
    Fk = np.array([F(j / d) for j in range(d + 1)])
    q = rho0
    for _ in range(iters):
        new = rho0 + (1 - rho0) * float(np.sum(comb(d - 1, m) * q ** m * (1 - q) ** (d - 1 - m) * Fk[:d]))
        if abs(new - q) < tol:
            q = new
            break
        q = new
    k = np.arange(d + 1)
    rho = rho0 + (1 - rho0) * float(np.sum(comb(d, k) * q ** k * (1 - q) ** (d - k) * Fk))
    return {"rho": rho, "q": q}
