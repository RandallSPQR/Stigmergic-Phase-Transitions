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
