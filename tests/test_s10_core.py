"""The S10 confirmatory runner reproduces the S8 runner (CPU, mock model)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("gates/S7", "gates/S8", "gates/S10"):
    sys.path.insert(0, str(ROOT / p))
import s7_core  # noqa: E402
import s8_core  # noqa: E402
import s10_core  # noqa: E402

CL = json.loads((ROOT / "gates/S8/inputs/clusters.json").read_text())
PRM = {"H": 12, "t0": 5, "D": 3, "W": 2, "r": 10, "k": 3}


def _strip(r):
    return {k: v for k, v in r.items() if k not in ("seconds", "wording", "setting")}


def test_reproduces_s8_runner():
    c = CL[0]
    a = s8_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM)
    b = s10_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM)
    assert json.dumps(_strip(a), sort_keys=True) == json.dumps(_strip(b), sort_keys=True)


def test_self_reset_off_and_rule_ii():
    c = CL[0]
    b = s10_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM, self_reset=False)
    assert b["self_reset"] is None and len(b["pulses"]) == 2
    r2 = s10_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM, rule="ii")
    assert r2["pulses"] == [] and r2["init"] == []


def test_variant_wording_changes_prompts_not_draws():
    c = CL[0]
    a = s10_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM)
    w = s10_core.run_cluster(c, 1.0, s7_core.MockKernel(), PRM, wording="w4")
    assert [r[1] for r in a["live"]] == [r[1] for r in w["live"]] and [r[6] for r in a["live"]] == [r[6] for r in w["live"]]
    assert a["live_sha"] != w["live_sha"]
