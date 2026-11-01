"""The header every StPT run manifest starts with: the pins (pipeline tag + commit, SPT tag + commit, coordination
record commit, brief revision), StPT's own commit, and, when the pipeline is installed, the pipeline's identity block
for the model in use. check_environment() refuses a run whose installed pipeline is not the pinned commit."""
from __future__ import annotations

import hashlib
import subprocess
import time

import yaml

from stpt import ROOT

PINS_FILE = ROOT / "pins.yaml"


def pins() -> dict:
    return yaml.safe_load(PINS_FILE.read_text())


def stpt_source() -> dict:
    def git(*a):
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD") or None, "dirty": bool(git("status", "--porcelain"))}


def server_start_id(pod_id: str, start_index: int, started_at: str) -> dict:
    """The server-start ID every run manifest records (D14, 2026-11-01): logprobs are bit-identical within one vLLM
    server start but can move by 1-2 bf16 steps between starts, so the start is a blocking factor in every analysis."""
    if not pod_id or start_index is None or not started_at:
        raise ValueError("a server-start ID needs pod_id, start_index and started_at")
    return {"id": f"{pod_id}/start{int(start_index)}/{started_at}", "pod": pod_id, "index": int(start_index),
            "started_at": started_at}


def header(model: str | None = None, server_start: dict | None = None) -> dict:
    """Run manifest header. A header for a model call (model given) must carry the server-start ID (D14)."""
    if model is not None and not (server_start and server_start.get("id")):
        raise ValueError("a run manifest for a model call must record the server-start ID (D14): pass server_start")
    p = pins()
    h = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "stpt": stpt_source(),
         "pins": p,
         "pins_sha256": hashlib.sha256(PINS_FILE.read_bytes()).hexdigest()}
    if server_start is not None:
        h["server_start"] = server_start
    if model is not None:
        import sae_ethos_pipeline  # noqa: F401
        from lineup import manifest as lm
        h["pipeline_identity"] = lm.identity_block(model)
    return h


def check_environment(model: str) -> dict:
    """The installed pipeline must be the pinned commit and its lineup must name `model`."""
    import sae_ethos_pipeline  # noqa: F401
    from lineup import manifest as lm
    p = pins()["pipeline"]
    block = lm.identity_block(model)
    lm.check_pin(block, p["tag"], p["commit"])
    return block
