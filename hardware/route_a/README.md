# Route-A hardware workspace

This is the version-controlled home for Route-A hardware research after the
software/model-binding gates.  It starts with metadata/control cost work and
keeps future payload-path and Chisel work separate.

## Status and authority

Research history and current conclusions are consolidated in the
[project overview](../../analysis/project_overview_20261111.md) and
[H1–H4](../../analysis/hardware_reports/). The bounded first-use path and
explicit persistent-read v2 witness have functional evidence; multi-group
admission, sustained decode and the complete numerical/service path remain
open. The accepted RD1+WCG1 control mapping reduces area, while top-level
setup/hold and complete incremental costs remain unresolved. This workspace
is not a completed numeric/memory realization or a PPA/speedup result.

Use the [project overview](../../analysis/project_overview_20261111.md) for the
short continuation state and [architecture specification](../../analysis/archive/architecture_spec.md)
for technical definitions. Historical contracts referenced by frozen records
can be read at their recorded Git revisions; the pre-cleanup hardware-document
snapshot is `636c19b`. The Chisel README also contains historical phase notes;
current research scope is described by H2 rather than those old launch states.

The frozen A4.12.0 interface table is the input authority for this workspace:

| Item | Frozen source | Interpretation here |
|---|---|---|
| 8 head-affine banks and abstract 2 read / 2 write / 2 commit-coupled RMW service capability | A4.9.1/A4.12.0 | Logical service requirement, never a selected SRAM port count. |
| `local32/shared256/staging512` | A4.10/A4.12.0 | Logical lossless resource contract, not automatic 36-layer physical replication. |
| 59/50 raw and 64/64 padded metadata accounting | A4.9.1/A4.12.0 | Semantic entry accounting; payload pointer fields remain parameters for A4.13. |
| token-to-span/group conversion and external-storage lifecycle binding | A4.11.2b/A4.12.0 | Software/binding evidence, not hardware ready/commit activity. |
| 64-token packed page, 32-KiB source page buffer, legal four-query-head GQA reuse | A4.13.3--A4.13.5 | Declared payload dataflow/interface, not a native HBM transaction or controller schedule. |
| M2 metadata proxy, P3 staging envelope and A4.14.1 omitted-cost budget | A4.12/A4.14 | M2 area is public-CACTI proxy; P3 and merge/control terms remain unestimated. |

`mem/` provides a reproducible public-CACTI proxy runner. `chisel/` contains
the staged RTL1--RTL3 Chisel sources and directed functional harnesses; it is
not a completed numeric/memory realization. A4.12 CACTI area and per-access
numbers are
estimates from a public technology model; they are not PDK, macro-compiler,
synthesis, layout, timing, throughput, workload-energy, architecture, or RTL
evidence.

The reviewed frozen interface boundary is `analysis/architecture_spec.md`.
It defines the common S2 versus Route-A incremental split, M2/P3/page/merge
interfaces, parameterized realization fields, omitted costs, and the separate
RTL gate.  It does not select a production macro, controller, clock, or RTL
implementation.

## Layout

```text
hardware/route_a/
  mem/                 generic MacroSpec and verified-CACTI runner
  chisel/              staged RTL1--RTL3 Chisel sources and functional harnesses
  docs/                evidence and stage-boundary notes
```

## Toolchain setup

The CACTI source checkout and locally compiled executable are deliberately
ignored because they are generated third-party build products.  Their public
source URL, exact commit, and required build command are tracked in
`mem/cacti_toolchain/source_lock.json`.

```bash
hardware/route_a/mem/cacti_toolchain/build_cacti.sh
hardware/route_a/mem/run_cacti_macro.py --help
```

The build script clones the pinned public source when necessary, validates an
existing checkout is clean and has the expected origin, then emits a local
toolchain manifest with source/template/binary SHA-256 values.  The runner
checks that manifest again before every non-preflight execution.

## Boundaries

- The runner models one explicitly described SRAM proxy macro at a time.  It
  never converts Route-A's abstract service requirement into a physical port
  implementation.
- `MacroSpec` records read, write, and read-write ports explicitly.  It does
  not choose them implicitly.
- Each run keeps the generated CACTI configuration plus stdout/stderr and a
  machine-readable record in the requested new output directory.
- A4.12.1 remains a frozen three-candidate result.  This workspace is a
  reusable toolchain for later, separately contracted studies, not a rewrite
  of that result.
