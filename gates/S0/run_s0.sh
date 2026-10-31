#!/bin/bash
# Gate S0: pipeline and harness. CPU parts only (no GPU, no API). Reproduces gates/S0/ from scratch:
#   bash gates/S0/run_s0.sh WORKDIR
# 1 pipeline: install sae-ethos-pipeline at the pinned commit; lineup-identity local + offline (HF API metadata only);
#   the pipeline's lineup tests (needs the Qwen tokenizer files: lineup-fetch-tokenizers)
# 2 SPT replay: fresh clone of the SPT release at the pinned tag; HEAD must be the pinned commit; the release's own
#   hash-locked environment; its replication steps qc.canary s1.cache s1.fits s1.summary (s1.cache rebuilds every Stage 1
#   battery request and checks every committed row against the recorded response cache, offline)
# 3 inherited harness/simulator: every vendored file equals the blob at the pinned SPT commit
# The GPU part of S0 (pipeline box identity check, sae-ethos-pipeline pipeline/lineup/pod/serve_lineup.sh, once per model)
# is separate and needs the owner's OK for GPU spend.
set -euo pipefail
W=${1:?workdir}; mkdir -p "$W"; HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PIPE_COMMIT=$(python3 -c "import yaml;print(yaml.safe_load(open('$REPO/pins.yaml'))['pipeline']['commit'])")
SPT_TAG=$(python3 -c "import yaml;print(yaml.safe_load(open('$REPO/pins.yaml'))['spt']['tag'])")
SPT_COMMIT=$(python3 -c "import yaml;print(yaml.safe_load(open('$REPO/pins.yaml'))['spt']['commit'])")
OUT="$HERE/artifacts"; mkdir -p "$OUT"

echo "== 1 pipeline @ $PIPE_COMMIT"
git clone -q https://github.com/RandallSPQR/SAE-Ethos-Calibration "$W/pipeline" && git -C "$W/pipeline" checkout -q "$PIPE_COMMIT"
[ "$(git -C "$W/pipeline" rev-parse HEAD)" = "$PIPE_COMMIT" ] || { echo "STOP: pipeline commit"; exit 2; }
python3.13 -m venv "$W/venv_pipe" && "$W/venv_pipe/bin/pip" install -q "transformers==5.17.0" jinja2 pytest huggingface_hub -e "$W/pipeline"
(cd "$W/pipeline/pipeline" && "$W/venv_pipe/bin/python" -m lineup.model_io.fetch_tokenizers)
(cd "$W/pipeline" && "$W/venv_pipe/bin/python" -m pytest -q pipeline/lineup/tests) | tee "$OUT/pipeline_lineup_tests.txt"
(cd "$W/pipeline/pipeline" && "$W/venv_pipe/bin/python" -m lineup.identity local --out "$OUT/pipeline_identity_local.json" >/dev/null)
(cd "$W/pipeline/pipeline" && "$W/venv_pipe/bin/python" -m lineup.identity offline --out "$OUT/pipeline_identity_offline.json" >/dev/null)

echo "== 2 SPT replay @ $SPT_TAG ($SPT_COMMIT)"
git clone -q --depth 1 --branch "$SPT_TAG" https://github.com/RandallSPQR/social-phase-transitions-public "$W/spt"
[ "$(git -C "$W/spt" rev-parse HEAD)" = "$SPT_COMMIT" ] || { echo "STOP: SPT tag does not point at the pinned commit"; exit 2; }
python3.13 -m venv "$W/venv_spt" && "$W/venv_spt/bin/pip" install -q --require-hashes -r "$W/spt/replication/requirements.lock"
(cd "$W/spt" && PATH="$W/venv_spt/bin:$PATH" python replication/replicate.py --mode fast --only qc.canary s1.cache s1.fits s1.summary) \
  | tee "$OUT/spt_replay_console.log"
cp "$W/spt/replication/out/REPORT.md" "$OUT/spt_replay_REPORT.md"; cp "$W/spt/replication/out/report.json" "$OUT/spt_replay_report.json"
cp "$W/spt/replication/out/stage1/cache_check.json" "$OUT/spt_replay_cache_check.json"

echo "== 3 inherited files vs the SPT tag"
(cd "$REPO" && python3 -m stpt.inherit verify --spt-checkout "$W/spt" --out "$OUT/inherited_verify.json" >/dev/null)
echo "done: $OUT"
