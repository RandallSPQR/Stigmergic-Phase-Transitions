"""CPU validation of the confirmatory driver (review #4, addendum 1). Mock model only; no GPU, no API call.

  python gates/S10/run/validate_driver_cpu.py [out_dir] -> gates/S10/results/driver_cpu_validation.json

Criteria, fixed before the run (each must hold):
  D1 uninterrupted run (Gemma-2-9B, blocks 1-2, core + secondary arms): every record equals run_cluster() for that
     cluster and arm (the driver adds only checkpoints and start IDs); T is the model's primary T (1.0 in the T1 arm);
     every arm's branches share one server start; each block has its own start; the analysis accepts every primary
     record (exact shape, pairing, branch alignment, one start).
  D2 cap kill mid-cluster: a stage cap reached inside a branch stops the driver mid-cluster; nothing becomes a final
     record for the interrupted block; resuming (new server start, raised cap) abandons the block's output (logged),
     reruns the whole block in one start, makes each final record once, and ends with records identical to D1 (apart
     from start IDs), every block in exactly one start (revised after the confirmation pass on bb0f12a).
  D3 80% flag: the driver stops at 80% of a stage cap; a resume without the owner's acknowledgement stops again before
     any server start or model call; with it, the run completes.
  D4 hard kill (SIGKILL of the driver process while the server keeps running): the resumed driver re-attaches to the
     same start, reuses the branches checkpointed in it, runs only the rest, and ends with records identical to D1.
  D6 cap precision (confirmation pass): with a $0.50 cap at $1 per 1,000 calls the driver stops within CHECK_EVERY
     calls of the cap; a Stop raised inside a model call is not retried by the harness.
  D7 hard-kill billing (confirmation pass): the time between a SIGKILL of the driver and the resume (server alive) is
     charged to the stage that was open.
  D8 startup caps (round 3): a server start is refused when the stage cap cannot cover one start; a readiness wait
     that runs past the cap stops within one 5 s check, with no model call.
  D9 data safety (round 3): with the upload failing, the pod script's finish() keeps UPLOAD_PENDING, writes no DONE,
     exits 5 and issues no pod command; with a verified upload it clears the marker and writes DONE; launch.py
     --data-safe stops (never deletes) a pod whose marker remains, and deletes one whose marker was cleared.
  D10 non-A/B mass (round 3): every call's mass is in the driver's records and the analysis accepts them.
  D5 refusals: failed environment (pipeline pin) check -> stop before any model call; unknown model; a stage without
     a cap; a cluster that is not one of the 61 frozen clusters; an undrawn arm.
"""
from __future__ import annotations

import copy
import gzip
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "gates/S10", ROOT / "gates/S10/analysis", ROOT / "gates/S7", HERE):
    sys.path.insert(0, str(p))
import confirmatory as CA  # noqa: E402
import driver as DR  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402
from stpt import board as B  # noqa: E402

MODEL = "gemma-2-9b-it"
RATE = 3.6                        # USD per metered hour; with the call clock below (1 s per call), $1 per 1,000 calls


class FakeServer:
    """A server whose state survives the driver process (file), so a hard-killed driver can re-attach."""

    def __init__(self, path, pod="cpu-mock"):
        self.path, self.pod = Path(path), pod

    def _st(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {"index": 0, "alive": False, "started_at": None}

    def start(self, check=lambda: None):
        check()
        st = self._st()
        if st["alive"]:
            return {"id": f"{self.pod}/start{st['index']}/{st['started_at']}", "pod": self.pod, "index": st["index"],
                    "started_at": st["started_at"], "attached": True}
        st = {"index": st["index"] + 1, "alive": True, "started_at": f"t{time.time_ns()}"}
        self.path.write_text(json.dumps(st))
        return {"id": f"{self.pod}/start{st['index']}/{st['started_at']}", "pod": self.pod, "index": st["index"],
                "started_at": st["started_at"], "attached": False}

    def stop(self):
        st = self._st(); st["alive"] = False; self.path.write_text(json.dumps(st))


class CallClock:
    """Metered time = 1 second per model call (deterministic spend)."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class ClockedKernel:
    def __init__(self, clock, slow=0.0):
        self.k, self.clock, self.slow = s7_core.MockKernel(), clock, slow

    def __call__(self, msgs):
        self.clock.t += 1.0
        if self.slow:
            time.sleep(self.slow)
        return self.k(msgs)


def make_driver(out, caps, ack=(), env_ok=True, slow=0.0, model=MODEL, wall=False):
    clock = CallClock(); kern = ClockedKernel(clock, slow)
    if wall:
        clock = time.time

    def env_check(m):
        if not env_ok:
            raise RuntimeError("installed pipeline is not the pinned commit (simulated)")
        return {"model": m, "pipeline": "mock"}
    d = DR.Driver(model, kern, FakeServer(Path(out) / "fake_server.json"), env_check, caps, out, RATE,
                  {"gate": "S10", "cpu_validation": True}, mock=True, clock=clock, ack_flags=ack)
    return d, kern


def records(out, model=MODEL):
    r = {}
    for p in sorted((Path(out) / model).glob("rec_*.json.gz")):
        r[p.name] = json.loads(gzip.decompress(p.read_bytes()))
    return r


def events(out):
    p = Path(out) / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def strip(res):
    return {k: v for k, v in res.items() if k not in ("seconds", "server_start_ids", "mock")}


CORE, SEC = f"{MODEL}:core", f"{MODEL}:secondary"
BIG = {CORE: 1e9, SEC: 1e9}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/stpt_driver_cpu")
    shutil.rmtree(base, ignore_errors=True); base.mkdir(parents=True)
    out = {"doc": __doc__, "criteria": {}}
    t0 = time.time()
    blocks = [1, 2]
    frozen = C.load_clusters()

    # ---- D1
    d1 = base / "D1"
    drv, _ = make_driver(d1, BIG)
    status = drv.run(stages=("core", "secondary"), blocks=blocks)
    R1 = records(d1)
    ok_equal, ok_T, ok_start, ok_analysis = True, True, True, True
    starts_by_block = {}
    for name, rec in R1.items():
        res = rec["result"]; j, arm = res["cluster"], res["arm"]
        direct = C.run_cluster(frozen[j], MODEL, s7_core.MockKernel(), C.PRM, arm=arm, frozen=frozen)
        ok_equal &= json.dumps(strip(res), sort_keys=True) == json.dumps(strip(direct), sort_keys=True)
        ok_T &= res["T"] == (1.0 if arm == "T1" else C.primary_T(MODEL))
        ids = set(res["server_start_ids"].values())
        ok_start &= len(ids) == 1 and rec["manifest"]["server_start"]["id"] in ids
        starts_by_block.setdefault(frozen[j]["start_block"], set()).update(ids)
        if arm == "primary":
            o = CA.outcomes(res)
            ok_analysis &= o["server_start"] is not None and o["identity"]["arm"] == "primary"
    expected_arms = sum(len(C.arms_for(frozen[j], MODEL)) for j in frozen if frozen[j]["start_block"] in blocks)
    one_start_per_block = all(len(v) == 1 for v in starts_by_block.values()) and len({next(iter(v)) for v in starts_by_block.values()}) == len(blocks)
    out["criteria"]["D1"] = {"status": status, "records": len(R1), "expected_records": expected_arms, "records_equal_run_cluster": ok_equal,
                             "T_enforced": ok_T, "one_start_per_arm": ok_start, "one_start_per_block": one_start_per_block,
                             "analysis_accepts_primary_records": ok_analysis}
    out["criteria"]["D1"]["pass"] = status == "complete" and len(R1) == expected_arms and ok_equal and ok_T and ok_start and one_start_per_block and ok_analysis
    print("D1", out["criteria"]["D1"], round(time.time() - t0), "s", flush=True)

    def same_as_d1(R):
        return set(R) == set(R1) and all(json.dumps(strip(R[n]["result"]), sort_keys=True) == json.dumps(strip(R1[n]["result"]), sort_keys=True) for n in R)

    # ---- D2 cap kill mid-cluster
    d2 = base / "D2"
    first_arm_calls = R1[sorted(R1)[0]]["model_calls"]
    cap = (first_arm_calls * 2.4) / 1000.0                      # reached inside the 3rd arm of block 1 (core stage)
    drv, _ = make_driver(d2, {CORE: cap, SEC: 1e9}, ack=(CORE,))
    s1 = drv.run(stages=("core", "secondary"), blocks=blocks)
    R2a = records(d2); ev = events(d2)
    blk = d2 / MODEL / "blocks"
    in_block = sorted(p.name for p in blk.rglob("*") if p.is_dir() and p.parent.name == "partial") if blk.exists() else []
    stopped_mid = s1.startswith("stopped") and "cap reached" in s1 and len(in_block) == 1 and len(R2a) == 0
    drv, _ = make_driver(d2, {CORE: 1e9, SEC: 1e9})
    s2 = drv.run(stages=("core", "secondary"), blocks=blocks)
    R2 = records(d2); ev = events(d2)
    abandoned = [e for e in ev if e["event"] == "block_abandoned"]
    final = [e["record"] for e in ev if e["event"] == "arm_final"]
    by_block = {}
    for n, r_ in R2.items():
        by_block.setdefault(frozen[r_["result"]["cluster"]]["start_block"], set()).update(r_["result"]["server_start_ids"].values())
    one_start_each = all(len(v) == 1 for v in by_block.values())
    out["criteria"]["D2"] = {"first_status": s1, "final_records_before_resume": len(R2a), "partial_arm_dirs_at_stop": in_block,
                             "stopped_mid_cluster": stopped_mid, "resume_status": s2, "blocks_abandoned": len(abandoned),
                             "final_records_made_once": len(final) == len(set(final)) == len(R2), "every_block_in_one_start": one_start_each,
                             "records_equal_D1": same_as_d1(R2)}
    out["criteria"]["D2"]["pass"] = stopped_mid and s2 == "complete" and len(abandoned) == 1 and len(final) == len(set(final)) == len(R2) \
        and one_start_each and same_as_d1(R2)
    print("D2", out["criteria"]["D2"], round(time.time() - t0), "s", flush=True)

    # ---- D3 80% flag
    d3 = base / "D3"
    cap = (first_arm_calls * 3.0) / 1000.0 / 0.8 * 0.999         # flag inside the 3rd/4th arm
    drv, kern = make_driver(d3, {CORE: cap, SEC: 1e9})
    s1 = drv.run(stages=("core", "secondary"), blocks=blocks)
    n_ev = len(events(d3))
    drv, kern = make_driver(d3, {CORE: cap, SEC: 1e9})
    s2 = drv.run(stages=("core", "secondary"), blocks=blocks)
    new_ev = events(d3)[n_ev:]
    no_start_no_call = kern.clock.t == 0 and not any(e["event"] in ("server_start", "server_attach") for e in new_ev)
    drv, kern = make_driver(d3, {CORE: 1e9, SEC: 1e9}, ack=(CORE,))
    s3 = drv.run(stages=("core", "secondary"), blocks=blocks)
    out["criteria"]["D3"] = {"first_status": s1, "unacknowledged_resume": s2, "no_server_start_or_call_without_ack": no_start_no_call,
                             "acknowledged_resume": s3, "records_equal_D1": same_as_d1(records(d3))}
    out["criteria"]["D3"]["pass"] = "80%" in s1 and "80%" in s2 and no_start_no_call and s3 == "complete" and same_as_d1(records(d3))
    print("D3", out["criteria"]["D3"], round(time.time() - t0), "s", flush=True)

    # ---- D4 hard kill (SIGKILL) while the server keeps running
    d4 = base / "D4"; d4.mkdir()
    child = subprocess.Popen([sys.executable, __file__, "--child", str(d4)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    killed_after = None
    deadline = time.time() + 600
    while time.time() < deadline:
        ev = events(d4)
        if sum(e["event"] == "branch_done" for e in ev) >= 9:    # first arm done (6 branches) + 3 branches of the next
            child.send_signal(signal.SIGKILL); child.wait(); killed_after = sum(e["event"] == "branch_done" for e in ev); break
        if child.poll() is not None:
            break
        time.sleep(0.05)
    ev_kill = events(d4)
    server_alive = json.loads((d4 / "fake_server.json").read_text())["alive"]
    t_kill = time.time()
    time.sleep(2.0)                                                     # downtime with the server alive
    drv, _ = make_driver(d4, BIG, wall=True)
    s2 = drv.run(stages=("core", "secondary"), blocks=blocks)
    gaps = json.loads((d4 / "ledger.json").read_text())["unclosed_gaps"]
    ev = events(d4)[len(ev_kill):]
    attached = any(e["event"] == "server_attach" for e in ev)
    no_abandon = not any(e["event"] in ("partial_abandoned", "block_abandoned") for e in ev)
    gap_charged = len(gaps) == 1 and gaps[0]["seconds"] >= 2.0
    # the interrupted arm: its branches checkpointed before the kill are not run again
    pre = [(e["cluster"], e["arm"], e["branch"]) for e in ev_kill if e["event"] == "branch_done"]
    post = [(e["cluster"], e["arm"], e["branch"]) for e in ev if e["event"] == "branch_done"]
    rerun = sorted(set(pre) & set(post))
    out["criteria"]["D4"] = {"killed_after_branches": killed_after, "server_alive_after_kill": server_alive,
                             "resume_status": s2, "re_attached_same_start": attached, "nothing_abandoned": no_abandon, "kill_gap_charged": gaps,
                             "branches_rerun": rerun, "records_equal_D1": same_as_d1(records(d4))}
    out["criteria"]["D4"]["pass"] = bool(killed_after) and server_alive and s2 == "complete" and attached and no_abandon and gap_charged and not rerun and same_as_d1(records(d4))
    print("D4", out["criteria"]["D4"], round(time.time() - t0), "s", flush=True)

    # ---- D6 cap precision; a Stop inside a model call is not retried
    d6 = base / "D6"
    drv, kern = make_driver(d6, {CORE: 0.5, SEC: 1e9}, ack=(CORE,))
    s6 = drv.run(stages=("core",), blocks=[1])
    calls6 = int(kern.clock.t)
    tries = []

    def stopper(msgs):
        tries.append(1); raise DR.Stop("cap")
    cb = C.make_board(frozen[1]["spec"], frozen[1]["alloc"], frozen[1]["adj"], frozen[1]["run_key"], True, 1.0)
    try:
        B.update(cb, B.State(0, ["A"] * 100), stopper); escaped = False
    except DR.Stop:
        escaped = True
    out["criteria"]["D6"] = {"status": s6, "calls": calls6, "bound": 500 + DR.CHECK_EVERY, "stop_escapes_retry": escaped,
                             "calls_in_retried_call": len(tries)}
    out["criteria"]["D6"]["pass"] = "cap reached" in s6 and calls6 <= 500 + DR.CHECK_EVERY and escaped and len(tries) == 1
    print("D6", out["criteria"]["D6"], flush=True)
    out["criteria"]["D7"] = {"see": "D4 kill_gap_charged", "pass": out["criteria"]["D4"]["pass"] and bool(out["criteria"]["D4"]["kill_gap_charged"])}

    # ---- D8 startup caps
    class SlowStart:
        def __init__(self, clk, with_check):
            self.clk, self.with_check = clk, with_check

        def start(self, check=lambda: None):
            for _ in range(200):
                self.clk.t += 5
                if self.with_check:
                    check()
            return {"id": f"slow/start/{time.time_ns()}", "attached": False}

        def stop(self):
            pass
    r8 = {}
    for name, cap in (("headroom_refused", 0.2), ("readiness_wait_capped", 0.5)):
        clk = CallClock(); k = ClockedKernel(clk)
        d = DR.Driver(MODEL, k, SlowStart(clk, True), lambda m: {}, {CORE: cap, SEC: 1e9}, base / f"D8_{name}", RATE,
                      {}, mock=True, clock=clk, ack_flags=(CORE,))
        st = d.run(stages=("core",), blocks=[1]); sp = d.ledger.d["spent_usd"].get(CORE, 0.0)
        r8[name] = {"status": st, "spent_usd": round(sp, 4), "model_calls": k.k.calls}
    r8["pass"] = ("less than one server start" in r8["headroom_refused"]["status"] and r8["headroom_refused"]["spent_usd"] == 0
                  and "cap reached" in r8["readiness_wait_capped"]["status"] and r8["readiness_wait_capped"]["model_calls"] == 0
                  and r8["readiness_wait_capped"]["spent_usd"] <= 0.5 + 5 * RATE / 3600 + 1e-9)
    out["criteria"]["D8"] = r8
    print("D8", r8, flush=True)

    # ---- D9 data safety (the real finish() of the pod script, and launch.py --data-safe)
    sys.path.insert(0, str(ROOT / "gates/S0/gpu")); import launch  # noqa: E402
    import base64
    sh = ROOT / "gates/S10/gpu/s10_driver.sh"
    r9 = {}
    for ok in (False, True):
        t = base / f"D9_finish_{'ok' if ok else 'fail'}"; (t / "bin").mkdir(parents=True)
        stub = t / "py"; stub.write_text(f"#!/bin/sh\ncat > /dev/null\nexit {0 if ok else 1}\n"); stub.chmod(0o755)
        for nm in ("runpodctl", "curl"):
            b_ = t / "bin" / nm; b_.write_text(f"#!/bin/sh\necho {nm} \"$@\" >> {t}/pod_commands.log\n"); b_.chmod(0o755)
        ws = t / "ws"; (ws / "out/run1").mkdir(parents=True); (ws / "out/run1/rec.json").write_text("{}"); (ws / "UPLOAD_PENDING").write_text("")
        env = {**os.environ, "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "STPT_WORKSPACE": str(ws), "STPT_RUN_ID": "run1",
               "STPT_PY": str(stub), "STPT_SRC": str(ROOT), "S10_SOURCE_ONLY": "1", "STPT_MODELS": MODEL}
        p = subprocess.run(["bash", "-c", f'source "{sh}"; sleep() {{ :; }}; finish 0'], env=env, capture_output=True, text=True)
        r9[f"finish_upload_{'ok' if ok else 'failed'}"] = {"exit": p.returncode, "marker_kept": (ws / "UPLOAD_PENDING").exists(),
                                                          "DONE": (ws / "out/run1/DONE").exists(),
                                                          "pod_commands": (t / "pod_commands.log").read_text().split("\n")[:-1] if (t / "pod_commands.log").exists() else []}
    for keep in (True, False):
        t = base / f"D9_launch_{'kept' if keep else 'cleared'}"; (t / "bin").mkdir(parents=True)
        for nm in ("runpodctl", "curl"):
            b_ = t / "bin" / nm; b_.write_text(f"#!/bin/sh\necho {nm} \"$@\" >> {t}/pod_commands.log\n"); b_.chmod(0o755)
        mk = t / "UPLOAD_PENDING"; mk.write_text("")
        drv = f"#!/bin/bash\n{'true' if keep else f'rm -f {mk}'}\nexit 0\n"
        env = {**os.environ, "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "STPT_MARKER": str(mk), "STPT_END_GRACE": "0",
               "RUNPOD_POD_ID": "fake-pod", "RUNPOD_API_KEY": "x", "STPT_DRIVER_B64": base64.b64encode(drv.encode()).decode()}
        cmd = launch.start_cmd_data_safe(1.0).replace("/root/driver.sh", str(t / "driver.sh")).replace("> /tmp/selfstop.log", f"> {t}/selfstop.log")
        subprocess.run(["bash", "-c", cmd], env=env, timeout=60)
        subprocess.run(["pkill", "-f", "sleep 3600"], check=False)
        r9[f"launch_marker_{'kept' if keep else 'cleared'}"] = (t / "pod_commands.log").read_text().split("\n")[:-1]
    f_, o_ = r9["finish_upload_failed"], r9["finish_upload_ok"]
    r9["pass"] = (f_["exit"] == 5 and f_["marker_kept"] and not f_["DONE"] and f_["pod_commands"] == []
                  and o_["exit"] == 0 and not o_["marker_kept"] and o_["DONE"] and o_["pod_commands"] == []
                  and r9["launch_marker_kept"] == ["runpodctl stop pod fake-pod"]
                  and any("remove pod fake-pod" in x for x in r9["launch_marker_cleared"])
                  and not any("stop pod" in x for x in r9["launch_marker_cleared"]))
    out["criteria"]["D9"] = r9
    print("D9", r9, flush=True)

    # ---- D10 non-A/B mass in the driver's records
    class MassKernel(s7_core.MockKernel):
        def __call__(self, msgs):
            return {**super().__call__(msgs), "non_option_mass": 0.123456789}
    d10 = base / "D10"
    d = DR.Driver(MODEL, MassKernel(), FakeServer(d10 / "fake_server.json"), lambda m: {}, BIG, d10, RATE, {}, mock=True)
    st = d.run(stages=("core",), blocks=[1]); R10 = records(d10)
    rows_ok, acc = True, True
    for n, rec in R10.items():
        res = rec["result"]
        rows = res["live"] + res["blind"] + [x for p in res["pulses"] for x in p["rows"]] + ((res["self_reset"] or {}).get("rows") or [])
        rows_ok &= all(r[9] == 0.123456789 for r in rows) and all((x[6] == 0.123456789) == (x[3] == 1) for x in res["init"])
        acc &= CA.outcomes(res) is not None
    out["criteria"]["D10"] = {"status": st, "records": len(R10), "mass_in_every_row": rows_ok, "analysis_accepts": acc,
                              "pass": st == "complete" and len(R10) == 4 and rows_ok and acc}
    print("D10", out["criteria"]["D10"], flush=True)

    # ---- D5 refusals
    r = {}
    drv, kern = make_driver(base / "D5a", BIG, env_ok=False)
    s = drv.run(stages=("core",), blocks=[1]); r["env_check_failure_stops_before_any_call"] = s.startswith("stopped") and kern.clock.t == 0
    try:
        make_driver(base / "D5b", BIG, model="gpt-x"); r["unknown_model_refused"] = False
    except C.Refused:
        r["unknown_model_refused"] = True
    drv, kern = make_driver(base / "D5c", {CORE: 1e9})
    s = drv.run(stages=("core", "secondary"), blocks=[1]); r["stage_without_cap_refused"] = "no cap" in s
    bad = copy.deepcopy(frozen[1]); bad["adj"][0] = list(reversed(bad["adj"][0]))
    try:
        C.run_cluster(bad, MODEL, s7_core.MockKernel(), arm="primary"); r["tampered_cluster_refused"] = False
    except C.Refused:
        r["tampered_cluster_refused"] = True
    fake = copy.deepcopy(frozen[1]); fake["cluster"] = 62
    try:
        C.run_cluster(fake, MODEL, s7_core.MockKernel()); r["cluster_62_refused"] = False
    except C.Refused:
        r["cluster_62_refused"] = True
    nd = next(j for j in frozen if not frozen[j]["arms"]["T1"])
    try:
        C.run_cluster(frozen[nd], MODEL, s7_core.MockKernel(), arm="T1"); r["undrawn_arm_refused"] = False
    except C.Refused:
        r["undrawn_arm_refused"] = True
    r["pass"] = all(r.values())
    out["criteria"]["D5"] = r
    print("D5", r, flush=True)

    out["pass"] = all(v["pass"] for v in out["criteria"].values())
    out["seconds"] = round(time.time() - t0, 1)
    dst = ROOT / "gates/S10/results/driver_cpu_validation.json"
    dst.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("pass", out["pass"], "| seconds", out["seconds"])


def child(out):
    drv, _ = make_driver(out, BIG, slow=0.0004, wall=True)
    drv.run(stages=("core", "secondary"), blocks=[1, 2])


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()
