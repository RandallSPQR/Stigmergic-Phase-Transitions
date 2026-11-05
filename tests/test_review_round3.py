"""Permanent tests for the reviewer's round 3 on fc0fc0c (addendum 1). CPU only; no GPU, no network.
The reviewer's script (osf/addendum1/reviewer_cases/stpt_final_operational_cases_fc0fc0c.py) reads fc0fc0c's shell layout,
which round 3 restructured; each of its cases is reproduced here against the new code."""
import base64
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S10/run", "gates/S7", "gates/S0/gpu"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as CA  # noqa: E402
import driver as DR  # noqa: E402
import launch  # noqa: E402
import ledger as LG  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402

F = C.load_clusters()
M = "gemma-2-9b-it"
SH = ROOT / "gates/S10/gpu/s10_driver.sh"


# ------------------------------------------------------------------ R3.1 a failed upload never loses the only copy
def _finish(tmp, upload_ok):
    """Run the real finish() of s10_driver.sh with the upload's Python stubbed to fail or succeed."""
    stub = tmp / "py"; stub.write_text(f"#!/bin/sh\ncat > /dev/null\nexit {0 if upload_ok else 1}\n"); stub.chmod(0o755)
    bindir = tmp / "bin"; bindir.mkdir(exist_ok=True)
    for name in ("runpodctl", "curl"):
        b = bindir / name; b.write_text(f"#!/bin/sh\necho {name} \"$@\" >> {tmp}/pod_commands.log\n"); b.chmod(0o755)
    ws = tmp / "ws"; (ws / "out/run1").mkdir(parents=True, exist_ok=True); (ws / "out/run1/rec.json").write_text("{}")
    (ws / "UPLOAD_PENDING").write_text("")
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "STPT_WORKSPACE": str(ws), "STPT_RUN_ID": "run1",
           "STPT_PY": str(stub), "STPT_SRC": str(ROOT), "S10_SOURCE_ONLY": "1", "STPT_MODELS": M}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; sleep() {{ :; }}; finish 0'], env=env, capture_output=True, text=True)
    log = (tmp / "pod_commands.log").read_text().splitlines() if (tmp / "pod_commands.log").exists() else []
    return p.returncode, (ws / "UPLOAD_PENDING").exists(), (ws / "out/run1/DONE").exists(), log, p.stdout


def test_upload_failure_keeps_marker_and_never_deletes(tmp_path):
    rc, marker, done, cmds, out = _finish(tmp_path, upload_ok=False)
    assert rc == 5 and marker and not done and cmds == [], (rc, marker, done, cmds, out)


def test_verified_upload_clears_marker(tmp_path):
    rc, marker, done, cmds, out = _finish(tmp_path, upload_ok=True)
    assert rc == 0 and not marker and done and cmds == [], (rc, marker, done, cmds, out)


def test_upload_function_returns_failure(tmp_path):
    stub = tmp_path / "py"; stub.write_text("#!/bin/sh\ncat > /dev/null\nexit 1\n"); stub.chmod(0o755)
    env = {**os.environ, "STPT_WORKSPACE": str(tmp_path), "STPT_RUN_ID": "r", "STPT_PY": str(stub), "S10_SOURCE_ONLY": "1",
           "STPT_MODELS": M}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; upload; echo "rc=$?"'], env=env, capture_output=True, text=True)
    assert "rc=1" in p.stdout


@pytest.mark.parametrize("keep_marker", [True, False])
def test_launch_data_safe_deletes_only_after_verified_upload(tmp_path, keep_marker):
    bindir = tmp_path / "bin"; bindir.mkdir()
    for name in ("runpodctl", "curl"):
        b = bindir / name; b.write_text(f"#!/bin/sh\necho {name} \"$@\" >> {tmp_path}/pod_commands.log\n"); b.chmod(0o755)
    marker = tmp_path / "UPLOAD_PENDING"; marker.write_text("")
    drv = f"#!/bin/bash\n{'true' if keep_marker else f'rm -f {marker}'}\nexit 0\n"
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "STPT_MARKER": str(marker), "STPT_END_GRACE": "0",
           "RUNPOD_POD_ID": "fake-pod", "RUNPOD_API_KEY": "x", "STPT_DRIVER_B64": base64.b64encode(drv.encode()).decode()}
    cmd = launch.start_cmd_data_safe(1.0).replace("/root/driver.sh", str(tmp_path / "driver.sh"))
    cmd = cmd.replace("> /tmp/selfstop.log", f"> {tmp_path}/selfstop.log")
    p = subprocess.Popen(["bash", "-c", cmd], env=env, start_new_session=True)
    p.wait(timeout=60)
    subprocess.run(["pkill", "-f", f"sleep 3600"], check=False)            # the deadline timer of this test
    log = (tmp_path / "pod_commands.log").read_text()
    if keep_marker:
        assert "stop pod fake-pod" in log and "remove" not in log and "DELETE" not in log, log
    else:
        assert "remove pod fake-pod" in log and "stop pod" not in log, log


# ------------------------------------------------------------------ R3.2 caps cover the whole paid lifecycle
class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_server_start_needs_headroom(tmp_path):
    clk = Clock(); k = s7_core.MockKernel(); stage = f"{M}:core"

    class SlowServer:                                   # the reviewer's double: 1,000 s of startup, no cap check
        def start(self):
            clk.t += 1000; return {"id": "fake/start1/t", "attached": False}

        def stop(self):
            pass
    d = DR.Driver(M, k, SlowServer(), lambda m: {}, {stage: .2}, tmp_path, 3.6, {}, mock=True, clock=clk, ack_flags=(stage,))
    s = d.run(blocks=[1])
    assert "less than one server start" in s and d.ledger.d["spent_usd"][stage] == 0.0 and k.calls == 0


def test_readiness_wait_is_cap_checked(tmp_path):
    clk = Clock(); k = s7_core.MockKernel(); stage = f"{M}:core"

    class SlowServer:                                   # like VLLMServer: check() every 5 s of the readiness wait
        def start(self, check=lambda: None):
            for _ in range(200):
                clk.t += 5; check()
            return {"id": "fake/start1/t", "attached": False}

        def stop(self):
            pass
    d = DR.Driver(M, k, SlowServer(), lambda m: {}, {stage: .5}, tmp_path, 3.6, {}, mock=True, clock=clk, ack_flags=(stage,))
    s = d.run(blocks=[1])
    assert "cap reached" in s and k.calls == 0 and d.ledger.d["spent_usd"][stage] <= 0.5 + 5 * 3.6 / 3600 + 1e-9


def test_pod_start_is_metered_from_its_first_line(tmp_path):
    clk = Clock(); clk.t = 1000.0
    L = LG.Ledger(tmp_path / "ledger.json", {"s": 10}, 3.6, clk, session="pod1")
    L.begin("s", since=400.0)                           # pod script started 600 s ago (install, downloads)
    assert abs(L.spent("s") - 0.6) < 1e-9


def test_time_between_phases_is_charged_within_a_pod_session(tmp_path):
    clk = Clock(); lp = tmp_path / "ledger.json"
    L = LG.Ledger(lp, {"a": 10, "b": 10}, 3.6, clk, session="pod1"); L.begin("a"); clk.t = 100; L.close()
    clk.t = 160                                         # 60 s between the driver's exit and the next download
    L2 = LG.Ledger(lp, {"a": 10, "b": 10}, 3.6, clk, session="pod1"); L2.begin("b")
    assert abs(L2.spent("b") - 0.06) < 1e-9 and abs(L2.spent("a") - 0.1) < 1e-9
    clk.t = 200; L2.close()                             # 40 s more on b, then a clean close
    clk.t = 10000                                       # a later pod (another session) is not charged for the gap
    L3 = LG.Ledger(lp, {"a": 10, "b": 10}, 3.6, clk, session="pod2"); L3.begin("b")
    assert abs(L3.spent("b") - 0.10) < 1e-9


def test_watchdog_stops_a_paid_phase_at_the_cap(tmp_path):
    lp = tmp_path / "ledger.json"
    clk = Clock(); L = LG.Ledger(lp, {"s": 1.0}, 3.6, clk, session="p"); L.begin("s")
    proc = subprocess.Popen(["sleep", "100"], start_new_session=True)  # a download, registered as paid
    (tmp_path / "paid.pids").write_text(f"{proc.pid}\n")
    assert LG.watchdog_once(tmp_path, {"s": 1.0}, 3.6, now=500) is None          # $0.50: under the cap and the flag
    r = LG.watchdog_once(tmp_path, {"s": 1.0}, 3.6, now=1001)                     # $1.001: past the cap
    assert r and "cap reached" in r and (tmp_path / "CAP_STOP").exists()
    proc.wait(timeout=20)
    assert proc.returncode is not None


def test_cumulative_caps_across_pods(tmp_path):
    prior = {"spent_usd": {"s": 7.5}, "flagged": {"s": True}}
    L = LG.Ledger(tmp_path / "ledger.json", {"s": 10}, 3.6, Clock(), session="p2")
    L.seed([("run0", prior)])
    assert L.spent("s") == 7.5 and L.d["flagged"]["s"] and not L.d["acked"].get("s")
    with pytest.raises(LG.Stop):
        L.seed([("run0", prior)])                        # seeding twice is refused


# ------------------------------------------------------------------ R3.3 non-A/B mass is saved and verified
class WithMass(s7_core.MockKernel):
    def __call__(self, msgs):
        return {**super().__call__(msgs), "non_option_mass": .123456789}


@pytest.fixture(scope="module")
def massrec():
    r = C.run_cluster(F[2], M, WithMass())
    r["server_start_ids"] = {n: "s1" for n in C.branch_names(F[2], M, "primary")}
    return r


def test_mass_recorded_for_every_call(massrec):
    rows = massrec["live"] + massrec["blind"] + [x for p in massrec["pulses"] for x in p["rows"]] + massrec["self_reset"]["rows"]
    assert all(r[9] == 0.123456789 for r in rows)
    assert all(x[6] == 0.123456789 for x in massrec["init"] if x[3] == 1) and all(x[6] is None for x in massrec["init"] if x[3] == 0)
    CA.outcomes(massrec)


@pytest.mark.parametrize("case", ["row_mass_missing", "row_mass_out_of_range", "row_mass_nan", "init_mass_missing",
                                  "init_row_short", "row_short"])
def test_mass_tampering_refused(massrec, case):
    r = copy.deepcopy(massrec)
    if case == "row_mass_missing":
        r["live"][100][9] = None
    elif case == "row_mass_out_of_range":
        r["blind"][100][9] = 1.5
    elif case == "row_mass_nan":
        r["pulses"][0]["rows"][5][9] = float("nan")
    elif case == "init_mass_missing":
        i = next(k for k, x in enumerate(r["init"]) if x[3] == 1); r["init"][i][6] = None
    elif case == "init_row_short":
        r["init"][0] = r["init"][0][:6]
    elif case == "row_short":
        r["live"][5] = r["live"][5][:9]
    with pytest.raises(ValueError):
        CA.outcomes(r)


def test_kernel_without_mass_stops_the_run():
    calls = []

    class NoMass(s7_core.MockKernel):
        def __call__(self, msgs):
            calls.append(1); r = super().__call__(msgs); r.pop("non_option_mass"); return r
    with pytest.raises(C.ProtocolError):
        C.run_cluster(F[2], M, NoMass(), {"H": 12, "t0": 5, "D": 3, "W": 2, "r": 10, "k": 3})
    assert len(calls) == 1                               # not retried by the harness
