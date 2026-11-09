package kvpress.routea

import circt.stage.ChiselStage
import kvpress.routea.top.RouteAMeasurementDut
import org.scalatest.funspec.AnyFunSpec

/** Local elaboration/firtool check only; no native simulation or synthesis. */
final class RouteAPersistentReadElaborationSpec extends AnyFunSpec {
  it("keeps v2 ports out of the default contour and lowers the complete v2 owner composition") {
    val p = RouteAPersistentPageReadTestParameters.small
    val legacy = ChiselStage.emitCHIRRTL(new RouteAMeasurementDut(p))
    val v2 = ChiselStage.emitCHIRRTL(new RouteAMeasurementDut(p, persistentReadEnabled = true))
    val optionalPort = "(?m)^\\s+(input|output) persistentRead\\s*:".r
    assert(optionalPort.findFirstIn(legacy).isEmpty)
    assert(optionalPort.findFirstIn(v2).nonEmpty)
    assert(!legacy.contains("module route_a_persistent_packed_read_controller_v2"))
    assert(v2.contains("module route_a_persistent_packed_read_controller_v2"))
    assert(v2.contains("module route_a_persistent_read_receipt_collector_v2"))
    assert(v2.contains("module route_a_r5_availability_array_boundary_persistent_v2"))
    assert(v2.contains("module route_a_m2_p3_wrapper"))
    val sv = ChiselStage.emitSystemVerilog(new RouteAMeasurementDut(p, persistentReadEnabled = true))
    assert(sv.contains("persistentRead_page_available_out_valid"))
    assert(sv.contains("persistentRead_page_select_in_valid"))
    println("PERSISTENT_READ_V2_ELABORATION_PASS legacy_optional_ports=0 v2_owners=1 firtool_lowering=1 native_simulation=0")
  }
}
