"""S10 confirmatory analysis, exactly as registered (osf/PREREGISTRATION.md §5; D65 step 2).

Runs only frozen/registered functions: secondary.require_unblinding (D65 and tag stpt-secondary-v1),
secondary.load_records (guarded loader), confirmatory.outcomes (full recomputation of each record) and
confirmatory.primary (both contrasts pooled over the four confirmatory models; REML with the server-start block random
effect; Satterthwaite df; Holm across the two; TOST at +/-0.03; generalisation reported beside). Nothing else.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path("/home/user/stigmergic-phase-transitions")
COORD = Path("/home/user/stpt-mp-coordination")
DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(REPO / "gates/S10/analysis"))
import confirmatory as CA  # noqa: E402
import secondary as S  # noqa: E402

FINAL_CORE = {"gemma-2-9b-it": "20261107T2359Z", "qwen3.5-9b": "20261108T1439Z",
              "gemma-3-27b-it": "20261108T1722Z", "qwen3.5-27b": "20261109T0504Z"}
assert list(FINAL_CORE) == CA.CONF

gate = S.require_unblinding(COORD, "D65")
runs = {m: [str(DATA / "stpt/S10" / r)] for m, r in FINAL_CORE.items()}
records = S.load_records(runs, COORD, "D65")
if sorted(records) != sorted((m, j, "primary") for m in CA.CONF for j in range(1, 62)):
    raise SystemExit("records are not exactly the 4 x 61 primary-arm runs")

table, missing = {}, {}
for (m, j, a), r in sorted(records.items()):
    rec = {k: v for k, v in r.items() if k != "_manifest"}          # the record as uploaded
    table[(m, j)] = CA.outcomes(rec)                                   # verify_record + outcomes (frozen)
    mm = missing.setdefault(m, {"init": 0, "live": 0, "blind": 0, "pulsed": 0, "self_reset": 0})
    mm["init"] += sum(x[5] for x in rec["init"])
    mm["live"] += sum(x[7] for x in rec["live"])
    mm["blind"] += sum(x[7] for x in rec["blind"])
    mm["pulsed"] += sum(x[7] for p in rec.get("pulses") or [] for x in p["rows"])
    mm["self_reset"] += sum(x[7] for x in (rec.get("self_reset") or {}).get("rows") or [])

res = CA.primary(table)                                                # the registered confirmatory analysis


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    return x


out = {"analysis": "S10 confirmatory analysis, as registered (osf/PREREGISTRATION.md section 5)",
       "functions": ["confirmatory.outcomes", "confirmatory.primary"],
       "unblinding": {"decision": "D65", **gate},
       "runs": {m: f"stpt/S10/{r}" for m, r in FINAL_CORE.items()},
       "records": len(table), "missing_calls_by_model_and_condition": missing,
       "constants": {"equivalence_bound": CA.BOUND, "family_alpha": CA.FAMILY_ALPHA, "tost_alpha": CA.TOST_ALPHA},
       "result": clean(res)}
OUT.write_text(json.dumps(out, indent=1))
print(f"written {OUT}")
