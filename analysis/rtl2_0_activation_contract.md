# RTL2.0 — Producer/consumer activation inventory

**Status:** `inventory_complete; rtl2_0a_to_0e_interface_owner_closed; behavior_not_started; hierarchy_interface_amendment_review_required`.

This is the first executable planning slice of RTL2.  It creates a
machine-readable activation inventory and validates it with no-model Python
tests.  It does not alter the top-level Chisel wiring, activate an inert
carrier, move payload data, create functional storage, select a numerical R4
implementation, or change the frozen Route-A architecture contract.

The companion [machine-readable manifest](rtl2_0_activation_manifest.json)
has 14 required scoreboard events and 20 concrete carrier records.  Every
record names a producer, consumer, identity fields, later activation phase,
and either its current safe wiring state or a specific required amendment.
The planned versioned RTL2 scoreboard schema is intentionally not created yet:
it must be created immediately before the first behaviorally active carrier,
not populated with events that this RTL cannot yet emit.

## Resolved existing ownership

The manifest confirms that the following existing paths retain their frozen
owners: R2-to-R1 accepted requests; R1 transaction identity and write
terminals; R6-to-R3 retained admission context; R3-to-R5 nested publication
visibility; R3-to-R6 post-publication observation; R4-to-source consumer
commit demultiplexing; R5 reclaim candidate and allocator release; and R6
retirement acknowledgement.  Existing wiring remains either control-only or
reclaim-only until its recorded RTL2 phase.

It also makes the RTL2.2 distinction executable at planning level:
`write_commit` must map to both the R3 packed-write terminal and the R5
descriptor terminal.  A validator rejects a collapsed untyped write path.
Likewise, `metadata_publish_commit` must retain both its existing R3-to-R5 and
R3-to-R6 effects; neither effect alone represents the atomic boundary.

## Required review before behavioral activation

The inventory found that production dataflow cannot be safely enabled merely
by replacing top-level ties.  The following amendments require explicit review
before their associated carrier is activated:

| Amendment | Why it is necessary | Explicitly not authorized here |
|---|---|---|
| `hot_payload_egress_interface` | **Closed at interface/owner level by [`rtl2_0a_payload_materialization_contract.md`](rtl2_0a_payload_materialization_contract.md).** It now names frontend materialization plus hot maturity egress, while behavior remains deferred. | Duplicating hot residency or selecting a physical hot macro. |
| `admission_publication_ingress_adapter` | **Closed at interface/owner level by [`rtl2_0b_admission_group_builder_contract.md`](rtl2_0b_admission_group_builder_contract.md).** It is a finite 64-member group builder, not a fanout; Chisel behavior remains deferred. | Re-deciding admission, publishing metadata, or owning authority. |
| `r2_multi_producer_ingress_interface` | **Closed at interface/owner level by [`rtl2_0c_r2_ingress_delivery_context_contract.md`](rtl2_0c_r2_ingress_delivery_context_contract.md).** Six semantic classes and producer-originated immutable ordering now feed R2 without an external selector; Chisel behavior remains deferred. | A top-level selector, a second R1 path, or a new scheduler. |
| `typed_delivery_router` | **Exact endpoint descriptors are closed by [`rtl2_0d_typed_delivery_router_contract.md`](rtl2_0d_typed_delivery_router_contract.md).** A separate registry resolves the opaque ref; the router may only preserve the typed read fragment or final write terminal to that one endpoint. Router behavior remains deferred. | Generic response reinterpretation, data loss, authority transfer, S2 READY creation, or a second memory port. |
| `r3_r5_durability_prerequisite_interface` | **Exact aggregate durability prerequisite is closed by [`rtl2_0e_r3_r5_durability_prerequisite_contract.md`](rtl2_0e_r3_r5_durability_prerequisite_contract.md).** Only R5 aggregates `new_page` and conditional `tail_link`; R3 treats accepted success as necessary but insufficient for the existing nested commit. Behavior remains deferred. | Visibility outside `metadata_publish_commit`, R3 durability reconstruction, authority transfer, duplicate commit, or page free. |
| `source_service_packet_adapter` | Owner-produced hot/direct/S2 facts require canonical packetization and `SourceInstance` transport to R4. | Top-generated source plan, numeric merge, or source-reorder claim. |
| `r4_result_stub_provider` | RTL2.5 needs a verification-only matching result/fault source. | An FP/exp/online-merge or latency claim. |

Accordingly, RTL2.0 is deliberately **not PASS**.  This is the intended
fail-closed result of the RTL2 phase contract: a new producer, hierarchy child,
or interface endpoint cannot be quietly introduced as an implementation
convenience. RTL2.0a through RTL2.0e resolve only bounded interface/owner
boundaries; no behavior should begin until the remaining source-service and
R4-stub amendments have been reviewed and accepted as a bounded
hierarchy/interface closure.

## Validation

Run from the repository root:

```bash
.venv/bin/python tools/validate_rtl2_activation_manifest.py --help
.venv/bin/python -m pytest tests/test_rtl2_activation_manifest.py -q
```

The test intentionally injects a missing amendment, an untyped write-terminal
mapping, a collapsed publication mapping, and a premature PASS disposition.
It is pure-software schema validation, not a model/GPU run, Chisel functional
test, dataflow proof, timing/throughput result, PPA claim, or new A4 DSE.
