package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteAS2GqaSourceWrapper, RouteASourceServicePacketAdapter}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Test-only RTL2.6.2 composition seam.  It copies public S2 owner
  * observations into packet availability; it never builds a production
  * R3/R5-to-S2 bridge, source plan, delivery context, or authority fact.
  */
final class RouteARTL26ComposedPackedSourceHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val sourcePlan = Flipped(RouteAChannels.source_completion_plan(p))
    val s2Service = Flipped(RouteAChannels.s2_service_req)
    val s2FillOpen = Flipped(RouteAChannels.s2_fill_open(p))
    val s2Payload = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2Terminal = Flipped(RouteAChannels.s2_fill_terminal(p))
    val packedOffer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packedFragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val numericFault = Flipped(RouteAChannels.r4_numeric_fault)
    val attentionTerminal = RouteAChannels.attention_terminal_rsp
    val s2Ready = Output(Bool())
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  StructuralTieOff.source(s2.io.s2_fill_lease_request_in)
  StructuralTieOff.sink(s2.io.s2_fill_lease_out)
  val packets = Module(new RouteASourceServicePacketAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.status
  lifecycle.io.source_completion_plan_in <> io.sourcePlan
  packets.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
  io.attentionTerminal <> lifecycle.io.attention_terminal_rsp
  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  lifecycle.io.hot_control_out.ready := true.B
  lifecycle.io.authority_transition_out.ready := true.B
  lifecycle.io.admission_context_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  lifecycle.io.packed_source_release_in <> s2.io.s2_release_out
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B

  s2.io.mem_init_done := true.B
  s2.io.drain_collection_enable := false.B
  s2.io.service_req_in <> io.s2Service
  s2.io.s2_fill_open_in <> io.s2FillOpen
  s2.io.s2_payload_fragment_in <> io.s2Payload
  StructuralTieOff.source(s2.io.s2_sidecar_fragment_in)
  s2.io.s2_fill_terminal_in <> io.s2Terminal
  StructuralTieOff.source(s2.io.s2_sidecar_complete_in)
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  s2.io.s2_observe_slot := 0.U
  s2.io.component_status_out.ready := true.B
  io.s2Ready := s2.io.s2_observe_available

  // Observation-only seam: no validity or association is invented here.
  packets.io.hot_available_in.valid := false.B
  packets.io.hot_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.hot_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.pending_available_in.valid := false.B
  packets.io.pending_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.pending_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.packed_available_in.valid := s2.io.s2_observe_available
  packets.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
  packets.io.packed_available_in.source_instance := s2.io.s2_observe_instance
  StructuralTieOff.source(packets.io.hot_offer_in)
  StructuralTieOff.source(packets.io.pending_offer_in)
  packets.io.packed_offer_in <> io.packedOffer
  StructuralTieOff.source(packets.io.hot_fragment_in)
  StructuralTieOff.source(packets.io.pending_fragment_in)
  packets.io.packed_fragment_in <> io.packedFragment

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> packets.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packets.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packets.io.r4_value_fragment_out
  merge.io.r4_accepted_partial_packet_out.ready := true.B
  StructuralTieOff.source(merge.io.r4_result_stub_in)
  merge.io.r4_numeric_fault_in <> io.numericFault
  merge.io.merge_req_in <> lifecycle.io.merge_req
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  StructuralTieOff.sink(merge.io.component_status_out)
  s2.io.gqa_consumer_commit_in.valid := merge.io.consumer_partial_commit.valid &&
    merge.io.consumer_partial_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U
  s2.io.gqa_consumer_commit_in.bits := merge.io.consumer_partial_commit.bits
  merge.io.consumer_partial_commit.ready := s2.io.gqa_consumer_commit_in.ready
}

/** One real S2 READY/release -> R4/R6 terminal path; no numeric/PPA claim. */
final class RouteARTL26ComposedPackedSourceHarnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def id(x: TransactionIdentity, r: Int): Unit = { x.request_id.poke(r.U); x.incarnation.poke(0.U) }
  private def inst(x: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = { x.source_kind.poke(kind.U); x.instance_coordinate.poke(coordinate.U); x.generation.poke(generation.U) }
  private def init(d: RouteARTL26ComposedPackedSourceHarness): Unit = {
    d.io.frontend.valid.poke(false.B); d.io.status.valid.poke(false.B); d.io.sourcePlan.valid.poke(false.B); d.io.s2Service.valid.poke(false.B); d.io.s2FillOpen.valid.poke(false.B); d.io.s2Payload.valid.poke(false.B); d.io.s2Terminal.valid.poke(false.B); d.io.packedOffer.valid.poke(false.B); d.io.packedFragment.valid.poke(false.B); d.io.numericFault.valid.poke(false.B); d.io.attentionTerminal.ready.poke(false.B)
  }
  private def status(d: RouteARTL26ComposedPackedSourceHarness, code: Int): Unit = { d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B); d.io.status.valid.poke(true.B); d.io.status.ready.expect(true.B); d.clock.step(); d.io.status.valid.poke(false.B) }
  private def frontend(d: RouteARTL26ComposedPackedSourceHarness, event: Int, r: Int): Unit = { val x=d.io.frontend.bits; x.event_kind.poke(event.U); x.session_id.poke(false.B); x.context_tokens.poke(32768.U); x.entry_id.poke(0.U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(0.U); x.payload_ref.poke(0.U); x.disposition.poke(false.B); id(x.transaction_identity,r); x.admission_group_tag.poke(0.U); x.admission_member_ordinal.poke(0.U); x.admission_group_valid_records.poke(1.U); d.io.frontend.valid.poke(true.B); d.io.frontend.ready.expect(true.B); d.clock.step(); d.io.frontend.valid.poke(false.B) }
  private def start(d: RouteARTL26ComposedPackedSourceHarness, r: Int): Unit = { Seq(p.r6.memInitDoneStatusCode,p.r6.m2P3InitDoneStatusCode,p.r6.pageManagerInitDoneStatusCode).foreach(status(d,_)); frontend(d,p.r6.sessionStartEventCode,0); frontend(d,p.r6.attentionServiceEventCode,r) }
  private def fill(d: RouteARTL26ComposedPackedSourceHarness, r: Int): Unit = {
    val s=d.io.s2Service.bits; id(s.transaction_identity,r); s.page_ref.page_id.poke(7.U); s.page_ref.generation.poke(1.U); s.s2_slot.poke(0.U); d.io.s2Service.valid.poke(true.B); d.io.s2Service.ready.expect(true.B); d.clock.step(); d.io.s2Service.valid.poke(false.B)
    val o=d.io.s2FillOpen.bits; id(o.transaction_identity,r); o.page_ref.page_id.poke(7.U); o.page_ref.generation.poke(1.U); o.s2_slot.poke(0.U); o.source_generation.poke(1.U); o.expected_fragment_count.poke(1.U); o.expected_sidecar_records.poke(0.U); o.requires_sidecar.poke(false.B); d.io.s2FillOpen.valid.poke(true.B); d.io.s2FillOpen.ready.expect(true.B); d.clock.step(); d.io.s2FillOpen.valid.poke(false.B)
    val q=d.io.s2Payload.bits; id(q.transaction_identity,r); q.s2_slot.poke(0.U); q.source_generation.poke(1.U); q.fragment_index.poke(0.U); q.last.poke(true.B); q.data.poke(0.U); d.io.s2Payload.valid.poke(true.B); d.io.s2Payload.ready.expect(true.B); d.clock.step(); d.io.s2Payload.valid.poke(false.B)
    val t=d.io.s2Terminal.bits; id(t.transaction_identity,r); t.s2_slot.poke(0.U); t.source_generation.poke(1.U); t.fragment_index.poke(0.U); t.last.poke(true.B); t.status.poke(p.coreMemoryOkStatusCode.U); d.io.s2Terminal.valid.poke(true.B); d.io.s2Terminal.ready.expect(true.B); d.clock.step(); d.io.s2Terminal.valid.poke(false.B); d.io.s2Ready.expect(true.B)
  }
  private def plan(d: RouteARTL26ComposedPackedSourceHarness, r: Int, generation: Int=1): Unit = { val x=d.io.sourcePlan.bits; id(x.transaction_identity,r); x.source_presence.poke(4.U); inst(x.hot_instance,0,0,0); inst(x.pending_instance,1,0,0); inst(x.packed_instance,2,0,generation); d.io.sourcePlan.valid.poke(true.B); d.io.sourcePlan.ready.expect(true.B); d.clock.step(); d.io.sourcePlan.valid.poke(false.B); d.clock.step() }
  private def header(c: Int): BigInt = (BigInt(2)<<64)|(BigInt(c)<<66)|(BigInt(1)<<69)|(BigInt(8)<<70)
  private def packet(d: RouteARTL26ComposedPackedSourceHarness, r: Int, c: Int): Unit = { val o=d.io.packedOffer.bits; id(o.transaction_identity,r); inst(o.source_instance,2,0,1); o.consumer_id.poke(c.U); o.r4_header.poke(header(c).U); o.partial_present.poke(true.B); d.io.packedOffer.valid.poke(true.B); d.io.packedOffer.ready.expect(true.B); d.clock.step(); d.io.packedOffer.valid.poke(false.B); d.clock.step(); (0 until 8).foreach { i => val f=d.io.packedFragment.bits; id(f.transaction_identity,r); inst(f.source_instance,2,0,1); f.consumer_id.poke(c.U); f.fragment_index.poke(i.U); f.last.poke((i==7).B); f.data.poke((c*8+i).U); d.io.packedFragment.valid.poke(true.B); d.io.packedFragment.ready.expect(true.B); d.clock.step(); d.io.packedFragment.valid.poke(false.B) }; d.clock.step(2) }

  it("carries one real S2 READY/release owner through four packed packets to one R4/R6 fault terminal") { simulate(new RouteARTL26ComposedPackedSourceHarness(p)) { d => init(d); start(d,1); fill(d,1); plan(d,1); (0 until 4).foreach(packet(d,1,_)); id(d.io.numericFault.bits.transaction_identity,1); var n=0; while(!d.io.numericFault.ready.peek().litToBoolean && n<8){d.clock.step();n+=1}; d.io.numericFault.ready.expect(true.B); d.io.numericFault.valid.poke(true.B); d.clock.step(); d.io.numericFault.valid.poke(false.B); n=0; while(!d.io.attentionTerminal.valid.peek().litToBoolean && n<8){d.clock.step();n+=1}; d.io.attentionTerminal.valid.expect(true.B); d.io.attentionTerminal.bits.transaction_identity.request_id.expect(1.U); d.io.attentionTerminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U); d.io.attentionTerminal.ready.poke(true.B); d.clock.step(); d.io.attentionTerminal.ready.poke(false.B) } }
  it("rejects a packed source-plan generation that cannot match the real S2 owner") { simulate(new RouteARTL26ComposedPackedSourceHarness(p)) { d => init(d); start(d,2); fill(d,2); plan(d,2,generation=0); val o=d.io.packedOffer.bits; id(o.transaction_identity,2); inst(o.source_instance,2,0,1); o.consumer_id.poke(0.U); o.r4_header.poke(header(0).U); o.partial_present.poke(true.B); d.io.packedOffer.valid.poke(true.B); d.io.packedOffer.ready.expect(false.B); d.io.packedOffer.valid.poke(false.B); d.io.attentionTerminal.valid.expect(false.B) } }
}
