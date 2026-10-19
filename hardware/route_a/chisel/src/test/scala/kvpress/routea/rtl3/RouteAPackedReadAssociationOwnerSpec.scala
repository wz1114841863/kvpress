package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAPackedS2ReadEndpoint, RouteAPackedS2ReadProducer, RouteAReadEndpointDemultiplexer, RouteAReadIssueCandidateAdapter, RouteAR2ReadIngressMerge, RouteAS2GqaSourceWrapper, RouteATypedDeliveryRouter}
import kvpress.routea.incremental.RouteAPackedReadAssociationOwner
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Test-only RTL3.2 composition.  Its only testbench ingress after init is
  * the four named grants, S2 service lease request, and explicit sidecar
  * transport; packed payload responses originate in the RTL3.1 environment
  * through the real R1 external port.
  */
final class RouteARTL32PackedReadFunctionalHarness(
    p: RouteASkeletonParameters,
    useRtl36cSidecarFixture: Boolean = false,
    sidecarFixture: RouteARTL36cSidecarFixture = RouteARTL36cSidecarFixture.Default,
) extends Module {
  val io = IO(new Bundle {
    val demand = Flipped(RouteAChannels.packed_source_demand(p))
    val publication = Flipped(RouteAChannels.publication_read_authorization(p))
    val descriptor = Flipped(RouteAChannels.descriptor_location_grant(p))
    val lease = Flipped(RouteAChannels.s2_fill_lease(p))
    val service = Flipped(RouteAChannels.s2_service_req)
    val sidecar_fragment = Flipped(RouteAChannels.s2_sidecar_fragment(p))
    val sidecar_complete = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val external = new CoreMemoryExternalPort(p)
    val s2_state = Output(UInt(3.W))
    val payload_read_req = Flipped(RouteAChannels.s2_payload_read_req(p))
    val payload_read_rsp = RouteAChannels.s2_payload_read_rsp(p)
    val sidecar_read_req = Flipped(RouteAChannels.s2_sidecar_read_req(p))
    val sidecar_read_rsp = RouteAChannels.s2_sidecar_read_rsp(p)
    val sidecar_fixture_complete = Output(Bool())
    val sidecar_fixture_faulted = Output(Bool())
  })

  val owner = Module(new RouteAPackedReadAssociationOwner(p))
  val producer = Module(new RouteAPackedS2ReadProducer(p))
  val issueAdapter = Module(new RouteAReadIssueCandidateAdapter(p))
  val readIngress = Module(new RouteAR2ReadIngressMerge(p))
  val r2 = Module(new RouteACoreSideArbiter(p))
  StructuralTieOff.sink(r2.io.direct_lease_eligibility_query_out)
  StructuralTieOff.source(r2.io.direct_lease_eligibility_in)
  StructuralTieOff.sink(r2.io.direct_lease_commit_out)
  val r1 = Module(new RouteACoreMemIfV1(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpointDemux = Module(new RouteAReadEndpointDemultiplexer(p))
  val endpoint = Module(new RouteAPackedS2ReadEndpoint(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  StructuralTieOff.source(s2.io.s2_fill_lease_request_in)
  StructuralTieOff.sink(s2.io.s2_fill_lease_out)
  val sidecarTap = if (useRtl36cSidecarFixture) Some(Module(new RouteARTL36cAllocationSidecarTap(p))) else None
  val sidecarFixtureTransport = if (useRtl36cSidecarFixture) Some(Module(new RouteARTL36cSidecarFixtureTransport(p, sidecarFixture))) else None

  owner.io.mem_init_done := r1.io.r1_init_complete
  owner.io.demand_in <> io.demand
  owner.io.publication_authorization_in <> io.publication
  owner.io.descriptor_grant_in <> io.descriptor
  owner.io.s2_fill_lease_in <> io.lease
  owner.io.invalidation_in.valid := false.B
  owner.io.invalidation_in.bits := 0.U.asTypeOf(new PackedReadInvalidation)
  if (useRtl36cSidecarFixture) {
    owner.io.registry_allocate_out <> sidecarTap.get.io.allocation_in
    sidecarTap.get.io.registry_allocation_out <> registry.io.allocation_in
  } else {
    owner.io.registry_allocate_out <> registry.io.allocation_in
  }
  owner.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  owner.io.packed_s2_work_out <> producer.io.work_in
  // RTL3.8.2 moves I4 to its own production-sidecar adapter.  This historical
  // payload-only harness deliberately observes no sidecar transport.
  StructuralTieOff.sink(owner.io.sidecar_read_work_out)
  StructuralTieOff.source(owner.io.terminal_in)
  StructuralTieOff.sink(owner.io.release_observation_out)

  producer.io.s2_fill_open_out <> s2.io.s2_fill_open_in
  producer.io.read_issue_out <> issueAdapter.io.read_issue_in
  readIngress.io.r5_s2_packed_in <> issueAdapter.io.candidate_out
  StructuralTieOff.source(readIngress.io.r3_pack_read_in)
  StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
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
  registry.io.resolve_in <> r2.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  endpointDemux.io.resolved_in <> router.io.read_fragment_out
  endpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_out
  StructuralTieOff.sink(endpointDemux.io.p3_pack_read_out)
  StructuralTieOff.sink(endpointDemux.io.direct_pending_out)
  StructuralTieOff.sink(endpointDemux.io.packed_s2_sidecar_out)
  StructuralTieOff.sink(router.io.r3_packed_write_out)
  StructuralTieOff.sink(router.io.r5_append_out)
  StructuralTieOff.sink(router.io.r5_reclaim_out)

  s2.io.mem_init_done := r1.io.r1_init_complete
  s2.io.drain_collection_enable := false.B
  s2.io.service_req_in <> io.service
  endpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
  endpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
  endpoint.io.endpoint_slot_in := 0.U
  endpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
  endpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
  endpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
  s2.io.s2_payload_fragment_in <> endpoint.io.s2_payload_fragment_out
  s2.io.s2_fill_terminal_in <> endpoint.io.s2_fill_terminal_out
  if (useRtl36cSidecarFixture) {
    val transport = sidecarFixtureTransport.get
    sidecarTap.get.io.sidecar_obligation_out <> transport.io.obligation_in
    transport.io.observed_filling := s2.io.s2_observe_filling
    transport.io.observed_fill_open := s2.io.s2_observe_fill_open
    transport.io.observed_identity := s2.io.s2_observe_identity
    transport.io.observed_page_ref := s2.io.s2_observe_page_ref
    transport.io.observed_generation := s2.io.s2_observe_generation
    s2.io.s2_sidecar_fragment_in <> transport.io.sidecar_fragment_out
    s2.io.s2_sidecar_complete_in <> transport.io.sidecar_complete_out
    io.sidecar_fragment.ready := false.B
    io.sidecar_complete.ready := false.B
    io.sidecar_fixture_complete := transport.io.complete
    io.sidecar_fixture_faulted := transport.io.faulted
  } else {
    s2.io.s2_sidecar_fragment_in <> io.sidecar_fragment
    s2.io.s2_sidecar_complete_in <> io.sidecar_complete
    io.sidecar_fixture_complete := false.B
    io.sidecar_fixture_faulted := false.B
  }
  s2.io.s2_payload_read_req_in <> io.payload_read_req
  io.payload_read_rsp <> s2.io.s2_payload_read_rsp_out
  s2.io.s2_sidecar_read_req_in <> io.sidecar_read_req
  io.sidecar_read_rsp <> s2.io.s2_sidecar_read_rsp_out
  StructuralTieOff.source(s2.io.gqa_consumer_commit_in)
  StructuralTieOff.sink(s2.io.s2_release_out)
  s2.io.s2_observe_slot := 0.U
  s2.io.component_status_out.ready := true.B
  io.s2_state := s2.io.s2_observe_state
}

/** RTL3.2 directed proof of the concrete four-grant association owner. */
final class RouteAPackedReadAssociationOwnerSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4,
    candidatePredicateWidth = 10, r2S2FullClassCode = 0, r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2, r2PackReadClassCode = 3, r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5, r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 64, coreMemoryFragmentCountWidth = 10,
    coreMemoryFragmentIndexWidth = 9, coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2,
    p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor)

  private def init(d: RouteAPackedReadAssociationOwner): Unit = {
    d.io.mem_init_done.poke(false.B)
    d.io.demand_in.valid.poke(false.B)
    d.io.publication_authorization_in.valid.poke(false.B)
    d.io.descriptor_grant_in.valid.poke(false.B)
    d.io.s2_fill_lease_in.valid.poke(false.B)
    d.io.invalidation_in.valid.poke(false.B)
    d.io.registry_allocate_out.ready.poke(false.B)
    d.io.registry_allocation_ack_in.valid.poke(false.B)
    d.io.packed_s2_work_out.ready.poke(false.B)
    d.io.sidecar_read_work_out.ready.poke(true.B)
    d.io.terminal_in.valid.poke(false.B)
    d.io.release_observation_out.ready.poke(false.B)
    d.clock.step()
    d.io.mem_init_done.poke(true.B)
    d.clock.step()
  }

  private def identity(identity: TransactionIdentity, rid: Int = 3): Unit = {
    identity.request_id.poke(rid.U); identity.incarnation.poke(1.U)
  }
  private def page(page: PageRef, id: Int = 7): Unit = {
    page.page_id.poke(id.U); page.generation.poke(1.U)
  }

  private def demand(d: RouteAPackedReadAssociationOwner, pageId: Int = 7): Unit = {
    identity(d.io.demand_in.bits.transaction_identity); page(d.io.demand_in.bits.page_ref, pageId)
    d.io.demand_in.bits.arrival_ordinal.poke(2.U); d.io.demand_in.bits.candidate_id.poke(1.U)
    d.io.demand_in.bits.eligibility_snapshot.poke(0x3f.U); d.io.demand_in.bits.destination_endpoint.poke(0.U)
    d.io.demand_in.valid.poke(true.B); d.io.demand_in.ready.expect(true.B); d.clock.step(); d.io.demand_in.valid.poke(false.B)
  }
  private def publication(d: RouteAPackedReadAssociationOwner, pageId: Int = 7): Unit = {
    identity(d.io.publication_authorization_in.bits.transaction_identity); page(d.io.publication_authorization_in.bits.page_ref, pageId)
    d.io.publication_authorization_in.bits.transaction_group_tag.poke(1.U)
    d.io.publication_authorization_in.bits.valid_records.poke(2.U)
    d.io.publication_authorization_in.bits.packed_authoritative.poke(true.B)
    d.io.publication_authorization_in.valid.poke(true.B); d.io.publication_authorization_in.ready.expect(true.B); d.clock.step(); d.io.publication_authorization_in.valid.poke(false.B)
  }
  private def descriptor(d: RouteAPackedReadAssociationOwner, pageId: Int = 7): Unit = {
    identity(d.io.descriptor_grant_in.bits.transaction_identity); page(d.io.descriptor_grant_in.bits.page_ref, pageId)
    d.io.descriptor_grant_in.bits.payload_handle_or_address.poke(0x99.U)
    d.io.descriptor_grant_in.bits.sidecar_handle_or_address.poke(0xaa.U)
    d.io.descriptor_grant_in.bits.valid_records.poke(2.U); d.io.descriptor_grant_in.bits.sidecar_records.poke(2.U)
    d.io.descriptor_grant_in.bits.live_reference_held.poke(true.B)
    d.io.descriptor_grant_in.valid.poke(true.B); d.io.descriptor_grant_in.ready.expect(true.B); d.clock.step(); d.io.descriptor_grant_in.valid.poke(false.B)
  }
  private def lease(d: RouteAPackedReadAssociationOwner, pageId: Int = 7): Unit = {
    identity(d.io.s2_fill_lease_in.bits.transaction_identity); page(d.io.s2_fill_lease_in.bits.page_ref, pageId)
    d.io.s2_fill_lease_in.bits.s2_slot.poke(0.U); d.io.s2_fill_lease_in.bits.source_generation.poke(1.U)
    d.io.s2_fill_lease_in.bits.requires_sidecar.poke(true.B)
    d.io.s2_fill_lease_in.valid.poke(true.B); d.io.s2_fill_lease_in.ready.expect(true.B); d.clock.step(); d.io.s2_fill_lease_in.valid.poke(false.B)
  }

  private def exactAck(d: RouteAPackedReadAssociationOwner, context: Int = 1): Unit = {
    val ack = d.io.registry_allocation_ack_in.bits
    ack.delivery_context_ref.poke(context.U)
    ack.allocation.candidate_class.poke(p.r2S2PackedClassCode.U)
    identity(ack.allocation.transaction_identity)
    ack.allocation.target_kind.poke(RouteADeliveryTargetKind.S2PackedFill.U)
    ack.allocation.target_identity_generation.poke(1.U)
    ack.allocation.expected_fragment_count.poke(16.U)
    ack.allocation.target_descriptor.write_endpoint.poke(0.U)
    ack.allocation.target_descriptor.p3_layer.poke(0.U)
    ack.allocation.target_descriptor.p3_stage_generation.poke(0.U)
    ack.allocation.target_descriptor.transaction_group_tag.poke(1.U)
    ack.allocation.target_descriptor.descriptor_kind.poke(0.U)
    page(ack.allocation.target_descriptor.descriptor_page_ref)
    ack.allocation.target_descriptor.descriptor_line.poke(0xaa.U)
    ack.allocation.target_descriptor.s2_slot.poke(0.U)
    ack.allocation.target_descriptor.source_generation.poke(1.U)
    ack.allocation.target_descriptor.requires_sidecar.poke(true.B)
    ack.allocation.target_descriptor.pending_ordinal.poke(0.U)
    ack.allocation.target_descriptor.p3_member_payload_ref.poke(0.U)
    ack.allocation.target_descriptor.direct_source_last.poke(false.B)
    ack.allocation.target_descriptor.pending_explicit_empty.poke(false.B)
    d.io.registry_allocation_ack_in.valid.poke(true.B)
    d.io.registry_allocation_ack_in.ready.expect(true.B)
    d.clock.step()
    d.io.registry_allocation_ack_in.valid.poke(false.B)
  }

  it("joins arbitrary-order live grants, preserves a stalled allocation, and emits work only after exact ack") {
    simulate(new RouteAPackedReadAssociationOwner(p)) { d =>
      init(d)
      lease(d); descriptor(d); demand(d); publication(d)
      d.clock.step(2)
      d.io.registry_allocate_out.valid.expect(true.B)
      d.io.registry_allocate_out.bits.expected_fragment_count.expect(16.U)
      d.io.registry_allocate_out.bits.target_descriptor.descriptor_page_ref.page_id.expect(7.U)
      d.clock.step()
      d.io.registry_allocate_out.valid.expect(true.B)
      d.io.registry_allocate_out.bits.expected_fragment_count.expect(16.U)
      d.io.registry_allocate_out.ready.poke(true.B); d.clock.step(); d.io.registry_allocate_out.ready.poke(false.B)
      d.io.packed_s2_work_out.valid.expect(false.B)
      exactAck(d)
      d.io.packed_s2_work_out.valid.expect(true.B)
      d.io.packed_s2_work_out.bits.delivery_context_ref.expect(1.U)
      d.io.packed_s2_work_out.bits.payload_handle_or_address.expect(0x99.U)
      d.io.packed_s2_work_out.bits.valid_records.expect(2.U)
      d.io.packed_s2_work_out.ready.poke(true.B); d.clock.step(); d.io.packed_s2_work_out.ready.poke(false.B)
      identity(d.io.terminal_in.bits.transaction_identity); page(d.io.terminal_in.bits.page_ref)
      d.io.terminal_in.bits.s2_slot.poke(0.U); d.io.terminal_in.bits.source_generation.poke(1.U)
      d.io.terminal_in.bits.delivery_context_ref.poke(1.U); d.io.terminal_in.bits.status.poke(p.coreMemoryOkStatusCode.U)
      d.io.terminal_in.valid.poke(true.B); d.io.terminal_in.ready.expect(true.B); d.clock.step(); d.io.terminal_in.valid.poke(false.B)
      d.io.release_observation_out.valid.expect(true.B)
      d.io.release_observation_out.bits.delivery_context_ref.expect(1.U)
      d.io.release_observation_out.ready.poke(true.B); d.clock.step(); d.io.release_observation_out.ready.poke(false.B)
      d.io.association_active.expect(false.B)
    }
  }

  it("fails closed on a cross-owner page mismatch without allocation or work") {
    simulate(new RouteAPackedReadAssociationOwner(p)) { d =>
      init(d)
      demand(d, pageId = 7); publication(d, pageId = 8); descriptor(d); lease(d)
      d.clock.step(3)
      d.io.registry_allocate_out.valid.expect(false.B)
      d.io.packed_s2_work_out.valid.expect(false.B)
      d.io.release_observation_out.valid.expect(false.B)
    }
  }

  it("delivers functional-memory payload through the real owner and R2/R1 path before explicit sidecar completion") {
    simulate(new RouteARTL32PackedReadFunctionalHarness(p)) { d =>
      val memory = new RouteAFunctionalMemoryEnvironment(p)
      memory.preload(0x99, Some(1), (0 until 16).map(i => BigInt(0x400 + i)).toVector,
        Vector(BigInt(0x900), BigInt(0x901)))

      d.io.demand.valid.poke(false.B); d.io.publication.valid.poke(false.B)
      d.io.descriptor.valid.poke(false.B); d.io.lease.valid.poke(false.B)
      d.io.service.valid.poke(false.B); d.io.sidecar_fragment.valid.poke(false.B); d.io.sidecar_complete.valid.poke(false.B)
      d.io.payload_read_req.valid.poke(false.B); d.io.payload_read_rsp.ready.poke(false.B)
      d.io.sidecar_read_req.valid.poke(false.B); d.io.sidecar_read_rsp.ready.poke(false.B)
      var requestCount = 0
      var responseCount = 0
      def tick(): Unit = {
        memory.drive(d.io.external)
        if (d.io.external.request.valid.peek().litToBoolean && d.io.external.request.ready.peek().litToBoolean) { requestCount += 1 }
        if (d.io.external.response.valid.peek().litToBoolean && d.io.external.response.ready.peek().litToBoolean) { responseCount += 1 }
        memory.observeAccepted(d.io.external)
        d.clock.step()
      }
      tick(); tick(); tick()

      identity(d.io.service.bits.transaction_identity); page(d.io.service.bits.page_ref)
      d.io.service.bits.s2_slot.poke(0.U)
      d.io.service.valid.poke(true.B); d.io.service.ready.expect(true.B); tick(); d.io.service.valid.poke(false.B)

      identity(d.io.demand.bits.transaction_identity); page(d.io.demand.bits.page_ref)
      d.io.demand.bits.arrival_ordinal.poke(2.U); d.io.demand.bits.candidate_id.poke(1.U)
      d.io.demand.bits.eligibility_snapshot.poke(0x3f.U); d.io.demand.bits.destination_endpoint.poke(0.U)
      d.io.demand.valid.poke(true.B); d.io.demand.ready.expect(true.B); tick(); d.io.demand.valid.poke(false.B)
      identity(d.io.publication.bits.transaction_identity); page(d.io.publication.bits.page_ref)
      d.io.publication.bits.transaction_group_tag.poke(1.U); d.io.publication.bits.valid_records.poke(2.U); d.io.publication.bits.packed_authoritative.poke(true.B)
      d.io.publication.valid.poke(true.B); d.io.publication.ready.expect(true.B); tick(); d.io.publication.valid.poke(false.B)
      identity(d.io.descriptor.bits.transaction_identity); page(d.io.descriptor.bits.page_ref)
      d.io.descriptor.bits.payload_handle_or_address.poke(0x99.U); d.io.descriptor.bits.sidecar_handle_or_address.poke(0xaa.U)
      d.io.descriptor.bits.valid_records.poke(2.U); d.io.descriptor.bits.sidecar_records.poke(2.U); d.io.descriptor.bits.live_reference_held.poke(true.B)
      d.io.descriptor.valid.poke(true.B); d.io.descriptor.ready.expect(true.B); tick(); d.io.descriptor.valid.poke(false.B)
      identity(d.io.lease.bits.transaction_identity); page(d.io.lease.bits.page_ref)
      d.io.lease.bits.s2_slot.poke(0.U); d.io.lease.bits.source_generation.poke(1.U); d.io.lease.bits.requires_sidecar.poke(true.B)
      d.io.lease.valid.poke(true.B); d.io.lease.ready.expect(true.B); tick(); d.io.lease.valid.poke(false.B)

      // One request plus sixteen deterministic R1 responses; no timing or
      // bandwidth claim is made by this bounded functional environment.
      (0 until 100).foreach(_ => tick())
      assert(requestCount == 1, s"expected one R1 request, observed $requestCount")
      assert(responseCount == 16, s"expected sixteen R1 responses, observed $responseCount")
      d.io.s2_state.expect(1.U) // filling: payload alone cannot become READY
      (0 until 2).foreach { record =>
        identity(d.io.sidecar_fragment.bits.transaction_identity)
        d.io.sidecar_fragment.bits.s2_slot.poke(0.U); d.io.sidecar_fragment.bits.source_generation.poke(1.U)
        d.io.sidecar_fragment.bits.record_ordinal.poke(record.U); d.io.sidecar_fragment.bits.data.poke((0x900 + record).U)
        d.io.sidecar_fragment.valid.poke(true.B); d.io.sidecar_fragment.ready.expect(true.B); tick(); d.io.sidecar_fragment.valid.poke(false.B)
      }
      identity(d.io.sidecar_complete.bits.transaction_identity)
      d.io.sidecar_complete.bits.s2_slot.poke(0.U); d.io.sidecar_complete.bits.source_generation.poke(1.U)
      d.io.sidecar_complete.valid.poke(true.B); d.io.sidecar_complete.ready.expect(true.B); tick(); d.io.sidecar_complete.valid.poke(false.B)
      d.io.s2_state.expect(2.U)

      identity(d.io.payload_read_req.bits.transaction_identity)
      d.io.payload_read_req.bits.s2_slot.poke(0.U); d.io.payload_read_req.bits.source_generation.poke(1.U); d.io.payload_read_req.bits.fragment_index.poke(15.U)
      d.io.payload_read_req.valid.poke(true.B); d.io.payload_read_req.ready.expect(true.B); tick(); d.io.payload_read_req.valid.poke(false.B)
      d.io.payload_read_rsp.valid.expect(true.B); d.io.payload_read_rsp.bits.data.expect(0x40f.U)
      d.io.payload_read_rsp.ready.poke(true.B); tick(); d.io.payload_read_rsp.ready.poke(false.B)
    }
  }

  it("closes the explicit sidecar ingress with a named fixture transport after the accepted RTL3.2 allocation") {
    simulate(new RouteARTL32PackedReadFunctionalHarness(p, useRtl36cSidecarFixture = true)) { d =>
      val memory = new RouteAFunctionalMemoryEnvironment(p)
      memory.preload(0x99, Some(1), (0 until 16).map(i => BigInt(0x400 + i)).toVector,
        RouteARTL36cSidecarFixture.Default.records)
      d.io.demand.valid.poke(false.B); d.io.publication.valid.poke(false.B)
      d.io.descriptor.valid.poke(false.B); d.io.lease.valid.poke(false.B)
      d.io.service.valid.poke(false.B); d.io.sidecar_fragment.valid.poke(false.B); d.io.sidecar_complete.valid.poke(false.B)
      d.io.payload_read_req.valid.poke(false.B); d.io.payload_read_rsp.ready.poke(false.B)
      d.io.sidecar_read_req.valid.poke(false.B); d.io.sidecar_read_rsp.ready.poke(false.B)
      var requestCount = 0
      def tick(): Unit = {
        memory.drive(d.io.external)
        if (d.io.external.request.valid.peek().litToBoolean && d.io.external.request.ready.peek().litToBoolean) { requestCount += 1 }
        memory.observeAccepted(d.io.external)
        d.clock.step()
      }
      tick(); tick(); tick()

      identity(d.io.service.bits.transaction_identity); page(d.io.service.bits.page_ref); d.io.service.bits.s2_slot.poke(0.U)
      d.io.service.valid.poke(true.B); d.io.service.ready.expect(true.B); tick(); d.io.service.valid.poke(false.B)
      identity(d.io.demand.bits.transaction_identity); page(d.io.demand.bits.page_ref)
      d.io.demand.bits.arrival_ordinal.poke(2.U); d.io.demand.bits.candidate_id.poke(1.U)
      d.io.demand.bits.eligibility_snapshot.poke(0x3f.U); d.io.demand.bits.destination_endpoint.poke(0.U)
      d.io.demand.valid.poke(true.B); d.io.demand.ready.expect(true.B); tick(); d.io.demand.valid.poke(false.B)
      identity(d.io.publication.bits.transaction_identity); page(d.io.publication.bits.page_ref)
      d.io.publication.bits.transaction_group_tag.poke(1.U); d.io.publication.bits.valid_records.poke(2.U); d.io.publication.bits.packed_authoritative.poke(true.B)
      d.io.publication.valid.poke(true.B); d.io.publication.ready.expect(true.B); tick(); d.io.publication.valid.poke(false.B)
      identity(d.io.descriptor.bits.transaction_identity); page(d.io.descriptor.bits.page_ref)
      d.io.descriptor.bits.payload_handle_or_address.poke(0x99.U); d.io.descriptor.bits.sidecar_handle_or_address.poke(0xaa.U)
      d.io.descriptor.bits.valid_records.poke(2.U); d.io.descriptor.bits.sidecar_records.poke(2.U); d.io.descriptor.bits.live_reference_held.poke(true.B)
      d.io.descriptor.valid.poke(true.B); d.io.descriptor.ready.expect(true.B); tick(); d.io.descriptor.valid.poke(false.B)
      identity(d.io.lease.bits.transaction_identity); page(d.io.lease.bits.page_ref)
      d.io.lease.bits.s2_slot.poke(0.U); d.io.lease.bits.source_generation.poke(1.U); d.io.lease.bits.requires_sidecar.poke(true.B)
      d.io.lease.valid.poke(true.B); d.io.lease.ready.expect(true.B); tick(); d.io.lease.valid.poke(false.B)

      (0 until 120).foreach(_ => tick())
      assert(requestCount == 1, s"expected one functional-memory payload read, observed $requestCount")
      d.io.sidecar_fragment.ready.expect(false.B); d.io.sidecar_complete.ready.expect(false.B)
      d.io.sidecar_fixture_faulted.expect(false.B); d.io.sidecar_fixture_complete.expect(true.B)
      d.io.s2_state.expect(2.U) // READY only after the fixture-owned sidecar completion.
      identity(d.io.payload_read_req.bits.transaction_identity)
      d.io.payload_read_req.bits.s2_slot.poke(0.U); d.io.payload_read_req.bits.source_generation.poke(1.U); d.io.payload_read_req.bits.fragment_index.poke(15.U)
      d.io.payload_read_req.valid.poke(true.B); d.io.payload_read_req.ready.expect(true.B); tick(); d.io.payload_read_req.valid.poke(false.B)
      d.io.payload_read_rsp.valid.expect(true.B); d.io.payload_read_rsp.bits.data.expect(0x40f.U)
      d.io.payload_read_rsp.ready.poke(true.B); tick(); d.io.payload_read_rsp.ready.poke(false.B)
      identity(d.io.sidecar_read_req.bits.transaction_identity)
      d.io.sidecar_read_req.bits.s2_slot.poke(0.U); d.io.sidecar_read_req.bits.source_generation.poke(1.U); d.io.sidecar_read_req.bits.record_ordinal.poke(0.U)
      d.io.sidecar_read_req.valid.poke(true.B); d.io.sidecar_read_req.ready.expect(true.B); tick(); d.io.sidecar_read_req.valid.poke(false.B)
      d.io.sidecar_read_rsp.valid.expect(true.B); d.io.sidecar_read_rsp.bits.data.expect(0x900.U)
      d.io.sidecar_read_rsp.ready.poke(true.B); tick(); d.io.sidecar_read_rsp.ready.poke(false.B)
    }
  }
}
