"""A44: restoring earlier runs' records (through a background paid phase, no stdin) and seeding the ledger from a
chain of earlier runs. CPU only; a stand-in Hugging Face client (tests/fakes)."""
import json, os, re, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "gates/S10/gpu/s10_driver.sh"
sys.path.insert(0, str(ROOT / "gates/S10/run"))
import ledger as LG  # noqa: E402


def _restore(tmp, make_unwritable=False):
    rem = tmp / "remote/stpt/S10/R1/gemma-2-9b-it"; rem.mkdir(parents=True)
    for j in (1, 2, 3, 4):
        (rem / f"rec_c{j}__primary.json.gz").write_bytes(b"rec%d" % j)
    (tmp / "remote/stpt/S10/R1/gemma-2-9b-it/blocks/b2").mkdir(parents=True)       # intermediates are never restored
    (tmp / "remote/stpt/S10/R1/gemma-2-9b-it/blocks/b2/rec_c5__primary.json.gz").write_bytes(b"x")
    out = tmp / "ws/out/R2"; out.mkdir(parents=True)
    if make_unwritable:
        (out / "gemma-2-9b-it").write_text("not a directory")                       # copying must fail
    env = {**os.environ, "S10_SOURCE_ONLY": "1", "STPT_WORKSPACE": str(tmp / "ws"), "STPT_RUN_ID": "R2", "STPT_MODELS": "gemma-2-9b-it",
           "STPT_PY": sys.executable, "PYTHONPATH": str(ROOT / "tests/fakes"), "FAKE_HF_REMOTE": str(tmp / "remote"),
           "STPT_RESULTS_REPO": "o/d", "STPT_PRIOR_RUNS": "R1"}
    p = subprocess.run(["bash", "-c", f'source "{SH}"; CUR_STAGE=gemma-2-9b-it:core; restore_prior_records; echo "rc=$?"'],
                       env=env, capture_output=True, text=True, timeout=60)
    return p.stdout + p.stderr, out


def test_restore_runs_in_a_background_paid_phase_and_places_every_record(tmp_path):
    log, out = _restore(tmp_path)
    assert "rc=0" in log and "4 records found" in log and "4 in place" in log, log
    assert sorted(p.name for p in (out / "gemma-2-9b-it").iterdir()) == [f"rec_c{j}__primary.json.gz" for j in (1, 2, 3, 4)]


def test_restore_fails_when_a_record_cannot_be_placed(tmp_path):
    log, _ = _restore(tmp_path, make_unwritable=True)
    assert "rc=0" not in log


def test_no_heredoc_is_fed_to_a_paid_phase():
    """A background paid phase gets an empty stdin; a heredoc fed to it is silently lost (the A44 bug)."""
    src = SH.read_text()
    assert not re.search(r"^\s*paid\b[^\n]*<<", src, re.M)


A = {"spent_usd": {"g:core": 0.8128}, "flagged": {}, "acked": {}}
B = {"spent_usd": {"g:core": 1.0838}, "flagged": {}, "acked": {}, "prior_runs": [{"ledger": "/x/out/B/prior_ledger_A.json", "spent_usd": {"g:core": 0.8128}}]}
ADJ = {"spent_usd": {"g:core": 0.066}}


@pytest.mark.parametrize("listed", [[("prior_ledger_A.json", A), ("prior_ledger_B.json", B), ("prior_ledger_B-adj.json", ADJ)],
                                    [("prior_ledger_B.json", B), ("prior_ledger_B-adj.json", ADJ)],
                                    [("prior_ledger_B-adj.json", ADJ), ("prior_ledger_B.json", B), ("prior_ledger_A.json", A)]])
def test_chained_seed_counts_each_run_once(tmp_path, listed):
    L = LG.Ledger(tmp_path / "l.json", {"g:core": 12.18}, 2.49, lambda: 0.0, session="s")
    L.seed(listed)
    assert abs(L.spent("g:core") - (0.8128 + (1.0838 - 0.8128) + 0.066)) < 1e-9
    assert sorted(p["ledger"] for p in L.d["prior_runs"]) == ["prior_ledger_A.json", "prior_ledger_B-adj.json", "prior_ledger_B.json"]


def test_seed_refuses_a_prior_with_less_than_its_own_priors(tmp_path):
    bad = {"spent_usd": {"g:core": 0.5}, "prior_runs": [{"ledger": "prior_ledger_A.json", "spent_usd": {"g:core": 0.8}}]}
    L = LG.Ledger(tmp_path / "l.json", {"g:core": 12.18}, 2.49, lambda: 0.0, session="s")
    with pytest.raises(LG.Stop):
        L.seed([("prior_ledger_X.json", bad)])
