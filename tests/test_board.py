"""Board harness isolation (CPU, mock model; the full check is gates/S7/run_s7_cpu.py)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gates" / "S7"))
import s7_core as C  # noqa: E402
from stpt import board as B  # noqa: E402

INP = json.loads((ROOT / "gates/S7/inputs/s7_inputs.json").read_text())
PULSE = {"r": 5, "k": 2, "toward": "B", "duration": 10}


def _board(live=True, key="t"):
    return C.make_board(INP["spec"], INP["alloc"], INP["adj"], key, live, 1.0)


def test_probes_and_branches_leave_main_unchanged():
    b = _board()
    base = C.scenario(b, C.MockKernel(), 120)
    full = C.scenario(b, C.MockKernel(), 120, probe_every=7, branches=[30, 80], branch_len=25, pulse=PULSE)
    ck = C.checks(base, full, board=b, kernel=C.MockKernel())
    assert ck["C1_main_identical"] and ck["C2_final_state_identical"]
    assert ck["C3_unpulsed_branch_equals_main_continuation"] and ck["C4_pulse_ok"] and ck["C6_save_restore"]


def test_leak_is_detected():
    b = _board()
    base = C.scenario(b, C.LeakyKernel(), 80)
    full = C.scenario(b, C.LeakyKernel(), 80, probe_every=7)
    assert not C.checks(base, full)["C1_main_identical"]


def test_live_and_blind_share_initial_state_and_draws():
    live = C.scenario(_board(True), C.MockKernel(), 40)
    blind = C.scenario(_board(False), C.MockKernel(), 40)
    ck = C.checks(live, live, blind=blind)
    assert ck["C7_live_blind_initial_identical"] and ck["C7_live_blind_same_agents_and_draws"]


def test_placeholder_balanced_and_letters_balanced():
    b = _board()
    ph = B.placeholder_votes(b)
    groups = {}
    for i in range(b.N):
        groups.setdefault((b.private[i] is not None, b.accuracy[i], b.favours[i]), []).append(ph[i])
    assert all(abs(v.count("A") - v.count("B")) <= 1 for v in groups.values())
    lay = [B.layout_for("k", "upd", t)["letter_of_content"]["A"] for t in range(200)]
    assert lay.count("A") == 100


def test_state_json_round_trip():
    s = B.State(5, ["A", "B"], {"0,1": ["A", 9]})
    assert B.State.from_json(s.to_json()).digest() == s.digest()
