"""Gate S7, CPU part (gates/S7/S7_PLAN.md): branch isolation with a deterministic mock model.

  python gates/S7/run_s7_cpu.py  -> gates/S7/results/s7_cpu.json, gates/S7/inputs/s7_inputs.json (graph + allocation for the pod)
"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates" / "S7"))
from stpt import board as B, evidence as E, sim  # noqa: E402
import s7_core as C  # noqa: E402

CPU = {"H": 400, "probe_every": 10, "branches": [100, 250], "branch_len": 100,
       "pulse": {"r": 5, "k": 2, "toward": "A", "duration": 30}}


def inputs():
    bank = ROOT / "gates/S2/banks/development"
    allocs = sorted(glob.glob(str(bank / "allocations/*.json")))
    alloc = next(a for a in (json.load(open(f)) for f in allocs)
                 if a["kind"] == "representative" and all(len(ids) <= 1 for ids in a["holders"].values()))   # one report per position
    spec = json.load(open(bank / f"{alloc['scenario_id']}.json"))
    indptr, nbr, info = sim.rrg(100, 4, E.seed_of("S7-graph-v1"))
    adj = [nbr[indptr[i]:indptr[i + 1]].tolist() for i in range(100)]
    return {"spec": spec, "alloc": alloc, "adj": adj, "graph": info}


def main():
    inp = inputs()
    (ROOT / "gates/S7/inputs").mkdir(parents=True, exist_ok=True)
    (ROOT / "gates/S7/inputs/s7_inputs.json").write_text(json.dumps(inp, sort_keys=True))
    res = {"plan": "gates/S7/S7_PLAN.md", "params": CPU, "graph": inp["graph"], "allocation": inp["alloc"]["sha256"], "rules": {}}
    for rule in ("i", "ii"):
        mk = lambda live: C.make_board(inp["spec"], inp["alloc"], inp["adj"], f"S7-cpu-{rule}", live, 1.0)
        bl, bb = mk(True), mk(False)
        K = C.MockKernel()
        base = C.scenario(bl, K, CPU["H"], rule)
        again = C.scenario(bl, C.MockKernel(), CPU["H"], rule)
        probes_only = C.scenario(bl, K, CPU["H"], rule, probe_every=CPU["probe_every"])
        branches_only = C.scenario(bl, K, CPU["H"], rule, branches=CPU["branches"], branch_len=CPU["branch_len"], pulse=CPU["pulse"])
        full = C.scenario(bl, K, CPU["H"], rule, probe_every=CPU["probe_every"], branches=CPU["branches"],
                          branch_len=CPU["branch_len"], pulse=CPU["pulse"])
        blind = C.scenario(bb, K, CPU["H"], rule)
        ck = C.checks(base, full, others=(probes_only, branches_only, again), blind=blind, board=bl, kernel=K)
        if rule == "i":
            ph = B.placeholder_votes(bl)
            groups = Counter()
            for i in range(bl.N):
                groups[((bl.private[i] is not None), bl.accuracy[i], bl.favours[i], ph[i])] += 1
            keys = {k[:3] for k in groups}
            ck["C8_placeholder_imbalance_max"] = max(abs(groups[(*k, "A")] - groups[(*k, "B")]) for k in keys)
            ck["C8_placeholder_groups"] = len(keys)
        else:
            init_votes = [r for r in base["main"] if r["kind"] == "init"]
            ck["C8_rule_ii_no_model_calls_at_init"] = len(init_votes) == 0
        blind_prompts_ok = all(r["shown"] is None for r in blind["main"] if r["kind"] == "update")
        ck["C7_blind_shows_no_contacts"] = blind_prompts_ok
        ck["main_sha"] = base["main_sha"]
        res["rules"][rule] = ck
    ok = all(r["C1_main_identical"] and r["C2_final_state_identical"] and r["C3_unpulsed_branch_equals_main_continuation"]
             and r["C4_pulse_ok"] and r.get("C6_save_restore", True) and r.get("C7_live_blind_initial_identical", True)
             and r["C7_blind_shows_no_contacts"] for r in res["rules"].values())
    ok = ok and res["rules"]["i"]["C8_placeholder_imbalance_max"] <= 1 and all(r["C9_letter_mapping_A_as_A_share"] == 0.5 for r in res["rules"].values())
    # negative control: a kernel that carries state across calls must be caught by C1/C3
    bl = C.make_board(inp["spec"], inp["alloc"], inp["adj"], "S7-cpu-i", True, 1.0)
    lb = C.scenario(bl, C.LeakyKernel(), CPU["H"], "i")
    lf = C.scenario(bl, C.LeakyKernel(), CPU["H"], "i", probe_every=CPU["probe_every"], branches=CPU["branches"],
                    branch_len=CPU["branch_len"], pulse=CPU["pulse"])
    lc = C.checks(lb, lf)
    res["negative_control_leaky_kernel"] = {"C1_main_identical": lc["C1_main_identical"],
                                            "C3_unpulsed_branch_equals_main_continuation": lc["C3_unpulsed_branch_equals_main_continuation"],
                                            "detected": not lc["C1_main_identical"] and not lc["C3_unpulsed_branch_equals_main_continuation"]}
    ok = ok and res["negative_control_leaky_kernel"]["detected"]
    res["pass"] = ok
    (ROOT / "gates/S7/results").mkdir(parents=True, exist_ok=True)
    (ROOT / "gates/S7/results/s7_cpu.json").write_text(json.dumps(res, indent=1))
    for rule, r in res["rules"].items():
        print(rule, {k: v for k, v in r.items() if k not in ("C4_pulse", "main_sha")})
        print("   pulse", r["C4_pulse"])
    print("CPU S7 pass:", ok)


if __name__ == "__main__":
    main()
