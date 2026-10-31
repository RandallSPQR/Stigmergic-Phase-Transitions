"""Viana–Bray baseline: +/-J Ising spins on Erdos–Renyi graphs (mean degree c),
fraction rho of antiferromagnetic (negative) couplings, heat-bath Glauber dynamics
with parallel tempering. Two independent replicas per temperature give overlaps.

Analytic (replica-symmetric / cavity) transition lines for ER graphs, J=1:
  paramagnet -> ferromagnet:  c (1-2 rho) tanh(beta) = 1
  paramagnet -> spin glass:   c tanh(beta)^2       = 1
  percolation (beta -> inf):  c = 1
"""
import numpy as np
from numba import njit


def make_graph(N, c, rho, rng):
    """ER multigraph-free graph: Poisson(cN/2) edges, self-loops and duplicates removed.
    Returns CSR arrays (indptr, nbr, J) with symmetric couplings."""
    M = rng.poisson(c * N / 2)
    a = rng.integers(0, N, M)
    b = rng.integers(0, N, M)
    keep = a != b
    a, b = a[keep], b[keep]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    key = np.unique(lo.astype(np.int64) * N + hi)
    lo, hi = (key // N).astype(np.int64), (key % N).astype(np.int64)
    Jv = np.where(rng.random(len(lo)) < rho, -1, 1).astype(np.int64)
    src = np.concatenate([lo, hi])
    dst = np.concatenate([hi, lo])
    Jall = np.concatenate([Jv, Jv])
    order = np.argsort(src, kind="stable")
    src, dst, Jall = src[order], dst[order], Jall[order]
    indptr = np.zeros(N + 1, np.int64)
    np.add.at(indptr, src + 1, 1)
    indptr = np.cumsum(indptr)
    return indptr, dst, Jall


@njit(cache=True)
def _energy(s, indptr, nbr, J):
    N = s.shape[0]
    e = 0
    for i in range(N):
        for k in range(indptr[i], indptr[i + 1]):
            e -= J[k] * s[i] * s[nbr[k]]
    return e // 2


@njit(cache=True)
def run_sample(indptr, nbr, J, betas, n_pow, seed):
    """Run 2**n_pow sweeps. Measurements every sweep are accumulated in log bins:
    bin b covers sweeps [2**(b-1), 2**b). Returns acc[bin, temp, obs] (sums) and counts.
    obs: 0 q^2, 1 q^4, 2 |q|, 3 m^2, 4 m^4, 5 |m|, 6 energy/N
    """
    np.random.seed(seed)
    N = indptr.shape[0] - 1
    K = betas.shape[0]
    dmax = 0
    for i in range(N):
        d = indptr[i + 1] - indptr[i]
        if d > dmax:
            dmax = d
    # heat-bath table: P(s=+1 | h) for h in [-dmax, dmax]
    tab = np.empty((K, 2 * dmax + 1))
    for k in range(K):
        for h in range(-dmax, dmax + 1):
            tab[k, h + dmax] = 1.0 / (1.0 + np.exp(-2.0 * betas[k] * h))
    # spins[rep, slot, i]; perm[rep, slot] = temperature index of the configuration in slot
    s = np.empty((2, K, N), np.int64)
    for r in range(2):
        for k in range(K):
            for i in range(N):
                s[r, k, i] = 1 if np.random.random() < 0.5 else -1
    tof = np.empty((2, K), np.int64)  # temp index -> slot
    for r in range(2):
        for k in range(K):
            tof[r, k] = k
    E = np.empty((2, K), np.int64)  # energy of slot
    for r in range(2):
        for k in range(K):
            E[r, k] = _energy(s[r, k], indptr, nbr, J)
    nbins = n_pow + 1
    acc = np.zeros((nbins, K, 7))
    cnt = np.zeros(nbins)
    swaps = np.zeros(K - 1)
    total = 1 << n_pow
    for t in range(1, total + 1):
        # sweeps: each slot at its current temperature
        for r in range(2):
            for k in range(K):
                sl = tof[r, k]
                for i in range(N):
                    h = 0
                    for q in range(indptr[i], indptr[i + 1]):
                        h += J[q] * s[r, sl, nbr[q]]
                    new = 1 if np.random.random() < tab[k, h + dmax] else -1
                    if new != s[r, sl, i]:
                        E[r, sl] += 2 * s[r, sl, i] * h  # dE = -h*(new-old) = 2*old*h
                        s[r, sl, i] = new
        # parallel tempering swaps
        for r in range(2):
            start = t & 1
            for k in range(start, K - 1, 2):
                a = tof[r, k]
                b = tof[r, k + 1]
                d = (betas[k] - betas[k + 1]) * (E[r, a] - E[r, b])
                if d >= 0 or np.random.random() < np.exp(d):
                    tof[r, k] = b
                    tof[r, k + 1] = a
                    swaps[k] += 1
        # measure
        b = 0
        x = t
        while x > 0:
            b += 1
            x >>= 1
        # t in [2^(b-1), 2^b) -> bin b
        if b >= nbins:
            b = nbins - 1
        for k in range(K):
            s1 = tof[0, k]
            s2 = tof[1, k]
            qq = 0
            m1 = 0
            m2 = 0
            for i in range(N):
                qq += s[0, s1, i] * s[1, s2, i]
                m1 += s[0, s1, i]
                m2 += s[1, s2, i]
            q = qq / N
            mm1 = m1 / N
            mm2 = m2 / N
            acc[b, k, 0] += q * q
            acc[b, k, 1] += q ** 4
            acc[b, k, 2] += abs(q)
            acc[b, k, 3] += 0.5 * (mm1 * mm1 + mm2 * mm2)
            acc[b, k, 4] += 0.5 * (mm1 ** 4 + mm2 ** 4)
            acc[b, k, 5] += 0.5 * (abs(mm1) + abs(mm2))
            acc[b, k, 6] += 0.5 * (E[0, s1] + E[1, s2]) / N
        cnt[b] += 1
    return acc, cnt, swaps / (2.0 * total / 2.0)


def analytic_TF(c, rho):
    x = 1.0 / (c * (1 - 2 * rho))
    return 1.0 / np.arctanh(x) if 0 < x < 1 else np.nan


def analytic_TSG(c):
    return 1.0 / np.arctanh(1.0 / np.sqrt(c))
