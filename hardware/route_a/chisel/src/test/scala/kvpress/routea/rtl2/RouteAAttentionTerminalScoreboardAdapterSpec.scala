package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.{Decoupled, RegEnable}
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteAAnchorWidths
import org.scalatest.funspec.AnyFunSpec

/** Testbench-only event payload for the frozen RTL2 attention_terminal record. */
final class AttentionTerminalScoreboardEvent extends Bundle {
  val transaction_identity = new TransactionIdentity
  val terminal_status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

/**
  * Testbench-only, zero-buffer terminal observation adapter. It observes a
  * named R6 outward terminal carrier and creates the event only on the same
  * accepted handshake. It is not a terminal producer or a production-top
  * component; event ready-low simply applies legal verification backpressure.
  */
final class RouteAAttentionTerminalScoreboardAdapter extends Module {
  override def desiredName: String = "testbench_route_a_attention_terminal_scoreboard_adapter"

  val io = IO(new Bundle {
    val attention_terminal_in = Flipped(RouteAChannels.attention_terminal_rsp)
    val attention_terminal_out = RouteAChannels.attention_terminal_rsp
    val scoreboard_event_out = Decoupled(new AttentionTerminalScoreboardEvent)
  })

  val terminal = io.attention_terminal_in.bits
  val statusLegal = terminal.terminal_status === 0.U || terminal.terminal_status === 1.U
  val offer = io.attention_terminal_in.valid && statusLegal
  // This is an atomic two-consumer observation: neither the real outward
  // terminal nor the testbench event may handshake alone. A blocked consumer
  // still sees a stable valid offer; its peer is suppressed only when ready
  // would otherwise permit a partial acceptance. The adapter is deliberately
  // a verification-only combinational barrier, not a FIFO.
  io.attention_terminal_out.valid := offer && (!io.attention_terminal_out.ready || io.scoreboard_event_out.ready)
  io.attention_terminal_out.bits := terminal
  io.scoreboard_event_out.valid := offer && (!io.scoreboard_event_out.ready || io.attention_terminal_out.ready)
  io.scoreboard_event_out.bits.transaction_identity := terminal.transaction_identity
  io.scoreboard_event_out.bits.terminal_status := terminal.terminal_status
  io.attention_terminal_in.ready := statusLegal && io.attention_terminal_out.ready && io.scoreboard_event_out.ready

  assert(io.attention_terminal_in.fire === io.attention_terminal_out.fire)
  assert(io.attention_terminal_out.fire === io.scoreboard_event_out.fire)
  val heldTerminal = RegEnable(io.attention_terminal_out.bits,
    io.attention_terminal_out.valid && !io.attention_terminal_out.ready)
  when(RegNext(io.attention_terminal_out.valid && !io.attention_terminal_out.ready, false.B)) {
    assert(io.attention_terminal_out.valid && io.attention_terminal_out.bits.asUInt === heldTerminal.asUInt)
  }
  val heldEvent = RegEnable(io.scoreboard_event_out.bits,
    io.scoreboard_event_out.valid && !io.scoreboard_event_out.ready)
  when(RegNext(io.scoreboard_event_out.valid && !io.scoreboard_event_out.ready, false.B)) {
    assert(io.scoreboard_event_out.valid && io.scoreboard_event_out.bits.asUInt === heldEvent.asUInt)
  }
}

/** RTL2.4.3 carrier-level event binding; no Python-oracle or numeric claim. */
final class RouteAAttentionTerminalScoreboardAdapterSpec extends AnyFunSpec with ChiselSim {
  private def driveTerminal(dut: RouteAAttentionTerminalScoreboardAdapter, rid: Int, incarnation: Int, status: Int): Unit = {
    dut.io.attention_terminal_in.bits.transaction_identity.request_id.poke(rid.U)
    dut.io.attention_terminal_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.attention_terminal_in.bits.terminal_status.poke(status.U)
  }

  private def init(dut: RouteAAttentionTerminalScoreboardAdapter): Unit = {
    driveTerminal(dut, 0, 0, 0)
    dut.io.attention_terminal_in.valid.poke(false.B)
    dut.io.attention_terminal_out.ready.poke(false.B)
    dut.io.scoreboard_event_out.ready.poke(false.B)
  }

  it("emits the exact event only with the same accepted outward success terminal") {
    simulate(new RouteAAttentionTerminalScoreboardAdapter) { dut =>
      init(dut)
      driveTerminal(dut, rid = 3, incarnation = 1, status = 0)
      dut.io.attention_terminal_in.valid.poke(true.B)
      dut.io.attention_terminal_in.ready.expect(false.B)
      dut.io.attention_terminal_out.valid.expect(true.B); dut.io.scoreboard_event_out.valid.expect(true.B)
      dut.io.attention_terminal_out.ready.poke(true.B); dut.io.scoreboard_event_out.ready.poke(true.B)
      dut.io.attention_terminal_out.valid.expect(true.B); dut.io.scoreboard_event_out.valid.expect(true.B)
      dut.io.attention_terminal_out.bits.transaction_identity.request_id.expect(3.U)
      dut.io.scoreboard_event_out.bits.transaction_identity.request_id.expect(3.U)
      dut.io.scoreboard_event_out.bits.transaction_identity.incarnation.expect(1.U)
      dut.io.scoreboard_event_out.bits.terminal_status.expect(0.U)
      dut.io.attention_terminal_in.ready.expect(true.B); dut.clock.step()
      dut.io.attention_terminal_in.valid.poke(false.B)
    }
  }

  it("prevents partial terminal/event acceptance under event backpressure and maps fault status exactly") {
    simulate(new RouteAAttentionTerminalScoreboardAdapter) { dut =>
      init(dut)
      driveTerminal(dut, rid = 4, incarnation = 2, status = 1)
      dut.io.attention_terminal_in.valid.poke(true.B)
      dut.io.attention_terminal_out.ready.poke(true.B); dut.io.scoreboard_event_out.ready.poke(false.B)
      dut.io.attention_terminal_in.ready.expect(false.B); dut.clock.step()
      dut.io.attention_terminal_out.valid.expect(false.B)
      dut.io.scoreboard_event_out.valid.expect(true.B)
      dut.io.scoreboard_event_out.bits.terminal_status.expect(1.U)
      dut.io.scoreboard_event_out.bits.transaction_identity.request_id.expect(4.U)
      dut.clock.step()
      dut.io.scoreboard_event_out.valid.expect(true.B)
      dut.io.scoreboard_event_out.bits.transaction_identity.request_id.expect(4.U)
      dut.io.scoreboard_event_out.ready.poke(true.B)
      dut.io.attention_terminal_out.valid.expect(true.B); dut.io.scoreboard_event_out.valid.expect(true.B)
      dut.io.attention_terminal_in.ready.expect(true.B)
      dut.clock.step(); dut.io.attention_terminal_in.valid.poke(false.B)
    }
  }

  it("emits no replay event after one accepted terminal") {
    simulate(new RouteAAttentionTerminalScoreboardAdapter) { dut =>
      init(dut)
      driveTerminal(dut, rid = 1, incarnation = 0, status = 0)
      dut.io.attention_terminal_in.valid.poke(true.B)
      dut.io.attention_terminal_out.ready.poke(true.B); dut.io.scoreboard_event_out.ready.poke(true.B)
      dut.io.attention_terminal_in.ready.expect(true.B); dut.clock.step()
      dut.io.attention_terminal_in.valid.poke(false.B)
      dut.io.attention_terminal_out.valid.expect(false.B); dut.io.scoreboard_event_out.valid.expect(false.B)
    }
  }
}
