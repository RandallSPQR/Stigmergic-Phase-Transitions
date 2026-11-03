"""Addendum 1, evidence per finding: each defect demonstrated on the registered code (commit cb10726) and its absence
on the fixed code. CPU only, mock model; reads the old files with `git show`, imports them under other names.

  python osf/addendum1/before_after.py -> osf/addendum1/before_after.json
"""
import copy
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S7"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as NEW_CA  # noqa: E402
import s10_core as NEW  # noqa: E402
import s7_core  # noqa: E402
from stpt import board as B  # noqa: E402

REG = "cb10726e3d359d8094fbd083f336453d6af9280d"
tmp = Path(tempfile.mkdtemp())


def old(path, name):
    src = subprocess.run(["git", "-C", str(ROOT), "show", f"{REG}:{path}"], capture_output=True, text=True, check=True).stdout
    f = tmp / f"{name}.py"; f.write_text(src)
    spec = importlib.util.spec_from_file_location(name, f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


OLD = old("gates/S10/s10_core.py", "s10_core_registered")
OLD_CA = old("gates/S10/analysis/confirmatory.py", "confirmatory_registered")
F = NEW.load_clusters()
M = "gemma-2-9b-it"; T = NEW.primary_T(M)
SMALL = {"H": 12, "t0": 5, "D": 3, "W": 2, "r": 10, "k": 3}
out = {"doc": __doc__, "registered_commit": REG}


def accepted(fn, *a, **k):
    try:
        fn(*a, **k); return True
    except Exception:  # noqa: BLE001
        return False


class Count(s7_core.MockKernel):
    pass


# #1 uninformed first votes: model calls at the initial state
c = F[5]; k_old = Count(); k_new = Count()
r_old = OLD.run_cluster(c, T, k_old, SMALL)
r_new = NEW.run_cluster(c, M, k_new, SMALL)
informed = sum(1 for ids in c["alloc"]["holders"].values() if ids)
out["1_initial_vote"] = {"informed_agents": informed,
                         "registered_code_init_calls": len(r_old["init"]),
                         "fixed_code_init_calls": sum(x[3] for x in r_new["init"]),
                         "fixed_uninformed_first_vote_equals_placeholder": all(
                             r_new["initial_votes"][x[0]] == x[1] for x in r_new["init"] if x[3] == 0)}

# #2 run shape: malformed records accepted by the registered extraction
full = NEW.run_cluster(F[2], M, s7_core.MockKernel())
full["server_start_ids"] = {n: "s" for n in NEW.branch_names(F[2], M, "primary")}
truth = F[2]["truth"]


def mutate(case):
    b = copy.deepcopy(full)
    if case == "both_runs_truncated_to_2900":
        b["live"], b["blind"] = b["live"][:2900], b["blind"][:2900]
    elif case == "one_pulsed_branch":
        b["pulses"] = b["pulses"][:1]
    elif case == "same_direction_twice":
        b["pulses"][1]["direction"] = b["pulses"][0]["direction"]
    elif case == "duplicate_recipient":
        b["pulses"][0]["recipients"][1] = b["pulses"][0]["recipients"][0]
    elif case == "pulsed_rows_truncated":
        b["pulses"][0]["rows"] = b["pulses"][0]["rows"][:500]
    elif case == "nan_draw":
        b["live"][7][6] = float("nan"); b["blind"][7][6] = float("nan")
    return b


cases = ["both_runs_truncated_to_2900", "one_pulsed_branch", "same_direction_twice", "duplicate_recipient",
         "pulsed_rows_truncated", "nan_draw"]
out["2_run_shape"] = {cs: {"registered_code_accepts": accepted(OLD_CA.outcomes, mutate(cs), truth),
                           "fixed_code_accepts": accepted(NEW_CA.outcomes, mutate(cs), truth)} for cs in cases}


# #3 primary(): caller metadata, non-primary arms, NaN, universe
def table(models=OLD_CA.CONF):
    t = {}
    for m in models:
        for j in range(1, 62):
            t[(m, j)] = {"identity": {"model": m, "cluster": j, "arm": "primary", "T": NEW_CA.primary_T(m), "wording": "w3",
                                      "init_wording": "w3", "rule": "i", "run_key": f"CONF-c{j}", "prm": NEW_CA.PRM, "mock": False},
                         "server_start": f"{m}/start{F[j]['start_block']}", "board": 0.01 * ((j * 7) % 5 - 2),
                         "persistence": 0.01 * ((j * 3) % 5 - 2)}
    return t


meta = {j: {"start_block": F[j]["start_block"], "story_key": F[j]["story_key"]} for j in F}
res = {}
t = table(); t[("qwen3.5-9b", 7)]["identity"].update({"arm": "T1", "T": 1.0})
res["T1_entry_in_primary_table"] = (accepted(OLD_CA.primary, t, meta, generalisation=False), accepted(NEW_CA.primary, t, generalisation=False))
t = table(); t[("qwen3.5-9b", 7)]["board"] = float("nan")
res["nan_outcome"] = (accepted(OLD_CA.primary, t, meta, generalisation=False), accepted(NEW_CA.primary, t, generalisation=False))
m60 = {j: v for j, v in meta.items() if j != 61}
res["caller_metadata_drops_a_cluster"] = (accepted(OLD_CA.primary, table(), m60, generalisation=False), accepted(NEW_CA.primary, table(), m60))
fake = {j: {"start_block": 1, "story_key": v["story_key"]} for j, v in meta.items()}
o1 = OLD_CA.primary(table(), meta, generalisation=False)["board"]["conditional"]["df"]
o2 = OLD_CA.primary(table(), fake, generalisation=False)["board"]["conditional"]["df"]
res["caller_block_labels_change_the_test"] = {"registered_df_with_scheduled_blocks": o1, "registered_df_with_caller_blocks_all_one": o2,
                                              "fixed_code_takes_caller_blocks": accepted(NEW_CA.primary, table(), fake)}
t = table(); t[("qwen3.5-9b", 7)]["identity"]["mock"] = True
res["mock_entry"] = (None, accepted(NEW_CA.primary, t, generalisation=False))
out["3_primary"] = {k: ({"registered_code_accepts": v[0], "fixed_code_accepts": v[1]} if isinstance(v, tuple) else v) for k, v in res.items()}

# #5 placeholder balance per start block x evidence group
worst_old = worst_new = 0
for blk in sorted({c["start_block"] for c in F.values()}):
    cs = [x for x in F.values() if x["start_block"] == blk]
    new_ph = NEW.block_placeholders(cs)
    tot_old, tot_new = Counter(), Counter()
    for x in cs:
        b = NEW.make_board(x["spec"], x["alloc"], x["adj"], x["run_key"], False, 1.0)
        old_ph = B.placeholder_votes(b)
        for g, mem in NEW._groups(x).items():
            tot_old[g] += sum(1 if old_ph[i] == "A" else -1 for i in mem)
            tot_new[g] += sum(1 if new_ph[x["cluster"]][i] == "A" else -1 for i in mem)
    worst_old = max(worst_old, max(abs(v) for v in tot_old.values())); worst_new = max(worst_new, max(abs(v) for v in tot_new.values()))
out["5_placeholders"] = {"registered_max_block_imbalance_A_minus_B": worst_old, "fixed_max_block_imbalance": worst_new}

# #6 arms: the registered runner ignores c["arms"]
off = next(x for x in F.values() if not x["arms"]["self_reset_saved_state_0"] and not x["arms"]["T1"])
r = OLD.run_cluster(off, T, s7_core.MockKernel(), SMALL)
out["6_arms"] = {"registered_runs_self_reset_when_not_drawn": r["self_reset"] is not None,
                 "registered_runs_T1_when_not_drawn": accepted(OLD.run_cluster, off, 1.0, s7_core.MockKernel(), SMALL),
                 "fixed_runs_self_reset_when_not_drawn": NEW.run_cluster(off, M, s7_core.MockKernel(), SMALL)["self_reset"] is not None,
                 "fixed_runs_T1_when_not_drawn": accepted(NEW.run_cluster, off, M, s7_core.MockKernel(), SMALL, arm="T1")}

# #7 initial call wording in a variant arm
m = "gemma-3-27b-it"; Tm = NEW.primary_T(m)
cv = next(x for x in F.values() if x["arms"]["variant_wordings"][m]); w = cv["arms"]["variant_wordings"][m][0]
ro_p = OLD.run_cluster(cv, Tm, s7_core.MockKernel(), SMALL); ro_v = OLD.run_cluster(cv, Tm, s7_core.MockKernel(), SMALL, wording=w)
rn_p = NEW.run_cluster(cv, m, s7_core.MockKernel(), SMALL); rn_v = NEW.run_cluster(cv, m, s7_core.MockKernel(), SMALL, arm=f"wording:{w}")
out["7_initial_wording"] = {"variant": w, "registered_init_prompts_equal_W3": ro_p["init_sha"] == ro_v["init_sha"],
                            "fixed_init_prompts_equal_W3": rn_p["init_sha"] == rn_v["init_sha"]}

(ROOT / "osf/addendum1/before_after.json").write_text(json.dumps(out, indent=1, default=lambda x: x if not isinstance(x, float) or math.isfinite(x) else str(x)) + "\n")
print(json.dumps({k: v for k, v in out.items() if k not in ("doc",)}, indent=1))
