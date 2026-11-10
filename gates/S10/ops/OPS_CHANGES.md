# S10 operations tools: changes during and after the core collection

Operational record (coordination record A54). None of these files is a frozen design file (`osf/FREEZE_MANIFEST.json`),
none is in the run payload (`gates/S10/run/make_payload.py` lists the 12 payload files), and none is the pod script. The
watcher only reads: it sends GET requests to the RunPod API and the dataset, writes a local `status.json` for the
monitoring page, and never writes to a pod or the dataset. The launcher only sets the pod's environment; the pod script
and the payload decide what runs.

## Files

| File | Role | In the tagged run code? |
|---|---|---|
| `gates/S10/ops/watch_s10.py` | read-only watcher; feeds the monitoring page | no (ran from the session's scratch folder until now; committed here) |
| `gates/S10/ops/launch_s10_model.sh` | wraps `gates/S0/gpu/launch.py create` for one model's stage | no (same) |
| `gates/S10/run/collection_integrity.py` | integrity check after collection (no outcome computed) | no: added after `stpt-run-v1.2` (`a77ba1f`), not in the payload |

## Changes during the core collection (2026-11-07 19:36 UTC to 2026-11-09 14:01 UTC)

Reconstructed from the session's command log; times UTC.

**Watcher (`watch_s10.py`)**

1. 2026-11-07 19:36, before the first full core pod: progress counted from the records on the dataset also after a run
   ends (it had shown 61 of 61 when a run stopped early). Display only.
2. 2026-11-07 21:49: `WATCH_ONCE=1` single-pass mode, used by scheduled check-ins after the background watcher reached
   its 2-hour limit. Display only.
3. 2026-11-08 00:48: the start-up message names the model being downloaded (it said Gemma-2-9B for every model).
   Display only.

**Launcher (`launch_s10_model.sh`)**

4. 2026-11-07 ~19:48: payload hash updated to `4f137411…` when the payload was rebuilt at `8f22f97` (A44).
5. 2026-11-07 21:52: optional `STPT_ACK` passed to the pod (the owner's acknowledged 80% flags, D52, D56).
6. 2026-11-08 14:39: `STPT_COMMIT` pinned to `8f22f97` (the payload's commit) instead of the working tree's HEAD, after
   commits that did not touch run code (integrity script, registry). Before then, HEAD was `8f22f97` at every launch.

## Changes before the secondary stage (this commit; not used by any core pod)

7. Watcher: the stage to watch (`WATCH_STAGE`, core or secondary) and its scheduled (cluster, arm) runs, counting only
   that stage's arms; a `SETUP_FAILED` run shown as such; repository-relative paths, and `WATCH_DIR` for its local
   `status.json`.
8. Launcher: the stage (`STPT_STAGE`, core by default), `STPT_COMMIT` = `stpt-run-v1.2.1` (`3404b7e`), and a refusal to
   launch if the pod script or `launch.py` differ from that commit; repository-relative path.
9. Integrity check: `--stage secondary` (every scheduled (cluster, arm) of the stage, nothing else), and a report of the
   code versions, cluster manifest and pins recorded in each record. Rerun on the four core stages: all 18 earlier
   fields identical, all passed (results files updated with the new fields).

10. Launcher, after D58 (Qwen3.5-9B secondary cap +$1): the payload is rebuilt with the new caps file (sha256
    `d4e01345…`, built at `7dbfe38`); `STPT_COMMIT` = `7dbfe38`; it refuses to launch unless the pod script, `launch.py`
    and the payload's code files are identical to `stpt-run-v1.2.1` (`3404b7e`) and the caps file to `7dbfe38`.

11. Launcher, after D59 (secondary caps raised): payload rebuilt with the new caps file (sha256 `f26677a4…`, built
    at `2f7bf0e`); `STPT_COMMIT` = `2f7bf0e`; the same checks against `stpt-run-v1.2.1` and the caps file.

12. Launcher, after D60 (Qwen3.5-9B secondary cap $14.00): payload rebuilt (sha256 `5cf79ede…`, built at `6bb30eb`);
    `STPT_COMMIT` = `6bb30eb`; the same checks.

## Integrity coverage

The integrity check reads only the records, ledgers and markers on the dataset, never the watcher's or launcher's
output, so changes 1-3 and 7 cannot affect what it checks. For changes 4-6 and 8, every record carries the code that
produced it in its manifest (`stpt_commit`, `payload_sha256`, `cluster_manifest_sha256`, `pins`), and the check now
reports them:

| Core stage | Records by code version | Cluster manifests | Pin sets |
|---|---|---|---|
| Gemma-2-9B | 57 × `8f22f97` / payload `4f137411`; 4 × `f810b64` / payload `92fe6b77` (smoke block, clusters 1-4, `stpt-run-v1.1`) | 1 | 1 |
| Qwen3.5-9B | 61 × `8f22f97` / payload `4f137411` | 1 | 1 |
| Gemma-3-27B | 61 × `8f22f97` / payload `4f137411` | 1 | 1 |
| Qwen3.5-27B | 61 × `8f22f97` / payload `4f137411` | 1 | 1 |

The two payloads differ only in `gates/S10/run/ledger.py` (chained spend seeding, A44), which does not produce or alter
records (`git diff f810b64 8f22f97` over the payload files). Results: `gates/S10/results/collection_integrity_*_core.json`.
