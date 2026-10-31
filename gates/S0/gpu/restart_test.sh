#!/bin/bash
# Restart-determinism test (owner's option b, 2026-10-31), on the GPU type StPT will serve on (RTX PRO 6000 Blackwell).
# Runs ON THE POD (gates/S0/gpu/launch.py --driver restart_test.sh). Question: which serving settings make logprobs
# bit-identical across COLD server starts (every compile / autotune cache cleared before each start, as on a fresh pod)?
#   C1 notune     torch.compile max-autotune and coordinate-descent tuning off; FlashInfer autotune off
#   C2 batchinv   VLLM_BATCH_INVARIANT=1
#   C3 eager      --enforce-eager
# Phase 1 (screen): llama-3.1-8b-it and qwen3.5-9b (both drifted at S0), 2 cold starts per config.
# Winner = the first of C1, C2, C3 identical across its starts for both screening models.
# Phase 2 (confirm): the winner on all five models (3rd start for the screening models, 2 starts for the others).
# Every start: 3 prompts x 4 identical requests (within-start identity), 20 timed calls (per-call latency).
# Nothing here changes the pipeline; a winning setting becomes a candidate for pipeline v1.2.1 (owner's decision).
set -uo pipefail
OUT=/root/out/$STPT_RUN_ID; mkdir -p "$OUT/logs"; touch /tmp/pod_driven
export HF_HOME=/root/hf HF_HUB_DISABLE_TELEMETRY=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TOKENIZERS_PARALLELISM=false
exec > >(tee -a "$OUT/logs/driver.log") 2>&1
echo "=== $(date -u +%FT%TZ) stack"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee "$OUT/gpu.txt"
python3 -m pip install -q uv >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages uv >/dev/null 2>&1
uv() { python3 -m uv "$@"; }
uv venv -q -p 3.11 /root/venv_vllm_lineup && uv pip install -q -p /root/venv_vllm_lineup/bin/python "vllm==0.19.1" "torch==2.10.0" \
  "transformers==5.5.3" "tokenizers==0.22.2" "huggingface-hub==1.10.2" > "$OUT/logs/pip_vllm.log" 2>&1
uv venv -q -p 3.11 /root/venv && uv pip install -q -p /root/venv/bin/python "transformers==5.17.0" jinja2 \
  "sae-ethos-pipeline @ git+https://github.com/RandallSPQR/SAE-Ethos-Calibration@$PIPE_COMMIT" > "$OUT/logs/pip_pipe.log" 2>&1
/root/venv_vllm_lineup/bin/python -c "import sys, vllm, torch; print(sys.version.split()[0], 'vllm', vllm.__version__, 'torch', torch.__version__, torch.cuda.get_device_name(0))" | tee "$OUT/stack.txt"

/root/venv/bin/python - "$OUT" <<'PYX'
import json, os, shutil, statistics, subprocess, sys, time, urllib.request
import sae_ethos_pipeline, lineup, modelcfg, importlib
from lineup import readout, serve
from huggingface_hub import HfApi, snapshot_download
from transformers import AutoTokenizer

OUT = sys.argv[1]; T0 = time.time(); BUDGET_S = float(os.environ.get("STPT_BUDGET_S", "3000"))
VPY = "/root/venv_vllm_lineup/bin/python"
CONFIGS = {
    "C1_notune": ({"VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE": "0", "VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING": "0"},
                  ["--kernel-config", '{"enable_flashinfer_autotune": false}']),
    "C2_batchinv": ({"VLLM_BATCH_INVARIANT": "1"}, []),
    "C3_eager": ({}, ["--enforce-eager"]),
}
if os.environ.get("STPT_CONFIGS"):          # follow-up runs name their own configs: {"name": [env, flags], ...}
    CONFIGS = {k: (v[0], v[1]) for k, v in json.loads(os.environ["STPT_CONFIGS"]).items()}
SCREEN = (os.environ.get("STPT_SCREEN_MODELS") or "llama-3.1-8b-it qwen3.5-9b").split()
PHASE2 = os.environ.get("STPT_PHASE2", "1") == "1"
PROMPTS = {"plain": "Two options, A and B. Evidence: the left door is warm. Answer with one letter: A or B.",
           "board": "Your evidence: the left door is warm.\nYour current vote: B.\nYour contacts' votes: A, B, A, A.\n\nWhich option do you vote for now? Answer with one letter: A or B.",
           "lopsided": "Option A is correct. Answer with one letter: A or B."}
CACHES = ["/root/.cache/vllm", "/tmp/torchinductor_root", "/root/.triton", "/root/.cache/flashinfer", "/root/.nv",
          "/root/.cache/torch", "/root/.cache/triton"]
api = HfApi(); state = {}
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def upload():
    kw = dict(repo_id=os.environ["STPT_RESULTS_REPO"], repo_type="dataset", folder_path=OUT,
              path_in_repo=f"stpt/S0/restart_test/{os.environ['STPT_RUN_ID']}", commit_message="S0 restart test")
    try:
        api.upload_folder(revision=state["rev"], **kw) if state.get("rev") else api.upload_folder(**kw)
    except Exception as e:
        if state.get("rev"):
            log("upload failed", e); return
        r = api.upload_folder(create_pr=True, **kw); state["rev"] = getattr(r, "pr_revision", None)


def setup(model):
    os.environ["MODEL_PROFILE_FILE"] = str(lineup.profile_path(model)); importlib.reload(modelcfg)
    e = lineup.models()[model]
    snapshot_download(e["hf_id"], revision=e["revision"],
                      allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.jinja", "*.model", "merges.txt", "vocab.json"])
    tok = AutoTokenizer.from_pretrained(e["hf_id"], revision=e["revision"])
    ser = modelcfg.serializer()
    ids = {k: ser.apply_to_tokenizer(tok, [{"role": "user", "content": v}]) for k, v in PROMPTS.items()}
    return ids, readout.option_token_ids(tok), modelcfg.models()["endpoint"]["served_model_name"]


def one_start(model, cfg, n, ids, opt, served):
    for c in CACHES:
        shutil.rmtree(c, ignore_errors=True)
    env_add, flags = CONFIGS[cfg]
    env = {**os.environ, **serve.env(), **env_add}
    argv = serve.vllm_argv(model, python=VPY) + flags
    logf = open(f"{OUT}/logs/vllm_{model}_{cfg}_{n}.log", "w")
    t = time.time(); p = subprocess.Popen(argv, env=env, stdout=logf, stderr=subprocess.STDOUT)
    up = False
    for _ in range(240):
        try:
            urllib.request.urlopen("http://localhost:8000/v1/models", timeout=5); up = True; break
        except Exception:
            if p.poll() is not None:
                break
            time.sleep(5)
    rec = {"model": model, "config": cfg, "start": n, "argv": argv[1:], "env": env_add, "up": up,
           "startup_s": round(time.time() - t, 1)}
    if up:
        tr = readout.HTTPTransport()
        rec["logp"], rec["within_identical"] = {}, True
        for k, x in ids.items():
            reads = [readout.readout(tr, served, x, opt) for _ in range(4)]
            rec["logp"][k] = reads[0]["logp"]
            rec["within_identical"] &= all(r["logp"] == reads[0]["logp"] for r in reads)
            rec.setdefault("non_option_mass", {})[k] = reads[0]["non_option_mass"]
        lat = []
        for _ in range(20):
            s = time.perf_counter(); readout.readout(tr, served, ids["board"], opt); lat.append(time.perf_counter() - s)
        rec["latency_ms_median"] = round(1000 * statistics.median(lat), 2)
        rec["latency_ms"] = [round(1000 * v, 2) for v in lat]
    p.terminate()
    try:
        p.wait(timeout=60)
    except Exception:
        p.kill()
    subprocess.run("pkill -9 -f '[v]llm.entrypoints'; for q in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do kill -9 $q; done",
                   shell=True); time.sleep(5)
    json.dump(rec, open(f"{OUT}/start_{model}_{cfg}_{n}.json", "w"), indent=1)
    log(model, cfg, n, "up" if up else "DOWN", rec.get("startup_s"), "s", rec.get("latency_ms_median"), "ms/call",
        "within", rec.get("within_identical"), {k: round(v["A"] - v["B"], 4) for k, v in (rec.get("logp") or {}).items()})
    return rec


def identical(recs):
    ok = [r for r in recs if r["up"]]
    return len(ok) == len(recs) >= 2 and all(r["within_identical"] for r in ok) and all(r["logp"] == ok[0]["logp"] for r in ok)


def maxdiff(recs):
    ok = [r for r in recs if r["up"]]
    if len(ok) < 2:
        return None
    return max(abs(r["logp"][k][o] - ok[0]["logp"][k][o]) for r in ok[1:] for k in r["logp"] for o in r["logp"][k])


results = {}
over = lambda: time.time() - T0 > BUDGET_S
for model in SCREEN:                                                                 # phase 1
    ids, opt, served = setup(model)
    for cfg in CONFIGS:
        results[(model, cfg)] = [one_start(model, cfg, n, ids, opt, served) for n in (1, 2)]
    upload()
winner = next((c for c in CONFIGS if all(identical(results[(m, c)]) for m in SCREEN)), None)
log("phase 1 winner:", winner)
if winner and PHASE2:                                                                 # phase 2
    for model in ["llama-3.1-8b-it", "qwen3.5-9b", "gemma-2-9b-it", "gemma-3-27b-it", "qwen3.5-27b"]:
        if over():
            log("budget reached; phase 2 stops before", model); break
        ids, opt, served = setup(model)
        starts = [3] if (model, winner) in results else [1, 2]
        results.setdefault((model, winner), [])
        results[(model, winner)] += [one_start(model, winner, n, ids, opt, served) for n in starts]
        if model in ("gemma-2-9b-it", "gemma-3-27b-it", "qwen3.5-27b"):
            e = lineup.models()[model]
            shutil.rmtree(f"/root/hf/hub/models--{e['hf_id'].replace('/', '--')}", ignore_errors=True)
            shutil.rmtree("/root/hf/xet", ignore_errors=True)
        upload()
summary = {"winner": winner, "elapsed_min": round((time.time() - T0) / 60, 1), "cells": [
    {"model": m, "config": c, "starts": len(r), "up": sum(x["up"] for x in r), "identical_across_starts": identical(r),
     "within_identical": all(x.get("within_identical") for x in r if x["up"]), "max_diff_nats": maxdiff(r),
     "latency_ms_median": statistics.median([x["latency_ms_median"] for x in r if x["up"]]) if any(x["up"] for x in r) else None}
    for (m, c), r in results.items()]}
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1)
for c in summary["cells"]:
    log(c)
open(f"{OUT}/DONE", "w").write("done\n"); upload()
PYX
echo "=== $(date -u +%FT%TZ) done"
runpodctl remove pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >> /root/selfstop.log 2>&1
