package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces.TransactionIdentity
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.5.2 directed cross-owner fault closure.  This reuses the RTL2.4.2
  * test-only R4--R6 harness: it does not add a retry, fallback, source, or
  * production-top carrier.
  */
final class RouteAFaultTerminalClosureSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def identity(port: TransactionIdentity, rid: Int, incarnation: Int): Unit = {
    port.request_id.poke(rid.U)
    port.incarnation.poke(incarnation.U)
  }

  private def init(dut: RouteAR4R6StubTerminalHarness): Unit = {
    dut.io.frontend.valid.poke(false.B)
    dut.io.status.valid.poke(false.B)
    dut.io.merge_ready.valid.poke(false.B)
    dut.io.scenario.valid.poke(false.B)
    dut.io.attention_terminal.ready.poke(false.B)
    dut.io.attention_terminal_scoreboard_event.ready.poke(false.B)
    dut.io.status.bits.asserted.poke(false.B)
    identity(dut.io.merge_ready.bits.transaction_identity, 0, 0)
    dut.io.merge_ready.bits.source_presence.poke(0.U)
    driveScenario(dut, 0, 0, RouteAR4StubScenarioDisposition.Success, BigInt(0))
  }

  private def driveScenario(
    dut: RouteAR4R6StubTerminalHarness,
    rid: Int,
    incarnation: Int,
    disposition: Int,
    value: BigInt,
  ): Unit = {
    identity(dut.io.scenario.bits.transaction_identity, rid, incarnation)
    dut.io.scenario.bits.disposition.poke(disposition.U)
    dut.io.scenario.bits.normalized_value.poke(value.U)
  }

  private def status(dut: RouteAR4R6StubTerminalHarness, code: Int): Unit = {
    dut.io.status.bits.acknowledgement_name.poke(code.U)
    dut.io.status.bits.asserted.poke(true.B)
    dut.io.status.valid.poke(true.B)
    dut.io.status.ready.expect(true.B)
    dut.clock.step()
    dut.io.status.valid.poke(false.B)
  }

  private def startSession(dut: RouteAR4R6StubTerminalHarness): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode)
      .foreach(status(dut, _))
    val f = dut.io.frontend.bits
    f.event_kind.poke(p.r6.sessionStartEventCode.U)
    f.session_id.poke(false.B)
    f.context_tokens.poke(32768.U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(0.U); f.disposition.poke(false.B)
    identity(f.transaction_identity, 0, 0)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    dut.io.frontend.valid.poke(true.B)
    dut.io.frontend.ready.expect(true.B)
    dut.clock.step()
    dut.io.frontend.valid.poke(false.B)
  }

  private def issueMerge(dut: RouteAR4R6StubTerminalHarness, rid: Int, incarnation: Int): Unit = {
    val f = dut.io.frontend.bits
    f.event_kind.poke(p.r6.attentionServiceEventCode.U)
    f.session_id.poke(false.B); f.context_tokens.poke(32768.U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(0.U); f.disposition.poke(false.B)
    identity(f.transaction_identity, rid, incarnation)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(1.U)
    dut.io.frontend.valid.poke(true.B)
    dut.io.frontend.ready.expect(true.B)
    dut.clock.step()
    dut.io.frontend.valid.poke(false.B)

    identity(dut.io.merge_ready.bits.transaction_identity, rid, incarnation)
    dut.io.merge_ready.bits.source_presence.poke(7.U)
    dut.io.merge_ready.valid.poke(true.B)
    dut.io.merge_ready.ready.expect(true.B)
    dut.clock.step()
    dut.io.merge_ready.valid.poke(false.B)
    // R6's held merge request is accepted by the real R4 boundary.
    dut.clock.step()
  }

  private def offerFault(dut: RouteAR4R6StubTerminalHarness, rid: Int, incarnation: Int): Unit = {
    driveScenario(dut, rid, incarnation, RouteAR4StubScenarioDisposition.NumericFault, BigInt(0))
    dut.io.scenario.valid.poke(true.B)
    dut.io.scenario.ready.expect(true.B)
    dut.clock.step()
    dut.io.scenario.valid.poke(false.B)
    // provider -> R4 terminal, then R4 -> R6 outward terminal.
    dut.clock.step(2)
  }

  it("emits one atomic fault terminal under backpressure and refuses replay without a new request") {
    simulate(new RouteAR4R6StubTerminalHarness(p)) { dut =>
      init(dut)
      startSession(dut)
      issueMerge(dut, rid = 5, incarnation = 1)
      offerFault(dut, rid = 5, incarnation = 1)

      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal.bits.transaction_identity.request_id.expect(5.U)
      dut.io.attention_terminal.bits.transaction_identity.incarnation.expect(1.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      dut.io.attention_terminal_scoreboard_event.valid.expect(true.B)
      dut.io.attention_terminal_scoreboard_event.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      dut.clock.step(2)
      dut.io.attention_terminal.bits.transaction_identity.request_id.expect(5.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)

      dut.io.attention_terminal.ready.poke(true.B)
      dut.io.attention_terminal_scoreboard_event.ready.poke(true.B)
      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal_scoreboard_event.valid.expect(true.B)
      dut.clock.step()
      dut.io.attention_terminal.ready.poke(false.B)
      dut.io.attention_terminal_scoreboard_event.ready.poke(false.B)
      dut.io.attention_terminal.valid.expect(false.B)
      dut.io.attention_terminal_scoreboard_event.valid.expect(false.B)

      // The terminal closed this live incarnation.  Replaying its scenario is
      // neither a retry path nor a second terminal; no Full-KV carrier exists
      // in this test-only R4--R6 interface.
      driveScenario(dut, 5, 1, RouteAR4StubScenarioDisposition.NumericFault, BigInt(0))
      dut.io.scenario.valid.poke(true.B)
      dut.io.scenario.ready.expect(false.B)
      dut.clock.step(2)
      dut.io.scenario.valid.poke(false.B)
      dut.io.attention_terminal.valid.expect(false.B)
      dut.io.attention_terminal_scoreboard_event.valid.expect(false.B)
    }
  }

  it("fails closed for mismatched or malformed fault scenarios before the unique matching terminal") {
    simulate(new RouteAR4R6StubTerminalHarness(p)) { dut =>
      init(dut)
      startSession(dut)
      issueMerge(dut, rid = 6, incarnation = 2)

      Seq(
        (7, 2, BigInt(0)), // wrong request id
        (6, 1, BigInt(0)), // wrong incarnation
        (6, 2, BigInt(1)), // numeric-fault payload must be zero
      ).foreach { case (rid, incarnation, value) =>
        driveScenario(dut, rid, incarnation, RouteAR4StubScenarioDisposition.NumericFault, value)
        dut.io.scenario.valid.poke(true.B)
        dut.io.scenario.ready.expect(false.B)
        dut.clock.step()
        dut.io.scenario.valid.poke(false.B)
        dut.io.attention_terminal.valid.expect(false.B)
        dut.io.attention_terminal_scoreboard_event.valid.expect(false.B)
      }

      offerFault(dut, rid = 6, incarnation = 2)
      dut.io.attention_terminal.valid.expect(true.B)
      dut.io.attention_terminal.bits.transaction_identity.request_id.expect(6.U)
      dut.io.attention_terminal.bits.transaction_identity.incarnation.expect(2.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
    }
  }
}
