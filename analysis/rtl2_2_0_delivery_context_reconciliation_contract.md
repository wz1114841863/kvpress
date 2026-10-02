# RTL2.2.0 — delivery-context provenance and interface reconciliation

**Status:** complete; no behavioral RTL activated.

RTL2.2.0 is a versioned, no-behavior reconciliation between the frozen RTL2.0c
R2 ingress/context contract and the frozen RTL2.0d typed delivery-router
contract. Its machine-readable authority is
[`rtl2_2_0_delivery_context_reconciliation_manifest.json`](rtl2_2_0_delivery_context_reconciliation_manifest.json).

## Historical correction without rewrite

The historical RTL2.0c manifest records `pack_read` as `future_rtl2_1b`.
RTL2.1 deliberately activated only packed **write** and descriptor durability/
publication behavior; it did not activate read-fragment delivery. RTL2.2.0
therefore records the correction:

```text
historical annotation: pack_read -> future_rtl2_1b
reconciled activation: pack_read -> rtl2_2
```

The original RTL2.0c manifest is not edited. This record SHA-256 binds it, the
RTL2.0d typed-router manifest, and the RTL2 scoreboard schema, so later work
cannot silently reinterpret their provenance.

## Frozen RTL2.2 interface boundary

R2 remains the sole arbitration/eligibility/FIFO/credit/read-rotation owner;
the delivery-context registry remains the sole opaque-reference allocation and
reuse-exclusion owner; the typed router may only forward a registry-validated
descriptor. The top may only compose these owner-produced carriers.

Typed read fragments freeze the common identity fields:

```text
delivery_context_ref, transaction_identity, reset_epoch,
candidate_class, target_kind, target_identity_generation,
fragment_index, last, status, data_512b
```

The four frozen read targets remain `p3_pending_read`, `s2_full_fill`,
`s2_packed_fill`, and `direct_pending_read`. Typed write terminals remain
separate (`packed_write_terminal`, `descriptor_maintenance_terminal`) and
retain RTL2.1 completion ownership.

## Explicit deferrals

RTL2.2.0 authorizes neither payload deposition nor source-service behavior.
Only `pack_read` has the later RTL2.2 **transport-only** activation slot.
`s2_packed` and `direct_pending` producers remain deferred to RTL2.3
functional-storage endpoints; the Full-KV adapter is not Route-A production
activated. `fragment_deliver` remains a declared scoreboard vocabulary until
the later router binds an owner-emitted event.

No M2/P3/S2/direct physical storage, SRAM macro, controller, port count,
clock, timing, throughput, energy, area, PPA, model/GPU, numeric, or new A4
DSE claim is made.

## No-model preflight

```bash
.venv/bin/python tools/validate_rtl2_2_0_delivery_context_reconciliation.py --help
.venv/bin/python -m pytest tests/test_rtl2_2_0_delivery_context_reconciliation.py -q
```
