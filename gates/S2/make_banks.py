"""Gate S2: build the development bank (specs + allocations) and the confirmatory bank (specs only, allocations
after S9), validate every spec, and write a manifest of sha256 hashes. No model is called (none is imported).

  python gates/S2/make_banks.py
Outputs: gates/S2/banks/{development,confirmatory}/<scenario_id>.json, gates/S2/banks/development/allocations/,
gates/S2/banks/MANIFEST.json, gates/S2/results/validation.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E  # noqa: E402

OUT = ROOT / "gates" / "S2"
EM = {"type": "independent_reports", "accuracy_mix": ["3/5", "3/4", "9/10"], "accuracy_weights": [1, 1, 1],
      "informed_fraction": 0.5, "reports_per_informed_agent": 1, "shared": []}
MARGIN = 3.0

DEV_STORIES = {
    "bridge": {"question": "After the storm, which bridge is open: {A} or {B}?", "options": {"A": "the east bridge", "B": "the west bridge"},
               "source": "a guard", "report": "{source} who is right {freq} says {option} is open.",
               "uninformed": "You have no report about which bridge is open."},
    "well": {"question": "Which well has safe water today: {A} or {B}?", "options": {"A": "the north well", "B": "the south well"},
             "source": "a water tester", "report": "{source} who is right {freq} says {option} has safe water.",
             "uninformed": "You have no report about which well has safe water."},
    "trail": {"question": "Which trail is passable this morning: {A} or {B}?", "options": {"A": "the river trail", "B": "the ridge trail"},
              "source": "a hiker", "report": "{source} who is right {freq} says {option} is passable.",
              "uninformed": "You have no report about which trail is passable."},
    "crate": {"question": "Which crate holds the spare parts: {A} or {B}?", "options": {"A": "the red crate", "B": "the blue crate"},
              "source": "a warehouse clerk", "report": "{source} who is right {freq} says {option} holds the spare parts.",
              "uninformed": "You have no report about which crate holds the spare parts."},
    "room": {"question": "Where is the meeting being held: {A} or {B}?", "options": {"A": "room 12", "B": "room 14"},
             "source": "a receptionist", "report": "{source} who is right {freq} says the meeting is in {option}.",
             "uninformed": "You have no report about where the meeting is being held."},
    "drawer": {"question": "Where is the key: {A} or {B}?", "options": {"A": "the left drawer", "B": "the right drawer"},
               "source": "a housemate", "report": "{source} who is right {freq} says the key is in {option}.",
               "uninformed": "You have no report about where the key is."},
}
CONF_STORIES = {
    "ferry": {"question": "Which dock is the ferry leaving from: {A} or {B}?", "options": {"A": "dock 3", "B": "dock 5"},
              "source": "a deckhand", "report": "{source} who is right {freq} says the ferry is leaving from {option}.",
              "uninformed": "You have no report about which dock the ferry is leaving from."},
    "tunnel": {"question": "Which tunnel is clear of flooding: {A} or {B}?", "options": {"A": "the upper tunnel", "B": "the lower tunnel"},
               "source": "a road inspector", "report": "{source} who is right {freq} says {option} is clear of flooding.",
               "uninformed": "You have no report about which tunnel is clear of flooding."},
    "market": {"question": "Which stall still has bread: {A} or {B}?", "options": {"A": "the corner stall", "B": "the square stall"},
               "source": "a shopper", "report": "{source} who is right {freq} says {option} still has bread.",
               "uninformed": "You have no report about which stall still has bread."},
    "train": {"question": "Which platform does the night train leave from: {A} or {B}?", "options": {"A": "platform 2", "B": "platform 4"},
              "source": "a porter", "report": "{source} who is right {freq} says the night train leaves from {option}.",
              "uninformed": "You have no report about which platform the night train leaves from."},
    "parcel": {"question": "Which locker holds the parcel: {A} or {B}?", "options": {"A": "locker 7", "B": "locker 9"},
               "source": "a courier", "report": "{source} who is right {freq} says the parcel is in {option}.",
               "uninformed": "You have no report about which locker holds the parcel."},
    "orchard": {"question": "Which orchard row is ready to pick: {A} or {B}?", "options": {"A": "the first row", "B": "the last row"},
                "source": "a farmhand", "report": "{source} who is right {freq} says {option} is ready to pick.",
                "uninformed": "You have no report about which orchard row is ready to pick."},
}
SHARED_VARIANTS = {"bridge", "crate"}       # development bank only: one weak shared report against the truth, 10 holders


def spec(story_key, story, truth, bank, shared=False):
    em = json.loads(json.dumps(EM))
    sid = f"{'dev' if bank == 'development' else 'conf'}-{story_key}-{truth}"
    if shared:
        em["shared"] = [{"favours": "against_truth", "accuracy": "3/5", "holders": 10}]
        sid += "-shared"
    return {"schema_version": E.SCHEMA_VERSION, "scenario_id": sid, "study": "StPT", "bank": bank, "story_key": story_key,
            "story": story, "hidden_state": truth, "prior": 0.5, "evidence_model": em, "pooled_margin_logodds": MARGIN,
            "challenge_set": False, "conventions": "gates/S2/CONVENTIONS.md (provisional)"}


def draw(scenario, label, maxtries=100):
    """Representative allocation from the fixed seed sequence; unsolvable draws are replaced by the next seed and logged."""
    replaced = []
    for t in range(maxtries):
        a = E.allocate(scenario, E.seed_of(label, t))
        if a["solvable"]:
            a["replaced_seeds"] = replaced
            return a
        replaced.append(E.seed_of(label, t))
    raise RuntimeError(f"no solvable allocation for {label}")


def main():
    banks = {"development": [], "confirmatory": []}
    for k, st in DEV_STORIES.items():
        for truth in E.OPTIONS:
            banks["development"].append(spec(k, st, truth, "development"))
            if k in SHARED_VARIANTS:
                banks["development"].append(spec(k, st, truth, "development", shared=True))
    for k, st in CONF_STORIES.items():
        for truth in E.OPTIONS:
            banks["confirmatory"].append(spec(k, st, truth, "confirmatory"))
    manifest = {"schema_version": E.SCHEMA_VERSION, "banks": {}, "allocations": {}}
    problems = {}
    for bank, specs in banks.items():
        d = OUT / "banks" / bank
        d.mkdir(parents=True, exist_ok=True)
        for s in specs:
            pr = E.validate(s)
            if pr:
                problems[s["scenario_id"]] = pr
            (d / f"{s['scenario_id']}.json").write_text(json.dumps(s, indent=1, sort_keys=True) + "\n")
            manifest["banks"].setdefault(bank, {})[s["scenario_id"]] = E.scenario_hash(s)
    alloc_dir = OUT / "banks" / "development" / "allocations"
    alloc_dir.mkdir(parents=True, exist_ok=True)
    stats = []
    for s in banks["development"]:
        allocs = [draw(s, f"dev-alloc|{s['scenario_id']}|{k}") for k in range(4)]
        if s["story_key"] in ("room", "drawer") and not s["evidence_model"]["shared"]:
            allocs += [E.challenge_allocation(s, E.seed_of(f"dev-chal|{s['scenario_id']}|{k}"), 12, 30) for k in range(2)]
        for i, a in enumerate(allocs):
            name = f"{s['scenario_id']}__{a['kind'][:4]}{i}.json"
            (alloc_dir / name).write_text(json.dumps(a, indent=1, sort_keys=True) + "\n")
            manifest["allocations"][name] = a["sha256"]
            stats.append({"file": name, "kind": a["kind"], "pooled": round(a["pooled_logodds_toward_truth"], 3),
                          "solvable": a["solvable"], "minority_correct": a["minority_correct"],
                          "held_reports": a["held_reports"], "favouring_truth": a["held_reports_favouring_truth"],
                          "replaced_seeds": len(a.get("replaced_seeds", []))})
    (OUT / "banks" / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    rep = [x for x in stats if x["kind"] == "representative"]
    ch = [x for x in stats if x["kind"] != "representative"]
    dev_truth = [s["hidden_state"] for s in banks["development"]]
    conf_truth = [s["hidden_state"] for s in banks["confirmatory"]]
    val = {"specs_valid": not problems, "problems": problems,
           "n_specs": {b: len(v) for b, v in banks.items()},
           "truth_balance": {"development": {o: dev_truth.count(o) for o in E.OPTIONS},
                             "confirmatory": {o: conf_truth.count(o) for o in E.OPTIONS}},
           "stories_disjoint": not (set(DEV_STORIES) & set(CONF_STORIES)),
           "representative_allocations": len(rep), "all_solvable": all(x["solvable"] for x in rep),
           "replaced_draws": sum(x["replaced_seeds"] for x in rep),
           "pooled_logodds_min": min(x["pooled"] for x in rep), "pooled_logodds_max": max(x["pooled"] for x in rep),
           "share_of_reports_favouring_truth": [round(x["favouring_truth"] / x["held_reports"], 3) for x in rep],
           "challenge_allocations": len(ch), "challenge_all_minority_correct": all(x["minority_correct"] for x in ch),
           "challenge_all_solvable": all(x["solvable"] for x in ch), "allocations": stats,
           "model_modules_imported": sorted(m for m in sys.modules if m.split(".")[0] in ("sae_ethos_pipeline", "lineup", "vllm", "transformers"))}
    (OUT / "results").mkdir(exist_ok=True)
    (OUT / "results" / "validation.json").write_text(json.dumps(val, indent=1) + "\n")
    print(json.dumps({k: v for k, v in val.items() if k not in ("allocations", "share_of_reports_favouring_truth")}, indent=1))
    srt = sorted(val["share_of_reports_favouring_truth"])
    print("share of held reports favouring truth: min", srt[0], "median", srt[len(srt) // 2], "max", srt[-1])


if __name__ == "__main__":
    main()
