"""StPT simulator core: memoryless agents on a graph, each update a draw from a per-agent kernel table.

Adapted from SPT v1.0.1's simulator (inherited/spt_v1.0.1/llm/surrogate.py and kernel_test.py): random-sequential
updates (the updated agent drawn uniformly WITH replacement; one sweep = N updates) and a table kernel. Two changes for
StPT: (1) the kernel is PER AGENT, so each agent's private evidence enters as its own table,
    P[i, own, n_plus] = probability that agent i votes +1 (A), given its own current vote (own = 0 for -1, 1 for +1)
    and the number n_plus of its contacts DISPLAYING +1;
(2) every random number is drawn by numpy's PCG64 from a recorded seed OUTSIDE the compiled loop (the order of
updates and one uniform per update), so a run is reproducible bit for bit and independent of numba's RNG.
`display` is the vote each agent shows to its contacts; it equals the real vote except where a study overrides it
(display pulses, built at a later gate). Decision noise, evidence and kernels are the caller's: this module only runs
the chain. Validated at gate S1 (gates/S1/) against exact large-N references.
"""
from __future__ import annotations

import hashlib

import numpy as np
from numba import njit

NETWORKX_PIN = "3.7"          # random_regular_graph builds different graphs from one seed across versions (SPT entry 51)


def rrg(N: int, d: int, seed: int):
    """Simple d-regular graph on N nodes (networkx's random_regular_graph, pinned), as CSR (indptr, nbr), plus a
    fingerprint (sha256[:16] of the sorted edge list) and checks: simple, d-regular, connected."""
    import networkx as nx
    if nx.__version__ != NETWORKX_PIN:
        raise RuntimeError(f"networkx {nx.__version__} != pinned {NETWORKX_PIN}: graphs would differ from the record")
    g = nx.random_regular_graph(d, N, seed=int(seed))
    e = np.array(sorted(tuple(sorted(x)) for x in g.edges()), dtype=np.int64)
    info = {"N": N, "d": d, "seed": int(seed), "edges": len(e),
            "simple": bool(len(e) == len({tuple(x) for x in e.tolist()}) and np.all(e[:, 0] != e[:, 1])),
            "regular": bool(all(deg == d for _, deg in g.degree())), "connected": bool(nx.is_connected(g)),
            "fingerprint": hashlib.sha256(e.tobytes()).hexdigest()[:16]}
    recv = np.concatenate([e[:, 0], e[:, 1]]); send = np.concatenate([e[:, 1], e[:, 0]])
    order = np.lexsort((send, recv))
    recv, send = recv[order], send[order]
    indptr = np.zeros(N + 1, np.int64)
    np.add.at(indptr, recv + 1, 1)
    return np.cumsum(indptr), send.astype(np.int64), info


@njit(cache=True)
def _sweep(indptr, nbr, ptab, s, display, follow, order, unif):
    """Apply len(order) updates in sequence. s, display: int8 arrays of +-1. follow[i] = 1 if agent i's display tracks
    its vote (normal), 0 if frozen by an override. Returns the number of vote changes."""
    flips = 0
    for t in range(order.shape[0]):
        i = order[t]
        n_plus = 0
        for q in range(indptr[i], indptr[i + 1]):
            if display[nbr[q]] > 0:
                n_plus += 1
        own = 1 if s[i] > 0 else 0
        new = 1 if unif[t] < ptab[i, own, n_plus] else -1
        if new != s[i]:
            flips += 1
            s[i] = new
            if follow[i]:
                display[i] = new
    return flips


class Chain:
    """One trajectory. All randomness from numpy PCG64(seed); state (s, display, follow) can be copied for branches."""

    def __init__(self, indptr, nbr, ptab, s_init, seed: int):
        self.indptr, self.nbr = indptr, nbr
        self.ptab = np.ascontiguousarray(ptab, dtype=np.float64)
        N = indptr.shape[0] - 1
        dmax = int(np.max(np.diff(indptr)))
        if self.ptab.shape != (N, 2, dmax + 1):
            raise ValueError(f"ptab shape {self.ptab.shape} != (N, 2, dmax+1) = {(N, 2, dmax + 1)}")
        self.s = np.array(s_init, dtype=np.int8)
        self.display = self.s.copy()
        self.follow = np.ones(N, np.int8)
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self.N, self.updates = N, 0

    def sweeps(self, n: int = 1) -> int:
        """n sweeps of N random-sequential updates; returns vote changes."""
        k = n * self.N
        order = self.rng.integers(0, self.N, size=k, dtype=np.int64)
        unif = self.rng.random(k)
        self.updates += k
        return int(_sweep(self.indptr, self.nbr, self.ptab, self.s, self.display, self.follow, order, unif))

    def set_table(self, ptab):
        ptab = np.ascontiguousarray(ptab, dtype=np.float64)
        if ptab.shape != self.ptab.shape:
            raise ValueError("table shape changed")
        self.ptab = ptab

    def stable(self) -> bool:
        """True when no agent's deterministic (0/1) table would change its vote (a fixed point of T = 0 dynamics)."""
        npl = np.zeros(self.N, np.int64)
        np.add.at(npl, np.repeat(np.arange(self.N), np.diff(self.indptr)), (self.display[self.nbr] > 0).astype(np.int64))
        p = self.ptab[np.arange(self.N), (self.s > 0).astype(np.int64), npl]
        want = np.where(p >= 1.0, 1, np.where(p <= 0.0, -1, 0))
        return bool(np.all((want == 0) | (want == self.s)))

    def relax(self, max_sweeps: int = 10_000) -> int:
        """Sweep until stable (deterministic tables); returns sweeps used. Raises if not stable by max_sweeps."""
        for n in range(1, max_sweeps + 1):
            self.sweeps(1)
            if self.stable():
                return n
        raise RuntimeError("not stable")

    def m(self) -> float:
        return float(self.s.mean())

    def bond(self) -> float:
        """Mean s_i s_j over edges (each edge counted twice in CSR, which leaves the mean unchanged)."""
        src = np.repeat(np.arange(self.N), np.diff(self.indptr))
        return float(np.mean(self.s[src].astype(np.int64) * self.s[self.nbr]))


def heat_bath_table(N, d, beta, J=1.0, H=0.0, h=None):
    """Glauber heat bath for +-J Ising spins with uniform field H and per-agent fields h (the random-field Ising
    model; with h = 0 the plain Ising model): P(+1) = sigma(2 beta (J (2 n_plus - d) + H + h_i)), own vote unused."""
    h = np.zeros(N) if h is None else np.asarray(h, float)
    n = np.arange(d + 1)
    loc = J * (2 * n[None, :] - d) + H + h[:, None]
    p = 1.0 / (1.0 + np.exp(-2.0 * beta * loc))
    return np.repeat(p[:, None, :], 2, axis=1)


def zero_T_table(N, d, J=1.0, H=0.0, h=None):
    """T = 0 rule (sign of the local field): P(+1) = 1 if J (2 n_plus - d) + H + h_i > 0 else 0."""
    h = np.zeros(N) if h is None else np.asarray(h, float)
    n = np.arange(d + 1)
    loc = J * (2 * n[None, :] - d) + H + h[:, None]
    p = (loc > 0).astype(float)
    return np.repeat(p[:, None, :], 2, axis=1)


def threshold_table(N, d, phi):
    """Monotone threshold (Watts) rule: an active agent stays active; an inactive one activates when the fraction of
    active contacts reaches its threshold phi_i. Uses the own-vote dimension of the table."""
    n = np.arange(d + 1)
    p = np.zeros((N, 2, d + 1))
    p[:, 0, :] = (n[None, :] / d >= np.asarray(phi, float)[:, None]).astype(float)
    p[:, 1, :] = 1.0
    return p
