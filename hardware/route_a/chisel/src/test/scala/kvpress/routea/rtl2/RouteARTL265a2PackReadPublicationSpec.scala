package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAExclusiveP3PendingIngress, RouteAFunctionalPartialProviderBoundary, RouteAFunctionalR4ReferenceBoundary, RouteAReadEndpointDemultiplexer, RouteAReadIssueCandidateAdapter, RouteAPackedS2ReadEndpoint, RouteAPackedS2ReadProducer, RouteAR2ReadIngressMerge, RouteAR2WriteIngressMerge, RouteAR3PackReadEndpoint, RouteAS2GqaSourceWrapper, RouteAS2PackedSidecarReadEndpoint, RouteASourceCommitDemultiplexer, RouteASourceServicePacketAdapter, RouteATypedDeliveryRouter, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.incremental.{RouteAExclusivePackedS2ReadIngress, RouteAExclusiveS2FillTerminalIngress, RouteAFunctionalSidecarDeliveryAdapter, RouteALifecycleAdapter, RouteAM2P3Wrapper, RouteAM2ReferenceProtocolProvider, RouteAMergeBoundary, RouteAPackedAllocationOwnerMux, RouteAPackedReadActivationBinder, RouteAPackedReadAssociationOwner, RouteAPackedReadTerminalBridge, RouteAPageManager, RouteASourceCompletionPlanActivationFork}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.RouteAComponentStatusCollector
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.6.5a.2's test-only composed retained-record witness.  One real R3
  * instance creates the immutable eight-fragment pack read, accepts it only
  * through the existing registry/R2/R1/typed-endpoint chain, and then emits
  * its normal packed-write candidate.  Read and write remain separate frozen
  * R2 ingress lanes; the unified bridge owns only their shared association
  * allocation.  This is functional protocol evidence, not a scheduler,
  * controller, timing, numeric, macro, or PPA realization.
  */
final class RouteARTL265a2PackReadPublicationHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val r5_allocate = Flipped(RouteAChannels.page_allocation_req(p))
    val r5_allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    val p3_claim = Flipped(RouteAChannels.p3_claim(p))
    val admission_context = Flipped(RouteAChannels.admission_context(p))
    val admission_authority = Flipped(RouteAChannels.r6_authority_transition(p))
    val pending_payload_binding = Flipped(RouteAChannels.pending_payload_read_binding(p))
    // B2 selects the already production-shaped R3 materializer feedback.
    // False preserves the historical direct-work compatibility harness.
    val materialize_from_binding = Input(Bool())
    // B3 selects the composition-top's existing functional M2 protocol and
    // R6 publication acceptor. False preserves the prior direct protocol
    // fixture for historical tests; it does not create a second owner.
    val automatic_publication_owner_mode = Input(Bool())
    val r6_frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val r6_component_status_in = Flipped(RouteAChannels.component_status(p))
    val pack_read_work = Flipped(RouteAChannels.p3_pack_read_work(p))
    val p3_sidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val external = new CoreMemoryExternalPort(p)
    val m2_member_request = RouteAChannels.m2_group_member_req(p)
    val m2_member_response = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val m2_publication_candidate = RouteAChannels.metadata_publish_req(p)
    val m2_publication_request = Flipped(RouteAChannels.metadata_publish_req(p))
    val authority_transition = RouteAChannels.r6_authority_transition(p)
    val publication_commit = RouteAChannels.publication_commit_observation(p)
    val publication_member = RouteAChannels.publication_member_observation(p)
    // RTL3.9-C1 test-only activation mode.  It reuses only the production-top
    // owner-to-owner connections from R6's accepted plan through C0/R5/S2 to
    // the existing association owner; it introduces no source selection.
    val c1_demand_activation_mode = Input(Bool())
    // C2 extends that accepted association only after the existing registry
    // acknowledges it.  Low preserves C1's held-allocation predecessor test.
    val c2_read_activation_mode = Input(Bool())
    // C3a consumes only the existing accepted plan and S2 READY observation.
    // Its partial/R4 carriers remain named outer functional environments.
    val c3_terminal_activation_mode = Input(Bool())
    val c3b_retire_reclaim_mode = Input(Bool())
    val c3b_runtime_retire = Flipped(RouteAChannels.runtime_retire_req)
    val c3b_retire_ack = RouteAChannels.session_retire_ack
    val c3b_direct_status = Flipped(RouteAChannels.component_status(p))
    val c3_packed_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val c3_packed_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val c3_r4_result = Flipped(RouteAChannels.r4_result_stub)
    val c3_r4_numeric_fault = Flipped(RouteAChannels.r4_numeric_fault)
    val c3_accepted_packet = RouteAChannels.r4_accepted_partial_packet(p)
    val c3_merge_work = RouteAChannels.merge_req
    val c3_attention_terminal = RouteAChannels.attention_terminal_rsp
    val c1_source_completion_plan = Flipped(RouteAChannels.source_completion_plan(p))
    val c1_page_ready_fire = Output(Bool())
    val c1_demand_fire = Output(Bool())
    val c1_association_active = Output(Bool())
    val c1_registry_allocate = RouteAChannels.delivery_context_allocate(p)
    val c2_s2_state = Output(UInt(3.W))
    val publication_ack = RouteAChannels.metadata_publish_ack(p)
    val r5_visibility_ack_fire = Output(Bool())
    val m2_member_request_fire = Output(Bool())
    val m2_member_response_fire = Output(Bool())
    val m2_publication_candidate_fire = Output(Bool())
    val m2_publication_request_fire = Output(Bool())
    val m2_publish_ack_valid = Output(Bool())
    val r6_publish_ack_ready = Output(Bool())
    val m2_publish_ack_fire = Output(Bool())
    val r6_authority_transition_fire = Output(Bool())
    val r6_authority_transition = Output(new R6AuthorityTransition(p))
    val p3_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
    // RTL2.6.5e test-only outward hooks.  They preserve the existing child
    // owners and let one outer lifecycle harness reclaim the exact R5 page
    // published by this R3 instance; they are not top-level production ports.
    val drain_collection_enable = Input(Bool())
    val reclaim_maintenance_enable = Input(Bool())
    val r1_drain_permitted = Input(Bool())
    val reclaim_permit = Flipped(RouteAChannels.reclaim_permit)
    val reclaim_complete = Output(Bool())
    val r1_status = RouteAChannels.component_status(p)
    val r2_payload_status = RouteAChannels.component_status(p)
    val r2_descriptor_status = RouteAChannels.component_status(p)
    val r3_status = RouteAChannels.component_status(p)
    val r5_status = RouteAChannels.component_status(p)
  })

  val r3 = Module(new RouteAM2P3Wrapper(p))
  val r5 = Module(new RouteAPageManager(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  val m2Reference = Module(new RouteAM2ReferenceProtocolProvider(p))
  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val c1PlanFork = Module(new RouteASourceCompletionPlanActivationFork(p))
  val c1Binder = Module(new RouteAPackedReadActivationBinder(p))
  val c1Association = Module(new RouteAPackedReadAssociationOwner(p))
  val c2AllocationMux = Module(new RouteAPackedAllocationOwnerMux(p))
  val c2TerminalBridge = Module(new RouteAPackedReadTerminalBridge(p))
  val c2SidecarDelivery = Module(new RouteAFunctionalSidecarDeliveryAdapter(p))
  val c2ReadIngress = Module(new RouteAExclusivePackedS2ReadIngress(p))
  val c2PayloadProducer = Module(new RouteAPackedS2ReadProducer(p))
  val c2PayloadIssueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val c2SidecarIssueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val c2PayloadEndpoint = Module(new RouteAPackedS2ReadEndpoint(p))
  val c2SidecarEndpoint = Module(new RouteAS2PackedSidecarReadEndpoint(p))
  val c2TerminalIngress = Module(new RouteAExclusiveS2FillTerminalIngress(p))
  val c3PacketAdapter = Module(new RouteASourceServicePacketAdapter(p))
  val c3PartialProvider = Module(new RouteAFunctionalPartialProviderBoundary(p))
  val c3Merge = Module(new RouteAMergeBoundary(p))
  val c3R4Reference = Module(new RouteAFunctionalR4ReferenceBoundary(p))
  val c3CommitDemux = Module(new RouteASourceCommitDemultiplexer(p))
  val c3bStatusCollector = Module(new RouteAComponentStatusCollector(p))
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val issueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val bridge = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  bridge.io.packed_association_allocate_in <> c2AllocationMux.io.allocate_out
  bridge.io.packed_association_arrival_ordinal_in := c2AllocationMux.io.ordinal_out
  bridge.io.packed_association_candidate_id_in := c2AllocationMux.io.candidate_id_out
  c2AllocationMux.io.ack_in <> bridge.io.packed_association_allocation_ack_out
  val readIngress = Module(new RouteAR2ReadIngressMerge(p))
  val writeIngress = Module(new RouteAR2WriteIngressMerge(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpointDemux = Module(new RouteAReadEndpointDemultiplexer(p))
  val endpoint = Module(new RouteAR3PackReadEndpoint(p))
  val p3Ingress = Module(new RouteAExclusiveP3PendingIngress(p))

  r3.io.mem_init_done := io.mem_init_done
  r3.io.drain_collection_enable := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.drain_collection_enable, io.drain_collection_enable)
  r3.io.p3_claim_in <> io.p3_claim
  r3.io.p3_claim_ack.ready := true.B
  r3.io.admission_context_in <> io.admission_context
  r3.io.admission_authority_in <> io.admission_authority
  r3.io.pending_payload_binding_in <> io.pending_payload_binding
  r3.io.p3_pack_read_work_in.valid := Mux(
    io.materialize_from_binding, r3.io.p3_pack_read_materialized_work_out.valid, io.pack_read_work.valid,
  )
  r3.io.p3_pack_read_work_in.bits := Mux(
    io.materialize_from_binding, r3.io.p3_pack_read_materialized_work_out.bits, io.pack_read_work.bits,
  )
  r3.io.p3_pack_read_materialized_work_out.ready := io.materialize_from_binding && r3.io.p3_pack_read_work_in.ready
  io.pack_read_work.ready := !io.materialize_from_binding && r3.io.p3_pack_read_work_in.ready
  issueAdapter.io.read_issue_in <> r3.io.p3_pack_read_issue_out
  bridge.io.r3_pack_read_in <> issueAdapter.io.candidate_out
  StructuralTieOff.source(bridge.io.r3_direct_pending_in)
  StructuralTieOff.source(bridge.io.r5_s2_packed_in)
  StructuralTieOff.sink(bridge.io.r3_direct_pending_out)
  StructuralTieOff.sink(bridge.io.r5_s2_packed_out)
  r3.io.p3_packed_write_candidate_out <> bridge.io.r3_packed_write_in

  r5.io.mem_init_done := io.mem_init_done
  r5.io.drain_collection_enable := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.drain_collection_enable, io.drain_collection_enable)
  r5.io.allocator_release_out.ready := true.B
  r5.io.page_allocation_req_in <> io.r5_allocate
  io.r5_allocation_rsp <> r5.io.page_allocation_rsp
  r5.io.reclaim_permit_in.valid := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.reclaim_permit_out.valid, io.reclaim_permit.valid)
  r5.io.reclaim_permit_in.bits := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.reclaim_permit_out.bits, io.reclaim_permit.bits)
  lifecycle.io.reclaim_permit_out.ready := io.c3b_retire_reclaim_mode && r5.io.reclaim_permit_in.ready
  io.reclaim_permit.ready := !io.c3b_retire_reclaim_mode && r5.io.reclaim_permit_in.ready
  io.reclaim_complete := r5.io.reclaim_complete
  StructuralTieOff.source(r5.io.descriptor_maintenance_terminal_in)
  r5.io.append_candidate_out <> bridge.io.r5_append_in
  r5.io.p3_payload_durable_in <> r3.io.p3_payload_durable_out
  r3.io.descriptor_durability_prerequisite_in <> r5.io.descriptor_durability_prerequisite_out
  r5.io.metadata_publish_visibility_in <> r3.io.metadata_publish_visibility_apply
  r3.io.metadata_publish_visibility_ack_in <> r5.io.metadata_publish_visibility_ack
  io.r5_visibility_ack_fire := r5.io.metadata_publish_visibility_ack.fire
  r5.io.reclaim_candidate_out <> bridge.io.r5_reclaim_in
  r5.io.reclaim_delivery_in <> router.io.r5_reclaim_out

  // C1 retains the existing R5/S2 owner-local request/grant rules.  C2 may
  // activate only the already-existing typed fill/sidecar carriers below.
  s2.io.mem_init_done := io.mem_init_done
  s2.io.drain_collection_enable := io.c3b_retire_reclaim_mode && lifecycle.io.drain_collection_enable
  s2.io.s2_observe_slot := 1.U
  s2.io.service_req_in.valid := io.c3_terminal_activation_mode && lifecycle.io.s2_service_req.valid
  s2.io.service_req_in.bits := lifecycle.io.s2_service_req.bits
  lifecycle.io.s2_service_req.ready := io.c3_terminal_activation_mode && s2.io.service_req_in.ready
  s2.io.s2_fill_open_in.valid := io.c2_read_activation_mode && c2PayloadProducer.io.s2_fill_open_out.valid
  s2.io.s2_fill_open_in.bits := c2PayloadProducer.io.s2_fill_open_out.bits
  c2PayloadProducer.io.s2_fill_open_out.ready := io.c2_read_activation_mode && s2.io.s2_fill_open_in.ready
  s2.io.s2_payload_fragment_in.valid := io.c2_read_activation_mode && c2PayloadEndpoint.io.s2_payload_fragment_out.valid
  s2.io.s2_payload_fragment_in.bits := c2PayloadEndpoint.io.s2_payload_fragment_out.bits
  c2PayloadEndpoint.io.s2_payload_fragment_out.ready := io.c2_read_activation_mode && s2.io.s2_payload_fragment_in.ready
  s2.io.s2_sidecar_fragment_in.valid := io.c2_read_activation_mode && c2SidecarEndpoint.io.sidecar_fragment_out.valid
  s2.io.s2_sidecar_fragment_in.bits := c2SidecarEndpoint.io.sidecar_fragment_out.bits
  c2SidecarEndpoint.io.sidecar_fragment_out.ready := io.c2_read_activation_mode && s2.io.s2_sidecar_fragment_in.ready
  s2.io.s2_fill_terminal_in.valid := io.c2_read_activation_mode && c2TerminalIngress.io.out.valid
  s2.io.s2_fill_terminal_in.bits := c2TerminalIngress.io.out.bits
  c2TerminalIngress.io.out.ready := io.c2_read_activation_mode && s2.io.s2_fill_terminal_in.ready
  s2.io.s2_sidecar_complete_in.valid := io.c2_read_activation_mode && c2SidecarEndpoint.io.sidecar_complete_out.valid
  s2.io.s2_sidecar_complete_in.bits := c2SidecarEndpoint.io.sidecar_complete_out.bits
  c2SidecarEndpoint.io.sidecar_complete_out.ready := io.c2_read_activation_mode && s2.io.s2_sidecar_complete_in.ready
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  StructuralTieOff.source(s2.io.gqa_consumer_commit_in)
  StructuralTieOff.sink(s2.io.s2_release_out)

  c1Binder.io.mem_init_done := io.mem_init_done
  r5.io.descriptor_location_request_in <> c1Binder.io.descriptor_location_request_out
  c1Binder.io.descriptor_grant_in <> r5.io.descriptor_location_grant_out
  s2.io.s2_fill_lease_request_in <> c1Binder.io.s2_fill_lease_request_out
  c1Binder.io.s2_fill_lease_in <> s2.io.s2_fill_lease_out
  c1Association.io.mem_init_done := io.mem_init_done
  c1Association.io.demand_in <> c1Binder.io.demand_out
  c1Association.io.publication_authorization_in <> c1Binder.io.publication_authorization_out
  c1Association.io.descriptor_grant_in <> c1Binder.io.descriptor_grant_out
  c1Association.io.s2_fill_lease_in <> c1Binder.io.s2_fill_lease_out
  c1Association.io.invalidation_in.valid := false.B
  c1Association.io.invalidation_in.bits := 0.U.asTypeOf(new PackedReadInvalidation)
  // C1's observable held request and C2's existing allocation bridge are
  // mutually exclusive modes.  The mux owns only the payload/sidecar return
  // association; it introduces no new registry lane or arbitration policy.
  io.c1_registry_allocate.valid := !io.c2_read_activation_mode && c1Association.io.registry_allocate_out.valid
  io.c1_registry_allocate.bits := c1Association.io.registry_allocate_out.bits
  c2AllocationMux.io.payload_allocate_in.valid := io.c2_read_activation_mode && c1Association.io.registry_allocate_out.valid
  c2AllocationMux.io.payload_allocate_in.bits := c1Association.io.registry_allocate_out.bits
  c1Association.io.registry_allocate_out.ready := Mux(
    io.c2_read_activation_mode, c2AllocationMux.io.payload_allocate_in.ready, io.c1_registry_allocate.ready,
  )
  c2AllocationMux.io.payload_ordinal_in := c1Association.io.registry_allocation_arrival_ordinal_out
  c2AllocationMux.io.payload_candidate_id_in := c1Association.io.registry_allocation_candidate_id_out
  c1Association.io.registry_allocation_ack_in.valid := io.c2_read_activation_mode && c2AllocationMux.io.payload_ack_out.valid
  c1Association.io.registry_allocation_ack_in.bits := c2AllocationMux.io.payload_ack_out.bits
  c2AllocationMux.io.payload_ack_out.ready := io.c2_read_activation_mode && c1Association.io.registry_allocation_ack_in.ready
  c2TerminalBridge.io.work_in.valid := io.c2_read_activation_mode && c1Association.io.packed_s2_work_out.valid
  c2TerminalBridge.io.work_in.bits := c1Association.io.packed_s2_work_out.bits
  c1Association.io.packed_s2_work_out.ready := Mux(
    io.c2_read_activation_mode, c2TerminalBridge.io.work_in.ready, true.B,
  )
  c2SidecarDelivery.io.work_in.valid := io.c2_read_activation_mode && c1Association.io.sidecar_read_work_out.valid
  c2SidecarDelivery.io.work_in.bits := c1Association.io.sidecar_read_work_out.bits
  c1Association.io.sidecar_read_work_out.ready := Mux(
    io.c2_read_activation_mode, c2SidecarDelivery.io.work_in.ready, true.B,
  )
  c1Association.io.terminal_in.valid := io.c2_read_activation_mode && c2TerminalBridge.io.association_terminal_out.valid
  c1Association.io.terminal_in.bits := c2TerminalBridge.io.association_terminal_out.bits
  c2TerminalBridge.io.association_terminal_out.ready := io.c2_read_activation_mode && c1Association.io.terminal_in.ready
  c2SidecarDelivery.io.payload_release_in.valid := io.c2_read_activation_mode && c1Association.io.release_observation_out.valid
  c2SidecarDelivery.io.payload_release_in.bits := c1Association.io.release_observation_out.bits
  c1Association.io.release_observation_out.ready := Mux(
    io.c2_read_activation_mode, c2SidecarDelivery.io.payload_release_in.ready, true.B,
  )
  c2AllocationMux.io.sidecar_allocate_in <> c2SidecarDelivery.io.registry_allocate_out
  c2AllocationMux.io.sidecar_ordinal_in := c2SidecarDelivery.io.registry_allocation_arrival_ordinal_out
  c2AllocationMux.io.sidecar_candidate_id_in := c2SidecarDelivery.io.registry_allocation_candidate_id_out
  c2SidecarDelivery.io.registry_allocation_ack_in <> c2AllocationMux.io.sidecar_ack_out
  io.c1_demand_fire := c1Binder.io.demand_out.fire
  io.c1_association_active := c1Association.io.association_active
  io.c2_s2_state := s2.io.s2_observe_state

  readIngress.io.r3_pack_read_in <> bridge.io.r3_pack_read_out
  StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
  c2PayloadIssueAdapter.io.read_issue_in <> c2PayloadProducer.io.read_issue_out
  c2SidecarIssueAdapter.io.read_issue_in <> c2SidecarDelivery.io.read_issue_out
  c2ReadIngress.io.payload_in <> c2PayloadIssueAdapter.io.candidate_out
  c2ReadIngress.io.sidecar_in <> c2SidecarIssueAdapter.io.candidate_out
  readIngress.io.r5_s2_packed_in <> c2ReadIngress.io.out
  c2TerminalBridge.io.work_out <> c2PayloadProducer.io.work_in
  c2TerminalBridge.io.endpoint_terminal_in <> c2PayloadEndpoint.io.s2_fill_terminal_out
  c2TerminalIngress.io.payload_in <> c2TerminalBridge.io.s2_terminal_out
  c2TerminalIngress.io.sidecar_in <> c2SidecarEndpoint.io.s2_fault_terminal_out
  r2.io.read_candidate_in <> readIngress.io.candidate_out
  writeIngress.io.r3_packed_write_in <> bridge.io.r3_packed_write_out
  writeIngress.io.r5_append_in <> bridge.io.r5_append_out
  writeIngress.io.r5_reclaim_in <> bridge.io.r5_reclaim_out
  r2.io.candidate_in <> writeIngress.io.candidate_out
  r2.io.drain_collection_enable := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.drain_collection_enable, io.drain_collection_enable)
  r2.io.reclaim_maintenance_enable := Mux(io.c3b_retire_reclaim_mode, lifecycle.io.reclaim_maintenance_enable, io.reclaim_maintenance_enable)
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  r1.io.external_core_mem_if_v1 <> io.external
  r1.io.r1_drain_permitted := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.r1_drain_permitted, io.r1_drain_permitted)

  registry.io.mem_init_done := r1.io.r1_init_complete
  registry.io.allocation_in <> bridge.io.registry_allocate_out
  bridge.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  registry.io.resolve_in <> r2.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  bridge.io.release_event_in := router.io.release_event_out
  r3.io.p3_packed_write_delivery_in <> router.io.r3_packed_write_out
  r5.io.append_delivery_in <> router.io.r5_append_out
  endpointDemux.io.resolved_in <> router.io.read_fragment_out
  endpoint.io.resolved_fragment_in <> endpointDemux.io.p3_pack_read_out
  StructuralTieOff.sink(endpointDemux.io.direct_pending_out)
  c2PayloadEndpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_out
  c2SidecarEndpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_sidecar_out
  c2PayloadEndpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  c2PayloadEndpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
  c2PayloadEndpoint.io.endpoint_slot_in := c2PayloadProducer.io.s2_fill_open_out.bits.s2_slot
  c2PayloadEndpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  c2PayloadEndpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  c2PayloadEndpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
  c2SidecarEndpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  c2SidecarEndpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  c2SidecarEndpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  c2SidecarEndpoint.io.endpoint_generation_in := s2.io.s2_observe_generation

  StructuralTieOff.source(p3Ingress.io.hot_in)
  p3Ingress.io.pack_read_in <> endpoint.io.p3_pending_fragment_out
  r3.io.p3_pending_fragment_in <> p3Ingress.io.out
  r3.io.p3_sidecar_bind_in.valid := Mux(
    io.materialize_from_binding, r3.io.p3_materialized_sidecar_out.valid, io.p3_sidecar.valid,
  )
  r3.io.p3_sidecar_bind_in.bits := Mux(
    io.materialize_from_binding, r3.io.p3_materialized_sidecar_out.bits, io.p3_sidecar.bits,
  )
  r3.io.p3_materialized_sidecar_out.ready := io.materialize_from_binding && r3.io.p3_sidecar_bind_in.ready
  io.p3_sidecar.ready := !io.materialize_from_binding && r3.io.p3_sidecar_bind_in.ready
  StructuralTieOff.source(r3.io.p3_packed_write_issue_in)
  StructuralTieOff.source(r3.io.p3_packed_write_terminal_in)
  m2Reference.io.member_request_in.valid := io.automatic_publication_owner_mode && r3.io.m2_group_member_req_out.valid
  m2Reference.io.member_request_in.bits := r3.io.m2_group_member_req_out.bits
  io.m2_member_request.valid := !io.automatic_publication_owner_mode && r3.io.m2_group_member_req_out.valid
  io.m2_member_request.bits := r3.io.m2_group_member_req_out.bits
  r3.io.m2_group_member_req_out.ready := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.member_request_in.ready, io.m2_member_request.ready,
  )
  io.m2_member_request_fire := r3.io.m2_group_member_req_out.fire
  r3.io.m2_group_member_rsp_in.valid := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.member_response_out.valid, io.m2_member_response.valid,
  )
  r3.io.m2_group_member_rsp_in.bits := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.member_response_out.bits, io.m2_member_response.bits,
  )
  m2Reference.io.member_response_out.ready := io.automatic_publication_owner_mode && r3.io.m2_group_member_rsp_in.ready
  io.m2_member_response.ready := !io.automatic_publication_owner_mode && r3.io.m2_group_member_rsp_in.ready
  io.m2_member_response_fire := r3.io.m2_group_member_rsp_in.fire

  m2Reference.io.publication_candidate_in.valid := io.automatic_publication_owner_mode && r3.io.m2_publish_candidate_out.valid
  m2Reference.io.publication_candidate_in.bits := r3.io.m2_publish_candidate_out.bits
  io.m2_publication_candidate.valid := !io.automatic_publication_owner_mode && r3.io.m2_publish_candidate_out.valid
  io.m2_publication_candidate.bits := r3.io.m2_publish_candidate_out.bits
  r3.io.m2_publish_candidate_out.ready := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.publication_candidate_in.ready, io.m2_publication_candidate.ready,
  )
  io.m2_publication_candidate_fire := r3.io.m2_publish_candidate_out.fire
  r3.io.m2_publish_req_in.valid := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.publication_request_out.valid, io.m2_publication_request.valid,
  )
  r3.io.m2_publish_req_in.bits := Mux(
    io.automatic_publication_owner_mode, m2Reference.io.publication_request_out.bits, io.m2_publication_request.bits,
  )
  m2Reference.io.publication_request_out.ready := io.automatic_publication_owner_mode && r3.io.m2_publish_req_in.ready
  io.m2_publication_request.ready := !io.automatic_publication_owner_mode && r3.io.m2_publish_req_in.ready
  io.m2_publication_request_fire := r3.io.m2_publish_req_in.fire

  lifecycle.io.frontend_lifecycle_req <> io.r6_frontend_lifecycle_req
  // C3b uses the production collector ordering, rather than inventing an
  // alternate retirement authority.  Outside C3b the historical direct R6
  // status fixture remains intact.
  c3bStatusCollector.io.drain_collection_enable := io.c3b_retire_reclaim_mode && lifecycle.io.drain_collection_enable
  c3bStatusCollector.io.reclaim_drain_restart := io.c3b_retire_reclaim_mode && lifecycle.io.reclaim_drain_restart
  c3bStatusCollector.io.reclaim_final_drain_enable := io.c3b_retire_reclaim_mode && lifecycle.io.reclaim_final_drain_enable
  lifecycle.io.component_status_in.valid := Mux(
    io.c3b_retire_reclaim_mode,
    c3bStatusCollector.io.component_status_out.valid,
    io.r6_component_status_in.valid,
  )
  lifecycle.io.component_status_in.bits := Mux(
    io.c3b_retire_reclaim_mode,
    c3bStatusCollector.io.component_status_out.bits,
    io.r6_component_status_in.bits,
  )
  c3bStatusCollector.io.component_status_out.ready := io.c3b_retire_reclaim_mode && lifecycle.io.component_status_in.ready
  io.r6_component_status_in.ready := !io.c3b_retire_reclaim_mode && lifecycle.io.component_status_in.ready
  lifecycle.io.runtime_retire_req.valid := io.c3b_retire_reclaim_mode && io.c3b_runtime_retire.valid
  lifecycle.io.runtime_retire_req.bits := io.c3b_runtime_retire.bits
  io.c3b_runtime_retire.ready := io.c3b_retire_reclaim_mode && lifecycle.io.runtime_retire_req.ready
  io.c3_attention_terminal.valid := io.c3_terminal_activation_mode && lifecycle.io.attention_terminal_rsp.valid
  io.c3_attention_terminal.bits := lifecycle.io.attention_terminal_rsp.bits
  lifecycle.io.attention_terminal_rsp.ready := Mux(io.c3_terminal_activation_mode, io.c3_attention_terminal.ready, true.B)
  io.c3b_retire_ack.valid := io.c3b_retire_reclaim_mode && lifecycle.io.session_retire_ack.valid
  io.c3b_retire_ack.bits := lifecycle.io.session_retire_ack.bits
  lifecycle.io.session_retire_ack.ready := Mux(io.c3b_retire_reclaim_mode, io.c3b_retire_ack.ready, true.B)
  lifecycle.io.r5_reclaim_complete_in := io.c3b_retire_reclaim_mode && r5.io.reclaim_complete
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  lifecycle.io.source_completion_plan_in.valid := io.c1_demand_activation_mode && io.c1_source_completion_plan.valid
  lifecycle.io.source_completion_plan_in.bits := io.c1_source_completion_plan.bits
  io.c1_source_completion_plan.ready := io.c1_demand_activation_mode && lifecycle.io.source_completion_plan_in.ready
  c1PlanFork.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
  c1Binder.io.accepted_plan_in <> c1PlanFork.io.packed_activation_plan_out
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  lifecycle.io.packed_source_release_in.valid := io.c3_terminal_activation_mode && s2.io.s2_release_out.valid
  lifecycle.io.packed_source_release_in.bits := s2.io.s2_release_out.bits
  s2.io.s2_release_out.ready := io.c3_terminal_activation_mode && lifecycle.io.packed_source_release_in.ready
  c3PacketAdapter.io.accepted_plan_in.valid := io.c3_terminal_activation_mode && c1PlanFork.io.packet_plan_out.valid
  c3PacketAdapter.io.accepted_plan_in.bits := c1PlanFork.io.packet_plan_out.bits
  c1PlanFork.io.packet_plan_out.ready := Mux(io.c3_terminal_activation_mode, c3PacketAdapter.io.accepted_plan_in.ready, true.B)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  c3Merge.io.merge_req_in.valid := io.c3_terminal_activation_mode && lifecycle.io.merge_req.valid
  c3Merge.io.merge_req_in.bits := lifecycle.io.merge_req.bits
  lifecycle.io.merge_req.ready := io.c3_terminal_activation_mode && c3Merge.io.merge_req_in.ready
  lifecycle.io.merge_terminal_in.valid := io.c3_terminal_activation_mode && c3Merge.io.merge_rsp_or_numeric_fault.valid
  lifecycle.io.merge_terminal_in.bits := c3Merge.io.merge_rsp_or_numeric_fault.bits
  c3Merge.io.merge_rsp_or_numeric_fault.ready := io.c3_terminal_activation_mode && lifecycle.io.merge_terminal_in.ready
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  // C3b selects this owner-local acknowledgement; predecessor modes keep it inactive.

  // C3a mirrors the existing production source-service/R4 composition for its
  // packed-only plan.  It does not generate a partial, result, source release,
  // or terminal: those remain with the named outer environment and child owners.
  c3PacketAdapter.io.hot_available_in.valid := false.B
  c3PacketAdapter.io.hot_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  c3PacketAdapter.io.hot_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  c3PacketAdapter.io.pending_available_in.valid := false.B
  c3PacketAdapter.io.pending_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  c3PacketAdapter.io.pending_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  c3PacketAdapter.io.packed_available_in.valid := s2.io.s2_observe_available
  c3PacketAdapter.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
  c3PacketAdapter.io.packed_available_in.source_instance := s2.io.s2_observe_instance
  StructuralTieOff.source(c3PartialProvider.io.hot_offer_in)
  StructuralTieOff.source(c3PartialProvider.io.pending_offer_in)
  c3PartialProvider.io.packed_offer_in <> io.c3_packed_offer
  StructuralTieOff.source(c3PartialProvider.io.hot_fragment_in)
  StructuralTieOff.source(c3PartialProvider.io.pending_fragment_in)
  c3PartialProvider.io.packed_fragment_in <> io.c3_packed_fragment
  c3PacketAdapter.io.hot_offer_in <> c3PartialProvider.io.hot_offer_out
  c3PacketAdapter.io.pending_offer_in <> c3PartialProvider.io.pending_offer_out
  c3PacketAdapter.io.packed_offer_in <> c3PartialProvider.io.packed_offer_out
  c3PacketAdapter.io.hot_fragment_in <> c3PartialProvider.io.hot_fragment_out
  c3PacketAdapter.io.pending_fragment_in <> c3PartialProvider.io.pending_fragment_out
  c3PacketAdapter.io.packed_fragment_in <> c3PartialProvider.io.packed_fragment_out
  c3Merge.io.drain_collection_enable := io.c3b_retire_reclaim_mode && lifecycle.io.drain_collection_enable
  StructuralTieOff.source(c3Merge.io.source_partial_in)
  c3Merge.io.r4_partial_header_in <> c3PacketAdapter.io.r4_partial_header_out
  c3Merge.io.r4_source_instance_in <> c3PacketAdapter.io.r4_source_instance_out
  c3Merge.io.r4_value_fragment_in <> c3PacketAdapter.io.r4_value_fragment_out
  c3R4Reference.io.accepted_packet_in <> c3Merge.io.r4_accepted_partial_packet_out
  c3R4Reference.io.active_merge_observation_in := c3Merge.io.r4_active_merge_observation
  io.c3_accepted_packet <> c3R4Reference.io.accepted_packet_out
  io.c3_merge_work <> c3R4Reference.io.merge_work_out
  c3R4Reference.io.functional_result_in <> io.c3_r4_result
  c3R4Reference.io.functional_numeric_fault_in <> io.c3_r4_numeric_fault
  c3Merge.io.r4_result_stub_in <> c3R4Reference.io.r4_result_stub_out
  c3Merge.io.r4_numeric_fault_in <> c3R4Reference.io.r4_numeric_fault_out
  c3CommitDemux.io.commit_in <> c3Merge.io.consumer_partial_commit
  StructuralTieOff.sink(c3CommitDemux.io.hot_commit_out)
  StructuralTieOff.sink(c3CommitDemux.io.pending_commit_out)
  s2.io.gqa_consumer_commit_in <> c3CommitDemux.io.packed_commit_out

  lifecycle.io.metadata_publish_ack_in.valid := io.automatic_publication_owner_mode && r3.io.m2_publish_ack.valid
  lifecycle.io.metadata_publish_ack_in.bits := r3.io.m2_publish_ack.bits
  io.publication_ack.valid := !io.automatic_publication_owner_mode && r3.io.m2_publish_ack.valid
  io.publication_ack.bits := r3.io.m2_publish_ack.bits
  r3.io.m2_publish_ack.ready := Mux(
    io.automatic_publication_owner_mode, lifecycle.io.metadata_publish_ack_in.ready, io.publication_ack.ready,
  )
  io.m2_publish_ack_valid := r3.io.m2_publish_ack.valid
  io.r6_publish_ack_ready := lifecycle.io.metadata_publish_ack_in.ready
  io.m2_publish_ack_fire := r3.io.m2_publish_ack.fire

  lifecycle.io.authority_transition_in.valid := io.automatic_publication_owner_mode && r3.io.authority_transition_out.valid
  lifecycle.io.authority_transition_in.bits := r3.io.authority_transition_out.bits
  io.authority_transition.valid := !io.automatic_publication_owner_mode && r3.io.authority_transition_out.valid
  io.authority_transition.bits := r3.io.authority_transition_out.bits
  r3.io.authority_transition_out.ready := Mux(
    io.automatic_publication_owner_mode, lifecycle.io.authority_transition_in.ready, io.authority_transition.ready,
  )
  io.r6_authority_transition_fire := lifecycle.io.authority_transition_in.fire
  io.r6_authority_transition := r3.io.authority_transition_out.bits
  io.publication_commit <> r3.io.publication_commit_observation
  io.publication_member.valid := !io.c1_demand_activation_mode && r3.io.publication_member_observation.valid
  io.publication_member.bits := r3.io.publication_member_observation.bits
  c1Binder.io.publication_member_in.valid := io.c1_demand_activation_mode && r3.io.publication_member_observation.valid
  c1Binder.io.publication_member_in.bits := r3.io.publication_member_observation.bits
  r3.io.publication_member_observation.ready := Mux(
    io.c1_demand_activation_mode, c1Binder.io.publication_member_in.ready, io.publication_member.ready,
  )
  c1Binder.io.post_r6_page_ready_in.valid := io.c1_demand_activation_mode && r3.io.post_r6_packed_page_ready_observation.valid
  c1Binder.io.post_r6_page_ready_in.bits := r3.io.post_r6_packed_page_ready_observation.bits
  r3.io.post_r6_packed_page_ready_observation.ready := Mux(
    io.c1_demand_activation_mode, c1Binder.io.post_r6_page_ready_in.ready, true.B,
  )
  io.c1_page_ready_fire := r3.io.post_r6_packed_page_ready_observation.fire
  // Sources 0--7 deliberately mirror RouteAKVSubsystemTop.  Direct-pending
  // remains an explicit outer functional environment in this composed
  // packed-only witness; it neither reads this page nor owns authority.
  c3bStatusCollector.io.status_sources(0).valid := io.c3b_retire_reclaim_mode && r1.io.component_status_out.valid
  c3bStatusCollector.io.status_sources(0).bits := r1.io.component_status_out.bits
  r1.io.component_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(0).ready, io.r1_status.ready)
  io.r1_status.valid := !io.c3b_retire_reclaim_mode && r1.io.component_status_out.valid
  io.r1_status.bits := r1.io.component_status_out.bits

  c3bStatusCollector.io.status_sources(1).valid := io.c3b_retire_reclaim_mode && r2.io.payload_drain_status_out.valid
  c3bStatusCollector.io.status_sources(1).bits := r2.io.payload_drain_status_out.bits
  r2.io.payload_drain_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(1).ready, io.r2_payload_status.ready)
  io.r2_payload_status.valid := !io.c3b_retire_reclaim_mode && r2.io.payload_drain_status_out.valid
  io.r2_payload_status.bits := r2.io.payload_drain_status_out.bits

  c3bStatusCollector.io.status_sources(2).valid := io.c3b_retire_reclaim_mode && r2.io.descriptor_drain_status_out.valid
  c3bStatusCollector.io.status_sources(2).bits := r2.io.descriptor_drain_status_out.bits
  r2.io.descriptor_drain_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(2).ready, io.r2_descriptor_status.ready)
  io.r2_descriptor_status.valid := !io.c3b_retire_reclaim_mode && r2.io.descriptor_drain_status_out.valid
  io.r2_descriptor_status.bits := r2.io.descriptor_drain_status_out.bits

  c3bStatusCollector.io.status_sources(3).valid := io.c3b_retire_reclaim_mode && r3.io.component_status_out.valid
  c3bStatusCollector.io.status_sources(3).bits := r3.io.component_status_out.bits
  r3.io.component_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(3).ready, io.r3_status.ready)
  io.r3_status.valid := !io.c3b_retire_reclaim_mode && r3.io.component_status_out.valid
  io.r3_status.bits := r3.io.component_status_out.bits

  c3bStatusCollector.io.status_sources(4).valid := io.c3b_retire_reclaim_mode && r5.io.component_status_out.valid
  c3bStatusCollector.io.status_sources(4).bits := r5.io.component_status_out.bits
  r5.io.component_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(4).ready, io.r5_status.ready)
  io.r5_status.valid := !io.c3b_retire_reclaim_mode && r5.io.component_status_out.valid
  io.r5_status.bits := r5.io.component_status_out.bits

  c3bStatusCollector.io.status_sources(5).valid := io.c3b_retire_reclaim_mode && s2.io.component_status_out.valid
  c3bStatusCollector.io.status_sources(5).bits := s2.io.component_status_out.bits
  s2.io.component_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(5).ready, true.B)

  c3bStatusCollector.io.status_sources(6).valid := io.c3b_retire_reclaim_mode && io.c3b_direct_status.valid
  c3bStatusCollector.io.status_sources(6).bits := io.c3b_direct_status.bits
  io.c3b_direct_status.ready := io.c3b_retire_reclaim_mode && c3bStatusCollector.io.status_sources(6).ready

  c3bStatusCollector.io.status_sources(7).valid := io.c3b_retire_reclaim_mode && c3Merge.io.component_status_out.valid
  c3bStatusCollector.io.status_sources(7).bits := c3Merge.io.component_status_out.bits
  c3Merge.io.component_status_out.ready := Mux(io.c3b_retire_reclaim_mode, c3bStatusCollector.io.status_sources(7).ready, true.B)
  r3.io.p3_observe_layer := 0.U
  io.p3_state := r3.io.p3_observe_state
}

/** Directed no-model RTL2.6.5a.2 protocol evidence. */
final class RouteARTL265a2PackReadPublicationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private val packReadEligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) |
    (1 << RouteAR2PredicateBits.Ownership) |
    (1 << RouteAR2PredicateBits.SourceCredit) |
    (1 << RouteAR2PredicateBits.DestinationReady) |
    (1 << RouteAR2PredicateBits.PendingAuthoritative) |
    (1 << RouteAR2PredicateBits.P3StageReadyOwned)

  private def init(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.r5_allocate.valid.poke(false.B); d.io.r5_allocation_rsp.ready.poke(true.B)
    d.io.p3_claim.valid.poke(false.B); d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B); d.io.pending_payload_binding.valid.poke(false.B)
    d.io.materialize_from_binding.poke(false.B)
    d.io.automatic_publication_owner_mode.poke(false.B)
    d.io.c1_demand_activation_mode.poke(false.B)
    d.io.c2_read_activation_mode.poke(false.B)
    d.io.c3_terminal_activation_mode.poke(false.B)
    d.io.c3b_retire_reclaim_mode.poke(false.B)
    d.io.c3b_runtime_retire.valid.poke(false.B)
    d.io.c3b_retire_ack.ready.poke(true.B)
    d.io.c3b_direct_status.valid.poke(false.B)
    d.io.c3b_direct_status.bits.acknowledgement_name.poke(0.U)
    d.io.c3b_direct_status.bits.asserted.poke(false.B)
    d.io.c3_packed_offer.valid.poke(false.B)
    d.io.c3_packed_fragment.valid.poke(false.B)
    d.io.c3_r4_result.valid.poke(false.B)
    d.io.c3_r4_numeric_fault.valid.poke(false.B)
    d.io.c3_accepted_packet.ready.poke(true.B)
    d.io.c3_merge_work.ready.poke(true.B)
    d.io.c3_attention_terminal.ready.poke(true.B)
    d.io.c1_source_completion_plan.valid.poke(false.B)
    val c1Plan = d.io.c1_source_completion_plan.bits
    c1Plan.transaction_identity.request_id.poke(0.U); c1Plan.transaction_identity.incarnation.poke(0.U)
    c1Plan.source_presence.poke(0.U)
    Seq(c1Plan.hot_instance, c1Plan.pending_instance, c1Plan.packed_instance).foreach { instance =>
      instance.source_kind.poke(0.U); instance.instance_coordinate.poke(0.U); instance.generation.poke(0.U)
    }
    d.io.c1_registry_allocate.ready.poke(false.B)
    d.io.pack_read_work.valid.poke(false.B); d.io.p3_sidecar.valid.poke(false.B)
    d.io.m2_member_request.ready.poke(false.B); d.io.m2_member_response.valid.poke(false.B)
    d.io.m2_publication_candidate.ready.poke(false.B); d.io.m2_publication_request.valid.poke(false.B)
    d.io.authority_transition.ready.poke(false.B); d.io.publication_commit.ready.poke(false.B); d.io.publication_member.ready.poke(false.B); d.io.publication_ack.ready.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.drain_collection_enable.poke(false.B); d.io.reclaim_maintenance_enable.poke(false.B); d.io.r1_drain_permitted.poke(false.B)
    d.io.reclaim_permit.valid.poke(false.B); d.io.reclaim_permit.bits.transaction_identity.request_id.poke(0.U); d.io.reclaim_permit.bits.transaction_identity.incarnation.poke(0.U)
    d.io.r1_status.ready.poke(true.B); d.io.r2_payload_status.ready.poke(true.B); d.io.r2_descriptor_status.ready.poke(true.B); d.io.r3_status.ready.poke(true.B); d.io.r5_status.ready.poke(true.B)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.r6_frontend_lifecycle_req.valid.poke(false.B)
    val frontend = d.io.r6_frontend_lifecycle_req.bits
    frontend.event_kind.poke(0.U); frontend.session_id.poke(false.B); frontend.context_tokens.poke(0.U)
    frontend.entry_id.poke(0.U); frontend.layer.poke(0.U); frontend.kv_head.poke(0.U); frontend.logical_position.poke(0.U)
    frontend.payload_ref.poke(0.U); frontend.disposition.poke(false.B)
    frontend.transaction_identity.request_id.poke(0.U); frontend.transaction_identity.incarnation.poke(0.U)
    frontend.admission_group_tag.poke(0.U); frontend.admission_member_ordinal.poke(0.U); frontend.admission_group_valid_records.poke(0.U)
    d.io.r6_component_status_in.valid.poke(false.B)
    d.io.r6_component_status_in.bits.acknowledgement_name.poke(0.U); d.io.r6_component_status_in.bits.asserted.poke(false.B)
    d.io.mem_init_done.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
  }

  private def initializeR6ForPublication(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach { code =>
      d.io.r6_component_status_in.bits.acknowledgement_name.poke(code.U)
      d.io.r6_component_status_in.bits.asserted.poke(true.B); d.io.r6_component_status_in.valid.poke(true.B)
      d.io.r6_component_status_in.ready.expect(true.B); d.clock.step(); d.io.r6_component_status_in.valid.poke(false.B)
    }
    val frontend = d.io.r6_frontend_lifecycle_req.bits
    frontend.event_kind.poke(p.r6.sessionStartEventCode.U); frontend.session_id.poke(false.B); frontend.context_tokens.poke(32768.U)
    d.io.r6_frontend_lifecycle_req.valid.poke(true.B); d.io.r6_frontend_lifecycle_req.ready.expect(true.B)
    d.clock.step(); d.io.r6_frontend_lifecycle_req.valid.poke(false.B)
    d.io.r6_publish_ack_ready.expect(true.B)
  }

  private def registerC1PackedAttention(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    val frontend = d.io.r6_frontend_lifecycle_req.bits
    frontend.event_kind.poke(p.r6.attentionServiceEventCode.U); frontend.session_id.poke(false.B); frontend.context_tokens.poke(0.U)
    frontend.entry_id.poke(0.U); frontend.layer.poke(0.U); frontend.kv_head.poke(0.U); frontend.logical_position.poke(0.U)
    frontend.payload_ref.poke(0.U); frontend.disposition.poke(false.B)
    frontend.transaction_identity.request_id.poke(3.U); frontend.transaction_identity.incarnation.poke(0.U)
    frontend.admission_group_tag.poke(0.U); frontend.admission_member_ordinal.poke(0.U); frontend.admission_group_valid_records.poke(0.U)
    d.io.r6_frontend_lifecycle_req.valid.poke(true.B); d.io.r6_frontend_lifecycle_req.ready.expect(true.B)
    d.clock.step(); d.io.r6_frontend_lifecycle_req.valid.poke(false.B)
  }

  private def sendC1PackedPlan(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    val plan = d.io.c1_source_completion_plan.bits
    plan.transaction_identity.request_id.poke(3.U); plan.transaction_identity.incarnation.poke(0.U)
    plan.source_presence.poke(4.U)
    plan.hot_instance.source_kind.poke(RouteASourceKind.Hot.U); plan.hot_instance.instance_coordinate.poke(0.U); plan.hot_instance.generation.poke(0.U)
    plan.pending_instance.source_kind.poke(RouteASourceKind.Pending.U); plan.pending_instance.instance_coordinate.poke(0.U); plan.pending_instance.generation.poke(0.U)
    plan.packed_instance.source_kind.poke(RouteASourceKind.Packed.U); plan.packed_instance.instance_coordinate.poke(1.U); plan.packed_instance.generation.poke(1.U)
    d.io.c1_source_completion_plan.valid.poke(true.B)
    var waited = 0
    while (!d.io.c1_source_completion_plan.ready.peek().litToBoolean && waited < 32) { d.clock.step(); waited += 1 }
    require(waited < 32, "timed out waiting for the accepted R6 packed plan")
    d.clock.step(); d.io.c1_source_completion_plan.valid.poke(false.B)
  }

  private def waitRequest(d: RouteARTL265a2PackReadPublicationHarness, kind: Int, index: Int): (Int, Int) = {
    var waited = 0
    while (!d.io.external.request.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, s"timed out waiting for kind=$kind index=$index")
    d.io.external.request.bits.request_kind.expect(kind.U)
    d.io.external.request.bits.fragment_index.expect(index.U)
    val requestId = d.io.external.request.bits.transaction_identity.request_id.peek().litValue.toInt
    val incarnation = d.io.external.request.bits.transaction_identity.incarnation.peek().litValue.toInt
    d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
    (requestId, incarnation)
  }

  private def response(d: RouteARTL265a2PackReadPublicationHarness, requestId: Int, fragment: Int, last: Boolean, fault: Boolean = false, incarnation: Int = 0): Unit = {
    val rsp = d.io.external.response.bits
    rsp.transaction_identity.request_id.poke(requestId.U); rsp.transaction_identity.incarnation.poke(incarnation.U)
    rsp.fragment_index.poke(fragment.U); rsp.last.poke(last.B); rsp.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U); rsp.data.poke((0x100 + fragment).U)
    d.io.external.response.valid.poke(true.B)
    var waited = 0
    while (!d.io.external.response.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, "timed out waiting for response acceptance")
    d.clock.step(); d.io.external.response.valid.poke(false.B); d.clock.step(2)
  }

  private def c3PackedPacket(d: RouteARTL265a2PackReadPublicationHarness, consumer: Int): Unit = {
    val offer = d.io.c3_packed_offer.bits
    offer.transaction_identity.request_id.poke(3.U); offer.transaction_identity.incarnation.poke(0.U)
    offer.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
    offer.source_instance.instance_coordinate.poke(1.U); offer.source_instance.generation.poke(1.U)
    offer.consumer_id.poke(consumer.U)
    offer.r4_header.poke(((BigInt(RouteASourceKind.Packed) << 64) | (BigInt(consumer) << 66) | (BigInt(1) << 69) | (BigInt(8) << 70)).U)
    offer.partial_present.poke(true.B)
    d.io.c3_packed_offer.valid.poke(true.B)
    var waited = 0
    while (!d.io.c3_packed_offer.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, "timed out waiting for C3 packed partial offer")
    d.clock.step(); d.io.c3_packed_offer.valid.poke(false.B)
    // The offer advances the packet adapter to its header state.  Preserve a
    // distinct header/sideband acceptance cycle before the first fragment.
    d.clock.step()
    (0 until 8).foreach { index =>
      val fragment = d.io.c3_packed_fragment.bits
      fragment.transaction_identity.request_id.poke(3.U); fragment.transaction_identity.incarnation.poke(0.U)
      fragment.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
      fragment.source_instance.instance_coordinate.poke(1.U); fragment.source_instance.generation.poke(1.U)
      fragment.consumer_id.poke(consumer.U); fragment.fragment_index.poke(index.U)
      fragment.last.poke((index == 7).B); fragment.data.poke((0x300 + consumer * 8 + index).U)
      d.io.c3_packed_fragment.valid.poke(true.B)
      waited = 0
      while (!d.io.c3_packed_fragment.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for C3 packed partial fragment")
      d.clock.step(); d.io.c3_packed_fragment.valid.poke(false.B)
    }
  }

  private def c3CompleteMerge(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    (0 until 4).foreach { expectedConsumer =>
      var waited = 0
      while (!d.io.c3_merge_work.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for C3 R4 merge work")
      d.io.c3_merge_work.bits.transaction_identity.request_id.expect(3.U)
      d.io.c3_merge_work.bits.consumer_id.expect(expectedConsumer.U)
      d.io.c3_merge_work.ready.poke(true.B); d.clock.step(); d.io.c3_merge_work.ready.poke(false.B)
      val result = d.io.c3_r4_result.bits
      result.transaction_identity.request_id.poke(3.U); result.transaction_identity.incarnation.poke(0.U)
      result.consumer_id.poke(expectedConsumer.U); result.normalized_value.poke((0x400 + expectedConsumer).U)
      d.io.c3_r4_result.valid.poke(true.B)
      waited = 0
      while (!d.io.c3_r4_result.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for C3 R4 result acceptance")
      d.clock.step(); d.io.c3_r4_result.valid.poke(false.B)
    }
  }

  private def retireC3PackedSession(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    val retire = d.io.c3b_runtime_retire.bits
    retire.session_id.poke(false.B)
    retire.transaction_identity.request_id.poke(3.U)
    retire.transaction_identity.incarnation.poke(0.U)
    d.io.c3b_runtime_retire.valid.poke(true.B)
    var waited = 0
    while (!d.io.c3b_runtime_retire.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, "timed out waiting for R6 runtime retirement acceptance")
    d.clock.step(); d.io.c3b_runtime_retire.valid.poke(false.B)
  }

  private def armC3bDirectDrain(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    d.io.c3b_direct_status.bits.acknowledgement_name.poke(p.r6.directPendingDrainedStatusCode.U)
    d.io.c3b_direct_status.bits.asserted.poke(true.B)
    d.io.c3b_direct_status.valid.poke(true.B)
  }

  private def admit(d: RouteARTL265a2PackReadPublicationHarness, manualSidecar: Boolean = true): Unit = {
    val a = d.io.r5_allocate.bits; a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(1.U); a.transaction_group_tag.poke(1.U)
    d.io.r5_allocate.valid.poke(true.B); d.io.r5_allocate.ready.expect(true.B); d.clock.step(); d.io.r5_allocate.valid.poke(false.B)
    val c = d.io.p3_claim.bits; c.layer.poke(0.U); c.kv_head.poke(0.U); c.owner.poke(0.U); c.page_ref.page_id.poke(0.U); c.page_ref.generation.poke(0.U); c.valid_records.poke(1.U); c.requires_tail_link.poke(false.B); c.transaction_group_tag.poke(1.U)
    d.io.p3_claim.valid.poke(true.B); d.io.p3_claim.ready.expect(true.B); d.clock.step(); d.io.p3_claim.valid.poke(false.B)
    val x = d.io.admission_context.bits; x.entry_id.poke(0.U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(0.U); x.payload_ref.poke(55.U); x.transaction_group_tag.poke(1.U); x.group_member_ordinal.poke(0.U); x.group_valid_records.poke(1.U)
    val h = d.io.admission_authority.bits; h.entry_id.poke(0.U); h.from_authority.poke(RouteAAuthorityStateCode.Hot.U); h.to_authority.poke(RouteAAuthorityStateCode.Pending.U); h.transaction_group_tag.poke(1.U)
    val b = d.io.pending_payload_binding.bits
    b.transaction_identity.request_id.poke(3.U); b.transaction_identity.incarnation.poke(0.U)
    b.entry_id.poke(0.U); b.layer.poke(0.U); b.kv_head.poke(0.U); b.logical_position.poke(0.U); b.payload_ref.poke(55.U)
    b.transaction_group_tag.poke(1.U); b.group_member_ordinal.poke(0.U); b.group_valid_records.poke(1.U)
    b.payload_handle_or_address.poke(55.U); b.source_generation.poke(1.U); b.destination_endpoint.poke(0.U)
    d.io.admission_context.valid.poke(true.B); d.io.admission_authority.valid.poke(true.B); d.io.pending_payload_binding.valid.poke(true.B)
    d.io.admission_context.ready.expect(true.B); d.io.pending_payload_binding.ready.expect(true.B); d.clock.step()
    d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B); d.io.pending_payload_binding.valid.poke(false.B)
    if (manualSidecar) {
      val s = d.io.p3_sidecar.bits; s.layer.poke(0.U); s.stage_generation.poke(1.U); s.record_ordinal.poke(0.U); s.payload_ref.poke(55.U); s.logical_position.poke(0.U)
      d.io.p3_sidecar.valid.poke(true.B); d.io.p3_sidecar.ready.expect(true.B); d.clock.step(); d.io.p3_sidecar.valid.poke(false.B)
    }
  }

  private def offerPackRead(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    val work = d.io.pack_read_work.bits
    work.layer.poke(0.U); work.stage_generation.poke(1.U); work.member_ordinal.poke(0.U); work.payload_ref.poke(55.U)
    work.transaction_identity.request_id.poke(3.U); work.transaction_identity.incarnation.poke(0.U)
    work.arrival_ordinal.poke(0.U); work.candidate_id.poke(0.U); work.eligibility_snapshot.poke(packReadEligibility.U)
    work.payload_handle_or_address.poke(55.U); work.destination_endpoint.poke(0.U); work.source_generation.poke(1.U)
    d.io.pack_read_work.valid.poke(true.B)
    waitRequest(d, p.coreMemoryReadRequestCode, 0)
    d.io.pack_read_work.valid.poke(false.B)
  }

  private def finishPayloadAndDescriptor(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    (0 until 8).foreach { index => response(d, 3, index, index == 7) }
    d.io.p3_state.expect(3.U)
    waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    (0 until 8).foreach { index => waitRequest(d, p.coreMemoryWriteDataCode, index) }
    response(d, 0, 0, last = true)
    d.io.p3_state.expect(5.U)
    waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    waitRequest(d, p.coreMemoryWriteDataCode, 0)
    response(d, 0, 0, last = true)
  }

  private def member(d: RouteARTL265a2PackReadPublicationHarness, memberId: Int): Unit = {
    var waited = 0
    while (!d.io.m2_member_request.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, "timed out waiting for M2 member request")
    d.io.m2_member_request.bits.member.expect(memberId.U)
    d.io.m2_member_request.ready.poke(true.B); d.clock.step(); d.io.m2_member_request.ready.poke(false.B)
    val rsp = d.io.m2_member_response.bits; rsp.layer.poke(0.U); rsp.stage_generation.poke(1.U); rsp.transaction_group_tag.poke(1.U); rsp.member.poke(memberId.U); rsp.status.poke(p.coreMemoryOkStatusCode.U)
    d.io.m2_member_response.valid.poke(true.B); d.io.m2_member_response.ready.expect(true.B); d.clock.step(); d.io.m2_member_response.valid.poke(false.B)
  }

  private def publish(d: RouteARTL265a2PackReadPublicationHarness): Unit = {
    member(d, RouteAM2GroupMember.HeadControlRmw); member(d, RouteAM2GroupMember.SpanOwnerRmw)
    var waited = 0
    while (!d.io.m2_publication_candidate.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, "timed out waiting for publication candidate")
    d.io.m2_publication_candidate.ready.poke(true.B); d.clock.step(); d.io.m2_publication_candidate.ready.poke(false.B)
    val req = d.io.m2_publication_request.bits; req.transaction_group_tag.poke(1.U); req.p3_layer.poke(0.U); req.p3_stage_generation.poke(1.U)
    d.io.m2_publication_request.valid.poke(true.B); d.io.m2_publication_request.ready.expect(true.B); d.clock.step(); d.io.m2_publication_request.valid.poke(false.B)
  }

  it("uses the actual R3 pack-read path before write durability and atomic publication") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d); admit(d); offerPackRead(d); finishPayloadAndDescriptor(d); publish(d)
      var waited = 0
      while (!d.io.publication_ack.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for publication acknowledgement")
      d.io.publication_ack.valid.expect(true.B)
      d.io.authority_transition.ready.poke(true.B); d.io.publication_commit.ready.poke(true.B); d.io.publication_member.ready.poke(true.B); d.io.publication_ack.ready.poke(true.B)
      d.clock.step()
      d.io.p3_state.expect(0.U)
    }
  }

  it("fails closed on a stale read response and on a read terminal fault before payload durability") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d); admit(d); offerPackRead(d)
      response(d, 2, 0, last = false)
      d.io.p3_state.expect(1.U)
      response(d, 3, 0, last = true, fault = true)
      d.io.p3_state.expect(6.U)
      d.io.m2_member_request.valid.expect(false.B)
      d.io.m2_publication_candidate.valid.expect(false.B)
    }
  }

  it("materializes an A0-bound record through payload durability before one matching R5 descriptor terminal enables M2") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      admit(d, manualSidecar = false)

      // The work and sidecar are now R3-owned feedback facts, not externally
      // supplied `P3PackReadWork` or sidecar fixtures.
      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach { index => response(d, 3, index, index == 7) }
      d.io.p3_state.expect(3.U)

      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach { index => waitRequest(d, p.coreMemoryWriteDataCode, index) }
      response(d, 0, 0, last = true)
      d.io.p3_state.expect(5.U)
      d.io.m2_member_request.valid.expect(false.B)

      // R5's real append candidate uses the same R2/R1/router path.  Payload
      // durability alone must not make its aggregate prerequisite visible.
      // The external-memory response interface only acknowledges transport;
      // exact append-delivery matching is owned by the existing typed R2/R5
      // boundary and is covered there, rather than by interpreting an
      // environment-port `ready` as an architectural identity verdict.
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      d.io.m2_member_request.valid.expect(false.B)

      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)
      var waited = 0
      while (!d.io.m2_member_request.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for descriptor-gated M2 member request")
      d.io.m2_member_request.bits.layer.expect(0.U)
      d.io.m2_member_request.bits.stage_generation.expect(1.U)
      d.io.m2_member_request.bits.transaction_group_tag.expect(1.U)
    }
  }

  it("closes automatic M2 publication, R5 visibility acknowledgement, and the R6 pending-to-packed handoff in one instance") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      initializeR6ForPublication(d)
      admit(d, manualSidecar = false)

      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach { index => response(d, 3, index, index == 7) }
      d.io.p3_state.expect(3.U)

      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach { index => waitRequest(d, p.coreMemoryWriteDataCode, index) }
      response(d, 0, 0, last = true)
      d.io.p3_state.expect(5.U)

      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)

      // The automatic reference provider owns only the existing M2 request/
      // response reflection.  Hold the post-commit observation to show that
      // it occurs after, rather than instead of, the nested R5 acknowledgement.
      var waited = 0
      var memberRequests = 0
      var memberResponses = 0
      var publicationCandidates = 0
      var sawM2PublicationRequest = false
      var sawR5VisibilityAck = false
      var sawPublishAck = false
      while (!d.io.publication_commit.valid.peek().litToBoolean && waited < 96) {
        if (d.io.m2_member_request_fire.peek().litToBoolean) { memberRequests += 1 }
        if (d.io.m2_member_response_fire.peek().litToBoolean) { memberResponses += 1 }
        if (d.io.m2_publication_candidate_fire.peek().litToBoolean) { publicationCandidates += 1 }
        sawM2PublicationRequest ||= d.io.m2_publication_request_fire.peek().litToBoolean
        sawR5VisibilityAck ||= d.io.r5_visibility_ack_fire.peek().litToBoolean
        sawPublishAck ||= d.io.m2_publish_ack_fire.peek().litToBoolean
        d.clock.step(); waited += 1
      }
      require(waited < 96,
        s"timed out waiting for automatic M2/R5 publication completion: members=$memberRequests/$memberResponses candidates=$publicationCandidates request=$sawM2PublicationRequest visibility=$sawR5VisibilityAck ack=$sawPublishAck ack-valid=${d.io.m2_publish_ack_valid.peek().litToBoolean} r6-ack-ready=${d.io.r6_publish_ack_ready.peek().litToBoolean}")
      sawM2PublicationRequest ||= d.io.m2_publication_request_fire.peek().litToBoolean
      sawR5VisibilityAck ||= d.io.r5_visibility_ack_fire.peek().litToBoolean
      sawPublishAck ||= d.io.m2_publish_ack_fire.peek().litToBoolean
      if (d.io.m2_member_request_fire.peek().litToBoolean) { memberRequests += 1 }
      if (d.io.m2_member_response_fire.peek().litToBoolean) { memberResponses += 1 }
      if (d.io.m2_publication_candidate_fire.peek().litToBoolean) { publicationCandidates += 1 }
      require(memberRequests == 2 && memberResponses == 2,
        s"expected exactly two required M2 member round trips, got requests=$memberRequests responses=$memberResponses")
      require(publicationCandidates == 1,
        s"expected exactly one R3 publication candidate, got $publicationCandidates")
      require(sawM2PublicationRequest, "automatic M2 provider never returned the exact publication request")
      require(sawR5VisibilityAck, "R5 visibility acknowledgement never completed the nested publication")
      require(sawPublishAck, "R3 did not accept the publication acknowledgement before post-commit observation")
      d.io.publication_commit.valid.expect(true.B)
      d.io.publication_commit.bits.p3_layer.expect(0.U)
      d.io.publication_commit.bits.p3_stage_generation.expect(1.U)
      d.io.publication_commit.bits.transaction_group_tag.expect(1.U)
      d.io.r6_authority_transition_fire.expect(false.B)
      d.clock.step()
      d.io.publication_commit.valid.expect(true.B)

      d.io.publication_member.ready.poke(true.B)
      d.io.publication_commit.ready.poke(true.B)
      d.clock.step()
      d.io.publication_commit.ready.poke(false.B)
      d.io.publication_member.ready.poke(false.B)

      waited = 0
      while (!d.io.r6_authority_transition_fire.peek().litToBoolean && waited < 32) { d.clock.step(); waited += 1 }
      require(waited < 32, "timed out waiting for R6 pending-to-packed authority acceptance")
      d.io.r6_authority_transition.entry_id.expect(0.U)
      d.io.r6_authority_transition.from_authority.expect(RouteAAuthorityStateCode.Pending.U)
      d.io.r6_authority_transition.to_authority.expect(RouteAAuthorityStateCode.Packed.U)
      d.io.r6_authority_transition.transaction_group_tag.expect(1.U)
      d.clock.step()
      d.io.p3_state.expect(0.U)
    }
  }

  it("activates exactly one post-R6 packed demand through R5 and S2 owners without entering C2 read transport") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      d.io.c1_demand_activation_mode.poke(true.B)
      d.io.publication_commit.ready.poke(true.B)
      initializeR6ForPublication(d)
      registerC1PackedAttention(d)
      sendC1PackedPlan(d)
      admit(d, manualSidecar = false)

      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach { index => response(d, 3, index, index == 7) }
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach { index => waitRequest(d, p.coreMemoryWriteDataCode, index) }
      response(d, 0, 0, last = true)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)

      var waited = 0
      var pageReadyFires = 0
      var demandFires = 0
      while (!d.io.c1_registry_allocate.valid.peek().litToBoolean && waited < 128) {
        if (d.io.c1_page_ready_fire.peek().litToBoolean) { pageReadyFires += 1 }
        if (d.io.c1_demand_fire.peek().litToBoolean) { demandFires += 1 }
        d.clock.step(); waited += 1
      }
      require(waited < 128, "timed out waiting for C1 association allocation after post-R6 readiness")
      if (d.io.c1_page_ready_fire.peek().litToBoolean) { pageReadyFires += 1 }
      if (d.io.c1_demand_fire.peek().litToBoolean) { demandFires += 1 }
      assert(pageReadyFires == 1, s"expected one C0 page-ready fire, got $pageReadyFires")
      assert(demandFires == 1, s"expected one C1 demand fire, got $demandFires")
      d.io.c1_association_active.expect(true.B)
      d.io.c1_registry_allocate.bits.candidate_class.expect(p.r2S2PackedClassCode.U)
      d.io.c1_registry_allocate.bits.transaction_identity.request_id.expect(3.U)
      d.io.c1_registry_allocate.bits.target_kind.expect(RouteADeliveryTargetKind.S2PackedFill.U)
      d.io.c1_registry_allocate.bits.target_descriptor.descriptor_page_ref.page_id.expect(0.U)
      d.io.c1_registry_allocate.bits.target_descriptor.s2_slot.expect(1.U)
      d.io.c1_registry_allocate.bits.target_descriptor.requires_sidecar.expect(true.B)
      // C1 stops before registry acknowledgement/R2/R1 read issue: holding
      // this boundary low proves no C2 transport work is manufactured here.
      d.io.c1_registry_allocate.ready.poke(false.B); d.clock.step()
      d.io.c1_registry_allocate.valid.expect(true.B)
    }
  }

  it("delivers the first post-R6 packed payload and sidecar through R2/R1 to S2 READY") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      d.io.c1_demand_activation_mode.poke(true.B)
      d.io.c2_read_activation_mode.poke(true.B)
      d.io.publication_commit.ready.poke(true.B)
      initializeR6ForPublication(d)
      registerC1PackedAttention(d)
      sendC1PackedPlan(d)
      admit(d, manualSidecar = false)

      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, 3, index, index == 7))
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
      response(d, 0, 0, last = true)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)

      // The newly published page must traverse the existing packed typed-read
      // path.  A stale response is consumed by R1 but cannot mutate S2.
      val (payloadRequestId, payloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, payloadRequestId + 1, 0, last = false, incarnation = payloadIncarnation)
      d.io.c2_s2_state.expect(1.U)
      (0 until 8).foreach(index => response(d, payloadRequestId, index, index == 7, incarnation = payloadIncarnation))

      // The existing sidecar adapter may issue only after the payload terminal
      // reaches the association owner.  Its distinct allocation then returns
      // one typed sidecar record and S2 alone transitions to READY.
      val (sidecarRequestId, sidecarIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, sidecarRequestId, 0, last = true, incarnation = sidecarIncarnation)
      d.clock.step(4)
      d.io.c2_s2_state.expect(2.U)

      // Destructive reset removes the owner-local READY state; it cannot
      // leave an old page usable when a later C2 association is attempted.
      d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B); d.clock.step()
      d.io.c2_s2_state.expect(0.U)

      // Rebuild the same first-use chain and fault the first matching payload
      // response.  The sidecar adapter must not issue and S2 must never reach
      // READY after a terminal fault.
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      d.io.c1_demand_activation_mode.poke(true.B)
      d.io.c2_read_activation_mode.poke(true.B)
      d.io.publication_commit.ready.poke(true.B)
      initializeR6ForPublication(d)
      registerC1PackedAttention(d)
      sendC1PackedPlan(d)
      admit(d, manualSidecar = false)
      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, 3, index, index == 7))
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
      response(d, 0, 0, last = true)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (faultDescriptorRequestId, faultDescriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, faultDescriptorRequestId, 0, last = true, incarnation = faultDescriptorIncarnation)
      val (faultPayloadRequestId, faultPayloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, faultPayloadRequestId, 0, last = true, fault = true, incarnation = faultPayloadIncarnation)
      d.clock.step(4)
      d.io.c2_s2_state.expect(3.U)
      d.io.external.request.valid.expect(false.B)
    }
  }

  it("continues the first post-R6 packed read through source service and four R4 completions to one terminal") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      d.io.c1_demand_activation_mode.poke(true.B)
      d.io.c2_read_activation_mode.poke(true.B)
      d.io.c3_terminal_activation_mode.poke(true.B)
      d.io.c3_merge_work.ready.poke(false.B)
      d.io.publication_commit.ready.poke(true.B)
      initializeR6ForPublication(d)
      registerC1PackedAttention(d)
      sendC1PackedPlan(d)
      admit(d, manualSidecar = false)

      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, 3, index, index == 7))
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
      response(d, 0, 0, last = true)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)
      val (payloadRequestId, payloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, payloadRequestId, index, index == 7, incarnation = payloadIncarnation))
      val (sidecarRequestId, sidecarIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, sidecarRequestId, 0, last = true, incarnation = sidecarIncarnation)
      d.clock.step(4); d.io.c2_s2_state.expect(2.U)

      // Only the existing packed S2 owner can now make the plan's packed
      // source available.  The named outer provider supplies four packets;
      // the named R4 environment returns one exact result per consumer.
      (0 until 4).foreach(c3PackedPacket(d, _))
      c3CompleteMerge(d)
      var waited = 0
      while (!d.io.c3_attention_terminal.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for C3 terminal")
      d.io.c3_attention_terminal.bits.transaction_identity.request_id.expect(3.U)
      d.io.c3_attention_terminal.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
      d.io.c3_attention_terminal.ready.poke(true.B); d.clock.step()
    }
  }

  it("retires the first post-R6 packed read only after final drain, durable R5 invalidation, and page reclaim") {
    simulate(new RouteARTL265a2PackReadPublicationHarness(p)) { d =>
      init(d)
      d.io.materialize_from_binding.poke(true.B)
      d.io.automatic_publication_owner_mode.poke(true.B)
      d.io.c1_demand_activation_mode.poke(true.B)
      d.io.c2_read_activation_mode.poke(true.B)
      d.io.c3_terminal_activation_mode.poke(true.B)
      d.io.c3_merge_work.ready.poke(false.B)
      d.io.publication_commit.ready.poke(true.B)
      initializeR6ForPublication(d)
      registerC1PackedAttention(d)
      sendC1PackedPlan(d)
      admit(d, manualSidecar = false)

      waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, 3, index, index == 7))
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
      response(d, 0, 0, last = true)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (descriptorRequestId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, descriptorRequestId, 0, last = true, incarnation = descriptorIncarnation)
      val (payloadRequestId, payloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, payloadRequestId, index, index == 7, incarnation = payloadIncarnation))
      val (sidecarRequestId, sidecarIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, sidecarRequestId, 0, last = true, incarnation = sidecarIncarnation)
      d.clock.step(4); d.io.c2_s2_state.expect(2.U)
      (0 until 4).foreach(c3PackedPacket(d, _))
      c3CompleteMerge(d)
      var waited = 0
      while (!d.io.c3_attention_terminal.valid.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
      require(waited < 64, "timed out waiting for the pre-retirement C3 terminal")
      d.io.c3_attention_terminal.bits.transaction_identity.request_id.expect(3.U)
      d.io.c3_attention_terminal.ready.poke(true.B); d.clock.step()

      // From here the composition uses the production collector, including
      // the final-pass suppression/replay of R1 and R2 descriptor drains.
      d.io.c3b_retire_reclaim_mode.poke(true.B)
      retireC3PackedSession(d)
      armC3bDirectDrain(d)

      // R6 cannot acknowledge retirement until it has first granted the
      // owner-local permit and R5's one descriptor invalidation reaches its
      // matching R1 terminal.  This is an outer functional-memory boundary.
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      // The request above is reachable only after R6 accepted all eight
      // pre-reclaim drain facts, including this held outer observation.
      d.io.c3b_direct_status.valid.poke(false.B)
      val (reclaimRequestId, reclaimIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      require(reclaimRequestId == 0, s"expected R5 reclaim sequence request id 0, got $reclaimRequestId")
      response(d, reclaimRequestId, 0, last = true, incarnation = reclaimIncarnation)

      waited = 0
      while (!d.io.c3b_retire_ack.valid.peek().litToBoolean && waited < 160) { d.clock.step(); waited += 1 }
      require(waited < 160, "timed out waiting for the final R6 retire acknowledgement")
      d.io.c3b_retire_ack.bits.session_id.expect(false.B)
      d.io.c3b_retire_ack.bits.transaction_identity.request_id.expect(3.U)
      d.io.c3b_retire_ack.ready.poke(true.B); d.clock.step()
      d.io.reclaim_complete.expect(true.B)
    }
  }
}
