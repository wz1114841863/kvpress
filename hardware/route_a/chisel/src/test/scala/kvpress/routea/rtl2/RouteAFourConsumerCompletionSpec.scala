package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteAHotSourcePath, RouteAS2GqaSourceWrapper, RouteASourceCommitDemultiplexer, RouteASourceServicePacketAdapter}
import kvpress.routea.incremental.{RouteADirectPendingEndpointV1, RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * C8 integration harness.  Source offers/fragments are explicit verification
  * inputs; they are structural packets, not hot/direct/S2 numeric arithmetic.
  */
final class RouteAFourConsumerCompletionHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val plan = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_open = Flipped(RouteAChannels.hot_source_open(p))
    val pending_open = Flipped(RouteAChannels.direct_pending_open(p))
    val pending_terminal = Flipped(RouteAChannels.direct_pending_record_terminal(p))
    val s2_service = Flipped(RouteAChannels.s2_service_req)
    val s2_fill_open = Flipped(RouteAChannels.s2_fill_open(p))
    val s2_payload = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2_terminal = Flipped(RouteAChannels.s2_fill_terminal(p))
    val hot_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val pending_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packed_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val hot_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val pending_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val packed_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val merge_req = RouteAChannels.merge_req
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val hot = Module(new RouteAHotSourcePath(p))
  val direct = Module(new RouteADirectPendingEndpointV1(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  StructuralTieOff.source(s2.io.s2_fill_lease_request_in)
  StructuralTieOff.sink(s2.io.s2_fill_lease_out)
  val packetAdapter = Module(new RouteASourceServicePacketAdapter(p))
  val commitDemux = Module(new RouteASourceCommitDemultiplexer(p))
  val merge = Module(new RouteAMergeBoundary(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.status
  lifecycle.io.source_completion_plan_in <> io.plan
  packetAdapter.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out

  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.attention_terminal_rsp)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.pending_source_failure_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B

  StructuralTieOff.source(hot.io.lifecycle_control_in)
  hot.io.hot_source_open_in <> io.hot_open
  lifecycle.io.hot_source_release_in <> hot.io.hot_release_out

  direct.io.mem_init_done := true.B
  direct.io.drain_collection_enable := false.B
  direct.io.pending_source_open_in <> io.pending_open
  StructuralTieOff.sink(direct.io.pending_source_open_ack_out)
  StructuralTieOff.source(direct.io.direct_abort_in)
  StructuralTieOff.sink(direct.io.direct_abort_ack_out)
  direct.io.direct_pending_record_terminal_in <> io.pending_terminal
  lifecycle.io.pending_source_release_in <> direct.io.direct_release_out
  StructuralTieOff.sink(direct.io.component_status_out)

  s2.io.mem_init_done := true.B
  s2.io.drain_collection_enable := false.B
  s2.io.service_req_in <> io.s2_service
  s2.io.s2_fill_open_in <> io.s2_fill_open
  s2.io.s2_payload_fragment_in <> io.s2_payload
  s2.io.s2_fill_terminal_in <> io.s2_terminal
  StructuralTieOff.source(s2.io.s2_sidecar_fragment_in)
  StructuralTieOff.source(s2.io.s2_sidecar_complete_in)
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  StructuralTieOff.sink(s2.io.component_status_out)
  s2.io.s2_observe_slot := packetAdapter.io.packed_observe_slot_out
  lifecycle.io.packed_source_release_in <> s2.io.s2_release_out

  packetAdapter.io.hot_available_in.valid := hot.io.hot_observe_active
  packetAdapter.io.hot_available_in.transaction_identity := hot.io.hot_observe_identity
  packetAdapter.io.hot_available_in.source_instance := hot.io.hot_observe_instance
  packetAdapter.io.pending_available_in.valid := direct.io.direct_observe_deliverable
  packetAdapter.io.pending_available_in.transaction_identity := direct.io.direct_observe_identity
  packetAdapter.io.pending_available_in.source_instance := direct.io.direct_observe_instance
  packetAdapter.io.packed_available_in.valid := s2.io.s2_observe_available
  packetAdapter.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
  packetAdapter.io.packed_available_in.source_instance := s2.io.s2_observe_instance
  packetAdapter.io.hot_offer_in <> io.hot_offer
  packetAdapter.io.pending_offer_in <> io.pending_offer
  packetAdapter.io.packed_offer_in <> io.packed_offer
  packetAdapter.io.hot_fragment_in <> io.hot_fragment
  packetAdapter.io.pending_fragment_in <> io.pending_fragment
  packetAdapter.io.packed_fragment_in <> io.packed_fragment

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> packetAdapter.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packetAdapter.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packetAdapter.io.r4_value_fragment_out
  merge.io.r4_accepted_partial_packet_out.ready := true.B
  StructuralTieOff.source(merge.io.r4_result_stub_in)
  StructuralTieOff.source(merge.io.r4_numeric_fault_in)
  StructuralTieOff.source(merge.io.merge_req_in)
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  StructuralTieOff.sink(merge.io.component_status_out)

  commitDemux.io.commit_in <> merge.io.consumer_partial_commit
  hot.io.gqa_consumer_commit_in <> commitDemux.io.hot_commit_out
  direct.io.gqa_consumer_commit_in <> commitDemux.io.pending_commit_out
  s2.io.gqa_consumer_commit_in <> commitDemux.io.packed_commit_out
  io.merge_req <> lifecycle.io.merge_req
}

/** Focused C8 fail-closed witness for the named R4-to-owner commit router. */
final class RouteASourceCommitDemultiplexerHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val commit_in = Flipped(RouteAChannels.consumer_partial_commit(p))
    val hot_commit = RouteAChannels.gqa_consumer_commit(p)
    val pending_commit = RouteAChannels.gqa_consumer_commit(p)
    val packed_commit = RouteAChannels.gqa_consumer_commit(p)
  })
  val demux = Module(new RouteASourceCommitDemultiplexer(p))
  demux.io.commit_in <> io.commit_in
  io.hot_commit <> demux.io.hot_commit_out
  io.pending_commit <> demux.io.pending_commit_out
  io.packed_commit <> demux.io.packed_commit_out
}

final class RouteAFourConsumerCompletionSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def instance(port: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = {
    port.source_kind.poke(kind.U); port.instance_coordinate.poke(coordinate.U); port.generation.poke(generation.U)
  }
  private def identity(port: TransactionIdentity, rid: Int): Unit = {
    port.request_id.poke(rid.U); port.incarnation.poke(0.U)
  }
  private def header(kind: Int, consumer: Int): BigInt = (BigInt(kind) << 64) | (BigInt(consumer) << 66) | (BigInt(1) << 69) | (BigInt(8) << 70)

  private def init(d: RouteAFourConsumerCompletionHarness): Unit = {
    Seq(d.io.frontend, d.io.status, d.io.plan, d.io.hot_open, d.io.pending_open, d.io.pending_terminal,
      d.io.s2_service, d.io.s2_fill_open, d.io.s2_payload, d.io.s2_terminal,
      d.io.hot_offer, d.io.pending_offer, d.io.packed_offer, d.io.hot_fragment, d.io.pending_fragment, d.io.packed_fragment).foreach(_.valid.poke(false.B))
    d.io.merge_req.ready.poke(false.B)
  }
  private def status(d: RouteAFourConsumerCompletionHarness, code: Int): Unit = {
    d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B); d.io.status.valid.poke(true.B)
    d.io.status.ready.expect(true.B); d.clock.step(); d.io.status.valid.poke(false.B)
  }
  private def frontend(d: RouteAFourConsumerCompletionHarness, event: Int, rid: Int): Unit = {
    val f = d.io.frontend.bits
    f.event_kind.poke(event.U); f.session_id.poke(false.B); f.context_tokens.poke(32768.U); f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U)
    f.logical_position.poke(0.U); f.payload_ref.poke(0.U); f.disposition.poke(false.B); identity(f.transaction_identity, rid)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    d.io.frontend.valid.poke(true.B); d.io.frontend.ready.expect(true.B); d.clock.step(); d.io.frontend.valid.poke(false.B)
  }
  private def activateHot(d: RouteAFourConsumerCompletionHarness, rid: Int): Unit = {
    identity(d.io.hot_open.bits.transaction_identity, rid); instance(d.io.hot_open.bits.source_instance, 0, 10, 1)
    d.io.hot_open.valid.poke(true.B); d.io.hot_open.ready.expect(true.B); d.clock.step(); d.io.hot_open.valid.poke(false.B)
  }
  private def activatePending(d: RouteAFourConsumerCompletionHarness, rid: Int): Unit = {
    val open = d.io.pending_open.bits; identity(open.transaction_identity, rid); open.pending_instance.source_kind.poke(RouteASourceKind.Pending.U); open.pending_instance.instance_coordinate.poke(0.U); open.pending_instance.generation.poke(1.U); open.layer.poke(0.U); open.kv_head.poke(0.U); open.ordered_pending_descriptor_ref.poke(0.U); open.expected_generation_or_validity.poke(0.U)
    d.io.pending_open.valid.poke(true.B); d.io.pending_open.ready.expect(true.B); d.clock.step(); d.io.pending_open.valid.poke(false.B)
    val terminal = d.io.pending_terminal.bits; identity(terminal.transaction_identity, rid); terminal.endpoint_generation.poke(1.U); terminal.ordinal.poke(0.U); terminal.last.poke(true.B); terminal.status.poke(p.coreMemoryOkStatusCode.U); terminal.explicit_empty.poke(false.B)
    d.io.pending_terminal.valid.poke(true.B); d.io.pending_terminal.ready.expect(true.B); d.clock.step(); d.io.pending_terminal.valid.poke(false.B)
  }
  private def activatePacked(d: RouteAFourConsumerCompletionHarness, rid: Int): Unit = {
    val service = d.io.s2_service.bits; identity(service.transaction_identity, rid); service.page_ref.page_id.poke(7.U); service.page_ref.generation.poke(0.U); service.s2_slot.poke(0.U)
    d.io.s2_service.valid.poke(true.B); d.io.s2_service.ready.expect(true.B); d.clock.step(); d.io.s2_service.valid.poke(false.B)
    val open = d.io.s2_fill_open.bits; identity(open.transaction_identity, rid); open.page_ref.page_id.poke(7.U); open.page_ref.generation.poke(0.U); open.s2_slot.poke(0.U); open.source_generation.poke(1.U); open.expected_fragment_count.poke(1.U); open.expected_sidecar_records.poke(0.U); open.requires_sidecar.poke(false.B)
    d.io.s2_fill_open.valid.poke(true.B); d.io.s2_fill_open.ready.expect(true.B); d.clock.step(); d.io.s2_fill_open.valid.poke(false.B)
    val payload = d.io.s2_payload.bits; identity(payload.transaction_identity, rid); payload.s2_slot.poke(0.U); payload.source_generation.poke(1.U); payload.fragment_index.poke(0.U); payload.last.poke(true.B); payload.data.poke(0.U)
    d.io.s2_payload.valid.poke(true.B); d.io.s2_payload.ready.expect(true.B); d.clock.step(); d.io.s2_payload.valid.poke(false.B)
    val terminal = d.io.s2_terminal.bits; identity(terminal.transaction_identity, rid); terminal.s2_slot.poke(0.U); terminal.source_generation.poke(1.U); terminal.fragment_index.poke(0.U); terminal.last.poke(true.B); terminal.status.poke(p.coreMemoryOkStatusCode.U)
    d.io.s2_terminal.valid.poke(true.B); d.io.s2_terminal.ready.expect(true.B); d.clock.step(); d.io.s2_terminal.valid.poke(false.B)
  }
  private def sendPlan(d: RouteAFourConsumerCompletionHarness, rid: Int, presence: Int): Unit = {
    val plan = d.io.plan.bits; identity(plan.transaction_identity, rid); plan.source_presence.poke(presence.U)
    instance(plan.hot_instance, 0, 10, 1); instance(plan.pending_instance, 1, 0, 1); instance(plan.packed_instance, 2, 0, 1)
    d.io.plan.valid.poke(true.B); d.io.plan.ready.expect(true.B); d.clock.step(); d.io.plan.valid.poke(false.B); d.clock.step()
  }
  private def offer(d: RouteAFourConsumerCompletionHarness, kind: Int) = kind match { case 0 => d.io.hot_offer; case 1 => d.io.pending_offer; case _ => d.io.packed_offer }
  private def fragment(d: RouteAFourConsumerCompletionHarness, kind: Int) = kind match { case 0 => d.io.hot_fragment; case 1 => d.io.pending_fragment; case _ => d.io.packed_fragment }
  private def sendPacket(d: RouteAFourConsumerCompletionHarness, rid: Int, kind: Int, consumer: Int): Unit = {
    val o = offer(d, kind); identity(o.bits.transaction_identity, rid); instance(o.bits.source_instance, kind, if (kind == 0) 10 else 0, 1); o.bits.consumer_id.poke(consumer.U); o.bits.r4_header.poke(header(kind, consumer).U); o.bits.partial_present.poke(true.B)
    o.valid.poke(true.B); o.ready.expect(true.B); d.clock.step(); o.valid.poke(false.B); d.clock.step()
    (0 until 8).foreach { index =>
      val f = fragment(d, kind); identity(f.bits.transaction_identity, rid); instance(f.bits.source_instance, kind, if (kind == 0) 10 else 0, 1); f.bits.consumer_id.poke(consumer.U); f.bits.fragment_index.poke(index.U); f.bits.last.poke((index == 7).B); f.bits.data.poke((kind * 0x100 + consumer * 8 + index).U)
      f.valid.poke(true.B); f.ready.expect(true.B); d.clock.step(); f.valid.poke(false.B)
    }
    // The R4 commit must be consumed by the exact source owner before a later
    // packet can advance; wait only for this event-level handoff.
    d.clock.step(2)
  }
  private def startAttention(d: RouteAFourConsumerCompletionHarness, rid: Int): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(d, _))
    frontend(d, p.r6.sessionStartEventCode, 0); frontend(d, p.r6.attentionServiceEventCode, rid)
  }

  it("requires all four exact R4 commits before the sole source can release and R6 can issue merge") {
    simulate(new RouteAFourConsumerCompletionHarness(p)) { d =>
      init(d); startAttention(d, 1); activateHot(d, 1); sendPlan(d, 1, 1)
      (0 until 3).foreach(sendPacket(d, 1, 0, _)); d.io.merge_req.valid.expect(false.B)
      sendPacket(d, 1, 0, 3)
      (0 until 4).foreach(_ => d.clock.step())
      d.io.merge_req.valid.expect(true.B); d.io.merge_req.bits.transaction_identity.request_id.expect(1.U); d.io.merge_req.bits.source_presence.expect(1.U)
      d.clock.step(); d.io.merge_req.valid.expect(true.B)
      d.io.merge_req.ready.poke(true.B); d.clock.step(); d.io.merge_req.ready.poke(false.B); d.io.merge_req.valid.expect(false.B)
    }
  }

  it("closes every nonempty mask through four commits per present owner and one R6 merge request") {
    for (presence <- 1 to 7) {
      simulate(new RouteAFourConsumerCompletionHarness(p)) { d =>
        val rid = presence
        init(d); startAttention(d, rid)
        if ((presence & 1) != 0) activateHot(d, rid)
        if ((presence & 2) != 0) activatePending(d, rid)
        if ((presence & 4) != 0) activatePacked(d, rid)
        sendPlan(d, rid, presence)
        val presentKinds = (0 to 2).filter(kind => (presence & (1 << kind)) != 0)
        presentKinds.zipWithIndex.foreach { case (kind, ordinal) =>
          (0 until 4).foreach(sendPacket(d, rid, kind, _))
          d.clock.step(2)
          if (ordinal != presentKinds.size - 1) d.io.merge_req.valid.expect(false.B)
        }
        var waited = 0
        while (d.io.merge_req.valid.peek().litValue == 0 && waited < 8) { d.clock.step(); waited += 1 }
        d.io.merge_req.valid.expect(true.B); d.io.merge_req.bits.transaction_identity.request_id.expect(rid.U); d.io.merge_req.bits.source_presence.expect(presence.U)
        d.io.merge_req.ready.poke(true.B); d.clock.step(); d.io.merge_req.ready.poke(false.B); d.io.merge_req.valid.expect(false.B)
      }
    }
  }

  it("fails closed when R4 header kind and SourceInstance kind disagree") {
    simulate(new RouteASourceCommitDemultiplexerHarness(p)) { d =>
      d.io.commit_in.valid.poke(false.B)
      Seq(d.io.hot_commit, d.io.pending_commit, d.io.packed_commit).foreach(_.ready.poke(true.B))
      val c = d.io.commit_in.bits
      identity(c.transaction_identity, 6); c.consumer_id.poke(2.U); c.source_kind.poke(0.U); instance(c.source_instance, 1, 0, 1)
      d.io.commit_in.valid.poke(true.B); d.io.commit_in.ready.expect(false.B)
      d.io.hot_commit.valid.expect(false.B); d.io.pending_commit.valid.expect(false.B); d.io.packed_commit.valid.expect(false.B)
      instance(c.source_instance, 0, 10, 1)
      d.io.commit_in.ready.expect(true.B); d.io.hot_commit.valid.expect(true.B); d.io.pending_commit.valid.expect(false.B); d.io.packed_commit.valid.expect(false.B)
      d.io.hot_commit.bits.transaction_identity.request_id.expect(6.U); d.io.hot_commit.bits.source_instance.instance_coordinate.expect(10.U); d.io.hot_commit.bits.consumer_id.expect(2.U)
    }
  }
}
