"""Check of the hand-implemented REML + Satterthwaite (gates/S10/analysis/confirmatory.py) against closed forms (owner,
S10): balanced one-way random-intercept design, a = 16 blocks x b = 4. Classical results:
  interior (between-block mean square MSB > within MSW): REML theta = grand mean; SE^2 = MSB / (a b); Satterthwaite df =
  a - 1 = 15; the test equals the one-sample t-test on the block means.
  boundary (MSB <= MSW): REML block variance = 0; theta = grand mean; SE^2 = s^2 / (a b) (pooled); df = a b - 1; the
  test equals the ordinary one-sample t-test on all values.
  python gates/S10/analysis/reml_classical_check.py -> gates/S10/results/reml_classical_check.json
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "gates/S10/analysis"))
import confirmatory as CA  # noqa: E402

a, b = 16, 4
blocks = np.repeat(np.arange(a), b)
rng = np.random.default_rng(20261103)
rows = []
for k in range(60):
    sdb = 0.03 if k < 40 else 0.0
    y = 0.01 + rng.normal(0, sdb, a)[blocks] + rng.normal(0, 0.04, a * b)
    bm = y.reshape(a, b).mean(1)
    msb = b * bm.var(ddof=1); msw = ((y.reshape(a, b) - bm[:, None]) ** 2).sum() / (a * (b - 1))
    r = CA.infer(y, blocks)
    if msb > msw:
        se_c, df_c = math.sqrt(msb / (a * b)), a - 1
        p_c = stats.ttest_1samp(bm, 0).pvalue; case = "interior"
    else:
        se_c, df_c = y.std(ddof=1) / math.sqrt(a * b), a * b - 1
        p_c = stats.ttest_1samp(y, 0).pvalue; case = "boundary"
    rows.append({"case": case, "theta_reml": r["theta"], "theta_classical": float(y.mean()), "se_reml": r["se"], "se_classical": se_c,
                 "df_reml": r["df"], "df_classical": df_c, "p_reml": float(r["p_two_sided"]), "p_classical": float(p_c)})
out = {"doc": __doc__, "n": len(rows), "cases": {c: sum(x["case"] == c for x in rows) for c in ("interior", "boundary")}}
for c in ("interior", "boundary"):
    R = [x for x in rows if x["case"] == c]
    if R:
        out[c] = {"max_abs_theta_diff": max(abs(x["theta_reml"] - x["theta_classical"]) for x in R),
                  "max_rel_se_diff": max(abs(x["se_reml"] / x["se_classical"] - 1) for x in R),
                  "max_abs_df_diff": max(abs(x["df_reml"] - x["df_classical"]) for x in R),
                  "max_abs_p_diff": max(abs(x["p_reml"] - x["p_classical"]) for x in R)}
# criteria (fixed here): theta within 1e-9; SE within 1e-3 relative; df within 0.05; p within 1e-3
out["pass"] = all(out[c]["max_abs_theta_diff"] < 1e-9 and out[c]["max_rel_se_diff"] < 1e-3 and out[c]["max_abs_df_diff"] < 0.05
                  and out[c]["max_abs_p_diff"] < 1e-3 for c in ("interior", "boundary") if c in out)
out["rows"] = rows
(ROOT / "gates/S10/results/reml_classical_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k not in ("rows", "doc")}, indent=1))
