# Analysis documentation index

## Current Route-A entry

This is the navigation page for the active KVzap Route-A research track. It
reduces the number of documents that must be read for current work without
deleting or rewriting frozen evidence.

| Read order | Living document | Role |
|---:|---|---|
| 1 | [`../AGENTS.md`](../AGENTS.md) | Repository rules, frozen boundaries, and claim restrictions. |
| 2 | [`../RESEARCH_CONTEXT.md`](../RESEARCH_CONTEXT.md) | Current project status and research positioning. |
| 3 | [`../KVZAP_ARCHITECTURE_PATH.md`](../KVZAP_ARCHITECTURE_PATH.md) | Longitudinal architecture route and stage transitions. |
| 4 | [`../TRACE_SCHEMA.md`](../TRACE_SCHEMA.md) | Continuous trace/event-schema record and trace-to-model mapping. |
| 5 | [`route_a_research_plan.md`](route_a_research_plan.md) | Continuous Route-A plan/progress record through A4.14 and Gate A. |
| 6 | [`architecture_spec.md`](architecture_spec.md) | **Current technical authority**: frozen pre-RTL interface contract. |

**Current disposition:** A4.11--A4.14 research DSE is closed; Reviewer-02
passed the R1--R6 architecture cross-closure; Gate-RTL0 passed and RTL1
owner-local control is complete. RTL1-I1--I4 have subsequently closed safe
start/empty retirement, retained-record publication association,
source-instance/R6 completion, and R5 reclaim through the unique R2/R1 path;
RTL1-V subsequently closed the remaining bounded verification/scoreboard
bindings. RTL2.0 has now closed its seven pre-behavior producer/interface
amendments, passed cross-owner completion review, and frozen a versioned
scoreboard-event schema. RTL2.1a--RTL2.1c atomic-publication behavior and
RTL2.2 read/write delivery prerequisites are implemented and directed tested.
RTL2.3.0--.3 plus C1--C5 close read-endpoint preparation and structural R4
packet ingress, but RTL2.3 is still partial: C6--C9 must bind a non-top
source-plan producer, source-owner packet service, four-consumer release, and
one top-composed endpoint path. RTL2.3-R records the active event-phase map;
the next work remains functional control/dataflow closure—not PPA, controller,
native-HBM, numeric realization, or performance work.

## Current architecture and verification records

Read these only when the corresponding level of detail is required:

| Need | Primary record |
|---|---|
| Current interface, frozen/parameterized/unestimated fields, omitted-cost constraints | [`architecture_spec.md`](architecture_spec.md) |
| Gate-A final cross-closure decision | [`architecture_gate_a_reviewer_02.md`](architecture_gate_a_reviewer_02.md) |
| Cross-closure matrix and integration amendments | [`architecture_gate_a_pre_reviewer_02_integration_audit.md`](architecture_gate_a_pre_reviewer_02_integration_audit.md) |
| Exact byte bindings for the final review | [`architecture_gate_a_reviewer_02_provenance_freeze.md`](architecture_gate_a_reviewer_02_provenance_freeze.md) |
| Route-A RTL/profile anchor | [`architecture_gate_a3_plan.md`](architecture_gate_a3_plan.md) and `architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` |
| Gate-RTL0 hierarchy and sole-owner split | [`rtl_entry_hierarchy_owner_contract.md`](rtl_entry_hierarchy_owner_contract.md), [`rtl_entry_interface_manifest.json`](rtl_entry_interface_manifest.json), and [`rtl_entry_hierarchy_owner_provenance_freeze.md`](rtl_entry_hierarchy_owner_provenance_freeze.md) |
| Gate-RTL0 logical port/parameter matrix | [`rtl_entry_port_parameter_contract.md`](rtl_entry_port_parameter_contract.md), [`rtl_entry_port_parameter_provenance_freeze.md`](rtl_entry_port_parameter_provenance_freeze.md), and `tools/validate_rtl_entry_interface_manifest.py` |
| Gate-RTL0 assertion/scoreboard/coverage plan | [`rtl_entry_assertion_verification_contract.md`](rtl_entry_assertion_verification_contract.md) and [`rtl_entry_assertion_matrix.json`](rtl_entry_assertion_matrix.json) |
| RTL1-V executable verification closure | [`rtl1_v_verification_completion_contract.md`](rtl1_v_verification_completion_contract.md), [`rtl1_v_scoreboard_event_schema.json`](rtl1_v_scoreboard_event_schema.json), and [`rtl1_v_provenance_freeze.md`](rtl1_v_provenance_freeze.md) |
| RTL2 production transaction/dataflow activation plan | [`rtl2_phase_contract.md`](rtl2_phase_contract.md) |
| RTL2.3 active phase/event reconciliation | [`rtl2_3_reconciliation_01.md`](rtl2_3_reconciliation_01.md) and [`rtl2_scoreboard_event_phase_reconciliation_01.json`](rtl2_scoreboard_event_phase_reconciliation_01.json) |
| RTL2.0 producer/event activation inventory | [`rtl2_0_activation_contract.md`](rtl2_0_activation_contract.md) and [`rtl2_0_activation_manifest.json`](rtl2_0_activation_manifest.json) |
| RTL2.0a logical payload materialization / hot maturity egress | [`rtl2_0a_payload_materialization_contract.md`](rtl2_0a_payload_materialization_contract.md) and [`rtl2_0a_payload_materialization_manifest.json`](rtl2_0a_payload_materialization_manifest.json) |
| RTL2.0b retained admission-group builder | [`rtl2_0b_admission_group_builder_contract.md`](rtl2_0b_admission_group_builder_contract.md) and [`rtl2_0b_admission_group_builder_manifest.json`](rtl2_0b_admission_group_builder_manifest.json) |
| RTL2.0c R2 logical ingress / delivery-context ownership | [`rtl2_0c_r2_ingress_delivery_context_contract.md`](rtl2_0c_r2_ingress_delivery_context_contract.md) and [`rtl2_0c_r2_ingress_delivery_context_manifest.json`](rtl2_0c_r2_ingress_delivery_context_manifest.json) |
| RTL2.0d typed read-fragment / write-terminal router endpoints | [`rtl2_0d_typed_delivery_router_contract.md`](rtl2_0d_typed_delivery_router_contract.md) and [`rtl2_0d_typed_delivery_router_manifest.json`](rtl2_0d_typed_delivery_router_manifest.json) |
| RTL2.0e R3/R5 descriptor-durability prerequisite | [`rtl2_0e_r3_r5_durability_prerequisite_contract.md`](rtl2_0e_r3_r5_durability_prerequisite_contract.md) and [`rtl2_0e_r3_r5_durability_prerequisite_manifest.json`](rtl2_0e_r3_r5_durability_prerequisite_manifest.json) |
| RTL2.0f source-service packet adapter | [`rtl2_0f_source_service_packet_adapter_contract.md`](rtl2_0f_source_service_packet_adapter_contract.md) and [`rtl2_0f_source_service_packet_adapter_manifest.json`](rtl2_0f_source_service_packet_adapter_manifest.json) |
| RTL2.0g R4 verification-only result-stub provider | [`rtl2_0g_r4_result_stub_provider_contract.md`](rtl2_0g_r4_result_stub_provider_contract.md) and [`rtl2_0g_r4_result_stub_provider_manifest.json`](rtl2_0g_r4_result_stub_provider_manifest.json) |
| RTL2.0 completion review and versioned pre-behavior scoreboard schema | [`rtl2_0_completion_review.md`](rtl2_0_completion_review.md), [`rtl2_0_completion_review_manifest.json`](rtl2_0_completion_review_manifest.json), and [`rtl2_scoreboard_event_schema.json`](rtl2_scoreboard_event_schema.json) |
| RTL2.1a immutable retained-group/admission activation | [`rtl2_1a_retained_group_admission_contract.md`](rtl2_1a_retained_group_admission_contract.md) and [`rtl2_1a_retained_group_admission_manifest.json`](rtl2_1a_retained_group_admission_manifest.json) |
| RTL1-I3 source/R4/R6 control composition | [`rtl1_i3_delivery_source_contract.md`](rtl1_i3_delivery_source_contract.md) and [`rtl1_i3_interface_manifest.json`](rtl1_i3_interface_manifest.json) |
| RTL1-I4 reclaim transport contract | [`rtl1_i4_reclaim_contract.md`](rtl1_i4_reclaim_contract.md) and [`rtl1_i4_interface_manifest.json`](rtl1_i4_interface_manifest.json) |

The R1--R6 contracts and their Python references remain the precise executable
attachments to the specification. They are not parallel living architecture
specifications: use them for module-level interface/assertion work or exact
historical provenance.

## A4 evidence chain

The final research disposition is the A4.14.1 ledger report at
`analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/`, SHA-256
`0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb`.

| Evidence topic | Canonical contract/index |
|---|---|
| External-storage correctness and lifecycle binding | [`route_a4112b_external_storage_lifecycle_contract.md`](route_a4112b_external_storage_lifecycle_contract.md) |
| M2 metadata/control contract | [`route_a4120_metadata_interface_inventory_contract.md`](route_a4120_metadata_interface_inventory_contract.md) through [`route_a4122_metadata_cycle_energy_contract.md`](route_a4122_metadata_cycle_energy_contract.md) |
| Packed payload, sidecar, source reuse, and service envelope | [`route_a4131_payload_organization_contract.md`](route_a4131_payload_organization_contract.md) through [`route_a4135_target_payload_service_cost_contract.md`](route_a4135_target_payload_service_cost_contract.md) |
| Workload-aligned metadata and final ledger | [`route_a4140_workload_aligned_metadata_cost_contract.md`](route_a4140_workload_aligned_metadata_cost_contract.md), [`route_a4141_accounted_net_benefit_ledger_contract.md`](route_a4141_accounted_net_benefit_ledger_contract.md) |

These are immutable research/provenance attachments. They must not be edited,
merged destructively, or interpreted as physical HBM timing, PPA, or measured
speedup evidence.

## Historical records and provenance

Older handoffs, stage archives, individual Gate-A closure records, and
per-revision provenance freezes are intentionally retained at their existing
paths. Many freezes name exact source paths and SHA-256 values; moving or
deleting them would make old evidence difficult to materialize and review.

For routine work, do not begin with those files. Start with the six living
documents above, then open a historical record only through a link from the
current plan/specification or when auditing a frozen claim.

## Maintenance rule

Update the appropriate living document when a gate or experiment changes
current status. Append compatible trace schema records to `TRACE_SCHEMA.md`;
append Route-A stage progress to `route_a_research_plan.md`; update
`architecture_spec.md` only for accepted interface-contract changes. Create a
new numbered volume only when a continuous living record becomes impractical to
navigate. Freeze/provenance/experiment/handoff documents remain append-free
historical evidence unless a separately authorized correction is required.

## Documentation-consolidation revision (2026-09-29)

This navigation revision consolidates current status into the living documents
above. It changes no frozen experiment, provenance, handoff, historical schema
section, Route-A semantic contract, or reported result. Earlier provenance
freezes remain byte snapshots of their own reviewed revisions; they are not
expected to hash-match a later living-document revision. Git history and the
current review/provenance links provide the continuity between such revisions.
