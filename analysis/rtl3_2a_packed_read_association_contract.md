# RTL3.2-A — packed-read association-owner closure

**Status:** `complete_executable_association_owner_contract_pre_rtl3_2_payload`.

RTL3.2-A resolves the RTL3.0 `packed_read_association_owner` stop at the
interface and executable-semantic level. It names one owner,
`route_a_packed_read_association_owner`, for joining already-authorized facts
before a packed page may enter the existing R2/R1 typed read path.

This is a pure-software, event-level contract and reference. It adds no Chisel
production module, top wiring, payload transfer, S2 deposit, sidecar transport,
page lookup implementation, scheduler, memory controller, or physical claim.
The companion machine-readable authority is
[`rtl3_2a_packed_read_association_manifest.json`](rtl3_2a_packed_read_association_manifest.json).

## Why the RTL2.6 adapter cannot be promoted

`RouteARTL26PublicationS2Association` is explicitly a test-only join: its
verification ingress supplies attention identity, S2 slot and source generation,
and it neither generates `PackedS2ReadWork` nor reads live R3/R5 state. It
therefore remains historical verification evidence and is not this owner.

In particular, `PublicationCommitObservation` reports that publication occurred;
it is not a durable future read permission. A later attention request requires
a fresh, identity-bound **live publication authorization** from R3/M2. The new
contract makes that distinction explicit instead of caching or replaying a
publication event as a second metadata authority.

## Sole owner and input grants

`route_a_packed_read_association_owner` is the sole cross-owner association
owner. It has no authority to select a source/page, allocate an S2 slot, choose
R2 priority, reconstruct descriptor fields, or maintain a second page/metadata
table. It accepts the following immutable grants in any event order and emits
nothing until their exact join is complete:

| Grant | Fact owner | Required fields | Owner limitation |
|---|---|---|---|
| `PackedSourceDemand` | `upstream_preselected_packed_source_boundary` | R6/R1 transaction identity, preselected `PageRef`, opaque R2 arrival/candidate/eligibility/destination facts | The upstream boundary decides the source/page before this module. This module may only reject or bind it; it is not a scheduler. |
| `PublicationReadAuthorization` | `route_a_m2_p3_wrapper` (R3/M2) | identity, exact `PageRef`, group tag, valid-record count, `packed_authoritative=1` | Must represent current publication state, not a replayed commit event; it does not transfer authority. |
| `DescriptorLocationGrant` | `route_a_page_manager` (R5) | identity, exact `PageRef`, payload/sidecar opaque handles, valid-record/sidecar-record counts, `live_reference_held=1` | R5 retains descriptor/page ownership and the live reference. The association owner cannot inspect a descriptor image or infer an address. |
| `S2FillLease` | `route_a_s2_gqa_source_wrapper` | identity, exact `PageRef`, S2 slot, source generation, `requires_sidecar=1` | S2 selects/reserves the slot and generation. This owner has no S2 allocator or release policy. |

The upstream demand is a named integration boundary, not a new scheduler
implementation. RTL3.2-A freezes the fact that a selected page must be passed
explicitly; it does not decide how an attention frontend selects that page.

## Exact join and output

The owner rejects any missing, duplicate, stale, non-authoritative, or
mismatched grant. Exactness requires:

```text
demand.identity == R3.identity == R5.identity == S2.identity
demand.PageRef  == R3.PageRef  == R5.PageRef  == S2.PageRef
R3.valid_records == R5.valid_records in [1, 64]
R5.sidecar_records == R5.valid_records
R5.live_reference_held == 1
S2.requires_sidecar == 1
```

Only after this join may the association owner issue one
`R2PackedReadAllocationRequest`. Its `arrival_ordinal`, `candidate_id`,
`eligibility_snapshot`, and destination are opaque copies of the demand;
association logic never changes them. Its expected fragment count is the
already frozen `valid_records * 8` 64-B fragments.

After the existing R2 delivery-context registry acknowledges one context, the
owner emits one `PackedS2ReadWork` equivalent with that context, exact page,
slot/generation, payload handle, valid-record count, and an explicit sidecar
requirement. The sidecar handle/count are transported as an obligation only:
RTL3.2-A does not select its transport or mark S2 sidecar-complete.

```text
preselected demand + live R3 authorization + live R5 grant + S2 lease
                    -> route_a_packed_read_association_owner
                    -> existing R2 context allocation
                    -> existing R2/R1 typed packed read
                    -> later RTL3.2 payload/sidecar endpoint work
```

No `PackedS2ReadWork` is generated directly by the top or testbench ingress
after this owner is active.

## Invalidation, fault, reset, and lifetime

- R5 invalidation may cancel an association only before it has issued to R2.
  Once issued, durable invalidation/free must wait for the terminal release of
  the R5-held live reference; this preserves R5's existing
  invalidation-before-free rule.
- A successful or fault terminal produces only an owner-returned release
  observation to R5/S2. It does not imply S2 READY, GQA release, R4 partial,
  attention success, metadata publication, or authority transfer.
- Destructive reset clears incomplete/issued association state and gates new
  grants until init. R1 remains the sole external stale-response suppressor;
  the association owner does not create a reset epoch wire or reinterpret an
  old grant as new work.
- The reference has no FIFO depth, arbitration order, outstanding count,
  cycle, latency, service-rate, or progress claim. Legal ready-low may delay
  a grant/R2 acknowledgement only; it cannot mutate or substitute fields.

## Executable verification

`PackedReadAssociationReference` directed tests cover:

1. all four grants arriving in arbitrary order, followed by exact R2 request,
   context acknowledgement, typed work and terminal release;
2. page/generation/population mismatches failing closed without R2 work;
3. invalidation before issue cancelling work, versus issued work requiring
   terminal release before invalidation;
4. reset gating and removal of an incomplete association.

Run the no-model reference checks with:

```bash
.venv/bin/python -m pytest -q tests/test_rtl3_2a_packed_read_association_reference.py \
  tests/test_rtl3_2a_packed_read_association.py
.venv/bin/python tools/validate_rtl3_2a_packed_read_association.py
```

## Evidence boundary and next authorization

RTL3.2-A authorizes only the subsequent implementation of this named
association interface and its integration with the already frozen R2/R1 typed
read contract. It does not yet authorize a packed-to-S2 payload/sidecar path
until the implemented owner is bound and verified against the RTL3.1 functional
memory environment.

It makes no model/GPU, accuracy, HBM/SRAM macro, controller, CDC, timing,
throughput, area, energy, PPA, numeric RTL, source scheduler, pruning,
admission, atomic-publication, or new A4 DSE claim.
