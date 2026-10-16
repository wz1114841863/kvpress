package kvpress.routea.top

import chisel3._
import chisel3.util.{Decoupled, Valid}
import kvpress.routea.common._
import kvpress.routea.incremental.RouteAPackedReadAssociationOwner
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Independent W0 Route-A packed-read measurement contour.
  *
  * Unlike the historical composition skeleton this top has no inactive
  * synthetic carrier: every non-local producer/consumer is a named
  * outer contract.  It retains the packed association -> R2/R1 -> registry ->
  * typed endpoint -> S2 route.  R3/R5 authorization and terminal/reclaim
  * remain explicit outer owner boundaries; it does not recreate R6 or claim a
  * same-instance C3/C4 closure.
  */
final class RouteAMeasurementDut(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val packed_demand_in = Flipped(RouteAChannels.packed_source_demand(p))
    val publication_authorization_in = Flipped(RouteAChannels.publication_read_authorization(p))
    val descriptor_grant_in = Flipped(RouteAChannels.descriptor_location_grant(p))
    val owner_s2_lease_in = Flipped(RouteAChannels.s2_fill_lease(p))
    val invalidation_in = Flipped(Valid(new PackedReadInvalidation))
    val sidecar_read_work_out = RouteAChannels.sidecar_read_work(p)
    val association_terminal_in = Flipped(RouteAChannels.packed_read_terminal(p))
    val release_observation_out = RouteAChannels.packed_read_release_observation(p)
    val common_legacy_candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_pack_read_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_direct_pending_in = Flipped(RouteAChannels.source_candidate(p))
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
    val r1_drain_permitted = Input(Bool())
    val r2_drain_collection_enable = Input(Bool())
    val r2_reclaim_maintenance_enable = Input(Bool())
    val r1_component_status_out = RouteAChannels.component_status(p)
    val r2_payload_drain_status_out = RouteAChannels.component_status(p)
    val r2_descriptor_drain_status_out = RouteAChannels.component_status(p)
    val r3_packed_write_out = RouteAChannels.source_delivery(p)
    val r5_append_out = RouteAChannels.source_delivery(p)
    val r5_reclaim_out = RouteAChannels.source_delivery(p)
    val p3_pack_read_out = RouteAChannels.resolved_delivery(p)
    val direct_pending_out = RouteAChannels.resolved_delivery(p)
    val packed_sidecar_out = RouteAChannels.resolved_delivery(p)
    val s2_fill_lease_request_in = Flipped(RouteAChannels.s2_fill_lease_request(p))
    val s2_fill_lease_out = RouteAChannels.s2_fill_lease(p)
    val s2_service_in = Flipped(RouteAChannels.s2_service_req)
    val s2_sidecar_fragment_in = Flipped(RouteAChannels.s2_sidecar_fragment(p))
    val s2_sidecar_complete_in = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val s2_payload_read_req_in = Flipped(RouteAChannels.s2_payload_read_req(p))
    val s2_payload_read_rsp_out = RouteAChannels.s2_payload_read_rsp(p)
    val s2_sidecar_read_req_in = Flipped(RouteAChannels.s2_sidecar_read_req(p))
    val s2_sidecar_read_rsp_out = RouteAChannels.s2_sidecar_read_rsp(p)
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val s2_release_out = RouteAChannels.source_release(p)
    val s2_component_status_out = RouteAChannels.component_status(p)
    val s2_observe_slot = Input(UInt(RouteAAnchorWidths.S2SlotWidth.W))
  })
  val owner = Module(new RouteAPackedReadAssociationOwner(p))
  val producer = Module(new RouteAPackedS2ReadProducer(p))
  val issue = Module(new RouteAReadIssueCandidateAdapter(p))
  val ingress = Module(new RouteAR2ReadIngressMerge(p))
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val demux = Module(new RouteAReadEndpointDemultiplexer(p))
  val endpoint = Module(new RouteAPackedS2ReadEndpoint(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))

  owner.io.mem_init_done := r1.io.r1_init_complete
  owner.io.demand_in <> io.packed_demand_in
  owner.io.publication_authorization_in <> io.publication_authorization_in
  owner.io.descriptor_grant_in <> io.descriptor_grant_in
  owner.io.s2_fill_lease_in <> io.owner_s2_lease_in
  owner.io.invalidation_in <> io.invalidation_in
  owner.io.sidecar_read_work_out <> io.sidecar_read_work_out
  owner.io.terminal_in <> io.association_terminal_in
  owner.io.release_observation_out <> io.release_observation_out
  owner.io.registry_allocate_out <> registry.io.allocation_in
  owner.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  owner.io.packed_s2_work_out <> producer.io.work_in
  producer.io.read_issue_out <> issue.io.read_issue_in
  producer.io.s2_fill_open_out <> s2.io.s2_fill_open_in
  ingress.io.r5_s2_packed_in <> issue.io.candidate_out
  ingress.io.r3_pack_read_in <> io.r3_pack_read_in
  ingress.io.r3_direct_pending_in <> io.r3_direct_pending_in
  r2.io.read_candidate_in <> ingress.io.candidate_out
  r2.io.candidate_in <> io.common_legacy_candidate_in
  r2.io.drain_collection_enable := io.r2_drain_collection_enable
  r2.io.reclaim_maintenance_enable := io.r2_reclaim_maintenance_enable
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  r1.io.external_core_mem_if_v1 <> io.external_core_mem_if_v1
  r1.io.r1_drain_permitted := io.r1_drain_permitted
  io.r1_component_status_out <> r1.io.component_status_out
  io.r2_payload_drain_status_out <> r2.io.payload_drain_status_out
  io.r2_descriptor_drain_status_out <> r2.io.descriptor_drain_status_out
  registry.io.mem_init_done := r1.io.r1_init_complete
  registry.io.resolve_in <> r2.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  demux.io.resolved_in <> router.io.read_fragment_out
  endpoint.io.resolved_fragment_in <> demux.io.packed_s2_out
  io.p3_pack_read_out <> demux.io.p3_pack_read_out
  io.direct_pending_out <> demux.io.direct_pending_out
  io.packed_sidecar_out <> demux.io.packed_s2_sidecar_out
  io.r3_packed_write_out <> router.io.r3_packed_write_out
  io.r5_append_out <> router.io.r5_append_out
  io.r5_reclaim_out <> router.io.r5_reclaim_out
  s2.io.mem_init_done := r1.io.r1_init_complete
  s2.io.drain_collection_enable := io.r2_drain_collection_enable
  s2.io.s2_fill_lease_request_in <> io.s2_fill_lease_request_in
  io.s2_fill_lease_out <> s2.io.s2_fill_lease_out
  s2.io.service_req_in <> io.s2_service_in
  s2.io.s2_sidecar_fragment_in <> io.s2_sidecar_fragment_in
  s2.io.s2_sidecar_complete_in <> io.s2_sidecar_complete_in
  s2.io.s2_payload_read_req_in <> io.s2_payload_read_req_in
  io.s2_payload_read_rsp_out <> s2.io.s2_payload_read_rsp_out
  s2.io.s2_sidecar_read_req_in <> io.s2_sidecar_read_req_in
  io.s2_sidecar_read_rsp_out <> s2.io.s2_sidecar_read_rsp_out
  s2.io.gqa_consumer_commit_in <> io.gqa_consumer_commit_in
  io.s2_release_out <> s2.io.s2_release_out
  io.s2_component_status_out <> s2.io.component_status_out
  s2.io.s2_observe_slot := io.s2_observe_slot
  endpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  endpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
  endpoint.io.endpoint_slot_in := io.s2_observe_slot
  endpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  endpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  endpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
  s2.io.s2_payload_fragment_in <> endpoint.io.s2_payload_fragment_out
  s2.io.s2_fill_terminal_in <> endpoint.io.s2_fill_terminal_out
}
