# Handoff: two repositories this session could not push

Git bundles keep every commit and tag hash exactly, so the pins in `pins.yaml` stay valid once these are pushed.

## 1. Pipeline release v1.2.0 → RandallSPQR/SAE-Ethos-Calibration

`sae-ethos-pipeline_v1.2.0.bundle` holds:
- branch `release/v1.2.0` = `5ca15f56a71f35d5818d0392f7f3b4acb2d85d1b`;
- annotated tag `v1.2.0` = `aedd002b6a2050547011aef210562e15ef588b51`.

Its prerequisite is v1.1.0 (`94a785c15ec8`), which is `main` today. From a clone of SAE-Ethos-Calibration:

```bash
git fetch /path/to/sae-ethos-pipeline_v1.2.0.bundle release/v1.2.0:release/v1.2.0 'refs/tags/v1.2.0:refs/tags/v1.2.0'
```

```bash
git push origin release/v1.2.0 v1.2.0
```

Merging `release/v1.2.0` into `main` is a fast-forward; whether to do it is your call. The tag is the lock either way.

## 2. Coordination record → RandallSPQR/StPT-MP-Coordination (create it empty first)

`stpt-mp-coordination.bundle` holds `main` = `93a9ee77429df76840999aab86daac5cc36734a6`.

```bash
git clone stpt-mp-coordination.bundle StPT-MP-Coordination
```

```bash
cd StPT-MP-Coordination && git remote set-url origin https://github.com/RandallSPQR/StPT-MP-Coordination && git push -u origin main
```

Alternatively, attach both repositories to a Claude session with push access and ask for the push.
