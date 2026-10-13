package kvpress.routea.rtl2

import chisel3._
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteAR2WriteDeliveryRouter, RouteAR2WriteIngressMerge}
import kvpress.routea.incremental.{RouteAM2P3Wrapper, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * RTL2.1c's one-group functional integration harness.
  *
  * The M2 member and publication carriers are deliberately exposed so tests
  * can inject stale, mismatched, and fault terminals.  Production composition
  * uses the replaceable reference protocol provider instead.  Neither harness
  * selects an M2 macro, timing, controller, or physical port organization.
  */
final class RouteA2_1cAtomicPublicationHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val r5_allocate = Flipped(RouteAChannels.page_allocation_req(p))
    val r5_allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    val p3_claim = Flipped(RouteAChannels.p3_claim(p))
    val admission_context = Flipped(RouteAChannels.admission_context(p))
    val admission_authority = Flipped(RouteAChannels.r6_authority_transition(p))
    val hot_payload = Flipped(RouteAChannels.p3_pending_fragment(p))
    val hot_sidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val external = new CoreMemoryExternalPort(p)
    val m2_member_request = RouteAChannels.m2_group_member_req(p)
    val m2_member_response = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val m2_publication_candidate = RouteAChannels.metadata_publish_req(p)
    val m2_publication_request = Flipped(RouteAChannels.metadata_publish_req(p))
    val authority_transition = RouteAChannels.r6_authority_transition(p)
    val publication_commit = RouteAChannels.publication_commit_observation(p)
    val publication_member = RouteAChannels.publication_member_observation(p)
    val publication_ack = RouteAChannels.metadata_publish_ack(p)
    val p3_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
  })

  val r3 = Module(new RouteAM2P3Wrapper(p))
  val r5 = Module(new RouteAPageManager(p))
  StructuralTieOff.source(r5.io.descriptor_location_request_in)
  StructuralTieOff.sink(r5.io.descriptor_location_grant_out)
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val ingress = Module(new RouteAR2WriteIngressMerge(p))
  val router = Module(new RouteAR2WriteDeliveryRouter(p))

  r3.io.mem_init_done := io.mem_init_done; r3.io.drain_collection_enable := false.B
  r5.io.mem_init_done := io.mem_init_done; r5.io.drain_collection_enable := false.B
  r5.io.allocator_release_out.ready := true.B
  r2.io.drain_collection_enable := false.B; r2.io.reclaim_maintenance_enable := false.B
  r1.io.r1_drain_permitted := false.B
  r3.io.p3_claim_ack.ready := true.B
  r3.io.p3_claim_in <> io.p3_claim
  r3.io.admission_context_in <> io.admission_context
  r3.io.admission_authority_in <> io.admission_authority
  StructuralTieOff.source(r3.io.pending_payload_binding_in)
  r3.io.p3_pending_fragment_in <> io.hot_payload
  r3.io.p3_sidecar_bind_in <> io.hot_sidecar
  StructuralTieOff.source(r3.io.p3_pack_read_work_in)
  StructuralTieOff.sink(r3.io.p3_pack_read_issue_out)
  StructuralTieOff.source(r3.io.p3_packed_write_issue_in)
  StructuralTieOff.source(r3.io.p3_packed_write_terminal_in)
  io.m2_member_request <> r3.io.m2_group_member_req_out
  r3.io.m2_group_member_rsp_in <> io.m2_member_response
  io.m2_publication_candidate <> r3.io.m2_publish_candidate_out
  r3.io.m2_publish_req_in <> io.m2_publication_request
  io.authority_transition <> r3.io.authority_transition_out
  io.publication_commit <> r3.io.publication_commit_observation
  io.publication_member <> r3.io.publication_member_observation
  StructuralTieOff.sink(r3.io.post_r6_packed_page_ready_observation)
  io.publication_ack <> r3.io.m2_publish_ack
  StructuralTieOff.sink(r3.io.component_status_out)
  r3.io.p3_observe_layer := 0.U

  r5.io.page_allocation_req_in <> io.r5_allocate
  io.r5_allocation_rsp <> r5.io.page_allocation_rsp
  StructuralTieOff.source(r5.io.reclaim_permit_in)
  StructuralTieOff.source(r5.io.reclaim_delivery_in)
  StructuralTieOff.sink(r5.io.reclaim_candidate_out)
  StructuralTieOff.source(r5.io.descriptor_maintenance_terminal_in)
  r5.io.append_delivery_in <> router.io.r5_append_out
  StructuralTieOff.sink(router.io.r5_reclaim_out)
  r5.io.p3_payload_durable_in <> r3.io.p3_payload_durable_out
  r3.io.descriptor_durability_prerequisite_in <> r5.io.descriptor_durability_prerequisite_out
  r5.io.metadata_publish_visibility_in <> r3.io.metadata_publish_visibility_apply
  r3.io.metadata_publish_visibility_ack_in <> r5.io.metadata_publish_visibility_ack
  StructuralTieOff.sink(r5.io.component_status_out)

  ingress.io.r3_packed_write_in <> r3.io.p3_packed_write_candidate_out
  ingress.io.r5_append_in <> r5.io.append_candidate_out
  StructuralTieOff.source(ingress.io.r5_reclaim_in)
  r2.io.candidate_in <> ingress.io.candidate_out
  StructuralTieOff.source(r2.io.read_candidate_in)
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  router.io.source_delivery_in <> r2.io.source_delivery_out
  r3.io.p3_packed_write_delivery_in <> router.io.r3_packed_write_out
  r1.io.external_core_mem_if_v1 <> io.external
  StructuralTieOff.sink(r2.io.payload_drain_status_out)
  StructuralTieOff.sink(r2.io.descriptor_drain_status_out)
  StructuralTieOff.sink(r1.io.component_status_out)

  io.p3_state := r3.io.p3_observe_state
}
