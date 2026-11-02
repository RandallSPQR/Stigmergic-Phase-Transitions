"""Gate S6 probe set (gates/S6/S6_PLAN.md): one agent holding ALL the evidence of a development allocation.

  python gates/S6/make_probes.py  -> probes/s6_contexts.json, probes/s6_probes.json, probes/SHA256
Every development allocation (72: 64 representative, 8 conditional challenge set), its DISTINCT reports (a shared report
held by many positions appears once), W3 board, blind, the vote question; own vote A and B; four layouts (letter mapping
x option order), each with its own seeded report order. 72 x 2 x 4 = 576 probes.
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

BANK = ROOT / "gates" / "S2" / "banks" / "development"


def contexts():
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "*.json")))}
    rng = np.random.Generator(np.random.PCG64(E.seed_of("S6-probes-v1")))
    out = []
    for f in sorted(glob.glob(str(BANK / "allocations" / "*.json"))):
        a = json.load(open(f)); s = specs[a["scenario_id"]]
        ids = sorted(a["items"], key=lambda k: (k[0], int(k[1:])))
        texts = [a["items"][k]["text"] for k in ids]
        for own in ("A", "B"):
            layouts = [{"letter_of_content": {"A": "A", "B": "B"} if aa else {"A": "B", "B": "A"}, "listed_first_letter": first,
                        "contact_order": [0, 1, 2, 3], "report_order": rng.permutation(len(texts)).tolist()}
                       for aa in (True, False) for first in ("A", "B")]
            out.append({"context_id": f"{a['sha256'][:12]}-own{own}", "scenario_id": a["scenario_id"], "allocation_sha256": a["sha256"],
                        "kind": a["kind"], "truth": s["hidden_state"], "pooled_logodds_toward_truth": a["pooled_logodds_toward_truth"],
                        "n_reports": len(texts), "reports_for_truth": sum(a["items"][k]["favours"] == s["hidden_state"] for k in ids),
                        "own_vote": own, "story": s["story"], "texts": texts, "layouts": layouts})
    return out


def main():
    ctx = contexts()
    out = P.build_s6(ctx, ["w3"])
    d = ROOT / "gates" / "S6" / "probes"
    (d / "s6_contexts.json").write_text(json.dumps(ctx, sort_keys=True, indent=1))
    blob = json.dumps({"version": "s6-v1", "wordings": ["w3"], "template": "stpt/prompts.py", "n": len(out), "prompts": out}, sort_keys=True, indent=1)
    (d / "s6_probes.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256").write_text(h + "  s6_probes.json\n")
    print(len(ctx), "contexts;", len(out), "probes | kinds", {k: sum(c["kind"] == k for c in ctx) for k in {c["kind"] for c in ctx}}, "| sha256", h[:16])
    m = [p for p in out if p["kind"] != "representative"][0]["messages"][0]["content"]
    print(m[:900], "...", m[-300:])


if __name__ == "__main__":
    main()
