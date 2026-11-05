#!/bin/bash
# S10 confirmatory collection on the pod (review #4; addendum 1, rounds 2-3). NOT YET RUN: needs the owner's explicit OK.
# Launched by gates/S0/gpu/launch.py --data-safe --driver gates/S10/gpu/s10_driver.sh --extra-env STPT_PAYLOAD_B64 ...
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PAYLOAD_B64,
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
POD_T0=$(date +%s.%N)
set -uo pipefail
WS=${STPT_WORKSPACE:-/workspace}
MARKER=${STPT_MARKER:-$WS/UPLOAD_PENDING}
OUT=$WS/out/$STPT_RUN_ID
PY=${STPT_PY:-/root/venv/bin/python}; VPY=/root/venv_vllm_lineup/bin/python
SRC=${STPT_SRC:-/root/stpt}
export STPT_POD_SESSION="${STPT_RUN_ID}-$(date +%s%N)"
step() { echo "=== $(date -u +%FT%TZ) $*"; }

upload() {
  # Upload $OUT and verify every file on the dataset. Returns non-zero on any failure or mismatch (round 3).
  "$PY" - "$OUT" <<'PYX'
import os, sys
from pathlib import Path
from huggingface_hub import HfApi
out = Path(sys.argv[1]); repo = os.environ["STPT_RESULTS_REPO"]; dest = f"stpt/S10/{os.environ['STPT_RUN_ID']}"
api = HfApi()
api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(out), path_in_repo=dest, commit_message="S10 confirmatory")
remote = {f.path[len(dest) + 1:]: getattr(f, "size", None) for f in api.list_repo_tree(repo, repo_type="dataset", path_in_repo=dest, recursive=True)}
bad = []
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

finish() {
  # $1: exit status to report. The pod is never deleted here. The ledger stays open (and the watchdog running) through
  # the final uploads, so their time is charged (round 4); the last close is final.
  local rc=$1
  [ -n "${UPL:-}" ] && kill "$UPL" 2>/dev/null
  ledger reopen --no-check >/dev/null 2>&1
  if upload_until_verified; then
    touch "$OUT/DONE"; upload_until_verified || echo "DONE marker not uploaded (records are verified)"
    [ -n "${WDOG:-}" ] && kill "$WDOG" 2>/dev/null
    ledger close --final --allowance 120 >/dev/null 2>&1   # all upload time charged; 120 s in advance for the next one
    upload_until_verified || echo "final ledger not uploaded (records are verified)"   # the dataset gets the final ledger
    rm -f "$MARKER"
    step "uploads verified; UPLOAD_PENDING cleared; exit $rc"
    exit "$rc"
  fi
  [ -n "${WDOG:-}" ] && kill "$WDOG" 2>/dev/null
  ledger close --final --allowance 120 >/dev/null 2>&1
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

if [ -e "$MARKER" ]; then                       # a previous run on this volume ended without a verified upload
  step "recovery: UPLOAD_PENDING from an earlier run; uploading only (no paid work)"
  python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
  python3 -m uv venv -q -p 3.11 /root/venv && python3 -m uv pip install -q -p $PY "huggingface-hub==1.10.2" >/dev/null 2>&1
  ok=1
  for d in "$WS"/out/*/; do OUT=${d%/}; STPT_RUN_ID=$(basename "$OUT"); export STPT_RUN_ID; upload_until_verified || ok=0; done
  [ $ok = 1 ] && { rm -f "$MARKER"; step "recovery: all uploads verified"; exit 0; }
  step "recovery: uploads still not verified; UPLOAD_PENDING kept"; exit 5
fi
step "payload"
mkdir -p "$SRC" && echo "$STPT_PAYLOAD_B64" | base64 -d > /root/payload.tar.gz
GOT=$(sha256sum /root/payload.tar.gz | cut -d' ' -f1)
[ "$GOT" = "$STPT_PAYLOAD_SHA256" ] || { echo "STOP: payload sha256 $GOT != $STPT_PAYLOAD_SHA256"; rm -f "$MARKER"; exit 3; }
tar -xzf /root/payload.tar.gz -C "$SRC" && echo "payload verified ${GOT:0:16}"
CAPS=$SRC/gates/S10/run/caps_approved.json
if [ -n "${STPT_PRIOR_RUNS:-}" ]; then              # cumulative caps across pods: earlier ledgers are required
  PRIORS=()
  for R in $STPT_PRIOR_RUNS; do
    curl -sf -H "Authorization: Bearer $HF_TOKEN" -o "$OUT/prior_ledger_$R.json" \
      "https://huggingface.co/datasets/$STPT_RESULTS_REPO/resolve/main/stpt/S10/$R/ledger.json" \
      || { echo "STOP: ledger of earlier run $R not available; refusing to start without its spend"; exit 3; }
    PRIORS+=("$OUT/prior_ledger_$R.json")
  done
  python3 "$SRC/gates/S10/run/ledger.py" seed --out "$OUT" --caps "$CAPS" --prior "${PRIORS[@]}" || exit 3
fi
CUR_STAGE=$(first_stage)
python3 "$SRC/gates/S10/run/ledger.py" open --out "$OUT" --caps "$CAPS" --stage "$CUR_STAGE" --since "$POD_T0" \
  || { echo "STOP: ledger refused the first stage (no paid work done)"; exit 3; }
python3 "$SRC/gates/S10/run/ledger.py" watchdog --out "$OUT" --caps "$CAPS" > "$OUT/logs/watchdog.log" 2>&1 & WDOG=$!

step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
paid bash -c "python3 -m uv venv -q -p 3.11 /root/venv_vllm_lineup && python3 -m uv pip install -q -p $VPY 'vllm==0.19.1' 'torch==2.10.0' 'transformers==5.5.3' 'tokenizers==0.22.2' 'huggingface-hub==1.10.2'" > "$OUT/logs/pip_vllm.log" 2>&1 \
  || { echo "STOP: install (no records yet)"; exit 3; }
paid bash -c "python3 -m uv venv -q -p 3.11 /root/venv && python3 -m uv pip install -q -p $PY 'transformers==5.17.0' jinja2 pyyaml numpy 'huggingface-hub==1.10.2' 'sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT'" > "$OUT/logs/pip_pipe.log" 2>&1 \
  || { echo "STOP: install (no records yet)"; exit 3; }
export CACHES="/root/.cache/vllm /tmp/torchinductor_root /root/.triton /root/.cache/flashinfer /root/.nv /root/.cache/torch /root/.cache/triton"
export LINEUP_VLLM_PYTHON=$VPY
if [ -n "${STPT_PRIOR_RUNS:-}" ]; then              # restore finished records of earlier pods (never rerun them)
  paid $PY - "$OUT" <<'PYX' || { echo "STOP: earlier records could not be restored"; exit 3; }
import os, shutil, sys
from pathlib import Path
from huggingface_hub import snapshot_download
out = Path(sys.argv[1]); repo = os.environ["STPT_RESULTS_REPO"]
for run in os.environ["STPT_PRIOR_RUNS"].split():
    d = Path(snapshot_download(repo, repo_type="dataset", allow_patterns=[f"stpt/S10/{run}/*/rec_*.json.gz"]))
    for p in (d / "stpt/S10" / run).glob("*/rec_*.json.gz"):
        dst = out / p.parent.name / p.name
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dst)
            print("restored", run, p.parent.name, p.name)
PYX
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
