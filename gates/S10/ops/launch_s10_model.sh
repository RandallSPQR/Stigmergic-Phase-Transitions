#!/bin/bash
# S10 confirmatory collection, one model's stage on one RTX PRO 6000 (registration §2), data-safe; earlier runs of
# the stage are restored (records) and counted (spend). Args: MODEL HOURS PRIOR_RUNS [--dry-run]
# Env: STPT_ACK (optional): the owner's acknowledged 80% flags, passed to the pod (e.g. gemma-2-9b-it:core).
#      STPT_STAGE (optional): core (default) or secondary.
# STPT_COMMIT is the run code's commit (stpt-run-v1.2.1): the pod script and launcher must be identical to it, and the
# payload files are byte-identical there to the payload below (built at 8f22f97, stpt-run-v1.2).
cd "$(dirname "$0")/../../.."
COMMIT=3404b7e02a119d72871b30c1272c9d420d811391
SHA=4f13741108015b8e98fbd8d4aa6974c6e693a61e6f02dab2fdf4b690f0ef14ea
git diff --quiet "$COMMIT" -- gates/S10/gpu/s10_driver.sh gates/S0/gpu/launch.py \
  || { echo "REFUSED: pod script or launcher differs from $COMMIT"; exit 2; }
python3 gates/S0/gpu/launch.py create $4 --data-safe --volume-gb 20 --repo RandallSPQR/stpt-gate-artifacts --gpu-set rtxpro6000 \
  --driver gates/S10/gpu/s10_driver.sh --hours "$2" --disk 200 --max-live 1 --models "$1" \
  --env PIPE_COMMIT 5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b --env STPT_COMMIT "$COMMIT" \
  --env STPT_PAYLOAD_SHA256 "$SHA" --env STPT_PAYLOAD_HF_PATH "stpt/S10/payload/$SHA.b64" \
  --env STPT_STAGES "${STPT_STAGE:-core}" --env STPT_PRIOR_RUNS "$3" --env USD_PER_GPU_HOUR 2.49 ${STPT_ACK:+--env STPT_ACK "$STPT_ACK"}
