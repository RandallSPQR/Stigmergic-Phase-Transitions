"""S3 round 2 prompt set (gates/S3/ROUND2_PLAN.md): the SAME 720 contexts as round 1, rendered in wordings W2 and W3,
plus vote-question readouts (240 contexts x W1, W2, W3) that measure non-A/B mass at the actual vote question.

Contexts are rebuilt from round 1's records (scenario, allocation, position, own vote, contact pattern, layout); the
script first re-renders W1 and requires it to be byte-identical to round 1's prompts.
  python gates/S3/make_prompts_round2.py -> gates/S3/prompts/s3_round2_prompts.json + SHA256_round2
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import prompts as P  # noqa: E402

D = 4
BANK = ROOT / "gates" / "S2" / "banks" / "development"


def main():
    r1 = json.load(open(ROOT / "gates" / "S3" / "prompts" / "s3_prompts.json"))["prompts"]
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "*.json")))}
    allocs = {json.load(open(f))["sha256"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "allocations" / "*.json")))}
    out, mismatches = [], 0
    for p in r1:
        s, a = specs[p["scenario_id"]], allocs[p["allocation_sha256"]]
        ids = a["holders"][str(p["position"])]
        informed = bool(ids)
        private = a["items"][ids[0]]["text"] if informed else s["story"]["uninformed"]
        contacts = ["A"] * p["contacts_A"] + ["B"] * (D - p["contacts_A"])
        w1 = P.render("w1", s["story"], private, p["own_vote"], contacts, p["layout"], p["qtype"])
        if w1 != p["messages"]:
            mismatches += 1
        for w in ("w2", "w3"):
            out.append({**{k: p[k] for k in ("qtype", "scenario_id", "allocation_sha256", "position", "correct_letter", "layout",
                                             "own_vote", "contacts_A", "report_accuracy")},
                        "prompt_id": f"{w}-{p['prompt_id']}", "wording": w, "round1_prompt_id": p["prompt_id"],
                        "messages": P.render(w, s["story"], private, p["own_vote"], contacts, p["layout"], p["qtype"], informed=informed)})
        if p["qtype"] == "own_vote":       # 240 contexts, any position: the actual vote question, in every wording
            for w in ("w1", "w2", "w3"):
                out.append({**{k: p[k] for k in ("scenario_id", "allocation_sha256", "position", "layout", "own_vote", "contacts_A",
                                                 "report_accuracy")},
                            "qtype": "vote", "correct_letter": None, "prompt_id": f"{w}-vote-{p['prompt_id']}", "wording": w,
                            "round1_prompt_id": p["prompt_id"], "informed": informed,
                            "messages": P.render(w, s["story"], private, p["own_vote"], contacts, p["layout"], "vote", informed=informed)})
    if mismatches:
        raise SystemExit(f"W1 does not reproduce round 1 on {mismatches} prompts")
    d = ROOT / "gates" / "S3" / "prompts"
    blob = json.dumps({"version": "s3-round2-v1", "template": "stpt/prompts.py", "n": len(out), "prompts": out}, sort_keys=True, indent=1)
    (d / "s3_round2_prompts.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256_round2").write_text(h + "  s3_round2_prompts.json\n")
    from collections import Counter
    print("W1 reproduces round 1 on all", len(r1), "contexts; round 2:", len(out), "prompts",
          dict(Counter((x["wording"], x["qtype"]) for x in out)), "sha256", h[:16])


if __name__ == "__main__":
    main()
