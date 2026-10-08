# RTL2.6.5c — accepted-carrier event capture and oracle replay

**Status:** `implemented_directed_tested_no_model`.

RTL2.6.5c closes the remaining event-capture/replay preparation without
altering the immutable RTL2 v1.0 event schema or attaching an observer to the
production top. The versioned
[`rtl2_6_5c_event_capture_replay_manifest.json`](rtl2_6_5c_event_capture_replay_manifest.json)
defines a testbench-only boundary:

```text
declared owner carrier + accepted handshake
  -> exact immutable-schema event fields
  -> captured architectural-event trace
  -> existing Python authority / terminal / reclaim oracles
```

An observation must name an owner and carrier already listed by the immutable
schema, preserve the schema-ordered fields exactly, and set `accepted=true`.
An unaccepted observation—including ready-low and rejected stale traffic—is
not an event. The adapter supplies no field default and derives no event from
private owner state.

The directed no-model tests capture all fourteen event types in the accepted
success witness, then replay it through the Route-A authority reference plus
the existing attention-terminal and reclaim scoreboards. The replay confirms
the one `pending -> packed` publication handoff, four distinct GQA consumer
commits before release, exactly one terminal, invalidation before page free,
matching retire acknowledgement, and no Full-KV substitution. Separate
directed branches show that a faulted fragment cannot become durable/published,
that an unaccepted stale response emits nothing and a mismatched accepted
response fails closed, and that bounded ready-low emits nothing until a later
actual acceptance.

This capture/replay evidence is intentionally an event-level testbench
contract. It is not a claim that the separate RTL2.6.5a.2 and RTL2.6.5b
composition slices have become one production waveform or that their events
carry cycle timestamps. It does not establish a production R3/R5-to-S2 bridge,
numeric R4, HBM/SRAM/controller realization, deadlock freedom, timing,
throughput, area, energy, PPA, model/GPU behavior, or new A4 DSE. RTL2.6.5d
must still perform the cross-owner completion review.
