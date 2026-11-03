"""Additional execution-review cases for StPT bb0f12a. CPU only; no paid/model service calls.

Run with the study's numpy/scipy environment:
    python stpt-reviewer-followup.py /path/to/Stigmergic-Phase-Transitions

Prints the observed behavior. All *_accepted fields below should be false;
cap_overshot_at_branch_boundary, resumed_block_split and unmetered_billable_gap
should also be false. Temporary driver records are kept in output_dir.
"""
import collections
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(ROOT), str(ROOT / 'gates/S10'), str(ROOT / 'gates/S10/analysis'),
               str(ROOT / 'gates/S10/run'), str(ROOT / 'gates/S7')]
import s10_core as C
import s7_core
import confirmatory as CA
import driver as DR

M = 'gemma-2-9b-it'
F = C.load_clusters()
base = Path(tempfile.mkdtemp(prefix='stpt-reviewer-followup-'))
out = {'reviewed_commit': 'bb0f12a9ba070be6d3f2e7e8f414c424e310baeb', 'output_dir': str(base)}
r = C.run_cluster(F[1], M, s7_core.MockKernel())
r['server_start_ids'] = {n: 'pod/start1/t' for n in C.branch_names(F[1], M, 'primary')}
r['mock'] = False
out['baseline_outcomes'] = CA.outcomes(r, F[1]['truth'])

for name in ('initial_vote_valid_letter_changed', 'live_vote_changed_hashes_unchanged',
             'missing_flag_but_vote_changes', 'missing_branch_start_ids'):
    b = copy.deepcopy(r)
    if name == 'initial_vote_valid_letter_changed':
        b['initial_votes'][0] = 'B' if b['initial_votes'][0] == 'A' else 'A'
    elif name == 'live_vote_changed_hashes_unchanged':
        row = b['live'][2499]
        row[4] = 'B' if row[4] == 'A' else 'A'
    elif name == 'missing_flag_but_vote_changes':
        row = b['live'][2499]
        row[7], row[5] = 1, None
        row[4] = 'B' if row[2] == 'A' else 'A'
    else:
        b['server_start_ids'] = {'init': 'pod/start1/t'}
    try:
        o = CA.outcomes(b, F[1]['truth'])
        out[name + '_accepted'] = True
        out[name + '_board_effect'] = o['board']
    except Exception as e:
        out[name + '_accepted'] = False
        out[name + '_refusal'] = str(e)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Server:
    def __init__(self):
        self.n = 0

    def start(self):
        self.n += 1
        return {'id': f'cpu/start{self.n}/t', 'attached': False}

    def stop(self):
        pass


class K(s7_core.MockKernel):
    def __init__(self, clk):
        super().__init__()
        self.clk = clk

    def __call__(self, msgs):
        self.clk.t += 1.0
        return super().__call__(msgs)


# At this artificial rate, one simulated second/model call costs $0.001.
stage = f'{M}:core'
clk, server = Clock(), Server()
k = K(clk)
d = DR.Driver(M, k, server, lambda m: {}, {stage: 0.2}, base / 'cap', 3.6, {},
              mock=True, clock=clk, ack_flags=(stage,))
status = d.run(blocks=[1])
out['cap_stop_status'] = status
out['cap_stop_actual_calls'] = k.calls
out['cap_spent_usd'] = d.ledger.d['spent_usd'][stage]
out['cap_overshot_at_branch_boundary'] = out['cap_spent_usd'] > 0.4

# Cap after one completed cluster but before the rest of its scheduled block.
clk, server = Clock(), Server()
k = K(clk)
d = DR.Driver(M, k, server, lambda m: {}, {stage: 8.0}, base / 'resume', 3.6, {},
              mock=True, clock=clk, ack_flags=(stage,))
out['resume_first_status'] = d.run(blocks=[1])
d = DR.Driver(M, k, server, lambda m: {}, {stage: 1e9}, base / 'resume', 3.6, {},
              mock=True, clock=clk)
out['resume_second_status'] = d.run(blocks=[1])
starts = {}
for p in (base / 'resume' / M).glob('rec_*.json.gz'):
    a = json.loads(gzip.decompress(p.read_bytes()))['result']
    starts[a['cluster']] = sorted(set(a['server_start_ids'].values()))
out['resumed_block_cluster_starts'] = starts
out['resumed_block_split'] = len({sid for ids in starts.values() for sid in ids}) > 1

# A killed driver is absent for 1,000 seconds while its server stays billable.
clk = Clock()
lp = base / 'gap-ledger.json'
l1 = DR.Ledger(lp, {'s': 1000}, 3.6, clk)
l1.begin('s')
clk.t = 10
l1.charge()
clk.t = 1010
l2 = DR.Ledger(lp, {'s': 1000}, 3.6, clk)
l2.begin('s')
l2.charge()
out['gap_actual_billable_usd'] = 1.01
out['gap_metered_usd'] = l2.d['spent_usd']['s']
out['unmetered_billable_gap'] = out['gap_metered_usd'] < 1.01 - 1e-9

result = base / 'results.json'
result.write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
