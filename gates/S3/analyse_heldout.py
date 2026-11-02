"""S3 held-out wording check: apply the rule of gates/S3/HELDOUT_PLAN.md to the pod's results.

  python gates/S3/analyse_heldout.py gates/S3/artifacts/<run>  -> results/heldout_summary.json
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("own_evidence", "own_vote", "contact_majority")
MODELS = ("llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b")


def main():
    run = Path(sys.argv[1])
    prompts = {p["prompt_id"]: p for p in json.load(open(ROOT / "gates" / "S3" / "prompts" / "s3_heldout_prompts.json"))["prompts"]}
    ctx = {c["prompt_id"]: c for c in json.load(open(ROOT / "gates" / "S3" / "prompts" / "s3_heldout_contexts.json"))}
    wordings = ("w3", "w4", "w5", "w6")
    out = {"rule": "a wording is valid if all five models score >= 0.90 on each of the three types on the held-out set; "
                   "W3 must pass to remain primary (gates/S3/HELDOUT_PLAN.md)", "models": {}}
    for f in sorted(glob.glob(str(run / "s3_*.json"))):
        r = json.load(open(f))
        m = r["manifest"]["model"]
        acc, pc, mass, shareA = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        split = defaultdict(list)
        for x in r["rows"]:
            p = prompts[x["prompt_id"]]
            w, q = p["wording"], p["qtype"]
            if q == "vote":
                mass[w].append(x["non_option_mass"]); shareA[w].append(x["logp_A"] > x["logp_B"])
                continue
            acc[(w, q)].append(bool(x["correct"])); pc[(w, q)].append(x["p_correct_renorm"])
            if q == "own_evidence":
                c = ctx[p["context_id"]]
                fav = {v: k for k, v in c["layout"]["letter_of_content"].items()}[c["correct_letter"]]
                agree_vote = c["own_vote"] == fav
                nA = c["contacts_A"]
                cont = "tie" if nA == 2 else ("agree" if (nA >= 3) == (fav == "A") else "disagree")
                split[(w, "vote", "agree" if agree_vote else "disagree")].append(bool(x["correct"]))
                split[(w, "contacts", cont)].append(bool(x["correct"]))
        M = {"server_start": r["manifest"]["server_start"]["id"], "pipeline_commit": r["manifest"]["identity_block"]["pipeline"]["commit"],
             "prompts_sha256": r["manifest"]["prompts_sha256"], "n_rows": len(r["rows"]), "wordings": {}}
        for w in wordings:
            M["wordings"][w] = {
                "accuracy": {q: sum(acc[(w, q)]) / len(acc[(w, q)]) for q in TYPES if acc[(w, q)]},
                "correct_of": {q: f"{sum(acc[(w, q)])}/{len(acc[(w, q)])}" for q in TYPES if acc[(w, q)]},
                "mean_p_correct_renorm": {q: sum(pc[(w, q)]) / len(pc[(w, q)]) for q in TYPES if pc[(w, q)]},
                "vote_non_option_mass": sum(mass[w]) / len(mass[w]) if mass[w] else None,
                "vote_share_A": sum(shareA[w]) / len(shareA[w]) if shareA[w] else None,
                "own_report_by_vote": {k: round(sum(split[(w, "vote", k)]) / len(split[(w, "vote", k)]), 4) for k in ("agree", "disagree") if split[(w, "vote", k)]},
                "own_report_by_contacts": {k: round(sum(split[(w, "contacts", k)]) / len(split[(w, "contacts", k)]), 4) for k in ("agree", "tie", "disagree") if split[(w, "contacts", k)]},
            }
            M["wordings"][w]["pass"] = len(M["wordings"][w]["accuracy"]) == 3 and min(M["wordings"][w]["accuracy"].values()) >= 0.90
        out["models"][m] = M
    have = all(m in out["models"] for m in MODELS)
    out["all_five_present"] = have
    out["valid"] = {w: have and all(out["models"][m]["wordings"][w]["pass"] for m in MODELS) for w in wordings}
    out["w3_passes"] = out["valid"]["w3"]
    out["wording_set"] = [w for w in wordings if out["valid"][w]] if out["w3_passes"] else []
    # D21 (owner, 2026-11-02): per-model wording sets for the per-model consistency check, and the fragility pattern
    out["valid_by_model"] = {m: [w for w in wordings if out["models"][m]["wordings"][w]["pass"]] for m in MODELS if m in out["models"]}
    out["fragility"] = [{"model": m, "wording": w, "qtype": q, "accuracy": a,
                         "correct_of": out["models"][m]["wordings"][w]["correct_of"][q],
                         "own_report_by_vote": out["models"][m]["wordings"][w]["own_report_by_vote"] if q == "own_evidence" else None}
                        for m in MODELS if m in out["models"] for w in wordings
                        for q, a in out["models"][m]["wordings"][w]["accuracy"].items() if a < 0.90]
    (ROOT / "gates" / "S3" / "results" / "heldout_summary.json").write_text(json.dumps(out, indent=1))
    for m in MODELS:
        if m in out["models"]:
            print(m.ljust(16), " | ".join(f"{w}: " + "/".join(f"{out['models'][m]['wordings'][w]['accuracy'].get(q, float('nan')):.3f}" for q in TYPES)
                                          + ("" if out["models"][m]["wordings"][w]["pass"] else " FAIL") for w in wordings))
    print("valid by model:", out["valid_by_model"])
    print("valid:", out["valid"], "| W3 passes:", out["w3_passes"], "| wording set:", out["wording_set"])


if __name__ == "__main__":
    main()
