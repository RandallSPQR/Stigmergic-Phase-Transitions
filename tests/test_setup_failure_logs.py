"""Operational change after A52: a setup failure (before UPLOAD_PENDING exists, after which the pod deletes itself)
uploads the run folder's small files with a stdlib uploader before the script exits, so the failing step is visible.

A local stand-in for the dataset's HTTP API (commit, tree, resolve) receives the uploads; the real pod script runs."""
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "gates/S10/gpu/s10_driver.sh"
REPO = "owner/data"


class FakeHub:
    """Commit API (application/x-ndjson, base64 files), recursive tree listing, and resolve downloads."""

    def __init__(self, fail_commits=0):
        self.files, self.commits, self.fail_commits = {}, [], fail_commits
        hub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", ctype="application/json"):
                self.send_response(code); self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(n)
                if self.path != f"/api/datasets/{REPO}/commit/main":
                    return self._send(404)
                if hub.fail_commits:
                    hub.fail_commits -= 1
                    return self._send(500, b'{"error":"busy"}')
                lines = [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
                assert lines[0]["key"] == "header"
                hub.commits.append(self.headers.get("Authorization"))
                for x in lines[1:]:
                    assert x["key"] == "file" and x["value"]["encoding"] == "base64"
                    hub.files[x["value"]["path"]] = base64.b64decode(x["value"]["content"])
                self._send(200, b'{"commitOid":"abc"}')

            def do_GET(self):
                m = re.match(rf"^/api/datasets/{REPO}/tree/main/(.+)\?recursive=true$", self.path)
                if m:
                    pre = m.group(1) + "/"
                    out = [{"type": "file", "path": p, "size": len(b)} for p, b in hub.files.items() if p.startswith(pre)]
                    return self._send(200, json.dumps(out).encode())
                m = re.match(rf"^/datasets/{REPO}/resolve/main/(.+)$", self.path)
                if m and m.group(1) in hub.files:
                    return self._send(200, hub.files[m.group(1)], "application/octet-stream")
                self._send(404)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def close(self):
        self.srv.shutdown()


def env_for(tmp, hub, **extra):
    return {**os.environ, "HF_ENDPOINT": hub.url, "HF_TOKEN": "hf_test", "STPT_RESULTS_REPO": REPO, "STPT_RUN_ID": "r1",
            "STPT_WORKSPACE": str(tmp / "ws"), "STPT_SRC": str(tmp / "src"), "STPT_PAYLOAD_FILE": str(tmp / "payload.tar.gz"),
            "STPT_PAYLOAD_HF_PATH": "stpt/S10/payload/p.tar.gz", "STPT_PAYLOAD_SHA256": "0" * 64,
            "STPT_MODELS": "gemma-2-9b-it", "STPT_SETUP_UPLOAD_BACKOFF": "0 0", "PIPE_COMMIT": "x", **extra}


def run_driver(env):
    # sleep is stubbed (the payload step's retry back-off); the real script runs end to end in a subprocess
    return subprocess.run(["bash", "-c", f'sleep() {{ :; }}; export -f sleep; bash "{SH}"'], env=env,
                          capture_output=True, text=True, timeout=120)


def test_payload_failure_uploads_logs(tmp_path):
    hub = FakeHub()
    try:
        p = run_driver(env_for(tmp_path, hub))
        assert p.returncode == 3, p.stdout + p.stderr
        log = hub.files["stpt/S10/r1/logs/driver.log"].decode()
        assert "STOP: payload not available or not verified" in log
        assert hub.files["stpt/S10/r1/SETUP_FAILED"].decode().strip() == "payload not available or not verified"
        assert hub.commits == ["Bearer hf_test"]
        assert not (tmp_path / "ws/UPLOAD_PENDING").exists()          # so the pod deletes itself, as before
        assert "setup logs uploaded and verified" in p.stdout
    finally:
        hub.close()


def test_missing_prior_ledger_after_payload_uploads_logs(tmp_path):
    hub = FakeHub()
    try:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            data = b"print('x')\n"; ti = tarfile.TarInfo("README"); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        tarball = buf.getvalue()
        hub.files["stpt/S10/payload/p.tar.gz"] = tarball
        env = env_for(tmp_path, hub, STPT_PAYLOAD_SHA256=hashlib.sha256(tarball).hexdigest(), STPT_PRIOR_RUNS="gone")
        p = run_driver(env)
        assert p.returncode == 3, p.stdout + p.stderr
        log = hub.files["stpt/S10/r1/logs/driver.log"].decode()
        assert "payload verified" in log and "STOP: ledger of earlier run gone not available" in log
        assert "ledger.json" not in {k.split("stpt/S10/r1/")[-1] for k in hub.files}   # no ledger was opened
    finally:
        hub.close()


def test_open_ledger_is_closed_final_and_uploaded(tmp_path):
    hub = FakeHub()
    try:
        env = env_for(tmp_path, hub, S10_SOURCE_ONLY="1", STPT_SRC=str(ROOT), USD_PER_GPU_HOUR="2.49",
                      STPT_SETUP_UPLOAD_TIMEOUT="60")
        out = tmp_path / "ws/out/r1"
        script = (f'source "{SH}"; mkdir -p "{out}/logs"; echo setup > "{out}/logs/driver.log"; '
                  f'python3 "$SRC/gates/S10/run/ledger.py" open --out "$OUT" --caps "$SRC/gates/S10/run/caps_approved.json" '
                  f'--stage gemma-2-9b-it:core --since "$POD_T0" || exit 9; '
                  f'( setup_stop 3 "install failed (no records yet)" ); echo "rc=$?"')
        p = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=120)
        assert "rc=3" in p.stdout, p.stdout + p.stderr
        led = json.loads(hub.files["stpt/S10/r1/ledger.json"])
        assert led["closed"]["final"] is True and led["open"] is None
        assert led["final_upload_allowance_s"] == 60.0 and led["charged_through"] > 0
        assert led["spent_usd"]["gemma-2-9b-it:core"] >= 60 * 2.49 / 3600 - 1e-9     # the upload's hard limit is charged
    finally:
        hub.close()


def test_failed_upload_still_exits_with_setup_status(tmp_path):
    hub = FakeHub(fail_commits=10)
    try:
        p = run_driver(env_for(tmp_path, hub))
        assert p.returncode == 3, p.stdout + p.stderr
        assert "setup logs NOT uploaded" in p.stdout and "setup log upload attempt failed" in p.stdout
        assert hub.files == {}
    finally:
        hub.close()


def test_retry_after_a_failed_commit(tmp_path):
    hub = FakeHub(fail_commits=1)
    try:
        p = run_driver(env_for(tmp_path, hub))
        assert p.returncode == 3 and "stpt/S10/r1/logs/driver.log" in hub.files, p.stdout + p.stderr
    finally:
        hub.close()


def test_no_bare_setup_exit_before_marker():
    """Lint: in the main flow, every stop before UPLOAD_PENDING is created goes through setup_stop (recovery-mode exits
    keep their status 5: the marker exists there, so the pod is stopped, not deleted)."""
    s = SH.read_text()
    main = s[s.index('[ "${S10_SOURCE_ONLY:-0}" = 1 ] && return 0'):s.index('touch "$MARKER"')]
    rec = main[main.index("if [ $RECOVERY = 1 ]; then"):main.index("CAPS=$SRC")]
    rest = main.replace(rec, "")
    assert not re.search(r"\bexit [0-9]", rest.replace("[ $RECOVERY = 1 ] && exit 5", "")), \
        [l for l in rest.splitlines() if re.search(r"\bexit [0-9]", l)]
    assert rest.count("setup_stop 3") == 6
