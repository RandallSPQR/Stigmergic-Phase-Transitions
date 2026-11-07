"""A41: the pod script fetches its payload from the private results dataset (too large for an environment string) and
uses it only if its sha256 matches. CPU only; curl is a stand-in."""
import base64
import hashlib
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "gates/S10/gpu/s10_driver.sh"


def _run(tmp, payload, sha, curl_ok=True, hf=True):
    src = tmp / "remote.tar.gz"; src.write_bytes(payload)
    b = tmp / "bin"; b.mkdir(exist_ok=True)
    (b / "curl").write_text("#!/bin/bash\n" + (f'out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done; cp {src} "$out"\n'
                                                if curl_ok else "exit 22\n"))
    (b / "curl").chmod(0o755)
    env = {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "S10_SOURCE_ONLY": "1", "STPT_WORKSPACE": str(tmp), "STPT_RUN_ID": "r",
           "STPT_MODELS": "gemma-2-9b-it", "STPT_PAYLOAD_SHA256": sha, "STPT_RESULTS_REPO": "o/d", "HF_TOKEN": "x"}
    if hf:
        env["STPT_PAYLOAD_HF_PATH"] = "stpt/S10/payload/p.tar.gz"
    else:
        env["STPT_PAYLOAD_B64"] = base64.b64encode(payload).decode()
    p = subprocess.run(["bash", "-c", f'source "{SH}"; sleep() {{ :; }}; fetch_payload {tmp}/got.tar.gz; echo "rc=$?"'],
                       env=env, capture_output=True, text=True, timeout=60)
    return p.stdout


P = b"payload bytes" * 100
SHA = hashlib.sha256(P).hexdigest()


def test_dataset_payload_with_matching_hash(tmp_path):
    out = _run(tmp_path, P, SHA)
    assert "rc=0" in out and (tmp_path / "got.tar.gz").read_bytes() == P


def test_dataset_payload_with_wrong_hash_is_refused(tmp_path):
    out = _run(tmp_path, P + b"x", SHA)
    assert "rc=1" in out and "payload sha256" in out


def test_failed_download_is_refused(tmp_path):
    out = _run(tmp_path, P, SHA, curl_ok=False)
    assert "rc=1" in out


@pytest.mark.parametrize("good", [True, False])
def test_environment_payload_still_works(tmp_path, good):
    out = _run(tmp_path, P, SHA if good else "0" * 64, hf=False)
    assert ("rc=0" in out) == good
