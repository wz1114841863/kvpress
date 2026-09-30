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
scoreboard attachment; this paragraph describes the bootstrap boundary rather
than the later owner-local RTL1 implementations below.

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
a stable formal/testbench attachment location. R1/R2/R3/S2 and selected R6
safety records are owner-Chisel-bound; descriptor reclaim and composed global
authority remain pending, and every progress property remains
`owner_event_pending`. Environment fairness remains a testbench assumption
rather than DUT logic.

## RTL1.1 R1 implementation

`common/RouteACommonSkeletons.scala` now implements R1 alone:

- finite four-read/one-write live identity tracking with `RID[2:0]` plus
  `incarnation[1:0]`, rejecting live-RID overlap while permitting post-terminal
  finite reuse only under the A3 external no-old-response/wrap-quiescence
  assumption;
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

## RTL1-I1.0 init/drain carrier closure

`external_core_mem_if_v1` includes a dedicated decoupled `init_ack` carrier
from the external R1 adapter. It is deliberately distinct from memory
responses. RTL1-I1 accepts it only at R1, fans its initialized fact to the
local reset-gated wrappers, and routes the three init/eight drain facts through
the reviewed integration-only collector to R6. The collector is not a physical
FIFO or an authority owner. This currently supports safe start and
empty-session retirement only; admission/publication/source/reclaim top wiring
remains the later I2--I4 scope. See
`analysis/rtl1_i1_init_drain_carrier_contract.md`.

## RTL1-I2 admission/publication association

RTL1-I2 joins an accepted RETAIN maturity's immutable record context with its
matching `hot -> pending` handoff at R3, records explicit member ordinals for
one already-formed `1..64` record group, and emits observations only after the
existing atomic publication acknowledgement.  The group tag/ordinal/population
remain opaque upstream association fields; this does not choose admission,
page packing, payload storage, HBM traffic, scheduling, physical memory, or
PPA.  The top wires R6--R3--R6 but intentionally lacks the later P3/R2
producer path.  See `analysis/rtl1_i2_admission_publication_contract.md`.

## RTL1-I3 delivery/source/R6 completion association

RTL1-I3 completes the frozen cross-owner control association from an R4
consumer commit to its sole hot/direct-pending/S2 owner, then from that owner's
generation-bearing four-consumer release to R6. `SourceCompletionPlan` gives
R6 the immutable nonempty expected hot/pending/packed source set for a live
attention identity; R6 emits the existing merge request only after exactly the
planned releases. R2 still treats `delivery_context_ref` as opaque, and the
R4 `SourceInstance` sideband stays separate from the frozen 128-bit header.

The top's source-plan/packet ingress remains structurally inactive, and the
test-only composition harness supplies directed logical stimuli. This is not a
payload/source-mux implementation, numeric merge, source scheduling choice,
or timing/PPA claim. See `analysis/rtl1_i3_delivery_source_contract.md`.

## RTL1-I4 R5 reclaim/R2/R1/R6 composition

RTL1-I4 adds the retirement-only, identity-bearing R6 reclaim permit, then
uses the existing R5 -> R2 -> unique R1 descriptor-maintenance route to write
one complete logical 64-B descriptor line at a time. R5 writes FREE plus the
next generation only for allocated lanes, frees those lanes only after the
matching terminal `ok`, and blocks retirement on a fault. R6 requires a fresh
post-reclaim R2-descriptor/R1 drain replay before its sole retirement ack.
This remains control-only: `address_ref` is opaque, there is no descriptor
read/cache/RMW, physical HBM realization, payload ingress, timing, or PPA
claim. See `analysis/rtl1_i4_reclaim_contract.md`.

## RTL1.2 R2 implementation

`RouteACoreSideArbiter` now realizes the frozen R2 eligibility and grant
boundary at module scope. Its candidate/storage bound and class encodings are
required elaboration parameters with no deployment defaults. It implements no
controller scheduling, source owner, publication, semantic-credit return, or
top-level traffic: the top's candidate source remains inactive until later
owner phases connect it.

The R2 ChiselSim suite checks ineligible backpressure, accepted-grant-only
cursor advance, ready-low stability, response association, and descriptor
terminal release. Its transport reservation is distinct from credits owned by
R3/R5/R6, so progress remains an environment-fairness obligation.

## RTL1.3.0 R3/R5 carrier closure

RTL1.3.0 adds module-local control carriers for later R3/R5 behavior: P3
claim/fragment/sidecar/write-terminal facts, the two M2 group-member results,
R5 allocation, and descriptor-maintenance terminals. They are deliberately
not external HBM commands, P3/SRAM macros, descriptor data writes, or a second
Route-A memory path. The frozen R3→R5 publication triplet remains unchanged,
and the top ties these carriers inactive until their owning integration paths
are implemented. See `analysis/rtl1_3_r3_r5_semantic_carrier_contract.md`.

RTL1.4.0 adds only module-local S2/direct-pending control carriers: S2 fill
and sidecar completion, source generation, direct record-terminal ordinal,
and generation-bearing GQA commit/release. The top keeps these inactive until
their owner modules gain RTL1.4 behavior. They neither instantiate the two
32-KiB source buffers nor create a direct pending buffer or source mux. See
`analysis/rtl1_4_s2_direct_pending_semantic_carrier_contract.md`.

RTL1.4 implements the corresponding module-scoped control state: S2 slot
generation, fill/sidecar completion, READY and four-consumer release; and
direct-pending endpoint generation, FIFO terminal order, close/fault and
four-consumer release. `RouteAS2DirectPendingSpec` checks these control
properties without storing source payload data or connecting a merge/source
mux.

RTL1.5.0 freezes the local R6 authority-transition and GQA-complete
merge-ready carriers, plus explicit elaboration-only logical encodings for
frontend events, component status names, and hot controls. These are neither
new top-level ports nor a deployment outstanding limit. The top ties them
inactive until lifecycle behavior is implemented. See
`analysis/rtl1_5_r6_lifecycle_semantic_carrier_contract.md`.

RTL1.5 implements only the R6 module control: init/session gates, staged hot
and authority events, finite attention identity/merge terminal association,
and eight-member retirement drain acknowledgement. It does not turn the top
into a source mux, create an authority table, connect R3 publication, or
implement R4 numeric behavior. `RouteALifecycleAdapterSpec` is a no-model
directed ChiselSim suite for this control scope.

RTL1.6.0 adds the identity-bearing R4 header/fragment/result/fault carriers
needed by the frozen packet boundary. They deliberately do not repurpose the
older opaque `SourcePartial` record. The top ties every new carrier inactive;
no exp/FP implementation, partial storage, source mux, numeric claim, or
terminal integration is present. See
`analysis/rtl1_6_r4_packet_boundary_contract.md`.

RTL1.6 completes module-local R4 packet/result/fault control in
`RouteAMergeBoundary`: frozen absent/present packet structure, one active
merge identity, stable consumer commits, and a single matching result-or-fault
mapping to the existing R6-facing terminal channel. It does not evaluate
binary32 fields or value fragments, implement `exp`/FP arithmetic, retain
partial payloads, choose a source schedule, or integrate the top. The no-model
directed evidence is `RouteAMergeBoundarySpec`.

RTL1-I0 is a documentation/manifest freeze only. It records why the current
top-level ties cannot yet be replaced by direct wiring: R3 publication needs
per-record membership for authority observation, R2 delivery needs a
reuse-safe context, R4 commits need a source-instance sideband, and init/drain
facts need explicit producers. It adds no Chisel behavior or hierarchy node.
See `analysis/rtl1_i_cross_owner_integration_contract.md`.

## Completed R3/R5 scope

RTL1.3 now implements module-scoped R3/R5 control: P3 state/generation and
completion bookkeeping, payload-durable association, two private M2 results,
private descriptor preparation, and the existing nested atomic-publication
handshake. It intentionally stores no P3 payload data and implements no M2
macro or descriptor HBM command. `RouteAR3R5PublicationSpec` exercises the
positive durable/publication order and negative P3/descriptor gates.

R4 remains a replaceable numeric boundary. Do not select a controller or infer
timing/PPA from the completed owner-local control bindings.
