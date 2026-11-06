package kvpress.routea.incremental

import chisel3._
import chisel3.util.HasBlackBoxInline
import kvpress.routea.params.RouteASkeletonParameters

/** WCG1 candidate primitive. No reset, pipeline or protocol state.
  * Simulation uses a low-phase transparent latch; the already screened
  * synthesis binding is the native positive-edge CKLNQ integrated gate.
  */
private final class RouteACompactWordClockGate extends BlackBox with HasBlackBoxInline {
  override def desiredName: String = "route_a_compact_word_clock_gate"
  val io = IO(new Bundle {
    val clock = Input(Clock())
    val enable = Input(Bool())
    val gated_clock = Output(Clock())
  })
  setInline("route_a_compact_word_clock_gate.sv", """module route_a_compact_word_clock_gate(input clock, input enable, output gated_clock);
`ifdef SYNTHESIS
  CKLNQD1BWP12T30P140LVT native_gate(.CP(clock), .E(enable), .TE(1'b0), .Q(gated_clock));
`else
  reg enable_low;
  always_latch begin
    if (!clock) enable_low = enable;
  end
  assign gated_clock = clock & enable_low;
`endif
endmodule
""")
}

/** Attach unreset, continuously readable words to the exact accepted join.
  * The two enables stay independent. Raw words retain their old contents
  * across reset/claim; the wrapper still owns every presence and control bit.
  */
object RouteACompactWordClocking {
  def attach(p: RouteASkeletonParameters, clock: Clock,
      memberEnable: Bool, suffixEnable: Bool, layer: UInt, ordinal: UInt,
      memberValue: RouteAM2P3MembershipRecord, suffixValue: RouteAM2P3PendingReadSuffix,
      members: Vec[Vec[RouteAM2P3MembershipRecord]],
      suffixes: Vec[Vec[RouteAM2P3PendingReadSuffix]]): Unit = {
    require(members.length == suffixes.length && members.head.length == 64)
    for (bank <- members.indices; record <- 0 until 64) {
      val selected = layer === bank.U && ordinal(5, 0) === record.U
      val memberGate = Module(new RouteACompactWordClockGate)
      memberGate.io.clock := clock
      memberGate.io.enable := memberEnable && selected
      val suffixGate = Module(new RouteACompactWordClockGate)
      suffixGate.io.clock := clock
      suffixGate.io.enable := suffixEnable && selected
      val memberWord = withClock(memberGate.io.gated_clock) { Reg(new RouteAM2P3MembershipRecord) }
      val suffixWord = withClock(suffixGate.io.gated_clock) { Reg(new RouteAM2P3PendingReadSuffix(p)) }
      memberWord := memberValue
      suffixWord := suffixValue
      members(bank)(record) := memberWord
      suffixes(bank)(record) := suffixWord
    }
  }
}
