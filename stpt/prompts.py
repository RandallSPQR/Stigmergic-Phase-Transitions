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


def render(wording, story, private_text, own_vote, contact_votes, layout, question_key, live=True, informed=True):
    q = QUESTIONS[wording][question_key]
    if wording == "w1":
        return render_board(story, private_text, own_vote, contact_votes, layout, q, live)
    return {"w2": render_w2, "w3": render_w3}[wording](story, private_text, own_vote, contact_votes, layout, q, live, informed)
