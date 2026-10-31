"""Confirmatory amplification phase, simulations (plan: llm/AMPLIFICATION_CONFIRM_PLAN.md §4 Step 3; §5-6 later).

  python llm/confirm_sim.py locate MODEL [MODEL ...]    # Step 3: coarse -> edge interval -> fine -> T_c, checks, W rule
  python llm/confirm_sim.py luna_draws                  # T_c per Beta kernel draw (exploratory model)

MODEL in P1 (fresh), gemma, gemini, selected, luna. Fresh graphs (seed confirm-graph|base|N|g, N = 100 included) and
seeds (salt confirm). Kernel at T: per-prompt letter logit / T, then the K_avg marginalisation (neutral: symmetrised
over the P<->Q relabelling, exactly as k_avg.kavg_table). Outputs: results/llm/confirm/sim/.
"""
import hashlib, json, math, os, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage3, surrogate as S, kernel_test as K, amplification_curve as A

ROOT = K.ROOT
OUT = os.path.join(ROOT, "results", "llm", "confirm", "sim")
CDIR = os.path.join(ROOT, "results", "llm", "confirm")
NS = [100, 400, 1600]
COARSE = [round(x, 4) for x in np.geomspace(0.2, 5.0, 15)]
RHO = {"gemma_exact": 0.25, "P1": 0.25, "P2": 0.5, "P4": 0.25, "gemma": 0.25, "gemini": 0.25, "selected": 0.25, "luna": 0.25}
seed = A.seed


# ---------------------------------------------------------------- kernels
def _calls(model):
    if model in ("gemma", "gemma_exact"):           # gemma_exact: exact full-vocabulary P(A) (censoring sensitivity)
        d = pd.concat([pd.read_csv(os.path.join(CDIR, "gemma", f"kavg_rep{r}.csv"), dtype={"counts": str, "seq": str}).assign(rep=r) for r in (0, 1)])
        if model == "gemma_exact":
            d["pA"] = d.pA_exact
        d["valid"] = d.pA.notna() & (d.leak <= stage3.LEAK_MAX); return d, "lp"
    tag = {"gemini": "gemini", "luna": "luna", "selected": "selected"}[model]
    d = pd.read_csv(os.path.join(CDIR, f"kavg_{tag}.csv"), dtype={"counts": str, "seq": str})
    return d, ("lp" if model == "selected" else "sample")


def new_model_table(model, T, draw=None):
    """Table over K.NT for a new model at temperature T. draw: Beta-draw index (sampled models) or None (Jeffreys)."""
    d, mode = _calls(model); d = d[d.valid].copy(); d["counts"] = d.counts.astype(str).str.zfill(4)
    g = d.groupby(["counts", "s0", "order", "seq"])
    if mode == "lp":
        p = g.pA.mean()
    else:
        x, n = g.pA.sum(), g.pA.size()
        if draw is None:
            p = (x + 0.5) / (n + 1)
        else:
            rng = np.random.default_rng(seed("confirm-beta", model, draw))
            p = pd.Series(rng.beta(x + 0.5, n - x + 0.5), index=x.index)
    p = pd.Series(A._tempered(np.clip(p.values, 1e-9, 1 - 1e-9), T), index=p.index)        # mapping 0: P = A
    byc = p.groupby(level=["counts", "s0"]).mean().to_dict()
    Tb = np.full(K.NT, np.nan)
    for c, s0 in K.configs(4, 0.25):
        cs = "".join(map(str, c)); sw = "".join(map(str, (c[1], c[0], c[3], c[2])))
        Tb[K.idx(c, s0)] = 0.5 * byc[(cs, s0)] + 0.5 * (1 - byc[(sw, -s0)])
    return Tb


def table(model, T, draw=None):
    if model in ("P1", "P2", "P4"):
        return A.kavg_T(model, T, A._calls())[0]
    return new_model_table(model, T, draw)


def graphs(model, N):
    base = model if model in ("P1", "P2", "P4") else model
    G = [S.make_graph(N, RHO[model], 0.0, np.random.default_rng(seed("confirm-graph", base, N, g)), "rrg", d=stage3.D) for g in range(5)]
    fp = {f"{base}:{N}:{g}": hashlib.sha256(np.concatenate(x).astype(np.int64).tobytes()).hexdigest()[:16] for g, x in enumerate(G)}
    return G, fp


# ---------------------------------------------------------------- one unit
def unit(args):
    """(stage, model, N, T, start 'h'|'c', W, R, draw) -> csv of R base runs."""
    stage, model, N, T, start, W, R, draw = args
    path = os.path.join(OUT, stage, f"{model}{'' if draw is None else f'_d{draw}'}_N{N}_T{T:.4f}_{start}_W{W}.csv.gz")
    if os.path.exists(path):
        return path
    G, _ = graphs(model, N); L = np.clip(A.lg(np.nan_to_num(table(model, T, draw), nan=0.5)), -A.CLIP, A.CLIP)
    rows = []
    for r in range(R):
        res, _ = A.sim_eq(*G[r % 5], L, seed("confirm", stage, model, draw, N, T, start, W, r), W, W, A.PERS_WIN, start == "c")
        rows.append(dict(run=r, **dict(zip(A.MEAS, res))))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame(rows).to_csv(path + ".tmp", index=False, compression="gzip"); os.replace(path + ".tmp", path)
    return path


def run_units(jobs, procs=4):
    t0 = time.time()
    with Pool(procs) as p:
        for i, path in enumerate(p.imap_unordered(unit, jobs), 1):
            if i % 10 == 0 or i == len(jobs):
                print(f"[{time.time() - t0:6.0f}s] {i}/{len(jobs)} {os.path.basename(path)}", flush=True)


def load(stage, model, N, T, start, W, draw=None):
    return pd.read_csv(os.path.join(OUT, stage, f"{model}{'' if draw is None else f'_d{draw}'}_N{N}_T{T:.4f}_{start}_W{W}.csv.gz"))


binder = A.binder


def crossings(Ts, ua, ub):
    d = np.asarray(ua) - np.asarray(ub); xs = []
    for j in range(len(Ts) - 1):
        if d[j] == 0 or d[j] * d[j + 1] < 0:
            xs.append(A.crossing(Ts[j:j + 2], list(ua[j:j + 2]), list(ub[j:j + 2])))
    return xs


def pick_tc(Ts, u400, u1600):
    xs = crossings(Ts, u400, u1600)
    if not xs:
        return None
    sl = np.abs(np.diff(u1600) / np.diff(np.log(Ts))); j = int(np.argmax(sl)); tst = math.sqrt(Ts[j] * Ts[j + 1])
    return min(xs, key=lambda x: abs(math.log(x / tst)))


# ---------------------------------------------------------------- Step 3
def locate(model, R=100, draw=None, fine_only_band=None):
    res = {"model": model}
    if fine_only_band is None:
        run_units([("coarse", model, N, T, s, 1000, R, draw) for N in sorted(NS, reverse=True) for T in COARSE for s in "hc"])
        U = {N: [binder(load("coarse", model, N, T, "h", 1000, draw)) for T in COARSE] for N in NS}
        hc = {T: (load("coarse", model, 1600, T, "h", 1000, draw).abs_m.mean(), load("coarse", model, 1600, T, "c", 1000, draw).abs_m.mean()) for T in COARSE}
        nonfrozen = [T for T in COARSE if abs(hc[T][0] - hc[T][1]) <= 0.02]
        res.update(coarse=COARSE, binder_coarse={str(N): [float(x) for x in U[N]] for N in NS},
                   hotcold_coarse_1600={str(T): [float(a), float(b)] for T, (a, b) in hc.items()}, frozen=[T for T in COARSE if T not in nonfrozen])
        ordered = [T for T in nonfrozen if U[1600][COARSE.index(T)] >= 0.5]
        pairs = [(COARSE[j], COARSE[j + 1]) for j in range(len(COARSE) - 1) if COARSE[j] in nonfrozen and COARSE[j + 1] in nonfrozen]
        drops = [(U[1600][COARSE.index(a)] - U[1600][COARSE.index(b)]) / math.log(b / a) for a, b in pairs]
        if not ordered or not pairs or max(drops) <= 0:
            res["result"] = "no transition in the swept range (never ordered at a non-frozen T, or no drop)"; return res
        a, b = pairs[int(np.argmax(drops))]; res["edge_interval"] = [a, b]
        band = [round(x, 4) for x in np.geomspace(a / 1.25, b * 1.25, 13)]
    else:
        band = fine_only_band
    res["fine"] = band
    run_units([("fine", model, N, T, s, 1000, R, draw) for N in sorted(NS, reverse=True) for T in band for s in ("hc" if draw is None else "h")])
    D = {(N, T): load("fine", model, N, T, "h", 1000, draw) for N in NS for T in band}
    U = {N: [binder(D[(N, T)]) for T in band] for N in NS}
    sm = {N: [math.sqrt(N) * D[(N, T)].m2.mean() for T in band] for N in NS}
    tc = pick_tc(band, U[400], U[1600])
    res.update(binder_fine={str(N): [float(x) for x in U[N]] for N in NS}, scaled_m2_fine={str(N): [float(x) for x in sm[N]] for N in NS}, Tc=tc)
    if tc is None:
        res["result"] = "no U(400)-U(1600) crossing in the fine band: no transition located"; return res
    rng = np.random.default_rng(seed("confirm-binder-boot", model, draw)); boots = []
    for _ in range(200):
        Ub = {N: [binder(D[(N, T)].iloc[rng.integers(len(D[(N, T)]), size=len(D[(N, T)]))]) for T in band] for N in (400, 1600)}
        boots.append(pick_tc(band, Ub[400], Ub[1600]))
    ok = [x for x in boots if x is not None]
    res.update(Tc_ci=[float(np.percentile(ok, 2.5)), float(np.percentile(ok, 97.5))] if len(ok) > 20 else None, boot_share=len(ok) / 200,
               check_100_400=crossings(band, U[100], U[400]), check_scaled_m2=crossings(band, sm[400], sm[1600]), result="transition located")
    if draw is not None:
        return res
    res["hotcold_fine_1600"] = {str(T): [float(load("fine", model, 1600, T, "h", 1000).abs_m.mean()), float(load("fine", model, 1600, T, "c", 1000).abs_m.mean())] for T in band}
    # Step 4 run length: shortest W in {200, 500, 1000} with hot/cold |m| gap <= 0.02 at N = 1600 on the Step 4 band
    s4 = [round(x, 4) for x in np.geomspace(tc / 1.3, tc * 1.3, 13)]; res["step4_band"] = s4; choice = None
    for W in (200, 500):
        run_units([("wrule", model, 1600, T, s, W, R, None) for T in s4 for s in "hc"])
        gaps = [abs(load("wrule", model, 1600, T, "h", W).abs_m.mean() - load("wrule", model, 1600, T, "c", W).abs_m.mean()) for T in s4]
        res[f"wrule_gap_W{W}"] = float(max(gaps))
        if max(gaps) <= 0.02:
            choice = W; break
    if choice is None:
        run_units([("wrule", model, 1600, T, s, 1000, R, None) for T in s4 for s in "hc"])
        res["wrule_gap_W1000"] = float(max(abs(load("wrule", model, 1600, T, "h", 1000).abs_m.mean() - load("wrule", model, 1600, T, "c", 1000).abs_m.mean()) for T in s4))
        choice = 1000
    res["step4"] = dict(W=choice, R=400 if choice <= 500 else 200)
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "locate":
        for m in sys.argv[2:]:
            r = locate(m); fps = {}
            for N in NS:
                fps.update(graphs(m, N)[1])
            r["graph_fingerprints"] = fps
            json.dump(r, open(os.path.join(OUT, f"locate_{m}.json"), "w"), indent=1, default=float)
            print(m, json.dumps({k: r.get(k) for k in ("result", "Tc", "Tc_ci", "check_100_400", "check_scaled_m2", "frozen", "step4")}, default=float), flush=True)
    elif cmd == "luna_draws":
        base = json.load(open(os.path.join(OUT, "locate_luna.json")))
        if base.get("Tc") is None:
            print("luna: no T_c; draws skipped"); return
        out = []
        for d in range(20):
            r = locate("luna", R=50, draw=d, fine_only_band=base["fine"]); out.append(r.get("Tc")); print("draw", d, r.get("Tc"), flush=True)
        json.dump(dict(Tc_draws=out), open(os.path.join(OUT, "locate_luna_draws.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
