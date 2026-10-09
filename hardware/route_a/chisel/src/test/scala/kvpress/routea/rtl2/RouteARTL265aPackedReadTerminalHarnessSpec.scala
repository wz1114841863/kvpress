package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteASourceServicePacketAdapter
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.6.5a.1 composition: actual packed-page R2/R1 read delivery reaches
  * S2 before the existing source/R4/R6 completion path.  `work` and sidecar
  * remain named verification ingress; no production packed-read scheduler or
  * R3/R5-to-work bridge is created by this harness.
  */
final class RouteARTL265aPackedReadTerminalHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val sourcePlan = Flipped(RouteAChannels.source_completion_plan(p))
    val work = Flipped(RouteAChannels.packed_s2_read_work(p))
    val service = Flipped(RouteAChannels.s2_service_req)
    val sidecarFragment = Flipped(RouteAChannels.s2_sidecar_fragment(p))
    val sidecarComplete = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val external = new CoreMemoryExternalPort(p)
    val packedOffer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packedFragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val numericFault = Flipped(RouteAChannels.r4_numeric_fault)
    val attentionTerminal = RouteAChannels.attention_terminal_rsp
    val s2Ready = Output(Bool())
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val readPath = Module(new RouteAPackedS2ReadPathHarness(p))
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
  lifecycle.io.packed_source_release_in <> readPath.io.release
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B

  readPath.io.work <> io.work
  readPath.io.service <> io.service
  readPath.io.sidecar_fragment <> io.sidecarFragment
  readPath.io.sidecar_complete <> io.sidecarComplete
  StructuralTieOff.source(readPath.io.payload_read_req)
  StructuralTieOff.sink(readPath.io.payload_read_rsp)
  StructuralTieOff.source(readPath.io.sidecar_read_req)
  StructuralTieOff.sink(readPath.io.sidecar_read_rsp)
  readPath.io.external <> io.external
  io.s2Ready := readPath.io.s2_available

  packets.io.hot_available_in.valid := false.B
  packets.io.hot_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.hot_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.pending_available_in.valid := false.B
  packets.io.pending_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.pending_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.packed_available_in.valid := readPath.io.s2_available
  packets.io.packed_available_in.transaction_identity := readPath.io.s2_identity
  packets.io.packed_available_in.source_instance := readPath.io.s2_instance
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
  readPath.io.gqa_commit.valid := merge.io.consumer_partial_commit.valid &&
    merge.io.consumer_partial_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U
  readPath.io.gqa_commit.bits := merge.io.consumer_partial_commit.bits
  merge.io.consumer_partial_commit.ready := readPath.io.gqa_commit.ready
}

final class RouteARTL265aPackedReadTerminalHarnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=64, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)
  private val eligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) | (1 << RouteAR2PredicateBits.Ownership) | (1 << RouteAR2PredicateBits.SourceCredit) | (1 << RouteAR2PredicateBits.DestinationReady) | (1 << RouteAR2PredicateBits.PackedMetadataPublished)
  private def id(x: TransactionIdentity, r:Int):Unit={x.request_id.poke(r.U);x.incarnation.poke(1.U)}
  private def inst(x: SourceInstance,k:Int,c:Int,g:Int):Unit={x.source_kind.poke(k.U);x.instance_coordinate.poke(c.U);x.generation.poke(g.U)}
  private def init(d:RouteARTL265aPackedReadTerminalHarness):Unit={d.io.frontend.valid.poke(false.B);d.io.status.valid.poke(false.B);d.io.sourcePlan.valid.poke(false.B);d.io.work.valid.poke(false.B);d.io.service.valid.poke(false.B);d.io.sidecarFragment.valid.poke(false.B);d.io.sidecarComplete.valid.poke(false.B);d.io.packedOffer.valid.poke(false.B);d.io.packedFragment.valid.poke(false.B);d.io.numericFault.valid.poke(false.B);d.io.attentionTerminal.ready.poke(false.B);d.io.external.init_ack.valid.poke(false.B);d.io.external.request.ready.poke(false.B);d.io.external.response.valid.poke(false.B);d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B);id(d.io.external.response.bits.transaction_identity,0);d.io.external.response.bits.fragment_index.poke(0.U);d.io.external.response.bits.last.poke(true.B);d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U);d.io.external.response.bits.data.poke(0.U);d.io.external.init_ack.valid.poke(true.B);d.clock.step();d.io.external.init_ack.valid.poke(false.B);d.clock.step()}
  private def status(d:RouteARTL265aPackedReadTerminalHarness,c:Int):Unit={d.io.status.bits.acknowledgement_name.poke(c.U);d.io.status.bits.asserted.poke(true.B);d.io.status.valid.poke(true.B);d.io.status.ready.expect(true.B);d.clock.step();d.io.status.valid.poke(false.B)}
  private def start(d:RouteARTL265aPackedReadTerminalHarness):Unit={Seq(p.r6.memInitDoneStatusCode,p.r6.m2P3InitDoneStatusCode,p.r6.pageManagerInitDoneStatusCode).foreach(status(d,_));val f=d.io.frontend.bits;f.event_kind.poke(p.r6.sessionStartEventCode.U);f.session_id.poke(false.B);f.context_tokens.poke(32768.U);f.entry_id.poke(0.U);f.layer.poke(0.U);f.kv_head.poke(0.U);f.logical_position.poke(0.U);f.payload_ref.poke(0.U);f.disposition.poke(false.B);id(f.transaction_identity,0);f.admission_group_tag.poke(0.U);f.admission_member_ordinal.poke(0.U);f.admission_group_valid_records.poke(1.U);d.io.frontend.valid.poke(true.B);d.io.frontend.ready.expect(true.B);d.clock.step();d.io.frontend.valid.poke(false.B);f.event_kind.poke(p.r6.attentionServiceEventCode.U);id(f.transaction_identity,3);d.io.frontend.valid.poke(true.B);d.io.frontend.ready.expect(true.B);d.clock.step();d.io.frontend.valid.poke(false.B);val q=d.io.sourcePlan.bits;id(q.transaction_identity,3);q.source_presence.poke(4.U);inst(q.hot_instance,0,0,0);inst(q.pending_instance,1,0,0);inst(q.packed_instance,2,0,1);d.io.sourcePlan.valid.poke(true.B);d.io.sourcePlan.ready.expect(true.B);d.clock.step();d.io.sourcePlan.valid.poke(false.B);d.clock.step()}
  private def serviceAndWork(d:RouteARTL265aPackedReadTerminalHarness):Unit={val s=d.io.service.bits;id(s.transaction_identity,3);s.page_ref.page_id.poke(7.U);s.page_ref.generation.poke(1.U);s.s2_slot.poke(0.U);d.io.service.valid.poke(true.B);d.io.service.ready.expect(true.B);d.clock.step();d.io.service.valid.poke(false.B);val w=d.io.work.bits;id(w.transaction_identity,3);w.page_ref.page_id.poke(7.U);w.page_ref.generation.poke(1.U);w.s2_slot.poke(0.U);w.source_generation.poke(1.U);w.valid_records.poke(1.U);w.arrival_ordinal.poke(0.U);w.candidate_id.poke(0.U);w.eligibility_snapshot.poke(eligibility.U);w.payload_handle_or_address.poke(99.U);w.destination_endpoint.poke(0.U);d.io.work.valid.poke(true.B);d.io.work.ready.expect(true.B);d.clock.step();d.io.work.valid.poke(false.B)}
  private def fill(d:RouteARTL265aPackedReadTerminalHarness):Unit={var n=0;while(!d.io.external.request.valid.peek().litToBoolean&&n<32){d.clock.step();n+=1};d.io.external.request.valid.expect(true.B);d.io.external.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U);d.io.external.request.bits.expected_fragment_count.expect(8.U);d.io.external.request.ready.poke(true.B);d.clock.step();d.io.external.request.ready.poke(false.B);(0 until 8).foreach{i=>val r=d.io.external.response.bits;id(r.transaction_identity,3);r.fragment_index.poke(i.U);r.last.poke((i==7).B);r.status.poke(p.coreMemoryOkStatusCode.U);r.data.poke((0x400+i).U);d.io.external.response.valid.poke(true.B);var m=0;while(!d.io.external.response.ready.peek().litToBoolean&&m<32){d.clock.step();m+=1};d.io.external.response.ready.expect(true.B);d.clock.step();d.io.external.response.valid.poke(false.B)};d.clock.step(3);val sc=d.io.sidecarFragment.bits;id(sc.transaction_identity,3);sc.s2_slot.poke(0.U);sc.source_generation.poke(1.U);sc.record_ordinal.poke(0.U);sc.data.poke(0.U);d.io.sidecarFragment.valid.poke(true.B);d.io.sidecarFragment.ready.expect(true.B);d.clock.step();d.io.sidecarFragment.valid.poke(false.B);val done=d.io.sidecarComplete.bits;id(done.transaction_identity,3);done.s2_slot.poke(0.U);done.source_generation.poke(1.U);d.io.sidecarComplete.valid.poke(true.B);d.io.sidecarComplete.ready.expect(true.B);d.clock.step();d.io.sidecarComplete.valid.poke(false.B);d.io.s2Ready.expect(true.B)}
  private def packet(d:RouteARTL265aPackedReadTerminalHarness,c:Int):Unit={val h=(BigInt(2)<<64)|(BigInt(c)<<66)|(BigInt(1)<<69)|(BigInt(8)<<70);val o=d.io.packedOffer.bits;id(o.transaction_identity,3);inst(o.source_instance,2,0,1);o.consumer_id.poke(c.U);o.r4_header.poke(h.U);o.partial_present.poke(true.B);d.io.packedOffer.valid.poke(true.B);d.io.packedOffer.ready.expect(true.B);d.clock.step();d.io.packedOffer.valid.poke(false.B);d.clock.step();(0 until 8).foreach{i=>val f=d.io.packedFragment.bits;id(f.transaction_identity,3);inst(f.source_instance,2,0,1);f.consumer_id.poke(c.U);f.fragment_index.poke(i.U);f.last.poke((i==7).B);f.data.poke((c*8+i).U);d.io.packedFragment.valid.poke(true.B);d.io.packedFragment.ready.expect(true.B);d.clock.step();d.io.packedFragment.valid.poke(false.B)};d.clock.step(2)}
  it("uses the actual packed R2/R1 read path before S2/R4/R6 fault completion") {simulate(new RouteARTL265aPackedReadTerminalHarness(p)){d=>init(d);start(d);serviceAndWork(d);fill(d);(0 until 4).foreach(packet(d,_));id(d.io.numericFault.bits.transaction_identity,3);var n=0;while(!d.io.numericFault.ready.peek().litToBoolean&&n<16){d.clock.step();n+=1};d.io.numericFault.ready.expect(true.B);d.io.numericFault.valid.poke(true.B);d.clock.step();d.io.numericFault.valid.poke(false.B);n=0;while(!d.io.attentionTerminal.valid.peek().litToBoolean&&n<16){d.clock.step();n+=1};d.io.attentionTerminal.valid.expect(true.B);d.io.attentionTerminal.bits.transaction_identity.request_id.expect(3.U);d.io.attentionTerminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)}}
}
