"""Asymmetric extension. Each tie has two directions: J[i<-j] (how j's state pulls i)
and J[j<-i]. With probability 1-eps the two directions are equal (reciprocal tie);
with probability eps the reverse direction is redrawn independently (negative w.p. rho).
eps = 0 recovers the symmetric Viana–Bray model; eps = 1 is fully non-reciprocal.

No energy function exists for eps > 0, so no parallel tempering and no Gibbs measure:
we run plain heat-bath dynamics and measure what the dynamics actually reach.
"""
import numpy as np
from numba import njit


def make_graph_asym(N, c, rho, eps, rng):
    M = rng.poisson(c * N / 2)
    a = rng.integers(0, N, M); b = rng.integers(0, N, M)
    keep = a != b; a, b = a[keep], b[keep]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    key = np.unique(lo.astype(np.int64) * N + hi)
    lo, hi = (key // N).astype(np.int64), (key % N).astype(np.int64)
    E = len(lo)
    J_fwd = np.where(rng.random(E) < rho, -1, 1)              # J[hi <- lo]
    redraw = rng.random(E) < eps
    J_bwd = np.where(redraw, np.where(rng.random(E) < rho, -1, 1), J_fwd)  # J[lo <- hi]
    # CSR over receiving node: row i lists (j, J[i<-j])
    src = np.concatenate([hi, lo]); dst = np.concatenate([lo, hi])
    Jall = np.concatenate([J_fwd, J_bwd]).astype(np.int64)
    order = np.argsort(src, kind="stable")
    src, dst, Jall = src[order], dst[order], Jall[order]
    indptr = np.zeros(N + 1, np.int64); np.add.at(indptr, src + 1, 1)
    return np.cumsum(indptr), dst, Jall


@njit(cache=True)
def run_dyn(indptr, nbr, J, beta, n_warm, n_meas, seed):
    """Two replicas from independent random starts, independent noise.
    Returns time-averaged |m|, m^2, q^2, |q|, plus the self-overlap C between the
    configuration at end of warm-up and later times (persistence: 1 = frozen)."""
    np.random.seed(seed)
    N = indptr.shape[0] - 1
    s = np.empty((2, N), np.int64)
    for r in range(2):
        for i in range(N):
            s[r, i] = 1 if np.random.random() < 0.5 else -1
    dmax = 0
    for i in range(N):
        if indptr[i + 1] - indptr[i] > dmax:
            dmax = indptr[i + 1] - indptr[i]
    tab = np.empty(2 * dmax + 1)
    for h in range(-dmax, dmax + 1):
        tab[h + dmax] = 1.0 / (1.0 + np.exp(-2.0 * beta * h))
    ref = np.empty((2, N), np.int64)
    out = np.zeros(6)
    for t in range(n_warm + n_meas):
        for r in range(2):
            for i in range(N):
                h = 0
                for k in range(indptr[i], indptr[i + 1]):
                    h += J[k] * s[r, nbr[k]]
                s[r, i] = 1 if np.random.random() < tab[h + dmax] else -1
        if t == n_warm - 1:
            for r in range(2):
                for i in range(N):
                    ref[r, i] = s[r, i]
        if t >= n_warm:
            q = 0; m1 = 0; m2 = 0; c1 = 0; c2 = 0
            for i in range(N):
                q += s[0, i] * s[1, i]; m1 += s[0, i]; m2 += s[1, i]
                c1 += s[0, i] * ref[0, i]; c2 += s[1, i] * ref[1, i]
            q /= N; m1 /= N; m2 /= N
            out[0] += 0.5 * (abs(m1) + abs(m2))
            out[1] += 0.5 * (m1 * m1 + m2 * m2)
            out[2] += q * q
            out[3] += abs(q)
            out[4] += 0.5 * (c1 + c2) / N     # persistence C(t_w + tau, t_w)
            out[5] += 1
    return out[:5] / out[5]
