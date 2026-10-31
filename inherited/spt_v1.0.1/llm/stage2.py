"""Stage 2 driver: surrogate simulations of networks of fitted LLM response functions.

  python llm/stage2.py fss          # long runs, N = 100/400/1600, finite-size scaling (results/llm/stage2/fss.csv)
  python llm/stage2.py stage3       # Stage-3-matched protocol, N = 100, 20 sweeps (results/llm/stage2/stage3.csv)
  python llm/stage2.py jitter       # explicit-jitter vs marginal consistency check (gate-failed endpoints)

Each run draws ONE parameter vector from the endpoint's cluster-bootstrap draws (llm/voter.py; model chosen by
the pre-stated rule: first-contact mixture MF if it beats A3 held-out by >= 2%, else A3), a fresh graph and
fresh dynamics, so the spread of run-level measures is a predictive interval combining fit uncertainty,
graph disorder and dynamical noise. "ising" rows replace the fitted rule by its naive Ising reading (same
β, nothing else); "fields_only" rows keep inertia and fields but remove all social coupling and the voter step,
so any consensus they show is field-driven, not social.
"""
import functools, json, os, sys, itertools
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surrogate as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "llm", "stage2"); os.makedirs(OUT, exist_ok=True)
FRAME_ARM = {"neutral": "neutral_own", "political": "political", "workplace": "workplace"}
CONFIRMATORY = ["llama-70b", "qwen-9b", "qwen-122b", "nemo-12b"]
GATE_FAILED = ["gemma-26b", "gemma-31b", "mistral-large"]          # jitter modelled explicitly (sigma = repeat SD)
SPOT = ["gpt6-luna", "haiku", "gemini-lite"]
NOT_PARSING = ["llama-8b", "mistral-small"]


@functools.lru_cache(maxsize=None)
def load_fit(key, framing):
    j = json.load(open(os.path.join(ROOT, "results", "llm", "fits", "surrogate", key + ".json")))
    a = j["arms"].get(FRAME_ARM[framing])
    if a is None:
        return None
    ch = a["choice"]
    # naive Ising reading uses the Stage 1 ADDITIVE fit (A0, no k-scaling): its β and bootstrap draws
    f0 = json.load(open(os.path.join(ROOT, "results", "llm", "fits", "main", key + ".json")))
    a0 = {x["arm"]: x for x in f0["arms"]}[FRAME_ARM[framing]]
    return {"names": a["names"], "choice": ch, "est": np.array(a[ch]["est"]), "draws": np.array(a[ch]["draws"]),
            "sigma": a.get("repeat_sd") or 0.0, "beta_A0_draws": np.array(a0["draws"]["beta"]), "beta_A0": a0["coef"]["beta"]["est"]}


def param_row(fit, framing, draw, mode):
    v = fit["draws"][draw] if draw is not None else fit["est"]
    if mode == "ising":     # Stage 1 additive β (A0), matching bootstrap draw index modulo its length
        return S.ising_row(fit["beta_A0_draws"][draw % len(fit["beta_A0_draws"])] if draw is not None else fit["beta_A0"])
    row = S.params_from_fit(fit["names"], v, framing, sigma=fit["sigma"])
    if mode == "fields_only":          # control: same inertia and fields, no social coupling, no voter step
        row[S.P_VOTER] = row[S.B_A] = row[S.B_R] = 0.0
    return row


def one_run(job):
    (pop, framing, mode, kind, N, rho, eps, nw, nm, seed, explicit) = job
    rng = np.random.default_rng(seed)
    ip, nb, tie = S.make_graph(N, rho, eps, rng, kind)
    rows, typ = [], np.zeros(N, np.int64)
    keys = pop.split("+")
    for t, key in enumerate(keys):
        fit = load_fit(key, framing)
        rows.append(param_row(fit, framing, int(rng.integers(len(fit["draws"]))), mode))
    if len(keys) > 1:
        typ = rng.permutation(np.arange(N) % len(keys)).astype(np.int64)    # equal shares, random placement
    par = np.array(rows)
    res = S.run(ip, nb, tie, typ, par, nw, nm, int(seed), explicit, 0.0)
    return dict(pop=pop, framing=framing, mode=mode, graph=kind, N=N, rho=rho, eps=eps, n_warm=nw, n_meas=nm,
                seed=seed, explicit_jitter=explicit, **dict(zip(S.MEASURES, res)))


def floor_run(job):
    """Frustration floor: near-zero-temperature quench (Ising, β = 6) — minimal reachable unsatisfied fraction."""
    kind, N, rho, eps, seed = job
    rng = np.random.default_rng(seed)
    ip, nb, tie = S.make_graph(N, rho, eps, rng, kind)
    res = S.run(ip, nb, tie, np.zeros(N, np.int64), S.ising_row(6.0)[None, :], 200, 50, seed, False, 0.0)
    return dict(graph=kind, N=N, rho=rho, eps=eps, seed=seed, unsat_floor=res[7])


def available(keys, framing):
    out = []
    for k in keys:
        p = os.path.join(ROOT, "results", "llm", "fits", "surrogate", k + ".json")
        if os.path.exists(p) and load_fit(k, framing) is not None:
            out.append(k)
    return out


def jobs_stage3(R=40):
    J = []; s = 0
    for framing in ("neutral", "political", "workplace"):
        pops = available(CONFIRMATORY + GATE_FAILED + SPOT, framing)
        for pop, mode, kind, rho in itertools.product(pops, ("fitted", "ising", "fields_only"), ("er", "rrg"), (0.0, 0.25, 0.5)):
            for r in range(R):
                s += 1; J.append((pop, framing, mode, kind, 100, rho, 0.0, 10, 10, 10_000_000 + s, False))
    # mixed populations and directed perceptions (neutral)
    mixes = [m for m in ("llama-70b+qwen-122b", "qwen-9b+qwen-122b", "gpt6-luna+gemini-lite", "llama-70b+gpt6-luna")
             if all(k in available(m.split("+"), "neutral") for k in m.split("+"))]
    for pop, kind, rho in itertools.product(mixes, ("er", "rrg"), (0.0, 0.25)):
        for r in range(R):
            s += 1; J.append((pop, "neutral", "fitted", kind, 100, rho, 0.0, 10, 10, 10_000_000 + s, False))
    for pop, kind, rho, eps in itertools.product(available(["llama-70b", "qwen-122b", "gpt6-luna"], "neutral"), ("er", "rrg"),
                                                 (0.25, 0.5), (0.2, 0.5, 1.0)):
        for r in range(R):
            s += 1; J.append((pop, "neutral", "fitted", kind, 100, rho, eps, 10, 10, 10_000_000 + s, False))
    return J


def jobs_fss(R=16):
    J = []; s = 0
    for framing in ("neutral", "political"):
        pops = available(CONFIRMATORY + GATE_FAILED + SPOT, framing)
        for pop, mode, kind, rho, N in itertools.product(pops, ("fitted", "ising"), ("er", "rrg"), (0.0, 0.25, 0.5), (100, 400, 1600)):
            for r in range(R):
                s += 1; J.append((pop, framing, mode, kind, N, rho, 0.0, 200, 200, 20_000_000 + s, False))
    return J


def jobs_jitter(R=40):
    J = []; s = 0
    for pop, framing, expl in itertools.product(available(GATE_FAILED, "neutral"), ("neutral", "political"), (False, True)):
        if load_fit(pop, framing) is None: continue
        for kind, rho in itertools.product(("er", "rrg"), (0.0, 0.25)):
            for r in range(R):
                s += 1; J.append((pop, framing, "fitted", kind, 100, rho, 0.0, 10, 10, 30_000_000 + r * 7 + (s % 7), expl))
    return J


def run_all(jobs, name, workers=4):
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(one_run, jobs, chunksize=16))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    print(f"{name}: {len(df)} runs -> results/llm/stage2/{name}.csv", flush=True)
    return df


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "floor":
        combos = [(k, N, rho) for k, N, rho in itertools.product(("er", "rrg"), (100, 400, 1600), (0.0, 0.25, 0.5)) for _ in range(8)]
        J = [(k, N, rho, 0.0, 40_000_000 + i) for i, (k, N, rho) in enumerate(combos)]          # distinct seed per run
        with ProcessPoolExecutor(4) as ex:
            pd.DataFrame(list(ex.map(floor_run, J))).to_csv(os.path.join(OUT, "floor.csv"), index=False)
    else:
        run_all({"stage3": jobs_stage3, "fss": jobs_fss, "jitter": jobs_jitter}[what](), what)
