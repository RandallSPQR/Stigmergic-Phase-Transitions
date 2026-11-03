"""Permanent tests for the independent execution review of cb10726 (addendum 1). Every adversarial case must be
refused; the conforming cases must pass. CPU only, mock model."""
import copy
import json
import math
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S10/run", "gates/S7", "gates/S8"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as CA  # noqa: E402
import driver as DR  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402
from stpt import board as B  # noqa: E402

F = C.load_clusters()
SMALL = {"H": 12, "t0": 5, "D": 3, "W": 2, "r": 10, "k": 3}
M = "gemma-2-9b-it"


class Spy(s7_core.MockKernel):
    def __init__(self):
        super().__init__(); self.prompts = []

    def __call__(self, msgs):
        self.prompts.append(msgs[0]["content"]); return super().__call__(msgs)


@pytest.fixture(scope="module")
def full():
    """One full-size primary record (3,000 updates per run), as the driver writes it."""
    c = F[2]                                                              # cluster 2: self-reset drawn
    r = C.run_cluster(c, M, s7_core.MockKernel())
    r["server_start_ids"] = {n: "pod/start1/t" for n in C.branch_names(c, M, "primary")}; r["mock"] = False
    return r, c["truth"]


def refuses(fn, *a, **k):
    with pytest.raises(ValueError):
        fn(*a, **k)


# ------------------------------------------------------------------ #1 initial vote
def test_1_uninformed_first_vote_is_placeholder_without_a_call():
    c = F[5]; k = Spy()
    r = C.run_cluster(c, M, k, SMALL)
    informed = [int(p) for p, ids in c["alloc"]["holders"].items() if ids]
    init = {row[0]: row for row in r["init"]}
    assert sum(row[3] for row in r["init"]) == len(informed)                      # calls only for informed agents
    for i in range(100):
        if i not in informed:
            assert init[i][3] == 0 and r["initial_votes"][i] == r["placeholders"][i]
    assert all("Your current vote" in t for t in k.prompts[:len(informed)])


def test_1_informed_first_vote_sampled_at_T():
    c = F[5]
    w3 = C.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, C.primary_T(M), "w3")
    ph = C.placeholders_for(c, F)
    st, recs = C.initial_state(w3, s7_core.MockKernel(), ph)
    for rec in recs:
        if rec["call"]:
            lA = B.content_logit_A(rec["layout"], rec["logp_A"], rec["logp_B"])
            assert rec["vote"] == ("A" if rec["u"] < B.sigmoid(lA / C.primary_T(M)) else "B")


def test_1_initial_call_refuses_live_or_variant_board():
    c = F[5]; ph = C.placeholders_for(c, F)
    for live, w in ((True, "w3"), (False, "w4")):
        b = C.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], live, 1.0, w)
        refuses(C.initial_state, b, s7_core.MockKernel(), ph)


# ------------------------------------------------------------------ #2 run shape
def test_2_conforming_record_passes(full):
    r, truth = full
    o = CA.outcomes(r, truth)
    assert math.isfinite(o["board"]) and math.isfinite(o["persistence"]) and o["server_start"] == "pod/start1/t"


@pytest.mark.parametrize("case", ["live_short", "blind_short", "both_short", "live_long", "one_pulse", "three_pulses",
                                  "same_direction", "duplicate_recipient", "nine_recipients", "recipient_out_of_range",
                                  "pulse_rows_short", "step_gap", "nan_u", "inf_logit", "nan_logit", "logit_without_flag",
                                  "bad_vote", "agent_out_of_range", "rule_ii_with_pulses", "bad_initial_votes", "no_pulses"])
def test_2_malformed_record_refused(full, case):
    r, truth = full
    b = copy.deepcopy(r)
    if case == "live_short":
        b["live"] = b["live"][:2999]
    elif case == "blind_short":
        b["blind"] = b["blind"][:2999]
    elif case == "both_short":
        b["live"], b["blind"] = b["live"][:2900], b["blind"][:2900]
    elif case == "live_long":
        b["live"] = b["live"] + [b["live"][-1][:]]
    elif case == "one_pulse":
        b["pulses"] = b["pulses"][:1]
    elif case == "three_pulses":
        b["pulses"] = b["pulses"] + [copy.deepcopy(b["pulses"][0])]
    elif case == "same_direction":
        b["pulses"][1]["direction"] = b["pulses"][0]["direction"]
    elif case == "duplicate_recipient":
        b["pulses"][0]["recipients"][1] = b["pulses"][0]["recipients"][0]
    elif case == "nine_recipients":
        b["pulses"][0]["recipients"] = b["pulses"][0]["recipients"][:9]
    elif case == "recipient_out_of_range":
        b["pulses"][0]["recipients"][0] = 100
    elif case == "pulse_rows_short":
        b["pulses"][0]["rows"] = b["pulses"][0]["rows"][:799]
    elif case == "step_gap":
        b["live"][10][0] += 1; b["blind"][10][0] += 1
    elif case == "nan_u":
        b["live"][7][6] = float("nan"); b["blind"][7][6] = float("nan")
    elif case == "inf_logit":
        b["live"][7][5] = float("inf")
    elif case == "nan_logit":
        b["blind"][7][5] = float("nan")
    elif case == "logit_without_flag":
        b["live"][7][5] = None
    elif case == "bad_vote":
        b["live"][7][4] = "C"
    elif case == "agent_out_of_range":
        b["live"][7][1] = 100; b["blind"][7][1] = 100
    elif case == "rule_ii_with_pulses":
        b["rule"] = "ii"
    elif case == "bad_initial_votes":
        b["initial_votes"] = b["initial_votes"][:99]
    elif case == "no_pulses":
        b["pulses"] = []
    refuses(CA.outcomes, b, truth)


def test_2_mixed_server_starts_refused(full):
    r, truth = full
    b = copy.deepcopy(r); b["server_start_ids"]["blind"] = "pod/start2/t"
    refuses(CA.outcomes, b, truth)


# ------------------------------------------------------------------ #3 primary(): universe, blocks, arm identity, NaN
def _table(models=CA.CONF, start=lambda m, j: f"{m}/start{F[j]['start_block']}"):
    t = {}
    for m in models:
        for j in range(1, 62):
            t[(m, j)] = {"identity": {"model": m, "cluster": j, "arm": "primary", "T": CA.primary_T(m), "wording": "w3",
                                      "init_wording": "w3", "rule": "i", "run_key": f"CONF-c{j}", "prm": CA.PRM, "mock": False},
                         "server_start": start(m, j), "board": 0.01 * ((j * 7) % 5 - 2), "persistence": 0.01 * ((j * 3) % 5 - 2)}
    return t


def test_3_conforming_table_passes():
    res = CA.primary(_table(), generalisation=False)
    assert res["board"]["n_clusters"] == 61 and res["blocks"]["n_recorded_starts"] == 16 and res["blocks"]["matches_scheduled_blocks"]


def test_3_caller_metadata_not_accepted():
    meta = {j: {"start_block": 1, "story_key": "x"} for j in range(1, 62)}
    with pytest.raises(TypeError):
        CA.primary(_table(), meta)
    with pytest.raises(TypeError):
        CA.subset_estimate(_table(), meta, CA.CONF, "board")


def test_3_block_labels_come_from_recorded_starts():
    named = CA.primary(_table(start=lambda m, j: f"{m}/pod-x/start{100 - F[j]['start_block']}"), generalisation=False)
    assert named["blocks"]["n_recorded_starts"] == 16 and named["blocks"]["matches_scheduled_blocks"]
    _, blocks, _ = CA.check_table(_table())
    assert len(set(blocks)) == 16


@pytest.mark.parametrize("layout", ["one_start_for_everything", "block_split_1_vs_2to4", "two_blocks_share_a_start"])
def test_3_start_layout_not_matching_scheduled_blocks_refused(layout):
    if layout == "one_start_for_everything":
        st = lambda m, j: f"{m}/single"
    elif layout == "block_split_1_vs_2to4":
        st = lambda m, j: f"{m}/start{F[j]['start_block']}" + ("b" if j in (2, 3, 4) else "")
    else:
        st = lambda m, j: f"{m}/start{min(F[j]['start_block'], 2) if F[j]['start_block'] <= 3 else F[j]['start_block']}"
    refuses(CA.primary, _table(start=st), generalisation=False)


@pytest.mark.parametrize("case", ["extra_cluster", "missing_cluster", "llama_included", "no_start", "arm_T1", "T_one",
                                  "wording_w4", "init_wording_w4", "rule_ii", "run_key", "prm", "mock", "key_mismatch",
                                  "nan_board", "inf_persistence", "missing_contrast", "no_identity"])
def test_3_nonconforming_table_refused(case):
    t = _table()
    e = t[("qwen3.5-9b", 7)]
    if case == "extra_cluster":
        t[("qwen3.5-9b", 62)] = copy.deepcopy(e)
    elif case == "missing_cluster":
        del t[("qwen3.5-9b", 7)]
    elif case == "llama_included":
        t[("llama-3.1-8b-it", 7)] = copy.deepcopy(e)
    elif case == "no_start":
        e["server_start"] = None
    elif case == "arm_T1":
        e["identity"]["arm"] = "T1"
    elif case == "T_one":
        e["identity"]["T"] = 1.0
    elif case == "wording_w4":
        e["identity"]["wording"] = "w4"
    elif case == "init_wording_w4":
        e["identity"]["init_wording"] = "w4"
    elif case == "rule_ii":
        e["identity"]["rule"] = "ii"
    elif case == "run_key":
        e["identity"]["run_key"] = "CONF-c8"
    elif case == "prm":
        e["identity"]["prm"] = {**CA.PRM, "H": 29}
    elif case == "mock":
        e["identity"]["mock"] = True
    elif case == "key_mismatch":
        e["identity"]["cluster"] = 8
    elif case == "nan_board":
        e["board"] = float("nan")
    elif case == "inf_persistence":
        e["persistence"] = float("inf")
    elif case == "missing_contrast":
        del e["persistence"]
    elif case == "no_identity":
        del e["identity"]
    refuses(CA.primary, t, generalisation=False)


def test_3_tampered_manifest_refused(tmp_path):
    (tmp_path / "gates/S10/clusters").mkdir(parents=True)
    src = (ROOT / "gates/S10/clusters/MANIFEST.json").read_text()
    (tmp_path / "gates/S10/clusters/MANIFEST.json").write_text(src.replace('"start_block": 1', '"start_block": 2', 1))
    refuses(CA.frozen_universe, root=tmp_path)
    refuses(C.load_manifest, root=tmp_path)


def test_3_nan_refused_in_inference():
    refuses(CA.infer, [0.1, float("nan"), 0.2, 0.1], [1, 1, 2, 2])


# ------------------------------------------------------------------ #5 placeholders
def test_5_placeholder_balance_within_block_and_cluster():
    for blk in sorted({c["start_block"] for c in F.values()}):
        cs = [c for c in F.values() if c["start_block"] == blk]
        ph = C.block_placeholders(cs)
        tot = {}
        for c in cs:
            for g, mem in C._groups(c).items():
                a = sum(ph[c["cluster"]][i] == "A" for i in mem); b = len(mem) - a
                assert abs(a - b) <= 1
                tot[g] = tot.get(g, 0) + a - b
        assert all(abs(v) <= 1 for v in tot.values()), (blk, tot)


def test_5_placeholders_identical_across_models_arms_and_conditions():
    c = next(x for x in F.values() if x["arms"]["T1"])
    a = C.run_cluster(c, M, s7_core.MockKernel(), SMALL)
    b = C.run_cluster(c, "qwen3.5-27b", s7_core.MockKernel(), SMALL, arm="T1")
    assert a["placeholders"] == b["placeholders"] == C.placeholders_for(c, F)


# ------------------------------------------------------------------ #6 arms
def test_6_arms_follow_drawn_flags():
    for j, c in F.items():
        arms = C.arms_for(c, M)
        assert arms[0] == "primary" and ("T1" in arms) == c["arms"]["T1"] and ("rule_ii" in arms) == c["arms"]["rule_ii"]
        assert [a for a in arms if a.startswith("wording:")] == [f"wording:{w}" for w in c["arms"]["variant_wordings"][M]]


def test_6_self_reset_only_when_drawn_and_only_in_primary():
    on = next(c for c in F.values() if c["arms"]["self_reset_saved_state_0"] and c["arms"]["T1"])
    off = next(c for c in F.values() if not c["arms"]["self_reset_saved_state_0"])
    assert C.run_cluster(on, M, s7_core.MockKernel(), SMALL)["self_reset"] is not None
    assert C.run_cluster(off, M, s7_core.MockKernel(), SMALL)["self_reset"] is None
    assert C.run_cluster(on, M, s7_core.MockKernel(), SMALL, arm="T1")["self_reset"] is None


@pytest.mark.parametrize("arm", ["T1", "rule_ii", "wording:w5", "wording:w6", "bogus"])
def test_6_undrawn_or_invalid_arm_refused(arm):
    c = next(x for x in F.values() if not x["arms"]["T1"] and not x["arms"]["rule_ii"] and not x["arms"]["variant_wordings"][M])
    refuses(C.run_cluster, c, M, s7_core.MockKernel(), SMALL, arm=arm)


def test_6_variant_not_valid_for_model_refused():
    c = next(x for x in F.values() if "w6" in x["arms"]["variant_wordings"]["gemma-3-27b-it"])
    refuses(C.run_cluster, c, M, s7_core.MockKernel(), SMALL, arm="wording:w6")      # w6 is not valid for Gemma-2 (D21)


def test_6_T_is_never_free():
    c = F[1]
    assert C.run_cluster(c, M, s7_core.MockKernel(), SMALL)["T"] == C.primary_T(M)
    with pytest.raises(TypeError):
        C.run_cluster(c, 1.0, s7_core.MockKernel(), SMALL, T=1.0)


# ------------------------------------------------------------------ #7 W3 for the initial call
def test_7_variant_arm_initial_call_uses_w3():
    m = "gemma-3-27b-it"
    c = next(x for x in F.values() if x["arms"]["variant_wordings"][m])
    w = c["arms"]["variant_wordings"][m][0]
    p = C.run_cluster(c, m, s7_core.MockKernel(), SMALL)
    v = C.run_cluster(c, m, s7_core.MockKernel(), SMALL, arm=f"wording:{w}")
    assert v["init_sha"] == p["init_sha"] and v["initial_votes"] == p["initial_votes"] and v["init_wording"] == "w3"
    assert v["wording"] == w and v["live_sha"] != p["live_sha"]


# ------------------------------------------------------------------ #4 driver (fast cases; the full CPU validation is
# gates/S10/run/validate_driver_cpu.py -> gates/S10/results/driver_cpu_validation.json)
class _Server:
    def __init__(self, reuse_ids=False):
        self.i, self.alive, self.reuse = 0, False, reuse_ids

    def start(self):
        import uuid
        if not self.alive:
            self.i += 1; self.alive = True
            self.tag = "x" if self.reuse else uuid.uuid4().hex[:8]
        return {"id": f"cpu/start{self.i}/{self.tag}", "index": self.i, "attached": False}

    def stop(self):
        self.alive = False


def _drv(tmp, caps, env_ok=True, model=M, kernel=None):
    def env(m):
        if not env_ok:
            raise RuntimeError("pipeline not pinned")
        return {}
    return DR.Driver(model, kernel or s7_core.MockKernel(), _Server(), env, caps, tmp, 3.6, {}, mock=True)


def test_4_unknown_model_refused(tmp_path):
    refuses(_drv, tmp_path, {}, model="gpt-x")


def test_4_env_check_failure_stops_before_any_call(tmp_path):
    k = s7_core.MockKernel()
    s = _drv(tmp_path, {f"{M}:core": 1e9}, env_ok=False, kernel=k).run(blocks=[1])
    assert s.startswith("stopped") and k.calls == 0


def test_4_stage_without_cap_refused(tmp_path):
    assert "no cap" in _drv(tmp_path, {}).run(blocks=[1])


def test_4_records_carry_one_start_per_arm_and_T(tmp_path):
    d = _drv(tmp_path, {f"{M}:core": 1e9, f"{M}:secondary": 1e9})
    assert d.run(stages=("core", "secondary"), blocks=[1]) == "complete"
    import gzip
    for p in (tmp_path / M).glob("rec_*.json.gz"):
        r = json.loads(gzip.decompress(p.read_bytes()))["result"]
        assert len(set(r["server_start_ids"].values())) == 1 and r["T"] == (1.0 if r["arm"] == "T1" else C.primary_T(M))
        if r["arm"] == "primary":
            CA.outcomes(r, F[r["cluster"]]["truth"])


def test_4_cap_kill_then_resume_reruns_the_block_in_one_start(tmp_path):
    class Clock:
        t = 0.0

        def __call__(self):
            return self.t
    clk = Clock()

    class K(s7_core.MockKernel):
        def __call__(self, msgs):
            clk.t += 1.0; return super().__call__(msgs)
    caps = {f"{M}:core": 10.0, f"{M}:secondary": 1e9}                    # $1 per 1,000 calls: stops inside cluster 2
    d = DR.Driver(M, K(), _Server(), lambda m: {}, caps, tmp_path, 3.6, {}, mock=True, clock=clk, ack_flags=(f"{M}:core",))
    s1 = d.run(blocks=[1])
    assert "cap reached" in s1 and not list((tmp_path / M).glob("rec_*.json.gz"))          # nothing final mid-block
    d = DR.Driver(M, K(), _Server(), lambda m: {}, {f"{M}:core": 1e9}, tmp_path, 3.6, {}, mock=True, clock=clk)
    d.ledger.d["spent_usd"] = {}                                          # owner raised the cap
    assert d.run(blocks=[1]) == "complete"
    import gzip
    starts = {json.loads(gzip.decompress(p.read_bytes()))["result"]["cluster"]:
              set(json.loads(gzip.decompress(p.read_bytes()))["result"]["server_start_ids"].values()) for p in (tmp_path / M).glob("rec_*.json.gz")}
    assert sorted(starts) == [1, 2, 3, 4] and len(set().union(*starts.values())) == 1
    ev = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    final = [e["record"] for e in ev if e["event"] == "arm_final"]
    assert len(final) == len(set(final)) == 4 and sum(e["event"] == "block_abandoned" for e in ev) == 1


def test_4_reused_start_id_refused(tmp_path):
    caps = {f"{M}:core": 1e9}
    assert DR.Driver(M, s7_core.MockKernel(), _Server(reuse_ids=True), lambda m: {}, caps, tmp_path, 3.6, {}, mock=True).run(blocks=[1]) == "complete"
    s = DR.Driver(M, s7_core.MockKernel(), _Server(reuse_ids=True), lambda m: {}, caps, tmp_path, 3.6, {}, mock=True).run(blocks=[2])
    assert "used before" in s


def test_4_tampered_cluster_refused():
    bad = copy.deepcopy(F[3]); bad["adj"][0] = list(reversed(bad["adj"][0]))
    refuses(C.run_cluster, bad, M, s7_core.MockKernel(), SMALL)
    fake = copy.deepcopy(F[3]); fake["cluster"] = 62
    refuses(C.run_cluster, fake, M, s7_core.MockKernel(), SMALL)


# ------------------------------------------------------------------ freeze verification, addendum mode
def test_verify_freeze_log_check_is_insert_only():
    sys.path.insert(0, str(ROOT / "osf"))
    import verify_freeze as VF
    old = "| D1 | a |\n| D2 | b |\n"
    assert VF.insert_only(old, "| D1 | a |\n| D2 | b |\n| D3 | c |\n")
    assert VF.insert_only(old, "| D1 | a |\n| D1b | x |\n| D2 | b |\n")
    assert not VF.insert_only(old, "| D1 | a, edited |\n| D2 | b |\n")
    assert not VF.insert_only(old, "| D2 | b |\n")
