"""Board wordings (CPU, no network): the W3 family renders W3 byte for byte, and every variant passes the
same-content lint on the S3 contexts, live and blind."""
import json
from pathlib import Path

from stpt import prompts as P

ROOT = Path(__file__).resolve().parents[1]
CTX = json.loads((ROOT / "gates" / "S3" / "prompts" / "s3_round2_contexts.json").read_text())


def _contacts(c):
    return ["A"] * c["contacts_A"] + ["B"] * (4 - c["contacts_A"])


def test_family_template_reproduces_w3():
    for c in CTX:
        for live in (True, False):
            for qk in P.QUESTIONS["w3"]:
                a = P.render_w3(c["story"], c["private"], c["own_vote"], _contacts(c), c["layout"], P.QUESTIONS["w3"][qk], live, c["informed"])
                b = P.render_family("w3", c["story"], c["private"], c["own_vote"], _contacts(c), c["layout"], P.QUESTIONS["w3"][qk], live, c["informed"])
                assert a == b


def test_variants_same_content():
    for c in CTX:
        for live in (True, False):
            assert P.lint_same_content(c["story"], c["private"], c["own_vote"], _contacts(c), c["layout"], live, c["informed"]) == []


def test_variants_differ_in_wording():
    keys = ["intro", "question", "options", "report", "own", "contacts", "blind"]
    for k in keys:
        assert len({P.TEMPLATES[w][k] for w in P.FAMILY}) == len(P.FAMILY) or k == "question", k
    for qk in P.QUESTIONS["w3"]:
        assert len({P.QUESTIONS[w][qk] for w in P.FAMILY}) == len(P.FAMILY), qk
