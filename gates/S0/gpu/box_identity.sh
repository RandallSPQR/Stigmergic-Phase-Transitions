#!/bin/bash
# Gate S0, GPU part: the pipeline's box identity check for the five lineup models, on ONE pod, models in sequence.
# Runs ON THE POD (started by gates/S0/gpu/launch.py). Implements the steps of the pipeline's
# pipeline/lineup/pod/serve_lineup.sh with the pipeline's own functions and console scripts. That script is not used:
# in v1.2.0 it calls `python -m lineup.serve`, which cannot import `lineup` from an installed copy (logged in the
# coordination record). Per model:
#   1 weights at the pinned revision; calibrate.preflight_weights --hash must reproduce the lineup weight_hash
#   2 modelcfg.check_tokenizer, template_agreement, and agreement on system-free conversations, on the real tokenizer
#   3 vLLM from `lineup-serve-cmd` (vLLM 0.19.1 stack, batch size 1, raw logprobs, seeded, prefix cache off)
#   4 readouts on three prompts: 8 identical requests each (bit-identity), the exact-fallback consistency check
#   5 the server restarted, the three prompts read again: identical across restarts?
#   6 weights deleted; results uploaded (after every model, so partial results survive)
# Environment: HF_TOKEN (RunPod secret), STPT_RESULTS_REPO, STPT_RUN_ID, PIPE_COMMIT. No other credential on the pod.
set -uo pipefail
OUT=/root/out/$STPT_RUN_ID; mkdir -p "$OUT/logs"; touch /tmp/pod_driven
export HF_HOME=/root/hf HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TOKENIZERS_PARALLELISM=false
exec > >(tee -a "$OUT/logs/driver.log") 2>&1
step() { echo "=== $(date -u +%FT%TZ) $*"; }
PY=/root/venv/bin/python; VPY=/root/venv_vllm_lineup/bin/python

upload() {   # direct commit if the token may write, else one pull request reused for later uploads
  $PY - "$OUT" <<'PYX' || echo "upload failed (results stay on the pod until the deadline)"
import os, sys, json
from huggingface_hub import HfApi
api, repo, out = HfApi(), os.environ["STPT_RESULTS_REPO"], sys.argv[1]
dest = f"stpt/S0/box_identity/{os.environ['STPT_RUN_ID']}"
state = "/root/upload_state.json"
st = json.load(open(state)) if os.path.exists(state) else {}
kw = dict(repo_id=repo, repo_type="dataset", folder_path=out, path_in_repo=dest, commit_message=f"S0 box identity {os.path.basename(out)}")
try:
    if st.get("revision"):
        api.upload_folder(revision=st["revision"], **kw)
    else:
        api.upload_folder(**kw)
    print("uploaded", st.get("revision", "main"))
except Exception as e:
    if st.get("revision"):
        raise
    print("direct commit refused:", type(e).__name__, str(e)[:200], "-> pull request")
    r = api.upload_folder(create_pr=True, **kw)
    st["revision"] = r.pr_revision if hasattr(r, "pr_revision") else str(r).split("/tree/")[-1]
    json.dump(st, open(state, "w")); print("uploaded to", st["revision"])
PYX
}

step "stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
uv() { python3 -m uv "$@"; }       # uv provides the lineup's Python 3.11 (lineup.yaml serving.python)
uv venv -q -p 3.11 /root/venv_vllm_lineup && uv pip install -q -p $VPY "vllm==0.19.1" "torch==2.10.0" "transformers==5.5.3" \
  "tokenizers==0.22.2" "huggingface-hub==1.10.2" > "$OUT/logs/pip_vllm.log" 2>&1
uv venv -q -p 3.11 /root/venv && uv pip install -q -p $PY "transformers==5.17.0" jinja2 \
  "sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT" > "$OUT/logs/pip_pipe.log" 2>&1
$VPY -c "import sys, vllm, torch, transformers; print(sys.version.split()[0], 'vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.version.cuda, 'transformers', transformers.__version__, torch.cuda.get_device_name(0))" | tee "$OUT/stack.txt"
[ -s "$OUT/stack.txt" ] || { echo "STOP: vLLM stack did not install"; upload; exit 3; }
$PY -c "import sae_ethos_pipeline as s; print(s.__version__)" | tee -a "$OUT/stack.txt"
upload

for M in llama-3.1-8b-it gemma-2-9b-it qwen3.5-9b gemma-3-27b-it qwen3.5-27b; do
  step "$M: weights"
  export MODEL_PROFILE_FILE=$($PY -c "import sae_ethos_pipeline, lineup; print(lineup.profile_path('$M'))")
  read HFID REV WANT < <($PY -c "import sae_ethos_pipeline, lineup; e=lineup.models()['$M']; print(e['hf_id'], e['revision'], e['weight_hash'])")
  $PY -c "from huggingface_hub import snapshot_download as s; s('$HFID', revision='$REV', allow_patterns=['*.json','*.safetensors','tokenizer*','*.jinja','*.model','merges.txt','vocab.json'])" \
    > "$OUT/logs/download_$M.log" 2>&1
  ROOTDIR=$($PY -c 'import sae_ethos_pipeline as s; print(s.ROOT)')
  (cd "$ROOTDIR" && $PY -m calibrate.preflight_weights --repo "$HFID" --revision "$REV" --allow '*.json' '*.safetensors' 'tokenizer*' \
     --hash --out "$OUT/preflight_$M.json") > "$OUT/logs/preflight_$M.log" 2>&1
  GOT=$($PY -c "import json; print(json.load(open('$OUT/preflight_$M.json'))['repos'][0]['weight_hash'])" 2>/dev/null)
  echo "$M weight_hash got=$GOT want=$WANT"

  step "$M: tokenizer"
  $PY - "$M" "$OUT/tokenizer_$M.json" <<'PYX'
import json, sys, sae_ethos_pipeline, modelcfg
from transformers import AutoTokenizer
tm = modelcfg.target(); tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"])
ser = modelcfg.serializer(); kw = dict(tm.get("chat_template_kwargs") or {})
convs = [[{"role": "user", "content": "Say hi."}],
         [{"role": "user", "content": "Your evidence: the left door is warm.\nYour current vote: B.\nYour contacts' votes: A, B, A, A.\n\nWhich option do you vote for now? Answer with one letter: A or B."}],
         [{"role": "user", "content": "Say hi."}, {"role": "assistant", "content": "Hi."}, {"role": "user", "content": "Again."}]]
sf = []
for c in convs:
    t = tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True, **kw)
    b = tok.bos_token or ""; t = t[len(b):] if b and t.startswith(b) else t
    sf.append(ser.serialize_messages(c) == t)
r = {"check_tokenizer": modelcfg.check_tokenizer(tok), "template_agreement": modelcfg.template_agreement(tok), "system_free_agreement": sf}
json.dump(r, open(sys.argv[2], "w"), indent=1); print(json.dumps(r)[:400])
PYX

  step "$M: serve"
  CMD=$(LINEUP_VLLM_PYTHON=$VPY /root/venv/bin/lineup-serve-cmd "$M"); echo "$CMD" > "$OUT/serve_cmd_$M.txt"
  for RUN in 1 2; do
    bash -c "$CMD" > "$OUT/logs/vllm_${M}_$RUN.log" 2>&1 & VPID=$!
    UP=0; for _ in $(seq 1 360); do curl -s localhost:8000/v1/models >/dev/null 2>&1 && { UP=1; break; }; kill -0 $VPID 2>/dev/null || break; sleep 5; done
    if [ $UP = 1 ]; then
      step "$M: readouts (server start $RUN)"
      $PY - "$M" "$OUT/readout_${M}_$RUN.json" <<'PYX'
import json, sys, sae_ethos_pipeline, modelcfg
from transformers import AutoTokenizer
from lineup import readout
tm = modelcfg.target(); tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"]); ser = modelcfg.serializer()
prompts = {"plain": "Two options, A and B. Evidence: the left door is warm. Answer with one letter: A or B.",
           "board": "Your evidence: the left door is warm.\nYour current vote: B.\nYour contacts' votes: A, B, A, A.\n\nWhich option do you vote for now? Answer with one letter: A or B.",
           "lopsided": "Option A is correct. Answer with one letter: A or B."}
t, served, opt = readout.HTTPTransport(), modelcfg.models()["endpoint"]["served_model_name"], readout.option_token_ids(tok)
r = {}
for k, text in prompts.items():
    ids = ser.apply_to_tokenizer(tok, [{"role": "user", "content": text}])
    r[k] = {"n_prompt_tokens": len(ids), "readout": readout.readout(t, served, ids, opt),
            "repeat_probe": readout.repeat_probe(t, served, ids, opt, n=8),
            "fallback_consistency": readout.fallback_consistency(t, served, ids, opt)}
json.dump(r, open(sys.argv[2], "w"), indent=1)
print({k: (v["repeat_probe"]["bit_identical"], v["fallback_consistency"]["ok"], round(v["readout"]["logit_AB"], 4), round(v["readout"]["non_option_mass"], 4)) for k, v in r.items()})
PYX
    else
      echo "STOP for $M: vLLM did not come up (start $RUN)"; tail -40 "$OUT/logs/vllm_${M}_$RUN.log"
    fi
    kill $VPID 2>/dev/null; sleep 5; pkill -9 -f "[v]llm.entrypoints" 2>/dev/null
    for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do kill -9 "$p" 2>/dev/null; done; sleep 5
    [ $UP = 1 ] || break
  done

  step "$M: summary"
  $PY - "$M" "$OUT" "$WANT" <<'PYX'
import json, os, sys, sae_ethos_pipeline
from lineup import manifest
m, out, want = sys.argv[1:4]
ld = lambda f: json.load(open(f)) if os.path.exists(f) else None
pf, tk, r1, r2 = ld(f"{out}/preflight_{m}.json"), ld(f"{out}/tokenizer_{m}.json"), ld(f"{out}/readout_{m}_1.json"), ld(f"{out}/readout_{m}_2.json")
rep = pf["repos"][0] if pf else {}
s = {"model": m, "identity_block": manifest.identity_block(m),
     "weight_hash": rep.get("weight_hash"), "weight_hash_ok": rep.get("ok") and rep.get("weight_hash") == want,
     "files_verified": f"{rep.get('files_verified')}/{rep.get('files_expected')}", "verified_by": rep.get("verified_by"),
     "tokenizer_ok": bool(tk) and tk["template_agreement"].get("agree") in (True, None) and all(tk["system_free_agreement"]),
     "template_agreement": tk and tk["template_agreement"].get("agree"),
     "bit_identical_repeats": bool(r1) and all(v["repeat_probe"]["bit_identical"] for v in r1.values()),
     "fallback_consistent": bool(r1) and all(v["fallback_consistency"]["ok"] for v in r1.values()),
     "identical_across_restart": bool(r1 and r2) and all(r1[k]["readout"]["logp"] == r2[k]["readout"]["logp"] for k in r1),
     "max_restart_diff_nats": (max(abs(r1[k]["readout"]["logp"][o] - r2[k]["readout"]["logp"][o]) for k in r1 for o in r1[k]["readout"]["logp"]) if r1 and r2 else None)}
s["pass"] = bool(s["weight_hash_ok"] and s["tokenizer_ok"] and s["bit_identical_repeats"] and s["fallback_consistent"])
json.dump(s, open(f"{out}/summary_{m}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in s.items() if k != "identity_block"}))
PYX
  rm -rf "$HF_HOME/hub/models--${HFID//\//--}"
  upload
done
step "done"; touch "$OUT/DONE"; upload
# self-terminate (pod-scoped key RunPod injects); the launcher also terminates once it sees DONE
curl -s -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID"
