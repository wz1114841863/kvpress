# Route-A metadata-memory tooling

## What was refactored

This directory replaces the ignored `tmp/mem` CACTI wrapper with a
Route-A-specific, version-controlled toolchain boundary.

| Former scratch component | Route-A replacement | Reason |
|---|---|---|
| `cacti_simulation.py` | `cacti_runner.py` | Keeps one-macro execution, explicit ports, generated config, raw logs, and source-checkout working directory. |
| `cacti_config.py` | pinned upstream `cache.cfg` plus `source_lock.json` | Avoids maintaining an unproven detached CACTI template. |
| bundled `cacti/cacti` | `cacti_toolchain/build_cacti.sh` | Builds a locally ignored executable from the pinned public source commit and validates SHA-256. |
| BRISK-KV `briskkv_memory_eval.py` / `mem_instance.py` | not migrated as live Route-A code | They encode a different RTL inventory, 28-nm interpolation, and fixed 1R+1W assumptions that cannot be silently imported into Route-A. |

The previous binary had no upstream source/commit/license provenance.  It is
therefore deliberately not a fallback executable for Route-A experiments.

## Rebuild and preflight

```bash
hardware/route_a/mem/cacti_toolchain/build_cacti.sh
.venv/bin/python hardware/route_a/mem/run_cacti_macro.py --preflight-only
```

The script pins public CACTI to the source lock, saves the locally observed
binary/template hashes in an ignored manifest, and requires those hashes before
each invocation.  Rebuilding a known source is normal; edit neither the local
checkout nor the generated manifest.

## Run one explicit macro proxy

```bash
.venv/bin/python hardware/route_a/mem/run_cacti_macro.py \
  --name metadata_1kib_1rw --role example_metadata \
  --depth 128 --width-bits 64 --readwrite-ports 1 \
  --output-dir analysis/experiments/<new_id>/
```

The output directory must not exist.  It contains `cache.cfg`, CACTI stdout and
stderr, and `macro_record.json` with the requested versus padded capacity,
explicit ports, exact toolchain hashes, and proxy metrics.

## Route-A usage constraints

- CACTI consumes a selected physical macro proxy.  A4.9.1's abstract HA8-wide
  2-read/2-write/2-RMW service capability does **not** select a 2R2W macro.
- Port counts are mandatory inputs to `MacroSpec`; the runner never defaults a
  logical service capability to a physical port count.
- The minimum 1-KiB and line-size padding are recorded separately from useful
  logical capacity.
- Per-access pJ values are macro characterization inputs, not workload energy.
  A4.12.2 needs an explicit access/cycle model before any multiplication.
- Payload address/page fields remain A4.13 parameters.  Do not use this runner
  to claim a final metadata entry width.
