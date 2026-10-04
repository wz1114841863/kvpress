package kvpress.routea.top

import chisel3._
import kvpress.routea.common._
import kvpress.routea.incremental._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * Composition-only RTL1.0 skeleton for the frozen Route-A hierarchy.
  *
  * All non-environment cross-owner channels exist and are connected. Channels
  * without a functional producer/consumer are structurally tied inactive. No
  * mutable architecture state, protocol transition, publication, arbitration,
  * source release, retry, fallback, or numeric behavior is implemented here.
  */
final class RouteAKVSubsystemTop(p: RouteASkeletonParameters) extends RawModule {
  override def desiredName: String = "route_a_kv_subsystem_top"

  val core_clk = IO(Input(Clock()))
  // A Bool carrier avoids selecting synchronous versus asynchronous reset at
  // RTL1.0. This shell contains no sequential state or reset behavior.
  val destructive_reset = IO(Input(Bool()))

  val frontend_lifecycle_req = IO(Flipped(RouteAChannels.frontend_lifecycle_req(p)))
  val runtime_retire_req = IO(Flipped(RouteAChannels.runtime_retire_req))
  val attention_terminal_rsp = IO(RouteAChannels.attention_terminal_rsp)
  val session_retire_ack = IO(RouteAChannels.session_retire_ack)
  // Hot-owner egress into R3's replaceable functional P3 backing. These are
  // environment-owned payload/sidecar inputs; the composition top creates no
  // data, address, admission, authority, or delivery-context fact.
  val hot_payload_fragment_in = IO(Flipped(RouteAChannels.p3_pending_fragment(p)))
  val hot_position_sidecar_in = IO(Flipped(RouteAChannels.p3_sidecar_bind(p)))
  val external_core_mem_if_v1 = IO(new CoreMemoryExternalPort(p))

  withClockAndReset(core_clk, destructive_reset) {
    val lifecycle = Module(new RouteALifecycleAdapter(p))
    val hot = Module(new RouteAHotSourcePath(p))
    val s2 = Module(new RouteAS2GqaSourceWrapper(p))
    val direct_pending = Module(new RouteADirectPendingEndpointV1(p))
    val arbiter = Module(new RouteACoreSideArbiter(p))
    val core_memory = Module(new RouteACoreMemIfV1(p))
    val m2_p3 = Module(new RouteAM2P3Wrapper(p))
    val m2_reference_protocol = Module(new RouteAM2ReferenceProtocolProvider(p))
    val page_manager = Module(new RouteAPageManager(p))
    val admission_group_builder = Module(new RouteAAdmissionPublicationIngressAdapter(p))
    val r2_write_ingress = Module(new RouteAR2WriteIngressMerge(p))
    val delivery_context_registry = Module(new RouteADeliveryContextRegistry(p))
    val delivery_context_bridge = Module(new RouteADeliveryContextAllocationBridge(p))
    val typed_delivery_router = Module(new RouteATypedDeliveryRouter(p))
    val merge = Module(new RouteAMergeBoundary(p))
    val status_collector = Module(new RouteAComponentStatusCollector(p))

    lifecycle.io.frontend_lifecycle_req <> frontend_lifecycle_req
    lifecycle.io.runtime_retire_req <> runtime_retire_req
    attention_terminal_rsp <> lifecycle.io.attention_terminal_rsp
    session_retire_ack <> lifecycle.io.session_retire_ack

    lifecycle.io.component_status_in <> status_collector.io.component_status_out

    hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
    val hot_source_open = Wire(RouteAChannels.hot_source_open(p)); StructuralTieOff.source(hot_source_open)
    val hot_release = Wire(RouteAChannels.source_release(p))
    hot.io.hot_source_open_in <> hot_source_open
    hot_release <> hot.io.hot_release_out
    val r6_merge_ready = Wire(RouteAChannels.r6_merge_ready); StructuralTieOff.source(r6_merge_ready)
    val source_completion_plan = Wire(RouteAChannels.source_completion_plan(p)); StructuralTieOff.source(source_completion_plan)
    lifecycle.io.merge_ready_in <> r6_merge_ready
    lifecycle.io.source_completion_plan_in <> source_completion_plan
    lifecycle.io.hot_source_release_in <> hot_release
    s2.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    s2.io.service_req_in <> lifecycle.io.s2_service_req
    val s2_fill_open = Wire(RouteAChannels.s2_fill_open(p)); StructuralTieOff.source(s2_fill_open)
    val s2_payload_fragment = Wire(RouteAChannels.s2_payload_fragment(p)); StructuralTieOff.source(s2_payload_fragment)
    val s2_sidecar_fragment = Wire(RouteAChannels.s2_sidecar_fragment(p)); StructuralTieOff.source(s2_sidecar_fragment)
    val s2_fill_terminal = Wire(RouteAChannels.s2_fill_terminal(p)); StructuralTieOff.source(s2_fill_terminal)
    val s2_sidecar_complete = Wire(RouteAChannels.s2_sidecar_complete(p)); StructuralTieOff.source(s2_sidecar_complete)
    val s2_payload_read_req = Wire(RouteAChannels.s2_payload_read_req(p)); StructuralTieOff.source(s2_payload_read_req)
    val s2_sidecar_read_req = Wire(RouteAChannels.s2_sidecar_read_req(p)); StructuralTieOff.source(s2_sidecar_read_req)
    val s2_release = Wire(RouteAChannels.source_release(p))
    s2.io.s2_fill_open_in <> s2_fill_open
    s2.io.s2_payload_fragment_in <> s2_payload_fragment
    s2.io.s2_sidecar_fragment_in <> s2_sidecar_fragment
    s2.io.s2_fill_terminal_in <> s2_fill_terminal
    s2.io.s2_sidecar_complete_in <> s2_sidecar_complete
    s2.io.s2_payload_read_req_in <> s2_payload_read_req
    s2.io.s2_sidecar_read_req_in <> s2_sidecar_read_req
    StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
    StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
    s2_release <> s2.io.s2_release_out
    lifecycle.io.packed_source_release_in <> s2_release
    s2.io.s2_observe_slot := 0.U
    direct_pending.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    direct_pending.io.pending_source_open_in <> lifecycle.io.direct_pending_open
    val direct_record_terminal = Wire(RouteAChannels.direct_pending_record_terminal(p)); StructuralTieOff.source(direct_record_terminal)
    val direct_release = Wire(RouteAChannels.source_release(p))
    direct_pending.io.direct_pending_record_terminal_in <> direct_record_terminal
    direct_release <> direct_pending.io.direct_release_out
    lifecycle.io.pending_source_release_in <> direct_release

    val source_partial_to_merge = Wire(RouteAChannels.source_partial)
    StructuralTieOff.source(source_partial_to_merge)
    merge.io.source_partial_in <> source_partial_to_merge

    val r4_partial_header = Wire(RouteAChannels.r4_partial_header); StructuralTieOff.source(r4_partial_header)
    val r4_source_instance = Wire(RouteAChannels.r4_source_instance_sideband(p)); StructuralTieOff.source(r4_source_instance)
    val r4_value_fragment = Wire(RouteAChannels.r4_value_fragment); StructuralTieOff.source(r4_value_fragment)
    val r4_result_stub = Wire(RouteAChannels.r4_result_stub); StructuralTieOff.source(r4_result_stub)
    val r4_numeric_fault = Wire(RouteAChannels.r4_numeric_fault); StructuralTieOff.source(r4_numeric_fault)
    merge.io.r4_partial_header_in <> r4_partial_header
    merge.io.r4_source_instance_in <> r4_source_instance
    merge.io.r4_value_fragment_in <> r4_value_fragment
    merge.io.r4_result_stub_in <> r4_result_stub
    merge.io.r4_numeric_fault_in <> r4_numeric_fault

    val merge_source_commit = Wire(RouteAChannels.consumer_partial_commit(p))
    merge_source_commit <> merge.io.consumer_partial_commit
    hot.io.gqa_consumer_commit_in.valid := merge_source_commit.valid &&
      merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Hot.U
    hot.io.gqa_consumer_commit_in.bits := merge_source_commit.bits
    direct_pending.io.gqa_consumer_commit_in.valid := merge_source_commit.valid &&
      merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Pending.U
    direct_pending.io.gqa_consumer_commit_in.bits := merge_source_commit.bits
    s2.io.gqa_consumer_commit_in.valid := merge_source_commit.valid &&
      merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U
    s2.io.gqa_consumer_commit_in.bits := merge_source_commit.bits
    merge_source_commit.ready := Mux(
      merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Hot.U,
      hot.io.gqa_consumer_commit_in.ready,
      Mux(
        merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Pending.U,
        direct_pending.io.gqa_consumer_commit_in.ready,
        Mux(
          merge_source_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U,
          s2.io.gqa_consumer_commit_in.ready,
          false.B,
        ),
      ),
    )

    merge.io.merge_req_in <> lifecycle.io.merge_req
    lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault

    // RTL1-I4: R5 is the only active source during retirement, and only after
    // R6's permit.  R2 remains the unique core-side issuer for this carrier.
    arbiter.io.candidate_in <> r2_write_ingress.io.candidate_out
    // RTL2.3.3 exposes the second logical ingress at its sole R2 owner.  It
    // remains tied inactive until a later closure attaches named R3/R5 read
    // producers through the shared registry-allocation boundary; the top does
    // not construct a candidate or choose between read/write offers.
    val r2_read_candidate_in = Wire(RouteAChannels.source_candidate(p)); StructuralTieOff.source(r2_read_candidate_in)
    arbiter.io.read_candidate_in <> r2_read_candidate_in

    core_memory.io.core_mem_req_in <> arbiter.io.core_mem_req
    arbiter.io.core_mem_rsp_in <> core_memory.io.core_mem_rsp
    external_core_mem_if_v1 <> core_memory.io.external_core_mem_if_v1
    arbiter.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    arbiter.io.reclaim_maintenance_enable := lifecycle.io.reclaim_maintenance_enable
    core_memory.io.r1_drain_permitted := status_collector.io.r1_drain_permitted

    // The R1 reset-epoch acknowledgement is the sole local init fanout. It
    // enables no data source path by itself and ordinary R1 responses are not
    // interpreted as init acknowledgements.
    s2.io.mem_init_done := core_memory.io.r1_init_complete
    direct_pending.io.mem_init_done := core_memory.io.r1_init_complete
    delivery_context_registry.io.mem_init_done := core_memory.io.r1_init_complete

    delivery_context_registry.io.resolve_in <> arbiter.io.source_delivery_out
    typed_delivery_router.io.resolved_in <> delivery_context_registry.io.resolved_out
    delivery_context_registry.io.release_in <> typed_delivery_router.io.release_out
    delivery_context_bridge.io.release_event_in := typed_delivery_router.io.release_event_out
    page_manager.io.reclaim_delivery_in <> typed_delivery_router.io.r5_reclaim_out
    page_manager.io.append_delivery_in <> typed_delivery_router.io.r5_append_out
    // Read fragments have no active top-level producer/functional endpoint in
    // RTL2.2.2. Keeping the typed output sink inactive prevents accidental
    // source delivery or payload deposition before RTL2.3.
    StructuralTieOff.sink(typed_delivery_router.io.read_fragment_out)

    m2_p3.io.mem_init_done := core_memory.io.r1_init_complete
    m2_p3.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    // RTL2.1a: only the admitted hot->pending pair enters the dedicated
    // one-group protocol owner. Arrival/drop edges remain local hot control
    // facts; the top creates neither admission context nor authority state.
    val r6ToPending = lifecycle.io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
      lifecycle.io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
    admission_group_builder.io.r6_admission_context_in <> lifecycle.io.admission_context_out
    admission_group_builder.io.r6_authority_in.valid := lifecycle.io.authority_transition_out.valid && r6ToPending
    admission_group_builder.io.r6_authority_in.bits := lifecycle.io.authority_transition_out.bits
    lifecycle.io.authority_transition_out.ready := Mux(r6ToPending, admission_group_builder.io.r6_authority_in.ready, true.B)
    admission_group_builder.io.r5_allocation_req <> page_manager.io.page_allocation_req_in
    admission_group_builder.io.r5_allocation_rsp_in <> page_manager.io.page_allocation_rsp
    admission_group_builder.io.r3_p3_claim <> m2_p3.io.p3_claim_in
    admission_group_builder.io.r3_p3_claim_ack_in <> m2_p3.io.p3_claim_ack
    admission_group_builder.io.r3_admission_context_out <> m2_p3.io.admission_context_in
    admission_group_builder.io.r3_admission_authority_out <> m2_p3.io.admission_authority_in
    val p3_fragment = hot_payload_fragment_in
    val p3_sidecar = hot_position_sidecar_in
    val p3_write_issue = Wire(RouteAChannels.p3_packed_write_issue(p)); StructuralTieOff.source(p3_write_issue)
    val p3_write_terminal = Wire(RouteAChannels.p3_packed_write_terminal(p)); StructuralTieOff.source(p3_write_terminal)
    m2_p3.io.p3_pending_fragment_in <> p3_fragment
    m2_p3.io.p3_sidecar_bind_in <> p3_sidecar
    m2_p3.io.p3_packed_write_issue_in <> p3_write_issue
    m2_p3.io.p3_packed_write_terminal_in <> p3_write_terminal
    m2_reference_protocol.io.member_request_in <> m2_p3.io.m2_group_member_req_out
    m2_p3.io.m2_group_member_rsp_in <> m2_reference_protocol.io.member_response_out
    m2_p3.io.p3_observe_layer := 0.U
    m2_reference_protocol.io.publication_candidate_in <> m2_p3.io.m2_publish_candidate_out
    m2_p3.io.m2_publish_req_in <> m2_reference_protocol.io.publication_request_out
    // R6 observes the completed R3/R5 commit acknowledgement; it is not a
    // second publication initiator.  R3 owns the issued candidate above.
    StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
    lifecycle.io.authority_transition_in <> m2_p3.io.authority_transition_out
    // These are non-authoritative monitor attachment points.  I2's directed
    // harness attaches to them; the inert production top has no group source.
    m2_p3.io.publication_commit_observation.ready := true.B
    m2_p3.io.publication_member_observation.ready := true.B
    page_manager.io.mem_init_done := core_memory.io.r1_init_complete
    page_manager.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    page_manager.io.reclaim_permit_in <> lifecycle.io.reclaim_permit_out
    lifecycle.io.r5_reclaim_complete_in := page_manager.io.reclaim_complete
    val descriptor_maintenance_terminal = Wire(RouteAChannels.descriptor_maintenance_terminal(p)); StructuralTieOff.source(descriptor_maintenance_terminal)
    page_manager.io.descriptor_maintenance_terminal_in <> descriptor_maintenance_terminal
    delivery_context_bridge.io.r3_in <> m2_p3.io.p3_packed_write_candidate_out
    delivery_context_bridge.io.r5_append_in <> page_manager.io.append_candidate_out
    delivery_context_bridge.io.r5_reclaim_in <> page_manager.io.reclaim_candidate_out
    r2_write_ingress.io.r3_packed_write_in <> delivery_context_bridge.io.r3_out
    r2_write_ingress.io.r5_append_in <> delivery_context_bridge.io.r5_append_out
    r2_write_ingress.io.r5_reclaim_in <> delivery_context_bridge.io.r5_reclaim_out
    delivery_context_registry.io.allocation_in <> delivery_context_bridge.io.registry_allocate_out
    delivery_context_bridge.io.registry_allocation_ack_in <> delivery_context_registry.io.allocation_ack_out
    m2_p3.io.p3_packed_write_delivery_in <> typed_delivery_router.io.r3_packed_write_out
    page_manager.io.p3_payload_durable_in <> m2_p3.io.p3_payload_durable_out
    m2_p3.io.descriptor_durability_prerequisite_in <> page_manager.io.descriptor_durability_prerequisite_out
    page_manager.io.metadata_publish_visibility_in <> m2_p3.io.metadata_publish_visibility_apply
    m2_p3.io.metadata_publish_visibility_ack_in <> page_manager.io.metadata_publish_visibility_ack
    lifecycle.io.metadata_publish_ack_in <> m2_p3.io.m2_publish_ack

    merge.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    status_collector.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    status_collector.io.reclaim_drain_restart := lifecycle.io.reclaim_drain_restart
    status_collector.io.reclaim_final_drain_enable := lifecycle.io.reclaim_final_drain_enable
    status_collector.io.status_sources(0) <> core_memory.io.component_status_out
    status_collector.io.status_sources(1) <> arbiter.io.payload_drain_status_out
    status_collector.io.status_sources(2) <> arbiter.io.descriptor_drain_status_out
    status_collector.io.status_sources(3) <> m2_p3.io.component_status_out
    status_collector.io.status_sources(4) <> page_manager.io.component_status_out
    status_collector.io.status_sources(5) <> s2.io.component_status_out
    status_collector.io.status_sources(6) <> direct_pending.io.component_status_out
    status_collector.io.status_sources(7) <> merge.io.component_status_out
  }
}
