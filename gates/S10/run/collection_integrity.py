"""S10 collection integrity check for one model's core stage (no outcomes computed or shown).
  python -I gates/S10/run/collection_integrity.py MODEL FINAL_RUN_DIR [EARLIER_RUN_DIR ...]  (local copies of stpt/S10/<run>/)
Checks: every frozen cluster has exactly one primary record in the final run; each passes verify_record (full
recomputation); restored records are byte-identical to the run that produced them; each scheduled block ran in one
server start and no start is shared across blocks; missing calls; non-A/B mass; letter balance per start; ledger final;
DONE present; no stop files."""
import collections, gzip, hashlib, json, math, sys
from pathlib import Path
R = str(Path(__file__).resolve().parents[3])
sys.path[:0] = [R, R + "/gates/S10", R + "/gates/S10/analysis", R + "/gates/S10/run"]
import confirmatory as CA

MODEL, FINAL, EARLIER = sys.argv[1], Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]]
U = CA.frozen_universe()
out, problems = {"model": MODEL, "final_run": FINAL.name, "earlier_runs": [p.name for p in EARLIER]}, []
recs = {int(p.name.split("rec_c")[1].split("__")[0]): p for p in (FINAL / MODEL).glob("rec_c*__primary.json.gz")}
others = sorted(p.name for p in (FINAL / MODEL).glob("rec_*.json.gz") if not p.name.endswith("__primary.json.gz"))
if set(recs) != set(U): problems.append(f"clusters: missing {sorted(set(U) - set(recs))}, extra {sorted(set(recs) - set(U))}")
if others: problems.append(f"non-primary records in a core run: {others}")
origin = {}
for j, p in recs.items():
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    src = [e.name for e in EARLIER if (e / MODEL / p.name).exists() and hashlib.sha256((e / MODEL / p.name).read_bytes()).hexdigest() == h]
    diff = [e.name for e in EARLIER if (e / MODEL / p.name).exists() and e.name not in src]
    if diff: problems.append(f"cluster {j}: differs from the copy in {diff}")
    origin[j] = src[0] if src else FINAL.name
starts_by_block, block_of_start = collections.defaultdict(set), collections.defaultdict(set)
miss = calls = 0; masses = []; letters = collections.defaultdict(collections.Counter); arms = collections.Counter(); mock = 0
for j, p in sorted(recs.items()):
    rec = json.loads(gzip.decompress(p.read_bytes())); r = rec["result"]
    try: CA.verify_record(r)
    except BaseException as e: problems.append(f"cluster {j}: verify_record refused: {e}"); continue
    ids = set(r["server_start_ids"].values())
    if len(ids) != 1: problems.append(f"cluster {j}: {len(ids)} server starts within one record")
    b = U[j]["scheduled_block"]
    for s in ids: starts_by_block[b].add(s); block_of_start[s].add(b)
    rows = r["live"] + r["blind"] + [x for q in r["pulses"] for x in q["rows"]] + ((r["self_reset"] or {}).get("rows") or [])
    miss += sum(x[7] for x in rows) + sum(x[5] for x in r["init"]); calls += rec["model_calls"]
    masses += [x[9] for x in rows if x[9] is not None] + [x[6] for x in r["init"] if x[6] is not None]
    for s in ids: letters[s].update(x[8] for x in rows)
    arms[r["arm"]] += 1; mock += bool(r["mock"])
split = {b: sorted(v) for b, v in starts_by_block.items() if len(v) != 1}
shared = {s: sorted(v) for s, v in block_of_start.items() if len(v) != 1}
if split: problems.append(f"blocks in more than one start: {split}")
if shared: problems.append(f"starts shared by blocks: {shared}")
if mock: problems.append(f"{mock} mock records")
bal = {s: round(c[1] / sum(c.values()), 4) for s, c in letters.items()}
L = json.loads((FINAL / "ledger.json").read_text())
stops = sorted(p.name for d in [FINAL] + EARLIER for p in d.glob("CAP_STOP*"))
if not (L.get("closed") or {}).get("final"): problems.append("final run's ledger is not closed final")
if not (FINAL / "DONE").exists(): problems.append("no DONE marker in the final run")
if (FINAL / "UPLOAD_PENDING").exists(): problems.append("upload marker on the dataset")
if stops: problems.append(f"stop files: {stops}")
if not all(0 <= m <= 1 and math.isfinite(m) for m in masses): problems.append("invalid non-A/B mass value")
out.update({"records": len(recs), "verified": len(recs) - sum("verify_record" in x for x in problems), "arms": dict(arms),
            "records_by_origin": dict(collections.Counter(origin.values())),
            "server_starts": len(block_of_start), "scheduled_blocks": len(starts_by_block),
            "model_calls": calls, "missing_calls": miss,
            "non_ab_mass": {"n": len(masses), "max": max(masses) if masses else None, "mean": sum(masses) / len(masses) if masses else None},
            "letter_share_A_as_A_by_start": {"min": min(bal.values()), "max": max(bal.values())} if bal else None,
            "ledger": {"spent_usd": L["spent_usd"], "closed_final": (L.get("closed") or {}).get("final"),
                       "prior_runs": [p["ledger"].split("/")[-1] for p in L.get("prior_runs", [])], "flagged": L.get("flagged"), "acked": L.get("acked")},
            "done_marker": (FINAL / "DONE").exists(), "stop_files": stops, "problems": problems, "passed": not problems})
print(json.dumps(out, indent=1, default=str))
