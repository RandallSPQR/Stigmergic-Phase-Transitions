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

Addendum mode (--addendum DECLARED_CHANGES.json; addendum 1, after the independent execution review):
  1'. every design file NOT declared in the file is byte-identical to its frozen hash; every declared file is listed
      with its reason and actually differs (a stale declaration fails); osf/PREREGISTRATION.md is byte-identical to the
      registered commit, and its design parts are identical to the frozen text (check 1);
  3'. the coordination record's protocol files (PROTOCOL_SPEC.md, PIPELINE.md, DATA_SEPARATION.md, the evidence schema)
      are byte-identical to the freeze; its logs (DECISIONS.md, AMENDMENTS.md, SEALED.md) only gained lines: every
      frozen line is still there, in order, unchanged (insert-only).
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


LOGS = {"DECISIONS.md", "AMENDMENTS.md", "SEALED.md"}


def insert_only(old, new):
    """Every line of `old` is in `new`, in order and unchanged (lines may only have been inserted)."""
    import difflib
    a, b = old.splitlines(), new.splitlines()
    return all(tag == "insert" or tag == "equal" for tag, *_ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes())


def addendum(coord, decl_path, out_path):
    man = json.loads(git(ROOT, "show", f"{FREEZE}:osf/FREEZE_MANIFEST.json"))
    decl = json.loads((ROOT / decl_path).read_text())
    reg = decl["registered_commit"]
    R = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "mode": "addendum",
         "freeze_commit": FREEZE, "registered_commit": reg, "declared": decl["changed"], "design_files": {},
         "coordination_files": {}}
    for f, h in man["design_files"].items():
        same = sha((ROOT / f).read_bytes()) == h
        if f == PREREG:
            continue
        R["design_files"][f] = {"identical": same, "declared": f in decl["changed"],
                                "pass": (not same) if f in decl["changed"] else same}
    unknown = sorted(set(decl["changed"]) - set(man["design_files"]))
    cur = (ROOT / PREREG).read_bytes()
    frozen = git(ROOT, "show", f"{FREEZE}:{PREREG}")
    pf, pc = parts(frozen.decode()), parts(cur.decode())
    R["preregistration"] = {"identical_to_registered_commit": cur == git(ROOT, "show", f"{reg}:{PREREG}"),
                            "design_parts_identical_to_freeze": [k for k in sorted(set(pf) - FILLED) if pf.get(k) != pc.get(k)] == [],
                            "declared": PREREG in decl["changed"]}
    R["preregistration"]["pass"] = R["preregistration"]["identical_to_registered_commit"] and \
        R["preregistration"]["design_parts_identical_to_freeze"] and not R["preregistration"]["declared"]
    for f, v in man["sealed_files"].items():
        R.setdefault("sealed_files", {})[f] = {"identical": sha((ROOT / f).read_bytes()) == v["sha256"]}
    pin = man["coordination_record"]["commit"]
    git(coord, "fetch", "-q", "origin", "main")
    head = git(coord, "rev-parse", "FETCH_HEAD", text=True).strip()
    for f, h in man["coordination_record"]["files"].items():
        at_pin = git(coord, "show", f"{pin}:{f}"); now = git(coord, "show", f"{head}:{f}")
        e = {"at_pinned_commit_matches": sha(at_pin) == h, "identical_at_current_main": sha(now) == h}
        e["insert_only"] = insert_only(at_pin.decode(), now.decode()) if f in LOGS else None
        e["pass"] = e["at_pinned_commit_matches"] and (e["insert_only"] if f in LOGS else e["identical_at_current_main"])
        R["coordination_files"][f] = e
    R["coordination_record"] = {"pinned_commit": pin, "current_main": head}
    d = R["design_files"]
    R["summary"] = {"design_files": len(man["design_files"]),
                    "unchanged_byte_identical": sum(v["identical"] for v in d.values() if not v["declared"]),
                    "unchanged_expected": sum(1 for v in d.values() if not v["declared"]),
                    "declared_changed": sorted(f for f, v in d.items() if v["declared"]),
                    "declared_but_identical": sorted(f for f, v in d.items() if v["declared"] and v["identical"]),
                    "undeclared_changes": sorted(f for f, v in d.items() if not v["declared"] and not v["identical"]),
                    "unknown_declarations": unknown,
                    "preregistration_pass": R["preregistration"]["pass"],
                    "sealed_files_identical": sum(v["identical"] for v in R["sealed_files"].values()),
                    "coordination_files_pass": sum(v["pass"] for v in R["coordination_files"].values()),
                    "coordination_files": len(R["coordination_files"])}
    s_ = R["summary"]
    R["pass"] = (all(v["pass"] for v in d.values()) and not unknown and R["preregistration"]["pass"]
                 and s_["sealed_files_identical"] == len(man["sealed_files"]) and s_["coordination_files_pass"] == s_["coordination_files"])
    out_path.write_text(json.dumps(R, indent=1, sort_keys=True) + "\n")
    print(json.dumps(s_), "| PASS" if R["pass"] else "| FAIL")
    sys.exit(0 if R["pass"] else 1)


def main():
    coord = Path(sys.argv[1])
    if "--addendum" in sys.argv:
        decl = sys.argv[sys.argv.index("--addendum") + 1]
        outp = ROOT / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "osf/addendum1/FREEZE_VERIFICATION_ADDENDUM1.json")
        return addendum(coord, decl, outp)
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
