"""Gate S7 core (gates/S7/S7_PLAN.md): branch isolation. Shared by the CPU check (mock model) and the pod (real model).

A scenario run = initial state (rule i or ii) + H main updates, optionally with probes every `probe_every` steps and,
at steps in `branches`, a pulsed and an unpulsed branch of `branch_len` updates each, run before the main trajectory
continues (so their model calls interleave with the main calls on the same server). The checks compare the main
records byte for byte across runs, and the unpulsed branch against the main continuation.
"""
from __future__ import annotations

import json
import math

try:
    from stpt import board as B
except ImportError:              # on the pod: board.py and prompts.py sit next to this file
    import board as B            # type: ignore


class MockKernel:
    """Deterministic stand-in for a model (CPU check only): the A/B logit is a fixed function of the prompt text, with
    some dependence on the own vote and the contacts' letters so that trajectories move."""

    def __init__(self):
        self.calls = 0

    def __call__(self, msgs):
        self.calls += 1
        t = msgs[0]["content"]
        own = t.split("Your current vote: ")[1][0] if "Your current vote: " in t else None
        cont = t.split("connected to: ")[1].split("\n")[0].split(", ") if "connected to: " in t else []
        l = (0.8 if own == "A" else -0.8 if own == "B" else 0.0) + 0.5 * (cont.count("A") - cont.count("B")) + (2 * B.unif("mock", t) - 1)
        sp = lambda z: math.log1p(math.exp(-abs(z))) + max(z, 0.0)
        return {"logp_A": -sp(-l), "logp_B": -sp(l), "non_option_mass": 0.0}


class LeakyKernel(MockKernel):
    """Negative control: the output drifts with the number of calls served (a stand-in for server state carried
    between calls). The checks must detect it."""

    def __call__(self, msgs):
        r = super().__call__(msgs)
        return {**r, "logp_A": r["logp_A"] - 1e-3 * self.calls}


def make_board(spec, alloc, adj, run_key, live, T, wording="w3"):
    N = len(adj)
    priv, fav, acc = [None] * N, [None] * N, [None] * N
    for pos, ids in alloc["holders"].items():
        if len(ids) > 1:
            raise ValueError("the board shows one report per agent; use an allocation with one report per position")
        if ids:
            it = alloc["items"][ids[0]]
            priv[int(pos)], fav[int(pos)], acc[int(pos)] = it["text"], it["favours"], it["accuracy"]
    return B.Board(run_key=run_key, adj=adj, story=spec["story"], private=priv, favours=fav, accuracy=acc, live=live, T=T,
                   wording=wording)


def scenario(board, kernel, H, init_rule="i", probe_every=None, branches=(), branch_len=0, pulse=None):
    state, init = B.initial_state(board, kernel, init_rule)
    main, side, saved = list(init), [], {}
    for t in range(H):
        if probe_every and t > 0 and t % probe_every == 0:
            ag = int(B.unif(board.run_key, "probe-agent", t) * board.N)
            side.append(B.probe(board, state, kernel, ag, "own_vote", f"p{t}"))
        if t in branches:
            saved[t] = state.to_json()
            for pulsed in (True, False):
                b = B.branch(state)
                pr = None
                if pulsed:
                    rec = B.perm(board.N, board.run_key, "recipients", t)[:pulse["r"]]
                    pr = B.apply_pulse(board, b, rec, pulse["k"], pulse["toward"], pulse["duration"], f"b{t}")
                    pairs = [(int(r), j) for r, js in pr["altered"].items() for j in js]
                    pr["shown_altered_at_start"] = all(B.displayed(b, r, j) == pulse["toward"] for r, j in pairs)
                    pr["others_unaltered_at_start"] = all(B.displayed(b, v, j) == b.votes[j] for v in range(board.N)
                                                          for j in board.adj[v] if (v, j) not in pairs)
                recs = [B.update(board, b, kernel) for _ in range(branch_len)]
                if pulsed:
                    pr["shown_real_after_end"] = all(B.displayed(b, r, j) == b.votes[j] for r, j in pairs) if branch_len >= pulse["duration"] else None
                side.append({"kind": "branch", "t0": t, "pulsed": pulsed, "pulse": pr, "records": recs,
                             "records_sha": B.sha(recs), "final": b.digest(), "overrides_left": len(b.overrides)})
        main.append(B.update(board, state, kernel))
    return {"main": main, "main_sha": B.sha(main), "final": state.digest(), "side": side, "saved": saved}


def checks(base, full, others=(), blind=None, board=None, kernel=None):
    """base: main only; full: with probes and branches; others: further variants (probes only, branches only)."""
    out = {}
    out["C1_main_identical"] = all(x["main_sha"] == base["main_sha"] for x in (full, *others))
    out["C2_final_state_identical"] = all(x["final"] == base["final"] for x in (full, *others))
    upd = {r["step"]: r for r in base["main"] if r["kind"] == "update"}
    c3, c4, c6 = [], [], []
    for br in full["side"]:
        if br["kind"] != "branch":
            continue
        t0, recs = br["t0"], br["records"]
        if not br["pulsed"]:
            c3.append(all(B.sha(r) == B.sha(upd[r["step"]]) for r in recs))
        else:
            unp = next(x for x in full["side"] if x["kind"] == "branch" and x["t0"] == t0 and not x["pulsed"])
            differs = sum(a["shown"] != b["shown"] for a, b in zip(recs, unp["records"]))
            c4.append({"t0": t0, "records_with_altered_display": differs, "overrides_left_at_end": br["overrides_left"],
                       "shown_altered_at_start": br["pulse"]["shown_altered_at_start"],
                       "others_unaltered_at_start": br["pulse"]["others_unaltered_at_start"],
                       "restored": br["overrides_left"] == 0 and br["pulse"]["shown_real_after_end"] is not False,
                       "same_agents_and_draws": all(a["agent"] == b["agent"] and a["u"] == b["u"] for a, b in zip(recs, unp["records"]))})
        if board is not None and kernel is not None and not br["pulsed"]:
            st = B.State.from_json(full["saved"][t0])            # save / restore through JSON
            again = [B.update(board, st, kernel) for _ in range(len(recs))]
            c6.append(B.sha(again) == B.sha(recs))
    out["C3_unpulsed_branch_equals_main_continuation"] = bool(c3) and all(c3)
    out["C4_pulse"] = c4
    out["C4_pulse_ok"] = bool(c4) and all(x["restored"] and x["shown_altered_at_start"] and x["others_unaltered_at_start"]
                                          and x["same_agents_and_draws"] for x in c4)
    if c6:
        out["C6_save_restore"] = all(c6)
    probes = [x for x in full["side"] if x["kind"] == "probe"]
    out["C5_probes_run"] = len(probes)
    if blind is not None:
        li = [r for r in base["main"] if r["kind"] == "init"]
        bi = [r for r in blind["main"] if r["kind"] == "init"]
        out["C7_live_blind_initial_identical"] = B.sha(li) == B.sha(bi)
        lu = [r for r in base["main"] if r["kind"] == "update"]
        bu = [r for r in blind["main"] if r["kind"] == "update"]
        out["C7_live_blind_same_agents_and_draws"] = all(a["agent"] == b["agent"] and a["u"] == b["u"] for a, b in zip(lu, bu))
    lay = [r["layout"]["letter_of_content"]["A"] for r in base["main"] if r["kind"] == "update"]
    out["C9_letter_mapping_A_as_A_share"] = sum(x == "A" for x in lay) / len(lay)
    return out
