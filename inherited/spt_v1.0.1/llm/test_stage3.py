"""Pre-data checks for Stage 3 (no API calls).   python llm/test_stage3.py

1. Live prompts vs the Stage 1 battery template (addendum a): every framing, own position, mapping, option order,
   contact order and the no-contacts arm; mutated prompts (changed wording, an added history line, instruction v1,
   a missing contact) must be rejected.
2. Ising-baseline regression (addendum e): the Stage 2 'ising' rows use exactly the Stage 1 additive A0 β (and its
   bootstrap draws), never the k-scaled surrogate coupling (the bug fixed in EXECUTION_LOG entry 12).
3. Live-runner dynamics: llm/stage3.py driven by a mock LLM that answers with the fitted surrogate's own response
   function must reproduce llm/surrogate.py's measures (same protocol, independent implementation).
"""
import json, math, os, random, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battery, stage2, stage3, surrogate as S

ROOT = stage3.ROOT


def test_prompts(n=3000):
    rng = random.Random(0)
    stage1 = {}
    for it in battery.items("neutral_own"):
        stage1[it["prompt"]] = it
    for i in range(n):
        framing = rng.choice(list(battery.FRAMINGS))
        k = rng.randint(1, 6)
        seq0 = [rng.choice(battery.TYPES) for _ in range(k)]
        counts = tuple(seq0.count(t) for t in battery.TYPES)
        s0, mapping, order = rng.choice((1, -1)), rng.randrange(2), rng.randrange(2)
        seq = seq0[:]; rng.shuffle(seq)
        for contacts in (True, False):
            p = stage3.render_live(framing, counts, s0, mapping, order, seq, contacts)
            assert stage3.check_prompt(p, framing, counts, s0, mapping, order, contacts)
            assert "previous" not in p.lower() and "history" not in p.lower() and "round" not in p.lower()
            if not contacts:
                assert stage3.CONTACT_HEADER not in p
                continue
            assert sum(1 for l in p.split("\n") if l.startswith("- ")) == k      # contacts listed individually
            if framing == "neutral":     # the reference is a literal Stage 1 battery prompt
                rc = (counts, s0) if mapping == 0 else ((counts[1], counts[0], counts[3], counts[2]), -s0)
                ref, _ = battery.render("neutral", rc[0], rc[1], 0, order, 0)
                assert ref in stage1
            bad = [p.replace("Reply with exactly one letter", "Answer with a single letter"),
                   p.replace("The people you are in contact with", "Your previous choices: A, A.\nThe people you are in contact with"),
                   "\n".join(l for j, l in enumerate(p.split("\n")) if not (l.startswith("- ") and j == p.split("\n").index(next(x for x in p.split("\n") if x.startswith("- "))))),
                   p.replace("holds", "has", 1),
                   p + " "]
            for b in bad:
                try:
                    stage3.check_prompt(b, framing, counts, s0, mapping, order, contacts)
                except AssertionError:
                    continue
                raise AssertionError("mutated prompt accepted:\n" + b)
    # the live order really is random per call, and different from the Stage 1 seeded order
    counts = (2, 1, 1, 0); seen = set()
    for _ in range(200):
        seq = ["aP", "aP", "aQ", "rP"]; rng.shuffle(seq)
        seen.add(stage3.render_live("political", counts, 1, 0, 0, seq))
    assert len(seen) == 12
    print(f"prompts: {n} random cells x (contacts, no contacts) match the Stage 1 template; mutations rejected")


def test_ising_beta():
    n = 0
    for key in stage2.CONFIRMATORY + stage2.GATE_FAILED + stage2.SPOT:
        for framing in ("neutral", "political", "workplace"):
            if not os.path.exists(os.path.join(ROOT, "results/llm/fits/surrogate", key + ".json")):
                continue
            fit = stage2.load_fit(key, framing)
            if fit is None:
                continue
            main = json.load(open(os.path.join(ROOT, "results/llm/fits/main", key + ".json")))
            a0 = {x["arm"]: x for x in main["arms"]}[stage2.FRAME_ARM[framing]]
            beta, draws = a0["coef"]["beta"]["est"], np.array(a0["draws"]["beta"])
            row = stage2.param_row(fit, framing, None, "ising")
            assert row[S.B_A] == row[S.B_R] == beta, (key, framing)
            assert row[[S.P_VOTER, S.ALPHA, S.GAMMA, S.H_C, S.H_L, S.H_O]].sum() == 0
            for d in (0, 7, len(fit["draws"]) - 1):
                assert stage2.param_row(fit, framing, d, "ising")[S.B_A] == draws[d % len(draws)]
            n += 1
    # anchor values from EXECUTION_LOG entry 12 (the pre-fix baseline used 6.95 and 0.51)
    assert abs(stage2.load_fit("llama-70b", "neutral")["beta_A0"] - 0.65) < 0.01
    assert abs(stage2.load_fit("qwen-9b", "neutral")["beta_A0"] - 0.09) < 0.01
    print(f"ising baseline: beta == Stage 1 A0 estimate and draws for {n} endpoint x framing fits")


def mock_llm(row, framing):
    """Answer like the fitted surrogate (letter-A frame): logit P(A) = k^-a(b_a Ma - b_r Mr) + g s + h_C c + h_L + h_O O."""
    def call(body, rep):
        p = body["messages"][0]["content"]; lines = p.split("\n")
        X = re.search(r"exactly one letter, ([AB]) or", lines[-1]).group(1)
        own = re.search(r"You currently hold position ([AB])", p).group(1)
        ma = mr = k = 0
        for l in lines:
            m = re.match(r"- (An ally|A rival) holds ([AB])", l)
            if m:
                k += 1; v = 1 if m.group(2) == "A" else -1
                if m.group(1) == "An ally": ma += v
                else: mr += v
        cA = 0.0
        if framing != "neutral":
            P = battery.FRAMINGS[framing]["content"]["P"]
            cA = 1.0 if f"A ({P})" in p else -1.0
        eta = (k ** -row[S.ALPHA] if k else 0.0) * (row[S.B_A] * ma - row[S.B_R] * mr) \
            + row[S.GAMMA] * (1 if own == "A" else -1) + row[S.H_C] * cA + row[S.H_L] + row[S.H_O] * (1 if X == "A" else -1)
        pa = 1 / (1 + math.exp(-eta))
        return {"resp": {"first": {"top": [["A", math.log(max(pa, 1e-12))], ["B", math.log(max(1 - pa, 1e-12))]]}}}
    return call


def test_dynamics(pids=("P4", "P1", "P4-nc"), G=10, R=40):
    import pandas as pd
    for pid in pids:
        key, framing, rho, contacts = stage3.POINTS[pid]
        fit = stage2.load_fit(key, framing)
        row = S.params_from_fit(fit["names"], fit["est"], framing)
        assert row[S.P_VOTER] < 1e-6 or fit["choice"] == "A3", "mock covers the logit rule only"
        row[S.P_VOTER] = 0.0
        if not contacts:
            row[S.B_A] = row[S.B_R] = 0.0
        live = []
        for g in range(G):
            ch = [stage3.chain(pid, 100 + g, r, call=mock_llm(row, framing)) for r in (0, 1)]
            st = np.stack([c[1] for c in ch]); upd = pd.concat([c[0] for c in ch])
            assert upd.invalid_first.sum() == 0
            live.append(stage3.graph_measures(*stage3.graph(pid, 100 + g), st, upd))
        live = pd.DataFrame(live)
        sim = []
        for j in range(R):
            ip, nb, tie = S.make_graph(100, rho, 0.0, np.random.default_rng(900 + j), "rrg")
            sim.append(dict(zip(S.MEASURES, S.run(ip, nb, tie, np.zeros(100, np.int64), row[None, :], 10, 10, 900 + j, False, 0.0))))
        sim = pd.DataFrame(sim)
        for m in ("abs_m", "persistence", "flip_rate", "unsatisfied", "abs_q"):
            se = math.sqrt(live[m].var() / G + sim[m].var() / R) + 1e-3
            z = (live[m].mean() - sim[m].mean()) / se
            print(f"  {pid} {m:12s} live-runner {live[m].mean():.3f}  simulator {sim[m].mean():.3f}  z {z:+.2f}")
            assert abs(z) < 3.5, (pid, m, z)
    print("dynamics: live runner with a surrogate-mock LLM reproduces llm/surrogate.py")


def main():
    test_prompts()
    test_ising_beta()
    test_dynamics()
    print("ALL STAGE 3 PRE-DATA CHECKS PASSED")


if __name__ == "__main__":
    main()
