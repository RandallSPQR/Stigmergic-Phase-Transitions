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
    # Added 2026-11-03 (coordination D29): 20 further confirmatory stories, so that clusters span many stories.
    "shuttle": {"question": "Which stop does the shuttle leave from: {A} or {B}?", "options": {"A": "the front gate", "B": "the side gate"},
                "source": "a driver", "report": "{source} who is right {freq} says the shuttle leaves from {option}.",
                "uninformed": "You have no report about which stop the shuttle leaves from."},
    "library": {"question": "Which shelf holds the atlas: {A} or {B}?", "options": {"A": "the top shelf", "B": "the bottom shelf"},
                "source": "a librarian", "report": "{source} who is right {freq} says the atlas is on {option}.",
                "uninformed": "You have no report about which shelf holds the atlas."},
    "garden": {"question": "Which bed has the ripe tomatoes: {A} or {B}?", "options": {"A": "the sunny bed", "B": "the shaded bed"},
               "source": "a gardener", "report": "{source} who is right {freq} says {option} has the ripe tomatoes.",
               "uninformed": "You have no report about which bed has the ripe tomatoes."},
    "hotel": {"question": "Which floor is the lost suitcase on: {A} or {B}?", "options": {"A": "floor 6", "B": "floor 8"},
              "source": "a bellhop", "report": "{source} who is right {freq} says the lost suitcase is on {option}.",
              "uninformed": "You have no report about which floor the lost suitcase is on."},
    "clinic": {"question": "Which desk is handling flu shots today: {A} or {B}?", "options": {"A": "the main desk", "B": "the annex desk"},
               "source": "a nurse", "report": "{source} who is right {freq} says {option} is handling flu shots today.",
               "uninformed": "You have no report about which desk is handling flu shots today."},
    "lake": {"question": "Which shore is the rowboat tied to: {A} or {B}?", "options": {"A": "the sandy shore", "B": "the rocky shore"},
             "source": "a fisher", "report": "{source} who is right {freq} says the rowboat is tied to {option}.",
             "uninformed": "You have no report about which shore the rowboat is tied to."},
    "museum": {"question": "Which hall has the new exhibit: {A} or {B}?", "options": {"A": "the glass hall", "B": "the stone hall"},
               "source": "a museum guide", "report": "{source} who is right {freq} says the new exhibit is in {option}.",
               "uninformed": "You have no report about which hall has the new exhibit."},
    "garage": {"question": "Which level has free parking spaces: {A} or {B}?", "options": {"A": "level 1", "B": "level 3"},
               "source": "an attendant", "report": "{source} who is right {freq} says {option} has free parking spaces.",
               "uninformed": "You have no report about which level has free parking spaces."},
    "bakery": {"question": "Which oven has the finished loaves: {A} or {B}?", "options": {"A": "the brick oven", "B": "the steel oven"},
               "source": "a baker", "report": "{source} who is right {freq} says the finished loaves are in {option}.",
               "uninformed": "You have no report about which oven has the finished loaves."},
    "mailbag": {"question": "Which bag holds the urgent letters: {A} or {B}?", "options": {"A": "the canvas bag", "B": "the leather bag"},
                "source": "a postal worker", "report": "{source} who is right {freq} says the urgent letters are in {option}.",
                "uninformed": "You have no report about which bag holds the urgent letters."},
    "campsite": {"question": "Which campsite has a working tap: {A} or {B}?", "options": {"A": "site 10", "B": "site 16"},
                 "source": "a ranger", "report": "{source} who is right {freq} says {option} has a working tap.",
                 "uninformed": "You have no report about which campsite has a working tap."},
    "exam": {"question": "Which classroom is the exam in: {A} or {B}?", "options": {"A": "the music room", "B": "the art room"},
             "source": "a teacher", "report": "{source} who is right {freq} says the exam is in {option}.",
             "uninformed": "You have no report about which classroom the exam is in."},
    "pier": {"question": "Which pier is the fishing boat at: {A} or {B}?", "options": {"A": "the old pier", "B": "the new pier"},
             "source": "a lighthouse keeper", "report": "{source} who is right {freq} says the fishing boat is at {option}.",
             "uninformed": "You have no report about which pier the fishing boat is at."},
    "printer": {"question": "Which printer is working: {A} or {B}?", "options": {"A": "the hallway printer", "B": "the lobby printer"},
                "source": "an office manager", "report": "{source} who is right {freq} says {option} is working.",
                "uninformed": "You have no report about which printer is working."},
    "barn": {"question": "Which barn are the goats in: {A} or {B}?", "options": {"A": "the hay barn", "B": "the tool barn"},
             "source": "a shepherd", "report": "{source} who is right {freq} says the goats are in {option}.",
             "uninformed": "You have no report about which barn the goats are in."},
    "stadium": {"question": "Which entrance is open for fans: {A} or {B}?", "options": {"A": "entrance 11", "B": "entrance 15"},
                "source": "a steward", "report": "{source} who is right {freq} says {option} is open for fans.",
                "uninformed": "You have no report about which entrance is open for fans."},
    "theatre": {"question": "Which row are the reserved seats in: {A} or {B}?", "options": {"A": "the front row", "B": "the back row"},
                "source": "an usher", "report": "{source} who is right {freq} says the reserved seats are in {option}.",
                "uninformed": "You have no report about which row the reserved seats are in."},
    "pharmacy": {"question": "Which counter has the prescription: {A} or {B}?", "options": {"A": "the window counter", "B": "the back counter"},
                 "source": "a pharmacist", "report": "{source} who is right {freq} says the prescription is at {option}.",
                 "uninformed": "You have no report about which counter has the prescription."},
    "airport": {"question": "Which gate is the flight boarding at: {A} or {B}?", "options": {"A": "gate 21", "B": "gate 23"},
                "source": "a gate agent", "report": "{source} who is right {freq} says the flight is boarding at {option}.",
                "uninformed": "You have no report about which gate the flight is boarding at."},
    "kitchen": {"question": "Which pot has the soup: {A} or {B}?", "options": {"A": "the large pot", "B": "the small pot"},
                "source": "a cook", "report": "{source} who is right {freq} says the soup is in {option}.",
                "uninformed": "You have no report about which pot has the soup."},
}
SHARED_VARIANTS = {"bridge", "crate"}       # development bank only: one weak shared report against the truth, 10 holders


CONF_EM = {"type": "independent_reports", "accuracy_mix": ["3/4", "9/10"], "accuracy_weights": [1, 1],
           "informed_fraction": 0.5, "reports_per_informed_agent": 1, "shared": []}            # D18
CONF_CONVENTIONS = "gates/S2/CONVENTIONS.md; confirmatory source set {3/4, 9/10} at informed fraction 0.5 (coordination D18)"


def spec(story_key, story, truth, bank, shared=False):
    em = json.loads(json.dumps(CONF_EM if bank == "confirmatory" else EM))
    sid = f"{'dev' if bank == 'development' else 'conf'}-{story_key}-{truth}"
    if shared:
        em["shared"] = [{"favours": "against_truth", "accuracy": "3/5", "holders": 10}]
        sid += "-shared"
    return {"schema_version": E.SCHEMA_VERSION, "scenario_id": sid, "study": "StPT", "bank": bank, "story_key": story_key,
            "story": story, "hidden_state": truth, "prior": 0.5, "evidence_model": em, "pooled_margin_logodds": MARGIN,
            "challenge_set": False,
            "conventions": CONF_CONVENTIONS if bank == "confirmatory" else "gates/S2/CONVENTIONS.md (provisional)"}


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
