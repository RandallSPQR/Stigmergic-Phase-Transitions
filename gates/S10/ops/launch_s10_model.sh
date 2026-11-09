#!/bin/bash
# S10 confirmatory collection, one model's stage on one RTX PRO 6000 (registration §2), data-safe; earlier runs of
# the stage are restored (records) and counted (spend). Args: MODEL HOURS PRIOR_RUNS [--dry-run]
# Env: STPT_ACK (optional): the owner's acknowledged 80% flags, passed to the pod (e.g. gemma-2-9b-it:core).
#      STPT_STAGE (optional): core (default) or secondary.
# Run code: stpt-run-v1.2.1 (3404b7e). The pod script, the launcher and the payload's code files must be identical to
# it; the payload (built at COMMIT) differs from v1.2.1's only in the caps file (D58, D59). STPT_COMMIT records COMMIT.
cd "$(dirname "$0")/../../.."
TAG=3404b7e02a119d72871b30c1272c9d420d811391
COMMIT=2f7bf0e24e48841005b84f3da737e1c85c0a292e
SHA=f26677a4b04cb9f28c789752fdcbd70ff0dc3e545f26af975e45bc697a245bbf
git diff --quiet "$TAG" -- gates/S10/gpu/s10_driver.sh gates/S0/gpu/launch.py pins.yaml stpt/__init__.py stpt/board.py \
  stpt/prompts.py gates/S10/s10_core.py gates/S10/run/driver.py gates/S10/run/ledger.py gates/S10/run/pod.py \
  gates/S10/clusters/MANIFEST.json gates/S10/clusters/confirmatory_clusters.json analysis/results/t_options.json \
  || { echo "REFUSED: run code differs from stpt-run-v1.2.1"; exit 2; }
git diff --quiet "$COMMIT" -- gates/S10/run/caps_approved.json || { echo "REFUSED: caps differ from $COMMIT"; exit 2; }
python3 gates/S0/gpu/launch.py create $4 --data-safe --volume-gb 20 --repo RandallSPQR/stpt-gate-artifacts --gpu-set rtxpro6000 \
  --driver gates/S10/gpu/s10_driver.sh --hours "$2" --disk 200 --max-live 1 --models "$1" \
  --env PIPE_COMMIT 5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b --env STPT_COMMIT "$COMMIT" \
  --env STPT_PAYLOAD_SHA256 "$SHA" --env STPT_PAYLOAD_HF_PATH "stpt/S10/payload/$SHA.b64" \
  --env STPT_STAGES "${STPT_STAGE:-core}" --env STPT_PRIOR_RUNS "$3" --env USD_PER_GPU_HOUR 2.49 ${STPT_ACK:+--env STPT_ACK "$STPT_ACK"}
