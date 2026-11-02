"""S3 held-out wording check (gates/S3/HELDOUT_PLAN.md): a FRESH comprehension set from the development bank, drawn by
round 1's procedure (same size, same type balance, same eligibility) with a new seed, rendered in W3 and its variants
W4, W5, W6, plus each own-vote context with the actual vote question (measured, not scored).

The context draw is round 1's (gates/S3/make_prompts.py), factored here; with round 1's seed it reproduces round 1's 720
contexts exactly (checked on every run).
  python gates/S3/make_prompts_heldout.py -> prompts/s3_heldout_contexts.json, prompts/s3_heldout_prompts.json, SHA256_heldout
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E, prompts as P  # noqa: E402

N_PER_TYPE, D = 240, 4
BANK = ROOT / "gates" / "S2" / "banks" / "development"
SEED = "S3-heldout-v1"
KEY = ("scenario_id", "allocation_sha256", "position", "own_vote", "contacts_A", "layout")


def draw_contexts(seed_label):
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "*.json")))}
    allocs = [json.load(open(f)) for f in sorted(glob.glob(str(BANK / "allocations" / "*.json")))]
    rng = np.random.Generator(np.random.PCG64(E.seed_of(seed_label)))
    out = []
    for qtype in P.COMPREHENSION:
        k = 0
        while k < N_PER_TYPE:
            a = allocs[int(rng.integers(len(allocs)))]
            s = specs[a["scenario_id"]]
            informed = [int(p) for p, ids in a["holders"].items() if ids]
            pos = int(rng.choice(informed)) if qtype == "own_evidence" else int(rng.integers(a["N"]))
            ids = a["holders"][str(pos)]
            if len(ids) > 1:
                continue
            private = a["items"][ids[0]]["text"] if ids else s["story"]["uninformed"]
            own = "A" if rng.random() < 0.5 else "B"
            n_a = int(rng.choice([0, 1, 3, 4])) if qtype == "contact_majority" else int(rng.integers(0, D + 1))
            layout = P.draw_layout(rng, D)
            L = layout["letter_of_content"]
            correct_content = {"own_evidence": a["items"][ids[0]]["favours"] if ids else None, "own_vote": own,
                               "contact_majority": "A" if n_a >= 3 else "B"}[qtype]
            out.append({"prompt_id": f"{qtype}-{k:03d}", "qtype": qtype, "scenario_id": s["scenario_id"],
                        "allocation_sha256": a["sha256"], "position": pos, "correct_letter": L[correct_content],
                        "layout": layout, "own_vote": own, "contacts_A": n_a,
                        "report_accuracy": a["items"][ids[0]]["accuracy"] if ids else None,
                        "story": s["story"], "private": private, "informed": bool(ids)})
            k += 1
    return out


def main():
    r1 = json.load(open(ROOT / "gates" / "S3" / "prompts" / "s3_prompts.json"))["prompts"]
    again = draw_contexts("S3-prompts-v1")
    same = all(all(x[k] == p[k] for k in KEY + ("prompt_id", "correct_letter")) for x, p in zip(again, r1)) and len(again) == len(r1)
    if not same:
        raise SystemExit("the factored draw does not reproduce round 1")
    ctx = draw_contexts(SEED)
    r1keys = {json.dumps([p[k] for k in KEY], sort_keys=True) for p in r1}
    overlap = sum(json.dumps([c[k] for k in KEY], sort_keys=True) in r1keys for c in ctx)
    lint = [pr for c in ctx for live in (True, False)
            for pr in P.lint_same_content(c["story"], c["private"], c["own_vote"], ["A"] * c["contacts_A"] + ["B"] * (D - c["contacts_A"]),
                                          c["layout"], live, c["informed"])]
    if lint:
        raise SystemExit(f"lint: {lint[:5]}")
    out = P.build_heldout(ctx, D)
    d = ROOT / "gates" / "S3" / "prompts"
    (d / "s3_heldout_contexts.json").write_text(json.dumps(ctx, sort_keys=True, indent=1))
    blob = json.dumps({"version": "s3-heldout-v1", "template": "stpt/prompts.py", "n": len(out), "prompts": out}, sort_keys=True, indent=1)
    (d / "s3_heldout_prompts.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256_heldout").write_text(h + "  s3_heldout_prompts.json\n")
    bal = {q: sum(c["correct_letter"] == "A" for c in ctx if c["qtype"] == q) for q in P.COMPREHENSION}
    print("round 1 reproduced by the factored draw; held-out contexts", len(ctx), "overlap with round 1:", overlap,
          "| correct letter A per type (of 240):", bal, "| informed:", sum(c["informed"] for c in ctx),
          "| prompts", len(out), dict(Counter((x["wording"], x["qtype"]) for x in out)), "| lint clean | sha256", h[:16])


if __name__ == "__main__":
    main()
