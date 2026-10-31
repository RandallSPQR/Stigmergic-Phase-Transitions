"""Stage 1 battery: configurations, prompt templates, request bodies (PREREG §3).

Spin coding: s = +1 for content P, −1 for content Q.
  neutral:   P = position A (letters are the content; mapping fixed)
  political: P = support the measure,  Q = oppose the measure
  workplace: P = adopt the new tool,   Q = keep the current tool
Neighbour types: aP, aQ (ally holding P/Q), rP, rQ (rival holding P/Q).
"""
import hashlib, itertools, random

TYPES = ("aP", "aQ", "rP", "rQ")

FRAMINGS = {
    "neutral": {
        "intro": ("You are one member of a group. Every member holds one of two positions, {X} or {Y}, and can "
                  "switch at any time. Some members are your allies (people you usually side with) and some are "
                  "your rivals (people you usually oppose)."),
        "content": None,
    },
    "political": {
        "intro": ("You are a voter in a mid-sized town. The town will vote on a ballot measure to raise the local "
                  "sales tax by half a percent to fund public transit. Every voter holds one of two positions, "
                  "{X} ({cX}) or {Y} ({cY}), and can switch at any time before the vote. Some voters are your "
                  "political allies (people who usually vote the way you do) and some are your political rivals "
                  "(people who usually vote against your side)."),
        "content": {"P": "support the measure", "Q": "oppose the measure"},
    },
    "workplace": {
        "intro": ("You work on a team that is deciding whether to switch to a new project-management tool. Every "
                  "team member holds one of two positions, {X} ({cX}) or {Y} ({cY}), and can switch at any time "
                  "before the decision. Some colleagues are your allies (people you usually back at work) and "
                  "some are your rivals (people you usually clash with at work)."),
        "content": {"P": "adopt the new tool", "Q": "keep the current tool"},
    },
}

ARMS = {  # arm: (framing, own position shown, mappings, orders)
    "neutral_own":   ("neutral", True, (0,), (0, 1)),
    "neutral_noown": ("neutral", False, (0,), (0, 1)),
    "political":     ("political", True, (0, 1), (0, 1)),
    "workplace":     ("workplace", True, (0, 1), (0, 1)),
    "neutral_own_w2": ("neutral", True, (0,), (0, 1)),      # wording-robustness arm (Amendment 3)
}
ARM_INSTRUCTION = {"neutral_own_w2": 3}


def multisets(kmax=6):
    """All neighbour multisets as count tuples (n_aP, n_aQ, n_rP, n_rQ), k = 1..kmax (209 for kmax=6)."""
    out = []
    for k in range(1, kmax + 1):
        for combo in itertools.combinations_with_replacement(range(4), k):
            out.append(tuple(combo.count(t) for t in range(4)))
    return out


def cells(own=True, kmax=6):
    ms = multisets(kmax)
    return [(m, s0) for m in ms for s0 in ((+1, -1) if own else (0,))]


def _h(*parts):
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def neighbour_order(counts, ident, perm):
    """Deterministic random order of the individual neighbours, seeded by prompt identity + permutation index."""
    seq = [t for t, n in zip(TYPES, counts) for _ in range(n)]
    random.Random(int(_h(ident, perm)[:16], 16)).shuffle(seq)
    return seq


def letters(mapping):
    """mapping 0: P→A, Q→B; mapping 1: P→B, Q→A."""
    return ({"P": "A", "Q": "B"} if mapping == 0 else {"P": "B", "Q": "A"})


# v1 (pilot 1) leaked 24-94% of first-token mass into explanations, rising with k (PREREG Amendment 2).
INSTRUCTION = {
    1: "Which position do you take now? Answer with a single letter: {X} or {Y}.",
    2: "Which position do you take now? Reply with exactly one letter, {X} or {Y}, and nothing else.",
    3: "Having considered your contacts, which position do you choose? Reply with exactly one letter, {X} or {Y}, and nothing else.",
}
# Comprehension battery (Amendment 3a): factual reading questions on the same scenario, not conformity-based.
COMPREHENSION = {
    "own": "Which position do you currently hold? Reply with exactly one letter, {X} or {Y}, and nothing else.",
    "ally_majority": "Which position do most of your allies currently hold? Reply with exactly one letter, {X} or {Y}, and nothing else.",
    "rival_majority": "Which position do most of your rivals currently hold? Reply with exactly one letter, {X} or {Y}, and nothing else.",
}
INSTRUCTION_VERSION = 2


def render(framing, counts, s0, mapping, order, perm, instruction=None, question=None, seq=None):
    """Return (prompt text, neighbour sequence). order 0: A listed first; 1: B listed first.
    seq: explicit neighbour order (Stage 3 live calls draw it fresh per call); default = Stage 1 seeded order."""
    instruction = instruction or INSTRUCTION_VERSION
    F = FRAMINGS[framing]
    let = letters(mapping)
    X, Y = ("A", "B") if order == 0 else ("B", "A")
    inv = {v: k for k, v in let.items()}            # letter -> content key
    def gloss(ckey):
        return "" if F["content"] is None else f" ({F['content'][ckey]})"
    intro = F["intro"].format(X=X, Y=Y, cX=(F["content"] or {}).get(inv[X], ""), cY=(F["content"] or {}).get(inv[Y], ""))
    ident = (framing, counts, s0, mapping, order)
    if seq is None:
        seq = neighbour_order(counts, ident, perm)
    assert sorted(seq) == sorted(t for t, n in zip(TYPES, counts) for _ in range(n)), "seq must match counts"
    lines = []
    for t in seq:
        who = "An ally" if t[0] == "a" else "A rival"
        lines.append(f"- {who} holds {let[t[1]]}{gloss(t[1])}.")
    parts = [intro, ""]
    if s0 != 0:
        own = "P" if s0 > 0 else "Q"
        parts += [f"You currently hold position {let[own]}{gloss(own)}.", ""]
    parts += ["The people you are in contact with, and the position each currently holds:", *lines, "",
              (question or INSTRUCTION[instruction]).format(X=X, Y=Y)]
    return "\n".join(parts), seq


def items(arm, cell_filter=None, extra_perms=False, instruction=None):
    """Yield one dict per prompt in an arm. extra_perms: the order-sensitivity subset (PREREG §3)."""
    framing, own, maps, orders = ARMS[arm]
    instruction = instruction or ARM_INSTRUCTION.get(arm)
    for counts, s0 in cells(own):
        if cell_filter is not None and not cell_filter(counts, s0):
            continue
        variants = [(m, o) for m in maps for o in orders]
        if extra_perms:
            if sum(counts) < 3:
                continue
            m, o = variants[int(_h("opick", arm, counts, s0)[:8], 16) % len(variants)]
            perms, variants = (1, 2), [(m, o)]
        else:
            perms = (0,)
        for m, o in variants:
            for perm in perms:
                text, seq = render(framing, counts, s0, m, o, perm, instruction)
                yield {"arm": arm, "framing": framing, "counts": counts, "s0": s0, "mapping": m, "order": o,
                       "perm": perm, "seq": "".join(t[0] + t[1] for t in seq), "prompt": text}


def comprehension_items():
    """Neutral framing, own position shown, both letter orders, k = 1..6. Majority questions only where the
    majority is strict (ties excluded). Correct answer is a letter (mapping 0: P = A)."""
    for counts, s0 in cells(True):
        Ma, Mr = counts[0] - counts[1], counts[2] - counts[3]
        qs = [("own", "A" if s0 > 0 else "B")]
        if Ma != 0:
            qs.append(("ally_majority", "A" if Ma > 0 else "B"))
        if Mr != 0:
            qs.append(("rival_majority", "A" if Mr > 0 else "B"))
        for qname, correct in qs:
            for o in (0, 1):
                text, seq = render("neutral", counts, s0, 0, o, 0, question=COMPREHENSION[qname])
                yield {"arm": "comprehension", "question": qname, "framing": "neutral", "counts": counts, "s0": s0,
                       "mapping": 0, "order": o, "perm": 0, "seq": "".join(t[0] + t[1] for t in seq),
                       "correct": correct, "prompt": text}


def body(model, tag, prompt, mode="lp", reasoning_off=False, temperature=1.0):
    b = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature,
         "provider": {"order": [tag], "allow_fallbacks": False}}
    if mode == "lp":
        b.update({"max_tokens": 1, "logprobs": True, "top_logprobs": 5})
        b["provider"]["require_parameters"] = True
    else:
        b["max_tokens"] = 8
    if reasoning_off:
        b["reasoning"] = {"enabled": False}
    return b


if __name__ == "__main__":
    import sys
    print(len(multisets()), "multisets;", {a: sum(1 for _ in items(a)) for a in ARMS},
          "order subset:", sum(1 for _ in items("neutral_own", extra_perms=True)))
    for arm in ARMS:
        it = list(items(arm))
        print("=" * 30, arm); print(it[len(it) // 2 + (3 if arm == "political" else 0)]["prompt"])
