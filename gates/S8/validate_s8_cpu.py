"""Gate S8, CPU validation before any S8 model call (gates/S8/S8_PLAN.md, D27): the runner, the analysis and the sealed-
file path, with the deterministic mock model.  python gates/S8/validate_s8_cpu.py WORKDIR -> gates/S8/results/s8_cpu_validation.json
"""
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S7")); sys.path.insert(0, str(ROOT / "gates/S8"))
from stpt import board as B  # noqa: E402
import s7_core  # noqa: E402
import s8_core  # noqa: E402

work = Path(sys.argv[1]); runs = work / "runs"; runs.mkdir(parents=True, exist_ok=True)
clusters = json.load(open(ROOT / "gates/S8/inputs/clusters.json")); prm = json.load(open(ROOT / "gates/S8/s8_params.json"))
out = {"checks": {}}


class Mock(s7_core.MockKernel):
    def __init__(self, tag):
        super().__init__(); self.tag = tag

    def __call__(self, msgs):
        r = super().__call__(msgs)
        b = 0.3 * (2 * B.unif(self.tag, msgs[0]["content"]) - 1)        # model-specific offset
        return {**r, "logp_A": r["logp_A"] + b}


t = time.time()
for m in ("gemma-2-9b-it", "qwen3.5-9b"):
    for k in (1, 2):
        K = Mock(m)
        for c in [c for c in clusters if c["start"] == k]:
            res = s8_core.run_cluster(c, 1.0, K, prm)
            (runs / f"s8_{m}_c{c['cluster']}.json.gz").write_bytes(gzip.compress(json.dumps({"model": m, "result": res, "model_calls": K.calls}).encode()))
        probes = [K([{"role": "user", "content": f"probe {i}"}])["logp_A"] for i in range(20)]
        (runs / f"s8_{m}_probes_start{k}.json").write_text(json.dumps({"start": k, "begin": probes, "end": probes}))
out["mock_run_seconds"] = round(time.time() - t, 1)

# replay: an unpulsed branch rebuilt from the saved state equals the live continuation (cluster 1, first model)
c = clusters[0]; K = Mock("gemma-2-9b-it")
live = s8_core.make_board(c["spec"], c["alloc"], c["adj"], c["run_key"], True, 1.0)
st0, _ = B.initial_state(live, K, "i")
N = 100; t0, D, W = prm["t0"] * N, prm["D"] * N, prm["W"] * N
s = B.branch(st0)
for _ in range(t0):
    B.update(live, s, K)
cont = [s8_core.compact(B.update(live, B.branch(s) if False else s, K)) for _ in range(D + W)]
r1 = json.loads(gzip.decompress((runs / "s8_gemma-2-9b-it_c1.json.gz").read_bytes()))["result"]
out["checks"]["unpulsed_equals_live_continuation"] = cont == r1["live"][t0:t0 + D + W]
out["checks"]["two_pulses_one_A_one_B"] = sorted(p["direction"] for p in r1["pulses"]) == ["A", "B"]
out["checks"]["self_reset_present"] = r1["self_reset"] is not None and len(r1["self_reset"]["rows"]) == W

summ, seal = work / "summary.json", work / "sealed" / "s8_sealed.json.gz.b64"
cmd = [sys.executable, str(ROOT / "gates/S8/analyse_s8.py"), "--runs", str(runs), "--sealed", str(seal), "--out", str(summ)]
p1 = subprocess.run(cmd, capture_output=True, text=True)
out["checks"]["analysis_ran"] = p1.returncode == 0
p2 = subprocess.run(cmd, capture_output=True, text=True)
out["checks"]["sealed_refuses_overwrite"] = p2.returncode != 0 and "REFUSED" in (p2.stdout + p2.stderr)
S = json.load(open(summ)); text = json.dumps(S)
out["checks"]["summary_has_variance_components"] = S["models"]["gemma-2-9b-it"]["variance_components"]["board_effect_between_cluster"]["s2_q80"] is not None
out["checks"]["summary_has_no_sealed_keys"] = not any(k in text for k in ("persistence_social", "persistence_self", "persistence_exposed", "board_effect_rule_ii"))
sealed_text = seal.read_text()
out["checks"]["sealed_not_plain_json"] = not sealed_text.lstrip().startswith("{")
coord = work / "SEALED.md"; coord.write_text("| file | written | sha256 |\n")
po = subprocess.run([sys.executable, str(ROOT / "gates/S8/open_sealed.py"), "--file", str(seal), "--reason", "validation",
                     "--requested-by", "test", "--coord", str(coord)], capture_output=True, text=True)
out["checks"]["open_refuses_unrecorded_hash"] = po.returncode != 0 and "REFUSED" in (po.stdout + po.stderr)
coord.write_text(f"| file | written | sha256 |\n| x | now | {S['sealed_file']['sha256']} |\n")
po = subprocess.run([sys.executable, str(ROOT / "gates/S8/open_sealed.py"), "--file", str(seal), "--reason", "validation",
                     "--requested-by", "test", "--coord", str(coord)], capture_output=True, text=True)
out["checks"]["open_logs_then_decodes"] = po.returncode == 0 and "validation" in coord.read_text() and "persistence_itt" in po.stdout
out["pass"] = all(out["checks"].values())
out["summary_open_fields_seen"] = sorted(S["models"]["gemma-2-9b-it"].keys())
out["pooled_open"] = {k: v for k, v in S["pooled_confirmatory"].items() if k != "variance_components"}
(ROOT / "gates/S8/results").mkdir(parents=True, exist_ok=True)
(ROOT / "gates/S8/results/s8_cpu_validation.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out["checks"], indent=1)); print("pass", out["pass"], "| mock seconds", out["mock_run_seconds"])
if p1.returncode:
    print(p1.stdout[-2000:], p1.stderr[-3000:])
