"""StPT S10 secondary analyses (registration §6) and the §8 calibration measures. WRITTEN BLIND (owner, D62).

Specification: gates/S10/analysis/SECONDARY_ANALYSIS_SPEC.md (items 1-11; choices A-H as the owner decided them blind,
D63, in OPTIONS below). This module was developed and tested on mock records and synthetic data only
(tests/test_secondary_analysis.py). Its loader (load_records) refuses real records unless the coordination record holds
an owner decision whose title begins "S10 unblinding authorised" (UNBLIND_TITLE).

Every record passes confirmatory.verify_record (full recomputation; via confirmatory.outcomes) before any value is
taken from it. Every estimate uses the confirmatory model (confirmatory.infer: server-start block random intercept,
REML, Satterthwaite df); models are fixed strata; pooled estimates average the models within a cluster first.
No Holm (registration §6), except inside the subset sensitivity analyses, where the registration compares conclusions
with the primary's (choice B).

Usage (only after an unblinding decision):
  python gates/S10/analysis/secondary.py --coord <StPT-MP-Coordination clone> --decision D<n> \
      --runs runs.json --out gates/S10/results/secondary_analysis.json
  runs.json: {"<model>": ["<local copy of stpt/S10/<run>>", ...], ...}; the final run of each stage and model, whose
  folder holds every record of that stage (restored records included).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (str(HERE), str(ROOT), str(ROOT / "gates/S10"), str(ROOT / "gates/S10/run")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import confirmatory as CA  # noqa: E402
import s10_core as RC  # noqa: E402
from driver import stage_of  # noqa: E402

Refused = CA.Refused
CONF, ALL = list(CA.CONF), list(CA.ALL_MODELS)
N = CA.N
H, T0, D, W = CA.PRM["H"], CA.PRM["t0"], CA.PRM["D"], CA.PRM["W"]
WINDOW = (25, 30)
CONTRASTS = ("board", "persistence")

OPTIONS = {                     # SECONDARY_ANALYSIS_SPEC.md, choices A-H as the owner decided them (D63)
    "A_w3_comparator": "all_clusters",      # A: the 61-cluster W3 estimate; the same-cluster paired check beside it
    "B_subset_conclusion": "holm_tost",     # B: the primary's procedure within each subset
    "C_size_contrast": "per_cluster",       # C: per-cluster differences, confirmatory model
    "D_propagation_window": "onset",        # D: D + W sweeps from onset; the W window beside it
    "E_contacts_off": "blind_kernel",       # E: blind-board cells for all agents after restoration
    "E_sim_reps": 200,                      # E: simulation replicates per self-reset cluster (not fixed by D63)
    "G_early_sweeps": (1, 5),               # G: mean live difference over sweeps 1-5
    "H_min_count": 30,                      # H: minimum calls per cell (each side of a within-study comparison)
    "H_bound_sd": 2.0,                      # H: 2 x sqrt(drift SD^2 + both cells' SE^2)
    "H_min_battery_contexts": 2,            # H secondary: a battery cell needs 2 contexts for an SE (not fixed by D63)
}
SUBSETS = {"without_qwen3.5-9b": ["gemma-2-9b-it", "gemma-3-27b-it", "qwen3.5-27b"],
           "27b_only": ["gemma-3-27b-it", "qwen3.5-27b"]}
SIZE_PAIRS = {"gemma_27b_minus_9b": ("gemma-3-27b-it", "gemma-2-9b-it"),
              "qwen_27b_minus_9b": ("qwen3.5-27b", "qwen3.5-9b")}
ACC_P = {"3/5": 0.6, "3/4": 0.75, "9/10": 0.9}


# ---------------------------------------------------------------- blinding guard and loading
UNBLIND_TITLE = "**S10 unblinding authorised"


def require_unblinding(coord: Path, decision: str) -> str:
    """The coordination record must hold the owner's decision `decision` whose bold title begins
    "S10 unblinding authorised" (written only on the owner's explicit OK). A row that merely mentions unblinding
    (such as D62 or D63) does not count."""
    txt = (Path(coord) / "DECISIONS.md").read_text()
    row = next((l for l in txt.splitlines() if l.startswith(f"| {decision} |")), None)
    if row is None:
        raise Refused(f"no decision {decision} in the coordination record")
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    if len(cells) < 5 or not cells[3].startswith(UNBLIND_TITLE) or cells[-1] != "owner":
        raise Refused(f"decision {decision} is not the owner's S10 unblinding decision")
    return row


def _arm_of(name: str) -> str:
    a = name.split("__", 1)[1][: -len(".json.gz")]
    return a.replace("-", ":", 1) if a.startswith("wording-") else a


def load_records(runs: dict, coord: Path, decision: str) -> dict:
    """{(model, cluster, arm): result} from the final run folders of each model's stages. Refuses unless unblinded."""
    require_unblinding(coord, decision)
    out = {}
    for model, dirs in runs.items():
        for d in dirs:
            for p in sorted((Path(d) / model).glob("rec_c*__*.json.gz")):
                rec = json.loads(gzip.decompress(p.read_bytes()))
                r = rec["result"]
                key = (model, int(r["cluster"]), r["arm"])
                if key[2] != _arm_of(p.name) or r["model"] != model:
                    raise Refused(f"{p}: holds model {r['model']}, cluster {r['cluster']}, arm {r['arm']}")
                if key in out and json.dumps(out[key], sort_keys=True) != json.dumps(r, sort_keys=True):
                    raise Refused(f"{key}: two different records")
                r = dict(r)
                r["server_start_ids"] = r.get("server_start_ids") or {}
                r["_manifest"] = rec.get("manifest") or {}
                out[key] = r
    return out


# ---------------------------------------------------------------- the frozen layout
def frozen_clusters() -> dict:
    CA.frozen_universe()                       # checks the manifest hashes
    return RC.load_clusters()


def cluster_info(c) -> dict:
    informed, acc, fav = [False] * N, [None] * N, [None] * N
    for pos, ids in c["alloc"]["holders"].items():
        if ids:
            it = c["alloc"]["items"][ids[0]]
            i = int(pos)
            informed[i], acc[i], fav[i] = True, it["accuracy"], it["favours"]
    return {"informed": informed, "acc": acc, "fav": fav, "adj": c["adj"], "truth": c["truth"],
            "story": c["story_key"], "block": c["start_block"]}


def scheduled(model: str, arm: str, F: dict) -> list:
    """The clusters on which the protocol runs (model, arm) (gates/S10/draw_clusters.py flags; driver.stage_of)."""
    return sorted(j for j, c in F.items() if arm in RC.arms_for(c, model))


def expected_identity(model: str, arm: str, j: int) -> dict:
    T = 1.0 if arm == "T1" else CA.primary_T(model)
    wording = arm.split(":", 1)[1] if arm.startswith("wording:") else "w3"
    return {"model": model, "cluster": j, "arm": arm, "T": T, "wording": wording, "init_wording": "w3",
            "rule": "ii" if arm == "rule_ii" else "i", "run_key": f"CONF-c{j}", "prm": CA.PRM}


# ---------------------------------------------------------------- record-level outcomes
def _share(v, idx, val):
    return sum(v[i] == val for i in idx) / len(idx) if idx else float("nan")


def _pool(adj, recipients):
    closed = set(recipients)
    for r in recipients:
        closed.update(adj[r])
    return [i for i in range(N) if i not in closed]


def record_outcomes(res, F) -> dict:
    """confirmatory.outcomes (verified record) plus the secondary record-level quantities (spec items 4, 5, 9, 11)."""
    o = CA.outcomes(res)
    c = F[res["cluster"]]
    info = cluster_info(c)
    truth = info["truth"]
    v0 = res["initial_votes"]
    _, sl, _ = CA.replay(v0, res["live"], every=N)
    _, sb, _ = CA.replay(v0, res["blind"], every=N)
    live, blind = [list(v0)] + sl, [list(v0)] + sb
    lo, hi = WINDOW
    inf = [i for i in range(N) if info["informed"][i]]
    uni = [i for i in range(N) if not info["informed"][i]]

    def win(states, idx):
        return float(np.mean([_share(s, idx, truth) for s in states[lo:hi + 1]]))
    o["traj_live"] = [CA.support(v, truth) for v in live]
    o["traj_blind"] = [CA.support(v, truth) for v in blind]
    o["board_informed"] = win(live, inf) - win(blind, inf)
    o["board_uninformed"] = win(live, uni) - win(blind, uni)
    o["n_informed"], o["n_uninformed"] = len(inf), len(uni)
    o["missing"] = {"init": sum(r[5] for r in res["init"]), "live": sum(r[7] for r in res["live"]),
                    "blind": sum(r[7] for r in res["blind"]),
                    "pulsed": sum(r[7] for p in res.get("pulses") or [] for r in p["rows"]),
                    "self_reset": sum(r[7] for r in (res.get("self_reset") or {}).get("rows") or [])}
    o["calls"] = {"init": sum(r[3] for r in res["init"]), "live": len(res["live"]), "blind": len(res["blind"]),
                  "pulsed": sum(len(p["rows"]) for p in res.get("pulses") or []),
                  "self_reset": len((res.get("self_reset") or {}).get("rows") or [])}
    if res.get("pulses"):
        vt0, _, _ = CA.replay(v0, res["live"][:T0 * N])
        unp = res["live"][T0 * N:(T0 + D + W) * N]
        br = []
        for p in res["pulses"]:
            R, d = p["recipients"], p["direction"]
            if list(p["votes_at_pulse"]) != list(vt0):
                raise Refused(f"cluster {res['cluster']}: votes at pulse onset differ from the live run's saved state")
            _, _, sp = CA.replay(vt0, p["rows"], watch=R, direction=d)
            _, _, su = CA.replay(vt0, unp, watch=R, direction=d)
            diff = np.array(sp) - np.array(su)
            pool = _pool(info["adj"], R)
            _, _, pp = CA.replay(vt0, p["rows"], watch=pool, direction=d)
            _, _, pu = CA.replay(vt0, unp, watch=pool, direction=d)
            pdiff = np.array(pp) - np.array(pu)
            upd = {row[1] for row in p["rows"][:D * N]}
            br.append({"index": p["index"], "direction": d, "toward_truth": d == truth,
                       "itt": float(diff[D * N:].mean()), "immediate": float(diff[:D * N].mean()),
                       "end": float(diff[-1]), "prop_onset": float(pdiff.mean()),
                       "prop_window": float(pdiff[D * N:].mean()), "pool": len(pool),
                       "exposure": sum(i in upd for i in R) / len(R),
                       "traj_pulsed": [float(x) for x in np.array(sp)[N - 1::N]],
                       "traj_unpulsed": [float(x) for x in np.array(su)[N - 1::N]], "_su": su})
        if abs(float(np.mean([b["itt"] for b in br])) - o["persistence"]) > 1e-12:
            raise AssertionError("ITT persistence differs from confirmatory.outcomes")
        o["end_of_window"] = float(np.mean([b["end"] for b in br]))
        o["propagation_onset"] = float(np.mean([b["prop_onset"] for b in br]))
        o["propagation_window"] = float(np.mean([b["prop_window"] for b in br]))
        o["propagation_pool"] = [b["pool"] for b in br]
        o["exposure"] = float(np.mean([b["exposure"] for b in br]))
        sr = res.get("self_reset")
        if sr:
            b = next(x for x in br if x["index"] == sr["pulse_index"])
            p = res["pulses"][sr["pulse_index"]]
            vr, _, _ = CA.replay(vt0, p["rows"][:D * N])
            for i in p["recipients"]:
                vr[i] = vt0[i]
            _, _, ss = CA.replay(vr, sr["rows"], watch=p["recipients"], direction=p["direction"])
            social = float((np.array(ss) - np.array(b["_su"][D * N:])).mean())
            o["social"], o["self"] = social, b["itt"] - social
            o["self_reset_state"] = {"restoration_votes": vr, "recipients": p["recipients"], "direction": p["direction"],
                                     "unpulsed_restoration_votes": CA.replay(vt0, unp[:D * N])[0]}
        for x in br:
            x.pop("_su")
        o["branches"] = br
    o["cluster"], o["model"], o["arm"] = res["cluster"], res["model"], res["arm"]
    return o


def outcome_table(records: dict, F: dict) -> dict:
    return {k: record_outcomes(r, F) for k, r in records.items()}


# ---------------------------------------------------------------- checks and estimators
def check_arm(table, model, arm, F, full=True) -> list:
    """Identity, no mock, a start ID, one start per scheduled block; full=True: exactly the scheduled clusters."""
    have = sorted(j for (m, j, a) in table if m == model and a == arm)
    if full and have != scheduled(model, arm, F):
        raise Refused(f"{model} {arm}: records for {len(have)} clusters, the protocol schedules {len(scheduled(model, arm, F))}")
    by_block = defaultdict(set)
    for j in have:
        o = table[(model, j, arm)]
        exp = expected_identity(model, arm, j)
        bad = {k: o["identity"].get(k) for k, v in exp.items() if o["identity"].get(k) != v}
        if bad:
            raise Refused(f"({model}, {j}, {arm}) identity differs from the protocol: {bad}")
        if o["identity"].get("mock"):
            raise Refused(f"({model}, {j}, {arm}) comes from a mock run")
        if not o.get("server_start"):
            raise Refused(f"({model}, {j}, {arm}) has no server-start ID")
        by_block[F[j]["start_block"]].add(o["server_start"])
    if any(len(v) != 1 for v in by_block.values()):
        raise Refused(f"{model} {arm}: a scheduled block ran in more than one server start")
    return have


def estimate(values: dict, labels: dict):
    """values, labels: {cluster: ...}; the confirmatory model (block random intercept). None if fewer than 3 values."""
    js = sorted(values)
    y = [float(values[j]) for j in js]
    if len(y) < 3:
        return None
    if not all(CA._finite(v) for v in y):
        raise Refused("non-finite value")
    if max(y) - min(y) < 1e-12:                 # no variation: the REML fit is undefined (confirmatory.reml is frozen)
        return {"theta": y[0], "se": None, "df": None, "ci95": None, "ci90": None, "p_two_sided": None,
                "tost_equivalent": None, "n_clusters": len(y), "degenerate": "every value equal; no fit"}
    try:
        out = CA.infer(y, [labels[j] for j in js])
    except np.linalg.LinAlgError as e:
        return {"theta": float(np.mean(y)), "se": None, "df": None, "ci95": None, "ci90": None, "p_two_sided": None,
                "tost_equivalent": None, "n_clusters": len(y), "degenerate": f"REML fit failed: {e}"}
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in out.items()}
    out["n_clusters"] = len(y)
    return out


def per_model(table, model, key, arm="primary", clusters=None):
    js = [j for (m, j, a) in table if m == model and a == arm and (clusters is None or j in clusters)]
    vals = {j: table[(model, j, arm)][key] for j in js if table[(model, j, arm)].get(key) is not None}
    labels = {j: str(table[(model, j, arm)]["server_start"]) for j in vals}
    return estimate(vals, labels)


def pooled(table, models, key, arm="primary", clusters=None):
    """Mean over models within each cluster, then the confirmatory model; only clusters every model has."""
    sets = [{j for (m, j, a) in table if m == mm and a == arm} for mm in models]
    js = set.intersection(*sets)
    if clusters is not None:
        js &= set(clusters)
    vals, labels = {}, {}
    for j in js:
        xs = [table[(m, j, arm)].get(key) for m in models]
        if any(x is None for x in xs):
            continue
        vals[j] = float(np.mean(xs))
        labels[j] = "|".join(str(table[(m, j, arm)]["server_start"]) for m in models)
    return estimate(vals, labels)


def paired_difference(table, a, b, key, clusters=None):
    """Per-cluster difference a - b; a, b = (model, arm). Block label: the pair of starts."""
    ja = {j for (m, j, x) in table if (m, x) == a}
    jb = {j for (m, j, x) in table if (m, x) == b}
    js = ja & jb if clusters is None else ja & jb & set(clusters)
    vals, labels = {}, {}
    for j in js:
        xa, xb = table[(a[0], j, a[1])].get(key), table[(b[0], j, b[1])].get(key)
        if xa is None or xb is None:
            continue
        vals[j] = xa - xb
        labels[j] = f"{table[(a[0], j, a[1])]['server_start']}|{table[(b[0], j, b[1])]['server_start']}"
    return estimate(vals, labels)


def _summ(e):
    if e is None:
        return None
    out = {k: e[k] for k in ("theta", "se", "df", "ci95", "ci90", "p_two_sided", "tost_equivalent", "n_clusters")}
    if e.get("degenerate"):
        out["degenerate"] = e["degenerate"]
    return out


# ---------------------------------------------------------------- items 1-3
def per_model_estimates(table):
    return {m: {k: _summ(per_model(table, m, k)) for k in CONTRASTS} for m in ALL}


def _consistent(ests):
    """Registration §6 (D20): every estimate has the same sign and the 95% intervals overlap (in one dimension,
    pairwise overlap is a common point). None with fewer than two estimates."""
    ests = [e for e in ests if e is not None]
    if len(ests) < 2 or any(e["ci95"] is None for e in ests):
        return None
    return bool(len({np.sign(e["theta"]) for e in ests}) == 1 and
                max(e["ci95"][0] for e in ests) <= min(e["ci95"][1] for e in ests))


def wording_consistency(table, F, opts=OPTIONS):
    """Item 2 with choice A (D63): consistency compares the model's 61-cluster W3 estimate with each variant's; beside
    it, prominently, for each variant the same-cluster paired comparison (variant - W3 per cluster, confirmatory model)
    and the consistency rule applied to the W3 estimate on the variant's clusters."""
    out, n_consistent = {}, 0
    for m in ALL:
        variants = sorted({a for (mm, j, a) in table if mm == m and a.startswith("wording:")})
        if not variants:
            continue
        res = {"variants": [v.split(":")[1] for v in variants]}
        for k in CONTRASTS:
            w3 = per_model(table, m, k)
            var = {v: per_model(table, m, k, arm=v) for v in variants}
            same = {}
            for v in variants:
                js = sorted(j for (mm, j, a) in table if mm == m and a == v)
                w3s = per_model(table, m, k, clusters=js)
                same[v.split(":")[1]] = {"w3_same_clusters": _summ(w3s), "n_clusters": len(js),
                                         "paired_variant_minus_w3": _summ(paired_difference(table, (m, v), (m, "primary"), k, js)),
                                         "consistent_same_clusters": _consistent([w3s, var[v]])}
            main = [w3] + list(var.values())
            if opts["A_w3_comparator"] == "same_clusters":
                flags = [same[v.split(":")[1]]["consistent_same_clusters"] for v in variants]
                rule = None if None in flags else all(flags)
            else:
                rule = _consistent(main)
            res[k] = {"w3_all_clusters": _summ(w3), "variants": {v.split(":")[1]: _summ(e) for v, e in var.items()},
                      "consistent": rule, "same_cluster_paired": same}
        flags = [res[k]["consistent"] for k in CONTRASTS]
        res["consistent_both"] = None if None in flags else all(flags)
        n_consistent += bool(res["consistent_both"])
        out[m] = res
    out["n_models_consistent"] = n_consistent
    out["n_models_with_variants"] = sum(1 for m in ALL if m in out)
    return out


def conclusions(table, models, opts=OPTIONS):
    est = {k: pooled(table, models, k) for k in CONTRASTS}
    if any(est[k] is None or est[k]["p_two_sided"] is None for k in CONTRASTS):
        raise Refused(f"subset {models}: an estimate could not be fitted")
    p = {k: est[k]["p_two_sided"] for k in CONTRASTS}
    sig = CA.holm(p) if opts["B_subset_conclusion"] == "holm_tost" else {k: p[k] <= 0.05 for k in CONTRASTS}
    return {k: {"estimate": _summ(est[k]), "significant": bool(sig[k]),
                "decision": CA.decide(bool(sig[k]), est[k]["tost_equivalent"])} for k in CONTRASTS}


def sensitivity(table, primary_decisions=None, opts=OPTIONS):
    out = {}
    for name, models in SUBSETS.items():
        r = conclusions(table, models, opts)
        if primary_decisions:
            for k in CONTRASTS:
                r[k]["differs_from_primary"] = r[k]["decision"] != primary_decisions[k]
        out[name] = r
    out["size_contrasts"] = {name: {k: _summ(paired_difference(table, (a, "primary"), (b, "primary"), k))
                                    for k in CONTRASTS} for name, (a, b) in SIZE_PAIRS.items()}
    return out


def comprehension_table(per_model_res):
    hs = json.loads((ROOT / "gates/S3/results/heldout_summary.json").read_text())
    rows = {}
    for m in ALL:
        acc = hs["models"][m]["wordings"]["w3"]["accuracy"]
        frag = [{"wording": f["wording"], "qtype": f["qtype"], "accuracy": f["accuracy"]}
                for f in hs["fragility"] if f["model"] == m]
        rows[m] = {"w3_mean_accuracy": float(np.mean(list(acc.values()))), "w3_min_accuracy": float(min(acc.values())),
                   "w3_accuracies": acc, "fragility": frag, "secondary_agent": m not in CONF,
                   "board": per_model_res[m]["board"], "persistence": per_model_res[m]["persistence"]}
    return rows


# ---------------------------------------------------------------- items 4, 5, 9
def informed_split(table):
    out = {"pooled": {}, "per_model": {}}
    for k in ("board_informed", "board_uninformed"):
        out["pooled"][k] = _summ(pooled(table, CONF, k))
        out["per_model"][k] = {m: _summ(per_model(table, m, k)) for m in ALL}
    for (m, j, a), o in table.items():
        if a == "primary":
            o["board_transmission_minus_override"] = o["board_uninformed"] - o["board_informed"]
    out["pooled"]["transmission_minus_override"] = _summ(pooled(table, CONF, "board_transmission_minus_override"))
    return out


def persistence_secondaries(table, F, records=None, opts=OPTIONS):
    prop = "propagation_onset" if opts["D_propagation_window"] == "onset" else "propagation_window"
    keys = ["persistence_exposed", "immediate", "end_of_window", prop,
            "propagation_window" if prop == "propagation_onset" else "propagation_onset", "social", "self"]
    out = {"pooled": {k: _summ(pooled(table, CONF, k)) for k in keys},
           "per_model": {m: {k: _summ(per_model(table, m, k)) for k in keys} for m in ALL},
           "propagation_primary_window": prop}
    out["exposure"] = {m: float(np.mean([o["exposure"] for (mm, j, a), o in table.items() if mm == m and a == "primary"]))
                       for m in ALL if any(mm == m for (mm, _, _) in table)}
    out["pool_size"] = {m: float(np.mean([x for (mm, j, a), o in table.items() if mm == m and a == "primary"
                                          for x in o["propagation_pool"]])) for m in ALL if any(mm == m for (mm, _, _) in table)}
    if records is not None:
        out["self_social_simulation"] = self_social_crosscheck(table, records, F, opts)
    return out


def trajectories(table):
    out = {}
    for m in ALL:
        prim = [o for (mm, j, a), o in table.items() if mm == m and a == "primary"]
        if not prim:
            continue
        L, B = np.array([o["traj_live"] for o in prim]), np.array([o["traj_blind"] for o in prim])
        P = np.array([b["traj_pulsed"] for o in prim for b in o.get("branches", [])])
        U = np.array([b["traj_unpulsed"] for o in prim for b in o.get("branches", [])])

        def band(X):
            mu, se = X.mean(0), X.std(0, ddof=1) / math.sqrt(len(X)) if len(X) > 1 else np.zeros(X.shape[1])
            return {"mean": mu.tolist(), "lo95": (mu - 1.96 * se).tolist(), "hi95": (mu + 1.96 * se).tolist()}
        out[m] = {"live": band(L), "blind": band(B), "recipients_pulsed": band(P) if len(P) else None,
                  "recipients_unpulsed": band(U) if len(U) else None, "n_clusters": len(prim)}
    return out


# ---------------------------------------------------------------- item 6
def _sig(z):
    return 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))


def _same_sign(a, b):
    return None if a is None or b is None else bool(np.sign(a["theta"]) == np.sign(b["theta"]))


def t1_regime(table):
    """Choice F (D63): per-model T = 1 estimates on the T1 arm, the paired T1 - primary differences on the same
    clusters, and for each T = 1 estimate whether its sign matches the primary's (the model's 61-cluster primary
    estimate; the same-cluster primary beside it). Descriptive; no conclusion attached."""
    out = {}
    for m in ALL:
        js = sorted(j for (mm, j, a) in table if mm == m and a == "T1")
        if not js:
            continue
        r = {"n_clusters": len(js)}
        for k in CONTRASTS:
            t1, prim, prim_same = (per_model(table, m, k, arm="T1"), per_model(table, m, k),
                                   per_model(table, m, k, clusters=js))
            r[k] = {"t1": _summ(t1), "primary": _summ(prim), "primary_same_clusters": _summ(prim_same),
                    "t1_minus_primary": _summ(paired_difference(table, (m, "T1"), (m, "primary"), k)),
                    "sign_matches_primary": _same_sign(t1, prim),
                    "sign_matches_primary_same_clusters": _same_sign(t1, prim_same)}
        out[m] = r
    return out


def calibration_generalisation(records, F):
    """Informed agents' first calls (W3 blind, evidence-only, placeholder own vote, primary T): mean P(follow the
    report) by source accuracy, against Bayes, with the range over stories. 3/5 from development only."""
    dev = json.loads((ROOT / "analysis/results/t_checks.json").read_text())["item2_generalisation"]
    out = {}
    for m in ALL:
        by_acc, by_story, lref = defaultdict(list), defaultdict(lambda: defaultdict(list)), defaultdict(list)
        for (mm, j, a), r in records.items():
            if mm != m or a != "primary":
                continue
            info = cluster_info(F[j])
            for agent, _ph, _vote, call, lA, miss, _mass in r["init"]:
                if not call or miss or not info["informed"][agent]:
                    continue
                p = _sig((lA if info["fav"][agent] == "A" else -lA) / r["T"])
                lref[info["acc"][agent]].append((lA if info["fav"][agent] == "A" else -lA) / r["T"])
                by_acc[info["acc"][agent]].append(p)
                by_story[info["acc"][agent]][info["story"]].append(p)
        res = {acc: {"mean": float(np.mean(v)), "bayes": ACC_P[acc], "signed_miss": float(np.mean(v)) - ACC_P[acc],
                     "p_at_mean_logit": _sig(float(np.mean(lref[acc]))),       # development's form: sigma(mean R / T)
                     "n": len(v), "per_story_range": [float(min(np.mean(x) for x in by_story[acc].values())),
                                                      float(max(np.mean(x) for x in by_story[acc].values()))],
                     "source": "S10 confirmatory first calls"}
               for acc, v in sorted(by_acc.items())}
        if m in dev:
            pf = dev[m]["P_follow"]["3/5"]
            res["3/5"] = {"mean": pf, "bayes": ACC_P["3/5"], "signed_miss": pf - ACC_P["3/5"],
                          "source": "development (analysis/results/t_checks.json); 3/5 is not in the confirmatory evidence"}
        out[m] = res
    return out


def social_response_checks(records, F):
    """The contact response (Llama as the weakly social agent) and G1, G2, G6 (analysis/T_CALIBRATION_CHECKS.md) for
    every model, on its primary-arm main-run calls at the primary T, as analysis/t_checks.py computed them on the
    S4 probes: G1 on uninformed live calls, G2 on every live and blind call, G6 on informed live calls."""
    out = {}
    for m in ALL:
        cells, conflict = defaultdict(list), []
        sat = n_all = 0
        for (mm, j, a), r in records.items():
            if mm != m or a != "primary":
                continue
            info = cluster_info(F[j])
            for row in r["blind"]:                              # G2 counts every call, as over all probes
                if not row[7]:
                    n_all += 1
                    sat += abs(row[5]) / r["T"] > math.log(99)
            for row in r["live"]:
                if row[7]:
                    continue
                agent, own, shown, lA = row[1], row[2], row[3], row[5]
                pA = _sig(lA / r["T"])
                n_all += 1
                sat += abs(lA) / r["T"] > math.log(99)
                rep = info["fav"][agent]
                if rep is None:
                    cells[(own, shown.count("A"))].append(pA)
                elif shown.count(rep) <= 1:                     # the report opposes a 3-1 or 4-0 contact majority
                    conflict.append(pA if rep == "A" else 1 - pA)
        if not n_all:
            continue
        grad = {own: [float(np.mean(cells[(own, k)])) if cells[(own, k)] else None for k in range(5)] for own in "AB"}
        inc = {o: (None if None in grad[o] else all(b > a for a, b in zip(grad[o], grad[o][1:]))) for o in "AB"}
        resp = None
        if all(grad[o][0] is not None and grad[o][4] is not None for o in "AB"):
            resp = float(np.mean([grad[o][4] - grad[o][0] for o in "AB"]))
        out[m] = {"contact_response_0_to_4": resp, "G1_gradient": grad, "G1_strictly_increasing": inc,
                  "G1_n": {f"{o}{k}": len(cells[(o, k)]) for o in "AB" for k in range(5)},
                  "G2_saturation_share": sat / n_all, "G2_n": n_all,
                  "G6_follow_report_against_majority": float(np.mean(conflict)) if conflict else None,
                  "G6_n": len(conflict)}
    g, others = out.get("gemma-3-27b-it"), [out[m] for m in ALL if m != "gemma-3-27b-it" and m in out]
    if g and others:
        g6o = [o["G6_follow_report_against_majority"] for o in others if o["G6_follow_report_against_majority"] is not None]
        g6 = g["G6_follow_report_against_majority"]
        out["gemma_3_27b_flags"] = {
            "G1": None if None in g["G1_strictly_increasing"].values() else not all(g["G1_strictly_increasing"].values()),
            "G2": g["G2_saturation_share"] > max(o["G2_saturation_share"] for o in others) + 0.10,
            "G6": None if g6 is None or not g6o else not (min(g6o) - 0.15 <= g6 <= max(g6o) + 0.15),
            "compared_with": [m for m in ALL if m != "gemma-3-27b-it" and m in out]}
    return out


# ---------------------------------------------------------------- item 7
def rule_ii(table, opts=OPTIONS):
    lo, hi = opts["G_early_sweeps"]
    out = {}
    for m in ALL:
        js = sorted(j for (mm, j, a) in table if mm == m and a == "rule_ii" and (m, j, "primary") in table)
        if not js:
            continue
        dl = np.array([np.array(table[(m, j, "rule_ii")]["traj_live"]) - np.array(table[(m, j, "primary")]["traj_live"]) for j in js])
        db = np.array([np.array(table[(m, j, "rule_ii")]["traj_blind"]) - np.array(table[(m, j, "primary")]["traj_blind"]) for j in js])
        for j, x in zip(js, dl):
            table[(m, j, "rule_ii")]["early_live_diff"] = float(x[lo:hi + 1].mean())
            table[(m, j, "rule_ii")]["zero"] = 0.0
        early = {j: table[(m, j, "rule_ii")]["early_live_diff"] for j in js}
        labels = {j: f"{table[(m, j, 'rule_ii')]['server_start']}" for j in js}
        out[m] = {"n_clusters": len(js), "live_diff_by_sweep": dl.mean(0).tolist(), "blind_diff_by_sweep": db.mean(0).tolist(),
                  "early_live_diff": _summ(estimate(early, labels)), "early_sweeps": [lo, hi],
                  "board_rule_ii": _summ(per_model(table, m, "board", arm="rule_ii")),
                  "board_rule_ii_minus_rule_i": _summ(paired_difference(table, (m, "rule_ii"), (m, "primary"), "board"))}
    return out


# ---------------------------------------------------------------- item 8 (and the kernels for item 5's cross-check)
CONDITIONS = ("blind", "init", "live", "pulse_on", "post_restoration")
WITHIN_PAIRS = (("blind", "init"), ("live", "pulse_on"), ("live", "post_restoration"), ("pulse_on", "post_restoration"))
BATTERY_FOR = {"blind": "blind", "init": "blind", "live": "live", "pulse_on": "live", "post_restoration": "live"}


def _cell(info, agent, own, shown, live):
    """(type, own vote agrees with the reference, displayed contacts showing it; None on the blind board), reference.
    Reference: the report's option for an informed agent, its own vote for an uninformed one (as the S9 tables)."""
    if info["informed"][agent]:
        typ, ref = info["acc"][agent], info["fav"][agent]
    else:
        typ, ref = "none", own
    return (typ, int(own == ref), shown.count(ref) if live else None), ref


def kernel_cells(records, F, model, conditions=CONDITIONS):
    """{condition: {cell: [P(vote the reference) at T, one per call]}} from the model's primary-arm calls.
    blind / live: the main runs; pulse_on / post_restoration: the pulsed branches during the D pulse sweeps (displayed
    contacts as recorded) and in the W sweeps after restoration; init: the informed agents' first calls (the W3 blind
    board prompt, own vote = placeholder; s10_core.initial_state). Missing calls are left out."""
    out = {c: defaultdict(list) for c in conditions}
    for (m, j, a), r in records.items():
        if m != model or a != "primary":
            continue
        info, T = cluster_info(F[j]), r["T"]
        streams = [("live", r["live"], True), ("blind", r["blind"], False)]
        for p in r.get("pulses") or []:
            streams += [("pulse_on", p["rows"][:D * N], True), ("post_restoration", p["rows"][D * N:], True)]
        for cond, rows, live in streams:
            if cond not in out:
                continue
            for row in rows:
                if row[7]:
                    continue
                cell, ref = _cell(info, row[1], row[2], row[3], live)
                out[cond][cell].append(_sig((row[5] if ref == "A" else -row[5]) / T))
        if "init" in out:
            for agent, ph, _vote, call, lA, miss, _mass in r["init"]:
                if call and not miss:
                    cell, ref = _cell(info, agent, ph, "", False)
                    out["init"][cell].append(_sig((lA if ref == "A" else -lA) / T))
    return out


def battery_cells(model):
    """Development battery at the model's primary T, by the same cells, one value per context (mean over its W3
    layouts of P(reference) at the start-averaged logit): live = S4 W3 live probes (all six starts), as
    analysis/pulse_design.py fitted the development kernels; blind = S5 W3 blind probes (one start)."""
    sys.path.insert(0, str(ROOT / "gates/S4"))
    import analyse_s4 as A4
    T = CA.primary_T(model)
    out = {"live": defaultdict(list), "blind": defaultdict(list)}

    def add(kind, c, vals):
        ref = c["report_favours"] if c["informed"] else c["own_vote"]
        typ = c["report_accuracy"] if c["informed"] else "none"
        mref = (c["contacts_A"] if ref == "A" else 4 - c["contacts_A"]) if kind == "live" else None
        out[kind][(typ, int(c["own_vote"] == ref), mref)].append(
            float(np.mean([_sig((lA if ref == "A" else -lA) / T) for lA in vals])))

    probes, runs = A4.load([ROOT / "gates/S4/artifacts/20261102T1535Z", ROOT / "gates/S4/artifacts/20261102T1535Zb"])
    ctx = {c["context_id"]: c for c in json.loads((ROOT / "gates/S4/probes/s4_contexts.json").read_text())}
    st = runs[model]
    by_ctx = defaultdict(list)
    for pid, p in probes.items():
        if p["wording"] == "w3" and ctx[p["context_id"]]["live"]:
            lA = float(np.mean([A4.ell(st[s]["first"][pid]) for s in sorted(st)]))
            by_ctx[p["context_id"]].append(lA if p["layout"]["letter_of_content"]["A"] == "A" else -lA)
    for cid, vals in by_ctx.items():
        add("live", ctx[cid], vals)
    p5 = json.loads((ROOT / "gates/S5/probes/s5_probes.json").read_text())
    p5 = {p["prompt_id"]: p for p in (p5["prompts"] if isinstance(p5, dict) else p5)}
    c5 = {c["context_id"]: c for c in json.loads((ROOT / "gates/S5/probes/s5_contexts.json").read_text())}
    rows = json.loads((ROOT / f"gates/S5/artifacts/20261102T1807Z/s5_{model}_start1.json").read_text())["rows"]
    by_ctx = defaultdict(list)
    for x in rows:
        p = p5.get(x["prompt_id"])
        if x["read"] != "first" or p is None or p["wording"] != "w3" or c5[p["context_id"]]["live"]:
            continue
        ell = x["logp_A"] - x["logp_B"]
        by_ctx[p["context_id"]].append(ell if p["layout"]["letter_of_content"]["A"] == "A" else -ell)
    for cid, vals in by_ctx.items():
        add("blind", c5[cid], vals)
    return out


def drift_sd_prob(model, p):
    """The S4 between-start SD of the W3 logit (start offset and probe x start), in probability at p and the model's T."""
    vc = json.loads((ROOT / "gates/S4/results/s4_variance_components.json").read_text())[model]["w3"]
    sd_nats = math.sqrt(vc["var_start_offset_nats2"] + vc["var_probe_x_start_nats2"])
    return p * (1 - p) * sd_nats / CA.primary_T(model)


def _stats(v):
    n = len(v)
    return float(np.mean(v)), (float(np.std(v, ddof=1)) / math.sqrt(n) if n > 1 else None), n


def compare_cells(model, A, B, min_a, min_b, k):
    """Cells present in both with enough values; bound = k * sqrt(drift_sd(p)^2 + se_A^2 + se_B^2), p = the mean of the
    two cell values (choice H, D63: the S4 between-start SD in probability combined with each cell's SE across
    contexts)."""
    rows = []
    for cell in sorted(set(A) & set(B), key=str):
        if len(A[cell]) < min_a or len(B[cell]) < min_b:
            continue
        (ma, sa, na), (mb, sb, nb) = _stats(A[cell]), _stats(B[cell])
        if sa is None or sb is None:
            continue
        drift = drift_sd_prob(model, (ma + mb) / 2)
        bound = k * math.sqrt(drift ** 2 + sa ** 2 + sb ** 2)
        rows.append({"cell": list(cell), "a": ma, "se_a": sa, "n_a": na, "b": mb, "se_b": sb, "n_b": nb,
                     "difference": ma - mb, "drift_sd": drift, "bound": bound, "within": bool(abs(ma - mb) <= bound)})
    return {"cells_checked": len(rows), "mismatches": sum(not r["within"] for r in rows), "cells": rows}


def kernel_consistency(records, F, opts=OPTIONS, battery=True):
    """Choice H as amended (D63). Main check (within this study): the kernels of the five conditions compared with each
    other on shared cells (blind vs the first calls, which use the same W3 blind prompt; live vs pulse-on vs
    post-restoration), each cell with >= H_min_count calls on both sides. Secondary: each condition against the
    development battery (live conditions vs S4 W3 live probes; blind conditions vs S5 W3 blind probes); a mismatch
    there reads "harness or story dependence" (the battery used development stories)."""
    k, nmin = opts["H_bound_sd"], opts["H_min_count"]
    out = {}
    for m in ALL:
        if not any(mm == m and a == "primary" for (mm, _, a) in records):
            continue
        K = kernel_cells(records, F, m)
        res = {"counts": {c: {str(cell): len(v) for cell, v in K[c].items()} for c in CONDITIONS},
               "within_study": {f"{a}_vs_{b}": compare_cells(m, K[a], K[b], nmin, nmin, k) for a, b in WITHIN_PAIRS}}
        res["within_study_mismatches"] = sum(v["mismatches"] for v in res["within_study"].values())
        if battery:
            bat = battery_cells(m)
            res["battery"] = {c: compare_cells(m, K[c], bat[BATTERY_FOR[c]], nmin, opts["H_min_battery_contexts"], k)
                              for c in CONDITIONS}
            res["battery_mismatches"] = sum(v["mismatches"] for v in res["battery"].values())
            res["battery_mismatch_reading"] = "harness or story dependence"
        out[m] = res
    return out


def _kernel_tables(records, F, model):
    """Live and blind kernel tables (mean P(vote reference) by cell) from the model's live and blind main runs."""
    cells = kernel_cells(records, F, model, conditions=("live", "blind"))
    return {c: {cell: float(np.mean(v)) for cell, v in cells[c].items()} for c in cells}


def _p_ref(K, info, i, own, nb_votes, live):
    shown = "".join(nb_votes) if live else ""
    cell, ref = _cell(info, i, own, shown, live)
    tab = K["live"] if live else K["blind"]
    p = tab.get(cell)
    if p is None:                                        # an unseen cell: the type's mean over its seen cells
        same = [v for c, v in tab.items() if c[0] == cell[0] and c[1] == cell[1]] or list(tab.values())
        p = float(np.mean(same))
    return p, ref


def _simulate(K, info, votes, steps, rng, live_after, watch, direction):
    v = list(votes)
    other = {"A": "B", "B": "A"}
    share = []
    for _ in range(steps):
        i = int(rng.integers(N))
        p, ref = _p_ref(K, info, i, v[i], [v[j] for j in info["adj"][i]], live_after)
        v[i] = ref if rng.random() < p else other[ref]
        share.append(sum(v[x] == direction for x in watch) / len(watch))
    return float(np.mean(share))


def self_social_crosscheck(table, records, F, opts=OPTIONS):
    """Item 5 cross-check: from each self-reset cluster's restoration state, simulate W sweeps with the full live
    kernel and with the contact terms off (choice E: blind-board cells); simulated social = full - off, each against
    the unpulsed restoration state with the same random stream."""
    out = {}
    for m in ALL:
        keys = [(mm, j, a) for (mm, j, a), o in table.items() if mm == m and a == "primary" and o.get("self_reset_state")]
        if not keys:
            continue
        K = _kernel_tables(records, F, m)
        sims, meas = [], []
        for k in keys:
            o = table[k]
            s = o["self_reset_state"]
            info = cluster_info(F[k[1]])
            full, off = [], []
            for rep in range(opts["E_sim_reps"]):
                seed = int.from_bytes(hashlib.sha256(f"selfsocial-{m}-{k[1]}-{rep}".encode()).digest()[:8], "big")
                args = (W * N, s["recipients"], s["direction"])
                fp = _simulate(K, info, s["restoration_votes"], args[0], np.random.default_rng(seed), True, args[1], args[2])
                fu = _simulate(K, info, s["unpulsed_restoration_votes"], args[0], np.random.default_rng(seed), True, args[1], args[2])
                op = _simulate(K, info, s["restoration_votes"], args[0], np.random.default_rng(seed), False, args[1], args[2])
                ou = _simulate(K, info, s["unpulsed_restoration_votes"], args[0], np.random.default_rng(seed), False, args[1], args[2])
                full.append(fp - fu); off.append(op - ou)
            sims.append(float(np.mean(full) - np.mean(off)))
            meas.append(o["social"])
        out[m] = {"n_clusters": len(keys), "simulated_social_mean": float(np.mean(sims)),
                  "measured_social_mean": float(np.mean(meas)),
                  "per_cluster": [{"cluster": k[1], "simulated": a, "measured": b} for k, a, b in zip(keys, sims, meas)]}
    return out


# ---------------------------------------------------------------- item 10
def load_predictions(coord: Path):
    sys.path.insert(0, str(ROOT / "osf"))
    import sealed_tables as ST
    _, P = ST.decode("gates/S10/sealed/s10_predictions.json.gz.b64", Path(coord))
    return P


def model_check(table, P, pooled_obs: dict, per_model_obs: dict):
    """pooled_obs[contrast] = observed pooled estimate (the primary's theta); per_model_obs[m][contrast] = theta."""
    out = {"pooled": {}, "per_model": {}, "per_cluster": {}, "widths": {}}
    for k in CONTRASTS:
        v = P["pooled_confirmatory"][k]
        out["pooled"][k] = {"observed": pooled_obs[k], "p05": v["p05"], "p95": v["p95"],
                            "inside_90": bool(v["p05"] <= pooled_obs[k] <= v["p95"]), "width_90": v["p95"] - v["p05"]}
    inside = []
    for m in ALL:
        for k in CONTRASTS:
            v = P["per_model"][m][k]
            obs = per_model_obs[m][k]
            ok = bool(v["p05"] <= obs <= v["p95"])
            inside.append(ok)
            out["per_model"].setdefault(m, {})[k] = {"observed": obs, "p05": v["p05"], "p95": v["p95"], "inside_90": ok,
                                                     "width_90": v["p95"] - v["p05"]}
    out["share_per_model_inside_90"] = float(np.mean(inside))
    cl = [c if isinstance(c, int) else c["cluster"] for c in P["clusters"]]
    for k in CONTRASTS:
        allin, xs_all, ys_all = [], [], []
        for m in ALL:
            mean = P["per_cluster_mean"][m][k]
            lo, hi = P["per_cluster_p05_p95"][m][k]
            xs, ys, ins = [], [], []
            for idx, j in enumerate(cl):
                o = table.get((m, j, "primary"))
                if o is None or o.get(k) is None:
                    continue
                xs.append(mean[idx]); ys.append(o[k]); ins.append(lo[idx] <= o[k] <= hi[idx])
            if len(xs) > 2:
                slope = float(np.polyfit(xs, ys, 1)[0])
                out["per_cluster"].setdefault(m, {})[k] = {"share_inside_90": float(np.mean(ins)), "slope_obs_on_pred": slope,
                                                          "n": len(xs), "mean_width_90": float(np.mean(np.array(hi) - np.array(lo)))}
                allin += ins; xs_all += xs; ys_all += ys
        if len(xs_all) > 2:
            out["per_cluster"].setdefault("all_models", {})[k] = {"share_inside_90": float(np.mean(allin)),
                                                                 "slope_obs_on_pred": float(np.polyfit(xs_all, ys_all, 1)[0])}
    return out


# ---------------------------------------------------------------- item 11 and the full report
def execution(table):
    out = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "missing": 0}))
    for (m, j, a), o in table.items():
        for cond in o["calls"]:
            out[m][cond]["calls"] += o["calls"][cond]
            out[m][cond]["missing"] += o["missing"][cond]
    return {m: dict(v) for m, v in out.items()}


def run_all(records, F, *, primary_result=None, predictions=None, full=True, opts=OPTIONS, simulate=True, battery=True):
    """Every secondary item. primary_result: confirmatory.primary(...) output (for item 3's comparison and item 10)."""
    table = outcome_table(records, F)
    for (m, a) in sorted({(m, a) for (m, _, a) in table}):
        check_arm(table, m, a, F, full=full)
    pm = per_model_estimates(table)
    res = {"options": {k: list(v) if isinstance(v, tuple) else v for k, v in opts.items()},
           "per_model": pm,
           "wording": wording_consistency(table, F, opts),
           "sensitivity": sensitivity(table, {k: primary_result[k]["decision"] for k in CONTRASTS} if primary_result else None, opts),
           "comprehension": comprehension_table(pm),
           "informed_split": informed_split(table),
           "persistence": persistence_secondaries(table, F, records if simulate else None, opts),
           "t1": t1_regime(table),
           "calibration": calibration_generalisation(records, F),
           "social_response": social_response_checks(records, F),
           "rule_ii": rule_ii(table, opts),
           "kernel_consistency": kernel_consistency(records, F, opts, battery=battery),
           "board_final": {"pooled": _summ(pooled(table, CONF, "board_final")),
                           "per_model": {m: _summ(per_model(table, m, "board_final")) for m in ALL}},
           "trajectories": trajectories(table),
           "execution": execution(table)}
    if predictions is not None and primary_result is not None:
        res["model_check"] = model_check(table, predictions,
                                         {k: primary_result[k]["conditional"]["theta"] for k in CONTRASTS},
                                         {m: {k: pm[m][k]["theta"] for k in CONTRASTS} for m in ALL})
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coord", required=True)
    ap.add_argument("--decision", required=True, help="the owner's unblinding decision in the coordination record")
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    runs = json.loads(Path(a.runs).read_text())
    records = load_records(runs, Path(a.coord), a.decision)
    F = frozen_clusters()
    prim_tab = {}
    for (m, j, arm), r in records.items():
        if arm == "primary" and m in CONF:
            prim_tab[(m, j)] = CA.outcomes(r)
    primary_result = CA.primary(prim_tab)
    res = run_all(records, F, primary_result=primary_result, predictions=load_predictions(Path(a.coord)))
    res["primary_conclusions_for_comparison"] = {k: primary_result[k]["decision"] for k in CONTRASTS}
    res["unblinding_decision"] = a.decision
    Path(a.out).write_text(json.dumps(res, indent=1, default=lambda x: x if not isinstance(x, np.generic) else x.item()))
    print(f"written {a.out}")


if __name__ == "__main__":
    main()
