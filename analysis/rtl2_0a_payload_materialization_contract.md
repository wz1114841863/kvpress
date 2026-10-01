# RTL2.0a — Payload materialization and hot maturity egress

**Status:** `interface_owner_closed; behavioral_storage_and_dataflow_pending`.

This closure resolves the first RTL2.0 review finding: `payload_ref` alone is
not K/V data, and the hot owner previously had no ingress or maturity-egress
contract.  It freezes only the logical transactions needed to materialize one
Qwen-anchor K/V record at the hot owner and later obtain its retained maturity
copy for P3 staging.  It does not implement those transactions in Chisel.

The machine-readable companion is
[`rtl2_0a_payload_materialization_manifest.json`](rtl2_0a_payload_materialization_manifest.json).

## Logical data boundary

One anchor record is 512 B of K+V and is carried as exactly eight ordered 64-B
fragments with a 512-bit logical data field.  The 8-B position sidecar remains
represented by the immutable logical position association; neither it nor the
payload selects an SRAM macro, a physical port count, an HBM command, address,
or service schedule.  `payload_ref[63:0]` remains an opaque frontend handle.

The three decoupled transactions are:

```text
frontend_payload_materializer -> hot owner
    frontend_hot_payload_fragment

admission-publication ingress -> hot owner
    hot_mature_payload_read_request

hot owner -> admission-publication ingress
    hot_mature_payload_fragment
```

Only the hot owner owns hot payload residency/provenance.  The materializer is
an environment transport endpoint; the future admission ingress adapter holds
only a transient request/group association.  None of these carriers transfers
hot/pending/packed authority or decides admission.

## Ordering and fail-closed boundary

For every accepted arrival, the environment must complete the matching ordered
eight-fragment materialization before it offers the immutable maturity
disposition.  This is an explicit environment assumption, not a timing or
throughput claim.  Later hot-owner behavior must reject a stale, duplicate,
out-of-order, mismatched-identity, or mismatched-`payload_ref` fragment.

An egress request is legal only for the matching retained maturity and is
one-shot.  Its response has the exact group tag/member ordinal and is a
transient non-authoritative copy.  It cannot by itself create a P3 claim,
issue R1 work, make a page visible, publish metadata, release a source, or
alter a mask/disposition.

## Explicit deferrals

RTL2.0a does not add a Chisel port, functional payload backing, P3 staging
write, R2 candidate, R1 request, page allocation, metadata publication, or
source packet.  Those require the next reviewed closure:
`admission_publication_ingress_adapter`, now correctly understood as a finite
group builder rather than a simple fanout.  A later functional-hot wrapper may
use simulation/reference backing only until the separate memory-realization
gate; it must never be represented as a selected SRAM implementation.

## Validation

```bash
.venv/bin/python tools/validate_rtl2_payload_materialization_manifest.py --help
.venv/bin/python -m pytest tests/test_rtl2_payload_materialization_manifest.py -q
```

This is pure-software interface-contract validation: no model/GPU, no Chisel
functional proof, no timing/throughput/PPA claim, and no new A4 DSE.
