package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAExclusiveP3PendingIngress, RouteAReadEndpointDemultiplexer, RouteAReadIssueCandidateAdapter, RouteAR2ReadIngressMerge, RouteAR2WriteIngressMerge, RouteAR3PackReadEndpoint, RouteATypedDeliveryRouter, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAM2P3Wrapper, RouteAM2ReferenceProtocolProvider, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
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
  val m2Reference = Module(new RouteAM2ReferenceProtocolProvider(p))
  val lifecycle = Module(new RouteALifecycleAdapter(p))
  StructuralTieOff.source(r5.io.descriptor_location_request_in)
  StructuralTieOff.sink(r5.io.descriptor_location_grant_out)
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val issueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val bridge = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  StructuralTieOff.source(bridge.io.packed_association_allocate_in)
  bridge.io.packed_association_arrival_ordinal_in := 0.U
  bridge.io.packed_association_candidate_id_in := 0.U
  StructuralTieOff.sink(bridge.io.packed_association_allocation_ack_out)
  val readIngress = Module(new RouteAR2ReadIngressMerge(p))
  val writeIngress = Module(new RouteAR2WriteIngressMerge(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpointDemux = Module(new RouteAReadEndpointDemultiplexer(p))
  val endpoint = Module(new RouteAR3PackReadEndpoint(p))
  val p3Ingress = Module(new RouteAExclusiveP3PendingIngress(p))

  r3.io.mem_init_done := io.mem_init_done
  r3.io.drain_collection_enable := io.drain_collection_enable
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
  r5.io.drain_collection_enable := io.drain_collection_enable
  r5.io.allocator_release_out.ready := true.B
  r5.io.page_allocation_req_in <> io.r5_allocate
  io.r5_allocation_rsp <> r5.io.page_allocation_rsp
  r5.io.reclaim_permit_in <> io.reclaim_permit
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
  io.r5_status <> r5.io.component_status_out

  readIngress.io.r3_pack_read_in <> bridge.io.r3_pack_read_out
  StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
  StructuralTieOff.source(readIngress.io.r5_s2_packed_in)
  r2.io.read_candidate_in <> readIngress.io.candidate_out
  writeIngress.io.r3_packed_write_in <> bridge.io.r3_packed_write_out
  writeIngress.io.r5_append_in <> bridge.io.r5_append_out
  writeIngress.io.r5_reclaim_in <> bridge.io.r5_reclaim_out
  r2.io.candidate_in <> writeIngress.io.candidate_out
  r2.io.drain_collection_enable := io.drain_collection_enable
  r2.io.reclaim_maintenance_enable := io.reclaim_maintenance_enable
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  r1.io.external_core_mem_if_v1 <> io.external
  r1.io.r1_drain_permitted := io.r1_drain_permitted
  io.r1_status <> r1.io.component_status_out
  io.r2_payload_status <> r2.io.payload_drain_status_out
  io.r2_descriptor_status <> r2.io.descriptor_drain_status_out

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
  StructuralTieOff.sink(endpointDemux.io.packed_s2_out)
  StructuralTieOff.sink(endpointDemux.io.packed_s2_sidecar_out)

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
  lifecycle.io.component_status_in <> io.r6_component_status_in
  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.attention_terminal_rsp)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  lifecycle.io.r5_reclaim_complete_in := false.B
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.source(lifecycle.io.source_completion_plan_in)
  lifecycle.io.source_completion_plan_copy_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  StructuralTieOff.source(lifecycle.io.packed_source_release_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.merge_req)
  StructuralTieOff.source(lifecycle.io.merge_terminal_in)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  lifecycle.io.reclaim_permit_out.ready := true.B

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
  io.publication_member <> r3.io.publication_member_observation
  StructuralTieOff.sink(r3.io.post_r6_packed_page_ready_observation)
  io.r3_status <> r3.io.component_status_out
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
}
