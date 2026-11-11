"""S10 secondary analyses (gates/S10/analysis/secondary.py), written blind (D62, D63). Mock records and synthetic data
only: no S10 record is read. CPU only.

Three groups: (1) the loader refuses real records without the owner's unblinding decision; (2) record-level quantities
on mock records satisfy identities against confirmatory.outcomes and the frozen layout; (3) the estimators recover
planted values in synthetic tables."""
import copy
import gzip
import json
import math
import subprocess
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in ("", "gates/S10", "gates/S10/analysis", "gates/S10/run", "gates/S7"):
    sys.path.insert(0, str(ROOT / p))
import confirmatory as CA  # noqa: E402
import s10_core as C  # noqa: E402
import s7_core  # noqa: E402
import secondary as S  # noqa: E402

F = C.load_clusters()
J = [1, 2, 3, 4, 5, 6, 12, 14, 20, 24]          # T1 on 5, 12, 14; rule (ii) on 12, 20, 24; self-reset on 2, 3, 20, 24
N = CA.N


def make(model, j, arm):
    r = C.run_cluster(F[j], model, s7_core.MockKernel(), arm=arm)
    r["server_start_ids"] = {n: f"{model}-pod/start{F[j]['start_block']}/t" for n in C.branch_names(F[j], model, arm)}
    r["mock"] = False
    return r


@pytest.fixture(scope="module")
def recs():
    return {(m, j, a): make(m, j, a) for m in CA.ALL_MODELS for j in J for a in C.arms_for(F[j], m)}


@pytest.fixture(scope="module")
def table(recs):
    return S.outcome_table(recs, F)


# ---------------------------------------------------------------- (1) blinding
TAG = "stpt-secondary-v1"
OWNER_ROW = f"| D99 | 2026-11-12 | StPT | **S10 unblinding authorised** (owner). Code at tag `{TAG}`. | owner |"
HEAD = "| # | date | scope | decision | by |\n|---|---|---|---|---|\n"


def _coord(tmp_path, rows, proposed=(), commit=True, name="coord"):
    d = tmp_path / name
    d.mkdir()
    (d / "DECISIONS.md").write_text("# Decisions\n\n## Accepted\n" + HEAD + "\n".join(rows) + "\n\n## Proposed\n" + HEAD
                                    + "\n".join(proposed) + "\n")
    if commit:
        g = ["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        subprocess.run(g + ["add", "DECISIONS.md"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "t"], check=True)
    return d


def _git(d, *args):
    subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


def _code_repo(tmp_path, tag=TAG, push=True, name="code"):
    """A stand-in for the analysis repository: a clone of a local 'origin', one commit, an annotated tag."""
    origin, work = tmp_path / f"{name}-origin.git", tmp_path / name
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / "analysis.py").write_text("x = 1\n")
    _git(work, "add", "analysis.py")
    _git(work, "commit", "-q", "-m", "code")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(work, "tag", "-a", tag, "-m", "reviewed")
    if push:
        _git(work, "push", "-q", "origin", f"refs/tags/{tag}")
    return work


@pytest.fixture
def code_repo(tmp_path, monkeypatch):
    w = _code_repo(tmp_path)
    monkeypatch.setattr(S, "CODE_REPO", w)
    return w


def _run_dir(tmp_path, rec, name):
    run = tmp_path / "run"
    (run / rec["model"]).mkdir(parents=True)
    (run / rec["model"] / name).write_bytes(gzip.compress(json.dumps({"model": rec["model"], "result": rec}).encode()))
    return run


@pytest.mark.parametrize("rows,decision", [
    ([], "D99"),
    (["| D62 | 2026-11-11 | StPT | **Secondary analysis code to be written now, blind** (owner). The loader refuses "
      "real records until the owner records an unblinding decision. | owner |"], "D62"),
    (["| D63 | 2026-11-11 | StPT | **Secondary-analysis decisions, made blind before unblinding** (owner). | owner |"], "D63"),
    (["| D99 | 2026-11-12 | StPT | **S10 unblinding authorised** (owner). | Claude |"], "D99"),
    (["| D98 | 2026-11-12 | StPT | Text that says S10 unblinding authorised, not as the title. | owner |"], "D98"),
    (["| D99 | 2026-11-12 | StPT | **S10 unblinding authorised once the review is closed** (pending). | owner |"], "D99"),
    ([OWNER_ROW], "D98"),
])
def test_loader_refuses_without_the_owners_unblinding_decision(tmp_path, recs, code_repo, rows, decision):
    m, j, a = "gemma-2-9b-it", 1, "primary"
    run = _run_dir(tmp_path, recs[(m, j, a)], f"rec_c{j}__{a}.json.gz")
    with pytest.raises(S.Refused):
        S.load_records({m: [str(run)]}, _coord(tmp_path, rows), decision)


def test_guard_refuses_proposed_uncommitted_and_unversioned(tmp_path, recs, code_repo):
    with pytest.raises(S.Refused):                                         # in the Proposed table
        S.require_unblinding(_coord(tmp_path, [], proposed=[OWNER_ROW], name="c1"), "D99")
    with pytest.raises(S.Refused):                                         # not a git clone
        S.require_unblinding(_coord(tmp_path, [OWNER_ROW], commit=False, name="c2"), "D99")
    d = _coord(tmp_path, [], name="c3")                                    # committed without, edited locally to add it
    (d / "DECISIONS.md").write_text((d / "DECISIONS.md").read_text().replace("## Proposed", OWNER_ROW + "\n\n## Proposed"))
    with pytest.raises(S.Refused):
        S.require_unblinding(d, "D99")
    ok = S.require_unblinding(_coord(tmp_path, [OWNER_ROW.replace("| owner |", "| owner, StPT session |")], name="c4"), "D99")
    assert ok["row"].startswith("| D99 |") and len(ok["coordination_commit"]) == 40
    assert ok["tag"] == TAG and len(ok["code_commit"]) == 40


def test_guard_requires_the_code_at_the_pushed_tag(tmp_path, monkeypatch):
    """D64: no unblinding until the reviewer-finalized code is pushed under a tag, and the analysis runs from it."""
    coord = _coord(tmp_path, [OWNER_ROW])
    no_tag = _coord(tmp_path, [OWNER_ROW.replace(f"Code at tag `{TAG}`.", "Code reviewed.")], name="c-notag")
    two = _coord(tmp_path, [OWNER_ROW.replace(f"`{TAG}`.", f"`{TAG}` or tag `other`.")], name="c-two")

    def refused(repo, c=coord):
        monkeypatch.setattr(S, "CODE_REPO", repo)
        with pytest.raises(S.Refused):
            S.require_unblinding(c, "D99")
    good = _code_repo(tmp_path, name="good")
    refused(good, no_tag)                                                   # the row names no tag
    refused(good, two)                                                      # the row names two tags
    refused(_code_repo(tmp_path, tag="stpt-secondary-v0", name="other-tag"))   # the named tag does not exist
    refused(_code_repo(tmp_path, push=False, name="unpushed"))             # the tag exists only locally
    later = _code_repo(tmp_path, name="later")                              # a commit after the tag is checked out
    (later / "analysis.py").write_text("x = 2\n")
    _git(later, "commit", "-q", "-am", "after review")
    refused(later)
    dirty = _code_repo(tmp_path, name="dirty")                              # a tracked file modified
    (dirty / "analysis.py").write_text("x = 3\n")
    refused(dirty)
    extra = _code_repo(tmp_path, name="extra")                              # an untracked Python file (could shadow)
    (extra / "confirmatory.py").write_text("")
    refused(extra)
    moved = _code_repo(tmp_path, name="moved")                              # origin's tag is on another commit
    (moved / "analysis.py").write_text("x = 4\n")
    _git(moved, "commit", "-q", "-am", "x")
    _git(moved, "tag", "-f", "-a", TAG, "-m", "moved")
    _git(moved, "push", "-q", "-f", "origin", f"refs/tags/{TAG}")            # origin now has the tag on the new commit
    _git(moved, "reset", "-q", "--hard", "HEAD~1")
    _git(moved, "tag", "-f", "-a", TAG, "-m", "back")
    refused(moved)
    monkeypatch.setattr(S, "CODE_REPO", good)
    assert S.require_unblinding(coord, "D99")["tag"] == TAG


def test_the_real_coordination_record_does_not_unblind():
    coord = ROOT.parent / "stpt-mp-coordination"
    if not (coord / "DECISIONS.md").exists():
        pytest.skip("coordination record not cloned beside the repository")
    txt = (coord / "DECISIONS.md").read_text()
    for row in txt.splitlines():
        if row.startswith("| D"):
            with pytest.raises(S.Refused):
                S.require_unblinding(coord, row.split("|")[1].strip())


def test_loader_reads_with_the_decision_and_checks_names(tmp_path, recs, code_repo):
    m, j, a = "gemma-2-9b-it", 3, "wording:w5"
    coord = _coord(tmp_path, [OWNER_ROW])
    run = _run_dir(tmp_path, recs[(m, j, a)], f"rec_c{j}__wording-w5.json.gz")
    got = S.load_records({m: [str(run)]}, coord, "D99")
    assert list(got) == [(m, j, a)] and got[(m, j, a)]["live"] == recs[(m, j, a)]["live"]
    assert list(S.load_records({m: [str(run), str(run)]}, coord, "D99")) == [(m, j, a)]     # identical copy: accepted
    other = tmp_path / "other"
    (other / m).mkdir(parents=True)
    changed = dict(recs[(m, j, a)], seconds=-1.0)
    (other / m / f"rec_c{j}__wording-w5.json.gz").write_bytes(gzip.compress(json.dumps({"model": m, "result": changed}).encode()))
    with pytest.raises(S.Refused):                                                     # a different copy: refused
        S.load_records({m: [str(run), str(other)]}, coord, "D99")
    (run / m / f"rec_c{j}__wording-w5.json.gz").rename(run / m / f"rec_c{j + 1}__wording-w5.json.gz")
    with pytest.raises(S.Refused):                                                     # cluster in the name differs
        S.load_records({m: [str(run)]}, coord, "D99")
    (run / m / f"rec_c{j + 1}__wording-w5.json.gz").rename(run / m / f"rec_c{j}__T1.json.gz")
    with pytest.raises(S.Refused):                                                     # arm in the name differs
        S.load_records({m: [str(run)]}, coord, "D99")


def test_cli_refuses_without_decision(tmp_path):
    runs = tmp_path / "runs.json"
    runs.write_text(json.dumps({}))
    with pytest.raises(S.Refused):
        S.main(["--coord", str(_coord(tmp_path, [])), "--decision", "D99", "--runs", str(runs), "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()


# ---------------------------------------------------------------- (2) record-level identities on mock records
def test_board_and_finals_match_confirmatory(recs, table):
    for k, o in table.items():
        ref = CA.outcomes(recs[k])
        assert o["board"] == ref["board"] and o["board_final"] == ref["board_final"]
        assert abs((o["traj_live"][-1] - o["traj_blind"][-1]) - o["board_final"]) < 1e-12
        assert abs(np.mean(o["traj_live"][25:31]) - np.mean(o["traj_blind"][25:31]) - o["board"]) < 1e-12


def test_informed_split_recombines(table):
    for o in table.values():
        assert o["n_informed"] + o["n_uninformed"] == N
        whole = (o["n_informed"] * o["board_informed"] + o["n_uninformed"] * o["board_uninformed"]) / N
        assert abs(whole - o["board"]) < 1e-12


def _bfs(adj, src):
    dist = {s: 0 for s in src}
    q = deque(src)
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def test_propagation_pool_is_distance_two_or_more(recs, table):
    for k, r in recs.items():
        for p in r.get("pulses") or []:
            d = _bfs(F[k[1]]["adj"], p["recipients"])
            assert sorted(S._pool(F[k[1]]["adj"], p["recipients"])) == sorted(i for i in range(N) if d.get(i, 99) >= 2)


def test_branch_quantities(recs, table):
    n_sr = 0
    for k, o in table.items():
        r = recs[k]
        if not r.get("pulses"):
            assert "branches" not in o
            continue
        assert len(o["branches"]) == 2
        assert abs(np.mean([b["itt"] for b in o["branches"]]) - o["persistence"]) < 1e-12
        assert abs(np.mean([b["immediate"] for b in o["branches"]]) - o["immediate"]) < 1e-12
        for b, p in zip(o["branches"], r["pulses"]):
            assert b["pool"] == N - len(set(p["recipients"]) | {x for i in p["recipients"] for x in F[k[1]]["adj"][i]})
            assert 0 <= b["exposure"] <= 1 and len(b["traj_pulsed"]) == D_W() + 1
            assert b["traj_pulsed"][0] == b["traj_unpulsed"][0]                         # onset share, before the pulse
        if r.get("self_reset"):
            n_sr += 1
            b = o["branches"][r["self_reset"]["pulse_index"]]
            assert abs(o["social"] + o["self"] - b["itt"]) < 1e-12
            st = o["self_reset_state"]
            p = r["pulses"][r["self_reset"]["pulse_index"]]
            for i in st["recipients"]:                     # reset state: recipients back to their votes at pulse onset
                assert st["reset_votes"][i] == p["votes_at_pulse"][i]
            vt0 = CA.replay(r["initial_votes"], r["live"][:CA.PRM["t0"] * N])[0]
            assert st["pulsed_restoration_votes"] == CA.replay(vt0, p["rows"][:CA.PRM["D"] * N])[0]
            assert [st["reset_votes"][i] for i in range(N) if i not in st["recipients"]] == \
                [st["pulsed_restoration_votes"][i] for i in range(N) if i not in st["recipients"]]
        else:
            assert "social" not in o
    assert n_sr > 0


def D_W():
    return CA.PRM["D"] + CA.PRM["W"]


def test_social_matches_the_pilot_definition(recs, table):
    """Recomputed independently: replay of the self-reset rows from the restoration state, minus the unpulsed share."""
    for k, r in recs.items():
        sr = r.get("self_reset")
        if not sr:
            continue
        p = r["pulses"][sr["pulse_index"]]
        D, W, t0 = CA.PRM["D"], CA.PRM["W"], CA.PRM["t0"]
        vt0 = CA.replay(r["initial_votes"], r["live"][:t0 * N])[0]
        vr = CA.replay(vt0, p["rows"][:D * N])[0]
        for i in p["recipients"]:
            vr[i] = vt0[i]
        ss = CA.replay(vr, sr["rows"], watch=p["recipients"], direction=p["direction"])[2]
        su = CA.replay(vt0, r["live"][t0 * N:(t0 + D + W) * N], watch=p["recipients"], direction=p["direction"])[2]
        assert abs(table[k]["social"] - float(np.mean(np.array(ss) - np.array(su[D * N:])))) < 1e-12


def test_missing_and_call_counts(recs, table):
    for k, o in table.items():
        r = recs[k]
        assert o["calls"]["live"] == len(r["live"]) == o["calls"]["blind"] == 30 * N
        assert o["calls"]["init"] == sum(1 for x in r["init"] if x[3])
        assert all(v == 0 for v in o["missing"].values())     # the mock kernel never misses


def test_check_arm(table):
    for (m, a) in sorted({(m, a) for (m, _, a) in table}):
        S.check_arm(table, m, a, F, full=False)
    with pytest.raises(S.Refused):
        S.check_arm(table, "gemma-2-9b-it", "primary", F, full=True)        # 10 of 61 clusters
    bad = dict(table)
    k = ("qwen3.5-9b", 5, "T1")
    bad[k] = dict(bad[k], identity=dict(bad[k]["identity"], T=CA.primary_T("qwen3.5-9b")))
    with pytest.raises(S.Refused):
        S.check_arm(bad, "qwen3.5-9b", "T1", F, full=False)
    bad = dict(table)
    bad[("qwen3.5-9b", 5, "T1")] = dict(table[("qwen3.5-9b", 5, "T1")], identity=dict(table[("qwen3.5-9b", 5, "T1")]["identity"], mock=True))
    with pytest.raises(S.Refused):
        S.check_arm(bad, "qwen3.5-9b", "T1", F, full=False)
    bad = dict(table)
    k = ("gemma-2-9b-it", 2, "primary")                                     # cluster 1 and 2 share block 1
    bad[k] = dict(bad[k], server_start="another-pod/start1/t")
    with pytest.raises(S.Refused):
        S.check_arm(bad, "gemma-2-9b-it", "primary", F, full=False)


def test_scheduled_matches_frozen_flags():
    assert S.scheduled("gemma-2-9b-it", "T1", F) == sorted(j for j in F if F[j]["arms"]["T1"])
    assert S.scheduled("llama-3.1-8b-it", "rule_ii", F) == sorted(j for j in F if F[j]["arms"]["rule_ii"])
    assert len(S.scheduled("qwen3.5-27b", "primary", F)) == 61


def test_kernel_cells(recs):
    K = S.kernel_cells(recs, F, "gemma-2-9b-it")
    n_rows = {"live": 0, "blind": 0, "pulse_on": 0, "post_restoration": 0, "init": 0}
    for (m, j, a), r in recs.items():
        if m == "gemma-2-9b-it" and a == "primary":
            n_rows["live"] += len(r["live"]); n_rows["blind"] += len(r["blind"])
            n_rows["init"] += sum(1 for x in r["init"] if x[3])
            for p in r["pulses"]:
                n_rows["pulse_on"] += CA.PRM["D"] * N; n_rows["post_restoration"] += CA.PRM["W"] * N
    for c, n in n_rows.items():
        assert sum(len(x) for v in K[c].values() for x in v.values()) == n
        assert all(set(v) <= set(J) for v in K[c].values())                  # grouped by cluster
    assert all(cell[2] is None for c in ("blind", "init") for cell in K[c])
    assert all(cell[2] in range(5) for c in ("live", "pulse_on", "post_restoration") for cell in K[c])
    assert {cell[0] for cell in K["init"]} <= {"3/4", "9/10"}
    assert all(cell[1] == 1 for c in K for cell in K[c] if cell[0] == "none")
    # one call recomputed by hand
    r = recs[("gemma-2-9b-it", 1, "primary")]
    info = S.cluster_info(F[1])
    row = r["live"][0]
    cell, ref = S._cell(info, row[1], row[2], row[3], True)
    p = S._sig((row[5] if ref == "A" else -row[5]) / r["T"])
    assert ref == (info["fav"][row[1]] or row[2]) and cell[2] == row[3].count(ref) and p in K["live"][cell][1]


def test_kernel_check_detects_a_planted_harness_fault(recs):
    """Negative control. The mock kernel is one function of the prompt in every condition, so the within-study check
    should pass; shifting every call's logit 0.3 nats toward the cell's reference option while the pulse is on (a
    response fault confined to one condition) must be detected."""
    m = "gemma-2-9b-it"
    sub = {k: r for k, r in recs.items() if k[0] == m}
    opts = dict(S.OPTIONS, H_min_clusters=3)
    clean = S.kernel_consistency(sub, F, opts, battery=False)[m]["within_study"]
    assert sum(v["mismatches"] for v in clean.values()) == 0 and clean["live_vs_pulse_on"]["cells_checked"] > 10
    bad = copy.deepcopy(sub)
    for (_, j, _), r in bad.items():
        info = S.cluster_info(F[j])
        for p in r.get("pulses") or []:
            for row in p["rows"][:CA.PRM["D"] * N]:
                ref = info["fav"][row[1]] or row[2]
                row[5] += 0.3 * r["T"] * (1 if ref == "A" else -1)
    faulty = S.kernel_consistency(bad, F, opts, battery=False)[m]["within_study"]
    n = faulty["live_vs_pulse_on"]["cells_checked"]
    assert faulty["live_vs_pulse_on"]["mismatches"] == n and faulty["pulse_on_vs_post_restoration"]["mismatches"] == n
    assert faulty["live_vs_post_restoration"]["mismatches"] == 0 and faulty["blind_vs_init"]["mismatches"] == 0


def test_cross_check_is_zero_when_contacts_do_not_matter(recs, table, monkeypatch):
    """Choice E: if the live kernel ignores the contacts and equals the blind one, full and contacts-off runs coincide
    on the same random stream, so the simulated social part is exactly 0; the self-reset analogue need not be."""
    def flat(records, F_, model):
        return {"live": {(t, a, k): 0.3 + 0.4 * a for t in ("none", "3/4", "9/10") for a in (0, 1) for k in range(5)},
                "blind": {(t, a, None): 0.3 + 0.4 * a for t in ("none", "3/4", "9/10") for a in (0, 1)}}
    monkeypatch.setattr(S, "_kernel_tables", flat)
    sub = {k: v for k, v in table.items() if k[0] == "qwen3.5-9b"}
    out = S.self_social_crosscheck(sub, recs, F, dict(S.OPTIONS, E_sim_reps=3))["qwen3.5-9b"]
    assert out["n_clusters"] >= 3
    assert all(r["simulated_social"] == 0.0 for r in out["per_cluster"])
    assert any(r["simulated_self_reset_branch"] != 0.0 for r in out["per_cluster"])


def test_run_all_end_to_end(recs):
    opts = dict(S.OPTIONS, E_sim_reps=2)
    res = S.run_all(recs, F, full=False, opts=opts)
    for key in ("per_model", "wording", "sensitivity", "comprehension", "informed_split", "persistence", "t1",
                "calibration", "social_response", "rule_ii", "kernel_consistency", "board_final", "trajectories", "execution"):
        assert key in res
    for m in CA.ALL_MODELS:
        t1 = res["t1"][m]
        for k in S.CONTRASTS:
            e, pr = t1[k]["t1"], t1[k]["primary"]
            if e is not None:
                assert t1[k]["sign_matches_primary"] == (np.sign(e["theta"]) == np.sign(pr["theta"]))
        kc = res["kernel_consistency"][m]
        assert set(kc["within_study"]) == {"blind_vs_init", "live_vs_pulse_on", "live_vs_post_restoration",
                                          "pulse_on_vs_post_restoration"}
        for v in kc["within_study"].values():
            assert all(c["n_a"] >= 30 and c["n_b"] >= 30 for c in v["cells"])
        assert kc["battery_mismatch_reading"] == "harness or story dependence"
        assert set(res["rule_ii"][m]["early_sweeps"]) == {1, 5}
    assert res["wording"]["n_models_with_variants"] == 5
    assert res["persistence"]["propagation_primary_window"] == "propagation_onset"
    ex = res["execution"]["gemma-2-9b-it"]
    assert ex["mass"]["live"]["n"] == ex["calls"]["live"] and ex["missing"]["live"] == 0
    assert sum(v["calls"] for v in ex["letter_balance_by_start"].values()) == ex["calls"]["live"] + ex["calls"]["blind"]
    assert all(0.3 < v["share_a_as_a"] < 0.7 for v in ex["letter_balance_by_start"].values())
    assert "transmission_minus_override" in res["informed_split"]["per_model"]
    json.dumps(res, default=lambda x: x.item())


def test_full_run_needs_every_scheduled_arm(recs):
    with pytest.raises(S.Refused):
        S.run_all(recs, F, full=True)                                         # 10 of 61 clusters
    with pytest.raises(S.Refused):                                             # a model's secondary arms all absent
        S.run_all({k: v for k, v in recs.items() if not (k[0] == "qwen3.5-9b" and k[2] != "primary")}, F, full=True)
    assert set(S.expected_arms(F)) >= {(k[0], k[2]) for k in recs}


# ---------------------------------------------------------------- (3) estimators on synthetic tables
def synth(effects, clusters=range(1, 25), sd=0.01, seed=0, arm="primary", key="board", per_block=4):
    """{(model, j, arm): {key: effect + noise, 'server_start': ...}}; blocks of per_block clusters, one start per
    (model, block); a block effect is added."""
    rng = np.random.default_rng(seed)
    out = {}
    for m, eff in effects.items():
        bl = {b: rng.normal(0, sd) for b in range(100)}
        for j in clusters:
            b = (j - 1) // per_block
            out[(m, j, arm)] = {key: eff + bl[b] + rng.normal(0, sd), "server_start": f"{m}/{arm}/start{b}"}
    return out


def test_per_model_and_pooled_recover_planted_values():
    eff = {"gemma-2-9b-it": 0.10, "qwen3.5-9b": 0.06, "gemma-3-27b-it": 0.02, "qwen3.5-27b": 0.06, "llama-3.1-8b-it": -0.2}
    t = synth(eff, sd=0.002)
    for m, e in eff.items():
        assert abs(S.per_model(t, m, "board")["theta"] - e) < 0.004
    pooled = S.pooled(t, CA.CONF, "board")
    assert abs(pooled["theta"] - 0.06) < 0.004 and pooled["n_clusters"] == 24
    # pooled = mean over models within cluster, then the confirmatory model (Llama never enters)
    vals = [np.mean([t[(m, j, "primary")]["board"] for m in CA.CONF]) for j in range(1, 25)]
    blocks = ["|".join(t[(m, j, "primary")]["server_start"] for m in CA.CONF) for j in range(1, 25)]
    assert abs(pooled["theta"] - CA.infer(vals, blocks)["theta"]) < 1e-12


def test_paired_difference_and_size_contrasts():
    t = synth({"gemma-3-27b-it": 0.09, "gemma-2-9b-it": 0.03, "qwen3.5-27b": 0.0, "qwen3.5-9b": 0.0}, sd=0.003)
    d = S.paired_difference(t, ("gemma-3-27b-it", "primary"), ("gemma-2-9b-it", "primary"), "board")
    assert abs(d["theta"] - 0.06) < 0.005 and d["ci95"][0] > 0
    q = S.paired_difference(t, ("qwen3.5-27b", "primary"), ("qwen3.5-9b", "primary"), "board")
    assert q["ci95"][0] < 0 < q["ci95"][1]


def test_degenerate_values_are_reported_not_fitted():
    t = {("m", j, "primary"): {"board": 0.0, "server_start": f"s{j // 3}"} for j in range(1, 10)}
    e = S.per_model(t, "m", "board")
    assert e["theta"] == 0.0 and e["se"] is None and "degenerate" in e
    assert S._summ(e)["degenerate"]
    assert S.per_model({k: v for k, v in list(t.items())[:2]}, "m", "board") is None      # fewer than 3 clusters


def test_consistency_rule():
    e = lambda th, lo, hi: {"theta": th, "ci95": [lo, hi]}
    assert S._consistent([e(0.05, 0.01, 0.09), e(0.03, 0.0, 0.06)]) is True
    assert S._consistent([e(0.05, 0.01, 0.09), e(-0.01, -0.05, 0.03)]) is False      # sign differs
    assert S._consistent([e(0.08, 0.06, 0.10), e(0.02, 0.01, 0.03)]) is False        # no overlap
    assert S._consistent([e(0.05, 0.01, 0.09)]) is None


def test_subset_conclusions_use_holm_and_tost():
    merged = synth({m: 0.10 for m in CA.CONF}, key="board", sd=0.003)
    other = synth({m: 0.0 for m in CA.CONF}, key="persistence", sd=0.003, seed=1)      # same start labels
    for k, v in other.items():
        merged[k]["persistence"] = v["persistence"]
    r = S.conclusions(merged, S.SUBSETS["27b_only"])
    assert r["board"]["decision"] == "effect" and r["board"]["significant"]
    assert r["persistence"]["decision"].startswith("equivalence")
    ps = {k: r[k]["estimate"]["p_two_sided"] for k in S.CONTRASTS}
    assert {k: r[k]["significant"] for k in S.CONTRASTS} == CA.holm(ps)


def test_t1_sign_flags():
    t = {**synth({"qwen3.5-9b": 0.05}, clusters=range(1, 25), sd=0.003),
         **synth({"qwen3.5-9b": -0.04}, clusters=[1, 5, 9, 13, 17, 21], sd=0.003, arm="T1", seed=2)}
    for k, v in t.items():
        v["persistence"] = v["board"]
    r = S.t1_regime(t)["qwen3.5-9b"]
    assert r["n_clusters"] == 6
    assert r["board"]["sign_matches_primary"] is False and r["board"]["sign_matches_primary_same_clusters"] is False
    assert r["board"]["t1_minus_primary"]["theta"] < -0.07


def test_rule_ii_early_difference():
    t = {}
    for j in range(1, 7):
        base = np.linspace(0.5, 0.8, 31)
        bump = np.zeros(31); bump[1:6] = 0.04
        t[("gemma-2-9b-it", j, "primary")] = {"traj_live": base.tolist(), "traj_blind": base.tolist(), "server_start": f"s{j // 3}"}
        t[("gemma-2-9b-it", j, "rule_ii")] = {"traj_live": (base + bump + 0.001 * j).tolist(), "traj_blind": base.tolist(),
                                              "server_start": f"s{j // 3}", "board": 0.0}
    for k in t:
        t[k].setdefault("board", 0.0)
    r = S.rule_ii(t)["gemma-2-9b-it"]
    assert abs(r["early_live_diff"]["theta"] - (0.04 + 0.0035)) < 1e-3
    assert max(abs(x) for x in r["blind_diff_by_sweep"]) == 0


def test_compare_cells_bound():
    rng = np.random.default_rng(3)
    g = lambda mu, sd, n, G=20: {c: list(rng.normal(mu, sd, n // G)) for c in range(G)}
    A = {("none", 1, 2): g(0.6, 0.05, 400), ("3/4", 0, 1): g(0.4, 0.05, 400), ("9/10", 1, 4): g(0.9, 0.01, 20, 4)}
    B = {("none", 1, 2): g(0.6, 0.05, 400), ("3/4", 0, 1): g(0.47, 0.05, 400), ("9/10", 1, 4): g(0.5, 0.01, 400)}
    m = "gemma-2-9b-it"                                    # zero between-start drift: the bound is the SEs alone
    r = S.compare_cells(m, A, B, (30, 5), (30, 5), 2.0)
    assert r["cells_checked"] == 2 and r["mismatches"] == 1                 # the 20-call cell is not checked
    row = {tuple(c["cell"]): c for c in r["cells"]}
    assert row[("none", 1, 2)]["within"] and not row[("3/4", 0, 1)]["within"]
    c = row[("3/4", 0, 1)]
    assert abs(c["bound"] - 2 * math.sqrt(c["drift_sd"] ** 2 + c["se_a"] ** 2 + c["se_b"] ** 2)) < 1e-15
    m2 = max(CA.ALL_MODELS, key=lambda x: S.drift_sd_prob(x, 0.5))          # a model with between-start drift
    assert S.drift_sd_prob(m2, 0.5) > 0
    r2 = S.compare_cells(m2, A, B, (30, 5), (30, 5), 2.0)
    assert all(c["bound"] > row[tuple(c["cell"])]["bound"] for c in r2["cells"])


def test_drift_sd_in_probability():
    vc = json.loads((ROOT / "gates/S4/results/s4_variance_components.json").read_text())
    for m in CA.ALL_MODELS:
        sd = math.sqrt(vc[m]["w3"]["var_start_offset_nats2"] + vc[m]["w3"]["var_probe_x_start_nats2"])
        assert abs(S.drift_sd_prob(m, 0.3) - 0.21 * sd / CA.primary_T(m)) < 1e-12


def test_battery_cells_shape():
    b = S.battery_cells("qwen3.5-9b")
    assert all(cell[2] is None for cell in b["blind"]) and all(cell[2] in range(5) for cell in b["live"])
    assert {cell[0] for cell in b["blind"]} == {"none", "3/5", "3/4", "9/10"}
    assert sum(len(v) for v in b["blind"].values()) == 84            # S5 contexts (all blind, all W3), one group each
    s4 = json.loads((ROOT / "gates/S4/probes/s4_contexts.json").read_text())
    assert sum(len(v) for v in b["live"].values()) == sum(1 for c in s4 if c["live"])
    assert all(len(x) == 1 and 0 < x[0] < 1 for v in b["live"].values() for x in v.values())


def test_cluster_robust_se():
    one = {c: [0.5 + 0.01 * c] for c in range(10)}                 # one value per group: SD / sqrt(G)
    mu, se, n, G = S._stats(one)
    v = [0.5 + 0.01 * c for c in range(10)]
    assert abs(se - np.std(v, ddof=1) / math.sqrt(10)) < 1e-15 and n == G == 10
    dup = {c: [0.5 + 0.01 * c] * 50 for c in range(10)}            # the same values repeated: the SE does not shrink
    assert abs(S._stats(dup)[1] - se) < 1e-12


def test_estimate_survives_a_near_degenerate_set():
    vals = {j: (0.05 if j == 12 else 0.0) for j in range(1, 13)}
    labels = {j: ("a" if j <= 4 else "b" if j <= 8 else f"s{j}") for j in vals}
    e = S.estimate(vals, labels)
    assert e["theta"] is not None and (e.get("degenerate") or e["se"] > 0)


def test_model_check_with_synthetic_predictions():
    clusters = list(range(1, 11))
    t = {}
    P = {"clusters": clusters, "pooled_confirmatory": {}, "per_model": {}, "per_cluster_mean": {}, "per_cluster_p05_p95": {}}
    for k in S.CONTRASTS:
        P["pooled_confirmatory"][k] = {"mean": 0.05, "p05": 0.0, "p50": 0.05, "p95": 0.1}
    for m in CA.ALL_MODELS:
        P["per_model"][m] = {k: {"mean": 0.05, "p05": 0.0, "p50": 0.05, "p95": 0.1} for k in S.CONTRASTS}
        P["per_cluster_mean"][m] = {k: [0.01 * j for j in clusters] for k in S.CONTRASTS}
        P["per_cluster_p05_p95"][m] = {k: [[0.01 * j - 0.02 for j in clusters], [0.01 * j + 0.02 for j in clusters]]
                                       for k in S.CONTRASTS}
        for j in clusters:
            off = 1.0 if m == "llama-3.1-8b-it" else 0.0                  # Llama far off: never pooled
            t[(m, j, "primary")] = {"board": 0.01 * j + (0.05 if j > 5 else 0.0) + off, "persistence": 0.01 * j + 0.2}
    r = S.model_check(t, P, {"board": 0.07, "persistence": 0.25})
    # observed = arithmetic mean over clusters (as the predictions); board 0.08 inside, persistence 0.255 outside
    assert abs(r["pooled"]["board"]["observed_mean"] - 0.08) < 1e-12 and r["pooled"]["board"]["inside_90"]
    assert not r["pooled"]["persistence"]["inside_90"] and r["pooled"]["board"]["theta_confirmatory_model"] == 0.07
    assert r["per_model"]["llama-3.1-8b-it"]["board"]["inside_90"] is False
    assert r["share_per_model_inside_90"] == 0.4                          # four board values of ten
    pc = r["per_cluster"]["gemma-2-9b-it"]
    assert abs(pc["persistence"]["slope_obs_on_pred"] - 1) < 1e-9 and pc["board"]["slope_obs_on_pred"] > 1
    assert pc["persistence"]["share_inside_90"] == 0.0 and pc["board"]["share_inside_90"] == 0.5
    pooled = r["per_cluster"]["confirmatory_models_pooled"]["board"]
    assert pooled["share_inside_90"] == 0.5 and pooled["n"] == 40           # four models, Llama left out
    assert "all_models" not in r["per_cluster"]


# Independent blind review: synthetic regression cases.
def test_unblinding_rejects_an_author_with_only_an_owner_prefix(tmp_path, code_repo):
    coord = _coord(tmp_path, [OWNER_ROW.replace('| owner |', '| ownerbot |')])
    with pytest.raises(S.Refused):
        S.require_unblinding(coord, 'D99')


def test_degenerate_subset_retains_estimates_and_other_contrasts():
    table = {}
    for m in S.SUBSETS['27b_only']:
        for j in range(1, 13):
            table[(m, j, 'primary')] = {
                'board': 0.0, 'persistence': 0.1 + 0.002 * j,
                'server_start': f'{m}/s{(j - 1) // 4}'}
    result = S.conclusions(table, S.SUBSETS['27b_only'])
    board = result['board']
    assert board['estimate']['theta'] == 0.0
    assert board['estimate']['ci95'] is None and board['estimate']['degenerate']
    assert board['significant'] is None and board['decision'] is None
    assert result['persistence']['estimate']['ci95'] is not None
    assert result['persistence']['decision'] == 'effect'


def test_unfitted_contrast_does_not_shrink_the_holm_family(monkeypatch):
    fitted = {'theta': 0.04, 'se': 0.02, 'df': 10, 'ci95': [-0.004, 0.084],
              'ci90': [0.004, 0.076], 'p_two_sided': 0.04,
              'tost_equivalent': False, 'n_clusters': 12}
    unknown = dict(fitted, theta=0.0, se=None, df=None, ci95=None, ci90=None,
                   p_two_sided=None, tost_equivalent=None, degenerate='every value equal; no fit')
    monkeypatch.setattr(S, 'pooled', lambda table, models, key: fitted if key == 'board' else unknown)
    result = S.sensitivity({}, {k: 'effect' for k in S.CONTRASTS})
    for name in S.SUBSETS:
        assert result[name]['board']['significant'] is False  # p=.04 must still face two-test Holm
        assert result[name]['persistence']['decision'] is None
        assert result[name]['persistence']['differs_from_primary'] is None


def test_recipient_bands_use_clusters_as_the_independent_units():
    model, table = S.ALL[0], {}
    for j, x in enumerate([0.2, 0.4, 0.6, 0.8], 1):
        branch = {'traj_pulsed': [x] * 9, 'traj_unpulsed': [x] * 9}
        table[(model, j, 'primary')] = {
            'traj_live': [x] * 31, 'traj_blind': [x] * 31,
            'branches': [copy.deepcopy(branch), copy.deepcopy(branch)]}
    result = S.trajectories(table)[model]
    half_width = 1.96 * np.std([0.2, 0.4, 0.6, 0.8], ddof=1) / math.sqrt(4)
    for name in ('recipients_pulsed', 'recipients_unpulsed'):
        assert result[name]['mean'][0] == pytest.approx(0.5)
        assert result[name]['lo95'][0] == pytest.approx(0.5 - half_width)
        assert result[name]['hi95'][0] == pytest.approx(0.5 + half_width)
    # Opposite branch deviations cancel within every cluster: no between-cluster variation remains.
    for o in table.values():
        o['branches'][1]['traj_pulsed'] = [1.0 - x for x in o['branches'][0]['traj_pulsed']]
    band = S.trajectories(table)[model]['recipients_pulsed']
    assert band['lo95'][0] == pytest.approx(0.5)
    assert band['hi95'][0] == pytest.approx(0.5)


@pytest.mark.parametrize('predicted', [0.0, 0.25])
def test_model_check_reports_an_undefined_slope_without_losing_coverage(predicted):
    clusters, table = [1, 2, 3, 4], {}
    P = {'clusters': clusters, 'pooled_confirmatory': {}, 'per_model': {},
         'per_cluster_mean': {}, 'per_cluster_p05_p95': {}}
    interval = {'p05': -0.1, 'p95': 0.1}
    for k in S.CONTRASTS:
        P['pooled_confirmatory'][k] = dict(interval)
    for m in S.ALL:
        P['per_model'][m] = {k: dict(interval) for k in S.CONTRASTS}
        P['per_cluster_mean'][m] = {k: [predicted] * 4 for k in S.CONTRASTS}
        P['per_cluster_p05_p95'][m] = {k: [[-0.1] * 4, [0.1] * 4] for k in S.CONTRASTS}
        for j in clusters:
            table[(m, j, 'primary')] = {k: 0.01 * j for k in S.CONTRASTS}
    result = S.model_check(table, P)
    for m in S.ALL + ['confirmatory_models_pooled']:
        for k in S.CONTRASTS:
            assert result['per_cluster'][m][k]['slope_obs_on_pred'] is None
            assert result['per_cluster'][m][k]['share_inside_90'] == 1.0
