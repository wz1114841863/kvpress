package kvpress.routea.top

import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths, StandardOpenOption}
import kvpress.routea.incremental.RouteAM2P3Wrapper
import kvpress.routea.params.RouteASynthesisControlProjectionProfile

/** Isolated real-wrapper comparison; never changes a production default. */
object EmitWCG1WrapperChirrtl extends App {
  require(args.length == 1, "expected new output directory")
  val root = Paths.get(args.head)
  require(!Files.exists(root), "refusing to overwrite output")
  Files.createDirectories(root)
  for (side <- Seq("reference", "gated")) {
    val dir = root.resolve(side)
    Files.createDirectories(dir)
    val fir = ChiselStage.emitCHIRRTL(new RouteAM2P3Wrapper(
      RouteASynthesisControlProjectionProfile.parameters,
      gateCompactMembershipWords = side == "gated",
    ))
    require(fir.contains("module route_a_m2_p3_wrapper"))
    Files.write(dir.resolve("wrapper.fir"), fir.getBytes(StandardCharsets.UTF_8),
      StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
    println(s"WCG1_WRAPPER_CHIRRTL_PASS side=$side")
  }
}
