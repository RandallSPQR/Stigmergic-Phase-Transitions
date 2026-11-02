"""Open a sealed file (D27) at the owner's request. The opening is appended to the coordination record's SEALED.md
BEFORE the file is decoded; the sha256 must match the recorded one.

  python gates/S8/open_sealed.py --file gates/S8/sealed/s8_sealed.json.gz.b64 --reason "..." --requested-by owner \\
         --coord /home/user/stpt-mp-coordination/SEALED.md
"""
import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json

ap = argparse.ArgumentParser()
ap.add_argument("--file", required=True); ap.add_argument("--reason", required=True)
ap.add_argument("--requested-by", required=True); ap.add_argument("--coord", required=True)
a = ap.parse_args()
data = open(a.file, "rb").read()
h = hashlib.sha256(data).hexdigest()
log = open(a.coord).read()
if h not in log:
    raise SystemExit(f"REFUSED: sha256 {h} is not recorded in {a.coord}")
row = f"| {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M')} | `{a.file}` | {a.requested_by} | {a.reason} |\n"
with open(a.coord, "a") as f:
    f.write(row)
print("opening logged in", a.coord, "- commit that file; contents follow")
print(json.dumps(json.loads(gzip.decompress(base64.b64decode(data))), indent=1))
