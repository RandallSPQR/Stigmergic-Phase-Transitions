#!/bin/bash
# Gate S3 on the pod (gates/S3/S3_PLAN.md): the comprehension prompt set through the five lineup models, exact A/B
# readouts, one server start per model. Started by gates/S0/gpu/launch.py --driver gates/S3/gpu/s3_driver.sh.
# Env: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT, STPT_COMMIT, STPT_PINS_JSON,
#      STPT_PROMPTS_B64 (gzip+base64 of the prompt set), STPT_PROMPTS_SHA256, STPT_MODELS (optional subset).
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
                      path_in_repo=f"stpt/S3/{os.environ['STPT_RUN_ID']}", commit_message="S3 comprehension")
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
step "prompts"
$PY - "$OUT" <<'PYX' || { echo "STOP: prompt set"; upload; exit 3; }
import base64, gzip, hashlib, json, os, sys
b64 = os.environ.get("STPT_PROMPTS_B64") or "".join(os.environ[f"STPT_PROMPTS_B64_{i}"] for i in range(int(os.environ["STPT_PROMPTS_PARTS"])))
d = json.loads(gzip.decompress(base64.b64decode(b64)))
blob = json.dumps(d, sort_keys=True, indent=1)
h = hashlib.sha256(blob.encode()).hexdigest()
assert h == os.environ["STPT_PROMPTS_SHA256"], f"prompt set sha256 {h} != committed"
open("/root/s3_prompts.json", "w").write(blob)
print("prompt set verified", h[:16], d["n"])
PYX
for M in ${STPT_MODELS:-llama-3.1-8b-it gemma-2-9b-it qwen3.5-9b gemma-3-27b-it qwen3.5-27b}; do
  step "$M: weights"; df -h / | tail -1
  export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
  read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
  $PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" > "$OUT/logs/download_$M.log" 2>&1
  ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
  (cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' --hash --out "$OUT/preflight_$M.json")   # --hash: with huggingface-hub 1.x (xet) cache blob names are not the LFS sha256, so the blob-name mode cannot verify (S3 first pod) > "$OUT/logs/preflight_$M.log" 2>&1
  GOT=$($PY -c "import json; print(json.load(open('$OUT/preflight_$M.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
  if [ "$GOT" != "$WANT" ]; then echo "STOP for $M: weight_hash $GOT != $WANT"; rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"; upload; continue; fi
  step "$M: serve"
  STARTED=$(date -u +%FT%TZ)
  CMD=$(LINEUP_VLLM_PYTHON=$VPY /root/venv/bin/lineup-serve-cmd "$M"); echo "$CMD" > "$OUT/serve_cmd_$M.txt"
  bash -c "$CMD" > "$OUT/logs/vllm_$M.log" 2>&1 & VPID=$!
  UP=0; for _ in $(seq 1 360); do curl -s localhost:8000/v1/models >/dev/null 2>&1 && { UP=1; break; }; kill -0 $VPID 2>/dev/null || break; sleep 5; done
  if [ $UP = 1 ]; then
    step "$M: readouts"
    $PY - "$M" "$OUT" "$STARTED" <<'PYX'
import json, os, sys, time
import sae_ethos_pipeline, modelcfg
from lineup import readout, manifest
from transformers import AutoTokenizer
m, out, started = sys.argv[1:4]
block = manifest.identity_block(m)
manifest.check_pin(block, "v1.2.0", os.environ["PIPE_COMMIT"])            # refuses any other pipeline commit
tm = modelcfg.target(); tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"]); ser = modelcfg.serializer()
opt = readout.option_token_ids(tok); tr = readout.HTTPTransport(); served = modelcfg.models()["endpoint"]["served_model_name"]
P = json.load(open("/root/s3_prompts.json"))
rows, t0 = [], time.time()
for p in P["prompts"]:
    r = readout.readout(tr, served, ser.apply_to_tokenizer(tok, p["messages"]), opt)
    lp = r["logp"]; c = p["correct_letter"]; o = None if c is None else ("B" if c == "A" else "A")
    rows.append({"prompt_id": p["prompt_id"], "qtype": p["qtype"], "wording": p.get("wording", "w1"), "correct_letter": c,
                 "logp_A": lp["A"], "logp_B": lp["B"], "answer": "A" if lp["A"] > lp["B"] else "B",
                 "correct": None if c is None else lp[c] > lp[o],
                 "p_correct_renorm": None if c is None else r["p"][c] / (r["p"]["A"] + r["p"]["B"]),
                 "non_option_mass": r["non_option_mass"], "read_by": r["read_by"], "calls": r["calls"]})
manifest_out = {"gate": "S3", "model": m, "identity_block": block,
                "server_start": {"id": f"{os.environ.get('RUNPOD_POD_ID', 'pod')}/start1/{started}", "pod": os.environ.get("RUNPOD_POD_ID"),
                                 "index": 1, "started_at": started},
                "stpt_commit": os.environ["STPT_COMMIT"], "pins": json.loads(os.environ["STPT_PINS_JSON"]),
                "prompts_sha256": os.environ["STPT_PROMPTS_SHA256"], "seconds": round(time.time() - t0, 1), "n": len(rows)}
json.dump({"manifest": manifest_out, "rows": rows}, open(f"{out}/s3_{m}.json", "w"))
acc = {f"{w}/{q}": round(sum(r["correct"] for r in rows if r["qtype"] == q and r["wording"] == w) / sum(1 for r in rows if r["qtype"] == q and r["wording"] == w), 4)
       for w in sorted({r["wording"] for r in rows}) for q in sorted({r["qtype"] for r in rows if r["correct"] is not None})
       if any(r["qtype"] == q and r["wording"] == w for r in rows)}
print(m, "accuracy", acc, "seconds", manifest_out["seconds"], flush=True)
PYX
  else
    echo "STOP for $M: vLLM did not come up"; tail -40 "$OUT/logs/vllm_$M.log"
  fi
  kill $VPID 2>/dev/null; sleep 5; pkill -9 -f "[v]llm.entrypoints" 2>/dev/null
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do kill -9 "$p" 2>/dev/null; done; sleep 5
  rm -rf "$HF_HOME/hub/models--${HFID//\//--}" "$HF_HOME/xet"
  upload
done
step "done"; touch "$OUT/DONE"; upload
runpodctl remove pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1
