"""Print the exact text of the given wordings for the coordination record's PROTOCOL_SPEC.md (D20, item 5).

  python gates/S3/lock_wordings.py w3 [w4 ...]  -> markdown on stdout
Each wording: the live board with placeholders, the blind line, the uninformed form of the report line, the four
questions, and the sha256 of the wording's definition (labels + questions, canonical JSON) as stpt/prompts.py has it.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from stpt import prompts as P  # noqa: E402

story = {"question": "{{QUESTION with the options in listed order}}", "options": {"A": "{OPTION listed first}", "B": "{OPTION listed second}"}}
layout = {"letter_of_content": {"A": "A", "B": "B"}, "listed_first_letter": "A", "contact_order": [0, 1, 2, 3]}
for w in sys.argv[1:]:
    t, q = P.TEMPLATES[w], P.QUESTIONS[w]
    h = hashlib.sha256(json.dumps({"labels": t, "questions": q}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    live = P.render(w, story, "{REPORT TEXT}", "A", ["A", "B", "A", "A"], layout, "vote")[0]["content"]
    live = live.replace(t["own"] + "A", t["own"] + "{OWN VOTE LETTER}").replace(t["contacts"].format(n=4) + "A, B, A, A",
                                                                             t["contacts"].format(n=4) + "{L1}, {L2}, {L3}, {L4}")
    live = live.replace("\nA: {OPTION", "\n{FIRST LETTER}: {OPTION").replace("\nB: {OPTION", "\n{SECOND LETTER}: {OPTION")
    print(f"### {w.upper()}  (definition sha256 `{h}`)\n")
    print("Live board, informed agent (the letter listed first, the letter mapping, the votes and the contact order are filled per call):\n\n```text\n" + live + "\n```\n")
    print(f"- Blind board: the contacts line is replaced by `{t['blind']}`")
    print(f"- Uninformed agent: the report line is `{t['report']}` followed by the scenario's no-report sentence, unquoted.")
    for k in ("vote", "own_evidence", "own_vote", "contact_majority"):
        print(f"- {k}: `{q[k]}`")
    print()
