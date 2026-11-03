"""Story lint for the StPT banks (coordination D29). CPU only; no model is called.

  python gates/S2/lint_stories.py  -> gates/S2/results/story_lint.json; exits non-zero on any problem
Checks per story: L1 question has one {A}, one {B}, ends with "?" and names no option outside the placeholders;
L2 two distinct options, neither contains the other, no bare letter A or B, length ratio <= 2.5, no evaluative word;
L3 source starts with the right article ("a"/"an"); L4 report has {source}, {freq} and {option} once each and ends with
"."; L5 the no-report sentence starts "You have no report about" and ends with "."; L6 every (option, accuracy) report
renders with no leftover braces and a capital first letter; L7 development and confirmatory keys and options disjoint;
L8 every W3-family wording passes stpt.prompts.lint_same_content for the story (live and blind, informed and not).
"""
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gates/S2"))
from stpt import evidence as E, prompts as P  # noqa: E402
import make_banks as M  # noqa: E402

EVAL = re.compile(r"\b(correct|true|wrong|false|best|safe bet)\b", re.I)   # "right" omitted: a direction in options ("the right drawer")


def lint(key, st):
    pr = []
    q = st["question"]
    if q.count("{A}") != 1 or q.count("{B}") != 1 or not q.endswith("?"):
        pr.append("L1 question placeholders/ending")
    if any(o.lower() in q.replace("{A}", "").replace("{B}", "").lower() for o in st["options"].values()):
        pr.append("L1 question names an option")
    a, b = st["options"]["A"], st["options"]["B"]
    if a == b or a in b or b in a:
        pr.append("L2 options not distinct")
    if any(re.search(r"\b[AB]\b", o) for o in (a, b)):
        pr.append("L2 bare letter in an option")
    if max(len(a), len(b)) / min(len(a), len(b)) > 2.5:
        pr.append("L2 option length ratio")
    if any(EVAL.search(o) for o in (a, b)):
        pr.append("L2 evaluative word in an option")
    src = st["source"]
    art, rest = src.split(" ", 1)
    if art not in ("a", "an") or (art == "an") != (rest[0].lower() in "aeiou"):
        pr.append("L3 article")
    r = st["report"]
    if any(r.count(f) != 1 for f in ("{source}", "{freq}", "{option}")) or not r.endswith("."):
        pr.append("L4 report template")
    if not (st["uninformed"].startswith("You have no report about") and st["uninformed"].endswith(".")):
        pr.append("L5 no-report sentence")
    for fav in "AB":
        for acc in (Fraction(3, 5), Fraction(3, 4), Fraction(9, 10)):
            t = E.render(E.Item("x", fav, acc, src), st)
            if "{" in t or "}" in t or not t[0].isupper():
                pr.append(f"L6 render {fav} {acc}")
    lay = {"letter_of_content": {"A": "B", "B": "A"}, "listed_first_letter": "A", "contact_order": [2, 0, 3, 1]}
    txt = E.render(E.Item("x", "A", Fraction(3, 4), src), st)
    for live in (True, False):
        for informed, priv in ((True, txt), (False, st["uninformed"])):
            if P.lint_same_content(st, priv, "B", ["A", "B", "B", "A"], lay, live, informed):
                pr.append(f"L8 W3-family lint (live={live}, informed={informed})")
    return pr


def main():
    res = {"dev": {k: lint(k, v) for k, v in M.DEV_STORIES.items()}, "conf": {k: lint(k, v) for k, v in M.CONF_STORIES.items()}}
    dev_opts = {o for v in M.DEV_STORIES.values() for o in v["options"].values()}
    conf_opts = {o for v in M.CONF_STORIES.values() for o in v["options"].values()}
    res["L7_keys_disjoint"] = not (set(M.DEV_STORIES) & set(M.CONF_STORIES))
    res["L7_options_disjoint"] = sorted(dev_opts & conf_opts)
    res["n"] = {"dev": len(M.DEV_STORIES), "conf": len(M.CONF_STORIES)}
    bad = {f"{b}/{k}": v for b in ("dev", "conf") for k, v in res[b].items() if v}
    res["pass"] = not bad and res["L7_keys_disjoint"] and not res["L7_options_disjoint"] and res["n"]["conf"] >= 24
    (ROOT / "gates/S2/results/story_lint.json").write_text(json.dumps(res, indent=1) + "\n")
    print("stories: dev", res["n"]["dev"], "conf", res["n"]["conf"], "| problems:", bad or "none", "| options shared dev/conf:",
          res["L7_options_disjoint"] or "none", "| pass", res["pass"])
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
