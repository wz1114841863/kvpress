package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.{Decoupled, RegEnable, Valid}
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteAAnchorWidths
import org.scalatest.funspec.AnyFunSpec

/** Testbench-only encodings for RTL2.4.1's explicit R4 terminal scenario. */
object RouteAR4StubScenarioDisposition {
  final val Width = 2
  final val Success = 0
  final val NumericFault = 1
}

/**
  * Explicit verification input only: its 4096-bit value is opaque and has no
  * numeric, packet, source-order, or latency meaning.
  */
final class R4StubScenario extends Bundle {
  val transaction_identity = new TransactionIdentity
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val disposition = UInt(RouteAR4StubScenarioDisposition.Width.W)
  val normalized_value = UInt(RouteAAnchorWidths.NormalizedValueWidth.W)
}

/**
  * RTL2.4.1 testbench-only provider. It observes (but does not consume or
  * backpressure) R4's accepted active merge and offers exactly one matching
  * success XOR fault carrier. This module is deliberately compiled only in
  * test scope and is never instantiated by the production composition top.
  */
final class RouteAR4ResultStubProvider extends Module {
  override def desiredName: String = "testbench_route_a_r4_result_stub_provider"

  val io = IO(new Bundle {
    val active_merge_observation = Input(Valid(new MergeRequest))
    val scenario_in = Flipped(Decoupled(new R4StubScenario))
    val r4_result_stub_out = RouteAChannels.r4_result_stub
    val r4_numeric_fault_out = RouteAChannels.r4_numeric_fault
  })

  private def identityMatches(left: TransactionIdentity, right: TransactionIdentity): Bool =
    left.asUInt === right.asUInt

  val held = RegInit(false.B)
  val heldIdentity = Reg(new TransactionIdentity)
  val heldConsumer = Reg(UInt(RouteAAnchorWidths.ConsumerIdWidth.W))
  val heldDisposition = Reg(UInt(RouteAR4StubScenarioDisposition.Width.W))
  val heldValue = Reg(UInt(RouteAAnchorWidths.NormalizedValueWidth.W))
  // Retire a completed scenario until R4 has stopped exposing that exact
  // active incarnation. This blocks a duplicate offer in the handoff cycle.
  val completed = RegInit(false.B)
  val completedIdentity = Reg(new TransactionIdentity)

  val scenario = io.scenario_in.bits
  val active = io.active_merge_observation.bits
  val activeNonempty = io.active_merge_observation.valid && active.source_presence.orR
  val scenarioMatches = identityMatches(scenario.transaction_identity, active.transaction_identity)
  val consumerMatches = scenario.consumer_id === active.consumer_id
  val dispositionLegal = scenario.disposition === RouteAR4StubScenarioDisposition.Success.U ||
    scenario.disposition === RouteAR4StubScenarioDisposition.NumericFault.U
  val faultValueLegal = scenario.disposition =/= RouteAR4StubScenarioDisposition.NumericFault.U ||
    scenario.normalized_value === 0.U
  val completedSameActive = completed && io.active_merge_observation.valid &&
    identityMatches(completedIdentity, active.transaction_identity)

  io.scenario_in.ready := !held && !completedSameActive && activeNonempty &&
    scenarioMatches && consumerMatches && dispositionLegal && faultValueLegal

  io.r4_result_stub_out.valid := held &&
    heldDisposition === RouteAR4StubScenarioDisposition.Success.U
  io.r4_result_stub_out.bits.transaction_identity := heldIdentity
  io.r4_result_stub_out.bits.consumer_id := heldConsumer
  io.r4_result_stub_out.bits.normalized_value := heldValue
  io.r4_numeric_fault_out.valid := held &&
    heldDisposition === RouteAR4StubScenarioDisposition.NumericFault.U
  io.r4_numeric_fault_out.bits.transaction_identity := heldIdentity
  io.r4_numeric_fault_out.bits.consumer_id := heldConsumer

  when(completed && (!io.active_merge_observation.valid ||
    !identityMatches(completedIdentity, active.transaction_identity))) {
    completed := false.B
  }
  when(io.scenario_in.fire) {
    held := true.B
    heldIdentity := scenario.transaction_identity
    heldConsumer := scenario.consumer_id
    heldDisposition := scenario.disposition
    heldValue := scenario.normalized_value
  }
  when(io.r4_result_stub_out.fire || io.r4_numeric_fault_out.fire) {
    held := false.B
    completed := true.B
    completedIdentity := heldIdentity
  }

  assert(!(io.r4_result_stub_out.valid && io.r4_numeric_fault_out.valid))
  when(io.scenario_in.fire) {
    assert(activeNonempty && scenarioMatches && consumerMatches && dispositionLegal && faultValueLegal)
  }
  val heldResult = RegEnable(io.r4_result_stub_out.bits,
    io.r4_result_stub_out.valid && !io.r4_result_stub_out.ready)
  when(RegNext(io.r4_result_stub_out.valid && !io.r4_result_stub_out.ready, false.B)) {
    assert(io.r4_result_stub_out.valid && io.r4_result_stub_out.bits.asUInt === heldResult.asUInt)
  }
  val heldFault = RegEnable(io.r4_numeric_fault_out.bits,
    io.r4_numeric_fault_out.valid && !io.r4_numeric_fault_out.ready)
  when(RegNext(io.r4_numeric_fault_out.valid && !io.r4_numeric_fault_out.ready, false.B)) {
    assert(io.r4_numeric_fault_out.valid && io.r4_numeric_fault_out.bits.asUInt === heldFault.asUInt)
  }
}

/** RTL2.4.1 isolated provider checks; no numeric R4 or R6 integration claim. */
final class RouteAR4ResultStubProviderSpec extends AnyFunSpec with ChiselSim {
  private def driveIdentity(identity: TransactionIdentity, requestId: Int, incarnation: Int): Unit = {
    identity.request_id.poke(requestId.U)
    identity.incarnation.poke(incarnation.U)
  }

  private def driveActive(dut: RouteAR4ResultStubProvider, valid: Boolean, requestId: Int, incarnation: Int, sourcePresence: Int, consumer: Int = 0): Unit = {
    dut.io.active_merge_observation.valid.poke(valid.B)
    driveIdentity(dut.io.active_merge_observation.bits.transaction_identity, requestId, incarnation)
    dut.io.active_merge_observation.bits.source_presence.poke(sourcePresence.U)
    dut.io.active_merge_observation.bits.consumer_id.poke(consumer.U)
  }

  private def driveScenario(dut: RouteAR4ResultStubProvider, requestId: Int, incarnation: Int, disposition: Int, value: BigInt, consumer: Int = 0): Unit = {
    driveIdentity(dut.io.scenario_in.bits.transaction_identity, requestId, incarnation)
    dut.io.scenario_in.bits.consumer_id.poke(consumer.U)
    dut.io.scenario_in.bits.disposition.poke(disposition.U)
    dut.io.scenario_in.bits.normalized_value.poke(value.U)
  }

  private def init(dut: RouteAR4ResultStubProvider): Unit = {
    driveActive(dut, valid = false, requestId = 0, incarnation = 0, sourcePresence = 0)
    driveScenario(dut, requestId = 0, incarnation = 0, RouteAR4StubScenarioDisposition.Success, BigInt(0))
    dut.io.scenario_in.valid.poke(false.B)
    dut.io.r4_result_stub_out.ready.poke(false.B)
    dut.io.r4_numeric_fault_out.ready.poke(false.B)
  }

  it("accepts an exact success scenario and holds the opaque result through ready-low") {
    simulate(new RouteAR4ResultStubProvider) { dut =>
      init(dut)
      driveActive(dut, valid = true, requestId = 7, incarnation = 2, sourcePresence = 3)
      driveScenario(dut, requestId = 7, incarnation = 2, RouteAR4StubScenarioDisposition.Success, BigInt("1234", 16))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(true.B)
      dut.clock.step(); dut.io.scenario_in.valid.poke(false.B)
      dut.io.r4_result_stub_out.valid.expect(true.B); dut.io.r4_numeric_fault_out.valid.expect(false.B)
      dut.io.r4_result_stub_out.bits.normalized_value.expect("h1234".U)
      driveScenario(dut, requestId = 6, incarnation = 2, RouteAR4StubScenarioDisposition.Success, BigInt(0))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(false.B)
      dut.clock.step(); dut.io.scenario_in.valid.poke(false.B)
      dut.io.r4_result_stub_out.valid.expect(true.B); dut.io.r4_result_stub_out.bits.transaction_identity.request_id.expect(7.U)
      dut.io.r4_result_stub_out.bits.normalized_value.expect("h1234".U)
      dut.io.r4_result_stub_out.ready.poke(true.B); dut.clock.step(); dut.io.r4_result_stub_out.ready.poke(false.B)
      driveScenario(dut, requestId = 7, incarnation = 2, RouteAR4StubScenarioDisposition.Success, BigInt(0))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(false.B)
    }
  }

  it("maps an exact zero-valued numeric-fault scenario to only the fault carrier") {
    simulate(new RouteAR4ResultStubProvider) { dut =>
      init(dut)
      driveActive(dut, valid = true, requestId = 5, incarnation = 1, sourcePresence = 7)
      driveScenario(dut, requestId = 5, incarnation = 1, RouteAR4StubScenarioDisposition.NumericFault, BigInt(1))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(false.B)
      driveScenario(dut, requestId = 5, incarnation = 1, RouteAR4StubScenarioDisposition.NumericFault, BigInt(0))
      dut.io.scenario_in.ready.expect(true.B); dut.clock.step(); dut.io.scenario_in.valid.poke(false.B)
      dut.io.r4_result_stub_out.valid.expect(false.B); dut.io.r4_numeric_fault_out.valid.expect(true.B)
      dut.io.r4_numeric_fault_out.bits.transaction_identity.request_id.expect(5.U)
      dut.clock.step(); dut.io.r4_numeric_fault_out.valid.expect(true.B)
      dut.io.r4_numeric_fault_out.ready.poke(true.B); dut.clock.step(); dut.io.r4_numeric_fault_out.ready.poke(false.B)
    }
  }

  it("fails closed before an active merge and on empty stale identity/consumer mismatched or malformed scenarios") {
    simulate(new RouteAR4ResultStubProvider) { dut =>
      init(dut)
      driveScenario(dut, requestId = 1, incarnation = 0, RouteAR4StubScenarioDisposition.Success, BigInt(0))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(false.B)
      driveActive(dut, valid = true, requestId = 1, incarnation = 0, sourcePresence = 0)
      dut.io.scenario_in.ready.expect(false.B)
      driveActive(dut, valid = true, requestId = 2, incarnation = 0, sourcePresence = 1)
      dut.io.scenario_in.ready.expect(false.B)
      driveActive(dut, valid = true, requestId = 2, incarnation = 0, sourcePresence = 1, consumer = 2)
      driveScenario(dut, requestId = 2, incarnation = 0, RouteAR4StubScenarioDisposition.Success, BigInt(0), consumer = 1)
      dut.io.scenario_in.ready.expect(false.B)
      driveScenario(dut, requestId = 2, incarnation = 0, disposition = 2, value = BigInt(0))
      dut.io.scenario_in.ready.expect(false.B)
      driveScenario(dut, requestId = 2, incarnation = 0, RouteAR4StubScenarioDisposition.NumericFault, BigInt(9))
      dut.io.scenario_in.ready.expect(false.B)
      dut.io.scenario_in.valid.poke(false.B)
      dut.io.r4_result_stub_out.valid.expect(false.B); dut.io.r4_numeric_fault_out.valid.expect(false.B)
    }
  }

  it("reset discards a held scenario and an old incarnation cannot match a reused request ID") {
    simulate(new RouteAR4ResultStubProvider) { dut =>
      init(dut)
      driveActive(dut, valid = true, requestId = 6, incarnation = 1, sourcePresence = 1)
      driveScenario(dut, requestId = 6, incarnation = 1, RouteAR4StubScenarioDisposition.Success, BigInt("55", 16))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(true.B); dut.clock.step()
      dut.io.r4_result_stub_out.valid.expect(true.B)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.scenario_in.valid.poke(false.B); dut.io.r4_result_stub_out.valid.expect(false.B); dut.io.r4_numeric_fault_out.valid.expect(false.B)
      driveActive(dut, valid = true, requestId = 6, incarnation = 2, sourcePresence = 4)
      driveScenario(dut, requestId = 6, incarnation = 1, RouteAR4StubScenarioDisposition.Success, BigInt(0))
      dut.io.scenario_in.valid.poke(true.B); dut.io.scenario_in.ready.expect(false.B)
      driveScenario(dut, requestId = 6, incarnation = 2, RouteAR4StubScenarioDisposition.Success, BigInt("66", 16))
      dut.io.scenario_in.ready.expect(true.B)
    }
  }
}
