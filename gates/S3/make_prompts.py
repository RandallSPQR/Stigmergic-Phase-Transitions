"""Gate S3 prompt set: branched comprehension questions on board contexts from the DEVELOPMENT bank only.

  python gates/S3/make_prompts.py  ->  gates/S3/prompts/s3_prompts.json (+ its sha256 in gates/S3/prompts/SHA256)
Per question type 240 prompts, all seeded:
  own_evidence      informed positions only; correct = the letter of the content the report favours
  own_vote          any position; correct = the letter of the agent's current vote
  contact_majority  contact patterns 3-1 or 4-0 only (no ties); correct = the letter of the majority
Contexts: a development scenario (representative, challenge-set and shared-report allocations all eligible), a
position (informed for own_evidence), a random own vote, random displayed contact votes, and a fresh layout (letter
mapping, option order, contact order). Correct letters come out balanced by the random letter mapping.
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

N_PER_TYPE, D = 240, 4
BANK = ROOT / "gates" / "S2" / "banks" / "development"


def main():
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(BANK / "*.json")))}
    allocs = [json.load(open(f)) for f in sorted(glob.glob(str(BANK / "allocations" / "*.json")))]
    rng = np.random.Generator(np.random.PCG64(E.seed_of("S3-prompts-v1")))
    out = []
    for qtype in P.COMPREHENSION:
        k = 0
        while k < N_PER_TYPE:
            a = allocs[int(rng.integers(len(allocs)))]
            s = specs[a["scenario_id"]]
            informed = [int(p) for p, ids in a["holders"].items() if ids]
            pos = int(rng.choice(informed)) if qtype == "own_evidence" else int(rng.integers(a["N"]))
            ids = a["holders"][str(pos)]
            if len(ids) > 1:           # shared-report variants can give a position two reports; S3 uses single-report positions
                continue
            private = a["items"][ids[0]]["text"] if ids else s["story"]["uninformed"]
            own = "A" if rng.random() < 0.5 else "B"
            if qtype == "contact_majority":
                n_a = int(rng.choice([0, 1, 3, 4]))
            else:
                n_a = int(rng.integers(0, D + 1))
            contacts = ["A"] * n_a + ["B"] * (D - n_a)
            layout = P.draw_layout(rng, D)
            msgs = P.render_board(s["story"], private, own, contacts, layout, P.COMPREHENSION[qtype])
            L = layout["letter_of_content"]
            correct_content = {"own_evidence": a["items"][ids[0]]["favours"] if ids else None, "own_vote": own,
                               "contact_majority": "A" if n_a >= 3 else "B"}[qtype]
            out.append({"prompt_id": f"{qtype}-{k:03d}", "qtype": qtype, "scenario_id": s["scenario_id"],
                        "allocation_sha256": a["sha256"], "position": pos, "messages": msgs,
                        "correct_letter": L[correct_content], "layout": layout, "own_vote": own, "contacts_A": n_a,
                        "report_accuracy": a["items"][ids[0]]["accuracy"] if ids else None})
            k += 1
    d = ROOT / "gates" / "S3" / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    blob = json.dumps({"version": "s3-v1", "template": "stpt/prompts.py", "n": len(out), "prompts": out}, sort_keys=True, indent=1)
    (d / "s3_prompts.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256").write_text(h + "  s3_prompts.json\n")
    bal = {q: sum(p["correct_letter"] == "A" for p in out if p["qtype"] == q) for q in P.COMPREHENSION}
    print(len(out), "prompts; correct letter A per type (of 240):", bal, "sha256", h[:16])
    print(out[0]["messages"][0]["content"])


if __name__ == "__main__":
    main()
