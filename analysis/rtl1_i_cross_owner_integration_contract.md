# RTL1-I — cross-owner semantic integration contract

## Status, entry, and non-goals

**Status:** `rtl1_i0_contract_frozen; no_behavioral_top_wiring`.

RTL1-I begins after the RTL1.1--RTL1.6 owner-local controls and R4's
replaceable packet boundary. Its entry condition is the documented fact that
the top remains intentionally inert and that module-local proof does not prove
cross-owner composition. This contract freezes the semantic associations needed
to remove those tie-offs in later RTL1-I substeps. It does not create a
synthesizable integration module, change a frozen owner, implement an HBM
controller, choose a queue depth/port count, create payload storage, select a
numeric core, establish a clock/latency/throughput claim, make a PPA claim, or
run a new A4 DSE.

The top remains composition-only. No integration bridge may become a second
token-authority table, source scheduler, source mux, physical memory model, or
alternate `metadata_publish_commit` boundary.

## I0 frozen association rules

### A. Admission and publication membership

An accepted RETAIN maturity eventually supplies an immutable admission context
from the hot/admission owner to R3/R5. It identifies the entry coordinate,
payload association, and one publication group without reconsidering the
already frozen DROP/RETAIN decision. The later finite carrier must contain an
`entry_id` (or exactly equivalent `(layer, kv_head, logical_position)`) for
every admitted record. A first-entry-plus-count span is forbidden: the original
KVzap mask permits non-contiguous retained positions.

R3/P3 owns the bounded, logical publication-membership ledger while its P3
group is live. Its maximum membership is the frozen 64-token page population.
This is an association with the existing position-sidecar records, not a
physical SRAM, P3 payload macro, or duplicate authoritative residency.

The sole `metadata_publish_commit` remains the atomic linearization point.
Only after its existing R3/R5 nested acknowledgement may R3 emit a
group-level `publication_commit_observation` and its bounded member-observation
sequence to R6/the verification monitor. Those observations may be delayed by
legal ready-low, but do not create a second commit: all reported members became
packed at the original one atomic boundary.

### B. R2/R1 delivery context

Every R2 `SourceCandidate` that launches R1 transport must carry a
reuse-safe, opaque `delivery_context_ref`. R2 preserves it through its live
outstanding association and returns it with the sole R1 response delivery.
The ref is resolved only by the source/admission owner that created it; R2
does not own S2 slot, direct-endpoint, P3-stage, or payload state.

The ref is required to derive the already frozen local facts for S2
fill-terminal, direct-pending record-terminal, P3 fragment/write-terminal, and
descriptor-maintenance terminal: identity, source/stage generation, page or
endpoint association, ordinal/last, and explicit-empty status where applicable.
It is a logical parameter with no selected implementation width, table, or
physical FIFO.

### C. Source-instance-safe R4 completion

The frozen 128-bit R4 partial header is not changed. A separate source-instance
sideband accompanies a header packet and returns unchanged with every
`consumer_partial_commit`. It carries the frozen route source kind
`{hot,pending,packed}`, a source-instance generation, and the finite source
instance coordinate required by that owner. The sideband must distinguish the
hot owner, the direct-pending endpoint, and a common S2 slot; hot must not be
silently treated as S2.

The current `source_is_direct` Boolean is therefore insufficient as the final
cross-owner completion association. RTL1-I refines the local GQA commit/release
carrier to use the sideband; it does not reinterpret the R4 numeric packet or
claim a physical multicast implementation. R4 forwards the association and
does not allocate, infer, or reuse a source instance.

Each source owner accepts only matching current-generation commits, emits one
release after four distinct consumer commits, and reports its release to R6.
R6 may own a finite attention-local expected/released source bitmap, because
that is short-lived terminal association rather than long-lived token
authority. The source set remains the already frozen canonical
`hot -> pending -> packed` set with no Full-KV fallback bit or source reordering
claim.

### D. Reset/init and global drain facts

The external R1 adapter is the sole producer of a named init acknowledgement;
ordinary R1 response traffic must never be reinterpreted as initialization.
After that acknowledgement, R1, R3/M2/P3, R5, S2, and direct may report only
their own initialization/drain facts. A lossless integration status collector
may serialize these facts to R6 but cannot fabricate, merge, or drop them.
Its arbitration realization remains unselected in I0.

Each R6 drain acknowledgement must be produced from the named owner's actual
local-live predicate. `retire_ack` remains blocked until all eight frozen drain
facts, active attention, staged control, merge, and terminal state are empty.

### E. Reclaim and reuse

R5 remains the sole allocator/generation owner. After global drain and the
already frozen per-page quiescence condition, R5 must issue one descriptor
invalidation through R2 then the unique R1 transport path. Only its matching
durable terminal permits generation advance and allocator-bit reuse. No reset,
source release, publication acknowledgement, or raw HBM-byte observation may
free a page.

## Required later implementation order

| Substep | Allowed scope | Required evidence |
|---|---|---|
| RTL1-I1 | external init acknowledgement, component-status collection, local drain producers | reset/init and withheld-drain top ChiselSim |
| RTL1-I2 | admission context, R3 membership ledger, one publication-to-authority observation | retained/non-contiguous group, fault, and atomic-visibility top tests |
| RTL1-I3 | delivery context preservation, source-instance sideband, hot/S2/direct completion and R6 merge-ready | all seven nonempty source masks, stale generation, R4 fault terminal tests |
| RTL1-I4 | R5 invalidation/reclaim/reuse and composed assertions | retire, durable-invalidate-before-free, generation reuse, fixed-seed legal stalls |

Each substep must retain the one R1 external memory path, the sole
`metadata_publish_commit`, fixed mask/admission semantics, direct-pending
realization, two S2 slots, legal four-consumer GQA reuse, and R4's replaceable
numeric boundary.

## Assertion and evidence boundary

RTL1-I is permitted to compose existing safety/progress assertions and the
already frozen Python references. It must label environment fairness explicitly
and may not translate a bounded directed/random protocol test into an RTL
correctness proof, timing result, throughput result, or PPA result. Numeric
result quality remains owned by the existing Python oracle and a future R4
numeric realization gate.
