# RTL2.3-C6 — source-plan binder closure

**Status:** `implemented_directed_tested; source_declaration_to_r6_plan_only`.

C6 closes the missing non-top producer for R6's immutable
`SourceCompletionPlan`. `route_a_source_plan_binder` accepts an upstream
`SourcePlanDeclaration`, validates its frozen structural form, holds one exact
accepted declaration under R6 backpressure, and emits one matching completion
plan. It is a finite control association only; it does not compute source
presence, choose a source, select a schedule, inspect payload, create an
attention tracker, or generate a source packet.

The machine-readable binding is
[`rtl2_3_c6_source_plan_binder_manifest.json`](rtl2_3_c6_source_plan_binder_manifest.json).

## Ownership and top boundary

The upstream declaration is environment-owned and already selected. Its
identity, nonempty `source_presence`, and three exact canonical
`SourceInstance` records are its immutable facts. The binder is the sole RTL
producer of the R6-facing `SourceCompletionPlan`; R6 remains the sole consumer
that decides whether the identity names a live `AwaitMergeReady` tracker.

```text
upstream SourcePlanDeclaration
  -> route_a_source_plan_binder
  -> RouteALifecycleAdapter SourceCompletionPlan input
```

`route_a_kv_subsystem_top` exposes the declaration only as an ingress and
composes the binder. It does not synthesize, alter, merge, or schedule a plan.
This makes the former inert source-plan carrier explicit without authorizing a
top-generated source set.

## Accepted form and fail-closed behavior

A declaration is accepted only when:

- `source_presence` is nonempty;
- hot/pending/packed instance kinds are exactly canonical `0/1/2`; and
- the binder has no held declaration awaiting R6 acceptance.

On acceptance, all identity, mask, coordinate, and generation fields are
copied exactly. Empty masks and noncanonical kind tuples are held
`ready`-low and cannot create output. While R6 applies backpressure, the held
completion plan is immutable and no second declaration is accepted. The
binder neither validates source residency nor substitutes direct-pending/S2;
those remain C7 and later owner-path concerns.

## Directed evidence and exclusions

`RouteASourcePlanBinderSpec` covers all seven nonempty source masks, empty and
noncanonical declarations, and exact hold under output backpressure. The top
structural test confirms the named binder and declaration ingress; the
init/drain integration regression remains valid with deliberately inactive
payload and declaration ingress tied off.

C6 does not activate `source_deliverable`, `consumer_partial_commit`,
`source_release`, or `merge_request`; the active event overlay assigns those
to C7/C8. It does not implement R4 packet production, numerical partials,
source arithmetic, read delivery, physical storage/controller behavior,
cycles, timing, throughput, PPA, a model/GPU workload, or a new A4 DSE.

## Reproduction

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteASourcePlanBinderSpec' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec' \
  'testOnly kvpress.routea.integration.RouteAInitDrainIntegrationSpec'
```
