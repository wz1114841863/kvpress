# Route-A Chisel RTL1 bootstrap

This directory is the isolated Chisel/SBT workspace for Route-A RTL1. It was
created only after Gate-RTL0 passed. Its authority and phase boundary are
`analysis/rtl1_phase_contract.md` and `analysis/architecture_spec.md`.

## Current implementation scope

The project contains the RTL1.0.a structural skeleton and its no-model test:
the frozen `route_a_kv_subsystem_top` plus all nine frozen children elaborate
as a Chisel hierarchy. The top has only the environment ports and the single
R1 external-memory carrier; all other RTL0.2 records are internal logical
ready/valid channels. Inert source/sink tie-offs exist only to make the ports
and connections elaboratable before their owner phases add behavior.

The top remains an integration skeleton: other than R1 it contains no
functional architecture behavior, M2/P3 storage, controller, CDC, SVA/formal
proof, or performance/PPA claim. RTL1.0.b provides the matrix/testbench/
scoreboard attachment; R2--R6 remain in their later RTL1 phases.

The structural top exposes `destructive_reset` as a single-bit carrier. R1
uses it for local transaction state; it still does not select a subsystem
CDC/controller reset sequence or a physical reset implementation. A later
lifecycle/reset owner must bind the top-level `mem_init_done` integration.

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
    sva/                            non-synthesizable assertion binding registry
  testbench/                        read-only Python oracle binding adapter
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
managed elaboration tool. `test` checks the full hierarchy in CHIRRTL, the
top-level ports in in-memory SystemVerilog, and the RTL1.1 R1 directed
ChiselSim suite; it does not invoke a model, GPU workload, Route-A experiment,
or performance measurement.

## RTL1.0.b verification binding

`src/test/resources/rtl1_0_verification_binding.json` is a read-only bridge
from the 15 frozen Gate-RTL0 assertion records to this skeleton hierarchy, the
SVA binding registry, fairness-versus-DUT responsibility, and the existing
Python oracle manifest. Its companion under `testbench/` exposes each oracle's
exact path, entry-point labels, observation, and forbidden adapter condition.
It does not translate or execute any event before owner behavior exists.

The SVA resource is a zero-port `bind` registry at the frozen top. It provides
a stable formal/testbench attachment location. All non-R1 safety properties
remain `owner_state_pending`, and every progress property remains
`owner_event_pending`; environment fairness remains a testbench assumption
rather than DUT logic.

## RTL1.1 R1 implementation

`common/RouteACommonSkeletons.scala` now implements R1 alone:

- finite four-read/one-write live identity tracking with `RID[2:0]` plus
  `incarnation[1:0]`, including same-epoch identical-identity rejection;
- exact ordered 512-bit fragment forwarding and `last` enforcement;
- write-data-before-write-commit ordering, terminal-fault fail-closed behavior,
  and payload-durable-only scope;
- reset-to-`mem_init_done` traffic gating and unmatched/stale-response
  suppression at R1's sole external-memory carrier.

`RouteACoreMemIfV1Spec` is a ChiselSim directed test suite for those module
semantics. It does not connect a controller, replace the frozen Python oracle
with an event adapter, prove SVA/formal properties, or establish end-to-end
Route-A behavior. The top binds R1's local `mem_init_done` low until the later
lifecycle/reset phase, intentionally leaving top-level traffic inactive.

## Next authorized step

Proceed to RTL1.2 only under the R2 eligibility/FIFO/credit/grant-on-accept
contract. Do not begin R3--R6 behavior, select a controller, or infer
timing/PPA from the completed R1 bindings.
