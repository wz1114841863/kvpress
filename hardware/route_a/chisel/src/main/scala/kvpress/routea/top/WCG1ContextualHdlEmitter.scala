package kvpress.routea.top

import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths, StandardOpenOption}
import kvpress.routea.params.RouteASynthesisControlProjectionProfile

/** Emit both variants under the real parent; production defaults stay off. */
object EmitWCG1ContextualChirrtl extends App {
  require(args.length == 2, "expected output directory and reference/gated side")
  val root = Paths.get(args.head)
  require(Set("reference", "gated").contains(args(1)), "unknown side")
  for (side <- Seq(args(1))) {
    val dir = root.resolve(side)
    require(!Files.exists(dir), "refusing to overwrite output")
    Files.createDirectories(dir)
    val fir = ChiselStage.emitCHIRRTL(RouteAControlProjectionGenerator.construct(
      RouteASynthesisControlProjectionProfile.parameters,
      bankPageManagerAllocatedLineSelector = false,
      gateCompactMembershipWords = side == "gated",
    ))
    Files.write(dir.resolve("route.fir"), fir.getBytes(StandardCharsets.UTF_8),
      StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
    println(s"WCG1_CONTEXTUAL_CHIRRTL_PASS side=$side PM1=false RD2=false")
  }
}
