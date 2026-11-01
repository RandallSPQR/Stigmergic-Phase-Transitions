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


def test_model_manifest_requires_server_start():
    import pytest
    with pytest.raises(ValueError):
        manifest.header("qwen3.5-9b")                    # no server-start ID: refused before anything else
    ss = manifest.server_start_id("podx", 2, "2026-11-01T05:16:00Z")
    assert ss["id"] == "podx/start2/2026-11-01T05:16:00Z"
    h = manifest.header(None, server_start=ss)
    assert h["server_start"]["index"] == 2
    with pytest.raises(ValueError):
        manifest.server_start_id("", 1, "t")
