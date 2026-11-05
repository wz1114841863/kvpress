package kvpress.routea.top

import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths, StandardOpenOption}
import kvpress.routea.params.RouteASynthesisControlProjectionProfile

/** Emit the full-profile control projection with PM1 selected only for its
  * Page Manager child.  Keeping the real measurement parent is required for
  * firtool to apply the same contextual port pruning as the frozen successor.
  * This does not select PM1 in the production Route-A top.
  */
object EmitPM1PageManagerChirrtl extends App {
  require(args.length == 1, "expected one output directory")
  val output = Paths.get(args.head)
  Files.createDirectories(output)
  val chirrtl = ChiselStage.emitCHIRRTL(RouteAControlProjectionGenerator.construct(
    RouteASynthesisControlProjectionProfile.parameters,
    bankPageManagerAllocatedLineSelector = true,
  ))
  require(chirrtl.contains("module route_a_control_projection"),
    "missing contextual Route-A control projection")
  require(chirrtl.contains("module route_a_page_manager_pm1"),
    "missing PM1 Page Manager module")
  Files.write(
    output.resolve("route_a_control_projection_pm1.fir"),
    chirrtl.getBytes(StandardCharsets.UTF_8),
    StandardOpenOption.CREATE_NEW,
    StandardOpenOption.WRITE,
  )
  println(s"PM1_PAGE_MANAGER_CHIRRTL_PASS output=$output")
}
