"""Permanent tests for the reviewer's confirmation pass on bb0f12a (addendum 1, round 2). CPU only, mock model.
The reviewer's own script is kept verbatim in osf/addendum1/reviewer_cases/ and run here; every flag it prints must be
false. Each case is also a direct test below, with further recomputation cases of the same kind."""
import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S10/run", "gates/S7"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as CA  # noqa: E402
import driver as DR  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402
from stpt import board as B  # noqa: E402

F = C.load_clusters()
M = "gemma-2-9b-it"


@pytest.fixture(scope="module")
def rec():
    r = C.run_cluster(F[2], M, s7_core.MockKernel())                       # cluster 2: self-reset drawn
    r["server_start_ids"] = {n: "pod/start1/t" for n in C.branch_names(F[2], M, "primary")}; r["mock"] = False
    return r


def refused(r):
    with pytest.raises(ValueError):
        CA.outcomes(r)


def test_reviewer_script_all_flags_false():
    script = ROOT / "osf/addendum1/reviewer_cases/stpt_reviewer_followup_bb0f12a.py"
    p = subprocess.run([sys.executable, str(script), str(ROOT)], capture_output=True, text=True, timeout=900)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout[p.stdout.index("{"):])
    flags = {k: v for k, v in out.items() if k.endswith("_accepted") or k in
             ("cap_overshot_at_branch_boundary", "resumed_block_split", "unmetered_billable_gap")}
    assert len(flags) == 7 and not any(flags.values()), flags


def test_conforming_record_passes(rec):
    o = CA.outcomes(rec)
    assert o["server_start"] == "pod/start1/t"


def _flip(v):
    return "B" if v == "A" else "A"


@pytest.mark.parametrize("case", [
    "initial_vote_valid_letter_changed", "informed_initial_vote_flipped", "placeholder_changed", "init_call_flag_changed",
    "live_vote_flipped", "blind_vote_flipped", "pulse_vote_flipped", "self_reset_vote_flipped",
    "missing_flag_but_vote_changes", "own_before_changed", "shown_changed", "pulse_display_override_removed",
    "agent_swapped_in_both_runs", "draw_changed_in_both_runs", "letter_mapping_flipped",
    "directions_swapped", "recipients_replaced", "altered_contacts_changed", "votes_at_pulse_changed",
    "self_reset_present_when_not_drawn", "self_reset_removed", "start_ids_only_init", "start_ids_extra_branch",
    "start_ids_two_starts", "run_key_changed", "truth_wrong", "T_changed", "arm_not_drawn"])
def test_recorded_value_tampering_refused(rec, case):
    r = copy.deepcopy(rec)
    informed = next(row[0] for row in r["init"] if row[3] == 1 and row[5] == 0)
    if case == "initial_vote_valid_letter_changed":
        r["initial_votes"][0] = _flip(r["initial_votes"][0])
    elif case == "informed_initial_vote_flipped":
        r["initial_votes"][informed] = _flip(r["initial_votes"][informed]); r["init"][informed][2] = r["initial_votes"][informed]
    elif case == "placeholder_changed":
        r["placeholders"][0] = _flip(r["placeholders"][0]); r["init"][0][1] = r["placeholders"][0]
    elif case == "init_call_flag_changed":
        r["init"][informed][3] = 0
    elif case == "live_vote_flipped":
        r["live"][2499][4] = _flip(r["live"][2499][4])
    elif case == "blind_vote_flipped":
        r["blind"][2999][4] = _flip(r["blind"][2999][4])
    elif case == "pulse_vote_flipped":
        r["pulses"][1]["rows"][700][4] = _flip(r["pulses"][1]["rows"][700][4])
    elif case == "self_reset_vote_flipped":
        r["self_reset"]["rows"][-1][4] = _flip(r["self_reset"]["rows"][-1][4])
    elif case == "missing_flag_but_vote_changes":
        row = r["live"][2499]; row[7], row[5] = 1, None; row[4] = _flip(row[2])
    elif case == "own_before_changed":
        r["live"][1500][2] = _flip(r["live"][1500][2])
    elif case == "shown_changed":
        row = r["live"][1500]; row[3] = "".join(_flip(x) for x in row[3])
    elif case == "pulse_display_override_removed":
        p = r["pulses"][0]; rk = set(p["recipients"])
        k = next(i for i, row in enumerate(p["rows"][:300]) if row[1] in rk)
        row = p["rows"][k]; row[3] = r["live"][500 + k][3] if r["live"][500 + k][1] == row[1] else _flip(row[3][0]) + row[3][1:]
    elif case == "agent_swapped_in_both_runs":
        for run in ("live", "blind"):
            r[run][2000][1] = (r[run][2000][1] + 1) % 100
    elif case == "draw_changed_in_both_runs":
        for run in ("live", "blind"):
            r[run][2000][6] = 0.5
    elif case == "letter_mapping_flipped":
        r["live"][1000][8] = 1 - r["live"][1000][8]
    elif case == "directions_swapped":
        r["pulses"][0]["direction"], r["pulses"][1]["direction"] = r["pulses"][1]["direction"], r["pulses"][0]["direction"]
    elif case == "recipients_replaced":
        p = r["pulses"][0]; p["recipients"][0] = next(i for i in range(100) if i not in p["recipients"])
    elif case == "altered_contacts_changed":
        p = r["pulses"][0]; x = str(p["recipients"][0]); p["altered"][x] = list(reversed(p["altered"][x]))
        if p["altered"][x] == list(reversed(p["altered"][x])):
            p["altered"][x] = p["altered"][x][:2]
    elif case == "votes_at_pulse_changed":
        r["pulses"][0]["votes_at_pulse"][0] = _flip(r["pulses"][0]["votes_at_pulse"][0])
    elif case == "self_reset_present_when_not_drawn":
        r2 = C.run_cluster(F[1], M, s7_core.MockKernel())
        r2["server_start_ids"] = {n: "s" for n in C.branch_names(F[1], M, "primary")}
        r2["self_reset"] = r["self_reset"]; r = r2
    elif case == "self_reset_removed":
        r["self_reset"] = None
    elif case == "start_ids_only_init":
        r["server_start_ids"] = {"init": "pod/start1/t"}
    elif case == "start_ids_extra_branch":
        r["server_start_ids"]["extra"] = "pod/start1/t"
    elif case == "start_ids_two_starts":
        r["server_start_ids"]["blind"] = "pod/start2/t"
    elif case == "run_key_changed":
        r["run_key"] = "CONF-c3"
    elif case == "truth_wrong":
        with pytest.raises(ValueError):
            CA.outcomes(r, _flip(F[2]["truth"]))
        return
    elif case == "T_changed":
        r["T"] = 1.0
    elif case == "arm_not_drawn":
        r["arm"] = "T1"
    refused(r)


def test_stop_escapes_the_retry_handler():
    """A Stop raised inside a model call is not retried by stpt/board.py _call (which catches Exception)."""
    calls = []

    def k(msgs):
        calls.append(1); raise DR.Stop("cap")
    c = F[1]
    b = C.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, 1.0)
    with pytest.raises(DR.Stop):
        B.update(b, B.State(0, ["A"] * 100), k)
    assert len(calls) == 1


def test_cap_stop_bounds_calls(tmp_path):
    class Clock:
        t = 0.0

        def __call__(self):
            return self.t
    clk = Clock()

    class K(s7_core.MockKernel):
        def __call__(self, msgs):
            clk.t += 1.0; return super().__call__(msgs)

    class S:
        n = 0

        def start(self):
            S.n += 1; return {"id": f"cpu/start{S.n}/u", "attached": False}

        def stop(self):
            pass
    k = K(); stage = f"{M}:core"                      # $0.50 covers one server start's headroom ($0.30), then calls
    d = DR.Driver(M, k, S(), lambda m: {}, {stage: 0.5}, tmp_path, 3.6, {}, mock=True, clock=clk, ack_flags=(stage,))
    assert "cap reached" in d.run(blocks=[1])
    assert k.calls <= 500 + DR.CHECK_EVERY and d.ledger.d["spent_usd"][stage] <= 0.5 + DR.CHECK_EVERY / 1000 + 1e-9


def test_unclosed_interval_is_charged(tmp_path):
    class Clock:
        t = 0.0

        def __call__(self):
            return self.t
    clk = Clock(); lp = tmp_path / "ledger.json"
    l1 = DR.Ledger(lp, {"s": 1000}, 3.6, clk); l1.begin("s"); clk.t = 10; l1.charge()
    clk.t = 1010                                                          # driver killed; server billable for 1,000 s
    l2 = DR.Ledger(lp, {"s": 1000}, 3.6, clk); l2.begin("s"); l2.charge()
    assert abs(l2.d["spent_usd"]["s"] - 1.01) < 1e-9 and l2.d["unclosed_gaps"][0]["seconds"] == 1000
    l2.close(); clk.t = 5000                                              # a clean stop closes the interval
    l3 = DR.Ledger(lp, {"s": 1000}, 3.6, clk); l3.begin("s")
    assert abs(l3.d["spent_usd"]["s"] - 1.01) < 1e-9
