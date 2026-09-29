# Gate-A1 provenance declaration — pending-delivery realization closure

## Status and scope

**Status:** `complete_architecture_closure; pre_rtl_only`.

This record binds the specification revision that closes pending delivery as
`direct_pending_endpoint_v1`.  It preserves the Gate-A0 freeze as a historical
input snapshot and does not replace, amend, or reclassify any accepted A4
report.  The closure is a reviewable architecture decision, not a performance
DSE result or evidence that a physical direct endpoint was selected by A4.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `eb866758685912800bd6f06a9ff7402694bb5b1c0bf42a1d8fe7afa65835798c` | Specification with the Gate-A1 endpoint closure. |
| `analysis/architecture_gate_a1_pending_delivery_realization_closure.md` | `8db961ef1cd75c826d7c13c245df654bd6141152613b88beaea6f542a393f780` | Candidate analysis and selected finite interface. |
| `analysis/architecture_gate_a0_provenance_freeze.md` | `589b9ba402140b1a3ae08354979d852fec30963721d3f3efe6336c6cb4931c31` | Historical local input declaration. |
| `analysis/architecture_gate_a0_remote_report_verification_20260928.md` | `91ceb6a488f4a10a414582ac45aaef744b091e37d185e8430ca3f14d36574b32` | Historical remote accepted-report verification. |
| `kvpress/route_a_attention.py` | `370224989113a83ff7ff9daa66076ab5957665920366dbe5d1b18bc1b319cd8e` | Functional reference with canonical `hot -> pending -> packed` source order. |
| `analysis/route_a4131_payload_organization_contract.md` | `fc58807647f10d7a8492652bb305bbc9a3614e360f41c9455b636eca454c3408` | P3 pending-HBM and transient-staging mapping. |
| `analysis/route_a4134_page_source_reuse_interface_contract.md` | `6e750d68cc1490d6c43f0a38fb2d1409ebf0e4d4ab104f082491956071178d61` | Logical direct pending delivery and GQA action contract. |
| `analysis/route_a4135_target_payload_service_cost_contract.md` | `4136a04a237be41dda1b189d2cc3ace88354a9d82383ef52a08e05ac29c59bad` | Separate direct-pending traffic accounting and unobserved issue ordering. |

The A4 report bytes named by the Gate-A0 remote verification record remain the
accepted inputs.  Gate-A1 introduces no additional report, trace, workload,
GPU execution, or A4.14.x result.

## Closure boundary

The selected direct endpoint is constrained to the pending-HBM authoritative
source, frozen FIFO ordering, no S2 allocation, no separate pending buffer,
and no additional persistent payload residency.  Its controller, physical
transport, macro, ports, clock, overlap, area, latency, and dynamic energy
remain unestimated and subject to the A4.14.1 omitted-cost budget at later
implementation gates.
