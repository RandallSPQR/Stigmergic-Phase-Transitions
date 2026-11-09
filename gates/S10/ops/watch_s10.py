"""Watch one S10 pod run and keep monitor/status.json current. Read-only on RunPod and the dataset.
Prints a line when stage or progress changes, every 10 min otherwise, and on alerts; exits when the run is over.
  python watch_s10.py POD_ID RUN_ID CREATED_ISO MODEL BLOCKS CAP [LABEL]
Env: WATCH_STAGE (core, default, or secondary); WATCH_ONCE=1 for one pass; WATCH_DIR: where status.json goes.
Read-only: GET requests to the RunPod API and the dataset; it never writes to a pod or the dataset."""
import datetime as dt, json, os, subprocess, sys, time, urllib.parse
REPO_ROOT = os.environ.get("STPT_REPO", str(__import__("pathlib").Path(__file__).resolve().parents[3]))
sys.path[:0] = [REPO_ROOT, f"{REPO_ROOT}/gates/S10", f"{REPO_ROOT}/gates/S10/run"]
import s10_core as C, ledger as LG
from driver import stage_of
POD, RUN, CREATED, MODEL, BLOCKS, CAP = sys.argv[1], sys.argv[2], dt.datetime.fromisoformat(sys.argv[3]), sys.argv[4], sys.argv[5], float(sys.argv[6])
LABEL = sys.argv[7] if len(sys.argv) > 7 else "S10"
BLOCKS = sorted({c["start_block"] for c in C.load_clusters().values()}) if BLOCKS == "all" else [int(b) for b in BLOCKS.split(",")]
STAGE = os.environ.get("WATCH_STAGE", "core"); STAGE_KEY = f"{MODEL}:{STAGE}"; RATE = 2.49
HERE = os.environ.get("WATCH_DIR") or os.path.dirname(os.path.abspath(__file__)); DS = "RandallSPQR/stpt-gate-artifacts"; BASE = f"stpt/S10/{RUN}"
F = C.load_clusters()
ITEMS = [(j, a) for j in sorted(F) if F[j]["start_block"] in BLOCKS for a in C.arms_for(F[j], MODEL) if stage_of(MODEL, a) == STAGE_KEY]
TOTAL = sum(len(C.branch_names(F[j], MODEL, a)) for j, a in ITEMS)
BR = {(j, a): len(C.branch_names(F[j], MODEL, a)) for j, a in ITEMS}
ITEM_SET = set(ITEMS)
EST = {"setup": 3 * 60, "start": 2 * 60, "per_branch": 30.0, "final": 5 * 60}   # measured in the smoke block (A42)

def curl(url, auth=None, out=None):
    cmd = ["curl", "-sfL", "--max-time", "60", url] + (["-H", f"Authorization: Bearer {auth}"] if auth else []) + (["-o", out] if out else [])
    r = subprocess.run(cmd, capture_output=True, text=out is None)
    return (r.returncode == 0), (r.stdout if out is None else None)

def pod():
    ok, t = curl(f"https://rest.runpod.io/v1/pods/{POD}", os.environ["RUNPOD_API_KEY"])
    if not ok: return {"gone": True}
    try: return json.loads(t)
    except Exception: return {}

def tree():
    ok, t = curl(f"https://huggingface.co/api/datasets/{DS}/tree/main/{BASE}?recursive=true", os.environ.get("HF_TOKEN", "x"))
    try: return {f["path"][len(BASE) + 1:]: f.get("size") for f in json.loads(t) if f.get("type") == "file"} if ok else {}
    except Exception: return {}

def fetch(rel):
    ok, t = curl(f"https://huggingface.co/datasets/{DS}/resolve/main/{BASE}/{urllib.parse.quote(rel)}", os.environ.get("HF_TOKEN", "x"))
    return t if ok else None

def fmt_min(s):
    s = max(0, int(s)); h, m = divmod(round(s / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"

last_sig, last_print, seen_sizes, cache = None, 0, {}, {}
first_seen_files = None
while True:
    now = dt.datetime.now(dt.timezone.utc); el = (now - CREATED).total_seconds()
    p = pod(); files = tree()
    if files and first_seen_files is None: first_seen_files = time.time()
    for rel in ("events.jsonl", "ledger.json", "logs/driver.log", "DONE"):
        if rel in files and files[rel] != seen_sizes.get(rel):
            cache[rel] = fetch(rel); seen_sizes[rel] = files[rel]
    ev = [json.loads(l) for l in (cache.get("events.jsonl") or "").splitlines() if l.strip()]
    log = [l for l in (cache.get("logs/driver.log") or "").splitlines() if l.startswith("=== ")]
    led = json.loads(cache["ledger.json"]) if cache.get("ledger.json") else None
    SLUG = {f"{MODEL}/rec_c{j}__{a.replace(':', '-')}.json.gz": (j, a) for j, a in ITEMS}
    final_cl = {SLUG[r] for r in files if r in SLUG}
    cur_start = next((e["server_start"]["id"] for e in reversed(ev) if e.get("event") in ("server_start", "server_attach")), None)
    cur_block = next((e.get("block") for e in reversed(ev) if e.get("event") in ("server_start", "server_attach")), None)
    branches = {(e["cluster"], e["arm"], e["branch"]) for e in ev if e.get("event") == "branch_done" and e.get("server_start") == cur_start and (e["cluster"], e["arm"]) in ITEM_SET and (e["cluster"], e["arm"]) not in final_cl}
    done_b = min(TOTAL, sum(BR[k] for k in final_cl) + len(branches))
    clusters_done = len(final_cl)
    stopped = next((e["reason"] for e in reversed(ev) if e.get("event") == "stopped"), None)
    gone = p.get("gone") or p.get("desiredStatus") in ("EXITED", "TERMINATED")
    state, alert = "running", None
    if "DONE" in files: state, stage = "done", "Done: records, DONE marker and final ledger uploaded and verified"
    elif "SETUP_FAILED" in files: state, stage = "stopped", "Setup failed before any model call (its logs are on the dataset)"
    elif stopped: state, stage = "stopped", f"Stopped: {stopped}"
    elif gone: state, stage = "stopped", "Pod stopped or removed" + ("" if files else " before any upload")
    elif not files: stage = f"Pod starting: installing software, then downloading {MODEL} (the pod uploads its first status about 5 min after setup)"
    elif ev:
        e = ev[-1]; k = e.get("event")
        stage = (f"Block {cur_block} of {len(BLOCKS)} · " if cur_block else "") + {"server_start": f"Server starting for block {e.get('block')}", "server_attach": f"Server re-attached for block {e.get('block')}",
                 "env_check_passed": "Pipeline pin checked; running clusters", "branch_done": f"Cluster {e.get('cluster')}: {e.get('branch')} branch done",
                 "arm_done": f"Cluster {e.get('cluster')} done", "arm_final": "Saving the block's records", "block_done": f"Block {e.get('block')} done",
                 "server_stop": "Server stopped; uploading", "complete": "Model calls complete; final uploads"}.get(k, k)
    else: stage = (log[-1].split(" ", 2)[2] if log else "Setting up") + " (no model calls yet)"
    if state == "running" and not files and el > 40 * 60: alert = "no upload after 40 min"
    # spend
    if led:
        sp = LG.provisional(led, RATE, now.timestamp()).get(STAGE_KEY, 0.0); spend = f"${sp:.2f}"
    else:
        sp = el * RATE / 3600; spend = f"${sp:.2f} (est.)"
    # time to complete
    if state != "running": eta = "Finished"
    elif done_b:
        bd = [dt.datetime.fromisoformat(x["utc"].replace("Z", "+00:00")) for x in ev if x.get("event") == "branch_done"]
        per = max(1.0, (now - bd[0]).total_seconds() / len(bd)) if len(bd) >= 5 else EST["per_branch"]   # includes server starts
        eta = "~" + fmt_min((TOTAL - done_b) * per + EST["final"])
    else:
        eta = "~" + fmt_min(max(EST["setup"] + EST["start"] + TOTAL * EST["per_branch"] + EST["final"] - el, EST["start"] + TOTAL * EST["per_branch"] + EST["final"] if files else 60))
    pct = round(100 * done_b / TOTAL)                    # from records, also when the pod has finished
    row = {"run": f"{LABEL} · {len(BLOCKS)} blocks, clusters {ITEMS[0][0]}–{ITEMS[-1][0]} · pod {POD} · run {RUN}",
           "state": state, "stage": stage + (f" (alert: {alert})" if alert else ""), "pct": pct,
           "progress": f"{clusters_done} of {len(ITEMS)} {'clusters' if STAGE == 'core' else 'runs'} · {done_b} of {TOTAL} branches",
           "elapsed": fmt_min(el), "eta": eta, "spend": spend, "cap": f"${CAP:.2f}", "updated": now.strftime("%Y-%m-%d %H:%M UTC")}
    json.dump({"rows": [row]}, open(os.path.join(HERE, "status.json"), "w"), indent=1)
    sig = (state, stage, done_b, alert)
    if sig != last_sig or time.time() - last_print > 600:
        print(f"[{row['updated']}] {state} | {stage} | {row['progress']} | elapsed {row['elapsed']} | eta {eta} | spend {spend}" + (f" | ALERT {alert}" if alert else ""), flush=True)
        last_sig, last_print = sig, time.time()
    if state in ("done", "stopped") and (gone or "DONE" in files):
        print(f"[{row['updated']}] FINAL {state}", flush=True); break
    if os.environ.get("WATCH_ONCE"):
        print(f"[{row['updated']}] {state} | {stage} | {row['progress']} | elapsed {row['elapsed']} | eta {eta} | spend {spend}", flush=True); break
    time.sleep(60)
