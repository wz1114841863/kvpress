# Compact membership read-port audit and selected change — 2026-11-04

## Scope and outcome

This batch inventories every read of the two compact tables, establishes the
useful concurrency restrictions, and selects a bounded implementation change.
It changes no RTL or synthesis input.  The running entry-id driver repair is
untouched.  Machine-readable inventory:
`dc_compact_membership_read_port_audit_20261104.csv`.

**Selected RD1 candidate:** share the 79-bit member-record read among M/S/O
inside each of the existing 36 banks.  Preserve independent global consumer
selection and concurrent service to different banks.  Keep C/F/B validation
reads and both 80-bit pending-suffix reads independent in the first batch.
Do not add registers, read arbitration, latency, caching, or a memory macro.

## Tables, notation and complete consumer inventory

`membershipEntries(layer)(ordinal)` contains position[14:0] and payload_ref[63:0].
`membershipPayloadBindings(layer)(ordinal)` contains identity[4:0], handle[63:0],
generation[7:0] and destination[2:0] in the current projection.

Source authority is `RouteAIncrementalSkeletons.scala`, RouteAM2P3Wrapper.
There are six logical member-table readers and two pending-suffix readers:

| ID | consumer | fields from compact tables | index | effective read condition |
| --- | --- | --- | --- | --- |
| M | materialized work | member payload_ref (64); all pending suffix (80) | candidate layer and candidate ordinal | eligible lowest layer/ordinal, RESERVED/FILLING, not materializerActive |
| S | materialized sidecar | full member record (79) | eligible sidecar layer and its materializerOrdinal | RESERVED/FILLING, active, sidecar not done, sidecarNext equals active ordinal |
| C | checked work/issue | member payload_ref (64); all pending suffix (80) | external work layer and low six ordinal bits | validate stage/generation/presence/count and exact immutable fields |
| F | pending-fragment validation | member payload_ref (64) | fragment layer; fragment_index[8:3] | full membership and live stage/generation, then payload/status/order checks |
| B | sidecar-bind validation | full member record (79) | bind layer; low six record_ordinal bits | presence/live stage/generation and sidecarNext, then exact position/payload checks |
| O | publication member + authority | full member record (79); position also reconstructs entry_id | selected observation layer and current observation ordinal | observationActive, commit sent, ordinal in range |

M/S/O are source outputs whose valid decisions do not require the record
data.  O is already ONE shared read for two independently accepted outputs;
it must remain live until both member and authority handoffs resolve.

C/F/B are different: their ready equations read the stored fields even with
input valid low.  The final fire is not an adequate read-demand predicate.
Reusing their port based on ready/fire would risk changing fail-closed or
backpressure behavior, or adding a combinational dependency cycle.

Other structures are outside these data-table ports: stage headers/counters,
the all-bank candidate masks, membership presence bitmaps and PopCount logic,
P3 payload/sidecar storage, the reconciliation journal and same-cycle admission
bypass.  Publication commit/page-ready outputs read headers rather than adding
another member-record port.  Withdrawal reads the persistent journal, not a
third copy of the compact tables.

## Concurrency: distinguish wrapper conditions and production composition

The following matrix describes SAME-bank effective reads at the wrapper
boundary, based on its current guards.  Y means no same-bank exclusion can be
used to remove a port; it does not promise both operations will fire.  D means
same-bank effective reads are excluded, while different-bank overlap is not
excluded by the wrapper's bank-state guards alone.

| pair | M | S | C | F | B | O |
| --- | --- | --- | --- | --- | --- | --- |
| M | — | D | Y | Y | Y | D |
| S | D | — | Y | Y | Y | D |
| C | Y | Y | — | Y | Y | D |
| F | Y | Y | Y | — | Y | D |
| B | Y | Y | Y | Y | — | D |
| O | D | D | D | D | D | — |

This is a conservative wrapper-interface analysis, not a claim that all
cross-bank traffic combinations are reachable in the current production run.
Current production admits one bound group per reset and the ingress remains
StateDone after relay; that is narrower than the wrapper's banked structure.
The first optimization deliberately does not exploit this reset-only bound
to remove capacity or force a single global read port.

Three important composition facts:

1. Production top wires M directly to C in the SAME cycle, so their layer,
   ordinal, valid and fire are equal there.  C remains independently driven in
   isolated wrapper tests, including mismatched/stale work.  Removing C's
   checks or silently assuming input equality inside the generic wrapper is
   not selected.
2. Production S enters B through the existing exclusive sidecar ingress.
   When S is valid, the legal environment excludes the hot sidecar offer,
   so B receives S's exact fields.  The wrapper still supports independently
   supplied B.  A malformed B address cannot be ignored just because a valid
   S exists.  Same-bank S and B have the same ordinal after B's non-data
   shape checks pass; this is not an unconditional equality for arbitrary B.
3. F and B can refer to different record ordinals: payload fragment progress
   and sidecar progress are tracked separately.  No common read index follows
   merely from both addressing the same stage.

## Why M/S/O sharing is valid per bank

For a fixed bank b:

- M requires state RESERVED/FILLING and materializerActive[b] false.
- S requires state RESERVED/FILLING and materializerActive[b] true.
- O requires observationActive[b].  The state-machine invariant is
  observationActive[b] implies stageState[b] == EMPTY.

M and S are therefore mutually exclusive; O excludes both.  O also excludes
C/F/B effective legal validation for that bank, but those readers' arbitrary
input and ready behavior makes their reuse a separate implementation problem.

The observation invariant follows from publication setting EMPTY and
observationActive together, the claim guard forbidding reuse while observation
is active, admission forbidding mutation during observation, and live-stage
guards on filling/writing paths.  Final fill acknowledgements must complete
before COMPLETE/write/publication; a pending old fill acknowledgement cannot
legally bypass that ordering.  A future RTL implementation must assert this
invariant rather than rely only on this source review.

An exhaustive abstract phase check covered 256 combinations of stage, active,
observation, commit and remaining eligibility bits, under that invariant,
and 2,048 subsets of global consumer selection.  No same-bank M/S/O conflict
exists.  Address-identity checks covered all 36 x 64 addresses for all three
consumers (6,912 cases).  This is a conditional combinational proof, not a
whole-RTL reachable-state/formal result or a production cross-bank witness.

## RD1 dataflow

For each bank independently:

```text
M request: M.valid && M.layer == bank     -> M.ordinal
S request: S.valid && S.layer == bank     -> S.ordinal
O request: memberObservationValid
           && observationLayer == bank -> observation ordinal
                 |
                 | at most one request; no ready/fire-based grant
                 v
          one selected ordinal
                 |
       membershipEntries(bank)(ordinal) : 79-bit record
                 |
     existing M/S/O bank selections and field extraction
```

Use a one-hot ordinal merge, not a new priority owner.  With no request the
bank address may default to zero; no consumer then has a valid record from
that bank.  Each consumer's existing global priority, valid equation, header
association and ready remain unchanged.  Three different banks can still serve
three requests in one cycle in a combinational reader unit test; this does not
assert reachability of that traffic in the one-group production contour.

Only M's payload_ref uses the shared member record.  Its pending-suffix data
continues through the existing independent read.  S/O use position+payload.
No new module boundary is necessary: use an inline Chisel helper/Vec wiring
so the existing generated source/port structure can remain intact.

## Stability, invalid data and writes

The sharing must remain selected for the entire valid interval, including
ready-low cycles.  Request selection is based on source validity/state, never
on fire.  Existing membership immutability and observation reuse guards keep
the selected record stable under the existing contract.  This change does not
try to repair or redefine any pre-existing global selector behavior.

M/S/O bits when their source valid is low are not promised bit-for-bit equal
to the old inactive mux outputs.  The implementation must not change any
valid-cycle bits, continuous ready output, accepted event or held-valid bits.
It must also keep both reconstructed entry_id outputs connected and retain the
ongoing synthesis driver-preservation policy.

Admission is a one-edge write to the accepted bank/ordinal; the table remains
Reg(Vec(...)).  Reads retain pre-edge register semantics.  A newly admitted
member becomes visible through the existing presence bits on the next cycle;
do not add same-cycle data forwarding.  Reads of prior accepted members can
overlap a different-ordinal admission.  No accepted admission overwrites an
already present ordinal, and no claim may recycle an observing bank.

## Validation and screening before integration

1. Reader-unit equivalence for all three consumers, all banks/ordinals,
   sentinel/random records and simultaneous requests on different banks.
2. Same-bank M/S exclusion, O -> EMPTY, and PopCount(local requests) <= 1
   assertions; exercise pending/fault/reset transitions and ready-low holds.
3. Full 64-member and tail-page cases, non-contiguous logical positions,
   admissions while earlier records are read, and no read/write forwarding.
4. Independently driven C/F/B mismatch/stale tests remain unchanged; ordinary
   admissions without a pending binding still publish correctly.
5. Keep the current production M->C and S->B wiring, fail-closed exclusive
   ingress and R2 eligibility/arbitration unchanged.
6. Compare original and candidate read networks in a small synthesis harness
   at the actual 36 x 64 geometry.  Measure combinational area, mux/decode
   structure and delay; use identical output observability on both sides.
7. Only a successful candidate proceeds to focused Chisel tests, the existing
   57-test regression, generated-source/proxy gates and integration with the
   verified driver repair.  Complete paired DC remains the final cost/timing
   evidence.

The 366,336 stored bits are unchanged by RD1.  A smaller number of source-level
read expressions or a large baseline cone is not evidence of area savings;
DC may already share part of the logic and the added request/address muxes may
offset some benefit.  Selection of RD1 authorizes its plan only in this batch;
no production RTL or new synthesis experiment is launched here.
