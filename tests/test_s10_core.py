"""The S10 confirmatory runner against the S8 runner (CPU, mock model).

After the execution review (addendum 1) the confirmatory initial state differs from S8's by design: uninformed agents
take their placeholder without a call (#1), placeholders are balanced per start block (#5), the initial call is always
W3 (#7). Everything after the initial state is the S8 machinery unchanged: given S8's initial state, the confirmatory
runner reproduces S8's live, blind, pulsed and self-reset branches byte for byte."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S7", "gates/S8", "gates/S10"):
    sys.path.insert(0, str(ROOT / p))
import s7_core  # noqa: E402
import s8_core  # noqa: E402
import s10_core  # noqa: E402
from stpt import board as B  # noqa: E402

F = s10_core.load_clusters()
PRM = {"H": 12, "t0": 5, "D": 3, "W": 2, "r": 10, "k": 3}
M = "gemma-2-9b-it"


def test_after_the_initial_state_the_runner_is_s8s(monkeypatch):
    c = next(x for x in F.values() if x["arms"]["self_reset_saved_state_0"])
    T = s10_core.primary_T(M)
    s8c = {**copy.deepcopy(c), "rule": "i", "setting": None}
    a = s8_core.run_cluster(s8c, T, s7_core.MockKernel(), PRM)
    def s8_init(board, kernel, ph):
        st, recs = B.initial_state(board, kernel, "i")
        return st, [dict(r, call=True) for r in recs]
    monkeypatch.setattr(s10_core, "initial_state", s8_init)
    b = s10_core.run_cluster(c, M, s7_core.MockKernel(), PRM)
    nine = lambda rows: [r[:9] for r in rows]                 # S8's row format; field 10 is the non-A/B mass (round 3)
    assert a["initial_votes"] == b["initial_votes"]
    for k in ("live_sha", "live_final", "blind_sha", "blind_final"):
        assert a[k] == b[k], k
    for k in ("live", "blind"):
        assert a[k] == nine(b[k]), k
        assert all(r[9] == 0.0 for r in b[k])                 # the mock's mass, recorded for every call
    for pa, pb in zip(a["pulses"], b["pulses"]):
        assert pa["rows"] == nine(pb["rows"]) and {k: v for k, v in pa.items() if k != "rows"} == {k: v for k, v in pb.items() if k != "rows"}
    sa, sb = a["self_reset"], b["self_reset"]
    assert sa["rows"] == nine(sb["rows"]) and {k: v for k, v in sa.items() if k != "rows"} == {k: v for k, v in sb.items() if k != "rows"}


def test_rule_ii_arm():
    c = next(x for x in F.values() if x["arms"]["rule_ii"])
    r2 = s10_core.run_cluster(c, M, s7_core.MockKernel(), PRM, arm="rule_ii")
    assert r2["pulses"] == [] and r2["init"] == [] and r2["self_reset"] is None


def test_variant_wording_changes_prompts_not_draws():
    m = "gemma-3-27b-it"
    c = next(x for x in F.values() if x["arms"]["variant_wordings"][m])
    w = c["arms"]["variant_wordings"][m][0]
    a = s10_core.run_cluster(c, m, s7_core.MockKernel(), PRM)
    v = s10_core.run_cluster(c, m, s7_core.MockKernel(), PRM, arm=f"wording:{w}")
    assert [r[1] for r in a["live"]] == [r[1] for r in v["live"]] and [r[6] for r in a["live"]] == [r[6] for r in v["live"]]
    assert a["live_sha"] != v["live_sha"]
