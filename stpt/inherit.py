"""The SPT code StPT inherits (harness and simulator only), vendored verbatim from the pinned SPT release.

  python -m stpt.inherit verify [--spt-checkout DIR]

Checks every vendored file against inherited/spt_v1.0.1/MANIFEST.json (git blob OID and sha256), and, given a checkout
of the SPT repository, against the blob at the pinned commit itself. Nothing else is inherited from SPT: no kernels,
no fitted parameters, no transition locations, no sample sizes, no endpoint choices. Those constants still appear inside
the vendored files (P1-P5 points, SPT budgets); StPT code imports functions from them and never reads those constants."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys

from stpt import ROOT

DIR = ROOT / "inherited" / "spt_v1.0.1"


def blob_oid(b: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def verify(spt_checkout: str | None = None) -> dict:
    man = json.loads((DIR / "MANIFEST.json").read_text())
    commit = man["source"]["commit"]
    out = {"source": man["source"], "files": {}}
    for f, ent in man["files"].items():
        b = (DIR / f).read_bytes()
        r = {"blob_ok": blob_oid(b) == ent["git_blob"], "sha256_ok": hashlib.sha256(b).hexdigest() == ent["sha256"]}
        if spt_checkout:
            oid = subprocess.run(["git", "-C", spt_checkout, "rev-parse", f"{commit}:{f}"], capture_output=True,
                                 text=True).stdout.strip()
            r["matches_spt_tag"] = oid == ent["git_blob"]
        r["ok"] = all(r.values())
        out["files"][f] = r
    out["ok"] = all(r["ok"] for r in out["files"].values())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify"])
    ap.add_argument("--spt-checkout")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    rep = verify(a.spt_checkout)
    txt = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w").write(txt + "\n")
    print(txt)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
