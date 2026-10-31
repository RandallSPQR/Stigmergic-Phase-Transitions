"""Stage 3: live networks of LLM agents (protocol: llm/STAGE3_PREDICTIONS.md and its pre-data addendum).

  python llm/stage3.py run [--points P1 P2 ...] [--workers 70] [--budget 12]
  python llm/stage3.py measures            # results/llm/stage3/measures_*.csv + summary.csv from the update logs
  python llm/stage3.py check               # prompt-template self-check, no API calls

One chain = one replica on one graph: N = 100 agents, random-regular d = 4, ties rival w.p. ρ (ε = 0), 50/50 random
start, 10 warm-up + 10 measured sweeps of random-sequential updates (i drawn with replacement, as llm/surrogate.py).
Every update is ONE live call built only from the current state (own position + current contact positions; no
history), with a fresh contact order, letter mapping and option order per call. Each prompt is verified against
the Stage 1 battery template before it is sent (check_prompt). Invalid replies (lp: no A/B in the top-5 or leak >
5%; sample: not a single A/B letter) are re-drawn with fresh per-call randomisation, up to MAX_ATTEMPTS; after that
the agent keeps its position. Calls are cached under a replicate tag unique to (point, graph, replica, sweep,
update, attempt), so a rerun reproduces every chain exactly at no cost (resume = rerun).
"No-contacts" arms (P2-nc, P4-nc): the same agents and protocol, but the prompt omits the contact block.
"""
import argparse, gzip, hashlib, json, math, os, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battery, client, surrogate as S
from endpoints import E
from run_stage1 import parse_lp, parse_sample

ROOT = client.ROOT
OUT = os.path.join(ROOT, "results", "llm", "stage3")
N, D, N_WARM, N_MEAS, N_GRAPHS = 100, 4, 10, 10, 5
MAX_ATTEMPTS, LEAK_MAX, INVALID_FLAG = 3, 0.05, 0.02
# id: (endpoint, framing, rho, contacts shown)
POINTS = {
    "P1": ("qwen-122b", "neutral", 0.25, True),
    "P2": ("qwen-9b", "political", 0.5, True),
    "P3": ("llama-70b", "political", 0.25, True),
    "P4": ("nemo-12b", "workplace", 0.25, True),
    "P5": ("gpt6-luna", "neutral", 0.0, True),
    "P2-nc": ("qwen-9b", "political", 0.5, False),
    "P4-nc": ("nemo-12b", "workplace", 0.25, False),
}
CONTACT_HEADER = "The people you are in contact with, and the position each currently holds:"


def _seed(*parts):
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:15], 16)


GRAPH_HASHES = os.path.join(OUT, "graph_hashes.json")


def graph(pid, g, check=True):
    """Graph g of a point. No-contacts arms reuse their parent point's graphs (same agents).
    The graph comes from networkx.random_regular_graph, which builds DIFFERENT graphs from the same seed across
    networkx versions (3.3 vs 3.7: EXECUTION_LOG entry 51). check=True asserts the committed fingerprint of the
    original Stage 3 graph, so a mismatched environment fails loudly instead of silently running other graphs."""
    base = pid.split("-")[0]
    rho = POINTS[base][2]
    ip, nb, tie = S.make_graph(N, rho, 0.0, np.random.default_rng(_seed("stage3-graph", base, g)), "rrg", d=D)
    if check and os.path.exists(GRAPH_HASHES):
        h = hashlib.sha256(np.concatenate([ip, nb, tie]).astype(np.int64).tobytes()).hexdigest()[:16]
        want = json.load(open(GRAPH_HASHES)).get(f"{base}:{g}")
        assert want is None or h == want, f"graph {base}:{g} differs from the original Stage 3 graph (networkx version?)"
    return ip, nb, tie


# ---------------------------------------------------------------- prompts
def render_live(framing, counts, s0, mapping, order, seq, contacts=True):
    text, _ = battery.render(framing, counts, s0, mapping, order, 0, seq=seq)
    if contacts:
        return text
    lines = text.split("\n")
    a = lines.index(CONTACT_HEADER)
    b = a + 1 + sum(counts)               # header + contact lines, then the blank line
    return "\n".join(lines[:a] + lines[b + 1:])


def check_prompt(prompt, framing, counts, s0, mapping, order, contacts=True):
    """Assert the live prompt is byte-identical to the Stage 1 battery template for this cell, up to the order of
    the individual contact lines (randomised per call). Neutral framing with mapping 1 is compared with the Stage 1
    prompt it equals after relabelling (P<->Q swapped, mapping 0), which is in the Stage 1 battery. No-contacts
    prompts must equal the template with exactly the contact block removed."""
    assert s0 in (1, -1)
    ref_cell = (counts, s0, mapping)
    if framing == "neutral" and mapping == 1:
        ref_cell = ((counts[1], counts[0], counts[3], counts[2]), -s0, 0)
    ref, _ = battery.render(framing, ref_cell[0], ref_cell[1], ref_cell[2], order, 0)
    if not contacts:
        L = ref.split("\n"); a = L.index(CONTACT_HEADER)
        ref = "\n".join(L[:a] + L[a + 2 + sum(counts):])
        assert prompt == ref, "no-contacts prompt differs from template"
        assert "- An ally" not in prompt and "- A rival" not in prompt
        return True
    P, R = prompt.split("\n"), ref.split("\n")
    assert len(P) == len(R), "line count differs from template"
    nb = [j for j, l in enumerate(R) if l.startswith("- ")]
    assert [j for j, l in enumerate(P) if l.startswith("- ")] == nb and len(nb) == sum(counts)
    assert all(P[j] == R[j] for j in range(len(R)) if j not in nb), "non-contact text differs from template"
    assert sorted(P[j] for j in nb) == sorted(R[j] for j in nb), "contact lines differ from template"
    X, Y = ("A", "B") if order == 0 else ("B", "A")
    assert P[-1] == battery.INSTRUCTION[2].format(X=X, Y=Y), "instruction is not v2"
    return True


# ---------------------------------------------------------------- one chain
def chain_rng(pid, g, r, run_tag=""):
    """Per-chain RNG (start, agent draws, presentation). run_tag "" = the original Stage 3 run; a replicate uses its
    own tag, so its starts and per-call randomisation are fresh while the graphs stay the same."""
    return random.Random(_seed("stage3-chain", pid, g, r) if not run_tag else _seed("stage3-chain", run_tag, pid, g, r))


def initial_state(pid, g, r, run_tag=""):
    rng = chain_rng(pid, g, r, run_tag)
    return np.array([1 if rng.random() < 0.5 else -1 for _ in range(N)], np.int64)


def chain(pid, g, r, budget=None, call=None, run_tag=""):
    """Run (or replay from cache) one replica. Returns (updates DataFrame, states array [N_WARM+N_MEAS+1, N])."""
    key, framing, rho, contacts = POINTS[pid]
    model, tag, mode, roff, _ = E[key]
    call = call or (lambda b, rep: client.chat(b, rep=rep, budget_usd=budget))
    ip, nb, tie = graph(pid, g)
    rng = chain_rng(pid, g, r, run_tag)
    s = np.array([1 if rng.random() < 0.5 else -1 for _ in range(N)], np.int64)
    states, rows = [s.copy()], []
    for t in range(N_WARM + N_MEAS):
        for u in range(N):
            i = rng.randrange(N)
            seq0 = []
            for q in range(ip[i], ip[i + 1]):
                seq0.append(("a" if tie[q] > 0 else "r") + ("P" if s[nb[q]] > 0 else "Q"))
            counts = tuple(seq0.count(x) for x in battery.TYPES)
            s0 = int(s[i]); new, att, first_invalid, last = s0, 0, None, {}
            for att in range(1, MAX_ATTEMPTS + 1):
                mapping, order = rng.randrange(2), rng.randrange(2)
                seq = seq0[:]; rng.shuffle(seq)
                prompt = render_live(framing, counts, s0, mapping, order, seq, contacts)
                check_prompt(prompt, framing, counts, s0, mapping, order, contacts)
                b = battery.body(model, tag, prompt, mode, roff, 1.0)
                rec = call(b, f"stage3{'-' + run_tag if run_tag else ''}:{pid}:{g}:{r}:{t}:{u}:{att}")
                resp = rec["resp"]
                if mode == "lp":
                    p = parse_lp(resp.get("first")); pA, leak = p["pA"], p["leak"]
                    valid = pA is not None and leak <= LEAK_MAX
                    letter = ("A" if rng.random() < pA else "B") if valid else None
                else:
                    letter = parse_sample(resp.get("content")); pA, leak = None, None
                    valid = letter is not None
                if first_invalid is None:
                    first_invalid = not valid
                last = dict(mapping=mapping, order=order, pA=pA, leak=leak, letter=letter,
                            cost=(resp.get("usage") or {}).get("cost") or 0.0)
                if valid:
                    new = 1 if letter == battery.letters(mapping)["P"] else -1
                    break
            rows.append(dict(point=pid, graph=g, replica=r, sweep=t, step=u, agent=i,
                             counts="".join(map(str, counts)), s0=s0, new=new, attempts=att,
                             invalid_first=int(first_invalid), kept_after_invalid=int(not valid), **last))
            s[i] = new
        states.append(s.copy())
    return pd.DataFrame(rows), np.array(states)


def save_chain(pid, g, r, df, states):
    d = os.path.join(OUT, "chains", pid); os.makedirs(d, exist_ok=True)
    df.to_csv(os.path.join(d, f"g{g}_r{r}.csv.gz"), index=False)
    np.save(os.path.join(d, f"g{g}_r{r}_states.npy"), states.astype(np.int8))


# ---------------------------------------------------------------- measures (identical definitions to surrogate.run)
def graph_measures(ip, nb, tie, st, upd):
    """st: [2, N_WARM+N_MEAS+1, N] states after each sweep (index 0 = initial); upd: the two replicas' update logs."""
    ref = st[:, N_WARM]                                  # configuration at the end of warm-up
    acc = np.zeros(8); n = 0
    recv = np.repeat(np.arange(N), np.diff(ip))
    for t in range(N_WARM + 1, N_WARM + N_MEAS + 1):
        s = st[:, t]
        m1, m2 = s[0].mean(), s[1].mean()
        q = (s[0] * s[1]).mean()
        c = (s * ref).mean(axis=1)
        agree = s[:, recv] == s[:, nb]
        un = (((tie > 0) & ~agree) | ((tie < 0) & agree)).sum() * 0.5 / max(ip[-1], 1)
        acc += [0.5 * (abs(m1) + abs(m2)), 0.5 * (m1 + m2), 0.5 * (m1 ** 2 + m2 ** 2), abs(q), q * q,
                c.mean(), 0.0, un]
        n += 1
    res = dict(zip(S.MEASURES, acc / n))
    meas = upd[upd.sweep >= N_WARM]
    res["flip_rate"] = float((meas.new != meas.s0).mean())
    return res


def measures():
    floor = pd.read_csv(os.path.join(ROOT, "results/llm/stage2/floor.csv"))
    floor = floor[(floor.graph == "rrg") & (floor.N == N)].groupby("rho").unsat_floor.mean()
    rows, inv = [], []
    for pid, (key, framing, rho, contacts) in POINTS.items():
        d = os.path.join(OUT, "chains", pid)
        if not os.path.isdir(d):
            continue
        for g in range(N_GRAPHS):
            paths = [os.path.join(d, f"g{g}_r{r}.csv.gz") for r in (0, 1)]
            if not all(os.path.exists(p) for p in paths):
                continue
            upd = pd.concat([pd.read_csv(p) for p in paths])
            st = np.stack([np.load(os.path.join(d, f"g{g}_r{r}_states.npy")).astype(np.int64) for r in (0, 1)])
            ip, nb, tie = graph(pid, g)
            m = graph_measures(ip, nb, tie, st, upd)
            m["excess_unsat"] = m["unsatisfied"] - floor.loc[rho]
            rows.append(dict(point=pid, endpoint=key, framing=framing, rho=rho, contacts=contacts, graph=g, **m))
            inv.append(dict(point=pid, graph=g, updates=len(upd), invalid_first=upd.invalid_first.sum(),
                            kept_after_invalid=upd.kept_after_invalid.sum(), cost=upd.cost.sum()))
    df = pd.DataFrame(rows); iv = pd.DataFrame(inv)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "measures_by_graph.csv"), index=False)
    agg = df.groupby("point").agg(n_graphs=("graph", "size"), **{m: (m, "mean") for m in
                                  ["abs_m", "m", "persistence", "excess_unsat", "flip_rate", "abs_q", "unsatisfied"]})
    v = iv.groupby("point")[["updates", "invalid_first", "kept_after_invalid", "cost"]].sum()
    v["invalid_rate"] = v.invalid_first / v.updates
    v["flag_invalid_gt_2pct"] = v.invalid_rate > INVALID_FLAG
    out = agg.join(v); out.to_csv(os.path.join(OUT, "summary.csv"))
    print(out.to_string())
    return out


# ---------------------------------------------------------------- driver
def run(points, workers, budget):
    jobs = [(p, g, r) for p in points for g in range(N_GRAPHS) for r in (0, 1)]
    done = lambda p, g, r: os.path.exists(os.path.join(OUT, "chains", p, f"g{g}_r{r}_states.npy"))
    todo = [j for j in jobs if not done(*j)]
    print(f"stage3: {len(jobs)} chains, {len(todo)} to run; workers {workers}; budget ${budget}", flush=True)
    t0 = time.time()

    def one(j):
        df, st = chain(*j, budget=budget)
        save_chain(*j, df, st)
        return j, len(df), df.invalid_first.mean()

    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(one, j): j for j in todo}
        for f in as_completed(futs):
            try:
                j, n, iv = f.result()
                print(f"  done {j}: {n} updates, invalid_first {iv:.3%}, {time.time()-t0:.0f}s, "
                      f"session spend ${client.spend()['usd']:.3f}", flush=True)
            except client.BudgetExceeded as e:
                print("BUDGET STOP:", e, flush=True); ex.shutdown(cancel_futures=True); break
            except Exception as e:
                print("chain error", futs[f], repr(e)[:300], flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["run", "measures", "check"])
    ap.add_argument("--points", nargs="+", default=list(POINTS))
    ap.add_argument("--workers", type=int, default=70)
    ap.add_argument("--budget", type=float, default=12.0)
    a = ap.parse_args()
    if a.what == "run":
        run(a.points, a.workers, a.budget)
    elif a.what == "measures":
        measures()
    else:
        import test_stage3; test_stage3.main()
