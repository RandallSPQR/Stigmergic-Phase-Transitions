"""Gate S5 probe set (gates/S5/S5_PLAN.md): each evidence template ALONE, development stories only.

  python gates/S5/make_probes.py w3 [w4 ...]  -> probes/s5_contexts.json, probes/s5_probes.json, probes/SHA256
Templates: 6 development stories x stated accuracy {3/5, 3/4, 9/10} x the option the report favours {A, B} = 36 reports,
rendered by stpt.evidence.render with each story's own source; plus each story's no-report sentence (6 baselines).
Every template is shown on the BLIND board (no contacts), the actual vote question, with the agent's own current vote
A and B (balanced; the response is averaged over it) and four layouts (letter mapping x option order, balanced).
42 templates x 2 own votes = 84 contexts x 4 layouts = 336 probes per wording. Rendered by stpt.prompts.build_s4 (same
compact-context format as S4). No allocation, no board, no confirmatory story.
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E, prompts as P  # noqa: E402

BANK = ROOT / "gates" / "S2" / "banks" / "development"
ACC = [Fraction(3, 5), Fraction(3, 4), Fraction(9, 10)]


def contexts():
    stories = {}
    for f in sorted(glob.glob(str(BANK / "*.json"))):
        d = json.load(open(f))
        stories.setdefault(d["story_key"], (d["scenario_id"], d["story"]))
    layouts = [{"letter_of_content": {"A": "A", "B": "B"} if a else {"A": "B", "B": "A"}, "listed_first_letter": first,
                "contact_order": [0, 1, 2, 3]} for a in (True, False) for first in ("A", "B")]
    out = []
    for key, (sid, story) in sorted(stories.items()):
        templates = [(None, None, story["uninformed"])]
        for acc in ACC:
            for fav in ("A", "B"):
                it = E.Item(item_id=f"s5-{key}-{acc.numerator}of{acc.denominator}-{fav}", favours=fav, accuracy=acc, source=story["source"])
                templates.append((acc, fav, E.render(it, story)))
        for acc, fav, text in templates:
            for own in ("A", "B"):
                tag = "none" if acc is None else f"{acc.numerator}of{acc.denominator}-{fav}"
                out.append({"context_id": f"{key}-{tag}-own{own}", "story_key": key, "live": False, "informed": acc is not None,
                            "contacts_A": 0, "own_vote": own, "scenario_id": sid, "allocation_sha256": None, "position": None,
                            "story": story, "private": text, "report_accuracy": None if acc is None else f"{acc.numerator}/{acc.denominator}",
                            "report_favours": fav, "layouts": layouts})
    return out


def main():
    wordings = sys.argv[1:] or ["w3"]
    assert wordings[0] == "w3" and all(w in P.FAMILY for w in wordings), wordings
    ctx = contexts()
    out = P.build_s4(ctx, wordings, 4)
    d = ROOT / "gates" / "S5" / "probes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "s5_contexts.json").write_text(json.dumps(ctx, sort_keys=True, indent=1))
    blob = json.dumps({"version": "s5-v1", "wordings": wordings, "template": "stpt/prompts.py", "n": len(out), "prompts": out},
                      sort_keys=True, indent=1)
    (d / "s5_probes.json").write_text(blob)
    h = hashlib.sha256(blob.encode()).hexdigest()
    (d / "SHA256").write_text(h + "  s5_probes.json\n")
    print(len(ctx), "contexts;", len(out), "probes,", len(out) // len(wordings), "per wording", wordings, "| sha256", h[:16])
    print(out[1]["messages"][0]["content"])


if __name__ == "__main__":
    main()
