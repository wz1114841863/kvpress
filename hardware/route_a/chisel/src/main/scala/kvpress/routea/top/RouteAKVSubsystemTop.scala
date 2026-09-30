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
  val external_core_mem_if_v1 = IO(new CoreMemoryExternalPort(p))

  withClockAndReset(core_clk, destructive_reset) {
    val lifecycle = Module(new RouteALifecycleAdapter(p))
    val hot = Module(new RouteAHotSourcePath(p))
    val s2 = Module(new RouteAS2GqaSourceWrapper(p))
    val direct_pending = Module(new RouteADirectPendingEndpointV1(p))
    val arbiter = Module(new RouteACoreSideArbiter(p))
    val core_memory = Module(new RouteACoreMemIfV1(p))
    val m2_p3 = Module(new RouteAM2P3Wrapper(p))
    val page_manager = Module(new RouteAPageManager(p))
    val merge = Module(new RouteAMergeBoundary(p))
    val status_collector = Module(new RouteAComponentStatusCollector(p))

    lifecycle.io.frontend_lifecycle_req <> frontend_lifecycle_req
    lifecycle.io.runtime_retire_req <> runtime_retire_req
    attention_terminal_rsp <> lifecycle.io.attention_terminal_rsp
    session_retire_ack <> lifecycle.io.session_retire_ack

    lifecycle.io.component_status_in <> status_collector.io.component_status_out

    hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
    val r6_merge_ready = Wire(RouteAChannels.r6_merge_ready); StructuralTieOff.source(r6_merge_ready)
    lifecycle.io.merge_ready_in <> r6_merge_ready
    s2.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    s2.io.service_req_in <> lifecycle.io.s2_service_req
    val s2_fill_open = Wire(RouteAChannels.s2_fill_open(p)); StructuralTieOff.source(s2_fill_open)
    val s2_fill_terminal = Wire(RouteAChannels.s2_fill_terminal(p)); StructuralTieOff.source(s2_fill_terminal)
    val s2_sidecar_complete = Wire(RouteAChannels.s2_sidecar_complete(p)); StructuralTieOff.source(s2_sidecar_complete)
    val s2_gqa_commit = Wire(RouteAChannels.gqa_consumer_commit(p)); StructuralTieOff.source(s2_gqa_commit)
    val s2_release = Wire(RouteAChannels.source_release(p)); StructuralTieOff.sink(s2_release)
    s2.io.s2_fill_open_in <> s2_fill_open
    s2.io.s2_fill_terminal_in <> s2_fill_terminal
    s2.io.s2_sidecar_complete_in <> s2_sidecar_complete
    s2.io.gqa_consumer_commit_in <> s2_gqa_commit
    s2_release <> s2.io.s2_release_out
    s2.io.s2_observe_slot := 0.U
    direct_pending.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    direct_pending.io.pending_source_open_in <> lifecycle.io.direct_pending_open
    val direct_record_terminal = Wire(RouteAChannels.direct_pending_record_terminal(p)); StructuralTieOff.source(direct_record_terminal)
    val direct_gqa_commit = Wire(RouteAChannels.gqa_consumer_commit(p)); StructuralTieOff.source(direct_gqa_commit)
    val direct_release = Wire(RouteAChannels.source_release(p)); StructuralTieOff.sink(direct_release)
    direct_pending.io.direct_pending_record_terminal_in <> direct_record_terminal
    direct_pending.io.gqa_consumer_commit_in <> direct_gqa_commit
    direct_release <> direct_pending.io.direct_release_out

    val source_partial_to_merge = Wire(RouteAChannels.source_partial)
    StructuralTieOff.source(source_partial_to_merge)
    merge.io.source_partial_in <> source_partial_to_merge

    val r4_partial_header = Wire(RouteAChannels.r4_partial_header); StructuralTieOff.source(r4_partial_header)
    val r4_value_fragment = Wire(RouteAChannels.r4_value_fragment); StructuralTieOff.source(r4_value_fragment)
    val r4_result_stub = Wire(RouteAChannels.r4_result_stub); StructuralTieOff.source(r4_result_stub)
    val r4_numeric_fault = Wire(RouteAChannels.r4_numeric_fault); StructuralTieOff.source(r4_numeric_fault)
    merge.io.r4_partial_header_in <> r4_partial_header
    merge.io.r4_value_fragment_in <> r4_value_fragment
    merge.io.r4_result_stub_in <> r4_result_stub
    merge.io.r4_numeric_fault_in <> r4_numeric_fault

    val merge_source_commit = Wire(RouteAChannels.consumer_partial_commit(p))
    merge_source_commit <> merge.io.consumer_partial_commit
    StructuralTieOff.sink(merge_source_commit)

    merge.io.merge_req_in <> lifecycle.io.merge_req
    lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault

    val source_candidate_to_r2 = Wire(RouteAChannels.source_candidate(p))
    StructuralTieOff.source(source_candidate_to_r2)
    arbiter.io.candidate_in <> source_candidate_to_r2

    core_memory.io.core_mem_req_in <> arbiter.io.core_mem_req
    arbiter.io.core_mem_rsp_in <> core_memory.io.core_mem_rsp
    external_core_mem_if_v1 <> core_memory.io.external_core_mem_if_v1
    arbiter.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    core_memory.io.r1_drain_permitted := status_collector.io.r1_drain_permitted

    // The R1 reset-epoch acknowledgement is the sole local init fanout. It
    // enables no data source path by itself and ordinary R1 responses are not
    // interpreted as init acknowledgements.
    s2.io.mem_init_done := core_memory.io.r1_init_complete
    direct_pending.io.mem_init_done := core_memory.io.r1_init_complete

    val source_delivery = Wire(RouteAChannels.source_delivery(p))
    source_delivery <> arbiter.io.source_delivery_out
    StructuralTieOff.sink(source_delivery)

    m2_p3.io.mem_init_done := core_memory.io.r1_init_complete
    m2_p3.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    // Only a retained hot->pending event joins its immutable post-decision
    // context at R3.  Arrival/drop transitions remain local hot control facts.
    val r6ToPending = lifecycle.io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
      lifecycle.io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
    m2_p3.io.admission_authority_in.valid := lifecycle.io.authority_transition_out.valid && r6ToPending
    m2_p3.io.admission_authority_in.bits := lifecycle.io.authority_transition_out.bits
    lifecycle.io.authority_transition_out.ready := Mux(r6ToPending, m2_p3.io.admission_authority_in.ready, true.B)
    m2_p3.io.admission_context_in <> lifecycle.io.admission_context_out
    val p3_claim = Wire(RouteAChannels.p3_claim(p)); StructuralTieOff.source(p3_claim)
    val p3_claim_ack = Wire(RouteAChannels.p3_claim_ack(p)); StructuralTieOff.sink(p3_claim_ack)
    val p3_fragment = Wire(RouteAChannels.p3_pending_fragment(p)); StructuralTieOff.source(p3_fragment)
    val p3_sidecar = Wire(RouteAChannels.p3_sidecar_bind(p)); StructuralTieOff.source(p3_sidecar)
    val p3_write_issue = Wire(RouteAChannels.p3_packed_write_issue(p)); StructuralTieOff.source(p3_write_issue)
    val p3_write_terminal = Wire(RouteAChannels.p3_packed_write_terminal(p)); StructuralTieOff.source(p3_write_terminal)
    val m2_group_member_rsp = Wire(RouteAChannels.m2_group_member_rsp(p)); StructuralTieOff.source(m2_group_member_rsp)
    m2_p3.io.p3_claim_in <> p3_claim
    p3_claim_ack <> m2_p3.io.p3_claim_ack
    m2_p3.io.p3_pending_fragment_in <> p3_fragment
    m2_p3.io.p3_sidecar_bind_in <> p3_sidecar
    m2_p3.io.p3_packed_write_issue_in <> p3_write_issue
    m2_p3.io.p3_packed_write_terminal_in <> p3_write_terminal
    m2_p3.io.m2_group_member_rsp_in <> m2_group_member_rsp
    m2_p3.io.p3_observe_layer := 0.U
    m2_p3.io.m2_publish_req_in <> lifecycle.io.metadata_publish_req
    lifecycle.io.authority_transition_in <> m2_p3.io.authority_transition_out
    // These are non-authoritative monitor attachment points.  I2's directed
    // harness attaches to them; the inert production top has no group source.
    m2_p3.io.publication_commit_observation.ready := true.B
    m2_p3.io.publication_member_observation.ready := true.B
    page_manager.io.mem_init_done := core_memory.io.r1_init_complete
    page_manager.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    val page_allocation_req = Wire(RouteAChannels.page_allocation_req(p)); StructuralTieOff.source(page_allocation_req)
    val page_allocation_rsp = Wire(RouteAChannels.page_allocation_rsp(p)); StructuralTieOff.sink(page_allocation_rsp)
    val descriptor_maintenance_terminal = Wire(RouteAChannels.descriptor_maintenance_terminal(p)); StructuralTieOff.source(descriptor_maintenance_terminal)
    page_manager.io.page_allocation_req_in <> page_allocation_req
    page_allocation_rsp <> page_manager.io.page_allocation_rsp
    page_manager.io.descriptor_maintenance_terminal_in <> descriptor_maintenance_terminal
    page_manager.io.metadata_publish_visibility_in <> m2_p3.io.metadata_publish_visibility_apply
    m2_p3.io.metadata_publish_visibility_ack_in <> page_manager.io.metadata_publish_visibility_ack
    lifecycle.io.metadata_publish_ack_in <> m2_p3.io.m2_publish_ack

    merge.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    status_collector.io.drain_collection_enable := lifecycle.io.drain_collection_enable
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
