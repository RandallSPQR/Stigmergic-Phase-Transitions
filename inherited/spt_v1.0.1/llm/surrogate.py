"""Stage 2 surrogate simulator: networks of agents whose update rule is a fitted LLM response function.

Update of agent i with k_i contacts (random sequential; one sweep = N updates; two replicas, same graph):
  with prob p          : voter step — pick a uniformly random contact j; copy s_j if i perceives j as ally,
                         take −s_j if rival
  otherwise            : s_i = +1 with prob σ(η),
                         η = k_i^-α (b_a M_a − b_r M_r) + γ s_i + h_C + h_L·L + h_O·O
                         M_a, M_r = sums of s_j over contacts i perceives as allies / rivals;
                         L, O = ±1 drawn fresh on every call (letter mapping and option order randomised per
                         call, the Stage 3 protocol, Amendment 3d); h_C is a real content field.
  explicit-jitter mode : η → η/κ + N(0, σ²), κ = (1 + πσ²/8)^-1/2 (σ = endpoint's measured repeat SD).
                         For independent per-call jitter this is, by construction, approximately the same chain
                         as the marginal (fitted) rule; run as a consistency check.
Ties: undirected ER (mean degree c) or random-regular (degree d) graph; each tie is rival w.p. ρ; with prob ε
the reverse perception is redrawn independently (directed tie perceptions, as sim/asym.py).
Measures (time-averaged over the measurement window): |m|, signed m, m², overlap q (|q| and q²) between
replicas, persistence (overlap with own configuration at end of warm-up), flip rate (share of updates that
change state), fraction of unsatisfied directed ties (ally with different position / rival with same position).
"""
import numpy as np
from numba import njit

# parameter columns
P_VOTER, ALPHA, B_A, B_R, GAMMA, H_C, H_L, H_O, SIGMA, KAPPA = range(10)
NPAR = 10


def make_graph(N, rho, eps, rng, kind="er", c=4.0, d=4, max_tries=200):
    """Return CSR (indptr, nbr, tie) over receivers; tie[k] = +1 ally / −1 rival as perceived by the receiver."""
    if kind == "er":
        M = rng.poisson(c * N / 2)
        a = rng.integers(0, N, M); b = rng.integers(0, N, M)
        keep = a != b; a, b = a[keep], b[keep]
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = np.unique(lo.astype(np.int64) * N + hi)
        lo, hi = key // N, key % N
    elif kind == "rrg":
        import networkx as nx            # uniform-ish simple d-regular graph (Steger–Wormald pairing)
        g = nx.random_regular_graph(d, N, seed=int(rng.integers(2**31)))
        e = np.array(g.edges(), dtype=np.int64)
        lo, hi = np.minimum(e[:, 0], e[:, 1]), np.maximum(e[:, 0], e[:, 1])
    else:
        raise ValueError(kind)
    E = len(lo)
    t_fwd = np.where(rng.random(E) < rho, -1, 1)                      # perception of hi about lo
    redraw = rng.random(E) < eps
    t_bwd = np.where(redraw, np.where(rng.random(E) < rho, -1, 1), t_fwd)
    recv = np.concatenate([hi, lo]); send = np.concatenate([lo, hi]); tie = np.concatenate([t_fwd, t_bwd])
    order = np.argsort(recv, kind="stable")
    recv, send, tie = recv[order], send[order], tie[order]
    indptr = np.zeros(N + 1, np.int64); np.add.at(indptr, recv + 1, 1)
    return np.cumsum(indptr), send.astype(np.int64), tie.astype(np.int64)


@njit(cache=True)
def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


@njit(cache=True)
def run(indptr, nbr, tie, typ, par, n_warm, n_meas, seed, explicit_jitter, init_bias):
    np.random.seed(seed)
    N = indptr.shape[0] - 1
    s = np.empty((2, N), np.int64)
    for r in range(2):
        for i in range(N):
            s[r, i] = 1 if np.random.random() < 0.5 + init_bias else -1
    ref = np.empty((2, N), np.int64)
    out = np.zeros(9)   # |m|, m, m2, |q|, q2, persistence, flip rate, unsatisfied, count
    nflip = 0.0; nupd = 0.0
    for t in range(n_warm + n_meas):
        for r in range(2):
            for _u in range(N):
                i = np.random.randint(N)
                p = par[typ[i]]
                k = indptr[i + 1] - indptr[i]
                old = s[r, i]
                if k > 0 and np.random.random() < p[P_VOTER]:
                    j = indptr[i] + np.random.randint(k)
                    new = s[r, nbr[j]] * tie[j]
                else:
                    ma = 0.0; mr = 0.0
                    for q in range(indptr[i], indptr[i + 1]):
                        if tie[q] > 0:
                            ma += s[r, nbr[q]]
                        else:
                            mr += s[r, nbr[q]]
                    scale = 1.0 if k == 0 else k ** (-p[ALPHA])
                    L = 1.0 if np.random.random() < 0.5 else -1.0
                    O = 1.0 if np.random.random() < 0.5 else -1.0
                    eta = scale * (p[B_A] * ma - p[B_R] * mr) + p[GAMMA] * old + p[H_C] + p[H_L] * L + p[H_O] * O
                    if explicit_jitter:
                        eta = eta / p[KAPPA] + p[SIGMA] * np.random.standard_normal()
                    new = 1 if np.random.random() < _sig(eta) else -1
                s[r, i] = new
                if t >= n_warm:
                    nupd += 1.0
                    if new != old:
                        nflip += 1.0
        if t == n_warm - 1:
            for r in range(2):
                for i in range(N):
                    ref[r, i] = s[r, i]
        if t >= n_warm:
            q = 0.0; m1 = 0.0; m2 = 0.0; c1 = 0.0; c2 = 0.0; un = 0.0
            for i in range(N):
                q += s[0, i] * s[1, i]; m1 += s[0, i]; m2 += s[1, i]
                c1 += s[0, i] * ref[0, i]; c2 += s[1, i] * ref[1, i]
                for e in range(indptr[i], indptr[i + 1]):
                    for r in range(2):
                        agree = s[r, i] == s[r, nbr[e]]
                        if (tie[e] > 0 and not agree) or (tie[e] < 0 and agree):
                            un += 0.5
            q /= N; m1 /= N; m2 /= N
            out[0] += 0.5 * (abs(m1) + abs(m2)); out[1] += 0.5 * (m1 + m2); out[2] += 0.5 * (m1 * m1 + m2 * m2)
            out[3] += abs(q); out[4] += q * q; out[5] += 0.5 * (c1 + c2) / N
            out[7] += un / max(indptr[N], 1); out[8] += 1
    res = out[:8] / out[8]
    res[6] = nflip / max(nupd, 1.0)
    return res


MEASURES = ["abs_m", "m", "m2", "abs_q", "q2", "persistence", "flip_rate", "unsatisfied"]


def params_from_fit(names, vec, framing, sigma=0.0, p_override=None):
    """Map a fitted mixture-model vector (llm/voter.py: ['logit_p','alpha','b_a','b_r', Z names...]) to a parameter row.
    neutral framing: the letter-A field h is applied as h·L (positions relabelled per call); no content field."""
    v = dict(zip(names, vec))
    row = np.zeros(NPAR)
    row[P_VOTER] = 1 / (1 + np.exp(-v["logit_p"])) if p_override is None else p_override
    row[ALPHA], row[B_A], row[B_R] = v["alpha"], v["b_a"], v["b_r"]
    row[GAMMA] = v.get("gamma", 0.0)
    if framing == "neutral":
        row[H_C], row[H_L] = 0.0, v.get("h", 0.0)
    else:
        row[H_C], row[H_L] = v.get("h_C", 0.0), v.get("h_L", 0.0)
    row[H_O] = v.get("h_O", 0.0)
    row[SIGMA] = sigma or 0.0
    row[KAPPA] = (1 + np.pi * row[SIGMA] ** 2 / 8) ** -0.5
    return row


def ising_row(beta):
    """Naive 'Ising reading' of an endpoint: symmetric heat-bath with logit coupling β per neighbour
    (logit P = β Σ J s; equivalent to the Viana–Bray heat bath at T = 2/β), no inertia, fields, voter or k-scaling."""
    row = np.zeros(NPAR); row[B_A] = row[B_R] = beta; row[KAPPA] = 1.0
    return row
