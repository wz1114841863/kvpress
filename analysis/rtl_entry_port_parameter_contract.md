# Gate-RTL0.2 — logical bundle-port and parameter closure

## Status and boundary

**Status:** `complete_non_implementational_port_parameter_closure; assertion_matrix_pending`.

This record binds the frozen Gate-RTL0.1 hierarchy to logical decoupled bundle
ports.  A row identifies both endpoint names but is not a SystemVerilog
declaration, aggregate-wire encoding, HBM command, SRAM port, controller
protocol, pipeline, cycle, frequency, or PPA claim.  `core_clk` names the R1
core-side domain; it does not select CDC behavior outside `core_mem_if_v1`.

The manifest is authoritative for record fields.  The marked table below is
rendered from it and is checked byte-for-byte by the no-model preflight.  The
top shell may route a bundle between named child owners, but cannot acquire its
own mutable resource ownership.  Parameterized/opaque fields stay symbolic;
they are not silently assigned an implementation width.

## Manifest-to-Markdown port matrix

<!-- BEGIN RTL_ENTRY_INTERFACE_MATRIX -->
| Record ID | Module.port | Direction | Producer -> consumer | Width | Clock/reset | Handshake | Parameter source | Contract reference |
|---|---|---|---|---|---|---|---|---|
| if_frontend_lifecycle_req | route_a_lifecycle_adapter.frontend_lifecycle_req | input | frontend_post_decision_adapter -> route_a_lifecycle_adapter | logical tagged union; no physical tag encoding selected | core_clk / destructive_reset; acceptance after all init acknowledgements | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/rtl1_i2_admission_publication_contract.md |
| if_pending_payload_read_binding | route_a_kv_subsystem_top.pending_payload_read_binding_in | input | pending_payload_storage_owner -> route_a_kv_subsystem_top | logical immutable identity/member coordinates plus opaque pending handle, generation, and endpoint | core_clk / destructive_reset; no retained binding survives reset | ready_valid | analysis/rtl3_9_a0_pending_payload_read_association_contract.md | analysis/rtl3_9_a0_pending_payload_read_association_contract.md |
| if_runtime_retire_req | route_a_lifecycle_adapter.runtime_retire_req | input | runtime_session_manager -> route_a_lifecycle_adapter | session_id[0:0] + transaction_identity[4:0] | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md |
| if_lifecycle_terminal_rsp | route_a_lifecycle_adapter.attention_terminal_rsp | output | route_a_lifecycle_adapter -> frontend_post_decision_adapter | transaction_identity[4:0] + terminal_status{ok,fault} | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md |
| if_lifecycle_retire_ack | route_a_lifecycle_adapter.session_retire_ack | output | route_a_lifecycle_adapter -> runtime_session_manager | session_id[0:0] + transaction_identity[4:0] | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md |
| if_lifecycle_component_status | route_a_lifecycle_adapter.component_status_in | input | route_a_component_status_collector -> route_a_lifecycle_adapter | logical named acknowledgement set; no physical vector encoding selected | core_clk / destructive_reset | ready_valid | analysis/rtl1_i1_init_drain_carrier_contract.md | analysis/rtl1_i1_init_drain_carrier_contract.md |
| if_lifecycle_hot_control | route_a_lifecycle_adapter.hot_control_out | output | route_a_lifecycle_adapter -> route_a_hot_source_path | entry coordinate/control bundle | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md |
| if_lifecycle_s2_control | route_a_lifecycle_adapter.s2_service_req | output | route_a_lifecycle_adapter -> route_a_s2_gqa_source_wrapper | transaction_identity + source/page reference bundle | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md | analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md |
| if_lifecycle_direct_pending_open | route_a_lifecycle_adapter.direct_pending_open | output | route_a_lifecycle_adapter -> route_a_direct_pending_endpoint_v1 | pending_source_open logical bundle | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a1_pending_delivery_realization_closure.md | analysis/architecture_gate_a1_pending_delivery_realization_closure.md |
| if_source_partial_to_merge | route_a_kv_subsystem_top.source_partial_to_merge | output | route_a_kv_subsystem_top -> route_a_merge_boundary | legacy opaque partial header[127:0] + value word[511:0] | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r4_numeric_merge_contract.md | analysis/rtl1_6_r4_packet_boundary_contract.md |
| if_r4_partial_header | route_a_kv_subsystem_top.r4_partial_header | output | route_a_kv_subsystem_top -> route_a_merge_boundary | transaction_identity + header[127:0] | core_clk / destructive_reset | ready_valid | analysis/rtl1_6_r4_packet_boundary_contract.md | analysis/rtl1_6_r4_packet_boundary_contract.md |
| if_r4_value_fragment | route_a_kv_subsystem_top.r4_value_fragment | output | route_a_kv_subsystem_top -> route_a_merge_boundary | transaction_identity + fragment_index[2:0] + last + data[511:0] | core_clk / destructive_reset | ready_valid | analysis/rtl1_6_r4_packet_boundary_contract.md | analysis/rtl1_6_r4_packet_boundary_contract.md |
| if_r4_accepted_partial_packet | route_a_merge_boundary.r4_accepted_partial_packet_out | output | route_a_merge_boundary -> route_a_functional_r4_merge_provider | transaction_identity + SourceInstance + consumer_id[1:0] + header[127:0] + value_payload[4095:0] | core_clk / destructive_reset | ready_valid | analysis/rtl3_4b_functional_r4_provider_contract.md | analysis/rtl3_4b_functional_r4_provider_contract.md |
| if_r4_result_stub | route_a_kv_subsystem_top.r4_result_stub | output | route_a_kv_subsystem_top -> route_a_merge_boundary | transaction_identity + consumer_id[1:0] + normalized_value[128*32] | core_clk / destructive_reset | ready_valid | analysis/rtl3_4a_r4_consumer_result_association_contract.md | analysis/rtl3_4a_r4_consumer_result_association_contract.md |
| if_r4_numeric_fault | route_a_kv_subsystem_top.r4_numeric_fault | output | route_a_kv_subsystem_top -> route_a_merge_boundary | transaction_identity + consumer_id[1:0] | core_clk / destructive_reset | ready_valid | analysis/rtl3_4a_r4_consumer_result_association_contract.md | analysis/rtl3_4a_r4_consumer_result_association_contract.md |
| if_merge_source_commit | route_a_merge_boundary.consumer_partial_commit | output | route_a_merge_boundary -> route_a_kv_subsystem_top | transaction_identity + consumer_id[1:0] + SourceInstance{source_kind[1:0],instance_coordinate,generation} | core_clk / destructive_reset | ready_valid | analysis/rtl1_i3_delivery_source_contract.md | analysis/rtl1_i3_delivery_source_contract.md |
| if_lifecycle_merge_req | route_a_lifecycle_adapter.merge_req | output | route_a_lifecycle_adapter -> route_a_merge_boundary | transaction_identity + source_presence[2:0] + consumer_id[1:0] | core_clk / destructive_reset | ready_valid | analysis/rtl3_4a_r4_consumer_result_association_contract.md | analysis/rtl3_4a_r4_consumer_result_association_contract.md |
| if_merge_lifecycle_rsp | route_a_merge_boundary.merge_rsp_or_numeric_fault | output | route_a_merge_boundary -> route_a_lifecycle_adapter | transaction_identity + consumer_id[1:0] + status + normalized_value[128*32] when ok | core_clk / destructive_reset | ready_valid | analysis/rtl3_4a_r4_consumer_result_association_contract.md | analysis/rtl3_4a_r4_consumer_result_association_contract.md |
| if_source_candidate_to_r2 | route_a_kv_subsystem_top.source_candidate_to_r2 | output | route_a_kv_subsystem_top -> route_a_core_side_arbiter | logical candidate bundle; no physical queue/port count selected | core_clk / destructive_reset | ready_valid | analysis/rtl1_2_r2_semantic_carrier_contract.md | analysis/architecture_gate_a_r2_arbitration_dependency_contract.md |
| if_r2_core_mem_req | route_a_core_side_arbiter.core_mem_req | output | route_a_core_side_arbiter -> route_a_core_mem_if_v1 | core_read_req or core_write_req/data logical bundle | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md |
| if_r1_core_mem_rsp | route_a_core_mem_if_v1.core_mem_rsp | output | route_a_core_mem_if_v1 -> route_a_core_side_arbiter | core_read_rsp or core_write_commit logical bundle | core_clk / destructive_reset; pre-reset response suppressed before init | ready_valid | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md |
| if_r1_external_memory | route_a_core_mem_if_v1.external_core_mem_if_v1 | output | route_a_core_mem_if_v1 -> external_memory_adapter | same selected core-side request/response bundles; native translation external | core_clk at Route-A boundary / destructive_reset + external pre-reset response suppression | ready_valid | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md | analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md |
| if_r1_external_init_ack | route_a_core_mem_if_v1.external_core_mem_if_v1.init_ack | input | external_memory_adapter -> route_a_core_mem_if_v1 | adapter_epoch_ready[0] | core_clk at Route-A boundary / destructive_reset; adapter suppresses/drains pre-reset responses before acknowledgement | ready_valid | analysis/rtl1_i1_init_drain_carrier_contract.md | analysis/rtl1_i1_init_drain_carrier_contract.md |
| if_r2_source_delivery | route_a_core_side_arbiter.source_delivery_out | output | route_a_core_side_arbiter -> route_a_kv_subsystem_top | candidate association + opaque delivery context + destination + routed R1 fragment/terminal bundle | core_clk / destructive_reset | ready_valid | analysis/rtl1_2_r2_semantic_carrier_contract.md | analysis/rtl1_i3_delivery_source_contract.md |
| if_lifecycle_publish_req | route_a_lifecycle_adapter.metadata_publish_req | output | route_a_lifecycle_adapter -> route_a_m2_p3_wrapper | transaction_group_tag + p3_layer + p3_stage_generation | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md | analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md |
| if_r3_r5_publish_visibility | route_a_m2_p3_wrapper.metadata_publish_visibility_apply | output | route_a_m2_p3_wrapper -> route_a_page_manager | page_ref + transaction_group_tag | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_pre_reviewer_02_integration_audit.md | analysis/architecture_gate_a_pre_reviewer_02_integration_audit.md |
| if_r5_r3_publish_ready | route_a_page_manager.metadata_publish_visibility_ack | output | route_a_page_manager -> route_a_m2_p3_wrapper | page_ref + status{ready,fault} | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md | analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md |
| if_r3_lifecycle_publish_ack | route_a_m2_p3_wrapper.m2_publish_ack | output | route_a_m2_p3_wrapper -> route_a_lifecycle_adapter | transaction_group_tag + status{published,fault} | core_clk / destructive_reset | ready_valid | analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md | analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md |
<!-- END RTL_ENTRY_INTERFACE_MATRIX -->

## Closed and deliberately deferred fields

The table preserves the selected anchor widths where the contracts selected
them: 64-B/512-bit core fragment, RID+incarnation `3+2`, page reference
`18+8`, page size 64, two S2 slots, four GQA consumers, R4 128-bit header,
and 512-bit value fragment.  It deliberately leaves opaque address/reference,
candidate ID/ordinal, transaction-group tag, stage generation, fragment-index,
error-detail, and native-controller fields parameterized at their cited source.

The grouped source candidate, source delivery, component-status, and
source-partial records are integration-shell wiring bundles, not hidden new
owners or physical mux implementations.  Their symbolic union/selection
encoding is intentionally unchosen.  In particular, the matrix does not imply
a physical M2 port count, P3 macro port, HBM burst/channel, CDC, queue depth,
service schedule, exp datapath, internal precision, or frequency.

`metadata_publish_visibility_apply` and its acknowledgement are nested inside
the one R3-outer `metadata_publish_commit`.  They cannot create an independent
publication path.  `merge_rsp_or_numeric_fault` preserves the R4 replaceable
boundary and the R6-only outward terminal consumer.
