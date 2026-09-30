# RTL1.5.0 — R6 lifecycle semantic-carrier closure

## Status and boundary

**Status:** `complete_r6_carrier_and_module_scope_control_closure; top_integration_pending`.

This record materializes the local Chisel carriers and module-scope control
required by the frozen R6 lifecycle adapter. It consumes the
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

## RTL1.5 module-control binding

`RouteALifecycleAdapter` now has only the finite R6 control state: reset/init
acknowledgements, session state, staged lifecycle event delivery, a
parameterized live-attention identity tracker, merge-ready-to-merge-request
association, one outward terminal staging register, and the eight-member
retirement drain predicate. It explicitly does **not** create a permanent
per-token authority table. Long-lived hot/pending/packed residency remains at
the hot/M2/R3/R5 owners; R6 carries and checks only the selected event-level
handoff forms.

An attention identity becomes merge-eligible only after accepted
`r6_merge_ready`; the existing R4 terminal is then accepted exactly once and
becomes one outward ok/fault response. Thus a numeric fault cannot terminalize
before the source service has reported the four-commit condition, and no
Full-KV fallback or retry exists. Retire stops new frontend lifecycle accepts,
but permits already live attention and named R1/R2/R3/R5/S2/direct/R4 drain
members to complete before the matching acknowledgement.

`RouteALifecycleAdapterSpec` is the directed no-model module check. It covers
init gating, ready-low event stability, authority-transition forms, nonempty
canonical merge-ready, unique terminal delivery, stale duplicate rejection,
all eight retirement members, and local destructive-reset reinitialization.
The Chisel assertions bind `a_numeric_fault_consumer`,
`a_global_retirement_membership`, and `a_exactly_one_terminal`. The full
cross-owner `a_authority_conservation` remains a composed scoreboard/SVA
property until R3/source/top integration exists; this module does not falsely
claim to prove every long-lived token's distributed residency.

## Integration status

The new carrier endpoints are module-local and top-tied inactive in RTL1.5.0.
They do not connect R3 publication, source service, S2/direct, or R4 at the
top. RTL1.5 tests them directly at the lifecycle owner. A later
top-integration phase must connect the named owners without moving state into
the top shell or changing the frozen architecture ports.

## Evidence boundary

This closure is no-model module-scope control evidence, not an RTL proof or
complete Route-A behavior claim. It establishes neither source service,
top-level integration, physical storage/controller behavior, latency,
frequency, energy, area, nor speedup.
