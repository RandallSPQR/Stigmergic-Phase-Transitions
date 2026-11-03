"""StPT confirmatory cluster runner (frozen at S10). The S8 runner (gates/S8/s8_core.py) with the frozen protocol's options:
wording (W3 primary; the D21 variants per model), T (D23 primary or the T = 1 secondary regime), the initial-vote rule (D25),
and whether the cluster's saved state gets a self-reset branch (D26 seeded share). With wording "w3", rule "i" and
self_reset=True it reproduces the S8 runner byte for byte (checked in tests/test_s10_core.py).

A rule-(i) cluster: one initial state (rule (i), the blind evidence-only call; shared by live and blind), a live and a
blind main run of H sweeps, and at t0 two pulsed branches from the live run's saved state (one toward A, one toward B,
independent recipient sets; D + W sweeps each), plus a self-reset branch from one pulsed branch at restoration (W
sweeps). The unpulsed branch is the live main continuation (common random numbers; S7). A rule-(ii) cluster: a seeded
50/50 start, live and blind main runs, no pulses.

Rows are compact: [step, agent, own_before, shown ("" on the blind board), vote, content-A logit (None if missing), u,
missing 0/1, letter mapping A-as-A 0/1]. Every run also carries the sha256 of its full harness records.
"""
from __future__ import annotations

import time

try:
    from stpt import board as B
except ImportError:              # on the pod: board.py and prompts.py sit next to this file
    import board as B            # type: ignore


def make_board(spec, alloc, adj, run_key, live, T, wording="w3"):  # noqa: D103
    N = len(adj)
    priv, fav, acc = [None] * N, [None] * N, [None] * N
    for pos, ids in alloc["holders"].items():
        if len(ids) > 1:
            raise ValueError("one report per position")
        if ids:
            it = alloc["items"][ids[0]]
            priv[int(pos)], fav[int(pos)], acc[int(pos)] = it["text"], it["favours"], it["accuracy"]
    return B.Board(run_key=run_key, adj=adj, story=spec["story"], private=priv, favours=fav, accuracy=acc, live=live, T=T,
                   wording=wording)


def compact(rec):
    miss = bool(rec.get("missing"))
    lA = None if miss else round(B.content_logit_A(rec["layout"], rec["logp_A"], rec["logp_B"]), 6)
    return [rec["step"], rec["agent"], rec["own_before"], "".join(rec["shown"]) if rec["shown"] else "", rec["vote"], lA,
            rec["u"], int(miss), int(rec["layout"]["letter_of_content"]["A"] == "A")]


def _run(board, state, kernel, n):
    recs = [B.update(board, state, kernel) for _ in range(n)]
    return [compact(r) for r in recs], B.sha(recs)


def run_cluster(c, T, kernel, prm, wording="w3", rule=None, self_reset=True):
    t_start = time.time()
    N = len(c["adj"])
    rule = rule or c.get("rule", "i")
    live = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, T, wording)
    blind = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, T, wording)
    st0, init = B.initial_state(live, kernel, rule)
    out = {"cluster": c["cluster"], "setting": c.get("setting"), "rule": rule, "run_key": c["run_key"], "T": T, "wording": wording,
           "initial_votes": list(st0.votes),
           "init": [[r["agent"], r["placeholder"], r["vote"], None if r.get("missing") else
                     round(B.content_logit_A(r["layout"], r["logp_A"], r["logp_B"]), 6), int(bool(r.get("missing")))] for r in init],
           "init_sha": B.sha(init)}
    H, t0, D, W = prm["H"] * N, prm["t0"] * N, prm["D"] * N, prm["W"] * N
    sl = B.branch(st0)
    if rule == "i":
        a_rows, a_sha = _run(live, sl, kernel, t0)
        saved = sl.to_json()
        b_rows, b_sha = _run(live, sl, kernel, H - t0)
        out["live"], out["live_sha"] = a_rows + b_rows, B.sha([a_sha, b_sha])
    else:
        out["live"], out["live_sha"] = _run(live, sl, kernel, H)
    out["live_final"] = sl.digest()
    sb = B.branch(st0)
    out["blind"], out["blind_sha"] = _run(blind, sb, kernel, H)
    out["blind_final"] = sb.digest()
    out["pulses"], out["self_reset"] = [], None
    if rule == "i":
        directions = ["A", "B"] if B.unif(c["run_key"], "direction-order") < 0.5 else ["B", "A"]
        sr_index = c["cluster"] % 2                                    # self-reset direction alternates across clusters
        for d_i, direction in enumerate(directions):
            b = B.State.from_json(saved)
            at_pulse = list(b.votes)
            rec = B.perm(N, c["run_key"], "recipients", d_i)[:prm["r"]]
            pr = B.apply_pulse(live, b, rec, prm["k"], direction, D, f"pulse{d_i}")
            on_rows, on_sha = _run(live, b, kernel, D)
            if b.overrides:
                raise AssertionError("displays not restored at the end of the pulse")
            restore = b.to_json()
            off_rows, off_sha = _run(live, b, kernel, W)
            out["pulses"].append({"index": d_i, "direction": direction, "recipients": rec, "altered": pr["altered"],
                                  "t0": t0, "rows": on_rows + off_rows, "sha": B.sha([on_sha, off_sha]),
                                  "votes_at_pulse": at_pulse})
            if self_reset and d_i == sr_index:
                s = B.State.from_json(restore)
                rr = B.self_reset(s, rec, at_pulse)
                sr_rows, sr_sha = _run(live, s, kernel, W)
                out["self_reset"] = {"pulse_index": d_i, "direction": direction, "recipients_reset": rr["recipients_reset"],
                                     "start_step": t0 + D, "rows": sr_rows, "sha": sr_sha}
    out["seconds"] = round(time.time() - t_start, 1)
    return out
