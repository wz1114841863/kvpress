# RTL2.0c — R2 multi-producer ingress and delivery-context ownership

**Status:** `interface_owner_closed; behavioral_r2_registry_router_pending`.

This closure preserves R2 as the sole owner of candidate eligibility, FIFO
predecessors, credit, within-class oldest selection, read rotation, and
grant-on-R1-accept.  It prevents a top mux or producer-side adapter from
quietly becoming a second scheduler.

The machine-readable record is
[`rtl2_0c_r2_ingress_delivery_context_manifest.json`](rtl2_0c_r2_ingress_delivery_context_manifest.json).

## Logical class ingress

The existing six semantic classes remain distinct logical producer endpoints:
`s2_full`, `s2_packed`, `direct_pending`, `pack_read`, `pack_write`, and
`descriptor_maintenance`.  This is not a decision about physical input ports
or FIFOs.  Each producer creates immutable `SourceCandidate` ordering fields
and obtains an opaque context reference before presenting the candidate.

If multiple candidates appear at one abstract acceptance opportunity, only R2
may apply the existing predicates and `(arrival_ordinal, candidate_id)` rule.
The top and every producer/adapter are prohibited from selecting among them.
Descriptor maintenance remains R5's single-fragment FIFO-ordered write class
through the same R1 path and never joins the read rotation.

## Delivery-context registry

`route_a_delivery_context_registry` is a future integration-only child that
owns one immutable association per presented candidate:

```text
producer allocates context -> opaque ref bound into candidate -> R2/R1
    -> R2 returns unchanged ref with response -> typed router asks registry
    -> registry emits exactly one typed target descriptor -> target accepts
    -> ref may be released
```

The registry owns no payload, page/source/authority state, R1 request-ID
allocation, terminal status, R2 FIFO/credit/cursor, scheduler, or arbitration.
It only keeps the target identity/generation, ordinal/last rule, operation
kind, and reset-epoch association needed to reject stale or mismatched
responses.  R2 never decodes the opaque ref; the later typed router cannot
reconstruct a target from response fields.

No Chisel behavior is introduced in RTL2.0c.  RTL2.1b may add reviewed R2
class-ingress and registry interfaces for the R3 pack-write producer; RTL2.2
may later add the router that consumes registry-resolved target descriptors.

Validation:

```bash
.venv/bin/python tools/validate_rtl2_r2_ingress_delivery_context_manifest.py --help
.venv/bin/python -m pytest tests/test_rtl2_r2_ingress_delivery_context_manifest.py -q
```
