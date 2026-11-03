"""CPU validation of the confirmatory driver (review #4, addendum 1). Mock model only; no GPU, no API call.

  python gates/S10/run/validate_driver_cpu.py [out_dir] -> gates/S10/results/driver_cpu_validation.json

Criteria, fixed before the run (each must hold):
  D1 uninterrupted run (Gemma-2-9B, blocks 1-2, core + secondary arms): every record equals run_cluster() for that
     cluster and arm (the driver adds only checkpoints and start IDs); T is the model's primary T (1.0 in the T1 arm);
     every arm's branches share one server start; each block has its own start; the analysis accepts every primary
     record (exact shape, pairing, branch alignment, one start).
  D2 cap kill mid-cluster: a stage cap reached inside a branch stops the driver mid-cluster; nothing is recorded for
     the unfinished arm; resuming (new server start, raised cap) abandons the partial branches (logged), restarts that
     arm, never re-runs a finished arm, and ends with records identical to D1 (apart from start IDs).
  D3 80% flag: the driver stops at 80% of a stage cap; a resume without the owner's acknowledgement stops again before
     any server start or model call; with it, the run completes.
  D4 hard kill (SIGKILL of the driver process while the server keeps running): the resumed driver re-attaches to the
     same start, reuses the branches checkpointed in it, runs only the rest, and ends with records identical to D1.
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

MODEL = "gemma-2-9b-it"
RATE = 3.6                        # USD per metered hour; with the call clock below (1 s per call), $1 per 1,000 calls


class FakeServer:
    """A server whose state survives the driver process (file), so a hard-killed driver can re-attach."""

    def __init__(self, path, pod="cpu-mock"):
        self.path, self.pod = Path(path), pod

    def _st(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {"index": 0, "alive": False, "started_at": None}

    def start(self):
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


def make_driver(out, caps, ack=(), env_ok=True, slow=0.0, model=MODEL):
    clock = CallClock(); kern = ClockedKernel(clock, slow)

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
            o = CA.outcomes(res, frozen[j]["truth"])
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
    partial = list((d2 / MODEL / "partial").glob("*")) if (d2 / MODEL / "partial").exists() else []
    stopped_mid = s1.startswith("stopped") and "cap reached" in s1 and len(partial) == 1
    drv, _ = make_driver(d2, {CORE: 1e9, SEC: 1e9})
    s2 = drv.run(stages=("core", "secondary"), blocks=blocks)
    R2 = records(d2); ev = events(d2)
    abandoned = [e for e in ev if e["event"] == "partial_abandoned"]
    done_twice = len([e for e in ev if e["event"] == "arm_done"]) != len({(e["cluster"], e["arm"]) for e in ev if e["event"] == "arm_done"})
    out["criteria"]["D2"] = {"first_status": s1, "records_before_resume": len(R2a), "partial_dirs_at_stop": len(partial),
                             "stopped_mid_cluster": stopped_mid, "resume_status": s2, "partials_abandoned": len(abandoned),
                             "an_arm_recorded_twice": done_twice, "records_equal_D1": same_as_d1(R2)}
    out["criteria"]["D2"]["pass"] = stopped_mid and s2 == "complete" and len(abandoned) == 1 and not done_twice and same_as_d1(R2)
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
    drv, _ = make_driver(d4, BIG)
    s2 = drv.run(stages=("core", "secondary"), blocks=blocks)
    ev = events(d4)[len(ev_kill):]
    attached = any(e["event"] == "server_attach" for e in ev)
    no_abandon = not any(e["event"] == "partial_abandoned" for e in ev)
    # the interrupted arm: its branches checkpointed before the kill are not run again
    pre = [(e["cluster"], e["arm"], e["branch"]) for e in ev_kill if e["event"] == "branch_done"]
    post = [(e["cluster"], e["arm"], e["branch"]) for e in ev if e["event"] == "branch_done"]
    rerun = sorted(set(pre) & set(post))
    out["criteria"]["D4"] = {"killed_after_branches": killed_after, "server_alive_after_kill": server_alive,
                             "resume_status": s2, "re_attached_same_start": attached, "no_partial_abandoned": no_abandon,
                             "branches_rerun": rerun, "records_equal_D1": same_as_d1(records(d4))}
    out["criteria"]["D4"]["pass"] = bool(killed_after) and server_alive and s2 == "complete" and attached and no_abandon and not rerun and same_as_d1(records(d4))
    print("D4", out["criteria"]["D4"], round(time.time() - t0), "s", flush=True)

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
    drv, _ = make_driver(out, BIG, slow=0.0004)
    drv.run(stages=("core", "secondary"), blocks=[1, 2])


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()
