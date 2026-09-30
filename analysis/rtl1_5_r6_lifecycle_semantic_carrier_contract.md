# RTL1.5.0 — R6 lifecycle semantic-carrier closure

## Status and boundary

**Status:** `complete_nonbehavioral_r6_carrier_and_parameter_closure; rtl1_5_control_pending`.

This record materializes only the local Chisel carriers required before the
frozen R6 lifecycle adapter can gain control behavior. It consumes the
existing score-free lifecycle, authority, merge-terminal, reset/init, and
retirement contracts. It changes no top-level environment port and makes no
controller/FSM, payload storage, source-mux, merge datapath, timing,
throughput, PPA, model/GPU, or new-A4-DSE claim.

## Parameterized logical encodings

`RouteAR6Encoding` requires a concrete elaboration to supply distinct codes
for the four existing frontend event kinds, the three existing hot-control
kinds, and all three init plus eight drain status names. It also supplies a
finite attention-tracker entry count in the selected 32-identity A3 namespace.
The `testOnlyAnchor` value exists only to elaborate no-model Chisel tests; it
is not a deployment default, wire protocol, maximum outstanding selection, or
physical queue/controller configuration.

The existing `FrontendLifecycleRequest.event_kind`,
`ComponentStatus.acknowledgement_name`, and `HotControl.control_kind` fields
remain width-parameterized. RTL1.5 must not silently infer their encodings.

## Local authority transition carrier

`r6_authority_transition` has:

```text
entry_id, from_authority, to_authority, transaction_group_tag
```

The four fixed values `none/hot/pending/packed` are logical transition labels,
not a token-residency memory encoding. The lifecycle-originated direction is
limited to `none -> hot` on arrival and `hot -> none|pending` on maturity. The
opposite direction carries only the already-selected R3
`pending -> packed` metadata-publication association. The latter explicitly
carries the group tag because the preexisting metadata acknowledgement alone
does not identify an `entry_id`.

This carrier is an event-level cross-owner observation. It is not a duplicate
full-session authority table, M2 record, P3 page, or new atomic-commit
boundary. `metadata_publish_commit` remains the sole pending-to-packed
linearization point.

## Local merge-ready carrier

`r6_merge_ready` has:

```text
transaction_identity, source_presence[hot,pending,packed]
```

Its acceptance represents the existing fact that all four legal GQA consumer
updates for that identity have committed. The source bitmap is nonzero and
contains only the frozen canonical `hot -> pending -> packed` positions; no
Full-KV bit, fallback, source reordering, payload, or numeric field exists.
Only after this carrier may R6 issue the existing `merge_req`. R4 still owns
the replaceable numeric boundary and R6 alone consumes its terminal/fault.

## Integration status

The new carrier endpoints are module-local and top-tied inactive in RTL1.5.0.
They do not connect R3 publication, source service, S2/direct, or R4 at the
top. RTL1.5 behavior may test them directly at the lifecycle owner. A later
top-integration phase must connect the named owners without moving state into
the top shell or changing the frozen architecture ports.

## Evidence boundary

This closure is synthesizable-interface preparation plus compile/elaboration
evidence only. It establishes neither R6 behavioral correctness, RTL proof,
source service, physical storage/controller behavior, latency, frequency,
energy, area, nor speedup.
