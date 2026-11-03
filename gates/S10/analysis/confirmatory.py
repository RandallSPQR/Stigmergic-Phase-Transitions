"""StPT confirmatory analysis (pre-registered at S10; coordination D2, D14/A16, D20-D21, D24, D26, D28-D31).

Outcomes per (model m, cluster j), from the run records (rows as written by gates/S8/s8_core.py, the harness format):
  board effect  b_mj = Y_live - Y_blind, Y = mean over sweeps 25-30 inclusive (snapshots at the end of sweeps 25..30)
                of the share of ordinary agents voting the correct option (D31). Live and blind share one initial state,
                one run key and one server start (paired; D14).
  persistence   p_mj = mean over the cluster's two pulsed branches of the ITT recipient effect: the share of ALL assigned
                recipients voting the pulse direction, averaged over the 5 sweeps after restoration, pulsed minus
                unpulsed (the unpulsed branch is the live main continuation) (D26).
Pooled estimand (D2, D24): theta = mean over the four confirmatory models of each model's mean effect; with shared
clusters this is the mean over clusters of c_j = mean_m (effect_mj).
Primary model, conditional on the story bank (D29): c_j = theta + u_block(j) + e_j, u ~ N(0, s_b^2) (server-start
block, mandatory under A16), REML; t reference with Satterthwaite df (as lmerTest; a variance component at its boundary
is held fixed). The first validation run used containment df (blocks - 1) and failed criterion B1 by being
conservative; the switch to Satterthwaite was made on synthetic data only, before any confirmatory data.
Generalisation to new stories (D29): c_j = theta + u_block + v_story + e_j, REML; Satterthwaite df.
Tests per contrast: superiority, two-sided, Holm across the two contrasts at family alpha 0.05; equivalence, TOST at
+/-0.03 with alpha 0.05 (90% interval inside the bound). Decision: effect / small effect within bound / equivalence /
inconclusive.

Input checks (independent execution review of cb10726, addendum 1; every failure raises Refused, nothing is dropped):
  #2 a run must have exactly H x N = 3,000 updates (live and blind), with consecutive steps; a rule-(i) record must have
     exactly two pulsed branches, toward A and toward B, each with r = 10 distinct recipients in 0..99 and exactly
     (D + W) x N rows aligned with the main run; every row is well formed and every number in it finite.
     Follow-up (confirmation pass on bb0f12a): every recorded value is recomputed (verify_record): agents, draws and
     letter mappings from the run key; each agent's own vote and displayed contacts from the replayed state (pulse
     displays included); each vote from its logit and u at T, or kept when the call was missing; initial votes from
     the block-balanced placeholders and the informed calls; pulse directions, recipients and altered contacts; a
     start ID for every branch of the arm.
  #3 primary() takes the cluster universe from the frozen, hashed 61-cluster manifest only (no caller metadata); the
     block label of a cluster is built from the server-start IDs recorded in its run records (all branches of a
     (model, cluster) must share one start, and for every model each scheduled block of 4 must be exactly one start); every entry must be the primary arm (model's primary T, W3 for the
     initial call and the updates, rule (i), the frozen parameters, the cluster's run key) and not a mock run; NaN or
     infinite values are refused at every input.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy import optimize, stats

CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
ALL_MODELS = CONF + ["llama-3.1-8b-it"]
BOUND, FAMILY_ALPHA, TOST_ALPHA = 0.03, 0.05, 0.05
N = 100
PRM = {"H": 30, "t0": 5, "D": 3, "W": 5, "r": 10, "k": 3}
ROOT = Path(__file__).resolve().parents[3]
import sys  # noqa: E402
for _p in (str(ROOT), str(ROOT / "gates/S10")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import s10_core as RC  # noqa: E402
from stpt import board as BB  # noqa: E402
MANIFEST_SHA256 = "dcdac6768510baa8b417945abab5206b9bd06a96322392374e174170058c351d"   # osf/FREEZE_MANIFEST.json


class Refused(ValueError):
    """An input that does not conform to the registered protocol."""


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def primary_T(model):
    opt = json.loads((ROOT / "analysis/results/t_options.json").read_text())["options"]["C_per_model_evidence_anchored"]
    return float(opt[model]["T"])


def frozen_universe(root=ROOT):
    """{cluster: {'story', 'scheduled_block'}} for clusters 1..61, from the frozen manifest only."""
    p = Path(root) / "gates/S10/clusters/MANIFEST.json"
    if hashlib.sha256(p.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise Refused("cluster MANIFEST.json does not match its frozen sha256")
    man = json.loads(p.read_text())
    u = {e["cluster"]: {"story": e["scenario_id"].rsplit("-", 1)[0].removeprefix("conf-"), "scheduled_block": e["start_block"]} for e in man["clusters"]}
    if man["n_clusters"] != 61 or sorted(u) != list(range(1, 62)):
        raise Refused("the frozen manifest does not list clusters 1..61")
    return u


# ---------------------------------------------------------------- outcomes from records
def replay(votes0, rows, every=None, watch=None, direction=None):
    v = list(votes0); snaps = []; share = []
    for k, row in enumerate(rows):
        v[row[1]] = row[4]
        if watch is not None:
            share.append(sum(v[i] == direction for i in watch) / len(watch))
        if every and (k + 1) % every == 0:
            snaps.append(list(v))
    return v, snaps, share


def support(v, truth):
    return sum(x == truth for x in v) / len(v)


def _check_rows(rows, first_step, n, what):
    if not isinstance(rows, list) or len(rows) != n:
        raise Refused(f"{what}: {0 if not isinstance(rows, list) else len(rows)} rows, protocol requires exactly {n}")
    for k, r in enumerate(rows):
        if not isinstance(r, list) or len(r) != 9:
            raise Refused(f"{what}: malformed row {k}")
        step, agent, own, shown, vote, lA, u, miss, amap = r
        if step != first_step + k:
            raise Refused(f"{what}: step {step} at row {k} (expected {first_step + k})")
        if not (isinstance(agent, int) and 0 <= agent < N) or own not in ("A", "B") or vote not in ("A", "B"):
            raise Refused(f"{what}: invalid agent or vote at row {k}")
        if not (_finite(u) and 0 <= u < 1) or miss not in (0, 1) or amap not in (0, 1):
            raise Refused(f"{what}: invalid draw or flag at row {k}")
        if (lA is None) != (miss == 1) or (lA is not None and not _finite(lA)):
            raise Refused(f"{what}: non-finite or inconsistent logit at row {k}")


def check_record(res, H=30, t0=5, D=3, W=5, r=10):
    """Review #2: the run has the registered shape; refuse anything else."""
    v0 = res.get("initial_votes")
    if not (isinstance(v0, list) and len(v0) == N and all(v in ("A", "B") for v in v0)):
        raise Refused("initial votes missing or invalid")
    _check_rows(res.get("live"), 0, H * N, "live run")
    _check_rows(res.get("blind"), 0, H * N, "blind run")
    rule = res.get("rule", "i")
    pulses = res.get("pulses") or []
    if rule == "ii":
        if pulses:
            raise Refused("a rule (ii) run has no pulsed branches")
        return
    if rule != "i":
        raise Refused(f"unknown initial-vote rule {rule!r}")
    if len(pulses) != 2:
        raise Refused(f"{len(pulses)} pulsed branches; protocol requires exactly two")
    if sorted(p.get("direction") for p in pulses) != ["A", "B"]:
        raise Refused("the two pulsed branches must point in opposite directions (one toward A, one toward B)")
    for p in pulses:
        rec = p.get("recipients")
        if not (isinstance(rec, list) and len(rec) == r and all(isinstance(i, int) and 0 <= i < N for i in rec)):
            raise Refused(f"pulse {p.get('index')}: recipients must be {r} agent IDs in 0..{N - 1}")
        if len(set(rec)) != len(rec):
            raise Refused(f"pulse {p.get('index')}: duplicate recipient IDs")
        _check_rows(p.get("rows"), t0 * N, (D + W) * N, f"pulse {p.get('index')}")


def check_pairing(res):
    """Refuse a cluster whose live and blind runs are not paired (same initial state, same agents and draws)."""
    if len(res["live"]) != len(res["blind"]):
        raise ValueError("live and blind runs differ in length")
    for a, b in zip(res["live"], res["blind"]):
        if a[0] != b[0] or a[1] != b[1] or a[6] != b[6]:
            raise ValueError("live and blind runs are not paired (agent or draw differs)")


def check_branch(res, t0):
    for p in res["pulses"]:
        for a, b in zip(p["rows"], res["live"][t0:]):
            if a[0] != b[0] or a[1] != b[1] or a[6] != b[6]:
                raise ValueError("pulsed branch does not share the main trajectory's agents and draws")




_PH = {}


def _placeholders(c):
    if c["cluster"] not in _PH:
        _PH.update(RC.block_placeholders([x for x in RC.load_clusters().values() if x["start_block"] == c["start_block"]]))
    return _PH[c["cluster"]]


def _drawn(u, lA, T):
    """The vote the protocol draws (u < sigma(l / T)); None if u is within rounding of the threshold."""
    p = BB.sigmoid(lA / T)
    return None if abs(u - p) < 1e-6 else ("A" if u < p else "B")


def _verify_rows(rows, v, c, T, live, first_step, what, override=None):
    """Recompute every row from the run key and the replayed state (review follow-up): agent, draw, letter mapping,
    own vote before the update, displayed contacts, and the vote (sampled at T, or kept when the call was missing).
    `override(t, viewer, contact)` returns the pulse display or None. Mutates v."""
    rk, adj = c["run_key"], c["adj"]
    for k, r in enumerate(rows):
        t = first_step + k
        step, agent, own, shown, vote, lA, u, miss, amap = r
        if agent != int(BB.unif(rk, "agent", t) * N) or u != BB.unif(rk, "draw", t):
            raise Refused(f"{what}: row {k} agent or draw is not the run key's")
        if amap != int(BB.layout_for(rk, "upd", t, len(adj[agent]))["letter_of_content"]["A"] == "A"):
            raise Refused(f"{what}: row {k} letter mapping is not the run key's")
        if own != v[agent]:
            raise Refused(f"{what}: row {k} own vote {own} does not match the replayed state ({v[agent]})")
        if live:
            exp = "".join((override(t, agent, j) if override else None) or v[j] for j in adj[agent])
        else:
            exp = ""
        if shown != exp:
            raise Refused(f"{what}: row {k} displayed contacts do not match the replayed state")
        if miss == 1:
            if vote != own:
                raise Refused(f"{what}: row {k} is a missing call but the vote changed (the previous vote is kept)")
        else:
            d = _drawn(u, lA, T)
            if d is not None and vote != d:
                raise Refused(f"{what}: row {k} vote {vote} is not the vote drawn from its logit and u at T")
        v[agent] = vote


def verify_record(res, truth=None, H=30, t0=5, D=3, W=5):
    """Review #2 and its follow-up: the run is one arm of one frozen cluster, with the registered shape, and every
    recorded value is the one the protocol produces from the run key, the frozen cluster and the recorded logits.
    Returns the frozen cluster."""
    frozen = RC.load_clusters()
    j = res.get("cluster")
    if j not in frozen:
        raise Refused(f"cluster {j!r} is not one of the 61 frozen clusters")
    c = frozen[j]
    if res.get("run_key") != c["run_key"]:
        raise Refused("run key is not the frozen cluster's")
    if truth is not None and truth != c["truth"]:
        raise Refused("truth differs from the frozen cluster's")
    model, arm = res.get("model"), res.get("arm")
    spec = RC.arm_spec(c, model, arm)
    for k in ("T", "wording", "rule"):
        if res.get(k) != spec[k]:
            raise Refused(f"{k} {res.get(k)!r} is not the arm's ({spec[k]!r})")
    if res.get("init_wording") != "w3" or res.get("prm") != PRM:
        raise Refused("initial wording or run parameters differ from the registered ones")
    check_record(res, H=H, t0=t0, D=D, W=W)
    T, rk = spec["T"], c["run_key"]
    # server starts: one ID for every branch of the arm (D14)
    starts = res.get("server_start_ids")
    names = RC.branch_names(c, model, arm)
    if not isinstance(starts, dict) or sorted(starts) != sorted(names):
        raise Refused(f"server-start IDs must be recorded for exactly the branches {names}")
    ids = set(starts.values())
    if len(ids) != 1 or not all(isinstance(x, str) and x for x in ids):
        raise Refused("the branches of one run were not all in one server start (paired contrasts must be; D14)")
    # initial state
    v0 = res["initial_votes"]
    if spec["rule"] == "ii":
        if res.get("init") != [] or v0 != ["A" if BB.unif(rk, "init-rand", i) < 0.5 else "B" for i in range(N)]:
            raise Refused("rule (ii) initial votes are not the run key's 50/50 start")
    else:
        ph = _placeholders(c)
        informed = {int(pos) for pos, ids_ in c["alloc"]["holders"].items() if ids_}
        if res.get("placeholders") != ph:
            raise Refused("placeholders are not the block-balanced placeholders of the frozen layout")
        init = res.get("init")
        if not isinstance(init, list) or [x[0] for x in init] != list(range(N)):
            raise Refused("initial records missing or out of order")
        for i, (agent, phi, vote, call, lA, miss) in enumerate(init):
            if phi != ph[i] or vote != v0[i] or call != int(i in informed):
                raise Refused(f"initial record {i} does not match the placeholder, the initial vote or the evidence")
            if not call or miss:
                if vote != ph[i] or lA is not None:
                    raise Refused(f"initial vote {i} must be the placeholder (uninformed, or a missing call)")
            else:
                if not _finite(lA):
                    raise Refused(f"initial record {i}: non-finite logit")
                d = _drawn(BB.unif(rk, "init-draw", i), lA, T)
                if d is not None and vote != d:
                    raise Refused(f"initial vote {i} is not the vote drawn from its logit at T")
    # main runs
    _verify_rows(res["live"], list(v0), c, T, True, 0, "live run")
    _verify_rows(res["blind"], list(v0), c, T, False, 0, "blind run")
    if spec["rule"] == "ii":
        if res.get("self_reset") is not None:
            raise Refused("a rule (ii) run has no self-reset branch")
        return c
    # pulsed branches from the live run's saved state at t0
    vt0 = list(v0)
    for r in res["live"][:t0 * N]:
        vt0[r[1]] = r[4]
    dirs = ["A", "B"] if BB.unif(rk, "direction-order") < 0.5 else ["B", "A"]
    adj = c["adj"]
    for d_i, p in enumerate(res["pulses"]):
        rec = BB.perm(N, rk, "recipients", d_i)[:PRM["r"]]
        altered = {str(x): [adj[x][q] for q in BB.perm(len(adj[x]), rk, "pulse", f"pulse{d_i}", x)[:PRM["k"]]] for x in rec}
        if p.get("index") != d_i or p.get("direction") != dirs[d_i] or p.get("recipients") != rec or p.get("altered") != altered \
                or p.get("votes_at_pulse") != vt0:
            raise Refused(f"pulse {d_i}: direction, recipients, altered contacts or saved state are not the protocol's")
        end_on = (t0 + D) * N
        alt = {(int(x), q) for x, qs in altered.items() for q in qs}
        ov = lambda t, viewer, q, _d=dirs[d_i], _a=alt, _e=end_on: _d if (t < _e and (viewer, q) in _a) else None
        vp = list(vt0)
        _verify_rows(p["rows"][:D * N], vp, c, T, True, t0 * N, f"pulse {d_i}", ov)
        restore = list(vp)
        _verify_rows(p["rows"][D * N:], vp, c, T, True, end_on, f"pulse {d_i}")
        sr = res.get("self_reset")
        if spec["self_reset"] and d_i == c["cluster"] % 2:
            if not sr or sr.get("pulse_index") != d_i or sr.get("start_step") != end_on:
                raise Refused("self-reset branch missing or misplaced")
            vs = list(restore)
            changed = sorted(int(x) for x in rec if vs[x] != vt0[x])
            for x in rec:
                vs[x] = vt0[x]
            if sorted(sr.get("recipients_reset", [])) != changed:
                raise Refused("self-reset: recipients reset do not match the replayed state")
            _check_rows(sr.get("rows"), end_on, W * N, "self-reset")
            _verify_rows(sr["rows"], vs, c, T, True, end_on, "self-reset")
    if not spec["self_reset"] and res.get("self_reset") is not None:
        raise Refused("a self-reset branch was recorded but not drawn")
    return c


def outcomes(res, truth=None, t0=5, D=3, W=5, window=(25, 30)):
    """Outcomes of one verified run record (verify_record). The truth is the frozen cluster's; a caller's truth, if
    given, must equal it."""
    c = verify_record(res, truth, t0=t0, D=D, W=W)
    truth = c["truth"]
    check_pairing(res)
    v0 = res["initial_votes"]
    _, sl, _ = replay(v0, res["live"], every=N)
    _, sb, _ = replay(v0, res["blind"], every=N)
    live = [support(v0, truth)] + [support(v, truth) for v in sl]
    blind = [support(v0, truth)] + [support(v, truth) for v in sb]
    lo, hi = window
    out = {"Y_live": float(np.mean(live[lo:hi + 1])), "Y_blind": float(np.mean(blind[lo:hi + 1])),
           "board_final": live[-1] - blind[-1]}
    out["board"] = out["Y_live"] - out["Y_blind"]
    if res.get("pulses"):
        check_branch(res, t0 * N)
        vt0, _, _ = replay(v0, res["live"][:t0 * N])
        itt, imm, exp_ = [], [], []
        for p in res["pulses"]:
            _, _, sp = replay(vt0, p["rows"], watch=p["recipients"], direction=p["direction"])
            _, _, su = replay(vt0, res["live"][t0 * N:(t0 + D + W) * N], watch=p["recipients"], direction=p["direction"])
            d = np.array(sp) - np.array(su)
            itt.append(float(d[D * N:].mean())); imm.append(float(d[:D * N].mean()))
            upd = {row[1] for row in p["rows"][:D * N]}
            ex = [i for i in p["recipients"] if i in upd]
            if ex:
                _, _, ep = replay(vt0, p["rows"], watch=ex, direction=p["direction"])
                _, _, eu = replay(vt0, res["live"][t0 * N:(t0 + D + W) * N], watch=ex, direction=p["direction"])
                exp_.append(float((np.array(ep) - np.array(eu))[D * N:].mean()))
        out.update({"persistence": float(np.mean(itt)), "immediate": float(np.mean(imm)),
                    "persistence_exposed": float(np.mean(exp_)) if exp_ else None})
    out["identity"] = {k: res.get(k) for k in ("model", "cluster", "arm", "T", "wording", "init_wording", "rule", "run_key",
                                               "prm", "mock")}
    out["server_start"] = next(iter(set(res["server_start_ids"].values())))
    return out


# ---------------------------------------------------------------- REML random-intercept model
def reml(y, groups):
    """y: (n,), groups: list of integer label arrays (one per random intercept). Returns theta, se, variance components."""
    y = np.asarray(y, float); n = len(y)
    Zs = []
    for g in groups:
        g = np.asarray(g); lev = {v: k for k, v in enumerate(sorted(set(g.tolist())))}
        Z = np.zeros((n, len(lev)))
        Z[np.arange(n), [lev[v] for v in g.tolist()]] = 1.0
        Zs.append(Z)
    X = np.ones((n, 1))

    def V_of(lp):
        V = math.exp(lp[0]) * np.eye(n)
        for Z, l in zip(Zs, lp[1:]):
            V += math.exp(l) * Z @ Z.T
        return V

    def nll(lp):
        V = V_of(lp)
        try:
            L = np.linalg.cholesky(V)
        except np.linalg.LinAlgError:
            return 1e10
        Vi = np.linalg.inv(V)
        XtViX = (X.T @ Vi @ X).item()
        beta = (X.T @ Vi @ y).item() / XtViX
        r = y - beta
        return 0.5 * (2 * np.log(np.diag(L)).sum() + math.log(XtViX) + float(r @ Vi @ r))

    v0 = max(np.var(y, ddof=1), 1e-8)
    best = None
    for init in ([math.log(v0)] + [math.log(v0 / 4)] * len(Zs), [math.log(v0)] + [math.log(v0 / 100)] * len(Zs)):
        r = optimize.minimize(nll, init, method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 4000})
        if best is None or r.fun < best.fun:
            best = r
    lp = np.clip(best.x, -40, 5)
    V = V_of(lp); Vi = np.linalg.inv(V)
    XtViX = (X.T @ Vi @ X).item()
    theta = (X.T @ Vi @ y).item() / XtViX
    out = {"theta": theta, "se": math.sqrt(1.0 / XtViX), "var_resid": math.exp(lp[0]),
           "var_groups": [math.exp(l) for l in lp[1:]]}
    out["df_satterthwaite"] = _satterthwaite(y, Zs, [math.exp(l) for l in lp])
    return out


def _satterthwaite(y, Zs, var):
    """Satterthwaite df for the intercept (as lmerTest): df = 2 Var(theta)^2 / (g' A g), with g the gradient of
    Var(theta) = (1' V^-1 1)^-1 in the variance parameters and A the inverse of the REML observed information in those
    parameters. A variance component at its boundary (< 1e-8 of the total) is held fixed (dropped from g and A)."""
    n = len(y); one = np.ones(n)
    tot = sum(var)
    free = [k for k, v in enumerate(var) if k == 0 or v > 1e-8 * tot]
    mats = [np.eye(n)] + [Z @ Z.T for Z in Zs]

    def V_of(v):
        return sum(vk * Mk for vk, Mk in zip(v, mats))

    def var_theta(v):
        Vi = np.linalg.inv(V_of(v)); return 1.0 / float(one @ Vi @ one)

    def reml_nll(v):
        V = V_of(v); Vi = np.linalg.inv(V); s, logdet = np.linalg.slogdet(V)
        a = float(one @ Vi @ one); beta = float(one @ Vi @ y) / a; r = y - beta
        return 0.5 * (logdet + math.log(a) + float(r @ Vi @ r))

    h = [max(1e-4 * var[k], 1e-12) for k in range(len(var))]
    g = np.zeros(len(free)); H = np.zeros((len(free), len(free)))
    for a_, k in enumerate(free):
        vp = list(var); vm = list(var); vp[k] += h[k]; vm[k] -= h[k]
        g[a_] = (var_theta(vp) - var_theta(vm)) / (2 * h[k])
        for b_, l in enumerate(free):
            vpp = list(var); vpm = list(var); vmp = list(var); vmm = list(var)
            vpp[k] += h[k]; vpp[l] += h[l]; vpm[k] += h[k]; vpm[l] -= h[l]
            vmp[k] -= h[k]; vmp[l] += h[l]; vmm[k] -= h[k]; vmm[l] -= h[l]
            H[a_, b_] = (reml_nll(vpp) - reml_nll(vpm) - reml_nll(vmp) + reml_nll(vmm)) / (4 * h[k] * h[l])
    try:
        A = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return float(n - 1)
    den = float(g @ A @ g)
    df = 2 * var_theta(var) ** 2 / den if den > 0 else float(n - 1)
    return float(min(max(df, 1.0), n - 1))


def infer(y, blocks, stories=None):
    """Conditional (block RE) or generalisation (block + story RE) inference for one contrast."""
    if not all(_finite(float(v)) for v in y):
        raise Refused("non-finite outcome")
    groups = [blocks] if stories is None else [blocks, stories]
    fit = reml(y, groups)
    df = fit["df_satterthwaite"]       # Satterthwaite (replaces containment df after the first validation run; S10)
    t = fit["theta"] / fit["se"]
    p = 2 * stats.t.sf(abs(t), df)
    tq = stats.t.ppf(1 - TOST_ALPHA, df)
    ci90 = (fit["theta"] - tq * fit["se"], fit["theta"] + tq * fit["se"])
    tq95 = stats.t.ppf(0.975, df)
    return {**fit, "df": df, "t": t, "p_two_sided": p, "ci90": ci90,
            "ci95": (fit["theta"] - tq95 * fit["se"], fit["theta"] + tq95 * fit["se"]),
            "tost_equivalent": bool(ci90[0] > -BOUND and ci90[1] < BOUND)}


def holm(pvals: dict, alpha=FAMILY_ALPHA):
    order = sorted(pvals, key=pvals.get); rej = {}; stop = False
    for k, name in enumerate(order):
        if not stop and pvals[name] <= alpha / (len(order) - k):
            rej[name] = True
        else:
            stop = True; rej[name] = False
    return rej


def decide(sig, eq):
    return {(True, True): "small effect within the equivalence bound", (True, False): "effect",
            (False, True): "equivalence (no effect beyond +/-0.03)", (False, False): "inconclusive"}[(sig, eq)]


def check_table(table, models=CONF, contrasts=("board", "persistence")):
    """Review #3. table[(model, cluster)] = outcomes() dict. Returns (clusters, block labels, stories)."""
    U = frozen_universe()
    want = {(m, j) for m in models for j in U}
    got = set(table)
    if got != want:
        extra, missing = sorted(got - want, key=str), sorted(want - got, key=str)
        raise Refused(f"table must hold exactly the frozen clusters for {list(models)}; extra {extra[:5]}, missing {missing[:5]}")
    T = {m: primary_T(m) for m in models}
    for (m, j), o in table.items():
        idn = o.get("identity") or {}
        exp = {"model": m, "cluster": j, "arm": "primary", "T": T[m], "wording": "w3", "init_wording": "w3", "rule": "i",
               "run_key": f"CONF-c{j}", "prm": PRM}
        bad = {k: idn.get(k) for k, v in exp.items() if idn.get(k) != v}
        if bad:
            raise Refused(f"({m}, cluster {j}) is not the primary arm: {bad}")
        if idn.get("mock"):
            raise Refused(f"({m}, cluster {j}) comes from a mock run")
        if not o.get("server_start"):
            raise Refused(f"({m}, cluster {j}) has no recorded server-start ID")
        for ctr in contrasts:
            if not _finite(o.get(ctr)):
                raise Refused(f"({m}, cluster {j}): {ctr} is missing or not finite")
    clusters = sorted(U)
    for m in models:                       # the registered layout: clusters go to starts in blocks of 4 (D14, §4)
        by_block = {}
        for j in clusters:
            by_block.setdefault(U[j]["scheduled_block"], set()).add(table[(m, j)]["server_start"])
        if any(len(v) != 1 for v in by_block.values()):
            split = {b_: sorted(v) for b_, v in by_block.items() if len(v) != 1}
            raise Refused(f"{m}: a scheduled block of clusters ran in more than one server start: {split}")
        if len({next(iter(v)) for v in by_block.values()}) != len(by_block):
            raise Refused(f"{m}: two scheduled blocks share one server start")
    blocks = ["|".join(str(table[(m, j)]["server_start"]) for m in models) for j in clusters]
    stories = [U[j]["story"] for j in clusters]
    return clusters, blocks, stories


def primary(table, *, generalisation=True):
    """table[(model, cluster)] = outcomes dict for the four confirmatory models x the 61 frozen clusters (primary arm).
    Cluster universe and stories from the frozen manifest; start blocks from the recorded server-start IDs.
    Returns the two confirmatory results (conditional = confirmatory; generalisation reported beside)."""
    clusters, blocks, stories = check_table(table)
    res = {}
    for contrast in ("board", "persistence"):
        c = [float(np.mean([table[(m, j)][contrast] for m in CONF])) for j in clusters]
        res[contrast] = {"conditional": infer(c, blocks), "n_clusters": len(c)}
        if generalisation:
            res[contrast]["generalisation"] = infer(c, blocks, stories)
    rej = holm({k: res[k]["conditional"]["p_two_sided"] for k in res})
    for k in res:
        res[k]["holm_significant"] = rej[k]
        res[k]["decision"] = decide(rej[k], res[k]["conditional"]["tost_equivalent"])
    U = frozen_universe()
    sched = [U[j]["scheduled_block"] for j in clusters]
    res["blocks"] = {"n_recorded_starts": len(set(blocks)),
                     "matches_scheduled_blocks": len({(a, b) for a, b in zip(blocks, sched)}) == len(set(blocks)) == len(set(sched))}
    return res


def subset_estimate(table, models, contrast):
    """Secondary/sensitivity: the same conditional model on the mean over a subset of models (D20, D21, D24); same
    checks as primary() for the models used."""
    sub = {k: v for k, v in table.items() if k[0] in models}
    clusters, blocks, _ = check_table(sub, models=tuple(models), contrasts=(contrast,))
    c = [float(np.mean([sub[(m, j)][contrast] for m in models])) for j in clusters]
    return infer(c, blocks)
