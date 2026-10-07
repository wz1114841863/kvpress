package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Decoupled
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.4.2 test-only cross-owner harness. `merge_ready` is an explicit
  * already-completed source-set event; this harness does not implement or
  * select source scheduling, packet production, or numeric arithmetic.
  */
final class RouteAR4R6StubTerminalHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val merge_ready = Flipped(RouteAChannels.r6_merge_ready)
    val scenario = Flipped(Decoupled(new R4StubScenario))
    val attention_terminal = RouteAChannels.attention_terminal_rsp
    val attention_terminal_scoreboard_event = Decoupled(new AttentionTerminalScoreboardEvent)
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))
  val provider = Module(new RouteAR4ResultStubProvider)
  val terminalScoreboard = Module(new RouteAAttentionTerminalScoreboardAdapter)

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.status
  lifecycle.io.merge_ready_in <> io.merge_ready
  terminalScoreboard.io.attention_terminal_in <> lifecycle.io.attention_terminal_rsp
  io.attention_terminal <> terminalScoreboard.io.attention_terminal_out
  io.attention_terminal_scoreboard_event <> terminalScoreboard.io.scoreboard_event_out
  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  lifecycle.io.hot_control_out.ready := true.B
  lifecycle.io.authority_transition_out.ready := true.B
  lifecycle.io.admission_context_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.source_completion_plan_in)
  lifecycle.io.source_completion_plan_copy_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  StructuralTieOff.source(lifecycle.io.packed_source_release_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  StructuralTieOff.source(merge.io.r4_partial_header_in)
  StructuralTieOff.source(merge.io.r4_source_instance_in)
  StructuralTieOff.source(merge.io.r4_value_fragment_in)
  StructuralTieOff.sink(merge.io.consumer_partial_commit)
  StructuralTieOff.sink(merge.io.component_status_out)
  merge.io.merge_req_in <> lifecycle.io.merge_req
  provider.io.active_merge_observation := merge.io.r4_active_merge_observation
  provider.io.scenario_in <> io.scenario
  merge.io.r4_result_stub_in <> provider.io.r4_result_stub_out
  merge.io.r4_numeric_fault_in <> provider.io.r4_numeric_fault_out
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
}

/**
  * RTL2.4.2 is an R4-to-R6 terminal-chain check only. It neither proves R4
  * numerical semantics nor converts the explicit test scenario into a source
  * scheduler, top-level endpoint, or production terminal provider.
  */
final class RouteAR4R6StubTerminalIntegrationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def identity(port: TransactionIdentity, rid: Int, incarnation: Int): Unit = {
    port.request_id.poke(rid.U); port.incarnation.poke(incarnation.U)
  }

  private def init(dut: RouteAR4R6StubTerminalHarness): Unit = {
    dut.io.frontend.valid.poke(false.B); dut.io.status.valid.poke(false.B)
    dut.io.merge_ready.valid.poke(false.B); dut.io.scenario.valid.poke(false.B)
    dut.io.attention_terminal.ready.poke(false.B)
    dut.io.attention_terminal_scoreboard_event.ready.poke(true.B)
    dut.io.status.bits.asserted.poke(false.B)
    identity(dut.io.merge_ready.bits.transaction_identity, 0, 0); dut.io.merge_ready.bits.source_presence.poke(0.U)
    identity(dut.io.scenario.bits.transaction_identity, 0, 0)
    dut.io.scenario.bits.disposition.poke(RouteAR4StubScenarioDisposition.Success.U)
    dut.io.scenario.bits.normalized_value.poke(0.U)
  }

  private def status(dut: RouteAR4R6StubTerminalHarness, code: Int): Unit = {
    dut.io.status.bits.acknowledgement_name.poke(code.U); dut.io.status.bits.asserted.poke(true.B)
    dut.io.status.valid.poke(true.B); dut.io.status.ready.expect(true.B)
    dut.clock.step(); dut.io.status.valid.poke(false.B)
  }

  private def frontend(dut: RouteAR4R6StubTerminalHarness, event: Int, rid: Int, incarnation: Int): Unit = {
    val f = dut.io.frontend.bits
    f.event_kind.poke(event.U); f.session_id.poke(false.B); f.context_tokens.poke(32768.U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(0.U); f.disposition.poke(false.B); identity(f.transaction_identity, rid, incarnation)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    dut.io.frontend.valid.poke(true.B); dut.io.frontend.ready.expect(true.B)
    dut.clock.step(); dut.io.frontend.valid.poke(false.B)
  }

  private def startSession(dut: RouteAR4R6StubTerminalHarness): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(dut, _))
    frontend(dut, p.r6.sessionStartEventCode, rid = 0, incarnation = 0)
  }

  private def issueMerge(dut: RouteAR4R6StubTerminalHarness, rid: Int, incarnation: Int, presence: Int): Unit = {
    frontend(dut, p.r6.attentionServiceEventCode, rid, incarnation)
    identity(dut.io.merge_ready.bits.transaction_identity, rid, incarnation)
    dut.io.merge_ready.bits.source_presence.poke(presence.U)
    dut.io.merge_ready.valid.poke(true.B); dut.io.merge_ready.ready.expect(true.B)
    dut.clock.step(); dut.io.merge_ready.valid.poke(false.B)
    // R6's held request is accepted by the real R4 boundary on this edge.
    dut.clock.step()
  }

  private def offerScenario(dut: RouteAR4R6StubTerminalHarness, rid: Int, incarnation: Int, disposition: Int, value: BigInt): Unit = {
    identity(dut.io.scenario.bits.transaction_identity, rid, incarnation)
    dut.io.scenario.bits.disposition.poke(disposition.U); dut.io.scenario.bits.normalized_value.poke(value.U)
    dut.io.scenario.valid.poke(true.B); dut.io.scenario.ready.expect(true.B)
    dut.clock.step(); dut.io.scenario.valid.poke(false.B)
    // provider -> R4 terminal, then R4 -> R6 terminal
    dut.clock.step(2)
  }

  it("routes one matching success through R4 and R6, withholding the event until the atomic terminal handoff") {
    simulate(new RouteAR4R6StubTerminalHarness(p)) { dut =>
      init(dut); startSession(dut); issueMerge(dut, rid = 1, incarnation = 1, presence = 3)
      offerScenario(dut, rid = 1, incarnation = 1, RouteAR4StubScenarioDisposition.Success, BigInt("1234", 16))
      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal.bits.transaction_identity.request_id.expect(1.U)
      dut.io.attention_terminal.bits.transaction_identity.incarnation.expect(1.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
      dut.io.attention_terminal_scoreboard_event.valid.expect(false.B)
      dut.clock.step()
      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal.ready.poke(true.B)
      dut.io.attention_terminal_scoreboard_event.valid.expect(true.B)
      dut.io.attention_terminal_scoreboard_event.bits.transaction_identity.request_id.expect(1.U)
      dut.io.attention_terminal_scoreboard_event.bits.transaction_identity.incarnation.expect(1.U)
      dut.io.attention_terminal_scoreboard_event.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
      dut.clock.step(); dut.io.attention_terminal.ready.poke(false.B)
      dut.io.attention_terminal.valid.expect(false.B)
    }
  }

  it("routes one matching numeric fault and rejects a stale scenario without an outward terminal") {
    simulate(new RouteAR4R6StubTerminalHarness(p)) { dut =>
      init(dut); startSession(dut); issueMerge(dut, rid = 2, incarnation = 0, presence = 5)
      identity(dut.io.scenario.bits.transaction_identity, 3, 0)
      dut.io.scenario.bits.disposition.poke(RouteAR4StubScenarioDisposition.NumericFault.U)
      dut.io.scenario.bits.normalized_value.poke(0.U); dut.io.scenario.valid.poke(true.B)
      dut.io.scenario.ready.expect(false.B); dut.io.scenario.valid.poke(false.B)
      dut.io.attention_terminal.valid.expect(false.B)
      offerScenario(dut, rid = 2, incarnation = 0, RouteAR4StubScenarioDisposition.NumericFault, BigInt(0))
      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal.bits.transaction_identity.request_id.expect(2.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      dut.io.attention_terminal_scoreboard_event.valid.expect(false.B)
      dut.io.attention_terminal.ready.poke(true.B)
      dut.io.attention_terminal_scoreboard_event.valid.expect(true.B)
      dut.io.attention_terminal_scoreboard_event.bits.transaction_identity.request_id.expect(2.U)
      dut.io.attention_terminal_scoreboard_event.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      dut.clock.step(); dut.io.attention_terminal.ready.poke(false.B)
    }
  }

  it("destructive reset removes an accepted scenario before it can become an R6 outward terminal") {
    simulate(new RouteAR4R6StubTerminalHarness(p)) { dut =>
      init(dut); startSession(dut); issueMerge(dut, rid = 4, incarnation = 1, presence = 1)
      identity(dut.io.scenario.bits.transaction_identity, 4, 1)
      dut.io.scenario.bits.disposition.poke(RouteAR4StubScenarioDisposition.Success.U)
      dut.io.scenario.bits.normalized_value.poke(BigInt("55", 16).U)
      dut.io.scenario.valid.poke(true.B); dut.io.scenario.ready.expect(true.B)
      dut.clock.step(); dut.io.scenario.valid.poke(false.B)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.attention_terminal.valid.expect(false.B)
      dut.io.scenario.ready.expect(false.B)
    }
  }
}
