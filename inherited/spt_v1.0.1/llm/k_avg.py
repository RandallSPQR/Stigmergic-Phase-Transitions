"""K_avg: order-marginalised one-shot battery for the P1–P5 endpoints (llm/KERNEL_TEST_PLAN.md, amendment 1).

  python llm/k_avg.py build                 # prompt list + template check, no calls
  python llm/k_avg.py run [--limit 10] [--workers 16] [--budget 1.5]   # API calls (cached per call)
  python llm/k_avg.py analyse [--R 400]     # kernel, simulation, verdict, amplification (no calls)

Outputs: results/llm/kernel_test/k_avg_prompts.csv, k_avg_calls.csv, k_avg_* evaluation files.
"""
import argparse, itertools, json, math, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battery, client, stage3, kernel_test as K
from endpoints import E
from run_stage1 import parse_lp, parse_sample

POINTS = ["P1", "P2", "P3", "P4", "P5"]
N_ORDERS, LP_REPS, SAMPLES = 8, 2, 30


def prompts():
    rows = []
    for pid in POINTS:
        key, framing, rho, contacts = stage3.POINTS[pid]
        model, tag, mode, roff, _ = E[key]
        d = K.live_rows(pid)
        cfg = {(tuple(int(x) for x in c), int(s0)) for c, s0 in zip(d.counts, d.s0)}
        maps = (0, 1)
        if framing == "neutral":
            cfg |= {((c[1], c[0], c[3], c[2]), -s0) for c, s0 in cfg}; maps = (0,)
        for c, s0 in sorted(cfg):
            types = [t for t, n in zip(battery.TYPES, c) for _ in range(n)]
            perms = sorted(set(itertools.permutations(types)))
            for m in maps:
                rng = random.Random(stage3._seed("kavg-orders", pid, c, s0, m))
                chosen = perms if len(perms) <= N_ORDERS else rng.sample(perms, N_ORDERS)
                for seq in chosen:
                    for o in (0, 1):
                        p = stage3.render_live(framing, c, s0, m, o, list(seq), True)
                        stage3.check_prompt(p, framing, c, s0, m, o, True)
                        reps = range(SAMPLES) if mode == "sample" else range(LP_REPS)
                        for r in reps:
                            rows.append(dict(point=pid, key=key, counts="".join(map(str, c)), s0=s0, mapping=m, order=o,
                                             seq="".join(seq), rep=r, prompt=p,
                                             tag=f"kavg:{pid}:{''.join(map(str, c))}:{s0}:{m}:{o}:{''.join(seq)}:{r}"))
    return pd.DataFrame(rows)


def build():
    P = prompts(); os.makedirs(K.OUT, exist_ok=True)
    P.drop(columns="prompt").to_csv(os.path.join(K.OUT, "k_avg_prompts.csv"), index=False)
    s = P.groupby("point").agg(prompts=("tag", lambda x: x.str.rsplit(":", n=1).str[0].nunique()), calls=("tag", "size"))
    summ = pd.read_csv(os.path.join(K.ROOT, "results/llm/stage3/summary.csv")).set_index("point")
    s["usd_est"] = [s.loc[p, "calls"] * summ.loc[p, "cost"] / summ.loc[p, "updates"] for p in s.index]
    print(s.to_string()); print("total calls", int(s.calls.sum()), "est $", round(s.usd_est.sum(), 3), "; all prompts pass check_prompt")
    return P


def run(limit, workers, budget):
    P = prompts()
    if limit:
        P = P.groupby("point").head(max(1, limit // len(POINTS)))
    print(f"k_avg: {len(P)} calls, workers {workers}, budget ${budget}", flush=True)
    out, t0, nerr = [], time.time(), 0

    def one(r):
        model, tag, mode, roff, _ = E[r.key]
        rec = client.chat(battery.body(model, tag, r.prompt, mode, roff, 1.0), rep=r.tag, budget_usd=budget)
        resp = rec["resp"]
        if mode == "lp":
            q = parse_lp(resp.get("first")); pA, leak = q["pA"], q["leak"]
            valid = pA is not None and leak <= stage3.LEAK_MAX
        else:
            a = parse_sample(resp.get("content")); valid = a is not None; pA = (1.0 if a == "A" else 0.0) if valid else None; leak = None
        return dict(point=r.point, counts=r.counts, s0=r.s0, mapping=r.mapping, order=r.order, seq=r.seq, rep=r.rep,
                    pA=pA, leak=leak, valid=valid, provider=resp.get("provider"), cost=(resp.get("usage") or {}).get("cost") or 0.0)

    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(one, r) for r in P.itertuples(index=False)]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                out.append(f.result())
            except client.BudgetExceeded as e:
                print("BUDGET STOP:", e, flush=True); ex.shutdown(cancel_futures=True); break
            except Exception as e:
                nerr += 1; print("call error", repr(e)[:200], flush=True)
            if i % 250 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)} calls, errors {nerr}, session spend ${client.spend()['usd']:.4f}, {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(out)
    path = os.path.join(K.OUT, "k_avg_calls.csv" if not limit else "k_avg_calls_e2e.csv")
    df.to_csv(path, index=False)
    print("saved", path, len(df), "rows; invalid", int((~df.valid).sum()), "; providers", df.provider.value_counts().to_dict(),
          "; cost $", round(df.cost.sum(), 4), flush=True)


def kavg_table(pid, calls, rng=None, filled=None):
    key, framing, rho, contacts = stage3.POINTS[pid]
    d = calls[(calls.point == pid) & calls.valid].copy()
    g = d.groupby(["counts", "s0", "mapping", "order", "seq"])
    if rng is None:
        pp = g.pA.mean()
    else:                                   # P5: Beta draw per prompt
        x, n = g.pA.sum(), g.pA.size()
        pp = pd.Series(rng.beta(1 + x, 1 + n - x), index=x.index, name="pA")
    pp = pp.reset_index(); pp["P"] = np.where(pp.mapping == 0, pp.pA, 1 - pp.pA)
    byc = pp.groupby(["counts", "s0"]).P.mean().to_dict()
    T = K.battery_kernel(pid)               # fallback for configurations never seen live
    for c, s0 in K.configs(4, rho):
        cs = "".join(map(str, c))
        if framing == "neutral":
            sw = "".join(map(str, (c[1], c[0], c[3], c[2])))
            if (cs, s0) in byc and (sw, -s0) in byc:
                T[K.idx(c, s0)] = 0.5 * byc[(cs, s0)] + 0.5 * (1 - byc[(sw, -s0)])
                if filled is not None: filled.add(K.idx(c, s0))
        elif (cs, s0) in byc:
            T[K.idx(c, s0)] = byc[(cs, s0)]
            if filled is not None: filled.add(K.idx(c, s0))
    return T


def analyse(R):
    calls = pd.read_csv(os.path.join(K.OUT, "k_avg_calls.csv"), dtype={"counts": str, "seq": str})
    calls["counts"] = calls.counts.str.zfill(4)
    exp = pd.read_csv(os.path.join(K.OUT, "k_avg_prompts.csv"), dtype={"counts": str, "seq": str})
    obs = pd.read_csv(os.path.join(K.ROOT, "results/llm/stage3/summary.csv")).set_index("point")
    pred = {p["id"].split(" ")[0]: p for p in json.load(open(os.path.join(K.ROOT, "results/llm/stage2/stage3_predictions.json")))}
    ev, amp = [], []
    lg = lambda p: np.clip(np.log(np.clip(p, 1e-12, 1) / np.clip(1 - p, 1e-12, 1)), -6, 6)
    kl = lambda p, q: (p * np.log(np.clip(p, 1e-6, 1) / np.clip(q, 1e-6, 1)) + (1 - p) * np.log(np.clip(1 - p, 1e-6, 1) / np.clip(1 - q, 1e-6, 1)))
    prev = pd.read_csv(os.path.join(K.OUT, "evaluation.csv"))
    for pid in POINTS:
        key = stage3.POINTS[pid][0]
        filled = set(); T0 = kavg_table(pid, calls, filled=filled)
        if E[key][2] == "sample":
            rng = np.random.default_rng(stage3._seed("kavg-beta", pid)); tabs = [kavg_table(pid, calls, rng) for _ in range(R)]
            fn = lambda run, g: tabs[run]
        else:
            fn = lambda run, g, T0=T0: T0
        df = K.simulate(pid, fn, R, "K_avg"); df.to_csv(os.path.join(K.OUT, f"sims_{pid}_K_avg.csv"), index=False)
        for m in K.MEAS:
            lo, hi = np.percentile(df[m], [5, 95])
            ev.append(dict(point=pid, kernel="K_avg", measure=m, primary=m in pred[pid]["primary"], observed=float(obs.loc[pid, m]),
                           lo=float(lo), hi=float(hi), mean=float(df[m].mean()), sd=float(df[m].std(ddof=1)),
                           inside=bool(lo <= obs.loc[pid, m] <= hi)))
        # per-step vs K_live and K_fixed, weighted by live visits
        d = K.live_rows(pid); st = d.groupby("idx").agg(S1=("p", "sum"), n=("p", "size"))
        Tl, _ = K.live_kernel(st, K.N0_MAIN); Tf = K.battery_kernel(pid)
        ii = st.index.values; w = st.n / st.n.sum()
        row = dict(point=pid, prompts_expected=int(exp[exp.point == pid].groupby(["counts", "s0", "mapping", "order", "seq"]).ngroups),
                   calls=int((calls.point == pid).sum()), invalid=int(((calls.point == pid) & ~calls.valid).sum()),
                   live_updates_on_fallback=float((~d.idx.isin(filled)).mean()))
        for nm, Tx in (("K_avg_vs_K_live", (T0, Tl)), ("K_fixed_vs_K_live", (Tf, Tl)), ("K_avg_vs_K_fixed", (T0, Tf))):
            a, b = Tx
            row[f"{nm}_dP"] = float((w * np.abs(a[ii] - b[ii])).sum())
            row[f"{nm}_dlogit_nats"] = float((w * np.abs(lg(a[ii]) - lg(b[ii]))).sum())
            row[f"{nm}_KL_nats"] = float((w * kl(b[ii], a[ii])).sum())
        ref = pd.read_csv(os.path.join(K.OUT, f"sims_{pid}_K_fixed.csv"))
        for m in pred[pid]["primary"]:
            row[f"z_obs_vs_K_avg_{m}"] = float((obs.loc[pid, m] - df[m].mean()) / df[m].std(ddof=1))
            row[f"z_K_avg_vs_K_fixed_{m}"] = float((df[m].mean() - ref[m].mean()) / ref[m].std(ddof=1))
        amp.append(row)
        print(pid, json.dumps(row), flush=True)
    E_ = pd.DataFrame(ev); E_.to_csv(os.path.join(K.OUT, "k_avg_evaluation.csv"), index=False)
    pd.DataFrame(amp).to_csv(os.path.join(K.OUT, "k_avg_amplification.csv"), index=False)
    pp = E_[E_.primary].groupby("point").inside.all()
    v = dict(points_passing=[p for p in POINTS if pp[p]], P1_P4_passing=int(sum(pp[p] for p in POINTS[:4])),
             reproduces=bool(sum(pp[p] for p in POINTS[:4]) >= 3))
    json.dump(dict(R=R, K_avg=v), open(os.path.join(K.OUT, "k_avg_verdict.json"), "w"), indent=1)
    E_["z"] = (E_.observed - E_["mean"]) / E_.sd
    print(E_[E_.primary][["point", "measure", "observed", "lo", "hi", "inside", "z"]].round(3).to_string(index=False)); print(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("what", choices=["build", "run", "analyse"])
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--budget", type=float, default=1.5); ap.add_argument("--R", type=int, default=400)
    a = ap.parse_args()
    {"build": build, "run": lambda: run(a.limit, a.workers, a.budget), "analyse": lambda: analyse(a.R)}[a.what]()
