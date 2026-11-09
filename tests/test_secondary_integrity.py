"""Operational change before the secondary stage: the collection integrity check (gates/S10/run/collection_integrity.py)
covers the secondary stage. CPU only, mock model: one conforming record per secondary arm type passes verify_record, and
the check reports the rest of the stage's schedule as missing without refusing the records it has."""
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S10/run", "gates/S7"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as CA  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402
from driver import stage_of  # noqa: E402

F = C.load_clusters()
M = "gemma-2-9b-it"
PICK = {"T1": (5, "T1"), "rule_ii": (12, "rule_ii"), "wording": (3, "wording:w5")}


def make(j, arm):
    r = C.run_cluster(F[j], M, s7_core.MockKernel(), arm=arm)
    r["server_start_ids"] = {n: f"pod/start{F[j]['start_block']}/t" for n in C.branch_names(F[j], M, arm)}
    r["mock"] = False
    return r


@pytest.fixture(scope="module")
def recs():
    return {k: make(*v) for k, v in PICK.items()}


def test_picked_arms_are_secondary():
    for j, arm in PICK.values():
        assert arm in C.arms_for(F[j], M) and stage_of(M, arm) == f"{M}:secondary"


@pytest.mark.parametrize("kind", sorted(PICK))
def test_secondary_record_verifies(recs, kind):
    CA.verify_record(recs[kind])                   # full recomputation; no outcome is computed here


def test_integrity_check_secondary_stage(recs, tmp_path):
    run = tmp_path / "run"; (run / M).mkdir(parents=True)
    for (j, arm), r in zip(PICK.values(), [recs[k] for k in PICK]):
        rec = {"model": M, "result": r, "model_calls": 1,
               "manifest": {"stpt_commit": "abcdef0", "payload_sha256": "12345678", "cluster_manifest_sha256": "c", "pins": {}}}
        (run / M / f"rec_c{j}__{arm.replace(':', '-')}.json.gz").write_bytes(gzip.compress(json.dumps(rec).encode()))
    (run / "ledger.json").write_text(json.dumps({"spent_usd": {f"{M}:secondary": 1.0}, "closed": {"final": True}}))
    (run / "DONE").write_text("")
    p = subprocess.run([sys.executable, "-I", str(ROOT / "gates/S10/run/collection_integrity.py"), "--stage", "secondary",
                        M, str(run)], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout)
    want = sum(1 for j in F for a in C.arms_for(F[j], M) if stage_of(M, a) == f"{M}:secondary")
    assert out["stage"] == "secondary" and out["scheduled"] == want and out["records"] == 3 and out["verified"] == 3
    assert out["arms"] == {"T1": 1, "rule_ii": 1, "wording": 1}
    assert out["code_versions"] == {"abcdef0 / payload 12345678": 3} and out["pin_sets"] == 1
    assert len(out["problems"]) == 1 and out["problems"][0].startswith(f"missing {want - 3} of {want}")
    assert not out["passed"]


def test_core_check_refuses_secondary_records(recs, tmp_path):
    run = tmp_path / "run"; (run / M).mkdir(parents=True)
    j, arm = PICK["T1"]
    rec = {"model": M, "result": recs["T1"], "model_calls": 1, "manifest": {}}
    (run / M / f"rec_c{j}__{arm}.json.gz").write_bytes(gzip.compress(json.dumps(rec).encode()))
    (run / "ledger.json").write_text(json.dumps({"spent_usd": {}, "closed": {"final": True}}))
    p = subprocess.run([sys.executable, "-I", str(ROOT / "gates/S10/run/collection_integrity.py"), M, str(run)],
                       capture_output=True, text=True, timeout=600)
    out = json.loads(p.stdout)
    assert any("not scheduled in the core stage" in x for x in out["problems"])
