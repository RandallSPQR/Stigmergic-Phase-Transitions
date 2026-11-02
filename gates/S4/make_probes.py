"""Gate S4 probe set (gates/S4/S4_PLAN.md): vote-question contexts from the DEVELOPMENT bank, each in four layouts.

  python gates/S4/make_probes.py w3 [w4 ...]   -> probes/s4_contexts.json, probes/s4_probes.json, probes/SHA256
120 contexts, seed "S4-probes-v1": 100 live (50 informed, 50 uninformed; contact pattern 0..4 A-votes, 10 of each per
informed status; own vote balanced) and 20 blind (10 informed, 10 uninformed). Each context gets four layouts: letter
mapping x option order (2 x 2, so the letter mapping is balanced within every start), contact order drawn per layout.
Single-report positions only, as at S3. The context draw does not depend on the wording set.
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E, prompts as P  # noqa: E402

D = 4
BANK = ROOT / "gates" / "S2" / "banks" / "development"


def draw():
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "*.json")))}
    allocs = [json.load(open(f)) for f in sorted(glob.glob(str(BANK / "allocations" / "*.json")))]
    rng = np.random.Generator(np.random.PCG64(E.seed_of("S4-probes-v1")))
    cells = [(True, inf, n_a) for inf in (True, False) for n_a in range(D + 1) for _ in range(10)] + \
            [(False, inf, 0) for inf in (True, False) for _ in range(10)]
    own_votes = {}
    out = []
    for k, (live, informed, n_a) in enumerate(cells):
        while True:
            a = allocs[int(rng.integers(len(allocs)))]
            pool = [int(p) for p, ids in a["holders"].items() if (len(ids) == 1) == informed and len(ids) <= 1]
            if pool:
                break
        s = specs[a["scenario_id"]]
        pos = int(rng.choice(pool))
        ids = a["holders"][str(pos)]
        cell = (live, informed, n_a)
        own_votes[cell] = own_votes.get(cell, 0) + 1
        own = "A" if own_votes[cell] % 2 else "B"          # balanced within each cell
        layouts = []
        for a_is_A in (True, False):
            for first in ("A", "B"):
                layouts.append({"letter_of_content": {"A": "A", "B": "B"} if a_is_A else {"A": "B", "B": "A"},
                                "listed_first_letter": first, "contact_order": rng.permutation(D).tolist()})
        out.append({"context_id": f"c{k:03d}", "live": live, "informed": informed, "contacts_A": n_a if live else 0,
                    "own_vote": own, "scenario_id": s["scenario_id"], "allocation_sha256": a["sha256"], "position": pos,
                    "story": s["story"], "private": a["items"][ids[0]]["text"] if ids else s["story"]["uninformed"],
                    "report_accuracy": a["items"][ids[0]]["accuracy"] if ids else None,
                    "report_favours": a["items"][ids[0]]["favours"] if ids else None, "layouts": layouts})
    order = rng.permutation(len(out)).tolist()                # one fixed reading order, the same in every start
    return [out[i] for i in order]


def main():
    wordings = sys.argv[1:] or ["w3"]
    assert wordings[0] == "w3" and all(w in P.FAMILY for w in wordings), wordings
    ctx = draw()
    out = P.build_s4(ctx, wordings, D)
    d = ROOT / "gates" / "S4" / "probes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "s4_contexts.json").write_text(json.dumps(ctx, sort_keys=True, indent=1))
    blob = json.dumps({"version": "s4-v1", "wordings": wordings, "template": "stpt/prompts.py", "n": len(out), "prompts": out},
                      sort_keys=True, indent=1)
    (d / "s4_probes.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256").write_text(h + "  s4_probes.json\n")
    per_w = len(out) // len(wordings)
    lettA = sum(p["layout"]["letter_of_content"]["A"] == "A" for p in out)
    print(len(ctx), "contexts;", len(out), "probes,", per_w, "per wording", wordings, "| content A shown as letter A:", lettA,
          "of", len(out), "| live", sum(c["live"] for c in ctx), "informed", sum(c["informed"] for c in ctx), "| sha256", h[:16])


if __name__ == "__main__":
    main()
