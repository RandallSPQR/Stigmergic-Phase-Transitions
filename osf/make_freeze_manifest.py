"""Freeze manifest (D45 item 2a): sha256 of every design file, the coordination-record commit, and the sealed-file
hashes, written BEFORE any sealed file is opened. Refuses if the coordination record's openings table is not empty.

  python osf/make_freeze_manifest.py /home/user/stpt-mp-coordination -> osf/FREEZE_MANIFEST.json
"""
import datetime as dt
import glob
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = Path(sys.argv[1])
FILES = ["osf/PREREGISTRATION.md", "pins.yaml", "CLAUDE.md",
         # protocol and decisions (StPT side)
         "analysis/DECISION_NOISE_T.md", "analysis/INITIAL_VOTE_RULE.md", "analysis/PULSE_SETTINGS.md", "analysis/CONFIRMATORY_SET.md",
         "analysis/PROMPT_SENSITIVITY.md", "analysis/PREREGISTERED_D21.md", "analysis/SENSITIVITY_WITHOUT_QWEN9B.md",
         "analysis/SECONDARY_INFORMED_SPLIT.md", "analysis/PREREGISTRATION_ITEMS.md",
         # banks, seed rule, clusters
         "gates/S2/banks/MANIFEST.json", "gates/S2/CONFIRMATORY_SEED_RULE.md", "gates/S2/make_banks.py", "gates/S2/lint_stories.py",
         "gates/S10/draw_clusters.py", "gates/S10/clusters/MANIFEST.json", "gates/S10/clusters/confirmatory_clusters.json",
         # run code
         "stpt/board.py", "stpt/prompts.py", "stpt/evidence.py", "stpt/manifest.py", "stpt/sim.py", "gates/S8/s8_core.py", "gates/S10/s10_core.py",
         # analysis code and its validation
         "gates/S10/analysis/confirmatory.py", "gates/S10/analysis/validate_confirmatory.py", "gates/S10/analysis/reml_classical_check.py",
         "gates/S10/results/analysis_validation.json", "gates/S10/results/reml_classical_check.json",
         "gates/S10/results/analysis_validation_run1_containment_df.log", "gates/S10/results/analysis_validation_run2_satterthwaite.log",
         # power and predictions code
         "gates/S9/s9_kernels.py", "gates/S9/s9_sim.py", "gates/S9/s9_run.py", "gates/S9/power_at_61.py", "gates/S10/predictions.py",
         "gates/S9/results/s9_tiers.json", "gates/S9/results/power_at_61.json", "gates/S9/results/kernels_s8.json"]
COORD_FILES = ["PROTOCOL_SPEC.md", "DECISIONS.md", "AMENDMENTS.md", "SEALED.md", "PIPELINE.md", "DATA_SEPARATION.md",
               "schema/evidence_schema_v1.0.json"]
SEALED = {"gates/S8/sealed/s8_sealed.json.gz.b64": "e6b1bc7ac35d28591428efc8dbc9836f8b9d6ff98b2cb55fcf76fa72f16a95a8",
          "gates/S10/sealed/s10_predictions.json.gz.b64": "1a73a88d2a5efb4bb351b2078f59cb405b1719b7063518aeb17a5d13858b58c2"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    missing = [f for f in FILES if not (ROOT / f).exists()]
    if missing:
        raise SystemExit(f"missing design files: {missing}")
    for f, h in SEALED.items():
        if sha(ROOT / f) != h:
            raise SystemExit(f"sealed file {f} does not match its recorded hash")
    sealed_reg = (COORD / "SEALED.md").read_text()
    openings = sealed_reg.split("## Openings", 1)[1]
    rows = [l for l in openings.splitlines() if l.startswith("|") and not l.startswith("| date") and not l.startswith("|---")]
    if rows:
        raise SystemExit("REFUSED: a sealed file has already been opened; the freeze manifest must precede any opening")
    git = lambda *a, cwd=COORD: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True).stdout.strip()
    if git("status", "--porcelain"):
        raise SystemExit("coordination record has uncommitted changes")
    man = {"written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "statement": "All design files below were hashed in this freeze commit before any sealed file was opened (D45).",
           "stpt_parent_commit": git("rev-parse", "HEAD", cwd=ROOT),
           "coordination_record": {"repo": "RandallSPQR/StPT-MP-Coordination", "commit": git("rev-parse", "HEAD"),
                                   "files": {f: sha(COORD / f) for f in COORD_FILES}},
           "design_files": {f: sha(ROOT / f) for f in FILES},
           "sealed_files": {f: {"sha256": h, "opened_before_freeze": False} for f, h in SEALED.items()},
           "openings_table_rows_at_freeze": 0}
    (ROOT / "osf/FREEZE_MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    print("freeze manifest:", len(man["design_files"]), "design files,", len(COORD_FILES), "coordination files; coordination commit",
          man["coordination_record"]["commit"][:12], "; sealed files unopened")


if __name__ == "__main__":
    main()
