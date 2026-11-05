package kvpress.routea.top

import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths, StandardOpenOption}
import kvpress.routea.incremental.RouteAPageManager
import kvpress.routea.params.RouteASynthesisControlProjectionProfile

/** Emit only the full-profile PM1 Page Manager CHIRRTL for a controlled
  * characterized child-replacement screen. This does not select PM1 in the
  * production Route-A top.
  */
object EmitPM1PageManagerChirrtl extends App {
  require(args.length == 1, "expected one output directory")
  val output = Paths.get(args.head)
  Files.createDirectories(output)
  val chirrtl = ChiselStage.emitCHIRRTL(new RouteAPageManager(
    RouteASynthesisControlProjectionProfile.parameters,
    externalizeDescriptorBacking = true,
    bankAllocatedLineSelector = true,
  ))
  require(chirrtl.contains("module route_a_page_manager_pm1"),
    "missing PM1 Page Manager module")
  Files.write(
    output.resolve("route_a_page_manager_pm1.fir"),
    chirrtl.getBytes(StandardCharsets.UTF_8),
    StandardOpenOption.CREATE_NEW,
    StandardOpenOption.WRITE,
  )
  println(s"PM1_PAGE_MANAGER_CHIRRTL_PASS output=$output")
}
