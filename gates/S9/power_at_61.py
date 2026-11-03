"""Power at the chosen size (D31): 61 clusters, rho = 1, primary board outcome = mean over sweeps 25-30.
python gates/S9/power_at_61.py -> gates/S9/results/power_at_61.json (from the sizing SDs in results/s9_tiers.json)."""
import json
import math
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
t = json.load(open(ROOT / "gates/S9/results/s9_tiers.json"))["sizing"]["rho1"]
n, BOUND, REF = 61, 0.03, 0.05
zmde = stats.norm.ppf(1 - 0.025 / 2) + stats.norm.ppf(0.8)
out = {"n_clusters": n, "rho": 1, "sizing_sd": {k: v["sizing_sd"] for k, v in t.items()}, "conditional": {}, "generalisation_story_sd": {}}
for lab, key in (("board_window_25_30", "board_window"), ("board_final_sweep", "board_final"), ("persistence", "persistence")):
    se = t[key]["sizing_sd"] / math.sqrt(n)
    out["conditional"][lab] = {"se": se, "mde_80": zmde * se,
                               "power_at_0.05_alpha025": float(stats.norm.cdf(REF / se - stats.norm.ppf(1 - 0.0125))),
                               "tost_power_alpha05": float(2 * stats.norm.cdf(BOUND / se - stats.norm.ppf(0.95)) - 1),
                               "tost_power_alpha025": float(2 * stats.norm.cdf(BOUND / se - stats.norm.ppf(0.975)) - 1)}
    for tau in (0.02, 0.04):
        se_g = math.sqrt(t[key]["sizing_sd"] ** 2 / n + tau ** 2 / 26)
        out["generalisation_story_sd"].setdefault(str(tau), {})[lab] = {
            "mde_80": zmde * se_g, "tost_power_alpha05": float(max(0, 2 * stats.norm.cdf(BOUND / se_g - stats.norm.ppf(0.95)) - 1))}
(ROOT / "gates/S9/results/power_at_61.json").write_text(json.dumps(out, indent=1))
for k, v in out["conditional"].items():
    print(f"{k:20s} MDE {v['mde_80']:.4f}  power@0.05 {v['power_at_0.05_alpha025']:.3f}  TOST(.05) {v['tost_power_alpha05']:.3f}  TOST(.025) {v['tost_power_alpha025']:.3f}")
for tau, d in out["generalisation_story_sd"].items():
    print("story SD", tau, {k: (round(v["mde_80"], 4), round(v["tost_power_alpha05"], 3)) for k, v in d.items()})
