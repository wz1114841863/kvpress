# Route-A Chisel RTL1 bootstrap

This directory is the isolated Chisel/SBT workspace for Route-A RTL1. It was
created only after Gate-RTL0 passed. Its authority and phase boundary are
`analysis/rtl1_phase_contract.md` and `analysis/architecture_spec.md`.

## Current RTL1.0.a scope

The project contains the RTL1.0.a structural skeleton and its no-model test:
the frozen `route_a_kv_subsystem_top` plus all nine frozen children elaborate
as a Chisel hierarchy. The top has only the environment ports and the single
R1 external-memory carrier; all other RTL0.2 records are internal logical
ready/valid channels. Inert source/sink tie-offs exist only to make the ports
and connections elaboratable before their owner phases add behavior.

This skeleton does **not** introduce functional architecture behavior, control
FSMs, mutable architectural state, M2/P3 storage, a memory controller, SVA, a
scoreboard binding, or a performance/PPA claim. RTL1.0.b remains responsible
for the planned SVA/testbench/scoreboard attachment; R1--R6 behavior remains
in their later RTL1 phases.

The structural top exposes `destructive_reset` as a single-bit carrier. Since
RTL1.0 has no sequential state, this does not select synchronous versus
asynchronous reset behavior; a later stateful phase must bind that realization
explicitly instead of inferring it from this shell.

## Pinned build contract

| Item | Pin | Purpose |
|---|---:|---|
| SBT | 1.11.5 | Project launcher ABI |
| Scala | 2.13.18 | Project compiler, selected by `build.sbt` rather than host `scala` |
| Chisel | 7.15.0 | Elaboration/compiler-plugin library |
| ScalaTest | 3.2.19 | No-model bootstrap test framework |

The Chisel pin and its required compiler plugin follow the official Chisel
project setup. Chisel 7.x supports the locally detected JDK 21; the project
uses Scala 2.13 deliberately, independent of the host's Scala 3 installation.
No Chisel source tree or snapshot dependency is used.

## Layout

```text
chisel/
  build.sbt                         pinned build dependency contract
  project/build.properties          pinned SBT launcher version
  src/main/scala/kvpress/routea/
    bootstrap/                      non-architectural elaboration smoke probe
    params/                         later frozen parameter adapters
    interfaces/                     later Chisel bundles from RTL0.2 manifest
    common/                         later common Full-KV / Route-A infrastructure
    incremental/                    later Route-A-only modules
    top/                            later top-shell skeleton
  src/test/scala/kvpress/routea/
    structural/                     current elaboration/port-structure tests
    r1/ r2/ r3_r5/ s2/ r6/ merge/   reserved RTL1 verification ownership areas
  src/test/resources/               non-frozen test fixtures only
  docs/                             local build and layout notes
```

The implemented source mapping is deliberately one-to-one with the frozen
hierarchy: `top/RouteAKVSubsystemTop.scala` is composition-only;
`common/RouteACommonSkeletons.scala` holds hot/S2/R2/R1 shells; and
`incremental/RouteAIncrementalSkeletons.scala` holds lifecycle,
direct-pending, M2/P3, page-manager, and R4-boundary shells.
`interfaces/RouteAInterfaces.scala` contains the logical carrier bundles and
`params/RouteASkeletonParameters.scala` contains the anchor/opaque-width split.

The selected anchor widths are fixed in source: RID/incarnation `3+2`,
PageRef `18+8`, 512-bit core fragment, 128-bit merge partial header, 512-bit
merge value fragment, and 4,096-bit normalized result. Opaque event/tag,
address/reference, ordinal, candidate, transaction-group, and stage-generation
fields have no deployment default and must be supplied by an integrator. Test
values only make elaboration possible; they are not an architecture selection.

The authoritative architecture owners, logical ports, assertions, and Python
scoreboard remain under `analysis/`; this directory must not fork or silently
renegotiate them. Generated artifacts and local IDE/build state are ignored
by this directory's `.gitignore`.

## Local no-model preflight

Use a command-scoped JDK path so no global `JAVA_HOME` change is required:

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch compile
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch test
```

The first invocation may download pinned Maven dependencies and Chisel's
managed elaboration tool. `test` checks the full hierarchy in CHIRRTL and the
top-level ports in in-memory SystemVerilog; it does not invoke a model, GPU
workload, Route-A experiment, or performance measurement. Verilator is
available for a later explicitly scoped simulation step, but RTL1.0.a does not
use it.

## Next authorized step

Complete RTL1.0.b according to `analysis/rtl1_phase_contract.md`: bind the
already-planned SVA/testbench/scoreboard infrastructure to this skeleton. Do
not begin R1--R6 behavior merely because structural elaboration passes.
