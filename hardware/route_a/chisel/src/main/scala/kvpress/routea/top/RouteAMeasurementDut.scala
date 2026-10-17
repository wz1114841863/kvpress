package kvpress.routea.top

import chisel3._
import chisel3.util.DecoupledIO
import kvpress.routea.common._
import kvpress.routea.incremental._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * W0 Route-A production-owner measurement contour.
  *
  * This is functional integration only: it is not a controller, macro,
  * attention PE, numeric pipeline, timing, throughput, or PPA implementation.
  * Only frozen outer environments remain at the boundary.  Packed demand,
  * publication authorization, descriptor grant, and S2 lease are internal
  * owner-to-owner carriers, not testbench inputs.
  */
final class RouteAMeasurementDut(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val source_plan_declaration_in = Flipped(RouteAChannels.source_plan_declaration(p))
    val hot_payload_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val hot_position_sidecar_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val pending_payload_read_binding_in = Flipped(RouteAChannels.pending_payload_read_binding(p))
    val functional_partial_hot_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_pending_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_packed_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_hot_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_partial_pending_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_partial_packed_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_r4_accepted_packet_out = RouteAChannels.r4_accepted_partial_packet(p)
    val functional_r4_merge_work_out = RouteAChannels.merge_req
    val functional_r4_result_in = Flipped(RouteAChannels.r4_result_stub)
    val functional_r4_numeric_fault_in = Flipped(RouteAChannels.r4_numeric_fault)
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
  })

  private def inactive[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.valid := false.B
    channel.bits := 0.U.asTypeOf(channel.bits)
  }
  private def discard[T <: Data](channel: DecoupledIO[T]): Unit = channel.ready := true.B

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val hot = Module(new RouteAHotSourcePath(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  val directPending = Module(new RouteADirectPendingEndpointV1(p))
  val arbiter = Module(new RouteACoreSideArbiter(p))
  val coreMemory = Module(new RouteACoreMemIfV1(p))
  val m2P3 = Module(new RouteAM2P3Wrapper(p))
  val m2Reference = Module(new RouteAM2ReferenceProtocolProvider(p))
  val pageManager = Module(new RouteAPageManager(p))
  val activationBinder = Module(new RouteAPackedReadActivationBinder(p))
  val associationOwner = Module(new RouteAPackedReadAssociationOwner(p))
  val planFork = Module(new RouteASourceCompletionPlanActivationFork(p))
  val hotActivation = Module(new RouteAHotSourcePlanActivationAdapter(p))
  val terminalBridge = Module(new RouteAPackedReadTerminalBridge(p))
  val allocationMux = Module(new RouteAPackedAllocationOwnerMux(p))
  val sidecarDelivery = Module(new RouteAFunctionalSidecarDeliveryAdapter(p))
  val packedReadIngress = Module(new RouteAExclusivePackedS2ReadIngress(p))
  val fillTerminalIngress = Module(new RouteAExclusiveS2FillTerminalIngress(p))
  val admission = Module(new RouteAAdmissionPublicationIngressAdapter(p))
  val writeIngress = Module(new RouteAR2WriteIngressMerge(p))
  val readIngress = Module(new RouteAR2ReadIngressMerge(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val delivery = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpointDemux = Module(new RouteAReadEndpointDemultiplexer(p))
  val pendingIngress = Module(new RouteAExclusiveP3PendingIngress(p))
  val sidecarIngress = Module(new RouteAExclusiveP3SidecarIngress(p))
  val packReadIssue = Module(new RouteAReadIssueCandidateAdapter(p))
  val packedReadProducer = Module(new RouteAPackedS2ReadProducer(p))
  val packedReadIssue = Module(new RouteAReadIssueCandidateAdapter(p))
  val packedSidecarIssue = Module(new RouteAReadIssueCandidateAdapter(p))
  val packReadEndpoint = Module(new RouteAR3PackReadEndpoint(p))
  val packedReadEndpoint = Module(new RouteAPackedS2ReadEndpoint(p))
  val packedSidecarEndpoint = Module(new RouteAS2PackedSidecarReadEndpoint(p))
  val sourcePlanBinder = Module(new RouteASourcePlanBinder(p))
  val packetAdapter = Module(new RouteASourceServicePacketAdapter(p))
  val partialProvider = Module(new RouteAFunctionalPartialProviderBoundary(p))
  val r4Reference = Module(new RouteAFunctionalR4ReferenceBoundary(p))
  val commitDemux = Module(new RouteASourceCommitDemultiplexer(p))
  val merge = Module(new RouteAMergeBoundary(p))
  val statusCollector = Module(new RouteAComponentStatusCollector(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend_lifecycle_req
  lifecycle.io.runtime_retire_req <> io.runtime_retire_req
  io.attention_terminal_rsp <> lifecycle.io.attention_terminal_rsp
  io.session_retire_ack <> lifecycle.io.session_retire_ack
  lifecycle.io.component_status_in <> statusCollector.io.component_status_out

  // The hot owner opens only from the exact R6-accepted plan copy.  The
  // adapter cannot select a source or construct a second plan.
  hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
  hot.io.hot_source_open_in <> hotActivation.io.hot_source_open_out
  lifecycle.io.hot_source_release_in <> hot.io.hot_release_out
  inactive(lifecycle.io.merge_ready_in)
  inactive(directPending.io.pending_source_open_in)
  inactive(directPending.io.direct_pending_record_terminal_in)
  lifecycle.io.pending_source_release_in <> directPending.io.direct_release_out
  discard(lifecycle.io.direct_pending_open)

  sourcePlanBinder.io.declaration_in <> io.source_plan_declaration_in
  lifecycle.io.source_completion_plan_in <> sourcePlanBinder.io.completion_plan_out
  planFork.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
  packetAdapter.io.accepted_plan_in <> planFork.io.packet_plan_out
  hotActivation.io.accepted_plan_in <> planFork.io.hot_activation_plan_out
  activationBinder.io.accepted_plan_in <> planFork.io.packed_activation_plan_out

  s2.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  s2.io.mem_init_done := coreMemory.io.r1_init_complete
  s2.io.service_req_in <> lifecycle.io.s2_service_req
  s2.io.s2_observe_slot := packetAdapter.io.packed_observe_slot_out
  lifecycle.io.packed_source_release_in <> s2.io.s2_release_out

  activationBinder.io.mem_init_done := coreMemory.io.r1_init_complete
  associationOwner.io.mem_init_done := coreMemory.io.r1_init_complete
  pageManager.io.descriptor_location_request_in <> activationBinder.io.descriptor_location_request_out
  activationBinder.io.descriptor_grant_in <> pageManager.io.descriptor_location_grant_out
  s2.io.s2_fill_lease_request_in <> activationBinder.io.s2_fill_lease_request_out
  activationBinder.io.s2_fill_lease_in <> s2.io.s2_fill_lease_out
  associationOwner.io.demand_in <> activationBinder.io.demand_out
  associationOwner.io.publication_authorization_in <> activationBinder.io.publication_authorization_out
  associationOwner.io.descriptor_grant_in <> activationBinder.io.descriptor_grant_out
  associationOwner.io.s2_fill_lease_in <> activationBinder.io.s2_fill_lease_out
  associationOwner.io.invalidation_in.valid := false.B
  associationOwner.io.invalidation_in.bits := 0.U.asTypeOf(new PackedReadInvalidation)
  associationOwner.io.sidecar_read_work_out <> sidecarDelivery.io.work_in
  associationOwner.io.release_observation_out <> sidecarDelivery.io.payload_release_in

  packetAdapter.io.hot_available_in.valid := hot.io.hot_observe_active
  packetAdapter.io.hot_available_in.transaction_identity := hot.io.hot_observe_identity
  packetAdapter.io.hot_available_in.source_instance := hot.io.hot_observe_instance
  packetAdapter.io.pending_available_in.valid := directPending.io.direct_observe_deliverable
  packetAdapter.io.pending_available_in.transaction_identity := directPending.io.direct_observe_identity
  packetAdapter.io.pending_available_in.source_instance := directPending.io.direct_observe_instance
  packetAdapter.io.packed_available_in.valid := s2.io.s2_observe_available
  packetAdapter.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
  packetAdapter.io.packed_available_in.source_instance := s2.io.s2_observe_instance
  partialProvider.io.hot_offer_in <> io.functional_partial_hot_offer_in
  partialProvider.io.pending_offer_in <> io.functional_partial_pending_offer_in
  partialProvider.io.packed_offer_in <> io.functional_partial_packed_offer_in
  partialProvider.io.hot_fragment_in <> io.functional_partial_hot_fragment_in
  partialProvider.io.pending_fragment_in <> io.functional_partial_pending_fragment_in
  partialProvider.io.packed_fragment_in <> io.functional_partial_packed_fragment_in
  packetAdapter.io.hot_offer_in <> partialProvider.io.hot_offer_out
  packetAdapter.io.pending_offer_in <> partialProvider.io.pending_offer_out
  packetAdapter.io.packed_offer_in <> partialProvider.io.packed_offer_out
  packetAdapter.io.hot_fragment_in <> partialProvider.io.hot_fragment_out
  packetAdapter.io.pending_fragment_in <> partialProvider.io.pending_fragment_out
  packetAdapter.io.packed_fragment_in <> partialProvider.io.packed_fragment_out
  merge.io.r4_partial_header_in <> packetAdapter.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packetAdapter.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packetAdapter.io.r4_value_fragment_out
  r4Reference.io.accepted_packet_in <> merge.io.r4_accepted_partial_packet_out
  r4Reference.io.active_merge_observation_in := merge.io.r4_active_merge_observation
  io.functional_r4_accepted_packet_out <> r4Reference.io.accepted_packet_out
  io.functional_r4_merge_work_out <> r4Reference.io.merge_work_out
  r4Reference.io.functional_result_in <> io.functional_r4_result_in
  r4Reference.io.functional_numeric_fault_in <> io.functional_r4_numeric_fault_in
  merge.io.r4_result_stub_in <> r4Reference.io.r4_result_stub_out
  merge.io.r4_numeric_fault_in <> r4Reference.io.r4_numeric_fault_out
  commitDemux.io.commit_in <> merge.io.consumer_partial_commit
  hot.io.gqa_consumer_commit_in <> commitDemux.io.hot_commit_out
  directPending.io.gqa_consumer_commit_in <> commitDemux.io.pending_commit_out
  s2.io.gqa_consumer_commit_in <> commitDemux.io.packed_commit_out
  merge.io.merge_req_in <> lifecycle.io.merge_req
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  inactive(merge.io.source_partial_in)

  arbiter.io.candidate_in <> writeIngress.io.candidate_out
  arbiter.io.read_candidate_in <> readIngress.io.candidate_out
  coreMemory.io.core_mem_req_in <> arbiter.io.core_mem_req
  arbiter.io.core_mem_rsp_in <> coreMemory.io.core_mem_rsp
  coreMemory.io.external_core_mem_if_v1 <> io.external_core_mem_if_v1
  arbiter.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  arbiter.io.reclaim_maintenance_enable := lifecycle.io.reclaim_maintenance_enable
  coreMemory.io.r1_drain_permitted := statusCollector.io.r1_drain_permitted
  registry.io.mem_init_done := coreMemory.io.r1_init_complete
  registry.io.resolve_in <> arbiter.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  delivery.io.release_event_in := router.io.release_event_out
  endpointDemux.io.resolved_in <> router.io.read_fragment_out
  packReadEndpoint.io.resolved_fragment_in <> endpointDemux.io.p3_pack_read_out
  packedReadEndpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_out
  packedSidecarEndpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_sidecar_out
  discard(endpointDemux.io.direct_pending_out)

  // R3 B1 is internal: R3 materializes/owns its candidate, R2/R1 transport
  // it, and the typed delivery alone returns the durable terminal to R3.
  m2P3.io.mem_init_done := coreMemory.io.r1_init_complete
  m2P3.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  directPending.io.mem_init_done := coreMemory.io.r1_init_complete
  directPending.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  pageManager.io.mem_init_done := coreMemory.io.r1_init_complete
  pageManager.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  pageManager.io.reclaim_permit_in <> lifecycle.io.reclaim_permit_out
  lifecycle.io.r5_reclaim_complete_in := pageManager.io.reclaim_complete
  inactive(pageManager.io.descriptor_maintenance_terminal_in)
  discard(pageManager.io.allocator_release_out)

  val r6ToPending = lifecycle.io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
    lifecycle.io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
  admission.io.r6_admission_context_in <> lifecycle.io.admission_context_out
  admission.io.r6_authority_in.valid := lifecycle.io.authority_transition_out.valid && r6ToPending
  admission.io.r6_authority_in.bits := lifecycle.io.authority_transition_out.bits
  lifecycle.io.authority_transition_out.ready := Mux(r6ToPending, admission.io.r6_authority_in.ready, true.B)
  admission.io.pending_payload_binding_in <> io.pending_payload_read_binding_in
  admission.io.r5_allocation_req <> pageManager.io.page_allocation_req_in
  admission.io.r5_allocation_rsp_in <> pageManager.io.page_allocation_rsp
  admission.io.r3_p3_claim <> m2P3.io.p3_claim_in
  admission.io.r3_p3_claim_ack_in <> m2P3.io.p3_claim_ack
  admission.io.r3_admission_context_out <> m2P3.io.admission_context_in
  admission.io.r3_admission_authority_out <> m2P3.io.admission_authority_in
  admission.io.r3_pending_payload_binding_out <> m2P3.io.pending_payload_binding_in
  pendingIngress.io.hot_in <> io.hot_payload_fragment_in
  pendingIngress.io.pack_read_in <> packReadEndpoint.io.p3_pending_fragment_out
  m2P3.io.p3_pending_fragment_in <> pendingIngress.io.out
  m2P3.io.p3_pack_read_work_in.valid := m2P3.io.p3_pack_read_materialized_work_out.valid
  m2P3.io.p3_pack_read_work_in.bits := m2P3.io.p3_pack_read_materialized_work_out.bits
  m2P3.io.p3_pack_read_materialized_work_out.ready := m2P3.io.p3_pack_read_work_in.ready
  when(m2P3.io.p3_pack_fill_reservation_out) {
    assert(!io.hot_payload_fragment_in.valid)
    assert(!io.hot_position_sidecar_in.valid)
  }
  sidecarIngress.io.hot_in <> io.hot_position_sidecar_in
  sidecarIngress.io.pack_read_in <> m2P3.io.p3_materialized_sidecar_out
  m2P3.io.p3_sidecar_bind_in <> sidecarIngress.io.out
  packReadIssue.io.read_issue_in <> m2P3.io.p3_pack_read_issue_out
  inactive(m2P3.io.p3_packed_write_issue_in)
  inactive(m2P3.io.p3_packed_write_terminal_in)
  m2Reference.io.member_request_in <> m2P3.io.m2_group_member_req_out
  m2P3.io.m2_group_member_rsp_in <> m2Reference.io.member_response_out
  m2P3.io.p3_observe_layer := 0.U
  m2Reference.io.publication_candidate_in <> m2P3.io.m2_publish_candidate_out
  m2P3.io.m2_publish_req_in <> m2Reference.io.publication_request_out
  discard(lifecycle.io.metadata_publish_req)
  lifecycle.io.authority_transition_in <> m2P3.io.authority_transition_out
  discard(m2P3.io.publication_commit_observation)
  activationBinder.io.publication_member_in <> m2P3.io.publication_member_observation
  activationBinder.io.post_r6_page_ready_in <> m2P3.io.post_r6_packed_page_ready_observation
  pageManager.io.p3_payload_durable_in <> m2P3.io.p3_payload_durable_out
  m2P3.io.descriptor_durability_prerequisite_in <> pageManager.io.descriptor_durability_prerequisite_out
  pageManager.io.metadata_publish_visibility_in <> m2P3.io.metadata_publish_visibility_apply
  m2P3.io.metadata_publish_visibility_ack_in <> pageManager.io.metadata_publish_visibility_ack
  lifecycle.io.metadata_publish_ack_in <> m2P3.io.m2_publish_ack

  terminalBridge.io.work_in <> associationOwner.io.packed_s2_work_out
  packedReadProducer.io.work_in <> terminalBridge.io.work_out
  packedReadIssue.io.read_issue_in <> packedReadProducer.io.read_issue_out
  sidecarDelivery.io.read_issue_out <> packedSidecarIssue.io.read_issue_in
  allocationMux.io.payload_allocate_in <> associationOwner.io.registry_allocate_out
  allocationMux.io.payload_ordinal_in := associationOwner.io.registry_allocation_arrival_ordinal_out
  allocationMux.io.payload_candidate_id_in := associationOwner.io.registry_allocation_candidate_id_out
  allocationMux.io.sidecar_allocate_in <> sidecarDelivery.io.registry_allocate_out
  allocationMux.io.sidecar_ordinal_in := sidecarDelivery.io.registry_allocation_arrival_ordinal_out
  allocationMux.io.sidecar_candidate_id_in := sidecarDelivery.io.registry_allocation_candidate_id_out
  delivery.io.packed_association_allocate_in <> allocationMux.io.allocate_out
  delivery.io.packed_association_arrival_ordinal_in := allocationMux.io.ordinal_out
  delivery.io.packed_association_candidate_id_in := allocationMux.io.candidate_id_out
  allocationMux.io.ack_in <> delivery.io.packed_association_allocation_ack_out
  associationOwner.io.registry_allocation_ack_in <> allocationMux.io.payload_ack_out
  sidecarDelivery.io.registry_allocation_ack_in <> allocationMux.io.sidecar_ack_out
  delivery.io.r3_packed_write_in <> m2P3.io.p3_packed_write_candidate_out
  delivery.io.r5_append_in <> pageManager.io.append_candidate_out
  inactive(delivery.io.r3_direct_pending_in)
  inactive(delivery.io.r5_s2_packed_in)
  delivery.io.r5_reclaim_in <> pageManager.io.reclaim_candidate_out
  discard(delivery.io.r3_direct_pending_out)
  discard(delivery.io.r5_s2_packed_out)
  delivery.io.r3_pack_read_in <> packReadIssue.io.candidate_out
  delivery.io.registry_allocate_out <> registry.io.allocation_in
  delivery.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  writeIngress.io.r3_packed_write_in <> delivery.io.r3_packed_write_out
  writeIngress.io.r5_append_in <> delivery.io.r5_append_out
  writeIngress.io.r5_reclaim_in <> delivery.io.r5_reclaim_out
  readIngress.io.r3_pack_read_in <> delivery.io.r3_pack_read_out
  inactive(readIngress.io.r3_direct_pending_in)
  packedReadIngress.io.payload_in <> packedReadIssue.io.candidate_out
  packedReadIngress.io.sidecar_in <> packedSidecarIssue.io.candidate_out
  readIngress.io.r5_s2_packed_in <> packedReadIngress.io.out
  m2P3.io.p3_packed_write_delivery_in <> router.io.r3_packed_write_out
  pageManager.io.append_delivery_in <> router.io.r5_append_out
  pageManager.io.reclaim_delivery_in <> router.io.r5_reclaim_out

  packedReadEndpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  packedReadEndpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
  packedReadEndpoint.io.endpoint_slot_in := packedReadProducer.io.s2_fill_open_out.bits.s2_slot
  packedReadEndpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  packedReadEndpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  packedReadEndpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
  terminalBridge.io.endpoint_terminal_in <> packedReadEndpoint.io.s2_fill_terminal_out
  fillTerminalIngress.io.payload_in <> terminalBridge.io.s2_terminal_out
  fillTerminalIngress.io.sidecar_in <> packedSidecarEndpoint.io.s2_fault_terminal_out
  associationOwner.io.terminal_in <> terminalBridge.io.association_terminal_out
  packedSidecarEndpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  packedSidecarEndpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  packedSidecarEndpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  packedSidecarEndpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
  s2.io.s2_fill_open_in <> packedReadProducer.io.s2_fill_open_out
  s2.io.s2_payload_fragment_in <> packedReadEndpoint.io.s2_payload_fragment_out
  s2.io.s2_sidecar_fragment_in <> packedSidecarEndpoint.io.sidecar_fragment_out
  s2.io.s2_fill_terminal_in <> fillTerminalIngress.io.out
  s2.io.s2_sidecar_complete_in <> packedSidecarEndpoint.io.sidecar_complete_out
  inactive(s2.io.s2_payload_read_req_in)
  discard(s2.io.s2_payload_read_rsp_out)
  inactive(s2.io.s2_sidecar_read_req_in)
  discard(s2.io.s2_sidecar_read_rsp_out)

  merge.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  statusCollector.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  statusCollector.io.reclaim_drain_restart := lifecycle.io.reclaim_drain_restart
  statusCollector.io.reclaim_final_drain_enable := lifecycle.io.reclaim_final_drain_enable
  statusCollector.io.status_sources(0) <> coreMemory.io.component_status_out
  statusCollector.io.status_sources(1) <> arbiter.io.payload_drain_status_out
  statusCollector.io.status_sources(2) <> arbiter.io.descriptor_drain_status_out
  statusCollector.io.status_sources(3) <> m2P3.io.component_status_out
  statusCollector.io.status_sources(4) <> pageManager.io.component_status_out
  statusCollector.io.status_sources(5) <> s2.io.component_status_out
  statusCollector.io.status_sources(6) <> directPending.io.component_status_out
  statusCollector.io.status_sources(7) <> merge.io.component_status_out
}
