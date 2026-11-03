"""Re-verify the freeze (osf/FREEZE_MANIFEST.json) before posting. Read-only except for its results file.

  python osf/verify_freeze.py /home/user/stpt-mp-coordination [--out osf/FREEZE_VERIFICATION.json]

Checks, all against the hashes recorded in the freeze commit 17063f58c9fb6f9064477c555c5e42200e70115f:
  1. Design files (41): every file except osf/PREREGISTRATION.md is byte-identical to its frozen hash.
     osf/PREREGISTRATION.md is finalised after the freeze by D45 step (c), so it is checked differently: the version in
     the freeze commit matches its frozen hash, and the current version differs from it only in the parts D45 (c)
     fills in (the status paragraph, §8 predictions, §9 sealed pilot estimates, and a new §12 timeline). Every other
     line of it (the preamble from "Repositories" on, §1-7, §10, §11) is identical to the frozen text.
  2. Sealed files (2): byte-identical to their registered hashes.
  3. Coordination record (7 files): at the pinned commit, each file matches its frozen hash. At the coordination
     record's current main, each file is still identical, except SEALED.md, whose frozen text must be an exact prefix
     of the current text, with only rows of the openings table appended (D45 step (b)).
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = "17063f58c9fb6f9064477c555c5e42200e70115f"
PREREG = "osf/PREREGISTRATION.md"
FILLED = {"status", "8", "9", "12"}          # parts of the pre-registration that D45 (c) fills in after the freeze


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(cwd, *a, text=False):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=text)
    if r.returncode:
        raise SystemExit(f"git {' '.join(a)} failed in {cwd}: {r.stderr}")
    return r.stdout


def parts(md):
    """Split the pre-registration into its status paragraph, the rest of the preamble, and numbered sections."""
    out, key, buf = {}, "pre", []
    for line in md.splitlines(keepends=True):
        m = re.match(r"^## (\d+)\.", line)
        if m:
            out[key] = "".join(buf); key, buf = m.group(1), []
        buf.append(line)
    out[key] = "".join(buf)
    pre = out.pop("pre")
    i = pre.index("- **Repositories:**")
    out["status"], out["preamble"] = pre[:i], pre[i:]
    return out


def main():
    coord = Path(sys.argv[1])
    out_path = ROOT / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "osf/FREEZE_VERIFICATION.json")
    man = json.loads(git(ROOT, "show", f"{FREEZE}:osf/FREEZE_MANIFEST.json"))
    if json.loads((ROOT / "osf/FREEZE_MANIFEST.json").read_text()) != man:
        raise SystemExit("osf/FREEZE_MANIFEST.json differs from the freeze commit's version")
    R = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "freeze_commit": FREEZE, "design_files": {}, "sealed_files": {}, "coordination_files": {}}

    # 1. design files
    for f, h in man["design_files"].items():
        if f == PREREG:
            continue
        cur = sha((ROOT / f).read_bytes())
        R["design_files"][f] = {"identical": cur == h}
    frozen = git(ROOT, "show", f"{FREEZE}:{PREREG}")
    pf, pc = parts(frozen.decode()), parts((ROOT / PREREG).read_text())
    unchanged = sorted(set(pf) - FILLED)
    R["design_files"][PREREG] = {
        "frozen_version_matches_hash": sha(frozen) == man["design_files"][PREREG],
        "parts_required_identical": unchanged,
        "parts_differing_outside_D45c": [k for k in unchanged if pf.get(k) != pc.get(k)],
        "unexpected_new_parts": sorted(set(pc) - set(pf) - FILLED),
        "parts_filled_after_freeze": sorted(k for k in FILLED if pf.get(k) != pc.get(k)),
    }
    d = R["design_files"][PREREG]
    d["pass"] = d["frozen_version_matches_hash"] and not d["parts_differing_outside_D45c"] and not d["unexpected_new_parts"]

    # 2. sealed files
    for f, v in man["sealed_files"].items():
        R["sealed_files"][f] = {"identical": sha((ROOT / f).read_bytes()) == v["sha256"]}

    # 3. coordination record
    pin = man["coordination_record"]["commit"]
    git(coord, "fetch", "-q", "origin", "main")
    head = git(coord, "rev-parse", "FETCH_HEAD", text=True).strip()
    for f, h in man["coordination_record"]["files"].items():
        at_pin = git(coord, "show", f"{pin}:{f}")
        now = git(coord, "show", f"{head}:{f}")
        e = {"at_pinned_commit_matches": sha(at_pin) == h, "identical_at_current_main": sha(now) == h}
        if f == "SEALED.md" and not e["identical_at_current_main"]:
            a, b = at_pin.decode(), now.decode()
            added = b[len(a):].splitlines() if b.startswith(a) else None
            rows = [l for l in (added or []) if l.strip()]
            ok = added is not None and all(re.match(r"^\| \d{4}-\d\d-\d\d \d\d:\d\d \| `gates/.+` \| .+ \| .+ \|$", l) for l in rows)
            e.update({"frozen_text_is_prefix": added is not None, "appended_lines": rows, "append_only_openings_rows": ok})
            e["pass"] = e["at_pinned_commit_matches"] and ok
        else:
            e["pass"] = e["at_pinned_commit_matches"] and e["identical_at_current_main"]
        R["coordination_files"][f] = e
    R["coordination_record"] = {"pinned_commit": pin, "current_main": head}

    n_id = sum(v["identical"] for v in R["design_files"].values() if "identical" in v)
    R["summary"] = {
        "design_files": len(man["design_files"]),
        "design_files_byte_identical": n_id,
        "design_files_checked_byte_identical": len(man["design_files"]) - 1,
        "preregistration_changes_confined_to_D45c": d["pass"],
        "sealed_files_identical": sum(v["identical"] for v in R["sealed_files"].values()),
        "coordination_files": len(man["coordination_record"]["files"]),
        "coordination_files_pass": sum(v["pass"] for v in R["coordination_files"].values()),
    }
    s = R["summary"]
    R["pass"] = (s["design_files_byte_identical"] == s["design_files_checked_byte_identical"] and d["pass"]
                 and s["sealed_files_identical"] == len(man["sealed_files"]) and s["coordination_files_pass"] == s["coordination_files"])
    out_path.write_text(json.dumps(R, indent=1, sort_keys=True) + "\n")
    print(json.dumps(R["summary"]), "| PASS" if R["pass"] else "| FAIL")
    for f, v in R["design_files"].items():
        if v.get("identical") is False:
            print("  CHANGED:", f)
    if not d["pass"]:
        print("  PRE-REGISTRATION outside D45(c):", d["parts_differing_outside_D45c"], d["unexpected_new_parts"])
    for f, v in R["coordination_files"].items():
        if not v["pass"]:
            print("  COORDINATION FAIL:", f, v)
    sys.exit(0 if R["pass"] else 1)


if __name__ == "__main__":
    main()
