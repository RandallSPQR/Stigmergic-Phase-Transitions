"""CPU reproduction of final ledger upload failure on de1cb9a. No cloud calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
stage = 'gemma-2-9b-it:core'
work = Path(tempfile.mkdtemp(prefix='stpt-de1cb9a-final-upload-'))
caps = work / 'caps.json'
caps.write_text(json.dumps({'status': 'APPROVED', 'caps_usd': {stage: 10.0}, 'usd_per_gpu_hour': 3.6}))
result = {}
for mode in ('final_upload_fails', 'final_upload_succeeds_on_last_retry'):
    ws = work / mode
    out = ws / 'out' / 'test-run'
    out.mkdir(parents=True)
    marker = ws / 'UPLOAD_PENDING'
    marker.touch()
    env = {**os.environ, 'S10_SOURCE_ONLY': '1', 'STPT_WORKSPACE': str(ws),
           'STPT_RUN_ID': 'test-run', 'STPT_SRC': str(root), 'STPT_ACK': '',
           'STPT_MODELS': 'gemma-2-9b-it', 'USD_PER_GPU_HOUR': '3.6',
           'STPT_MARKER': str(marker), 'UPL': '', 'WDOG': ''}
    script = r'''
source "$1/gates/S10/gpu/s10_driver.sh"
run_ledger() { "$TEST_PY" "$TEST_ROOT/gates/S10/run/ledger.py" "$1" --out "$OUT" --caps "$TEST_CAPS" "${@:2}"; }
TEST_ROOT=$1; TEST_PY=$2; TEST_CAPS=$3; TEST_MODE=$4
ledger() { run_ledger "$@"; }
ledger open --stage gemma-2-9b-it:core
attempts=0; final_sleep=0
is_final() { "$TEST_PY" -c 'import json,sys; sys.exit(not (json.load(open(sys.argv[1])).get("closed") or {}).get("final"))' "$OUT/ledger.json"; }
sleep() { if is_final; then final_sleep=$((final_sleep + $1)); echo "$final_sleep" > "$OUT/final_sleep"; fi; }
upload() {
    if is_final; then
        attempts=$((attempts + 1))
        if [[ "$TEST_MODE" = final_upload_fails || $attempts -lt 6 ]]; then return 1; fi
    fi
    cp "$OUT/ledger.json" "$OUT/remote_ledger.json"
}
finish 0
'''
    p = subprocess.run(['bash', '-c', script, 'review', str(root), sys.executable, str(caps), mode],
                       env=env, capture_output=True, text=True, timeout=30)
    local = json.loads((out / 'ledger.json').read_text())
    remote = json.loads((out / 'remote_ledger.json').read_text())
    result[mode] = {'exit': p.returncode, 'marker_kept': marker.exists(),
                    'local_ledger_final': local['closed']['final'],
                    'remote_ledger_final': bool((remote.get('closed') or {}).get('final')),
                    'final_upload_allowance_s': local['final_upload_allowance_s'],
                    'final_upload_retry_sleep_s': int((out / 'final_sleep').read_text()),
                    'stdout': p.stdout, 'stderr': p.stderr}
print(json.dumps(result, indent=2))
