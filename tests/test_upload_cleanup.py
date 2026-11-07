"""A43: the pod script's upload removes stale intermediate block copies from the dataset and verifies they are gone.
The real upload() runs with a stand-in huggingface_hub (tests/fakes) backed by a local folder."""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "gates/S10/gpu/s10_driver.sh"


def _upload(tmp, out):
    env = {**os.environ, "S10_SOURCE_ONLY": "1", "STPT_WORKSPACE": str(tmp / "ws"), "STPT_RUN_ID": "run1", "STPT_MODELS": "gemma-2-9b-it",
           "STPT_PY": sys.executable, "PYTHONPATH": str(ROOT / "tests/fakes"), "FAKE_HF_REMOTE": str(tmp / "remote"),
           "STPT_RESULTS_REPO": "o/d"}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; OUT={out}; upload; echo "rc=$?"'], env=env, capture_output=True, text=True, timeout=60)
    return p.stdout + p.stderr


def _files(d):
    return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())


def test_finalized_block_leaves_only_final_records(tmp_path):
    out = tmp_path / "ws/out/run1"; blk = out / "gemma-2-9b-it/blocks/b1"
    (blk / "partial/c1__primary").mkdir(parents=True)
    (blk / "partial/c1__primary/live.json.gz").write_text("x"); (blk / "rec_c2__primary.json.gz").write_text("y")
    (out / "ledger.json").write_text("{}")
    assert "rc=0" in _upload(tmp_path, out)                                       # mid-block: intermediates mirrored
    remote = tmp_path / "remote/stpt/S10/run1"
    assert "gemma-2-9b-it/blocks/b1/partial/c1__primary/live.json.gz" in _files(remote)
    import shutil                                                                 # the block is finalized locally
    (out / "gemma-2-9b-it/rec_c1__primary.json.gz").write_text("y1"); (out / "gemma-2-9b-it/rec_c2__primary.json.gz").write_text("y")
    shutil.rmtree(out / "gemma-2-9b-it/blocks")
    assert "rc=0" in _upload(tmp_path, out)
    assert _files(remote) == ["gemma-2-9b-it/rec_c1__primary.json.gz", "gemma-2-9b-it/rec_c2__primary.json.gz", "ledger.json"]


def test_abandoned_output_is_kept(tmp_path):
    out = tmp_path / "ws/out/run1"; (out / "gemma-2-9b-it/abandoned/b1__1").mkdir(parents=True)
    (out / "gemma-2-9b-it/abandoned/b1__1/rec_c1__primary.json.gz").write_text("a")
    assert "rc=0" in _upload(tmp_path, out)
    out_files = _files(tmp_path / "remote/stpt/S10/run1")
    assert out_files == ["gemma-2-9b-it/abandoned/b1__1/rec_c1__primary.json.gz"]


def test_stale_intermediate_left_remotely_fails_verification(tmp_path):
    """If the dataset still held a stale block copy after the upload (e.g. a delete that did not apply), upload fails."""
    out = tmp_path / "ws/out/run1"; out.mkdir(parents=True); (out / "ledger.json").write_text("{}")
    stale = tmp_path / "remote/stpt/S10/run1/gemma-2-9b-it/blocks/b1/rec_c1__primary.json.gz"
    stale.parent.mkdir(parents=True); stale.write_text("old")
    env_fake = tmp_path / "fakes2/huggingface_hub"; env_fake.mkdir(parents=True)          # a client that ignores deletes
    src = (ROOT / "tests/fakes/huggingface_hub/__init__.py").read_text().replace("if delete_patterns and root.exists():", "if False:")
    (env_fake / "__init__.py").write_text(src)
    env = {**os.environ, "S10_SOURCE_ONLY": "1", "STPT_WORKSPACE": str(tmp_path / "ws"), "STPT_RUN_ID": "run1", "STPT_MODELS": "gemma-2-9b-it",
           "STPT_PY": sys.executable, "PYTHONPATH": str(tmp_path / "fakes2"), "FAKE_HF_REMOTE": str(tmp_path / "remote"), "STPT_RESULTS_REPO": "o/d"}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; OUT={out}; upload; echo "rc=$?"'], env=env, capture_output=True, text=True, timeout=60)
    assert "rc=1" in p.stdout and "NOT VERIFIED" in p.stdout
