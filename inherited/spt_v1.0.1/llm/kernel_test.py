"""Three-kernel test (plan: llm/KERNEL_TEST_PLAN.md, committed before any kernel was computed).

  python llm/kernel_test.py run [--R 400]     # K_fixed, K_fixed-A3, K_live (n0 = 20; sensitivity 5, 100); no API calls
  python llm/kernel_test.py cost              # K_avg prompt counts and cost estimate (no calls)

A kernel is a table T[idx(c, s0)] = P(+1 | contact configuration c = (n_aP, n_aQ, n_rP, n_rQ), own position s0) for one
point. Simulation: surrogate.run with ONLY its update rule replaced by a table lookup and its random start replaced by
the live start (measurement lines verbatim), on the live Stage 3 graphs. Outputs: results/llm/kernel_test/.
"""
import argparse, inspect, itertools, json, math, os, sys, textwrap
import numpy as np, pandas as pd
from numba import njit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battery, stage2, stage3, surrogate as S
from endpoints import E

ROOT = stage3.ROOT
OUT = os.path.join(ROOT, "results", "llm", "kernel_test")
POINTS = list(stage3.POINTS)
MEAS = ["abs_m", "m", "persistence", "excess_unsat", "flip_rate", "abs_q"]
NT = 625 * 2
N0_MAIN, N0_SENS = 20, (5, 100)


def idx(c, s0):
    return (c[0] * 125 + c[1] * 25 + c[2] * 5 + c[3]) * 2 + (1 if s0 > 0 else 0)


def expand_nc(T, rho):
    """No-contacts arms: agents have graph neighbours but do not see them, so P(+1) depends on s0 only; copy the
    k = 0 entry to every k = 4 configuration the simulator can encounter."""
    T = T.copy()
    for c, s0 in configs(stage3.D, rho):
        T[idx(c, s0)] = T[idx((0, 0, 0, 0), s0)]
    return T


def configs(k, rho):
    out = []
    for c in itertools.product(range(k + 1), repeat=4):
        if sum(c) == k and (rho > 0 or c[2] + c[3] == 0):
            out += [(c, 1), (c, -1)]
    return out


# ---------------------------------------------------------------- simulator with a kernel table (verbatim measurement)
def _build_sim():
    src = textwrap.dedent(inspect.getsource(S.run.py_func))
    rep = [("@njit(cache=True)\n", ""),
           ("def run(indptr, nbr, tie, typ, par, n_warm, n_meas, seed, explicit_jitter, init_bias):",
            "def run_kernel(indptr, nbr, tie, S0, T, n_warm, n_meas, seed):"),
           ("            s[r, i] = 1 if np.random.random() < 0.5 + init_bias else -1", "            s[r, i] = S0[r, i]")]
    for a, b in rep:
        assert src.count(a) == 1, a
        src = src.replace(a, b)
    a = src.index("                p = par[typ[i]]\n"); b = src.index("                s[r, i] = new\n")
    body = ("                old = s[r, i]\n                c = 0\n"
            "                for q in range(indptr[i], indptr[i + 1]):\n"
            "                    if tie[q] > 0:\n                        c += 125 if s[r, nbr[q]] > 0 else 25\n"
            "                    else:\n                        c += 5 if s[r, nbr[q]] > 0 else 1\n"
            "                c = c * 2 + (1 if old > 0 else 0)\n"
            "                new = 1 if np.random.random() < T[c] else -1\n")
    src = src[:a] + body + src[b:]
    ns = {"np": np}
    exec(src, ns)
    return njit(cache=False)(ns["run_kernel"]), src


SIM, SIM_SRC = None, None


def sim():
    global SIM, SIM_SRC
    if SIM is None:
        SIM, SIM_SRC = _build_sim()
    return SIM


# ---------------------------------------------------------------- live data
def live_rows(pid):
    key, framing, rho, contacts = stage3.POINTS[pid]
    mode = E[key][2]
    D = []
    for g in range(stage3.N_GRAPHS):
        for r in (0, 1):
            d = pd.read_csv(os.path.join(stage3.OUT, "chains", pid, f"g{g}_r{r}.csv.gz"), dtype={"counts": str})
            d["chain"] = g * 2 + r; D.append(d)
    d = pd.concat(D, ignore_index=True)
    d["counts"] = d["counts"].str.zfill(4) if contacts else "0000"     # nc: the configuration is not shown
    d = d[d.kept_after_invalid == 0]
    c = np.array([[int(x) for x in s] for s in d["counts"]])
    d["idx"] = [idx(tuple(cc), s0) for cc, s0 in zip(c, d.s0)]
    if mode == "lp":
        d["p"] = np.where(d.mapping == 0, d.pA, 1 - d.pA)       # P(+1) of this call
    else:
        d["p"] = (d.new == 1).astype(float)
    return d


def live_starts(pid, g):
    return np.stack([np.load(os.path.join(stage3.OUT, "chains", pid, f"g{g}_r{r}_states.npy"))[0] for r in (0, 1)]).astype(np.int64)


def feats(i):
    s0 = 1 if i % 2 else -1; c = i // 2
    naP, naQ, nrP, nrQ = c // 125, (c // 25) % 5, (c // 5) % 5, c % 5
    Ma, Mr = naP - naQ, nrP - nrQ
    return [1.0, Ma, Mr, s0, s0 * Ma, s0 * Mr]


def logit_fit(X, S1, n, ridge=1e-6, iters=60):
    """Aggregated soft-label logistic: maximise sum S1 log σ + (n − S1) log(1 − σ)."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        g = X.T @ (S1 - n * p) - ridge * b
        H = X.T @ (X * (n * p * (1 - p))[:, None]) + ridge * np.eye(len(b))
        step = np.linalg.solve(H, g); b += step
        if np.abs(step).max() < 1e-10:
            break
    return b


def live_kernel(stats, n0):
    """stats: DataFrame idx -> (S1 = Σ p, n). Hierarchical posterior mean toward a logistic prior. Returns (T, prior)."""
    ii = stats.index.values
    X = np.array([feats(i) for i in ii]); keep = X.std(0) > 0; keep[0] = True
    X = X[:, keep]
    b = logit_fit(X, stats.S1.values, stats.n.values.astype(float))
    allX = np.array([feats(i) for i in range(NT)])[:, keep]
    prior = 1 / (1 + np.exp(-allX @ b))
    T = prior.copy()
    T[ii] = (stats.S1.values + n0 * prior[ii]) / (stats.n.values + n0)
    if set(ii) <= {0, 1}:                       # no-contacts arm
        T = expand_nc(T, 0.5)
    return T, prior


def chain_stats(d):
    return {ch: g.groupby("idx").agg(S1=("p", "sum"), n=("p", "size")) for ch, g in d.groupby("chain")}


def pooled(cs, chains):
    return pd.concat([cs[c] for c in chains]).groupby(level=0).sum()


# ---------------------------------------------------------------- fixed kernels
def battery_kernel(pid, rng=None):
    """Stage 1 battery kernel: mean over (2 mappings x 2 option orders) of P(choose P), perm-0 prompts."""
    key, framing, rho, contacts = stage3.POINTS[pid]
    d = pd.read_csv(os.path.join(ROOT, f"results/llm/stage1/main/{key}.csv"), dtype={"counts": str})
    d = d[(d.arm == stage2.FRAME_ARM[framing]) & (d.perm == 0)].copy(); d["counts"] = d.counts.str.zfill(4)
    sampled = E[key][2] == "sample"
    if sampled:
        d["a"] = (d.answer == "A").astype(float); d["v"] = d.answer.notna().astype(float)
        g = d.groupby(["counts", "s0", "mapping", "order"]).agg(x=("a", "sum"), n=("v", "sum"))
        pa = (g.x / g.n) if rng is None else pd.Series(rng.beta(1 + g.x, 1 + g.n - g.x), index=g.index)
    else:
        pa = d.groupby(["counts", "s0", "mapping", "order"]).pA.mean()
    pa = pa.to_dict()
    T = np.full(NT, np.nan)
    for c, s0 in configs(4, rho):
        vals = []
        for m in (0, 1):
            for o in (0, 1):
                if framing == "neutral":
                    if m == 0:
                        vals.append(pa[("".join(map(str, c)), s0, 0, o)])
                    else:
                        sw = (c[1], c[0], c[3], c[2])
                        vals.append(1 - pa[("".join(map(str, sw)), -s0, 0, o)])
                else:
                    v = pa[("".join(map(str, c)), s0, m, o)]
                    vals.append(v if m == 0 else 1 - v)
        T[idx(c, s0)] = np.mean(vals)
    return T


def a3_kernel(row, k, rho):
    """Surrogate rule averaged over L, O (plus P5's voter step): exactly surrogate.run's marginal update."""
    T = np.full(NT, np.nan)
    for c, s0 in configs(k, rho):
        Ma, Mr = c[0] - c[1], c[2] - c[3]
        soc = (k ** -row[S.ALPHA]) * (row[S.B_A] * Ma - row[S.B_R] * Mr) if k else 0.0
        pl = np.mean([1 / (1 + math.exp(-(soc + row[S.GAMMA] * s0 + row[S.H_C] + row[S.H_L] * L + row[S.H_O] * O)))
                      for L in (1, -1) for O in (1, -1)])
        if k and row[S.P_VOTER] > 0:
            pl = row[S.P_VOTER] * (c[0] + c[3]) / k + (1 - row[S.P_VOTER]) * pl
        T[idx(c, s0)] = pl
    return T if k else expand_nc(T, rho)


# ---------------------------------------------------------------- simulate one kernel
def simulate(pid, table_fn, R, salt, starts=None):
    """table_fn(run, graph) -> table. Returns DataFrame of R mean-of-5 rows."""
    key, framing, rho, contacts = stage3.POINTS[pid]
    fl = pd.read_csv(os.path.join(ROOT, "results/llm/stage2/floor.csv"))
    floor = fl[(fl.graph == "rrg") & (fl.N == stage3.N)].groupby("rho").unsat_floor.mean().loc[rho]
    G = [stage3.graph(pid, g) for g in range(stage3.N_GRAPHS)]
    S0 = starts if starts is not None else [live_starts(pid, g) for g in range(stage3.N_GRAPHS)]
    f = sim(); rows = []
    for run in range(R):
        per = []
        for g in range(stage3.N_GRAPHS):
            T = table_fn(run, g)
            seed = int(stage3._seed("kernel-test", salt, pid, run, g) % 2**31)
            r = dict(zip(S.MEASURES, f(*G[g], S0[g], T, stage3.N_WARM, stage3.N_MEAS, seed)))
            r["excess_unsat"] = r["unsatisfied"] - floor; per.append(r)
        rows.append({m: float(np.mean([x[m] for x in per])) for m in MEAS})
    return pd.DataFrame(rows)


def run_all(R):
    os.makedirs(OUT, exist_ok=True)
    pred = {p["id"].split(" ")[0]: p for p in json.load(open(os.path.join(ROOT, "results/llm/stage2/stage3_predictions.json")))}
    for p in json.load(open(os.path.join(ROOT, "results/llm/stage2/stage3_predictions_nocontacts.json"))):
        pred[p["id"]] = p
    obs = pd.read_csv(os.path.join(ROOT, "results/llm/stage3/summary.csv")).set_index("point")
    evals, amp, cfg_rows, sims = [], [], [], {}
    for pid in POINTS:
        key, framing, rho, contacts = stage3.POINTS[pid]
        k = stage3.D if contacts else 0
        d = live_rows(pid); cs = chain_stats(d); chains = sorted(cs)
        allst = pooled(cs, chains)
        fit = stage2.load_fit(key, framing)
        mode_fixed = "fitted" if contacts else "fields_only"
        rng = np.random.default_rng(stage3._seed("kernel-test-boot", pid))
        boots = {}
        for n0 in (N0_MAIN,) + N0_SENS:
            boots[n0] = [live_kernel(pooled(cs, list(rng.choice(chains, len(chains)))), n0)[0] for _ in range(R)]
        draws = np.random.default_rng(stage3._seed("kernel-test-a3", pid)).integers(len(fit["draws"]), size=(R, stage3.N_GRAPHS))
        a3_tab = {}
        def a3(run, g):
            dd = int(draws[run, g])
            if dd not in a3_tab:
                a3_tab[dd] = a3_kernel(stage2.param_row(fit, framing, dd, mode_fixed), k, rho)
            return a3_tab[dd]
        kern = {"K_fixed-A3": a3}
        if contacts:
            bat0 = battery_kernel(pid)
            if E[key][2] == "sample":
                brng = np.random.default_rng(stage3._seed("kernel-test-bat", pid))
                btabs = [battery_kernel(pid, brng) for _ in range(R)]
                kern["K_fixed"] = lambda run, g: btabs[run]
            else:
                kern["K_fixed"] = lambda run, g: bat0
        else:
            kern["K_fixed"] = a3                     # no battery cell at k = 0: the committed fields-only rule
        for n0 in (N0_MAIN,) + N0_SENS:
            kern[f"K_live_n0{n0}"] = (lambda B: (lambda run, g: B[run]))(boots[n0])
        res = {}
        for name, fn in kern.items():
            res[name] = simulate(pid, fn, R, name)
            res[name].to_csv(os.path.join(OUT, f"sims_{pid}_{name}.csv"), index=False)
        sims[pid] = res
        # pass/fail per kernel
        prim = pred[pid]["primary"]
        for name, df in res.items():
            for m in MEAS:
                lo, hi = np.percentile(df[m], [5, 95])
                evals.append(dict(point=pid, kernel=name, measure=m, primary=m in prim, observed=float(obs.loc[pid, m]),
                                  lo=float(lo), hi=float(hi), mean=float(df[m].mean()), sd=float(df[m].std(ddof=1)),
                                  inside=bool(lo <= obs.loc[pid, m] <= hi)))
        # per-configuration table and per-step discrepancy (weights = live visit frequency)
        Tlive, prior = live_kernel(allst, N0_MAIN)
        Tfix = kern["K_fixed"](0, 0) if contacts else None
        Ta3 = a3_kernel(stage2.param_row(fit, framing, None, mode_fixed), k, rho)
        w = allst.n / allst.n.sum()
        lg = lambda p: np.clip(np.log(np.clip(p, 1e-12, 1) / np.clip(1 - p, 1e-12, 1)), -6, 6)
        kl = lambda p, q: (p * np.log(np.clip(p, 1e-6, 1) / np.clip(q, 1e-6, 1))
                           + (1 - p) * np.log(np.clip(1 - p, 1e-6, 1) / np.clip(1 - q, 1e-6, 1)))
        ii = allst.index.values
        for i in ii:
            f_ = feats(i); c = i // 2
            cfg_rows.append(dict(point=pid, counts=f"{c // 125}{(c // 25) % 5}{(c // 5) % 5}{c % 5}", s0=1 if i % 2 else -1,
                                 n_live=int(allst.n.loc[i]), raw=float(allst.S1.loc[i] / allst.n.loc[i]), K_live=float(Tlive[i]),
                                 prior=float(prior[i]), K_fixed=float(Tfix[i]) if contacts else np.nan, K_fixed_A3=float(Ta3[i])))
        thin = d.idx.map(allst.n).lt(20).mean()
        row = dict(point=pid, n_configs_live=int(len(ii)), n_configs_lt20=int((allst.n < 20).sum()),
                   share_live_updates_on_lt20=float(thin))
        for nm, Tf in (("K_fixed", Tfix), ("K_fixed-A3", Ta3)):
            if Tf is None:
                continue
            row[f"{nm}_dP"] = float((w * np.abs(Tlive[ii] - Tf[ii])).sum())
            row[f"{nm}_dlogit_nats"] = float((w * np.abs(lg(Tlive[ii]) - lg(Tf[ii]))).sum())
            row[f"{nm}_KL_nats"] = float((w * kl(Tlive[ii], Tf[ii])).sum())
        for nm in ("K_fixed", "K_fixed-A3"):
            ref = res[nm]
            for m in prim + [x for x in MEAS if x not in prim]:
                row[f"{nm}_z_obs_{m}"] = float((obs.loc[pid, m] - ref[m].mean()) / ref[m].std(ddof=1))
                row[f"{nm}_z_kernel_{m}"] = float((res[f"K_live_n0{N0_MAIN}"][m].mean() - ref[m].mean()) / ref[m].std(ddof=1))
        amp.append(row)
        ev = pd.DataFrame([e for e in evals if e["point"] == pid and e["primary"]])
        print(pid, {k_: bool(g.inside.all()) for k_, g in ev.groupby("kernel")}, flush=True)
    E_ = pd.DataFrame(evals); E_.to_csv(os.path.join(OUT, "evaluation.csv"), index=False)
    pd.DataFrame(cfg_rows).to_csv(os.path.join(OUT, "kernel_tables.csv"), index=False)
    A_ = pd.DataFrame(amp); A_.to_csv(os.path.join(OUT, "amplification.csv"), index=False)
    pp = E_[E_.primary].groupby(["kernel", "point"]).inside.all().unstack()
    verdict = {kn: dict(points_passing=[p for p in POINTS if bool(pp.loc[kn, p])],
                        P1_P4_passing=int(sum(bool(pp.loc[kn, p]) for p in ("P1", "P2", "P3", "P4"))),
                        reproduces=bool(sum(bool(pp.loc[kn, p]) for p in ("P1", "P2", "P3", "P4")) >= 3)) for kn in pp.index}
    json.dump(dict(R=R, verdict=verdict), open(os.path.join(OUT, "verdict.json"), "w"), indent=1)
    open(os.path.join(OUT, "sim_kernel_source.py"), "w").write(SIM_SRC)
    print(json.dumps(verdict, indent=1))


# ---------------------------------------------------------------- known-answer self-test
def selftest(R=300):
    """The table simulator with the A3 kernel must reproduce surrogate.run with the same parameter row (random 50/50
    starts in both; same graphs). Asserts |z| < 3.5 on every measure for P1, P4, P5 (voter step) and P4-nc."""
    f = sim()
    for pid in ("P1", "P4", "P5", "P4-nc"):
        key, framing, rho, contacts = stage3.POINTS[pid]
        fit = stage2.load_fit(key, framing)
        row = stage2.param_row(fit, framing, None, "fitted" if contacts else "fields_only")
        T = a3_kernel(row, stage3.D if contacts else 0, rho)
        ip, nb, tie = stage3.graph(pid, 0)
        a, b = [], []
        for j in range(R):
            rng = np.random.default_rng(j)
            S0 = np.where(rng.random((2, stage3.N)) < 0.5, 1, -1).astype(np.int64)
            a.append(f(ip, nb, tie, S0, T, 10, 10, 1000 + j))
            b.append(S.run(ip, nb, tie, np.zeros(stage3.N, np.int64), row[None, :], 10, 10, 5000 + j, False, 0.0))
        a, b = np.array(a), np.array(b)
        z = (a.mean(0) - b.mean(0)) / np.sqrt(a.var(0) / R + b.var(0) / R + 1e-12)
        print(pid, dict(zip(S.MEASURES, np.round(z, 2))))
        assert np.all(np.abs(z) < 3.5), (pid, z)
    print("selftest passed: table simulator == surrogate.run")


# ---------------------------------------------------------------- K_avg cost estimate (no calls)
def n_orders(c):
    return math.factorial(sum(c)) // math.prod(math.factorial(x) for x in c)


def cost():
    summ = pd.read_csv(os.path.join(ROOT, "results/llm/stage3/summary.csv")).set_index("point")
    rows = []
    for pid in ("P1", "P2", "P3", "P4", "P5"):
        key, framing, rho, contacts = stage3.POINTS[pid]
        d = live_rows(pid)
        cfg = {(tuple(int(x) for x in c), s0) for c, s0 in zip(d.counts, d.s0)}
        if framing == "neutral":                 # mapping 1 = the swapped configuration's prompt at mapping 0
            cfg |= {((c[1], c[0], c[3], c[2]), -s0) for c, s0 in cfg}
            maps = 1
        else:
            maps = 2
        samples = 4 if E[key][2] == "sample" else 1
        prompts = sum(min(8, n_orders(c)) * 2 * maps for c, s0 in cfg)
        calls = prompts * samples
        per_call = summ.loc[pid, "cost"] / summ.loc[pid, "updates"]
        rows.append(dict(point=pid, endpoint=key, configs=len(cfg), prompts=prompts, samples_per_prompt=samples, calls=calls,
                         usd_per_call=per_call, usd=calls * per_call))
    df = pd.DataFrame(rows); os.makedirs(OUT, exist_ok=True); df.to_csv(os.path.join(OUT, "K_avg_cost_estimate.csv"), index=False)
    print(df.to_string(index=False)); print("total calls", int(df.calls.sum()), "total $", round(df.usd.sum(), 3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("what", choices=["run", "cost", "selftest"]); ap.add_argument("--R", type=int, default=400)
    a = ap.parse_args()
    {"run": lambda: run_all(a.R), "cost": cost, "selftest": selftest}[a.what]()
