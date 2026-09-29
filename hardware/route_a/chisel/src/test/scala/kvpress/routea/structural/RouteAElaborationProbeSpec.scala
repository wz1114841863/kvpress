package kvpress.routea.structural

import circt.stage.ChiselStage
import kvpress.routea.bootstrap.RouteAElaborationProbe
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/** No-model Chisel/CIRCT elaboration preflight; no Route-A behavior is tested. */
final class RouteAElaborationProbeSpec extends AnyFlatSpec with Matchers {
  behavior of "RouteAElaborationProbe"

  it should "emit a structural SystemVerilog shell in memory" in {
    val systemVerilog = ChiselStage.emitSystemVerilog(new RouteAElaborationProbe)

    systemVerilog should include("module RouteAElaborationProbe")
    systemVerilog should include("input coreClock")
    systemVerilog should include("destructiveReset")
  }
}
