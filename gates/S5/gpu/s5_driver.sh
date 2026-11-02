#!/bin/bash
# Gate S5 on the pod (gates/S5/S5_PLAN.md): the S5 probe set through the five lineup models, STPT_STARTS cold server starts
# per model (every compile / autotune cache cleared before each start, as on a fresh pod), exact A/B readouts.
# In each start: the W3 block, the other wordings' blocks, then the W3 block again (exact within-start repeats).
# Started by gates/S0/gpu/launch.py --driver gates/S5/gpu/s5_driver.sh. Same procedure as the S4 driver.
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PINS_JSON,
#      STPT_CONTEXTS_B64 (gzip+base64 of {contexts, wordings, prompts_py}), STPT_PROMPTS_SHA256, STPT_STARTS, STPT_MODELS,
#      STPT_WORDINGS_BY_MODEL (JSON {model: [wordings valid for it]}, W3 first; D21).
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
                      path_in_repo=f"stpt/S5/{os.environ['STPT_RUN_ID']}", commit_message="S5 responsiveness")
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
step "probes"
$PY - <<'PYX' || { echo "STOP: probe set"; upload; exit 3; }
import base64, gzip, hashlib, importlib.util, json, os
pl = json.loads(gzip.decompress(base64.b64decode(os.environ["STPT_CONTEXTS_B64"])))
open("/root/stpt_prompts.py", "w").write(pl["prompts_py"])
spec = importlib.util.spec_from_file_location("stpt_prompts", "/root/stpt_prompts.py"); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
out = P.build_s4(pl["contexts"], pl["wordings"], 4)
d = {"version": "s5-v1", "wordings": pl["wordings"], "template": "stpt/prompts.py", "n": len(out), "prompts": out}
blob = json.dumps(d, sort_keys=True, indent=1)
h = hashlib.sha256(blob.encode()).hexdigest()
assert h == os.environ["STPT_PROMPTS_SHA256"], f"probe set sha256 {h} != committed"
open("/root/s5_probes.json", "w").write(blob)
print("probe set verified", h[:16], d["n"], d["wordings"])
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
  for K in $(seq 1 ${STPT_STARTS:-3}); do
    rm -rf $CACHES
    step "$M: cold start $K"
    STARTED=$(date -u +%FT%TZ)
    CMD=$(LINEUP_VLLM_PYTHON=$VPY /root/venv/bin/lineup-serve-cmd "$M"); echo "$CMD" > "$OUT/serve_cmd_$M.txt"
    bash -c "$CMD" > "$OUT/logs/vllm_${M}_start$K.log" 2>&1 & VPID=$!
    UP=0; for _ in $(seq 1 360); do curl -s localhost:8000/v1/models >/dev/null 2>&1 && { UP=1; break; }; kill -0 $VPID 2>/dev/null || break; sleep 5; done
    if [ $UP = 1 ]; then
      $PY - "$M" "$OUT" "$STARTED" "$K" <<'PYX'
import json, os, sys, time
import sae_ethos_pipeline, modelcfg
from lineup import readout, manifest
from transformers import AutoTokenizer
m, out, started, k = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
block = manifest.identity_block(m)
manifest.check_pin(block, "v1.2.0", os.environ["PIPE_COMMIT"])            # refuses any other pipeline commit
tm = modelcfg.target(); tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"]); ser = modelcfg.serializer()
opt = readout.option_token_ids(tok); tr = readout.HTTPTransport(); served = modelcfg.models()["endpoint"]["served_model_name"]
P = json.load(open("/root/s5_probes.json"))
mine = json.loads(os.environ.get("STPT_WORDINGS_BY_MODEL", "{}")).get(m, P["wordings"])   # D21: only this model's valid wordings
assert mine[0] == "w3" and set(mine) <= set(P["wordings"]), mine
blocks = [("first", "w3")] + [("first", w) for w in mine if w != "w3"] + [("repeat", "w3")]
rows, t0 = [], time.time()
for read, w in blocks:
    for p in (x for x in P["prompts"] if x["wording"] == w):
        r = readout.readout(tr, served, ser.apply_to_tokenizer(tok, p["messages"]), opt)
        rows.append({"prompt_id": p["prompt_id"], "read": read, "logp_A": r["logp"]["A"], "logp_B": r["logp"]["B"],
                     "non_option_mass": r["non_option_mass"], "read_by": r["read_by"], "calls": r["calls"]})
pod = os.environ.get("RUNPOD_POD_ID", "pod")
manifest_out = {"gate": "S5", "model": m, "identity_block": block,
                "server_start": {"id": f"{pod}/start{k}/{started}", "pod": pod, "index": k, "started_at": started,
                                 "cold": True, "caches_cleared": os.environ["CACHES"].split()},
                "stpt_commit": os.environ["STPT_COMMIT"], "pins": json.loads(os.environ["STPT_PINS_JSON"]),
                "probes_sha256": os.environ["STPT_PROMPTS_SHA256"], "wordings": mine, "probe_set_wordings": P["wordings"],
                "seconds": round(time.time() - t0, 1), "n": len(rows)}
json.dump({"manifest": manifest_out, "rows": rows}, open(f"{out}/s5_{m}_start{k}.json", "w"))
rep = {x["prompt_id"]: x for x in rows if x["read"] == "repeat"}
same = sum((x["logp_A"], x["logp_B"]) == (rep[x["prompt_id"]]["logp_A"], rep[x["prompt_id"]]["logp_B"]) for x in rows if x["read"] == "first" and x["prompt_id"] in rep)
print(m, "start", k, "readouts", len(rows), "repeats identical", same, "of", len(rep), "seconds", manifest_out["seconds"], flush=True)
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
