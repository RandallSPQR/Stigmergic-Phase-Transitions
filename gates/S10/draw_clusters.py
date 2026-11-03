"""S10: draw the confirmatory clusters by the seed rule fixed before any draw (gates/S2/CONFIRMATORY_SEED_RULE.md, D29),
for n = 61 (D31). CPU only; no model is called or imported.

  python gates/S10/draw_clusters.py -> gates/S10/clusters/confirmatory_clusters.json, gates/S10/clusters/MANIFEST.json
"""
import glob
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S2"))
from stpt import board as B, evidence as E, sim  # noqa: E402
import make_banks as M  # noqa: E402

N_CLUSTERS = 61
SHARES = {"T1": 0.2, "rule_ii": 0.2, "self_reset": 0.5, "variant_wording": 0.2}
VALID_VARIANTS = {"llama-3.1-8b-it": ["w4", "w5"], "gemma-2-9b-it": ["w5"], "qwen3.5-9b": ["w4"],
                  "gemma-3-27b-it": ["w4", "w5", "w6"], "qwen3.5-27b": ["w4", "w5", "w6"]}       # D21


def main():
    specs = {json.load(open(f))["scenario_id"]: json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "gates/S2/banks/confirmatory/*.json")))}
    stories = {s["story_key"] for s in specs.values()}
    if len(stories) < 24:
        raise SystemExit(f"REFUSED: confirmatory bank has {len(stories)} stories (< 24; D31)")
    A = sorted((s for s in specs if specs[s]["hidden_state"] == "A"), key=lambda s: E.seed_of("conf-cluster-order", "A", s))
    Bs = sorted((s for s in specs if specs[s]["hidden_state"] == "B"), key=lambda s: E.seed_of("conf-cluster-order", "B", s))
    seq = [x for pair in zip(A, Bs) for x in pair]
    assert len(seq) == 52
    clusters = []
    for j in range(1, N_CLUSTERS + 1):
        sid = seq[(j - 1) % 52]; spec = specs[sid]
        alloc = M.draw(spec, f"conf-alloc|{j}")
        indptr, nbr, info = sim.rrg(100, 4, E.seed_of("conf-graph", j))
        arms = {"T1": B.unif("conf-arm", "T1", j) < SHARES["T1"], "rule_ii": B.unif("conf-arm", "rule_ii", j) < SHARES["rule_ii"],
                "self_reset_saved_state_0": B.unif("conf-arm", "self-reset", j, 0) < SHARES["self_reset"],
                "variant_wordings": {m: [w for w in ws if B.unif("conf-arm", f"wording:{m}:{w}", j) < SHARES["variant_wording"]]
                                     for m, ws in VALID_VARIANTS.items()}}
        clusters.append({"cluster": j, "scenario_id": sid, "story_key": spec["story_key"], "truth": spec["hidden_state"],
                         "spec": spec, "alloc": alloc, "graph": info, "adj": [nbr[indptr[i]:indptr[i + 1]].tolist() for i in range(100)],
                         "run_key": f"CONF-c{j}", "start_block": math.ceil(j / 4), "arms": arms})
    blob = json.dumps(clusters, sort_keys=True, separators=(",", ":"))
    d = ROOT / "gates/S10/clusters"; d.mkdir(parents=True, exist_ok=True)
    (d / "confirmatory_clusters.json").write_text(blob)
    man = {"n_clusters": N_CLUSTERS, "seed_rule": "gates/S2/CONFIRMATORY_SEED_RULE.md (D29)", "shares": SHARES,
           "confirmatory_bank_manifest_sha256": hashlib.sha256((ROOT / "gates/S2/banks/MANIFEST.json").read_bytes()).hexdigest(),
           "confirmatory_clusters_json_sha256": hashlib.sha256(blob.encode()).hexdigest(),
           "stories_used": len({c["story_key"] for c in clusters}), "specs_used": len({c["scenario_id"] for c in clusters}),
           "truth_balance": {"A": sum(c["truth"] == "A" for c in clusters), "B": sum(c["truth"] == "B" for c in clusters)},
           "all_solvable": all(c["alloc"]["solvable"] for c in clusters), "replaced_draws": sum(len(c["alloc"].get("replaced_seeds", [])) for c in clusters),
           "informed_positions": sorted({c["alloc"]["informed_positions"] for c in clusters}),
           "graphs_regular_connected": all(c["graph"]["regular"] and c["graph"]["connected"] and c["graph"]["simple"] for c in clusters),
           "start_blocks": max(c["start_block"] for c in clusters),
           "arm_counts": {"T1": sum(c["arms"]["T1"] for c in clusters), "rule_ii": sum(c["arms"]["rule_ii"] for c in clusters),
                          "self_reset": sum(c["arms"]["self_reset_saved_state_0"] for c in clusters),
                          "variant_runs": {m: sum(len(c["arms"]["variant_wordings"][m]) for c in clusters) for m in VALID_VARIANTS}},
           "clusters": [{"cluster": c["cluster"], "scenario_id": c["scenario_id"], "allocation_sha256": c["alloc"]["sha256"],
                         "graph_fingerprint": c["graph"]["fingerprint"], "start_block": c["start_block"]} for c in clusters],
           "never_reused": "pilot (S8) clusters and development allocations are disjoint from these (D27)"}
    (d / "MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "clusters"}, indent=1))


if __name__ == "__main__":
    main()
