"""Spend ledger and cap watchdog for the confirmatory collection (review #4; rounds 2 and 3). Standard library only,
so the pod can meter from its first line, before anything is installed.

Metering covers the whole paid lifecycle of a pod (round 3): the pod script opens an interval at its first line
(`open --since <pod start>`), so installation, weight downloads, server starts, model calls and teardown are all
charged. Each interval is charged to a stage ("<model>:core" or "<model>:secondary"; install time to the first
stage the pod runs). Within one pod session (STPT_POD_SESSION), the time between a close and the next open is charged
too (`continuous`). A driver that dies without closing leaves the interval open, and the next begin() charges the
whole gap (round 2).

Enforcement: the driver checks in process (every 10 model calls, every 5 s of a server's readiness wait, and before a
server start, which needs headroom for one start). The watchdog enforces the same caps every 5 s for every phase,
including installation and downloads: at a cap (or an unacknowledged 80% flag) it writes CAP_STOP and terminates the
registered paid processes (downloads, the driver, vLLM). It never terminates an upload.

  python ledger.py open --out OUT --caps CAPS --stage STAGE [--since EPOCH]     (charges the gap; leaves it open)
  python ledger.py check --out OUT --caps CAPS                                    (exit 3 at a cap or flag)
  python ledger.py close --out OUT --caps CAPS
  python ledger.py watchdog --out OUT --caps CAPS [--every 5]
  python ledger.py seed --out OUT --caps CAPS --prior LEDGER.json ...           (a resumed run on a new pod: earlier
                                                                                 pods' spend counts against the caps)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class Stop(BaseException):
    """The collection stops (cap, flag, failed environment check, refused start). A BaseException, like
    KeyboardInterrupt, so that `except Exception` (the retry around every model call, stpt/board.py _call) cannot
    swallow it (round 2)."""


class Ledger:
    """Spend per stage, persisted. clock() gives wall-clock seconds; spend = metered seconds x usd_per_hour / 3600."""

    def __init__(self, path, caps, usd_per_hour, clock=time.time, session=None):
        self.path, self.caps, self.rate, self.clock = Path(path), caps, usd_per_hour, clock
        self.session = session if session is not None else os.environ.get("STPT_POD_SESSION")
        self.d = json.loads(self.path.read_text()) if self.path.exists() else {}
        for k in ("spent_usd", "flagged", "acked"):
            self.d.setdefault(k, {})
        self.d.setdefault("open", None); self.d.setdefault("closed", None); self.d.setdefault("unclosed_gaps", [])
        self.stage, self.t_last = None, None

    def save(self):
        tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.d, indent=1, sort_keys=True)); os.replace(tmp, self.path)

    def _add(self, stage, seconds):
        self.d["spent_usd"][stage] = self.d["spent_usd"].get(stage, 0.0) + max(0.0, seconds) * self.rate / 3600

    def spent(self, stage):
        return self.d["spent_usd"].get(stage, 0.0)

    def begin(self, stage, since=None):
        if stage not in self.caps:
            raise Stop(f"no cap set for stage {stage}: refused")
        now = self.clock()
        if self.stage is None:
            o, c = self.d.get("open"), self.d.get("closed")
            if o:                                                   # an earlier process died with its interval open
                gap = now - o["t_last"]; self._add(o["stage"], gap)
                self.d["unclosed_gaps"].append({"stage": o["stage"], "seconds": max(0.0, gap)})
            elif c and self.session and c.get("session") == self.session:
                self._add(stage, now - c["at"])                     # continuous within one pod session
            if since is not None:                                   # the pod's first line: charge from then
                self._add(stage, now - float(since))
        else:
            self.charge(save=False)
        self.stage, self.t_last = stage, now
        self.d["open"] = {"stage": stage, "t_last": now, "session": self.session}
        self.save()

    def charge(self, save=True):
        if self.stage is not None and self.t_last is not None:
            now = self.clock()
            self._add(self.stage, now - self.t_last)
            self.t_last = now
            self.d["open"] = {"stage": self.stage, "t_last": now, "session": self.session}
            if save:
                self.save()

    def close(self):
        """A clean stop: charge up to now and close the interval."""
        self.charge(save=False)
        self.d["open"] = None; self.d["closed"] = {"at": self.clock(), "session": self.session}
        self.stage = self.t_last = None
        self.save()

    def status(self, stage, spent):
        cap = self.caps[stage]
        if spent >= cap:
            return "cap"
        if spent >= 0.8 * cap and not self.d["acked"].get(stage):
            return "flag"
        return "ok"

    def check(self, log=lambda e: None):
        """Raise Stop at the 80% flag (until acknowledged) or at the cap."""
        self.charge()
        s = self.stage; spent = self.spent(s); cap = self.caps[s]; st = self.status(s, spent)
        if st == "cap":
            log({"event": "cap_reached", "stage": s, "spent_usd": round(spent, 4), "cap_usd": cap})
            raise Stop(f"stage {s}: cap reached (${spent:.2f} of ${cap:.2f})")
        if st == "flag":
            if not self.d["flagged"].get(s):
                self.d["flagged"][s] = True; self.save()
                log({"event": "flag_80pct", "stage": s, "spent_usd": round(spent, 4), "cap_usd": cap})
            raise Stop(f"stage {s}: 80% of the cap reached (${spent:.2f} of ${cap:.2f}); flagged to the owner, awaiting acknowledgement")

    def headroom(self, stage, seconds):
        """Refuse to begin something that needs `seconds` of metered time if the stage cap cannot cover it."""
        spent = self.spent(stage)
        if self.caps[stage] - spent < seconds * self.rate / 3600:
            raise Stop(f"stage {stage}: ${self.caps[stage] - spent:.2f} left, less than one server start "
                       f"({seconds} s = ${seconds * self.rate / 3600:.2f}): refused")

    def ack(self, stage):
        self.d["acked"][stage] = True; self.save()

    def seed(self, priors):
        """Add earlier runs' spend (and their flags) before anything is charged here, so caps are cumulative across
        pods. Acknowledgements are not carried over: the owner gives them again."""
        if any(v > 0 for v in self.d["spent_usd"].values()) or self.d.get("prior_runs"):
            raise Stop("seed refused: this ledger already has spend or priors")
        self.d["prior_runs"] = []
        for name, prior in priors:
            for k, v in prior.get("spent_usd", {}).items():
                self.d["spent_usd"][k] = self.d["spent_usd"].get(k, 0.0) + float(v)
            for k, v in prior.get("flagged", {}).items():
                self.d["flagged"][k] = self.d["flagged"].get(k) or v
            self.d["prior_runs"].append({"ledger": name, "spent_usd": prior.get("spent_usd", {})})
        self.save()


# ---------------------------------------------------------------- watchdog
def provisional(d, rate, now):
    """Spend per stage including the open interval up to now (read-only)."""
    sp = dict(d.get("spent_usd", {}))
    o = d.get("open")
    if o:
        sp[o["stage"]] = sp.get(o["stage"], 0.0) + max(0.0, now - o["t_last"]) * rate / 3600
    return sp


def terminate_paid(out):
    """SIGTERM, then SIGKILL, every registered paid process group (out/paid.pids) and any vLLM server."""
    pids = [int(x) for x in (Path(out) / "paid.pids").read_text().split()] if (Path(out) / "paid.pids").exists() else []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.killpg(pid, sig)
            except OSError:
                pass
        subprocess.run(["pkill", "-9" if sig == signal.SIGKILL else "-15", "-f", "[v]llm.entrypoints"], check=False)
        if sig == signal.SIGTERM:
            time.sleep(10)


def watchdog_once(out, caps, rate, now=None):
    """One check: returns None, or the reason the paid processes were terminated."""
    p = Path(out) / "ledger.json"
    if not p.exists() or (Path(out) / "CAP_STOP").exists():
        return None
    d = json.loads(p.read_text())
    o = d.get("open")
    if not o:
        return None
    s = o["stage"]; spent = provisional(d, rate, now if now is not None else time.time()).get(s, 0.0); cap = caps.get(s)
    if cap is None:
        reason = f"open stage {s} has no cap"
    elif spent >= cap:
        reason = f"stage {s}: cap reached (${spent:.2f} of ${cap:.2f}) [watchdog]"
    elif spent >= 0.8 * cap and not d.get("acked", {}).get(s):
        reason = f"stage {s}: 80% of the cap reached (${spent:.2f} of ${cap:.2f}) [watchdog]"
    else:
        return None
    (Path(out) / "CAP_STOP").write_text(json.dumps({"reason": reason, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    terminate_paid(out)
    return reason


def _caps(path):
    c = json.loads(Path(path).read_text())
    return c["caps_usd"], float(os.environ.get("USD_PER_GPU_HOUR", c["usd_per_gpu_hour"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["open", "check", "close", "watchdog", "seed"])
    ap.add_argument("--prior", nargs="*", default=[])
    ap.add_argument("--out", required=True); ap.add_argument("--caps", required=True)
    ap.add_argument("--stage"); ap.add_argument("--since", type=float); ap.add_argument("--every", type=float, default=5.0)
    a = ap.parse_args(argv)
    caps, rate = _caps(a.caps)
    L = Ledger(Path(a.out) / "ledger.json", caps, rate)
    try:
        if a.cmd == "seed":
            L.seed([(p, json.loads(Path(p).read_text())) for p in a.prior])
        elif a.cmd == "open":
            L.begin(a.stage, since=a.since); L.check()
        elif a.cmd == "check":
            o = L.d.get("open")
            if o:
                L.stage, L.t_last = o["stage"], o["t_last"]; L.check()
        elif a.cmd == "close":
            o = L.d.get("open")
            if o:
                L.stage, L.t_last = o["stage"], o["t_last"]
            L.close()
        else:
            while True:
                r = watchdog_once(a.out, caps, rate)
                if r:
                    print("watchdog:", r, flush=True)
                time.sleep(a.every)
    except Stop as e:
        print("STOP:", e, flush=True)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
