"""Evidence model (gate S2): designed likelihood ratios, dependence counting, pooled benchmark, allocation determinism,
challenge-set labelling, validation."""
import math
from fractions import Fraction

import pytest

from stpt import evidence as E

STORY = {"question": "Which bridge is open: {A} or {B}?", "options": {"A": "the east bridge", "B": "the west bridge"},
         "source": "a guard", "report": "{source} who is right {freq} says {option} is open.",
         "uninformed": "You have no report about which bridge is open."}


def scen(**kw):
    s = {"schema_version": "1.0", "scenario_id": "t-bridge-A", "study": "StPT", "bank": "development", "story": STORY,
         "hidden_state": "A", "prior": 0.5, "pooled_margin_logodds": 3.0, "challenge_set": False,
         "evidence_model": {"type": "independent_reports", "accuracy_mix": ["3/5", "3/4", "9/10"],
                            "accuracy_weights": [1, 1, 1], "informed_fraction": 0.5, "shared": []}}
    s.update(kw)
    return s


def test_lr_from_stated_accuracy():
    assert E.lr_of(Fraction(3, 4)) == pytest.approx(3.0)
    assert E.lr_of(Fraction(9, 10)) == pytest.approx(9.0)
    assert E.lr_of(Fraction(3, 5)) == pytest.approx(1.5)
    with pytest.raises(ValueError):
        E.lr_of(0.5)


def test_render_states_accuracy_in_frequencies():
    it = E.Item("r0", "B", Fraction(3, 4), "a guard")
    assert E.render(it, STORY) == "A guard who is right 3 times out of 4 says the west bridge is open."


def test_pooled_counts_shared_once_and_groups_once():
    a = E.Item("x", "A", Fraction(3, 4), "g")
    b = E.Item("y", "B", Fraction(3, 5), "g")
    assert E.pooled_logodds([a, b]) == pytest.approx(math.log(3) - math.log(1.5))
    assert E.pooled_logodds([a, a, a, b]) == pytest.approx(math.log(3) - math.log(1.5))       # one shared item
    g1 = E.Item("p", "A", Fraction(3, 5), "g", dependence_group="G")
    g2 = E.Item("q", "A", Fraction(9, 10), "g", dependence_group="G")
    assert E.pooled_logodds([g1, g2]) == pytest.approx(math.log(9))                          # group once (strongest)
    assert E.pooled_logodds([a], toward="B") == pytest.approx(-math.log(3))
    with pytest.raises(ValueError):
        E.pooled_logodds([g1, E.Item("r", "B", Fraction(3, 4), "g", dependence_group="G")])


def test_allocation_deterministic_and_informed_fraction():
    s = scen()
    a1, a2, a3 = E.allocate(s, 11), E.allocate(s, 11), E.allocate(s, 12)
    assert a1["sha256"] == a2["sha256"] and a1["sha256"] != a3["sha256"]
    assert a1["informed_positions"] == 50 and a1["held_reports"] == 50
    lo = sum(math.log(v["lr"]) * (1 if v["favours"] == "A" else -1) for v in a1["items"].values())
    assert a1["pooled_logodds_toward_truth"] == pytest.approx(lo)


def test_shared_report_held_by_many_counts_once():
    s = scen(evidence_model={**scen()["evidence_model"], "shared": [{"favours": "against_truth", "accuracy": "3/5", "holders": 10}]})
    a = E.allocate(s, 5)
    assert sum("s0" in v for v in a["holders"].values()) == 10
    assert a["items"]["s0"]["favours"] == "B"
    reps = [v for k, v in a["items"].items() if k.startswith("r")]
    lo = sum(math.log(v["lr"]) * (1 if v["favours"] == "A" else -1) for v in reps) - math.log(1.5)
    assert a["pooled_logodds_toward_truth"] == pytest.approx(lo)


def test_generative_direction_rate():
    s = scen()
    fav, n = 0, 0
    for k in range(200):
        a = E.allocate(s, k)
        for v in a["items"].values():
            fav += v["favours"] == "A"; n += 1
    expected = (0.6 + 0.75 + 0.9) / 3
    assert abs(fav / n - expected) < 4 * math.sqrt(expected * (1 - expected) / n)


def test_challenge_profile_is_minority_correct_and_labelled():
    a = E.challenge_allocation(scen(), 3, 12, 30)
    assert a["kind"] == "conditional_challenge_set" and a["minority_correct"]
    assert a["pooled_logodds_toward_truth"] == pytest.approx(12 * math.log(9) - 30 * math.log(1.5))


def test_validate():
    assert E.validate(scen()) == []
    assert "prior must be 0.5" in E.validate(scen(prior=0.6))
    assert any("missing" in p for p in E.validate({"scenario_id": "x"}))
    assert E.validate(scen(evidence_model={**scen()["evidence_model"], "accuracy_mix": ["7/10"]}))
