"""Pod side of the confirmatory driver (review #4): the real vLLM server control, the HTTP kernel and the pipeline-pin
check, plugged into driver.Driver. Mirrors the S8 pod code (gates/S8/gpu/s8_driver.sh), which ran on all five models.
NOT YET RUN ON A GPU: the first paid use needs the owner's explicit OK and starts with a smoke block.

  python gates/S10/run/pod.py --model M --caps caps.json --out /root/out/RUN [--stages core secondary] [--blocks 1 2]
                              [--ack M:core ...]
Env (as S8): PIPE_COMMIT (must equal pins.yaml's pipeline commit), STPT_COMMIT, STPT_PAYLOAD_SHA256, MODEL_PROFILE_FILE,
LINEUP_VLLM_PYTHON, CACHES, RUNPOD_POD_ID, USD_PER_GPU_HOUR.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(ROOT))
import driver as DR  # noqa: E402
import s10_core as C  # noqa: E402


def pins():
    import yaml
    return yaml.safe_load((ROOT / "pins.yaml").read_text())


def _alive(pid):
    try:
        os.kill(pid, 0); return True
    except (OSError, TypeError):
        return False


def _healthy():
    try:
        urllib.request.urlopen("http://localhost:8000/v1/models", timeout=5).read(); return True
    except Exception:  # noqa: BLE001
        return False


class VLLMServer:
    """One cold vLLM start per call to start(), unless a server this driver started is still up (re-attach after a
    killed driver). State in <out>/server_state.json."""

    def __init__(self, model, out):
        self.model, self.state = model, Path(out) / "server_state.json"
        self.pod = os.environ.get("RUNPOD_POD_ID", "pod")

    def _st(self):
        return json.loads(self.state.read_text()) if self.state.exists() else {"index": 0, "pid": None, "started_at": None, "model": None}

    def start(self, check=lambda: None):
        """check() is the driver's cap check; it runs every 5 s while the server comes up (round 3) and may raise
        Stop, after which the driver's finally stops this server."""
        st = self._st()
        if st["pid"] and st["model"] == self.model and _alive(st["pid"]) and _healthy():
            return {"id": f"{self.pod}/start{st['index']}/{st['started_at']}", "pod": self.pod, "index": st["index"],
                    "started_at": st["started_at"], "cold": True, "attached": True}
        self.stop()
        subprocess.run(["rm", "-rf", *os.environ.get("CACHES", "").split()], check=False)
        cmd = subprocess.run(["/root/venv/bin/lineup-serve-cmd", self.model], capture_output=True, text=True, check=True,
                             env={**os.environ}).stdout.strip()
        idx = st["index"] + 1
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log = open(self.state.parent / f"vllm_{self.model}_start{idx}.log", "w")
        p = subprocess.Popen(["bash", "-c", cmd], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.state.write_text(json.dumps({"index": idx, "pid": p.pid, "started_at": started, "model": self.model}))
        with open(self.state.parent / "paid.pids", "a") as f:          # the watchdog may terminate it (round 3)
            f.write(f"{p.pid}\n")
        for _ in range(360):
            check()
            if _healthy():
                break
            if p.poll() is not None:
                raise RuntimeError(f"vLLM exited during start {idx} (see {log.name})")
            time.sleep(5)
        else:
            raise RuntimeError(f"vLLM did not come up in 30 min (start {idx})")
        return {"id": f"{self.pod}/start{idx}/{started}", "pod": self.pod, "index": idx, "started_at": started, "cold": True,
                "caches_cleared": os.environ.get("CACHES", "").split(), "attached": False}

    def stop(self):
        st = self._st()
        if st.get("pid") and _alive(st["pid"]):
            try:
                os.killpg(st["pid"], signal.SIGTERM)
            except OSError:
                pass
            time.sleep(5)
        subprocess.run(["pkill", "-9", "-f", "[v]llm.entrypoints"], check=False)
        q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True)
        for pid in q.stdout.split():
            subprocess.run(["kill", "-9", pid], check=False)
        time.sleep(5)
        st["pid"] = None
        self.state.write_text(json.dumps(st))


class HTTPKernel:
    """As S8: exact A/B readout through the pinned pipeline's lineup.readout."""

    def __init__(self):
        import sae_ethos_pipeline  # noqa: F401
        import modelcfg
        from lineup import readout
        from transformers import AutoTokenizer
        tm = modelcfg.target()
        self.tok = AutoTokenizer.from_pretrained(tm["hf_id"], revision=tm["revision"]); self.ser = modelcfg.serializer()
        self.opt = readout.option_token_ids(self.tok); self.tr = readout.HTTPTransport()
        self.served = modelcfg.models()["endpoint"]["served_model_name"]; self.readout = readout.readout
        self.calls, self.mass_max = 0, 0.0

    def __call__(self, msgs):
        self.calls += 1
        r = self.readout(self.tr, self.served, self.ser.apply_to_tokenizer(self.tok, msgs), self.opt)
        self.mass_max = max(self.mass_max, r["non_option_mass"])
        return {"logp_A": r["logp"]["A"], "logp_B": r["logp"]["B"], "non_option_mass": r["non_option_mass"]}


def env_check_factory():
    p = pins()["pipeline"]
    if os.environ.get("PIPE_COMMIT") != p["commit"]:
        raise SystemExit(f"REFUSED: PIPE_COMMIT {os.environ.get('PIPE_COMMIT')} != pinned {p['commit']}")

    def env_check(model):
        import sae_ethos_pipeline  # noqa: F401
        from lineup import manifest
        block = manifest.identity_block(model)
        manifest.check_pin(block, p["tag"], p["commit"])           # refuses any other pipeline commit
        return block
    return env_check


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--caps", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--stages", nargs="+", default=["core"]); ap.add_argument("--blocks", nargs="*", type=int)
    ap.add_argument("--ack", nargs="*", default=[])
    a = ap.parse_args(argv)
    caps = json.loads(Path(a.caps).read_text())
    if caps.get("status", "").startswith("PROPOSED"):
        raise SystemExit("REFUSED: the caps file is still a proposal; the owner must approve it (status APPROVED)")
    env_check = env_check_factory()
    base = {"gate": "S10", "confirmatory": True, "stpt_commit": os.environ.get("STPT_COMMIT"), "pins": pins(),
            "payload_sha256": os.environ.get("STPT_PAYLOAD_SHA256"), "T_primary": C.primary_T(a.model), "prm": C.PRM,
            "cluster_manifest_sha256": C.MANIFEST_SHA256}
    d = DR.Driver(a.model, HTTPKernel(), VLLMServer(a.model, a.out), env_check, caps["caps_usd"], a.out,
                  float(os.environ.get("USD_PER_GPU_HOUR", caps["usd_per_gpu_hour"])), base, mock=False, ack_flags=a.ack)
    status = d.run(stages=tuple(a.stages), blocks=a.blocks or None)
    print(a.model, status, flush=True)
    return 0 if status == "complete" else 4


if __name__ == "__main__":
    sys.exit(main())
