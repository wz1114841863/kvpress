# RTL2.3-C7 — source-service top integration closure

**Status:** `implemented_directed_tested; plan-copy_and_owner-observation_only`.

C7 places the existing `route_a_source_service_packet_adapter` in
`route_a_kv_subsystem_top`.  The composition-only top forwards the exact
R6-accepted `SourceCompletionPlan` copy and connects the three owner-local
availability observations.  It does not choose a source, create a plan,
compute a partial, introduce an alternate payload path, or make a terminal or
authority decision.

The machine-readable provenance record is
[`rtl2_3_c7_source_service_top_integration_manifest.json`](rtl2_3_c7_source_service_top_integration_manifest.json).

## Exact composition

The only plan path is:

```text
upstream immutable declaration
  -> route_a_source_plan_binder
  -> R6 accepts SourceCompletionPlan
  -> R6 exact copy
  -> route_a_source_service_packet_adapter
  -> frozen R4 packet ingress
```

The top neither reads the copy to select a source nor reconstructs its
identity, presence mask, coordinates, or generations.  The adapter owns its
own accepted-plan copy.  It exports only the packed instance's logical S2-slot
selector so that the top can ask the S2 owner for the corresponding read-only
observation.  An out-of-range packed coordinate is truncated only for the
read-only slot lookup; it still fails closed because the adapter requires an
exact full `SourceInstance` equality, including the untruncated coordinate and
generation, before it can accept an offer.

The connected observations are fixed by owner:

| Plan source kind | Owner | C7 availability binding |
|---|---|---|
| hot | `route_a_hot_source_path` | `hot_observe_active`, exact identity, exact instance |
| pending | `route_a_direct_pending_endpoint_v1` | `direct_observe_deliverable`, exact identity, exact instance |
| packed | `route_a_s2_gqa_source_wrapper` | `s2_observe_available`, exact identity, exact instance at the adapter-selected slot |

These are read-only eligibility facts.  They do not cause a hot open, direct
pending record terminal, S2 fill, state transition, GQA consumer completion,
source release, or source substitution.  In particular, an available S2 slot
cannot stand in for a planned direct-pending source.

## Deliberately inactive packet producer boundary

No source owner has yet been authorized to produce a numeric partial or an
owner-local `SourceServicePartialOffer` / `SourceServiceValueFragment` stream.
C7 therefore ties all six offer/fragment ingress carriers inactive while it
connects the adapter's legal R4 header/sideband/fragment egress to the frozen
merge boundary.  This is intentional fail-closed behavior: no incomplete,
stale, mismatched, or fabricated packet can reach R4 merely because an owner
observation is valid.

Consequently, C7 does not itself issue an accepted source packet or a host-side
scoreboard `source_deliverable` record.  It activates only the owner-observation
carrier on which a later authorized source-packet producer may be accepted.
The active phase overlay's C7 label names this prerequisite carrier, not a
numeric partial, an arbitrary internal-state inference, or a new scoreboard
adapter.  C8 remains responsible for four matching R4 commits, exactly one
owner release per present source, and R6 `merge_req`.

## Directed evidence and exclusions

`RouteAKVSubsystemTopSpec` elaborates the top with the packet adapter and its
owned packed-slot observation port.  The pre-existing packet-adapter suite
continues to validate all seven nonempty masks, canonical order, malformed and
stale fail-closed behavior, and R4 backpressure.  The top init/drain suite
confirms that the new inactive packet ingress does not disturb reset/init or
empty-session retirement.

C7 is synthesizable structural/protocol evidence only.  It makes no
model/GPU, A4 DSE, numeric-datapath correctness, full attention, end-to-end
RTL correctness, controller, physical-memory, cycle, latency, throughput,
area, energy, or PPA claim.

## Reproduction

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'Test / compile' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec' \
  'testOnly kvpress.routea.rtl2.RouteASourceServicePacketAdapterSpec' \
  'testOnly kvpress.routea.integration.RouteAInitDrainIntegrationSpec'
```
