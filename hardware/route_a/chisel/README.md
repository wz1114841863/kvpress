# Route-A Chisel RTL1 bootstrap

This directory is the isolated Chisel/SBT workspace for Route-A RTL1. It was
created only after Gate-RTL0 passed. Its authority and phase boundary are
`analysis/rtl1_phase_contract.md` and `analysis/architecture_spec.md`.

## Bootstrap scope

The initial project deliberately contains only an elaboration smoke probe and
its no-model test. The probe is not `route_a_kv_subsystem_top`, is not one of
the frozen Route-A hierarchy modules, and owns no Route-A architectural state.
It exists solely to prove that the pinned toolchain can compile and elaborate a
minimal Chisel circuit on this host.

This bootstrap does **not** introduce synthesizable architecture behavior,
control FSMs, M2/P3 storage, a memory controller, SVA, a scoreboard binding,
or a performance/PPA claim. RTL1.0 is the separately reviewed next phase: it
may add the frozen hierarchy's skeletons, interfaces, reset/ready-valid wiring,
and verification attachment, but still makes no functional-correctness claim.

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
managed elaboration tool. `test` only emits SystemVerilog in memory for the
bootstrap probe; it does not invoke a model, GPU workload, Route-A experiment,
or performance measurement. Verilator is available for a later explicitly
scoped simulation step, but this bootstrap does not use it.

## Next authorized step

After this bootstrap is reproducibly green, implement RTL1.0 according to
`analysis/rtl1_phase_contract.md`: first frozen module skeletons and logical
interfaces, then the already-planned SVA/testbench/scoreboard attachment. Do
not begin R1--R6 behavior merely because this host preflight passes.
