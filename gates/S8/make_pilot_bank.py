"""Gate S8 pilot bank and clusters (gates/S8/S8_PLAN.md). Development data only; no model is called.

  python gates/S8/make_pilot_bank.py  -> gates/S8/bank_d18/*.json (12 development specs, setting S_a),
                                         gates/S8/inputs/clusters.json (+ sha256), gates/S8/inputs/MANIFEST.json
S_a: the D18 setting {3/4, 9/10} at f = 0.5 as DEVELOPMENT specs, derived from the 12 non-shared development specs
     (same story and truth; accuracy_mix {3/4, 9/10}); scenario ids dev-<story>-<truth>-d18. Kept in their own folder
     so that the S3-S6 builders, which read the development folder, are unchanged.
S_b: the provisional setting {3/5, 3/4, 9/10}: the existing non-shared development specs.
Clusters (identical for every model): 1-3 rule (i) S_a, 4-6 rule (i) S_b, 7 rule (ii) S_a, 8 rule (ii) S_b; server
start 1 = clusters 1, 2, 4, 7; start 2 = clusters 3, 5, 6, 8. Each: a fresh random-regular graph (N 100, d 4), a fresh
solvable representative allocation, a (story, truth) from a seeded rotation with truth balanced 4 A / 4 B.
These clusters are pilot clusters: never reused in confirmatory work (D27).
"""
import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stpt import evidence as E, sim  # noqa: E402

DEV = ROOT / "gates/S2/banks/development"
OUT = ROOT / "gates/S8"
CLUSTERS = [(1, "S_a", "i", 1), (2, "S_a", "i", 1), (3, "S_a", "i", 2), (4, "S_b", "i", 1), (5, "S_b", "i", 2),
            (6, "S_b", "i", 2), (7, "S_a", "ii", 1), (8, "S_b", "ii", 2)]


def draw(spec, label, maxtries=100):
    replaced = []
    for t in range(maxtries):
        a = E.allocate(spec, E.seed_of(label, t))
        if a["solvable"]:
            a["replaced_seeds"] = replaced
            return a
        replaced.append(E.seed_of(label, t))
    raise RuntimeError(label)


def main():
    base = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(DEV / "*.json")))}
    base = {k: v for k, v in base.items() if not v["evidence_model"].get("shared")}
    assert len(base) == 12, len(base)
    (OUT / "bank_d18").mkdir(parents=True, exist_ok=True)
    d18 = {}
    for sid, s in sorted(base.items()):
        t = json.loads(json.dumps(s))
        t["scenario_id"] = f"{sid}-d18"
        t["evidence_model"]["accuracy_mix"] = ["3/4", "9/10"]
        t["evidence_model"]["accuracy_weights"] = [1, 1]
        t["conventions"] = "development copy of the D18 confirmatory setting for the S8 pilot (gates/S8/S8_PLAN.md)"
        probs = E.validate(t)
        if probs:
            raise SystemExit(f"{t['scenario_id']}: {probs}")
        (OUT / "bank_d18" / f"{t['scenario_id']}.json").write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
        d18[t["scenario_id"]] = t
    settings = {"S_a": d18, "S_b": base}
    combos = sorted({(s["story_key"], s["hidden_state"]) for s in base.values()})
    order = sorted(combos, key=lambda c: E.seed_of("S8-story-rotation", *c))
    A = [c for c in order if c[1] == "A"]; Bc = [c for c in order if c[1] == "B"]
    picks = [A[0], Bc[0], A[1], Bc[1], A[2], Bc[2], Bc[3], A[3]]       # truth balanced: 4 A, 4 B; every setting gets both truths
    clusters = []
    for (j, setting, rule, start), (story, truth) in zip(CLUSTERS, picks):
        spec = next(s for s in settings[setting].values() if s["story_key"] == story and s["hidden_state"] == truth)
        alloc = draw(spec, f"S8-cluster-{j}")
        indptr, nbr, info = sim.rrg(100, 4, E.seed_of("S8-cluster-graph", j))
        clusters.append({"cluster": j, "setting": setting, "rule": rule, "start": start, "run_key": f"S8-c{j}",
                         "spec": spec, "alloc": alloc, "graph": info,
                         "adj": [nbr[indptr[i]:indptr[i + 1]].tolist() for i in range(100)]})
    (OUT / "inputs").mkdir(exist_ok=True)
    blob = json.dumps(clusters, sort_keys=True, separators=(",", ":"))
    (OUT / "inputs/clusters.json").write_text(blob)
    man = {"bank_d18": {k: E.scenario_hash(v) for k, v in d18.items()},
           "clusters": [{"cluster": c["cluster"], "setting": c["setting"], "rule": c["rule"], "start": c["start"],
                         "scenario_id": c["spec"]["scenario_id"], "allocation_sha256": c["alloc"]["sha256"],
                         "graph_fingerprint": c["graph"]["fingerprint"], "informed": c["alloc"]["informed_positions"],
                         "pooled_logodds_toward_truth": round(c["alloc"]["pooled_logodds_toward_truth"], 2)} for c in clusters],
           "clusters_json_sha256": hashlib.sha256(blob.encode()).hexdigest()}
    (OUT / "inputs/MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    for c in man["clusters"]:
        print(c)
    print("clusters.json sha256", man["clusters_json_sha256"][:16])


if __name__ == "__main__":
    main()
