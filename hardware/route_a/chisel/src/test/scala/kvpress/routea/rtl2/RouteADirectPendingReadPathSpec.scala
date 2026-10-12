package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAReadEndpointDemultiplexer, RouteAR2ReadIngressMerge, RouteADirectPendingReadEndpoint, RouteAReadIssueCandidateAdapter, RouteAR3DirectPendingReadProducer, RouteATypedDeliveryRouter, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.incremental.RouteADirectPendingEndpointV1
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** C3 actual R3 -> C1/R2/R1 -> direct-pending control/transport harness. */
final class RouteADirectPendingReadPathHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val direct_mem_init_done = Input(Bool())
    val direct_open = Flipped(RouteAChannels.direct_pending_open(p))
    val direct_work = Flipped(RouteAChannels.direct_pending_read_work(p))
    val direct_payload = RouteAChannels.direct_pending_payload_fragment(p)
    val direct_commit = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val external = new CoreMemoryExternalPort(p)
    val direct_active = Output(Bool())
    val direct_generation = Output(UInt(p.sourceGenerationWidth.W))
  })

  val producer = Module(new RouteAR3DirectPendingReadProducer(p))
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
  val endpoint = Module(new RouteADirectPendingReadEndpoint(p))
  val direct = Module(new RouteADirectPendingEndpointV1(p))

  producer.io.work_in <> io.direct_work
  issueAdapter.io.read_issue_in <> producer.io.read_issue_out
  StructuralTieOff.source(bridge.io.r3_pack_read_in)
  bridge.io.r3_direct_pending_in <> issueAdapter.io.candidate_out
  StructuralTieOff.source(bridge.io.r5_s2_packed_in)
  StructuralTieOff.source(bridge.io.r3_packed_write_in)
  StructuralTieOff.source(bridge.io.r5_append_in)
  StructuralTieOff.source(bridge.io.r5_reclaim_in)
  StructuralTieOff.sink(bridge.io.r3_pack_read_out)
  StructuralTieOff.sink(bridge.io.r5_s2_packed_out)
  StructuralTieOff.sink(bridge.io.r3_packed_write_out)
  StructuralTieOff.sink(bridge.io.r5_append_out)
  StructuralTieOff.sink(bridge.io.r5_reclaim_out)
  StructuralTieOff.source(readIngress.io.r3_pack_read_in)
  readIngress.io.r3_direct_pending_in <> bridge.io.r3_direct_pending_out
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
  endpoint.io.resolved_fragment_in <> endpointDemux.io.direct_pending_out
  StructuralTieOff.sink(endpointDemux.io.p3_pack_read_out)
  StructuralTieOff.sink(endpointDemux.io.packed_s2_out)
  StructuralTieOff.sink(router.io.r3_packed_write_out)
  StructuralTieOff.sink(router.io.r5_append_out)
  StructuralTieOff.sink(router.io.r5_reclaim_out)

  direct.io.mem_init_done := io.direct_mem_init_done
  direct.io.drain_collection_enable := false.B
  direct.io.pending_source_open_in <> io.direct_open
  direct.io.gqa_consumer_commit_in <> io.direct_commit
  direct.io.direct_release_out.ready := true.B
  StructuralTieOff.sink(direct.io.component_status_out)
  endpoint.io.endpoint_active_in := direct.io.direct_observe_active
  endpoint.io.endpoint_identity_in := direct.io.direct_observe_identity
  endpoint.io.endpoint_generation_in := direct.io.direct_observe_generation
  io.direct_payload <> endpoint.io.payload_fragment_out
  direct.io.direct_pending_record_terminal_in <> endpoint.io.record_terminal_out
  io.direct_active := direct.io.direct_observe_active
  io.direct_generation := direct.io.direct_observe_generation
}

final class RouteADirectPendingReadPathSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=64, coreMemoryFragmentCountWidth=4, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private val eligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) |
    (1 << RouteAR2PredicateBits.Ownership) |
    (1 << RouteAR2PredicateBits.SourceCredit) |
    (1 << RouteAR2PredicateBits.DestinationReady) |
    (1 << RouteAR2PredicateBits.PendingAuthoritative)

  private def init(d: RouteADirectPendingReadPathHarness): Unit = {
    d.io.direct_mem_init_done.poke(false.B); d.io.direct_open.valid.poke(false.B); d.io.direct_work.valid.poke(false.B)
    d.io.direct_payload.ready.poke(false.B); d.io.direct_commit.valid.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B)
    d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.direct_mem_init_done.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
  }

  private def open(d: RouteADirectPendingReadPathHarness, rid: Int = 3, generation: Int = 1): Unit = {
    val o = d.io.direct_open.bits
    o.transaction_identity.request_id.poke(rid.U); o.transaction_identity.incarnation.poke(1.U)
    o.layer.poke(0.U); o.kv_head.poke(0.U); o.ordered_pending_descriptor_ref.poke(0.U); o.expected_generation_or_validity.poke(0.U)
    d.io.direct_open.valid.poke(true.B); d.io.direct_open.ready.expect(true.B); d.clock.step(); d.io.direct_open.valid.poke(false.B)
    d.io.direct_active.expect(true.B); d.io.direct_generation.expect(generation.U)
  }

  private def offerWork(d: RouteADirectPendingReadPathHarness, rid: Int = 3, generation: Int = 1, ordinal: Int = 0, sourceLast: Boolean = true): Unit = {
    val w = d.io.direct_work.bits
    w.transaction_identity.request_id.poke(rid.U); w.transaction_identity.incarnation.poke(1.U)
    w.arrival_ordinal.poke(0.U); w.candidate_id.poke(0.U); w.eligibility_snapshot.poke(eligibility.U)
    w.payload_handle_or_address.poke(55.U); w.valid_count.poke(1.U); w.destination_endpoint.poke(0.U)
    w.endpoint_generation.poke(generation.U); w.pending_ordinal.poke(ordinal.U); w.source_last.poke(sourceLast.B)
    d.io.direct_work.valid.poke(true.B)
  }

  private def acceptRead(d: RouteADirectPendingReadPathHarness): Unit = {
    var waited = 0
    while (d.io.external.request.valid.peek().litValue == 0 && waited < 24) { d.clock.step(); waited += 1 }
    d.io.external.request.valid.expect(true.B); d.io.external.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U)
    d.io.external.request.bits.expected_fragment_count.expect(8.U); d.io.external.request.bits.address_ref.expect(55.U)
    d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B); d.io.direct_work.valid.poke(false.B)
  }

  private def respondAndAcceptPayload(d: RouteADirectPendingReadPathHarness, index: Int, last: Boolean, status: Int = 0, rid: Int = 3, incarnation: Int = 1, expectPayload: Boolean = true): Unit = {
    val r = d.io.external.response.bits
    r.transaction_identity.request_id.poke(rid.U); r.transaction_identity.incarnation.poke(incarnation.U)
    r.fragment_index.poke(index.U); r.last.poke(last.B); r.status.poke(status.U); r.data.poke((0x200 + index).U)
    d.io.external.response.valid.poke(true.B)
    var responseWait = 0
    while (d.io.external.response.ready.peek().litValue == 0 && responseWait < 24) { d.clock.step(); responseWait += 1 }
    d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
    if (expectPayload) {
      var payloadWait = 0
      while (d.io.direct_payload.valid.peek().litValue == 0 && payloadWait < 24) { d.clock.step(); payloadWait += 1 }
      d.io.direct_payload.valid.expect(true.B); d.io.direct_payload.bits.fragment_index.expect(index.U)
      d.io.direct_payload.bits.data.expect((0x200 + index).U); d.io.direct_payload.bits.source_last.expect(true.B)
      d.io.direct_payload.ready.poke(true.B)
      d.clock.step(); d.io.direct_payload.ready.poke(false.B)
    }
    d.clock.step(2)
  }

  private def commit(d: RouteADirectPendingReadPathHarness, consumer: Int): Unit = {
    val c = d.io.direct_commit.bits
    c.transaction_identity.request_id.poke(3.U); c.transaction_identity.incarnation.poke(1.U)
    c.source_instance.source_kind.poke(RouteASourceKind.Pending.U); c.source_instance.instance_coordinate.poke(0.U); c.source_instance.generation.poke(1.U); c.consumer_id.poke(consumer.U)
    d.io.direct_commit.valid.poke(true.B); d.io.direct_commit.ready.expect(true.B); d.clock.step(); d.io.direct_commit.valid.poke(false.B)
  }

  it("transports one direct pending record as eight fragments before terminal and four-commit release") {
    simulate(new RouteADirectPendingReadPathHarness(p)) { d =>
      init(d); open(d); offerWork(d); acceptRead(d)
      (0 until 8).foreach(index => respondAndAcceptPayload(d, index, index == 7))
      (0 until 4).foreach(commit(d, _)); d.clock.step(); d.io.direct_active.expect(false.B)
    }
  }

  it("consumes a stale external identity without direct payload mutation") {
    simulate(new RouteADirectPendingReadPathHarness(p)) { d =>
      init(d); open(d); offerWork(d); acceptRead(d)
      val stale = d.io.external.response.bits
      stale.transaction_identity.request_id.poke(2.U); stale.transaction_identity.incarnation.poke(0.U); stale.fragment_index.poke(0.U); stale.last.poke(false.B); stale.status.poke(0.U); stale.data.poke(0.U)
      d.io.external.response.valid.poke(true.B); d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
      d.io.direct_payload.valid.expect(false.B); d.io.direct_active.expect(true.B)
      (0 until 8).foreach(index => respondAndAcceptPayload(d, index, index == 7))
    }
  }

  it("refuses a generation-mismatched direct endpoint without payload handoff") {
    simulate(new RouteADirectPendingReadPathHarness(p)) { d =>
      init(d); open(d); offerWork(d, generation = 2); acceptRead(d)
      val bad = d.io.external.response.bits
      bad.transaction_identity.request_id.poke(3.U); bad.transaction_identity.incarnation.poke(1.U); bad.fragment_index.poke(0.U); bad.last.poke(false.B); bad.status.poke(0.U); bad.data.poke(0.U)
      d.io.external.response.valid.poke(true.B); d.clock.step(4); d.io.direct_payload.valid.expect(false.B); d.io.external.response.ready.expect(false.B); d.io.direct_active.expect(true.B)
    }
  }

  it("converts a matching terminal R1 fault into direct fault control without payload or release") {
    simulate(new RouteADirectPendingReadPathHarness(p)) { d =>
      init(d); open(d); offerWork(d); acceptRead(d)
      respondAndAcceptPayload(d, index = 0, last = true, status = p.coreMemoryFaultStatusCode, expectPayload = false)
      d.io.direct_payload.valid.expect(false.B); d.io.direct_commit.valid.poke(true.B); d.io.direct_commit.ready.expect(false.B); d.io.direct_commit.valid.poke(false.B)
      d.io.direct_active.expect(true.B)
    }
  }

  it("normalizes a malformed matching fragment to direct fault control without payload handoff") {
    simulate(new RouteADirectPendingReadPathHarness(p)) { d =>
      init(d); open(d); offerWork(d); acceptRead(d)
      respondAndAcceptPayload(d, index = 1, last = false, expectPayload = false)
      d.io.direct_payload.valid.expect(false.B); d.io.direct_commit.valid.poke(true.B); d.io.direct_commit.ready.expect(false.B); d.io.direct_commit.valid.poke(false.B)
      d.io.direct_active.expect(true.B)
    }
  }
}
