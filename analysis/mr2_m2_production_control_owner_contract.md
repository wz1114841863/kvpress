# MR-2 M2 bounded production-control owner

**Status:** implementation and bounded composed-DUT verification complete.

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

It reflects an OK response only for an accepted in-range request. No request is
accepted while a response is outstanding. R3's existing exact-response
comparison remains the fail-closed gate; this owner neither fabricates a
completion nor converts a mismatch into a successful M2 member.

## Bounded control state

For the measurement-DUT's frozen `KvHeadWidth=3` and 36-layer parameterization,
the owner contains only:

1. two equal head-control mirrors and one span-owner record per one of eight
   head-affine logical banks; and
2. a 36-entry group-completion scoreboard containing the two accepted member
   bits and immutable group provenance needed to gate reflection.

The head member writes both mirrors together; the span member writes the span
record. A candidate can be reflected only after both matching members have
completed for its `(layer, generation, tag)`. Candidate reflection consumes
those two completion bits, so it cannot emit a second publication request.
The candidate's real publication handshake and linearization remain R3/R5's
existing path; the M2 owner only supplies the pre-existing request/response and
candidate/reflection protocol.

## Reset, backpressure, and exclusions

Reset clears all response, candidate, bank-control, and group-completion state.
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
| exact head-plus-span commit, wrong-tag/no-early reflection, output stability, out-of-range/reset failure, and cross-immutable-group rejection | 3/3 passed | `RouteAM2ProductionControlOwnerSpec` in `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_final_directed.log` |
| production R3/R5/R6 packed path through terminal/reclaim, hot-plan path, stale packed-read rejection, and direct candidate cancellation/fault | 4/4 passed | `RouteAMeasurementDutR3Spec` in the same log |
| admission provenance and atomic-publication non-regression | 7/7 passed | `RouteAAdmissionPublicationIngressAdapterSpec` plus `RouteAR3R5PublicationSpec` in the same log |

The combined run is 4 suites, 14/14 tests passed, `EXIT_CODE=0` (18 minutes,
5 seconds). Its follow-on W0/MR-1A/B2c non-regression is 6 suites, 27/27
passed, `EXIT_CODE=0` (51 minutes, 52 seconds), at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_nonreg.log`.
That run covers Full-KV baseline-local lifecycle/fault/reset, shared
four-consumer/S2 and packed activation, dual-DUT structural guards,
direct-pending, and pack-read paths.

This is functional Chisel evidence only; it does not establish an M2 array
realization, macro, wrapper timing, synthesis, area, energy, or PPA.
