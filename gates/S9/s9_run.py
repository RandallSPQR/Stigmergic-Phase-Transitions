"""Gate S9 run (gates/S9/S9_PLAN.md, approved; D29: Strong tier sized at rho = 1). CPU only; development data only.

  python gates/S9/s9_run.py  -> gates/S9/results/s9_tiers.json, gates/S9/results/kernels_s8.json
Outputs contain no level of either confirmatory contrast: only changes of the expected board effect across sweeps
(D28), spreads, variance ratios, powers, cluster counts and costs, plus open-type validation quantities (blind support,
live-only slope, immediate response, exposure, between-cluster SDs).
"""
from __future__ import annotations

import gzip
import glob
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S9")); sys.path.insert(0, str(ROOT / "gates/S8"))
from stpt import sim, evidence as E  # noqa: E402
import s9_kernels as KK  # noqa: E402
import s9_sim as S  # noqa: E402
import analyse_s8 as A8  # noqa: E402

CONF, ALL = KK.CONF, KK.ALL
T0, D, W = 5, 3, 5
HMAX = 60
import os
QUICK = os.environ.get("S9_QUICK") == "1"                     # smoke test only; never the reported run
POOL, HZ_BOARDS, VAL_REPS = (8, 20, 1) if QUICK else (200, 2000, 5)
NDRAW = 4 if QUICK else 200
S8_CONS = {"board": 0.0712, "persistence": 0.0546}          # S8 conservative pooled SDs (s8_summary.json, df 16)
REF, BOUND = 0.05, 0.03
Z = {"mde": stats.norm.ppf(1 - 0.025 / 2) + stats.norm.ppf(0.8)}
GPU_H = 2.49
t_start = time.time()


def log(*a):
    print(f"[{time.time() - t_start:6.0f}s]", *a, flush=True)


def jitter_sd():
    vc = json.load(open(ROOT / "gates/S4/results/s4_variance_components.json"))
    T = {m: v["T"] for m, v in json.load(open(ROOT / "analysis/results/t_options.json"))["options"]["C_per_model_evidence_anchored"].items()}
    return {m: math.sqrt(vc[m]["w3"]["var_probe_x_start_nats2"]) / T[m] for m in ALL}


def board_values(r, H):
    live, blind = np.array(r["live"]), np.array(r["blind"])
    return {"final": live[H] - blind[H], "window": float((live[H - 5:H + 1] - blind[H - 5:H + 1]).mean()),
            "persistence": r["persistence"], "traj": live - blind, "live": live}


def main():
    out = {"plan": "gates/S9/S9_PLAN.md", "params": {"T0": T0, "D": D, "W": W, "HMAX": HMAX, "pool": POOL, "horizon_boards": HZ_BOARDS}}
    log("kernels")
    KD = KK.point_and_draws(NDRAW)
    js = jitter_sd(); out["jitter_sd_logit_at_T"] = js
    out_k = {m: {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in KD[m]["point"].items()} for m in ALL}
    (ROOT / "gates/S9/results").mkdir(parents=True, exist_ok=True)
    if not QUICK:
        (ROOT / "gates/S9/results/kernels_s8.json").write_text(json.dumps({"doc": KK.__doc__, "point": out_k}, indent=1))

    # ---------- pool of simulated confirmatory clusters (shared by every model and kernel draw) ----------
    rng = np.random.Generator(np.random.PCG64(E.seed_of("S9-pool")))
    pool = [(S.make_cluster(rng, sim.rrg, E.seed_of("S9-pool-graph", j)), S.make_stream(rng, HMAX, T0, D, W)) for j in range(POOL)]
    log("pool ready")
    res = {m: {} for m in ALL}            # res[m][k] = list of board_values dicts (k = "point" or draw index)
    for m in ALL:
        for k in ["point"] + list(range(NDRAW)):
            K = KD[m]["point"] if k == "point" else KD[m]["draws"][k]
            res[m][k] = [S.simulate_cluster(cl, st, K, js[m], HMAX, T0, D, W) for cl, st in pool]
        log("pool simulated", m)

    # ---------- horizon (D28): point estimate on >= 1,000 fresh boards; draws on the pool ----------
    rng_h = np.random.Generator(np.random.PCG64(E.seed_of("S9-horizon")))
    hz_boards = [(S.make_cluster(rng_h, sim.rrg, E.seed_of("S9-horizon-graph", j)), S.make_stream(rng_h, HMAX, T0, D, W)) for j in range(HZ_BOARDS)]
    horizon = {"H_grid": list(range(30, HMAX + 1, 5)), "models": {}}
    live_slope = {}
    final_vs_window = {}
    for m in CONF + ["llama-3.1-8b-it"]:
        rs = [S.simulate_cluster(cl, st, KD[m]["point"], js[m], HMAX, T0, D, W) for cl, st in hz_boards]
        traj = np.array([np.array(r["live"]) - np.array(r["blind"]) for r in rs])          # boards x 61
        mean_traj = traj.mean(0)
        se_traj = traj.std(0, ddof=1) / math.sqrt(len(rs))
        ch = {H: float(mean_traj[H] - mean_traj[H - 10]) for H in horizon["H_grid"]}
        ch_se = {H: float(math.sqrt(se_traj[H] ** 2 + se_traj[H - 10] ** 2)) for H in horizon["H_grid"]}
        draws_ch = []
        for k in range(NDRAW):
            tr = np.array([b["traj"] for b in (board_values(r, 30) for r in res[m][k])])
            draws_ch.append({H: float(tr[:, H].mean() - tr[:, H - 10].mean()) for H in horizon["H_grid"]})
        q80 = {H: float(np.quantile([abs(d[H]) for d in draws_ch], 0.8)) for H in horizon["H_grid"]}
        horizon["models"][m] = {"change_last10_point": ch, "change_last10_point_se": ch_se, "abs_change_last10_q80_over_draws": q80}
        L = np.array([np.array(r["live"]) for r in rs])
        sl = [np.polyfit(np.arange(20, 31), L[i, 20:31], 1)[0] for i in range(len(rs))]
        live_slope[m] = {"mean_per_sweep": float(np.mean(sl)), "implied_change_10_sweeps": float(10 * np.mean(sl))}
        fin = traj[:, 30]; win = traj[:, 25:31].mean(1)
        final_vs_window[m] = {"var_ratio_window_over_final_H30": float(win.var(ddof=1) / fin.var(ddof=1))}
        log("horizon", m)
    ok = {}
    for H in horizon["H_grid"]:
        ok[H] = all(abs(horizon["models"][m]["change_last10_point"][H]) < 0.025 and horizon["models"][m]["abs_change_last10_q80_over_draws"][H] < 0.025
                    for m in CONF)
    horizon["rule_met_by_H"] = {str(H): bool(v) for H, v in ok.items()}
    H_star = 30 if ok[30] else next((H for H in horizon["H_grid"] if ok[H]), None)
    horizon["decision"] = ("30 sweeps stands" if H_star == 30 else
                           (f"proposed: {H_star} sweeps (for approval)" if H_star else "no H <= 60 meets the rule (to the owner)"))
    horizon["H_star"] = H_star
    horizon["sim_live_slope_sweeps_20_30"] = live_slope
    horizon["s8_live_slope_open"] = {"mean_per_sweep": 0.002977, "ci95": [0.000772, 0.005183], "units": 24}
    out["horizon"] = horizon
    out["final_window"] = final_vs_window
    Hs = H_star or 30

    # ---------- validation against S8 open quantities ----------
    log("validation")
    clusters = json.load(open(ROOT / "gates/S8/inputs/clusters.json"))
    prm8 = json.load(open(ROOT / "gates/S8/s8_params.json"))
    s8 = json.load(open(ROOT / "gates/S8/results/s8_summary.json"))
    obs_blind = {}
    for m in CONF:
        tr = []
        for f in glob.glob(str(ROOT / f"gates/S8/artifacts/*/s8_{m}_c*.json.gz")):
            r = json.loads(gzip.decompress(open(f, "rb").read()))["result"]; c = next(x for x in clusters if x["cluster"] == r["cluster"])
            _, _, _, truth = A8.info(c)
            _, sw, _ = A8.replay(r["initial_votes"], r["blind"], every=100)
            tr.append([A8.truth_share(r["initial_votes"], truth)] + [A8.truth_share(v, truth) for v in sw])
        obs_blind[m] = np.mean(tr, 0)[[0, 5, 10, 15, 20, 25, 30]].tolist()
    s8cl = []
    for c in clusters:
        _, informed, fav, truth = A8.info(c)
        typ = np.array([0 if not informed[i] else KK.ACC_TYPE[c["alloc"]["items"][c["alloc"]["holders"][str(i)][0]]["accuracy"]] for i in range(100)], np.int64)
        favs = np.array([0 if fav[i] is None else int(fav[i] == truth) for i in range(100)], np.int64)
        adj = c["adj"]; indptr = np.cumsum([0] + [len(a) for a in adj]).astype(np.int64); nbr = np.array([j for a in adj for j in a], np.int64)
        s8cl.append((c, indptr, nbr, typ, favs))
    rng_v = np.random.Generator(np.random.PCG64(E.seed_of("S9-validation")))
    reps = []
    for d in range(NDRAW):
        for rep in range(VAL_REPS):
            streams = [S.make_stream(rng_v, 30, T0, D, W) for _ in s8cl]
            phs = []
            for (c, indptr, nbr, typ, favs) in s8cl:
                cl = S.make_cluster(rng_v, lambda N_, d_, s_: (indptr, nbr, None), 0, typ_override=(typ, favs))
                if c["rule"] == "ii":
                    cl["ph"] = (rng_v.random(100) < 0.5).astype(np.int64)
                phs.append(cl)
            rec = {}
            for m in CONF:
                K = KD[m]["draws"][d]
                vals = []
                for (c, *_), cl, st in zip(s8cl, phs, streams):
                    K2 = K if c["rule"] == "i" else {**K, "init": np.array([[0.5, 0.5]] * 4)}     # rule (ii): 50/50 start
                    r = S.simulate_cluster(cl, st, K2, js[m], 30, T0, D, W)
                    vals.append((c, r))
                rec[m] = vals
            reps.append(rec)
        if d % 50 == 49:
            log("validation draws", d + 1)

    def sd_centred(vals_by_setting):
        ss, df = 0.0, 0
        for v in vals_by_setting.values():
            a = np.array(v); ss += float(((a - a.mean()) ** 2).sum()); df += len(a) - 1
        return math.sqrt(ss / df)

    sim_q = {"blind_traj": {m: [] for m in CONF}, "live_slope_pooled": [], "immediate_pooled": [],
             "sd_board": {m: [] for m in CONF}, "sd_persistence": {m: [] for m in CONF}, "sd_board_pooled": [], "sd_persistence_pooled": []}
    for rec in reps:
        slopes, imms, pb, pp = [], [], {}, {}
        for m in CONF:
            bt = np.mean([np.array(r["blind"]) for _, r in rec[m]], 0)[[0, 5, 10, 15, 20, 25, 30]]
            sim_q["blind_traj"][m].append(bt.tolist())
            be, pe = {}, {}
            for c, r in rec[m]:
                if c["rule"] != "i":
                    continue
                slopes.append(np.polyfit(np.arange(20, 31), np.array(r["live"])[20:31], 1)[0]); imms.append(r["immediate"])
                be.setdefault(c["setting"], []).append(r["live"][30] - r["blind"][30]); pe.setdefault(c["setting"], []).append(r["persistence"])
                pb.setdefault((m, c["setting"]), []).append(r["live"][30] - r["blind"][30]); pp.setdefault((m, c["setting"]), []).append(r["persistence"])
            sim_q["sd_board"][m].append(sd_centred(be)); sim_q["sd_persistence"][m].append(sd_centred(pe))
        sim_q["live_slope_pooled"].append(float(np.mean(slopes))); sim_q["immediate_pooled"].append(float(np.mean(imms)))
        sim_q["sd_board_pooled"].append(sd_centred(pb)); sim_q["sd_persistence_pooled"].append(sd_centred(pp))
    rng95 = lambda a: [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]
    val = {"blind_trajectory_sweeps_0_5_10_15_20_25_30": {}, "flags": []}
    for m in CONF:
        A_ = np.array(sim_q["blind_traj"][m]); lo, hi = np.quantile(A_, 0.025, 0), np.quantile(A_, 0.975, 0)
        inside = [bool(lo[i] <= obs_blind[m][i] <= hi[i]) for i in range(7)]
        val["blind_trajectory_sweeps_0_5_10_15_20_25_30"][m] = {"s8": obs_blind[m], "sim_lo": lo.tolist(), "sim_hi": hi.tolist(), "inside": inside}
        if not all(inside):
            val["flags"].append(f"{m}: S8 blind trajectory outside the simulation's 95% range at sweeps " +
                                str([s for s, ok_ in zip([0, 5, 10, 15, 20, 25, 30], inside) if not ok_]))
    for key, obs in (("live_slope_pooled", 0.002977), ("immediate_pooled", s8["pooled_confirmatory"]["manipulation_check_immediate_response"]["mean"])):
        r_ = rng95(sim_q[key]); val[key] = {"s8": obs, "sim_95": r_, "inside": bool(r_[0] <= obs <= r_[1])}
        if not val[key]["inside"]:
            val["flags"].append(f"{key}: S8 {obs:.4f} outside the simulation's 95% range {r_[0]:.4f} to {r_[1]:.4f}")
    for key, s8key in (("sd_board", "board_effect_between_cluster"), ("sd_persistence", "persistence_itt_between_cluster")):
        val[key] = {}
        for m in CONF:
            obs = s8["models"][m]["variance_components"][s8key]["sd"]; r_ = rng95(sim_q[key][m])
            val[key][m] = {"s8": obs, "sim_95": r_, "sim_median": float(np.median(sim_q[key][m])), "inside": bool(r_[0] <= obs <= r_[1])}
            if not val[key][m]["inside"]:
                val["flags"].append(f"{key} {m}: S8 {obs:.3f} outside the simulation's 95% range {r_[0]:.3f} to {r_[1]:.3f}")
        obs_p = s8["pooled_confirmatory"]["variance_components"][s8key]["sd"]; med = float(np.median(sim_q[key + "_pooled"]))
        val[key + "_pooled"] = {"s8": obs_p, "sim_median": med, "sim_95": rng95(sim_q[key + "_pooled"]), "ratio_sim_over_s8": med / obs_p}
        if med < 0.7 * obs_p:
            val["flags"].append(f"{key} pooled: simulated median {med:.3f} < 0.7 x S8 {obs_p:.3f}")
    val["exposure_sim_mean"] = float(np.mean([r["exposure"] for m in CONF for r in res[m]["point"]]))
    val["exposure_s8"] = 0.958
    out["validation"] = val

    # ---------- sizing at rho = 1 ----------
    log("sizing")
    sd = {"board_final": {}, "board_window": {}, "persistence": {}}
    native_rho = {"board_final": [], "persistence": []}
    for m in CONF:
        for key in sd:
            per_draw = []
            for k in range(NDRAW):
                bv = [board_values(r, Hs) for r in res[m][k]]
                per_draw.append(float(np.std([b["final" if key == "board_final" else "window" if key == "board_window" else "persistence"] for b in bv], ddof=1)))
            sd[key][m] = {"q80": float(np.quantile(per_draw, 0.8)), "median": float(np.median(per_draw))}
    for k in range(NDRAW):
        for key, f in (("board_final", "final"), ("persistence", "persistence")):
            X = np.array([[board_values(r, Hs)[f] for r in res[m][k]] for m in CONF])
            R = np.corrcoef(X); native_rho[key].append(float(R[~np.eye(4, dtype=bool)].mean()))
    sizing = {}
    win_ratio = np.mean([sd["board_window"][m]["q80"] / sd["board_final"][m]["q80"] for m in CONF])
    for key, s8key in (("board_final", "board"), ("board_window", "board"), ("persistence", "persistence")):
        sim_rho1 = float(np.mean([sd[key][m]["q80"] for m in CONF]))          # rho = 1: SD of the cross-model mean = mean SD
        s8_floor = S8_CONS[s8key] * (win_ratio if key == "board_window" else 1.0)
        sizing[key] = {"sim_q80_sd_rho1": sim_rho1, "s8_conservative_sd": s8_floor, "sizing_sd": max(sim_rho1, s8_floor),
                       "source": "simulation" if sim_rho1 >= s8_floor else "S8 conservative"}
    out["sizing"] = {"per_model_sd": sd, "rho1": sizing, "native_rho_sim": {k: {"median": float(np.median(v)), "q80": float(np.quantile(v, 0.8))} for k, v in native_rho.items()},
                     "rho_s8_variance_components": json.load(open(ROOT / "gates/S9/results/rho_from_s8.json"))["board_effect"]["rho_mean_offdiag"],
                     "window_over_final_sd_ratio": float(win_ratio)}

    def n_for(se_max, sdv):
        return int(math.ceil((sdv / se_max) ** 2))

    se_lean = REF / Z["mde"]; se_std = BOUND / (stats.norm.ppf(0.95) + stats.norm.ppf(0.90)); se_strong = BOUND / (2 * stats.norm.ppf(0.95))

    def tier_table(board_key):
        rows = {}
        for name, se in (("Lean", se_lean), ("Standard", se_std), ("Strong", se_strong)):
            nb = n_for(se, sizing[board_key]["sizing_sd"]); npers = n_for(se, sizing["persistence"]["sizing_sd"]); n = max(nb, npers)
            row = {"clusters": n, "driven_by": "board effect" if nb >= npers else "persistence"}
            for key, lab in ((board_key, "board"), ("persistence", "persistence")):
                s_ = sizing[key]["sizing_sd"] / math.sqrt(n)
                row[f"mde_{lab}"] = float(Z["mde"] * s_)
                row[f"tost_power_{lab}_alpha05"] = float(max(0.0, 2 * stats.norm.cdf(BOUND / s_ - stats.norm.ppf(0.95)) - 1))
                row[f"tost_power_{lab}_alpha025"] = float(max(0.0, 2 * stats.norm.cdf(BOUND / s_ - stats.norm.ppf(0.975)) - 1))
            rows[name] = row
        return rows
    tiers = {"final_sweep_outcome": tier_table("board_final"), "window_outcome_25_30": tier_table("board_window")}

    # ---------- normal-approximation check (complete studies; native rho; point kernel; centred) ----------
    def study_check(n, reps_=200 if QUICK else 4000):
        rng_c = np.random.Generator(np.random.PCG64(E.seed_of("S9-studies", n)))
        X = {key: np.mean([[board_values(r, Hs)[key] for r in res[m]["point"]] for m in CONF], 0) for key in ("final", "persistence")}
        outc = {}
        for key, x in X.items():
            x = x - x.mean()
            hits_tost, hits_sup = 0, 0
            for _ in range(reps_):
                smp = rng_c.choice(x, n, replace=True); mu, se = smp.mean(), smp.std(ddof=1) / math.sqrt(n)
                tq = stats.t.ppf(0.95, n - 1)
                hits_tost += (mu - tq * se > -BOUND) and (mu + tq * se < BOUND)
                smp2 = smp + REF; mu2 = smp2.mean()
                hits_sup += abs(mu2 / se) > stats.t.ppf(1 - 0.0125, n - 1)
            sdx = x.std(ddof=1)
            outc[key] = {"empirical_tost_power": hits_tost / reps_, "normal_tost_power": float(max(0, 2 * stats.norm.cdf(BOUND / (sdx / math.sqrt(n)) - stats.norm.ppf(0.95)) - 1)),
                         "empirical_power_at_0.05": hits_sup / reps_, "normal_power_at_0.05": float(stats.norm.cdf(REF / (sdx / math.sqrt(n)) - stats.norm.ppf(1 - 0.0125)))}
        return outc
    checks = {}
    for name in ("Lean", "Standard", "Strong"):
        n = tiers["final_sweep_outcome"][name]["clusters"]
        checks[f"{name} (n={n})"] = study_check(n)
    out["normal_approximation_check_native_rho"] = checks

    # ---------- story random effect: generalisation sensitivity at the Strong tier ----------
    gen = {}
    for outcome, bkey in (("final_sweep_outcome", "board_final"), ("window_outcome_25_30", "board_window")):
        n = tiers[outcome]["Strong"]["clusters"]; Sst = min(n, 26)
        gen[outcome] = {}
        for tau in (0.0, 0.02, 0.04):
            g = {}
            for key, lab in ((bkey, "board"), ("persistence", "persistence")):
                se = math.sqrt(sizing[key]["sizing_sd"] ** 2 / n + tau ** 2 / Sst)
                g[f"mde_{lab}"] = float(Z["mde"] * se); g[f"tost_power_{lab}"] = float(max(0, 2 * stats.norm.cdf(BOUND / se - stats.norm.ppf(0.95)) - 1))
            gen[outcome][f"story_sd_{tau}"] = g
    out["generalisation_to_new_stories_at_Strong"] = gen

    # ---------- cost ----------
    sec = {m: float(np.mean([c["seconds"] for c, cl in zip(s8["models"][m]["cost"], range(8)) if c["cluster"] <= 6])) for m in ALL}
    calls_s8 = 100 + 2 * 3000 + 2 * 800 + 500

    def calls(H, self_reset_share=0.5):
        return 100 + 2 * H * 100 + 2 * 800 + self_reset_share * 500
    variants = {"llama-3.1-8b-it": 2, "gemma-2-9b-it": 1, "qwen3.5-9b": 1, "gemma-3-27b-it": 3, "qwen3.5-27b": 3}

    def cost(n, H):
        per_m = {m: sec[m] * calls(H) / calls_s8 for m in ALL}
        core = n * sum(per_m[m] for m in CONF)
        start_overhead = 240.0 * math.ceil(n / 4) * len(CONF)
        llama = n * per_m["llama-3.1-8b-it"] + 240.0 * math.ceil(n / 4)
        t1 = 0.2 * n * sum(per_m[m] for m in ALL)
        rule2 = 0.2 * n * sum(sec[m] * (2 * H * 100) / calls_s8 for m in ALL)
        var = 0.2 * n * sum(variants[m] * per_m[m] for m in ALL)
        setup = 3 * 600 + 5 * 300                                      # 3 pods' setup; downloads
        core_s = (core + start_overhead + setup) * 1.10
        all_s = (core + start_overhead + llama + t1 + rule2 + var + setup) * 1.10
        return {"core_usd": core_s / 3600 * GPU_H, "all_arms_usd": all_s / 3600 * GPU_H, "core_gpu_hours": core_s / 3600, "all_arms_gpu_hours": all_s / 3600}
    for outcome in tiers:
        for name, row in tiers[outcome].items():
            row.update(cost(row["clusters"], Hs))
    out["tiers"] = tiers
    out["tier_definitions"] = {"Lean": "MDE <= 0.05 on both contrasts (80% power, two-sided alpha 0.025)",
                               "Standard": "TOST power >= 0.80 at +/-0.03 on both (alpha 0.05)",
                               "Strong": "TOST power >= 0.90 at +/-0.03 on both (alpha 0.05)", "sized_at": "rho = 1 (D29)",
                               "sizing_sd_rule": "max(simulated 80th-percentile SD over kernel draws, S8 conservative SD) (D27)"}
    out["cost_assumptions"] = {"per_model_seconds_per_S8_cluster": sec, "calls_per_cluster_at_H": calls(Hs), "self_reset_share": 0.5,
                               "secondary_shares": {"llama": 1.0, "T1": 0.2, "rule_ii": 0.2, "variant_wordings_per_variant": 0.2},
                               "start_overhead_s_per_start_per_model": 240, "clusters_per_start": 4, "failed_pod_margin": 0.10, "usd_per_gpu_hour": GPU_H}
    out["seconds"] = round(time.time() - t_start, 1)
    # guard: no contrast level in the output (only changes/SDs/powers/costs); keys checked
    txt = json.dumps(out)
    for bad in ("mean_traj", "\"level\"", "board_effect_mean", "persistence_mean"):
        assert bad not in txt, bad
    (ROOT / ("gates/S9/results/s9_tiers_QUICK.json" if QUICK else "gates/S9/results/s9_tiers.json")).write_text(json.dumps(out, indent=1))
    log("done")
    print(json.dumps({"horizon": horizon["decision"], "flags": val["flags"], "sizing": sizing,
                      "Strong_final": tiers["final_sweep_outcome"]["Strong"], "Strong_window": tiers["window_outcome_25_30"]["Strong"]}, indent=1))


if __name__ == "__main__":
    main()
