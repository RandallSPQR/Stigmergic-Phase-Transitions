"""Download the response-cache snapshots listed in results/llm/cache_manifest.json from the private Hugging Face
dataset and verify their SHA-256. The snapshots are not in git (removed 2026-10-09); the dataset is their only
home. With the cache in place every Stage 1 rerun is free (no API calls). llm/client.py calls fetch() itself
when a cached model's snapshot is missing, so a fresh clone never silently re-queries OpenRouter.
  HF_TOKEN=... python llm/fetch_cache.py [OUT_DIR]   # default OUT_DIR = results/llm/cache"""
import hashlib, json, os, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "results/llm/cache_manifest.json")


def manifest():
    return json.load(open(MANIFEST))


def fetch(out=None, only=None, verbose=True):
    """Fetch the manifest's snapshots (or just the file names in `only`) into `out`; returns the number of
    SHA-256 mismatches (bad files are deleted). Files already present with the right hash are skipped."""
    m = manifest(); d = m["dataset"]
    out = out or os.path.join(ROOT, "results/llm/cache"); os.makedirs(out, exist_ok=True)
    bad = 0
    for f in m["files"]:
        if only is not None and f["file"] not in only:
            continue
        p = os.path.join(out, f["file"])
        if os.path.exists(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() == f["sha256"]:
            verbose and print("ok (present)", f["file"]); continue
        url = d["url_template"].format(repo_id=d["repo_id"], revision=d["revision"], file=f["file"])
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + os.environ["HF_TOKEN"]} if os.environ.get("HF_TOKEN") else {})
        with urllib.request.urlopen(req) as r, open(p, "wb") as fo:
            fo.write(r.read())
        ok = hashlib.sha256(open(p, "rb").read()).hexdigest() == f["sha256"]
        if not ok:
            os.remove(p)
        bad += not ok; verbose and print(("ok " if ok else "SHA-256 MISMATCH ") + f["file"])
    return bad


if __name__ == "__main__":
    sys.exit(1 if fetch(sys.argv[1] if len(sys.argv) > 1 else None) else 0)
