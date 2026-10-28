# Paired bounded control-projection profile

**Profile ID:** `qwen3_8b_32k_s1_control_projection_v1`  
**Scope:** one Qwen3-8B / 32,768-token / one-sequence Route-A control anchor;
paired Full-KV and Route-A control projections use the identical object.

This is the explicit successor to the paired functional test profile. It is a
logical control-profile choice required before generated HDL can be considered.
It is not a deployment configuration, an SRAM/HBM realization, a clock or
frequency choice, a controller contract, a continuous-run proof, or PPA
evidence.

## Selected values and provenance

| Field group | Selected value | Basis and limit |
| --- | ---: | --- |
| Anchor geometry | 36 layers × 8 KV heads; 32K context; 64-record page; 512-bit beat; 2 S2 slots; 4 GQA consumers | Frozen A3 Qwen3-8B/32K/s1 entry profile and fixed `RouteAAnchorWidths`. |
| R5 logical pool/streams | 146,880 pages; 288 streams | Frozen A3 allocator pool and 36×8 logical head streams. This is logical state, not a macro selection. |
| R2 | 6 classes, 3-bit class code, 2 candidate slots/class, 7-bit arrival ordinal, 4-bit candidate ID, 10 predicates | Six frozen classes; two-slot bound is the already verified bounded control contour. The ordinal represents page-member order through 63; it is not an admission-policy change. |
| Core service | 3 request-kind bits, 3 destination bits, 64-bit opaque address, 10-bit count, 9-bit index, codes read/write/write-data=`0/1/2` | Existing R1 logical contract; 9/10-bit geometry supports the 512-fragment anchor. Destination code meanings remain an external typed-interface concern. |
| Pending/R5 association | 18-bit descriptor reference, 8-bit validity/generation | Directly matches the frozen R5 page-ID/generation widths; does not choose descriptor-HBM placement. |
| Delivery context | 4-bit opaque reference (16 entries) | Covers every 6×2 bounded R2 candidate slot without silently making delivery-context state a narrower capacity limit. |
| Association generations | 8-bit group tag, P3-stage generation, and source generation | Explicit finite namespaces for this bounded anchor. No continuous wrap/reuse claim follows; existing stale/reset/fail-closed contracts remain required. |
| R6 local codes | 2 event bits, 2 hot-control bits, 4 status bits, 4 tracker entries | Four event kinds, three hot controls, eleven named status values, and the A3 maximum four live reads. This is a local internal encoding, not `testOnlyAnchor` or an external protocol. |

## Deliberate non-selections

The profile does not alter pruning, admission, page size, M2 ownership,
publication, R6 authority, R2 order, direct-pending's single-record scope, or
the Full-KV baseline. It also does not select:

- a memory macro, physical port count, latency, banking, or clock;
- an external memory controller/PHY/CDC/address mapping;
- R4 numeric arithmetic, partial-state placement, or an attention PE; or
- S2/lifecycle common-cost cancellation.

All wrapper, external memory, R4 numeric, outer partial-provider, and
integration-shell rows remain nonzero and unestimated as recorded by
`control_projection_p1_bom_delta_20261028.json` and the prior realization
records.

## Acceptance checks

`RouteASynthesisControlProjectionProfileSpec` checks that the Scala profile is
complete, has the exact bounded capacity/width selections, and does not import
`RouteAR6Encoding.testOnlyAnchor`. A later HDL-emission check must explicitly
pass `RouteASynthesisControlProjectionProfile.parameters`; the generators keep
their generic required-parameter argument and therefore cannot silently fall
back to this or a test profile.
