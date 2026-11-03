"""StPT confirmatory collection driver (S10; review #4, addendum 1). No model call is made by importing this module.

  Driver(model, kernel, server, env_check, caps, out_dir, ...).run(stages=("core",), blocks=None)

What it enforces:
- **Clusters:** only the 61 frozen clusters (s10_core.load_clusters checks the cluster file, the manifest and every
  cluster against its frozen hashes). A selection of blocks is allowed; any other cluster is refused.
- **T and arms:** from s10_core.arm_spec only (the model's primary T, or 1.0 in the T1 arm; drawn arms only).
- **Pipeline pin:** env_check(model) runs after every server start, before the first call in it; a failure stops the
  driver (real runs: the pinned pipeline commit in pins.yaml; see pod.py).
- **Server starts (D14):** one server start per scheduled block of 4 clusters (the frozen layout), and the block is
  the unit of work: its arms are recorded in a block folder and become final records only when the whole block has
  finished within one start. If a block was interrupted and the driver resumes in a different start, everything the
  block produced (finished arms and partial branches) is moved to `abandoned/` (logged) and the block reruns from the
  start, so every block's clusters, and every paired contrast (live vs blind; pulsed vs unpulsed), are in one start.
  A start reported as new whose ID was used before is refused.
- **Checkpoints:** after every branch (init, live, blind, each pulsed branch, self-reset), written atomically. After a
  hard kill of the driver with the server still up, the driver re-attaches to the same start and reuses the block's
  finished arms and the same-start branches; nothing is run twice within a start.
- **Caps:** per stage, keyed "<model>:core" (the primary arm of a confirmatory model) or "<model>:secondary" (every
  other arm, and every Llama arm), in USD from metered time. At 80% of a stage's cap the driver writes a flag and stops
  until the owner acknowledges (ack_flags); at 100% it stops. The meter is checked every 10 calls inside a branch (overshoot <= 10 calls).
  A stop is a BaseException (Stop), so the harness's retry of failed model calls (which catches Exception) cannot
  swallow it; the unfinished branch is discarded and rerun on resume. The ledger meters wall-clock time and persists an
  open interval: if a driver dies without closing it (hard kill; the server may still run and bill), the next driver
  charges the whole gap to the stage that was open.

Output (out_dir/<model>/): one record per finished (cluster, arm): rec_c<j>__<arm>.json.gz =
{"model", "manifest", "result", "model_calls"}; result carries server_start_ids and mock, as the analysis requires.
Event log: out_dir/events.jsonl. Ledger: out_dir/ledger.json.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
try:
    import s10_core as C                                  # in the repository (gates/S10) or next to this file on the pod
except ImportError:  # pragma: no cover
    raise

CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
CHECK_EVERY = 10                     # cap overshoot is bounded by 10 model calls


class Stop(BaseException):
    """The driver stops (cap, flag, failed environment check, refused start); state is checkpointed. A BaseException,
    like KeyboardInterrupt, so that `except Exception` (the retry around every model call, stpt/board.py _call) cannot
    swallow it (confirmation pass on bb0f12a)."""


def stage_of(model, arm):
    """Cap key: "<model>:core" for the primary arm of a confirmatory model, "<model>:secondary" otherwise."""
    return f"{model}:" + ("core" if (model in CONF and arm == "primary") else "secondary")


# ---------------------------------------------------------------- ledger and meter
class Ledger:
    """Spend per stage, persisted. clock() gives wall-clock seconds; spend = metered seconds x usd_per_hour / 3600.
    The open interval (stage, last charge time) is persisted: a driver that dies without close() leaves it open, and the
    next driver's begin() charges the whole gap to that stage (the server, and the pod, may have run all along)."""

    def __init__(self, path, caps, usd_per_hour, clock=time.time):
        self.path, self.caps, self.rate, self.clock = Path(path), caps, usd_per_hour, clock
        self.d = json.loads(self.path.read_text()) if self.path.exists() else {}
        for k in ("spent_usd", "flagged", "acked"):
            self.d.setdefault(k, {})
        self.d.setdefault("open", None); self.d.setdefault("unclosed_gaps", [])
        self.stage, self.t_last = None, None

    def save(self):
        tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.d, indent=1, sort_keys=True)); os.replace(tmp, self.path)

    def _add(self, stage, seconds):
        self.d["spent_usd"][stage] = self.d["spent_usd"].get(stage, 0.0) + max(0.0, seconds) * self.rate / 3600

    def begin(self, stage):
        if stage not in self.caps:
            raise Stop(f"no cap set for stage {stage}: refused")
        now = self.clock()
        if self.stage is None and self.d.get("open"):            # an earlier driver died with its interval open
            o = self.d["open"]; gap = now - o["t_last"]
            self._add(o["stage"], gap)
            self.d["unclosed_gaps"].append({"stage": o["stage"], "seconds": max(0.0, gap)})
        else:
            self.charge(save=False)
        self.stage, self.t_last = stage, now
        self.d["open"] = {"stage": stage, "t_last": now}
        self.save()

    def charge(self, save=True):
        if self.stage is not None and self.t_last is not None:
            now = self.clock()
            self._add(self.stage, now - self.t_last)
            self.t_last = now
            self.d["open"] = {"stage": self.stage, "t_last": now}
            if save:
                self.save()

    def close(self):
        """A clean stop: charge up to now and close the interval (the server is stopped)."""
        self.charge(save=False)
        self.d["open"] = None; self.stage = self.t_last = None
        self.save()

    def check(self, log):
        """Raise Stop at the 80% flag (until acknowledged) or at the cap."""
        self.charge()
        s = self.stage; spent = self.d["spent_usd"].get(s, 0.0); cap = self.caps[s]
        if spent >= cap:
            log({"event": "cap_reached", "stage": s, "spent_usd": round(spent, 4), "cap_usd": cap})
            raise Stop(f"stage {s}: cap reached (${spent:.2f} of ${cap:.2f})")
        if spent >= 0.8 * cap and not self.d["acked"].get(s):
            if not self.d["flagged"].get(s):
                self.d["flagged"][s] = True; self.save()
                log({"event": "flag_80pct", "stage": s, "spent_usd": round(spent, 4), "cap_usd": cap})
            raise Stop(f"stage {s}: 80% of the cap reached (${spent:.2f} of ${cap:.2f}); flagged to the owner, awaiting acknowledgement")

    def ack(self, stage):
        self.d["acked"][stage] = True; self.save()


class MeteredKernel:
    def __init__(self, kernel, ledger, log):
        self.k, self.ledger, self.log, self.calls = kernel, ledger, log, 0

    def __call__(self, msgs):
        self.calls += 1
        if self.calls % CHECK_EVERY == 0:
            self.ledger.check(self.log)
        return self.k(msgs)


# ---------------------------------------------------------------- checkpoints
class DiskStore:
    """Branch checkpoints of one (model, cluster, arm), tagged with the server start they ran in."""

    def __init__(self, d, start_id, on_put):
        self.d, self.start_id, self.on_put = Path(d), start_id, on_put
        self.d.mkdir(parents=True, exist_ok=True)

    def get(self, name):
        p = self.d / f"{name}.json.gz"
        if not p.exists():
            return None
        o = json.loads(gzip.decompress(p.read_bytes()))
        if o["server_start"] != self.start_id:
            raise AssertionError("a checkpoint from another start was reached; the arm should have been restarted")
        return o["data"]

    def put(self, name, obj):
        p = self.d / f"{name}.json.gz"; tmp = self.d / f".{name}.tmp"
        tmp.write_bytes(gzip.compress(json.dumps({"server_start": self.start_id, "data": obj}).encode()))
        os.replace(tmp, p)
        self.on_put(name)

    def starts(self):
        return {json.loads(gzip.decompress(p.read_bytes()))["server_start"] for p in self.d.glob("*.json.gz")}


# ---------------------------------------------------------------- driver
class Driver:
    def __init__(self, model, kernel, server, env_check, caps, out_dir, usd_per_hour, manifest_base, mock,
                 clock=time.time, ack_flags=()):
        if model not in C.MODELS:
            raise C.Refused(f"unknown model {model!r}")
        self.model, self.kernel, self.server, self.env_check = model, kernel, server, env_check
        self.out = Path(out_dir); (self.out / model).mkdir(parents=True, exist_ok=True)
        self.frozen = C.load_clusters()
        self.ledger = Ledger(self.out / "ledger.json", caps, usd_per_hour, clock)
        for s in ack_flags:
            self.ledger.ack(s)
        self.manifest_base, self.mock = manifest_base, bool(mock)
        self.start = None

    def log(self, ev):
        ev = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": self.model, **ev}
        with open(self.out / "events.jsonl", "a") as f:
            f.write(json.dumps(ev) + "\n")

    def rec_path(self, j, arm):
        return self.out / self.model / f"rec_c{j}__{arm.replace(':', '-')}.json.gz"

    def plan(self, stages, blocks):
        """[(block, [(cluster, arm), ...])] in schedule order: blocks ascending; within a block, clusters ascending and,
        per cluster, the primary arm first, then its drawn secondary arms."""
        blocks = sorted(blocks or {c["start_block"] for c in self.frozen.values()})
        out = []
        for b in blocks:
            items = []
            for j in sorted(x for x, c in self.frozen.items() if c["start_block"] == b):
                for arm in C.arms_for(self.frozen[j], self.model):
                    if stage_of(self.model, arm).split(":", 1)[1] in stages:
                        items.append((j, arm))
            out.append((b, items))
        return out

    def _start_server(self, block):
        """server.start() returns {"id", ..., "attached": bool}: a new start, or (after a hard kill of the driver while
        the server kept running) the same start re-attached, in which case same-start checkpoints are reused."""
        st = self.server.start()
        p = self.out / "events.jsonl"
        seen = {json.loads(l)["server_start"]["id"] for l in (p.read_text().splitlines() if p.exists() else [])
                if json.loads(l).get("event") in ("server_start", "server_attach")}
        if not st.get("attached") and st["id"] in seen:
            self.start = st
            raise Stop(f"server start {st['id']} reported as new but its ID was used before: refused (D14)")
        self.start = st
        self.log({"event": "server_attach" if st.get("attached") else "server_start", "block": block, "server_start": st})
        try:
            ident = self.env_check(self.model)
        except Exception as e:  # noqa: BLE001
            self.log({"event": "env_check_failed", "error": str(e)})
            raise Stop(f"environment check failed for {self.model}: {e}")
        self.log({"event": "env_check_passed", "identity": ident})

    def _bdir(self, b):
        return self.out / self.model / "blocks" / f"b{b}"

    def _block_start(self, bd):
        p = bd / "block_start.json"
        return json.loads(p.read_text())["id"] if p.exists() else None

    def _finalize(self, b, bd):
        """Move the block's records to their final paths (all from one start). Resumable: a FINALIZING marker means
        the block finished in one start and only the moves remain."""
        (bd / "FINALIZING").write_text(self._block_start(bd) or "")
        for p in sorted(bd.glob("rec_*.json.gz")):
            os.replace(p, self.out / self.model / p.name)
            self.log({"event": "arm_final", "block": b, "record": p.name, "server_start": self._block_start(bd)})
        shutil.rmtree(bd)
        self.log({"event": "block_done", "block": b})

    def _arm(self, j, arm, bd):
        c = self.frozen[j]
        stage = stage_of(self.model, arm)
        self.ledger.begin(stage)
        self.ledger.check(self.log)
        d = bd / "partial" / f"c{j}__{arm.replace(':', '-')}"
        sid = self.start["id"]
        if d.exists() and DiskStore(d, sid, lambda n: None).starts() - {sid}:
            raise AssertionError("partial branches from another start inside a live block folder")
        done = []
        store = DiskStore(d, sid, lambda n: (done.append(n), self.log({"event": "branch_done", "cluster": j, "arm": arm,
                                                                                "branch": n, "server_start": sid}),
                                              self.ledger.check(self.log)))
        mk = MeteredKernel(self.kernel, self.ledger, self.log)
        res = C.run_cluster(c, self.model, mk, C.PRM, arm=arm, store=store, frozen=self.frozen)
        names = C.branch_names(c, self.model, arm)
        res["server_start_ids"] = {n: sid for n in names}
        res["mock"] = self.mock
        rec = {"model": self.model, "manifest": {**self.manifest_base, "server_start": self.start, "stage": stage},
               "result": res, "model_calls": mk.calls}
        p = bd / self.rec_path(j, arm).name; tmp = p.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(rec).encode())); os.replace(tmp, p)
        shutil.rmtree(d)
        self.log({"event": "arm_done", "cluster": j, "arm": arm, "server_start": sid, "model_calls": mk.calls,
                  "branches_run_now": done})

    def run(self, stages=("core",), blocks=None):
        try:
            for b, items in self.plan(stages, blocks):
                bd = self._bdir(b)
                if (bd / "FINALIZING").exists():
                    self._finalize(b, bd)
                todo = [(j, a) for j, a in items if not self.rec_path(j, a).exists()]
                if not todo:
                    continue
                self.ledger.begin(stage_of(self.model, todo[0][1]))       # the start's overhead is metered too
                self.ledger.check(self.log)                               # no server is started past a flag or cap
                try:
                    self._start_server(b)
                    sid = self.start["id"]
                    prior = self._block_start(bd) if bd.exists() else None
                    if bd.exists() and prior != sid:
                        dest = self.out / self.model / "abandoned" / f"b{b}__{int(time.time() * 1e6)}"
                        dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(bd), str(dest))
                        self.log({"event": "block_abandoned", "block": b, "previous_start": prior, "current_start": sid,
                                  "discarded_arms": sorted(p.name for p in dest.glob("rec_*.json.gz")), "moved_to": str(dest),
                                  "reason": "the block was interrupted and the server start changed; it reruns whole in one start"})
                    bd.mkdir(parents=True, exist_ok=True)
                    (bd / "block_start.json").write_text(json.dumps({"id": sid}))
                    for j, arm in todo:
                        if not (bd / self.rec_path(j, arm).name).exists():
                            self._arm(j, arm, bd)
                    self._finalize(b, bd)
                finally:
                    self.server.stop(); self.ledger.close(); self.log({"event": "server_stop", "block": b})
                    self.start = None
            self.log({"event": "complete", "stages": list(stages), "blocks": blocks})
            return "complete"
        except Stop as e:
            self.log({"event": "stopped", "reason": str(e)})
            return f"stopped: {e}"
