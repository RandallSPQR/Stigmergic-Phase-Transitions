"""StPT evidence model (gate S2): scenarios, designed likelihood ratios, dependence, allocation, pooled benchmark.

A SCENARIO fixes, before any model sees it:
  - a hidden state S in {A, B} and a prior P(S = A) (0.5);
  - a story: a question with two content options (letters A/B are mapped to contents per call, so the hidden state
    is a CONTENT, recorded as the option key "A" or "B" of the scenario's own option table);
  - the evidence model: every item is a REPORT from a source with a STATED accuracy a (in plain frequencies, e.g.
    "right 3 times out of 4"), favouring one option. Its designed likelihood ratio is LR = a / (1 - a) toward the
    option it favours (a symmetric source: correct with probability a whatever the state). The ratio is a design
    quantity, fixed by the text; how strongly a model RESPONDS to it is measured separately (gate S5);
  - dependence: items with the same item_id are one item (a shared report held by several agents); items in the
    same dependence_group are counted once per group (declared dependent, e.g. two copies of one source's report);
    everything else is conditionally independent given S;
  - a pooled margin: the pooled-evidence benchmark (prior log-odds + summed log LRs of the distinct items and groups
    in the population, signed toward the true state) must reach the margin for the allocation to be solvable.
An ALLOCATION assigns items to the 100 board positions by one recorded seed (graph, starts and every other draw use
their own seeds). Representative allocations are draws from the generative model; profiles constructed for difficulty
(minority-correct: most reports point the wrong way, the pooled evidence the right way) are labelled CONDITIONAL
CHALLENGE SET. No allocation or scenario is ever selected on a group outcome.
Schema: coordination record, evidence schema v1.0 (shared with Missing Piece). Conventions: gates/S2/CONVENTIONS.md.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

SCHEMA_VERSION = "1.0"
OPTIONS = ("A", "B")
FREQ = {Fraction(3, 5): "3 times out of 5", Fraction(3, 4): "3 times out of 4", Fraction(9, 10): "9 times out of 10",
        Fraction(2, 3): "2 times out of 3", Fraction(4, 5): "4 times out of 5"}


def lr_of(accuracy) -> float:
    a = float(accuracy)
    if not 0.5 < a < 1.0:
        raise ValueError(f"accuracy {a} must be in (0.5, 1)")
    return a / (1.0 - a)


def other(o):
    return "B" if o == "A" else "A"


@dataclass(frozen=True)
class Item:
    item_id: str
    favours: str                 # "A" or "B" (scenario option keys)
    accuracy: Fraction           # stated accuracy of the source
    source: str                  # e.g. "a guard"
    dependence_group: str | None = None

    @property
    def lr(self) -> float:
        return lr_of(self.accuracy)


def render(item: Item, story: dict) -> str:
    """The item's text: the source, its stated accuracy as a plain frequency, and the content it favours."""
    t = story["report"].format(source=item.source, freq=FREQ[item.accuracy], option=story["options"][item.favours]).strip()
    return t[:1].upper() + t[1:]


def pooled_logodds(items, prior=0.5, toward="A") -> float:
    """Prior log-odds plus the summed log LRs of the DISTINCT items (by item_id) and dependence groups (once per group,
    the group's strongest item; all members of a group must favour one option), signed toward `toward`."""
    lo = math.log(prior / (1 - prior)) * (1 if toward == "A" else -1)
    seen_ids, groups = set(), {}
    for it in items:
        if it.item_id in seen_ids:
            continue
        seen_ids.add(it.item_id)
        if it.dependence_group:
            g = groups.setdefault(it.dependence_group, it)
            if g.favours != it.favours:
                raise ValueError(f"dependence group {it.dependence_group} mixes directions")
            if it.lr > g.lr:
                groups[it.dependence_group] = it
            continue
        lo += math.log(it.lr) * (1 if it.favours == toward else -1)
    for g in groups.values():
        lo += math.log(g.lr) * (1 if g.favours == toward else -1)
    return lo


def seed_of(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:15], 16)


def allocate(scenario: dict, alloc_seed: int, N: int = 100) -> dict:
    """Representative allocation: a fraction f of positions (exactly round(f N), positions by the seed) each hold one
    independent report, its source accuracy drawn from the scenario's accuracy mix and its direction = the hidden state
    with probability = that accuracy (the generative model). Optional shared reports (scenario["shared"]) are added to
    the listed number of positions, each one item (one item_id) however many hold it. Returns positions -> item ids,
    the items, and the pooled benchmark."""
    em = scenario["evidence_model"]
    rng = np.random.Generator(np.random.PCG64(alloc_seed))
    truth = scenario["hidden_state"]
    n_inf = int(round(em["informed_fraction"] * N))
    informed = np.sort(rng.choice(N, size=n_inf, replace=False))
    accs = [Fraction(x) for x in em["accuracy_mix"]]
    w = np.array(em["accuracy_weights"], float); w = w / w.sum()
    items, holders = {}, {i: [] for i in range(N)}
    for k, pos in enumerate(informed):
        a = accs[int(rng.choice(len(accs), p=w))]
        fav = truth if rng.random() < float(a) else other(truth)
        it = Item(f"r{k}", fav, a, scenario["story"]["source"])
        items[it.item_id] = it
        holders[int(pos)].append(it.item_id)
    for j, sh in enumerate(em.get("shared", [])):
        it = Item(f"s{j}", sh["favours"] if sh["favours"] in OPTIONS else (truth if sh["favours"] == "truth" else other(truth)),
                  Fraction(sh["accuracy"]), sh.get("source", scenario["story"]["source"]))
        items[it.item_id] = it
        for pos in rng.choice(N, size=sh["holders"], replace=False):
            holders[int(pos)].append(it.item_id)
    return finish_allocation(scenario, alloc_seed, holders, items, kind="representative")


def finish_allocation(scenario, alloc_seed, holders, items, kind):
    truth = scenario["hidden_state"]
    pooled = pooled_logodds(items.values(), scenario["prior"], toward=truth)
    held = [items[i] for hs in holders.values() for i in hs]
    reports_for_truth = sum(1 for it in held if it.favours == truth)
    out = {"schema_version": SCHEMA_VERSION, "scenario_id": scenario["scenario_id"], "alloc_seed": int(alloc_seed),
           "kind": kind, "N": len(holders),
           "holders": {str(k): v for k, v in holders.items()},
           "items": {k: {"favours": v.favours, "accuracy": str(v.accuracy), "lr": v.lr, "source": v.source,
                         "dependence_group": v.dependence_group, "text": render(v, scenario["story"])} for k, v in items.items()},
           "pooled_logodds_toward_truth": pooled, "margin": scenario["pooled_margin_logodds"],
           "solvable": pooled >= scenario["pooled_margin_logodds"],
           "informed_positions": sum(1 for v in holders.values() if v),
           "held_reports": len(held), "held_reports_favouring_truth": reports_for_truth,
           "minority_correct": len(held) > 0 and reports_for_truth / len(held) < 0.5}
    out["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in out.items() if k != "sha256"}, sort_keys=True).encode()).hexdigest()
    return out


def challenge_allocation(scenario: dict, alloc_seed: int, n_strong_true: int, n_weak_false: int,
                         strong=Fraction(9, 10), weak=Fraction(3, 5), N: int = 100) -> dict:
    """Constructed minority-correct profile (CONDITIONAL CHALLENGE SET): n_strong_true strong reports for the truth and
    n_weak_false weak reports against it, at positions drawn by the seed; the rest uninformed."""
    rng = np.random.Generator(np.random.PCG64(alloc_seed))
    truth = scenario["hidden_state"]
    pos = rng.choice(N, size=n_strong_true + n_weak_false, replace=False)
    items, holders = {}, {i: [] for i in range(N)}
    for k, p in enumerate(pos):
        it = Item(f"c{k}", truth if k < n_strong_true else other(truth), strong if k < n_strong_true else weak,
                  scenario["story"]["source"])
        items[it.item_id] = it
        holders[int(p)].append(it.item_id)
    return finish_allocation(scenario, alloc_seed, holders, items, kind="conditional_challenge_set")


REQUIRED = ["schema_version", "scenario_id", "study", "bank", "story", "hidden_state", "prior", "evidence_model",
            "pooled_margin_logodds", "challenge_set"]


def validate(scenario: dict) -> list[str]:
    """Problems with a scenario spec (empty list = valid)."""
    p = [f"missing {k}" for k in REQUIRED if k not in scenario]
    if p:
        return p
    if scenario["schema_version"] != SCHEMA_VERSION:
        p.append("schema_version")
    if scenario["bank"] not in ("development", "confirmatory"):
        p.append("bank")
    if scenario["hidden_state"] not in OPTIONS:
        p.append("hidden_state")
    if scenario["prior"] != 0.5:
        p.append("prior must be 0.5")
    st = scenario["story"]
    for k in ("question", "options", "report", "source", "uninformed"):
        if k not in st:
            p.append(f"story.{k}")
    if set(st.get("options", {})) != set(OPTIONS):
        p.append("story.options must be exactly A and B")
    em = scenario["evidence_model"]
    try:
        accs = [Fraction(x) for x in em["accuracy_mix"]]
        if any(a not in FREQ for a in accs):
            p.append("accuracy without a plain-frequency wording")
        [lr_of(a) for a in accs]
        if len(em["accuracy_weights"]) != len(accs):
            p.append("accuracy_weights length")
        if not 0 < em["informed_fraction"] <= 1:
            p.append("informed_fraction")
    except Exception as e:  # noqa: BLE001
        p.append(f"evidence_model: {e}")
    if not scenario["pooled_margin_logodds"] > 0:
        p.append("pooled_margin_logodds must be > 0")
    return p


def scenario_hash(scenario: dict) -> str:
    return hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest()
