#!/usr/bin/env python3
"""Launch, watch and terminate the ONE pod of gate S0's GPU part (stdlib only). Follows the pipeline's pods.py rules
in a container without launchd: it touches only the pod it created (ids in gates/S0/gpu/registry.json); it never lists
the account's pods; the account API key never goes on the pod (the pod's self-stop uses RunPod's pod-scoped key); HF_TOKEN
reaches the pod as a RunPod secret reference, never as a value; every pod carries a hard deadline after which it deletes
itself.

  python gates/S0/gpu/launch.py create --repo RandallSPQR/stpt-gate-artifacts [--hours 4] [--dry-run]
  python gates/S0/gpu/launch.py status
  python gates/S0/gpu/launch.py terminate --why TEXT
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE / "registry.json"
API = "https://rest.runpod.io/v1/pods"
UA = "stpt-s0/1.0"
IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
GPU_SETS = {   # secure-cloud $/h read 2026-10-31; one GPU type family per run; the report names the one served
    "a100": (["NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe"], 1.79),
    "rtxpro6000": (["NVIDIA RTX PRO 6000 Blackwell Server Edition"], 2.49),   # owner's fallback when no A100 (2026-10-31)
}
PIPE_COMMIT = "5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b"


def _req(method, url, body=None):
    key = os.environ.get("RUNPOD_API_KEY") or sys.exit("RUNPOD_API_KEY not set")
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def load():
    return json.loads(REG.read_text()) if REG.exists() else {"pods": {}}


def save(reg):
    REG.write_text(json.dumps(reg, indent=1) + "\n")


def start_cmd(hours: float) -> str:
    secs = int(hours * 3600)
    return (f"(sleep {secs}; curl -s -X DELETE -H \"Authorization: Bearer $RUNPOD_API_KEY\" "
            f"https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID) > /tmp/selfstop.log 2>&1 & "
            "echo \"$STPT_DRIVER_B64\" | base64 -d > /root/box_identity.sh && bash /root/box_identity.sh; "
            "sleep 60; curl -s -X DELETE -H \"Authorization: Bearer $RUNPOD_API_KEY\" https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID")


def cmd_create(a):
    reg = load()
    live = [p for p, v in reg["pods"].items() if not v.get("ended")]
    if live:
        sys.exit(f"REFUSED: a registered pod is still live: {live}")
    now = dt.datetime.now(dt.timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%MZ")
    driver = (HERE / "box_identity.sh").read_bytes()
    body = {"name": f"stpt-s0-box-identity-{run_id}", "imageName": IMAGE, "cloudType": "SECURE",
            "gpuTypeIds": GPU_SETS[a.gpu_set][0], "gpuTypePriority": "custom", "gpuCount": 1,
            "containerDiskInGb": a.disk, "volumeInGb": 0, "allowedCudaVersions": ["12.8", "12.9", "13.0"],
            "ports": [], "dockerEntrypoint": ["bash", "-c"], "dockerStartCmd": [start_cmd(a.hours)],
            "env": {"HF_TOKEN": "{{ RUNPOD_SECRET_HF_TOKEN }}", "STPT_RESULTS_REPO": a.repo, "STPT_RUN_ID": run_id,
                    "PIPE_COMMIT": PIPE_COMMIT, "STPT_DRIVER_B64": base64.b64encode(driver).decode()}}
    if os.environ.get("RUNPOD_API_KEY", "\0") in json.dumps(body):
        sys.exit("REFUSED: the account API key appears in the pod body")
    if a.dry_run:
        print(json.dumps({**body, "env": {**body["env"], "STPT_DRIVER_B64": f"<{len(driver)} bytes>"}}, indent=1))
        return 0
    code, resp = _req("POST", API, body)
    if code not in (200, 201) or not isinstance(resp, dict) or "id" not in resp:
        sys.exit(f"create failed: {code} {resp}")
    pid = resp["id"]
    reg["pods"][pid] = {"name": body["name"], "run_id": run_id, "created": now.isoformat(), "hours_cap": a.hours,
                        "deadline": (now + dt.timedelta(hours=a.hours)).isoformat(), "gpu_set": a.gpu_set,
                        "price_cap_usd_h": GPU_SETS[a.gpu_set][1], "max_cost_usd": round(a.hours * GPU_SETS[a.gpu_set][1], 2), "gpu": (resp.get("machine") or {}).get("gpuTypeId"),
                        "cost_per_hr": resp.get("costPerHr"), "repo": a.repo}
    save(reg)
    print(json.dumps({"id": pid, **reg["pods"][pid]}, indent=1))
    return 0


def cmd_status(a):
    reg = load()
    for pid, v in reg["pods"].items():
        if v.get("ended"):
            print(pid, "ended", v["ended"]); continue
        code, p = _req("GET", f"{API}/{pid}")
        st = p.get("desiredStatus") if isinstance(p, dict) else p
        print(pid, code, st, "costPerHr", isinstance(p, dict) and p.get("costPerHr"), "gpu",
              isinstance(p, dict) and (p.get("machine") or {}).get("gpuTypeId"), "deadline", v["deadline"])
        if code == 404:
            v["ended"] = f"gone at {dt.datetime.now(dt.timezone.utc).isoformat()} (self-stop or terminated)"
    save(reg)
    return 0


def cmd_terminate(a):
    reg = load()
    for pid, v in reg["pods"].items():
        if v.get("ended"):
            continue
        code, resp = _req("DELETE", f"{API}/{pid}")
        print(pid, "DELETE", code, resp)
        if code in (200, 204, 404):
            v["ended"] = f"terminated {dt.datetime.now(dt.timezone.utc).isoformat()}: {a.why}"
    save(reg)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--repo", required=True); c.add_argument("--hours", type=float, default=4.0)
    c.add_argument("--disk", type=int, default=200); c.add_argument("--dry-run", action="store_true")
    c.add_argument("--gpu-set", choices=sorted(GPU_SETS), default="a100")
    sub.add_parser("status")
    t = sub.add_parser("terminate"); t.add_argument("--why", required=True)
    a = ap.parse_args(argv)
    return {"create": cmd_create, "status": cmd_status, "terminate": cmd_terminate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
