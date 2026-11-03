"""Validation of the confirmatory analysis on synthetic data (brief: analysis code validated before real data; S10).

  python gates/S10/analysis/validate_confirmatory.py -> gates/S10/results/analysis_validation.json
Criteria, fixed before the run:
  A. Extraction (pilot-style clusters from gates/S8/inputs, mock model, the real record format):
     A1 window outcome equals an independent recomputation from the harness state (exact);
     A2 tampered live/blind pairing is refused; A3 a tampered pulsed branch is refused.
  B. Inference (synthetic datasets on the confirmatory cluster layout: 61 clusters, 16 start blocks, 26 stories;
     per-model SD = the S9 sizing SDs; 1,000 datasets per scenario):
     B1 type I error at theta = 0, conditional, two-sided alpha 0.025: within [0.013, 0.037] (alpha 0.05: [0.035, 0.065]);
     B2 Holm family-wise error with both contrasts null: <= 0.06;
     B3 sign recovery at theta = +/-0.05: significant with the correct sign >= 0.95; wrong sign significant <= 0.002;
     B4 95% CI coverage of the bank mean (conditional): within [0.93, 0.97];
     B5 TOST passes at theta = 0 at a rate >= 0.85 (both contrasts; S9 expects >= 0.95);
     B6 generalisation CI coverage of theta with story SD 0.02: within [0.92, 0.98];
     scenarios: rho in {0.3, 1.0}; start-block SD in {0, 0.01}.
Revised after the independent execution review of cb10726 (addendum 1): primary() now takes no cluster metadata. Each
synthetic entry carries the primary-arm identity and a server-start ID per model that follows the frozen schedule
(blocks of 4); the random draws and the criteria are unchanged, so the results should equal validation run 2.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S10/analysis")); sys.path.insert(0, str(ROOT / "gates/S8"))
sys.path.insert(0, str(ROOT / "gates/S7"))
import confirmatory as CA  # noqa: E402
import s8_core  # noqa: E402
import s7_core  # noqa: E402
from stpt import board as B  # noqa: E402

out = {"doc": __doc__, "A": {}, "B": {}}
t0 = time.time()

# ---------------- A: extraction ----------------
clusters = json.load(open(ROOT / "gates/S8/inputs/clusters.json"))
prm = {"H": 30, "t0": 5, "D": 3, "W": 5, "r": 10, "k": 3}
c = next(x for x in clusters if x["rule"] == "i")
res = s8_core.run_cluster(c, 1.0, s7_core.MockKernel(), prm)
truth = c["spec"]["hidden_state"]
o = CA.outcomes(res, truth)
# independent recomputation via the harness state
live = s8_core.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, 1.0)
blind = s8_core.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], False, 1.0)
st0, _ = B.initial_state(live, s7_core.MockKernel(), "i")
sl, sb = B.branch(st0), B.branch(st0)
yl, yb = [], []
for sweep in range(1, 31):
    for _ in range(100):
        B.update(live, sl, s7_core.MockKernel()); B.update(blind, sb, s7_core.MockKernel())
    if 25 <= sweep <= 30:
        yl.append(sum(v == truth for v in sl.votes) / 100); yb.append(sum(v == truth for v in sb.votes) / 100)
out["A"]["A1_window_outcome_exact"] = bool(abs(o["Y_live"] - np.mean(yl)) < 1e-12 and abs(o["Y_blind"] - np.mean(yb)) < 1e-12)
bad = copy.deepcopy(res); bad["blind"][100][1] = (bad["blind"][100][1] + 1) % 100
try:
    CA.outcomes(bad, truth); out["A"]["A2_bad_pairing_refused"] = False
except ValueError:
    out["A"]["A2_bad_pairing_refused"] = True
bad = copy.deepcopy(res); bad["pulses"][0]["rows"][10][6] = 0.123
try:
    CA.outcomes(bad, truth); out["A"]["A3_bad_branch_refused"] = False
except ValueError:
    out["A"]["A3_bad_branch_refused"] = True
out["A"]["pass"] = all(out["A"].values())
print("A", out["A"], round(time.time() - t0), "s", flush=True)

# ---------------- B: inference ----------------
man = json.load(open(ROOT / "gates/S10/clusters/MANIFEST.json"))
cl = json.load(open(ROOT / "gates/S10/clusters/confirmatory_clusters.json"))
meta = {x["cluster"]: {"start_block": x["start_block"], "story_key": x["story_key"]} for x in cl}
J = sorted(meta); blocks = np.array([meta[j]["start_block"] for j in J]); stories = [meta[j]["story_key"] for j in J]
story_idx = {s: k for k, s in enumerate(sorted(set(stories)))}; sidx = np.array([story_idx[s] for s in stories])
sizing = json.load(open(ROOT / "gates/S9/results/s9_tiers.json"))["sizing"]["rho1"]
SD = {"board": sizing["board_window"]["sizing_sd"], "persistence": sizing["persistence"]["sizing_sd"]}
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
OUT = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "gates/S10/results/analysis_validation.json")
IDENT = {m: {"arm": "primary", "T": CA.primary_T(m), "wording": "w3", "init_wording": "w3", "rule": "i", "prm": CA.PRM,
             "mock": False} for m in CA.CONF}
assert all(CA.frozen_universe()[j]["story"] == meta[j]["story_key"] for j in J), "manifest stories differ from the cluster file"
rng = np.random.Generator(np.random.PCG64(20261103))


def dataset(theta, rho, sd_block, sd_story):
    """Per-model, per-cluster values for both contrasts; returns table and the bank mean per contrast."""
    table, bank_mean = {}, {}
    for k, contrast in enumerate(("board", "persistence")):
        s = SD[contrast]; sa = s * np.sqrt(rho); se = s * np.sqrt(1 - rho)
        a = rng.normal(0, sa, len(J)); bl = rng.normal(0, sd_block, blocks.max() + 1); stv = rng.normal(0, sd_story, len(story_idx))
        base = theta[k] + a + bl[blocks] + stv[sidx]
        bank_mean[contrast] = theta[k] + float(stv[sidx].mean())
        for m in CA.CONF:
            y = base + rng.normal(0, se, len(J))
            for jj, j in enumerate(J):
                e = table.setdefault((m, j), {"identity": {**IDENT[m], "model": m, "cluster": j, "run_key": f"CONF-c{j}"},
                                              "server_start": f"{m}/synthetic-start{meta[j]['start_block']}"})
                e[contrast] = float(y[jj])
    return table, bank_mean


scen = []
for rho in (0.3, 1.0):
    for sdb in (0.0, 0.01):
        scen.append({"rho": rho, "sd_block": sdb})
res_B = {}
for sc in scen:
    key = f"rho={sc['rho']},block_sd={sc['sd_block']}"
    r = {"null": {"rej025": {"board": 0, "persistence": 0}, "rej05": {"board": 0, "persistence": 0}, "fwer": 0, "tost": {"board": 0, "persistence": 0}},
         "pos": {"right": 0, "wrong": 0}, "neg": {"right": 0, "wrong": 0}, "cover": 0}
    for _ in range(REPS):
        tab, _ = dataset((0.0, 0.0), sc["rho"], sc["sd_block"], 0.0)
        P = CA.primary(tab, generalisation=False)
        for ctr in ("board", "persistence"):
            p = P[ctr]["conditional"]["p_two_sided"]
            r["null"]["rej025"][ctr] += p < 0.025; r["null"]["rej05"][ctr] += p < 0.05
            r["null"]["tost"][ctr] += P[ctr]["conditional"]["tost_equivalent"]
        r["null"]["fwer"] += P["board"]["holm_significant"] or P["persistence"]["holm_significant"]
    for sign, lab in ((1, "pos"), (-1, "neg")):
        for _ in range(REPS // 2):
            tab, _ = dataset((0.05 * sign, 0.05 * sign), sc["rho"], sc["sd_block"], 0.0)
            P = CA.primary(tab, generalisation=False)
            for ctr in ("board", "persistence"):
                th = P[ctr]["conditional"]["theta"]; sig = P[ctr]["holm_significant"]
                r[lab]["right"] += sig and np.sign(th) == sign; r[lab]["wrong"] += sig and np.sign(th) != sign
    for _ in range(REPS // 2):
        tab, bm = dataset((0.02, 0.02), sc["rho"], sc["sd_block"], 0.0)
        P = CA.primary(tab, generalisation=False)
        lo, hi = P["board"]["conditional"]["ci95"]; r["cover"] += lo <= bm["board"] <= hi
    n_null = REPS
    res_B[key] = {"type1_alpha025": {k: v / n_null for k, v in r["null"]["rej025"].items()},
                  "type1_alpha05": {k: v / n_null for k, v in r["null"]["rej05"].items()},
                  "holm_fwer": r["null"]["fwer"] / n_null, "tost_pass_at_0": {k: v / n_null for k, v in r["null"]["tost"].items()},
                  "sign_correct_at_0.05": (r["pos"]["right"] + r["neg"]["right"]) / (2 * REPS), "sign_wrong_at_0.05": (r["pos"]["wrong"] + r["neg"]["wrong"]) / (2 * REPS),
                  "ci95_coverage_bank_mean": r["cover"] / (REPS // 2)}
    print(key, res_B[key], round(time.time() - t0), "s", flush=True)
# B6: generalisation coverage with story SD 0.02 (rho 1, block SD 0.01)
cov = 0
for _ in range(REPS // 2):
    tab, _ = dataset((0.02, 0.02), 1.0, 0.01, 0.02)
    P = CA.primary(tab)
    lo, hi = P["board"]["generalisation"]["ci95"]; cov += lo <= 0.02 <= hi
res_B["generalisation_coverage_story_sd_0.02"] = cov / (REPS // 2)
out["B"] = res_B
crit = []
for key, v in res_B.items():
    if not isinstance(v, dict):
        continue
    crit += [0.013 <= v["type1_alpha025"][k] <= 0.037 for k in v["type1_alpha025"]]
    crit += [0.035 <= v["type1_alpha05"][k] <= 0.065 for k in v["type1_alpha05"]]
    crit += [v["holm_fwer"] <= 0.06, v["sign_correct_at_0.05"] >= 0.95, v["sign_wrong_at_0.05"] <= 0.002,
             0.93 <= v["ci95_coverage_bank_mean"] <= 0.97, min(v["tost_pass_at_0"].values()) >= 0.85]
crit.append(0.92 <= res_B["generalisation_coverage_story_sd_0.02"] <= 0.98)
out["B_pass"] = all(crit)
out["pass"] = out["A"]["pass"] and out["B_pass"]
out["seconds"] = round(time.time() - t0, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=1, default=float))
print("generalisation coverage", res_B["generalisation_coverage_story_sd_0.02"], "| pass", out["pass"], "| seconds", out["seconds"])
