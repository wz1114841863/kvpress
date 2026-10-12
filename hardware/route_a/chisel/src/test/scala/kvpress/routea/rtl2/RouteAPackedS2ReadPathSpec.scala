package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAPackedS2ReadEndpoint, RouteAPackedS2ReadProducer, RouteAReadEndpointDemultiplexer, RouteAReadIssueCandidateAdapter, RouteAR2ReadIngressMerge, RouteAS2GqaSourceWrapper, RouteATypedDeliveryRouter, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** C4 actual packed-page -> R2/R1 -> typed endpoint -> S2 functional-path harness. */
final class RouteAPackedS2ReadPathHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val work = Flipped(RouteAChannels.packed_s2_read_work(p))
    val service = Flipped(RouteAChannels.s2_service_req)
    val sidecar_fragment = Flipped(RouteAChannels.s2_sidecar_fragment(p))
    val sidecar_complete = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val payload_read_req = Flipped(RouteAChannels.s2_payload_read_req(p))
    val payload_read_rsp = RouteAChannels.s2_payload_read_rsp(p)
    val sidecar_read_req = Flipped(RouteAChannels.s2_sidecar_read_req(p))
    val sidecar_read_rsp = RouteAChannels.s2_sidecar_read_rsp(p)
    val gqa_commit = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val release = RouteAChannels.source_release(p)
    val external = new CoreMemoryExternalPort(p)
    val s2_state = Output(UInt(3.W))
    val s2_generation = Output(UInt(p.sourceGenerationWidth.W))
    // Test-only public owner observations for RTL2.6 composition.  These
    // expose no payload store and do not turn this harness into a source
    // scheduler or production-top component.
    val s2_available = Output(Bool())
    val s2_identity = Output(new TransactionIdentity)
    val s2_instance = Output(new SourceInstance(p))
  })

  val producer = Module(new RouteAPackedS2ReadProducer(p))
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
  val endpoint = Module(new RouteAPackedS2ReadEndpoint(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  StructuralTieOff.source(s2.io.s2_fill_lease_request_in)
  StructuralTieOff.sink(s2.io.s2_fill_lease_out)

  producer.io.work_in <> io.work
  producer.io.s2_fill_open_out <> s2.io.s2_fill_open_in
  issueAdapter.io.read_issue_in <> producer.io.read_issue_out
  StructuralTieOff.source(bridge.io.r3_pack_read_in)
  StructuralTieOff.source(bridge.io.r3_direct_pending_in)
  bridge.io.r5_s2_packed_in <> issueAdapter.io.candidate_out
  StructuralTieOff.source(bridge.io.r3_packed_write_in)
  StructuralTieOff.source(bridge.io.r5_append_in)
  StructuralTieOff.source(bridge.io.r5_reclaim_in)
  StructuralTieOff.sink(bridge.io.r3_pack_read_out)
  StructuralTieOff.sink(bridge.io.r3_direct_pending_out)
  StructuralTieOff.sink(bridge.io.r3_packed_write_out)
  StructuralTieOff.sink(bridge.io.r5_append_out)
  StructuralTieOff.sink(bridge.io.r5_reclaim_out)
  StructuralTieOff.source(readIngress.io.r3_pack_read_in)
  StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
  readIngress.io.r5_s2_packed_in <> bridge.io.r5_s2_packed_out
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
  s2.io.s2_sidecar_fragment_in <> io.sidecar_fragment
  s2.io.s2_sidecar_complete_in <> io.sidecar_complete
  s2.io.s2_payload_read_req_in <> io.payload_read_req
  io.payload_read_rsp <> s2.io.s2_payload_read_rsp_out
  s2.io.s2_sidecar_read_req_in <> io.sidecar_read_req
  io.sidecar_read_rsp <> s2.io.s2_sidecar_read_rsp_out
  s2.io.gqa_consumer_commit_in <> io.gqa_commit
  io.release <> s2.io.s2_release_out
  s2.io.s2_observe_slot := 0.U
  s2.io.component_status_out.ready := true.B
  io.s2_state := s2.io.s2_observe_state
  io.s2_generation := s2.io.s2_observe_generation
  io.s2_available := s2.io.s2_observe_available
  io.s2_identity := s2.io.s2_observe_identity
  io.s2_instance := s2.io.s2_observe_instance
}

final class RouteAPackedS2ReadPathSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=64, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private val eligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) |
    (1 << RouteAR2PredicateBits.Ownership) |
    (1 << RouteAR2PredicateBits.SourceCredit) |
    (1 << RouteAR2PredicateBits.DestinationReady) |
    (1 << RouteAR2PredicateBits.PackedMetadataPublished)

  private def init(d: RouteAPackedS2ReadPathHarness): Unit = {
    d.io.work.valid.poke(false.B); d.io.service.valid.poke(false.B); d.io.sidecar_fragment.valid.poke(false.B); d.io.sidecar_complete.valid.poke(false.B)
    d.io.payload_read_req.valid.poke(false.B); d.io.payload_read_rsp.ready.poke(false.B); d.io.sidecar_read_req.valid.poke(false.B); d.io.sidecar_read_rsp.ready.poke(false.B)
    d.io.gqa_commit.valid.poke(false.B); d.io.release.ready.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
    // R1 exposes init completion after the adapter handshake; S2 captures that
    // cross-owner fact into its own local initialization state on the next edge.
    d.clock.step()
  }

  private def serviceSlot(d: RouteAPackedS2ReadPathHarness, rid: Int = 3, page: Int = 7): Unit = {
    val service = d.io.service.bits
    service.transaction_identity.request_id.poke(rid.U); service.transaction_identity.incarnation.poke(1.U)
    service.page_ref.page_id.poke(page.U); service.page_ref.generation.poke(1.U); service.s2_slot.poke(0.U)
    d.io.service.valid.poke(true.B); d.io.service.ready.expect(true.B); d.clock.step(); d.io.service.valid.poke(false.B)
    d.io.s2_state.expect(1.U); d.io.s2_generation.expect(1.U)
  }

  private def offerWork(d: RouteAPackedS2ReadPathHarness, records: Int, rid: Int = 3, page: Int = 7, generation: Int = 1, slot: Int = 0): Unit = {
    val work = d.io.work.bits
    work.transaction_identity.request_id.poke(rid.U); work.transaction_identity.incarnation.poke(1.U)
    work.page_ref.page_id.poke(page.U); work.page_ref.generation.poke(1.U); work.s2_slot.poke(slot.U); work.source_generation.poke(generation.U)
    work.valid_records.poke(records.U); work.arrival_ordinal.poke(0.U); work.candidate_id.poke(0.U); work.eligibility_snapshot.poke(eligibility.U)
    work.payload_handle_or_address.poke(99.U); work.destination_endpoint.poke(0.U)
    d.io.work.valid.poke(true.B); d.io.work.ready.expect(true.B); d.clock.step(); d.io.work.valid.poke(false.B)
  }

  private def acceptRead(d: RouteAPackedS2ReadPathHarness, expectedFragments: Int): Unit = {
    var waited = 0
    while (d.io.external.request.valid.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
    d.io.external.request.valid.expect(true.B); d.io.external.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U)
    d.io.external.request.bits.expected_fragment_count.expect(expectedFragments.U); d.io.external.request.bits.address_ref.expect(99.U)
    d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
  }

  private def response(d: RouteAPackedS2ReadPathHarness, index: Int, last: Boolean, status: Int = 0, rid: Int = 3, incarnation: Int = 1): Unit = {
    val rsp = d.io.external.response.bits
    rsp.transaction_identity.request_id.poke(rid.U); rsp.transaction_identity.incarnation.poke(incarnation.U)
    rsp.fragment_index.poke(index.U); rsp.last.poke(last.B); rsp.status.poke(status.U); rsp.data.poke((0x400 + index).U)
    d.io.external.response.valid.poke(true.B)
    var waited = 0
    while (d.io.external.response.ready.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
    d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
  }

  private def settleEndpoint(d: RouteAPackedS2ReadPathHarness): Unit = {
    var waited = 0
    while (d.io.external.response.ready.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
    d.io.external.response.ready.expect(true.B)
    // The registry may release the final R1 identity before the endpoint's
    // locally captured payload/terminal pair reaches S2. Wait for that local
    // serialized handoff before supplying the independently-owned sidecar.
    d.clock.step(3)
  }

  private def sidecars(d: RouteAPackedS2ReadPathHarness, records: Int, rid: Int = 3, generation: Int = 1): Unit = {
    (0 until records).foreach { ordinal =>
      val sidecar = d.io.sidecar_fragment.bits
      sidecar.transaction_identity.request_id.poke(rid.U); sidecar.transaction_identity.incarnation.poke(1.U)
      sidecar.s2_slot.poke(0.U); sidecar.source_generation.poke(generation.U); sidecar.record_ordinal.poke(ordinal.U); sidecar.data.poke((0x900 + ordinal).U)
      d.io.sidecar_fragment.valid.poke(true.B); d.io.sidecar_fragment.ready.expect(true.B); d.clock.step(); d.io.sidecar_fragment.valid.poke(false.B)
    }
    val complete = d.io.sidecar_complete.bits
    complete.transaction_identity.request_id.poke(rid.U); complete.transaction_identity.incarnation.poke(1.U); complete.s2_slot.poke(0.U); complete.source_generation.poke(generation.U)
    d.io.sidecar_complete.valid.poke(true.B); d.io.sidecar_complete.ready.expect(true.B); d.clock.step(); d.io.sidecar_complete.valid.poke(false.B)
  }

  private def readPayload(d: RouteAPackedS2ReadPathHarness, index: Int, expected: Int): Unit = {
    val read = d.io.payload_read_req.bits
    read.transaction_identity.request_id.poke(3.U); read.transaction_identity.incarnation.poke(1.U); read.s2_slot.poke(0.U); read.source_generation.poke(1.U); read.fragment_index.poke(index.U)
    d.io.payload_read_req.valid.poke(true.B); d.io.payload_read_req.ready.expect(true.B); d.clock.step(); d.io.payload_read_req.valid.poke(false.B)
    d.io.payload_read_rsp.valid.expect(true.B); d.io.payload_read_rsp.bits.data.expect(expected.U); d.io.payload_read_rsp.ready.poke(true.B); d.clock.step(); d.io.payload_read_rsp.ready.poke(false.B)
  }

  private def commit(d: RouteAPackedS2ReadPathHarness, consumer: Int): Unit = {
    val c = d.io.gqa_commit.bits
    c.transaction_identity.request_id.poke(3.U); c.transaction_identity.incarnation.poke(1.U)
    c.source_instance.source_kind.poke(RouteASourceKind.Packed.U); c.source_instance.instance_coordinate.poke(0.U); c.source_instance.generation.poke(1.U); c.consumer_id.poke(consumer.U)
    d.io.gqa_commit.valid.poke(true.B); d.io.gqa_commit.ready.expect(true.B); d.clock.step(); d.io.gqa_commit.valid.poke(false.B)
  }

  it("loads a complete 64-record packed page as 512 fragments and waits for all sidecars before READY/release") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 64); acceptRead(d, expectedFragments = 512)
      (0 until 512).foreach(index => response(d, index, index == 511)); settleEndpoint(d)
      d.io.s2_state.expect(1.U); sidecars(d, records = 64); d.io.s2_state.expect(2.U)
      readPayload(d, 0, 0x400); readPayload(d, 511, 0x400 + 511)
      (0 until 4).foreach(commit(d, _)); d.io.release.valid.expect(true.B); d.io.release.ready.poke(true.B); d.clock.step(); d.io.release.ready.poke(false.B); d.io.s2_state.expect(0.U)
    }
  }

  it("consumes a stale external identity without S2 payload mutation") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1); acceptRead(d, expectedFragments = 8)
      response(d, index = 0, last = false, rid = 2, incarnation = 0)
      d.io.s2_state.expect(1.U)
      (0 until 8).foreach(index => response(d, index, index == 7)); settleEndpoint(d)
      sidecars(d, records = 1); d.io.s2_state.expect(2.U); readPayload(d, 0, 0x400)
    }
  }

  it("fails closed when work generation cannot open the current S2 slot") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1, generation = 2)
      d.clock.step(3); d.io.external.request.valid.expect(false.B); d.io.s2_state.expect(1.U)
    }
  }

  it("fails closed when packed-page or S2-slot association cannot open the current slot") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1, page = 8)
      d.clock.step(3); d.io.external.request.valid.expect(false.B); d.io.s2_state.expect(1.U)
    }
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1, slot = 1)
      d.clock.step(3); d.io.external.request.valid.expect(false.B); d.io.s2_state.expect(1.U)
    }
  }

  it("converts a matching terminal R1 fault into S2 fault without payload or release") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1); acceptRead(d, expectedFragments = 8)
      response(d, index = 0, last = true, status = p.coreMemoryFaultStatusCode)
      d.clock.step(2); d.io.s2_state.expect(3.U); d.io.release.valid.expect(false.B)
    }
  }

  it("normalizes malformed matching fragments fail-closed without S2 payload deposit") {
    simulate(new RouteAPackedS2ReadPathHarness(p)) { d =>
      init(d); serviceSlot(d); offerWork(d, records = 1); acceptRead(d, expectedFragments = 8)
      response(d, index = 1, last = false)
      d.clock.step(2); d.io.s2_state.expect(3.U); d.io.release.valid.expect(false.B)
    }
  }
}
