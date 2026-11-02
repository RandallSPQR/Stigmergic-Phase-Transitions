"""StPT board prompt (draft, tested at gate S3) and the branched comprehension questions.

One call shows an agent: the question with its two options as letters, its private information (one report, or none),
its own current vote, and the displayed votes of its contacts (live board) or a line saying it sees no one (blind
board). Randomised per call and recorded: the letter mapping (which content is A), the option order (which letter is
listed first), and the contact order. No system message (Gemma-2's own template refuses one; the pipeline folds it, but
StPT keeps every model's prompt identical in structure). Votes are contents internally; letters exist only in text.

A comprehension question is a BRANCH: the same context with the final vote question replaced. Branches never return
to a trajectory (the agents are memoryless, so the branch is fully described by its prompt).
"""
from __future__ import annotations

import numpy as np

VOTE_Q = "Which option do you vote for now? Answer with a single letter: A or B."
COMPREHENSION = {
    "own_evidence": "Question about your private information: which option does your report say? Answer with a single letter: A or B.",
    "own_vote": "Question about your own vote: which option is your current vote? Answer with a single letter: A or B.",
    "contact_majority": "Question about the people you are connected to: which option do more of them currently vote for? Answer with a single letter: A or B.",
}


def draw_layout(rng: np.random.Generator, n_contacts: int):
    """Per-call randomisation: letter mapping (content key -> letter), option order, contact order."""
    a_is_A = bool(rng.random() < 0.5)
    letter = {"A": "A", "B": "B"} if a_is_A else {"A": "B", "B": "A"}
    first = "A" if rng.random() < 0.5 else "B"            # which LETTER is listed first
    order = rng.permutation(n_contacts).tolist()
    return {"letter_of_content": letter, "listed_first_letter": first, "contact_order": order}


def render_board(story: dict, private_text: str, own_vote: str, contact_votes, layout: dict, final_question: str = VOTE_Q,
                 live: bool = True):
    """story: scenario story (question with {A}/{B} placeholders, options); own_vote, contact_votes: content keys
    ('A'/'B' of the scenario); layout from draw_layout. Returns the chat messages (one user turn)."""
    L = layout["letter_of_content"]
    content_of_letter = {v: k for k, v in L.items()}
    first = layout["listed_first_letter"]
    second = "B" if first == "A" else "A"
    q = story["question"].format(A=story["options"][content_of_letter[first]], B=story["options"][content_of_letter[second]])
    lines = [
        "You are one of 100 people answering the same question. Each person has their own private information, "
        "and each person can see the current votes of a few of the others.",
        "",
        f"Question: {q}",
        "",
        "The two options are:",
        f"{first}: {story['options'][content_of_letter[first]]}",
        f"{second}: {story['options'][content_of_letter[second]]}",
        "",
        f"Your private information: {private_text}",
        f"Your current vote: {L[own_vote]}",
    ]
    if live:
        shown = [L[contact_votes[i]] for i in layout["contact_order"]]
        lines.append(f"Current votes of the {len(shown)} people you are connected to: {', '.join(shown)}")
    else:
        lines.append("You cannot see anyone else's vote.")
    lines += ["", final_question]
    return [{"role": "user", "content": "\n".join(lines)}]


# ---- Wordings (S3 round 2, 2026-11-01). W1 = render_board above, unchanged. W2 and W3 carry the same content (question,
# options, report text, own vote, contacts) with different framing; the brief treats wordings as a random factor, and a
# wording is used only if every model passes S3 with it (gates/S3/ROUND2_PLAN.md).
STRICT = "Reply with exactly one letter, A or B, and nothing else."
QUESTIONS = {
    "w1": {"vote": VOTE_Q, **COMPREHENSION},
    "w2": {"vote": f"Which option do you vote for now? {STRICT}",
           "own_evidence": f"Question about your private report: which option does your private report say? {STRICT}",
           "own_vote": f"Question about your own vote: which option is your current vote? {STRICT}",
           "contact_majority": f"Question about the people you are connected to: which option do more of them currently vote for? {STRICT}"},
    "w3": {"vote": f"Which option do you vote for now? {STRICT}",
           "own_evidence": f"Question about your private report: which option does your private report say? {STRICT}",
           "own_vote": f"Question about your own vote: which option is your current vote? {STRICT}",
           "contact_majority": f"Question about the people you are connected to: which option do more of them currently vote for? {STRICT}"},
}


def _letters(story, layout):
    L = layout["letter_of_content"]
    c_of = {v: k for k, v in L.items()}
    first = layout["listed_first_letter"]
    second = "B" if first == "A" else "A"
    q = story["question"].format(A=story["options"][c_of[first]], B=story["options"][c_of[second]])
    return L, c_of, first, second, q


def render_w2(story, private_text, own_vote, contact_votes, layout, final_question, live=True, informed=True):
    """W2, structured: labelled sections; the board (own vote, contacts) first; the private report LAST, quoted and set
    apart, so it sits next to the question."""
    L, c_of, first, second, q = _letters(story, layout)
    lines = ["You are one of 100 people answering the same question. Each person has their own private report (or none) "
             "and can see the current votes of a few of the others.", "",
             f"Question: {q}", "Options:", f"{first}: {story['options'][c_of[first]]}", f"{second}: {story['options'][c_of[second]]}", "",
             "On the board:", f"- Your current vote: {L[own_vote]}"]
    if live:
        lines.append(f"- Current votes of the {len(contact_votes)} people you are connected to: "
                     + ", ".join(L[contact_votes[i]] for i in layout["contact_order"]))
    else:
        lines.append("- You cannot see anyone else's vote.")
    lines += ["", "Your private report (only you have it):", f"\"{private_text}\"" if informed else private_text, "", final_question]
    return [{"role": "user", "content": "\n".join(lines)}]


def render_w3(story, private_text, own_vote, contact_votes, layout, final_question, live=True, informed=True):
    """W3, minimal change from W1: the same order, with the report labelled as a private report and quoted, and the
    votes labelled as votes."""
    L, c_of, first, second, q = _letters(story, layout)
    lines = ["You are one of 100 people answering the same question. Each person has their own private report (or none) "
             "and can see the current votes of a few of the others.", "",
             f"Question: {q}", "", "The two options are:", f"{first}: {story['options'][c_of[first]]}",
             f"{second}: {story['options'][c_of[second]]}", "",
             "Your private report: " + (f"\"{private_text}\"" if informed else private_text),
             f"Your current vote: {L[own_vote]}"]
    if live:
        lines.append(f"Votes currently shown by the {len(contact_votes)} people you are connected to: "
                     + ", ".join(L[contact_votes[i]] for i in layout["contact_order"]))
    else:
        lines.append("You cannot see anyone else's vote.")
    lines += ["", final_question]
    return [{"role": "user", "content": "\n".join(lines)}]


# ---- W3 variants (held-out wording check, 2026-11-02; gates/S3/HELDOUT_PLAN.md). Same structure as W3: the same order
# (intro, question, options, private report labelled and quoted in place, own vote, contacts or the blind line, question)
# and a strict one-letter instruction; different phrasing and label text. TEMPLATES["w3"] reproduces render_w3 byte for
# byte (tests/test_prompts.py), so every member of the family is rendered by one function.
TEMPLATES = {
    "w3": {"intro": "You are one of 100 people answering the same question. Each person has their own private report (or none) "
                    "and can see the current votes of a few of the others.",
           "question": "Question: ", "options": "The two options are:", "report": "Your private report: ",
           "own": "Your current vote: ", "contacts": "Votes currently shown by the {n} people you are connected to: ",
           "blind": "You cannot see anyone else's vote."},
    "w4": {"intro": "This is a group decision among 100 people who all answer the same question. Each of them may hold a private "
                    "report of their own (some hold none), and each can see how a few of the others are voting at the moment.",
           "question": "The question: ", "options": "Options:", "report": "Private report you hold: ",
           "own": "Your vote at the moment: ", "contacts": "Your {n} connections' votes at the moment: ",
           "blind": "No one else's vote is visible to you."},
    "w5": {"intro": "You are taking part in a vote among 100 people on one question. Some people were given a private report that "
                    "only they can see, and everyone can see the votes of the few people they are linked to.",
           "question": "Question to decide: ", "options": "Choices:", "report": "The report you received privately: ",
           "own": "How you are voting right now: ", "contacts": "How the {n} people linked to you are voting right now: ",
           "blind": "You cannot see how anyone else is voting."},
    "w6": {"intro": "100 people are each answering the same question. Each has a private report or none, and each can see the "
                    "latest votes of the few people they are connected to.",
           "question": "The question is: ", "options": "Answer options:", "report": "Your own report (no one else sees it): ",
           "own": "Your own vote so far: ", "contacts": "Latest votes of your {n} contacts: ",
           "blind": "You see no one else's vote."},
}
STRICT4 = "Answer with one letter only, A or B, and no other text."
STRICT5 = "Respond with a single letter, A or B, and nothing more."
STRICT6 = "Give exactly one letter, A or B, with nothing else."
QUESTIONS["w4"] = {"vote": f"Which option is your vote now? {STRICT4}",
                   "own_evidence": f"Question about the private report you hold: which option does that report say? {STRICT4}",
                   "own_vote": f"Question about your vote at the moment: which option is it? {STRICT4}",
                   "contact_majority": f"Question about your connections: which option are more of them voting for at the moment? {STRICT4}"}
QUESTIONS["w5"] = {"vote": f"Which choice do you vote for now? {STRICT5}",
                   "own_evidence": f"Question about the report you received privately: which choice does that report support? {STRICT5}",
                   "own_vote": f"Question about how you are voting right now: which choice is your vote? {STRICT5}",
                   "contact_majority": f"Question about the people linked to you: which choice are more of them voting for right now? {STRICT5}"}
QUESTIONS["w6"] = {"vote": f"What is your vote now? {STRICT6}",
                   "own_evidence": f"Question about your own report: which option does it say? {STRICT6}",
                   "own_vote": f"Question about your own vote so far: which option is it? {STRICT6}",
                   "contact_majority": f"Question about your contacts: which option do more of them vote for? {STRICT6}"}
FAMILY = ("w3", "w4", "w5", "w6")


def render_family(wording, story, private_text, own_vote, contact_votes, layout, final_question, live=True, informed=True):
    """W3 and its variants: one structure, the wording's own labels."""
    t = TEMPLATES[wording]
    L, c_of, first, second, q = _letters(story, layout)
    lines = [t["intro"], "", t["question"] + q, "", t["options"], f"{first}: {story['options'][c_of[first]]}",
             f"{second}: {story['options'][c_of[second]]}", "",
             t["report"] + (f"\"{private_text}\"" if informed else private_text), t["own"] + L[own_vote]]
    if live:
        lines.append(t["contacts"].format(n=len(contact_votes)) + ", ".join(L[contact_votes[i]] for i in layout["contact_order"]))
    else:
        lines.append(t["blind"])
    lines += ["", final_question]
    return [{"role": "user", "content": "\n".join(lines)}]


def lint_same_content(story, private_text, own_vote, contact_votes, layout, live=True, informed=True, wordings=FAMILY):
    """Linted wordings carry the same content in the same order: the question with its options in the listed order, the
    two options (listed order), the report text verbatim (quoted if informed), the own-vote letter, the contact letters
    in contact order (or the blind line), the final question. Returns a list of problems (empty = same content)."""
    problems = []
    L, c_of, first, second, q = _letters(story, layout)
    for w in wordings:
        t = TEMPLATES[w]
        text = render_family(w, story, private_text, own_vote, contact_votes, layout, QUESTIONS[w]["vote"], live, informed)[0]["content"]
        rows = text.split("\n")
        need = [t["question"] + q, f"{first}: {story['options'][c_of[first]]}", f"{second}: {story['options'][c_of[second]]}",
                t["report"] + (f"\"{private_text}\"" if informed else private_text), t["own"] + L[own_vote],
                (t["contacts"].format(n=len(contact_votes)) + ", ".join(L[contact_votes[i]] for i in layout["contact_order"]))
                if live else t["blind"], QUESTIONS[w]["vote"]]
        idx = [rows.index(r) if r in rows else -1 for r in need]
        if -1 in idx or idx != sorted(idx):
            problems.append(f"{w}: content missing or out of order {idx}")
        if len(rows) != 13 or text.count("\"") != (2 if informed else 0) + story["question"].count("\""):
            problems.append(f"{w}: structure differs ({len(rows)} lines)")
        for qk, qq in QUESTIONS[w].items():
            if not qq.endswith(("A or B, and nothing else.", "A or B, and no other text.", "A or B, and nothing more.",
                                "A or B, with nothing else.")):
                problems.append(f"{w}/{qk}: no strict one-letter instruction")
    return problems


def render(wording, story, private_text, own_vote, contact_votes, layout, question_key, live=True, informed=True):
    q = QUESTIONS[wording][question_key]
    if wording == "w1":
        return render_board(story, private_text, own_vote, contact_votes, layout, q, live)
    if wording == "w2":
        return render_w2(story, private_text, own_vote, contact_votes, layout, q, live, informed)
    if wording == "w3":
        return render_w3(story, private_text, own_vote, contact_votes, layout, q, live, informed)
    return render_family(wording, story, private_text, own_vote, contact_votes, layout, q, live, informed)


def build_round2(contexts, d=4):
    """S3 round-2 prompt records from compact contexts (one per round-1 prompt: story, private text, informed flag,
    own vote, contact pattern, layout and identifiers). Used identically by gates/S3/make_prompts_round2.py and on the
    pod, whose rendering must reproduce the committed sha256."""
    out = []
    for c in contexts:
        contacts = ["A"] * c["contacts_A"] + ["B"] * (d - c["contacts_A"])
        base = {k: c[k] for k in ("scenario_id", "allocation_sha256", "position", "layout", "own_vote", "contacts_A", "report_accuracy")}
        for w in ("w2", "w3"):
            out.append({**base, "qtype": c["qtype"], "correct_letter": c["correct_letter"], "prompt_id": f"{w}-{c['prompt_id']}",
                        "wording": w, "round1_prompt_id": c["prompt_id"],
                        "messages": render(w, c["story"], c["private"], c["own_vote"], contacts, c["layout"], c["qtype"], informed=c["informed"])})
        if c["qtype"] == "own_vote":
            for w in ("w1", "w2", "w3"):
                out.append({**base, "qtype": "vote", "correct_letter": None, "prompt_id": f"{w}-vote-{c['prompt_id']}", "wording": w,
                            "round1_prompt_id": c["prompt_id"], "informed": c["informed"],
                            "messages": render(w, c["story"], c["private"], c["own_vote"], contacts, c["layout"], "vote", informed=c["informed"])})
    return out


def build_heldout(contexts, d=4):
    """S3 held-out prompt records (gates/S3/HELDOUT_PLAN.md) from compact contexts: every context in W3, W4, W5 and W6
    with its comprehension question, and each own-vote context also with the actual vote question (measured, not
    scored). Used identically by gates/S3/make_prompts_heldout.py and on the pod (the sha256 must match)."""
    out = []
    for c in contexts:
        contacts = ["A"] * c["contacts_A"] + ["B"] * (d - c["contacts_A"])
        base = {k: c[k] for k in ("scenario_id", "allocation_sha256", "position", "layout", "own_vote", "contacts_A", "report_accuracy")}
        for w in FAMILY:
            out.append({**base, "qtype": c["qtype"], "correct_letter": c["correct_letter"], "prompt_id": f"{w}-{c['prompt_id']}",
                        "wording": w, "context_id": c["prompt_id"],
                        "messages": render(w, c["story"], c["private"], c["own_vote"], contacts, c["layout"], c["qtype"], informed=c["informed"])})
            if c["qtype"] == "own_vote":
                out.append({**base, "qtype": "vote", "correct_letter": None, "prompt_id": f"{w}-vote-{c['prompt_id']}", "wording": w,
                            "context_id": c["prompt_id"], "informed": c["informed"],
                            "messages": render(w, c["story"], c["private"], c["own_vote"], contacts, c["layout"], "vote", informed=c["informed"])})
    return out


def build_s4(contexts, wordings, d=4):
    """S4 noise probes (gates/S4/S4_PLAN.md) from compact contexts: each context x each of its four layouts (letter
    mapping x option order, both balanced) with the actual vote question, live or blind as the context says, in every
    wording of the study's set. The order is the contexts' order, the same in every server start."""
    out = []
    for w in wordings:
        for c in contexts:
            contacts = ["A"] * c["contacts_A"] + ["B"] * (d - c["contacts_A"])
            for j, lay in enumerate(c["layouts"]):
                out.append({"prompt_id": f"{w}-{c['context_id']}-L{j}", "context_id": c["context_id"], "wording": w, "layout_index": j,
                            "layout": lay, "live": c["live"], "informed": c["informed"], "own_vote": c["own_vote"],
                            "contacts_A": c["contacts_A"], "report_accuracy": c["report_accuracy"], "report_favours": c["report_favours"],
                            "scenario_id": c["scenario_id"], "allocation_sha256": c["allocation_sha256"], "position": c["position"],
                            "messages": render(w, c["story"], c["private"], c["own_vote"], contacts, lay, "vote", live=c["live"],
                                               informed=c["informed"])})
    return out
