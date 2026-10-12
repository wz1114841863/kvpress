package kvpress.routea.rtl3

import chisel3._
import chisel3.util.{Cat, DecoupledIO, UIntToOH}
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteAFunctionalPartialProviderBoundary, RouteAFunctionalR4ReferenceBoundary, RouteASourceServicePacketAdapter}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Test-only observer for the already frozen four-consumer completion rule.
  * It does not select a source or produce a packet: it emits a release only
  * after four exact commits for the one observed source instance.
  */
private final class RouteARTL385CommitReleaseObserver(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val commit_in = Flipped(RouteAChannels.consumer_partial_commit(p))
    val hot_release_out = RouteAChannels.source_release(p)
    val pending_release_out = RouteAChannels.source_release(p)
    val packed_release_out = RouteAChannels.source_release(p)
  })

  private def identityMatches(left: TransactionIdentity, right: TransactionIdentity): Bool = left.asUInt === right.asUInt
  val identityValid = RegInit(false.B)
  val identity = Reg(new TransactionIdentity)
  val seen = RegInit(VecInit(Seq.fill(3)(0.U(4.W))))
  val releasePending = RegInit(VecInit(Seq.fill(3)(false.B)))
  val instances = Reg(Vec(3, new SourceInstance(p)))
  val commit = io.commit_in.bits
  val kindLegal = commit.source_kind <= RouteASourceKind.Packed.U
  val consumerLegal = commit.consumer_id < 4.U
  val instanceMatchesKind = commit.source_kind === commit.source_instance.source_kind
  val identityCompatible = !identityValid || identityMatches(identity, commit.transaction_identity)
  val consumerBit = UIntToOH(commit.consumer_id, 4)
  val notDuplicate = consumerLegal && (seen(commit.source_kind) & consumerBit) === 0.U
  io.commit_in.ready := kindLegal && consumerLegal && instanceMatchesKind && identityCompatible &&
    !releasePending(commit.source_kind) && notDuplicate
  when(io.commit_in.fire) {
    when(!identityValid) { identityValid := true.B; identity := commit.transaction_identity }
    val next = seen(commit.source_kind) | consumerBit
    seen(commit.source_kind) := next
    instances(commit.source_kind) := commit.source_instance
    when(next === "b1111".U) { releasePending(commit.source_kind) := true.B }
  }

  private def driveRelease(out: DecoupledIO[SourceRelease], kind: Int): Unit = {
    out.valid := releasePending(kind)
    out.bits.transaction_identity := identity
    out.bits.source_instance := instances(kind)
    when(out.fire) { releasePending(kind) := false.B }
  }
  driveRelease(io.hot_release_out, RouteASourceKind.Hot)
  driveRelease(io.pending_release_out, RouteASourceKind.Pending)
  driveRelease(io.packed_release_out, RouteASourceKind.Packed)
}

/** Test-only dynamic response environment; it evaluates no numeric function. */
private final class RouteARTL385ReferenceEnvironment(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val accepted_packet_in = Flipped(RouteAChannels.r4_accepted_partial_packet(p))
    val merge_work_in = Flipped(RouteAChannels.merge_req)
    val packet_accept_enable = Input(Bool())
    val work_accept_enable = Input(Bool())
    val response_enable = Input(Bool())
    val numeric_fault = Input(Bool())
    val stale_response = Input(Bool())
    val result_out = RouteAChannels.r4_result_stub
    val fault_out = RouteAChannels.r4_numeric_fault
    val packets_seen = Output(UInt(6.W))
    val works_seen = Output(UInt(3.W))
  })

  val packetsSeen = RegInit(0.U(6.W))
  val worksSeen = RegInit(0.U(3.W))
  val responsePending = RegInit(false.B)
  val heldWork = Reg(new MergeRequest)
  val heldFault = RegInit(false.B)
  val heldStale = RegInit(false.B)
  io.accepted_packet_in.ready := io.packet_accept_enable
  when(io.accepted_packet_in.fire) { packetsSeen := packetsSeen + 1.U }
  io.merge_work_in.ready := io.work_accept_enable && !responsePending
  when(io.merge_work_in.fire) {
    heldWork := io.merge_work_in.bits
    heldFault := io.numeric_fault
    heldStale := io.stale_response
    responsePending := true.B
    worksSeen := worksSeen + 1.U
  }

  val responseIdentity = Wire(new TransactionIdentity)
  responseIdentity := heldWork.transaction_identity
  when(heldStale) { responseIdentity.request_id := heldWork.transaction_identity.request_id + 1.U }
  io.result_out.valid := responsePending && io.response_enable && !heldFault
  io.result_out.bits.transaction_identity := responseIdentity
  io.result_out.bits.consumer_id := heldWork.consumer_id
  // Opaque directed-test payload only; the RTL3.4-B Python oracle remains the
  // sole numerical evaluator and this fixture makes no numeric claim.
  io.result_out.bits.normalized_value := Cat(heldWork.consumer_id, heldWork.source_presence)
  io.fault_out.valid := responsePending && io.response_enable && heldFault
  io.fault_out.bits.transaction_identity := responseIdentity
  io.fault_out.bits.consumer_id := heldWork.consumer_id
  when(io.result_out.fire || io.fault_out.fire) { responsePending := false.B }
  assert(!(io.result_out.valid && io.fault_out.valid))
  io.packets_seen := packetsSeen
  io.works_seen := worksSeen
}

/** One functional-path composition used only by RTL3.8.5 directed coverage. */
private final class RouteARTL385FullPathHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val source_plan = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_available = Input(new SourceServiceAvailability(p))
    val pending_available = Input(new SourceServiceAvailability(p))
    val packed_available = Input(new SourceServiceAvailability(p))
    val hot_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val pending_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packed_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val hot_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val pending_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val packed_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val packet_accept_enable = Input(Bool())
    val work_accept_enable = Input(Bool())
    val response_enable = Input(Bool())
    val numeric_fault = Input(Bool())
    val stale_response = Input(Bool())
    val attention_terminal = RouteAChannels.attention_terminal_rsp
    val packets_seen = Output(UInt(6.W))
    val works_seen = Output(UInt(3.W))
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val provider = Module(new RouteAFunctionalPartialProviderBoundary(p))
  val packets = Module(new RouteASourceServicePacketAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))
  val reference = Module(new RouteAFunctionalR4ReferenceBoundary(p))
  val environment = Module(new RouteARTL385ReferenceEnvironment(p))
  val releases = Module(new RouteARTL385CommitReleaseObserver(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.status
  lifecycle.io.source_completion_plan_in <> io.source_plan
  packets.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
  packets.io.hot_available_in := io.hot_available
  packets.io.pending_available_in := io.pending_available
  packets.io.packed_available_in := io.packed_available
  provider.io.hot_offer_in <> io.hot_offer; provider.io.pending_offer_in <> io.pending_offer; provider.io.packed_offer_in <> io.packed_offer
  provider.io.hot_fragment_in <> io.hot_fragment; provider.io.pending_fragment_in <> io.pending_fragment; provider.io.packed_fragment_in <> io.packed_fragment
  packets.io.hot_offer_in <> provider.io.hot_offer_out; packets.io.pending_offer_in <> provider.io.pending_offer_out; packets.io.packed_offer_in <> provider.io.packed_offer_out
  packets.io.hot_fragment_in <> provider.io.hot_fragment_out; packets.io.pending_fragment_in <> provider.io.pending_fragment_out; packets.io.packed_fragment_in <> provider.io.packed_fragment_out

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> packets.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packets.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packets.io.r4_value_fragment_out
  reference.io.accepted_packet_in <> merge.io.r4_accepted_partial_packet_out
  reference.io.active_merge_observation_in := merge.io.r4_active_merge_observation
  environment.io.accepted_packet_in <> reference.io.accepted_packet_out
  environment.io.merge_work_in <> reference.io.merge_work_out
  reference.io.functional_result_in <> environment.io.result_out
  reference.io.functional_numeric_fault_in <> environment.io.fault_out
  merge.io.r4_result_stub_in <> reference.io.r4_result_stub_out
  merge.io.r4_numeric_fault_in <> reference.io.r4_numeric_fault_out
  environment.io.packet_accept_enable := io.packet_accept_enable
  environment.io.work_accept_enable := io.work_accept_enable
  environment.io.response_enable := io.response_enable
  environment.io.numeric_fault := io.numeric_fault
  environment.io.stale_response := io.stale_response
  io.packets_seen := environment.io.packets_seen
  io.works_seen := environment.io.works_seen

  releases.io.commit_in <> merge.io.consumer_partial_commit
  lifecycle.io.hot_source_release_in <> releases.io.hot_release_out
  lifecycle.io.pending_source_release_in <> releases.io.pending_release_out
  lifecycle.io.packed_source_release_in <> releases.io.packed_release_out
  merge.io.merge_req_in <> lifecycle.io.merge_req
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  io.attention_terminal <> lifecycle.io.attention_terminal_rsp

  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B
  StructuralTieOff.sink(merge.io.component_status_out)
}

/** RTL3.8.5 full-path coverage; it remains a no-model functional protocol test. */
final class RouteARTL385FullPathClosureSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2, r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2, coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def instance(i: SourceInstance, kind: Int): Unit = { i.source_kind.poke(kind.U); i.instance_coordinate.poke((10 + kind).U); i.generation.poke(1.U) }
  private def header(kind: Int, consumer: Int): BigInt = (BigInt(kind) << 64) | (BigInt(consumer) << 66) | (BigInt(1) << 69) | (BigInt(8) << 70)

  private def init(d: RouteARTL385FullPathHarness): Unit = {
    d.io.frontend.valid.poke(false.B); d.io.status.valid.poke(false.B); d.io.source_plan.valid.poke(false.B)
    Seq(d.io.hot_offer, d.io.pending_offer, d.io.packed_offer, d.io.hot_fragment, d.io.pending_fragment, d.io.packed_fragment).foreach(_.valid.poke(false.B))
    d.io.packet_accept_enable.poke(true.B); d.io.work_accept_enable.poke(true.B); d.io.response_enable.poke(true.B); d.io.numeric_fault.poke(false.B); d.io.stale_response.poke(false.B)
    d.io.attention_terminal.ready.poke(true.B)
    d.io.status.bits.asserted.poke(false.B)
    Seq(d.io.hot_available, d.io.pending_available, d.io.packed_available).zipWithIndex.foreach { case (a, kind) =>
      a.valid.poke(false.B); a.transaction_identity.request_id.poke(0.U); a.transaction_identity.incarnation.poke(0.U); instance(a.source_instance, kind)
    }
  }
  private def status(d: RouteARTL385FullPathHarness, code: Int): Unit = {
    d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B); d.io.status.valid.poke(true.B); d.io.status.ready.expect(true.B); d.clock.step(); d.io.status.valid.poke(false.B)
  }
  private def frontend(d: RouteARTL385FullPathHarness, event: Int, rid: Int): Unit = {
    val f = d.io.frontend.bits
    f.event_kind.poke(event.U); f.session_id.poke(false.B); f.context_tokens.poke(32768.U); f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U); f.payload_ref.poke(0.U); f.disposition.poke(false.B)
    f.transaction_identity.request_id.poke(rid.U); f.transaction_identity.incarnation.poke(0.U); f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    d.io.frontend.valid.poke(true.B); d.io.frontend.ready.expect(true.B); d.clock.step(); d.io.frontend.valid.poke(false.B)
  }
  private def availability(d: RouteARTL385FullPathHarness, rid: Int, mask: Int): Unit =
    Seq(d.io.hot_available, d.io.pending_available, d.io.packed_available).zipWithIndex.foreach { case (a, kind) =>
      a.valid.poke(((mask & (1 << kind)) != 0).B); a.transaction_identity.request_id.poke(rid.U); a.transaction_identity.incarnation.poke(0.U); instance(a.source_instance, kind)
    }
  private def plan(d: RouteARTL385FullPathHarness, rid: Int, mask: Int): Unit = {
    val q = d.io.source_plan.bits; q.transaction_identity.request_id.poke(rid.U); q.transaction_identity.incarnation.poke(0.U); q.source_presence.poke(mask.U)
    instance(q.hot_instance, 0); instance(q.pending_instance, 1); instance(q.packed_instance, 2)
    d.io.source_plan.valid.poke(true.B); d.io.source_plan.ready.expect(true.B); d.clock.step(); d.io.source_plan.valid.poke(false.B); d.clock.step()
  }
  private def offer(d: RouteARTL385FullPathHarness, kind: Int) = Seq(d.io.hot_offer, d.io.pending_offer, d.io.packed_offer)(kind)
  private def fragment(d: RouteARTL385FullPathHarness, kind: Int) = Seq(d.io.hot_fragment, d.io.pending_fragment, d.io.packed_fragment)(kind)
  private def packet(d: RouteARTL385FullPathHarness, rid: Int, kind: Int, consumer: Int): Unit = {
    val o = offer(d, kind); o.bits.transaction_identity.request_id.poke(rid.U); o.bits.transaction_identity.incarnation.poke(0.U); instance(o.bits.source_instance, kind); o.bits.consumer_id.poke(consumer.U); o.bits.r4_header.poke(header(kind, consumer).U); o.bits.partial_present.poke(true.B)
    o.valid.poke(true.B); o.ready.expect(true.B); d.clock.step(); o.valid.poke(false.B); d.clock.step()
    (0 until 8).foreach { index =>
      val f = fragment(d, kind); f.bits.transaction_identity.request_id.poke(rid.U); f.bits.transaction_identity.incarnation.poke(0.U); instance(f.bits.source_instance, kind); f.bits.consumer_id.poke(consumer.U); f.bits.fragment_index.poke(index.U); f.bits.last.poke((index == 7).B); f.bits.data.poke((kind * 0x100 + consumer * 8 + index).U)
      f.valid.poke(true.B); f.ready.expect(true.B); d.clock.step(); f.valid.poke(false.B)
    }
  }
  private def boot(d: RouteARTL385FullPathHarness): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(d, _)); frontend(d, p.r6.sessionStartEventCode, 0)
  }
  private def completeSuccess(d: RouteARTL385FullPathHarness, rid: Int, mask: Int): Unit = {
    frontend(d, p.r6.attentionServiceEventCode, rid); availability(d, rid, mask); plan(d, rid, mask)
    for (kind <- 0 to 2 if (mask & (1 << kind)) != 0; consumer <- 0 until 4) packet(d, rid, kind, consumer)
    var limit = 80
    while (!d.io.attention_terminal.valid.peek().litToBoolean && limit > 0) { d.clock.step(); limit -= 1 }
    d.io.works_seen.expect(4.U)
    d.io.attention_terminal.valid.expect(true.B); d.io.attention_terminal.bits.transaction_identity.request_id.expect(rid.U); d.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U); d.clock.step()
  }

  it("covers all seven nonempty source subsets and four dynamic R4 consumer completions in one elaborated harness") {
    simulate(new RouteARTL385FullPathHarness(p)) { d =>
      init(d)
      for (mask <- 1 to 7) {
        boot(d)
        completeSuccess(d, rid = mask, mask)
        d.io.works_seen.expect(4.U)
        d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B)
        init(d)
      }
    }
  }

  it("preserves packet/work ready-low, maps a dynamic fault, and fail-closes a stale response until reset") {
    simulate(new RouteARTL385FullPathHarness(p)) { d =>
      init(d); boot(d); frontend(d, p.r6.attentionServiceEventCode, 1); availability(d, 1, 1); plan(d, 1, 1)
      d.io.packet_accept_enable.poke(false.B)
      packet(d, 1, RouteASourceKind.Hot, 0)
      d.io.packets_seen.expect(0.U)
      d.io.packet_accept_enable.poke(true.B); d.clock.step(); d.io.packets_seen.expect(1.U)
      for (consumer <- 1 until 4) packet(d, 1, RouteASourceKind.Hot, consumer)
      d.io.work_accept_enable.poke(false.B); d.clock.step(); d.io.works_seen.expect(0.U)
      d.io.work_accept_enable.poke(true.B); d.io.numeric_fault.poke(true.B)
      var limit = 40; while (!d.io.attention_terminal.valid.peek().litToBoolean && limit > 0) { d.clock.step(); limit -= 1 }
      d.io.attention_terminal.valid.expect(true.B); d.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U); d.clock.step()

      d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B); init(d); boot(d); frontend(d, p.r6.attentionServiceEventCode, 2); availability(d, 2, 1); plan(d, 2, 1)
      for (consumer <- 0 until 4) packet(d, 2, RouteASourceKind.Hot, consumer)
      d.io.stale_response.poke(true.B)
      (0 until 8).foreach(_ => d.clock.step())
      d.io.attention_terminal.valid.expect(false.B)
      d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B); init(d)
      d.io.attention_terminal.valid.expect(false.B)
    }
  }
}
