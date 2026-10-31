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


def header(model: str | None = None) -> dict:
    p = pins()
    h = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "stpt": stpt_source(),
         "pins": p,
         "pins_sha256": hashlib.sha256(PINS_FILE.read_bytes()).hexdigest()}
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
