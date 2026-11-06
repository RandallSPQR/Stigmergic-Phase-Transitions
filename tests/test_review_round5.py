"""Permanent tests for the reviewer's round 5 on de1cb9a (addendum 1): the final ledger upload is required, and its
retries are charged. CPU only. The reviewer's script is kept verbatim (osf/addendum1/reviewer_cases/stpt_final_upload_de1cb9a.py)
and run here."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gates/S10/run"))
import ledger as LG  # noqa: E402

M = "gemma-2-9b-it"; STAGE = f"{M}:core"
SH = ROOT / "gates/S10/gpu/s10_driver.sh"


def test_reviewer_script_both_cases():
    p = subprocess.run([sys.executable, str(ROOT / "osf/addendum1/reviewer_cases/stpt_final_upload_de1cb9a.py"), str(ROOT)],
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout)
    f, s = out["final_upload_fails"], out["final_upload_succeeds_on_last_retry"]
    assert f["exit"] == 5 and f["marker_kept"] and not f["remote_ledger_final"]
    assert s["exit"] == 0 and not s["marker_kept"] and s["remote_ledger_final"]
    # charged in advance: six attempts at their hard limit (300 s) plus every backoff sleep
    assert s["final_upload_allowance_s"] >= s["final_upload_retry_sleep_s"] + 6 * 300


def test_final_closes_accumulate_to_the_worst_case():
    clk = SimpleNamespace(t=0.0)
    L = LG.Ledger(Path(os.environ.get("TMPDIR", "/tmp")) / f"l_{time.time_ns()}.json", {STAGE: 100}, 3600.0, lambda: clk.t, session="p")
    L.begin(STAGE); clk.t = 10
    L.close(final=True, allowance=300)                  # attempt 1 charged to t = 310
    clk.t = 20; L.close(final=True, allowance=30)       # it failed at t = 20; the sleep is charged to t = 340
    clk.t = 50; L.close(final=True, allowance=300)      # attempt 2 charged to t = 640
    assert L.d["charged_through"] == 640 and abs(L.spent(STAGE) - 640) < 1e-9 and L.d["final_upload_allowance_s"] == 630
    clk.t = 900; L.close(final=True, allowance=0)       # real time past the allowance is still charged
    assert abs(L.spent(STAGE) - 900) < 1e-9


def test_restarted_pod_charges_only_its_own_time(tmp_path):
    clk = SimpleNamespace(t=0.0)
    L = LG.Ledger(tmp_path / "l.json", {STAGE: 100}, 3600.0, lambda: clk.t, session="p")
    L.begin(STAGE); clk.t = 10; L.close(final=True, allowance=300)          # charged to 310; the pod is then stopped
    clk.t = 10000                                                           # restarted at 9900 (recovery)
    L2 = LG.Ledger(tmp_path / "l.json", {STAGE: 100}, 3600.0, lambda: clk.t, session="p2")
    L2.close(final=True, allowance=300, since=9900)
    assert abs(L2.spent(STAGE) - (310 + 100 + 300)) < 1e-9


def _src(tmp):
    src = tmp / "src"; (src / "gates/S10/run").mkdir(parents=True)
    (src / "gates/S10/run/ledger.py").write_text((ROOT / "gates/S10/run/ledger.py").read_text())
    (src / "gates/S10/run/caps_approved.json").write_text(json.dumps({"status": "APPROVED", "caps_usd": {STAGE: 1e6}, "usd_per_gpu_hour": 3600.0}))
    return src


def test_real_finish_charges_real_retry_time(tmp_path):
    """The real finish() with real sleeps: records upload ok, the final upload fails twice, then succeeds. The ledger it
    uploads covers the wall-clock time up to the end of the successful attempt."""
    ws = tmp_path / "ws"; out = ws / "out/run1"; out.mkdir(parents=True); (ws / "UPLOAD_PENDING").write_text("")
    (out / "ledger.json").write_text(json.dumps({"spent_usd": {STAGE: 0.0}, "flagged": {}, "acked": {}, "open": None,
                                                 "closed": {"at": time.time(), "session": None, "stage": STAGE, "final": False},
                                                 "unclosed_gaps": []}))
    n = tmp_path / "n"; n.write_text("0")
    stub = tmp_path / "py"                              # call 1 (records) ok; calls 2-3 (final) fail; call 4 ok
    stub.write_text(f"#!/bin/bash\ncat > /dev/null\nk=$(( $(cat {n}) + 1 )); echo $k > {n}\n"
                    f"[ $k -eq 2 -o $k -eq 3 ] && exit 1\ncp {out}/ledger.json {tmp_path}/remote.json; date +%s.%N > {tmp_path}/end\nexit 0\n")
    stub.chmod(0o755)
    env = {**os.environ, "STPT_WORKSPACE": str(ws), "STPT_RUN_ID": "run1", "STPT_PY": str(stub), "STPT_SRC": str(_src(tmp_path)),
           "S10_SOURCE_ONLY": "1", "STPT_MODELS": M, "STPT_FINAL_ATTEMPT_S": "2", "STPT_FINAL_BACKOFF": "1 1 1"}
    env.pop("STPT_ACK", None)
    t0 = time.time()
    p = subprocess.run(["bash", "-c", f'source "{SH}"; POD_T0={t0}; finish 0'], env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0 and not (ws / "UPLOAD_PENDING").exists(), p.stdout + p.stderr
    remote = json.loads((tmp_path / "remote.json").read_text()); end = float((tmp_path / "end").read_text())
    assert remote["closed"]["final"] and remote["charged_through"] >= end           # covers the successful attempt's end
    assert remote["final_upload_allowance_s"] == 2 + 1 + 2 + 1 + 2                    # three attempts and two sleeps


def test_upload_attempt_is_time_limited(tmp_path):
    stub = tmp_path / "py"; stub.write_text("#!/bin/sh\ncat > /dev/null\nsleep 30\nexit 0\n"); stub.chmod(0o755)
    env = {**os.environ, "STPT_WORKSPACE": str(tmp_path), "STPT_RUN_ID": "r", "STPT_PY": str(stub), "S10_SOURCE_ONLY": "1",
           "STPT_MODELS": M}
    t = time.time()
    p = subprocess.run(["bash", "-c", f'source "{SH}"; UPLOAD_TIMEOUT=1 upload; echo "rc=$?"'], env=env, capture_output=True, text=True, timeout=60)
    assert "rc=0" not in p.stdout and time.time() - t < 10


def test_ledger_failure_keeps_the_marker(tmp_path):
    """If the ledger cannot be written, the final upload does not proceed and the marker stays (pod kept)."""
    ws = tmp_path / "ws"; (ws / "out/run1").mkdir(parents=True); (ws / "UPLOAD_PENDING").write_text("")
    stub = tmp_path / "py"; stub.write_text("#!/bin/sh\ncat > /dev/null\nexit 0\n"); stub.chmod(0o755)
    env = {**os.environ, "STPT_WORKSPACE": str(ws), "STPT_RUN_ID": "run1", "STPT_PY": str(stub), "STPT_SRC": str(tmp_path / "nowhere"),
           "S10_SOURCE_ONLY": "1", "STPT_MODELS": M}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; sleep() {{ :; }}; finish 0'], env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 5 and (ws / "UPLOAD_PENDING").exists()
