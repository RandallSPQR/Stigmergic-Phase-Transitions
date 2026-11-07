"""Payload for the confirmatory pod (review #4): the files the pod needs, at their repository paths, as gzip+base64 of
a tar, with its sha256. CPU only.

  python gates/S10/run/make_payload.py CAPS_APPROVED.json -> prints {"sha256", "bytes", "files"}; writes
                                                             gates/S10/run/payload.b64 and payload.tar.gz (not committed;
                                                             the .tar.gz is uploaded to stpt/S10/payload/<sha256>.tar.gz)
The caps file must carry status "APPROVED" (the owner's approval of gates/S10/run/caps_proposed.json or of a revision).
"""
import base64
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = ["pins.yaml", "stpt/__init__.py", "stpt/board.py", "stpt/prompts.py", "gates/S10/s10_core.py",
         "gates/S10/run/driver.py", "gates/S10/run/ledger.py", "gates/S10/run/pod.py", "gates/S10/clusters/MANIFEST.json",
         "gates/S10/clusters/confirmatory_clusters.json", "analysis/results/t_options.json"]


def main():
    caps = json.loads(Path(sys.argv[1]).read_text())
    if caps.get("status") != "APPROVED":
        raise SystemExit("REFUSED: caps file status is not APPROVED")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in FILES:
            tf.add(ROOT / f, arcname=f)
        data = json.dumps(caps, indent=1, sort_keys=True).encode()
        ti = tarfile.TarInfo("gates/S10/run/caps_approved.json"); ti.size = len(data); tf.addfile(ti, io.BytesIO(data))
    raw = buf.getvalue()
    (ROOT / "gates/S10/run/payload.b64").write_text(base64.b64encode(raw).decode())
    (ROOT / "gates/S10/run/payload.tar.gz").write_bytes(raw)   # A41: delivered through the private results dataset
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "files": FILES + ["gates/S10/run/caps_approved.json"]}))


if __name__ == "__main__":
    main()
