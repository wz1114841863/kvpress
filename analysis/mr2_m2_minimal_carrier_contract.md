# MR-2 M2 minimal production-carrier contract

**Status:** implementation and bounded functional verification complete.

This narrowly closes the identity/provenance gap between the existing
pending-payload/location owner and R3's two fixed semantic M2 group members.
It does not select an M2 macro, an address format, update-data format, port
count, timing, controller, or PPA model; the M2 storage-array interior remains
a separate MR-2 item.

## Immutable facts and owners

`PendingPayloadReadBinding`, produced by the existing pending-payload/location
owner, now carries these group-scoped logical facts when it participates in a
retained R3 packing group:

| Field | Production source and scope | Prohibited interpretation |
|---|---|---|
| `m2_group_opaque_address_ref` | Immutable logical M2 mapping reference supplied by the pending-payload/location owner; every member in one accepted group must agree. | Payload reference, HBM/SRAM address, macro row, or inferred page address. |
| `m2_group_owner` | Immutable logical mapping/update-owner identifier supplied by that same owner; every member in one accepted group must agree. | R3 authority, a new source selector, residency authority, or physical owner encoding. |
| `kv_head` | Already accepted R3 claim/stage fact; it selects the frozen head-affine logical bank. | A newly chosen bank or physical banking decision. |

`RouteAAdmissionPublicationIngressAdapter` preserves the first accepted
member's two group facts and accepts later members only when they match.  It
copies them into the one `P3Claim`; `RouteAM2P3Wrapper` stores them with the
accepted stage.  R3 never derives either field from `layer`, tag, page,
payload reference, logical position, or a test fixture.

## M2 member carrier and fail-closed behavior

`M2GroupMemberRequest` and `M2GroupMemberResponse` now include the exact
`kv_head`, `opaque_address_ref`, and `owner` alongside the pre-existing
`(layer, stage_generation, transaction_group_tag, member)` identity.  R3
issues the two frozen members in the existing order and accepts a response
only when every old and new field matches its one outstanding request and the
locked stage facts.  A bad bank, opaque reference, or owner is `ready=0` and
cannot complete a member, publish metadata, or change authority.

The replaceable functional M2 endpoint reflects the extended carrier only for
legacy/test composition.  It is still excluded from the measurement DUT cost
boundary and is not the forthcoming M2 production state owner.

## Explicit non-goals and next boundary

The carrier represents only the already-frozen logical group RMW operation;
there is no M2 data/update payload at this functional boundary.  Hence this
change does not claim that M2 storage contents, mirrored writes, or queue and
staging dynamic accesses are implemented.  The next MR-2 M2 sub-batch may
replace the reference protocol endpoint with a production control owner using
this exact carrier.  Separating its array interior remains later work and may
not black-box R3's member, publication, fault, or reset control.

## Verification record

Both runs used the user-local offline EDA-server Chisel/Verilator platform at
the same local source state before this batch's commit:

| Scope | Result | Evidence |
|---|---|---|
| Carrier-directed: admission mapping agreement, R3/R5 identity propagation, and one composed measurement-DUT R3 path | 11/11 passed, `EXIT_CODE=0` | `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_directed.log` |
| W0/MR-1A/B2c non-regression plus dual-DUT structural guard | 27/27 passed, `EXIT_CODE=0` | `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_nonreg.log` |

These results are functional Chisel evidence only.  They neither replace the
M2 reference endpoint nor establish a storage realization, synthesis, timing,
area, energy, controller, or PPA result.
