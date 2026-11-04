package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

private final class RouteAPM1RegisteredSelectorMiter extends Module {
  val io = IO(new Bundle {
    val serial_in = Input(Bool())
    val equal = Output(Bool())
  })
  val original = Module(new RouteAPM1RegisteredSelectorNetwork(73, 8, banked = false))
  val candidate = Module(new RouteAPM1RegisteredSelectorNetwork(73, 8, banked = true))
  original.io.serial_in := io.serial_in
  candidate.io.serial_in := io.serial_in
  io.equal := original.io.selected_valid === candidate.io.selected_valid &&
    original.io.selected_index === candidate.io.selected_index
  assert(io.equal, "PM1 registered harness must preserve cycle-exact selector results")
}

final class RouteAPM1RegisteredSelectorSpec extends AnyFunSpec with ChiselSim {
  it("preserves cycle-exact results across zero, one, boundary and random shift histories") {
    simulate(new RouteAPM1RegisteredSelectorMiter) { d =>
      def shift(bit: Boolean): Unit = {
        d.io.serial_in.poke(bit.B)
        d.io.equal.expect(true.B)
        d.clock.step()
        d.io.equal.expect(true.B)
      }
      for (_ <- 0 until 80) shift(false)
      for (_ <- 0 until 80) shift(true)
      for (i <- 0 until 160) shift(i % 8 == 0 || i % 17 == 0)
      val random = new scala.util.Random(0x504d3152L)
      for (_ <- 0 until 1024) shift(random.nextBoolean())
    }
  }
}
