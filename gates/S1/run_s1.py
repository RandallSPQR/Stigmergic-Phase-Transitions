"""Gate S1 runner: the benchmarks of gates/S1/S1_PLAN.md, with its points and tolerances, nothing else.

  python gates/S1/run_s1.py [--only B1 B2 B3 B4 G R]
Writes gates/S1/results/<section>.json and summary.json. Seeds are derived from the section and point labels, so a
rerun reproduces every number.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import references as R, sim  # noqa: E402

OUT = ROOT / "gates" / "S1" / "results"
N_BIG = 20_000
WARM, MEAS, NBATCH = 500, 1000, 20


def seed_of(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:15], 16)


def batch_se(x, nb=NBATCH):
    x = np.asarray(x, float)
    b = x[: len(x) // nb * nb].reshape(nb, -1).mean(axis=1)
    return float(b.mean()), float(b.std(ddof=1) / math.sqrt(nb))


def heat_bath_run(d, T, H, h, label, start_plus):
    s_ = seed_of(label)
    indptr, nbr, info = sim.rrg(N_BIG, d, s_ % 2**31)
    rng = np.random.Generator(np.random.PCG64(s_ + 1))
    s0 = np.ones(N_BIG, np.int8) if start_plus else np.where(rng.random(N_BIG) < 0.5, 1, -1).astype(np.int8)
    ch = sim.Chain(indptr, nbr, sim.heat_bath_table(N_BIG, d, 1.0 / T, H=H, h=h), s0, seed=s_ + 2)
    ch.sweeps(WARM)
    ms, bs = [], []
    for _ in range(MEAS):
        ch.sweeps(1)
        ms.append(ch.m()); bs.append(ch.bond())
    (m, m_se), (b, b_se) = batch_se(ms), batch_se(bs)
    return {"m": m, "m_se": m_se, "bond": b, "bond_se": b_se, "graph": info, "indptr": indptr, "nbr": nbr}


def check(sim_v, sim_se, ref_v, ref_se=0.0, k=4.0, a=0.005):
    tol = k * math.sqrt(sim_se ** 2 + ref_se ** 2) + a
    return {"sim": sim_v, "sim_se": sim_se, "ref": ref_v, "ref_se": ref_se, "diff": sim_v - ref_v, "tol": tol,
            "ok": abs(sim_v - ref_v) <= tol}


def b1():
    pts = [(4, 2.0, 0.1), (4, 2.885, 0.1), (4, 4.0, 0.1), (4, 4.0, 0.0),
           (6, 3.5, 0.1), (6, 4.933, 0.1), (6, 7.0, 0.1), (6, 7.0, 0.0)]
    sys.path.insert(0, str(ROOT / "inherited" / "spt_v1.0.1" / "llm"))
    import surrogate  # SPT v1.0.1, verbatim
    rows = []
    for d, T, H in pts:
        ref = R.bethe_ising(d, T, H)
        r = heat_bath_run(d, T, H, None, f"B1|{d}|{T}|{H}", start_plus=H > 0)
        row = {"d": d, "T": T, "H": H, "graph": r["graph"], "m": check(r["m"], r["m_se"], ref["m"]),
               "bond": check(r["bond"], r["bond_se"], ref["bond"])}
        if d == 4:   # cross-check with the inherited SPT simulator on the same graph
            beta = 1.0 / T
            par = np.zeros((1, surrogate.NPAR)); par[0, surrogate.B_A] = 2 * beta; par[0, surrogate.H_C] = 2 * beta * H
            par[0, surrogate.KAPPA] = 1.0
            tie = np.ones(r["nbr"].shape[0], np.int64); typ = np.zeros(N_BIG, np.int64)
            vals = [float(surrogate.run(r["indptr"], r["nbr"], tie, typ, par, WARM, MEAS, seed_of("B1x", d, T, H, k) % 2**31,
                                        False, 0.5 if H > 0 else 0.0)[1]) for k in range(4)]
            row["inherited_m"] = check(float(np.mean(vals)), float(np.std(vals, ddof=1) / 2), ref["m"])
            row["inherited_m"]["seeds"] = vals
        rows.append(row)
        print("B1", d, T, H, round(row["m"]["diff"], 4), row["m"]["ok"], round(row["bond"]["diff"], 4), row["bond"]["ok"],
              row.get("inherited_m", {}).get("ok"), flush=True)
    return rows


def b2():
    pts = [(4, 2.0, 1.0, 0.1), (4, 2.0, 3.0, 0.1), (4, 3.5, 1.0, 0.0),
           (6, 3.5, 1.5, 0.1), (6, 3.5, 4.0, 0.1), (6, 6.0, 1.5, 0.0)]
    rows = []
    for d, T, sg, H in pts:
        ref = R.rfim_popdyn(d, T, sg, H, M=200_000, iters=400, R=4, seed=seed_of("B2ref", d, T, sg, H) % 2**31)
        reals = []
        for k in range(2):
            lab = f"B2|{d}|{T}|{sg}|{H}|{k}"
            h = sg * np.random.Generator(np.random.PCG64(seed_of(lab, "fields"))).standard_normal(N_BIG)
            reals.append(heat_bath_run(d, T, H, h, lab, start_plus=H > 0))
        row = {"d": d, "T": T, "sigma": sg, "H": H, "graphs": [x["graph"] for x in reals]}
        for q in ("m", "bond"):
            v = np.array([x[q] for x in reals]); se = np.array([x[q + "_se"] for x in reals])
            se_tot = math.sqrt(float(np.sum(se ** 2)) / len(v) ** 2 + float(np.var(v, ddof=1)) / len(v))
            row[q] = check(float(v.mean()), se_tot, ref[q], ref[q + "_se"])
            row[q]["realisations"] = v.tolist()
        rows.append(row)
        print("B2", d, T, sg, H, round(row["m"]["diff"], 4), row["m"]["ok"], round(row["bond"]["diff"], 4), row["bond"]["ok"], flush=True)
    return rows


def b3():
    pts = [(4, 2.5), (4, 1.5), (6, 3.5), (6, 2.0)]
    coarse = [round(-4.0 + 0.25 * i, 2) for i in range(33)]
    rows = []
    for d, sg in pts:
        jump = R.dss_jump(d, sg)
        lab = f"B3|{d}|{sg}"
        indptr, nbr, info = sim.rrg(N_BIG, d, seed_of(lab) % 2**31)
        h = sg * np.random.Generator(np.random.PCG64(seed_of(lab, "fields"))).standard_normal(N_BIG)
        fine = [] if jump is None else [round(jump["H"] - 0.3 + 0.005 * i, 3) for i in range(121)]
        grid = sorted(set(coarse) | set(fine))
        chains = [sim.Chain(indptr, nbr, sim.zero_T_table(N_BIG, d, H=grid[0], h=h), -np.ones(N_BIG, np.int8),
                            seed=seed_of(lab, "order", k)) for k in (0, 1)]
        m_sim, identical = {}, True
        for H in grid:
            for ch in chains:
                ch.set_table(sim.zero_T_table(N_BIG, d, H=H, h=h)); ch.relax()
            identical &= bool(np.array_equal(chains[0].s, chains[1].s))
            m_sim[H] = chains[0].m()
        pts_out = []
        for H in coarse:
            if jump is not None and abs(H - jump["H"]) <= 0.1:
                continue
            ref = R.dss_hysteresis(d, sg, H)["m"]
            pts_out.append({"H": H, "sim": m_sim[H], "ref": ref, "diff": m_sim[H] - ref, "ok": abs(m_sim[H] - ref) <= 0.02})
        row = {"d": d, "sigma": sg, "graph": info, "points": pts_out, "all_points_ok": all(p["ok"] for p in pts_out),
               "order_independent": identical, "ref_jump": jump}
        if jump is not None:
            dm = np.diff([m_sim[H] for H in fine]); i = int(np.argmax(dm))
            Hs, size = 0.5 * (fine[i] + fine[i + 1]), float(dm[i])
            row["sim_jump"] = {"H": Hs, "size": size}
            row["jump_H_ok"] = abs(Hs - jump["H"]) <= 0.08
            row["jump_size_ok"] = abs(size - jump["size"]) <= 0.1
        row["ok"] = row["all_points_ok"] and identical and row.get("jump_H_ok", True) and row.get("jump_size_ok", True)
        rows.append(row)
        print("B3", d, sg, "points", row["all_points_ok"], "max|diff|", round(max(abs(p["diff"]) for p in pts_out), 4),
              "order-indep", identical, "jump", row.get("sim_jump"), jump and (round(jump["H"], 3), round(jump["size"], 3)), flush=True)
    return rows


def b3a():
    """Amendment 1 (post-outcome deviation DV1): smooth cases on the mean of 10 realisations, 4 SE + 0.005 per point;
    pass/fail at (4, 2.5) and (6, 4.5); (6, 3.5) reported as a near-critical diagnostic (no pass/fail); new seeds."""
    coarse = [round(-4.0 + 0.25 * i, 2) for i in range(33)]
    rows = []
    for d, sg, graded in ((4, 2.5, True), (6, 4.5, True), (6, 3.5, False)):
        ref = np.array([R.dss_hysteresis(d, sg, H)["m"] for H in coarse])
        sims, identical = [], True
        for k in range(10):
            lab = f"B3A|{d}|{sg}|{k}"
            indptr, nbr, info = sim.rrg(N_BIG, d, seed_of(lab) % 2**31)
            h = sg * np.random.Generator(np.random.PCG64(seed_of(lab, "fields"))).standard_normal(N_BIG)
            chs = [sim.Chain(indptr, nbr, sim.zero_T_table(N_BIG, d, H=coarse[0], h=h), -np.ones(N_BIG, np.int8),
                             seed=seed_of(lab, "order", j)) for j in (0, 1)]
            row = []
            for H in coarse:
                for ch in chs:
                    ch.set_table(sim.zero_T_table(N_BIG, d, H=H, h=h)); ch.relax(100_000)
                identical &= bool(np.array_equal(chs[0].s, chs[1].s))
                row.append(chs[0].m())
            sims.append(row)
        diff = np.array(sims) - ref[None, :]
        pts = []
        for j, H in enumerate(coarse):
            md, sd = float(diff[:, j].mean()), float(diff[:, j].std(ddof=1))
            se = sd / math.sqrt(10)
            pts.append({"H": H, "ref": float(ref[j]), "mean_sim": float(np.mean(np.array(sims)[:, j])), "mean_diff": md,
                        "sd_across_graphs": sd, "se": se, "tol": 4 * se + 0.005, "ok": abs(md) <= 4 * se + 0.005})
        row = {"d": d, "sigma": sg, "graded": graded, "realisations": 10, "order_independent": identical, "points": pts,
               "max_abs_mean_diff": max(abs(p["mean_diff"]) for p in pts), "max_sd_across_graphs": max(p["sd_across_graphs"] for p in pts),
               "H_at_max_sd": max(pts, key=lambda p: p["sd_across_graphs"])["H"]}
        if graded:
            row["ok"] = all(p["ok"] for p in pts) and identical
        rows.append(row)
        print("B3A", d, sg, "graded" if graded else "diagnostic", "ok" if not graded else row["ok"], "max|mean diff|",
              round(row["max_abs_mean_diff"], 4), "max SD", round(row["max_sd_across_graphs"], 4), "at H", row["H_at_max_sd"],
              "order-indep", identical, flush=True)
    return rows


def b4():
    from scipy.special import ndtr
    pts = [(d, mu, r0) for d in (4, 6) for mu, r0 in ((0.5, 0.05), (0.5, 0.1), (0.5, 0.2), (0.4, 0.05), (0.4, 0.2))]
    rows = []
    for d, mu, r0 in pts:
        ref = R.gleeson_cascade(d, r0, lambda x: float(ndtr((x - mu) / 0.1)))["rho"]
        vals = []
        for k in range(5):
            lab = f"B4|{d}|{mu}|{r0}|{k}"
            indptr, nbr, info = sim.rrg(N_BIG, d, seed_of(lab) % 2**31)
            g = np.random.Generator(np.random.PCG64(seed_of(lab, "draws")))
            phi = mu + 0.1 * g.standard_normal(N_BIG)
            s0 = np.where(g.random(N_BIG) < r0, 1, -1).astype(np.int8)
            ch = sim.Chain(indptr, nbr, sim.threshold_table(N_BIG, d, phi), s0, seed=seed_of(lab, "order"))
            ch.relax()
            vals.append(float(np.mean(ch.s > 0)))
        row = {"d": d, "mu": mu, "rho0": r0, "rho": check(float(np.mean(vals)), float(np.std(vals, ddof=1) / math.sqrt(5)), ref)}
        row["rho"]["realisations"] = vals
        rows.append(row)
        print("B4", d, mu, r0, round(row["rho"]["sim"], 4), round(ref, 4), row["rho"]["ok"], flush=True)
    return rows


def g():
    import networkx as nx
    out = {"networkx": nx.__version__}
    for d in (4, 6):
        infos = [sim.rrg(100, d, s)[2] for s in range(1000)]
        again = [sim.rrg(100, d, s)[2]["fingerprint"] for s in range(1000)]
        out[f"d{d}"] = {"n": 1000, "simple": sum(i["simple"] for i in infos), "regular": sum(i["regular"] for i in infos),
                        "connected": sum(i["connected"] for i in infos),
                        "same_fingerprint_twice": sum(a == i["fingerprint"] for a, i in zip(again, infos)),
                        "distinct_fingerprints": len({i["fingerprint"] for i in infos}),
                        "disconnected_seeds": [i["seed"] for i in infos if not i["connected"]]}
    out["ok"] = out["networkx"] == sim.NETWORKX_PIN and all(
        out[k]["simple"] == out[k]["regular"] == out[k]["same_fingerprint_twice"] == 1000 for k in ("d4", "d6"))
    print("G", json.dumps(out), flush=True)
    return out


def r():
    indptr, nbr, _ = sim.rrg(100, 4, 11)
    h = np.random.Generator(np.random.PCG64(5)).standard_normal(100)
    tab = sim.heat_bath_table(100, 4, 0.5, h=h)
    s0 = np.where(np.random.Generator(np.random.PCG64(6)).random(100) < 0.5, 1, -1).astype(np.int8)
    a = sim.Chain(indptr, nbr, tab, s0, seed=7); a.sweeps(50)
    b = sim.Chain(indptr, nbr, tab, s0, seed=7); b.sweeps(50)
    c = sim.Chain(indptr, nbr, tab, s0, seed=8); c.sweeps(50)
    x = sim.Chain(indptr, nbr, tab, s0, seed=9); x.sweeps(20)
    y = copy.deepcopy(x); x.sweeps(30); y.sweeps(30)
    out = {"same_seed_identical": bool(np.array_equal(a.s, b.s)), "different_seed_differs": not np.array_equal(a.s, c.s),
           "copied_state_continues_identically": bool(np.array_equal(x.s, y.s) and np.array_equal(x.display, y.display))}
    out["ok"] = all(out.values())
    print("R", out, flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=["R", "G", "B1", "B2", "B3", "B4"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    import networkx, numba, scipy
    env = {"python": platform.python_version(), "numpy": np.__version__, "numba": numba.__version__,
           "networkx": networkx.__version__, "scipy": scipy.__version__, "machine": platform.platform()}
    fns = {"R": r, "G": g, "B1": b1, "B2": b2, "B3": b3, "B3A": b3a, "B4": b4}
    for k in a.only:
        t0 = time.time()
        res = fns[k]()
        json.dump({"section": k, "env": env, "minutes": round((time.time() - t0) / 60, 2), "results": res},
                  open(OUT / f"{k}.json", "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    summ = {}
    for k in ("R", "G", "B1", "B2", "B3", "B3A", "B4"):
        f = OUT / f"{k}.json"
        if not f.exists():
            continue
        res = json.load(open(f))["results"]
        if k in ("R", "G"):
            summ[k] = res["ok"]
        elif k == "B3":
            summ[k] = all(x["ok"] for x in res)           # original rule (kept on record)
            summ["B3_jump_cases"] = all(x["ok"] for x in res if x.get("ref_jump"))
        elif k == "B3A":
            summ[k] = all(x["ok"] for x in res if x["graded"])
        else:
            summ[k] = all(all(v["ok"] for q, v in x.items() if isinstance(v, dict) and "ok" in v) for x in res)
    # Amendment 1 (DV1): B3's smooth cases are judged by B3A; the original B3 result stays in the summary, on record
    need = ["R", "G", "B1", "B2", "B4", "B3_jump_cases", "B3A"]
    summ["pass_original_plan"] = all(summ.get(k, False) for k in ["R", "G", "B1", "B2", "B3", "B4"])
    summ["pass"] = all(summ.get(k, False) for k in need)
    json.dump({"env": env, "sections": summ}, open(OUT / "summary.json", "w"), indent=1)
    print("SUMMARY", summ)


if __name__ == "__main__":
    main()
