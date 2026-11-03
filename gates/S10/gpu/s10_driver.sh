#!/bin/bash
# S10 confirmatory collection on the pod (review #4; addendum 1). NOT YET RUN: needs the owner's explicit OK.
# Started by gates/S0/gpu/launch.py --driver gates/S10/gpu/s10_driver.sh --extra-env STPT_PAYLOAD_B64 ... STPT_PAYLOAD_SHA256 ...
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PAYLOAD_B64,
#      STPT_PAYLOAD_SHA256, STPT_MODELS, STPT_STAGES (default "core"), STPT_BLOCKS (optional), STPT_ACK (optional).
# Per model: weights checked against the pinned weight hash; then gates/S10/run/pod.py runs the driver, which owns the
# server starts (one per block), checkpoints after every branch and stops at a stage's 80% flag or cap.
set -uo pipefail
OUT=/root/out/$STPT_RUN_ID; mkdir -p "$OUT/logs"; touch /tmp/pod_driven
export HF_HOME=/root/hf HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TOKENIZERS_PARALLELISM=false
exec > >(tee -a "$OUT/logs/driver.log") 2>&1
PY=/root/venv/bin/python; VPY=/root/venv_vllm_lineup/bin/python
step() { echo "=== $(date -u +%FT%TZ) $*"; }
upload() {
  $PY - "$OUT" <<'PYX' || echo "upload failed"
import os, sys
from huggingface_hub import HfApi
HfApi().upload_folder(repo_id=os.environ["STPT_RESULTS_REPO"], repo_type="dataset", folder_path=sys.argv[1],
                      path_in_repo=f"stpt/S10/{os.environ['STPT_RUN_ID']}", commit_message="S10 confirmatory")
PYX
}
step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
uv() { python3 -m uv "$@"; }
uv venv -q -p 3.11 /root/venv_vllm_lineup && uv pip install -q -p $VPY "vllm==0.19.1" "torch==2.10.0" "transformers==5.5.3" \
  "tokenizers==0.22.2" "huggingface-hub==1.10.2" > "$OUT/logs/pip_vllm.log" 2>&1
uv venv -q -p 3.11 /root/venv && uv pip install -q -p $PY "transformers==5.17.0" jinja2 pyyaml numpy \
  "sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT" > "$OUT/logs/pip_pipe.log" 2>&1
step "payload"
mkdir -p /root/stpt && echo "$STPT_PAYLOAD_B64" | base64 -d > /root/payload.tar.gz
GOT=$(sha256sum /root/payload.tar.gz | cut -d' ' -f1)
[ "$GOT" = "$STPT_PAYLOAD_SHA256" ] || { echo "STOP: payload sha256 $GOT != $STPT_PAYLOAD_SHA256"; upload; exit 3; }
tar -xzf /root/payload.tar.gz -C /root/stpt && echo "payload verified ${GOT:0:16}"
export CACHES="/root/.cache/vllm /tmp/torchinductor_root /root/.triton /root/.cache/flashinfer /root/.nv /root/.cache/torch /root/.cache/triton"
export LINEUP_VLLM_PYTHON=$VPY
( while sleep 300; do upload >/dev/null 2>&1; done ) & UPL=$!
for M in ${STPT_MODELS}; do
  step "$M: weights"; df -h / | tail -1
  export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
  read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
  $PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" > "$OUT/logs/download_$M.log" 2>&1
  ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
  (cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' --hash --out "$OUT/preflight_$M.json") > "$OUT/logs/preflight_$M.log" 2>&1
  GOTW=$($PY -c "import json; print(json.load(open('$OUT/preflight_$M.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
  if [ "$GOTW" != "$WANT" ]; then echo "STOP for $M: weight_hash $GOTW != $WANT"; upload; continue; fi
  step "$M: driver"
  $PY /root/stpt/gates/S10/run/pod.py --model "$M" --caps /root/stpt/gates/S10/run/caps_approved.json --out "$OUT" \
      --stages ${STPT_STAGES:-core} ${STPT_BLOCKS:+--blocks $STPT_BLOCKS} ${STPT_ACK:+--ack $STPT_ACK}
  RC=$?; step "$M: driver exit $RC"; upload
  [ $RC = 0 ] || { echo "STOP: $M did not complete (flag, cap or error); pod stops for the owner"; break; }
  rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"
done
kill $UPL 2>/dev/null; step "done"; touch "$OUT/DONE"; upload
runpodctl remove pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1
