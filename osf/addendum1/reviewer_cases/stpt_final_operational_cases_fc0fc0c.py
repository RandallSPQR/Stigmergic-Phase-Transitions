"""CPU-only final execution review of fc0fc0c; no GPU or external service calls.
Usage: python stpt-final-operational-cases.py /path/to/Stigmergic-Phase-Transitions
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/'gates/S10'),str(root/'gates/S10/run'),str(root/'gates/S7')]
import driver as DR
import s10_core as C
import s7_core

work=Path(tempfile.mkdtemp(prefix='stpt-final-operational-'))
out={'commit':'fc0fc0c8df704d04e1da70d89bd8cdf1d48ab9ab','output_dir':str(work)}
M='gemma-2-9b-it'; stage=f'{M}:core'

# The real upload function's error handling and the real final teardown.
shell=(root/'gates/S10/gpu/s10_driver.sh').read_text()
upload=shell[shell.index('upload() {'):shell.index('step "stack"')]
tail=shell[shell.index('kill $UPL 2>/dev/null;'):]
fail=work/'fail_upload';fail.write_text('#!/bin/sh\nexit 1\n');fail.chmod(0o755)
outdir=work/'upload-out';outdir.mkdir()
deletions=work/'pod_commands.log'
script='''set -uo pipefail
OUT="$1"; PY="$2"; STPT_RUN_ID=cpu-test; RUNPOD_POD_ID=fake-pod; UPL=fake
kill() { :; }
step() { :; }
runpodctl() { printf '%s\\n' "$*" >> "$3"; }
'''
# Bind the mock removal log without changing the reviewed control flow.
script=script.replace('>> "$3"','>> '+"'"+str(deletions)+"'")
script+=upload+tail.replace('/root/selfstop.log',str(work/'selfstop.log'))
p=subprocess.run(['bash','-c',script,'review',str(outdir),str(fail)],capture_output=True,text=True)
out['upload_failure']={'exit_code':p.returncode,'stdout':p.stdout.strip(),
 'DONE_written':(outdir/'DONE').exists(),'pod_commands':deletions.read_text().splitlines() if deletions.exists() else []}

# Startup consumes billable time before the next cap check, with no model calls.
class Clock:
 def __init__(self):self.t=0.0
 def __call__(self):return self.t
clk=Clock()
class SlowServer:
 def start(self):
  clk.t+=1000
  return {'id':'fake/start1/t','attached':False}
 def stop(self):pass
k=s7_core.MockKernel()
d=DR.Driver(M,k,SlowServer(),lambda m:{},{stage:.2},work/'startup',3.6,{},mock=True,clock=clk,ack_flags=(stage,))
status=d.run(blocks=[1])
out['startup_cap']={'cap_usd':.2,'status':status,'spent_usd':d.ledger.d['spent_usd'][stage],'model_calls':k.calls}

# The readout supplies non-A/B mass; test whether the run result preserves it.
class WithMass(s7_core.MockKernel):
 def __call__(self,msgs):
  return {**super().__call__(msgs),'non_option_mass':.123456789}
r=C.run_cluster(C.load_clusters()[1],M,WithMass())
def mass_fields(obj,prefix=''):
 if isinstance(obj,dict):
  return [prefix+'/'+str(k) for k in obj if 'mass' in str(k).lower()]+[x for k,v in obj.items() for x in mass_fields(v,prefix+'/'+str(k))]
 if isinstance(obj,list):
  return [x for i,v in enumerate(obj) for x in mass_fields(v,prefix+'/'+str(i))]
 return []
out['non_option_mass']={'readout_supplied_mass':.123456789,'mass_fields_in_run_result':mass_fields(r)}
(work/'results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
