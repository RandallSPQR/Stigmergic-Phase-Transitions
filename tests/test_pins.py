"""Pins and inheritance (CPU, no network)."""
import re

from stpt import inherit, manifest


def test_pins_are_exact():
    p = manifest.pins()
    for k in ("pipeline", "spt"):
        assert p[k]["tag"] and re.fullmatch(r"[0-9a-f]{40}", p[k]["commit"]), k
    assert p["pipeline"]["tag"] == "v1.2.0" and p["spt"]["tag"] == "v1.0.1"
    assert re.fullmatch(r"[0-9a-f]{40}", p["coordination"]["commit"])


def test_header_carries_pins():
    h = manifest.header()
    assert h["pins"]["pipeline"]["commit"] == manifest.pins()["pipeline"]["commit"]
    assert len(h["pins_sha256"]) == 64


def test_inherited_files_unchanged():
    rep = inherit.verify()
    assert rep["ok"], {f: r for f, r in rep["files"].items() if not r["ok"]}
    assert rep["source"]["commit"] == manifest.pins()["spt"]["commit"]
