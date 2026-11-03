"""Tables for pre-registration §8 (predictions) and §9 (S8 pilot estimates), decoded directly from the sealed files.

  python osf/sealed_tables.py /home/user/stpt-mp-coordination -> markdown on stdout

Each sealed file's sha256 is checked against osf/FREEZE_MANIFEST.json and against the coordination record's register
(SEALED.md) before it is decoded; the script refuses on any mismatch. It writes nothing and logs no opening: both files
were opened, and the openings logged, on 2026-11-03 06:22 UTC (D45), after the freeze commit.
"""
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = ["gemma-2-9b-it", "qwen3.5-9b", "gemma-3-27b-it", "qwen3.5-27b"]
SECONDARY = ["llama-3.1-8b-it"]
NAMES = {"gemma-2-9b-it": "Gemma-2-9B-IT", "qwen3.5-9b": "Qwen3.5-9B", "gemma-3-27b-it": "Gemma-3-27B-IT",
         "qwen3.5-27b": "Qwen3.5-27B", "llama-3.1-8b-it": "Llama-3.1-8B (secondary, D24)"}


def decode(rel, coord):
    man = json.loads((ROOT / "osf/FREEZE_MANIFEST.json").read_text())
    want = man["sealed_files"][rel]["sha256"]
    data = (ROOT / rel).read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise SystemExit(f"REFUSED: {rel} sha256 {got} != freeze manifest {want}")
    if want not in (coord / "SEALED.md").read_text():
        raise SystemExit(f"REFUSED: {want} is not in the coordination register")
    return got, json.loads(gzip.decompress(base64.b64decode(data)))


def f3(x):
    return f"{x:+.3f}"


def main():
    coord = Path(sys.argv[1])
    h, P = decode("gates/S10/sealed/s10_predictions.json.gz.b64", coord)
    print(f"<!-- decoded from gates/S10/sealed/s10_predictions.json.gz.b64, sha256 {h} (matches the freeze manifest) -->")
    print(f"Simulated studies: {P['n_simulated_studies']}. Clusters: {len(P['clusters'])}.\n")
    print("| estimand | mean | 5th pct | median | 95th pct |\n|---|---|---|---|---|")
    lab = {"board": "board effect, sweeps 25–30 (live − blind)", "persistence": "pulse persistence (ITT)"}
    for k in ("board", "persistence"):
        v = P["pooled_confirmatory"][k]
        print(f"| **pooled, four confirmatory models:** {lab[k]} | {f3(v['mean'])} | {f3(v['p05'])} | {f3(v['p50'])} | {f3(v['p95'])} |")
    for m in CONF + SECONDARY:
        for k in ("board", "persistence"):
            v = P["per_model"][m][k]
            print(f"| {NAMES[m]}: {lab[k]} | {f3(v['mean'])} | {f3(v['p05'])} | {f3(v['p50'])} | {f3(v['p95'])} |")
    print()
    h, S = decode("gates/S8/sealed/s8_sealed.json.gz.b64", coord)
    print(f"<!-- decoded from gates/S8/sealed/s8_sealed.json.gz.b64, sha256 {h} (matches the freeze manifest) -->")
    cols = [("board_effect", "board effect, rule (i)"), ("board_effect_rule_ii", "board effect, rule (ii)"),
            ("persistence_itt", "persistence ITT"), ("persistence_exposed", "persistence, exposed"),
            ("persistence_social", "social part"), ("persistence_self", "self part")]
    print("| model | " + " | ".join(c[1] for c in cols) + " |\n|---|" + "---|" * len(cols))
    for m in CONF + SECONDARY:
        M = S["models"][m]
        print(f"| {NAMES[m]} | " + " | ".join(f"{f3(M[k]['all'])} (n {M[k]['n']})" for k, _ in cols) + " |")
    Q = S["pooled_confirmatory_mean_of_model_means"]
    print("| **mean of the four confirmatory models** | " + " | ".join(f3(Q[k]) for k, _ in cols) + " |")


if __name__ == "__main__":
    main()
