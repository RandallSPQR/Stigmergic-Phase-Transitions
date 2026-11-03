"""StPT confirmatory cluster runner (S10; revised after the independent execution review of cb10726, addendum 1).

What one call of run_cluster(c, model, kernel, arm=...) does, for one of the 61 frozen confirmatory clusters:
- The ARM is taken from the cluster's drawn flags (c["arms"], gates/S10/draw_clusters.py; review #6). "primary" always
  runs; "T1", "rule_ii" and "wording:<w>" run only if drawn for this cluster (and, for a wording, valid for this model,
  D21); anything else is refused. The self-reset branch runs only in the primary arm and only if the cluster's
  self-reset flag is drawn; run_cluster's own default is no self-reset.
- T is never a free argument: the primary T of the model (D23, analysis/results/t_options.json, option C) or 1.0 in
  the T1 arm.
- INITIAL VOTE, rule (i) (D25; clarification in addendum 1, review #1): an UNINFORMED agent's first vote is its balanced
  placeholder, with no model call. An INFORMED agent's first vote is sampled at T from its blind, evidence-only call
  carrying the placeholder own vote. That call always uses wording W3 (review #7); a variant wording applies to the
  updates only. The init calls' letter mappings are balanced in consecutive pairs over the informed agents (D20).
- PLACEHOLDERS are assigned at the level of the server-start block (review #5): within each block of the frozen
  layout (4 clusters) and each evidence group (uninformed; informed by accuracy x favoured content), the counts of A and
  B placeholders differ by at most 1, and within each cluster and group by at most 1. They depend on the run keys only,
  so they are identical for live and blind, for every arm and for every model.
- Then, unchanged from S8 (gates/S8/s8_core.py): a live and a blind main run of H sweeps from that initial state; in
  rule (i), at t0 two pulsed branches from the live run's saved state (toward A and toward B, independent recipient
  sets; D + W sweeps each), the unpulsed branch being the live main continuation (common random numbers; S7); the
  self-reset branch from one pulsed branch at restoration (W sweeps). Rule (ii): a seeded 50/50 start, live and blind,
  no pulses.

Branches are produced through a checkpoint store (store.get/put) so a driver can checkpoint after every branch and
resume (gates/S10/run/driver.py). With no store, an in-memory store is used and the result is the same.

Rows are compact: [step, agent, own_before, shown ("" on the blind board), vote, content-A logit (None if missing), u,
missing 0/1, letter mapping A-as-A 0/1]. Every run also carries the sha256 of its full harness records.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

try:
    from stpt import board as B
except ImportError:              # on the pod: board.py and prompts.py sit next to this file
    import board as B            # type: ignore

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b", "llama-3.1-8b-it"]
PRM = {"H": 30, "t0": 5, "D": 3, "W": 5, "r": 10, "k": 3}          # D26, D28 (frozen)
VALID_VARIANTS = {"llama-3.1-8b-it": ["w4", "w5"], "gemma-2-9b-it": ["w5"], "qwen3.5-9b": ["w4"],
                  "gemma-3-27b-it": ["w4", "w5", "w6"], "qwen3.5-27b": ["w4", "w5", "w6"]}     # D21 (as draw_clusters.py)
# The frozen cluster layout (osf/FREEZE_MANIFEST.json): MANIFEST.json's sha256 and, inside it, the cluster file's.
MANIFEST_SHA256 = "dcdac6768510baa8b417945abab5206b9bd06a96322392374e174170058c351d"
CLUSTERS_SHA256 = "48a3eb8da9ec0052cef13b43551f3156d4d874133feb32a724c01e95895c42f0"


class Refused(ValueError):
    """A run or input that does not conform to the registered protocol."""


# ---------------------------------------------------------------- frozen inputs
def _sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_manifest(root=ROOT) -> dict:
    p = Path(root) / "gates/S10/clusters/MANIFEST.json"
    if _sha_file(p) != MANIFEST_SHA256:
        raise Refused("cluster MANIFEST.json does not match its frozen sha256")
    man = json.loads(p.read_text())
    if man["confirmatory_clusters_json_sha256"] != CLUSTERS_SHA256 or man["n_clusters"] != 61:
        raise Refused("cluster manifest does not name the frozen 61-cluster file")
    return man


def load_clusters(root=ROOT) -> dict:
    """The 61 frozen clusters, keyed by cluster number, after checking the file and every cluster against the
    manifest (allocation hash, graph fingerprint, start block, scenario)."""
    man = load_manifest(root)
    p = Path(root) / "gates/S10/clusters/confirmatory_clusters.json"
    if _sha_file(p) != CLUSTERS_SHA256:
        raise Refused("confirmatory_clusters.json does not match its frozen sha256")
    cl = {c["cluster"]: c for c in json.loads(p.read_text())}
    ref = {e["cluster"]: e for e in man["clusters"]}
    if sorted(cl) != list(range(1, 62)) or sorted(ref) != list(range(1, 62)):
        raise Refused("the cluster universe is not clusters 1..61")
    for j, c in cl.items():
        e = ref[j]
        if (c["alloc"]["sha256"], c["graph"]["fingerprint"], c["start_block"], c["scenario_id"]) != \
                (e["allocation_sha256"], e["graph_fingerprint"], e["start_block"], e["scenario_id"]):
            raise Refused(f"cluster {j} does not match the frozen manifest")
    return cl


def check_cluster(c, frozen=None) -> dict:
    """Refuse any cluster that is not one of the 61 frozen clusters, byte for byte."""
    frozen = frozen or load_clusters()
    j = c.get("cluster") if isinstance(c, dict) else None
    if j not in frozen or json.dumps(c, sort_keys=True) != json.dumps(frozen[j], sort_keys=True):
        raise Refused(f"cluster {j!r} is not one of the 61 frozen confirmatory clusters (or differs from it)")
    return frozen[j]


def primary_T(model) -> float:
    if model not in MODELS:
        raise Refused(f"unknown model {model!r}")
    opt = json.loads((ROOT / "analysis/results/t_options.json").read_text())["options"]["C_per_model_evidence_anchored"]
    return float(opt[model]["T"])


# ---------------------------------------------------------------- arms (review #6)
def arm_spec(c, model, arm) -> dict:
    """T, wording, rule and self-reset for one arm of one cluster; refuses an arm that was not drawn for it."""
    a = c["arms"]
    if arm == "primary":
        return {"arm": arm, "T": primary_T(model), "wording": "w3", "rule": "i", "self_reset": bool(a["self_reset_saved_state_0"])}
    if arm == "T1":
        if a["T1"] is not True:
            raise Refused(f"cluster {c['cluster']}: T1 arm not drawn")
        return {"arm": arm, "T": 1.0, "wording": "w3", "rule": "i", "self_reset": False}
    if arm == "rule_ii":
        if a["rule_ii"] is not True:
            raise Refused(f"cluster {c['cluster']}: rule (ii) arm not drawn")
        return {"arm": arm, "T": primary_T(model), "wording": "w3", "rule": "ii", "self_reset": False}
    if isinstance(arm, str) and arm.startswith("wording:"):
        w = arm.split(":", 1)[1]
        if w not in VALID_VARIANTS.get(model, []) or w not in a["variant_wordings"].get(model, []):
            raise Refused(f"cluster {c['cluster']}: wording {w} not drawn (or not valid) for {model}")
        return {"arm": arm, "T": primary_T(model), "wording": w, "rule": "i", "self_reset": False}
    raise Refused(f"unknown arm {arm!r}")


def arms_for(c, model) -> list:
    """Every arm drawn for this cluster and model, primary first."""
    a = c["arms"]
    out = ["primary"] + (["T1"] if a["T1"] else []) + (["rule_ii"] if a["rule_ii"] else [])
    return out + [f"wording:{w}" for w in a["variant_wordings"].get(model, []) if w in VALID_VARIANTS.get(model, [])]


# ---------------------------------------------------------------- boards and placeholders (review #5)
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


def _groups(c):
    b = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, 1.0)
    g = {}
    for i in range(b.N):
        g.setdefault((b.private[i] is not None, b.accuracy[i], b.favours[i]), []).append(i)
    return g


def block_placeholders(block_clusters) -> dict:
    """{cluster: placeholder list} for the clusters of one server-start block. Within each evidence group, each cluster
    alternates A/B over a keyed order of its members (balance across graph positions; within-cluster imbalance <= 1);
    the clusters whose group has an odd size take the extra placeholder in alternation (keyed), so the block's
    imbalance per group is <= 1."""
    cs = sorted(block_clusters, key=lambda c: c["cluster"])
    if len({c["start_block"] for c in cs}) != 1:
        raise Refused("block_placeholders needs the clusters of one start block")
    out = {c["cluster"]: [None] * len(c["adj"]) for c in cs}
    groups = {c["cluster"]: _groups(c) for c in cs}
    keys = sorted({k for g in groups.values() for k in g}, key=str)
    blk = cs[0]["start_block"]
    for g in keys:
        odd = [c for c in cs if len(groups[c["cluster"]].get(g, [])) % 2 == 1]
        odd = sorted(odd, key=lambda c: B.unif("CONF-block", blk, "placeholder-odd", str(g), c["cluster"]))
        extra0 = "A" if B.unif("CONF-block", blk, "placeholder-extra", str(g)) < 0.5 else "B"
        extra = {c["cluster"]: (extra0 if k % 2 == 0 else ("B" if extra0 == "A" else "A")) for k, c in enumerate(odd)}
        for c in cs:
            members = groups[c["cluster"]].get(g, [])
            if not members:
                continue
            order = sorted(members, key=lambda i: B.unif(c["run_key"], "placeholder", str(g), i))
            first = extra.get(c["cluster"]) or ("A" if B.unif(c["run_key"], "placeholder-first", str(g)) < 0.5 else "B")
            second = "B" if first == "A" else "A"
            for k, i in enumerate(order):
                out[c["cluster"]][i] = first if k % 2 == 0 else second
    return out


def placeholders_for(c, frozen=None) -> list:
    frozen = frozen or load_clusters()
    return block_placeholders([x for x in frozen.values() if x["start_block"] == c["start_block"]])[c["cluster"]]


# ---------------------------------------------------------------- initial vote (reviews #1, #7)
def initial_state(board_w3, kernel, ph):
    """Rule (i). Uninformed: placeholder, no call. Informed: W3 blind evidence-only call with the placeholder own vote,
    sampled at T. Letter mappings balanced in pairs over the informed agents."""
    if board_w3.wording != "w3" or board_w3.live:
        raise Refused("the rule (i) initial call uses the W3 blind board")
    recs, votes, k = [], [], 0
    for i in range(board_w3.N):
        if board_w3.private[i] is None:
            recs.append({"kind": "init", "agent": i, "placeholder": ph[i], "call": False, "vote": ph[i]})
            votes.append(ph[i]); continue
        layout = B.layout_for(board_w3.run_key, "init-informed", k); k += 1
        msgs, r = B._call(board_w3, kernel, i, ph[i], [], layout, "vote", live=False)
        u = B.unif(board_w3.run_key, "init-draw", i)
        if r is None:
            v = ph[i]
            recs.append({"kind": "init", "agent": i, "placeholder": ph[i], "call": True, "prompt_sha": B.sha(msgs),
                         "layout": layout, "logp_A": None, "logp_B": None, "u": u, "vote": v, "missing": True})
        else:
            lA = B.content_logit_A(layout, r["logp_A"], r["logp_B"])
            v = "A" if u < B.sigmoid(lA / board_w3.T) else "B"
            recs.append({"kind": "init", "agent": i, "placeholder": ph[i], "call": True, "prompt_sha": B.sha(msgs),
                         "layout": layout, "logp_A": r["logp_A"], "logp_B": r["logp_B"], "u": u, "vote": v})
        votes.append(v)
    return B.State(0, votes), recs


def initial_state_rule_ii(board):
    return B.State(0, ["A" if B.unif(board.run_key, "init-rand", i) < 0.5 else "B" for i in range(board.N)]), []


# ---------------------------------------------------------------- runs
def compact(rec):
    miss = bool(rec.get("missing"))
    lA = None if miss else round(B.content_logit_A(rec["layout"], rec["logp_A"], rec["logp_B"]), 6)
    return [rec["step"], rec["agent"], rec["own_before"], "".join(rec["shown"]) if rec["shown"] else "", rec["vote"], lA,
            rec["u"], int(miss), int(rec["layout"]["letter_of_content"]["A"] == "A")]


def _run(board, state, kernel, n):
    recs = [B.update(board, state, kernel) for _ in range(n)]
    return [compact(r) for r in recs], B.sha(recs)


class MemoryStore:
    """Checkpoint store interface: get(name) -> dict or None; put(name, dict). Branch outputs are plain JSON."""

    def __init__(self):
        self.d = {}

    def get(self, name):
        return self.d.get(name)

    def put(self, name, obj):
        self.d[name] = json.loads(json.dumps(obj))


def run_cluster(c, model, kernel, prm=None, arm="primary", store=None, frozen=None):
    """One arm of one frozen cluster for one model (see the module docstring). prm defaults to the frozen PRM; a
    smaller prm is for tests only (the driver always uses PRM and the analysis refuses anything else)."""
    t_start = time.time()
    frozen = frozen or load_clusters()
    c = check_cluster(c, frozen)
    spec = arm_spec(c, model, arm)
    prm = prm or PRM
    store = store or MemoryStore()
    T, wording, rule = spec["T"], spec["wording"], spec["rule"]
    N = len(c["adj"])
    live = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, T, wording)
    blind = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, T, wording)
    out = {"cluster": c["cluster"], "model": model, "arm": arm, "rule": rule, "run_key": c["run_key"], "T": T,
           "wording": wording, "init_wording": "w3", "self_reset_drawn": spec["self_reset"], "prm": prm}

    # branch 1: initial state
    ini = store.get("init")
    if ini is None:
        if rule == "i":
            ph = placeholders_for(c, frozen)
            w3 = make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, T, "w3")
            st0, init = initial_state(w3, kernel, ph)
            ini = {"initial_votes": list(st0.votes), "placeholders": ph,
                   "init": [[r["agent"], r["placeholder"], r["vote"], int(r["call"]),
                             None if (not r["call"] or r.get("missing")) else round(B.content_logit_A(r["layout"], r["logp_A"], r["logp_B"]), 6),
                             int(bool(r.get("missing")))] for r in init],
                   "init_sha": B.sha(init)}
        else:
            st0, _ = initial_state_rule_ii(live)
            ini = {"initial_votes": list(st0.votes), "placeholders": None, "init": [], "init_sha": B.sha([])}
        store.put("init", ini)
    out.update(ini)
    st0 = B.State(0, list(ini["initial_votes"]))
    H, t0, D, W = prm["H"] * N, prm["t0"] * N, prm["D"] * N, prm["W"] * N

    # branch 2: live main run (saved state at t0 in rule (i))
    lv = store.get("live")
    if lv is None:
        sl = B.branch(st0)
        if rule == "i":
            a_rows, a_sha = _run(live, sl, kernel, t0)
            saved = sl.to_json()
            b_rows, b_sha = _run(live, sl, kernel, H - t0)
            lv = {"live": a_rows + b_rows, "live_sha": B.sha([a_sha, b_sha]), "saved_t0": saved, "live_final": sl.digest()}
        else:
            rows, s = _run(live, sl, kernel, H)
            lv = {"live": rows, "live_sha": s, "saved_t0": None, "live_final": sl.digest()}
        store.put("live", lv)
    out.update({k: lv[k] for k in ("live", "live_sha", "live_final")})

    # branch 3: blind main run
    bl = store.get("blind")
    if bl is None:
        sb = B.branch(st0)
        rows, s = _run(blind, sb, kernel, H)
        bl = {"blind": rows, "blind_sha": s, "blind_final": sb.digest()}
        store.put("blind", bl)
    out.update(bl)

    # branches 4-6: two pulsed branches, and the self-reset branch if drawn
    out["pulses"], out["self_reset"] = [], None
    if rule == "i":
        directions = ["A", "B"] if B.unif(c["run_key"], "direction-order") < 0.5 else ["B", "A"]
        sr_index = c["cluster"] % 2                                    # self-reset direction alternates across clusters
        for d_i, direction in enumerate(directions):
            p = store.get(f"pulse{d_i}")
            if p is None:
                b = B.State.from_json(lv["saved_t0"])
                at_pulse = list(b.votes)
                rec = B.perm(N, c["run_key"], "recipients", d_i)[:prm["r"]]
                pr = B.apply_pulse(live, b, rec, prm["k"], direction, D, f"pulse{d_i}")
                on_rows, on_sha = _run(live, b, kernel, D)
                if b.overrides:
                    raise AssertionError("displays not restored at the end of the pulse")
                restore = b.to_json()
                off_rows, off_sha = _run(live, b, kernel, W)
                p = {"index": d_i, "direction": direction, "recipients": rec, "altered": pr["altered"], "t0": t0,
                     "rows": on_rows + off_rows, "sha": B.sha([on_sha, off_sha]), "votes_at_pulse": at_pulse,
                     "restore_state": restore}
                store.put(f"pulse{d_i}", p)
            out["pulses"].append({k: v for k, v in p.items() if k != "restore_state"})
            if spec["self_reset"] and d_i == sr_index:
                s_ = store.get("self_reset")
                if s_ is None:
                    s = B.State.from_json(p["restore_state"])
                    rr = B.self_reset(s, p["recipients"], p["votes_at_pulse"])
                    sr_rows, sr_sha = _run(live, s, kernel, W)
                    s_ = {"pulse_index": d_i, "direction": direction, "recipients_reset": rr["recipients_reset"],
                          "start_step": t0 + D, "rows": sr_rows, "sha": sr_sha}
                    store.put("self_reset", s_)
                out["self_reset"] = s_
    out["seconds"] = round(time.time() - t_start, 1)
    return out


def branch_names(c, model, arm) -> list:
    """The checkpointed branches of one arm, in order."""
    s = arm_spec(c, model, arm)
    names = ["init", "live", "blind"]
    if s["rule"] == "i":
        names += ["pulse0", "self_reset", "pulse1"] if (s["self_reset"] and c["cluster"] % 2 == 0) else \
                 ["pulse0", "pulse1", "self_reset"] if s["self_reset"] else ["pulse0", "pulse1"]
    return names
