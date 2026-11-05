"""Reproduce three launcher/adapter integration gaps on 0778869 without cloud calls.
Usage: python stpt-0778869-launch-path-cases.py /path/to/Stigmergic-Phase-Transitions
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root), str(root/'gates/S10'), str(root/'gates/S10/run')]
import ledger as LG
import pod
import s10_core as C
from stpt import board as B

work = Path(tempfile.mkdtemp(prefix='stpt-0778869-launch-'))
stage = 'gemma-2-9b-it:core'
caps = work/'caps.json'
caps.write_text(json.dumps({'status':'APPROVED','caps_usd':{stage:10.0},'usd_per_gpu_hour':3.6}))
prior = work/'prior.json'
prior.write_text(json.dumps({'spent_usd':{stage:8.1},'flagged':{stage:True},'acked':{}}))
ledger_cli = [sys.executable, str(root/'gates/S10/run/ledger.py')]
env = {**os.environ, 'STPT_POD_SESSION':'cpu-new-pod', 'STPT_ACK':stage, 'USD_PER_GPU_HOUR':'3.6'}
def ledger_command(command, *args):
    return subprocess.run(ledger_cli + [command,'--out',str(work),'--caps',str(caps),*args],
                          env=env, capture_output=True, text=True, check=False)

seed = ledger_command('seed','--prior',str(prior))
opened = ledger_command('open','--stage',stage)
out = {'commit':'0778869c087b22902c00a1122fba92245dbe4a93',
       'acknowledged_new_pod_resume':{'seed_rc':seed.returncode,'STPT_ACK':stage,
           'open_rc':opened.returncode,'open_output':opened.stdout.strip(),
           'ack_in_ledger':json.loads((work/'ledger.json').read_text())['acked']}}

class Clock:
    t = 0.0
    def __call__(self): return self.t

clk = Clock()
u = work/'upload'; u.mkdir()
L = LG.Ledger(u/'ledger.json',{stage:0.2},3.6,clk,session='same-pod')
L.begin(stage)
clk.t = 100.0
L.close()   # Driver.run() finally, after finishing or stopping the model.
clk.t = 1100.0   # 1000 more billable seconds in the final upload/retry phase.
watchdog = LG.watchdog_once(u,{stage:0.2},3.6,now=clk.t)
L2 = LG.Ledger(u/'ledger.json',{stage:0.2},3.6,clk,session='same-pod')
L2.close()  # finish() issues ledger.py close; there is no open interval to charge.
out['final_upload_gap'] = {'simulated_billable_usd':1.1,'recorded_usd':L2.spent(stage),
                           'watchdog_stop':watchdog,'cap_usd':0.2}

# Exercise the real HTTP adapter with a fake readout that omits mass.
k = pod.HTTPKernel.__new__(pod.HTTPKernel)
k.calls = 0; k.mass_max = 0.0
k.tr = k.served = k.tok = k.opt = None
k.ser = SimpleNamespace(apply_to_tokenizer=lambda tok,msgs:msgs)
k.readout = lambda *args: {'logp':{'A':-0.7,'B':-0.8}}
c = C.load_clusters()[1]
board = C.make_board(c['spec'],c['alloc'],c['adj'],c['run_key'],True,C.primary_T('gemma-2-9b-it'))
try:
    rec = B.update(board,B.State(0,['A']*100),C.MassRecorder(k))
    out['actual_adapter_missing_mass'] = {'stopped':False,'attempts':k.calls,'counted_as_missing':rec.get('missing',False)}
except C.ProtocolError as e:
    out['actual_adapter_missing_mass'] = {'stopped':True,'attempts':k.calls,'error':str(e)}

dest = work/'results.json'
dest.write_text(json.dumps(out,indent=2)+'\n')
print(dest)
print(json.dumps(out,indent=2))
