"""Gate S8 analysis (gates/S8/S8_PLAN.md, with the owner's changes of D27).

  python gates/S8/analyse_s8.py --runs DIR [DIR ...] --sealed PATH --out PATH
Writes:
  --out     the S8 summary: execution, exposure, manipulation check, horizon, settling, blind support per setting, the
            rule (i) vs (ii) early live difference, VARIANCE COMPONENTS of the two confirmatory contrasts (with the 80th
            percentile of the variance's sampling distribution), live-fitted kernels, between-start shift, cost.
            It contains NO point estimate of either confirmatory contrast or of their decompositions.
  --sealed  written ONCE (refuses to overwrite), gzip + base64, never printed: the point estimates (live - blind;
            persistence, ITT and exposed-only; social and self persistence), per model, per setting and pooled.
            Its sha256 is printed so that it can be recorded in the coordination record (SEALED.md).
Inputs: per (model, cluster) files s8_<model>_c<j>.json.gz and per (model, start) probe files s8_<model>_probes_start<k>.json
from the pod; gates/S8/inputs/clusters.json; gates/S8/s8_params.json.
"""
from __future__ import annotations

import argparse
import base64
import glob
import gzip
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
CONF = ("gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b")
SECONDARY = ("llama-3.1-8b-it",)
SEALED_KEYS = ("board_effect", "persistence_itt", "persistence_exposed", "persistence_social", "persistence_self",
               "board_effect_rule_ii")


# ---------- sealed file ----------
def write_sealed(obj, path) -> str:
    path = Path(path)
    if path.exists():
        raise SystemExit(f"REFUSED: sealed file {path} exists; it is written once (D27)")
    raw = json.dumps(obj, sort_keys=True).encode()
    data = base64.b64encode(gzip.compress(raw, 9, mtime=0))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as f:                 # exclusive create: never overwrite
        f.write(data)
    return hashlib.sha256(data).hexdigest()


# ---------- reconstruction ----------
def info(c):
    N = len(c["adj"])
    informed = [False] * N; fav = [None] * N
    for pos, ids in c["alloc"]["holders"].items():
        if ids:
            informed[int(pos)] = True; fav[int(pos)] = c["alloc"]["items"][ids[0]]["favours"]
    return N, informed, fav, c["spec"]["hidden_state"]


def replay(votes0, rows, every=None, watch=None, direction=None):
    """Apply rows to a copy of votes0. Returns final votes, per-sweep truth support (if every) and per-step share of
    `watch` voting `direction` (if watch)."""
    v = list(votes0); sweep = []; share = []
    for k, row in enumerate(rows):
        v[row[1]] = row[4]
        if watch is not None:
            share.append(sum(v[i] == direction for i in watch) / len(watch))
        if every and (k + 1) % every == 0:
            sweep.append(v)
            sweep[-1] = list(v)
    return v, sweep, share


def truth_share(v, truth):
    return sum(x == truth for x in v) / len(v)


# ---------- variance components ----------
def pooled_variance(values_by_group):
    """values_by_group: {group: [values]}; each group centred on its own mean; pooled s2, df."""
    ss, df = 0.0, 0
    for vals in values_by_group.values():
        if len(vals) >= 2:
            a = np.array(vals, float)
            ss += float(((a - a.mean()) ** 2).sum()); df += len(a) - 1
    if df == 0:
        return {"s2": None, "df": 0, "s2_q80": None}
    s2 = ss / df
    return {"s2": s2, "sd": math.sqrt(s2), "df": df, "s2_q80": s2 * df / stats.chi2.ppf(0.20, df),
            "sd_q80": math.sqrt(s2 * df / stats.chi2.ppf(0.20, df))}


def tci(x):
    x = np.array(x, float); n = len(x); m = float(x.mean()); se = float(x.std(ddof=1) / math.sqrt(n))
    q = stats.t.ppf(0.975, n - 1)
    return {"n": n, "mean": m, "lo95": m - q * se, "hi95": m + q * se}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True); ap.add_argument("--sealed", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--clusters", default=str(ROOT / "gates/S8/inputs/clusters.json"))
    ap.add_argument("--params", default=str(ROOT / "gates/S8/s8_params.json"))
    a = ap.parse_args()
    clusters = {c["cluster"]: c for c in json.load(open(a.clusters))}
    prm = json.load(open(a.params))
    files = sorted(f for d in a.runs for f in glob.glob(os.path.join(d, "s8_*_c*.json.gz")))
    runs = defaultdict(dict)
    for f in files:
        r = json.loads(gzip.decompress(open(f, "rb").read()))
        runs[r["model"]][r["result"]["cluster"]] = r
    summary = {"plan": "gates/S8/S8_PLAN.md (D27)", "models": {}, "pooled_confirmatory": {}}
    sealed = {"note": "S8 pilot point estimates, sealed (D27). Development data; pilot clusters are never reused.", "models": {}}
    units_immediate, units_slope, pooled_be, pooled_pe = [], [], defaultdict(list), defaultdict(list)
    for m in sorted(runs):
        R = runs[m]; M = {"clusters": sorted(R)}; S = {}
        rows_total = miss_total = map_aa = 0
        be = defaultdict(list); be_ii = defaultdict(list); pe = defaultdict(list); pe_exp = defaultdict(list)
        soc = defaultdict(list); slf = defaultdict(list); within = []
        exposure, immediate_by_cluster = [], {}
        live_traj = defaultdict(list); blind_traj = defaultdict(list); early = defaultdict(list); blind_final = defaultdict(list)
        kern_u, kern_i = [], []
        cost = []
        for j, run in sorted(R.items()):
            res = run["result"]; c = clusters[j]; N, informed, fav, truth = info(c)
            H, t0, D, W = prm["H"] * N, prm["t0"] * N, prm["D"] * N, prm["W"] * N
            for key in ("live", "blind"):
                for row in res[key]:
                    rows_total += 1; miss_total += row[7]; map_aa += row[8]
            for p in res["pulses"]:
                rows_total += len(p["rows"]); miss_total += sum(r[7] for r in p["rows"])
            v0 = res["initial_votes"]
            vl, sw_l, _ = replay(v0, res["live"], every=N)
            vb, sw_b, _ = replay(v0, res["blind"], every=N)
            tl = [truth_share(v, truth) for v in sw_l]; tb = [truth_share(v, truth) for v in sw_b]
            live_traj[res["rule"]].append([truth_share(v0, truth)] + tl); blind_traj[res["rule"]].append([truth_share(v0, truth)] + tb)
            early[res["rule"]].append([truth_share(v0, truth)] + tl[:5])
            effect = truth_share(vl, truth) - truth_share(vb, truth)
            if res["rule"] == "i":
                be[c["setting"]].append(effect)
                blind_final[c["setting"]].append(truth_share(vb, truth))
                if m in CONF:
                    xs = np.arange(20, 31); ys = np.array(([truth_share(v0, truth)] + tl)[20:31])
                    units_slope.append(float(np.polyfit(xs, ys, 1)[0]))
            else:
                be_ii[c["setting"]].append(effect)
            # kernels from live main updates (reference coordinates, at T)
            for row in res["live"]:
                if row[5] is None:
                    continue
                i, own, shown = row[1], row[2], row[3]
                lA = row[5] / res["T"]
                ref = fav[i] if informed[i] else own
                lref = lA if ref == "A" else -lA
                mref = shown.count(ref)
                if informed[i]:
                    kern_i.append((1.0, 1.0 if own == ref else -1.0, mref - 2.0, lref))
                else:
                    kern_u.append((1.0, mref - 2.0, lref))
            if res["rule"] == "i":
                vt0, _, _ = replay(v0, res["live"][:t0])
                cl_imm, cl_pe, cl_pe_exp = [], [], []
                for p in res["pulses"]:
                    Rset, d = p["recipients"], p["direction"]
                    _, _, sh_p = replay(vt0, p["rows"], watch=Rset, direction=d)
                    _, _, sh_u = replay(vt0, res["live"][t0:t0 + D + W], watch=Rset, direction=d)
                    diff = np.array(sh_p) - np.array(sh_u)
                    upd = {row[1] for row in p["rows"][:D]}
                    exposed = [i for i in Rset if i in upd]
                    exposure.append(len(exposed) / len(Rset))
                    cl_imm.append(float(diff[:D].mean())); cl_pe.append(float(diff[D:].mean()))
                    if exposed:
                        _, _, ep = replay(vt0, p["rows"], watch=exposed, direction=d)
                        _, _, eu = replay(vt0, res["live"][t0:t0 + D + W], watch=exposed, direction=d)
                        cl_pe_exp.append(float((np.array(ep) - np.array(eu))[D:].mean()))
                    if res["self_reset"] and res["self_reset"]["pulse_index"] == p["index"]:
                        # self-reset branch: state at restoration = pulsed branch after D rows, recipients reset
                        vr, _, _ = replay(vt0, p["rows"][:D])
                        for i in Rset:
                            vr[i] = p["votes_at_pulse"][i]
                        _, _, sh_s = replay(vr, res["self_reset"]["rows"], watch=Rset, direction=d)
                        social = float((np.array(sh_s) - np.array(sh_u[D:])).mean())
                        soc[c["setting"]].append(social); slf[c["setting"]].append(cl_pe[-1] - social)
                immediate_by_cluster[j] = float(np.mean(cl_imm))
                pe[c["setting"]].append(float(np.mean(cl_pe)))
                within.append(float((cl_pe[0] - cl_pe[1]) ** 2 / 2))
                if cl_pe_exp:
                    pe_exp[c["setting"]].append(float(np.mean(cl_pe_exp)))
                if m in CONF:
                    units_immediate.append(immediate_by_cluster[j])
            cost.append({"cluster": j, "seconds": res["seconds"], "calls": run.get("model_calls")})
        # ---- open summary for this model (no contrast point estimates) ----
        M["execution"] = {"rows": rows_total, "missing": miss_total, "missing_share": miss_total / max(rows_total, 1),
                          "letter_A_as_A_share_main": map_aa / max(sum(len(r["result"]["live"]) + len(r["result"]["blind"]) for r in R.values()), 1)}
        M["exposure_itt"] = {"mean": float(np.mean(exposure)) if exposure else None, "n_pulses": len(exposure)}
        M["immediate_response_by_cluster"] = immediate_by_cluster
        M["immediate_response_mean"] = float(np.mean(list(immediate_by_cluster.values()))) if immediate_by_cluster else None
        M["variance_components"] = {
            "board_effect_between_cluster": pooled_variance(be),
            "persistence_itt_between_cluster": pooled_variance(pe),
            "persistence_within_cluster_between_branch_s2": float(np.mean(within)) if within else None,
            "assumption": "between-cluster variance pooled across the two evidence settings, each centred on its own mean (D27)"}
        M["blind_final_support_by_setting"] = {s: float(np.mean(v)) for s, v in blind_final.items()}
        M["settling_sweep"] = {}
        for cond, tr in (("live", live_traj.get("i", [])), ("blind", blind_traj.get("i", []))):
            if tr:
                mean = np.mean(tr, 0); final = mean[25:].mean()
                M["settling_sweep"][cond] = next((int(k) for k in range(len(mean)) if np.all(np.abs(mean[k:] - final) < 0.02)), None)
        if early.get("ii") and early.get("i"):
            ei, eii = np.mean(early["i"], 0), np.mean(early["ii"], 0)
            M["rule_i_vs_ii_live_support_sweeps_0_5"] = {"rule_i": ei.tolist(), "rule_ii": eii.tolist(), "difference": (ei - eii).tolist(),
                                                        "n_clusters": [len(early["i"]), len(early["ii"])]}
        if kern_u and kern_i:
            U = np.array(kern_u); I = np.array(kern_i)
            bu = np.linalg.lstsq(U[:, :2], U[:, 2], rcond=None)[0]; bi = np.linalg.lstsq(I[:, :3], I[:, 3], rcond=None)[0]
            M["live_kernel_at_T"] = {"a_u": float(bu[0]), "c_u": float(bu[1]), "a_i": float(bi[0]), "b_i": float(bi[1]), "c_i": float(bi[2]),
                                     "n_uninformed": len(U), "n_informed": len(I)}
        M["cost"] = cost
        # within-start probes (begin vs end of each start) and between-start shift (S_p at the model's T)
        pf = sorted(f for d in a.runs for f in glob.glob(os.path.join(d, f"s8_{m}_probes_start*.json")))
        P = {json.load(open(f))["start"]: json.load(open(f)) for f in pf}
        if P:
            M["within_start_probes_identical"] = {str(k): bool(v["begin"] == v["end"]) for k, v in P.items()}
            if len(P) >= 2:
                k1, k2 = sorted(P)[:2]
                d = np.array(P[k1]["begin"]) - np.array(P[k2]["begin"])
                T = next(iter(R.values()))["result"]["T"]
                M["between_start_shift"] = {"rms_logit_diff_nats": float(np.sqrt(np.mean(d ** 2))),
                                            "S_p_at_T": float(0.25 * np.sqrt(np.mean(d ** 2)) / T)}
        summary["models"][m] = M
        if m in CONF:
            for s, v in be.items():
                pooled_be[f"{m}|{s}"] += v
            for s, v in pe.items():
                pooled_pe[f"{m}|{s}"] += v
        # ---- sealed point estimates ----
        allv = lambda d: [x for v in d.values() for x in v]
        S = {k: {"by_setting": {s: float(np.mean(v)) for s, v in d.items()}, "all": float(np.mean(allv(d))) if allv(d) else None, "n": len(allv(d))}
             for k, d in (("board_effect", be), ("board_effect_rule_ii", be_ii), ("persistence_itt", pe), ("persistence_exposed", pe_exp),
                          ("persistence_social", soc), ("persistence_self", slf))}
        sealed["models"][m] = S
    # ---- pooled (confirmatory four) ----
    summary["pooled_confirmatory"]["manipulation_check_immediate_response"] = tci(units_immediate) if len(units_immediate) > 1 else None
    if summary["pooled_confirmatory"]["manipulation_check_immediate_response"]:
        summary["pooled_confirmatory"]["manipulation_check_pass"] = bool(summary["pooled_confirmatory"]["manipulation_check_immediate_response"]["lo95"] > 0)
    if len(units_slope) > 1:
        h = tci(units_slope)
        summary["pooled_confirmatory"]["live_slope_sweeps_20_30_descriptive"] = {
            **h, "implied_change_over_10_sweeps": [10 * h["lo95"], 10 * h["hi95"]],
            "role": "descriptive consistency check only (D28); the horizon is decided in S9 by simulation"}
    summary["pooled_confirmatory"]["variance_components"] = {
        "board_effect_between_cluster": pooled_variance(pooled_be),
        "persistence_itt_between_cluster": pooled_variance(pooled_pe),
        "assumption": "centred per model x setting; pooled across settings and the four confirmatory models (D27)"}
    sc = {}
    for k in SEALED_KEYS:
        vals = [sealed["models"][m][k]["all"] for m in CONF if m in sealed["models"] and sealed["models"][m][k]["all"] is not None]
        sc[k] = float(np.mean(vals)) if vals else None
    sealed["pooled_confirmatory_mean_of_model_means"] = sc
    # ---- guard: nothing sealed may appear in the summary ----
    sealed_numbers = set()
    for m, S in sealed["models"].items():
        for k, d in S.items():
            sealed_numbers |= {round(x, 12) for x in d["by_setting"].values()}
            if d["all"] is not None:
                sealed_numbers.add(round(d["all"], 12))
    sealed_numbers |= {round(x, 12) for x in sc.values() if x is not None}

    def floats(o, path=""):
        if isinstance(o, float):
            yield path, round(o, 12)
        elif isinstance(o, dict):
            for k, v in o.items():
                yield from floats(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from floats(v, f"{path}[{i}]")
    # Shares on N = 100 boards lie on a coarse grid, so the planned grid-valued fields (the D25 rule (i) vs (ii) early
    # live support and the blind support per setting) can equal a sealed value by coincidence; they are not contrasts
    # and are exempt from the value check (fix made when the guard fired on them, before any output was written).
    GRID_FIELDS = ("/rule_i_vs_ii_live_support_sweeps_0_5/", "/blind_final_support_by_setting/")
    hits = sorted({p for p, x in floats(summary) if x in sealed_numbers and x != 0.0 and not any(g in p + "/" for g in GRID_FIELDS)})
    if hits:      # report WHERE only, never the values
        raise SystemExit("REFUSED: summary fields equal to a sealed value: " + "; ".join(hits))
    if any(k in json.dumps(summary) for k in ("persistence_itt\"", "board_effect\"", "persistence_social", "persistence_self", "persistence_exposed")):
        raise SystemExit("REFUSED: a sealed key appears in the summary")
    h = write_sealed(sealed, a.sealed)
    summary["sealed_file"] = {"path": str(a.sealed), "sha256": h}
    Path(a.out).write_text(json.dumps(summary, indent=1))
    print("summary written:", a.out)
    print("sealed file written once:", a.sealed, "sha256", h)


if __name__ == "__main__":
    main()
