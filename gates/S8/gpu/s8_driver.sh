#!/bin/bash
# Gate S8 on the pod (gates/S8/S8_PLAN.md, D27): the pilot clusters through the StPT board harness. Per model, two cold
# server starts; in each, 20 fixed probes at the beginning and at the end, and the clusters assigned to that start
# (gates/S8/inputs/clusters.json), each uploaded as soon as it is done.
# Started by gates/S0/gpu/launch.py --driver gates/S8/gpu/s8_driver.sh.
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PINS_JSON,
#      STPT_PAYLOAD_B64 (gzip+base64 of {files, clusters, params, probes}), STPT_PAYLOAD_SHA256, STPT_MODELS.
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
                      path_in_repo=f"stpt/S8/{os.environ['STPT_RUN_ID']}", commit_message="S8 pilot")
PYX
}
step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
uv() { python3 -m uv "$@"; }
uv venv -q -p 3.11 /root/venv_vllm_lineup && uv pip install -q -p $VPY "vllm==0.19.1" "torch==2.10.0" "transformers==5.5.3" \
  "tokenizers==0.22.2" "huggingface-hub==1.10.2" > "$OUT/logs/pip_vllm.log" 2>&1
uv venv -q -p 3.11 /root/venv && uv pip install -q -p $PY "transformers==5.17.0" jinja2 \
  "sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT" > "$OUT/logs/pip_pipe.log" 2>&1
$VPY -c "import sys, vllm, torch; print(sys.version.split()[0], 'vllm', vllm.__version__, 'torch', torch.__version__, torch.cuda.get_device_name(0))" | tee "$OUT/stack.txt"
step "payload"
$PY - <<'PYX' || { echo "STOP: payload"; upload; exit 3; }
import base64, gzip, hashlib, json, os
raw = gzip.decompress(base64.b64decode(os.environ["STPT_PAYLOAD_B64"]))
h = hashlib.sha256(raw).hexdigest()
assert h == os.environ["STPT_PAYLOAD_SHA256"], f"payload sha256 {h} != committed"
pl = json.loads(raw)
os.makedirs("/root/s8", exist_ok=True)
for name, src in pl["files"].items():
    open(f"/root/s8/{name}", "w").write(src)
for k in ("clusters", "params", "probes"):
    json.dump(pl[k], open(f"/root/s8/{k}.json", "w"))
print("payload verified", h[:16], sorted(pl["files"]))
PYX
export CACHES="/root/.cache/vllm /tmp/torchinductor_root /root/.triton /root/.cache/flashinfer /root/.nv /root/.cache/torch /root/.cache/triton"
for M in ${STPT_MODELS:-llama-3.1-8b-it gemma-2-9b-it qwen3.5-9b gemma-3-27b-it qwen3.5-27b}; do
  step "$M: weights"; df -h / | tail -1
  export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
  read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
  $PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" > "$OUT/logs/download_$M.log" 2>&1
  ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
  (cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' --hash --out "$OUT/preflight_$M.json") > "$OUT/logs/preflight_$M.log" 2>&1
  GOT=$($PY -c "import json; print(json.load(open('$OUT/preflight_$M.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
  if [ "$GOT" != "$WANT" ]; then echo "STOP for $M: weight_hash $GOT != $WANT"; rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"; upload; continue; fi
  for K in 1 2; do
    rm -rf $CACHES
    step "$M: cold start $K"
    STARTED=$(date -u +%FT%TZ)
    CMD=$(LINEUP_VLLM_PYTHON=$VPY /root/venv/bin/lineup-serve-cmd "$M"); echo "$CMD" > "$OUT/serve_cmd_$M.txt"
    bash -c "$CMD" > "$OUT/logs/vllm_${M}_start$K.log" 2>&1 & VPID=$!
    UP=0; for _ in $(seq 1 360); do curl -s localhost:8000/v1/models >/dev/null 2>&1 && { UP=1; break; }; kill -0 $VPID 2>/dev/null || break; sleep 5; done
    if [ $UP = 1 ]; then
      $PY - "$M" "$OUT" "$STARTED" "$K" <<'PYX'
import gzip, json, os, sys, time
sys.path.insert(0, "/root/s8")
import sae_ethos_pipeline, modelcfg
from lineup import readout, manifest
from transformers import AutoTokenizer
from huggingface_hub import HfApi
import s8_core as C
m, out, started, k = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
block = manifest.identity_block(m)
manifest.check_pin(block, "v1.2.0", os.environ["PIPE_COMMIT"])            # refuses any other pipeline commit
tm = modelcfg.target(); tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"]); ser = modelcfg.serializer()
opt = readout.option_token_ids(tok); tr = readout.HTTPTransport(); served = modelcfg.models()["endpoint"]["served_model_name"]


class HTTPKernel:
    def __init__(self):
        self.calls = 0; self.mass_sum = 0.0; self.mass_max = 0.0

    def __call__(self, msgs):
        self.calls += 1
        r = readout.readout(tr, served, ser.apply_to_tokenizer(tok, msgs), opt)
        self.mass_sum += r["non_option_mass"]; self.mass_max = max(self.mass_max, r["non_option_mass"])
        return {"logp_A": r["logp"]["A"], "logp_B": r["logp"]["B"], "non_option_mass": r["non_option_mass"]}


clusters = json.load(open("/root/s8/clusters.json")); prm = json.load(open("/root/s8/params.json")); probes = json.load(open("/root/s8/probes.json"))
T = prm["T"][m]
pod = os.environ.get("RUNPOD_POD_ID", "pod")
ss = {"id": f"{pod}/start{k}/{started}", "pod": pod, "index": k, "started_at": started, "cold": True,
      "caches_cleared": os.environ["CACHES"].split()}
man = {"gate": "S8", "model": m, "identity_block": block, "server_start": ss, "stpt_commit": os.environ["STPT_COMMIT"],
       "pins": json.loads(os.environ["STPT_PINS_JSON"]), "payload_sha256": os.environ["STPT_PAYLOAD_SHA256"], "T": T, "params": prm}
K = HTTPKernel()
def rd():
    out_ = []
    for p in probes:
        r = K(p); out_.append(round(r["logp_A"] - r["logp_B"], 9))
    return out_
begin = rd()
api = HfApi()
for c in [c for c in clusters if c["start"] == k]:
    c0 = K.calls; t0 = time.time()
    res = C.run_cluster(c, T, K, prm)
    rec = {"model": m, "manifest": man, "result": res, "model_calls": K.calls - c0}
    open(f"{out}/s8_{m}_c{c['cluster']}.json.gz", "wb").write(gzip.compress(json.dumps(rec).encode()))
    print(m, "start", k, "cluster", c["cluster"], c["rule"], c["setting"], "calls", K.calls - c0, "seconds", round(time.time() - t0, 1), flush=True)
    try:
        api.upload_folder(repo_id=os.environ["STPT_RESULTS_REPO"], repo_type="dataset", folder_path=out,
                          path_in_repo=f"stpt/S8/{os.environ['STPT_RUN_ID']}", commit_message=f"S8 {m} cluster {c['cluster']}")
    except Exception as e:
        print("upload failed", e, flush=True)
end = rd()
json.dump({"model": m, "start": k, "server_start": ss, "begin": begin, "end": end, "identical": begin == end,
           "non_option_mass_mean": K.mass_sum / max(K.calls, 1), "non_option_mass_max": K.mass_max, "calls": K.calls},
          open(f"{out}/s8_{m}_probes_start{k}.json", "w"))
print(m, "start", k, "probes identical", begin == end, "calls", K.calls, flush=True)
PYX
    else
      echo "STOP for $M start $K: vLLM did not come up"; tail -40 "$OUT/logs/vllm_${M}_start$K.log"
    fi
    kill $VPID 2>/dev/null; sleep 5; pkill -9 -f "[v]llm.entrypoints" 2>/dev/null
    for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do kill -9 "$p" 2>/dev/null; done; sleep 5
    upload
  done
  rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"
done
step "done"; touch "$OUT/DONE"; upload
runpodctl remove pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1
