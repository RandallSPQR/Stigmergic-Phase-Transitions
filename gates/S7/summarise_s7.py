"""Summarise the S7 GPU run (gates/S7/S7_PLAN.md).  python gates/S7/summarise_s7.py gates/S7/artifacts/<run>"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ["C1_main_identical", "C2_final_state_identical", "C3_unpulsed_branch_equals_main_continuation", "C4_pulse_ok",
        "C6_save_restore", "C7_live_blind_initial_identical", "C7_live_blind_same_agents_and_draws"]
MODELS = ("llama-3.1-8b-it", "gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b")
out = {"plan": "gates/S7/S7_PLAN.md", "models": {}}
for f in sorted(glob.glob(str(Path(sys.argv[1]) / "s7_*_start1.json"))):
    d = json.load(open(f)); m = d["manifest"]["model"]; ck = d["checks"]
    out["models"][m] = {"server_start": d["manifest"]["server_start"]["id"], "model_calls": d["manifest"]["model_calls"],
                        "T": d["manifest"]["T"], **{k: ck.get(k) for k in KEYS}, "letter_share": ck["C9_letter_mapping_A_as_A_share"],
                        "probes": ck["C5_probes_run"], "pulse": ck["C4_pulse"], "base_vs_again_identical": ck["base_vs_again_identical"],
                        "main_sha": d["base"]["main_sha"]}
    M = out["models"][m]
    M["pass"] = all(M[k] for k in KEYS) and M["letter_share"] == 0.5 and M["base_vs_again_identical"]
out["all_five_present"] = all(m in out["models"] for m in MODELS)
out["pass"] = out["all_five_present"] and all(M["pass"] for M in out["models"].values())
(ROOT / "gates/S7/results/s7_gpu_summary.json").write_text(json.dumps(out, indent=1))
for m, M in out["models"].items():
    print(m, "pass", M["pass"], {k: M[k] for k in KEYS}, "calls", M["model_calls"])
print("S7 GPU pass:", out["pass"])
