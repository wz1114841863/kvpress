# MR-2 M2 bounded production-control owner

**Status:** bounded production-control ownership is implemented.  The later
prepare/resolution extension has directed-unit coverage; its current
composed-DUT/non-regression refresh remains a separate required result.  This
document does not claim M2 entry-data or production lifecycle closure.

This MR-2 sub-batch replaces `RouteAM2ReferenceProtocolProvider` only in
`RouteAMeasurementDut` with `RouteAM2ProductionControlOwner`. It is a bounded
control/provenance owner, not an M2 payload-array, macro, memory controller, or
new Route-A authority owner. The historical composition-only
`RouteAKVSubsystemTop` remains a functional skeleton and is deliberately not
changed by this batch.

## Retained ownership and accepted events

R3 remains the sole issuer of the two frozen M2 semantic members and retains
all admission, publication, fault, and authority responsibility. The new owner
receives only the exact request carrier established by
`mr2_m2_minimal_carrier_contract.md`:

- group identity: `layer`, `stage_generation`, `transaction_group_tag`, and
  member class;
- immutable group provenance: `kv_head`, `opaque_address_ref`, and `owner`.

Before R3 can issue either member, the admission/publication adapter emits one
immutable `M2GroupPrepareDeclaration` only after the existing P3 claim
acknowledgement.  The owner stores that group privately.  It reflects an OK
response only for an accepted in-range member that exactly matches this private
group. No request is accepted while a response is outstanding. R3's existing exact-response
comparison remains the fail-closed gate; this owner neither fabricates a
completion nor converts a mismatch into a successful M2 member.

## Bounded control state

For the measurement-DUT's frozen `KvHeadWidth=3` and 36-layer parameterization,
the owner contains only:

1. two equal head-control mirrors and one span-owner record per one of eight
   head-affine logical banks; and
2. a 36-entry private group reservation/completion scoreboard containing the
   prepare provenance, two accepted member bits, and an outstanding-publication
   bit needed to gate reflection.

The head member writes both mirrors together; the span member writes the span
record. A candidate can be reflected only after both matching members have
completed for its `(layer, generation, tag)`. Candidate reflection locks the
private reservation but does not release it.  `RouteAM2P3Wrapper` then emits a
Valid-only `M2GroupPublicationResolution` on the actual accepted R3/R5
publication acknowledgement; that fanout cannot backpressure the
acknowledgement.  A matching Published *or* Fault resolution releases the
private reservation.  The candidate's real publication handshake and
linearization remain R3/R5's existing path; the M2 owner only supplies the
pre-existing request/response and candidate/reflection protocol.

This extension is **control/provenance only**.  It does not carry a
`MetadataAppend` operand, allocate a span, mutate a 128-bit M2 entry, or
provide the future two-object data prepare/commit.  Therefore it cannot by
itself satisfy the grouped data-state atomicity requirement.

## Reset, backpressure, and exclusions

Reset clears all response, candidate, bank-control, private reservation, and
group-completion state.
The response and reflected candidate remain stable under downstream
backpressure. The owner has no external fault input and does not alter the
existing R3 negative-response/fault tests.

This does **not** realize M2 update data, storage contents, queue/staging
dynamic access, physical address mapping, macro ports, latency, timing, area,
energy, or PPA. Those remain the later M2 array-only/wrapper realization work;
the control, response, publication, reset, and wrapper-peripheral logic
introduced here must remain inside a future candidate DUT rather than being
black-boxed with an array.

## Verification record

The final directed remote run used the user-local offline EDA-server
Chisel/Verilator platform at the source state of this batch:

| Scope | Result | Evidence |
|---|---|---|
| private prepare, exact two-member gating, wrong-tag/no-early reflection, response stability, out-of-range/reset failure, cross-immutable-group rejection, and Published/Fault resolution cleanup | **6/6 passed** | `RouteAM2ProductionControlOwnerSpec` and `RouteAAdmissionPublicationIngressAdapterSpec`, `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_coord_p1_20261022.log`, exit 0 |
| prepare/resolution-integrated production R3/R5/R6 packed path through terminal/reclaim, hot-plan path, stale packed-read rejection, and direct candidate cancellation/fault | **4/4 passed** | `RouteAMeasurementDutR3Spec`, `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_coord_p2_retry_20261022.log`, exit 0 |
| independent Full-KV/Route-A top elaboration, owner-chain source check, and bounded B2c structural guard | **3/3 passed** | `DualMeasurementDutStructuralSpec`, `mr2_m2_coord_p2_retry_20261022.log`, exit 0 |
| historical R1/R2/R5/R6 fixed-stall reclaim witness after B2c test-only tie-offs | **1/1 passed** | `RouteAFairReclaimIntegrationSpec`, `mr2_m2_coord_p2_retry_20261022.log`, exit 0 |

The prepare/resolution extension is **composed-DUT PASS** for the scoped eight
directed checks above.  Its current serial W0/MR-1A/MR-1B/M2 refresh also
passed: eight suites, 33/33 tests, exit 0, in 52 minutes 03 seconds at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_nonreg_current_20261022.log`.
That selected set covers Full-KV lifecycle/fault/reset, four-consumer
completion, packed activation, both-DUT structural guards, direct-pending,
R3 pack-read/reconciliation, M2 control, and admission ingress.

This verification closes neither the missing production `MetadataAppend`
carrier nor grouped entry-data atomic commit.  It proves that the new
control-only prepare/resolution state has not regressed the listed functional
paths; production M2 entry integration and array-only boundary remain blocked
as stated in the M2 runtime-semantics decision.

This is functional Chisel evidence only; it does not establish an M2 array
realization, macro, wrapper timing, synthesis, area, energy, or PPA.
