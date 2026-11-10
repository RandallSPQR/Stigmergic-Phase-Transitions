#!/bin/bash
# Launch one model's secondary stage, avoiding a slow machine (D61). Args: MODEL HOURS [PRIORS...]; env BAD (default
# 4scjboia96mu). A pod that lands on BAD is deleted at once and its
# lifetime charged (rounded up to whole minutes plus 2, at $2.49/h, plus $0.02 storage) in <run>-adjustment, which the
# next attempt lists as a prior run so the cumulative cap counts it.
MODEL=$1; HOURS=$2; shift 2
BAD=${BAD:-4scjboia96mu}
SP=/tmp/claude-0/-home-user/287669f2-bde2-5fec-ab29-de393ea1aa41/scratchpad
V=/tmp/claude-0/-home-user-Social-Phase-Transitions/287669f2-bde2-5fec-ab29-de393ea1aa41/scratchpad/venv/bin/python
PRIORS="$*"
cd /home/user/stigmergic-phase-transitions
for i in $(seq 1 12); do
  r=$(STPT_STAGE=secondary STPT_ACK=$MODEL:secondary gates/S10/ops/launch_s10_model.sh $MODEL $HOURS "$PRIORS" 2>&1)
  if ! echo "$r" | grep -q '"id"'; then echo "$(date -u +%H:%M:%S) attempt $i: $(echo "$r" | tail -1 | cut -c1-100)"; sleep 120; continue; fi
  J=$(echo "$r" | sed -n '/^{/,$p'); POD=$(echo "$J" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
  RUN=$(echo "$J" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])"); T0=$(date +%s)
  M=""; for k in $(seq 1 12); do
    M=$(curl -s -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" https://api.runpod.io/graphql \
      -d "{\"query\":\"query { pod(input:{podId:\\\"$POD\\\"}) { machineId } }\"}" | python3 -c "import json,sys; print((json.load(sys.stdin).get('data') or {}).get('pod',{}).get('machineId') or '')" 2>/dev/null)
    [ -n "$M" ] && break; sleep 5
  done
  if [ "$M" = "$BAD" ]; then
    python3 gates/S0/gpu/launch.py terminate --pod "$POD" --why "landed on slow machine $BAD; deleted at once (D61)" >/dev/null 2>&1
    SECS=$(( $(date +%s) - T0 + 30 )); USD=$(python3 -c "import math; print(round((math.ceil($SECS/60)+2)*2.49/60+0.02, 4))")
    python3 -c "import json; json.dump({'spent_usd':{'$MODEL:secondary':$USD},'flagged':{},'acked':{},'note':'Pod $POD (run $RUN) landed on the slow machine $BAD and was deleted at once (D61); its lifetime (about $SECS s) is charged conservatively: whole minutes plus 2 at \$2.49/h, plus \$0.02 storage.'}, open('$SP/adj_$RUN.json','w'), indent=1)"
    HF_HUB_DISABLE_XET=1 $V -c "
from huggingface_hub import HfApi
HfApi().upload_file(path_or_fileobj='$SP/adj_$RUN.json', path_in_repo='stpt/S10/$RUN-adjustment/ledger.json', repo_id='RandallSPQR/stpt-gate-artifacts', repo_type='dataset', commit_message='S10: spend for pod $POD, deleted on the slow machine (D61)')" >/dev/null 2>&1 \
      || { echo "adjustment upload failed for $RUN; stopping"; exit 3; }
    PRIORS="$PRIORS $RUN-adjustment"
    echo "$(date -u +%H:%M:%S) attempt $i: $POD on $BAD, deleted; charged \$$USD as $RUN-adjustment"; sleep 90; continue
  fi
  echo "$(date -u +%H:%M:%S) LAUNCHED $POD (run $RUN) on machine ${M:-unknown}; priors: $PRIORS"; echo "$J" > $SP/s10_sec_${MODEL}_launch.json; exit 0
done
echo "no launch on another machine after 12 attempts"; exit 4
