package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAExclusiveP3PendingIngress, RouteAReadEndpointDemultiplexer, RouteAR2ReadIngressMerge, RouteAR3PackReadEndpoint, RouteAReadIssueCandidateAdapter, RouteATypedDeliveryRouter, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.incremental.RouteAM2P3Wrapper
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * One minimal C2 integration composition.  It exercises an explicit R3
  * member work item through the sole registry/R2/R1 path into P3.  It has no
  * top-level source schedule, hot/pack ingress merge, S2/direct activation,
  * publication, source packet, numeric, or physical-memory behavior.
  */
final class RouteAR3PackReadPathHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val p3_mem_init_done = Input(Bool())
    val p3_claim = Flipped(RouteAChannels.p3_claim(p))
    val admission_context = Flipped(RouteAChannels.admission_context(p))
    val admission_authority = Flipped(RouteAChannels.r6_authority_transition(p))
    val pending_payload_binding = Flipped(RouteAChannels.pending_payload_read_binding(p))
    val pack_read_work = Flipped(RouteAChannels.p3_pack_read_work(p))
    val p3_sidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val external = new CoreMemoryExternalPort(p)
    val p3_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
  })

  val r3 = Module(new RouteAM2P3Wrapper(p))
  val issueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val bridge = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  StructuralTieOff.source(bridge.io.packed_association_allocate_in)
  bridge.io.packed_association_arrival_ordinal_in := 0.U
  bridge.io.packed_association_candidate_id_in := 0.U
  StructuralTieOff.sink(bridge.io.packed_association_allocation_ack_out)
  val readIngress = Module(new RouteAR2ReadIngressMerge(p))
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpointDemux = Module(new RouteAReadEndpointDemultiplexer(p))
  val endpoint = Module(new RouteAR3PackReadEndpoint(p))
  val p3Ingress = Module(new RouteAExclusiveP3PendingIngress(p))

  r3.io.mem_init_done := io.p3_mem_init_done
  r3.io.drain_collection_enable := false.B
  r3.io.p3_claim_in <> io.p3_claim
  StructuralTieOff.sink(r3.io.p3_claim_ack)
  r3.io.admission_context_in <> io.admission_context
  r3.io.admission_authority_in <> io.admission_authority
  r3.io.pending_payload_binding_in <> io.pending_payload_binding
  r3.io.p3_pack_read_work_in <> io.pack_read_work
  issueAdapter.io.read_issue_in <> r3.io.p3_pack_read_issue_out
  bridge.io.r3_pack_read_in <> issueAdapter.io.candidate_out
  StructuralTieOff.source(bridge.io.r3_direct_pending_in)
  StructuralTieOff.source(bridge.io.r5_s2_packed_in)
  StructuralTieOff.source(bridge.io.r3_packed_write_in)
  StructuralTieOff.source(bridge.io.r5_append_in)
  StructuralTieOff.source(bridge.io.r5_reclaim_in)
  StructuralTieOff.sink(bridge.io.r3_direct_pending_out)
  StructuralTieOff.sink(bridge.io.r5_s2_packed_out)
  StructuralTieOff.sink(bridge.io.r3_packed_write_out)
  StructuralTieOff.sink(bridge.io.r5_append_out)
  StructuralTieOff.sink(bridge.io.r5_reclaim_out)
  readIngress.io.r3_pack_read_in <> bridge.io.r3_pack_read_out
  StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
  StructuralTieOff.source(readIngress.io.r5_s2_packed_in)
  r2.io.read_candidate_in <> readIngress.io.candidate_out
  StructuralTieOff.source(r2.io.candidate_in)
  r2.io.drain_collection_enable := false.B
  r2.io.reclaim_maintenance_enable := false.B
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  r1.io.external_core_mem_if_v1 <> io.external
  r1.io.r1_drain_permitted := false.B
  StructuralTieOff.sink(r1.io.component_status_out)
  StructuralTieOff.sink(r2.io.payload_drain_status_out)
  StructuralTieOff.sink(r2.io.descriptor_drain_status_out)

  registry.io.mem_init_done := r1.io.r1_init_complete
  registry.io.allocation_in <> bridge.io.registry_allocate_out
  bridge.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  registry.io.resolve_in <> r2.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  bridge.io.release_event_in := router.io.release_event_out
  endpointDemux.io.resolved_in <> router.io.read_fragment_out
  endpoint.io.resolved_fragment_in <> endpointDemux.io.p3_pack_read_out
  StructuralTieOff.sink(endpointDemux.io.direct_pending_out)
  StructuralTieOff.sink(endpointDemux.io.packed_s2_out)
  StructuralTieOff.sink(endpointDemux.io.packed_s2_sidecar_out)
  StructuralTieOff.sink(router.io.r3_packed_write_out)
  StructuralTieOff.sink(router.io.r5_append_out)
  StructuralTieOff.sink(router.io.r5_reclaim_out)

  StructuralTieOff.source(p3Ingress.io.hot_in)
  p3Ingress.io.pack_read_in <> endpoint.io.p3_pending_fragment_out
  r3.io.p3_pending_fragment_in <> p3Ingress.io.out
  r3.io.p3_sidecar_bind_in <> io.p3_sidecar
  StructuralTieOff.source(r3.io.p3_packed_write_issue_in)
  StructuralTieOff.source(r3.io.p3_packed_write_terminal_in)
  StructuralTieOff.sink(r3.io.p3_packed_write_candidate_out)
  StructuralTieOff.source(r3.io.p3_packed_write_delivery_in)
  StructuralTieOff.sink(r3.io.p3_payload_durable_out)
  StructuralTieOff.source(r3.io.descriptor_durability_prerequisite_in)
  StructuralTieOff.sink(r3.io.m2_group_member_req_out)
  StructuralTieOff.source(r3.io.m2_group_member_rsp_in)
  StructuralTieOff.sink(r3.io.m2_publish_candidate_out)
  StructuralTieOff.source(r3.io.m2_publish_req_in)
  StructuralTieOff.sink(r3.io.metadata_publish_visibility_apply)
  StructuralTieOff.source(r3.io.metadata_publish_visibility_ack_in)
  StructuralTieOff.sink(r3.io.m2_publish_ack)
  StructuralTieOff.sink(r3.io.authority_transition_out)
  StructuralTieOff.sink(r3.io.publication_commit_observation)
  StructuralTieOff.sink(r3.io.publication_member_observation)
  StructuralTieOff.sink(r3.io.post_r6_packed_page_ready_observation)
  StructuralTieOff.sink(r3.io.component_status_out)
  r3.io.p3_observe_layer := 0.U
  io.p3_state := r3.io.p3_observe_state
}

final class RouteAR3PackReadPathSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=64, coreMemoryFragmentCountWidth=4, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private val packReadEligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) |
    (1 << RouteAR2PredicateBits.Ownership) |
    (1 << RouteAR2PredicateBits.SourceCredit) |
    (1 << RouteAR2PredicateBits.DestinationReady) |
    (1 << RouteAR2PredicateBits.PendingAuthoritative) |
    (1 << RouteAR2PredicateBits.P3StageReadyOwned)

  private def init(d: RouteAR3PackReadPathHarness): Unit = {
    d.io.p3_mem_init_done.poke(false.B); d.io.p3_claim.valid.poke(false.B)
    d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B)
    d.io.pending_payload_binding.valid.poke(false.B)
    d.io.pack_read_work.valid.poke(false.B); d.io.p3_sidecar.valid.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B)
    d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.p3_mem_init_done.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
  }

  private def claimAndAdmit(d: RouteAR3PackReadPathHarness, payloadRef: Int = 55): Unit = {
    val claim = d.io.p3_claim.bits
    claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U)
    claim.page_ref.page_id.poke(1.U); claim.page_ref.generation.poke(1.U)
    claim.valid_records.poke(1.U); claim.requires_tail_link.poke(false.B); claim.transaction_group_tag.poke(1.U)
    d.io.p3_claim.valid.poke(true.B); d.io.p3_claim.ready.expect(true.B); d.clock.step(); d.io.p3_claim.valid.poke(false.B)
    val admission = d.io.admission_context.bits
    admission.entry_id.poke(0.U); admission.layer.poke(0.U); admission.kv_head.poke(0.U); admission.logical_position.poke(0.U)
    admission.payload_ref.poke(payloadRef.U); admission.transaction_group_tag.poke(1.U); admission.group_member_ordinal.poke(0.U); admission.group_valid_records.poke(1.U)
    val authority = d.io.admission_authority.bits
    authority.entry_id.poke(0.U); authority.from_authority.poke(RouteAAuthorityStateCode.Hot.U); authority.to_authority.poke(RouteAAuthorityStateCode.Pending.U); authority.transaction_group_tag.poke(1.U)
    val binding = d.io.pending_payload_binding.bits
    binding.transaction_identity.request_id.poke(3.U); binding.transaction_identity.incarnation.poke(1.U)
    binding.entry_id.poke(0.U); binding.layer.poke(0.U); binding.kv_head.poke(0.U); binding.logical_position.poke(0.U)
    binding.payload_ref.poke(payloadRef.U); binding.transaction_group_tag.poke(1.U); binding.group_member_ordinal.poke(0.U); binding.group_valid_records.poke(1.U)
    binding.payload_handle_or_address.poke(payloadRef.U); binding.source_generation.poke(1.U); binding.destination_endpoint.poke(0.U)
    d.io.admission_context.valid.poke(true.B); d.io.admission_authority.valid.poke(true.B); d.io.pending_payload_binding.valid.poke(true.B)
    d.io.admission_context.ready.expect(true.B); d.io.admission_authority.ready.expect(true.B); d.io.pending_payload_binding.ready.expect(true.B); d.clock.step()
    d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B); d.io.pending_payload_binding.valid.poke(false.B)
  }

  private def bindSidecar(d: RouteAR3PackReadPathHarness, payloadRef: Int = 55): Unit = {
    val sidecar = d.io.p3_sidecar.bits
    sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U)
    sidecar.payload_ref.poke(payloadRef.U); sidecar.logical_position.poke(0.U)
    d.io.p3_sidecar.valid.poke(true.B); d.io.p3_sidecar.ready.expect(true.B); d.clock.step(); d.io.p3_sidecar.valid.poke(false.B)
  }

  private def offerWork(d: RouteAR3PackReadPathHarness, payloadRef: Int = 55, generation: Int = 1): Unit = {
    val work = d.io.pack_read_work.bits
    work.layer.poke(0.U); work.stage_generation.poke(1.U); work.member_ordinal.poke(0.U); work.payload_ref.poke(payloadRef.U)
    work.transaction_identity.request_id.poke(3.U); work.transaction_identity.incarnation.poke(1.U)
    work.arrival_ordinal.poke(0.U); work.candidate_id.poke(0.U); work.eligibility_snapshot.poke(packReadEligibility.U)
    work.payload_handle_or_address.poke(payloadRef.U); work.destination_endpoint.poke(0.U); work.source_generation.poke(generation.U)
    d.io.pack_read_work.valid.poke(true.B)
  }

  private def acceptRead(d: RouteAR3PackReadPathHarness): Unit = {
    var waited = 0
    while (d.io.external.request.valid.peek().litValue == 0 && waited < 24) { d.clock.step(); waited += 1 }
    d.io.external.request.valid.expect(true.B); d.io.external.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U)
    d.io.external.request.bits.expected_fragment_count.expect(8.U); d.io.external.request.bits.address_ref.expect(55.U)
    d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
    d.io.pack_read_work.valid.poke(false.B)
  }

  private def respond(d: RouteAR3PackReadPathHarness, index: Int, last: Boolean, status: Int = 0, requestId: Int = 3, incarnation: Int = 1): Unit = {
    val response = d.io.external.response.bits
    response.transaction_identity.request_id.poke(requestId.U); response.transaction_identity.incarnation.poke(incarnation.U)
    response.fragment_index.poke(index.U); response.last.poke(last.B); response.status.poke(status.U); response.data.poke((0x100 + index).U)
    d.io.external.response.valid.poke(true.B)
    var waited = 0
    while (d.io.external.response.ready.peek().litValue == 0 && waited < 24) { d.clock.step(); waited += 1 }
    d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
    // R1/R2 acceptance is followed by registry/router endpoint delivery.
    // Allow that architectural handoff to retire before offering the next
    // external response or observing the P3 state.
    d.clock.step(2)
  }

  it("maps one immutable retained member to one eight-fragment pack read and completes P3 only after sidecar") {
    simulate(new RouteAR3PackReadPathHarness(p)) { d =>
      init(d); claimAndAdmit(d); bindSidecar(d); offerWork(d); acceptRead(d)
      (0 until 8).foreach { index => respond(d, index, index == 7) }
      d.io.p3_state.expect(3.U)
    }
  }

  it("drops stale identity and refuses mismatched member work without P3 deposit") {
    simulate(new RouteAR3PackReadPathHarness(p)) { d =>
      init(d); claimAndAdmit(d); bindSidecar(d); offerWork(d, payloadRef = 54)
      d.clock.step(3); d.io.pack_read_work.ready.expect(false.B); d.io.external.request.valid.expect(false.B); d.io.p3_state.expect(1.U)
      // A correct member reference is still insufficient when the work tries
      // to replace the pending owner's generation/identity binding.
      d.io.pack_read_work.valid.poke(false.B); offerWork(d, generation = 0)
      d.clock.step(3); d.io.pack_read_work.ready.expect(false.B); d.io.external.request.valid.expect(false.B); d.io.p3_state.expect(1.U)
      d.io.pack_read_work.valid.poke(false.B); offerWork(d); acceptRead(d)
      respond(d, index = 0, last = false, requestId = 2, incarnation = 0)
      d.io.p3_state.expect(1.U)
      (0 until 8).foreach { index => respond(d, index, index == 7) }
      d.io.p3_state.expect(3.U)
    }
  }

  it("turns an R1 terminal fault into P3 fault control without payload deposit") {
    simulate(new RouteAR3PackReadPathHarness(p)) { d =>
      init(d); claimAndAdmit(d); bindSidecar(d); offerWork(d); acceptRead(d)
      respond(d, index = 0, last = true, status = p.coreMemoryFaultStatusCode)
      d.io.p3_state.expect(6.U)
    }
  }

  it("fails closed on a malformed fragment sequence without completing P3") {
    simulate(new RouteAR3PackReadPathHarness(p)) { d =>
      init(d); claimAndAdmit(d); bindSidecar(d); offerWork(d); acceptRead(d)
      // R1 normalizes this matching but out-of-order response to a terminal
      // fault; endpoint forwards no payload data and P3 cannot COMPLETE.
      respond(d, index = 1, last = false)
      d.io.p3_state.expect(6.U)
    }
  }
}
