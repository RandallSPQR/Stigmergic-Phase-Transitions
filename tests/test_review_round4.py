"""Permanent tests for the reviewer's round 4 on 0778869 (addendum 1). CPU only; no GPU, no network.
The reviewer's script is kept verbatim (osf/addendum1/reviewer_cases/stpt_launch_path_cases_0778869.py) and run here."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/run", "gates/S7"):
    sys.path.insert(0, str(ROOT / p))
import ledger as LG  # noqa: E402
import pod  # noqa: E402
import s10_core as C  # noqa: E402
from stpt import board as B  # noqa: E402

M = "gemma-2-9b-it"; STAGE = f"{M}:core"
SH = ROOT / "gates/S10/gpu/s10_driver.sh"
LEDGER = [sys.executable, str(ROOT / "gates/S10/run/ledger.py")]


def test_reviewer_script_all_three_fixed():
    p = subprocess.run([sys.executable, str(ROOT / "osf/addendum1/reviewer_cases/stpt_launch_path_cases_0778869.py"), str(ROOT)],
                       capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout[p.stdout.index("{"):])
    assert out["acknowledged_new_pod_resume"]["open_rc"] == 0
    assert abs(out["final_upload_gap"]["recorded_usd"] - 1.1) < 1e-9 and out["final_upload_gap"]["watchdog_stop"]
    assert out["actual_adapter_missing_mass"] == {**out["actual_adapter_missing_mass"], "stopped": True, "attempts": 1}


# ------------------------------------------------------------------ R4.1 acknowledgements reach every check
def _cli(tmp, env_extra, *args):
    caps = tmp / "caps.json"
    caps.write_text(json.dumps({"status": "APPROVED", "caps_usd": {STAGE: 10.0}, "usd_per_gpu_hour": 3.6}))
    env = {**os.environ, "STPT_POD_SESSION": "p", "USD_PER_GPU_HOUR": "3.6", **env_extra}
    env.pop("STPT_ACK", None) if "STPT_ACK" not in env_extra else None
    return subprocess.run(LEDGER + [args[0], "--out", str(tmp), "--caps", str(caps), *args[1:]], env=env, capture_output=True, text=True)


def _seeded(tmp):
    prior = tmp / "prior.json"; prior.write_text(json.dumps({"spent_usd": {STAGE: 8.1}, "flagged": {STAGE: True}, "acked": {}}))
    assert _cli(tmp, {}, "seed", "--prior", str(prior)).returncode == 0


def test_flag_without_ack_still_stops(tmp_path):
    _seeded(tmp_path)
    r = _cli(tmp_path, {}, "open", "--stage", STAGE)
    assert r.returncode == 3 and "awaiting acknowledgement" in r.stdout


def test_ack_lets_a_new_pod_resume(tmp_path):
    _seeded(tmp_path)
    r = _cli(tmp_path, {"STPT_ACK": STAGE}, "open", "--stage", STAGE)
    assert r.returncode == 0 and json.loads((tmp_path / "ledger.json").read_text())["acked"] == {STAGE: True}


def test_ack_for_an_unknown_stage_is_refused(tmp_path):
    _seeded(tmp_path)
    r = _cli(tmp_path, {"STPT_ACK": "gemma-2-9b-it:cor"}, "open", "--stage", STAGE)
    assert r.returncode == 3 and "without a cap" in r.stdout


def test_watchdog_honours_ack(tmp_path, monkeypatch):
    clk = SimpleNamespace(t=0.0)
    L = LG.Ledger(tmp_path / "ledger.json", {STAGE: 10.0}, 3.6, lambda: clk.t, session="p"); L.begin(STAGE)
    monkeypatch.delenv("STPT_ACK", raising=False)
    assert LG.watchdog_once(tmp_path, {STAGE: 10.0}, 3.6, now=8500) and "80%" in LG.stop_file(tmp_path, STAGE).read_text()
    LG.stop_file(tmp_path, STAGE).unlink()
    monkeypatch.setenv("STPT_ACK", STAGE)
    assert LG.watchdog_once(tmp_path, {STAGE: 10.0}, 3.6, now=8500) is None
    assert LG.watchdog_once(tmp_path, {STAGE: 10.0}, 3.6, now=10001)                # the cap itself still stops


# ------------------------------------------------------------------ R4.2 final upload time is metered and capped
def test_driver_close_is_not_the_end_of_billing(tmp_path):
    clk = SimpleNamespace(t=0.0)
    L = LG.Ledger(tmp_path / "ledger.json", {STAGE: 0.2}, 3.6, lambda: clk.t, session="p")
    L.begin(STAGE); clk.t = 100; L.close()                                          # the driver exits
    assert LG.watchdog_once(tmp_path, {STAGE: 0.2}, 3.6, now=1100)                  # uploads run past the cap
    clk.t = 1100
    L2 = LG.Ledger(tmp_path / "ledger.json", {STAGE: 0.2}, 3.6, lambda: clk.t, session="p"); L2.close(final=True)
    assert abs(L2.spent(STAGE) - 1.1) < 1e-9
    clk.t = 5000                                                                    # after the final close: nothing
    L3 = LG.Ledger(tmp_path / "ledger.json", {STAGE: 0.2}, 3.6, lambda: clk.t, session="p"); L3.close(final=True)
    assert abs(L3.spent(STAGE) - 1.1) < 1e-9 and LG.watchdog_once(tmp_path, {STAGE: 0.2}, 3.6, now=6000) is None


def test_pod_finish_meters_its_uploads(tmp_path):
    """The real finish(): the ledger is reopened before the uploads, and closed as final after them."""
    ws = tmp_path / "ws"; out = ws / "out/run1"; out.mkdir(parents=True); (ws / "UPLOAD_PENDING").write_text("")
    src = tmp_path / "src"; (src / "gates/S10/run").mkdir(parents=True)
    (src / "gates/S10/run/ledger.py").write_text((ROOT / "gates/S10/run/ledger.py").read_text())
    (src / "gates/S10/run/caps_approved.json").write_text(json.dumps({"status": "APPROVED", "caps_usd": {STAGE: 100.0}, "usd_per_gpu_hour": 3600.0}))
    t0 = time.time() - 2.0                                                          # the driver closed 2 s ago
    (out / "ledger.json").write_text(json.dumps({"spent_usd": {STAGE: 0.0}, "flagged": {}, "acked": {}, "open": None,
                                                 "closed": {"at": t0, "session": None, "stage": STAGE, "final": False},
                                                 "unclosed_gaps": []}))
    stub = tmp_path / "py"                                                          # the upload: record the ledger it saw
    stub.write_text(f"#!/bin/sh\ncat > /dev/null\ncp {out}/ledger.json {tmp_path}/seen_$$.json\nsleep 1\nexit 0\n"); stub.chmod(0o755)
    env = {**os.environ, "STPT_WORKSPACE": str(ws), "STPT_RUN_ID": "run1", "STPT_PY": str(stub), "STPT_SRC": str(src),
           "S10_SOURCE_ONLY": "1", "STPT_MODELS": M, "STPT_POD_SESSION": "p"}
    env.pop("STPT_ACK", None)
    p = subprocess.run(["bash", "-c", f'source "{SH}"; finish 0'], env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    seen = [json.loads(f.read_text()) for f in sorted(tmp_path.glob("seen_*.json"), key=lambda f: f.stat().st_mtime_ns)]
    assert seen and all(s["open"] and s["open"]["stage"] == STAGE for s in seen[:-1])  # open during every metered upload
    d = json.loads((out / "ledger.json").read_text())
    assert d["closed"]["final"] and d["final_upload_allowance_s"] == 120
    assert d["spent_usd"][STAGE] >= 3.0 + 120                                     # gap + uploads + the last upload's allowance
    assert len(seen) == 3 and seen[-1]["closed"]["final"]                           # records, DONE, then the final ledger


def test_one_stages_stop_does_not_block_another(tmp_path):
    out = tmp_path / "out/run1"; out.mkdir(parents=True)
    LG.stop_file(out, "a:core").write_text("{}")
    env = {**os.environ, "STPT_WORKSPACE": str(tmp_path), "STPT_RUN_ID": "run1", "S10_SOURCE_ONLY": "1", "STPT_MODELS": M}
    r = subprocess.run(["bash", "-c", f'source "{SH}"; CUR_STAGE=a:core; paid true; echo "a=$?"; CUR_STAGE=b:core; paid true; echo "b=$?"'],
                       env=env, capture_output=True, text=True)
    assert "a=3" in r.stdout and "b=0" in r.stdout


# ------------------------------------------------------------------ R4.3 the real adapter: malformed readouts stop
def _adapter(readout):
    k = pod.HTTPKernel.__new__(pod.HTTPKernel)
    k.calls = 0; k.mass_max = 0.0; k.tr = k.served = k.tok = k.opt = None
    k.ser = SimpleNamespace(apply_to_tokenizer=lambda tok, msgs: msgs); k.readout = readout
    return k


def _update(k):
    c = C.load_clusters()[1]
    b = C.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, C.primary_T(M))
    return B.update(b, B.State(0, ["A"] * 100), C.MassRecorder(k))


@pytest.mark.parametrize("readout", [{"logp": {"A": -0.7, "B": -0.8}}, {"non_option_mass": 0.1}, {"logp": {"A": -0.7}, "non_option_mass": 0.1},
                                     {"logp": {"A": -0.7, "B": -0.8}, "non_option_mass": 1.5},
                                     {"logp": {"A": -0.7, "B": -0.8}, "non_option_mass": float("nan")}, None])
def test_malformed_readout_stops_the_run(readout):
    k = _adapter(lambda *a: readout)
    with pytest.raises(C.ProtocolError):
        _update(k)
    assert k.calls == 1


def test_transport_failure_is_retried_then_missing():
    def fail(*a):
        raise ConnectionError("server unreachable")
    k = _adapter(fail)
    rec = _update(k)
    assert k.calls == 4 and rec.get("missing")                                      # registered: 3 retries, then missing


def test_valid_readout_passes_with_its_mass():
    k = _adapter(lambda *a: {"logp": {"A": -0.7, "B": -0.8}, "non_option_mass": 0.123456789})
    mr = C.MassRecorder(k)
    c = C.load_clusters()[1]
    b = C.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, C.primary_T(M))
    rec = B.update(b, B.State(0, ["A"] * 100), mr)
    assert not rec.get("missing") and mr.last == 0.123456789 and k.mass_max == 0.123456789
