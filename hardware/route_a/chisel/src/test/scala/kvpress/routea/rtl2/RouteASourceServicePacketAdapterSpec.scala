package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteASourceServicePacketAdapter
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** C5 protocol harness: R6-accepted plan copy -> packet adapter -> frozen R4 parser. */
final class RouteASourceServicePacketAdapterHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val plan = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_available = Input(new SourceServiceAvailability(p))
    val pending_available = Input(new SourceServiceAvailability(p))
    val packed_available = Input(new SourceServiceAvailability(p))
    val hot_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val pending_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packed_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val hot_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val pending_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val packed_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val commit = RouteAChannels.consumer_partial_commit(p)
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val adapter = Module(new RouteASourceServicePacketAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.status
  lifecycle.io.source_completion_plan_in <> io.plan
  adapter.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
  adapter.io.hot_available_in := io.hot_available
  adapter.io.pending_available_in := io.pending_available
  adapter.io.packed_available_in := io.packed_available
  adapter.io.hot_offer_in <> io.hot_offer
  adapter.io.pending_offer_in <> io.pending_offer
  adapter.io.packed_offer_in <> io.packed_offer
  adapter.io.hot_fragment_in <> io.hot_fragment
  adapter.io.pending_fragment_in <> io.pending_fragment
  adapter.io.packed_fragment_in <> io.packed_fragment

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> adapter.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> adapter.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> adapter.io.r4_value_fragment_out
  StructuralTieOff.source(merge.io.r4_result_stub_in)
  StructuralTieOff.source(merge.io.r4_numeric_fault_in)
  io.commit <> merge.io.consumer_partial_commit
  merge.io.merge_req_in <> lifecycle.io.merge_req
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault

  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.attention_terminal_rsp)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  StructuralTieOff.source(lifecycle.io.packed_source_release_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B
  StructuralTieOff.sink(merge.io.component_status_out)
}

final class RouteASourceServicePacketAdapterSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def driveInstance(instance: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = {
    instance.source_kind.poke(kind.U); instance.instance_coordinate.poke(coordinate.U); instance.generation.poke(generation.U)
  }

  private def init(d: RouteASourceServicePacketAdapterHarness): Unit = {
    d.io.frontend.valid.poke(false.B); d.io.status.valid.poke(false.B); d.io.plan.valid.poke(false.B); d.io.commit.ready.poke(false.B)
    Seq(d.io.hot_offer, d.io.pending_offer, d.io.packed_offer).foreach(_.valid.poke(false.B))
    Seq(d.io.hot_fragment, d.io.pending_fragment, d.io.packed_fragment).foreach(_.valid.poke(false.B))
    Seq(d.io.hot_available, d.io.pending_available, d.io.packed_available).zipWithIndex.foreach { case (a, kind) =>
      a.valid.poke(false.B); a.transaction_identity.request_id.poke(0.U); a.transaction_identity.incarnation.poke(0.U); driveInstance(a.source_instance, kind, kind, 1)
    }
  }

  private def status(d: RouteASourceServicePacketAdapterHarness, code: Int): Unit = {
    d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B); d.io.status.valid.poke(true.B)
    d.io.status.ready.expect(true.B); d.clock.step(); d.io.status.valid.poke(false.B)
  }

  private def frontend(d: RouteASourceServicePacketAdapterHarness, event: Int, rid: Int, presence: Int): Unit = {
    val f = d.io.frontend.bits
    f.event_kind.poke(event.U); f.session_id.poke(false.B); f.context_tokens.poke(32768.U); f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U)
    f.logical_position.poke(0.U); f.payload_ref.poke(0.U); f.disposition.poke(false.B); f.transaction_identity.request_id.poke(rid.U); f.transaction_identity.incarnation.poke(0.U)
    // Source presence belongs exclusively to the subsequently accepted R6
    // SourceCompletionPlan; a frontend attention request must not select it.
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    d.io.frontend.valid.poke(true.B); d.io.frontend.ready.expect(true.B); d.clock.step(); d.io.frontend.valid.poke(false.B)
  }

  private def setAvailability(d: RouteASourceServicePacketAdapterHarness, rid: Int, valid: Boolean = true): Unit = {
    Seq(d.io.hot_available, d.io.pending_available, d.io.packed_available).zipWithIndex.foreach { case (a, kind) =>
      a.valid.poke(valid.B); a.transaction_identity.request_id.poke(rid.U); a.transaction_identity.incarnation.poke(0.U); driveInstance(a.source_instance, kind, 10 + kind, 1)
    }
  }

  private def sendPlan(d: RouteASourceServicePacketAdapterHarness, rid: Int, presence: Int): Unit = {
    val plan = d.io.plan.bits
    plan.transaction_identity.request_id.poke(rid.U); plan.transaction_identity.incarnation.poke(0.U); plan.source_presence.poke(presence.U)
    driveInstance(plan.hot_instance, 0, 10, 1); driveInstance(plan.pending_instance, 1, 11, 1); driveInstance(plan.packed_instance, 2, 12, 1)
    d.io.plan.valid.poke(true.B); d.io.plan.ready.expect(true.B); d.clock.step(); d.io.plan.valid.poke(false.B); d.clock.step()
  }

  private def header(kind: Int, consumer: Int): BigInt = (BigInt(kind) << 64) | (BigInt(consumer) << 66) | (BigInt(1) << 69) | (BigInt(8) << 70)

  private def offerChannel(d: RouteASourceServicePacketAdapterHarness, kind: Int) = kind match {
    case 0 => d.io.hot_offer
    case 1 => d.io.pending_offer
    case _ => d.io.packed_offer
  }
  private def fragmentChannel(d: RouteASourceServicePacketAdapterHarness, kind: Int) = kind match {
    case 0 => d.io.hot_fragment
    case 1 => d.io.pending_fragment
    case _ => d.io.packed_fragment
  }

  private def sendPacket(d: RouteASourceServicePacketAdapterHarness, rid: Int, kind: Int, consumer: Int, acceptCommit: Boolean = true): Unit = {
    val offer = offerChannel(d, kind)
    offer.bits.transaction_identity.request_id.poke(rid.U); offer.bits.transaction_identity.incarnation.poke(0.U); driveInstance(offer.bits.source_instance, kind, 10 + kind, 1)
    offer.bits.consumer_id.poke(consumer.U); offer.bits.r4_header.poke(header(kind, consumer).U); offer.bits.partial_present.poke(true.B)
    offer.valid.poke(true.B); offer.ready.expect(true.B); d.clock.step(); offer.valid.poke(false.B)
    // The adapter must complete the coupled R4 header/sideband handshake
    // before it can accept the first value fragment.
    d.clock.step()
    (0 until 8).foreach { index =>
      val fragment = fragmentChannel(d, kind)
      fragment.bits.transaction_identity.request_id.poke(rid.U); fragment.bits.transaction_identity.incarnation.poke(0.U); driveInstance(fragment.bits.source_instance, kind, 10 + kind, 1)
      fragment.bits.consumer_id.poke(consumer.U); fragment.bits.fragment_index.poke(index.U); fragment.bits.last.poke((index == 7).B); fragment.bits.data.poke((kind * 0x100 + consumer * 8 + index).U)
      fragment.valid.poke(true.B); fragment.ready.expect(true.B); d.clock.step(); fragment.valid.poke(false.B)
    }
    d.io.commit.valid.expect(true.B); d.io.commit.bits.transaction_identity.request_id.expect(rid.U); d.io.commit.bits.source_kind.expect(kind.U); d.io.commit.bits.consumer_id.expect(consumer.U)
    if (acceptCommit) {
      d.io.commit.ready.poke(true.B); d.clock.step(); d.io.commit.ready.poke(false.B)
    }
  }

  it("forwards every present source/consumer packet in canonical order for all seven nonempty masks") {
    // Each mask is an independent attention transaction. The harness does not
    // drive R4 terminal completion, so retaining them in one instance would
    // deliberately exhaust R6's four live-attention tracker entries.
    for (presence <- 1 to 7) {
      simulate(new RouteASourceServicePacketAdapterHarness(p)) { d =>
        init(d)
        Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(d, _))
        frontend(d, p.r6.sessionStartEventCode, 0, 0)
        frontend(d, p.r6.attentionServiceEventCode, presence, presence); setAvailability(d, presence); sendPlan(d, presence, presence)
        for (kind <- 0 to 2 if (presence & (1 << kind)) != 0; consumer <- 0 until 4) sendPacket(d, presence, kind, consumer)
      }
    }
  }

  it("rejects stale availability, malformed header, and duplicate consumer without R4 commit") {
    simulate(new RouteASourceServicePacketAdapterHarness(p)) { d =>
      init(d)
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(d, _))
      frontend(d, p.r6.sessionStartEventCode, 0, 0); frontend(d, p.r6.attentionServiceEventCode, 4, 1); sendPlan(d, 4, 1)
      setAvailability(d, 4, valid = false)
      val hot = d.io.hot_offer
      hot.bits.transaction_identity.request_id.poke(4.U); hot.bits.transaction_identity.incarnation.poke(0.U); driveInstance(hot.bits.source_instance, 0, 10, 1)
      hot.bits.consumer_id.poke(0.U); hot.bits.r4_header.poke(header(0, 0).U); hot.bits.partial_present.poke(true.B); hot.valid.poke(true.B); hot.ready.expect(false.B); hot.valid.poke(false.B)
      setAvailability(d, 4)
      hot.bits.r4_header.poke(header(1, 0).U); hot.valid.poke(true.B); hot.ready.expect(false.B); hot.valid.poke(false.B)
      sendPacket(d, 4, 0, 0)
      hot.bits.r4_header.poke(header(0, 0).U); hot.valid.poke(true.B); hot.ready.expect(false.B); hot.valid.poke(false.B); d.io.commit.valid.expect(false.B)
    }
  }

  it("holds the next packet at R4 ingress until a stalled prior consumer commit is accepted") {
    simulate(new RouteASourceServicePacketAdapterHarness(p)) { d =>
      init(d)
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(d, _))
      frontend(d, p.r6.sessionStartEventCode, 0, 0); frontend(d, p.r6.attentionServiceEventCode, 5, 1)
      setAvailability(d, 5); sendPlan(d, 5, 1)
      sendPacket(d, 5, 0, 0, acceptCommit = false)

      val hot = d.io.hot_offer
      hot.bits.transaction_identity.request_id.poke(5.U); hot.bits.transaction_identity.incarnation.poke(0.U); driveInstance(hot.bits.source_instance, 0, 10, 1)
      hot.bits.consumer_id.poke(1.U); hot.bits.r4_header.poke(header(0, 1).U); hot.bits.partial_present.poke(true.B)
      hot.valid.poke(true.B); hot.ready.expect(true.B); d.clock.step(); hot.valid.poke(false.B)
      // R4 is still holding commit(consumer 0), so the adapter must retain the
      // coupled header/sideband for consumer 1 and cannot accept a fragment.
      d.clock.step(); hot.ready.expect(false.B)
      d.io.hot_fragment.ready.expect(false.B)

      d.io.commit.ready.poke(true.B); d.clock.step(); d.io.commit.ready.poke(false.B)
      d.clock.step()
      // First R4 clears the held commit, then it accepts the coupled next
      // header/sideband; the following cycle enables the first fragment.
      d.clock.step()
      val fragment = d.io.hot_fragment
      fragment.bits.transaction_identity.request_id.poke(5.U); fragment.bits.transaction_identity.incarnation.poke(0.U)
      driveInstance(fragment.bits.source_instance, 0, 10, 1); fragment.bits.consumer_id.poke(1.U)
      fragment.bits.fragment_index.poke(0.U); fragment.bits.last.poke(false.B); fragment.bits.data.poke(0.U)
      fragment.valid.poke(true.B)
      d.io.hot_fragment.ready.expect(true.B)
      fragment.valid.poke(false.B)
    }
  }
}
