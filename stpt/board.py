"""StPT board harness: trajectories, initial votes (D25), probes and display-pulse branches.

Isolation by construction:
- Every random number is counter-based: unif(run_key, purpose, index...) = a fixed function of its arguments
  (sha256), never a stream that one call could advance for another. So:
  - live and blind runs of a pair share the agent order, the vote draws, the layouts and the initial state;
  - a branch from a saved state at step t uses the same keys as the main trajectory from step t (common random
    numbers), so an unpulsed branch reproduces the main continuation byte for byte;
  - probes and branches never consume any number the main trajectory uses.
- Probes read the state and never write it. Pulses change only what chosen recipients SEE of chosen contacts (display
  overrides keyed by (viewer, contact)), for a fixed number of steps; real votes and evidence are never touched.
- The state is plain data (JSON round trip), so a saved state is the whole state.

Votes are content keys ("A"/"B" of the scenario); letters exist only in the rendered text. A vote is drawn as
u < sigma(l / T), with l the content-A logit from the exact readout, u = unif(run_key, "draw", step).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field

try:                                    # in the repository
    from . import prompts as P
except ImportError:                     # on a pod, loaded as a top-level module next to prompts.py
    import prompts as P                 # type: ignore


def unif(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:13], 16) / float(16 ** 13)


def perm(n: int, *parts) -> list[int]:
    return sorted(range(n), key=lambda i: unif(*parts, i))


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))


@dataclass
class Board:
    run_key: str                  # shared by the live and blind runs of a pair
    adj: list                     # adj[i] = agent i's contacts, fixed order
    story: dict                   # scenario story (question, options, uninformed sentence)
    private: list                 # per agent: report text, or None if uninformed
    favours: list                 # per agent: content key the report favours, or None
    accuracy: list                # per agent: stated accuracy string, or None
    live: bool
    T: float
    wording: str = "w3"

    @property
    def N(self) -> int:
        return len(self.adj)

    def __post_init__(self):
        if not (len(self.private) == len(self.favours) == len(self.accuracy) == len(self.adj)):
            raise ValueError("per-agent lists must match the graph size")

    def text(self, i):
        return self.private[i] if self.private[i] is not None else self.story["uninformed"]


@dataclass
class State:
    step: int
    votes: list                   # content keys
    overrides: dict = field(default_factory=dict)   # "viewer,contact" -> [content, until_step]

    def to_json(self) -> str:
        return json.dumps({"step": self.step, "votes": self.votes, "overrides": self.overrides}, sort_keys=True)

    @staticmethod
    def from_json(s: str) -> "State":
        d = json.loads(s)
        return State(d["step"], d["votes"], d["overrides"])

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()


def layout_for(run_key, purpose, idx, n_contacts=4):
    """Per-call layout. Letter mapping balanced in consecutive pairs of calls (idx 2k, 2k+1 get one mapping each, order
    by key), so it is balanced within every server-start block (D20). Option order and contact order by key."""
    a_is_A = (unif(run_key, purpose, "L", idx // 2) < 0.5) == (idx % 2 == 0)
    return {"letter_of_content": {"A": "A", "B": "B"} if a_is_A else {"A": "B", "B": "A"},
            "listed_first_letter": "A" if unif(run_key, purpose, "F", idx) < 0.5 else "B",
            "contact_order": perm(n_contacts, run_key, purpose, "C", idx)}


def content_logit_A(layout, logp_A, logp_B):
    return (logp_A - logp_B) if layout["letter_of_content"]["A"] == "A" else (logp_B - logp_A)


def displayed(state: State, viewer: int, j: int) -> str:
    ov = state.overrides.get(f"{viewer},{j}")
    return ov[0] if ov is not None and state.step < ov[1] else state.votes[j]


def _call(board: Board, kernel, i, own_vote, shown, layout, question_key, live):
    msgs = P.render(board.wording, board.story, board.text(i), own_vote, shown, layout, question_key, live=live,
                    informed=board.private[i] is not None)
    r = kernel(msgs)
    return msgs, r


def placeholder_votes(board: Board) -> list:
    """D25: seeded placeholder own vote for the first call, balanced within evidence type (uninformed; informed by
    accuracy x favoured content), across graph positions (a keyed random order within each type) and within the run
    (so within its server-start block). Identical for the live and blind runs of a pair (it depends on run_key only)."""
    groups = {}
    for i in range(board.N):
        groups.setdefault((board.private[i] is not None, board.accuracy[i], board.favours[i]), []).append(i)
    out = [None] * board.N
    for g, members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        order = sorted(members, key=lambda i: unif(board.run_key, "placeholder", str(g), i))
        first = "A" if unif(board.run_key, "placeholder-first", str(g)) < 0.5 else "B"
        second = "B" if first == "A" else "A"
        for k, i in enumerate(order):
            out[i] = first if k % 2 == 0 else second
    return out


def initial_state(board: Board, kernel, rule: str = "i"):
    """Rule (i) (D25): first vote sampled at T from the W3 BLIND evidence-only call with the placeholder own vote.
    Rule (ii): seeded 50/50. Both depend on run_key only, so live and blind runs of a pair start identically."""
    recs = []
    if rule == "ii":
        votes = ["A" if unif(board.run_key, "init-rand", i) < 0.5 else "B" for i in range(board.N)]
        return State(0, votes), recs
    ph = placeholder_votes(board)
    votes = []
    for i in range(board.N):
        layout = layout_for(board.run_key, "init", i)
        msgs, r = _call(board, kernel, i, ph[i], [], layout, "vote", live=False)
        lA = content_logit_A(layout, r["logp_A"], r["logp_B"])
        u = unif(board.run_key, "init-draw", i)
        v = "A" if u < sigmoid(lA / board.T) else "B"
        votes.append(v)
        recs.append({"kind": "init", "agent": i, "placeholder": ph[i], "prompt_sha": sha(msgs), "layout": layout,
                     "logp_A": r["logp_A"], "logp_B": r["logp_B"], "u": u, "vote": v})
    return State(0, votes), recs


def update(board: Board, state: State, kernel) -> dict:
    """One random-sequential update (agent drawn with replacement by key). Mutates state."""
    t = state.step
    i = int(unif(board.run_key, "agent", t) * board.N)
    shown = [displayed(state, i, j) for j in board.adj[i]]
    layout = layout_for(board.run_key, "upd", t, len(board.adj[i]))
    msgs, r = _call(board, kernel, i, state.votes[i], shown, layout, "vote", live=board.live)
    lA = content_logit_A(layout, r["logp_A"], r["logp_B"])
    u = unif(board.run_key, "draw", t)
    v = "A" if u < sigmoid(lA / board.T) else "B"
    rec = {"kind": "update", "step": t, "agent": i, "own_before": state.votes[i], "shown": shown if board.live else None,
           "prompt_sha": sha(msgs), "layout": layout, "logp_A": r["logp_A"], "logp_B": r["logp_B"], "u": u, "vote": v}
    state.votes[i] = v
    state.step = t + 1
    state.overrides = {k: o for k, o in state.overrides.items() if state.step < o[1]}   # restore expired displays
    return rec


def probe(board: Board, state: State, kernel, agent: int, question_key: str, probe_id: str) -> dict:
    """A forked, non-returning branch: the agent's current context with the question replaced. Never writes state."""
    before = state.digest()
    shown = [displayed(state, agent, j) for j in board.adj[agent]]
    layout = layout_for(board.run_key, f"probe:{probe_id}", 0, len(board.adj[agent]))
    msgs, r = _call(board, kernel, agent, state.votes[agent], shown, layout, question_key, live=board.live)
    if state.digest() != before:
        raise AssertionError("probe changed the state")
    return {"kind": "probe", "probe_id": probe_id, "step": state.step, "agent": agent, "question": question_key,
            "prompt_sha": sha(msgs), "layout": layout, "logp_A": r["logp_A"], "logp_B": r["logp_B"]}


def apply_pulse(board: Board, state: State, recipients, k: int, toward: str, duration: int, pulse_id: str) -> dict:
    """Display pulse: for each recipient, k of its contacts (chosen by key) are SHOWN to it as voting `toward` for
    `duration` steps, then restored. Real votes and evidence are unchanged."""
    votes_before = list(state.votes)
    altered = {}
    for r in recipients:
        chosen = [board.adj[r][c] for c in perm(len(board.adj[r]), board.run_key, "pulse", pulse_id, r)[:k]]
        for j in chosen:
            state.overrides[f"{r},{j}"] = [toward, state.step + duration]
        altered[str(r)] = chosen
    if state.votes != votes_before:
        raise AssertionError("pulse changed real votes")
    return {"kind": "pulse", "pulse_id": pulse_id, "step": state.step, "toward": toward, "k": k, "duration": duration,
            "altered": altered}


def branch(state: State) -> State:
    """A branch starts from a full copy of the saved state; it shares the main trajectory's keys from that step."""
    return copy.deepcopy(state)
