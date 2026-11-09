#!/bin/bash
# S10 confirmatory collection on the pod (review #4; addendum 1, rounds 2-3). NOT YET RUN: needs the owner's explicit OK.
# Launched by gates/S0/gpu/launch.py --data-safe --driver gates/S10/gpu/s10_driver.sh --extra-env STPT_PAYLOAD_B64 ...
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PAYLOAD_HF_PATH, or
#      STPT_PAYLOAD_B64_PARTS + STPT_PAYLOAD_B64_1..N, or STPT_PAYLOAD_B64 for a payload under 128 KiB,
#      STPT_PAYLOAD_SHA256, STPT_MODELS, STPT_STAGES (default "core"), STPT_BLOCKS, STPT_ACK, USD_PER_GPU_HOUR,
#      STPT_PRIOR_RUNS (run IDs of earlier pods of this collection: their ledgers make the caps cumulative, and their
#      finished records are restored so finished blocks are not run again).
#
# Data safety (round 3): outputs live on the pod's persistent volume (/workspace). UPLOAD_PENDING is created before the
# first paid model phase and removed only after an upload whose every file is verified on the dataset (name, and size for every file but the
# live log). This script never deletes the pod: launch.py --data-safe removes it only when UPLOAD_PENDING is gone, and
# otherwise stops it (the volume, and so every record, survives). A restarted pod with UPLOAD_PENDING only retries the
# upload (recovery mode); it never re-runs paid work.
# Metering (round 3): the ledger opens at this script's first line, so installation, downloads, server starts, model
# calls and teardown are all charged; the watchdog (gates/S10/run/ledger.py) enforces the caps during every paid phase
# and never terminates an upload.
# Setup failures (operational change after A52): a stop in setup, before UPLOAD_PENDING exists, makes the pod delete
# itself; setup_stop() first uploads the run folder's small files (logs, and the ledger closed final when one is open)
# with a stdlib uploader, so the failing step is visible on the dataset.
POD_T0=$(date +%s.%N)
set -uo pipefail
WS=${STPT_WORKSPACE:-/workspace}
MARKER=${STPT_MARKER:-$WS/UPLOAD_PENDING}
OUT=$WS/out/$STPT_RUN_ID
PY=${STPT_PY:-/root/venv/bin/python}; VPY=/root/venv_vllm_lineup/bin/python
SRC=${STPT_SRC:-/root/stpt}
export STPT_POD_SESSION="${STPT_RUN_ID}-$(date +%s%N)"
HF_EP=${HF_ENDPOINT:-https://huggingface.co}
step() { echo "=== $(date -u +%FT%TZ) $*"; }

upload_setup_logs() {
  # Stdlib only (setup may fail before any venv exists, or before the payload is unpacked): commit the run folder's
  # small files (no *.gz, none over 5 MB) through the dataset's commit API, then check each is listed with its size
  # (the live log's size may grow). Returns non-zero if every attempt fails.
  timeout "${STPT_SETUP_UPLOAD_TIMEOUT:-300}" python3 - "$OUT" <<'PYX'
import base64, json, os, sys, time, urllib.request
from pathlib import Path
out = Path(sys.argv[1]); ep = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
repo = os.environ["STPT_RESULTS_REPO"]; run = os.environ["STPT_RUN_ID"]; dest = f"stpt/S10/{run}"
H = {"Authorization": f"Bearer {os.environ.get('HF_TOKEN', '')}", "User-Agent": "stpt-s10-setup/1.0"}
files = {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*"))
         if p.is_file() and not p.name.endswith(".gz") and p.stat().st_size <= 5_000_000}
lines = [{"key": "header", "value": {"summary": f"S10 setup failure: logs of {run}", "description": ""}}]
lines += [{"key": "file", "value": {"path": f"{dest}/{r}", "encoding": "base64", "content": base64.b64encode(b).decode()}}
          for r, b in files.items()]
body = "\n".join(json.dumps(x) for x in lines).encode()
for wait in [0] + [int(x) for x in os.environ.get("STPT_SETUP_UPLOAD_BACKOFF", "15 45").split()]:
    time.sleep(wait)
    try:
        req = urllib.request.Request(f"{ep}/api/datasets/{repo}/commit/main", data=body, method="POST",
                                     headers={**H, "Content-Type": "application/x-ndjson"})
        urllib.request.urlopen(req, timeout=120).read()
        req = urllib.request.Request(f"{ep}/api/datasets/{repo}/tree/main/{dest}?recursive=true", headers=H)
        remote = {f["path"][len(dest) + 1:]: f.get("size") for f in json.load(urllib.request.urlopen(req, timeout=60))
                  if f.get("type") == "file"}
        bad = [r for r, b in files.items() if r not in remote or (r != "logs/driver.log" and remote[r] != len(b))]
        if not bad:
            print(f"setup logs uploaded and verified: {len(files)} files"); sys.exit(0)
        print("setup log upload not verified:", bad[:5])
    except Exception as e:
        print("setup log upload attempt failed:", type(e).__name__, str(e)[:200])
sys.exit(1)
PYX
}

setup_stop() {
  # $1: exit status; the rest: the reason. For a stop before UPLOAD_PENDING exists (the pod then deletes itself): the
  # reason goes to SETUP_FAILED, an open ledger is closed final (charged through this upload's hard limit), and the
  # small files are uploaded; the exit status is the setup failure's whether or not the upload succeeds.
  local rc=$1; shift
  echo "STOP: $*"; echo "$*" > "$OUT/SETUP_FAILED"
  if [ -e "$OUT/ledger.json" ] && [ -f "$SRC/gates/S10/run/ledger.py" ]; then
    ledger close --final --allowance "${STPT_SETUP_UPLOAD_TIMEOUT:-300}" --since "$POD_T0" >/dev/null 2>&1
  fi
  sleep 1                                       # let the logging tee catch up before the log is read
  upload_setup_logs || echo "setup logs NOT uploaded"
  exit "$rc"
}

upload() {
  # Upload $OUT and verify every file on the dataset. Returns non-zero on any failure or mismatch (round 3).
  # UPLOAD_TIMEOUT (seconds; 0 = none) is a hard limit on the attempt (round 5: final attempts are charged in advance).
  timeout "${UPLOAD_TIMEOUT:-0}" "$PY" - "$OUT" <<'PYX'
import os, sys
from pathlib import Path
from huggingface_hub import HfApi
out = Path(sys.argv[1]); repo = os.environ["STPT_RESULTS_REPO"]; dest = f"stpt/S10/{os.environ['STPT_RUN_ID']}"
api = HfApi()
# A43: intermediate block copies (<model>/blocks/...) that no longer exist locally are removed from the dataset in the
# same commit, so after a block is finalized only its final records (<model>/rec_*.json.gz) remain there.
api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(out), path_in_repo=dest, commit_message="S10 confirmatory",
                  delete_patterns=["*/blocks/**"])
remote = {f.path[len(dest) + 1:]: getattr(f, "size", None) for f in api.list_repo_tree(repo, repo_type="dataset", path_in_repo=dest, recursive=True)}
local = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
bad = [r for r in remote if "/blocks/" in "/" + r and r not in local]      # stale intermediates must be gone
for p in out.rglob("*"):
    if p.is_file() and not p.name.endswith(".tmp"):
        rel = str(p.relative_to(out))
        if rel not in remote or (rel != "logs/driver.log" and remote[rel] != p.stat().st_size):
            bad.append(rel)
if bad:
    print("UPLOAD NOT VERIFIED:", len(bad), "files missing or different, e.g.", bad[:5]); sys.exit(1)
print("upload verified:", sum(1 for p in out.rglob("*") if p.is_file()), "files")
PYX
}

upload_until_verified() {
  local i
  for i in 0 30 60 120 240 480; do
    sleep "$i"
    upload && return 0
    echo "upload attempt failed; retrying"
  done
  return 1
}

ledger() { python3 "$SRC/gates/S10/run/ledger.py" "$1" --out "$OUT" --caps "$SRC/gates/S10/run/caps_approved.json" "${@:2}"; }

FINAL_ATTEMPT_S=${STPT_FINAL_ATTEMPT_S:-300}               # hard limit of one final upload attempt
FINAL_BACKOFF=${STPT_FINAL_BACKOFF:-"30 60 120 240 480"}   # sleeps between final attempts

final_ledger_upload() {
  # Required (round 5): the upload that carries the final ledger, verified like every upload. Before each attempt the
  # ledger is charged through that attempt's hard limit, and before each sleep through the sleep, so the ledger an
  # attempt uploads already covers all billable time up to that attempt's end. Returns non-zero if every attempt fails.
  local b
  ledger close --final --allowance "$FINAL_ATTEMPT_S" --since "$POD_T0" >/dev/null 2>&1 || return 1
  UPLOAD_TIMEOUT=$FINAL_ATTEMPT_S upload && return 0
  for b in $FINAL_BACKOFF; do
    echo "final ledger upload failed; retrying in $b s"
    ledger close --final --allowance "$b" --since "$POD_T0" >/dev/null 2>&1 || return 1
    sleep "$b"
    ledger close --final --allowance "$FINAL_ATTEMPT_S" --since "$POD_T0" >/dev/null 2>&1 || return 1
    UPLOAD_TIMEOUT=$FINAL_ATTEMPT_S upload && return 0
  done
  return 1
}

finish() {
  # $1: exit status to report. The pod is never deleted here. The ledger stays open (and the watchdog running) through
  # the final uploads, so their time is charged (round 4); the last close is final.
  local rc=$1
  [ -n "${UPL:-}" ] && kill "$UPL" 2>/dev/null
  ledger reopen --no-check >/dev/null 2>&1
  if upload_until_verified; then
    touch "$OUT/DONE"
    [ -n "${WDOG:-}" ] && kill "$WDOG" 2>/dev/null
    if final_ledger_upload; then                        # records, DONE and the final ledger, verified (round 5)
      rm -f "$MARKER"
      step "uploads verified, final ledger included; UPLOAD_PENDING cleared; exit $rc"
      exit "$rc"
    fi
    step "FINAL LEDGER NOT UPLOADED: UPLOAD_PENDING kept; the pod will be stopped, not deleted, and its volume kept"
    exit 5
  fi
  [ -n "${WDOG:-}" ] && kill "$WDOG" 2>/dev/null
  ledger close --final --since "$POD_T0" >/dev/null 2>&1
  step "UPLOAD NOT VERIFIED: UPLOAD_PENDING kept; the pod will be stopped, not deleted, and its volume kept"
  exit 5
}

paid() {
  # Run a paid phase of stage $CUR_STAGE in its own process group, registered for the watchdog; refuse after that
  # stage's cap stop (the watchdog writes one stop file per stage, so another stage's work is not blocked).
  local sf="$OUT/CAP_STOP_${CUR_STAGE//:/_}"
  [ -e "$sf" ] && { echo "cap stop for $CUR_STAGE: $(cat "$sf")"; return 3; }
  setsid "$@" & local pid=$!
  echo "$pid" >> "$OUT/paid.pids"
  wait "$pid"; local rc=$?
  [ -e "$sf" ] && { echo "stopped by the watchdog: $(cat "$sf")"; return 3; }
  return $rc
}

fetch_payload() {
  # The payload (code and the 61 frozen clusters; A41: at 146,636 base64 characters it exceeds Linux's 128 KiB limit
  # for one environment string) comes from the private results dataset when STPT_PAYLOAD_HF_PATH is set, from
  # STPT_PAYLOAD_B64_1..N when STPT_PAYLOAD_B64_PARTS=N is set (each part under the limit), otherwise from
  # STPT_PAYLOAD_B64 as before. Either way it is used only if its sha256 is STPT_PAYLOAD_SHA256.
  local dest=$1 i
  if [ -n "${STPT_PAYLOAD_HF_PATH:-}" ]; then
    for i in 1 2 3 4 5; do
      curl -sfL -H "Authorization: Bearer $HF_TOKEN" -o "$dest.dl" \
        "$HF_EP/datasets/$STPT_RESULTS_REPO/resolve/main/$STPT_PAYLOAD_HF_PATH" && break
      echo "payload download attempt $i failed"; sleep $((i * 10))
    done
    case "$STPT_PAYLOAD_HF_PATH" in                    # stored as base64 text (an ordinary dataset file) or as bytes
      *.b64) base64 -d "$dest.dl" > "$dest" 2>/dev/null; rm -f "$dest.dl";;
      *) mv -f "$dest.dl" "$dest" 2>/dev/null;;
    esac
  elif [ -n "${STPT_PAYLOAD_B64_PARTS:-}" ]; then        # split across variables, each under the 128 KiB limit
    local k v all=""
    for k in $(seq 1 "$STPT_PAYLOAD_B64_PARTS"); do
      v="STPT_PAYLOAD_B64_$k"; [ -n "${!v:-}" ] || { echo "STOP: payload part $k missing"; return 1; }
      all+="${!v}"
    done
    printf '%s' "$all" | base64 -d > "$dest"
  else
    echo "$STPT_PAYLOAD_B64" | base64 -d > "$dest"
  fi
  [ -s "$dest" ] || { echo "STOP: no payload"; return 1; }
  local got; got=$(sha256sum "$dest" | cut -d' ' -f1)
  [ "$got" = "$STPT_PAYLOAD_SHA256" ] || { echo "STOP: payload sha256 $got != $STPT_PAYLOAD_SHA256"; return 1; }
  echo "payload verified ${got:0:16}"
}

restore_prior_records() {
  # Copy the final records (<model>/rec_*.json.gz) of every run in STPT_PRIOR_RUNS into $OUT, so finished blocks are not
  # run again. A44: the script goes to a file, not stdin (a background paid phase gets an empty stdin, which made the
  # earlier version do nothing and exit 0), and the step fails unless every record found is in place afterwards.
  local f=/root/restore_prior_records.py
  [ -w /root ] || f="$OUT/.restore_prior_records.py"
  cat > "$f" <<'PYX'
import os, shutil, sys
from pathlib import Path
from huggingface_hub import snapshot_download
out = Path(sys.argv[1]); repo = os.environ["STPT_RESULTS_REPO"]; found = placed = 0
for run in os.environ["STPT_PRIOR_RUNS"].split():
    d = Path(snapshot_download(repo, repo_type="dataset", allow_patterns=[f"stpt/S10/{run}/*/rec_*.json.gz"]))
    for p in sorted((d / "stpt/S10" / run).glob("*/rec_*.json.gz")):
        found += 1
        dst = out / p.parent.name / p.name
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dst)
            print("restored", run, p.parent.name, p.name)
        placed += dst.exists() and dst.stat().st_size > 0
print(f"restore: {found} records found in {os.environ['STPT_PRIOR_RUNS']}, {placed} in place")
sys.exit(0 if placed == found else 1)
PYX
  paid "$PY" "$f" "$OUT"
}

first_stage() {
  local m=${STPT_MODELS%% *}
  case " gemma-2-9b-it qwen3.5-9b gemma-3-27b-it qwen3.5-27b " in
    *" $m "*) case " ${STPT_STAGES:-core} " in *" core "*) echo "$m:core"; return;; esac;;
  esac
  echo "$m:secondary"
}

[ "${S10_SOURCE_ONLY:-0}" = 1 ] && return 0

mkdir -p "$OUT/logs"; touch /tmp/pod_driven
export HF_HOME=/root/hf HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TOKENIZERS_PARALLELISM=false
exec > >(tee -a "$OUT/logs/driver.log") 2>&1

RECOVERY=0; [ -e "$MARKER" ] && RECOVERY=1         # a previous run on this volume ended without a verified upload
step "payload"
mkdir -p "$SRC"
PAYLOAD=${STPT_PAYLOAD_FILE:-/root/payload.tar.gz}
fetch_payload "$PAYLOAD" || { [ $RECOVERY = 1 ] && exit 5; setup_stop 3 "payload not available or not verified"; }
tar -xzf "$PAYLOAD" -C "$SRC"
if [ $RECOVERY = 1 ]; then
  step "recovery: UPLOAD_PENDING from an earlier run; uploading only (no paid work); this pod's time is charged"
  python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
  python3 -m uv venv -q -p 3.11 /root/venv && python3 -m uv pip install -q -p $PY "huggingface-hub==1.10.2" >/dev/null 2>&1
  ok=1
  for d in "$WS"/out/*/; do
    OUT=${d%/}; STPT_RUN_ID=$(basename "$OUT"); export STPT_RUN_ID
    final_ledger_upload || ok=0                         # charged from this pod's start; records and ledger verified
  done
  [ $ok = 1 ] && { rm -f "$MARKER"; step "recovery: all uploads verified, final ledgers included"; exit 0; }
  step "recovery: uploads still not verified; UPLOAD_PENDING kept"; exit 5
fi
CAPS=$SRC/gates/S10/run/caps_approved.json
if [ -n "${STPT_PRIOR_RUNS:-}" ]; then              # cumulative caps across pods: earlier ledgers are required
  PRIORS=()
  for R in $STPT_PRIOR_RUNS; do
    curl -sf -H "Authorization: Bearer $HF_TOKEN" -o "$OUT/prior_ledger_$R.json" \
      "$HF_EP/datasets/$STPT_RESULTS_REPO/resolve/main/stpt/S10/$R/ledger.json" \
      || setup_stop 3 "ledger of earlier run $R not available; refusing to start without its spend"
    PRIORS+=("$OUT/prior_ledger_$R.json")
  done
  python3 "$SRC/gates/S10/run/ledger.py" seed --out "$OUT" --caps "$CAPS" --prior "${PRIORS[@]}" \
    || setup_stop 3 "earlier ledgers could not be seeded"
fi
CUR_STAGE=$(first_stage)
python3 "$SRC/gates/S10/run/ledger.py" open --out "$OUT" --caps "$CAPS" --stage "$CUR_STAGE" --since "$POD_T0" \
  || setup_stop 3 "ledger refused the first stage (no paid work done)"
python3 "$SRC/gates/S10/run/ledger.py" watchdog --out "$OUT" --caps "$CAPS" > "$OUT/logs/watchdog.log" 2>&1 & WDOG=$!

step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
paid bash -c "python3 -m uv venv -q -p 3.11 /root/venv_vllm_lineup && python3 -m uv pip install -q -p $VPY 'vllm==0.19.1' 'torch==2.10.0' 'transformers==5.5.3' 'tokenizers==0.22.2' 'huggingface-hub==1.10.2'" > "$OUT/logs/pip_vllm.log" 2>&1 \
  || setup_stop 3 "install failed (no records yet); see logs/pip_*.log"
paid bash -c "python3 -m uv venv -q -p 3.11 /root/venv && python3 -m uv pip install -q -p $PY 'transformers==5.17.0' jinja2 pyyaml numpy 'huggingface-hub==1.10.2' 'sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT'" > "$OUT/logs/pip_pipe.log" 2>&1 \
  || setup_stop 3 "install failed (no records yet); see logs/pip_*.log"
export CACHES="/root/.cache/vllm /tmp/torchinductor_root /root/.triton /root/.cache/flashinfer /root/.nv /root/.cache/torch /root/.cache/triton"
export LINEUP_VLLM_PYTHON=$VPY
if [ -n "${STPT_PRIOR_RUNS:-}" ]; then              # restore finished records of earlier pods (never rerun them)
  restore_prior_records || { echo "STOP: earlier records could not be restored"; finish 3; }
fi
touch "$MARKER"                                   # from here on, records exist that must reach the dataset
( while sleep 300; do upload >/dev/null 2>&1; done ) & UPL=$!
RC=0
for M in ${STPT_MODELS}; do
  case " gemma-2-9b-it qwen3.5-9b gemma-3-27b-it qwen3.5-27b " in
    *" $M "*) case " ${STPT_STAGES:-core} " in *" core "*) ST="$M:core";; *) ST="$M:secondary";; esac;;
    *) ST="$M:secondary";;
  esac
  CUR_STAGE=$ST
  python3 "$SRC/gates/S10/run/ledger.py" open --out "$OUT" --caps "$CAPS" --stage "$ST" || { RC=3; break; }
  step "$M: weights"; df -h / | tail -1
  export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
  read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
  paid $PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" > "$OUT/logs/download_$M.log" 2>&1 || { RC=3; break; }
  ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
  (cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' --hash --out "$OUT/preflight_$M.json") > "$OUT/logs/preflight_$M.log" 2>&1
  GOTW=$($PY -c "import json; print(json.load(open('$OUT/preflight_$M.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
  if [ "$GOTW" != "$WANT" ]; then echo "STOP for $M: weight_hash $GOTW != $WANT"; RC=4; break; fi
  step "$M: driver"
  paid $PY "$SRC/gates/S10/run/pod.py" --model "$M" --caps "$CAPS" --out "$OUT" \
      --stages ${STPT_STAGES:-core} ${STPT_BLOCKS:+--blocks $STPT_BLOCKS} ${STPT_ACK:+--ack $STPT_ACK}
  RC=$?; step "$M: driver exit $RC"
  ledger reopen --no-check >/dev/null 2>&1          # the pod still bills while uploading (round 4)
  upload_until_verified || { echo "STOP: uploads not verified after $M; no further paid work"; RC=5; break; }
  [ $RC = 0 ] || { echo "STOP: $M did not complete (flag, cap or error)"; break; }
  rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"
done
step "done (status $RC)"
finish "$RC"
